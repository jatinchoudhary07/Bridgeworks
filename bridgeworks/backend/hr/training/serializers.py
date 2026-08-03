from rest_framework import serializers
from django.contrib.auth import get_user_model
from hr.training.models import TrainingFile, TrainingPush, TrainingPushRecipient, TrainingAcknowledgement

User = get_user_model()


# ─── Minimal User representation ─────────────────────────────────────────────

class MemberMinimalSerializer(serializers.ModelSerializer):
    full_name  = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'full_name', 'avatar_url']

    def get_full_name(self, obj):
        try:
            from core.models import WorkforceMember
            member = WorkforceMember.objects.filter(email=obj.email).first()
            if member and member.full_name:
                return member.full_name
        except Exception:
            pass
        try:
            if obj.profile.full_name:
                return obj.profile.full_name
        except Exception:
            pass
        return obj.get_full_name() or obj.username

    def get_avatar_url(self, obj):
        try:
            pic = obj.profile.profile_picture
            return pic.url if pic else None
        except Exception:
            return None


# ─── TrainingAcknowledgement ──────────────────────────────────────────────────

class TrainingAcknowledgementSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TrainingAcknowledgement
        fields = ['id', 'acknowledged_at', 'ip_address', 'device_info', 'notes']


# ─── TrainingPushRecipient ────────────────────────────────────────────────────

class TrainingPushRecipientSerializer(serializers.ModelSerializer):
    # Both aliases exposed so the frontend can use either key
    user_detail   = MemberMinimalSerializer(source='user', read_only=True)
    member_detail = MemberMinimalSerializer(source='user', read_only=True)
    # acknowledged = property alias on the model (returns is_acknowledged)
    acknowledged  = serializers.BooleanField(source='is_acknowledged', read_only=True)

    # Nested push info (for the employee "my-assignments" view)
    push_training_file_detail = serializers.SerializerMethodField()

    class Meta:
        model  = TrainingPushRecipient
        fields = [
            'id', 'push',
            'user', 'user_detail', 'member_detail',
            'is_acknowledged', 'acknowledged',
            'acknowledged_at', 'task_id',
            'push_training_file_detail',
        ]
        read_only_fields = ['id', 'is_acknowledged', 'acknowledged', 'acknowledged_at', 'task_id']

    def get_push_training_file_detail(self, obj):
        """Return the training file nested inside the push so the frontend can
        access push.training_file_detail directly on assignment objects."""
        try:
            tf = obj.push.training_file
            return {
                'id':               tf.id,
                'title':            tf.title,
                'category':         tf.category,
                'category_display': tf.get_category_display(),
                'file':             tf.file.url if tf.file else None,
                'video_url':        tf.video_url,
                'file_type':        tf.file_type,
                'is_mandatory':     tf.is_mandatory,
                'department_target': tf.department_target or tf.target_dept,
                'expiry_date':      str(tf.expiry_date) if tf.expiry_date else None,
                'version':          tf.version,
            }
        except Exception:
            return None


# ─── TrainingFile ─────────────────────────────────────────────────────────────

class TrainingFileSerializer(serializers.ModelSerializer):
    category_display   = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_detail = MemberMinimalSerializer(source='uploaded_by', read_only=True)
    is_expiring_soon   = serializers.ReadOnlyField()
    is_expired         = serializers.ReadOnlyField()
    versions_count     = serializers.SerializerMethodField()
    total_recipients   = serializers.SerializerMethodField()
    overall_completion = serializers.SerializerMethodField()

    class Meta:
        model  = TrainingFile
        fields = [
            'id', 'org_id', 'title', 'description',
            'file', 'video_url', 'file_type', 'file_size_kb',
            'category', 'category_display',
            'is_mandatory',
            'target_dept', 'department_target',
            'expiry_date', 'version',
            'parent_file', 'superseded_by',
            'uploaded_by', 'uploaded_by_detail',
            'created_at', 'updated_at',
            'is_expiring_soon', 'is_expired',
            'versions_count', 'total_recipients', 'overall_completion',
        ]
        read_only_fields = [
            'id', 'org_id', 'version', 'uploaded_by', 'created_at', 'updated_at',
            'file_type', 'file_size_kb',
        ]

    def get_versions_count(self, obj):
        root = obj.parent_file if obj.parent_file else obj
        return TrainingFile.objects.filter(parent_file=root).count() + (1 if root.parent_file is None else 0)

    def get_total_recipients(self, obj):
        return TrainingPushRecipient.objects.filter(push__training_file=obj).count()

    def get_overall_completion(self, obj):
        recipients = TrainingPushRecipient.objects.filter(push__training_file=obj)
        total = recipients.count()
        if total == 0:
            return 0
        acked = recipients.filter(is_acknowledged=True).count()
        return round((acked / total) * 100, 1)

    def create(self, validated_data):
        file_obj = self.context.get('request', None)
        if file_obj:
            file_obj = self.context['request'].FILES.get('file')
        if file_obj:
            validated_data['file_size_kb'] = round(file_obj.size / 1024)
            validated_data['file_type']    = file_obj.name.rsplit('.', 1)[-1].lower()
        elif validated_data.get('video_url'):
            validated_data['file_type']    = 'mp4'
        return super().create(validated_data)


# ─── TrainingPush ─────────────────────────────────────────────────────────────

class TrainingPushSerializer(serializers.ModelSerializer):
    pushed_by_detail     = MemberMinimalSerializer(source='pushed_by', read_only=True)
    training_file_detail = TrainingFileSerializer(source='training_file', read_only=True)
    recipients           = TrainingPushRecipientSerializer(many=True, read_only=True)
    recipient_ids        = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    completion_percentage = serializers.ReadOnlyField()
    completion_rate       = serializers.SerializerMethodField()

    class Meta:
        model  = TrainingPush
        fields = [
            'id', 'org_id',
            'training_file', 'training_file_detail',
            'vault_id', 'vault_name',
            'pushed_by', 'pushed_by_detail',
            'is_mandatory', 'create_task', 'notify_members',
            'pushed_at', 'notes',
            'target_departments',
            'recipients', 'recipient_ids',
            'completion_percentage', 'completion_rate',
        ]
        read_only_fields = ['id', 'org_id', 'pushed_by', 'pushed_at']

    def get_completion_rate(self, obj):
        total = obj.recipients.count()
        if total == 0:
            return 0.0
        acked = obj.recipients.filter(is_acknowledged=True).count()
        return round((acked / total) * 100, 2)

    def create(self, validated_data):
        recipient_ids = validated_data.pop('recipient_ids', [])
        push = TrainingPush.objects.create(**validated_data)
        for uid in recipient_ids:
            TrainingPushRecipient.objects.get_or_create(push=push, user_id=uid)
        return push


# ─── Stats ────────────────────────────────────────────────────────────────────

class TrainingStatsSerializer(serializers.Serializer):
    total_files          = serializers.IntegerField()
    total_pushed         = serializers.IntegerField()
    avg_completion       = serializers.FloatField()
    expiring_soon_count  = serializers.IntegerField()
    mandatory_count      = serializers.IntegerField()
    optional_count       = serializers.IntegerField()
