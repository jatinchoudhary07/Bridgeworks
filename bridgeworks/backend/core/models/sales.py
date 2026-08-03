from django.db import models
from django.contrib.auth import get_user_model
from .store import ShopCredentials

User = get_user_model()


class WholesaleLead(models.Model):
    STAGE_CHOICES = [
        ('cold_lead', 'Cold Lead'),
        ('contacted', 'Contacted'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('proposal_sent', 'Proposal Sent'),
        ('negotiation', 'Negotiation'),
        ('agreement_signed', 'Agreement Signed'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
    ]
    CATEGORY_CHOICES = [
        ('domestic', 'Domestic'),
        ('international', 'International'),
    ]
    COMPANY_SIZE_CHOICES = [
        ('micro', 'Micro (<10 employees)'),
        ('small', 'Small (10-49)'),
        ('medium', 'Medium (50-249)'),
        ('large', 'Large (250-999)'),
        ('enterprise', 'Enterprise (1000+)'),
    ]
    MODE_CHOICES = [
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Distributor'),
        ('retailer', 'Retailer'),
        ('trader', 'Trader'),
        ('other', 'Other'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='wholesale_leads')
    # Basic info
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_designation = models.CharField(max_length=100, blank=True, help_text="Job title of primary contact")
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    # B2B classification
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default='domestic', db_index=True)
    company_size = models.CharField(max_length=20, choices=COMPANY_SIZE_CHOICES, blank=True)
    mode_of_operations = models.CharField(max_length=20, choices=MODE_CHOICES, blank=True)
    industry = models.CharField(max_length=100, blank=True, help_text="Industry or sector of the company")
    # Financial info
    capital = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text="Estimated working capital")
    estimated_monthly_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_deal_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    credit_terms = models.CharField(max_length=100, blank=True, help_text="e.g., Net-30, 50% advance")
    # Business details
    customer_base = models.TextField(blank=True, help_text="Description of their customer base")
    products_interested = models.TextField(blank=True, help_text="Products or categories they are interested in")
    # Pipeline
    stage = models.CharField(max_length=25, choices=STAGE_CHOICES, default='cold_lead', db_index=True)
    notes = models.TextField(blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    last_contact_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.company_name} ({self.stage})"


class RetailStore(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='retail_stores')
    name = models.CharField(max_length=255)
    location = models.TextField(blank=True, help_text="Full address of the store")
    city = models.CharField(max_length=100, blank=True)
    manager_name = models.CharField(max_length=255, blank=True)
    manager_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.city})"


class RetailStoreCustomer(models.Model):
    FUNNEL_STAGE_CHOICES = [
        ('view_only', 'View Only'),
        ('purchase_intent', 'Showed Purchase Intent'),
        ('asked_pricing', 'Asked for Pricing'),
        ('initiated_billing', 'Initiated Billing'),
        ('purchased', 'Purchased'),
    ]

    store = models.ForeignKey(RetailStore, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    funnel_stage = models.CharField(
        max_length=20, choices=FUNNEL_STAGE_CHOICES, default='view_only', db_index=True
    )
    last_visit = models.DateField(null=True, blank=True)
    visit_count = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name or self.phone} @ {self.store.name} ({self.funnel_stage})"


CHANNEL_CHOICES = [
    ('shopify', 'Shopify'),
    ('marketplace', 'Marketplace'),
    ('retail', 'Retail Store'),
    ('b2b', 'B2B Leads'),
    ('wholesale', 'Wholesale CRM'),
]

RECOVERY_STATUS_CHOICES = [
    ('pending', 'Pending Recovery'),
    ('email_sent', 'Email Sent'),
    ('whatsapp_sent', 'WhatsApp Sent'),
    ('recovered', 'Recovered'),
    ('lost', 'Lost'),
]


class AbandonedCart(models.Model):
    RECOVERY_STATUS_CHOICES = RECOVERY_STATUS_CHOICES
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='abandoned_carts')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='shopify', db_index=True)
    channel_meta = models.JSONField(default=dict, blank=True)  # e.g. {"platform":"Amazon"} or {"store_id":3}
    # FlexyPe identifiers
    flexype_checkout_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    session_state = models.CharField(max_length=100, blank=True, default='')  # e.g. "Payment Page", "Address Page"
    # Customer info
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    cart_value = models.DecimalField(max_digits=12, decimal_places=2)
    items_snapshot = models.JSONField(default=list)  # [{sku, title, qty, price}]
    abandoned_at = models.DateTimeField(db_index=True)
    recovery_status = models.CharField(
        max_length=20, choices=RECOVERY_STATUS_CHOICES, default='pending', db_index=True
    )
    last_action_at = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-abandoned_at']

    def __str__(self):
        return f"{self.customer_name or self.customer_email} — ₹{self.cart_value}"


class ChannelDraftOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_MODE_CHOICES = [
        ('prepaid', 'Prepaid'),
        ('cod', 'COD'),
        ('partially_paid', 'Partially Paid'),
    ]
    CUSTOMER_STAGE_CHOICES = [
        ('view_only', 'View Only'),
        ('purchase_intent', 'Purchase Intent'),
        ('asked_pricing', 'Asked Pricing'),
        ('initiated_billing', 'Initiated Billing'),
        ('purchased', 'Purchased'),
    ]
    ORDER_TYPE_CHOICES = [
        ('new', 'New'),
        ('exchange', 'Exchange'),
        ('reship', 'Reship'),
        ('duplicate', 'Duplicate'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='channel_draft_orders')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, db_index=True)
    channel_meta = models.JSONField(default=dict, blank=True)
    # Shopify-specific — blank for non-Shopify channels
    shopify_draft_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    # Customer
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    # Order details
    line_items = models.JSONField(default=list)          # [{title, qty, price}]
    shipping_address = models.JSONField(default=dict, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='prepaid')
    customer_stage = models.CharField(max_length=20, choices=CUSTOMER_STAGE_CHOICES, blank=True, default='', db_index=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='new', db_index=True)
    reference_order_id = models.CharField(max_length=100, blank=True, default='')
    note = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    # Metadata
    invoice_url = models.URLField(null=True, blank=True, max_length=500)
    shopify_created_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.channel}] {self.customer_name or self.customer_email} — ₹{self.total}"


class ChannelAbandonedCheckout(models.Model):
    RECOVERY_STATUS_CHOICES = RECOVERY_STATUS_CHOICES

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='channel_abandoned_checkouts')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, db_index=True)
    channel_meta = models.JSONField(default=dict, blank=True)
    # Shopify-specific
    shopify_token = models.CharField(max_length=100, blank=True, default='', db_index=True)
    checkout_url = models.URLField(blank=True)
    # Customer
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    # Cart details
    cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    item_count = models.PositiveIntegerField(default=0)
    line_items = models.JSONField(default=list)
    # Checkout funnel stage at abandonment
    CHECKOUT_STAGE_CHOICES = [
        ('cart', 'Cart'),
        ('contact_info', 'Contact Info'),
        ('shipping', 'Shipping'),
        ('payment', 'Payment'),
        ('processing', 'Processing'),
    ]
    checkout_stage = models.CharField(
        max_length=20, choices=CHECKOUT_STAGE_CHOICES, default='cart', blank=True, db_index=True
    )
    # Recovery
    recovery_status = models.CharField(
        max_length=20, choices=RECOVERY_STATUS_CHOICES, default='pending', db_index=True
    )
    last_action_at = models.DateTimeField(null=True, blank=True)
    abandoned_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-abandoned_at']
        # Prevent duplicate Shopify checkouts being stored
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'shopify_token'],
                condition=models.Q(shopify_token__gt=''),
                name='unique_shopify_checkout_token',
            )
        ]

    def __str__(self):
        return f"[{self.channel}] {self.customer_name or self.customer_email} — ₹{self.cart_value}"


class MarketplaceCustomer(models.Model):
    """Tracks customer/lead relationships acquired through online marketplace platforms."""
    STAGE_CHOICES = [
        ('new_inquiry', 'New Inquiry'),
        ('negotiating', 'Negotiating'),
        ('sample_requested', 'Sample Requested'),
        ('order_placed', 'Order Placed'),
        ('repeat_buyer', 'Repeat Buyer'),
    ]
    PLATFORM_CHOICES = [
        ('amazon', 'Amazon'),
        ('flipkart', 'Flipkart'),
        ('meesho', 'Meesho'),
        ('myntra', 'Myntra'),
        ('nykaa', 'Nykaa'),
        ('ajio', 'AJIO'),
        ('other', 'Other'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='marketplace_customers')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='amazon', db_index=True)
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='new_inquiry', db_index=True)
    last_activity = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name or self.phone} @ {self.get_platform_display()} ({self.get_stage_display()})"


class Quotation(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('sent', 'Sent'),
        ('negotiation', 'Negotiation'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='quotations')
    quote_number = models.CharField(max_length=50, unique=True)
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField(blank=True)
    items = models.JSONField(default=list)  # [{sku, title, qty, unit_price}]
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='draft', db_index=True)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quote_number} — {self.client_name} (v{self.version})"


class QuotationVersion(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    items = models.JSONField(default=list)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.quotation.quote_number} — v{self.version_number}"


class QuotationTimeline(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='timeline')
    action = models.CharField(max_length=100)  # e.g., 'created', 'submitted_approval', 'approved', 'sent_email', 'negotiated', etc.
    details = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on {self.quotation.quote_number} at {self.created_at}"


class QuotationApprovalHistory(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='approvals')
    status = models.CharField(max_length=50)  # 'approved' or 'rejected'
    comments = models.TextField(blank=True)
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.status} by {self.action_by} for {self.quotation.quote_number}"


class QuotationEmailLog(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='emails')
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Email to {self.recipient_email} re: {self.quotation.quote_number}"



class WholesaleLeadActivity(models.Model):
    ACTIVITY_TYPE_CHOICES = [
        ('call', 'Call Logged'),
        ('email', 'Email Sent'),
        ('meeting', 'Meeting Scheduled'),
        ('stage_change', 'Stage Changed'),
    ]
    lead = models.ForeignKey(WholesaleLead, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField(blank=True, help_text="Summary of what happened")
    details = models.JSONField(default=dict, blank=True, help_text="Structured event properties e.g., call duration, email subject, meeting time")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_activity_type_display()} on {self.lead.company_name}"


class WholesaleLeadTask(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]
    lead = models.ForeignKey(WholesaleLead, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_lead_tasks')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.status}) for {self.lead.company_name}"


class WholesaleLeadNote(models.Model):
    lead = models.ForeignKey(WholesaleLead, on_delete=models.CASCADE, related_name='notes_set')
    content = models.TextField(help_text="Rich text / plaintext note content")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Note by {self.created_by.username if self.created_by else 'Unknown'} on {self.lead.company_name}"


# --- SALES & BD MODULE (DAY 1) ---

class SalesRepresentative(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, null=True, blank=True, related_name='sales_representatives')
    employee_id = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_representative_profile')
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    reporting_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reporting_reps')
    department = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'sales_representatives'
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.employee_id})"


class SalesActivity(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    sales_rep = models.ForeignKey(SalesRepresentative, on_delete=models.CASCADE, related_name='activities')
    customer_name = models.CharField(max_length=255)
    customer_type = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    visit_date = models.DateField()
    remarks = models.TextField(blank=True)
    activities_performed = models.JSONField(default=list, blank=True, help_text="List of activity types performed during the visit")
    image_file = models.FileField(upload_to='sales_activities/images/', null=True, blank=True)
    invoice_file = models.FileField(upload_to='sales_activities/invoices/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_sales_activities')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'sales_activities'
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.sales_rep.full_name} ({self.visit_date})"


class SalesActivityProduct(models.Model):
    sales_activity = models.ForeignKey(SalesActivity, on_delete=models.CASCADE, related_name='products')
    product_id = models.CharField(max_length=255, null=True, blank=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'sales_activity_products'

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class IncentiveRule(models.Model):
    RULE_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('target_bonus', 'Target Bonus'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, null=True, blank=True, related_name='incentive_rules')
    rule_name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    product_id = models.CharField(max_length=255, null=True, blank=True)
    percentage_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'incentive_rules'
        ordering = ['rule_name']

    def __str__(self):
        return f"{self.rule_name} ({self.get_rule_type_display()})"


class IncentiveRecord(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
    ]
    sales_rep = models.ForeignKey(SalesRepresentative, on_delete=models.CASCADE, related_name='incentive_records')
    sales_activity = models.ForeignKey(SalesActivity, on_delete=models.CASCADE, null=True, blank=True, related_name='incentive_records')
    rule = models.ForeignKey(IncentiveRule, on_delete=models.CASCADE, related_name='incentive_records')
    incentive_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'incentive_records'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sales_rep.full_name} - {self.incentive_amount} ({self.status})"


