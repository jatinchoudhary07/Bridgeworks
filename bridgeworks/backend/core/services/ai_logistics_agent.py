"""
AI Logistics Agent
==================
Uses Gemini to analyze logistics & delivery performance data and provide
actionable insights: delivery rates, NDR analysis, RTO trends, shipping costs,
COD remittance, and courier performance.
"""
import logging
import json
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q, F
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, date

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


# ─── Logistics KPI Benchmarks (Indian D2C) ───────────────────────────────────
LOGISTICS_BENCHMARKS = {
    "d2c_india_avg_delivery_rate_pct": 85.0,
    "d2c_india_avg_rto_rate_pct": 12.0,
    "d2c_india_avg_ndr_rate_pct": 8.0,
    "d2c_india_avg_cod_pct": 60.0,
    "note": "Approximate averages for Indian D2C shipments, use for directional benchmarking only."
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS — Each fetches one context layer
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_order_status_summary(org_id, start_date, end_date):
    """Overall order counts by fulfillment and internal status."""
    try:
        from core.models import Order
        qs = Order.objects.filter(
            org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        total = qs.count()
        if total == 0:
            return None

        delivered = qs.filter(
            Q(current_status__iexact='delivered') | Q(current_status__iexact='DELIVERED')
        ).count()
        rto = qs.filter(current_status__icontains='rto').count()
        ndr = qs.filter(is_ndr=True).count()
        in_transit = qs.filter(
            Q(current_status__icontains='in transit') |
            Q(current_status__icontains='out for delivery') |
            Q(current_status__icontains='out_for_delivery') |
            Q(current_status__icontains='picked up') |
            Q(current_status__icontains='awb assigned') |
            Q(current_status__icontains='awb_assigned') |
            Q(current_status__icontains='shipment booked') |
            Q(current_status__icontains='reached at') |
            Q(current_status__icontains='delayed')
        ).count()
        pending_dispatch = qs.filter(
            Q(fulfillment_status__isnull=True) | Q(current_status__isnull=True)
        ).count()

        delivery_rate = round((delivered / total) * 100, 2) if total > 0 else 0
        rto_rate = round((rto / total) * 100, 2) if total > 0 else 0
        ndr_rate = round((ndr / total) * 100, 2) if total > 0 else 0
        avg_order_value = float(qs.aggregate(avg=Avg('total_price'))['avg'] or 0)
        total_revenue = float(qs.aggregate(s=Sum('total_price'))['s'] or 0)

        # Courier-level delivery performance
        from django.db.models.functions import Upper
        courier_perf = list(
            qs.exclude(fulfillments__tracking_info__company__isnull=True)
            .exclude(fulfillments__tracking_info__company='')
            .annotate(courier_upper=Upper('fulfillments__tracking_info__company'))
            .values('courier_upper')
            .annotate(
                total=Count('id', distinct=True),
                delivered=Count('id', distinct=True, filter=Q(current_status__iexact='delivered')),
                rto=Count('id', distinct=True, filter=Q(current_status__icontains='rto')),
                ndr=Count('id', distinct=True, filter=Q(is_ndr=True)),
            )
            .order_by('-total')[:10]
        )
        for cp in courier_perf:
            t = cp['total'] or 1
            cp['delivery_rate_pct'] = round((cp['delivered'] / t) * 100, 2)
            cp['rto_rate_pct'] = round((cp['rto'] / t) * 100, 2)
            cp['ndr_rate_pct'] = round((cp['ndr'] / t) * 100, 2)

        return {
            "total_orders": total,
            "delivered": delivered,
            "rto": rto,
            "ndr": ndr,
            "in_transit": in_transit,
            "pending_dispatch": pending_dispatch,
            "delivery_rate_pct": delivery_rate,
            "rto_rate_pct": rto_rate,
            "ndr_rate_pct": ndr_rate,
            "avg_order_value_inr": round(avg_order_value, 2),
            "total_revenue_inr": round(total_revenue, 2),
            "courier_performance": courier_perf,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch order status summary: {e}")
        return None


def _fetch_ndr_analysis(org_id, start_date, end_date):
    """NDR (Non-Delivery Report) breakdown by call status and attempts."""
    try:
        from core.models import Order
        ndr_qs = Order.objects.filter(
            org_id=org_id,
            is_ndr=True,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        total_ndr = ndr_qs.count()
        if total_ndr == 0:
            return None

        # NDR failure reasons — actual reason reported by courier (current_status_details)
        by_failure_reason = list(
            ndr_qs.exclude(current_status_details__isnull=True).exclude(current_status_details='')
            .values('current_status_details')
            .annotate(count=Count('id'))
            .order_by('-count')[:15]
        )
        # Fallback to current_status if details not populated
        if not by_failure_reason:
            by_failure_reason = list(
                ndr_qs.values('current_status')
                .annotate(count=Count('id'))
                .order_by('-count')[:15]
            )

        by_status = list(
            ndr_qs.values('ndr_call_status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        by_attempts = list(
            ndr_qs.values('ndr_call_attempts')
            .annotate(count=Count('id'))
            .order_by('ndr_call_attempts')[:10]
        )
        avg_attempts = ndr_qs.aggregate(avg=Avg('ndr_call_attempts'))['avg'] or 0
        resolved = ndr_qs.filter(ndr_call_status__in=['Will Accept', 'Delivered']).count()
        unresolved = total_ndr - resolved

        # Courier-level NDR breakdown: count NDR orders per courier company
        try:
            from core.models import TrackingInfo
            all_qs = Order.objects.filter(
                org_id=org_id,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
            # Total orders per courier
            courier_totals = {
                row['fulfillments__tracking_info__company']: row['cnt']
                for row in all_qs.values('fulfillments__tracking_info__company')
                    .annotate(cnt=Count('id', distinct=True))
                if row['fulfillments__tracking_info__company']
            }
            # NDR orders per courier
            courier_ndr = {
                row['fulfillments__tracking_info__company']: row['cnt']
                for row in ndr_qs.values('fulfillments__tracking_info__company')
                    .annotate(cnt=Count('id', distinct=True))
                if row['fulfillments__tracking_info__company']
            }
            by_courier = []
            for company, ndr_cnt in sorted(courier_ndr.items(), key=lambda x: -x[1]):
                total_c = courier_totals.get(company, ndr_cnt)
                by_courier.append({
                    "courier": company,
                    "ndr_orders": ndr_cnt,
                    "total_orders": total_c,
                    "ndr_rate_pct": round((ndr_cnt / total_c) * 100, 2) if total_c > 0 else 0,
                })
        except Exception:
            by_courier = []

        return {
            "total_ndr": total_ndr,
            "resolved": resolved,
            "unresolved": unresolved,
            "resolution_rate_pct": round((resolved / total_ndr) * 100, 2) if total_ndr > 0 else 0,
            "avg_call_attempts": round(float(avg_attempts), 2),
            "by_failure_reason": by_failure_reason,
            "by_call_status": by_status,
            "by_attempts_distribution": by_attempts,
            "by_courier": by_courier,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch NDR analysis: {e}")
        return None


def _fetch_rto_analysis(org_id, start_date, end_date):
    """RTO (Return to Origin) breakdown."""
    try:
        from core.models import Order
        rto_qs = Order.objects.filter(
            org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            current_status__icontains='rto',
        )
        total_rto = rto_qs.count()
        if total_rto == 0:
            return None

        # Payment type breakdown (COD RTOs cost more)
        from core.utils.payment_utils import get_payment_q_objects
        try:
            _pq = get_payment_q_objects()
            cod_rto = rto_qs.filter(_pq['cod']).count()
            prepaid_rto = rto_qs.filter(_pq['prepaid']).count()
        except Exception:
            cod_rto = 0
            prepaid_rto = 0

        by_status = list(
            rto_qs.values('rto_internal_status')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        by_state = list(
            rto_qs.values('shipping_state')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        rto_value = rto_qs.aggregate(total=Sum('total_price'))['total'] or 0

        return {
            "total_rto": total_rto,
            "cod_rto": cod_rto,
            "prepaid_rto": prepaid_rto,
            "rto_value_inr": float(rto_value),
            "by_internal_status": by_status,
            "top_rto_states": by_state,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch RTO analysis: {e}")
        return None


def _fetch_cod_analysis(org_id, start_date, end_date):
    """COD remittance and payment type breakdown."""
    try:
        from core.models import Order
        from core.utils.payment_utils import get_payment_q_objects
        qs = Order.objects.filter(
            org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        total = qs.count()
        if total == 0:
            return None

        try:
            _pq = get_payment_q_objects()
            cod = qs.filter(_pq['cod'])
            prepaid = qs.filter(_pq['prepaid'])
            ppcod = qs.filter(_pq['partial'])
            cod_count = cod.count()
            prepaid_count = prepaid.count()
            ppcod_count = ppcod.count()
            cod_revenue = float(cod.aggregate(t=Sum('total_price'))['t'] or 0)
            prepaid_revenue = float(prepaid.aggregate(t=Sum('total_price'))['t'] or 0)
        except Exception:
            cod_count = 0
            prepaid_count = 0
            ppcod_count = 0
            cod_revenue = 0.0
            prepaid_revenue = 0.0

        return {
            "total_orders": total,
            "cod_orders": cod_count,
            "prepaid_orders": prepaid_count,
            "ppcod_orders": ppcod_count,
            "cod_pct": round((cod_count / total) * 100, 2) if total > 0 else 0,
            "prepaid_pct": round((prepaid_count / total) * 100, 2) if total > 0 else 0,
            "cod_revenue_inr": cod_revenue,
            "prepaid_revenue_inr": prepaid_revenue,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch COD analysis: {e}")
        return None


def _fetch_shipping_cost_analysis(org_id, start_date, end_date):
    """Shipping cost breakdown from ShippingCostEntry or Order-level data."""
    try:
        from core.models import Order
        qs = Order.objects.filter(
            org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        # Try to get actual shipping cost from related models
        try:
            from core.models import ShippingCostEntry
            entries = ShippingCostEntry.objects.filter(
                order__org_id=org_id,
                order__created_at__date__gte=start_date,
                order__created_at__date__lte=end_date,
            )
            total_cost = float(entries.aggregate(t=Sum('amount'))['t'] or 0)
            by_courier = list(
                entries.values('courier_name')
                .annotate(cost=Sum('amount'), shipments=Count('id'))
                .order_by('-cost')[:10]
            )
            return {
                "total_shipping_cost_inr": total_cost,
                "by_courier": by_courier,
            }
        except Exception:
            pass

        # Fallback: no dedicated shipping cost data
        total_revenue = float(qs.aggregate(t=Sum('total_price'))['t'] or 0)
        order_count = qs.count()
        return {
            "total_orders": order_count,
            "total_revenue_inr": total_revenue,
            "note": "Detailed shipping cost data not available — showing order revenue only."
        }
    except Exception as e:
        logger.warning(f"Failed to fetch shipping cost analysis: {e}")
        return None


def _fetch_delivery_trends(org_id, start_date, end_date):
    """Day-by-day delivery vs RTO trend."""
    try:
        from core.models import Order
        from django.db.models.functions import TruncDate
        rows = list(
            Order.objects.filter(
                org_id=org_id,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                orders=Count('id'),
                delivered=Count('id', filter=Q(current_status__iexact='delivered')),
                rto=Count('id', filter=Q(current_status__icontains='rto')),
                ndr=Count('id', filter=Q(is_ndr=True)),
                total_revenue=Sum('total_price'),
            )
            .order_by('day')
        )
        for r in rows:
            r['day'] = r['day'].isoformat() if r['day'] else None
            total = r['orders'] or 1
            r['delivery_rate_pct'] = round((r['delivered'] / total) * 100, 2)
            r['rto_rate_pct'] = round((r['rto'] / total) * 100, 2)
            r['total_revenue_inr'] = round(float(r.pop('total_revenue') or 0), 2)
            r['avg_order_value_inr'] = round(r['total_revenue_inr'] / r['orders'], 2) if r['orders'] > 0 else 0
        return rows
    except Exception as e:
        logger.warning(f"Failed to fetch delivery trends: {e}")
        return []


def _fetch_top_problem_pincodes(org_id, start_date, end_date):
    """States/pincodes with highest RTO/NDR rates."""
    try:
        from core.models import Order
        qs = Order.objects.filter(
            org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        by_state = list(
            qs.values('shipping_state')
            .annotate(
                total=Count('id'),
                delivered=Count('id', filter=Q(current_status__iexact='delivered')),
                rto=Count('id', filter=Q(current_status__icontains='rto')),
                ndr=Count('id', filter=Q(is_ndr=True)),
            )
            .order_by('-rto')[:15]
        )
        for row in by_state:
            total = row['total'] or 1
            row['delivery_rate_pct'] = round((row['delivered'] / total) * 100, 2)
            row['rto_rate_pct'] = round((row['rto'] / total) * 100, 2)
            row['ndr_rate_pct'] = round((row['ndr'] / total) * 100, 2)
        return by_state
    except Exception as e:
        logger.warning(f"Failed to fetch problem pincodes: {e}")
        return []


def _fetch_returns_exchanges_analysis(org_id, start_date, end_date):
    """Returns and Exchanges breakdown — values computed from raw_data JSON since DB refund_amount is not populated."""
    try:
        from core.models import ReturnRequest, Order
        from decimal import Decimal as _D
        qs = ReturnRequest.objects.filter(
            order__org_id=org_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
        )
        total = qs.count()
        if total == 0:
            return None

        total_returns = qs.filter(request_type='RETURN').count()
        total_exchanges = qs.filter(request_type='EXCHANGE').count()

        returns_by_status = list(
            qs.filter(request_type='RETURN')
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        exchanges_by_status = list(
            qs.filter(request_type='EXCHANGE')
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # ── Compute financial values from raw_data (DB refund_amount field is 0) ──
        return_value = _D('0')
        exchange_value = _D('0')
        reasons = {}
        couriers = {}
        products = {}
        exchange_products = {}

        for rr in qs.exclude(raw_data__isnull=True).only('request_type', 'raw_data'):
            raw = rr.raw_data or {}
            req = raw.get('request', raw)
            li = req.get('line_items', [])
            if not li:
                continue
            item = li[0]
            sp = item.get('shop_price', {})
            amt = _D(str(sp.get('actual_amount', 0) or 0))
            qty = int(item.get('quantity', 1) or 1)
            item_total = amt * qty

            if rr.request_type == 'RETURN':
                return_value += item_total
                reason = (item.get('reason') or 'Not specified').strip()
                reasons[reason] = reasons.get(reason, 0) + 1
                orig = item.get('original_product', {})
                if orig and orig.get('title'):
                    p = orig['title']
                    products[p] = products.get(p, 0) + 1
            else:
                exchange_value += item_total
                exc_prod = item.get('exchange_product', {})
                if exc_prod and exc_prod.get('title'):
                    ep = exc_prod['title']
                    exchange_products[ep] = exchange_products.get(ep, 0) + 1

            # Courier from return shipment
            ship = item.get('shipping', [])
            if ship and ship[0].get('shipping_company'):
                c = ship[0]['shipping_company'].strip()
                if c:
                    couriers[c] = couriers.get(c, 0) + 1

        top_reasons = sorted(reasons.items(), key=lambda x: -x[1])[:10]
        top_products = sorted(products.items(), key=lambda x: -x[1])[:10]
        top_exchange_products = sorted(exchange_products.items(), key=lambda x: -x[1])[:10]
        by_courier = sorted(couriers.items(), key=lambda x: -x[1])

        # How many return shipments have AWB (actually picked up by courier)
        with_awb = qs.exclude(awb_number__isnull=True).exclude(awb_number='').count()
        refunded = qs.filter(status='REFUNDED').count()
        rejected = qs.filter(status='REJECTED').count()
        received = qs.filter(status='RECEIVED').count()
        approved = qs.filter(status='APPROVED').count()

        # Exchange orders created in Shopify
        try:
            exchange_orders_count = Order.objects.filter(
                org_id=org_id,
                is_exchange_order=True,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            ).count()
        except Exception:
            exchange_orders_count = 0

        # Return / Exchange rate vs total orders
        try:
            total_orders_in_period = Order.objects.filter(
                org_id=org_id,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            ).count()
            return_rate_pct = round((total_returns / total_orders_in_period) * 100, 2) if total_orders_in_period > 0 else 0
            exchange_rate_pct = round((total_exchanges / total_orders_in_period) * 100, 2) if total_orders_in_period > 0 else 0
        except Exception:
            return_rate_pct = 0
            exchange_rate_pct = 0

        return {
            "total_requests": total,
            "total_returns": total_returns,
            "total_exchanges": total_exchanges,
            "approved_count": approved,
            "received_count": received,
            "refunded_count": refunded,
            "rejected_count": rejected,
            "with_awb_count": with_awb,
            "total_return_value_inr": round(float(return_value), 2),
            "total_exchange_value_inr": round(float(exchange_value), 2),
            "return_rate_pct": return_rate_pct,
            "exchange_rate_pct": exchange_rate_pct,
            "exchange_orders_created": exchange_orders_count,
            "returns_by_status": returns_by_status,
            "exchanges_by_status": exchanges_by_status,
            "top_return_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
            "top_returned_products": [{"product": p, "count": c} for p, c in top_products],
            "top_exchanged_for_products": [{"product": p, "count": c} for p, c in top_exchange_products],
            "by_courier": [{"courier": c, "count": n} for c, n in by_courier],
        }
    except Exception as e:
        logger.warning(f"Failed to fetch returns/exchanges analysis: {e}")
        return None


def _fetch_logistics_payload(org, start_date, end_date):
    """Aggregate all logistics metrics for the AI context payload."""
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    end_date = min(end_date, date.today())
    org_id = org.organization_id

    cache_key = f"logistics_aura_payload:{org.id}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"LOGISTICS AURA cache HIT for {org} ({start_date} to {end_date})")
        return cached

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from django.db import close_old_connections

    tasks = {
        'order_summary': lambda: _fetch_order_status_summary(org_id, start_date, end_date),
        'ndr_analysis': lambda: _fetch_ndr_analysis(org_id, start_date, end_date),
        'rto_analysis': lambda: _fetch_rto_analysis(org_id, start_date, end_date),
        'cod_analysis': lambda: _fetch_cod_analysis(org_id, start_date, end_date),
        'shipping_costs': lambda: _fetch_shipping_cost_analysis(org_id, start_date, end_date),
        'delivery_trends': lambda: _fetch_delivery_trends(org_id, start_date, end_date),
        'problem_locations': lambda: _fetch_top_problem_pincodes(org_id, start_date, end_date),
        'returns_exchanges': lambda: _fetch_returns_exchanges_analysis(org_id, start_date, end_date),
    }

    def _safe_run(name, fn):
        try:
            close_old_connections()
            return name, fn()
        except Exception as e:
            logger.warning(f"Logistics payload '{name}' failed: {e}")
            return name, None

    payload = {"date_range": f"{start_date} to {end_date}"}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_safe_run, name, fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name, result = future.result()
            if result is not None:
                payload[name] = result

    payload['benchmarks'] = LOGISTICS_BENCHMARKS

    try:
        cache.set(cache_key, payload, timeout=900)
    except Exception:
        pass

    return payload


def _build_direct_delivery_rate_response(question, payload, start_date, end_date):
    """
    Return a deterministic response for delivery-rate questions.
    This avoids vague LLM fallbacks when KPI data is already available.
    """
    q = (question or "").lower()
    delivery_rate_tokens = (
        "delivery rate",
        "delivery %",
        "delivery percentage",
        "deliver rate",
    )
    if not any(tok in q for tok in delivery_rate_tokens):
        return None

    order_summary = payload.get("order_summary") or {}
    rate = order_summary.get("delivery_rate_pct")
    total_orders = int(order_summary.get("total_orders") or 0)
    delivered_orders = int(order_summary.get("delivered") or 0)

    # Fallback: derive rate from daily trend rows if summary is unavailable.
    if rate is None:
        trends = payload.get("delivery_trends") or []
        if trends:
            total_orders = sum(int(r.get("orders") or 0) for r in trends)
            delivered_orders = sum(int(r.get("delivered") or 0) for r in trends)
            rate = round((delivered_orders / total_orders) * 100, 2) if total_orders > 0 else 0.0

    if rate is None:
        rate = 0.0

    benchmark = float(LOGISTICS_BENCHMARKS.get("d2c_india_avg_delivery_rate_pct", 85.0))
    delta = round(float(rate) - benchmark, 2)
    if total_orders == 0:
        benchmark_line = "No orders were found in this date range, so performance comparison is not applicable."
    elif delta > 0:
        benchmark_line = f"This is {abs(delta):.2f}% above the typical D2C benchmark ({benchmark:.0f}%)."
    elif delta < 0:
        benchmark_line = f"This is {abs(delta):.2f}% below the typical D2C benchmark ({benchmark:.0f}%)."
    else:
        benchmark_line = f"This is exactly at the typical D2C benchmark ({benchmark:.0f}%)."

    return (
        f"Delivery rate for {start_date} to {end_date}: {float(rate):.2f}%\n"
        f"Delivered orders: {delivered_orders:,} out of {total_orders:,} total orders.\n"
        f"{benchmark_line}"
    )


def build_logistics_system_prompt(base_prompt: str, org=None) -> str:
    """
    Build the full system prompt for Logistics AURA by layering:
      1. Persona lock header (from LogisticsAgentConfiguration)
      2. Base audit prompt (base_prompt arg)
      3. Active global rules (from LogisticsAgentGlobalRule)
      4. Active correction rules (from LogisticsCorrectionRule)
      5. Persona reinforcement footer
    Returns the enriched system prompt string.
    """
    try:
        from core.models import LogisticsAgentConfiguration, LogisticsAgentGlobalRule, LogisticsCorrectionRule
        config = LogisticsAgentConfiguration.objects.filter(is_active=True).first()
        persona = getattr(config, 'persona', 'default') if config else 'default'
        response_style = getattr(config, 'response_style', 'Balanced') if config else 'Balanced'
    except Exception:
        persona = 'default'
        response_style = 'Balanced'

    persona_headers = {
        'default': "You are a professional, data-driven logistics analyst. Be precise, structured, and direct.",
        'warm': "You are a warm and encouraging logistics advisor. Celebrate wins, gently point out issues.",
        'calm': "You are calm and measured. Present findings without alarming language. Be steady and reassuring.",
        'genz': "You're a Gen Z logistics analyst — use energy, casual language, and emoji where it fits. Be smart but keep it fresh.",
        'aggressive': "You are bold and blunt. Call out underperforming couriers directly. No sugarcoating — brands need the hard truth.",
        'zen': "You are minimal and mindful. Short, impactful sentences. Prioritize signal over noise.",
    }
    style_instructions = {
        'Concise': "Keep responses short and to the point. Bullet points preferred. No filler text.",
        'Balanced': "Strike a balance between brevity and depth. Use bullets for key points, 1-2 sentence explanations.",
        'Detailed': "Provide in-depth analysis with full context. Include trend interpretation, root causes, and specific recommendations.",
    }

    header = persona_headers.get(persona, persona_headers['default'])
    style = style_instructions.get(response_style, style_instructions['Balanced'])

    parts = [f"[PERSONA]: {header}", f"[RESPONSE STYLE]: {style}", "", base_prompt]

    # Global rules
    try:
        rules = LogisticsAgentGlobalRule.objects.filter(is_active=True).order_by('-priority', '-created_at')[:20]
        active_rules = [r for r in rules if not r.is_expired]
        if active_rules:
            parts.append("\n\n[GLOBAL RULES — follow these for every response]:")
            for i, rule in enumerate(active_rules, 1):
                parts.append(f"{i}. {rule.rule_text}")
    except Exception:
        pass

    # Correction rules (few-shot)
    try:
        corrections = LogisticsCorrectionRule.objects.filter(is_active=True).order_by('-created_at')[:10]
        if corrections:
            parts.append("\n\n[LEARNED CORRECTIONS — avoid these past mistakes]:")
            for c in corrections:
                parts.append(f"- Mistake: {c.bad_behavior_description}")
                parts.append(f"  Fix: {c.corrected_instruction}")
                if c.example_bad_response:
                    parts.append(f"  BAD example: {c.example_bad_response}")
                if c.example_good_response:
                    parts.append(f"  GOOD example: {c.example_good_response}")
    except Exception:
        pass

    # Persona reinforcement footer
    persona_footers = {
        'genz': "\n\n[REMINDER]: Stay energetic, use relevant emoji, keep the vibe fresh but data-backed.",
        'aggressive': "\n\n[REMINDER]: Be direct and bold. Call underperformers by name. Drive urgency.",
        'zen': "\n\n[REMINDER]: Less is more. Say what matters, nothing else.",
        'warm': "\n\n[REMINDER]: Be encouraging. Acknowledge effort. Soften criticism with context.",
    }
    if persona in persona_footers:
        parts.append(persona_footers[persona])

    return "\n".join(parts)


def run_logistics_chat(
    org,
    question,
    start_date=None,
    end_date=None,
    model_name='gemini-2.5-flash-lite',
    conversation_context=None,
    attached_files=None,
    session_id='',
    user_identifier='',
):
    """
    Conversational interface for Logistics AURA.
    Uses the new google.genai SDK (genai.Client) and supports:
    - File attachments (PDF, images, spreadsheets)
    - Conversation audit logging (LogisticsConversationLog)
    - Dynamic system prompt enrichment via build_logistics_system_prompt()
    Returns dict: {"stream": generator, "system_prompt_snapshot": str}
    """
    import time as _time
    data_json = None
    payload = None
    if start_date and end_date:
        payload = _fetch_logistics_payload(org, start_date, end_date)
        if "error" in payload:
            return payload
        data_json = json.dumps(payload, cls=DecimalEncoder)

    if payload:
        direct_delivery_rate_response = _build_direct_delivery_rate_response(
            question=question,
            payload=payload,
            start_date=start_date,
            end_date=end_date,
        )
        if direct_delivery_rate_response:
            def _direct_stream():
                yield direct_delivery_rate_response

            return {
                "stream": _direct_stream(),
                "system_prompt_snapshot": "DIRECT_DELIVERY_RATE_RESPONSE",
            }

    current_date = timezone.now().date()
    org_name = getattr(org, 'name', str(org))

    # Choose base prompt based on whether we have data
    try:
        from core.models import LogisticsAgentConfiguration
        config = LogisticsAgentConfiguration.objects.filter(is_active=True).first()
        if config:
            if data_json:
                base_prompt = config.system_prompt
            else:
                base_prompt = config.general_prompt or config.system_prompt
            model_name = config.model_name or model_name
        else:
            base_prompt = None
    except Exception:
        base_prompt = None

    if not base_prompt:
        base_prompt = f"""You are Logistics AURA — the friendly logistics assistant for "{org_name}".
Today is {current_date}. You have access to all real logistics data for this brand.

YOUR JOB:
Answer questions about orders, deliveries, returns, exchanges, NDR, RTO, shipping, couriers, payment methods, and trends — using simple, plain language. The person asking may not have a logistics background, so explain things clearly and practically.

WHAT DATA YOU HAVE ACCESS TO:
- Order counts, delivery numbers, revenue, average order value
- How many orders are delivered, in-transit, stuck, or came back (RTO)
- NDR: orders where delivery was attempted but failed (customer refused, not home, etc.)
- RTO: orders that came back to the warehouse
- COD vs prepaid split and revenue by payment type
- Day-by-day order count, revenue, and delivery performance
- Which states have the most delivery failures or returns
- Returns: how many customers returned products, total value returned, why they returned, which products are returned most
- Exchanges: how many customers swapped products, total value, what they exchanged for
- Courier performance (Bluedart, Delhivery, etc.)

HOW TO RESPOND:
- Use plain, conversational language. Write like you're explaining to a business owner, not a developer.
- Format numbers nicely: ₹1,41,172 not 141172.55 | "52%" not "0.52" | "374 orders" not just "374"
- NEVER mention technical terms like "payload", "data structure", "JSON key", "field", "null", or variable names like `total_return_value_inr`
- Instead of "the payload contains total_return_value_inr: 141172.55" say "Customers returned products worth ₹1,41,172"
- Use bullet points and short sections to make answers easy to scan
- Add a simple one-line insight or suggestion at the end when useful (e.g. "Quality issues are the #1 return reason — worth reviewing your packaging or product QC")
- Use ₹ for all monetary values (format with commas: ₹1,41,172)
- When something is performing well vs industry average (85% delivery, 12% RTO, 8% NDR), say so in plain terms
- If data for something isn't available, say "I don't have that detail right now" — don't explain why technically

INDUSTRY AVERAGES (for reference):
- Good delivery rate: 85%+ | Typical RTO rate: 12% | Typical NDR rate: 8% | COD orders: ~60%"""

    enriched_system_prompt = build_logistics_system_prompt(base_prompt, org=org)

    # Append date context + data payload
    if data_json:
        enriched_system_prompt += f"\n\nOrg: {org_name} | Analysis period: {start_date} to {end_date}\nLogistics data payload:\n{data_json}"

    human_message = question

    try:
        from google import genai as genai_client
        from google.genai import types

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return {"error": "GEMINI_API_KEY not configured"}

        client = genai_client.Client(api_key=api_key)

        # Build history from conversation context
        native_messages = []
        if conversation_context:
            for msg in conversation_context[-12:]:
                role = "user" if msg["role"] == "user" else "model"
                content_text = msg.get("content", "")
                # Summarise heavy structured data to save tokens
                if msg.get("structured_data") and not content_text:
                    content_text = "[Logistics data analysis was shown here]"
                if content_text:
                    native_messages.append(
                        types.Content(role=role, parts=[types.Part.from_text(text=content_text)])
                    )

        # Build user parts (text + optional file attachments)
        user_parts = [types.Part.from_text(text=human_message)]

        if attached_files:
            for af in attached_files:
                file_bytes = af.get("data")
                mime = af.get("mime_type", "application/octet-stream")
                if file_bytes:
                    user_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))

        native_messages.append(types.Content(role="user", parts=user_parts))

        config_obj = types.GenerateContentConfig(
            system_instruction=enriched_system_prompt,
            temperature=0.1,
            max_output_tokens=65536,
        )

        t_start = _time.time()

        def _stream_and_log():
            full_response = []
            from core.utils.gemini_fallback import generate_content_stream_with_fallback
            try:
                stream = generate_content_stream_with_fallback(
                    client=client,
                    model=model_name,
                    contents=native_messages,
                    config=config_obj,
                )
                for chunk in stream:
                    if chunk.text:
                        full_response.append(chunk.text)
                        yield chunk.text
            finally:
                # Log to audit trail
                try:
                    from core.models import LogisticsConversationLog
                    elapsed_ms = int((_time.time() - t_start) * 1000)
                    LogisticsConversationLog.objects.create(
                        session_id=session_id or '',
                        user_identifier=user_identifier or '',
                        shop_name=org_name,
                        system_prompt_snapshot=enriched_system_prompt[:4000],
                        user_message=human_message[:2000],
                        ai_response=''.join(full_response)[:8000],
                        model_used=model_name,
                        response_time_ms=elapsed_ms,
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log logistics conversation: {log_err}")

        return {"stream": _stream_and_log(), "system_prompt_snapshot": enriched_system_prompt}

    except Exception as e:
        logger.error(f"Logistics AI chat failed: {e}", exc_info=True)
        return {"error": str(e)}
