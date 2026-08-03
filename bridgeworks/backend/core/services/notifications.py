from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.models import UnifiedNotification


SOUND_CATEGORY_TASK_URGENT = 'task_urgent'
SOUND_CATEGORY_TASK_NORMAL = 'task_normal'
SOUND_CATEGORY_CHAT = 'chat'
SOUND_CATEGORY_GENERAL = 'general'
SOUND_CATEGORY_ASSIGN_BATCH = 'assign_batch'

_VALID_TASK_PRIORITIES = {'low', 'medium', 'high', 'critical'}
_VALID_SOUND_CATEGORIES = {
    SOUND_CATEGORY_TASK_URGENT,
    SOUND_CATEGORY_TASK_NORMAL,
    SOUND_CATEGORY_CHAT,
    SOUND_CATEGORY_GENERAL,
    SOUND_CATEGORY_ASSIGN_BATCH,
}


def normalize_task_priority(value):
    normalized = str(value or '').strip().lower()
    if normalized in _VALID_TASK_PRIORITIES:
        return normalized
    return ''


def resolve_notification_sound_category(*, module, task_priority='', explicit_category=''):
    explicit = str(explicit_category or '').strip().lower()
    if explicit in _VALID_SOUND_CATEGORIES:
        return explicit

    if module == UnifiedNotification.MODULE_TASKS:
        if task_priority in {'high', 'critical'}:
            return SOUND_CATEGORY_TASK_URGENT
        return SOUND_CATEGORY_TASK_NORMAL

    if module == UnifiedNotification.MODULE_CHATS:
        return SOUND_CATEGORY_CHAT

    return SOUND_CATEGORY_GENERAL


def _broadcast_to_user(recipient_id, event_type, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f'notifications_user_{recipient_id}',
        {
            'type': event_type,
            **payload,
        },
    )


def broadcast_notification_read(*, recipient_id, notification_id):
    _broadcast_to_user(
        recipient_id,
        'notification.read',
        {
            'notification_id': int(notification_id),
        },
    )


def broadcast_notification_all_read(*, recipient_id, notification_ids=None, read_at=''):
    ids = [int(value) for value in (notification_ids or [])]
    _broadcast_to_user(
        recipient_id,
        'notification.all_read',
        {
            'notification_ids': ids,
            'read_at': read_at or '',
        },
    )


def push_unified_notification(
    *,
    recipient,
    actor,
    module,
    action,
    message,
    title='',
    preview='',
    entity_type='',
    entity_id='',
    sub_entity_type='',
    sub_entity_id='',
    deep_link=None,
    metadata=None,
    task_priority='',
    sound_category='',
    priority='',
):
    metadata_payload = dict(metadata) if isinstance(metadata, dict) else {}

    resolved_task_priority = normalize_task_priority(
        task_priority or metadata_payload.get('task_priority') or metadata_payload.get('priority')
    )
    if module == UnifiedNotification.MODULE_TASKS and not resolved_task_priority:
        resolved_task_priority = 'medium'

    resolved_sound_category = resolve_notification_sound_category(
        module=module,
        task_priority=resolved_task_priority,
        explicit_category=sound_category or metadata_payload.get('sound_category'),
    )

    if resolved_task_priority:
        metadata_payload['task_priority'] = resolved_task_priority
    metadata_payload['sound_category'] = resolved_sound_category

    # Determine resolved notification priority
    resolved_priority = priority or metadata_payload.get('priority') or task_priority or metadata_payload.get('task_priority') or 'medium'
    resolved_priority = str(resolved_priority).strip().lower()
    if resolved_priority not in {'critical', 'high', 'medium', 'low'}:
        resolved_priority = 'medium'
    metadata_payload['priority'] = resolved_priority

    # 1. Write legacy UnifiedNotification (ensures zero regression)
    notification = UnifiedNotification.objects.create(
        recipient=recipient,
        actor=actor,
        module=module,
        action=action,
        title=title or '',
        message=message,
        preview=preview or '',
        entity_type=entity_type or '',
        entity_id=str(entity_id or ''),
        sub_entity_type=sub_entity_type or '',
        sub_entity_id=str(sub_entity_id or ''),
        deep_link=deep_link or {},
        metadata=metadata_payload,
    )

    # 2. Resolve shop credentials for tenant boundary
    from core.models.store import ShopCredentials
    shop = None
    if hasattr(recipient, 'shop_credentials'):
        shop = recipient.shop_credentials
    else:
        from core.models.users import WorkspaceMembership
        m = WorkspaceMembership.objects.filter(user=recipient).first()
        if m:
            shop = m.workspace
    if not shop:
        shop = ShopCredentials.objects.first()

    # 3. Determine new category mapping
    module_mapping = {
        'postits': 'taskmanager',
        'notes': 'taskmanager',
        'tasks': 'taskmanager',
        'my_chats': 'taskmanager',
        'expenses': 'finance',
        'leave_requests': 'hr',
        'gallery': 'taskmanager',
        'my_meetings': 'taskmanager',
        'training': 'taskmanager',
        'leads': 'sales',
        'quotes': 'sales',
    }
    
    mapped_module = module_mapping.get(module, module)
    category_list = [
        'leadership', 'product', 'branding', 'marketing', 'ecommerce',
        'operations', 'tracking', 'rto_management', 'taskmanager',
        'customerExperience', 'intelligence', 'webhooks', 'finance',
        'hr', 'it', 'production', 'sales'
    ]
    if mapped_module not in category_list:
        mapped_module = 'taskmanager'
    
    category = metadata_payload.get('category') or mapped_module
    if category not in category_list:
        category = 'taskmanager'

    # 4. Check user preferences
    from core.models.notification import Notification, NotificationPreference, NotificationDeliveryLog
    pref, _ = NotificationPreference.objects.get_or_create(
        user=recipient,
        category=category,
        defaults={'email_delivery': True, 'in_app_delivery': True, 'push_delivery': True}
    )

    new_notif = None
    if pref.in_app_delivery or pref.email_delivery or pref.push_delivery:
        # Create new Notification
        new_notif = Notification.objects.create(
            shop=shop,
            recipient=recipient,
            actor=actor,
            category=category,
            priority=resolved_priority,
            module=module,
            action=action,
            title=title or '',
            message=message,
            preview=preview or '',
            entity_type=entity_type or '',
            entity_id=str(entity_id or ''),
            deep_link=deep_link or {},
            metadata=metadata_payload
        )

        if pref.in_app_delivery:
            NotificationDeliveryLog.objects.create(
                notification=new_notif,
                channel='in_app',
                status='sent'
            )

        if pref.email_delivery:
            # Simulate email dispatch
            NotificationDeliveryLog.objects.create(
                notification=new_notif,
                channel='email',
                status='sent'
            )

        if pref.push_delivery:
            # Simulate push dispatch
            NotificationDeliveryLog.objects.create(
                notification=new_notif,
                channel='push' if hasattr(NotificationDeliveryLog, 'CHANNEL_CHOICES') and any(c[0] == 'push' for c in NotificationDeliveryLog.CHANNEL_CHOICES) else 'email',
                status='sent'
            )

    # Dispatch outbound webhook integration event
    try:
        from django.utils import timezone
        from core.services.webhook_dispatcher import dispatch_webhook_event
        webhook_payload = {
            'event': category,
            'title': title or '',
            'message': message,
            'entity_type': entity_type or '',
            'entity_id': str(entity_id or ''),
            'recipient': {
                'id': recipient.id,
                'username': recipient.username,
                'email': recipient.email,
            },
            'actor': {
                'id': actor.id,
                'username': actor.username,
                'email': actor.email,
            } if actor else None,
            'metadata': metadata_payload,
            'created_at': timezone.now().isoformat()
        }
        dispatch_webhook_event(shop.id, category, webhook_payload)
    except Exception as e:
        import sys
        print(f"Webhook dispatch failed in push_unified_notification: {e}", file=sys.stderr)

    # 5. Broadcast real-time websocket packet if in-app delivery is enabled
    if not pref.in_app_delivery:
        # If in-app is disabled, don't broadcast to the frontend
        return notification

    payload = {
        'id': new_notif.id if new_notif else notification.id,
        'recipient_id': notification.recipient_id,
        'module': notification.module,
        'action': notification.action,
        'category': category,
        'priority': resolved_priority,
        'title': notification.title,
        'message': notification.message,
        'preview': notification.preview,
        'entity_type': notification.entity_type,
        'entity_id': notification.entity_id,
        'sub_entity_type': notification.sub_entity_type,
        'sub_entity_id': notification.sub_entity_id,
        'deep_link': notification.deep_link,
        'metadata': notification.metadata,
        'sound_category': notification.metadata.get('sound_category', resolved_sound_category),
        'task_priority': notification.metadata.get('task_priority', resolved_task_priority),
        'is_read': new_notif.is_read if new_notif else notification.is_read,
        'created_at': (new_notif.created_at if new_notif else notification.created_at).isoformat(),
    }

    _broadcast_to_user(
        notification.recipient_id,
        'notification.created',
        {
            'notification': payload,
        },
    )

    return new_notif or notification

