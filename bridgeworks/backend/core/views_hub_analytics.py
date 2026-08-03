"""
views_hub_analytics.py — Hub Analytics API
==========================================
Endpoints for Hub Analytics enterprise feature.

Hub Proxy Strategy:
    Since Shipway/tracking APIs do NOT return location data (hub names),
    hubs are proxied as: "{courier_partner} — {order.shipping_state}"
    e.g. "Bluedart — Maharashtra", "Delhivery — Delhi"

    When CourierZoneMapping.hub_name is populated (via zone mapping upload),
    Shipment.transit_hub is auto-filled and used as the hub label instead.

Endpoints:
    GET /api/logistics/hub-analytics/               → All hub metrics table
    GET /api/logistics/hub-analytics/top-bottlenecks/ → Top 5 worst-performing hubs
"""
import logging
from datetime import datetime, date, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response

from core.permissions import HasModulePermission
from core.services.hub_analytics_service import get_hub_metrics, get_top_bottlenecks
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)


def _parse_dates(request):
    """Parse start_date and end_date from query params. Defaults to last 30 days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    start_str = request.query_params.get('start_date') or request.query_params.get('from')
    end_str = request.query_params.get('end_date') or request.query_params.get('to')

    try:
        if start_str:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        if end_str:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        pass

    return start_date, end_date


class HubAnalyticsView(APIView):
    """
    GET /api/logistics/hub-analytics/

    Returns hub-level metrics table for all hubs in the date range.

    Query params:
        start_date, end_date    (YYYY-MM-DD, default: last 30 days)
        courier                 (filter by courier name, optional)
        state                   (filter by state, optional)
        sort_by                 (total_shipments | rto_rate | ndr_rate | delivery_rate | avg_transit_days)

    Each row:
        hub_label, courier, state, total_shipments, delivered, rto, ndr, in_transit,
        delivery_rate, rto_rate, ndr_rate, avg_transit_days, delay_rate

    Note on hub_label:
        Proxied as "Courier — State" until CourierZoneMapping.hub_name is populated.
        Example: "Bluedart — Maharashtra"
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:hub_analytics:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        courier_filter = request.query_params.get('courier', '').strip().lower()
        state_filter = request.query_params.get('state', '').strip().lower()
        sort_by = request.query_params.get('sort_by', 'total_shipments')

        VALID_SORTS = ['total_shipments', 'rto_rate', 'ndr_rate', 'delivery_rate', 'avg_transit_days', 'delay_rate']
        if sort_by not in VALID_SORTS:
            sort_by = 'total_shipments'

        try:
            rows = get_hub_metrics(org_id, start_date, end_date)
        except Exception as e:
            logger.error(f"[HUB-ANALYTICS] get_hub_metrics failed for org {org_id}: {e}")
            return Response({'error': 'Failed to compute hub metrics'}, status=500)

        # Post-fetch filtering
        if courier_filter:
            rows = [r for r in rows if courier_filter in r['courier'].lower()]
        if state_filter:
            rows = [r for r in rows if state_filter in r['state'].lower()]

        # Sort
        reverse = sort_by not in ('avg_transit_days',)  # all high-first except avg_transit_days
        rows.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

        return Response({
            'start_date': str(start_date),
            'end_date': str(end_date),
            'hub_data_note': (
                'Hubs are proxied as Courier — State since tracking API does not '
                'return hub location data. Upload a hub-level zone mapping via '
                '/api/delivery/zone-mappings/upload/ to enable named hubs.'
            ),
            'rows': rows,
            'count': len(rows),
        })


class HubBottlenecksView(APIView):
    """
    GET /api/logistics/hub-analytics/top-bottlenecks/

    Returns the top N worst-performing hubs (highest RTO + NDR rate combined).
    Only includes hubs with >= 10 shipments (statistically significant).

    Query params:
        start_date, end_date    (YYYY-MM-DD, default: last 30 days)
        n                       (number of bottlenecks to return, default: 5, max: 20)
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:hub_analytics:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        n = min(20, max(1, int(request.query_params.get('n', 5))))

        try:
            bottlenecks = get_top_bottlenecks(org_id, start_date, end_date, n=n)
        except Exception as e:
            logger.error(f"[HUB-ANALYTICS] get_top_bottlenecks failed for org {org_id}: {e}")
            return Response({'error': 'Failed to compute bottleneck data'}, status=500)

        return Response({
            'start_date': str(start_date),
            'end_date': str(end_date),
            'bottlenecks': bottlenecks,
            'count': len(bottlenecks),
            'note': 'Sorted by combined RTO + NDR rate (worst first). Min 10 shipments required.',
        })
