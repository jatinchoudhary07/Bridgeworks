from rest_framework import serializers
from presence.models import UserPresence

class UserPresenceSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:  # type: ignore
        model = UserPresence
        fields = (
            'user_id', 'username', 'email', 'resolved_status',
            'leave_active', 'meeting_active', 'manual_status',
            'activity_status', 'last_seen', 'updated_at'
        )
