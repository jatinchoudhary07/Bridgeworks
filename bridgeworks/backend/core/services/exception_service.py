"""
exception_service.py — Exception Management Center Service
===========================================================
Auto-detection of shipment exceptions + summary analytics.

Key functions:
  - auto_detect_exceptions(org_id)     → (created, skipped)
  - get_exception_summary(org_id)      → counts by type + status
"""
import logging
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count, Q

logger = logging.getLogger(__name__)


# Detection thresholds
LOST_THRESHOLD_DAYS = 15          # In Transit > 15 days with no delivery → Lost
MISSING_SCAN_THRESHOLD_DAYS = 3   # No tracking event in 3 days → MissingScan


def auto_detect_exceptions(org_id: str) -> tuple:
    """
    Scan all active in-transit shipments for auto-detectable exceptions.
    Skips any shipment that already has a matching open exception.

    Detection rules:
        1. Lost       — Shipment.current_stage='In Transit' AND dispatch > 15 days ago
        2. Delayed    — Delivered but actual days > promised_days (CourierSLAContract)
        3. MissingScan — In Transit AND latest TrackingEvent > 3 days ago (or no events at all)

    Returns:
        (created_count: int, skipped_count: int)
    """
    from core.models.delivery import Shipment, CourierSLAContract, ShipmentException
    from core.models import TrackingEvent

    now = timezone.now()
    created = 0
    skipped = 0

    # ── 1. LOST — In Transit > 15 days ──────────────────────────────────────
    lost_cutoff = now - timedelta(days=LOST_THRESHOLD_DAYS)
    lost_candidates = Shipment.objects.filter(
        org_id=org_id,
        current_stage__in=['In Transit', 'in-transit', 'In-Transit', 'in transit'],
        dispatch_date__lt=lost_cutoff,
    ).select_related('order')

    existing_lost = set(ShipmentException.objects.filter(
        org_id=org_id,
        exception_type='Lost',
        status__in=['Open', 'InvestigationPending', 'ResolutionPending', 'ClaimRecovery'],
    ).values_list('shipment_id', flat=True))

    for shipment in lost_candidates:
        if shipment.id in existing_lost:
            skipped += 1
            continue
        try:
            days_in_transit = (now - shipment.dispatch_date).days
            ShipmentException.objects.create(
                org_id=org_id,
                shipment=shipment,
                exception_type='Lost',
                status='Open',
                description=(
                    f"Auto-detected: Shipment {shipment.awb_number} has been In Transit "
                    f"for {days_in_transit} days (threshold: {LOST_THRESHOLD_DAYS} days). "
                    f"Courier: {shipment.courier_partner}. "
                    f"Dispatched: {shipment.dispatch_date.strftime('%Y-%m-%d')}."
                ),
                is_auto_detected=True,
            )
            created += 1
        except Exception as e:
            logger.error(f"[EXCEPTION-DETECT] Failed to create Lost exception for {shipment.awb_number}: {e}")

    # ── 2. DELAYED — Delivered but past SLA promised days ───────────────────
    contracts = {
        (c.courier_partner, c.zone): c
        for c in CourierSLAContract.objects.filter(org_id=org_id, is_active=True)
    }

    if contracts:
        delivered_candidates = Shipment.objects.filter(
            org_id=org_id,
            current_stage='Delivered',
            dispatch_date__date__gte=(now - timedelta(days=90)).date(),
            dispatch_date__isnull=False,
            delivery_date__isnull=False,
        )

        existing_delayed = set(ShipmentException.objects.filter(
            org_id=org_id,
            exception_type='Delayed',
            status__in=['Open', 'InvestigationPending', 'ResolutionPending', 'ClaimRecovery'],
        ).values_list('shipment_id', flat=True))

        for shipment in delivered_candidates:
            if shipment.id in existing_delayed:
                skipped += 1
                continue
            contract = contracts.get((shipment.courier_partner, shipment.zone))
            if not contract:
                continue
            actual_days = max(0, (shipment.delivery_date - shipment.dispatch_date).days)
            if actual_days > contract.promised_days:
                breach_days = actual_days - contract.promised_days
                try:
                    ShipmentException.objects.create(
                        org_id=org_id,
                        shipment=shipment,
                        exception_type='Delayed',
                        status='Open',
                        description=(
                            f"Auto-detected SLA breach: {shipment.courier_partner} promised "
                            f"{contract.promised_days} days for zone '{contract.zone}', "
                            f"actual delivery took {actual_days} days "
                            f"({breach_days} day(s) late). AWB: {shipment.awb_number}."
                        ),
                        is_auto_detected=True,
                    )
                    created += 1
                except Exception as e:
                    logger.error(f"[EXCEPTION-DETECT] Failed to create Delayed exception for {shipment.awb_number}: {e}")

    # ── 3. MISSING SCAN — In Transit with no recent TrackingEvent ───────────
    scan_cutoff = now - timedelta(days=MISSING_SCAN_THRESHOLD_DAYS)

    in_transit_ids = list(
        Shipment.objects.filter(
            org_id=org_id,
            current_stage__in=['In Transit', 'in-transit', 'In-Transit', 'in transit'],
            dispatch_date__isnull=False,
        ).values_list('id', 'order_id')
    )

    existing_missing = set(ShipmentException.objects.filter(
        org_id=org_id,
        exception_type='MissingScan',
        status__in=['Open', 'InvestigationPending'],
    ).values_list('shipment_id', flat=True))

    for shipment_id, order_id in in_transit_ids:
        if shipment_id in existing_missing:
            skipped += 1
            continue

        # Check latest tracking event for this order's fulfillments
        latest_event = TrackingEvent.objects.filter(
            fulfillment__order_id=order_id
        ).order_by('-datetime').first()

        if latest_event is None or latest_event.datetime < scan_cutoff:
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                last_seen = latest_event.datetime.strftime('%Y-%m-%d') if latest_event else 'Never'
                ShipmentException.objects.create(
                    org_id=org_id,
                    shipment=shipment,
                    exception_type='MissingScan',
                    status='Open',
                    description=(
                        f"Auto-detected: No tracking update for shipment {shipment.awb_number} "
                        f"in the last {MISSING_SCAN_THRESHOLD_DAYS} days. "
                        f"Last scan: {last_seen}. Courier: {shipment.courier_partner}."
                    ),
                    is_auto_detected=True,
                )
                created += 1
            except Exception as e:
                logger.error(f"[EXCEPTION-DETECT] Failed to create MissingScan exception for shipment {shipment_id}: {e}")

    logger.info(f"[EXCEPTION-DETECT] Org {org_id}: {created} created, {skipped} skipped")
    return created, skipped


def get_exception_summary(org_id: str) -> dict:
    """
    Returns exception counts grouped by type and status for the dashboard.

    Returns:
        {
            by_type: [{type, total, open, in_progress, closed}],
            by_status: [{status, count}],
            total_open: int,
            total_claim_amount: float,
            total_recovered: float,
            recovery_rate: float,
        }
    """
    from core.models.delivery import ShipmentException
    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from decimal import Decimal

    qs = ShipmentException.objects.filter(org_id=org_id)

    # By status
    by_status = list(
        qs.values('status').annotate(count=Count('id')).order_by('-count')
    )

    # By type
    by_type_raw = list(
        qs.values('exception_type').annotate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status='Open')),
            in_progress=Count('id', filter=Q(
                status__in=['InvestigationPending', 'ResolutionPending', 'ClaimRecovery']
            )),
            closed_count=Count('id', filter=Q(status__in=['Closed', 'Rejected'])),
        ).order_by('-total')
    )

    # Financials
    financials = qs.aggregate(
        total_claim=Coalesce(Sum('claim_amount'), Decimal('0')),
        total_recovered=Coalesce(Sum('recovered_amount'), Decimal('0')),
    )

    total_claim = float(financials['total_claim'])
    total_recovered = float(financials['total_recovered'])
    recovery_rate = round((total_recovered / total_claim) * 100, 1) if total_claim > 0 else 0

    total_open = qs.filter(status='Open').count()

    return {
        'by_type': [
            {
                'type': r['exception_type'],
                'total': r['total'],
                'open': r['open_count'],
                'in_progress': r['in_progress'],
                'closed': r['closed_count'],
            }
            for r in by_type_raw
        ],
        'by_status': [{'status': r['status'], 'count': r['count']} for r in by_status],
        'total_open': total_open,
        'total_claim_amount': total_claim,
        'total_recovered': total_recovered,
        'recovery_rate': recovery_rate,
    }
