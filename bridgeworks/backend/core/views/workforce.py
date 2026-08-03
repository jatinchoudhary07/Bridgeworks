from django.db.models import Q
import cloudinary.uploader
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import WorkforceDepartment, WorkforceMember, UserProfile
from core.permissions import IsOrganizationOwner, HasModulePermission, _check_granular_permission, is_org_owner
from core.serializers import WorkforceDepartmentSerializer, WorkforceMemberSerializer

from .helpers import _get_org_id_or_none


DEFAULT_WORKFORCE_DEPARTMENTS = [
    'Marketing',
    'Customer Relation Management',
    'Operations',
    'Design',
    'Logistics',
    'Purchase',
    'Sales / Business Development',
    'Finance',
    'Information Technology',
    'Human Resource',
    'Production',
    'Services',
    'House Keeping',
    'Other',
]

User = get_user_model()


def _sync_profile_from_workforce_member(member, org_id):
    email = (member.email or '').strip()
    if not email:
        return

    linked_user = User.objects.filter(
        Q(team_settings__organization__organization_id=org_id) | Q(shop_credentials__organization_id=org_id),
        email__iexact=email,
        is_active=True,
    ).distinct().first()

    if not linked_user:
        return

    profile, _ = UserProfile.objects.get_or_create(user=linked_user)
    extra_data = member.extra_data if isinstance(member.extra_data, dict) else {}

    profile.full_name = member.full_name or profile.full_name
    profile.phone = member.phone or ''
    profile.location = member.current_location or ''
    profile.gender = member.gender or ''
    profile.about = member.notes or ''
    profile.whatsapp = extra_data.get('whatsapp') or ''
    profile.first_language = extra_data.get('first_language') or profile.first_language or 'Hindi'
    profile.second_language = extra_data.get('second_language') or profile.second_language or 'English'
    profile.bank_account_holder = extra_data.get('bank_account_name') or ''
    profile.bank_name = extra_data.get('bank_name') or ''
    profile.bank_account_number = extra_data.get('account_number') or ''
    profile.bank_ifsc_code = extra_data.get('ifsc') or ''

    dob_value = extra_data.get('dob')
    if dob_value:
        try:
            from datetime import datetime
            profile.dob = datetime.fromisoformat(dob_value).date()
        except Exception:
            pass

    profile.save()


class WorkforceDepartmentListCreateView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view'],
        'POST': 'human_resources:workforce_sheet:create'
    }

    def _ensure_default_departments(self, org_id, user):
        existing_names = set(
            WorkforceDepartment.objects.filter(org_id=org_id).values_list('name', flat=True)
        )

        missing_departments = [
            WorkforceDepartment(org_id=org_id, name=name, created_by=user)
            for name in DEFAULT_WORKFORCE_DEPARTMENTS
            if name not in existing_names
        ]

        if missing_departments:
            WorkforceDepartment.objects.bulk_create(missing_departments, ignore_conflicts=True)

    def get(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response([], status=status.HTTP_200_OK)

        self._ensure_default_departments(org_id, request.user)
        departments = WorkforceDepartment.objects.filter(org_id=org_id).order_by('name')
        serializer = WorkforceDepartmentSerializer(departments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)

        name = str(request.data.get('name', '')).strip()
        if not name:
            return Response({'name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        department, created = WorkforceDepartment.objects.get_or_create(
            org_id=org_id,
            name=name,
            defaults={'created_by': request.user},
        )

        serializer = WorkforceDepartmentSerializer(department)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=code)


class WorkforceDepartmentDetailView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'DELETE': 'human_resources:workforce_sheet:delete'
    }

    def delete(self, request, department_id):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)

        department = WorkforceDepartment.objects.filter(id=department_id, org_id=org_id).first()
        if not department:
            return Response({'detail': 'Department not found.'}, status=status.HTTP_404_NOT_FOUND)

        department.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkforceMemberListCreateView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view'],
        'POST': 'human_resources:workforce_sheet:create'
    }

    def get(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response([], status=status.HTTP_200_OK)

        queryset = WorkforceMember.objects.filter(org_id=org_id).select_related('department')

        search = str(request.query_params.get('search', '')).strip()
        department_id = request.query_params.get('department')
        working_style = request.query_params.get('working_style')
        member_status = request.query_params.get('status')
        gender = request.query_params.get('gender')
        archive_state = str(request.query_params.get('archive_state', 'active')).strip().lower()

        if archive_state == 'archived':
            queryset = queryset.filter(is_archived=True)
        elif archive_state == 'all':
            pass
        else:
            queryset = queryset.filter(is_archived=False)

        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
                | Q(current_location__icontains=search)
            )
        if department_id and department_id != 'all':
            queryset = queryset.filter(department_id=department_id)
        if working_style and working_style != 'all':
            queryset = queryset.filter(working_style=working_style)
        if member_status and member_status != 'all':
            queryset = queryset.filter(status=member_status)
        if gender and gender != 'all':
            queryset = queryset.filter(gender=gender)

        serializer = WorkforceMemberSerializer(queryset.order_by('-created_at'), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WorkforceMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save(org_id=org_id, created_by=request.user)
        _sync_profile_from_workforce_member(member, org_id)
        return Response(WorkforceMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class WorkforceMemberDetailView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view'],
        'PATCH': 'human_resources:workforce_sheet:edit',
        'DELETE': 'human_resources:workforce_sheet:delete'
    }

    def _get_member(self, request, member_id):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return None
        return WorkforceMember.objects.filter(id=member_id, org_id=org_id).select_related('department').first()

    def get(self, request, member_id):
        member = self._get_member(request, member_id)
        if not member:
            return Response({'detail': 'Workforce member not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkforceMemberSerializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, member_id):
        member = self._get_member(request, member_id)
        if not member:
            return Response({'detail': 'Workforce member not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WorkforceMemberSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_member = serializer.save()
        org_id = _get_org_id_or_none(request)
        if org_id:
            _sync_profile_from_workforce_member(updated_member, org_id)
        return Response(WorkforceMemberSerializer(updated_member).data, status=status.HTTP_200_OK)

    def delete(self, request, member_id):
        # Use centralized helper for more flexible access
        if not _check_granular_permission(request.user, 'human_resources', 'workforce_sheet', 'DELETE'):
             return Response({'detail': 'Only organization owner or authorized managers can delete members.'}, status=status.HTTP_403_FORBIDDEN)

        member = self._get_member(request, member_id)
        if not member:
            return Response({'detail': 'Workforce member not found.'}, status=status.HTTP_404_NOT_FOUND)

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkforceMemberBulkArchiveView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'human_resources:workforce_sheet:edit'
    }

    def post(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)

        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'ids': ['Provide at least one member id.']}, status=status.HTTP_400_BAD_REQUEST)

        action = str(request.data.get('action', 'archive')).strip().lower()
        if action not in {'archive', 'unarchive'}:
            return Response({'action': ['Action must be archive or unarchive.']}, status=status.HTTP_400_BAD_REQUEST)

        target_archived_state = action == 'archive'
        updated_count = WorkforceMember.objects.filter(org_id=org_id, id__in=ids).update(is_archived=target_archived_state)

        return Response(
            {
                'updated_count': updated_count,
                'action': action,
            },
            status=status.HTTP_200_OK,
        )


class WorkforceMemberPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def _has_access(self, request):
        user = request.user
        if not user.is_authenticated:
            return False
            
        # Org owners, co-founders & superusers always allowed
        if is_org_owner(user):
            return True
            
        # Check via RBAC role permissions
        return _check_granular_permission(user, 'human_resources', 'roles_permissions', request.method)

    def _get_member(self, request, member_id):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return None
        return WorkforceMember.objects.filter(id=member_id, org_id=org_id).first()

    def get(self, request, member_id):
        if not self._has_access(request):
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        member = self._get_member(request, member_id)
        if not member:
            return Response({'error': 'Workforce member not found.'}, status=status.HTTP_404_NOT_FOUND)

        extra_data = member.extra_data if isinstance(member.extra_data, dict) else {}
        return Response(
            {
                'member_id': member.id,
                'email': member.email,
                'permissions': extra_data.get('permissions', {}),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, member_id):
        if not self._has_access(request):
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        member = self._get_member(request, member_id)
        if not member:
            return Response({'error': 'Workforce member not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Founder protection: if this workforce member is linked to the founder,
        # only the founder themselves or a superuser can edit their access.
        email = (member.email or '').strip()
        if email:
            linked_user = User.objects.filter(email__iexact=email, is_active=True).first()
            if linked_user and hasattr(linked_user, 'shop_credentials'):
                if not request.user.is_superuser and not hasattr(request.user, 'shop_credentials'):
                    return Response({"error": "Cannot modify the founder's access."}, status=status.HTTP_403_FORBIDDEN)

        permissions = request.data.get('permissions', {})
        if not isinstance(permissions, dict):
            return Response({'error': 'Invalid permissions structure provided.'}, status=status.HTTP_400_BAD_REQUEST)

        extra_data = member.extra_data if isinstance(member.extra_data, dict) else {}
        extra_data['permissions'] = permissions
        member.extra_data = extra_data
        member.save(update_fields=['extra_data', 'updated_at'])

        # Handle role_id assignment (mirrors TeammatePermissionsView logic)
        role_id = request.data.get('role_id')
        if role_id:
            from core.models import Role, WorkspaceMembership
            # Find linked Django User by email
            linked_user = None
            email = (member.email or '').strip()
            if email:
                linked_user = User.objects.filter(email__iexact=email, is_active=True).first()

            if linked_user:
                try:
                    role = Role.objects.get(id=role_id)
                    # Determine workspace with fallback logic
                    workspace = getattr(request.user, 'shop_credentials', None)
                    if not workspace:
                        from core.models.users import WorkspaceMembership as WM
                        mem = WM.objects.filter(user=request.user).select_related('workspace').first()
                        if mem:
                            workspace = mem.workspace
                    if workspace:
                        WorkspaceMembership.objects.update_or_create(
                            user=linked_user,
                            workspace=workspace,
                            defaults={'role': role}
                        )
                except Role.DoesNotExist:
                    pass

        return Response({'status': 'Permissions updated successfully.'}, status=status.HTTP_200_OK)


class WorkforceDocumentUploadView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'human_resources:workforce_sheet:edit'
    }
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, doc_type):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if doc_type not in {'aadhaar', 'pan'}:
            return Response({'detail': 'Invalid document type.'}, status=status.HTTP_400_BAD_REQUEST)

        document = request.FILES.get('document')
        if not document:
            return Response({'detail': 'No document file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upload_result = cloudinary.uploader.upload(
                document,
                folder=f'bridgeworks/workforce/{org_id}/{doc_type}',
                resource_type='auto',
                overwrite=True,
            )
        except Exception as upload_error:
            return Response(
                {'detail': f'Failed to upload document: {str(upload_error)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secure_url = upload_result.get('secure_url') or upload_result.get('url')
        if not secure_url:
            return Response({'detail': 'Cloudinary did not return a document URL.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'doc_type': doc_type,
                'url': secure_url,
                'public_id': upload_result.get('public_id'),
            },
            status=status.HTTP_200_OK,
        )
