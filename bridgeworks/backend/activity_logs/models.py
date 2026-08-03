from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    """
    Central store for all user activity events — both frontend-submitted
    (via POST /api/logs/batch) and server-side API calls (via middleware).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )

    # ── What happened ──────────────────────────────────────────────────────────
    action = models.CharField(max_length=128)
    component = models.CharField(max_length=256, blank=True, default="")
    page = models.CharField(max_length=512, blank=True, default="")

    # ── Session context ────────────────────────────────────────────────────────
    session_id = models.CharField(max_length=128, blank=True, default="")

    # ── Payload ────────────────────────────────────────────────────────────────
    metadata = models.JSONField(default=dict, blank=True)
    is_sensitive = models.BooleanField(default=False)

    # ── Request context (populated by middleware for server-side events) ───────
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    status_code = models.SmallIntegerField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "activity_logs"
        ordering = ["-timestamp"]
        indexes = [
            # (user_id, timestamp) — user's own log queries filtered by date range
            models.Index(fields=["user", "timestamp"], name="actlog_user_ts_idx"),
            # (action, timestamp)  — analytics queries grouped by action type
            models.Index(fields=["action", "timestamp"], name="actlog_action_ts_idx"),
            # session_id           — session replay / grouping queries
            models.Index(fields=["session_id"], name="actlog_session_idx"),
        ]

    def __str__(self) -> str:
        user_str = self.user_id or "anon"
        return f"[{self.action}] user={user_str} @ {self.timestamp}"
