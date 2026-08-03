"""
Midnight auto-logout cron task.

Runs every 15 minutes via Django-Q scheduler. For each firm whose local time
has just crossed midnight, it expires all active attendance sessions and
writes a logout timestamp.

Why every 15 minutes?
  Different firms have different timezones (IST, PST, GST, etc.). Running
  every 15 minutes lets us check which firms just crossed midnight in *their*
  timezone and process only those. This is the standard approach for
  multi-timezone cron jobs.
"""

import logging
from datetime import time

import pytz
from django.utils import timezone

logger = logging.getLogger(__name__)


def midnight_logout_job():
    """
    For each org whose local time is 00:00–00:14, expire all active sessions
    and write logout_timestamp to attendance records.
    """
    from core.models import ShopCredentials, AttendanceSession, AttendanceEntry

    now_utc = timezone.now()
    processed_orgs = 0
    expired_sessions = 0

    for org in ShopCredentials.objects.all():
        tz_name = org.timezone or 'Asia/Kolkata'
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            logger.warning(
                '[midnight_logout] Unknown timezone "%s" for org %s, skipping.',
                tz_name, org.organization_id,
            )
            continue

        local_now = now_utc.astimezone(tz)

        # Only act if we're within the first 15-minute window past midnight
        if local_now.hour != 0 or local_now.minute >= 15:
            continue

        org_id = org.organization_id
        active_sessions = AttendanceSession.objects.filter(
            org_id=org_id,
            logout_at__isnull=True,
        )

        count = active_sessions.count()
        if count == 0:
            continue

        # Compute midnight in the firm's timezone, then convert to UTC
        midnight_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_utc = midnight_local.astimezone(pytz.utc)

        for session in active_sessions:
            session.logout_at = midnight_utc
            session.logout_source = 'midnight_job'
            session.save(update_fields=['logout_at', 'logout_source'])

            # Update corresponding AttendanceEntry's out_time
            try:
                login_date = session.login_at.astimezone(tz).date()
                entry = AttendanceEntry.objects.filter(
                    org_id=org_id,
                    user=session.user,
                    entry_date=login_date,
                    is_active=True,
                ).order_by('-updated_at').first()

                if entry:
                    from core.views_mydesk import _effective_rulebook
                    rb = _effective_rulebook(session.user)
                    out_time_to_write = rb.shift_end

                    if session.last_activity_at:
                        try:
                            local_last_act = session.last_activity_at.astimezone(tz)
                            out_time_to_write = local_last_act.time()
                        except Exception:
                            pass

                    entry.out_time = out_time_to_write
                    from core.views_mydesk import _auto_compute_status, _calculate_net_worked_hours
                    net_hours = _calculate_net_worked_hours(session.user, login_date)
                    final_status, total_deduction, late_minutes, early_leave, hours_worked, score = _auto_compute_status(
                        in_time=entry.in_time,
                        out_time=entry.out_time,
                        rulebook=rb,
                        hours_worked=net_hours
                    )

                    # Preserve WFH status mapping if final calculated status is 'present'
                    if final_status == 'present' and (entry.status == 'wfh' or entry.work_mode == 'wfh'):
                        final_status = 'wfh'

                    entry.auto_status = final_status
                    if not entry.hr_override_status:
                        entry.status = final_status
                        entry.salary_deduction_days = total_deduction
                        entry.attendance_score_points = score
                    else:
                        entry.status = entry.hr_override_status
                        if entry.status == 'absent':
                            entry.attendance_score_points = 0
                            entry.salary_deduction_days = 1.0
                        elif entry.status == 'half_day':
                            entry.attendance_score_points = 50
                            entry.salary_deduction_days = 0.5
                        elif entry.status == 'leave':
                            entry.attendance_score_points = 0
                            entry.salary_deduction_days = 1.0
                        elif entry.status in ('present', 'wfh', 'on_duty'):
                            entry.attendance_score_points = 100
                            entry.salary_deduction_days = 0.0

                    entry.late_minutes = late_minutes
                    entry.early_leave_minutes = early_leave
                    entry.hours_worked = hours_worked
                    entry.save(update_fields=[
                        'status', 'auto_status', 'out_time', 'late_minutes',
                        'early_leave_minutes', 'hours_worked', 'salary_deduction_days',
                        'attendance_score_points', 'updated_at'
                    ])
            except Exception as exc:
                logger.error(
                    '[midnight_logout] Failed to update entry for session %s: %s',
                    session.id, exc,
                )

        expired_sessions += count
        processed_orgs += 1
        logger.info(
            '[midnight_logout] org=%s tz=%s — expired %d sessions.',
            org_id, tz_name, count,
        )

    if processed_orgs > 0:
        logger.info(
            '[midnight_logout] Done. Processed %d orgs, expired %d sessions.',
            processed_orgs, expired_sessions,
        )


def close_idle_sessions_job():
    """
    Identifies active sessions that have had no heartbeat activity for longer than
    their office geofence idle timeout configuration (or a default of 30 minutes),
    and closes them cleanly as 'idle' at their last recorded activity time.
    """
    from datetime import timedelta, datetime
    from core.models import AttendanceSession, ShopCredentials, AttendanceEntry
    import pytz

    active_sessions = AttendanceSession.objects.filter(logout_at__isnull=True)
    closed_count = 0

    for session in active_sessions:
        # 1. Determine timezone
        org = ShopCredentials.objects.filter(organization_id=session.org_id).first()
        tz_name = getattr(org, 'timezone', None) or 'Asia/Kolkata'
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone('Asia/Kolkata')

        # 2. Determine idle timeout threshold
        timeout_mins = 30
        if session.gps_nearest_office and session.gps_nearest_office.idle_timeout_enabled:
            timeout_mins = session.gps_nearest_office.idle_timeout_minutes or 30

        last_activity = session.last_activity_at or session.login_at
        now = timezone.now()

        if now - last_activity > timedelta(minutes=timeout_mins):
            # Session is idle, expire it
            session.logout_at = last_activity
            session.logout_source = 'idle'
            session.save(update_fields=['logout_at', 'logout_source'])

            # Update corresponding AttendanceEntry's out_time
            try:
                login_date = session.login_at.astimezone(tz).date()
                entry = AttendanceEntry.objects.filter(
                    org_id=session.org_id,
                    user=session.user,
                    entry_date=login_date,
                    is_active=True,
                ).order_by('-updated_at').first()

                if entry:
                    from core.views_mydesk import _effective_rulebook, _auto_compute_status, _calculate_net_worked_hours
                    rb = _effective_rulebook(session.user)
                    local_last_act = last_activity.astimezone(tz)
                    entry.out_time = local_last_act.time()
                    net_hours = _calculate_net_worked_hours(session.user, login_date)

                    final_status, total_deduction, late_minutes, early_leave, hours_worked, score = _auto_compute_status(
                        in_time=entry.in_time,
                        out_time=entry.out_time,
                        rulebook=rb,
                        hours_worked=net_hours
                    )

                    # Preserve WFH status mapping if final calculated status is 'present'
                    if final_status == 'present' and (entry.status == 'wfh' or entry.work_mode == 'wfh'):
                        final_status = 'wfh'

                    entry.auto_status = final_status
                    if not entry.hr_override_status:
                        entry.status = final_status
                        entry.salary_deduction_days = total_deduction
                        entry.attendance_score_points = score
                    else:
                        entry.status = entry.hr_override_status
                        if entry.status == 'absent':
                            entry.attendance_score_points = 0
                            entry.salary_deduction_days = 1.0
                        elif entry.status == 'half_day':
                            entry.attendance_score_points = 50
                            entry.salary_deduction_days = 0.5
                        elif entry.status == 'leave':
                            entry.attendance_score_points = 0
                            entry.salary_deduction_days = 1.0
                        elif entry.status in ('present', 'wfh', 'on_duty'):
                            entry.attendance_score_points = 100
                            entry.salary_deduction_days = 0.0

                    entry.late_minutes = late_minutes
                    entry.early_leave_minutes = early_leave
                    entry.hours_worked = hours_worked
                    entry.save(update_fields=[
                        'status', 'auto_status', 'out_time', 'late_minutes',
                        'early_leave_minutes', 'hours_worked', 'salary_deduction_days',
                        'attendance_score_points', 'updated_at'
                    ])
            except Exception as exc:
                logger.error(
                    '[close_idle_sessions] Failed to update entry for session %s: %s',
                    session.id, exc,
                )

            closed_count += 1

    if closed_count > 0:
        logger.info('[close_idle_sessions] Done. Expired %d idle sessions.', closed_count)
