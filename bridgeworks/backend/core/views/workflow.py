from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from core.models.workflow import Workflow, WorkflowExecution
from core.serializers.workflow import WorkflowSerializer, WorkflowExecutionSerializer
from core.views_sales import _resolve_org

class WorkflowViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkflowSerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return Workflow.objects.none()
        return Workflow.objects.filter(shop=shop)

    def perform_create(self, serializer):
        org_id, shop = _resolve_org(self.request)
        serializer.save(shop=shop, created_by=self.request.user)


class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkflowExecutionSerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return WorkflowExecution.objects.none()
        
        workflow_id = self.kwargs.get('workflow_id')
        qs = WorkflowExecution.objects.filter(workflow__shop=shop)
        if workflow_id:
            qs = qs.filter(workflow_id=workflow_id)
        return qs


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def check_overdue_tasks_view(request):
    """
    Trigger overdue tasks workflow evaluation engine.
    """
    from core.services.workflow_engine import execute_overdue_task_workflows
    try:
        execute_overdue_task_workflows()
        return Response({'message': 'Triggered check for overdue tasks successfully.'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
