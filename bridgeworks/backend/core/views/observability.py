from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Count, Q
from django.utils import timezone
from core.models import WholesaleLead, Quotation, Workflow, WorkflowExecution, Recommendation, ShopCredentials
from core.models.webhooks import WebhookSubscription, OutboundWebhookLog
from core.models.readiness import SystemAuditLog
from core.models.crm import CRMTask
from core.views.helpers import _get_org_id_or_none

class SystemObservabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Resolve shop
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization context not found."}, status=status.HTTP_404_NOT_FOUND)
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if not shop:
            return Response({"error": "Shop credentials not found."}, status=status.HTTP_404_NOT_FOUND)

        # 1. System Metrics
        system_metrics = {
            "total_leads": WholesaleLead.objects.filter(shop=shop).count(),
            "total_quotations": Quotation.objects.filter(shop=shop).count(),
            "total_tasks": CRMTask.objects.filter(content_type__app_label='core').count(),
            "total_webhook_subs": WebhookSubscription.objects.filter(shop=shop).count(),
        }

        # 2. Workflow Metrics
        wf_breakdown_raw = WorkflowExecution.objects.filter(workflow__shop=shop).values('status').annotate(count=Count('id'))
        wf_breakdown = {item['status']: item['count'] for item in wf_breakdown_raw}
        workflow_metrics = {
            "total_defined": Workflow.objects.filter(shop=shop).count(),
            "total_executed": WorkflowExecution.objects.filter(workflow__shop=shop).count(),
            "status_breakdown": wf_breakdown,
        }

        # 3. Recommendation Metrics
        rec_breakdown_raw = Recommendation.objects.filter(shop=shop).values('status').annotate(count=Count('id'))
        rec_breakdown = {item['status']: item['count'] for item in rec_breakdown_raw}
        rec_severity_raw = Recommendation.objects.filter(shop=shop).values('severity').annotate(count=Count('id'))
        rec_severity = {item['severity']: item['count'] for item in rec_severity_raw}
        recommendation_metrics = {
            "total_generated": Recommendation.objects.filter(shop=shop).count(),
            "status_breakdown": rec_breakdown,
            "severity_breakdown": rec_severity,
        }

        # 4. Background Job Metrics (safe import)
        job_metrics = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
        }
        try:
            from django_q.models import Task
            # We filter general background jobs
            job_metrics["completed"] = Task.objects.filter(success=True).count()
            job_metrics["failed"] = Task.objects.filter(success=False).count()
            job_metrics["total_tasks"] = Task.objects.count()
        except Exception:
            # Fallback if django_q models aren't directly queryable/installed
            job_metrics["completed"] = WorkflowExecution.objects.filter(workflow__shop=shop, status='success').count()
            job_metrics["failed"] = WorkflowExecution.objects.filter(workflow__shop=shop, status='failed').count()
            job_metrics["total_tasks"] = WorkflowExecution.objects.filter(workflow__shop=shop).count()

        # 5. API / Webhook Performance Metrics
        webhook_logs = OutboundWebhookLog.objects.filter(shop=shop)
        total_webhooks = webhook_logs.count()
        success_webhooks = webhook_logs.filter(status='success').count()
        failed_webhooks = webhook_logs.filter(status='failed').count()
        
        # Calculate average duration
        avg_duration = 0
        if total_webhooks > 0:
            from django.db.models import Avg
            avg_duration = webhook_logs.aggregate(Avg('duration_ms'))['duration_ms__avg'] or 0

        performance_metrics = {
            "total_outbound_webhooks": total_webhooks,
            "success_webhooks": success_webhooks,
            "failed_webhooks": failed_webhooks,
            "avg_webhook_duration_ms": round(avg_duration, 2),
        }

        # 6. Recent Audit Logs
        recent_audits = list(
            SystemAuditLog.objects.filter(shop=shop)
            .order_by('-created_at')[:20]
            .values('id', 'user__username', 'action', 'model_name', 'object_id', 'created_at')
        )

        return Response({
            "system": system_metrics,
            "workflows": workflow_metrics,
            "recommendations": recommendation_metrics,
            "background_jobs": job_metrics,
            "performance": performance_metrics,
            "recent_audit_logs": recent_audits
        }, status=status.HTTP_200_OK)
