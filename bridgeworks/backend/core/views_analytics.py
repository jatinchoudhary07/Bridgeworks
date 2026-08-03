import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django.db.utils import OperationalError
from django.core.cache import cache

from .models import Order
from .utils.stage_queries import get_q_filter_for_stage, STAGES_REQUIRING_DISTINCT
from .utils.payment_utils import get_payment_q_objects

logger = logging.getLogger(__name__)

STAGE_LIST = [
    "Order Placed but not confirmed",
    "Confirmed but AWB not generated",
    "Label Generated but not fulfilled",
    "Fulfilled but not packed",
    "Packed but not manifested",
    "Manifested",
    "Dispatched",
    "In Transit",
    "NDR (Failed Delivery)",
    "Delivered Orders",
    "RTO Intransit",
    "RTO Delivered",
    "RTO Dispute/FRAUD",
    "Returns",
    "Exchange",
    "Restocked",
    "Cancelled",
    "New Order Created",
    "Compensation Received",
]

# Cache TTL in seconds (15 minutes – this query is expensive)
STAGE_SUMMARY_CACHE_TTL = 900


def _slug(stage_name):
    """Convert a stage name into a valid Python identifier for dict keys."""
    return stage_name.lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace('-', '_')


def _empty_summary():
    """Return a zeroed-out summary list (used as fallback on timeout)."""
    summary = []
    for stage in STAGE_LIST:
        breakdown = [
            {"order_type": "Prepaid",        "qty": 0, "amount": 0},
            {"order_type": "COD",            "qty": 0, "amount": 0},
            {"order_type": "Partial COD",    "qty": 0, "amount": 0},
            {"order_type": "Exchange/Return","qty": 0, "amount": 0},
        ]
        summary.append({
            "stage_name": stage,
            "total_orders": 0,
            "breakdown": breakdown,
        })
    return summary


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stage_summary(request):
    """
    Returns counts and breakdown for the 19 order stages.

    Optimised: all 19 stages are computed in a SINGLE database aggregate call
    using conditional expressions (Count/Sum with filter=). Response is cached
    per (org_id, startDate, endDate) for 15 minutes.
    """
    # ------------------------------------------------------------------
    # 1. Resolve org and build base queryset
    # ------------------------------------------------------------------
    user = request.user
    org_id = None

    if hasattr(user, 'shop_credentials'):
        org_id = user.shop_credentials.organization_id
    elif hasattr(user, 'team_settings') and user.team_settings.organization:
        org_id = user.team_settings.organization.organization_id
    else:
        try:
            from core.models.users import WorkspaceMembership
            membership = WorkspaceMembership.objects.select_related('workspace').get(user=user)
            org_id = membership.workspace.organization_id
        except Exception:
            pass

    if not org_id:
        from django.conf import settings as _settings
        if _settings.DEBUG and user.is_superuser:
            from core.models import ShopCredentials
            shop = ShopCredentials.objects.first()
            if shop:
                org_id = shop.organization_id
        if not org_id:
            return Response([])

    start_date = request.GET.get('startDate', '')
    end_date = request.GET.get('endDate', '')
    source = request.GET.get('source', '')  # e.g. shopify, marketplace, retail, b2b

    # ------------------------------------------------------------------
    # 2. Cache check
    # ------------------------------------------------------------------
    cache_key = f"stage_summary:{org_id}:{start_date}:{end_date}:{source}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    # ------------------------------------------------------------------
    # 3. Build base queryset (org-scoped + date filters)
    # ------------------------------------------------------------------
    from django.db.models import Exists, OuterRef
    from .models import TrackingInfo, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
    from .utils.payment_utils import derive_payment_type_from_fields
    from django.utils import timezone
    from datetime import timedelta

    # Subquery to check if a tracking number exists for any fulfillment of the order
    has_awb_subquery = TrackingInfo.objects.filter(
        fulfillment__order=OuterRef('pk')
    ).exclude(number='').exclude(number__isnull=True)

    orders_query = Order.objects.filter(org_id=org_id)
    if source:
        orders_query = orders_query.filter(source=source)
    
    from datetime import datetime, time
    if start_date:
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        dt_start = timezone.make_aware(datetime.combine(start_date, time.min))
        orders_query = orders_query.filter(created_at__gte=dt_start)
    if end_date:
        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        dt_end = timezone.make_aware(datetime.combine(end_date, time.max))
        orders_query = orders_query.filter(created_at__lte=dt_end)

    orders_query = orders_query.annotate(has_awb=Exists(has_awb_subquery))

    fields = [
        'id', 'status', 'fulfillment_status', 'internal_fulfillment_status',
        'current_status', 'is_ndr', 'rto_internal_status', 'tags',
        'created_at', 'total_price', 'payment_gateway_names', 'financial_status', 'has_awb'
    ]

    try:
        orders_list = list(orders_query.values(*fields))
    except OperationalError as e:
        logger.warning(f"Stage summary values query timed out for org {org_id}: {e}")
        stale_key = f"stage_summary_stale:{org_id}"
        stale = cache.get(stale_key)
        if stale is not None:
            return Response(stale)
        return Response(_empty_summary())

    # ------------------------------------------------------------------
    # 4. Classify and aggregate stage metrics in Python memory
    # ------------------------------------------------------------------
    yesterday = timezone.now() - timedelta(days=1)

    # Initialize counts dictionary
    stage_data = {}
    for stage in STAGE_LIST:
        stage_data[stage] = {
            'total': 0,
            'amt': 0.0,
            'cod': 0,
            'amt_cod': 0.0,
            'partial': 0,
            'amt_partial': 0.0,
            'exchange': 0,
            'amt_exchange': 0.0,
            'prepaid': 0,
            'amt_prepaid': 0.0
        }

    for order in orders_list:
        has_awb = order['has_awb']
        
        # Derive payment type using backend utility (pass None for raw_data to avoid loading it)
        payment_type = derive_payment_type_from_fields(
            order['payment_gateway_names'],
            order['financial_status'],
            order['tags'],
            None
        )
        
        # Identify exchange status
        gateways_str = str(order['payment_gateway_names'] or []).lower()
        tags_str = str(order['tags'] or '').lower()
        is_exchange = 'exchange' in gateways_str or 'exchange' in tags_str
        
        total_price = float(order['total_price'] or 0.0)
        
        # Map to stages
        for stage in STAGE_LIST:
            stage_lower = stage.lower().strip()
            matched = False
            
            if stage_lower == "order placed but not confirmed":
                matched = (order['status'] == 'Pending')
            elif stage_lower == "confirmed but awb not generated":
                matched = (order['status'] == 'Confirmed' and not has_awb)
            elif stage_lower == "label generated but not fulfilled":
                fs_lower = (order['fulfillment_status'] or '').lower()
                matched = (has_awb and fs_lower not in ('fulfilled', 'tracking_added') and order['status'] not in ('Batched',))
            elif stage_lower == "fulfilled but not packed":
                fs_lower = (order['fulfillment_status'] or '').lower()
                matched = (fs_lower in ('fulfilled', 'tracking_added') and (order['internal_fulfillment_status'] not in ['Packaged', 'On Hold']))
            elif stage_lower == "packed but not manifested":
                matched = (order['internal_fulfillment_status'] == 'Packaged' and 
                           not (order['current_status'] and order['current_status'].lower() == 'manifested'))
            elif stage_lower == "manifested":
                matched = (order['current_status'] and order['current_status'].lower() == 'manifested')
            elif stage_lower == "dispatched":
                cs_lower = (order['current_status'] or '').lower()
                matched = cs_lower in (
                    'awb assigned', 'awb_assigned', 'shipment booked', 'shipment_booked',
                    'picked up', 'picked_up', 'pkp', 'out for pickup', 'out_for_pickup',
                    'out of pickup', 'dispatched', 'pkf',
                )
            elif stage_lower == "in transit":
                cs_lower = (order['current_status'] or '').lower()
                matched = cs_lower in (
                    'in transit', 'in_transit', 'out for delivery', 'out_for_delivery',
                    'ofp', 'nfid', 'rad', 'reached at destination', 'reached_at_destination',
                    'consignee unavailable', 'nfi', 'pnr',
                )
            elif stage_lower == "ndr (failed delivery)" or stage_lower == "ndr":
                matched = bool(order['is_ndr'])
            elif stage_lower == "delivered orders" or stage_lower == "delivered":
                cs_lower = (order['current_status'] or '').lower()
                matched = cs_lower in ('delivered', 'dlv', 'del')
            elif stage_lower == "rto intransit":
                cs_lower = (order['current_status'] or '').lower()
                matched = (order['current_status'] in RTO_TRANSIT_STATUSES
                           or cs_lower in ('rto in transit', 'rto in-transit', 'rto_in_transit',
                                           'rto initiated', 'rto_initiated', 'rto - initiated',
                                           'rto - in transit', 'return in transit', 'return_in_transit'))
            elif stage_lower == "rto delivered":
                cs_lower = (order['current_status'] or '').lower()
                matched = (order['current_status'] in RTO_DELIVERED_STATUSES
                           or cs_lower in ('rto delivered', 'rto_delivered', 'rto - delivered',
                                           'return delivered', 'return_delivered'))
            elif stage_lower == "returns":
                matched = (order['rto_internal_status'] != 'Pending')
            elif stage_lower == "exchange":
                matched = is_exchange
            elif stage_lower == "restocked":
                matched = (order['rto_internal_status'] == 'Restocked')
            elif stage_lower == "cancelled":
                matched = (order['status'] == 'Cancelled')
            elif stage_lower == "new order created":
                matched = (order['created_at'] and order['created_at'] >= yesterday)
                
            if matched:
                d = stage_data[stage]
                d['total'] += 1
                d['amt'] += total_price
                
                if payment_type == 'COD':
                    d['cod'] += 1
                    d['amt_cod'] += total_price
                elif payment_type == 'Partially Paid':
                    d['partial'] += 1
                    d['amt_partial'] += total_price
                else:
                    d['prepaid'] += 1
                    d['amt_prepaid'] += total_price
                    
                if is_exchange:
                    d['exchange'] += 1
                    d['amt_exchange'] += total_price

    # ------------------------------------------------------------------
    # 5. Assemble response structure
    # ------------------------------------------------------------------
    summary = []
    for stage in STAGE_LIST:
        d = stage_data[stage]
        breakdown = [
            {"order_type": "Prepaid",        "qty": d['prepaid'],  "amount": d['amt_prepaid']},
            {"order_type": "COD",            "qty": d['cod'],      "amount": d['amt_cod']},
            {"order_type": "Partial COD",    "qty": d['partial'],  "amount": d['amt_partial']},
            {"order_type": "Exchange/Return","qty": d['exchange'], "amount": d['amt_exchange']},
        ]
        summary.append({
            "stage_name": stage,
            "total_orders": d['total'],
            "breakdown": breakdown,
        })

    # ------------------------------------------------------------------
    # 6. Cache and return
    # ------------------------------------------------------------------
    cache.set(cache_key, summary, STAGE_SUMMARY_CACHE_TTL)
    cache.set(f"stage_summary_stale:{org_id}", summary, STAGE_SUMMARY_CACHE_TTL * 4)
    return Response(summary)
