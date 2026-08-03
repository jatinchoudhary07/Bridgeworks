from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, Sum
from django.contrib.contenttypes.models import ContentType

from core.models import (
    ShopCredentials,
    WholesaleLead,
    RetailStore,
    RetailStoreCustomer,
    Quotation,
    Order
)
from core.models.crm import CRMActivity, CRMTask, CRMNote
from core.models.recommendation import Recommendation

def generate_recommendations_for_shop(shop):
    """
    Scans the database for actionable business intelligence insights
    for the given shop and reconciles recommendations.
    Returns a tuple: (created_count, resolved_count)
    """
    lead_ct = ContentType.objects.get_for_model(WholesaleLead)
    store_ct = ContentType.objects.get_for_model(RetailStore)
    quote_ct = ContentType.objects.get_for_model(Quotation)
    customer_ct = ContentType.objects.get_for_model(RetailStoreCustomer)

    candidates = []
    
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    today_val = date.today()
    
    # -------------------------------------------------------------
    # RULE 1: Stale Lead
    # Wholesale leads in non-closed stages with no logged CRM activities/notes/tasks in 7+ days.
    # -------------------------------------------------------------
    stale_leads = WholesaleLead.objects.filter(
        shop=shop,
        created_at__lt=seven_days_ago
    ).exclude(
        stage__in=['closed_won', 'closed_lost']
    )
    
    for lead in stale_leads:
        has_recent_activity = CRMActivity.objects.filter(
            content_type=lead_ct,
            object_id=lead.id,
            created_at__gte=seven_days_ago
        ).exists()
        
        has_recent_note = CRMNote.objects.filter(
            content_type=lead_ct,
            object_id=lead.id,
            created_at__gte=seven_days_ago
        ).exists()
        
        has_recent_task = CRMTask.objects.filter(
            content_type=lead_ct,
            object_id=lead.id,
            updated_at__gte=seven_days_ago
        ).exists()
        
        if not (has_recent_activity or has_recent_note or has_recent_task):
            val = float(lead.expected_deal_value or 0)
            score = 50.0 + min(val / 10000.0, 50.0)
            candidates.append({
                'type': 'stale_lead',
                'severity': 'medium',
                'title': f"Stale Lead: {lead.company_name}",
                'description': f"Lead '{lead.company_name}' in stage '{lead.get_stage_display()}' has had no activities, notes, or tasks recorded in the last 7 days.",
                'entity_type': 'lead',
                'entity_id': str(lead.id),
                'score': score
            })

    # -------------------------------------------------------------
    # RULE 2: Expiring Quote
    # Quotations in sent/negotiation status valid until date within next 48 hours.
    # -------------------------------------------------------------
    forty_eight_hours_later = today_val + timedelta(days=2)
    
    expiring_quotes = Quotation.objects.filter(
        shop=shop,
        status__in=['sent', 'negotiation'],
        valid_until__gte=today_val,
        valid_until__lte=forty_eight_hours_later
    )
    
    for quote in expiring_quotes:
        val = float(quote.total_value or 0)
        score = 70.0 + min(val / 10000.0, 30.0)
        candidates.append({
            'type': 'expiring_quote',
            'severity': 'high',
            'title': f"Expiring Quote: {quote.quote_number}",
            'description': f"Quotation {quote.quote_number} for {quote.client_name} (Value: ₹{quote.total_value}) is set to expire on {quote.valid_until}.",
            'entity_type': 'quote',
            'entity_id': str(quote.id),
            'score': score
        })

    # -------------------------------------------------------------
    # RULE 3: Overdue Task
    # CRM tasks in pending state past their due date.
    # -------------------------------------------------------------
    overdue_tasks = CRMTask.objects.filter(
        status='pending',
        due_date__lt=today_val
    )
    
    for task in overdue_tasks:
        belongs_to_shop = False
        
        if task.content_type == lead_ct:
            belongs_to_shop = WholesaleLead.objects.filter(id=task.object_id, shop=shop).exists()
        elif task.content_type == store_ct:
            belongs_to_shop = RetailStore.objects.filter(id=task.object_id, shop=shop).exists()
        elif task.content_type == quote_ct:
            belongs_to_shop = Quotation.objects.filter(id=task.object_id, shop=shop).exists()
        elif task.content_type == customer_ct:
            belongs_to_shop = RetailStoreCustomer.objects.filter(id=task.object_id, store__shop=shop).exists()
            
        if belongs_to_shop:
            days_overdue = (today_val - task.due_date).days
            severity = 'high' if days_overdue > 3 else 'medium'
            score = 40.0 + min(days_overdue * 5.0, 40.0)
            candidates.append({
                'type': 'overdue_task',
                'severity': severity,
                'title': f"Overdue Task: {task.title}",
                'description': f"Task '{task.title}' was due on {task.due_date} but is still pending.",
                'entity_type': 'task',
                'entity_id': str(task.id),
                'score': score
            })

    # -------------------------------------------------------------
    # RULE 4: Inactive Company
    # Retail stores (companies) with no quotation or activity in 30 days.
    # -------------------------------------------------------------
    thirty_days_ago = now - timedelta(days=30)
    
    active_stores = RetailStore.objects.filter(
        shop=shop,
        is_active=True,
        created_at__lt=thirty_days_ago
    )
    
    for store in active_stores:
        has_recent_activity = CRMActivity.objects.filter(
            content_type=store_ct,
            object_id=store.id,
            created_at__gte=thirty_days_ago
        ).exists()
        
        has_recent_note = CRMNote.objects.filter(
            content_type=store_ct,
            object_id=store.id,
            created_at__gte=thirty_days_ago
        ).exists()
        
        has_recent_task = CRMTask.objects.filter(
            content_type=store_ct,
            object_id=store.id,
            updated_at__gte=thirty_days_ago
        ).exists()
        
        customer_emails = RetailStoreCustomer.objects.filter(store=store).values_list('email', flat=True)
        has_recent_quote = False
        if customer_emails:
            has_recent_quote = Quotation.objects.filter(
                shop=shop,
                client_email__in=customer_emails,
                created_at__gte=thirty_days_ago
            ).exists()
            
        if not (has_recent_activity or has_recent_note or has_recent_task or has_recent_quote):
            candidates.append({
                'type': 'inactive_company',
                'severity': 'medium',
                'title': f"Inactive Company: {store.name}",
                'description': f"Company '{store.name}' has had no CRM activity or quotations recorded in the last 30 days.",
                'entity_type': 'company',
                'entity_id': str(store.id),
                'score': 30.0
            })

    # -------------------------------------------------------------
    # RULE 5: High Value Opportunity
    # Leads in negotiation/proposal stages worth >= ₹5 Lakhs.
    # -------------------------------------------------------------
    high_value_leads = WholesaleLead.objects.filter(
        shop=shop,
        stage__in=['negotiation', 'proposal_sent', 'meeting_scheduled'],
        expected_deal_value__gte=500000
    )
    
    for lead in high_value_leads:
        val = float(lead.expected_deal_value or 0)
        score = 90.0 + min(val / 100000.0, 10.0)
        candidates.append({
            'type': 'high_value_opportunity',
            'severity': 'critical',
            'title': f"High Value Opportunity: {lead.company_name}",
            'description': f"Lead '{lead.company_name}' is a high-value opportunity valued at ₹{lead.expected_deal_value} currently in the '{lead.get_stage_display()}' stage.",
            'entity_type': 'lead',
            'entity_id': str(lead.id),
            'score': score
        })

    # -------------------------------------------------------------
    # RULE 6: Revenue Decline
    # Retail stores whose trailing 30-day orders revenue is >= 20% lower than preceding 30-day (30-60 day) order revenue.
    # -------------------------------------------------------------
    t30_start = now - timedelta(days=30)
    p30_start = now - timedelta(days=60)
    
    for store in RetailStore.objects.filter(shop=shop, is_active=True):
        customers = RetailStoreCustomer.objects.filter(store=store)
        emails = [c.email for c in customers if c.email]
        phones = [c.phone for c in customers if c.phone]
        
        if not (emails or phones):
            continue
            
        o_filter = Q(org_id=shop.organization_id)
        sub_filter = Q()
        if emails and phones:
            sub_filter = Q(contact_email__in=emails) | Q(contact_phone__in=phones)
        elif emails:
            sub_filter = Q(contact_email__in=emails)
        elif phones:
            sub_filter = Q(contact_phone__in=phones)
            
        store_orders = Order.objects.filter(o_filter).filter(sub_filter)
        
        t30_revenue = store_orders.filter(created_at__gte=t30_start).aggregate(total=Sum('total_price'))['total'] or 0
        p30_revenue = store_orders.filter(created_at__gte=p30_start, created_at__lt=t30_start).aggregate(total=Sum('total_price'))['total'] or 0
        
        if p30_revenue > 0:
            decline_percent = (float(p30_revenue) - float(t30_revenue)) / float(p30_revenue)
            if decline_percent >= 0.20:
                score = 80.0 + min(decline_percent * 20.0, 20.0)
                candidates.append({
                    'type': 'revenue_decline',
                    'severity': 'critical',
                    'title': f"Revenue Decline: {store.name}",
                    'description': f"Store '{store.name}' has shown a {round(decline_percent * 100)}% revenue decline over the last 30 days (₹{round(t30_revenue, 2)} vs ₹{round(p30_revenue, 2)} in the preceding period).",
                    'entity_type': 'company',
                    'entity_id': str(store.id),
                    'score': score
                })

    # -------------------------------------------------------------
    # RECONCILIATION
    # Compare generated candidates against existing recommendations.
    # -------------------------------------------------------------
    existing_recs = Recommendation.objects.filter(shop=shop).exclude(status='resolved')
    existing_lookup = {
        (rec.type, rec.entity_type, rec.entity_id): rec
        for rec in existing_recs
    }
    
    still_valid_ids = set()
    created_count = 0
    
    for cand in candidates:
        key = (cand['type'], cand['entity_type'], cand['entity_id'])
        if key in existing_lookup:
            rec = existing_lookup[key]
            if rec.status == 'active':
                rec.title = cand['title']
                rec.description = cand['description']
                rec.score = cand['score']
                rec.severity = cand['severity']
                rec.save()
            still_valid_ids.add(rec.id)
        else:
            new_rec = Recommendation.objects.create(
                shop=shop,
                type=cand['type'],
                severity=cand['severity'],
                title=cand['title'],
                description=cand['description'],
                entity_type=cand['entity_type'],
                entity_id=cand['entity_id'],
                score=cand['score'],
                status='active'
            )
            created_count += 1
            still_valid_ids.add(new_rec.id)
            
            # Send notification to shop owner
            if shop.owner:
                try:
                    from core.services.notifications import push_unified_notification
                    push_unified_notification(
                        recipient=shop.owner,
                        actor=None,
                        module='tasks',
                        action='reminder',
                        title=f"New recommendation: {new_rec.title}",
                        message=new_rec.description,
                        entity_type=new_rec.entity_type,
                        entity_id=new_rec.entity_id,
                        metadata={'category': 'recommendation_generated'}
                    )
                except Exception:
                    pass
            
    # Resolve any existing active recommendations that are no longer true
    to_resolve = Recommendation.objects.filter(
        shop=shop,
        status='active'
    ).exclude(
        id__in=still_valid_ids
    )
    
    resolved_count = to_resolve.count()
    to_resolve.update(status='resolved')
    
    return created_count, resolved_count
