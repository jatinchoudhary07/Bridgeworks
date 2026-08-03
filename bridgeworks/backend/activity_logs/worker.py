"""
Activity log async worker.

Primary path  → django-q2  (already configured in Q_CLUSTER, uses Redis or ORM broker).
Fallback path → daemon thread with an in-memory queue when the qcluster worker is
                not running (e.g. local dev without `python manage.py qcluster`).

The bulk_insert_logs() function is importable as a django-q2 task:
    async_task('activity_logs.worker.bulk_insert_logs', events_data)
"""

from __future__ import annotations

import logging
import queue as stdlib_queue
import threading
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

# ── In-memory fallback ────────────────────────────────────────────────────────
_fallback_queue: stdlib_queue.Queue[list[dict]] = stdlib_queue.Queue()
_fallback_lock = threading.Lock()
_fallback_started = False


def _ensure_fallback_worker() -> None:
    global _fallback_started
    with _fallback_lock:
        if not _fallback_started:
            _fallback_started = True
            t = threading.Thread(target=_fallback_loop, daemon=True, name="actlog-fallback")
            t.start()
            logger.info("Activity log fallback worker thread started.")


def _fallback_loop() -> None:
    """Drain the in-memory queue; runs forever in a daemon thread."""
    while True:
        try:
            events_data = _fallback_queue.get(timeout=5)
            bulk_insert_logs(events_data)
        except stdlib_queue.Empty:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.error("Activity log fallback worker error: %s", exc)


# ── Public API ────────────────────────────────────────────────────────────────

def enqueue_logs(events_data: list[dict[str, Any]]) -> None:
    """
    Push a list of serialised event dicts to the async worker.

    Strategy: always use the in-memory daemon thread queue so logs are written
    immediately without requiring `python manage.py qcluster` to be running.

    django-q2's async_task silently parks tasks in the ORM/Redis broker without
    executing them until a qcluster process is running — meaning logs would never
    appear if qcluster is stopped.  The in-memory daemon thread is simpler,
    always-on, and perfectly suitable for a logging workload.
    """
    if not events_data:
        return

    _fallback_queue.put(events_data)
    _ensure_fallback_worker()


# ── django-q2 task (also called directly by fallback worker) ─────────────────

def bulk_insert_logs(events_data: list[dict[str, Any]]) -> None:
    """
    Bulk-insert ActivityLog rows.

    Called by:
    - django-q2 worker process (primary)
    - _fallback_loop daemon thread (dev / no qcluster)

    Never raises — all errors are logged and swallowed so callers stay alive.
    """
    from .models import ActivityLog  # deferred import; safe in task context

    objs: list[ActivityLog] = []

    for e in events_data:
        try:
            ts = e.get("timestamp")
            if ts and isinstance(ts, str):
                ts = parse_datetime(ts)
            if not ts:
                ts = timezone.now()

            objs.append(
                ActivityLog(
                    user_id=e.get("user_id"),
                    action=(e.get("action") or "UNKNOWN")[:128],
                    component=(e.get("component") or "")[:256],
                    page=(e.get("page") or "")[:512],
                    session_id=(e.get("session_id") or "")[:128],
                    metadata=e.get("metadata") or {},
                    is_sensitive=bool(e.get("is_sensitive", False)),
                    ip_address=e.get("ip_address") or None,
                    user_agent=(e.get("user_agent") or "")[:2048],
                    method=(e.get("method") or "")[:10],
                    status_code=e.get("status_code"),
                    duration_ms=e.get("duration_ms"),
                    timestamp=ts,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Activity log: failed to build ActivityLog object: %s | event=%s", exc, e)

    if not objs:
        return

    try:
        ActivityLog.objects.bulk_create(objs, ignore_conflicts=True)
        logger.debug("Activity logs: bulk inserted %d records.", len(objs))
    except Exception as exc:  # noqa: BLE001
        logger.error("Activity log bulk_create failed (%s). Dropping %d records.", exc, len(objs))
