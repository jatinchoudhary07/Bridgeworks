"""
ndr_engine.py
=============
BlueDart Panel CSV Processor for Escalation 1.

Reads the standard CSV output from BlueDart's panel,
matches AWBs to orders, and updates their escalation status.
"""

import csv
import io
import logging
from django.db import transaction
from django.utils import timezone
from core.models import Order, NDREscalationBatch, TrackingInfo

logger = logging.getLogger(__name__)


# Status keywords from BlueDart panel CSV
DELIVERED_KEYWORDS = {'accepted', 'delivered', 'success', 'completed'}
FAILED_KEYWORDS = {'failed', 'pending', 'undelivered', 'not delivered', 'rto', 'refused'}

ESCALATION_TIERS = {
    0: 'ESCALATION_1',
    1: 'ESCALATION_2',
    2: 'ESCALATION_3',
    3: 'RTO_CONFIRMED',  # After 3 escalations, auto-RTO
}


def _get_next_escalation(current_count):
    """Get the next escalation tier based on current count."""
    return ESCALATION_TIERS.get(current_count, 'RTO_CONFIRMED')


def _find_order_by_awb(awb):
    """Find an Order by its AWB number via TrackingInfo."""
    ti = TrackingInfo.objects.filter(number=awb).select_related(
        'fulfillment__order'
    ).first()
    if ti:
        return ti.fulfillment.order
    return None


@transaction.atomic
def process_bluedart_panel_csv(batch_id, csv_content):
    """
    Process a BlueDart panel CSV output for an existing batch.

    Args:
        batch_id: ID of the NDREscalationBatch to process
        csv_content: String content of the CSV file (or file-like object)

    Returns:
        dict with processing summary
    """
    try:
        batch = NDREscalationBatch.objects.get(id=batch_id)
    except NDREscalationBatch.DoesNotExist:
        return {'error': f'Batch {batch_id} not found'}

    # Parse CSV
    if isinstance(csv_content, str):
        reader = csv.DictReader(io.StringIO(csv_content))
    else:
        # File-like object
        decoded = csv_content.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))

    summary = {
        'total': 0,
        'delivered': 0,
        're_escalated': 0,
        'not_found': 0,
        'errors': [],
    }

    for row in reader:
        summary['total'] += 1

        # Try common column names for AWB
        awb = (
            row.get('AWB') or row.get('awb') or
            row.get('AWB Number') or row.get('awb_number') or
            row.get('Tracking Number') or row.get('tracking_number') or
            row.get('AIRWAYBILL NO') or ''
        ).strip()

        # Try common column names for Status
        status_raw = (
            row.get('Status') or row.get('status') or
            row.get('Delivery Status') or row.get('Result') or
            row.get('STATUS') or ''
        ).strip().lower()

        if not awb:
            summary['errors'].append(f"Row {summary['total']}: Missing AWB number")
            continue

        order = _find_order_by_awb(awb)
        if not order:
            summary['not_found'] += 1
            summary['errors'].append(f"AWB {awb}: Order not found in system")
            continue

        if any(kw in status_raw for kw in DELIVERED_KEYWORDS):
            # SUCCESS: Mark as delivered after escalation
            order.ndr_escalation_status = 'DELIVERED'
            order.save(update_fields=['ndr_escalation_status'])
            summary['delivered'] += 1

        elif any(kw in status_raw for kw in FAILED_KEYWORDS):
            # FAILED: Increment escalation count and advance tier
            order.ndr_escalation_count += 1
            order.ndr_escalation_status = _get_next_escalation(order.ndr_escalation_count)
            order.save(update_fields=['ndr_escalation_status', 'ndr_escalation_count'])
            summary['re_escalated'] += 1

        else:
            # Unknown status — treat as failed to be safe
            order.ndr_escalation_count += 1
            order.ndr_escalation_status = _get_next_escalation(order.ndr_escalation_count)
            order.save(update_fields=['ndr_escalation_status', 'ndr_escalation_count'])
            summary['re_escalated'] += 1
            summary['errors'].append(f"AWB {awb}: Unknown status '{status_raw}', treated as failed")

    # Update batch
    batch.status = 'PROCESSED'
    batch.processed_at = timezone.now()
    batch.summary = summary
    batch.save()

    return summary
