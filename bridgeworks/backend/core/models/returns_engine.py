"""
Returns & Exchange Engine Models — Day 1 Foundation
====================================================
ReturnExchangeCase   — tracks a single return/exchange parcel through the QC pipeline
ReturnExchangeActivity — audit timeline for every status change / action on a case
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ReturnExchangeBatch(models.Model):
    name = models.CharField(max_length=100, help_text="Batch ID e.g., RE-20260603-01")
    org_id = models.CharField(max_length=50, db_index=True, blank=True, null=True, help_text="The organization this batch belongs to.")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    STATUS_CHOICES = [('Open', 'Open'), ('Processed', 'Processed')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'core'
        verbose_name = 'Return Exchange Batch'
        verbose_name_plural = 'Return Exchange Batches'
        ordering = ['-created_at']
        unique_together = [('org_id', 'name')]


class ReturnExchangeCase(models.Model):
    """
    Master tracking record created the moment a parcel is scanned and moved to QC.
    One case per parcel arrival (idempotent — re-scanning returns the same case).
    """

    CASE_TYPE_CHOICES = [
        ('return', 'Return'),
        ('exchange', 'Exchange'),
    ]

    STATUS_CHOICES = [
        ('pending_qc', 'Pending QC'),
        ('refund_pending', 'Refund Pending'),
        ('exchange_pending', 'Exchange Pending'),
        ('exchange_ready', 'Exchange Ready'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('exchange_closed', 'Exchange Closed'),
    ]

    SOURCE_CHOICES = [
        ('return_prime', 'Return Prime'),
        ('self_shipped', 'Self Shipped'),
        ('walk_in', 'Walk-In'),
    ]

    batch = models.ForeignKey(
        'core.ReturnExchangeBatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases',
        help_text='The processing batch this return/exchange belongs to.'
    )
    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        related_name='return_exchange_cases',
        help_text='The original order this return/exchange relates to.',
    )
    customer = models.ForeignKey(
        'core.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='return_exchange_cases',
    )
    case_type = models.CharField(
        max_length=20,
        choices=CASE_TYPE_CHOICES,
        default='return',
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_qc',
        db_index=True,
    )
    remarks = models.TextField(blank=True, default='')

    # How the return parcel arrived — Return Prime pickup, or self-shipped by customer
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='return_prime',
        db_index=True,
        help_text='How the return arrived: via Return Prime pickup, self-shipped by customer, or walk-in.',
    )

    # ── Self-Shipped Fields ───────────────────────────────────────────────────
    # Populated for self_shipped source — when customer sends via their own courier.
    courier_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Courier name when customer self-ships (e.g. DTDC, Blue Dart, India Post).',
    )
    self_shipped_tracking = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Tracking number provided by customer for self-shipped parcel.',
    )
    manual_intake_notes = models.TextField(
        blank=True,
        default='',
        help_text='Notes entered during manual / self-shipped intake.',
    )
    store_location = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Store location for walk-in cases.',
    )
    received_by = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Staff member who received the walk-in / parcel.',
    )
    customer_present = models.BooleanField(
        default=False,
        help_text='True if the customer was present at the store during intake.',
    )
    parcel_received_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date the parcel was received at the warehouse.',
    )
    parcel_condition = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Condition of the parcel upon arrival (e.g., intact, damaged).',
    )
    replacement_product = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Replacement product name for manual intake exchange cases.',
    )
    replacement_product_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Replacement product value for manual intake exchange cases.',
    )
    # ─────────────────────────────────────────────────────────────────────────

    # ── Return-to-Exchange Conversion Fields ─────────────────────────────────
    # Populated when operations converts a refund_pending case to an exchange.
    converted_to_exchange = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True when this case was originally a return that was converted to an exchange.',
    )
    conversion_notes = models.TextField(
        blank=True,
        default='',
        help_text='Reason / notes recorded when the case was converted to an exchange.',
    )
    converted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_exchange_cases',
        help_text='The user who triggered the return-to-exchange conversion.',
    )
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the case was converted to an exchange.',
    )
    conversion_product_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Replacement product details entered during conversion (name, sku, price, variant, qty).',
    )
    # ─────────────────────────────────────────────────────────────────────────

    # The RETURN shipment AWB — assigned by the courier when the customer
    # sends the product back. This is DIFFERENT from the original dispatch AWB
    # stored on the Order / Shipment model.
    return_awb = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text='Courier AWB on the return parcel label (not the original dispatch AWB).',
    )

    # Who created the case (first scanner)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_return_exchange_cases',
    )

    # ── QC Result Fields ──────────────────────────────────────────────────────
    # Populated when an operator submits QC PASS or QC FAIL.

    CONDITION_CHOICES = [
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('missing_parts', 'Missing Parts'),
        ('wrong_product', 'Wrong Product'),
        ('packaging_issue', 'Packaging Issue'),
    ]

    condition = models.CharField(
        max_length=30,
        choices=CONDITION_CHOICES,
        blank=True,
        default='',
        help_text='Physical condition assessed during QC inspection.',
    )
    qc_notes = models.TextField(
        blank=True,
        default='',
        help_text='Inspector notes entered during QC.',
    )
    qc_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qc_completed_cases',
        help_text='The user who performed QC.',
    )
    qc_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when QC was completed.',
    )
    # ─────────────────────────────────────────────────────────────────────────

    # ── Exchange Metadata Fields ──────────────────────────────────────────────
    # Populated at scan/move-to-QC time by reading Return Prime raw_data.
    # Persist throughout the lifecycle so future modules don't re-derive them.

    exchange_exists = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True when Return Prime has already created a replacement order for this exchange.',
    )
    exchange_order_number = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Return Prime exchange order name (e.g. #JANKI40970).',
    )
    exchange_status = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='exchanged_status from Return Prime (e.g. success, pending).',
    )
    replacement_order_number = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Shopify order number for the replacement order (without #).',
    )
    replacement_order_status = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Current fulfillment/shipping status of the replacement order.',
    )
    exchange_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the exchange order was created in Return Prime.',
    )
    exchange_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON bag for replacement_products list and any extra exchange data.',
    )
    # ─────────────────────────────────────────────────────────────────────────

    # ── Refund Fields ─────────────────────────────────────────────────────────
    # Populated when the finance / operations team processes the refund.

    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Final refund amount approved by finance.',
    )
    refund_notes = models.TextField(
        blank=True,
        default='',
        help_text='Finance processing notes for the refund.',
    )
    refund_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when refund was marked as completed.',
    )
    refund_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_completed_cases',
        help_text='The user who completed/approved the refund.',
    )
    refund_rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text='Reason recorded when a refund is rejected.',
    )
    refund_screenshot = models.FileField(
        upload_to='refund_screenshots/',
        null=True,
        blank=True,
        help_text='Payment screenshot/receipt of the processed refund.',
    )
    refund_method = models.CharField(
        max_length=30,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('upi', 'UPI Refund'),
            ('store_credit', 'Store Credit'),
        ],
        default='bank_transfer',
        help_text='The method used to process the refund.',
    )
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Transaction reference code for Bank/UPI refund.',
    )
    wallet_credit_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Store credit reference generated for future wallet integration.',
    )
    # ── Exchange Settlement Fields ──────────────────────────────────────────
    settlement_type = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=[
            ('refund_required', 'Refund Required'),
            ('payment_required', 'Additional Payment Required'),
            ('no_settlement', 'No Settlement Required'),
        ],
        help_text='Type of exchange settlement required.',
    )
    difference_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Computed difference: replacement price - original price.',
    )
    settlement_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Method used for settlement (Refund or Payment).',
    )
    settlement_notes = models.TextField(
        blank=True,
        default='',
        help_text='Notes entered during settlement processing.',
    )
    settlement_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when settlement was finalized.',
    )
    settlement_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_exchange_settlements',
        help_text='The user who finalized the exchange settlement.',
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Transaction reference code or wallet credit code for exchange settlement.',
    )
    # ─────────────────────────────────────────────────────────────────────────

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='idx_rec_status_created'),
            models.Index(fields=['case_type', '-created_at'], name='idx_rec_type_created'),
        ]

    def __str__(self):
        return f"Case #{self.pk} — {self.get_case_type_display()} | Order #{self.order.order_number} [{self.status}]"


class ReturnExchangeActivity(models.Model):
    """
    Immutable audit log — one row per action taken on a ReturnExchangeCase.
    Never updated; only appended.
    """

    ACTION_CHOICES = [
        ('parcel_scanned', 'Parcel Scanned'),
        ('moved_to_qc', 'Moved To QC'),
        ('qc_passed', 'QC Passed'),
        ('qc_failed', 'QC Failed'),
        ('refund_initiated', 'Refund Initiated'),
        ('refund_completed', 'Refund Completed'),
        ('store_credit_issued', 'Store Credit Issued'),
        ('exchange_initiated', 'Exchange Initiated'),
        ('settlement_completed', 'Settlement Completed'),
        ('dispatched', 'Dispatched'),
        ('rejected', 'Rejected'),
        ('note_added', 'Note Added'),
        ('moved_to_exchange_settlement', 'Moved To Exchange Settlement'),
        ('settlement_started', 'Settlement Started'),
        ('refund_processed', 'Refund Difference Processed'),
        ('payment_collected', 'Additional Payment Collected'),
        ('no_settlement_req', 'No Settlement Required'),
        ('exchange_closed', 'Exchange Closed'),
        ('converted_to_exchange', 'Converted To Exchange'),
        ('self_shipped_registered', 'Self Shipped Return Registered'),
        ('self_shipped_case_created', 'Self Shipped Case Created'),
        ('courier_registered', 'Courier Registered'),
        ('parcel_received', 'Parcel Received'),
        ('self_shipped_exchange_created', 'Self Shipped Exchange Created'),
        ('replacement_product_selected', 'Replacement Product Selected'),
        ('walk_in_return_registered', 'Walk In Return Registered'),
        ('received_at_store', 'Received At Store'),
        ('walk_in_exchange_registered', 'Walk In Exchange Registered'),
        ('exchange_creation_started', 'Exchange Creation Started'),
        ('exchange_order_generated', 'Exchange Order Generated'),
        ('shopify_order_created', 'Shopify Order Created'),
        ('return_prime_updated', 'Return Prime Updated'),
        ('exchange_created_successfully', 'Exchange Created Successfully'),
    ]

    case = models.ForeignKey(
        ReturnExchangeCase,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    notes = models.TextField(blank=True, default='')
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='return_exchange_activities',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']  # Timeline order — oldest first

    def __str__(self):
        return f"[{self.case_id}] {self.get_action_display()} @ {self.created_at:%d %b %H:%M}"


# ─── Signals ──────────────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=ReturnExchangeCase)
def clear_scan_cache_on_case_save(sender, instance, created, **kwargs):
    if created and instance.order:
        from django.core.cache import cache
        order = instance.order
        keys = [
            f"returns_scan:ident:{order.order_number}",
            f"returns_scan:ident:{order.id}",
        ]
        
        try:
            rr = order.return_requests.order_by('-created_at').first()
            if rr:
                if rr.awb_number:
                    keys.append(f"returns_scan:ident:{rr.awb_number}")
                    keys.append(f"returns_scan:ident:{rr.awb_number.upper()}")
                if rr.request_number:
                    keys.append(f"returns_scan:ident:{rr.request_number}")
                    keys.append(f"returns_scan:ident:{rr.request_number.upper()}")
                if rr.return_prime_id:
                    keys.append(f"returns_scan:ident:{rr.return_prime_id}")
                    keys.append(f"returns_scan:ident:{rr.return_prime_id.upper()}")
        except Exception:
            pass
            
        if instance.return_awb:
            keys.append(f"returns_scan:ident:{instance.return_awb}")
            keys.append(f"returns_scan:ident:{instance.return_awb.upper()}")
            
        cache.delete(f"return_case_exists:order_id:{order.id}")
        cache.delete_many(keys)
