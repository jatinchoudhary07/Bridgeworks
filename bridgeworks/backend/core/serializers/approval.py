from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models.approval import ApprovalPolicy, ApprovalStep, ApprovalRequest, ApprovalHistory
from core.serializers.crm import UserMinimalSerializer

User = get_user_model()

class ApprovalStepSerializer(serializers.ModelSerializer):
    approvers_details = UserMinimalSerializer(source='approvers', many=True, read_only=True)
    escalate_to_details = UserMinimalSerializer(source='escalate_to', read_only=True)
    approver_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True, many=True, source='approvers'
    )
    escalate_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True, required=False, allow_null=True, source='escalate_to'
    )

    class Meta:
        model = ApprovalStep
        fields = [
            'id', 'sequence', 'approvers_details', 'approver_ids', 
            'min_approvals_required', 'sla_hours', 'escalate_to_details', 'escalate_to_id'
        ]


class ApprovalPolicySerializer(serializers.ModelSerializer):
    steps = ApprovalStepSerializer(many=True, required=False, default=[])

    class Meta:
        model = ApprovalPolicy
        fields = [
            'id', 'shop', 'name', 'description', 'entity_type', 
            'trigger_conditions', 'is_active', 'steps', 'created_at', 'updated_at'
        ]
        read_only_fields = ['shop', 'created_at', 'updated_at']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        policy = ApprovalPolicy.objects.create(**validated_data)
        for step in steps_data:
            approvers = step.pop('approvers', [])
            step_instance = ApprovalStep.objects.create(policy=policy, **step)
            step_instance.approvers.set(approvers)
        return policy

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.entity_type = validated_data.get('entity_type', instance.entity_type)
        instance.trigger_conditions = validated_data.get('trigger_conditions', instance.trigger_conditions)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()

        if steps_data is not None:
            instance.steps.all().delete()
            for step in steps_data:
                approvers = step.pop('approvers', [])
                step_instance = ApprovalStep.objects.create(policy=instance, **step)
                step_instance.approvers.set(approvers)
        return instance


class ApprovalHistorySerializer(serializers.ModelSerializer):
    approver_details = UserMinimalSerializer(source='approver', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = ApprovalHistory
        fields = [
            'id', 'request', 'step', 'sequence', 'action', 
            'action_display', 'approver', 'approver_details', 'comments', 'created_at'
        ]


class ApprovalRequestSerializer(serializers.ModelSerializer):
    history = ApprovalHistorySerializer(many=True, read_only=True)
    policy_name = serializers.CharField(source='policy.name', read_only=True)
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'shop', 'policy', 'policy_name', 'entity_type', 'entity_id', 
            'status', 'status_display', 'current_step_sequence', 'created_by', 
            'created_by_details', 'history', 'created_at', 'updated_at'
        ]
        read_only_fields = ['shop', 'created_by', 'created_at', 'updated_at']
