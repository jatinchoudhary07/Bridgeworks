from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta

from core.models import WholesaleLead, Quotation, CRMActivity, CRMTask
from core.models.customer_success import RenewalTracker, CustomerHealthScore
from core.views_sales import _resolve_org

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def crm_advanced_report(request):
    org_id, shop = _resolve_org(request)
    if not shop:
        return Response({'error': 'Organization/Shop not found'}, status=status.HTTP_400_BAD_REQUEST)

    persona = request.query_params.get('persona', 'manager')
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Resolve core WholesaleLead content type
    from django.contrib.contenttypes.models import ContentType
    lead_ct = ContentType.objects.get_for_model(WholesaleLead)
    lead_ids = WholesaleLead.objects.filter(shop=shop).values_list('id', flat=True)

    if persona == 'manager':
        # 1. Sales Manager View: Team Activity & Task Metrics
        activities = CRMActivity.objects.filter(
            content_type=lead_ct,
            object_id__in=lead_ids,
            created_at__gte=thirty_days_ago
        ).values('created_by__username').annotate(
            calls=Count('id', filter=Q(activity_type='call')),
            emails=Count('id', filter=Q(activity_type='email')),
            meetings=Count('id', filter=Q(activity_type='meeting')),
            total=Count('id')
        ).order_by('-total')

        tasks = CRMTask.objects.filter(
            content_type=lead_ct,
            object_id__in=lead_ids
        ).values('assignee__username').annotate(
            completed=Count('id', filter=Q(status='completed')),
            pending=Count('id', filter=Q(status='pending')),
            total=Count('id')
        )

        return Response({
            'persona': 'manager',
            'activities_last_30_days': list(activities),
            'tasks_performance': list(tasks)
        })

    elif persona == 'revenue':
        # 2. Revenue Manager View: MRR/ARR & Weighted Pipeline Value
        renewals = RenewalTracker.objects.filter(shop=shop).aggregate(
            total_mrr=Sum('monthly_recurring_revenue'),
            total_arr=Sum('annual_recurring_revenue'),
            total_upsell=Sum('upsell_opportunity_value'),
            active_contracts=Count('id', filter=Q(status='active'))
        )

        # Stage weights mapping for weighted pipeline calculation
        stage_weights = {
            'cold_lead': 0.10,
            'contacted': 0.20,
            'meeting_scheduled': 0.35,
            'proposal_sent': 0.50,
            'negotiation': 0.70,
            'agreement_signed': 0.90,
            'closed_won': 1.00,
            'closed_lost': 0.00
        }
        
        leads = WholesaleLead.objects.filter(shop=shop).values('stage').annotate(
            raw_value=Sum('expected_deal_value'),
            count=Count('id')
        )

        pipeline_breakdown = []
        total_weighted_value = 0.0
        for l in leads:
            stage = l['stage']
            weight = stage_weights.get(stage, 0.0)
            raw_val = float(l['raw_value'] or 0.0)
            weighted_val = raw_val * weight
            total_weighted_value += weighted_val
            pipeline_breakdown.append({
                'stage': stage,
                'stage_display': dict(WholesaleLead.STAGE_CHOICES).get(stage, stage),
                'raw_value': raw_val,
                'weighted_value': weighted_val,
                'weight_percentage': weight * 100,
                'deal_count': l['count']
            })

        return Response({
            'persona': 'revenue',
            'mrr_arr_summary': {
                'total_mrr': renewals['total_mrr'] or 0.0,
                'total_arr': renewals['total_arr'] or 0.0,
                'total_upsell': renewals['total_upsell'] or 0.0,
                'active_contracts': renewals['active_contracts']
            },
            'pipeline_breakdown': pipeline_breakdown,
            'total_weighted_pipeline': total_weighted_value
        })

    elif persona == 'bd':
        # 3. BD Head View: Lead Conversion Rate & Cycle Velocity
        leads_stats = WholesaleLead.objects.filter(shop=shop).aggregate(
            total_leads=Count('id'),
            closed_won=Count('id', filter=Q(stage='closed_won')),
            closed_lost=Count('id', filter=Q(stage='closed_lost')),
            active_pipeline=Count('id', filter=~Q(stage__in=['closed_won', 'closed_lost']))
        )

        total_closed = leads_stats['closed_won'] + leads_stats['closed_lost']
        conversion_rate = (leads_stats['closed_won'] / total_closed * 100) if total_closed > 0 else 0.0

        # Cycle velocity (days between created and closed/updated date)
        closed_leads = WholesaleLead.objects.filter(shop=shop, stage__in=['closed_won', 'closed_lost'])
        durations = []
        for cl in closed_leads:
            durations.append((cl.updated_at - cl.created_at).days)
        avg_cycle_days = (sum(durations) / len(durations)) if durations else 0.0

        avg_won_deal = closed_leads.filter(stage='closed_won').aggregate(avg_val=Avg('expected_deal_value'))['avg_val'] or 0.0

        return Response({
            'persona': 'bd',
            'conversion_summary': {
                'total_leads': leads_stats['total_leads'],
                'closed_won': leads_stats['closed_won'],
                'closed_lost': leads_stats['closed_lost'],
                'active_pipeline': leads_stats['active_pipeline'],
                'conversion_rate': conversion_rate
            },
            'avg_cycle_velocity_days': avg_cycle_days,
            'avg_won_deal_size': avg_won_deal
        })

    elif persona == 'executive':
        # 4. Executive View: macro KPIs
        total_won = WholesaleLead.objects.filter(shop=shop, stage='closed_won').aggregate(val=Sum('expected_deal_value'))['val'] or 0.0
        open_pipeline = WholesaleLead.objects.filter(shop=shop).exclude(stage__in=['closed_won', 'closed_lost']).aggregate(val=Sum('expected_deal_value'))['val'] or 0.0
        
        health_dist = CustomerHealthScore.objects.filter(shop=shop).values('churn_risk').annotate(count=Count('id'))
        avg_quote = Quotation.objects.filter(shop=shop).aggregate(avg_val=Avg('total_value'))['avg_val'] or 0.0

        return Response({
            'persona': 'executive',
            'executive_kpis': {
                'total_closed_revenue': total_won or 0.0,
                'open_pipeline_value': open_pipeline or 0.0,
                'average_quotation_value': avg_quote or 0.0
            },
            'churn_risk_distribution': list(health_dist)
        })

    return Response({'error': 'Invalid persona specifier'}, status=status.HTTP_400_BAD_REQUEST)
