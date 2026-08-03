"""
Attribution Backfill API Views
==============================
DRF endpoints for triggering the Historical Attribution Backfill and
viewing attribution summary/analytics.

All views are protected by IsAuthenticated + IsMarketingAnalyst.
"""
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Sum
from core.permissions import IsMarketingAnalyst
from core.views_marketing import _get_org

logger = logging.getLogger(__name__)


class TriggerAttributionBackfillView(APIView):
    """
    POST /api/marketing/attribution/backfill/

    Kicks off the historical attribution backfill as a background task.
    Accepts optional start_date, end_date, and force flag.

    Request Body (all optional):
        {
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "force": false
        }

    Returns:
        {"detail": "Backfill task queued.", "task_id": "..."}
    """
    permission_classes = [IsAuthenticated, IsMarketingAnalyst]

    def post(self, request):
        shop = _get_org(request)
        if not shop:
            return Response(
                {'error': 'No organization found for this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = request.data.get('start_date')  # Optional ISO string
        end_date = request.data.get('end_date')  # Optional ISO string
        force = request.data.get('force', False)  # Overwrite existing?

        # Kick off async task via django-q2
        from django_q.tasks import async_task
        from core.tasks.attribution_backfill import run_historical_attribution_backfill

        task_id = async_task(
            run_historical_attribution_backfill,
            shop.id,
            start_date,
            end_date,
            force,
            task_name=f"Attribution Backfill — {shop.organization_id}",
            timeout=7200  # 2 hours to avoid 300s timeout on large stores
        )

        logger.info(
            f"Attribution backfill queued for org={shop.organization_id}, "
            f"task_id={task_id}, range={start_date}→{end_date}, force={force}"
        )

        return Response({
            'detail': 'Attribution backfill task has been queued. '
                      'It will process orders in the background.',
            'task_id': str(task_id),
            'shop_id': shop.id,
            'organization_id': shop.organization_id,
        }, status=status.HTTP_202_ACCEPTED)


class AttributionSummaryView(APIView):
    """
    GET /api/marketing/attribution/summary/

    Returns aggregated attribution statistics for the organization:
    - Total orders with/without attribution
    - Channel breakdown (count + percentage)
    - Top matched campaigns
    - Backfill coverage percentage
    """
    permission_classes = [IsAuthenticated, IsMarketingAnalyst]

    def get(self, request):
        shop = _get_org(request)
        if not shop:
            return Response(
                {'error': 'No organization found for this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.models import Order, OrderAttribution
        from django.utils.dateparse import parse_date
        from django.utils import timezone
        from datetime import timedelta

        org_id = shop.organization_id
        
        # ── Date Handling ─────────────────────────────────────────────
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')
        
        sd = parse_date(start_str) if start_str else None
        ed = parse_date(end_str) if end_str else None
        
        # If no dates, default to last 7 days for current stats
        if not sd or not ed:
            ed = timezone.now().date()
            sd = ed - timedelta(days=7)

        # Calculate previous period for comparison
        days_diff = (ed - sd).days + 1
        prev_ed = sd - timedelta(days=1)
        prev_sd = prev_ed - timedelta(days=days_diff - 1)

        def get_stats(start, end):
            # Total orders
            q_orders = Order.objects.filter(org_id=org_id, created_at__date__range=[start, end])
            total = q_orders.count()
            
            # Attributed
            q_attr = OrderAttribution.objects.filter(
                order__org_id=org_id, 
                order__created_at__date__range=[start, end]
            )
            attr_count = q_attr.count()
            
            # Matched
            matched_count = q_attr.exclude(matched_campaign_id='').count()
            
            return {
                'total': total,
                'attributed': attr_count,
                'matched': matched_count,
                'coverage': round((attr_count / total * 100) if total > 0 else 0, 1),
                'match_rate': round((matched_count / attr_count * 100) if attr_count > 0 else 0, 1)
            }

        curr = get_stats(sd, ed)
        prev = get_stats(prev_sd, prev_ed)

        def calc_delta(c, p):
            if p == 0: return 0 if c == 0 else 100
            return round(((c - p) / p) * 100, 1)

        # ── Breakdown Data (Current Period Only) ──────────────────────
        q_attr_curr = OrderAttribution.objects.filter(
            order__org_id=org_id, 
            order__created_at__date__range=[sd, ed]
        )
        
        channel_breakdown = list(
            q_attr_curr.values('channel')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        for item in channel_breakdown:
            item['percentage'] = round((item['count'] / curr['attributed'] * 100) if curr['attributed'] > 0 else 0, 1)

        top_campaigns = list(
            q_attr_curr.filter(matched_platform='meta').exclude(matched_campaign_id='')
            .values('matched_campaign_id', 'utm_campaign')
            .annotate(order_count=Count('id'))
            .order_by('-order_count')[:10]
        )

        top_sources = list(
            q_attr_curr.exclude(utm_source='')
            .values('utm_source')
            .annotate(order_count=Count('id'))
            .order_by('-order_count')[:10]
        )

        # ── First-Visit vs Multi-Visit Calculations ─────────────────────
        from decimal import Decimal
        first_visit_count = 0
        first_visit_revenue = Decimal('0.00')
        multi_visit_count = 0
        multi_visit_revenue = Decimal('0.00')

        # We also want to map channel slugs to pretty labels
        def get_channel_label(channel_slug):
            mapping = {
                'meta_paid': 'Meta Paid',
                'google_paid': 'Google Paid',
                'tiktok_paid': 'TikTok Paid',
                'pinterest_paid': 'Pinterest Paid',
                'snapchat_paid': 'Snapchat Paid',
                'organic_social': 'Organic Social',
                'organic_search': 'Organic Search',
                'email': 'Email',
                'whatsapp': 'WhatsApp',
                'referral': 'Referral',
                'direct': 'Direct',
                'unknown': 'Direct/Unknown'
            }
            if not channel_slug:
                return 'Direct'
            return mapping.get(channel_slug.lower(), channel_slug.replace('_', ' ').title())

        # Path combination tracking
        path_counts = {}

        # Select related order to prevent N+1 queries when fetching total_price
        for attr in q_attr_curr.select_related('order'):
            journey = attr.touch_journey or []
            price = Decimal(str(attr.order.total_price or 0))
            
            # If journey has <= 1 touchpoint, it's a first-visit purchase
            # (or if journey is empty, since no other touchpoints were recorded)
            if len(journey) <= 1:
                first_visit_count += 1
                first_visit_revenue += price
            else:
                multi_visit_count += 1
                multi_visit_revenue += price
            
            # Map path combinations
            if journey:
                path = " → ".join(get_channel_label(step.get('source')) for step in journey)
            else:
                path = get_channel_label(attr.channel)
            
            if path:
                if path not in path_counts:
                    path_counts[path] = {'count': 0, 'revenue': Decimal('0.00')}
                path_counts[path]['count'] += 1
                path_counts[path]['revenue'] += price

        # Sort path combinations by conversion count
        top_combinations = []
        for path, stats in sorted(path_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:5]:
            top_combinations.append({
                'path': path,
                'count': stats['count'],
                'revenue': float(stats['revenue'])
            })

        # Calculate percentages
        total_attributed_orders = curr['attributed']
        first_visit_percentage = round((first_visit_count / total_attributed_orders * 100) if total_attributed_orders > 0 else 0, 1)
        multi_visit_percentage = round((multi_visit_count / total_attributed_orders * 100) if total_attributed_orders > 0 else 0, 1)

        # ── Ad-Level Performance Analytics ─────────────────────────────
        from core.models import AdDailyMetric

        ad_metrics = AdDailyMetric.objects.filter(
            credential__shop=shop,
            date__range=[sd, ed]
        ).values('ad_id', 'ad_name').annotate(
            total_spend=Sum('spend'),
            total_clicks=Sum('clicks'),
            total_purchases=Sum('purchases'),
            total_impressions=Sum('impressions'),
            total_revenue=Sum('revenue')
        )

        best_converting_ads = []
        high_traffic_low_perf_ads = []

        for ad in ad_metrics:
            clicks = ad['total_clicks'] or 0
            purchases = ad['total_purchases'] or 0
            spend = float(ad['total_spend'] or 0)
            revenue = float(ad['total_revenue'] or 0)
            
            conv_rate = round((purchases / clicks * 100) if clicks > 0 else 0, 2)
            roas = round(revenue / spend, 2) if spend > 0 else 0.0
            
            ad_info = {
                'ad_id': ad['ad_id'],
                'ad_name': ad['ad_name'],
                'clicks': clicks,
                'purchases': purchases,
                'spend': spend,
                'revenue': revenue,
                'conversion_rate': conv_rate,
                'roas': roas
            }
            
            best_converting_ads.append(ad_info)
            high_traffic_low_perf_ads.append(ad_info)

        # 1. Best converting Meta ads (at least 1 purchase, sorted by conversion rate descending)
        best_converting_ads = sorted(
            [ad for ad in best_converting_ads if ad['purchases'] > 0],
            key=lambda x: x['conversion_rate'],
            reverse=True
        )[:5]

        # 2. High-traffic, low-performing Meta ads (sorted by clicks descending, with 0 or low conversion rate)
        # We sort by: conversion rate ASC, then clicks DESC
        high_traffic_low_perf_ads = sorted(
            [ad for ad in high_traffic_low_perf_ads if ad['clicks'] > 5],
            key=lambda x: (x['conversion_rate'], -x['clicks'])
        )[:5]

        return Response({
            'total_orders': curr['total'],
            'total_orders_delta': calc_delta(curr['total'], prev['total']),
            
            'attributed_orders': curr['attributed'],
            'attributed_orders_delta': calc_delta(curr['attributed'], prev['attributed']),
            
            'coverage_percentage': curr['coverage'],
            'coverage_delta': round(curr['coverage'] - prev['coverage'], 1), # percentage point diff
            
            'campaign_match_rate': curr['match_rate'],
            'campaign_match_rate_delta': round(curr['match_rate'] - prev['match_rate'], 1),
            
            'channel_breakdown': channel_breakdown,
            'top_matched_campaigns': top_campaigns,
            'top_utm_sources': top_sources,
            'start_date': sd,
            'end_date': ed,
            'prev_start_date': prev_sd,
            'prev_end_date': prev_ed,

            # Advanced Multi-Touch Insights
            'first_visit_purchases': {
                'count': first_visit_count,
                'revenue': float(first_visit_revenue),
                'percentage': first_visit_percentage,
            },
            'multi_visit_purchases': {
                'count': multi_visit_count,
                'revenue': float(multi_visit_revenue),
                'percentage': multi_visit_percentage,
            },
            'top_combinations': top_combinations,
            'best_converting_ads': best_converting_ads,
            'high_traffic_low_perf_ads': high_traffic_low_perf_ads,
        })


from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_date

class AttributionOrderPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


class AttributionOrderSheetView(APIView):
    """
    GET /api/marketing/attribution/sheet/

    Returns paginated orders combined with their attribution data.
    Supports date filtering via start_date / end_date query params.
    Defaults to showing all attributed orders if no date given.

    Query Params:
        start_date  — ISO date string e.g. "2025-01-01"
        end_date    — ISO date string e.g. "2025-12-31"
        channel     — filter by channel slug e.g. "meta_paid"
        page        — page number (1-indexed)
        page_size   — results per page (default 50, max 500)
    """
    permission_classes = [IsAuthenticated, IsMarketingAnalyst]

    def get(self, request):
        shop = _get_org(request)
        if not shop:
            return Response({'error': 'No organization found'}, status=status.HTTP_400_BAD_REQUEST)

        from core.models import Order, OrderAttribution

        org_id = shop.organization_id

        # ── Build queryset ────────────────────────────────────────────
        # Query all orders for this org, joined with attribution
        queryset = Order.objects.filter(
            org_id=org_id
        ).select_related('attribution').order_by('-created_at')

        # ── Date filtering ────────────────────────────────────────────
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            sd = parse_date(start_date_str)
            if sd:
                queryset = queryset.filter(created_at__date__gte=sd)

        if end_date_str:
            ed = parse_date(end_date_str)
            if ed:
                queryset = queryset.filter(created_at__date__lte=ed)

        # ── Channel filter ────────────────────────────────────────────
        channel = request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(orderattribution__channel=channel)

        # ── Platform filter ───────────────────────────────────────────
        platform = request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(orderattribution__matched_platform=platform)

        # ── Campaign / Order search filter ────────────────────────────
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(orderattribution__utm_campaign__icontains=search) |
                Q(order_number__icontains=search)
            )

        # ── Paginate ──────────────────────────────────────────────────
        paginator = AttributionOrderPagination()
        paginated_orders = paginator.paginate_queryset(queryset, request)

        data = []
        for order in paginated_orders:
            attr = getattr(order, 'attribution', None)

            data.append({
                'id': order.id,
                'order_number': order.order_number,
                'created_at': order.created_at.isoformat() if order.created_at else None,
                'status': order.status,
                'financial_status': order.financial_status,
                'total_price': order.total_price,

                # Attribution Data
                'has_attribution': attr is not None,
                'channel': attr.channel if attr else 'unattributed',
                'source': attr.source if attr else '',
                'utm_source': attr.utm_source if attr else '',
                'utm_medium': attr.utm_medium if attr else '',
                'utm_campaign': attr.utm_campaign if attr else '',
                'utm_term': attr.utm_term if attr else '',
                'utm_content': attr.utm_content if attr else '',
                'fbclid': attr.fbclid if attr else '',
                'gclid': attr.gclid if attr else '',
                'epik': attr.epik if attr else '',
                'sclid': attr.sclid if attr else '',
                'fp_id': attr.fp_id if attr else '',
                'referer': attr.referer if attr else '',
                'matched_platform': attr.matched_platform if attr else '',
                'matched_campaign_id': attr.matched_campaign_id if attr else '',
                'touch_journey': attr.touch_journey if attr else [],
            })

        return paginator.get_paginated_response(data)


class AttributionReconciliationView(APIView):
    """
    GET /api/marketing/attribution/reconciliation/

    Returns platform-reported metrics (Meta, Google) side-by-side with
    Shori-measured conversions, aggregated by campaign and by date.
    """
    permission_classes = [IsAuthenticated, IsMarketingAnalyst]

    def get(self, request):
        shop = _get_org(request)
        if not shop:
            return Response(
                {'error': 'No organization found for this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.models import CampaignDailyMetric, GoogleCampaignDailyMetric, OrderAttribution, MetaCampaign
        from django.utils.dateparse import parse_date
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Count

        org_id = shop.organization_id

        # ── Date Handling ─────────────────────────────────────────────
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        sd = parse_date(start_str) if start_str else None
        ed = parse_date(end_str) if end_str else None

        if not sd or not ed:
            ed = timezone.now().date()
            sd = ed - timedelta(days=7)

        # ── 1. Fetch Platform Campaign Metrics ────────────────────────
        # Meta Campaigns
        meta_qs = CampaignDailyMetric.objects.filter(
            credential__shop=shop,
            date__range=[sd, ed]
        ).values('campaign_id', 'campaign_name').annotate(
            spend=Sum('spend'),
            purchases=Sum('purchases'),
            revenue=Sum('revenue')
        )

        # Google Campaigns
        google_qs = GoogleCampaignDailyMetric.objects.filter(
            credential__shop=shop,
            date__range=[sd, ed]
        ).values('campaign_name').annotate(
            spend=Sum('spend'),
            purchases=Sum('conversions'),
            revenue=Sum('revenue')
        )

        # ── 2. Fetch Shori First-Party Attributed Orders ──────────────
        local_qs = OrderAttribution.objects.filter(
            order__org_id=org_id,
            order__created_at__date__range=[sd, ed]
        ).values('matched_platform', 'matched_campaign_id').annotate(
            purchases=Count('id'),
            revenue=Sum('order__total_price')
        )

        # Build MetaCampaign ID -> Name lookup mapping (fallback)
        meta_names = {
            c.campaign_id: c.name 
            for c in MetaCampaign.objects.filter(credential__shop=shop)
        }

        # ── 3. Combine Data by Campaign ──────────────────────────────
        campaigns = {}

        # Meta platform rows
        for row in meta_qs:
            cid = row['campaign_id']
            campaigns[('meta', cid)] = {
                'campaign_id': cid,
                'campaign_name': row['campaign_name'],
                'platform': 'meta',
                'spend': float(row['spend'] or 0),
                'platform_reported_purchases': float(row['purchases'] or 0),
                'platform_reported_revenue': float(row['revenue'] or 0),
                'measured_purchases': 0,
                'measured_revenue': 0.0,
            }

        # Google platform rows
        for row in google_qs:
            cname = row['campaign_name']
            campaigns[('google', cname)] = {
                'campaign_id': cname,
                'campaign_name': cname,
                'platform': 'google',
                'spend': float(row['spend'] or 0),
                'platform_reported_purchases': float(row['purchases'] or 0),
                'platform_reported_revenue': float(row['revenue'] or 0),
                'measured_purchases': 0,
                'measured_revenue': 0.0,
            }

        # Local attributed orders matching platform rows or standalone UTMs
        for row in local_qs:
            platform = row['matched_platform']
            cid = row['matched_campaign_id']
            if not platform or not cid:
                continue

            key = (platform, cid)
            if key in campaigns:
                campaigns[key]['measured_purchases'] = row['purchases'] or 0
                campaigns[key]['measured_revenue'] = float(row['revenue'] or 0)
            else:
                # Local order attributed to a campaign but platform metrics don't show spend/performance
                name = meta_names.get(cid, cid) if platform == 'meta' else cid
                campaigns[key] = {
                    'campaign_id': cid,
                    'campaign_name': name,
                    'platform': platform,
                    'spend': 0.0,
                    'platform_reported_purchases': 0.0,
                    'platform_reported_revenue': 0.0,
                    'measured_purchases': row['purchases'] or 0,
                    'measured_revenue': float(row['revenue'] or 0),
                }

        # Calculate gaps
        campaign_list = []
        for key, item in campaigns.items():
            plat_pur = item['platform_reported_purchases']
            meas_pur = item['measured_purchases']
            item['gap_purchases'] = float(plat_pur - meas_pur)

            plat_rev = item['platform_reported_revenue']
            meas_rev = item['measured_revenue']
            item['gap_revenue'] = float(plat_rev - meas_rev)

            if plat_pur > 0:
                item['gap_pct'] = round((item['gap_purchases'] / plat_pur) * 100, 1)
            elif meas_pur > 0:
                item['gap_pct'] = -100.0
            else:
                item['gap_pct'] = 0.0

            if item['platform'] == 'meta':
                item['explanation'] = "Meta uses a 7-day click / 1-day view attribution window and models conversions. Shori attributes using exact first-party click tracking."
            elif item['platform'] == 'google':
                item['explanation'] = "Google Ads uses algorithmic data-driven models and cross-device mappings. Shori uses direct first-party visitor session links."
            else:
                item['explanation'] = "Differences are due to platform-specific attribution settings vs Shori direct tracking."

            campaign_list.append(item)

        campaign_list.sort(key=lambda x: x['spend'], reverse=True)

        # ── 4. Daily Aggregation for Charts ───────────────────────────
        meta_daily = CampaignDailyMetric.objects.filter(
            credential__shop=shop,
            date__range=[sd, ed]
        ).values('date').annotate(
            spend=Sum('spend'),
            purchases=Sum('purchases'),
            revenue=Sum('revenue')
        )

        google_daily = GoogleCampaignDailyMetric.objects.filter(
            credential__shop=shop,
            date__range=[sd, ed]
        ).values('date').annotate(
            spend=Sum('spend'),
            purchases=Sum('conversions'),
            revenue=Sum('revenue')
        )

        local_daily = OrderAttribution.objects.filter(
            order__org_id=org_id,
            order__created_at__date__range=[sd, ed]
        ).values('order__created_at__date', 'matched_platform').annotate(
            purchases=Count('id'),
            revenue=Sum('order__total_price')
        )

        # Construct daily dictionary
        daily_records = {}
        curr_d = sd
        while curr_d <= ed:
            daily_records[curr_d] = {
                'date': curr_d.isoformat(),
                'meta_spend': 0.0,
                'meta_platform_purchases': 0.0,
                'meta_platform_revenue': 0.0,
                'meta_measured_purchases': 0.0,
                'meta_measured_revenue': 0.0,
                'google_spend': 0.0,
                'google_platform_purchases': 0.0,
                'google_platform_revenue': 0.0,
                'google_measured_purchases': 0.0,
                'google_measured_revenue': 0.0,
            }
            curr_d += timedelta(days=1)

        for row in meta_daily:
            d = row['date']
            if d in daily_records:
                daily_records[d]['meta_spend'] = float(row['spend'] or 0)
                daily_records[d]['meta_platform_purchases'] = float(row['purchases'] or 0)
                daily_records[d]['meta_platform_revenue'] = float(row['revenue'] or 0)

        for row in google_daily:
            d = row['date']
            if d in daily_records:
                daily_records[d]['google_spend'] = float(row['spend'] or 0)
                daily_records[d]['google_platform_purchases'] = float(row['purchases'] or 0)
                daily_records[d]['google_platform_revenue'] = float(row['revenue'] or 0)

        for row in local_daily:
            d = row['order__created_at__date']
            plat = row['matched_platform']
            if d in daily_records:
                if plat == 'meta':
                    daily_records[d]['meta_measured_purchases'] = float(row['purchases'] or 0)
                    daily_records[d]['meta_measured_revenue'] = float(row['revenue'] or 0)
                elif plat == 'google':
                    daily_records[d]['google_measured_purchases'] = float(row['purchases'] or 0)
                    daily_records[d]['google_measured_revenue'] = float(row['revenue'] or 0)

        daily_list = [daily_records[d] for d in sorted(daily_records.keys())]

        return Response({
            'campaigns': campaign_list,
            'daily': daily_list,
            'start_date': sd.isoformat(),
            'end_date': ed.isoformat()
        })


class AttributionModelView(APIView):
    """
    GET /api/marketing/attribution/model/

    Calculates multi-touch attribution credit weights (Last Touch, First Touch,
    Linear, Time Decay) across all channels for a given date range.
    """
    permission_classes = [IsAuthenticated, IsMarketingAnalyst]

    def get(self, request):
        shop = _get_org(request)
        if not shop:
            return Response(
                {'error': 'No organization found for this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.models import OrderAttribution
        from core.utils.attribution_models import compute_attribution
        from django.utils.dateparse import parse_date
        from django.utils import timezone
        from datetime import timedelta

        org_id = shop.organization_id

        # ── Date Handling ─────────────────────────────────────────────
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        sd = parse_date(start_str) if start_str else None
        ed = parse_date(end_str) if end_str else None

        if not sd or not ed:
            ed = timezone.now().date()
            sd = ed - timedelta(days=7)

        # Query all order attributions inside range
        attributions = OrderAttribution.objects.filter(
            order__org_id=org_id,
            order__created_at__date__range=[sd, ed]
        ).select_related('order')

        # Initialize stats structure
        channel_slugs = [choice[0] for choice in OrderAttribution.CHANNEL_CHOICES]
        stats = {}
        for ch in channel_slugs:
            stats[ch] = {
                'channel': ch,
                'last_touch_orders': 0.0,
                'last_touch_revenue': 0.0,
                'first_touch_orders': 0.0,
                'first_touch_revenue': 0.0,
                'linear_orders': 0.0,
                'linear_revenue': 0.0,
                'time_decay_orders': 0.0,
                'time_decay_revenue': 0.0,
            }

        models = ['last_touch', 'first_touch', 'linear', 'time_decay']

        for attr in attributions:
            price = float(attr.order.total_price or 0)
            fallback = attr.channel or 'unknown'
            journey = attr.touch_journey or []

            for model in models:
                distribution = compute_attribution(journey, fallback, model_name=model)
                for ch, weight in distribution.items():
                    if ch not in stats:
                        stats[ch] = {
                            'channel': ch,
                            'last_touch_orders': 0.0,
                            'last_touch_revenue': 0.0,
                            'first_touch_orders': 0.0,
                            'first_touch_revenue': 0.0,
                            'linear_orders': 0.0,
                            'linear_revenue': 0.0,
                            'time_decay_orders': 0.0,
                            'time_decay_revenue': 0.0,
                        }
                    stats[ch][f'{model}_orders'] += weight
                    stats[ch][f'{model}_revenue'] += weight * price

        # Round results to 2 decimal places
        results = []
        for ch, data in stats.items():
            has_data = any(data[f'{m}_orders'] > 0 for m in models)
            if not has_data:
                continue

            rounded_data = {'channel': ch}
            for m in models:
                rounded_data[f'{m}_orders'] = round(data[f'{m}_orders'], 2)
                rounded_data[f'{m}_revenue'] = round(data[f'{m}_revenue'], 2)
            results.append(rounded_data)

        # Sort results by time decay revenue descending
        results.sort(key=lambda x: x.get('time_decay_revenue', 0.0), reverse=True)

        return Response({
            'start_date': sd.isoformat(),
            'end_date': ed.isoformat(),
            'attribution_data': results
        })

