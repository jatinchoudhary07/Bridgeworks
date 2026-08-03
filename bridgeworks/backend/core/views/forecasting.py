from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Q, Count
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.models.forecasting import SalesQuota
from core.models.sales import WholesaleLead, Quotation
from core.models.crm import CRMActivity, CRMTask
from core.serializers.forecasting import SalesQuotaSerializer
from core.views_sales import _resolve_org

class SalesQuotaViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SalesQuotaSerializer

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        if not shop:
            return SalesQuota.objects.none()
        return SalesQuota.objects.filter(shop=shop)

    def perform_create(self, serializer):
        org_id, shop = _resolve_org(self.request)
        serializer.save(shop=shop)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_sales_forecast(request):
    """
    Retrieves the actual sales forecast metrics and analytics data.
    """
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Resolve current period
    now = timezone.now()
    year = now.year
    month = now.month
    
    # 2. Get Quota target
    quota_qs = SalesQuota.objects.filter(shop=shop, year=year, month=month)
    total_quota = float(quota_qs.aggregate(total=Sum('target_amount'))['total'] or 0.0)
    if total_quota == 0.0:
        total_quota = 1000000.0  # Default ₹10L fallback target if not configured

    # 3. Retrieve actual closed won this month
    # Leads closed won
    won_leads_value = float(WholesaleLead.objects.filter(
        shop=shop, stage='closed_won', updated_at__year=year, updated_at__month=month
    ).aggregate(total=Sum('expected_deal_value'))['total'] or 0.0)
    
    # Quotes accepted
    won_quotes_value = float(Quotation.objects.filter(
        shop=shop, status='accepted', updated_at__year=year, updated_at__month=month
    ).aggregate(total=Sum('total_value'))['total'] or 0.0)
    
    actual_won = won_leads_value + won_quotes_value

    # 4. Open Leads Pipeline
    open_leads = WholesaleLead.objects.filter(shop=shop).exclude(stage__in=['closed_won', 'closed_lost'])
    
    lead_stage_weights = {
        'cold_lead': 0.10,
        'contacted': 0.20,
        'meeting_scheduled': 0.40,
        'proposal_sent': 0.60,
        'negotiation': 0.80,
        'agreement_signed': 0.95,
    }
    
    leads_pipeline_total = 0.0
    leads_weighted_total = 0.0
    leads_commit_total = 0.0
    
    for lead in open_leads:
        val = float(lead.expected_deal_value or 0.0)
        weight = lead_stage_weights.get(lead.stage, 0.10)
        leads_pipeline_total += val
        leads_weighted_total += val * weight
        if lead.stage in ('negotiation', 'agreement_signed'):
            leads_commit_total += val

    # 5. Open Quotes Pipeline
    open_quotes = Quotation.objects.filter(shop=shop).filter(
        status__in=['draft', 'pending_approval', 'sent', 'negotiation']
    )
    
    quote_status_weights = {
        'draft': 0.15,
        'pending_approval': 0.30,
        'sent': 0.50,
        'negotiation': 0.75,
    }
    
    quotes_pipeline_total = 0.0
    quotes_weighted_total = 0.0
    quotes_commit_total = 0.0
    
    for quote in open_quotes:
        val = float(quote.total_value or 0.0)
        weight = quote_status_weights.get(quote.status, 0.15)
        quotes_pipeline_total += val
        quotes_weighted_total += val * weight
        if quote.status == 'negotiation':
            quotes_commit_total += val

    # 6. Forecasting Calculations
    # Revenue Forecast = Actual Won + Weighted Open Leads + Weighted Open Quotes
    revenue_forecast = actual_won + leads_weighted_total + quotes_weighted_total
    
    # Commit Forecast = Actual Won + late stage open pipeline
    commit_forecast = actual_won + leads_commit_total + quotes_commit_total
    
    # Best Case Forecast = Actual Won + all open pipeline (100% value)
    best_case_forecast = actual_won + leads_pipeline_total + quotes_pipeline_total
    
    # Worst Case Forecast = Actual Won + agreement signed leads (95%)
    worst_case_leads = open_leads.filter(stage='agreement_signed')
    worst_case_leads_val = sum(float(l.expected_deal_value or 0.0) for l in worst_case_leads)
    worst_case_forecast = actual_won + (worst_case_leads_val * 0.95)

    # 7. Coverage and Accuracy
    remaining_quota = max(0.0, total_quota - actual_won)
    total_open_pipeline = leads_pipeline_total + quotes_pipeline_total
    pipeline_coverage = round(total_open_pipeline / max(1.0, remaining_quota), 2)
    
    forecast_accuracy = 100.0
    if total_quota > 0.0:
        forecast_accuracy = max(0.0, round((1.0 - (abs(actual_won - total_quota) / total_quota)) * 100.0, 1))

    # 8. Historical Win/Loss Rate
    total_won_count = WholesaleLead.objects.filter(shop=shop, stage='closed_won').count()
    total_lost_count = WholesaleLead.objects.filter(shop=shop, stage='closed_lost').count()
    win_loss_total = total_won_count + total_lost_count
    win_rate = round((total_won_count / max(1, win_loss_total)) * 100.0, 1) if win_loss_total > 0 else 0.0

    # 9. Activity metrics (volume & completion rate)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    activity_count = CRMActivity.objects.filter(
        created_at__gte=thirty_days_ago,
        content_type__model__in=['wholesalelead', 'quotation']
    ).count() # activity volume
    
    tasks_qs = CRMTask.objects.filter(content_type__model__in=['wholesalelead', 'quotation'])
    total_tasks = tasks_qs.count()
    completed_tasks = tasks_qs.filter(status='completed').count()
    task_completion_rate = round((completed_tasks / max(1, total_tasks)) * 100.0, 1) if total_tasks > 0 else 0.0

    # 10. Forecast Trend and Breakdown for Charts
    # Break down pipeline by stage
    stage_breakdown = {}
    for choice in WholesaleLead.STAGE_CHOICES:
        stage_breakdown[choice[0]] = 0.0
    for lead in WholesaleLead.objects.filter(shop=shop):
        stage_breakdown[lead.stage] = stage_breakdown.get(lead.stage, 0.0) + float(lead.expected_deal_value or 0.0)

    # Risk analysis count
    risk_leads_count = open_leads.filter(last_activity__lt=timezone.now() - timedelta(days=14)).count()

    return Response({
        'quota': total_quota,
        'actual_won': actual_won,
        'revenue_forecast': revenue_forecast,
        'commit_forecast': commit_forecast,
        'best_case_forecast': best_case_forecast,
        'worst_case_forecast': worst_case_forecast,
        'pipeline_coverage': pipeline_coverage,
        'forecast_accuracy': forecast_accuracy,
        'win_rate': win_rate,
        'activity_volume': activity_count,
        'task_completion_rate': task_completion_rate,
        'stage_breakdown': stage_breakdown,
        'risk_factors': {
            'stale_opportunities': risk_leads_count,
            'stuck_quotes': open_quotes.filter(valid_until__lt=date.today()).count(),
        }
    }, status=status.HTTP_200_OK)
