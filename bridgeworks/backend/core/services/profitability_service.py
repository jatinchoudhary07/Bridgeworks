"""
Profitability Service — Core Business Logic
=============================================
Pure calculation functions for:
  - Income Analysis (Spend, Revenue, ROAS, Net Profit)
  - Retention Breakdown (New vs Returning)
  - Best Performing Ads
  - Goal Tracking (actual vs target CPA/ROAS)
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_income_analysis(shop, start_date, end_date):
    """
    Calculate the Income Analysis dashboard metrics.
    Returns: total_spend, total_revenue, blended_roas, true_net_profit, net_profit_margin
    """
    from core.models import (
        CampaignDailyMetric, GoogleCampaignDailyMetric,
        Order, StoreFinancials
    )

    # --- Financials Config ---
    try:
        financials = StoreFinancials.objects.get(shop=shop)
    except StoreFinancials.DoesNotExist:
        financials = None

    cogs_pct = Decimal(str(financials.average_cogs_percentage)) / 100 if financials else Decimal('0.30')
    shipping_cost = financials.shipping_cost_per_order if financials else Decimal('50.00')

    # --- Meta Ad Spend ---
    meta_qs = CampaignDailyMetric.objects.filter(
        credential__shop=shop, credential__platform='Meta'
    )
    if start_date and end_date:
        meta_qs = meta_qs.filter(date__range=[start_date, end_date])

    meta_stats = meta_qs.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_purchases=Sum('purchases'),
    )

    # --- Google Ad Spend ---
    google_qs = GoogleCampaignDailyMetric.objects.filter(credential__shop=shop)
    if start_date and end_date:
        google_qs = google_qs.filter(date__range=[start_date, end_date])

    google_stats = google_qs.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_conversions=Sum('conversions'),
    )

    # --- Store Revenue (from orders) ---
    from django.db.models.functions import TruncDate
    orders_qs = Order.objects.filter(org_id=shop.organization_id)
    if start_date and end_date:
        orders_qs = orders_qs.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

    order_stats = orders_qs.aggregate(
        total_revenue=Sum('total_price'),
        total_orders=Count('id'),
    )

    total_ad_spend = (meta_stats['total_spend'] or Decimal('0.00')) + (google_stats['total_spend'] or Decimal('0.00'))
    total_store_revenue = order_stats['total_revenue'] or Decimal('0.00')
    total_orders = order_stats['total_orders'] or 0

    # --- Calculations ---
    blended_roas = round(total_store_revenue / total_ad_spend, 2) if total_ad_spend > 0 else Decimal('0.00')

    # True Net Profit = Revenue - Ad Spend - COGS - Shipping
    cogs_amount = total_store_revenue * cogs_pct
    shipping_amount = shipping_cost * total_orders
    true_net_profit = total_store_revenue - total_ad_spend - cogs_amount - shipping_amount
    net_profit_margin = round((true_net_profit / total_store_revenue) * 100, 2) if total_store_revenue > 0 else Decimal('0.00')

    # Meta-specific ROAS
    meta_spend = meta_stats['total_spend'] or Decimal('0.00')
    meta_revenue = meta_stats['total_revenue'] or Decimal('0.00')
    meta_roas = round(meta_revenue / meta_spend, 2) if meta_spend > 0 else Decimal('0.00')

    # CPA
    meta_purchases = meta_stats['total_purchases'] or 0
    meta_cpa = round(meta_spend / meta_purchases, 2) if meta_purchases > 0 else Decimal('0.00')

    return {
        'total_spend': total_ad_spend,
        'total_revenue': total_store_revenue,
        'total_orders': total_orders,
        'blended_roas': blended_roas,
        'true_net_profit': true_net_profit,
        'net_profit_margin': net_profit_margin,
        'cogs_amount': round(cogs_amount, 2),
        'shipping_amount': round(shipping_amount, 2),
        'meta_spend': meta_spend,
        'meta_revenue': meta_revenue,
        'meta_roas': meta_roas,
        'meta_cpa': meta_cpa,
        'meta_purchases': meta_purchases,
        'google_spend': google_stats['total_spend'] or Decimal('0.00'),
        'google_revenue': google_stats['total_revenue'] or Decimal('0.00'),
        'google_conversions': google_stats['total_conversions'] or Decimal('0.00'),
        'cogs_percentage': (financials.average_cogs_percentage if financials else Decimal('30.00')),
        'shipping_cost_per_order': shipping_cost,
    }


def get_retention_breakdown(org_id, start_date, end_date):
    """
    Calculate New vs Returning customer breakdown.
    Uses `previous_order_count` field:
      - New customer: previous_order_count == 0
      - Returning customer: previous_order_count > 0
    """
    from core.models import Order

    orders_qs = Order.objects.filter(org_id=org_id)
    if start_date and end_date:
        orders_qs = orders_qs.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

    total_stats = orders_qs.aggregate(
        total_revenue=Sum('total_price'),
        total_orders=Count('id'),
    )

    new_stats = orders_qs.filter(previous_order_count=0).aggregate(
        revenue=Sum('total_price'),
        orders=Count('id'),
    )

    returning_stats = orders_qs.filter(previous_order_count__gt=0).aggregate(
        revenue=Sum('total_price'),
        orders=Count('id'),
    )

    total_revenue = total_stats['total_revenue'] or Decimal('0.00')
    new_revenue = new_stats['revenue'] or Decimal('0.00')
    returning_revenue = returning_stats['revenue'] or Decimal('0.00')
    returning_pct = round((returning_revenue / total_revenue) * 100, 2) if total_revenue > 0 else Decimal('0.00')

    return {
        'total_orders': total_stats['total_orders'] or 0,
        'total_revenue': total_revenue,
        'new_customers': {
            'orders': new_stats['orders'] or 0,
            'revenue': new_revenue,
            'percentage': round((new_revenue / total_revenue) * 100, 2) if total_revenue > 0 else Decimal('0.00'),
        },
        'returning_customers': {
            'orders': returning_stats['orders'] or 0,
            'revenue': returning_revenue,
            'percentage': returning_pct,
        },
    }


def get_best_performing_ads(shop, start_date, end_date, sort_by='roas', limit=50):
    """
    Aggregate AdDailyMetric by ad_id to show best performing individual ads.
    Returns a list sorted by the specified metric (default: highest ROAS).
    """
    from core.models import AdDailyMetric

    qs = AdDailyMetric.objects.filter(
        credential__shop=shop, credential__platform='Meta'
    )
    if start_date and end_date:
        qs = qs.filter(date__range=[start_date, end_date])

    ads = qs.values('ad_id', 'ad_name').annotate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_purchases=Sum('purchases'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
    )

    results = []
    for ad in ads:
        spend = ad['total_spend'] or Decimal('0.00')
        revenue = ad['total_revenue'] or Decimal('0.00')
        purchases = ad['total_purchases'] or 0
        clicks = ad['total_clicks'] or 0

        roas = round(revenue / spend, 2) if spend > 0 else Decimal('0.00')
        cpa = round(spend / purchases, 2) if purchases > 0 else Decimal('0.00')
        ctr = round((clicks / (ad['total_impressions'] or 1)) * 100, 2)

        results.append({
            'ad_id': ad['ad_id'],
            'ad_name': ad['ad_name'],
            'spend': spend,
            'revenue': revenue,
            'purchases': purchases,
            'roas': roas,
            'cpa': cpa,
            'ctr': ctr,
        })

    # Sort
    reverse = True
    if sort_by == 'cpa':
        # For CPA, lower is better — but still show highest first for "worst" or lowest first for "best"
        reverse = False
    results.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

    return results[:limit]


def get_goal_tracker(shop, start_date, end_date):
    """
    Compare actual CPA/ROAS against targets defined in StoreFinancials.
    Returns actual values, targets, and progress percentages.
    """
    from core.models import CampaignDailyMetric, StoreFinancials

    # Get targets
    try:
        financials = StoreFinancials.objects.get(shop=shop)
    except StoreFinancials.DoesNotExist:
        financials = None

    target_roas = financials.target_roas if financials else Decimal('3.00')
    target_cpa = financials.target_cpa if financials else Decimal('500.00')

    # Get actual metrics
    qs = CampaignDailyMetric.objects.filter(
        credential__shop=shop, credential__platform='Meta'
    )
    if start_date and end_date:
        qs = qs.filter(date__range=[start_date, end_date])

    stats = qs.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_purchases=Sum('purchases'),
    )

    spend = stats['total_spend'] or Decimal('0.00')
    revenue = stats['total_revenue'] or Decimal('0.00')
    purchases = stats['total_purchases'] or 0

    actual_roas = round(revenue / spend, 2) if spend > 0 else Decimal('0.00')
    actual_cpa = round(spend / purchases, 2) if purchases > 0 else Decimal('0.00')

    # Progress calculations
    # ROAS: actual/target * 100 (higher is better)
    roas_progress = round((actual_roas / target_roas) * 100, 1) if target_roas > 0 else 0
    # CPA: target/actual * 100 (lower CPA is better, so invert)
    cpa_progress = round((target_cpa / actual_cpa) * 100, 1) if actual_cpa > 0 else 100

    return {
        'roas': {
            'actual': actual_roas,
            'target': target_roas,
            'progress': min(float(roas_progress), 150),  # Cap at 150%
            'on_track': actual_roas >= target_roas,
        },
        'cpa': {
            'actual': actual_cpa,
            'target': target_cpa,
            'progress': min(float(cpa_progress), 150),
            'on_track': actual_cpa <= target_cpa,
        },
    }
