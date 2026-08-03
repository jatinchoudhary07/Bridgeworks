from rest_framework import serializers
from core.models.revenue_intelligence import DealRisk

class DealRiskSerializer(serializers.ModelSerializer):
    entity_type_display = serializers.CharField(source='get_entity_type_display', read_only=True)

    class Meta:
        model = DealRisk
        fields = ['id', 'shop', 'entity_type', 'entity_type_display', 'entity_id', 'risk_score', 'risk_factors', 'last_calculated']
        read_only_fields = ['shop', 'last_calculated']
