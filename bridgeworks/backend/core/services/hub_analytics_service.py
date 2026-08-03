"""
hub_analytics_service.py — Hub Analytics Service
=================================================
Computes hub-level shipment metrics.

IMPORTANT — Hub Location Reality:
    The Shipway/tracking API does NOT return hub/location data in tracking events.
    TrackingEvent.details only contains status strings like "RTO DELIVERED".

    Hub Proxy Strategy (Option A — current implementation):
        hub = f"{courier_partner} — {order.shipping_state}"
        e.g. "Bluedart — Maharashtra", "Delhivery — Delhi"

    Hub Upgrade Path (Option B — future):
        When CourierZoneMapping.hub_name is populated (via zone mapping upload),
        Shipment.transit_hub gets filled on dispatch via pincode lookup.
        At that point, switch hub_name field as the primary grouping key.

Key functions:
    - get_hub_metrics(org_id, start_date, end_date)        → list of hub rows
    - get_top_bottlenecks(org_id, start_date, end_date, n) → top N worst hubs
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Avg, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger(__name__)

# Stages used for classification
DELIVERED_STAGE = 'Delivered'
RTO_STAGES = {'RTO Delivered', 'RTO', 'RTO In Transit', 'Returned to Origin'}
NDR_STAGES = {'NDR', 'Undelivered', 'Out for Delivery', 'Customer Not Available'}


def _classify_stage(stage: str) -> str:
    """Classify a current_stage string into 'Delivered', 'RTO', 'NDR', or 'InTransit'."""
    if stage == DELIVERED_STAGE:
        return 'Delivered'
    s = stage.lower()
    if 'rto' in s or 'return' in s:
        return 'RTO'
    if 'ndr' in s or 'undeliver' in s or 'not available' in s:
        return 'NDR'
    return 'InTransit'


def get_hub_metrics(org_id: str, start_date, end_date) -> list:
    """
    Compute hub-level metrics by grouping shipments on:
        hub_label = courier_partner + "  —  " + order.shipping_state

    Falls back to named hubs via Shipment.transit_hub if populated.

    Returns list of dicts:
        [
            {
                hub_label: str,         # e.g. "Bluedart — Maharashtra"
                courier: str,
                state: str,
                total_shipments: int,
                delivered: int,
                rto: int,
                ndr: int,
                in_transit: int,
                delivery_rate: float,   # %
                rto_rate: float,        # %
                ndr_rate: float,        # %
                avg_transit_days: float,
                delay_rate: float,      # % shipments taking > 5 days
            },
            ...
        ]
    """
    from core.models.delivery import Shipment

    shipments = list(
        Shipment.objects.filter(
            org_id=org_id,
            dispatch_date__date__gte=start_date,
            dispatch_date__date__lte=end_date,
        ).exclude(
            order__shipping_state=''
        ).exclude(
            order__shipping_state__isnull=True
        ).values(
            'courier_partner',
            'zone',
            'current_stage',
            'dispatch_date',
            'delivery_date',
            'transit_hub',         # named hub if available
            'order__shipping_state',
        )[:100000]
    )

    # Group by hub
    hub_data = defaultdict(lambda: {
        'courier': '', 'state': '', 'total': 0,
        'delivered': 0, 'rto': 0, 'ndr': 0, 'in_transit': 0,
        'total_days': 0, 'delivered_count_with_days': 0, 'delayed': 0,
    })

    for s in shipments:
        courier = s['courier_partner'] or 'Unknown'
        state = s['order__shipping_state'] or 'Unknown'

        # Prefer named hub_name if available; else proxy
        hub_label = s.get('transit_hub') or f"{courier} — {state}"

        d = hub_data[hub_label]
        d['courier'] = courier
        d['state'] = state
        d['total'] += 1

        classification = _classify_stage(s['current_stage'] or '')
        if classification == 'Delivered':
            d['delivered'] += 1
            if s['dispatch_date'] and s['delivery_date']:
                days = max(0, (s['delivery_date'] - s['dispatch_date']).days)
                d['total_days'] += days
                d['delivered_count_with_days'] += 1
                if days > 5:  # > 5 days = delayed
                    d['delayed'] += 1
        elif classification == 'RTO':
            d['rto'] += 1
        elif classification == 'NDR':
            d['ndr'] += 1
        else:
            d['in_transit'] += 1

    rows = []
    for hub_label, d in hub_data.items():
        total = d['total']
        delivered = d['delivered']
        avg_days = round(d['total_days'] / d['delivered_count_with_days'], 1) if d['delivered_count_with_days'] else 0
        delay_rate = round((d['delayed'] / delivered) * 100, 1) if delivered else 0

        rows.append({
            'hub_label': hub_label,
            'courier': d['courier'],
            'state': d['state'],
            'total_shipments': total,
            'delivered': delivered,
            'rto': d['rto'],
            'ndr': d['ndr'],
            'in_transit': d['in_transit'],
            'delivery_rate': round((delivered / total) * 100, 1) if total else 0,
            'rto_rate': round((d['rto'] / total) * 100, 1) if total else 0,
            'ndr_rate': round((d['ndr'] / total) * 100, 1) if total else 0,
            'avg_transit_days': avg_days,
            'delay_rate': delay_rate,
        })

    # Sort by total_shipments descending
    rows.sort(key=lambda x: x['total_shipments'], reverse=True)
    return rows


def get_top_bottlenecks(org_id: str, start_date, end_date, n: int = 5) -> list:
    """
    Returns the top N worst-performing hubs (highest combined RTO + NDR rate).

    Bottleneck score = rto_rate + ndr_rate (higher = worse)
    Only includes hubs with >= 10 shipments to avoid statistical noise.

    Returns list of hub rows (same structure as get_hub_metrics), sorted worst-first.
    """
    all_hubs = get_hub_metrics(org_id, start_date, end_date)

    # Filter for statistical significance
    significant = [h for h in all_hubs if h['total_shipments'] >= 10]

    # Sort by combined bad rate (RTO + NDR)
    significant.sort(key=lambda x: x['rto_rate'] + x['ndr_rate'], reverse=True)

    return significant[:n]
