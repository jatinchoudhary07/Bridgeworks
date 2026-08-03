from rest_framework import serializers
from core.models.forecasting import SalesQuota
from core.serializers.crm import UserMinimalSerializer

class SalesQuotaSerializer(serializers.ModelSerializer):
    user_details = UserMinimalSerializer(source='user', read_only=True)

    class Meta:
        model = SalesQuota
        fields = ['id', 'shop', 'user', 'user_details', 'target_amount', 'year', 'month', 'created_at', 'updated_at']
        read_only_fields = ['shop', 'created_at', 'updated_at']
