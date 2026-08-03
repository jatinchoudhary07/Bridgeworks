from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models.workflow import Workflow, WorkflowTrigger, WorkflowCondition, WorkflowAction, WorkflowExecution
from core.serializers.crm import UserMinimalSerializer

User = get_user_model()

class WorkflowTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTrigger
        fields = ['entity_type', 'trigger_type']


class WorkflowConditionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = WorkflowCondition
        fields = ['id', 'field_name', 'operator', 'value']


class WorkflowActionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = WorkflowAction
        fields = ['id', 'action_type', 'configuration']


class WorkflowSerializer(serializers.ModelSerializer):
    trigger = WorkflowTriggerSerializer()
    conditions = WorkflowConditionSerializer(many=True, required=False, default=[])
    actions = WorkflowActionSerializer(many=True, required=False, default=[])
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = Workflow
        fields = [
            'id', 'name', 'description', 'is_active', 
            'trigger', 'conditions', 'actions', 
            'created_by_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        trigger_data = validated_data.pop('trigger')
        conditions_data = validated_data.pop('conditions', [])
        actions_data = validated_data.pop('actions', [])
        
        workflow = Workflow.objects.create(**validated_data)
        
        WorkflowTrigger.objects.create(workflow=workflow, **trigger_data)
        
        for cond in conditions_data:
            WorkflowCondition.objects.create(workflow=workflow, **cond)
            
        for act in actions_data:
            WorkflowAction.objects.create(workflow=workflow, **act)
            
        return workflow

    def update(self, instance, validated_data):
        trigger_data = validated_data.pop('trigger', None)
        conditions_data = validated_data.pop('conditions', None)
        actions_data = validated_data.pop('actions', None)
        
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        
        if trigger_data:
            trigger_instance = getattr(instance, 'trigger', None)
            if trigger_instance:
                trigger_instance.entity_type = trigger_data.get('entity_type', trigger_instance.entity_type)
                trigger_instance.trigger_type = trigger_data.get('trigger_type', trigger_instance.trigger_type)
                trigger_instance.save()
            else:
                WorkflowTrigger.objects.create(workflow=instance, **trigger_data)
                
        if conditions_data is not None:
            # Recreate conditions (simpler/safer than partial updates on sets)
            instance.conditions.all().delete()
            for cond in conditions_data:
                # Remove ID if passed to avoid key conflicts during insert
                cond.pop('id', None)
                WorkflowCondition.objects.create(workflow=instance, **cond)
                
        if actions_data is not None:
            instance.actions.all().delete()
            for act in actions_data:
                # Remove ID if passed
                act.pop('id', None)
                WorkflowAction.objects.create(workflow=instance, **act)
                
        return instance


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = [
            'id', 'workflow', 'workflow_name', 'entity_type', 
            'entity_id', 'status', 'logs', 'started_at', 'completed_at'
        ]
