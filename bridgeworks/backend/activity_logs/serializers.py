import json
from rest_framework import serializers


# ---------------------------------------------------------------------------
# Inbound (batch ingest) serializers
# ---------------------------------------------------------------------------

class BatchEventSerializer(serializers.Serializer):
    """Validates a single event inside the POST /api/logs/batch payload."""

    action = serializers.CharField(max_length=128, trim_whitespace=True)
    component = serializers.CharField(
        max_length=256, required=False, default="", trim_whitespace=True, allow_blank=True
    )
    page = serializers.CharField(
        max_length=512, required=False, default="", trim_whitespace=True, allow_blank=True
    )
    sessionId = serializers.CharField(
        max_length=128, required=False, default="", trim_whitespace=True, allow_blank=True
    )
    metadata = serializers.DictField(required=False, default=dict)
    timestamp = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate_metadata(self, value: dict) -> dict:
        """Guard against oversized payloads (4 KB cap)."""
        if len(json.dumps(value, default=str)) > 4096:
            raise serializers.ValidationError("metadata must not exceed 4 KB.")
        return value


class BatchIngestRequestSerializer(serializers.Serializer):
    """Wraps the list of events with a max-100 guard."""

    events = BatchEventSerializer(many=True)

    def validate_events(self, value: list) -> list:
        if not value:
            raise serializers.ValidationError("events list must not be empty.")
        if len(value) > 100:
            raise serializers.ValidationError("Maximum 100 events per batch.")
        return value


# ---------------------------------------------------------------------------
# Outbound (read) serializers
# ---------------------------------------------------------------------------

class ActivityLogSerializer(serializers.Serializer):
    """Read-only serializer — personal log view (no user field exposed)."""

    id = serializers.IntegerField(read_only=True)
    action = serializers.CharField(read_only=True)
    component = serializers.CharField(read_only=True)
    page = serializers.CharField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    is_sensitive = serializers.BooleanField(read_only=True)
    method = serializers.CharField(read_only=True)
    status_code = serializers.IntegerField(read_only=True, allow_null=True)
    duration_ms = serializers.IntegerField(read_only=True, allow_null=True)
    timestamp = serializers.DateTimeField(read_only=True)


class HRActivityLogSerializer(serializers.Serializer):
    """
    HR view serializer — includes user info.
    Sensitive metadata is replaced with '[REDACTED]' at the view layer.
    """

    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    username = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    action = serializers.CharField(read_only=True)
    component = serializers.CharField(read_only=True)
    page = serializers.CharField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    metadata = serializers.SerializerMethodField()
    is_sensitive = serializers.BooleanField(read_only=True)
    ip_address = serializers.CharField(read_only=True, allow_null=True)
    method = serializers.CharField(read_only=True)
    status_code = serializers.IntegerField(read_only=True, allow_null=True)
    duration_ms = serializers.IntegerField(read_only=True, allow_null=True)
    timestamp = serializers.DateTimeField(read_only=True)

    def get_username(self, obj) -> str:
        return obj.user.username if obj.user_id else ""

    def get_email(self, obj) -> str:
        return obj.user.email if obj.user_id else ""

    def get_metadata(self, obj) -> object:
        if obj.is_sensitive:
            return "[REDACTED]"
        return obj.metadata
