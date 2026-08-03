import os
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

from core.models import (
    MyDeskNote,
    MyDeskNoteVersion,
    MyDeskNoteAttachment,
    PersonalTodoItem,
    PersonalTodoAttachment,
    ExpenseEntry,
    LeaveRequest,
    AttendanceEntry,
    PayrollProfile,
    PayrollPaymentRecord,
    PayrollSalaryStructure,
    PayrollTaxDeclaration,
    GalleryAlbum,
    GalleryItem,
)

try:
    import cloudinary.api as cloudinary_api
    from cloudinary.utils import private_download_url as cloudinary_private_download_url
    CLOUDINARY_SIGNED_DOWNLOAD_AVAILABLE = True
except Exception:
    cloudinary_api = None
    cloudinary_private_download_url = None
    CLOUDINARY_SIGNED_DOWNLOAD_AVAILABLE = False

from core.cloudinary_utils import get_cloudinary_file_url, build_file_access_url


def _cloudinary_private_download_link(file_field, attachment=False):
    """Safe Cloudinary URL resolution — delegates to cloudinary_utils.

    The old implementation made up to 6 synchronous blocking HTTP calls
    per file to brute-force the resource type, which caused connection-pool
    exhaustion and cascading server crashes.  The new implementation uses
    extension-based inference, Django cache, and a 3-second timeout guard.
    """
    return get_cloudinary_file_url(file_field, attachment=attachment)


def _build_file_access_url(request, file_field, attachment=False):
    return build_file_access_url(request, file_field, attachment=attachment)



class MyDeskNoteVersionSerializer(serializers.ModelSerializer):
    version_label = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = MyDeskNoteVersion
        fields = ['id', 'title', 'content_html', 'saved_at', 'version_label', 'author']
        read_only_fields = ['id', 'saved_at', 'version_label', 'author']

    def get_version_label(self, obj):
        from django.utils import timezone
        saved = obj.saved_at
        if not saved:
            return 'Unknown'
        local = timezone.localtime(saved)
        # Avoid platform-specific strftime flags like %-d (Linux) or %#d (Windows)
        day = str(local.day)
        return local.strftime(f'%b {day}, %I:%M %p')

    def get_author(self, obj):
        # Version author is the note's owner
        user = getattr(obj.note, 'user', None)
        if not user:
            return None
        return user.get_full_name() or user.first_name or user.username or user.email


class MyDeskNoteAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = MyDeskNoteAttachment
        fields = ['id', 'original_name', 'mime_type', 'file_size', 'file_url', 'created_at']
        read_only_fields = ['id', 'file_url', 'created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        return _build_file_access_url(request, obj.file)


class MyDeskNoteSerializer(serializers.ModelSerializer):
    versions = MyDeskNoteVersionSerializer(many=True, read_only=True)
    file_attachments = MyDeskNoteAttachmentSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    shared_with = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = MyDeskNote
        fields = [
            'id',
            'title',
            'content_html',
            'tags',
            'labels',
            'is_pinned',
            'attachments',
            'drive_links',
            'ai_summary',
            'created_at',
            'updated_at',
            'versions',
            'file_attachments',
            'created_by_name',
            'is_owner',
            'shared_with',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'versions', 'file_attachments', 'created_by_name', 'is_owner', 'shared_with', 'ai_summary']

    def get_created_by_name(self, obj):
        user = getattr(obj, 'user', None)
        if not user:
            return None
        return user.get_full_name() or user.first_name or user.username or user.email

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return True
        return obj.user == request.user

    def get_shared_with(self, obj):
        labels = obj.labels if isinstance(obj.labels, list) else []
        member_ids = []
        for label in labels:
            if isinstance(label, str) and label.startswith('shared:member:'):
                try:
                    member_ids.append(int(label.replace('shared:member:', '', 1)))
                except ValueError:
                    pass
        if not member_ids:
            return []
        users = User.objects.filter(id__in=member_ids)
        return [{
            'id': u.id,
            'name': u.get_full_name() or u.first_name or u.username,
            'email': u.email
        } for u in users]


class PersonalTodoItemSerializer(serializers.ModelSerializer):
    task_attachments = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = PersonalTodoItem
        fields = ['id', 'text', 'is_done', 'recurring', 'sort_order', 'meta', 'attachment', 'attachment_url', 'task_attachments', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_attachment_url(self, obj):
        request = self.context.get('request')
        return _build_file_access_url(request, obj.attachment)

    def get_task_attachments(self, obj):
        include_task_attachments = self.context.get('include_task_attachments', True)
        if not include_task_attachments:
            return []

        request = self.context.get('request')
        items = []
        for attachment in obj.task_attachments.all():
            file_url = _build_file_access_url(request, attachment.file)
            items.append({
                'id': attachment.id,
                'original_name': attachment.original_name,
                'mime_type': attachment.mime_type,
                'file_size': attachment.file_size,
                'file_url': file_url,
                'created_at': attachment.created_at,
            })
        return items


class ExpenseEntrySerializer(serializers.ModelSerializer):
    receipt_url = serializers.SerializerMethodField()
    shared_with = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = ExpenseEntry
        fields = [
            'id',
            'transaction_type',
            'category',
            'amount',
            'approved_amount',
            'spent_on',
            'bill_date',
            'department',
            'status',
            'receipt',
            'receipt_url',
            'notes',
            'rejection_reason',
            'payment_date',
            'payment_method',
            'finance_status',
            'finance_entry_id',
            'workflow_steps',
            'shared_with',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'receipt_url', 'status', 'rejection_reason',
            'approved_amount',
            'finance_status', 'finance_entry_id', 'workflow_steps',
            'created_at', 'updated_at',
        ]

    def get_receipt_url(self, obj):
        request = self.context.get('request')
        return _build_file_access_url(request, obj.receipt)

    def get_shared_with(self, obj):
        # Use the prefetch cache (populated by prefetch_related('shares__recipient')
        # in the view) – iterating obj.shares.all() is zero extra DB queries.
        recipients = []
        for share in obj.shares.all():
            recipient = share.recipient
            if not recipient:
                continue
            name = (recipient.get_full_name() or recipient.first_name or recipient.username or recipient.email or '').strip()
            recipients.append({
                'id': recipient.id,
                'name': name,
                'email': recipient.email,
            })
        return recipients


class LeaveRequestSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.SerializerMethodField()
    requested_to_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    manager_actioned_by_name = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    is_requester = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = LeaveRequest
        fields = [
            'id',
            'leave_type',
            'start_date',
            'end_date',
            'reason',
            'decline_reason',
            'status',
            'reminder_count',
            'document',
            'document_url',
            'requested_to',
            'requested_to_name',
            'requested_by_name',
            'can_review',
            'is_requester',
            'manager_action',
            'manager_note',
            'manager_actioned_by',
            'manager_actioned_by_name',
            'manager_actioned_at',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'google_synced',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'requested_to_name', 'requested_by_name', 'can_review', 'is_requester',
            'approved_by_name', 'approved_at', 'manager_actioned_by_name', 'manager_actioned_at',
            'document_url', 'created_at', 'updated_at',
        ]

    def get_approved_by_name(self, obj):
        if not obj.approved_by:
            return None
        return obj.approved_by.get_full_name() or obj.approved_by.username

    def get_requested_to_name(self, obj):
        if not obj.requested_to:
            return None
        return obj.requested_to.get_full_name() or obj.requested_to.username

    def get_requested_by_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.username

    def get_manager_actioned_by_name(self, obj):
        if not obj.manager_actioned_by:
            return None
        return obj.manager_actioned_by.get_full_name() or obj.manager_actioned_by.username

    def get_can_review(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        return bool(obj.status == 'pending' and obj.requested_to_id == request.user.id)

    def get_is_requester(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        return bool(obj.user_id == request.user.id)

    def get_document_url(self, obj):
        request = self.context.get('request')
        return _build_file_access_url(request, obj.document)


class AttendanceEntrySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    hr_override_by_name = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = AttendanceEntry
        fields = [
            'id',
            'user',
            'user_name',
            'entry_date',
            'status',
            'work_mode',
            'auto_status',
            'hr_override_status',
            'hr_override_reason',
            'hr_override_by',
            'hr_override_by_name',
            'hr_override_at',
            'in_time',
            'out_time',
            'note',
            'on_duty_detail',
            'is_regularization',
            'regularization_reason',
            'approval_status',
            'source',
            'late_minutes',
            'early_leave_minutes',
            'hours_worked',
            'salary_deduction_days',
            'attendance_score_points',
            'approved_by',
            'approved_by_name',
            'approved_at',
            'rejection_reason',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_name', 'auto_status',
            'hr_override_by_name', 'hr_override_at',
            'late_minutes', 'early_leave_minutes', 'hours_worked',
            'salary_deduction_days', 'attendance_score_points',
            'approved_by_name', 'approved_at', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        status_value = attrs.get('status') or getattr(self.instance, 'status', '')
        on_duty_detail = (attrs.get('on_duty_detail') if 'on_duty_detail' in attrs else getattr(self.instance, 'on_duty_detail', '')).strip()
        in_time = attrs.get('in_time') if 'in_time' in attrs else getattr(self.instance, 'in_time', None)
        out_time = attrs.get('out_time') if 'out_time' in attrs else getattr(self.instance, 'out_time', None)
        is_regularization = attrs.get('is_regularization') if 'is_regularization' in attrs else getattr(self.instance, 'is_regularization', False)
        regularization_reason = (attrs.get('regularization_reason') if 'regularization_reason' in attrs else getattr(self.instance, 'regularization_reason', '')).strip()

        if in_time and out_time and out_time <= in_time:
            raise serializers.ValidationError({'out_time': 'Out time must be later than in time.'})

        if is_regularization and not regularization_reason:
            raise serializers.ValidationError({'regularization_reason': 'Reason is required for regularization requests.'})

        return attrs

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.first_name or obj.user.username or obj.user.email

    def get_approved_by_name(self, obj):
        if not obj.approved_by:
            return None
        return obj.approved_by.get_full_name() or obj.approved_by.first_name or obj.approved_by.username or obj.approved_by.email

    def get_hr_override_by_name(self, obj):
        if not obj.hr_override_by:
            return None
        return obj.hr_override_by.get_full_name() or obj.hr_override_by.first_name or obj.hr_override_by.username or obj.hr_override_by.email


class PayrollProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = PayrollProfile
        fields = [
            'id',
            'user',
            'user_name',
            'employee_code',
            'pan_number',
            'uan_number',
            'bank_name',
            'bank_account_number',
            'base_monthly_gross',
            'tax_regime',
            'payment_mode',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_name', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.first_name or obj.user.username or obj.user.email


class PayrollPaymentRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    payslip_pdf_url = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = PayrollPaymentRecord
        fields = [
            'id',
            'user',
            'user_name',
            'month',
            'working_days',
            'present_days',
            'lop_days',
            'gross_amount',
            'total_deductions',
            'net_amount',
            'payment_date',
            'utr_reference',
            'payment_mode',
            'status',
            'earnings_breakup',
            'deductions_breakup',
            'salary_structure_snapshot',
            'salary_structure_version',
            'remarks',
            'payslip_pdf_url',
            'dispute_status',
            'dispute_query',
            'dispute_resolution_note',
            'dispute_raised_at',
            'dispute_resolved_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user_name', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.first_name or obj.user.username or obj.user.email

    def get_payslip_pdf_url(self, obj):
        request = self.context.get('request')
        if not obj.payslip_pdf:
            return None
        try:
            url = obj.payslip_pdf.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None


class PayrollSalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:  # type: ignore
        model = PayrollSalaryStructure
        fields = [
            'id',
            'component_name',
            'monthly_amount',
            'annual_amount',
            'taxability',
            'remarks',
            'sort_order',
            'version',
            'effective_from',
            'effective_to',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayrollTaxDeclarationSerializer(serializers.ModelSerializer):
    class Meta:  # type: ignore
        model = PayrollTaxDeclaration
        fields = [
            'id',
            'financial_year',
            'section_code',
            'investment_name',
            'max_limit',
            'declared_amount',
            'proof_file_name',
            'status',
            'sort_order',
            'is_active',
            'submitted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'submitted_at', 'created_at', 'updated_at']

    def validate(self, attrs):
        max_limit = attrs.get('max_limit', getattr(self.instance, 'max_limit', 0))
        declared_amount = attrs.get('declared_amount', getattr(self.instance, 'declared_amount', 0))
        if declared_amount is not None and max_limit is not None and declared_amount > max_limit:
            raise serializers.ValidationError({'declared_amount': 'Declared amount cannot exceed max limit.'})
        return attrs


class GalleryAlbumSerializer(serializers.ModelSerializer):
    class Meta:  # type: ignore
        model = GalleryAlbum
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class GalleryItemSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()
    file_size_bytes = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    album_name = serializers.CharField(source='album.name', read_only=True)
    shared_with = serializers.SerializerMethodField()

    class Meta:  # type: ignore
        model = GalleryItem
        fields = [
            'id',
            'album',
            'album_name',
            'file',
            'file_name',
            'file_size_bytes',
            'file_url',
            'download_url',
            'media_type',
            'is_favorite',
            'is_reference',
            'captured_on',
            # vault / chat metadata
            'source',
            'category',
            'download_count',
            'chat_message_id',
            'chat_context_name',
            'chat_sender_name',
            'chat_shared_at',
            'shared_with',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'file_name', 'file_size_bytes', 'file_url', 'download_url',
            'album_name', 'download_count',
            'chat_message_id', 'chat_context_name', 'chat_sender_name', 'chat_shared_at',
            'created_at', 'updated_at',
        ]

    def get_file_name(self, obj):
        if not obj.file:
            return ''
        file_name = str(getattr(obj.file, 'name', '') or '')
        if not file_name:
            return ''
        return os.path.basename(file_name)

    def get_file_size_bytes(self, obj):
        if not obj.file:
            return None
        try:
            return int(getattr(obj.file, 'size', 0))
        except Exception:
            return None

    def get_file_url(self, obj):
        request = self.context.get('request')
        relative_path = f"/api/mydesk/gallery/items/{obj.id}/download/?serve=1"
        if request:
            return request.build_absolute_uri(relative_path)
        return relative_path

    def get_download_url(self, obj):
        request = self.context.get('request')
        relative_path = f"/api/mydesk/gallery/items/{obj.id}/download/?serve=1&download=1"
        if request:
            return request.build_absolute_uri(relative_path)
        return relative_path

    def get_shared_with(self, obj):
        import typing
        recipients = []
        for share in obj.shares.select_related('recipient').all():
            recipient = typing.cast(typing.Any, share.recipient)
            name = (recipient.get_full_name() or recipient.first_name or recipient.username or recipient.email or '').strip()
            recipients.append({
                'id': recipient.pk,
                'name': name,
                'email': recipient.email,
            })
        return recipients


class PublicHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = None  # Will be resolved dynamically
        fields = ['id', 'date', 'name', 'holiday_type']
        read_only_fields = ['id']

    def __init__(self, *args, **kwargs):
        from core.models import PublicHoliday
        super().__init__(*args, **kwargs)
        self.Meta.model = PublicHoliday


class AttendanceSessionExemptionSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = ['id', 'user', 'user_name', 'exemption_type', 'reason', 'is_active', 'created_at']
        read_only_fields = ['id', 'user_name', 'created_at']

    def __init__(self, *args, **kwargs):
        from core.models import AttendanceSessionExemption
        super().__init__(*args, **kwargs)
        self.Meta.model = AttendanceSessionExemption

    def get_user_name(self, obj):
        if not obj.user:
            return None
        return obj.user.get_full_name() or obj.user.first_name or obj.user.username or obj.user.email

