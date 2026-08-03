"""
Activity Logs API Views
=======================

POST /api/logs/batch       — frontend batch ingest (202, async)
GET  /api/logs/me          — personal log history (authenticated)
GET  /api/logs/hr/logs     — all-user log viewer  (HR role)
GET  /api/logs/hr/export   — CSV stream export    (HR role)
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

from django.http import StreamingHttpResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.utils.timezone import make_aware, is_naive
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardResultsSetPagination

from .models import ActivityLog
from .permissions import IsHRManager
from .serializers import (
    ActivityLogSerializer,
    BatchIngestRequestSerializer,
    HRActivityLogSerializer,
)
from .worker import enqueue_logs

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parse_datetime(value)
        if dt is None:
            return None
        # Make timezone-aware if naive (frontend sends bare ISO strings like 2026-05-08T00:00:00)
        if is_naive(dt):
            dt = make_aware(dt)
        return dt
    except (ValueError, TypeError):
        return None


def _apply_common_filters(qs, request):
    """Apply ?from=&to=&action=&source= filters shared between /me and /hr/logs.

    ?source=frontend  → only rows with method='FRONTEND' (user-triggered events)
    ?source=server    → only rows captured by the middleware (API calls)
    (omitted)         → all rows
    """
    from_dt = _parse_dt(request.query_params.get("from"))
    to_dt = _parse_dt(request.query_params.get("to"))
    action = request.query_params.get("action", "").strip()
    source = request.query_params.get("source", "").strip().lower()

    if from_dt:
        qs = qs.filter(timestamp__gte=from_dt)
    if to_dt:
        qs = qs.filter(timestamp__lte=to_dt)
    if action:
        qs = qs.filter(action__iexact=action)
    if source == "frontend":
        qs = qs.filter(method="FRONTEND")
    elif source == "server":
        qs = qs.exclude(method="FRONTEND")
    return qs


# ── POST /api/logs/batch ──────────────────────────────────────────────────────

class BatchIngestView(APIView):
    """
    Accepts up to 100 frontend events and pushes them to the async worker.
    Returns 202 immediately — never blocks on a DB write.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BatchIngestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        events = serializer.validated_data["events"]
        user_id = request.user.pk
        ip = _get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")[:2048]

        # Enrich each event with server-side context
        enriched = []
        for e in events:
            enriched.append(
                {
                    "user_id": user_id,
                    "action": e["action"],
                    "component": e.get("component", ""),
                    "page": e.get("page", ""),
                    "session_id": e.get("sessionId", ""),
                    "metadata": e.get("metadata", {}),
                    "is_sensitive": False,
                    "ip_address": ip,
                    "user_agent": ua,
                    "method": "FRONTEND",
                    "status_code": None,
                    "duration_ms": None,
                    "timestamp": (
                        e["timestamp"].isoformat()
                        if e.get("timestamp")
                        else timezone.now().isoformat()
                    ),
                }
            )

        enqueue_logs(enriched)
        return Response({"accepted": len(enriched)}, status=status.HTTP_202_ACCEPTED)


def _get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


# ── GET /api/logs/me ──────────────────────────────────────────────────────────

class MyLogsView(APIView):
    """
    Returns the authenticated user's own activity logs — never exposes other
    users' data regardless of query params.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            ActivityLog.objects.filter(user=request.user)
            .order_by("-timestamp")
        )
        qs = _apply_common_filters(qs, request)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = ActivityLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ── GET /api/logs/hr/logs ─────────────────────────────────────────────────────

class HRLogsView(APIView):
    """
    HR-only view: all users' logs with filtering, search, and sensitive
    metadata masking.
    """

    permission_classes = [IsAuthenticated, IsHRManager]

    def get(self, request):
        qs = (
            ActivityLog.objects.select_related("user")
            .order_by("-timestamp")
        )

        # ── Filters ───────────────────────────────────────────────────────────
        qs = _apply_common_filters(qs, request)

        user_id = request.query_params.get("userId", "").strip()
        component = request.query_params.get("component", "").strip()
        search = request.query_params.get("search", "").strip()

        if user_id:
            qs = qs.filter(user_id=user_id)
        if component:
            qs = qs.filter(component__icontains=component)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(action__icontains=search)
                | Q(component__icontains=search)
                | Q(page__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
            )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = HRActivityLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ── GET /api/logs/hr/export ───────────────────────────────────────────────────

class _CsvEcho:
    """Pseudo-file that returns the written value for StreamingHttpResponse."""

    def write(self, value: str) -> str:
        return value


def _stream_csv(queryset):
    """
    Generator that yields CSV rows one at a time.
    Uses queryset.iterator() so the full table is never loaded into RAM.
    """
    writer = csv.writer(_CsvEcho())

    # Header
    yield writer.writerow(
        [
            "id",
            "user_id",
            "username",
            "email",
            "action",
            "component",
            "page",
            "session_id",
            "metadata",
            "is_sensitive",
            "ip_address",
            "method",
            "status_code",
            "duration_ms",
            "timestamp",
        ]
    )

    for log in queryset.select_related("user").iterator(chunk_size=500):
        metadata_value = "[REDACTED]" if log.is_sensitive else str(log.metadata)
        yield writer.writerow(
            [
                log.id,
                log.user_id or "",
                log.user.username if log.user_id else "",
                log.user.email if log.user_id else "",
                log.action,
                log.component,
                log.page,
                log.session_id,
                metadata_value,
                log.is_sensitive,
                log.ip_address or "",
                log.method,
                log.status_code or "",
                log.duration_ms or "",
                log.timestamp.isoformat() if log.timestamp else "",
            ]
        )


class HRExportView(APIView):
    """
    Streams the full filtered log set as a CSV download.
    No in-memory buffering — safe for millions of rows.
    """

    permission_classes = [IsAuthenticated, IsHRManager]

    def get(self, request):
        qs = ActivityLog.objects.order_by("-timestamp")
        qs = _apply_common_filters(qs, request)

        user_id = request.query_params.get("userId", "").strip()
        component = request.query_params.get("component", "").strip()
        search = request.query_params.get("search", "").strip()

        if user_id:
            qs = qs.filter(user_id=user_id)
        if component:
            qs = qs.filter(component__icontains=component)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(action__icontains=search)
                | Q(component__icontains=search)
                | Q(page__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
            )

        filename = f"activity_logs_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = StreamingHttpResponse(
            _stream_csv(qs),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
