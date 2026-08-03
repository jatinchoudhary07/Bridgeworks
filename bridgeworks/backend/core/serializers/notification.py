from rest_framework import serializers
from core.models.notification import Notification, NotificationPreference, NotificationDeliveryLog
from core.serializers.crm import UserMinimalSerializer

class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'shop', 'recipient', 'actor', 'actor_name', 'category', 
            'category_display', 'priority', 'module', 'action', 'title', 'message', 
            'preview', 'entity_type', 'entity_id', 'deep_link', 'metadata', 
            'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['shop', 'created_at']

    def get_actor_name(self, obj):
        if not obj.actor:
            return 'System'
        return obj.actor.first_name or obj.actor.username


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = NotificationPreference
        fields = ['id', 'user', 'category', 'category_display', 'email_delivery', 'in_app_delivery', 'push_delivery']
        read_only_fields = ['user']


class NotificationDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDeliveryLog
        fields = ['id', 'notification', 'channel', 'status', 'error_message', 'sent_at']
