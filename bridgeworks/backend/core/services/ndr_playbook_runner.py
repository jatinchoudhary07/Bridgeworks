"""
ndr_playbook_runner.py
======================
Executes configured NDRPlaybooks for classified NDR orders.
Handles routing, step verification, and multi-tenant integrations.
"""

import logging
import requests
from django.utils import timezone
from core.models import Order
from core.models.delivery import NDRPlaybook

logger = logging.getLogger(__name__)


def evaluate_playbook_conditions(order: Order, playbook: NDRPlaybook) -> bool:
    """
    Evaluates custom operational conditions stored in the playbook configuration.
    """
    conditions = playbook.conditions
    if not conditions:
        return True

    # 1. Minimum Order Value Check
    min_val = conditions.get('min_order_value')
    if min_val is not None:
        if float(order.total_price or 0) < float(min_val):
            return False

    # 2. Maximum Order Value Check
    max_val = conditions.get('max_order_value')
    if max_val is not None:
        if float(order.total_price or 0) > float(max_val):
            return False

    # 3. Pincode Blacklist Check
    exclude_pincodes = conditions.get('exclude_pincodes', [])
    if exclude_pincodes and order.shipping_pincode in exclude_pincodes:
        return False

    # 4. Pincode Whitelist Check
    include_pincodes = conditions.get('include_pincodes', [])
    if include_pincodes and order.shipping_pincode not in include_pincodes:
        return False

    # 5. Customer Risk Score Check
    min_customer_risk = conditions.get('min_customer_risk_score')
    if min_customer_risk is not None:
        profile = getattr(order, 'customer_risk_profile', None)
        if profile and profile.risk_score < int(min_customer_risk):
            return False

    return True


def execute_playbook_step(order: Order, step: dict, shop_creds) -> bool:
    """
    Executes a single step in the playbook action array.
    Designed to be open-ended for Chatwoot CRM / external WhatsApp integrations.
    """
    action_type = step.get('action')
    if not action_type:
        return False

    if action_type == 'send_whatsapp':
        template_id = step.get('template_id')
        logger.info(f"[PLAYBOOK] Outbound WhatsApp trigger request. Order #{order.order_number}, Template: {template_id}")

        endpoint = shop_creds.chatwoot_endpoint
        api_key = shop_creds.get_chatwoot_api_key()

        if endpoint:
            try:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                payload = {
                    "event": "ndr_playbook_trigger",
                    "order_number": order.order_number,
                    "phone": order.contact_phone,
                    "template_id": template_id,
                    "reason_category": order.ndr_reason_category,
                    "metadata": {
                        "customer_name": f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
                        "amount": float(order.total_price or 0),
                        "pincode": order.shipping_pincode or ""
                    }
                }
                
                # Make the outbound POST request to Chatwoot/CRM
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                logger.info(f"[PLAYBOOK] Outbound webhook sent to {endpoint}. Status: {resp.status_code}")
                return resp.ok
            except Exception as e:
                logger.error(f"[PLAYBOOK] Failed to dispatch CRM webhook to {endpoint}: {e}")
                return False
        else:
            logger.warning(f"[PLAYBOOK] No CRM webhook endpoint configured for ShopCredentials of org {order.org_id}.")
            return False

    elif action_type == 'manual_agent_queue':
        logger.info(f"[PLAYBOOK] Route Order #{order.order_number} to manual agent calling queue.")
        order.ndr_call_status = 'Pending Agent Call'
        
        if not isinstance(order.ndr_call_history, list):
            order.ndr_call_history = []
        
        order.ndr_call_history.insert(0, {
            'datetime': timezone.now().isoformat(),
            'status': 'Pending Agent Call',
            'remark': 'Auto-assigned to agent desk via NDR Playbook routing.',
            'agent': 'System',
            'source': 'playbook'
        })
        order.save(update_fields=['ndr_call_status', 'ndr_call_history'])
        return True

    elif action_type == 'auto_rto':
        logger.info(f"[PLAYBOOK] Flagging Order #{order.order_number} for Auto-RTO.")
        order.ndr_escalation_status = 'RTO_CONFIRMED'
        order.save(update_fields=['ndr_escalation_status'])
        return True

    return False


def run_ndr_playbook_for_order(order: Order) -> bool:
    """
    Finds the playbook that matches the classified reason category,
    evaluates conditions, and executes the associated action array.
    """
    from core.models import ShopCredentials

    category = order.ndr_reason_category
    if not category:
        logger.info(f"[PLAYBOOK] Order #{order.order_number} has no NDR reason category. Skipping.")
        return False

    try:
        shop_creds = ShopCredentials.objects.get(organization_id=order.org_id)
    except ShopCredentials.DoesNotExist:
        logger.warning(f"[PLAYBOOK] ShopCredentials matching org {order.org_id} not found.")
        return False

    # Find the matching playbook with the highest priority
    playbook = NDRPlaybook.objects.filter(
        org_id=order.org_id,
        reason_category=category,
        is_active=True
    ).order_by('-priority').first()

    if not playbook:
        logger.info(f"[PLAYBOOK] No active playbook found for org {order.org_id} under category {category}.")
        return False

    if not evaluate_playbook_conditions(order, playbook):
        logger.info(f"[PLAYBOOK] Order #{order.order_number} did not satisfy conditions for playbook '{playbook.name}'.")
        return False

    logger.info(f"[PLAYBOOK] Running playbook '{playbook.name}' for Order #{order.order_number}")
    success = True

    for step in playbook.actions:
        try:
            step_ok = execute_playbook_step(order, step, shop_creds)
            if not step_ok:
                success = False
        except Exception as err:
            logger.error(f"[PLAYBOOK] Error running step {step} for Order #{order.order_number}: {err}")
            success = False

    return success
