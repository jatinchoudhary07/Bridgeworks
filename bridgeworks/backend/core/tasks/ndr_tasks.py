"""
ndr_tasks.py
============
Django-Q asynchronous background tasks for the NDR Module.
"""

import logging
from django.db.models import Q
from django.utils import timezone
from core.models import Order

logger = logging.getLogger(__name__)


def batch_classify_remarks_task(batch_size=50):
    """
    Django-Q Task: Selects all orders where is_ndr=True and
    ndr_reason_category is NULL / empty, and classifies them using Gemini.
    Runs periodically (e.g., every 15 minutes).
    """
    from core.services.ndr_classifier import classify_ndr_remark

    # Select orders that are in NDR state but lack classification (NULL or empty string)
    unclassified_orders = Order.objects.filter(
        is_ndr=True
    ).filter(
        Q(ndr_reason_category__isnull=True) | Q(ndr_reason_category='')
    ).exclude(current_status_details__isnull=True)[:batch_size]

    if not unclassified_orders.exists():
        logger.info("[NDR-CLASSIFIER] No new NDR remarks to classify.")
        return "No orders to classify"

    logger.info(f"[NDR-CLASSIFIER] Classifying {unclassified_orders.count()} NDR remarks...")
    classified_count = 0

    for order in unclassified_orders:
        remark_text = order.current_status_details or order.ndr_remarks or ""
        if not remark_text:
            continue

        result = classify_ndr_remark(remark_text)
        order.ndr_reason_category = result.get('category', 'OTHERS')
        order.ndr_classification_confidence = result.get('confidence', 0)
        
        # Also set last scan time if event date is available
        if order.current_status_date:
            order.ndr_last_scan_time = order.current_status_date
        else:
            order.ndr_last_scan_time = timezone.now()

        order.save(update_fields=[
            'ndr_reason_category',
            'ndr_classification_confidence',
            'ndr_last_scan_time'
        ])
        classified_count += 1
        logger.info(f"[NDR-CLASSIFIER] Order #{order.order_number} classified as {order.ndr_reason_category}")

    return f"Classified {classified_count} orders"


def daily_ndr_risk_rescoring_task():
    """
    Django-Q Task: Recalculates the RTO risk score (ndr_rto_risk_score)
    for all active NDR orders. Runs daily at midnight.
    """
    from core.services.customer_risk_service import compute_ndr_rto_score

    active_ndr_orders = Order.objects.filter(is_ndr=True)
    if not active_ndr_orders.exists():
        logger.info("[NDR-RISK-SCORER] No active NDR orders to rescore.")
        return "No orders to rescore"

    rescored_count = 0
    for order in active_ndr_orders:
        try:
            score = compute_ndr_rto_score(order)
            order.ndr_rto_risk_score = score
            order.save(update_fields=['ndr_rto_risk_score'])
            rescored_count += 1
            
            # Auto-RTO triggers if score >= 90
            if score >= 90 and order.ndr_escalation_status != 'RTO_CONFIRMED':
                logger.info(f"[NDR-RISK-SCORER] Order #{order.order_number} RTO Risk score is {score}. Triggering auto-RTO alert.")
                # We can flag it or notify merchant consent
                order.ndr_escalation_status = 'RTO_CONFIRMED'
                order.save(update_fields=['ndr_escalation_status'])
        except Exception as e:
            logger.error(f"[NDR-RISK-SCORER] Failed to rescore order #{order.order_number}: {e}")

    return f"Rescored {rescored_count} orders"
