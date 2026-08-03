"""
ActivityLoggerMiddleware — auto-captures every server-side API request.

Skipped routes:
  - /api/logs/*   (avoids infinite logging loop)
  - /health
  - /ping
  - /metrics      (Prometheus scrape endpoint)
  - Static / media files

Registration (add ONE line to MIDDLEWARE in settings.py):
    'activity_logs.middleware.ActivityLoggerMiddleware',
"""

from __future__ import annotations

import time
import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = (
    "/api/logs/",
    "/health",
    "/ping",
    "/metrics",
    "/static/",
    "/media/",
    "/favicon",
)


def _get_client_ip(request: HttpRequest) -> str | None:
    """Extract real client IP, respecting standard proxy headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first (leftmost) address; the rest are proxies
        ip = x_forwarded_for.split(",")[0].strip()
        return ip or None
    return request.META.get("REMOTE_ADDR") or None


class ActivityLoggerMiddleware:
    """
    WSGI/ASGI-compatible middleware that logs every non-skipped HTTP request
    as an ActivityLog event with action="API_CALL".

    Install:
        MIDDLEWARE = [
            ...
            'activity_logs.middleware.ActivityLoggerMiddleware',
        ]
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path: str = request.path

        # ── Fast-path skip ───────────────────────────────────────────────────
        if any(path.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return self.get_response(request)

        # ── Time the request ─────────────────────────────────────────────────
        start = time.monotonic()
        response: HttpResponse = self.get_response(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # ── Build event dict (never block on DB) ─────────────────────────────
        try:
            user = getattr(request, "user", None)
            user_id = user.pk if (user and user.is_authenticated) else None

            event = {
                "user_id": user_id,
                "action": "API_CALL",
                "component": path,
                "page": path,
                "session_id": "",
                "metadata": {
                    "method": request.method,
                    "status_code": response.status_code,
                    "query_string": request.META.get("QUERY_STRING", "")[:512],
                },
                "is_sensitive": False,
                "ip_address": _get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:2048],
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "timestamp": timezone.now().isoformat(),
            }

            from activity_logs.worker import enqueue_logs

            enqueue_logs([event])

        except Exception as exc:  # noqa: BLE001
            # Never let logging break the actual response
            logger.error("ActivityLoggerMiddleware: failed to enqueue log: %s", exc)

        return response
