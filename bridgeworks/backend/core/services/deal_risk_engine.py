import logging
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
from core.models.revenue_intelligence import DealRisk
from core.models.cases import CaseFile

logger = logging.getLogger(__name__)

def calculate_lead_risk(lead, lead_ct):
    """Calculates risk score (0-100) and factors for a WholesaleLead."""
    score = 0
    factors = []
    now = timezone.now()

    # 1. Stagnation: no CRM activity/tasks/notes logged recently
    last_touch = lead.updated_at
    recent_act = CRMActivity.objects.filter(content_type=lead_ct, object_id=lead.id).first()
    if recent_act and recent_act.created_at > last_touch:
        last_touch = recent_act.created_at
        
    days_since_touch = (now - last_touch).days
    if days_since_touch >= 14:
        score += 40
        factors.append(f"Stale: No activity logged in the last {days_since_touch} days.")
    elif days_since_touch >= 7:
        score += 20
        factors.append("Inactive: No activity logged in the last 7 days.")

    # 2. Stage stuckness
    if lead.stage in ('proposal_sent', 'negotiation'):
        # Check how long it has been since stage change
        stage_change = CRMActivity.objects.filter(
            content_type=lead_ct, object_id=lead.id, activity_type='stage_change'
        ).first()
        if stage_change:
            days_stuck = (now - stage_change.created_at).days
            if days_stuck >= 15:
                score += 25
                factors.append(f"Stuck Opportunity: In '{lead.get_stage_display()}' stage for {days_stuck} days.")

    # 3. Task overdue status
    pending_tasks = CRMTask.objects.filter(content_type=lead_ct, object_id=lead.id, status='pending')
    overdue_count = pending_tasks.filter(due_date__lt=date.today()).count()
    if overdue_count > 0:
        score += 20
        factors.append(f"Overdue Tasks: Has {overdue_count} pending checklist tasks past due date.")
    elif not pending_tasks.exists():
        score += 10
        factors.append("No Next Actions: Zero pending CRM tasks assigned.")

    # 4. Low estimated monthly value vs expected value ratio
    if lead.expected_deal_value and lead.estimated_monthly_value:
        ratio = float(lead.estimated_monthly_value) / float(lead.expected_deal_value)
        if ratio < 0.05:
            score += 15
            factors.append("Low Yield Opportunity: Expected deal value has extremely low estimated monthly yield.")

    return min(100, score), factors


def calculate_quote_risk(quote, quote_ct):
    """Calculates risk score (0-100) and factors for a Quotation."""
    score = 0
    factors = []
    now = timezone.now()

    # 1. Expiration
    if quote.valid_until:
        if quote.valid_until < date.today():
            score += 40
            factors.append("Expired: Quotation is past its valid-until date.")
        elif quote.valid_until <= date.today() + timedelta(days=2):
            score += 25
            factors.append(f"Expiring Soon: Validity period expires on {quote.valid_until}.")

    # 2. Stuck in Approval
    if quote.status == 'pending_approval':
        # Check approval creation age
        from core.models.approval import ApprovalRequest
        req = ApprovalRequest.objects.filter(entity_type='quote', entity_id=str(quote.id), status='pending').first()
        if req:
            days_in_approval = (now - req.created_at).days
            if days_in_approval >= 3:
                score += 20
                factors.append(f"Delayed Approval: Pending internal review for {days_in_approval} days.")

    # 3. High discount percentage check
    # Check total value vs sum of items retail values
    total_base = 0.0
    for item in (quote.items or []):
        qty = item.get('qty', 1)
        price = item.get('unit_price', 0)
        total_base += float(qty) * float(price)
        
    if total_base > 0:
        discount = (total_base - float(quote.total_value)) / total_base
        if discount >= 0.25:
            score += 25
            factors.append(f"High Discount Risk: Total discount rate of {round(discount * 100)}% applied.")

    # 4. Inactivity
    recent_act = CRMActivity.objects.filter(content_type=quote_ct, object_id=quote.id, created_at__gte=now - timedelta(days=7)).exists()
    if not recent_act:
        score += 15
        factors.append("Unfollowed: No customer interactions logged in the last 7 days.")

    return min(100, score), factors


def calculate_company_risk(store, store_ct, shop):
    """Calculates risk score (0-100) and factors for a RetailStore (Company)."""
    score = 0
    factors = []
    now = timezone.now()

    # 1. Revenue Decline
    t30_start = now - timedelta(days=30)
    p30_start = now - timedelta(days=60)
    customers = RetailStoreCustomer.objects.filter(store=store)
    emails = [c.email for c in customers if c.email]
    phones = [c.phone for c in customers if c.phone]
    
    if emails or phones:
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
                score += 40
                factors.append(f"Revenue Drop: Revenue declined by {round(decline_percent * 100)}% over last 30 days.")

    # 2. Activity / Quotation absence
    thirty_days_ago = now - timedelta(days=30)
    has_recent_activity = CRMActivity.objects.filter(
        content_type=store_ct, object_id=store.id, created_at__gte=thirty_days_ago
    ).exists()
    
    has_recent_quote = False
    if emails:
        has_recent_quote = Quotation.objects.filter(
            shop=shop, client_email__in=emails, created_at__gte=thirty_days_ago
        ).exists()
        
    if not (has_recent_activity or has_recent_quote):
        score += 35
        factors.append("Inactive Account: No activities or new quotations in the last 30 days.")

    # 3. Support Issues Open
    # Issues can be mapped via CaseFile models related to customer/store emails
    if emails:
        open_cases = CaseFile.objects.filter(
            org_id=shop.organization_id,
            status='open',
            created_at__lt=now - timedelta(days=5)
        ).filter(Q(customer_email__in=emails) | Q(customer_name__icontains=store.name)).count()
        if open_cases > 0:
            score += 25
            factors.append(f"Unresolved Support Tickets: {open_cases} open cases older than 5 days.")

    return min(100, score), factors


def calculate_deal_risks_for_shop(shop):
    """
    Main runner to recalculate risk scores across all open leads, quotes, and active companies.
    """
    lead_ct = ContentType.objects.get_for_model(WholesaleLead)
    quote_ct = ContentType.objects.get_for_model(Quotation)
    store_ct = ContentType.objects.get_for_model(RetailStore)

    recs_updated = 0

    # 1. Calculate for Leads
    open_leads = WholesaleLead.objects.filter(shop=shop).exclude(stage__in=['closed_won', 'closed_lost'])
    for lead in open_leads:
        score, factors = calculate_lead_risk(lead, lead_ct)
        DealRisk.objects.update_or_create(
            shop=shop, entity_type='lead', entity_id=str(lead.id),
            defaults={'risk_score': score, 'risk_factors': factors}
        )
        recs_updated += 1

    # 2. Calculate for Quotes
    open_quotes = Quotation.objects.filter(shop=shop).filter(
        status__in=['draft', 'pending_approval', 'sent', 'negotiation']
    )
    for quote in open_quotes:
        score, factors = calculate_quote_risk(quote, quote_ct)
        DealRisk.objects.update_or_create(
            shop=shop, entity_type='quote', entity_id=str(quote.id),
            defaults={'risk_score': score, 'risk_factors': factors}
        )
        recs_updated += 1

    # 3. Calculate for Companies
    active_stores = RetailStore.objects.filter(shop=shop, is_active=True)
    for store in active_stores:
        score, factors = calculate_company_risk(store, store_ct, shop)
        DealRisk.objects.update_or_create(
            shop=shop, entity_type='company', entity_id=str(store.id),
            defaults={'risk_score': score, 'risk_factors': factors}
        )
        recs_updated += 1

    return recs_updated
