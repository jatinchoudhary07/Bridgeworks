from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import LeaveRequest
from presence.models import UserPresence
from django.utils import timezone
from django_q.tasks import schedule
from django_q.models import Schedule
import datetime

@receiver(post_save, sender=LeaveRequest)
def handle_leave_request_save(sender, instance, **kwargs):
    """
    Listens to changes on LeaveRequest. If status changes to 'approved',
    updates/evaluates user presence leave_active, and schedules start/end tasks.
    """
    if instance.status != 'approved':
        try:
            presence, created = UserPresence.objects.get_or_create(user=instance.user)
            today = timezone.localdate()
            other_active_leaves = LeaveRequest.objects.filter(
                user=instance.user,
                status='approved',
                start_date__lte=today,
                end_date__gte=today
            ).exclude(pk=instance.pk)

            if not other_active_leaves.exists():
                presence.leave_active = False
                presence.resolve_status()
                presence.save_and_broadcast(source='leave_cancelled')
        except Exception:
            pass
        return

    today = timezone.localdate()
    presence, created = UserPresence.objects.get_or_create(user=instance.user)

    if instance.start_date <= today <= instance.end_date:
        presence.leave_active = True
        presence.resolve_status()
        presence.save_and_broadcast(source='leave_start_immediate')

    start_dt = datetime.datetime.combine(instance.start_date, datetime.time.min)
    from django.utils.timezone import make_aware
    try:
        start_dt = make_aware(start_dt)
    except Exception:
        pass

    end_dt = datetime.datetime.combine(instance.end_date + datetime.timedelta(days=1), datetime.time.min)
    try:
        end_dt = make_aware(end_dt)
    except Exception:
        pass

    try:
        Schedule.objects.filter(name=f"leave_start_{instance.id}").delete()
        Schedule.objects.filter(name=f"leave_end_{instance.id}").delete()

        if start_dt > timezone.now():
            schedule(
                'presence.tasks.set_leave_active',
                instance.user_id,
                schedule_type=Schedule.ONCE,
                next_run=start_dt,
                name=f"leave_start_{instance.id}"
            )

        schedule(
            'presence.tasks.clear_leave_active',
            instance.user_id,
            schedule_type=Schedule.ONCE,
            next_run=end_dt,
            name=f"leave_end_{instance.id}"
        )
    except Exception:
        pass
