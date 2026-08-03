from datetime import timedelta
from django.utils import timezone
from presence.models import UserPresence

def degrade_inactive_users():
    """
    Finds users who are currently 'online' in activity_status, but whose
    last_seen is older than 2 minutes, and marks them offline.
    """
    cutoff = timezone.now() - timedelta(minutes=2)
    inactive_presences = UserPresence.objects.filter(
        activity_status='online',
        last_seen__lt=cutoff
    )
    for presence in inactive_presences:
        presence.activity_status = 'offline'
        presence.meeting_active = False
        presence.resolve_status()
        presence.save_and_broadcast(source='inactivity_degradation')


def set_leave_active(user_id):
    """
    Sets leave_active = True for the user, re-resolves and broadcasts.
    """
    try:
        presence, created = UserPresence.objects.get_or_create(user_id=user_id)
        presence.leave_active = True
        presence.resolve_status()
        presence.save_and_broadcast(source='leave_task_activation')
    except Exception:
        pass


def clear_leave_active(user_id):
    """
    Sets leave_active = False for the user, re-resolves and broadcasts.
    """
    try:
        presence, created = UserPresence.objects.get_or_create(user_id=user_id)
        presence.leave_active = False
        presence.resolve_status()
        presence.save_and_broadcast(source='leave_task_deactivation')
    except Exception:
        pass
