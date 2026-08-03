from rest_framework import serializers
from core.models.customer_success import CustomerHealthScore, RenewalTracker, SuccessTask

class CustomerHealthScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerHealthScore
        fields = ['id', 'shop', 'content_type', 'object_id', 'health_score', 'engagement_score', 'support_ticket_count', 'churn_risk', 'metrics', 'last_calculated']
        read_only_fields = ['shop', 'last_calculated']


class RenewalTrackerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenewalTracker
        fields = ['id', 'shop', 'content_type', 'object_id', 'contract_start_date', 'contract_end_date', 'annual_recurring_revenue', 'monthly_recurring_revenue', 'upsell_opportunity_value', 'status', 'renewal_notes', 'updated_at']
        read_only_fields = ['shop', 'updated_at']


class SuccessTaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.username', read_only=True)

    class Meta:
        model = SuccessTask
        fields = ['id', 'shop', 'content_type', 'object_id', 'title', 'description', 'task_type', 'status', 'due_date', 'assignee', 'assignee_name', 'completed_at', 'created_at', 'updated_at']
        read_only_fields = ['shop', 'created_at', 'updated_at']
