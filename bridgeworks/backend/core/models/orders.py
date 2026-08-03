from django.db import models
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django.conf import settings
from .constants import NDR_STATUSES, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

User = get_user_model()


class OrderQuerySet(models.QuerySet):
    def unfulfilled(self):
        return self.annotate(f_count=Count("fulfillments")).filter(
            Q(f_count=0) | Q(fulfillment_status__isnull=True) | Q(fulfillment_status__iexact="unfulfilled")
        )
    def confirmed(self):
        return self.filter(status='Confirmed')


class RTOBatch(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Batch ID e.g., RTO-20260209-01")
    org_id = models.CharField(max_length=50, db_index=True, blank=True, null=True, help_text="The organization this batch belongs to.")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    STATUS_CHOICES = [('Open', 'Open'), ('Processed', 'Processed')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')

    def __str__(self): return self.name

    class Meta:
        app_label = 'core'


class Order(models.Model):
    org_id = models.CharField(max_length=50, db_index=True, help_text="The Organization ID this order belongs to.")
    customer = models.ForeignKey('core.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    shopify_id = models.BigIntegerField(unique=True)
    order_number = models.IntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    currency = models.CharField(max_length=10, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    subtotal_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_discounts = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    financial_status = models.CharField(max_length=50, null=True, blank=True)
    fulfillment_status = models.CharField(max_length=50, null=True, blank=True)
    contact_email = models.EmailField(max_length=254, null=True, blank=True)
    contact_phone = models.CharField(max_length=30, null=True, blank=True)
    customer_first_name = models.CharField(max_length=100, null=True, blank=True)
    customer_last_name = models.CharField(max_length=100, null=True, blank=True)
    payment_gateway_names = models.JSONField(default=list, blank=True)
    discount_codes = models.JSONField(default=list, blank=True)
    tags = models.CharField(max_length=255, null=True, blank=True)
    previous_order_count = models.IntegerField(default=0)
    shipping_address = models.TextField(null=True, blank=True)
    shipping_state = models.CharField(max_length=100, null=True, blank=True, help_text="State extracted from Shipway PII")
    shipping_pincode = models.CharField(max_length=10, null=True, blank=True, help_text="Pincode/ZIP extracted from Shipway PII")
    billing_address = models.TextField(null=True, blank=True)
    fulfillment_reason = models.CharField(max_length=100, null=True, blank=True)
    hold_history = models.JSONField(default=list, blank=True, help_text="A history of reasons why the order was put on hold.")
    packaged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='packaged_orders')
    packaged_at = models.DateTimeField(null=True, blank=True)
    manifested_at = models.DateTimeField(null=True, blank=True)
    STATUS_CHOICES = [('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Batched', 'Batched'), ('Cancelled', 'Cancelled')]
    status = models.CharField(max_length=64, choices=STATUS_CHOICES, default='Pending', null=True, blank=True)
    INTERNAL_FULFILLMENT_CHOICES = [
        ('Pending', 'Pending'), 
        ('Fulfilled', 'Fulfilled'), 
        ('Sent for Packaging', 'Sent for Packaging'),
        ('Packaged', 'Packaged'), 
        ('On Hold', 'On Hold'),
        ('Manifested', 'Manifested'),
    ]
    internal_fulfillment_status = models.CharField(max_length=64, choices=INTERNAL_FULFILLMENT_CHOICES, default='Pending', help_text="Internal status for the packaging workflow")
    risk_status = models.CharField(max_length=64, null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    call_attempts = models.IntegerField(default=0)
    last_called_at = models.DateTimeField(null=True, blank=True)
    call_history = models.JSONField(default=list, blank=True, help_text="List of call remarks and timestamps")
    call_status = models.CharField(max_length=64, null=True, blank=True, help_text="Current call status (RNR, Busy, etc.)")
    raw_data = models.JSONField(null=True, blank=True)

    is_test_order = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Explicitly marked as a test order. Excluded from auto-confirmation and picklist generation."
    )
    is_auto_confirmed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if confirmed automatically by the AI agent, False if confirmed manually by a user."
    )
    picklist_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when this order was last exported/sent in a picklist email."
    )

    def check_is_test(self) -> bool:
        """
        Returns True if the order matches any test order criteria:
        1. Explicit is_test_order field is True
        2. Total price is 2 digits (between ₹0.01 and ₹99.99)
        3. Shopify tags contain "test" (case-insensitive)
        """
        if self.is_test_order:
            return True
        if self.total_price and 0 < self.total_price < 100:
            return True
        if self.tags:
            tags_lower = self.tags.lower()
            if "test" in tags_lower:
                return True
        return False

    # --- ORDER SOURCE ---
    SOURCE_CHOICES = [
        ('shopify', 'Shopify'),
        ('marketplace', 'Marketplace'),
        ('retail', 'Retail Store'),
        ('b2b', 'B2B'),
        ('manual', 'Manual'),
    ]
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='shopify', db_index=True,
        help_text="Channel/source through which this order was created"
    )
    marketplace_platform = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Marketplace platform name (e.g., Amazon, Flipkart, Meesho) when source=marketplace"
    )

    # --- TRACKING OPTIMIZATION ---
    current_status = models.CharField(max_length=100, blank=True, null=True, db_index=True) 
    current_status_details = models.TextField(blank=True, null=True)
    current_status_date = models.DateTimeField(blank=True, null=True, db_index=True)
    is_ndr = models.BooleanField(default=False, db_index=True)

    # --- RETURN & EXCHANGE TRACKING ---
    return_awb = models.CharField(max_length=100, blank=True, default='', help_text="AWB of the returned items")
    return_shipping_company = models.CharField(max_length=100, blank=True, default='', help_text="Shipping carrier for returns")
    exchange_awb = models.CharField(max_length=100, blank=True, default='', help_text="AWB of the exchange delivery")
    exchange_shipping_company = models.CharField(max_length=100, blank=True, default='', help_text="Shipping carrier for exchange")

    # NOTE: Full-text search is handled via query-time SearchVector annotations
    # in views/orders.py (Postgres only). No stored tsvector column needed.

    confirmed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='confirmed_orders',
        help_text="User who marked the order as confirmed"
    )

    # --- NDR SPECIFIC CALLING FIELDS ---
    ndr_call_status = models.CharField(
        max_length=64, 
        null=True, 
        blank=True, 
        help_text="Status of the NDR call (e.g., 'Will Accept', 'RNR', 'Refused')"
    )
    ndr_remarks = models.TextField(
        null=True, 
        blank=True, 
        help_text="Final remark to be exported for the courier (e.g., 'Please re-attempt on Monday')"
    )
    ndr_call_history = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Log of all NDR call attempts: [{date, status, remark, agent}]"
    )
    ndr_last_called_at = models.DateTimeField(null=True, blank=True)
    ndr_call_attempts = models.IntegerField(default=0)

    # --- NDR AI UPGRADE FIELDS ---
    ndr_reason_category = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Gemini-classified reason category for delivery failure"
    )
    ndr_classification_confidence = models.IntegerField(
        default=0,
        help_text="AI classification confidence score (0-100)"
    )
    ndr_conversion_status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending'), ('CONVERTED', 'Converted'), ('RTO', 'RTO')],
        default='PENDING',
        db_index=True,
        help_text="Funnel conversion status of this NDR"
    )
    ndr_rto_risk_score = models.IntegerField(
        default=0,
        db_index=True,
        help_text="RTO probability score from 0-100 calculated by RTO Scorer"
    )
    ndr_last_scan_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last tracking event"
    )

    # --- NDR ESCALATION ENGINE FIELDS ---
    NDR_ESCALATION_STATUS_CHOICES = [
        ('NONE', 'None'),
        ('ESCALATION_1', 'Escalation 1 (Panel Upload)'),
        ('ESCALATION_2', 'Escalation 2 (Re-escalated)'),
        ('ESCALATION_3', 'Escalation 3 (Re-re-escalated)'),
        ('RTO_CONFIRMED', 'RTO Confirmed'),
        ('DELIVERED', 'Delivered After Escalation'),
    ]
    ndr_escalation_status = models.CharField(
        max_length=20, choices=NDR_ESCALATION_STATUS_CHOICES, default='NONE', db_index=True,
        help_text="Current tier in the BlueDart escalation workflow"
    )
    ndr_escalation_count = models.IntegerField(default=0, help_text="Number of escalation rounds completed")

    @property
    def awb_number(self):
        """Convenience property: fetch AWB from related TrackingInfo."""
        tf = self.fulfillments.first()
        if tf:
            ti = tf.tracking_info.first()
            if ti:
                return ti.number
        return None

    # --- REVERSE LOGISTICS (RTO) FIELDS ---
    RTO_INTERNAL_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Received', 'Received'),
        ('Batched', 'Batched'),
        ('Unpacked', 'Unpacked'),
        ('Restocked', 'Restocked'),
        ('Discarded', 'Discarded'),
    ]
    rto_internal_status = models.CharField(
        max_length=50, 
        choices=RTO_INTERNAL_STATUS_CHOICES, 
        default='Pending', 
        db_index=True
    )
    rto_received_at = models.DateTimeField(null=True, blank=True)
    rto_restocked_at = models.DateTimeField(null=True, blank=True)
    rto_remarks = models.TextField(null=True, blank=True, help_text="Damage or QC remarks")
    rto_batch = models.ForeignKey(
        RTOBatch, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='orders',
        help_text="The processing batch this return belongs to"
    )

    # --- ORDER INTELLIGENCE ENGINE FIELDS ---
    INTELLIGENCE_FLAG_CHOICES = [
        ('NONE', 'Not Analyzed'),
        ('GREEN', 'Green (Low Risk)'),
        ('YELLOW', 'Yellow (Medium Risk)'),
        ('RED', 'Red (High Risk)'),
    ]
    risk_score = models.IntegerField(default=0, help_text="Trust score from 0-100, calculated by the Intelligence Bot")
    intelligence_flag = models.CharField(
        max_length=10, 
        choices=INTELLIGENCE_FLAG_CHOICES, 
        default='NONE', 
        db_index=True,
        help_text="Color-coded risk flag set by the Intelligence Bot"
    )
    system_suggestion = models.TextField(
        blank=True, 
        default='', 
        help_text="Bot-generated recommendation e.g. 'Low Risk: Assign Bluedart'"
    )
    agent_reasoning = models.TextField(
        blank=True,
        default='',
        help_text="Detailed reasoning from the AI agent about this order's risk assessment"
    )
    confirmation_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Why the AI auto-confirmed this order."
    )
    hold_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Why the AI placed the order on hold."
    )
    awb_error = models.TextField(
        blank=True,
        default='',
        help_text="Error message if auto AWB generation/booking failed"
    )

    objects = OrderQuerySet.as_manager()
    
    # --- EXCHANGE ORDER LINKAGE ---
    parent_order = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='exchange_orders',
        help_text="If this is an Exchange order generated by Return Prime, links back to the original Order."
    )
    is_exchange_order = models.BooleanField(default=False, db_index=True)

    def __str__(self): return f"Order #{self.order_number} (Org: {self.org_id})"
    @property
    def is_unfulfilled(self):
        if self.fulfillments.exists(): return False
        return (not self.fulfillment_status) or (self.fulfillment_status.lower() in ["", "null", "unfulfilled"])

    def update_tracking_status(self):
        """
        Calculates the latest tracking status from related TrackingEvents
        and updates the optimized fields (current_status, current_status_date, etc.)
        """
        events = []
        for fulfillment in self.fulfillments.all():
            events.extend(fulfillment.tracking_events.all())

        if not events:
            self.current_status = self.fulfillment_status or "Pending"
            self.current_status_details = ""
            self.current_status_date = None
            self.is_ndr = False
            self.save(update_fields=['current_status', 'current_status_details', 'current_status_date', 'is_ndr'])
            return

        sorted_events = sorted(events, key=lambda x: x.datetime, reverse=True)
        latest_event = sorted_events[0]
        
        status = latest_event.status
        details = latest_event.details or ""
        dt = latest_event.datetime

        self.current_status = status
        self.current_status_details = details
        self.current_status_date = dt

        status_clean = str(status).upper().strip() if status else ""
        details_clean = str(details).upper().strip() if details else ""

        is_ndr_status = status_clean in [s.upper() for s in NDR_STATUSES]
        is_ndr_detail = details_clean in [s.upper() for s in NDR_STATUSES]
        
        is_completed = (
            status_clean == "DELIVERED" or 
            status_clean in [s.upper() for s in RTO_TRANSIT_STATUSES] or 
            status_clean in [s.upper() for s in RTO_DELIVERED_STATUSES] or
            status_clean.startswith("RTO") or 
            status_clean.startswith("RETURN")
        )

        # Check if the order has ever been in an NDR cohort
        was_ndr = self.is_ndr or bool(self.ndr_reason_category) or self.ndr_conversion_status in ['CONVERTED', 'RTO']

        if (is_ndr_status or is_ndr_detail) and not is_completed:
            self.is_ndr = True
            self.ndr_conversion_status = 'PENDING'
        else:
            self.is_ndr = False
            if is_completed and was_ndr:
                if status_clean == "DELIVERED":
                    self.ndr_conversion_status = 'CONVERTED'
                else:
                    self.ndr_conversion_status = 'RTO'

        self.save(update_fields=[
            'current_status', 'current_status_details', 'current_status_date',
            'is_ndr', 'ndr_conversion_status'
        ])

        # Auto-sync shipment record for delivery tracking/COD remittance
        try:
            from core.services.delivery_services import sync_shipment_from_order
            sync_shipment_from_order(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to auto-sync shipment in update_tracking_status for Order #{self.order_number}: {e}"
            )

        # Auto-sync shipment record for delivery tracking/COD remittance
        try:
            from core.services.delivery_services import sync_shipment_from_order
            sync_shipment_from_order(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to auto-sync shipment in update_tracking_status for Order #{self.order_number}: {e}"
            )

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['shipping_pincode', '-created_at'], name='idx_ord_pcode_created'),
            models.Index(fields=['current_status', '-created_at'], name='idx_ord_status_created'),
            models.Index(fields=['shipping_pincode', 'current_status', '-created_at'], name='idx_ord_pcode_stat_created'),
            models.Index(fields=['org_id', 'order_number'], name='idx_ord_org_ordernum'),
            models.Index(fields=['org_id', 'status', 'internal_fulfillment_status'], name='idx_ord_org_stat_ifs'),
        ]


class ReturnRequest(models.Model):
    return_prime_id = models.CharField(max_length=100, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    
    STATUS_CHOICES = [
        ('REQUEST_CREATED', 'Request Created'),
        ('APPROVED', 'Approved'),
        ('RECEIVED', 'Received'),
        ('INSPECTED', 'Inspected'),
        ('REFUNDED', 'Refunded'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='REQUEST_CREATED')
    
    REQUEST_TYPE_CHOICES = [
        ('RETURN', 'Return'),
        ('EXCHANGE', 'Exchange'),
    ]
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='RETURN')
    
    awb_number = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    request_number = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    customer_notes = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(null=True, blank=True, help_text="Stores the full Return Prime JSON payload for this request.")
    
    from django.contrib.auth.models import User
    stocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocked_returns')
    stocked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.request_type} {self.return_prime_id} for {self.order.order_number}"

    class Meta:
        app_label = 'core'


class LineItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='line_items')
    product_id = models.BigIntegerField(null=True, blank=True)
    variant_id = models.BigIntegerField(null=True, blank=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    title = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True, blank=True)
    vendor = models.CharField(max_length=100, null=True, blank=True)
    sku = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self): return f"{self.title} (x{self.quantity}) for Order #{self.order.order_number}"

    @property
    def variant_title(self):
        if self.name and self.title and self.name.startswith(self.title):
            return self.name[len(self.title):].lstrip(' -')
        return self.name or ''

    class Meta:
        app_label = 'core'


class RTOEngineBatch(models.Model):
    """
    Groups orders scanned & dispatched together in one session.
    batch_number is auto-incrementing per org (1, 2, 3 …).
    """
    batch_number = models.PositiveIntegerField(db_index=True)
    org_id = models.CharField(max_length=50, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rto_engine_batches'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = [('org_id', 'batch_number')]
        ordering = ['-created_at']

    @property
    def display_name(self):
        return f"RTO BATCH {self.batch_number}"

    def __str__(self):
        return self.display_name


class RTOEngineItem(models.Model):
    """Tracks each returned order through the RTO Engine QC pipeline."""

    SCAN_STATUS_CHOICES = [
        ('pending_qc', 'Pending QC'),
        ('suspicious', 'Suspicious'),
        ('damaged', 'Damaged'),
        ('qc_passed', 'QC Passed'),
        ('qc_failed', 'QC Failed'),
        ('sent_to_inventory', 'Sent to Inventory'),
        ('under_investigation', 'Under Investigation'),
        ('investigation_resolved', 'Investigation Resolved'),
        ('sent_for_repair', 'Sent for Repair'),
        ('written_off', 'Written Off'),
    ]

    INVESTIGATION_STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    ]

    WRITE_OFF_REASON_CHOICES = [
        ('not_our_product', 'Not Our Product'),
        ('fraud', 'Fraud'),
    ]

    REPAIR_STAGE_CHOICES = [
        ('hand_setting', 'Hand Setting'),
        ('final_polish', 'Final Polish'),
        ('plating', 'Plating'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='rto_engine_items')
    line_item = models.ForeignKey(
        'LineItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rto_engine_entries',
    )
    scan_status = models.CharField(
        max_length=30, choices=SCAN_STATUS_CHOICES, default='pending_qc', db_index=True
    )

    # Scan info
    scanned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rto_engine_scans'
    )
    scanned_at = models.DateTimeField(auto_now_add=True)
    scan_notes = models.TextField(blank=True, null=True)

    # QC info
    qc_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rto_engine_qc'
    )
    qc_at = models.DateTimeField(null=True, blank=True)
    qc_notes = models.TextField(blank=True, null=True)

    # Investigation info
    investigation_notes = models.TextField(blank=True, null=True)
    investigation_status = models.CharField(
        max_length=20, choices=INVESTIGATION_STATUS_CHOICES, default='open', null=True, blank=True
    )
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rto_engine_resolutions'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Others (write-off) reason
    write_off_reason = models.CharField(
        max_length=30, choices=WRITE_OFF_REASON_CHOICES, null=True, blank=True
    )

    # Batch grouping (null = single-order scan, not part of a batch)
    rto_engine_batch = models.ForeignKey(
        'RTOEngineBatch', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items',
    )

    # Repair routing
    repair_stage = models.CharField(
        max_length=30, choices=REPAIR_STAGE_CHOICES, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RTOEngine #{self.pk} Order#{self.order.order_number} [{self.scan_status}]"

    class Meta:
        app_label = 'core'
        ordering = ['-scanned_at']


class Fulfillment(models.Model):
    shopify_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='fulfillments')
    status = models.CharField(max_length=50, null=True, blank=True)
    shipment_status = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    service = models.CharField(max_length=255, null=True, blank=True)
    fulfillment_order_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        app_label = 'core'


class TrackingInfo(models.Model):
    fulfillment = models.ForeignKey(Fulfillment, on_delete=models.CASCADE, related_name='tracking_info')
    company = models.CharField(max_length=255, null=True, blank=True)
    number = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    url = models.URLField(max_length=500, null=True, blank=True)

    class Meta:
        app_label = 'core'


class TrackingEvent(models.Model):
    fulfillment = models.ForeignKey(Fulfillment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=255)
    datetime = models.DateTimeField(db_index=True)
    details = models.CharField(max_length=512, null=True, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-datetime']
        unique_together = ('fulfillment', 'datetime', 'status')
        indexes = [
            models.Index(fields=['status', '-datetime'], name='idx_trk_evt_stat_dt'),
        ]
    
    def __str__(self):
        return f"{self.status} @ {self.datetime}"


# ─── Signals ──────────────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=RTOEngineItem)
def clear_rto_cache_on_item_save(sender, instance, **kwargs):
    if instance.order:
        from django.core.cache import cache
        order = instance.order
        keys = [
            f"rto_scan:ident:{order.order_number}",
            f"rto_scan:ident:{order.id}",
        ]
        
        try:
            if hasattr(order, 'shipment') and order.shipment and order.shipment.awb_number:
                keys.append(f"rto_scan:ident:{order.shipment.awb_number}")
                keys.append(f"rto_scan:ident:{order.shipment.awb_number.upper()}")
        except Exception:
            pass
            
        try:
            ti_numbers = order.fulfillments.values_list('tracking_info__number', flat=True)
            for num in ti_numbers:
                if num:
                    keys.append(f"rto_scan:ident:{num}")
                    keys.append(f"rto_scan:ident:{num.upper()}")
        except Exception:
            pass
            
        cache.delete(f"rto_item_status:order_id:{order.id}")
        cache.delete_many(keys)
