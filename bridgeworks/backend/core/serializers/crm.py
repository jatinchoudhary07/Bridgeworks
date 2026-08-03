import os
from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models.crm import CRMActivity, CRMTask, CRMNote, CRMAttachment

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']

    def get_full_name(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username


class CRMActivitySerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = CRMActivity
        fields = [
            'id', 'content_type', 'object_id', 'content_type_name',
            'activity_type', 'description', 'created_by', 'created_by_details', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']


class CRMTaskSerializer(serializers.ModelSerializer):
    assignee_details = UserMinimalSerializer(source='assignee', read_only=True)
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = CRMTask
        fields = [
            'id', 'content_type', 'object_id', 'content_type_name',
            'title', 'description', 'due_date', 'priority', 'status',
            'assignee', 'assignee_details', 'created_by', 'created_by_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class CRMNoteSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    mentions_details = UserMinimalSerializer(source='mentions', many=True, read_only=True)
    mention_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='mentions',
        many=True,
        write_only=True,
        required=False
    )
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = CRMNote
        fields = [
            'id', 'content_type', 'object_id', 'content_type_name',
            'content', 'mentions', 'mentions_details', 'mention_ids',
            'created_by', 'created_by_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class CRMAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_details = UserMinimalSerializer(source='uploaded_by', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = CRMAttachment
        fields = [
            'id', 'content_type', 'object_id', 'content_type_name',
            'file', 'file_name', 'file_size', 'uploaded_by', 'uploaded_by_details', 'uploaded_at'
        ]
        read_only_fields = ['uploaded_by', 'uploaded_at']

    def get_file_name(self, obj):
        return os.path.basename(obj.file.name) if obj.file else ''

    def get_file_size(self, obj):
        try:
            if obj.file:
                size_in_kb = obj.file.size / 1024.0
                return f"{size_in_kb:.1f} KB"
            return '0 KB'
        except Exception:
            return '0 KB'
