import logging
from django.utils import timezone
from core.models import Order

logger = logging.getLogger(__name__)

def auto_confirm_if_eligible(order: Order):
    """
    Auto-confirms a pending order if:
    - Status is still 'Pending'
    - Order is NOT a test order (field check + tag check + price check)
    - risk_score is > 30 (trustworthy/medium risk)
    """
    try:
        from core.models import ShopCredentials
        shop_cred = ShopCredentials.objects.get(organization_id=order.org_id)
        if not getattr(shop_cred, 'enable_auto_confirm_orders', True):
            logger.info(f"[AUTO-CONFIRM] Order #{order.order_number} skipped: auto-confirmation is disabled in settings.")
            return
    except Exception as e:
        logger.error(f"[AUTO-CONFIRM] Error checking settings for order #{order.order_number}: {e}")

    if order.status not in ['Pending', 'On Hold']:
        logger.info(f"[AUTO-CONFIRM] Order #{order.order_number} skipped: status is '{order.status}'.")
        return

    if order.check_is_test():
        logger.info(f"[AUTO-CONFIRM] Order #{order.order_number} skipped: identified as a test order.")
        return

    # Check if the score meets the auto-confirmation criteria (>30)
    # Note: 0 = high risk, 100 = safe trust score.
    if order.risk_score is None or order.risk_score <= 30:
        logger.info(f"[AUTO-CONFIRM] Order #{order.order_number} skipped: score {order.risk_score} <= 30.")
        return

    # Auto-confirm the order
    order.status = 'Confirmed'
    order.is_auto_confirmed = True
    order.confirmed_at = timezone.now()
    order.confirmed_by = None  # Confirmed by system
    order.save(update_fields=['status', 'is_auto_confirmed', 'confirmed_at', 'confirmed_by'])
    logger.info(f"[AUTO-CONFIRM] ✅ Order #{order.order_number} successfully auto-confirmed (Score: {order.risk_score}).")


def bulk_confirm_orders_task(order_numbers, org_id, user_id=None):
    """
    Background worker task to confirm a list of orders in bulk.
    Updates status to 'Confirmed' atomically in a transaction.
    """
    logger.info(f"Starting bulk confirmation for orders: {order_numbers} for org: {org_id}")
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from core.models import Order

    User = get_user_model()
    user = None
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(f"User with ID {user_id} not found when bulk confirming orders.")
            
    now = timezone.now()
    
    with transaction.atomic():
        orders = Order.objects.filter(
            order_number__in=order_numbers,
            org_id=org_id
        ).select_for_update()
        
        count = 0
        for order in orders:
            if order.status in ['Pending', 'On Hold']:
                order.status = 'Confirmed'
                order.confirmed_at = now
                order.confirmed_by = user
                order.save(update_fields=['status', 'confirmed_at', 'confirmed_by'])
                count += 1
                
    logger.info(f"Successfully bulk confirmed {count} out of {len(order_numbers)} orders.")
    return {"confirmed_count": count, "total": len(order_numbers)}

