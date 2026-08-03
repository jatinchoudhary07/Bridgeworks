from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models.approval import ApprovalPolicy, ApprovalRequest, ApprovalHistory
from core.serializers.approval import ApprovalPolicySerializer, ApprovalRequestSerializer
from core.services.approval_service import submit_for_approval, process_approval_action, check_and_escalate_approvals
from core.views_sales import _resolve_org

class ApprovalPolicyViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ApprovalPolicySerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return ApprovalPolicy.objects.none()
        return ApprovalPolicy.objects.filter(shop=shop)

    def perform_create(self, serializer):
        org_id, shop = _resolve_org(self.request)
        serializer.save(shop=shop)


class ApprovalRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ApprovalRequestSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return ApprovalRequest.objects.none()
        return ApprovalRequest.objects.filter(shop=shop)

    @action(detail=False, methods=['post'], url_path='submit')
    def submit_entity(self, request):
        """
        Submits an entity (e.g. quotation) for approval.
        POST parameters: entity_type (str), entity_id (int/str)
        """
        org_id, shop = _resolve_org(request)
        if not shop:
            return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)
            
        entity_type = request.data.get('entity_type')
        entity_id = request.data.get('entity_id')
        
        if not entity_type or not entity_id:
            return Response({'error': 'entity_type and entity_id are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            req = submit_for_approval(entity_type, entity_id, shop, request.user)
            if req:
                return Response(ApprovalRequestSerializer(req).data, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'message': 'No matching approval policies found. Entity was automatically approved.'
                }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_step(self, request, pk=None):
        """
        Approves the current step of this request.
        POST parameters: comments (str)
        """
        req = self.get_object()
        comments = request.data.get('comments', 'Approved')
        try:
            process_approval_action(req, request.user, 'approved', comments)
            return Response(ApprovalRequestSerializer(req).data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_step(self, request, pk=None):
        """
        Rejects this request.
        POST parameters: comments (str)
        """
        req = self.get_object()
        comments = request.data.get('comments', 'Rejected')
        try:
            process_approval_action(req, request.user, 'rejected', comments)
            return Response(ApprovalRequestSerializer(req).data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='check-sla')
    def check_sla(self, request):
        """
        Triggers evaluation of pending approvals against their SLAs, escalating overdue ones.
        """
        try:
            escalated_count = check_and_escalate_approvals()
            return Response({
                'message': f"SLA check completed. Escalated {escalated_count} approval requests."
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

