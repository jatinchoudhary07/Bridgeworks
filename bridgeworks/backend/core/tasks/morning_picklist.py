import logging
from django.utils import timezone
from core.models import ShopCredentials, TeamMemberSettings
from core.services.picklist_service import get_pending_picklist_orders, send_picklist_email

logger = logging.getLogger(__name__)

def send_morning_picklist_task():
    """
    Scheduled Job (7:00 AM IST / 01:30 UTC):
    Finds active organizations, queries their subscribed team members,
    generates their picklist file, and emails it.
    """
    logger.info("[MORNING-PICKLIST-TASK] Starting scheduled task...")
    
    # Find all shops/organizations
    shops = ShopCredentials.objects.all()
    
    for shop in shops:
        org_id = shop.organization_id
        
        # Check if auto sending picklists is enabled
        if not getattr(shop, 'enable_auto_send_picklists', True):
            logger.info(f"[MORNING-PICKLIST-TASK] Skipped org {org_id} because auto-send picklists is disabled in settings.")
            continue
        
        # Get all subscribed users for this org
        subscribers = TeamMemberSettings.objects.filter(
            organization=shop,
            subscribe_picklist_email=True
        ).select_related('user')
        
        recipient_emails = [sub.user.email for sub in subscribers if sub.user.email]
        
        if not recipient_emails:
            # Fallback to organization owner email if no one has explicitly subscribed
            owner_emails = TeamMemberSettings.objects.filter(
                organization=shop,
                role='founder'
            ).select_related('user')
            recipient_emails = [owner.user.email for owner in owner_emails if owner.user.email]
            
        if not recipient_emails:
            logger.warning(f"[MORNING-PICKLIST-TASK] No subscribers or founders found with valid email for org {org_id}. Skipping.")
            continue
            
        orders = get_pending_picklist_orders(org_id)
        
        if not orders.exists():
            logger.info(f"[MORNING-PICKLIST-TASK] No pending orders for org {org_id}. Skipping.")
            continue
            
        try:
            from django_q.tasks import async_task
            order_ids = list(orders.values_list('id', flat=True))
            async_task(
                'core.tasks.shipway_sync.auto_generate_awb_for_orders_task',
                order_ids,
                org_id,
                recipient_emails,
                False, # is_manual = False
                None,  # user_id = None
                task_name=f"auto_awb_morning_{org_id}_{len(order_ids)}"
            )
            logger.info(f"[MORNING-PICKLIST-TASK] Successfully queued auto AWB and picklist task for org {org_id} (orders: {len(order_ids)})")
        except Exception as e:
            logger.error(f"[MORNING-PICKLIST-TASK] Failed for org {org_id}: {e}", exc_info=True)
