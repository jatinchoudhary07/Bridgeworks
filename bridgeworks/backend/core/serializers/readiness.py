from rest_framework import serializers
from core.models.readiness import SystemAuditLog, SavedFilter

class SystemAuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SystemAuditLog
        fields = ['id', 'shop', 'user', 'username', 'action', 'model_name', 'object_id', 'changed_fields', 'ip_address', 'created_at']
        read_only_fields = ['shop', 'created_at']


class SavedFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedFilter
        fields = ['id', 'shop', 'user', 'module_name', 'name', 'query_params', 'created_at']
        read_only_fields = ['shop', 'user', 'created_at']
