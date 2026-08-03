from rest_framework import serializers
from core.models import WorkforceDepartment, WorkforceMember


class WorkforceDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkforceDepartment
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class WorkforceMemberSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = WorkforceMember
        fields = [
            'id',
            'full_name',
            'department',
            'department_name',
            'category',
            'role_designation',
            'working_style',
            'status',
            'gender',
            'phone',
            'email',
            'current_location',
            'notes',
            'extra_data',
            'is_archived',
            'date_of_joining',
            'date_of_leaving',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'department_name']
