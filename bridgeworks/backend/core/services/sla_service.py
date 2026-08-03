"""
sla_service.py — SLA Dashboard Service
=======================================
Breach detection and KPI computation for the SLA Dashboard.

Key functions:
  - compute_sla_kpis(org_id, start_date, end_date)   → dict of dashboard KPIs
  - get_sla_breach_table(org_id, start_date, end_date) → per-courier table
  - get_sla_state_performance(org_id, start_date, end_date) → per-state breakdown
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Avg, Q, F, Value, DecimalField, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_actual_days(shipment):
    """Return actual transit days for a delivered shipment, or None if dates missing."""
    if shipment.dispatch_date and shipment.delivery_date:
        return max(0, (shipment.delivery_date - shipment.dispatch_date).days)
    return None


def compute_sla_kpis(org_id: str, start_date, end_date) -> dict:
    """
    Compute top-level SLA KPIs for the dashboard header.

    Returns:
        {
            sla_met_count: int,
            sla_breached_count: int,
            sla_met_pct: float,
            sla_breached_pct: float,
            avg_delay_days: float,       # avg breach days (only for breached)
            penalty_recovery: float,     # total penalty ₹ recovered
            total_delivered: int,
            contracts_active: int,
        }
    """
    from core.models.delivery import Shipment, CourierSLAContract

    delivered_qs = Shipment.objects.filter(
        org_id=org_id,
        current_stage='Delivered',
        dispatch_date__date__gte=start_date,
        dispatch_date__date__lte=end_date,
        dispatch_date__isnull=False,
        delivery_date__isnull=False,
    )

    contracts = {
        (c.courier_partner, c.zone): c
        for c in CourierSLAContract.objects.filter(org_id=org_id, is_active=True)
    }

    if not contracts:
        # No SLA contracts configured — return raw totals only
        total = delivered_qs.count()
        return {
            'sla_met_count': 0,
            'sla_breached_count': 0,
            'sla_met_pct': 0,
            'sla_breached_pct': 0,
            'avg_delay_days': 0,
            'penalty_recovery': 0,
            'total_delivered': total,
            'contracts_active': 0,
            'no_contracts': True,
        }

    met = 0
    breached = 0
    total_breach_days = 0
    total_penalty = Decimal('0')

    # Batch fetch to avoid N+1
    shipments = list(delivered_qs.values(
        'courier_partner', 'zone', 'dispatch_date', 'delivery_date'
    )[:50000])

    for s in shipments:
        key = (s['courier_partner'], s['zone'])
        contract = contracts.get(key)
        if not contract:
            continue  # No contract for this courier/zone — skip SLA check

        if s['dispatch_date'] and s['delivery_date']:
            actual_days = max(0, (s['delivery_date'].date() - s['dispatch_date'].date()).days)
            if actual_days <= contract.promised_days:
                met += 1
            else:
                breached += 1
                breach_days = actual_days - contract.promised_days
                total_breach_days += breach_days
                total_penalty += contract.penalty_per_day * breach_days

    total_with_contract = met + breached
    return {
        'sla_met_count': met,
        'sla_breached_count': breached,
        'sla_met_pct': round((met / total_with_contract) * 100, 1) if total_with_contract else 0,
        'sla_breached_pct': round((breached / total_with_contract) * 100, 1) if total_with_contract else 0,
        'avg_delay_days': round(total_breach_days / breached, 1) if breached else 0,
        'penalty_recovery': float(total_penalty),
        'total_delivered': delivered_qs.count(),
        'contracts_active': len(contracts),
    }


def get_sla_breach_table(org_id: str, start_date, end_date) -> list:
    """
    Per-courier × zone SLA breach table.

    Returns list of rows:
        [
            {
                courier: str,
                zone: str,
                promised_days: int,
                total_shipments: int,
                met: int,
                breached: int,
                met_pct: float,
                avg_actual_days: float,
                avg_delay_days: float,
                penalty_recovery: float,
            },
            ...
        ]
    """
    from core.models.delivery import Shipment, CourierSLAContract

    contracts = list(CourierSLAContract.objects.filter(org_id=org_id, is_active=True))
    if not contracts:
        return []

    delivered_qs = Shipment.objects.filter(
        org_id=org_id,
        current_stage='Delivered',
        dispatch_date__date__gte=start_date,
        dispatch_date__date__lte=end_date,
        dispatch_date__isnull=False,
        delivery_date__isnull=False,
    )

    # Group by courier + zone
    from collections import defaultdict
    bucket = defaultdict(list)
    for s in delivered_qs.values('courier_partner', 'zone', 'dispatch_date', 'delivery_date')[:50000]:
        bucket[(s['courier_partner'], s['zone'])].append(s)

    rows = []
    for contract in contracts:
        key = (contract.courier_partner, contract.zone)
        shipments = bucket.get(key, [])
        met = 0
        breached = 0
        total_actual = 0
        total_breach = 0
        total_penalty = Decimal('0')

        for s in shipments:
            days = max(0, (s['delivery_date'].date() - s['dispatch_date'].date()).days)
            total_actual += days
            if days <= contract.promised_days:
                met += 1
            else:
                breached += 1
                bd = days - contract.promised_days
                total_breach += bd
                total_penalty += contract.penalty_per_day * bd
 
        total = len(shipments)
        rows.append({
            'courier': contract.courier_partner,
            'courier_partner': contract.courier_partner,
            'zone': contract.zone,
            'shipping_mode': contract.shipping_mode,
            'promised_days': contract.promised_days,
            'penalty_per_day': float(contract.penalty_per_day),
            'total_shipments': total,
            'met': met,
            'breached': breached,
            'met_pct': round((met / total) * 100, 1) if total else 0,
            'met_percentage': round((met / total) * 100, 1) if total else 0,
            'sla_met_pct': round((met / total) * 100, 1) if total else 0,
            'avg_actual_days': round(total_actual / total, 1) if total else 0,
            'avg_delay_days': round(total_breach / breached, 1) if breached else 0,
            'penalty_recovery': float(total_penalty),
        })

    rows.sort(key=lambda x: x['breached'], reverse=True)
    return rows


def get_sla_state_performance(org_id: str, start_date, end_date) -> list:
    """
    Per-state SLA performance.

    Returns list of rows per state with met %, breach %, avg actual days.
    Uses avg promised_days across all active contracts as baseline when no
    specific state-level contract exists.
    """
    from core.models.delivery import Shipment, CourierSLAContract

    contracts = list(CourierSLAContract.objects.filter(org_id=org_id, is_active=True))
    if not contracts:
        return []

    # Build a lookup: (courier, zone) → promised_days
    contract_map = {(c.courier_partner, c.zone): c.promised_days for c in contracts}

    delivered_qs = Shipment.objects.filter(
        org_id=org_id,
        current_stage='Delivered',
        dispatch_date__date__gte=start_date,
        dispatch_date__date__lte=end_date,
        dispatch_date__isnull=False,
        delivery_date__isnull=False,
        order__shipping_state__isnull=False,
    ).exclude(order__shipping_state='').values(
        'courier_partner', 'zone', 'dispatch_date', 'delivery_date',
        'order__shipping_state'
    )[:50000]

    from collections import defaultdict
    state_data = defaultdict(lambda: {'met': 0, 'breached': 0, 'total_days': 0})

    for s in delivered_qs:
        state = s['order__shipping_state']
        promised = contract_map.get((s['courier_partner'], s['zone']))
        if promised is None:
            continue
        days = max(0, (s['delivery_date'].date() - s['dispatch_date'].date()).days)
        state_data[state]['total_days'] += days
        if days <= promised:
            state_data[state]['met'] += 1
        else:
            state_data[state]['breached'] += 1
 
    rows = []
    for state, d in state_data.items():
        total = d['met'] + d['breached']
        rows.append({
            'state': state,
            'total_shipments': total,
            'met': d['met'],
            'breached': d['breached'],
            'met_pct': round((d['met'] / total) * 100, 1) if total else 0,
            'met_percentage': round((d['met'] / total) * 100, 1) if total else 0,
            'sla_met_pct': round((d['met'] / total) * 100, 1) if total else 0,
            'avg_actual_days': round(d['total_days'] / total, 1) if total else 0,
        })

    rows.sort(key=lambda x: x['breached'], reverse=True)
    return rows
