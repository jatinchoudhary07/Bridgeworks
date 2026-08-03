import json
import hmac
import hashlib
import time
import requests
from django.utils import timezone
from django_q.tasks import async_task
from core.models.webhooks import WebhookSubscription, OutboundWebhookLog

def dispatch_webhook_event(shop_id, event_type, payload):
    """
    Query active webhook subscriptions for this shop and event type,
    and trigger outbound requests in the background.
    """
    subscriptions = WebhookSubscription.objects.filter(
        shop_id=shop_id,
        event_type=event_type,
        is_active=True
    )
    
    for sub in subscriptions:
        # Queue dispatch as background task
        async_task(
            'core.services.webhook_dispatcher.send_webhook_request',
            sub.id,
            payload
        )

def send_webhook_request(subscription_id, payload):
    """
    Sends the POST request to the subscription's target URL, calculates HMAC-SHA256
    if a secret token is present, and logs the outcome in OutboundWebhookLog.
    """
    try:
        sub = WebhookSubscription.objects.get(id=subscription_id)
    except WebhookSubscription.DoesNotExist:
        return

    target_url = sub.target_url
    event_type = sub.event_type
    shop = sub.shop
    secret_token = sub.secret_token

    log_entry = OutboundWebhookLog.objects.create(
        shop=shop,
        subscription=sub,
        event_type=event_type,
        target_url=target_url,
        payload=payload,
        status='pending'
    )

    headers = {
        'Content-Type': 'application/json',
        'X-BridgeWorks-Event': event_type,
    }

    body_bytes = json.dumps(payload).encode('utf-8')

    if secret_token:
        # Generate signature
        signature = hmac.new(
            secret_token.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        headers['X-BridgeWorks-Signature'] = signature

    start_time = time.time()
    try:
        response = requests.post(
            target_url,
            data=body_bytes,
            headers=headers,
            timeout=10
        )
        duration = int((time.time() - start_time) * 1000)
        
        log_entry.response_status = response.status_code
        log_entry.response_body = response.text[:2000]
        log_entry.duration_ms = duration
        
        if 200 <= response.status_code < 300:
            log_entry.status = 'success'
        else:
            log_entry.status = 'failed'
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        log_entry.response_status = 500
        log_entry.response_body = f"Exception: {str(e)}"
        log_entry.duration_ms = duration
        log_entry.status = 'failed'

    log_entry.created_at = timezone.now()
    log_entry.save()
