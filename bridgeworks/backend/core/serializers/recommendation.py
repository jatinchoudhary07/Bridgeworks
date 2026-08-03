from rest_framework import serializers
from core.models.recommendation import Recommendation

class RecommendationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            'id', 'shop', 'type', 'type_display', 'severity', 'severity_display',
            'title', 'description', 'entity_type', 'entity_id', 
            'score', 'status', 'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['shop', 'created_at', 'updated_at']
