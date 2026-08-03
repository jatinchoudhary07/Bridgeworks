from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, F, Avg
from django.utils import timezone
from datetime import timedelta
import calendar
import re
import json
from decimal import Decimal
from core.models import (
    Order, CampaignDailyMetric, MetaCampaign, MetaAdSet, MetaAd,
    AdSetDailyMetric, AdDailyMetric, MarketingSettings,
    GoogleAdsCredential, GoogleCampaignDailyMetric,
    GoogleSearchTermMetric, GoogleDemographicMetric, GoogleAdPerformanceMetric,
    StoreFinancials, MarketingAlert
)
from core.permissions import IsMarketingAnalyst
import threading
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Helper: Date Range
# =============================================================================

def get_date_range_from_preset(preset):
    today = timezone.now().date()
    
    if preset == 'today':
        return today, today
    elif preset == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif preset == 'this_week':
        mon = today - timedelta(days=today.weekday())
        return mon, today
    elif preset == 'last_week':
        mon = today - timedelta(days=today.weekday() + 7)
        return mon, mon + timedelta(days=6)
    elif preset == 'this_month':
        return today.replace(day=1), today
    elif preset == 'last_month':
        first_of_this = today.replace(day=1)
        last_of_last = first_of_this - timedelta(days=1)
        return last_of_last.replace(day=1), last_of_last
    elif preset == 'this_quarter':
        m = 3 * ((today.month - 1) // 3) + 1
        return today.replace(month=m, day=1), today
    elif preset == 'last_quarter':
        m = 3 * ((today.month - 1) // 3) + 1
        first_of_this_q = today.replace(month=m, day=1)
        last_of_last_q = first_of_this_q - timedelta(days=1)
        m_last = 3 * ((last_of_last_q.month - 1) // 3) + 1
        return last_of_last_q.replace(month=m_last, day=1), last_of_last_q
    elif preset == 'this_year':
        return today.replace(month=1, day=1), today
    elif preset == 'last_year':
        return today.replace(year=today.year-1, month=1, day=1), today.replace(year=today.year-1, month=12, day=31)
    elif preset == 'last_3d':
        return today - timedelta(days=3), today
    elif preset == 'last_7d':
        return today - timedelta(days=7), today
    elif preset == 'last_14d':
        return today - timedelta(days=14), today
    elif preset == 'last_28d':
        return today - timedelta(days=28), today
    elif preset == 'last_30d':
        return today - timedelta(days=30), today
    elif preset == 'last_90d':
        return today - timedelta(days=90), today
    elif preset in ['maximum', 'data_maximum']:
        return None, None
    else:
        # Default fallback: last 7 days
        return today - timedelta(days=7), today


# =============================================================================
# Helper: Get Org
# =============================================================================

def _get_org(request):
    user = request.user
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials
    elif hasattr(user, 'team_settings') and user.team_settings.organization:
        return user.team_settings.organization
    return None


def _get_date_params(request):
    """Parse date range from request params or data."""
    data_source = request.GET if request.method == 'GET' else request.data
    
    date_preset = data_source.get('date_preset')
    start_date_str = data_source.get('start_date')
    end_date_str = data_source.get('end_date')
    
    if date_preset:
        sd, ed = get_date_range_from_preset(date_preset)
        return sd, ed
    elif start_date_str and end_date_str:
        from datetime import date as dt_date
        return dt_date.fromisoformat(start_date_str), dt_date.fromisoformat(end_date_str)
    else:
        return get_date_range_from_preset('last_7d')


def _detect_date_ranges_in_question(question):
    """
    Search for date-related keywords and return ONE or TWO date ranges.
    Returns: (start1, end1), (start2, end2) or None
    Today is assumed from timezone.now().date()
    """
    from datetime import date, timedelta
    import calendar
    import re
    
    today = timezone.now().date()
    # Normalize question text
    q = question.lower().strip()
    
    # 0. Check for "same day last year"
    if "same day" in q and ("last year" in q or "2025" in q):
        target_day = today.replace(year=2025)
        return (target_day, target_day), (today, today)
        
    months_map = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }
    
    # Try to extract day-specific dates sequentially
    matches = []
    
    # 1. Numeric dates: e.g. 13/05/2026, 2026-06-13
    num_pattern = r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})\b'
    for m in re.finditer(num_pattern, q):
        d_str = m.group(1)
        parsed_d = None
        for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%y', '%d-%m-%y'):
            try:
                from datetime import datetime
                parsed_d = datetime.strptime(d_str, fmt).date()
                break
            except ValueError:
                pass
        if parsed_d:
            matches.append((m.start(), m.end(), parsed_d))
            
    # 2. Word pattern A: <day> <month> <year?> e.g., "13th may 2026", "13 may", "1st of june"
    word_pattern_a = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(\d{2,4}))?\b'
    for m in re.finditer(word_pattern_a, q):
        day = int(m.group(1))
        month_str = m.group(2)
        month = months_map[month_str]
        year_str = m.group(3)
        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = today.year - 1 if ("last year" in q or "2025" in q) else today.year
        try:
            parsed_d = date(year, month, day)
            matches.append((m.start(), m.end(), parsed_d))
        except ValueError:
            pass

    # 3. Word pattern B: <month> <day> <year?> e.g., "may 13th, 2026", "may 13", "june 13th"
    word_pattern_b = r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,\s*(\d{2,4})|\s+(\d{2,4}))?\b'
    for m in re.finditer(word_pattern_b, q):
        month_str = m.group(1)
        month = months_map[month_str]
        day = int(m.group(2))
        year_str = m.group(3) or m.group(4)
        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            year = today.year - 1 if ("last year" in q or "2025" in q) else today.year
        try:
            parsed_d = date(year, month, day)
            matches.append((m.start(), m.end(), parsed_d))
        except ValueError:
            pass
            
    # Filter overlaps (sequential ordering)
    matches.sort(key=lambda x: x[0])
    non_overlapping = []
    last_end = -1
    for start, end, parsed_d in matches:
        if start >= last_end:
            non_overlapping.append(parsed_d)
            last_end = end
            
    # If we found day-specific dates:
    if len(non_overlapping) >= 2:
        if len(non_overlapping) == 2:
            # Single range from date1 to date2
            sd, ed = min(non_overlapping), max(non_overlapping)
            return (sd, ed), None
        elif len(non_overlapping) == 4:
            # Two ranges (comparison)
            sorted_dates = sorted(non_overlapping)
            return (sorted_dates[0], sorted_dates[1]), (sorted_dates[2], sorted_dates[3])
        else:
            # Fallback: return first to last as a range
            sd, ed = min(non_overlapping), max(non_overlapping)
            return (sd, ed), None
    elif len(non_overlapping) == 1:
        # Single day
        return (non_overlapping[0], non_overlapping[0]), None
        
    # No day-specific dates found, look for month-only mentions or presets
    detected_ranges = []
    
    def _get_month_dates_by_num(month_num, year):
        try:
            first = date(year, month_num, 1)
            last = date(year, month_num, calendar.monthrange(year, month_num)[1])
            return first, last
        except:
            return None, None

    for m_name, m_num in months_map.items():
        if not re.search(rf'\b{m_name}\b', q):
            continue
        if "last year" in q or "previous year" in q or "2025" in q:
            sd, ed = _get_month_dates_by_num(m_num, today.year - 1)
            if sd: detected_ranges.append((sd, ed))
        if "this year" in q or "2026" in q or "current year" in q or "compare" in q:
            sd, ed = _get_month_dates_by_num(m_num, today.year)
            if sd: detected_ranges.append((sd, ed))
        if not any(y in q for y in ["2025", "2026", "last year", "next year", "previous year"]) and not ("compare" in q):
            sd, ed = _get_month_dates_by_num(m_num, today.year)
            if sd: detected_ranges.append((sd, ed))
            
    # Presets
    if not detected_ranges:
        presets = {
            'last year': 'last_year', '2025': 'last_year',
            'last month': 'last_month', 'this month': 'this_month',
            'yesterday': 'yesterday', 'today': 'today',
            'last 7 days': 'last_7d', 'last 30 days': 'last_30d',
            'last week': 'last_7d', 'this week': 'last_7d',
            'past week': 'last_7d', 'past month': 'last_month',
        }
        for kw, pr in presets.items():
            if kw in q:
                sd, ed = get_date_range_from_preset(pr)
                if sd: detected_ranges.append((sd, ed))
                
    # Dynamic N days
    if not detected_ranges:
        n_days_match = re.search(r'(?:last|past|previous)\s+(\d+)\s*days?', q)
        if n_days_match:
            n = int(n_days_match.group(1))
            if 1 <= n <= 365:
                ed = today
                sd = today - timedelta(days=n)
                detected_ranges.append((sd, ed))
                
    # Deduplicate
    unique_ranges = []
    for r in detected_ranges:
        if r not in unique_ranges:
            unique_ranges.append(r)
            
    if not unique_ranges:
        return None, None
    if len(unique_ranges) >= 2:
        return unique_ranges[0], unique_ranges[1]
    return unique_ranges[0], None


# =============================================================================
# Funnel fields helper for aggregation
# =============================================================================

FUNNEL_FIELDS = [
    'reach', 'engagement', 'view_content', 'add_to_cart',
    'initiate_checkout', 'add_payment_info', 'outbound_clicks'
]

def _compute_ratios(spd, rev, pur, imp, clk, row_data):
    """Compute derived ratios from base metrics."""
    roas = round(rev / spd, 2) if spd > 0 else Decimal('0.00')
    cpa = round(spd / pur, 2) if pur > 0 else Decimal('0.00')
    cpc = round(spd / clk, 2) if clk > 0 else Decimal('0.00')
    cpm = round((spd / imp) * 1000, 2) if imp > 0 else Decimal('0.00')
    ctr = round((clk / imp) * 100, 2) if imp > 0 else Decimal('0.00')
    cvr = round((pur / clk) * 100, 2) if clk > 0 else Decimal('0.00')
    
    vc = row_data.get('view_content', 0) or 0
    ob = row_data.get('outbound_clicks', 0) or 0
    vc_pct = round((vc / clk) * 100, 2) if clk > 0 else Decimal('0.00')
    outbound_ctr = round((ob / imp) * 100, 2) if imp > 0 else Decimal('0.00')

    return {
        'roas': roas, 'cpa': cpa, 'cpc': cpc, 'cpm': cpm, 'ctr': ctr,
        'cvr': cvr, 'view_content_pct': vc_pct, 'outbound_ctr': outbound_ctr,
    }


# =============================================================================
# 1. Marketing Overview (with GST + AOV)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def marketing_overview(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization associated with this user"}, status=400)
    
    sd, ed = _get_date_params(request)
    start_date = sd.strftime('%Y-%m-%d') if sd else None
    end_date = ed.strftime('%Y-%m-%d') if ed else None
    
    # GST Rate
    try:
        ms = MarketingSettings.objects.get(shop=org)
        gst_rate = ms.gst_rate
    except MarketingSettings.DoesNotExist:
        gst_rate = Decimal('18.00')
    
    gst_multiplier = 1 + (gst_rate / 100)
    
    # 1. Shopify Store Revenue
    import zoneinfo
    tz_name = request.headers.get('X-User-Timezone', 'Asia/Kolkata')
    try:
        user_tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        user_tz = timezone.get_current_timezone()
    from django.db.models.functions import TruncDate

    orders_qs = Order.objects.filter(org_id=org.organization_id)
    if start_date and end_date:
        orders_qs = orders_qs.annotate(created_at_local=TruncDate('created_at', tzinfo=user_tz)).filter(
            created_at_local__gte=start_date, created_at_local__lte=end_date
        )
    
    shopify_stats = orders_qs.aggregate(
        total_revenue=Sum('total_price'),
        total_purchases=Count('id'),
        avg_order_value=Avg('total_price')
    )
    
    total_store_revenue = shopify_stats['total_revenue'] or Decimal('0.00')
    total_store_purchases = shopify_stats['total_purchases'] or 0
    aov = round(shopify_stats['avg_order_value'] or Decimal('0.00'), 2)


    # 2. Meta Ads Metrics
    meta_qs = CampaignDailyMetric.objects.filter(
        credential__shop=org, credential__platform='Meta'
    )
    if start_date and end_date:
        meta_qs = meta_qs.filter(date__range=[start_date, end_date])
    
    meta_stats = meta_qs.aggregate(
        spend=Sum('spend'), revenue=Sum('revenue'), purchases=Sum('purchases'),
        impressions=Sum('impressions'), clicks=Sum('clicks'), reach=Sum('reach'),
    )
    
    meta_spend = meta_stats['spend'] or Decimal('0.00')
    meta_revenue = meta_stats['revenue'] or Decimal('0.00')
    meta_purchases = meta_stats['purchases'] or 0
    meta_reach = meta_stats['reach'] or 0
    
    meta_spend_after_tax = round(meta_spend * gst_multiplier, 2)
    meta_roas = round(meta_revenue / meta_spend, 2) if meta_spend > 0 else Decimal('0.00')
    meta_roas_after_tax = round(meta_revenue / meta_spend_after_tax, 2) if meta_spend_after_tax > 0 else Decimal('0.00')

    # 3. Google Ads Metrics
    google_qs = GoogleCampaignDailyMetric.objects.filter(credential__shop=org)
    if start_date and end_date:
        google_qs = google_qs.filter(date__range=[start_date, end_date])
    
    google_stats = google_qs.aggregate(
        spend=Sum('spend'), conversions=Sum('conversions'), revenue=Sum('revenue'),
        impressions=Sum('impressions'), clicks=Sum('clicks')
    )
    
    google_spend = google_stats['spend'] or Decimal('0.00')
    google_conversions = google_stats['conversions'] or Decimal('0.00')
    google_revenue = google_stats['revenue'] or Decimal('0.00')
    google_impressions = google_stats['impressions'] or 0
    google_clicks = google_stats['clicks'] or 0
    
    google_spend_after_tax = round(google_spend * gst_multiplier, 2)
    google_cpa = round(google_spend / google_conversions, 2) if google_conversions > 0 else Decimal('0.00')
    google_roas = round(google_revenue / google_spend, 2) if google_spend > 0 else Decimal('0.00')
    google_roas_after_tax = round(google_revenue / google_spend_after_tax, 2) if google_spend_after_tax > 0 else Decimal('0.00')
    
    # Platform breakdown
    platforms = [
        {
            "platform": "Meta Ads",
            "spend": meta_spend,
            "spend_after_tax": meta_spend_after_tax,
            "revenue": meta_revenue,
            "purchases": meta_purchases,
            "reach": meta_reach,
            "roas": meta_roas,
            "roas_after_tax": meta_roas_after_tax,
            "blended_roas": round(total_store_revenue / meta_spend, 2) if meta_spend > 0 else Decimal('0.00'),
            "blended_roas_after_tax": round(total_store_revenue / meta_spend_after_tax, 2) if meta_spend_after_tax > 0 else Decimal('0.00'),
        },
        {
            "platform": "Google Ads",
            "spend": google_spend,
            "spend_after_tax": google_spend_after_tax,
            "revenue": google_revenue,
            "purchases": int(google_conversions), 
            "reach": 0, # reach not in campaign metrics
            "roas": google_roas,
            "roas_after_tax": google_roas_after_tax,
            "blended_roas": round(total_store_revenue / google_spend, 2) if google_spend > 0 else Decimal('0.00'),
            "blended_roas_after_tax": round(total_store_revenue / google_spend_after_tax, 2) if google_spend_after_tax > 0 else Decimal('0.00'),
            "conversions": google_conversions,
            "cpa": google_cpa,
            "impressions": google_impressions,
            "clicks": google_clicks,
        },
    ]
    
    total_ad_spend = meta_spend + google_spend
    total_ad_spend_after_tax = meta_spend_after_tax + google_spend_after_tax
    blended_roas = round(total_store_revenue / total_ad_spend, 2) if total_ad_spend > 0 else Decimal('0.00')
    blended_roas_after_tax = round(total_store_revenue / total_ad_spend_after_tax, 2) if total_ad_spend_after_tax > 0 else Decimal('0.00')
    
    return Response({
        "summary": {
            "total_spend": total_ad_spend,
            "total_spend_after_tax": total_ad_spend_after_tax,
            "total_revenue": total_store_revenue,
            "total_purchases": total_store_purchases,
            "aov": aov,
            "blended_roas": blended_roas,
            "blended_roas_after_tax": blended_roas_after_tax,
            "mer": blended_roas,
            "mer_after_tax": blended_roas_after_tax,
            "gst_rate": gst_rate,
        },
        "shopify": {
            "revenue": total_store_revenue,
            "orders": total_store_purchases,
            "aov": aov,
        },
        "platforms": platforms
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def google_campaigns_list(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization found"}, status=400)
    
    sd, ed = _get_date_params(request)
    
    qs = GoogleCampaignDailyMetric.objects.filter(credential__shop=org)
    if sd and ed:
        qs = qs.filter(date__range=[sd.strftime('%Y-%m-%d'), ed.strftime('%Y-%m-%d')])
        
    metrics = qs.values('campaign_name').annotate(
        spend=Sum('spend'),
        conversions=Sum('conversions'),
        revenue=Sum('revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
        avg_is=Avg('search_impression_share'),
        avg_budget_lost_is=Avg('search_budget_lost_impression_share')
    ).order_by('-spend')
    
    results = []
    for m in metrics:
        spd = m['spend'] or Decimal('0.00')
        conv = m['conversions'] or Decimal('0.00')
        rev = m['revenue'] or Decimal('0.00')
        clk = m['clicks'] or 0
        imp = m['impressions'] or 0
        
        results.append({
            'campaign_name': m['campaign_name'],
            'spend': spd,
            'conversions': conv,
            'revenue': rev,
            'impressions': imp,
            'clicks': clk,
            'cpc': round(spd / clk, 2) if clk > 0 else Decimal('0.00'),
            'cpa': round(spd / conv, 2) if conv > 0 else Decimal('0.00'),
            'ctr': round((clk / imp) * 100, 2) if imp > 0 else Decimal('0.00'),
            'roas': round(rev / spd, 2) if spd > 0 else Decimal('0.00'),
            'impression_share': round(m['avg_is'] * 100, 2) if m['avg_is'] else None,
            'budget_lost_is': round(m['avg_budget_lost_is'] * 100, 2) if m['avg_budget_lost_is'] else None,
        })
        
    return Response(results)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def google_search_terms_list(request):
    org = _get_org(request)
    if not org: return Response({"error": "No organization"}, status=400)
    sd, ed = _get_date_params(request)
    
    qs = GoogleSearchTermMetric.objects.filter(credential__shop=org)
    if sd and ed:
        qs = qs.filter(date__range=[sd, ed])
    
    terms = qs.values('search_term').annotate(
        spend=Sum('spend'), conversions=Sum('conversions'),
        revenue=Sum('revenue'), clicks=Sum('clicks')
    ).order_by('-spend')[:50]
    
    return Response(terms)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def google_demographics_summary(request):
    org = _get_org(request)
    if not org: return Response({"error": "No organization"}, status=400)
    sd, ed = _get_date_params(request)
    
    qs = GoogleDemographicMetric.objects.filter(credential__shop=org)
    if sd and ed:
        qs = qs.filter(date__range=[sd, ed])
    
    results = {}
    for dim in ['age', 'gender', 'device']:
        data = qs.filter(dimension=dim).values('dimension_value').annotate(
            spend=Sum('spend'), conversions=Sum('conversions'),
            revenue=Sum('revenue'), clicks=Sum('clicks')
        ).order_by('-spend')
        results[dim] = list(data)
        
    return Response(results)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def google_ads_creative_list(request):
    org = _get_org(request)
    if not org: return Response({"error": "No organization"}, status=400)
    sd, ed = _get_date_params(request)
    
    # We want to group by ad_id to show aggregate performance of a creative
    qs = GoogleAdPerformanceMetric.objects.filter(credential__shop=org)
    if sd and ed:
        qs = qs.filter(date__range=[sd, ed])
    
    # Note: headlines and descriptions are JSON, so we take the first seen entry for the display
    ads_data = qs.values('ad_id', 'campaign_name', 'ad_group_name', 'headlines', 'descriptions').annotate(
        spend=Sum('spend'), conversions=Sum('conversions'),
        revenue=Sum('revenue'), clicks=Sum('clicks')
    ).order_by('-spend')
    
    return Response(ads_data)


# =============================================================================
# 2. Marketing Settings CRUD
# =============================================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def marketing_settings_view(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)
    
    ms, created = MarketingSettings.objects.get_or_create(shop=org)
    
    if request.method == 'GET':
        return Response({"gst_rate": ms.gst_rate})
    
    elif request.method == 'PUT':
        gst_rate = request.data.get('gst_rate')
        if gst_rate is not None:
            ms.gst_rate = Decimal(str(gst_rate))
            ms.save()
        return Response({"gst_rate": ms.gst_rate})


# =============================================================================
# 3. Meta Campaigns List (with funnel metrics)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def meta_campaigns_list(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)
    
    sd, ed = _get_date_params(request)
    
    # Structural campaigns
    meta_campaigns = MetaCampaign.objects.filter(
        credential__shop=org, credential__platform='Meta'
    )
    
    all_campaigns = {}
    for c in meta_campaigns:
        all_campaigns[c.campaign_id] = {
            "campaign_id": c.campaign_id,
            "campaign_name": c.name,
            "status": c.status,
            "effective_status": c.effective_status,
            "daily_budget": c.daily_budget,
            "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
            "purchases": 0, "impressions": 0, "clicks": 0,
            "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
            "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
            "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
            "reach": 0, "engagement": 0, "view_content": 0,
            "add_to_cart": 0, "initiate_checkout": 0,
            "add_payment_info": 0, "outbound_clicks": 0,
            "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
        }

    # Metrics
    qs = CampaignDailyMetric.objects.filter(
        credential__shop=org, credential__platform='Meta'
    )
    if sd and ed:
        qs = qs.filter(date__range=[sd.strftime('%Y-%m-%d'), ed.strftime('%Y-%m-%d')])
    
    agg_fields = {
        'total_spend': Sum('spend'), 'total_revenue': Sum('revenue'),
        'total_purchases': Sum('purchases'), 'total_impressions': Sum('impressions'),
        'total_clicks': Sum('clicks'), 'total_reach': Sum('reach'),
        'total_engagement': Sum('engagement'), 'total_view_content': Sum('view_content'),
        'total_add_to_cart': Sum('add_to_cart'), 'total_initiate_checkout': Sum('initiate_checkout'),
        'total_add_payment_info': Sum('add_payment_info'), 'total_outbound_clicks': Sum('outbound_clicks'),
    }
    
    metrics = qs.values('campaign_id', 'campaign_name').annotate(**agg_fields)
    
    for m in metrics:
        cid = m['campaign_id']
        if cid not in all_campaigns:
            all_campaigns[cid] = {
                "campaign_id": cid, "campaign_name": m['campaign_name'],
                "status": "UNKNOWN", "effective_status": "UNKNOWN",
                "daily_budget": Decimal('0.00'),
                "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
                "purchases": 0, "impressions": 0, "clicks": 0,
                "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
                "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
                "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
                "reach": 0, "engagement": 0, "view_content": 0,
                "add_to_cart": 0, "initiate_checkout": 0,
                "add_payment_info": 0, "outbound_clicks": 0,
                "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
            }
        
        spd = m['total_spend'] or Decimal('0.00')
        rev = m['total_revenue'] or Decimal('0.00')
        pur = m['total_purchases'] or 0
        imp = m['total_impressions'] or 0
        clk = m['total_clicks'] or 0
        
        funnel = {
            'reach': m['total_reach'] or 0,
            'engagement': m['total_engagement'] or 0,
            'view_content': m['total_view_content'] or 0,
            'add_to_cart': m['total_add_to_cart'] or 0,
            'initiate_checkout': m['total_initiate_checkout'] or 0,
            'add_payment_info': m['total_add_payment_info'] or 0,
            'outbound_clicks': m['total_outbound_clicks'] or 0,
        }
        
        ratios = _compute_ratios(spd, rev, pur, imp, clk, funnel)
        
        camp = all_campaigns[cid]
        camp.update({
            'spend': spd, 'revenue': rev, 'purchases': pur,
            'impressions': imp, 'clicks': clk,
            **funnel, **ratios,
        })

    results = sorted(all_campaigns.values(), key=lambda x: x['spend'], reverse=True)
    return Response(results)


# =============================================================================
# 4. Meta Ad Sets List (with funnel metrics)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def meta_adsets_list(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    campaign_id = request.GET.get('campaign_id')
    sd, ed = _get_date_params(request)

    # Structural
    adset_qs = MetaAdSet.objects.filter(credential__shop=org, credential__platform='Meta')
    if campaign_id:
        adset_qs = adset_qs.filter(campaign_id=campaign_id)

    all_adsets = {}
    zero_entry = lambda a: {
        "adset_id": a.adset_id, "adset_name": a.name,
        "campaign_id": a.campaign_id,
        "status": a.status, "effective_status": a.effective_status,
        "daily_budget": a.daily_budget,
        "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
        "purchases": 0, "impressions": 0, "clicks": 0,
        "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
        "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
        "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
        "reach": 0, "engagement": 0, "view_content": 0,
        "add_to_cart": 0, "initiate_checkout": 0,
        "add_payment_info": 0, "outbound_clicks": 0,
        "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
    }
    for a in adset_qs:
        all_adsets[a.adset_id] = zero_entry(a)

    # Metrics
    metric_qs = AdSetDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta')
    if campaign_id:
        metric_qs = metric_qs.filter(campaign_id=campaign_id)
    if sd and ed:
        metric_qs = metric_qs.filter(date__range=[sd.strftime('%Y-%m-%d'), ed.strftime('%Y-%m-%d')])

    agg_fields = {
        'total_spend': Sum('spend'), 'total_revenue': Sum('revenue'),
        'total_purchases': Sum('purchases'), 'total_impressions': Sum('impressions'),
        'total_clicks': Sum('clicks'), 'total_reach': Sum('reach'),
        'total_engagement': Sum('engagement'), 'total_view_content': Sum('view_content'),
        'total_add_to_cart': Sum('add_to_cart'), 'total_initiate_checkout': Sum('initiate_checkout'),
        'total_add_payment_info': Sum('add_payment_info'), 'total_outbound_clicks': Sum('outbound_clicks'),
    }
    metrics = metric_qs.values('adset_id', 'adset_name').annotate(**agg_fields)

    for m in metrics:
        aid = m['adset_id']
        if aid not in all_adsets:
            all_adsets[aid] = {
                "adset_id": aid, "adset_name": m['adset_name'],
                "campaign_id": campaign_id or "", "status": "UNKNOWN",
                "effective_status": "UNKNOWN", "daily_budget": Decimal('0.00'),
                "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
                "purchases": 0, "impressions": 0, "clicks": 0,
                "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
                "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
                "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
                "reach": 0, "engagement": 0, "view_content": 0,
                "add_to_cart": 0, "initiate_checkout": 0,
                "add_payment_info": 0, "outbound_clicks": 0,
                "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
            }

        spd = m['total_spend'] or Decimal('0.00')
        rev = m['total_revenue'] or Decimal('0.00')
        pur = m['total_purchases'] or 0
        imp = m['total_impressions'] or 0
        clk = m['total_clicks'] or 0
        funnel = {
            'reach': m['total_reach'] or 0, 'engagement': m['total_engagement'] or 0,
            'view_content': m['total_view_content'] or 0, 'add_to_cart': m['total_add_to_cart'] or 0,
            'initiate_checkout': m['total_initiate_checkout'] or 0,
            'add_payment_info': m['total_add_payment_info'] or 0,
            'outbound_clicks': m['total_outbound_clicks'] or 0,
        }
        ratios = _compute_ratios(spd, rev, pur, imp, clk, funnel)
        entry = all_adsets[aid]
        entry.update({'spend': spd, 'revenue': rev, 'purchases': pur, 'impressions': imp, 'clicks': clk, **funnel, **ratios})

    results = sorted(all_adsets.values(), key=lambda x: x['spend'], reverse=True)
    return Response(results)


# =============================================================================
# 5. Meta Ads List (with funnel metrics)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def meta_ads_list(request):
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    adset_id = request.GET.get('adset_id')
    campaign_id = request.GET.get('campaign_id')
    sd, ed = _get_date_params(request)

    # Structural
    ad_qs = MetaAd.objects.filter(credential__shop=org, credential__platform='Meta')
    if adset_id:
        ad_qs = ad_qs.filter(adset_id=adset_id)
    elif campaign_id:
        ad_qs = ad_qs.filter(campaign_id=campaign_id)

    all_ads = {}
    for a in ad_qs:
        all_ads[a.ad_id] = {
            "ad_id": a.ad_id, "ad_name": a.name,
            "adset_id": a.adset_id, "campaign_id": a.campaign_id,
            "status": a.status, "effective_status": a.effective_status,
            "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
            "purchases": 0, "impressions": 0, "clicks": 0,
            "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
            "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
            "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
            "reach": 0, "engagement": 0, "view_content": 0,
            "add_to_cart": 0, "initiate_checkout": 0,
            "add_payment_info": 0, "outbound_clicks": 0,
            "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
        }

    # Metrics
    metric_qs = AdDailyMetric.objects.filter(credential__shop=org, credential__platform='Meta')
    if adset_id:
        metric_qs = metric_qs.filter(adset_id=adset_id)
    elif campaign_id:
        metric_qs = metric_qs.filter(campaign_id=campaign_id)
    if sd and ed:
        metric_qs = metric_qs.filter(date__range=[sd.strftime('%Y-%m-%d'), ed.strftime('%Y-%m-%d')])

    agg_fields = {
        'total_spend': Sum('spend'), 'total_revenue': Sum('revenue'),
        'total_purchases': Sum('purchases'), 'total_impressions': Sum('impressions'),
        'total_clicks': Sum('clicks'), 'total_reach': Sum('reach'),
        'total_engagement': Sum('engagement'), 'total_view_content': Sum('view_content'),
        'total_add_to_cart': Sum('add_to_cart'), 'total_initiate_checkout': Sum('initiate_checkout'),
        'total_add_payment_info': Sum('add_payment_info'), 'total_outbound_clicks': Sum('outbound_clicks'),
    }
    metrics = metric_qs.values('ad_id', 'ad_name').annotate(**agg_fields)

    for m in metrics:
        aid = m['ad_id']
        if aid not in all_ads:
            all_ads[aid] = {
                "ad_id": aid, "ad_name": m['ad_name'],
                "adset_id": adset_id or "", "campaign_id": campaign_id or "",
                "status": "UNKNOWN", "effective_status": "UNKNOWN",
                "spend": Decimal('0.00'), "revenue": Decimal('0.00'),
                "purchases": 0, "impressions": 0, "clicks": 0,
                "roas": Decimal('0.00'), "cpa": Decimal('0.00'),
                "cpc": Decimal('0.00'), "cpm": Decimal('0.00'),
                "ctr": Decimal('0.00'), "cvr": Decimal('0.00'),
                "reach": 0, "engagement": 0, "view_content": 0,
                "add_to_cart": 0, "initiate_checkout": 0,
                "add_payment_info": 0, "outbound_clicks": 0,
                "view_content_pct": Decimal('0.00'), "outbound_ctr": Decimal('0.00'),
            }

        spd = m['total_spend'] or Decimal('0.00')
        rev = m['total_revenue'] or Decimal('0.00')
        pur = m['total_purchases'] or 0
        imp = m['total_impressions'] or 0
        clk = m['total_clicks'] or 0
        funnel = {
            'reach': m['total_reach'] or 0, 'engagement': m['total_engagement'] or 0,
            'view_content': m['total_view_content'] or 0, 'add_to_cart': m['total_add_to_cart'] or 0,
            'initiate_checkout': m['total_initiate_checkout'] or 0,
            'add_payment_info': m['total_add_payment_info'] or 0,
            'outbound_clicks': m['total_outbound_clicks'] or 0,
        }
        ratios = _compute_ratios(spd, rev, pur, imp, clk, funnel)
        entry = all_ads[aid]
        entry.update({'spend': spd, 'revenue': rev, 'purchases': pur, 'impressions': imp, 'clicks': clk, **funnel, **ratios})

    results = sorted(all_ads.values(), key=lambda x: x['spend'], reverse=True)
    return Response(results)


# =============================================================================
# 6. Demographics (Live Meta API call)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def meta_demographic_insights(request):
    """
    Fetches demographic breakdowns live from Meta API.
    ?breakdown=age_gender | device | region
    &date_preset=last_30d
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    from core.models import MarketingCredential
    cred = MarketingCredential.objects.filter(shop=org, platform='Meta', is_active=True).first()
    if not cred:
        return Response({"error": "No Meta credentials found"}, status=400)

    breakdown_type = request.GET.get('breakdown', 'age_gender')
    
    # Hybrid Mode: Check for custom calendar dates vs presets
    date_preset = request.GET.get('date_preset')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount

        FacebookAdsApi.init(
            app_id=cred.get_app_id(),
            app_secret=cred.get_app_secret(),
            access_token=cred.get_access_token()
        )
        account = AdAccount(cred.ad_account_id)

        fields = ['spend', 'impressions', 'clicks', 'reach', 'actions', 'action_values']
        params = {'time_increment': 'all_days'}
        
        # Hybrid Parameter Switching
        if start_date_str and end_date_str:
            params['time_range'] = {'since': start_date_str, 'until': end_date_str}
        elif date_preset and date_preset not in ['', 'undefined']:
            params['date_preset'] = date_preset
        else:
            params['date_preset'] = 'last_30d' # Safe default

        # Apply breakdowns
        if breakdown_type == 'age_gender':
            params['breakdowns'] = ['age', 'gender']
        elif breakdown_type == 'device':
            params['breakdowns'] = ['impression_device']
        elif breakdown_type == 'region':
            params['breakdowns'] = ['region']
        elif breakdown_type == 'platform':
            params['breakdowns'] = ['publisher_platform']
        else:
            params['breakdowns'] = ['age', 'gender']

        insights = account.get_insights(fields=fields, params=params)

        def _extract(actions, action_type):
            if not actions:
                return 0
            for a in actions:
                if a.get('action_type') == action_type:
                    return int(float(a.get('value', '0')))
            return 0

        def _extract_val(action_values, action_type):
            if not action_values:
                return Decimal('0.00')
            for a in action_values:
                if a.get('action_type') == action_type:
                    return Decimal(a.get('value', '0'))
            return Decimal('0.00')

        results = []
        for item in insights:
            row = {
                'spend': Decimal(item.get('spend', '0')),
                'impressions': int(item.get('impressions', '0')),
                'clicks': int(item.get('clicks', '0')),
                'reach': int(item.get('reach', '0')),
                'purchases': _extract(item.get('actions', []), 'purchase'),
                'revenue': _extract_val(item.get('action_values', []), 'purchase'),
            }

            if breakdown_type == 'age_gender':
                row['age'] = item.get('age', 'Unknown')
                row['gender'] = item.get('gender', 'Unknown')
            elif breakdown_type == 'device':
                row['device'] = item.get('impression_device', 'Unknown')
            elif breakdown_type == 'region':
                row['region'] = item.get('region', 'Unknown')
            elif breakdown_type == 'platform':
                row['platform'] = item.get('publisher_platform', 'Unknown')

            results.append(row)

        return Response({"breakdown_type": breakdown_type, "data": results})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


# =============================================================================
# 7. AI Marketing Intelligence (Gemini)
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def marketing_ai_sessions(request):
    """
    GET: List all past AI chat sessions.
    POST: Create a new session and generate the first structural insight report.
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    from core.models import MarketingAIChatSession, MarketingAIChatMessage

    if request.method == 'GET':
        sessions = MarketingAIChatSession.objects.filter(shop=org, user=request.user).order_by('-created_at')
        data = [{
            "id": s.id,
            "title": s.title,
            "date_preset": s.date_preset,
            "model_name": s.model_name,
            "created_at": s.created_at
        } for s in sessions]
        return Response(data)

    elif request.method == 'POST':
        sd, ed = _get_date_params(request)
        model_name = request.data.get('model', 'gemini-2.5-flash-lite')
        date_preset = request.data.get('date_preset', '')
        skip_initial = request.data.get('skip_initial_analysis', False)

        try:
            # 1. Create session
            from django.utils import timezone
            
            # Hybrid: Check if this is a general chat or a dated audit
            if not date_preset:
                title = "New Chat"
                session = MarketingAIChatSession.objects.create(
                    shop=org, user=request.user, title=title, model_name=model_name
                )
                return Response({
                    "message": "General chat session created",
                    "session_id": session.id,
                    "title": session.title
                })

            title = f"Analysis: {date_preset} ({timezone.now().strftime('%b %d, %H:%M')})"
            session = MarketingAIChatSession.objects.create(
                shop=org,
                user=request.user,
                title=title,
                date_preset=date_preset,
                model_name=model_name
            )
            
            if skip_initial:
                return Response({
                    "message": "Empty session created",
                    "session_id": session.id,
                    "title": session.title
                })

            # 2. Run analysis
            from core.services.ai_marketing_agent import run_marketing_analysis
            result = run_marketing_analysis(org, sd, ed, model_name=model_name)
            
            # 3. Save resulting insight as first AI message
            if result and "error" not in result:
                msg = MarketingAIChatMessage.objects.create(
                    session=session,
                    role='ai',
                    content="Strategic Intelligence Report Generated:",
                    structured_data=result
                )
                
                return Response({
                    "session_id": session.id,
                    "title": session.title,
                    "first_message": {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "structured_data": msg.structured_data,
                        "created_at": msg.created_at
                    }
                })
            else:
                session.delete() # Revert since analysis failed
                return Response(result, status=400)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def marketing_ai_session_detail(request, session_id):
    """
    GET: Fetch history of messages inside a session.
    DELETE: Remove the session.
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    from core.models import MarketingAIChatSession
    try:
        session = MarketingAIChatSession.objects.get(id=session_id, shop=org, user=request.user)
    except MarketingAIChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
        
    if request.method == 'DELETE':
        session.delete()
        return Response({"detail": "Session deleted"})

    messages = session.messages.all()
    data = [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "structured_data": m.structured_data,
        "created_at": m.created_at
    } for m in messages]
    
    return Response({
        "session": {
            "id": session.id, "title": session.title, 
            "date_preset": session.date_preset, "model_name": session.model_name
        },
        "messages": data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def marketing_ai_chat(request):
    """
    POST a new question to an existing session and get an AI response.
    Accepts both application/json AND multipart/form-data (for file attachments).
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    session_id = request.data.get('session_id')
    question = request.data.get('question')
    uploaded_file = request.FILES.get('file')  # Optional file attachment
    
    if not session_id or not question:
        return Response({"error": "session_id and question are required"}, status=400)

    from core.models import MarketingAIChatSession, MarketingAIChatMessage
    try:
        session = MarketingAIChatSession.objects.get(id=session_id, shop=org, user=request.user)
        
        # Convert preset back to dates to recreate payload context
        # ADVANCED: Dynamic Date Detection with smart fallback
        from datetime import date as _date
        sd2, ed2 = None, None
        sd, ed = None, None
        
        range1, range2 = _detect_date_ranges_in_question(question)
        if range1 and range2:
            # Comparison requested — clamp future end dates to today
            today = timezone.now().date()
            sd, ed = range1[0], min(range1[1], today)
            sd2, ed2 = range2[0], min(range2[1], today)
        elif range1:
            # Single override detected — clamp future end date to today
            today = timezone.now().date()
            sd, ed = range1[0], min(range1[1], today)
        else:
            # Default session dates
            if session.date_preset:
                request.data._mutable = True
                request.data['date_preset'] = session.date_preset
                sd, ed = _get_date_params(request)
            else:
                # GENERAL CHAT: Do not load any data payload by default so that the AI responds in GENERAL CHAT mode (strategist/greetings)
                sd, ed = None, None
            
        model_name = request.data.get('model', session.model_name)

        # 1. Save user question (with optional attachment)
        user_msg = MarketingAIChatMessage.objects.create(
            session=session, role='user', content=question,
            attachment=uploaded_file if uploaded_file else None,
            attachment_name=uploaded_file.name if uploaded_file else None,
        )

        # Auto-rename session title from first question (like Gemini/ChatGPT)
        msg_count = session.messages.filter(role='user').count()
        if msg_count <= 1:
            session.title = question[:50] + ('...' if len(question) > 50 else '')
            session.save(update_fields=['title'])

        def stream_generator():
            try:
                # Yield immediate keep-alive to flush headers
                yield ": keep-alive\n\n"
                
                from core.services.ai_marketing_agent import run_marketing_chat
                
                # Load history — 12 messages for richer context
                history_msgs = list(session.messages.all().order_by('-created_at')[:12])
                history_msgs.reverse()
                history_context = []
                for m in history_msgs:
                    if m.structured_data:
                        # Preserve richer context from structured reports
                        sd_data = m.structured_data
                        parts = [f"Report summary: {sd_data.get('summary', '')}"]
                        if sd_data.get('key_metrics'):
                            parts.append(f"Key metrics: {json.dumps(sd_data['key_metrics'])}")
                        if sd_data.get('budget_recommendations'):
                            parts.append(f"Budget recs: {json.dumps(sd_data['budget_recommendations'][:3])}")
                        history_context.append({"role": m.role, "content": " | ".join(parts)})
                    else:
                        history_context.append({"role": m.role, "content": m.content})
                
                result = run_marketing_chat(
                    org, question, sd, ed, 
                    start_date2=sd2, end_date2=ed2,
                    model_name=model_name, conversation_context=history_context,
                    attachment=uploaded_file,
                )
                
                if result and "stream" in result:
                    full_text = []
                    prompt_snapshot = result.get("system_prompt_snapshot", "")
                    for chunk_text in result["stream"]:
                        if chunk_text:
                            full_text.append(chunk_text)
                            # Yield SSE format
                            payload = json.dumps({"chunk": chunk_text})
                            yield f"data: {payload}\n\n"
                    
                    final_text = "".join(full_text)
                    if final_text:
                        msg = MarketingAIChatMessage.objects.create(session=session, role='ai', content=final_text)
                        done_payload = json.dumps({"done": True, "message_id": msg.id})
                        yield f"data: {done_payload}\n\n"

                        # ── AGENT MANAGER: Log this conversation for audit trail ──
                        try:
                            from core.models import MarketingConversationLog
                            MarketingConversationLog.objects.create(
                                session_id=str(session.id),
                                user_identifier=request.user.username if request.user.is_authenticated else 'anon',
                                shop_name=getattr(org, 'name', str(org)),
                                system_prompt_snapshot=prompt_snapshot,
                                user_message=question,
                                ai_response=final_text,
                                model_used=model_name,
                            )
                        except Exception as log_err:
                            logger.warning(f"Agent Manager: Failed to write conversation log: {log_err}")
                elif result and "error" in result:
                    payload = json.dumps({"error": result["error"]})
                    yield f"data: {payload}\n\n"
                else:
                    payload = json.dumps({"error": "Unknown AI response"})
                    yield f"data: {payload}\n\n"

            except Exception as e:
                logger.error(f"Streaming AI Thread failed: {e}", exc_info=True)
                payload = json.dumps({"error": str(e)})
                yield f"data: {payload}\n\n"

        from django.http import StreamingHttpResponse
        response = StreamingHttpResponse(stream_generator(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        return response

    except MarketingAIChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


# =============================================================================
# 8. Profitability & Income Analysis
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_income_analysis(request):
    """Returns income analysis: spend, revenue, ROAS, true net profit."""
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    sd, ed = _get_date_params(request)
    from core.services.profitability_service import get_income_analysis
    data = get_income_analysis(org, sd, ed)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_best_ads(request):
    """Returns best performing Meta ads sorted by ROAS."""
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    sd, ed = _get_date_params(request)
    sort_by = request.GET.get('sort_by', 'roas')
    from core.services.profitability_service import get_best_performing_ads
    data = get_best_performing_ads(org, sd, ed, sort_by=sort_by)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_retention(request):
    """Returns New vs Returning customer revenue breakdown."""
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    sd, ed = _get_date_params(request)
    from core.services.profitability_service import get_retention_breakdown
    data = get_retention_breakdown(org.organization_id, sd, ed)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_goal_tracker(request):
    """Returns CPA/ROAS actual vs target progress."""
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    sd, ed = _get_date_params(request)
    from core.services.profitability_service import get_goal_tracker
    data = get_goal_tracker(org, sd, ed)
    return Response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_alerts(request):
    """
    GET: List recent marketing alerts.
    POST: Mark an alert as read (pass alert_id in body).
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    if request.method == 'GET':
        alerts = MarketingAlert.objects.filter(shop=org)[:20]
        data = [{
            'id': a.id,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'title': a.title,
            'message': a.message,
            'metric_data': a.metric_data,
            'is_read': a.is_read,
            'created_at': a.created_at,
        } for a in alerts]
        return Response(data)

    elif request.method == 'POST':
        alert_id = request.data.get('alert_id')
        if alert_id:
            MarketingAlert.objects.filter(id=alert_id, shop=org).update(is_read=True)
        return Response({"detail": "Alert marked as read"})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def profitability_financials(request):
    """
    GET/PUT for StoreFinancials (COGS%, shipping cost, targets).
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization"}, status=400)

    financials, created = StoreFinancials.objects.get_or_create(shop=org)

    if request.method == 'GET':
        return Response({
            'average_cogs_percentage': financials.average_cogs_percentage,
            'shipping_cost_per_order': financials.shipping_cost_per_order,
            'target_roas': financials.target_roas,
            'target_cpa': financials.target_cpa,
        })

    elif request.method == 'PUT':
        for field in ['average_cogs_percentage', 'shipping_cost_per_order', 'target_roas', 'target_cpa']:
            val = request.data.get(field)
            if val is not None:
                setattr(financials, field, Decimal(str(val)))
        financials.save()
        return Response({
            'average_cogs_percentage': financials.average_cogs_percentage,
            'shipping_cost_per_order': financials.shipping_cost_per_order,
            'target_roas': financials.target_roas,
            'target_cpa': financials.target_cpa,
        })


# =============================================================================
# AGENT MANAGER API VIEWS
# Global Rules CRUD | Response Audit | Flag + Correct
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def agent_global_rules(request):
    """
    GET: List all global override rules (active + inactive).
    POST: Create a new global rule.
    Body: { rule_text, priority, expires_at (optional ISO string) }
    """
    from core.models import MarketingAgentGlobalRule

    if request.method == 'GET':
        rules = MarketingAgentGlobalRule.objects.all().order_by('-priority', '-created_at')
        data = [{
            'id': r.id, 'rule_text': r.rule_text, 'is_active': r.is_active,
            'priority': r.priority, 'expires_at': r.expires_at,
            'created_by': r.created_by, 'created_at': r.created_at,
            'is_expired': r.is_expired,
        } for r in rules]
        return Response(data)

    # POST
    rule_text = request.data.get('rule_text', '').strip()
    if not rule_text:
        return Response({'error': 'rule_text is required'}, status=400)

    expires_at = None
    if request.data.get('expires_at'):
        try:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(request.data['expires_at'])
        except Exception:
            pass

    rule = MarketingAgentGlobalRule.objects.create(
        rule_text=rule_text,
        priority=int(request.data.get('priority', 0)),
        expires_at=expires_at,
        created_by=request.user.username,
        is_active=True,
    )
    return Response({
        'id': rule.id, 'rule_text': rule.rule_text, 'is_active': rule.is_active,
        'priority': rule.priority, 'expires_at': rule.expires_at,
        'created_at': rule.created_at,
    }, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def agent_global_rule_detail(request, rule_id):
    """
    PATCH: Toggle is_active or update rule text.
    DELETE: Remove the rule permanently.
    """
    from core.models import MarketingAgentGlobalRule
    try:
        rule = MarketingAgentGlobalRule.objects.get(id=rule_id)
    except MarketingAgentGlobalRule.DoesNotExist:
        return Response({'error': 'Rule not found'}, status=404)

    if request.method == 'DELETE':
        rule.delete()
        return Response({'detail': 'Rule deleted'})

    # PATCH
    if 'is_active' in request.data:
        rule.is_active = request.data['is_active']
    if 'rule_text' in request.data:
        rule.rule_text = request.data['rule_text']
    if 'priority' in request.data:
        rule.priority = int(request.data['priority'])
    rule.save()
    return Response({'id': rule.id, 'is_active': rule.is_active, 'rule_text': rule.rule_text})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def agent_conversation_logs(request):
    """
    GET: List conversation logs for audit.
    ?flagged=true  → only flagged entries
    ?session_id=X  → filter by session
    """
    from core.models import MarketingConversationLog
    qs = MarketingConversationLog.objects.all()

    if request.query_params.get('flagged') == 'true':
        qs = qs.filter(flagged_for_review=True)
    if request.query_params.get('session_id'):
        qs = qs.filter(session_id=request.query_params['session_id'])

    qs = qs[:50]  # Cap at 50 for performance
    data = [{
        'id': log.id,
        'session_id': log.session_id,
        'user_identifier': log.user_identifier,
        'user_message': log.user_message,
        'ai_response': log.ai_response[:500],  # truncate for listing
        'model_used': log.model_used,
        'flagged_for_review': log.flagged_for_review,
        'admin_note': log.admin_note,
        'created_at': log.created_at,
    } for log in qs]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def agent_audit_response(request):
    """
    POST { log_id }: Explain why AURA gave that specific response.
    Makes a second Gemini call using the stored system_prompt_snapshot.
    """
    from core.models import MarketingConversationLog

    log_id = request.data.get('log_id')
    if not log_id:
        return Response({'error': 'log_id is required'}, status=400)

    try:
        log = MarketingConversationLog.objects.get(id=log_id)
    except MarketingConversationLog.DoesNotExist:
        return Response({'error': 'Log entry not found'}, status=404)

    try:
        from core.services.ai_marketing_agent import genai_client
        from google.genai import types
        from django.conf import settings

        question = request.data.get('question')
        if question:
            audit_prompt = f"""
You are an AI response auditor. The user has a specific question about why the Marketing AURA agent produced a specific response.

--- SYSTEM PROMPT THAT WAS ACTIVE ---
{log.system_prompt_snapshot[:3000]}

--- USER ASKED ---
{log.user_message}

--- AI RESPONDED ---
{log.ai_response[:2000]}

--- USER'S QUESTION ABOUT THIS RESPONSE ---
{question}

--- YOUR INSTRUCTIONS ---
Answer the user's question directly and concisely. Explain exactly what caused the AI to say that, citing the system prompt or data above if necessary.
"""
        else:
            audit_prompt = f"""
You are an AI response auditor. Explain exactly why the Marketing AURA agent produced the response below.

--- SYSTEM PROMPT THAT WAS ACTIVE ---
{log.system_prompt_snapshot[:3000]}

--- USER ASKED ---
{log.user_message}

--- AI RESPONDED ---
{log.ai_response[:2000]}

--- YOUR AUDIT ---
Explain:
1. Which part of the system prompt triggered this response?
2. Was this response aligned with the active override rules (if any)?
3. What correction could be added to the system prompt to improve this?
Be specific. Cite exact sections of the system prompt.
"""
        from core.utils.gemini_fallback import generate_content_with_fallback
        response = generate_content_with_fallback(
            client=genai_client,
            model='gemini-2.5-flash-lite',
            contents=audit_prompt,
        )
        return Response({'explanation': response.text, 'log_id': log_id})

    except Exception as e:
        logger.error(f"Agent audit failed: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def agent_flag_and_correct(request):
    """
    POST { log_id, instruction }: Flag a log entry and save a correction rule.
    This is the "don't repeat that" feature.
    """
    from core.models import MarketingConversationLog, MarketingCorrectionRule

    log_id = request.data.get('log_id')
    instruction = request.data.get('instruction', '').strip()

    if not log_id or not instruction:
        return Response({'error': 'log_id and instruction are required'}, status=400)

    try:
        log = MarketingConversationLog.objects.get(id=log_id)
    except MarketingConversationLog.DoesNotExist:
        return Response({'error': 'Log not found'}, status=404)

    # 1. Save the correction rule
    correction = MarketingCorrectionRule.objects.create(
        bad_behavior_description=f"Response to: '{log.user_message[:200]}'" ,
        corrected_instruction=instruction,
        example_bad_response=log.ai_response[:500],
        source_log_id=log.id,
        created_by=request.user.username,
        is_active=True,
    )

    # 2. Flag the original log
    log.flagged_for_review = True
    log.admin_note = instruction
    log.save(update_fields=['flagged_for_review', 'admin_note'])

    return Response({
        'detail': 'Correction rule saved. AURA will not repeat this mistake.',
        'correction_id': correction.id,
    }, status=201)
