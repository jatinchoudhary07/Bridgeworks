"""
views_control_tower.py — Logistics Control Tower API
====================================================
Real-time command center for logistics operations.
All endpoints are cached for 60 seconds (best balance between freshness and load).

Endpoints:
    GET /api/logistics/control-tower/live/           → Live shipment snapshot (today)
    GET /api/logistics/control-tower/courier-health/ → Per-courier health summary
    GET /api/logistics/control-tower/alerts/         → Active Aura alerts
"""
import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response

from core.permissions import HasModulePermission
from core.models.delivery import Shipment, ShipmentException
from core.models import CustomerRiskProfile
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # seconds — 60s cache for near-real-time freshness

# Stage classifications for control tower
STAGE_GROUPS = {
    'in_transit': ['In Transit', 'Out for Delivery'],
    'delivered': ['Delivered'],
    'ndr': ['Undelivered', 'NDR', 'Customer Not Available'],
    'rto': ['RTO', 'RTO In Transit', 'RTO Delivered', 'Returned to Origin'],
    'delayed': [],   # computed, not stage-based
    'lost': [],      # from ShipmentException
}


def _get_live_metrics(org_id: str) -> dict:
    """
    Compute today's live shipment metrics.
    Uses dispatch_date = today for "today" context.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_7_days = today - timedelta(days=7)

    # --- TODAY'S DISPATCHES ---
    today_qs = Shipment.objects.filter(
        org_id=org_id,
        dispatch_date__date=today,
    )
    today_total = today_qs.count()

    # --- OVERALL ACTIVE SHIPMENTS (last 30 days, not yet delivered/RTO) ---
    active_qs = Shipment.objects.filter(
        org_id=org_id,
        dispatch_date__date__gte=today - timedelta(days=30),
    )

    stage_counts = active_qs.values('current_stage').annotate(count=Count('id'))
    stage_map = {s['current_stage']: s['count'] for s in stage_counts}

    def sum_stages(stages):
        return sum(stage_map.get(s, 0) for s in stages)

    in_transit = sum_stages(STAGE_GROUPS['in_transit'])
    ndr = sum_stages(STAGE_GROUPS['ndr'])
    rto = sum_stages(STAGE_GROUPS['rto'])
    delivered = sum_stages(STAGE_GROUPS['delivered'])

    # Delayed: In Transit > 5 days
    delayed_cutoff = timezone.now() - timedelta(days=5)
    delayed = Shipment.objects.filter(
        org_id=org_id,
        current_stage__in=STAGE_GROUPS['in_transit'],
        dispatch_date__lt=delayed_cutoff,
    ).count()

    # Lost: Open Lost exceptions
    lost = ShipmentException.objects.filter(
        org_id=org_id,
        exception_type='Lost',
        status__in=['Open', 'InvestigationPending', 'ResolutionPending'],
    ).count()

    # High-risk customers count
    high_risk = CustomerRiskProfile.objects.filter(
        org_id=org_id, risk_level__in=['High', 'Blocked']
    ).count()

    # Open exceptions total
    open_exceptions = ShipmentException.objects.filter(
        org_id=org_id, status='Open'
    ).count()

    # Week's delivery rate
    week_delivered = Shipment.objects.filter(
        org_id=org_id,
        dispatch_date__date__gte=last_7_days,
        current_stage='Delivered',
    ).count()
    week_total = Shipment.objects.filter(
        org_id=org_id,
        dispatch_date__date__gte=last_7_days,
    ).count()
    delivery_rate_7d = round((week_delivered / week_total) * 100, 1) if week_total else 0

    return {
        'timestamp': timezone.now().isoformat(),
        'today': {
            'dispatched': today_total,
        },
        'active_shipments': {
            'in_transit': in_transit,
            'ndr': ndr,
            'rto': rto,
            'delivered': delivered,
            'delayed': delayed,
            'lost': lost,
        },
        'alerts': {
            'open_exceptions': open_exceptions,
            'high_risk_customers': high_risk,
        },
        'week_summary': {
            'total_dispatched': week_total,
            'delivered': week_delivered,
            'delivery_rate': delivery_rate_7d,
        },
    }


def _get_courier_health(org_id: str) -> list:
    """
    Per-courier health summary for the last 7 days.
    """
    from collections import defaultdict

    last_7_days = date.today() - timedelta(days=7)

    shipments = list(
        Shipment.objects.filter(
            org_id=org_id,
            dispatch_date__date__gte=last_7_days,
        ).values('courier_partner', 'current_stage')[:100000]
    )

    courier_data = defaultdict(lambda: {
        'total': 0, 'delivered': 0, 'rto': 0, 'ndr': 0, 'in_transit': 0
    })

    for s in shipments:
        c = s['courier_partner'] or 'Unknown'
        courier_data[c]['total'] += 1
        stage = s['current_stage'] or ''
        if stage == 'Delivered':
            courier_data[c]['delivered'] += 1
        elif 'rto' in stage.lower() or 'return' in stage.lower():
            courier_data[c]['rto'] += 1
        elif 'ndr' in stage.lower() or 'undeliver' in stage.lower():
            courier_data[c]['ndr'] += 1
        else:
            courier_data[c]['in_transit'] += 1

    rows = []
    for courier, d in courier_data.items():
        total = d['total']
        rows.append({
            'courier': courier,
            'total_shipments': total,
            'delivered': d['delivered'],
            'rto': d['rto'],
            'ndr': d['ndr'],
            'in_transit': d['in_transit'],
            'delivery_rate': round((d['delivered'] / total) * 100, 1) if total else 0,
            'rto_rate': round((d['rto'] / total) * 100, 1) if total else 0,
            'ndr_rate': round((d['ndr'] / total) * 100, 1) if total else 0,
            'health_status': (
                'Good' if (d['rto'] + d['ndr']) / total < 0.10
                else 'Warning' if (d['rto'] + d['ndr']) / total < 0.20
                else 'Critical'
            ) if total else 'Unknown',
        })

    rows.sort(key=lambda x: x['total_shipments'], reverse=True)
    return rows


def _get_active_alerts(org_id: str) -> list:
    """
    Build active alert list from:
    1. Open exceptions by type
    2. High-risk customers
    3. Courier health degradation
    """
    alerts = []

    # Exception-based alerts
    from django.db.models import Count
    exc_counts = ShipmentException.objects.filter(
        org_id=org_id, status='Open'
    ).values('exception_type').annotate(count=Count('id'))

    for exc in exc_counts:
        if exc['count'] > 0:
            alert_level = 'Critical' if exc['exception_type'] == 'Lost' else 'Warning'
            alerts.append({
                'type': 'ShipmentException',
                'exception_type': exc['exception_type'],
                'level': alert_level,
                'count': exc['count'],
                'message': f"{exc['count']} open {exc['exception_type']} exception(s) require attention.",
                'action_url': f'/logistics/exceptions?exception_type={exc["exception_type"]}&status=Open',
            })

    # High-risk customer alert
    high_risk_count = CustomerRiskProfile.objects.filter(
        org_id=org_id, risk_level='Blocked'
    ).count()
    if high_risk_count > 0:
        alerts.append({
            'type': 'CustomerRisk',
            'level': 'Warning',
            'count': high_risk_count,
            'message': f"{high_risk_count} Blocked-risk customer(s) — COD should be restricted.",
            'action_url': '/logistics/customer-risk?risk_level=Blocked',
        })

    # Sort: Critical first, then by count
    alerts.sort(key=lambda x: (0 if x['level'] == 'Critical' else 1, -x['count']))
    return alerts


class ControlTowerLiveView(APIView):
    """
    GET /api/logistics/control-tower/live/

    Real-time logistics snapshot. Cached for 60 seconds.

    Returns:
        today: { dispatched }
        active_shipments: { in_transit, ndr, rto, delivered, delayed, lost }
        alerts: { open_exceptions, high_risk_customers }
        week_summary: { total_dispatched, delivered, delivery_rate }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:control_tower:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        cache_key = f'control_tower:live:{org_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            cached['from_cache'] = True
            return Response(cached)

        try:
            data = _get_live_metrics(org_id)
            data['from_cache'] = False
            cache.set(cache_key, data, CACHE_TTL)
            return Response(data)
        except Exception as e:
            logger.error(f"[CONTROL-TOWER] live failed for org {org_id}: {e}")
            return Response({'error': 'Failed to compute live metrics'}, status=500)


class ControlTowerCourierHealthView(APIView):
    """
    GET /api/logistics/control-tower/courier-health/

    Per-courier health summary for the last 7 days. Cached for 60 seconds.

    Returns list of courier rows with delivery_rate, rto_rate, ndr_rate, health_status.
    health_status: Good (< 10% bad), Warning (10-20% bad), Critical (> 20% bad)
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:control_tower:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        cache_key = f'control_tower:courier_health:{org_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({'couriers': cached, 'from_cache': True})

        try:
            data = _get_courier_health(org_id)
            cache.set(cache_key, data, CACHE_TTL)
            return Response({'couriers': data, 'from_cache': False, 'period': 'last_7_days'})
        except Exception as e:
            logger.error(f"[CONTROL-TOWER] courier_health failed for org {org_id}: {e}")
            return Response({'error': 'Failed to compute courier health'}, status=500)


class ControlTowerAlertsView(APIView):
    """
    GET /api/logistics/control-tower/alerts/

    Active alerts from:
    - Open ShipmentException records (by type)
    - Blocked-risk customers
    - (Future: Aura AI-generated recommendations)

    Alerts are sorted: Critical first, then by count descending.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:control_tower:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        cache_key = f'control_tower:alerts:{org_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({'alerts': cached, 'from_cache': True})

        try:
            alerts = _get_active_alerts(org_id)
            cache.set(cache_key, alerts, CACHE_TTL)
            return Response({
                'alerts': alerts,
                'total': len(alerts),
                'from_cache': False,
            })
        except Exception as e:
            logger.error(f"[CONTROL-TOWER] alerts failed for org {org_id}: {e}")
            return Response({'error': 'Failed to compute alerts'}, status=500)
