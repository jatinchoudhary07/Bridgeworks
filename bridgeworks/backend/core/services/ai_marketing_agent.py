"""
AI Marketing Agent
==================
Uses Gemini to analyze campaign and adset performance data and provide
highly granular, actionable insights: best performers, scaling opportunities,
funnel bottlenecks, ad fatigue, and budget recommendations.
"""
import logging
import json
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import CampaignDailyMetric, AdSetDailyMetric, AdDailyMetric
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Global client for reusing connection pools and preventing GC closure during streams
genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


# ─── Industry Benchmarks (Indian D2C averages) ───────────────────────────
INDUSTRY_BENCHMARKS = {
    "d2c_india_avg_roas": 3.0,
    "d2c_india_avg_cpa_inr": 400,
    "d2c_india_avg_ctr_pct": 1.5,
    "d2c_india_avg_cvr_pct": 2.5,
    "d2c_india_avg_cpc_inr": 15,
    "d2c_india_avg_cpm_inr": 250,
    "note": "Approximate averages for Indian D2C Meta/Google campaigns, use for directional benchmarking only."
}


# ═══════════════════════════════════════════════════════════════════════════
# AGENT MANAGER — System Prompt Orchestrator
# Fetches active global rules + correction rules from DB on every call.
# ═══════════════════════════════════════════════════════════════════════════

def build_marketing_system_prompt(base_prompt: str) -> str:
    """
    Dynamically assembles the final system prompt for Marketing AURA by
    appending all active global override rules and learned correction rules.

    Called on EVERY Gemini API invocation — changes to rules take effect
    immediately without any code deploy.

    Args:
        base_prompt: The full base system prompt (CMO_CAPABILITIES etc.)

    Returns:
        Enriched system prompt string with rules injected.
    """
    # ── 0. Neutralise any hardcoded Gen Z identity from the base prompt ──────
    # These phrases are remnants of the original prompt. If the user selects
    # a different persona we must remove them so they don't override the choice.
    GENZ_PHRASES_TO_STRIP = [
        "You are a cracked performance marketing analyst",
        "You have zero chill and pure growth rizz.",
        "You have zero chill and pure growth rizz",
        "Stay grounded but keep the vibe gen-z.",
        "Stay grounded but keep the vibe gen-z",
        "keep the vibe gen-z",
        "pure growth rizz",
        "zero chill",
        "no cap.",
        "fr fr.",
        "bussin",
    ]
    PERSONA_NEUTRAL_IDENTITY = (
        "You are a professional, expert performance marketing analyst for an Indian D2C brand. "
        "Analyse the provided Meta Ads data (Campaign, AdSet, and Ad level) meticulously. "
        "Identify top performers, areas of improvement, and the most effective creatives."
    )

    PERSONA_DEFINITIONS = {
        'default': (
            "COMMUNICATION STYLE: Professional & Analytical\n"
            "Respond as a sharp, objective performance marketing analyst. "
            "Be data-forward, structured, and clear. Use professional language."
        ),
        'warm': (
            "COMMUNICATION STYLE: Warm & Encouraging\n"
            "Adopt a warm, encouraging, and supportive tone. Celebrate wins genuinely. "
            "Frame negatives constructively ('Here's an opportunity to improve...'). "
            "Use friendly but sharp language."
        ),
        'calm': (
            "COMMUNICATION STYLE: Calm & Measured\n"
            "Respond in a calm, composed tone. Avoid hype or alarm. "
            "Use measured language like 'The data suggests...', 'It appears that...'. "
            "Present good and bad news evenly."
        ),
        'genz': (
            "COMMUNICATION STYLE: Gen Z (Casual & Energetic)\n"
            "Respond like a sharp Gen Z marketing strategist. Use casual language, "
            "pop-culture references, and energy. Use phrases like 'no cap', 'lowkey', "
            "'this slaps', 'main character energy'. Be data-accurate but conversational."
        ),
        'aggressive': (
            "COMMUNICATION STYLE: Aggressive & Direct\n"
            "Be bold, direct, and unapologetically honest. No sugarcoating. "
            "Call out underperforming campaigns bluntly. Use strong action language: "
            "'Kill this campaign', 'This is bleeding money', 'Scale this NOW'."
        ),
        'zen': (
            "COMMUNICATION STYLE: Zen & Minimal\n"
            "Respond with elegant brevity. Say more with less. Avoid filler phrases. "
            "Use short paragraphs and impactful sentences. Quality of insight over quantity."
        ),
    }

    try:
        from core.models import MarketingAgentGlobalRule, MarketingCorrectionRule, MarketingAgentConfiguration
        from django.utils import timezone as tz
        from django.db import models

        # Fetch active persona
        config = MarketingAgentConfiguration.objects.filter(is_active=True).first()
        active_persona = config.persona if (config and config.persona) else 'default'
        persona_def = PERSONA_DEFINITIONS.get(active_persona, PERSONA_DEFINITIONS['default'])

        # Clean the base prompt of Gen Z identity phrases
        cleaned_prompt = base_prompt
        # Only strip if persona is NOT genz
        if active_persona != 'genz':
            for phrase in GENZ_PHRASES_TO_STRIP:
                cleaned_prompt = cleaned_prompt.replace(phrase, '')
            # If the base prompt starts with a cracked/rizz identity, replace it
            if "cracked" in cleaned_prompt.lower() or "rizz" in cleaned_prompt.lower():
                # Replace first paragraph (identity line) with neutral version
                lines = cleaned_prompt.split('\n')
                lines[0] = PERSONA_NEUTRAL_IDENTITY
                cleaned_prompt = '\n'.join(lines)

        # ── PERSONA LOCK at the very TOP — highest priority ──────────────────
        persona_lock_header = (
            f"## 🎯 CRITICAL — ACTIVE COMMUNICATION PERSONA\n"
            f"This instruction OVERRIDES any other tone or personality described elsewhere in this prompt.\n"
            f"{persona_def}\n"
            f"You MUST adopt this communication style for EVERY response in this conversation. "
            f"Do not revert to any other tone under any circumstance.\n"
            f"---\n\n"
        )

        prompt_parts = [persona_lock_header, cleaned_prompt]

        # ── 1. Global Override Rules ──────────────────────────────────────────
        global_rules = list(
            MarketingAgentGlobalRule.objects.filter(
                is_active=True
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=tz.now())
            ).order_by('-priority', '-created_at')
        )

        if global_rules:
            prompt_parts.append(
                "\n\n---\n"
                "## ⚠️ CRITICAL OVERRIDE RULES — READ FIRST\n"
                "The following rules are set by the business owner and override everything else.\n"
                "Apply ALL of them to EVERY response, no exceptions:"
            )
            for rule in global_rules:
                prompt_parts.append(f"- {rule.rule_text}")

        # ── 2. Learned Correction Rules ───────────────────────────────────────
        corrections = list(
            MarketingCorrectionRule.objects.filter(is_active=True).order_by('-created_at')
        )

        if corrections:
            prompt_parts.append(
                "\n\n---\n"
                "## 📋 LEARNED CORRECTIONS — MISTAKES YOU MUST NEVER REPEAT\n"
                "The following corrections were flagged by the team after reviewing past responses:\n"
            )
            for c in corrections:
                prompt_parts.append(f"\n**Issue:** {c.bad_behavior_description}")
                prompt_parts.append(f"**Rule:** {c.corrected_instruction}")
                if c.example_bad_response and c.example_good_response:
                    prompt_parts.append(f"**Example of what NOT to do:** {c.example_bad_response[:300]}")
                    prompt_parts.append(f"**Example of what TO do:** {c.example_good_response[:300]}")

        # ── 3. Persona REINFORCEMENT at the very END — final instruction wins ─
        prompt_parts.append(
            f"\n\n---\n"
            f"## 🔒 FINAL REMINDER — PERSONA LOCK\n"
            f"Your active persona is: **{active_persona.upper()}**\n"
            f"{persona_def}\n"
            f"This is your final instruction. Respond in this style now."
        )

        return "\n".join(prompt_parts)

    except Exception as e:
        # Fail gracefully — return the base prompt unmodified rather than break the AI
        logger.warning(f"Agent Manager: Failed to build enriched system prompt: {e}")
        return base_prompt



# ═══════════════════════════════════════════════════════════════════════════
# INTRADAY PACING HELPER
# Answers questions like "how many orders did I have at this time yesterday?"
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_intraday_pacing(org):
    """
    Returns a real-time pacing snapshot comparing Shopify orders up to the
    current minute today vs the exact same time yesterday.

    Gives the AI the ability to answer:
      "I have 5 purchases at 1pm today, how many did I have at 1pm yesterday?"
    """
    try:
        from core.models import Order
        from django.db.models import Sum, Count
        import pytz

        # Use IST timezone so times match what the user sees
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = timezone.now().astimezone(IST)

        today_date     = now_ist.date()
        yesterday_date = today_date - timedelta(days=1)
        current_hour   = now_ist.hour
        current_minute = now_ist.minute

        org_id = str(org.id) if hasattr(org, 'id') else str(org)

        # Build UTC cutoff datetimes for exact "same-minute" comparisons
        # e.g. if now_ist = 13:06 IST → cutoff_today_utc = 07:36 UTC
        from datetime import datetime as dt
        cutoff_today_utc = now_ist.astimezone(pytz.utc)
        cutoff_yesterday_utc = cutoff_today_utc - timedelta(days=1)

        # Start-of-day boundaries in UTC
        today_start_utc = IST.localize(dt.combine(today_date, dt.min.time())).astimezone(pytz.utc)
        yesterday_start_utc = IST.localize(dt.combine(yesterday_date, dt.min.time())).astimezone(pytz.utc)

        def _query(day_start_utc, cutoff_utc):
            """Orders placed from start-of-day (IST) up to the cutoff moment."""
            return Order.objects.filter(
                org_id=org_id,
                created_at__gte=day_start_utc,
                created_at__lte=cutoff_utc,
            ).exclude(
                financial_status__in=['cancelled', 'refunded', 'voided']
            )

        today_qs     = _query(today_start_utc,     cutoff_today_utc)
        yesterday_qs = _query(yesterday_start_utc, cutoff_yesterday_utc)

        today_agg     = today_qs.aggregate(orders=Count('id'),     revenue=Sum('total_price'))
        yesterday_agg = yesterday_qs.aggregate(orders=Count('id'), revenue=Sum('total_price'))

        today_orders     = today_agg['orders']     or 0
        today_revenue    = float(today_agg['revenue'] or 0)
        yesterday_orders = yesterday_agg['orders'] or 0
        yesterday_revenue = float(yesterday_agg['revenue'] or 0)

        orders_delta_pct = (
            round((today_orders - yesterday_orders) / yesterday_orders * 100, 1)
            if yesterday_orders > 0 else None
        )
        revenue_delta_pct = (
            round((today_revenue - yesterday_revenue) / yesterday_revenue * 100, 1)
            if yesterday_revenue > 0 else None
        )

        # Full-day yesterday for day-over-day context
        full_yesterday = Order.objects.filter(
            org_id=org_id,
            created_at__date=yesterday_date,
        ).exclude(
            financial_status__in=['cancelled', 'refunded', 'voided']
        ).aggregate(orders=Count('id'), revenue=Sum('total_price'))

        return {
            "snapshot_time": now_ist.strftime('%I:%M %p IST, %d %b %Y'),
            "current_time_label": now_ist.strftime('%I:%M %p'),
            "today": {
                "date": str(today_date),
                "orders_so_far": today_orders,
                "revenue_so_far": round(today_revenue, 2),
            },
            "yesterday_same_time": {
                "date": str(yesterday_date),
                "orders_at_same_time": yesterday_orders,
                "revenue_at_same_time": round(yesterday_revenue, 2),
            },
            "yesterday_full_day": {
                "total_orders": full_yesterday['orders'] or 0,
                "total_revenue": round(float(full_yesterday['revenue'] or 0), 2),
            },
            "pacing": {
                "orders_delta_pct": orders_delta_pct,
                "revenue_delta_pct": revenue_delta_pct,
                "orders_ahead": today_orders > yesterday_orders,
                "revenue_ahead": today_revenue > yesterday_revenue,
            },
            "note": "Shopify orders only. Excludes cancelled/refunded/voided orders."
        }
    except Exception as e:
        logger.warning(f"Intraday pacing fetch failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# NEW DATA HELPERS — Each fetches one context layer for the AI payload
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_daily_trends(org, start_date, end_date):
    """Day-by-day spend/revenue/purchases for trend detection."""
    try:
        rows = list(
            CampaignDailyMetric.objects.filter(
                credential__shop=org, credential__platform='Meta',
                date__gte=start_date, date__lte=end_date
            ).values('date').annotate(
                spend=Sum('spend'), revenue=Sum('revenue'),
                purchases=Sum('purchases'), impressions=Sum('impressions'),
                clicks=Sum('clicks')
            ).order_by('date')
        )
        for r in rows:
            s = float(r['spend'] or 0)
            rev = float(r['revenue'] or 0)
            r['roas'] = round(rev / s, 2) if s > 0 else 0
            r['cpa'] = round(s / r['purchases'], 2) if r['purchases'] else 0
        return rows
    except Exception as e:
        logger.warning(f"Failed to fetch daily trends: {e}")
        return []


def _fetch_google_payload(org, start_date, end_date):
    """Google Ads campaign + search term data (if connected)."""
    try:
        from core.models import GoogleAdsCredential, GoogleCampaignDailyMetric, GoogleSearchTermMetric
        cred = GoogleAdsCredential.objects.filter(shop=org, is_active=True).first()
        if not cred:
            return None

        campaigns = list(
            GoogleCampaignDailyMetric.objects.filter(
                credential=cred, date__gte=start_date, date__lte=end_date
            ).values('campaign_name').annotate(
                spend=Sum('spend'), revenue=Sum('revenue'),
                conversions=Sum('conversions'), impressions=Sum('impressions'),
                clicks=Sum('clicks')
            ).order_by('-spend')[:30]
        )
        for c in campaigns:
            s = float(c['spend'] or 0)
            c['roas'] = round(float(c['revenue'] or 0) / s, 2) if s > 0 else 0
            c['cpa'] = round(s / float(c['conversions']), 2) if c['conversions'] else 0

        search_terms = list(
            GoogleSearchTermMetric.objects.filter(
                credential=cred, date__gte=start_date, date__lte=end_date
            ).values('search_term', 'campaign_name').annotate(
                spend=Sum('spend'), clicks=Sum('clicks'),
                conversions=Sum('conversions'), revenue=Sum('revenue')
            ).order_by('-spend')[:20]
        )

        return {"google_campaigns": campaigns, "google_search_terms": search_terms}
    except Exception as e:
        logger.warning(f"Failed to fetch Google Ads payload: {e}")
        return None


def _fetch_attribution_summary(org, start_date, end_date):
    """Real order-level channel attribution from OrderAttribution model."""
    try:
        from core.models import OrderAttribution, Order
        attrs = (
            OrderAttribution.objects.filter(
                order__org_id=org.organization_id,
                order__created_at__date__gte=start_date,
                order__created_at__date__lte=end_date,
            )
            .values('channel')
            .annotate(
                orders=Count('id'),
                revenue=Sum('order__total_price')
            )
            .order_by('-revenue')
        )
        summary = {}
        for a in attrs:
            ch = a['channel'] or 'unknown'
            summary[ch] = {
                "orders": a['orders'],
                "revenue": float(a['revenue'] or 0)
            }
        return summary if summary else None
    except Exception as e:
        logger.warning(f"Failed to fetch attribution summary: {e}")
        return None


def _fetch_top_products_from_ads(org, start_date, end_date):
    """Top products purchased through paid channels."""
    try:
        from core.models import Order, LineItem, OrderAttribution
        paid_channels = ['meta_paid', 'google_paid', 'tiktok_paid', 'pinterest_paid', 'snapchat_paid']
        products = (
            LineItem.objects.filter(
                order__org_id=org.organization_id,
                order__created_at__date__gte=start_date,
                order__created_at__date__lte=end_date,
                order__attribution__channel__in=paid_channels
            )
            .values('title')
            .annotate(
                orders=Count('order', distinct=True),
                total_qty=Sum('quantity'),
                revenue=Sum(F('price') * F('quantity'))
            )
            .order_by('-revenue')[:15]
        )
        return [
            {"product": p['title'], "orders": p['orders'],
             "qty_sold": p['total_qty'], "revenue": float(p['revenue'] or 0)}
            for p in products
        ] or None
    except Exception as e:
        logger.warning(f"Failed to fetch top products from ads: {e}")
        return None


def _fetch_financial_context(org):
    """COGS, shipping, targets from StoreFinancials."""
    try:
        from core.models import StoreFinancials, MarketingSettings
        fin = StoreFinancials.objects.filter(shop=org).first()
        ms = MarketingSettings.objects.filter(shop=org).first()
        if not fin:
            return None
        return {
            "cogs_pct": float(fin.average_cogs_percentage),
            "shipping_per_order_inr": float(fin.shipping_cost_per_order),
            "target_roas": float(fin.target_roas),
            "target_cpa_inr": float(fin.target_cpa),
            "gst_rate_pct": float(ms.gst_rate) if ms else 18.0
        }
    except Exception as e:
        logger.warning(f"Failed to fetch financial context: {e}")
        return None


def _fetch_shopify_revenue(org, start_date, end_date):
    """Actual Shopify order-level revenue for cross-verification."""
    try:
        from core.models import Order
        qs = Order.objects.filter(
            org_id=org.organization_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        total = qs.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_price'),
            avg_order_value=Avg('total_price'),
        )
        # COD vs Prepaid breakdown
        cod_keywords = ['cash on delivery (cod)', 'cash_on_delivery', 'cash on delivery', 'cod']
        cod_count = 0
        for pgn in qs.values_list('payment_gateway_names', flat=True):
            if not pgn:
                continue
            if isinstance(pgn, str):
                import json
                try:
                    pgn = json.loads(pgn)
                except json.JSONDecodeError:
                    pgn = [pgn]
            if not isinstance(pgn, list):
                pgn = [str(pgn)]
            
            is_cod = False
            for gateway in pgn:
                gw_lower = str(gateway).lower()
                if any(kw in gw_lower for kw in cod_keywords):
                    is_cod = True
                    break
            if is_cod:
                cod_count += 1
        return {
            "total_orders": total['total_orders'] or 0,
            "total_revenue_inr": float(total['total_revenue'] or 0),
            "avg_order_value_inr": round(float(total['avg_order_value'] or 0), 2),
            "cod_orders": cod_count,
            "prepaid_orders": (total['total_orders'] or 0) - cod_count,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch Shopify revenue: {e}")
        return None


def _fetch_retention_stats(org, start_date, end_date):
    """New vs Returning customer breakdown."""
    try:
        from core.services.profitability_service import get_retention_breakdown
        return get_retention_breakdown(org.organization_id, start_date, end_date)
    except Exception as e:
        logger.warning(f"Failed to fetch retention stats: {e}")
        return None


def _fetch_goal_tracking(org, start_date, end_date):
    """CPA/ROAS actual vs targets."""
    try:
        from core.services.profitability_service import get_goal_tracker
        return get_goal_tracker(org, start_date, end_date)
    except Exception as e:
        logger.warning(f"Failed to fetch goal tracking: {e}")
        return None


def _fetch_merchandising_data(org, start_date, end_date):
    """Fetch product-level inventory from local ShopifyProductCache DB.
    Kept fresh by Shopify webhooks (products/create, products/update,
    products/delete, inventory_levels/update) and periodic sync.
    """
    try:
        from inventory.models import ShopifyProductCache

        cached_products = list(
            ShopifyProductCache.objects.filter(
                organization_id=org.organization_id
            ).values_list('data', flat=True)
        )

        # Auto-sync if the cache is completely empty (first run)
        if not cached_products:
            logger.info("No cached Shopify products — triggering initial sync...")
            try:
                from core.models import ShopCredentials
                from inventory.management.commands.sync_shopify_cache import _sync_org
                creds = ShopCredentials.objects.get(organization_id=org.organization_id)
                _sync_org(creds, force=True)
                cached_products = list(
                    ShopifyProductCache.objects.filter(
                        organization_id=org.organization_id
                    ).values_list('data', flat=True)
                )
            except Exception as sync_err:
                logger.warning(f"Initial Shopify sync failed: {sync_err}")
                return None

        if not cached_products:
            return None

        products = []
        for data in cached_products:
            if not isinstance(data, dict):
                continue
            variants = []
            total_stock = 0
            oos_sizes = []
            for v in data.get('variants', []):
                qty = v.get('stock', 0) or 0
                total_stock += qty
                size_name = v.get('title', 'Default')
                if qty <= 0:
                    oos_sizes.append(size_name)
                variants.append({
                    'size': size_name,
                    'sku': v.get('sku', ''),
                    'stock': qty,
                })

            products.append({
                'title': data.get('name', ''),
                'total_stock': total_stock,
                'oos_sizes': oos_sizes,
                'variants': variants,
            })
        return products
    except Exception as e:
        logger.warning(f"Failed to fetch merchandising data: {e}")
        return None

def _fetch_shopify_order_intelligence(org, start_date, end_date):
    """
    Fetches SKU-level data directly from Shopify orders (COD vs Prepaid, 
    cancellations, new vs repeat customers, avg units per order).
    """
    try:
        from core.models import Order, LineItem
        from django.db.models import Sum, Count, F, Q

        org_id = str(org.id) if hasattr(org, 'id') else str(org)

        # Get all orders in date range
        line_items = LineItem.objects.filter(
            order__org_id=org_id,
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date
        ).values('sku', 'title').annotate(
            total_quantity=Sum('quantity'),
            total_sales=Sum(F('quantity') * F('price')),
            order_count=Count('order', distinct=True),
            cancelled_orders=Count('order', filter=Q(order__financial_status__iexact='cancelled') | Q(order__status__iexact='Cancelled'), distinct=True),
            new_customers=Count('order', filter=Q(order__previous_order_count=0), distinct=True),
            repeat_customers=Count('order', filter=Q(order__previous_order_count__gt=0), distinct=True),
        ).order_by('-total_sales')[:50]

        sku_stats = {}
        for li in line_items:
            sku = li['sku']
            if not sku: continue
            sku_stats[sku] = {
                'title': li['title'],
                'total_sales': float(li['total_sales'] or 0),
                'total_quantity': li['total_quantity'] or 0,
                'order_count': li['order_count'] or 0,
                'cancelled_orders': li['cancelled_orders'] or 0,
                'new_customers': li['new_customers'] or 0,
                'repeat_customers': li['repeat_customers'] or 0,
                'cod_orders': 0,
                'prepaid_orders': 0,
            }

        top_skus = list(sku_stats.keys())
        if top_skus:
            # Check COD on Orders associated with these SKUs
            li_orders = LineItem.objects.filter(
                order__org_id=org_id,
                order__created_at__date__gte=start_date,
                order__created_at__date__lte=end_date,
                sku__in=top_skus
            ).select_related('order')

            for li in li_orders:
                sku = li.sku
                if not sku or sku not in sku_stats:
                    continue
                pg = li.order.payment_gateway_names
                is_cod = False
                if pg and isinstance(pg, list):
                    is_cod = any('cod' in str(p).lower() or 'cash on delivery' in str(p).lower() for p in pg)
                elif pg and isinstance(pg, str):
                    is_cod = 'cod' in pg.lower() or 'cash on delivery' in pg.lower()
                
                if is_cod:
                    sku_stats[sku]['cod_orders'] += 1
                else:
                    sku_stats[sku]['prepaid_orders'] += 1

        results = []
        for sku, data in sku_stats.items():
            oc = data['order_count']
            results.append({
                'sku': sku,
                'title': data['title'],
                'total_sales': data['total_sales'],
                'order_count': oc,
                'cancelled_orders': data['cancelled_orders'],
                'cod_percentage': round((data['cod_orders'] / oc * 100), 1) if oc > 0 else 0,
                'new_customers': data['new_customers'],
                'repeat_customers': data['repeat_customers'],
                'avg_units_per_order': round((data['total_quantity'] / oc), 1) if oc > 0 else 0
            })

        return sorted(results, key=lambda x: x['total_sales'], reverse=True)
    except Exception as e:
        logger.warning(f"Failed to fetch Shopify order intelligence: {e}")
        return None



def run_marketing_analysis(org, start_date=None, end_date=None, model_name='gemini-2.5-flash-lite'):
    """
    Aggregates campaign, adset, and individual ad data for the given date range 
    and sends to Gemini for deep, structured analysis.
    """
    payload = _fetch_marketing_payload(org, start_date, end_date)
    if "error" in payload: return payload

    data_json = json.dumps(payload, cls=DecimalEncoder, indent=2)

    from core.models import MarketingAgentConfiguration
    config = MarketingAgentConfiguration.objects.filter(is_active=True).first()
    
    if config:
        system_prompt = config.system_prompt
        if config.model_name and model_name == 'gemini-2.5-pro': # Override if default
            model_name = config.model_name
    else:
        system_prompt = """You are an expert performance marketing analyst for an Indian D2C brand.
Analyze the provided Meta Ads data (Campaign, AdSet, and Ad level) meticulously.
Identify top performers, areas of improvement, and the most effective creatives.

Provide your response strictly as valid JSON with these exact keys:
{
    "summary": "A 3-5 sentence executive summary of the overall performance during this period.",
    "key_metrics": {
        "total_spend": 250000, "total_revenue": 1000000,
        "overall_roas": 4.0, "avg_cpa": 300, "total_purchases": 830
    },
    "best_campaigns": [
        {"name": "campaign name", "reason": "Specific data-backed reason for success (e.g. high CVR)", "roas": 5.2, "spend": 50000}
    ],
    "worst_campaigns": [
        {"name": "campaign name", "reason": "Why this campaign is underperforming", "roas": 0.3, "spend": 20000}
    ],
    "audience_insights": "Detailed analysis of audience performance. Which AdSets are performing best?",
    "ad_level_insights": "Deep dive into the ads. Which creative is driving the most value?",
    "funnel_bottlenecks": {
        "Reach": 0, "VC": 0, "ATC": 0, "IC": 0, "Purchase": 0,
        "analysis": "Where is the funnel falling off? (VC -> ATC -> IC -> Purchase). Identify the biggest drop-off point with percentages."
    },
    "ad_fatigue_warnings": "Identify ads that are experiencing ad fatigue (dropping CTRs/high CPCs).",
    "scaling_opportunities": "Concrete, data-backed recommendations on which campaigns/ads to scale.",
    "budget_recommendations": [
        {"action": "INCREASE", "target_name": "Campaign or AdSet name", "reason": "Why this budget should be increased"},
        {"action": "DECREASE", "target_name": "Campaign or AdSet name", "reason": "Why this budget should be decreased"}
    ]
}

Rules:
- All monetary values are in Indian Rupees (₹).
- Use specific names from the JSON.
- Output ONLY valid JSON, no markdown formatting.
- The response MUST parse directly via json.loads()."""

    try:
        from google import genai
        from google.genai import types
        from core.utils.gemini_fallback import generate_content_with_fallback

        if not settings.GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not configured"}

        response = generate_content_with_fallback(
            client=genai_client,
            model=model_name,
            contents=f"Analyze this payload:\n\n{data_json}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                response_mime_type='application/json',
            ),
        )

        text = response.text.strip()
        result = json.loads(text)
        
        # Ensure we don't crash if LLM missed some keys
        for key in ["audience_insights", "funnel_bottlenecks", "ad_fatigue_warnings", "scaling_opportunities", "ad_level_insights"]:
            if key not in result:
                result[key] = "Not enough data to determine specific insights for this area."
                
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini marketing response: {e}")
        return {
            "summary": "AI analysis completed but response parsing failed. Raw data is available via logs.",
            "error": "Failed to parse JSON response from Gemini."
        }
    except Exception as e:
        logger.error(f"Marketing AI analysis failed: {e}", exc_info=True)
        return {"error": str(e)}
def _fetch_marketing_payload(org, start_date, end_date):
    """Internal helper to aggregate all metrics for analysis context.
    Now includes: Meta, Google, Attribution, Products, Financials, Trends, Benchmarks.
    Uses caching (15 min TTL) and parallel fetching for speed.
    """
    # Default range: last 30 days including today
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    # Always clamp end_date to today — future dates produce empty results and confuse the AI
    end_date = min(end_date, date.today())

    # ── CACHE CHECK ──────────────────────────────────────────────────
    cache_key = f"aura_payload_v5:{org.id}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"AURA cache HIT for {org} ({start_date} to {end_date})")
        return cached

    date_filter = {'date__gte': start_date, 'date__lte': end_date}

    # SELF-HEALING CHECK (Campaigns & Ads)
    camp_qs = CampaignDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)
    ad_qs = AdDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)
    
    sync_summary = None
    if camp_qs.count() == 0 or ad_qs.count() == 0:
        logger.info(f"Self-Healing: Data gap detected for {org} ({start_date} to {end_date}). Syncing now...")
        from core.views_marketing_sync import perform_meta_sync_for_shop
        sync_results = perform_meta_sync_for_shop(org, start_date=start_date, end_date=end_date, skip_structural=False)
        total_m = sum(r['metrics'] for r in sync_results)
        sync_summary = f"Synthetically synchronized {total_m} delivery records for this period."
        logger.info(f"Self-Healing: {sync_summary}")
        # Refresh querysets
        camp_qs = CampaignDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)
        ad_qs = AdDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)

    # 1. Campaigns
    campaigns = camp_qs.values('campaign_id', 'campaign_name').annotate(
        spend=Sum('spend'), revenue=Sum('revenue'), purchases=Sum('purchases'),
        impressions=Sum('impressions'), clicks=Sum('clicks'), reach=Sum('reach'),
        view_content=Sum('view_content'), add_to_cart=Sum('add_to_cart'), initiate_checkout=Sum('initiate_checkout')
    ).order_by('-spend')

    # 2. AdSets
    adset_qs = AdSetDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)
    adsets = adset_qs.values('adset_id', 'adset_name').annotate(
        spend=Sum('spend'), revenue=Sum('revenue'), purchases=Sum('purchases'),
        clicks=Sum('clicks'), impressions=Sum('impressions')
    ).order_by('-spend')

    # 3. Ads
    ad_qs = AdDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta', **date_filter)
    ads = ad_qs.values('ad_id', 'ad_name', 'adset_id').annotate(
        spend=Sum('spend'), revenue=Sum('revenue'), purchases=Sum('purchases'),
        clicks=Sum('clicks'), impressions=Sum('impressions')
    ).order_by('-spend')

    # 4. Merchandising & Extras
    from threading import Thread
    from queue import Queue
    
    q = Queue()
    def _run_fetcher(name, fn):
        try: q.put((name, fn()))
        except: q.put((name, None))

    extra_fetchers = {
        'merchandising_data': lambda: _fetch_merchandising_data(org, start_date, end_date),
        'goal_tracking': lambda: _fetch_goal_tracking(org, start_date, end_date),
        'retention': lambda: _fetch_retention_stats(org, start_date, end_date),
        'shopify_intelligence': lambda: _fetch_shopify_order_intelligence(org, start_date, end_date),
    }

    threads = []
    for name, fn in extra_fetchers.items():
        t = Thread(target=_run_fetcher, args=(name, fn))
        t.start()
        threads.append(t)
    for t in threads: t.join()

    extras = {}
    while not q.empty():
        n, res = q.get()
        extras[n] = res

    merch = extras.get('merchandising_data') or []
    shop_intel = extras.get('shopify_intelligence') or []
    
    # Merge shop_intel into merch by SKU so the AI sees a unified product list
    shop_intel_map = {item['sku']: item for item in shop_intel if 'sku' in item}
    for item in merch:
        sku = item.get('sku')
        if sku and sku in shop_intel_map:
            intel = shop_intel_map[sku]
            item['cancelled_orders'] = intel.get('cancelled_orders', 0)
            item['cod_percentage'] = intel.get('cod_percentage', 0)
            item['new_customers'] = intel.get('new_customers', 0)
            item['repeat_customers'] = intel.get('repeat_customers', 0)
            item['avg_units_per_order'] = intel.get('avg_units_per_order', 1.0)

    # Build the base payload (existing Meta data)
    payload = {
        "date_range": f"{start_date} to {end_date}",
        "sync_status": sync_summary or "Data retrieved from local cache.",
        "inventory_data": merch,
        "goals": extras.get('goal_tracking'),
        "retention_stats": extras.get('retention'),
        "campaigns": [
            {
                "name": c['campaign_name'], "spend": float(c['spend']), "revenue": float(c['revenue']),
                "roas": round(float(c['revenue'])/float(c['spend']), 2) if c['spend'] > 0 else 0,
                "cpa": round(float(c['spend'])/c['purchases'], 2) if c.get('purchases') else 0,
                "ctr_percent": round((c['clicks']/c['impressions'])*100, 2) if c.get('impressions') else 0,
                "cpc": round(float(c['spend'])/c['clicks'], 2) if c.get('clicks') else 0,
                "clicks": c.get('clicks', 0),
                "impressions": c.get('impressions', 0),
                "funnel": {"reach": c['reach'], "vc": c['view_content'], "atc": c['add_to_cart'], "ic": c['initiate_checkout'], "purchase": c.get('purchases', 0)}
            } for c in campaigns[:50]
        ],
        "adsets": [
            {
                "name": a['adset_name'], "spend": float(a['spend']), "roas": round(float(a['revenue'])/float(a['spend']), 2) if a['spend'] > 0 else 0,
                "purchases": a['purchases'],
                "cpa": round(float(a['spend'])/a['purchases'], 2) if a.get('purchases') else 0,
                "ctr_percent": round((a['clicks']/a['impressions'])*100, 2) if a.get('impressions') else 0,
                "cpc": round(float(a['spend'])/a['clicks'], 2) if a.get('clicks') else 0,
                "clicks": a.get('clicks', 0),
                "impressions": a.get('impressions', 0)
            } for a in adsets[:50]
        ],
        "top_ads": [
            {
                "name": d['ad_name'], "spend": float(d['spend']), "roas": round(float(d['revenue'])/float(d['spend']), 2) if d['spend'] > 0 else 0,
                "cpa": round(float(d['spend'])/d['purchases'], 2) if d['purchases'] > 0 else 0,
                "ctr_percent": round((d['clicks']/d['impressions'])*100, 2) if d['impressions'] > 0 else 0,
                "cpc": round(float(d['spend'])/d['clicks'], 2) if d['clicks'] > 0 else 0,
                "clicks": d['clicks'],
                "impressions": d['impressions']
            } for d in ads[:50]
        ]
    }

    # Pre-compute aggregate funnel totals so the UI always has real numbers
    total_funnel = {
        "Reach":    sum(c.get('reach', 0) or 0 for c in campaigns),
        "VC":       sum(c.get('view_content', 0) or 0 for c in campaigns),
        "ATC":      sum(c.get('add_to_cart', 0) or 0 for c in campaigns),
        "IC":       sum(c.get('initiate_checkout', 0) or 0 for c in campaigns),
        "Purchase": sum(c.get('purchases', 0) or 0 for c in campaigns),
    }
    payload["total_funnel"] = total_funnel

    # ── PARALLEL ENRICHMENT — fetch all new layers concurrently ──────
    from django.db import close_old_connections
    # Import merchandising intelligence service (separate module)
    from core.services.merchandising_intelligence import fetch_merchandising_intelligence

    enrichment_tasks = {
        'demographics': lambda: _fetch_all_demographics(org, start_date, end_date),
        'daily_trends': lambda: _fetch_daily_trends(org, start_date, end_date),
        'google': lambda: _fetch_google_payload(org, start_date, end_date),
        'attribution_summary': lambda: _fetch_attribution_summary(org, start_date, end_date),
        'top_products_from_ads': lambda: _fetch_top_products_from_ads(org, start_date, end_date),
        'financial_context': lambda: _fetch_financial_context(org),
        'shopify_revenue': lambda: _fetch_shopify_revenue(org, start_date, end_date),
        'retention_stats': lambda: _fetch_retention_stats(org, start_date, end_date),
        'goal_tracking': lambda: _fetch_goal_tracking(org, start_date, end_date),
        'merchandising_data': lambda: _fetch_merchandising_data(org, start_date, end_date),
        # Always use 30-day window for merchandising intelligence to get
        # meaningful velocity data, regardless of the user's date range.
        'merchandising_intelligence': lambda: fetch_merchandising_intelligence(
            org,
            max(start_date, end_date - timedelta(days=30)),
            end_date,
        ),
    }

    def _safe_run(name, fn):
        try:
            close_old_connections()
            return name, fn()
        except Exception as e:
            logger.warning(f"Enrichment '{name}' failed: {e}")
            return name, None

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_safe_run, name, fn): name for name, fn in enrichment_tasks.items()}
        for future in as_completed(futures):
            name, result = future.result()
            if result is not None:
                if name == 'google':
                    # Unpack google sub-keys into payload
                    payload['google_campaigns'] = result.get('google_campaigns', [])
                    payload['google_search_terms'] = result.get('google_search_terms', [])
                else:
                    payload[name] = result

    # Always include industry benchmarks (static, no fetch needed)
    payload['industry_benchmarks'] = INDUSTRY_BENCHMARKS

    # ── DEBUG: Confirm inventory data made it into the payload ────
    inv_data = payload.get('merchandising_data')
    merch_intel = payload.get('merchandising_intelligence')
    inv_count = len(inv_data) if isinstance(inv_data, list) else 0
    merch_count = merch_intel.get('product_count', 0) if isinstance(merch_intel, dict) else 0
    logger.info(f"AURA payload built: merchandising_data={inv_count} products, merchandising_intelligence={merch_count} products")

    # ── CACHE SET (1 hour TTL) ───────────────────────────────────────
    try:
        cache.set(cache_key, payload, timeout=3600)
    except Exception:
        pass  # Cache failures should never block the response

    return payload

def _fetch_all_demographics(org, start_date, end_date):
    """
    Helper to fetch all demographic breakdowns from Meta.
    """
    from core.models import MarketingCredential
    cred = MarketingCredential.objects.filter(shop=org, platform='Meta', is_active=True).first()
    if not cred: return {}

    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount

    try:
        FacebookAdsApi.init(
            app_id=cred.get_app_id(),
            app_secret=cred.get_app_secret(),
            access_token=cred.get_access_token()
        )
        account = AdAccount(cred.ad_account_id)
        fields = ['spend', 'impressions', 'clicks', 'reach', 'actions', 'action_values']
        
        # We'll batch these for efficiency
        breakdowns = {
            'age_gender': ['age', 'gender'],
            'device': ['impression_device'],
            'region': ['region'],
            'platform': ['publisher_platform']
        }
        
        demo_payload = {}
        for key, bd_list in breakdowns.items():
            try:
                # Use specific time_range (Calendar mode) for AI - safest for custom periods
                params = {
                    'time_range': {
                        'since': start_date.strftime('%Y-%m-%d'), 
                        'until': end_date.strftime('%Y-%m-%d')
                    },
                    'time_increment': 'all_days',
                    'breakdowns': bd_list
                }
                insights = account.get_insights(fields=fields, params=params)
                
                rows = []
                for item in insights:
                    try:
                        # Basic parsing
                        actions = item.get('actions', [])
                        pur = 0
                        for a in actions:
                            if a.get('action_type') == 'purchase':
                                pur = int(float(a.get('value', '0')))
                        
                        act_vals = item.get('action_values', [])
                        rev = 0
                        for v in act_vals:
                            if v.get('action_type') == 'purchase':
                                rev = float(v.get('value', '0'))

                        row = {
                            "spend": float(item.get('spend', '0')),
                            "purchases": pur,
                            "revenue": rev,
                            "clicks": int(item.get('clicks', '0')),
                            "impressions": int(item.get('impressions', '0'))
                        }
                        # Add specific breakdown keys
                        for bd in bd_list:
                            row[bd] = item.get(bd, 'Unknown')
                        rows.append(row)
                    except Exception as row_e:
                        logger.warning(f"Skipping malformed demo row: {row_e}")
                        continue
                
                demo_payload[key] = sorted(rows, key=lambda x: x['spend'], reverse=True)[:15] # Keep top 15 for context window
            except Exception as bd_e:
                logger.error(f"Failed to fetch {key} demographics for {cred.ad_account_id}: {bd_e}")
                demo_payload[key] = []
            
        return demo_payload
    except Exception as e:
        logger.error(f"Failed to fetch demographics for AI: {e}")
        return {}

def run_marketing_chat(org, question, start_date=None, end_date=None, start_date2=None, end_date2=None, model_name='gemini-2.5-flash-lite', conversation_context=None, attachment=None):
    """
    Conversational interface to ask specific questions about the marketing data.
    Supports optional dual-period comparison and multimodal file attachments
    (PDF, Image, Word/Excel sheets).
    Defaults to gemini-2.5-flash for fast response times.
    """
    # FETCH DATA (OPTIONAL)
    data_json1 = None
    data_json2 = None

    # Always fetch real-time pacing — costs < 5ms and answers the most common questions
    pacing = _fetch_intraday_pacing(org)
    pacing_json = json.dumps(pacing, cls=DecimalEncoder, indent=2) if pacing else None

    if start_date and end_date:
        payload1 = _fetch_marketing_payload(org, start_date, end_date)
        if "error" in payload1: return payload1
        data_json1 = json.dumps(payload1, cls=DecimalEncoder, indent=2)
        
        if start_date2 and end_date2:
            payload2 = _fetch_marketing_payload(org, start_date2, end_date2)
            data_json2 = json.dumps(payload2, cls=DecimalEncoder, indent=2) if payload2 else None

    comparison_info = ""
    if data_json2:
        comparison_info = f"""

⚠️ COMPARISON MODE ACTIVE:
You have been given TWO separate data payloads for a side-by-side comparison.
- PRIMARY PERIOD: {start_date} to {end_date}
- COMPARISON PERIOD: {start_date2} to {end_date2}

IMPORTANT RULES FOR COMPARISON:
- If a period is in the future or partially complete (e.g., current month up to today), the data will only cover dates up to today ({timezone.now().date()}). This is EXPECTED and VALID — do NOT say you don't have the data. Work with what is available and note it covers a partial period.
- Always explicitly name both periods in your tables (e.g., "May 2025" vs "May 2026 (partial)").
- Compute % change for every key metric with direction arrows (↑ ↓).
- If one period is partial, normalize per-day averages for a fair comparison (e.g., daily avg spend).

COMPARISON PERIOD DATA ({start_date2} to {end_date2}):
{data_json2}"""

    # SYSTEM PROMPT
    current_date = timezone.now().date()
    from django.utils import timezone as tz
    import pytz
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = timezone.now().astimezone(IST)
    current_datetime_str = now_ist.strftime('%A, %d %B %Y at %I:%M %p IST')
    org_name = org.name if hasattr(org, 'name') else str(org)

    from core.models import MarketingAgentConfiguration
    config = MarketingAgentConfiguration.objects.filter(is_active=True).first()

    # Inject Response Style & COGS config
    style_instruction = ""
    cogs_instruction = ""
    if config:
        if config.response_style == 'Concise':
            style_instruction = "\n\nRESPONSE STYLE: Concise. Keep your answers brief, direct, and to the point. Avoid unnecessary fluff or verbosity."
        elif config.response_style == 'Detailed':
            style_instruction = "\n\nRESPONSE STYLE: Detailed. Provide a comprehensive, highly detailed response. Explain nuance, provide examples where possible, and break down complex concepts."
        
        if config.cogs_margin_pct:
            cogs_instruction = f"""
COGS & ROI CALCULATION:
The user has configured a COGS margin of {config.cogs_margin_pct}%. 
When calculating "Actual ROI" or "Profit", use this margin against the total revenue. 
(Formula: Gross Margin = Revenue * {config.cogs_margin_pct/100} — then subtract Ad Spend to get Net Profit. Actual ROI = Net Profit / Ad Spend).
"""

    # ── CMO-GRADE SYSTEM PROMPT ──────────────────────────────────────
    CMO_CAPABILITIES = f"""
You are a sharp, senior Performance Marketing Analyst embedded inside a D2C brand's internal dashboard.

{cogs_instruction}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE #1 — QUESTION SCOPE (HIGHEST PRIORITY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You ONLY answer what the user actually asked. Nothing else.

- If the user asks about **ad spend** → give spend numbers. Do NOT mention inventory, stock, or line items.
- If the user asks about **ROAS** → give ROAS. Do NOT mention product segmentation or catalog recommendations.
- If the user asks about **a specific campaign** → answer about that campaign only.
- If the user asks a **simple factual question** → give a direct answer in 1-3 lines. No tables, no JSON, no extra sections.
- **NEVER volunteer data that wasn't asked for.** Having access to 900+ products in the payload does NOT mean you should mention all of them.
- The payload is a reference library. You read from it selectively based on what the question needs — you do NOT dump it.
- If the user greets you (e.g., "sup", "hey", "hello", "hi", "how are you") or sends a casual message, respond with a brief, friendly greeting aligned with your active persona. Do NOT perform a performance analysis, print metrics, or show JSON unless they explicitly asked for one.

BAD example: User asks "what was my spend today?" → AI talks about inventory, OOS sizes, product segmentation. ❌
GOOD example: User asks "what was my spend today?" → AI says "Today's spend was ₹X across Y campaigns." ✅

Only trigger the full JSON visual block when the user explicitly asks for an "analysis", "full report", "performance breakdown", "audit", or "product health check".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMMUNICATION STYLE:
- Speak directly. No greetings ("Hey there!"), no filler ("Great question!"), no corporate language.
- If the answer is one number, say the number. If it's 3 bullet points, give 3 bullet points.
- Do not use section headers like "Executive Summary" or "Winning Plays" for simple answers.
- If you see something genuinely alarming in the data that the user MUST know (e.g. scaling spend on an OOS product), add a one-line alert at the end — but keep it brief.

DATA ACCURACY:
- All numbers must come directly from the payload. Never estimate or fabricate.
- The payload has a pre-computed 'total_funnel' field. When outputting funnel_bottlenecks in JSON, copy those values exactly — NEVER output all zeros if total_funnel has real numbers.

VISUAL JSON OUTPUT (only when analysis/report is explicitly requested):
- Append a ```json ... ``` block at the END of your response.
- Do NOT describe the JSON in text — the UI renders it as charts.
- funnel_bottlenecks MUST use the values from total_funnel in the payload.

STRUCTURED JSON SCHEMA (use only the fields relevant to the question):
{{
  "summary": "1-2 sentence analytical take based on actual numbers",
  "key_metrics": {{"spend": 0, "revenue": 0, "roas": 0, "cpa": 0, "purchases": 0}},
  "best_campaigns": [{{"name": "", "roas": 0, "spend": 0, "reason": ""}}],
  "worst_campaigns": [{{"name": "", "roas": 0, "spend": 0, "reason": ""}}],
  "funnel_bottlenecks": {{"Reach": 0, "VC": 0, "ATC": 0, "IC": 0, "Purchase": 0}},
  "ad_fatigue_warnings": [{{"ad": "", "issue": ""}}],
  "inventory_alerts": [{{"name": "", "oos_sizes": []}}],
  "scaling_opportunities": [{{"name": "", "roas": 0, "spend": 0}}],
  "month_end_forecast": {{"predicted_revenue": 0, "predicted_roas": 0}},
  "budget_recommendations": [{{"action": "", "target_name": "", "reason": ""}}],
  "merchandising_segmentation": {{
    "winners": [],
    "declining_winners": [],
    "low_inventory_alerts": [],
    "emerging_winners": []
  }},
  "catalog_recommendations": [{{"action": "", "product": "", "reason": ""}}]
}}

MERCHANDISING MODULE (only when user asks about products/inventory/catalog):
- Use 'inventory_data' payload which has per-product DUAL-PERIOD data: revenue, orders, sessions, CVR, stock levels, size breakdown, cod_percentage, cancelled_orders, new_customers, repeat_customers.
- Segment products into 4 categories ONLY when explicitly asked:
  1. WINNERS: Top 20% revenue both periods, CVR above store average.
  2. DECLINING WINNERS: Session drop ≥30% or CVR drop ≥20% vs previous period.
  3. LOW INVENTORY ALERT: total_stock <10 or key sizes (M,L,XL) OOS.
  4. NEW EMERGING: Revenue growth ≥30%, stable CVR, adequate inventory.
- Catalog actions: REMOVE_FROM_CATALOG / RESTOCK_IMMEDIATELY / SCALE_IN_ADS / HOLD_MONITOR.
- Restock urgency: 🔴 <3 days stock | 🟡 3-7 days | 🟢 7-14 days | skip >14 days.
- ALWAYS check inventory before blaming creative fatigue for any ad performance drop.
"""

    if data_json1:
        # AUDIT MODE
        if config and config.system_prompt:
            audit_base = config.system_prompt
        else:
            audit_base = f"Analyze data for '{org_name}' ({start_date} to {end_date})."

        pacing_block = ""
        if pacing_json:
            pacing_block = f"""

⏰ REAL-TIME INTRADAY PACING DATA (as of {pacing['snapshot_time']}):
{pacing_json}

INTRADAY PACING RULES:
- You have access to live order counts and revenue up to the EXACT current time of day.
- Use this to answer questions like "how many orders did I have at this time yesterday?"
- 'yesterday_same_time' is the apples-to-apples comparison — same clock time yesterday.
- 'yesterday_full_day' gives yesterday's final tally for context.
- Always state the snapshot time when referencing pacing data.
- If today is ahead of yesterday's same-time pace, say so with the % delta.
"""

        system_prompt = f"""{audit_base}

{CMO_CAPABILITIES}
{style_instruction}
Current Date & Time: {current_datetime_str}

PRIMARY DATA PAYLOAD ({start_date} to {end_date}):
{data_json1}
{comparison_info}
{pacing_block}"""
    else:
        # GENERAL CHAT MODE — Proactive strategy advisor
        if config and config.general_prompt:
            general_base = config.general_prompt
        else:
            general_base = f"""You are a specialized Performance Marketing Strategist for '{org_name}', an Indian D2C brand.

You currently have NO data payload loaded. Instead of just asking for a timeframe, be PROACTIVELY HELPFUL:

1. If they ask for specific metrics, suggest: "I'd love to check that — just mention a timeframe like 'today', 'last 7 days', or 'this month' and I'll pull the data instantly."
2. For general strategy questions, give DETAILED expert advice drawing from:
   - Meta Ads best practices (CBO vs ABO, Advantage+, broad vs interest targeting)
   - Google Ads strategies (PMAX, brand vs non-brand, search term optimization)
   - Creative frameworks (hook rates, thumb-stop ratios, UGC vs studio)
   - Audience strategies (lookalike expansion, retargeting windows, exclusions)
   - Budget allocation frameworks (70/20/10 rule, MER-based decisions)
   - Indian D2C specific insights (COD optimization, tier-2/3 targeting, festive scaling)
3. Suggest specific campaign structures, ad copy angles, and testing frameworks.
4. When giving advice, use real examples and frameworks, not generic platitudes."""

        pacing_block = ""
        if pacing_json:
            pacing_block = f"""

⏰ REAL-TIME INTRADAY PACING (as of {pacing['snapshot_time']}):
{pacing_json}

INTRADAY PACING RULES:
- Use this data to answer questions like "how many orders did I have at this time yesterday?"
- 'yesterday_same_time' is the direct apples-to-apples comparison.
- Always state the snapshot time when referencing pacing data.
"""

        system_prompt = f"""{general_base}
{style_instruction}
Current Date & Time: {current_datetime_str}
{pacing_block}"""

    # ── AGENT MANAGER: Inject global rules + corrections ──────────────────
    # This is the single point where ALL active rules are merged into the prompt.
    # Rules are fetched from DB on every call — no restart needed.
    enriched_system_prompt = build_marketing_system_prompt(system_prompt)

    # The genai.Client and its httpx connection MUST stay alive for the
    # entire duration of streaming. We achieve this by making this function
    # itself a generator — the client stays in scope until the last chunk.
    def _stream_chunks():
        try:
            # Build conversation history in native format
            native_messages = []
            if conversation_context:
                for ctx in conversation_context:
                    role = "user" if ctx['role'] == 'user' else "model"
                    native_messages.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=ctx['content'])]
                    ))

            # Build final user turn — add file attachment if present
            user_parts = [types.Part.from_text(text=question)]

            if attachment:
                try:
                    attachment.seek(0)
                    file_bytes = attachment.read()
                    # Determine MIME type from file name
                    fname = getattr(attachment, 'name', '').lower()
                    if fname.endswith('.pdf'):
                        mime = 'application/pdf'
                    elif fname.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        mime = 'image/jpeg' if fname.endswith(('.jpg', '.jpeg')) else f'image/{fname.split(".")[-1]}'
                    elif fname.endswith(('.xlsx', '.xls')):
                        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    elif fname.endswith('.csv'):
                        # For CSV, embed as inline text since Gemini doesn't natively read CSV bytes
                        csv_text = file_bytes.decode('utf-8', errors='replace')
                        user_parts.append(types.Part.from_text(text=f'\n\n---UPLOADED FILE ({attachment.name})---\n{csv_text[:50000]}'))
                        file_bytes = None
                    elif fname.endswith(('.docx', '.doc')):
                        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    else:
                        mime = 'application/octet-stream'

                    if file_bytes:
                        user_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))
                    logger.info(f'Attachment added to Gemini prompt: {getattr(attachment, "name", "unknown")}')
                except Exception as att_err:
                    logger.warning(f'Could not read attachment: {att_err}')

            native_messages.append(types.Content(
                role="user",
                parts=user_parts
            ))

            from core.utils.gemini_fallback import generate_content_stream_with_fallback
            stream = generate_content_stream_with_fallback(
                client=genai_client,
                model=model_name,
                contents=native_messages,
                config=types.GenerateContentConfig(
                    system_instruction=enriched_system_prompt,
                    temperature=0.1,
                    max_output_tokens=65536,
                ),
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error(f"Marketing AI stream failed: {e}", exc_info=True)
            raise

    # Return stream + prompt snapshot for the audit log
    return {"stream": _stream_chunks(), "system_prompt_snapshot": enriched_system_prompt}



