import time

from core.models import ChatMessage
from core.services.chat_realtime import broadcast_new_message, broadcast_task_update


class _SyncTask:
    def __init__(self, fn):
        self._fn = fn

    def delay(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


def _run_broadcast_new_message(org_id, message_id, response_ready_epoch_ms=None):
    message = ChatMessage.objects.prefetch_related('recipient_entries__recipient').select_related('sender', 'task_assignee').filter(id=message_id).first()
    if not message:
        return False

    queue_delay_ms = 0.0
    if response_ready_epoch_ms:
        try:
            queue_delay_ms = max(0.0, (time.time() * 1000.0) - float(response_ready_epoch_ms))
        except (TypeError, ValueError):
            queue_delay_ms = 0.0

    broadcast_new_message(org_id, message, queue_delay_ms=queue_delay_ms)
    return True


def _run_broadcast_task_update(org_id, message_id):
    message = ChatMessage.objects.filter(id=message_id).first()
    if not message:
        return False
    broadcast_task_update(org_id, message)
    return True


broadcast_new_message_task = _SyncTask(_run_broadcast_new_message)
broadcast_task_update_task = _SyncTask(_run_broadcast_task_update)
