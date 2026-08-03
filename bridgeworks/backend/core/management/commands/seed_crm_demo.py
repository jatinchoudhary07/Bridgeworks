"""
Management command: seed_crm_demo
Seeds realistic demo data for all Sales & CRM modules.

Usage:
  python manage.py seed_crm_demo
  python manage.py seed_crm_demo --flush
  python manage.py seed_crm_demo --leads 30 --quotes 20
"""

import random
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

User = get_user_model()

COMPANY_NAMES = [
    "Apex Retail Solutions", "BlueStar Distribution", "CoreTech Enterprises",
    "Delta Commerce Group", "EagleEye Wholesale", "Frontier Goods Ltd",
    "Gemstone Trading Co", "Horizon Retail Partners", "Indus Valley Traders",
    "Jade Pacific Inc", "Kiran Exports", "Luxe Merchandise Hub",
    "Metro Supply Chain", "Nexus Wholesale", "Orbit Distributors",
    "Pioneer Trading House", "Quest Retail Group", "Regal Commerce",
    "Stellar Supply Co", "Titan Industries", "Unified Traders",
    "Vertex Wholesale", "Windsor Distribution", "Xenith Retail",
    "Yonder Commerce", "Zenith Merchandise",
]

CONTACT_NAMES = [
    "Arjun Sharma", "Priya Mehta", "Rohit Verma", "Sneha Patel",
    "Vikram Singh", "Anita Kapoor", "Deepak Joshi", "Kavya Nair",
    "Manish Gupta", "Neha Iyer", "Rajesh Bose", "Sunita Rao",
    "Tarun Malhotra", "Usha Krishnan", "Vivek Khanna",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune",
    "Kolkata", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kochi",
]

INDUSTRIES = [
    "FMCG", "Fashion & Apparel", "Electronics", "Home Furnishings",
    "Food & Beverage", "Healthcare Products", "Sporting Goods",
    "Consumer Goods", "Beauty & Wellness", "Industrial Equipment",
]

STAGES = [
    'cold_lead', 'contacted', 'meeting_scheduled',
    'proposal_sent', 'negotiation', 'agreement_signed',
    'closed_won', 'closed_lost',
]

QUOTE_STATUSES = [
    'draft', 'pending_approval', 'sent', 'negotiation', 'accepted',
    'rejected', 'expired',
]

PRODUCT_CATALOGUE = [
    {"sku": "SKU-001", "title": "Premium Cotton T-Shirts (Pack of 12)", "unit_price": 480},
    {"sku": "SKU-002", "title": "Denim Jeans Assorted (Pack of 6)", "unit_price": 1200},
    {"sku": "SKU-003", "title": "Linen Kurta Set (Pack of 10)", "unit_price": 750},
    {"sku": "SKU-004", "title": "Woolen Sweaters (Pack of 8)", "unit_price": 950},
    {"sku": "SKU-005", "title": "Ethnic Wear Dupatta (Pack of 20)", "unit_price": 320},
    {"sku": "SKU-006", "title": "Athletic Track Pants (Pack of 12)", "unit_price": 560},
    {"sku": "SKU-007", "title": "Summer Dress Collection (Pack of 6)", "unit_price": 1450},
    {"sku": "SKU-008", "title": "Formal Shirt Assortment (Pack of 10)", "unit_price": 890},
    {"sku": "SKU-009", "title": "Kids Wear Combo (Pack of 15)", "unit_price": 390},
    {"sku": "SKU-010", "title": "Accessories Bundle (Pack of 24)", "unit_price": 240},
]

TASK_TITLES = [
    "Send revised pricing sheet",
    "Schedule discovery call",
    "Prepare custom proposal",
    "Follow up on pending samples",
    "Get sign-off on credit terms",
    "Arrange factory/warehouse visit",
    "Submit contract for legal review",
    "Update CRM with call notes",
    "Prepare quarterly business review deck",
    "Confirm delivery timelines with logistics",
]

NOTE_CONTENTS = [
    "Client is expanding their retail footprint to 3 new cities. High growth potential.",
    "Currently sourcing from competitor. Offered 10% better pricing to switch.",
    "Decision maker is the MD directly. No committee approval needed for orders under Rs 10L.",
    "Prefers WhatsApp communication. Very responsive on mornings.",
    "Visited their warehouse. Excellent infrastructure. Can handle large volume orders.",
    "Had a great call today. They are ready to pilot with a small order of Rs 2L.",
    "Credit background check cleared. Can extend Net-30 terms.",
    "Interested in exclusive distribution for their region. Needs board approval.",
    "Key concern: MOQ flexibility. Need to offer smaller initial quantities.",
    "Very interested in our premium range. Requested brand authorization letter.",
]

ACTIVITY_DESCRIPTIONS = [
    "Discovery call completed. Client interested in Q3 bulk procurement.",
    "Email sent with updated catalogue and pricing sheet.",
    "Video meeting held. Discussed MOQ and credit terms.",
    "Product demo conducted at client office. Positive feedback.",
    "Follow-up call after sending samples. Client requested 15% discount.",
    "Contract review meeting scheduled with legal team.",
    "Proposal presentation delivered to procurement committee.",
    "WhatsApp conversation - client confirmed availability for site visit.",
    "Cold outreach email sent. Awaiting response.",
    "Follow-up scheduled for next week post-holiday.",
]


class Command(BaseCommand):
    help = "Seed realistic CRM and Sales demo data"

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true', help='Clear existing CRM data before seeding')
        parser.add_argument('--leads', type=int, default=20, help='Number of wholesale leads (default: 20)')
        parser.add_argument('--quotes', type=int, default=15, help='Number of quotations (default: 15)')

    def handle(self, *args, **options):
        from core.models import (
            ShopCredentials, WholesaleLead, Quotation,
            RetailStore, RetailStoreCustomer,
            CRMActivity, CRMTask, CRMNote,
            CustomerHealthScore, DealRisk, Recommendation,
            Workflow, WorkflowCondition, WorkflowAction,
        )
        from core.models.sales import (
            WholesaleLeadActivity, WholesaleLeadTask, WholesaleLeadNote,
            QuotationTimeline,
        )

        if options['flush']:
            self.stdout.write("[FLUSH] Clearing existing CRM/Sales data...")
            WholesaleLead.objects.all().delete()
            Quotation.objects.all().delete()
            RetailStore.objects.all().delete()
            CRMActivity.objects.all().delete()
            CRMTask.objects.all().delete()
            CRMNote.objects.all().delete()
            CustomerHealthScore.objects.all().delete()
            DealRisk.objects.all().delete()
            Recommendation.objects.all().delete()
            Workflow.objects.all().delete()
            self.stdout.write(self.style.WARNING("[FLUSH] Done."))

        shop = ShopCredentials.objects.first()
        if not shop:
            self.stdout.write(self.style.ERROR("[ERROR] No ShopCredentials found. Run onboarding first."))
            return

        users = list(User.objects.filter(is_active=True)[:10])
        if not users:
            self.stdout.write(self.style.ERROR("[ERROR] No active users found."))
            return

        shop_label = getattr(shop, 'store_name', None) or getattr(shop, 'organization_id', str(shop.pk))
        self.stdout.write(f"\n[START] Seeding data for shop: {shop_label}")
        self.stdout.write(f"[INFO] Using {len(users)} team members\n")

        # ──────────────────────────────────────────────────────
        # 1. WHOLESALE LEADS
        # ──────────────────────────────────────────────────────
        self.stdout.write("[1/10] Creating Wholesale Leads...")
        leads_created = []
        num_leads = options['leads']

        for i in range(num_leads):
            company = COMPANY_NAMES[i % len(COMPANY_NAMES)]
            if i >= len(COMPANY_NAMES):
                company = f"{company} Group {i // len(COMPANY_NAMES) + 1}"

            stage = random.choices(
                STAGES, weights=[15, 20, 15, 20, 10, 5, 10, 5], k=1
            )[0]
            days_ago = random.randint(1, 180)
            created_dt = timezone.now() - datetime.timedelta(days=days_ago)
            last_contact = (timezone.now() - datetime.timedelta(days=random.randint(0, days_ago))).date()

            lead = WholesaleLead.objects.create(
                shop=shop,
                company_name=company,
                contact_person=random.choice(CONTACT_NAMES),
                contact_designation=random.choice([
                    "CEO", "MD", "Procurement Head", "Purchase Manager",
                    "Director", "VP Sales", "Regional Head",
                ]),
                phone=f"+91 9{random.randint(100000000, 999999999)}",
                email=f"contact{i+1}@example{i+1}.com",
                city=random.choice(CITIES),
                category=random.choice(['domestic', 'international']),
                company_size=random.choice(['small', 'medium', 'large', 'enterprise']),
                mode_of_operations=random.choice(['manufacturer', 'distributor', 'retailer', 'trader']),
                industry=random.choice(INDUSTRIES),
                estimated_monthly_value=Decimal(str(random.randint(50000, 2000000))),
                expected_deal_value=Decimal(str(random.randint(200000, 15000000))),
                credit_terms=random.choice(['Net-30', 'Net-45', 'Net-60', '50% Advance', 'Full Advance']),
                stage=stage,
                notes=f"Initial contact via trade show. Interested in bulk orders for {random.choice(INDUSTRIES)} vertical.",
                last_contact_date=last_contact,
                created_by=random.choice(users),
            )
            WholesaleLead.objects.filter(pk=lead.pk).update(created_at=created_dt, updated_at=created_dt)
            leads_created.append(lead)

            # Legacy activities
            for _ in range(random.randint(1, 3)):
                act_type = random.choice(['call', 'email', 'meeting', 'stage_change'])
                WholesaleLeadActivity.objects.create(
                    lead=lead,
                    activity_type=act_type,
                    description=f"{act_type.replace('_', ' ').title()}: Discussed pricing and catalogue.",
                    details={"duration_mins": random.randint(10, 60)} if act_type == 'call' else {},
                    created_by=random.choice(users),
                )

            # Legacy tasks
            for _ in range(random.randint(1, 2)):
                WholesaleLeadTask.objects.create(
                    lead=lead,
                    title=random.choice(TASK_TITLES),
                    due_date=(timezone.now() + datetime.timedelta(days=random.randint(-5, 30))).date(),
                    priority=random.choice(['low', 'medium', 'high']),
                    status=random.choice(['pending', 'completed']),
                    assignee=random.choice(users),
                    created_by=random.choice(users),
                )

            # Legacy note
            WholesaleLeadNote.objects.create(
                lead=lead,
                content=random.choice(NOTE_CONTENTS),
                created_by=random.choice(users),
            )

        self.stdout.write(self.style.SUCCESS(f"   OK: {len(leads_created)} wholesale leads"))

        # ──────────────────────────────────────────────────────
        # 2. QUOTATIONS
        # ──────────────────────────────────────────────────────
        self.stdout.write("[2/10] Creating Quotations...")
        quotes_created = []

        for i in range(options['quotes']):
            num_items = random.randint(2, 5)
            selected_products = random.sample(PRODUCT_CATALOGUE, num_items)
            items = []
            total = Decimal('0')
            for p in selected_products:
                qty = random.randint(10, 200)
                unit_price = Decimal(str(round(p['unit_price'] * random.uniform(0.9, 1.15), 2)))
                line_total = unit_price * qty
                items.append({
                    "sku": p["sku"], "title": p["title"], "qty": qty,
                    "unit_price": float(unit_price), "line_total": float(line_total),
                })
                total += line_total

            status = random.choices(
                QUOTE_STATUSES, weights=[20, 15, 25, 10, 15, 10, 5], k=1
            )[0]
            days_ago = random.randint(0, 120)
            creator = random.choice(users)
            client_name = random.choice(COMPANY_NAMES)

            quote = Quotation.objects.create(
                shop=shop,
                quote_number=f"QT-{timezone.now().year}-{1000 + i}",
                client_name=client_name,
                client_email=f"accounts@quoteclient{i+1}.com",
                items=items,
                total_value=total,
                status=status,
                valid_until=(timezone.now() + datetime.timedelta(days=random.randint(-10, 60))).date(),
                notes=f"Quote for {random.choice(['seasonal procurement', 'annual contract', 'pilot order', 'strategic partnership'])}.",
                version=random.randint(1, 3),
                created_by=creator,
            )
            created_dt = timezone.now() - datetime.timedelta(days=days_ago)
            Quotation.objects.filter(pk=quote.pk).update(created_at=created_dt, updated_at=created_dt)
            quotes_created.append(quote)

            # Timeline
            actions = ['created', 'reviewed', 'sent_to_client']
            if status in ('pending_approval', 'accepted', 'rejected'):
                actions.append('submitted_for_approval')
            if status == 'accepted':
                actions += ['approved_by_manager', 'accepted_by_client']
            if status == 'negotiation':
                actions.append('client_requested_revision')
            for action in actions:
                QuotationTimeline.objects.create(
                    quotation=quote, action=action,
                    details=action.replace('_', ' ').title(), created_by=creator,
                )

        self.stdout.write(self.style.SUCCESS(f"   OK: {len(quotes_created)} quotations"))

        # ──────────────────────────────────────────────────────
        # 3. RETAIL STORES
        # ──────────────────────────────────────────────────────
        self.stdout.write("[3/10] Creating Retail Stores...")
        store_defs = [
            ("Flagship Store", "Mumbai"),
            ("Delhi Central Store", "Delhi"),
            ("Bangalore Gallery", "Bangalore"),
            ("Chennai Showroom", "Chennai"),
            ("Pune Experience Center", "Pune"),
            ("Hyderabad Hub", "Hyderabad"),
        ]
        stores_created = []
        streets = ['MG Road', 'Linking Road', 'Brigade Road', 'Commercial Street', 'FC Road', 'Anna Salai']
        for name, city in store_defs:
            store = RetailStore.objects.create(
                shop=shop,
                name=name,
                location=f"Plot {random.randint(10, 999)}, {random.choice(streets)}, {city}",
                city=city,
                manager_name=random.choice(CONTACT_NAMES),
                manager_phone=f"+91 9{random.randint(100000000, 999999999)}",
                is_active=True,
            )
            stores_created.append(store)
            for _ in range(random.randint(10, 25)):
                funnel = random.choices(
                    ['view_only', 'purchase_intent', 'asked_pricing', 'initiated_billing', 'purchased'],
                    weights=[30, 25, 20, 15, 10], k=1
                )[0]
                RetailStoreCustomer.objects.create(
                    store=store,
                    name=random.choice(CONTACT_NAMES) if random.random() > 0.3 else "",
                    phone=f"9{random.randint(100000000, 999999999)}",
                    funnel_stage=funnel,
                    last_visit=(timezone.now() - datetime.timedelta(days=random.randint(0, 60))).date(),
                    visit_count=random.randint(1, 8),
                    notes="Walk-in customer." if funnel == 'view_only' else "Interested in premium range.",
                )
        self.stdout.write(self.style.SUCCESS(f"   OK: {len(stores_created)} retail stores"))

        # ──────────────────────────────────────────────────────
        # 4. CRM ACTIVITIES (Generic GFK)
        # ──────────────────────────────────────────────────────
        self.stdout.write("[4/10] Creating CRM Activities...")
        crm_act_count = 0
        if leads_created:
            lead_ct = ContentType.objects.get_for_model(WholesaleLead)
            sample = random.sample(leads_created, min(len(leads_created), 15))
            for lead in sample:
                for _ in range(random.randint(1, 4)):
                    act_type = random.choice(['call', 'email', 'meeting', 'stage_change'])
                    CRMActivity.objects.create(
                        content_type=lead_ct, object_id=lead.id,
                        activity_type=act_type,
                        description=random.choice(ACTIVITY_DESCRIPTIONS),
                        created_by=random.choice(users),
                    )
                    crm_act_count += 1
        self.stdout.write(self.style.SUCCESS(f"   OK: {crm_act_count} CRM activities"))

        # ──────────────────────────────────────────────────────
        # 5. CRM TASKS (Generic GFK)
        # ──────────────────────────────────────────────────────
        self.stdout.write("[5/10] Creating CRM Tasks...")
        crm_task_count = 0
        if leads_created:
            lead_ct = ContentType.objects.get_for_model(WholesaleLead)
            sample = random.sample(leads_created, min(len(leads_created), 12))
            for lead in sample:
                CRMTask.objects.create(
                    content_type=lead_ct, object_id=lead.id,
                    title=random.choice(TASK_TITLES),
                    description="Action item from last meeting.",
                    due_date=(timezone.now() + datetime.timedelta(days=random.randint(-5, 21))).date(),
                    priority=random.choice(['low', 'medium', 'high']),
                    status=random.choice(['pending', 'completed']),
                    assignee=random.choice(users),
                    created_by=random.choice(users),
                )
                crm_task_count += 1
        self.stdout.write(self.style.SUCCESS(f"   OK: {crm_task_count} CRM tasks"))

        # ──────────────────────────────────────────────────────
        # 6. CRM NOTES (Generic GFK)
        # ──────────────────────────────────────────────────────
        self.stdout.write("[6/10] Creating CRM Notes...")
        crm_note_count = 0
        if leads_created:
            lead_ct = ContentType.objects.get_for_model(WholesaleLead)
            sample = random.sample(leads_created, min(len(leads_created), 10))
            for lead in sample:
                CRMNote.objects.create(
                    content_type=lead_ct, object_id=lead.id,
                    content=random.choice(NOTE_CONTENTS),
                    created_by=random.choice(users),
                )
                crm_note_count += 1
        self.stdout.write(self.style.SUCCESS(f"   OK: {crm_note_count} CRM notes"))

        # ──────────────────────────────────────────────────────
        # 7. CUSTOMER HEALTH SCORES
        # ──────────────────────────────────────────────────────
        self.stdout.write("[7/10] Creating Customer Health Scores...")
        health_count = 0
        if leads_created:
            lead_ct = ContentType.objects.get_for_model(WholesaleLead)
            sample = random.sample(leads_created, min(len(leads_created), 12))
            for lead in sample:
                score = random.randint(20, 98)
                churn_risk = (
                    'low' if score >= 75 else
                    'medium' if score >= 50 else
                    'high' if score >= 30 else
                    'critical'
                )
                try:
                    CustomerHealthScore.objects.get_or_create(
                        shop=shop, content_type=lead_ct, object_id=lead.id,
                        defaults={
                            'health_score': score,
                            'engagement_score': random.randint(20, 100),
                            'support_ticket_count': random.randint(0, 5),
                            'churn_risk': churn_risk,
                            'metrics': {
                                'last_order_days_ago': random.randint(0, 120),
                                'avg_order_value': random.randint(50000, 500000),
                                'total_orders': random.randint(1, 25),
                            },
                        }
                    )
                    health_count += 1
                except Exception:
                    pass
        self.stdout.write(self.style.SUCCESS(f"   OK: {health_count} health scores"))

        # ──────────────────────────────────────────────────────
        # 8. DEAL RISK SCORES
        # ──────────────────────────────────────────────────────
        self.stdout.write("[8/10] Creating Deal Risk Scores...")
        risk_count = 0
        risk_factors_pool = [
            "No activity in 30+ days",
            "Quote expiring in 7 days",
            "Multiple competitors involved",
            "Decision maker unresponsive",
            "Budget not confirmed",
            "Long sales cycle stagnation",
            "Price objection raised",
            "Strong competitor relationship",
        ]
        if quotes_created:
            sample = random.sample(quotes_created, min(len(quotes_created), 10))
            for quote in sample:
                try:
                    DealRisk.objects.get_or_create(
                        shop=shop, entity_type='quote', entity_id=str(quote.id),
                        defaults={
                            'risk_score': random.randint(5, 95),
                            'risk_factors': random.sample(risk_factors_pool, k=random.randint(2, 4)),
                        }
                    )
                    risk_count += 1
                except Exception:
                    pass
        self.stdout.write(self.style.SUCCESS(f"   OK: {risk_count} deal risk scores"))

        # ──────────────────────────────────────────────────────
        # 9. AI RECOMMENDATIONS
        # ──────────────────────────────────────────────────────
        self.stdout.write("[9/10] Creating AI Recommendations...")
        rec_specs = [
            ('stale_lead', 'high', 'Re-engage Stale Lead',
             'This lead has not been contacted in 45+ days. Immediate follow-up recommended.', 'lead'),
            ('expiring_quote', 'critical', 'Quote Expiring Soon',
             f'QT-{timezone.now().year}-1003 expires in 5 days. Send a renewal or follow up with the client.', 'quotation'),
            ('overdue_task', 'medium', 'Overdue Task Alert',
             '3 tasks are overdue and have not been actioned. Assign or reschedule.', 'lead'),
            ('high_value_opportunity', 'high', 'High-Value Lead Identified',
             'Nexus Wholesale has a potential deal value of Rs 45L. Prioritize engagement.', 'lead'),
            ('inactive_company', 'medium', 'Inactive Company Detected',
             'BlueStar Distribution has had no activity for 60 days. Risk of losing relationship.', 'lead'),
            ('revenue_decline', 'high', 'Revenue Decline Alert',
             'Q2 wholesale revenue is 23% below target. Review pipeline and accelerate deals.', 'quotation'),
        ]
        for rec_type, severity, title, description, entity_type in rec_specs:
            entity_id = (
                str(random.choice(leads_created).id) if entity_type == 'lead' and leads_created
                else str(random.choice(quotes_created).id) if quotes_created else '1'
            )
            Recommendation.objects.create(
                shop=shop, type=rec_type, severity=severity,
                title=title, description=description,
                entity_type=entity_type, entity_id=entity_id,
                score=random.randint(60, 99), status='active',
            )
        self.stdout.write(self.style.SUCCESS(f"   OK: {len(rec_specs)} AI recommendations"))

        # ──────────────────────────────────────────────────────
        # 10. WORKFLOW AUTOMATIONS
        # ──────────────────────────────────────────────────────
        self.stdout.write("[10/10] Creating Workflow Automations...")
        workflows_spec = [
            {
                "name": "New Lead Auto-Task",
                "description": "When a new B2B lead is created, create an initial follow-up task within 24 hours.",
                "is_active": True,
                "conditions": [],
                "actions": [{"action_type": "create_task", "configuration": {"title": "Initial follow-up call", "due_days": 1, "priority": "high"}}],
            },
            {
                "name": "Quote Accepted Notification",
                "description": "Notify the sales team when a quote is accepted by the client.",
                "is_active": True,
                "conditions": [{"field_name": "status", "operator": "equals", "value": "accepted"}],
                "actions": [{"action_type": "send_notification", "configuration": {"message": "Quote accepted! Time to prepare the order."}}],
            },
            {
                "name": "Stale Lead Re-engagement",
                "description": "Create a follow-up activity when leads have no activity for 30+ days.",
                "is_active": True,
                "conditions": [{"field_name": "days_since_activity", "operator": "greater_than", "value": "30"}],
                "actions": [{"action_type": "create_activity", "configuration": {"type": "follow_up", "description": "Auto-triggered 30-day re-engagement."}}],
            },
            {
                "name": "High Value Lead Priority Alert",
                "description": "Create a high-priority task when a lead with deal value > Rs 10L is created.",
                "is_active": False,
                "conditions": [{"field_name": "expected_deal_value", "operator": "greater_than", "value": "1000000"}],
                "actions": [{"action_type": "create_task", "configuration": {"title": "High-value lead review - escalate to BDM", "priority": "high"}}],
            },
        ]
        wf_count = 0
        for spec in workflows_spec:
            wf = Workflow.objects.create(
                shop=shop, name=spec["name"], description=spec["description"],
                is_active=spec["is_active"], created_by=random.choice(users),
            )
            for cond in spec["conditions"]:
                WorkflowCondition.objects.create(
                    workflow=wf, field_name=cond["field_name"],
                    operator=cond["operator"], value=cond["value"],
                )
            for act in spec["actions"]:
                WorkflowAction.objects.create(
                    workflow=wf, action_type=act["action_type"],
                    configuration=act["configuration"],
                )
            wf_count += 1
        self.stdout.write(self.style.SUCCESS(f"   OK: {wf_count} workflow automations"))

        # ── SUMMARY ──────────────────────────────────────────
        self.stdout.write("\n" + "=" * 55)
        self.stdout.write(self.style.SUCCESS("SUCCESS: CRM Demo Data Seeded!"))
        self.stdout.write("=" * 55)
        self.stdout.write(f"  Wholesale Leads   : {len(leads_created)}")
        self.stdout.write(f"  Quotations        : {len(quotes_created)}")
        self.stdout.write(f"  Retail Stores     : {len(stores_created)}")
        self.stdout.write(f"  CRM Activities    : {crm_act_count}")
        self.stdout.write(f"  CRM Tasks         : {crm_task_count}")
        self.stdout.write(f"  CRM Notes         : {crm_note_count}")
        self.stdout.write(f"  Health Scores     : {health_count}")
        self.stdout.write(f"  Deal Risk Scores  : {risk_count}")
        self.stdout.write(f"  Recommendations   : {len(rec_specs)}")
        self.stdout.write(f"  Workflows         : {wf_count}")
        self.stdout.write("=" * 55)
        self.stdout.write("Visit: http://localhost:5173 -> Sales\n")
