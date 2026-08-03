import logging
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hr.training.models import (
    TrainingFile, TrainingPush, TrainingPushRecipient, TrainingAcknowledgement
)
from hr.training.serializers import (
    TrainingFileSerializer, TrainingPushSerializer,
    TrainingPushRecipientSerializer, TrainingStatsSerializer,
)

try:
    from core.models import WorkforceMember
except ImportError:
    WorkforceMember = None

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_org_id(request):
    try:
        return request.user.team_settings.organization.organization_id
    except Exception:
        return None


def is_hr_admin(user):
    from core.permissions import is_org_owner, _check_granular_permission
    if is_org_owner(user):
        return True
    return (
        _check_granular_permission(user, 'human_resources', 'workforce', 'GET') or
        _check_granular_permission(user, 'human_resources', 'master_task_tracker', 'GET')
    )


# ─── Training File ViewSet ────────────────────────────────────────────────────

class TrainingFileViewSet(viewsets.ModelViewSet):
    """
    CRUD for training files.

    Extra actions
    ─────────────
    GET  /training-files/stats/              → dashboard KPIs
    POST /training-files/{id}/push/          → push to vault
    POST /training-files/{id}/acknowledge/   → employee acknowledges
    GET  /training-files/{id}/recipients/    → all recipients across all pushes
    GET  /training-files/{id}/versions/      → full version chain
    """
    serializer_class   = TrainingFileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['title', 'description', 'target_dept', 'department_target']
    ordering_fields    = ['created_at', 'title', 'expiry_date']
    ordering           = ['-created_at']

    def get_queryset(self):
        org_id = _get_org_id(self.request)
        qs = TrainingFile.objects.select_related('uploaded_by').filter(
            org_id=org_id, parent_file__isnull=True
        )
        # Non-HR employees can view all training documents in the organization
        pass

        category  = self.request.query_params.get('category')
        mandatory = self.request.query_params.get('is_mandatory')
        dept      = self.request.query_params.get('dept')

        if category:
            qs = qs.filter(category=category)
        if mandatory is not None:
            qs = qs.filter(is_mandatory=mandatory.lower() == 'true')
        if dept:
            qs = qs.filter(
                Q(target_dept__iexact=dept) | Q(department_target__iexact=dept) |
                Q(target_dept__iexact='all') | Q(department_target__iexact='all')
            )
        return qs

    def perform_create(self, serializer):
        org_id   = _get_org_id(self.request)
        file_obj = self.request.FILES.get('file')
        extra    = {'org_id': org_id, 'uploaded_by': self.request.user}
        if file_obj:
            extra['file_size_kb'] = round(file_obj.size / 1024)
            extra['file_type']    = file_obj.name.rsplit('.', 1)[-1].lower()
        elif self.request.data.get('video_url'):
            extra['file_type']    = 'mp4'
        serializer.save(**extra)

    def create(self, request, *args, **kwargs):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        org_id = _get_org_id(request)
        files  = TrainingFile.objects.filter(org_id=org_id, parent_file__isnull=True)

        total_files      = files.count()
        total_pushed     = TrainingPush.objects.filter(org_id=org_id).values('training_file').distinct().count()
        mandatory_count  = files.filter(is_mandatory=True).count()
        optional_count   = files.filter(is_mandatory=False).count()

        today = timezone.now().date()
        expiring_soon_count = files.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timezone.timedelta(days=30),
        ).count()

        recipients = TrainingPushRecipient.objects.filter(push__org_id=org_id)
        total_r    = recipients.count()
        acked_r    = recipients.filter(is_acknowledged=True).count()
        avg_completion = round((acked_r / total_r * 100) if total_r else 0, 1)

        data = {
            'total_files':          total_files,
            'total_pushed':         total_pushed,
            'avg_completion':       avg_completion,
            'expiring_soon_count':  expiring_soon_count,
            'mandatory_count':      mandatory_count,
            'optional_count':       optional_count,
        }
        return Response(TrainingStatsSerializer(data).data)

    # ── Push ──────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='push')
    def push(self, request, pk=None):
        """Push a training file to a vault with a specific recipient list."""
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        training_file      = self.get_object()
        org_id             = _get_org_id(request)
        recipient_ids      = request.data.get('recipient_ids', [])
        target_departments = request.data.get('target_departments', [])

        push = TrainingPush.objects.create(
            org_id             = org_id,
            training_file      = training_file,
            pushed_by          = request.user,
            vault_id           = request.data.get('vault_id', ''),
            vault_name         = request.data.get('vault_name', ''),
            is_mandatory       = request.data.get('is_mandatory', training_file.is_mandatory),
            create_task        = request.data.get('create_task', False),
            notify_members     = request.data.get('notify_members', True),
            notes              = request.data.get('notes', ''),
            target_departments = target_departments,
        )

        member_users = set()
        if recipient_ids:
            member_users.update(User.objects.filter(id__in=recipient_ids))
        if target_departments and WorkforceMember is not None:
            emails = WorkforceMember.objects.filter(
                org_id=org_id, status='Active',
                department__name__in=target_departments,
            ).values_list('email', flat=True)
            member_users.update(User.objects.filter(email__in=emails))

        for u in member_users:
            TrainingPushRecipient.objects.get_or_create(push=push, user=u)

        return Response(
            TrainingPushSerializer(push, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Acknowledge ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        """Employee acknowledges reading/watching a training file."""
        training_file = self.get_object()
        push_id       = request.data.get('push_id')

        try:
            recipient = TrainingPushRecipient.objects.get(
                push_id=push_id,
                push__training_file=training_file,
                user=request.user,
            )
        except TrainingPushRecipient.DoesNotExist:
            return Response({'detail': 'No matching push recipient found.'}, status=404)

        if recipient.is_acknowledged:
            return Response({'detail': 'Already acknowledged.'}, status=400)

        recipient.mark_acknowledged()

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        ua = request.META.get('HTTP_USER_AGENT', '')[:255]
        TrainingAcknowledgement.objects.get_or_create(
            training_file=training_file,
            user=request.user,
            defaults={
                'org_id':        _get_org_id(request) or '',
                'push_recipient': recipient,
                'ip_address':    ip,
                'device_info':   ua,
                'notes':         request.data.get('notes', ''),
            },
        )
        return Response({'detail': 'Acknowledged.', 'acknowledged_at': recipient.acknowledged_at})

    # ── Recipients ────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='recipients')
    def recipients(self, request, pk=None):
        """All recipients across all pushes for this file (latest push wins per member)."""
        training_file = self.get_object()
        qs = TrainingPushRecipient.objects.filter(
            push__training_file=training_file
        ).select_related('user', 'push')

        seen = {}
        for r in qs:
            uid   = r.user.id
            entry = {
                'member_id':       uid,
                'full_name':       r.user.get_full_name() or r.user.username,
                'email':           r.user.email,
                'push_id':         r.push.id,
                'vault_name':      r.push.vault_name,
                'pushed_at':       r.push.pushed_at,
                'acknowledged':    r.is_acknowledged,
                'acknowledged_at': r.acknowledged_at,
            }
            if uid not in seen or r.push.pushed_at > seen[uid]['pushed_at']:
                seen[uid] = entry

        return Response(list(seen.values()))

    # ── Versions ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        org_id        = _get_org_id(request)
        training_file = get_object_or_404(TrainingFile, pk=pk, org_id=org_id)
        root          = training_file.parent_file if training_file.parent_file else training_file
        qs = TrainingFile.objects.filter(
            models.Q(parent_file=root) | models.Q(id=root.id)
        ).order_by('-version')
        return Response(TrainingFileSerializer(qs, many=True).data)


# ─── Training Push ViewSet ────────────────────────────────────────────────────

class TrainingPushViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = TrainingPushSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org_id = _get_org_id(self.request)
        qs = TrainingPush.objects.filter(org_id=org_id).select_related(
            'training_file', 'pushed_by'
        ).prefetch_related('recipients__user')

        if not is_hr_admin(self.request.user):
            qs = qs.filter(recipients__user=self.request.user)
        return qs


# ─── My Assignments ViewSet ───────────────────────────────────────────────────

class TrainingMyAssignmentsViewSet(viewsets.GenericViewSet):
    """Employee-facing: list their assignments and acknowledge individual ones."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org_id = _get_org_id(self.request)
        return TrainingPushRecipient.objects.filter(
            user=self.request.user, push__org_id=org_id,
        ).select_related('push__training_file', 'push__pushed_by')

    @action(detail=False, methods=['get'], url_path='', url_name='list')
    def list_assignments(self, request):
        serializer = TrainingPushRecipientSerializer(
            self.get_queryset(), many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        org_id    = _get_org_id(request)
        recipient = get_object_or_404(
            TrainingPushRecipient, pk=pk, user=request.user, push__org_id=org_id,
        )
        if not recipient.is_acknowledged:
            recipient.mark_acknowledged()
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            ua = request.META.get('HTTP_USER_AGENT', '')[:255]
            TrainingAcknowledgement.objects.get_or_create(
                training_file=recipient.push.training_file,
                user=request.user,
                defaults={
                    'org_id':        org_id or '',
                    'push_recipient': recipient,
                    'ip_address':    ip,
                    'device_info':   ua,
                    'notes':         request.data.get('notes', ''),
                },
            )
        return Response(
            TrainingPushRecipientSerializer(recipient, context={'request': request}).data
        )


# ─── Compliance Dashboard ─────────────────────────────────────────────────────

class TrainingComplianceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        org_id = _get_org_id(request)
        pushes = TrainingPush.objects.filter(org_id=org_id).select_related(
            'training_file'
        ).prefetch_related('recipients')

        total_recipients   = 0
        total_acknowledged = 0
        file_stats         = []

        for push in pushes:
            push_recipients = push.recipients.all()
            p_total = push_recipients.count()
            p_ack   = push_recipients.filter(is_acknowledged=True).count()
            total_recipients   += p_total
            total_acknowledged += p_ack

            file_stats.append({
                'push_id':            push.id,
                'file_id':            push.training_file_id,
                'title':              push.training_file.title,
                'category':           push.training_file.get_category_display(),
                'pushed_at':          push.pushed_at,
                'is_mandatory':       push.is_mandatory,
                'total_recipients':   p_total,
                'total_acknowledged': p_ack,
                'completion_rate':    round((p_ack / p_total * 100) if p_total > 0 else 0.0, 2),
            })

        overall_compliance = round(
            (total_acknowledged / total_recipients * 100) if total_recipients > 0 else 0.0, 2
        )

        return Response({
            'total_files':        TrainingFile.objects.filter(org_id=org_id, parent_file__isnull=True).count(),
            'total_pushes':       pushes.count(),
            'overall_compliance': overall_compliance,
            'total_recipients':   total_recipients,
            'total_acknowledged': total_acknowledged,
            'file_stats':         file_stats,
        })


# ─── Legacy CBV wrappers (url-compat) ────────────────────────────────────────

class TrainingFileListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if is_hr_admin(request.user):
            qs = TrainingFile.objects.filter(org_id=org_id, parent_file__isnull=True)
        else:
            qs = TrainingFile.objects.filter(org_id=org_id, parent_file__isnull=True)
        return Response(TrainingFileSerializer(qs, many=True).data)

    def post(self, request):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        org_id   = _get_org_id(request)
        file_obj = request.FILES.get('file')
        extra    = {'org_id': org_id, 'uploaded_by': request.user}
        if file_obj:
            extra['file_size_kb'] = round(file_obj.size / 1024)
            extra['file_type']    = file_obj.name.rsplit('.', 1)[-1].lower()
        elif request.data.get('video_url'):
            extra['file_type']    = 'mp4'
        serializer = TrainingFileSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            obj = serializer.save(**extra)
            return Response(TrainingFileSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrainingFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_obj(self, pk, org_id):
        return get_object_or_404(TrainingFile, pk=pk, org_id=org_id)

    def get(self, request, pk):
        return Response(TrainingFileSerializer(self._get_obj(pk, _get_org_id(request))).data)

    def patch(self, request, pk):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        org_id        = _get_org_id(request)
        training_file = self._get_obj(pk, org_id)
        create_version = request.data.get('create_version') in [True, 'true', '1']

        if create_version:
            root = training_file.parent_file if training_file.parent_file else training_file
            highest = TrainingFile.objects.filter(
                models.Q(parent_file=root) | models.Q(id=root.id)
            ).order_by('-version').first()
            next_v = (highest.version + 1) if highest else (training_file.version + 1)

            dept_val = request.data.get('department_target', training_file.department_target)
            new_instance = TrainingFile(
                org_id            = org_id,
                title             = request.data.get('title', training_file.title),
                category          = request.data.get('category', training_file.category),
                department_target = dept_val,
                target_dept       = dept_val,
                is_mandatory      = request.data.get('is_mandatory', training_file.is_mandatory),
                expiry_date       = request.data.get('expiry_date', training_file.expiry_date),
                version           = next_v,
                parent_file       = root,
                uploaded_by       = request.user,
                video_url         = request.data.get('video_url', training_file.video_url or ''),
            )
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                new_instance.file = uploaded_file
                new_instance.file_size_kb = round(uploaded_file.size / 1024)
                new_instance.file_type    = uploaded_file.name.rsplit('.', 1)[-1].lower()
            else:
                if new_instance.video_url:
                    new_instance.file = None
                    new_instance.file_type = 'mp4'
                else:
                    new_instance.file = training_file.file
                    new_instance.file_size_kb = training_file.file_size_kb
                    new_instance.file_type = training_file.file_type
            new_instance.save()
            return Response(TrainingFileSerializer(new_instance).data, status=status.HTTP_201_CREATED)

        serializer = TrainingFileSerializer(training_file, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        self._get_obj(pk, _get_org_id(request)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainingPushListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if is_hr_admin(request.user):
            qs = TrainingPush.objects.filter(org_id=org_id)
        else:
            qs = TrainingPush.objects.filter(org_id=org_id, recipients__user=request.user)
        serializer = TrainingPushSerializer(
            qs.prefetch_related('recipients__user'), many=True
        )
        return Response(serializer.data)

    def post(self, request):
        if not is_hr_admin(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        org_id             = _get_org_id(request)
        file_id            = request.data.get('training_file')
        training_file      = get_object_or_404(TrainingFile, pk=file_id, org_id=org_id)
        target_departments = request.data.get('target_departments', [])
        target_members     = request.data.get('target_members', [])
        is_mandatory       = request.data.get('is_mandatory', training_file.is_mandatory)

        push = TrainingPush.objects.create(
            org_id             = org_id,
            training_file      = training_file,
            pushed_by          = request.user,
            is_mandatory       = is_mandatory,
            target_departments = target_departments,
        )

        recipient_users = set()
        if target_departments and WorkforceMember is not None:
            emails = WorkforceMember.objects.filter(
                org_id=org_id, status='Active',
                department__name__in=target_departments,
            ).values_list('email', flat=True)
            recipient_users.update(User.objects.filter(email__in=emails))
        if target_members:
            recipient_users.update(User.objects.filter(id__in=target_members))

        for u in recipient_users:
            TrainingPushRecipient.objects.get_or_create(push=push, user=u)

        return Response(TrainingPushSerializer(push).data, status=status.HTTP_201_CREATED)


class TrainingMyAssignmentsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        qs = TrainingPushRecipient.objects.filter(
            user=request.user, push__org_id=org_id,
        ).select_related('push__training_file', 'push__pushed_by')
        return Response(TrainingPushRecipientSerializer(qs, many=True).data)


class TrainingPushRecipientAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_id    = _get_org_id(request)
        recipient = get_object_or_404(
            TrainingPushRecipient, pk=pk, user=request.user, push__org_id=org_id,
        )
        if not recipient.is_acknowledged:
            recipient.mark_acknowledged()
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            ua = request.META.get('HTTP_USER_AGENT', '')[:255]
            TrainingAcknowledgement.objects.get_or_create(
                training_file=recipient.push.training_file,
                user=request.user,
                defaults={
                    'org_id':        org_id or '',
                    'push_recipient': recipient,
                    'ip_address':    ip,
                    'device_info':   ua,
                    'notes':         request.data.get('notes', ''),
                },
            )
        return Response(TrainingPushRecipientSerializer(recipient).data)


class TrainingFileVersionsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org_id        = _get_org_id(request)
        training_file = get_object_or_404(TrainingFile, pk=pk, org_id=org_id)
        root          = training_file.parent_file if training_file.parent_file else training_file
        qs = TrainingFile.objects.filter(
            models.Q(parent_file=root) | models.Q(id=root.id)
        ).order_by('-version')
        return Response(TrainingFileSerializer(qs, many=True).data)
