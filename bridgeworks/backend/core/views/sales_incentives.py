from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q
from core.models.sales import (
    SalesRepresentative, SalesActivity, SalesActivityProduct,
    IncentiveRule, IncentiveRecord
)
from core.serializers.sales import (
    SalesRepresentativeSerializer, SalesActivitySerializer,
    IncentiveRuleSerializer, IncentiveRecordSerializer
)
from core.permissions import HasModulePermission, is_org_owner
from core.views_sales import _resolve_org


class SalesRepresentativeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasModulePermission]
    serializer_class = SalesRepresentativeSerializer

    required_permissions = {
        'GET': ['sales.activities.view', 'sales_business:sales_activities:view'],
        'POST': ['sales.activities.create', 'sales_business:sales_activities:create'],
        'PUT': ['sales.activities.edit', 'sales_business:sales_activities:edit'],
        'PATCH': ['sales.activities.edit', 'sales_business:sales_activities:edit'],
        'DELETE': ['sales.activities.delete', 'sales_business:sales_activities:delete']
    }

    def get_queryset(self):
        _, shop = _resolve_org(self.request)
        if not shop:
            return SalesRepresentative.objects.none()
        return SalesRepresentative.objects.filter(shop=shop).select_related('user', 'reporting_manager')

    def perform_create(self, serializer):
        _, shop = _resolve_org(self.request)
        serializer.save(shop=shop)


class SalesActivityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasModulePermission]
    serializer_class = SalesActivitySerializer

    required_permissions = {
        'GET': ['sales.activities.view', 'sales_business:sales_activities:view'],
        'POST': ['sales.activities.create', 'sales_business:sales_activities:create'],
        'PUT': ['sales.activities.edit', 'sales_business:sales_activities:edit'],
        'PATCH': ['sales.activities.edit', 'sales_business:sales_activities:edit'],
        'DELETE': ['sales.activities.delete', 'sales_business:sales_activities:delete']
    }

    def get_queryset(self):
        _, shop = _resolve_org(self.request)
        if not shop:
            return SalesActivity.objects.none()
        qs = SalesActivity.objects.filter(
            sales_rep__shop=shop
        ).select_related(
            'sales_rep', 'approved_by'
        ).prefetch_related('products')

        # Status filter
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)

        # Date range filter
        date_from = self.request.GET.get('date_from', '').strip()
        if date_from:
            qs = qs.filter(visit_date__gte=date_from)

        date_to = self.request.GET.get('date_to', '').strip()
        if date_to:
            qs = qs.filter(visit_date__lte=date_to)

        # Sales rep filter
        sales_rep_id = self.request.GET.get('sales_rep', '').strip()
        if sales_rep_id:
            try:
                qs = qs.filter(sales_rep_id=int(sales_rep_id))
            except (ValueError, TypeError):
                pass

        # Text search across customer name and activity ID
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search) |
                Q(location__icontains=search) |
                Q(id__icontains=search)
            )

        return qs

    def perform_create(self, serializer):
        # Auto-set submitted_at when creating with submitted status
        status_val = self.request.data.get('status', 'draft')
        submitted_at = timezone.now() if status_val == 'submitted' else None
        serializer.save(submitted_at=submitted_at)

    def perform_update(self, serializer):
        # Auto-set submitted_at when transitioning to submitted
        instance = serializer.instance
        new_status = self.request.data.get('status', instance.status)
        submitted_at = instance.submitted_at
        if new_status == 'submitted' and not submitted_at:
            submitted_at = timezone.now()
        serializer.save(submitted_at=submitted_at)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Return aggregate counts of activities by status for the current shop."""
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'draft': qs.filter(status='draft').count(),
            'submitted': qs.filter(status='submitted').count(),
            'approved': qs.filter(status='approved').count(),
            'rejected': qs.filter(status='rejected').count(),
        })

    def _check_approve_permission(self, user):
        if is_org_owner(user):
            return True
        from core.models.users import WorkspaceMembership
        try:
            membership = WorkspaceMembership.objects.filter(user=user).select_related('role').first()
            if membership and membership.role:
                perms = set(membership.role.permissions.values_list('identifier', flat=True))
                return '*:*:*' in perms or 'sales.activities.approve' in perms or 'sales_business:approvals:approve' in perms
        except Exception:
            pass
        return False

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not self._check_approve_permission(request.user):
            return Response({'error': 'You do not have permission to approve activities.'}, status=status.HTTP_403_FORBIDDEN)
        activity = self.get_object()
        activity.status = 'approved'
        activity.approved_at = timezone.now()
        activity.approved_by = request.user
        activity.save()
        return Response({'status': 'activity approved', 'status_code': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not self._check_approve_permission(request.user):
            return Response({'error': 'You do not have permission to reject activities.'}, status=status.HTTP_403_FORBIDDEN)
        activity = self.get_object()
        activity.status = 'rejected'
        activity.save()
        return Response({'status': 'activity rejected', 'status_code': 'rejected'})


class IncentiveRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasModulePermission]
    serializer_class = IncentiveRuleSerializer

    required_permissions = {
        'GET': ['sales.incentives.view', 'sales_business:incentives:view'],
        'POST': ['sales.incentives.manage', 'sales_business:incentives:create'],
        'PUT': ['sales.incentives.manage', 'sales_business:incentives:edit'],
        'PATCH': ['sales.incentives.manage', 'sales_business:incentives:edit'],
        'DELETE': ['sales.incentives.manage', 'sales_business:incentives:delete']
    }

    def get_queryset(self):
        _, shop = _resolve_org(self.request)
        if not shop:
            return IncentiveRule.objects.none()
        return IncentiveRule.objects.filter(shop=shop)

    def perform_create(self, serializer):
        _, shop = _resolve_org(self.request)
        serializer.save(shop=shop)


class IncentiveRecordViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasModulePermission]
    serializer_class = IncentiveRecordSerializer

    required_permissions = {
        'GET': ['sales.incentives.view', 'sales_business:incentives:view']
    }

    def get_queryset(self):
        _, shop = _resolve_org(self.request)
        if not shop:
            return IncentiveRecord.objects.none()
        return IncentiveRecord.objects.filter(sales_rep__shop=shop)
