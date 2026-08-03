"""
Operations Summary API — Aggregates live counts from all operational sheets
(Calling, AWB, Confirmation, Packaging) into a single JSON response.
"""
import logging
from datetime import datetime, timedelta, date

from django.db.models import Q, Sum, Count, DecimalField
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Order, Batch, PackagingBatch
from core.utils.payment_utils import get_payment_q_objects

logger = logging.getLogger(__name__)


def _get_org_id(request):
    """Retrieve org_id for the current user."""
    if not request.user.is_authenticated:
        return None
    if hasattr(request.user, 'shop_credentials'):
        return request.user.shop_credentials.organization_id
    try:
        membership = request.user.workspace_memberships.first()
        if membership and membership.workspace:
            return membership.workspace.organization_id
    except Exception:
        pass
    try:
        return request.user.team_settings.organization.organization_id
    except Exception:
        return None


def _classify_payment(order):
    """Classify a single order into 'cod', 'ppcod', or 'prepaid'."""
    fs = (order.financial_status or '').lower()
    tags = (order.tags or '').lower()
    gateways = order.payment_gateway_names or []
    gateways_str = str(gateways).lower()

    if fs == 'partially_paid' or 'partial payment' in tags or 'ppcod' in gateways_str:
        return 'ppcod'
    if fs == 'pending' or 'cash on delivery' in gateways_str or 'cash_on_delivery' in gateways_str:
        return 'cod'
    return 'prepaid'


def _normalize_courier(company_name):
    if not company_name:
        return 'Other'
    name = company_name.lower()
    if 'bluedart' in name:
        return 'Bluedart'
    if 'delhivery' in name:
        return 'Delhivery'
    if 'xpressbees' in name:
        return 'Xpressbees'
    if 'ecom' in name:
        return 'Ecom Express'
    if 'amazon' in name:
        return 'Amazon Shipping'
    if 'shadowfax' in name:
        return 'Shadowfax'
    if 'dtdc' in name:
        return 'DTDC'
    return company_name


def _get_courier_for_order(order):
    """Extract courier company name from order fulfillments."""
    for f in order.fulfillments.all():
        for t in f.tracking_info.all():
            if t.number and t.number.strip():
                return _normalize_courier(t.company)
    return None


def _build_calling_summary(org_id, date_start, date_end):
    """Build calling sheet summary — Risk × Payment matrix + agent performance."""
    # Calling sheet: unfulfilled orders where status is not Batched/Confirmed
    calling_qs = Order.objects.filter(
        org_id=org_id,
        fulfillment_status__isnull=True,
    ).exclude(
        status__in=['Batched', 'Cancelled']
    )

    if date_start:
        calling_qs = calling_qs.filter(created_at__date__gte=date_start)
    if date_end:
        calling_qs = calling_qs.filter(created_at__date__lte=date_end)

    calling_qs = calling_qs.select_related('confirmed_by')

    risk_levels = ['High', 'Medium', 'Low', 'Uncalled']
    payment_types = ['Prepaid', 'COD', 'PPCOD']

    matrix = {}
    for r in risk_levels:
        matrix[r] = {}
        for p in payment_types:
            matrix[r][p] = {'pending': 0, 'confirmed': 0}

    total = 0
    pending_count = 0
    confirmed_count = 0
    uncalled_count = 0
    follow_up_count = 0
    flagged_count = 0
    agent_counts = {}

    for order in calling_qs.iterator():
        total += 1
        pt = _classify_payment(order)
        pay_key = 'PPCOD' if pt == 'ppcod' else ('COD' if pt == 'cod' else 'Prepaid')

        is_confirmed = order.status == 'Confirmed'
        status_key = 'confirmed' if is_confirmed else 'pending'

        if is_confirmed:
            confirmed_count += 1
        else:
            pending_count += 1

        attempts = order.call_attempts or 0
        if attempts == 0:
            uncalled_count += 1
            risk_key = 'Uncalled'
        else:
            risk_key = order.risk_status or 'Low'
            if risk_key not in risk_levels[:3]:
                risk_key = 'Low'
            if not is_confirmed:
                follow_up_count += 1

        if order.intelligence_flag and order.intelligence_flag != 'NONE':
            flagged_count += 1

        if risk_key in matrix and pay_key in matrix[risk_key]:
            matrix[risk_key][pay_key][status_key] += 1

        if is_confirmed:
            agent = 'Shori' if order.is_auto_confirmed else (order.confirmed_by.username if order.confirmed_by else None)
            if agent:
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

    top_agents = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        'total': total,
        'pending': pending_count,
        'confirmed': confirmed_count,
        'uncalled': uncalled_count,
        'follow_up': follow_up_count,
        'flagged': flagged_count,
        'matrix': matrix,
        'top_agents': top_agents,
    }


def _build_awb_summary(org_id, date_start, date_end):
    """Build AWB sheet summary — pending orders + batch courier distribution."""
    # Pending AWB: confirmed orders without tracking
    pending_qs = Order.objects.filter(
        org_id=org_id,
        status='Confirmed',
    ).exclude(
        fulfillments__tracking_info__number__isnull=False
    )
    if date_start:
        pending_qs = pending_qs.filter(created_at__date__gte=date_start)
    if date_end:
        pending_qs = pending_qs.filter(created_at__date__lte=date_end)

    pending_cod = 0
    pending_ppcod = 0
    pending_prepaid = 0

    for order in pending_qs.iterator():
        pt = _classify_payment(order)
        if pt == 'cod':
            pending_cod += 1
        elif pt == 'ppcod':
            pending_ppcod += 1
        else:
            pending_prepaid += 1

    pending_total = pending_cod + pending_ppcod + pending_prepaid

    # AWB Batch summary
    awb_batches = Batch.objects.filter(
        name__startswith='printed_AWB_batch_',
        orders__org_id=org_id
    ).distinct()

    if date_start:
        awb_batches = awb_batches.filter(created_at__date__gte=date_start)
    if date_end:
        awb_batches = awb_batches.filter(created_at__date__lte=date_end)

    awb_batches = awb_batches.prefetch_related('orders__fulfillments__tracking_info')

    total_batches = awb_batches.count()
    courier_data = {}
    total_batch_orders = 0
    seen_orders = set()

    for batch in awb_batches:
        for order in batch.orders.all():
            if order.id in seen_orders:
                continue
            seen_orders.add(order.id)
            total_batch_orders += 1

            pt = _classify_payment(order)
            courier = _get_courier_for_order(order) or 'Unknown'

            if courier not in courier_data:
                courier_data[courier] = {'count': 0, 'cod': 0, 'ppcod': 0, 'prepaid': 0}

            courier_data[courier]['count'] += 1
            courier_data[courier][pt] += 1

    couriers = sorted(
        [{'name': k, **v} for k, v in courier_data.items()],
        key=lambda x: x['count'], reverse=True
    )

    totals = {
        'count': sum(c['count'] for c in couriers),
        'cod': sum(c['cod'] for c in couriers),
        'ppcod': sum(c['ppcod'] for c in couriers),
        'prepaid': sum(c['prepaid'] for c in couriers),
    }

    avg_per_batch = round(total_batch_orders / total_batches, 1) if total_batches > 0 else 0

    return {
        'pending_summary': {
            'cod': pending_cod,
            'ppcod': pending_ppcod,
            'prepaid': pending_prepaid,
            'total': pending_total,
        },
        'batch_summary': {
            'total_batches': total_batches,
            'total_orders': total_batch_orders,
            'avg_per_batch': avg_per_batch,
            'couriers': couriers,
            'totals': totals,
        }
    }


def _build_confirmation_summary(org_id, date_start, date_end):
    """
    Build confirmation sheet summary.
    Confirmation sheet = orders with status='Batched' in Batches
    filtered by the BATCH creation date (not order creation date).
    """
    VISIBLE_IFS = ['Pending', 'Fulfilled', 'On Hold']

    # Find batches in date range (same logic as BatchListView)
    batch_qs = Batch.objects.filter(
        orders__org_id=org_id,
        orders__status='Batched',
        orders__internal_fulfillment_status__in=VISIBLE_IFS,
    ).distinct()

    if date_start:
        batch_qs = batch_qs.filter(created_at__date__gte=date_start)
    if date_end:
        batch_qs = batch_qs.filter(created_at__date__lte=date_end)

    batch_qs = batch_qs.prefetch_related(
        'orders__fulfillments__tracking_info'
    )

    total = 0
    fulfilled = 0
    pending = 0
    on_hold = 0

    financials = {
        'total_orders': 0, 'total_amount': 0.0,
        'cod': {'qty': 0, 'amount': 0.0},
        'ppcod': {'qty': 0, 'amount': 0.0},
        'prepaid': {'qty': 0, 'amount': 0.0},
    }

    courier_data = {}
    seen_order_ids = set()

    for batch in batch_qs:
        for order in batch.orders.filter(
            org_id=org_id,
            status='Batched',
            internal_fulfillment_status__in=VISIBLE_IFS
        ).prefetch_related('fulfillments__tracking_info'):
            if order.id in seen_order_ids:
                continue
            seen_order_ids.add(order.id)
            total += 1

            ifs = (order.internal_fulfillment_status or '').lower()
            if ifs == 'fulfilled':
                fulfilled += 1
            elif ifs == 'on hold':
                on_hold += 1
            else:
                pending += 1

            pt = _classify_payment(order)
            price = float(order.total_price or 0)

            financials['total_orders'] += 1
            financials['total_amount'] += price
            financials[pt]['qty'] += 1
            financials[pt]['amount'] += price

            courier = _get_courier_for_order(order)
            if courier:
                if courier not in courier_data:
                    courier_data[courier] = {'total': 0, 'cod': 0, 'ppcod': 0, 'prepaid': 0}
                courier_data[courier]['total'] += 1
                courier_data[courier][pt] += 1

    courier_breakdown = sorted(
        [{'company': k, **v} for k, v in courier_data.items()],
        key=lambda x: x['total'], reverse=True
    )

    return {
        'overview': {'total': total, 'fulfilled': fulfilled, 'pending': pending, 'on_hold': on_hold},
        'financials': financials,
        'courier_breakdown': courier_breakdown,
    }


def _build_packaging_summary(org_id, date_start, date_end):
    """Build packaging sheet summary — financials + courier + batch progress."""
    pkg_batches = PackagingBatch.objects.filter(
        orders__org_id=org_id
    ).distinct()

    if date_start:
        pkg_batches = pkg_batches.filter(created_at__date__gte=date_start)
    if date_end:
        pkg_batches = pkg_batches.filter(created_at__date__lte=date_end)

    pkg_batches = pkg_batches.prefetch_related('orders__fulfillments__tracking_info')

    financials = {
        'total_orders': 0, 'total_amount': 0.0,
        'cod': {'qty': 0, 'amount': 0.0},
        'ppcod': {'qty': 0, 'amount': 0.0},
        'prepaid': {'qty': 0, 'amount': 0.0},
    }

    courier_counts = {}
    total_with_courier = 0
    batch_progress = []
    seen_orders = set()

    for batch in pkg_batches:
        b_total = 0
        b_packaged = 0
        b_on_hold = 0
        b_pending = 0

        for order in batch.orders.filter(org_id=org_id).prefetch_related('fulfillments__tracking_info'):
            b_total += 1
            ifs = (order.internal_fulfillment_status or '').lower()
            if ifs == 'packaged':
                b_packaged += 1
            elif ifs == 'on hold':
                b_on_hold += 1
            else:
                b_pending += 1

            if order.id not in seen_orders:
                seen_orders.add(order.id)

                pt = _classify_payment(order)
                price = float(order.total_price or 0)

                financials['total_orders'] += 1
                financials['total_amount'] += price
                financials[pt]['qty'] += 1
                financials[pt]['amount'] += price

                courier = _get_courier_for_order(order)
                if courier:
                    courier_counts[courier] = courier_counts.get(courier, 0) + 1
                    total_with_courier += 1

        completion = round((b_packaged / b_total) * 100) if b_total > 0 else 0
        batch_progress.append({
            'batch_id': batch.id,
            'total': b_total,
            'packaged': b_packaged,
            'on_hold': b_on_hold,
            'pending': b_pending,
            'completion': completion,
        })

    courier_breakdown = []
    for company, count in sorted(courier_counts.items(), key=lambda x: x[1], reverse=True):
        share = round((count / total_with_courier) * 100) if total_with_courier > 0 else 0
        courier_breakdown.append({'company': company, 'count': count, 'share': share})

    return {
        'financials': financials,
        'courier_breakdown': courier_breakdown,
        'batch_progress': batch_progress,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def operations_summary(request):
    """
    GET /api/operations/summary/
    Returns live summary data from all operational sheets.

    Query Params:
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        (defaults to today if not provided)
    """
    org_id = _get_org_id(request)
    if not org_id:
        return Response({'error': 'Organization not found'}, status=400)

    # Parse date filters
    start_str = request.query_params.get('start_date')
    end_str = request.query_params.get('end_date')

    if start_str:
        date_start = parse_date(start_str)
    else:
        date_start = timezone.now().date()

    if end_str:
        date_end = parse_date(end_str)
    else:
        date_end = timezone.now().date()

    try:
        calling = _build_calling_summary(org_id, date_start, date_end)
    except Exception as e:
        logger.error(f"Calling summary error: {e}", exc_info=True)
        calling = {'error': str(e)}

    try:
        awb = _build_awb_summary(org_id, date_start, date_end)
    except Exception as e:
        logger.error(f"AWB summary error: {e}", exc_info=True)
        awb = {'error': str(e)}

    try:
        confirmation = _build_confirmation_summary(org_id, date_start, date_end)
    except Exception as e:
        logger.error(f"Confirmation summary error: {e}", exc_info=True)
        confirmation = {'error': str(e)}

    try:
        packaging = _build_packaging_summary(org_id, date_start, date_end)
    except Exception as e:
        logger.error(f"Packaging summary error: {e}", exc_info=True)
        packaging = {'error': str(e)}

    return Response({
        'date_range': {
            'start': str(date_start) if date_start else None,
            'end': str(date_end) if date_end else None,
        },
        'calling_sheet': calling,
        'awb_sheet': awb,
        'confirmation_sheet': confirmation,
        'packaging_sheet': packaging,
    })
