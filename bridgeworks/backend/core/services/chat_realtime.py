from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.cloudinary_utils import build_file_access_url

def _serialize_message(message):
    import html
    recipients = list(message.recipient_entries.select_related('recipient').all())
    recipient_ids = [entry.recipient_id for entry in recipients]
    recipient_usernames = [entry.recipient.username for entry in recipients if entry.recipient]
    reaction_rows = list(message.reactions.select_related('user').all())
    reactions = {}
    for row in reaction_rows:
        item = reactions.setdefault(row.reaction, {'reaction': row.reaction, 'count': 0, 'user_ids': []})
        item['count'] += 1
        item['user_ids'].append(row.user_id)

    if len(recipient_usernames) > 3:
        to_label = 'Team'
    elif recipient_usernames:
        to_label = ', '.join(f'@{name}' for name in recipient_usernames)
    else:
        to_label = 'Team'

    sender_name = message.sender.get_full_name().strip() or message.sender.username
    task_assignee_name = ''
    if message.task_assignee:
        task_assignee_name = message.task_assignee.get_full_name().strip() or message.task_assignee.username

    return {
        'id': message.id,
        'sender_id': message.sender_id,
        'sender_name': sender_name,
        'content': html.unescape(message.content or ''),
        'meet_link': message.meet_link,
        'event_title': html.unescape(message.event_title or ''),
        'event_tagged_names': html.unescape(message.event_tagged_names or ''),
        'is_event': message.is_event,
        'is_broadcast': message.is_broadcast,
        'room_id': str(message.room.room_id) if message.room_id else '',
        'room_name': message.room.name if message.room_id and message.room else '',
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'is_deleted': message.is_deleted,
        'is_task': message.is_task,
        'task_title': html.unescape(message.task_title or ''),
        'task_description': html.unescape(message.task_description or ''),
        'task_due_date': message.task_due_date.isoformat() if message.task_due_date else None,
        'task_priority': message.task_priority,
        'task_status': message.task_status,
        'task_source_message_id': message.task_source_message_id,
        'task_assignee_id': message.task_assignee_id,
        'task_assignee_name': task_assignee_name,
        'attachment_url': build_file_access_url(None, message.attachment) if message.attachment else '',
        'attachment_name': message.attachment_name,
        'attachment_mime_type': message.attachment_mime_type,
        'attachment_kind': message.attachment_kind,
        'created_at': message.created_at.isoformat() if message.created_at else None,
        'is_archived': False,
        'is_read': False,
        'to_label': to_label,
        'recipient_user_ids': recipient_ids,
        'delivery_status': 'delivered',
        'reactions': list(reactions.values()),
        'is_pinned': message.pin_entries.exists(),
        'channel_id': message.channel_id,
        'parent_message_id': message.parent_message_id,
        'thread_reply_count': message.thread_reply_count,
        'last_reply_at': message.last_reply_at.isoformat() if message.last_reply_at else None,
        'last_reply_by': message.last_reply_by_id,
    }


def _send_group_event(org_id, event_type, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RuntimeError('Channel layer is not configured')

    async_to_sync(channel_layer.group_send)(
        f'chat_org_{org_id}',
        {
            'type': event_type,
            **payload,
        }
    )


def broadcast_new_message(org_id, message, queue_delay_ms=0.0):
    _send_group_event(
        org_id,
        'chat.message',
        {
            'message': _serialize_message(message),
            'queue_delay_ms': float(queue_delay_ms or 0.0),
        },
    )


def broadcast_task_update(org_id, message):
    _send_group_event(
        org_id,
        'chat.task_update',
        {
            'task': {
                'id': message.id,
                'task_status': message.task_status,
            }
        },
    )


def broadcast_presence_update(org_id, user_id: int, is_online: bool):
    """
    Push a real-time presence change to every connected member of the org.
    Called from ChatPresenceHeartbeatView after stamping last_seen.
    Payload: { type: "presence.update", user_id: N, is_online: true/false }
    """
    try:
        _send_group_event(
            org_id,
            'presence.update',
            {
                'user_id': user_id,
                'is_online': is_online,
            },
        )
    except Exception:
        pass  # Never let a broadcast failure break the heartbeat response
