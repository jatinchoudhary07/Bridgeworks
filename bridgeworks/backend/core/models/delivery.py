"""
delivery.py — Delivery & Logistics Module Models
=================================================
Models:
  - Shipment: Lifecycle tracker for each shipped order
  - CourierRule: Courier allocation engine rules
  - ShipmentCost: Cost breakdown per shipment
  - DeliveryPartner: Partner management
  - CODRemittance: COD collection & remittance tracking
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ==============================================================================
# 1. SHIPMENT (Lifecycle Tracker)
# ==============================================================================
class Shipment(models.Model):
    """
    Logistics-layer view of an Order.
    Links 1:1 to Order and stores delivery-specific metadata.
    Auto-populated via signals when TrackingInfo is created.
    """
    order = models.OneToOneField(
        'core.Order', on_delete=models.CASCADE, related_name='shipment',
        help_text="The source order this shipment tracks."
    )
    org_id = models.CharField(max_length=50, db_index=True)
    awb_number = models.CharField(max_length=100, db_index=True, blank=True, default='')

    COURIER_CHOICES = [
        ('Bluedart', 'Bluedart'),
        ('Delhivery', 'Delhivery'),
        ('Aggregator', 'Aggregator'),
        ('Other', 'Other'),
    ]
    courier_partner = models.CharField(
        max_length=50, choices=COURIER_CHOICES, default='Other', db_index=True
    )

    SHIPPING_MODE_CHOICES = [
        ('Air', 'Air'),
        ('Surface', 'Surface'),
        ('Apex', 'Apex / Air Express'),
    ]
    shipping_mode = models.CharField(
        max_length=10, choices=SHIPPING_MODE_CHOICES, default='Surface'
    )

    ZONE_CHOICES = [
        ('Local', 'Local'),
        ('Intra-City', 'Intra-City'),
        ('Within State', 'Within State'),
        ('Regional', 'Regional'),
        ('Metro', 'Metro-to-Metro'),
        ('National', 'National'),
        ('Special', 'Special / Remote'),
    ]
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES, default='National')

    weight_slab = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.50,
        help_text="Charged weight slab in KG"
    )

    PAYMENT_TYPE_CHOICES = [
        ('COD', 'COD'),
        ('Partially Paid', 'Partially Paid'),
        ('PrePaid', 'PrePaid'),
    ]
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPE_CHOICES, default='PrePaid', db_index=True
    )

    dispatch_date = models.DateTimeField(null=True, blank=True, help_text="When the order was handed to the courier")
    delivery_date = models.DateTimeField(null=True, blank=True, help_text="When the order was delivered to customer")

    STAGE_CHOICES = [
        ('Order', 'Order'),
        ('Packed', 'Packed'),
        ('Manifested', 'Manifested'),
        ('Picked', 'Picked'),
        ('In Transit', 'In Transit'),
        ('OFD', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('RTO', 'RTO'),
        ('Lost', 'Lost'),
    ]
    current_stage = models.CharField(
        max_length=20, choices=STAGE_CHOICES, default='Order', db_index=True
    )

    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Collected', 'Collected'),
        ('Remitted', 'Remitted'),
        ('Not Applicable', 'Not Applicable'),
    ]
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending'
    )

    # Delivery attempt tracking (denormalized for fast aggregation)
    total_delivery_attempts = models.IntegerField(default=0)
    first_attempt_date = models.DateTimeField(null=True, blank=True)
    ndr_reason = models.CharField(max_length=255, blank=True, default='')

    # Hub linkage (auto-populated from CourierZoneMapping.hub_name on dispatch)
    transit_hub = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Courier hub name serving this shipment (e.g., 'Jaipur Hub'). Populated via pincode lookup."
    )

    # Warehouse linkage (for multi-warehouse cost attribution)
    warehouse = models.ForeignKey(
        'core.Warehouse', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shipments', help_text="Origin warehouse for this shipment"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def shipping_state(self):
        return self.order.shipping_state if self.order else ""

    @property
    def shipping_pincode(self):
        return self.order.shipping_pincode if self.order else ""

    @property
    def delivered_at(self):
        return self.delivery_date

    def __str__(self):
        return f"Shipment {self.awb_number} ({self.courier_partner}) → Order #{self.order.order_number}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Auto-calculate costs on save or update
        # Import lazily to avoid circular imports
        try:
            from core.services.zone_engine import calculate_shipment_cost
            calculate_shipment_cost(self, save=True)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to auto-calculate shipment cost for {self.id}: {e}")

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['org_id', 'courier_partner', 'payment_type'], name='idx_shp_org_cour_pay'),
            models.Index(fields=['org_id', 'current_stage', '-dispatch_date'], name='idx_shp_org_stage_disp'),
            models.Index(fields=['org_id', '-dispatch_date'], name='idx_shp_org_dispatch'),
        ]


# ==============================================================================
# 2. COURIER RULE (Allocation Engine)
# ==============================================================================
class CourierRule(models.Model):
    """
    Rule-based courier allocation engine.
    Evaluates conditions to recommend the best courier partner for an order.
    """
    org_id = models.CharField(max_length=50, db_index=True)

    rule_name = models.CharField(max_length=200)

    CONDITION_CHOICES = [
        ('Cheapest', 'Cheapest'),
        ('Fastest', 'Fastest'),
        ('Success Rate', 'Highest Success Rate'),
        ('RTO Risk', 'Lowest RTO Risk'),
        ('COD Allowed', 'COD Allowed'),
    ]
    condition = models.CharField(max_length=30, choices=CONDITION_CHOICES)

    action_courier_partner = models.CharField(
        max_length=100,
        help_text="Courier to assign when this rule matches"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority rules are evaluated first"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.rule_name} → {self.action_courier_partner}"

    class Meta:
        app_label = 'core'
        ordering = ['-priority', 'rule_name']


# ==============================================================================
# 3. SHIPMENT COST (Cost Engine)
# ==============================================================================
class ShipmentCost(models.Model):
    """
    Granular cost breakdown per shipment.
    Supports reconciliation against courier billing invoices.
    """
    shipment = models.OneToOneField(
        Shipment, on_delete=models.CASCADE, related_name='cost'
    )

    forward_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rto_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fuel_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weight_discrepancy_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ndr_reattempt_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Auto-calculated: Forward + (RTO probability * RTO cost)
    true_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="True Cost = Forward + (RTO probability * RTO cost)"
    )

    # Expected vs Actual for reconciliation
    expected_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Expected cost based on rate card"
    )
    actual_billed_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Actual amount billed by courier"
    )

    is_overbilled = models.BooleanField(default=False)
    overbilling_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_cost(self):
        """Sum of all cost components."""
        return (
            self.forward_cost + self.rto_cost + self.cod_charges +
            self.fuel_surcharge + self.weight_discrepancy_charges +
            self.ndr_reattempt_cost
        )

    def save(self, *args, **kwargs):
        # Auto-detect overbilling
        if self.actual_billed_cost > 0 and self.expected_cost > 0:
            diff = self.actual_billed_cost - self.expected_cost
            self.is_overbilled = diff > 0
            self.overbilling_amount = max(diff, 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cost for {self.shipment.awb_number}: ₹{self.total_cost}"

    class Meta:
        app_label = 'core'


# ==============================================================================
# 4. DELIVERY PARTNER
# ==============================================================================
class DeliveryPartner(models.Model):
    """
    Courier partner configuration and credentials.
    Stores rate cards, SPOC details, and active serviceable pincodes.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100)

    PARTNER_TYPE_CHOICES = [
        ('Direct', 'Direct'),
        ('Aggregator', 'Aggregator'),
    ]
    partner_type = models.CharField(
        max_length=20, choices=PARTNER_TYPE_CHOICES, default='Direct'
    )

    credentials = models.JSONField(
        default=dict, blank=True,
        help_text="Encrypted API credentials for this partner"
    )
    spoc_details = models.JSONField(
        default=dict, blank=True,
        help_text='{"name": "...", "email": "...", "phone": "..."}'
    )
    rate_list = models.JSONField(
        default=dict, blank=True,
        help_text='{"local_500g": 30, "regional_500g": 50, "national_500g": 70, ...}'
    )
    active_pincodes = models.JSONField(
        default=list, blank=True,
        help_text="List of serviceable pincodes or pincode ranges"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.partner_type})"

    class Meta:
        app_label = 'core'
        unique_together = ['org_id', 'name']


# ==============================================================================
# 5. COD REMITTANCE
# ==============================================================================
class CODRemittance(models.Model):
    """
    Tracks COD collection and remittance from courier partners.
    Flags delays and mismatches between expected and received amounts.
    """
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name='remittances'
    )
    expected_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    received_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expected_remittance_date = models.DateField(
        null=True, blank=True,
        help_text="When the courier should remit the COD amount"
    )
    actual_remittance_date = models.DateField(
        null=True, blank=True,
        help_text="When the COD amount was actually received"
    )
    delay_days = models.IntegerField(
        default=0,
        help_text="Days delayed past expected remittance date"
    )

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Received', 'Received'),
        ('Overdue', 'Overdue'),
        ('Mismatch', 'Mismatch'),
        ('Seized', 'Seized'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate delay_days
        if self.expected_remittance_date and self.actual_remittance_date:
            delta = (self.actual_remittance_date - self.expected_remittance_date).days
            self.delay_days = max(delta, 0)
        elif self.expected_remittance_date and not self.actual_remittance_date:
            from django.utils import timezone
            delta = (timezone.now().date() - self.expected_remittance_date).days
            self.delay_days = max(delta, 0)
            if self.delay_days > 0 and self.status == 'Pending':
                self.status = 'Overdue'

        # Detect amount mismatch
        if (self.received_amount > 0 and self.expected_amount > 0 and
                self.received_amount != self.expected_amount):
            self.status = 'Mismatch'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"COD ₹{self.expected_amount} for {self.shipment.awb_number} ({self.status})"

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['status', '-expected_remittance_date'], name='idx_cod_status_date'),
        ]


# ==============================================================================
# 6. WAREHOUSE (Origin Location)
# ==============================================================================
class Warehouse(models.Model):
    """
    Organization's warehouse / pickup location.
    The pincode determines the origin for zone calculations.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=200, help_text="e.g., 'Main Warehouse', 'Mumbai Hub'")
    pincode = models.CharField(max_length=6, help_text="6-digit origin pincode")
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    contact_name = models.CharField(max_length=200, blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    is_default = models.BooleanField(
        default=False, help_text="Default warehouse for cost calculations"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If this is the only warehouse or marked as default, ensure no other is default
        if self.is_default:
            Warehouse.objects.filter(
                org_id=self.org_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.pincode}) — {'Default' if self.is_default else 'Active' if self.is_active else 'Inactive'}"

    class Meta:
        app_label = 'core'
        unique_together = ['org_id', 'name']


# ==============================================================================
# 7. COURIER RATE CARD (Per-Courier Pricing Configuration)
# ==============================================================================
class CourierRateCard(models.Model):
    """
    Rate card for a specific courier partner.
    Supports two pricing modes:
      - SLAB: Fixed price per weight slab per zone
      - BASE_PLUS: Base rate for first N kg + additional per-increment rate
    """
    org_id = models.CharField(max_length=50, db_index=True)
    courier_partner = models.CharField(
        max_length=50, db_index=True,
        help_text="Must match Shipment.courier_partner values (Bluedart, Delhivery, Aggregator, Other)"
    )
    name = models.CharField(max_length=200, help_text="e.g., 'Bluedart Surface Q1 2026'")

    SHIPPING_MODE_CHOICES = [
        ('Surface', 'Surface'), 
        ('Air', 'Air'),
        ('Apex', 'Apex / Air Express')
    ]
    shipping_mode = models.CharField(
        max_length=10, choices=SHIPPING_MODE_CHOICES, default='Surface'
    )

    PRICING_MODE_CHOICES = [
        ('SLAB', 'Fixed Slab (₹ per weight range)'),
        ('BASE_PLUS', 'Base + Additional (₹ base for first Xkg, ₹ per additional increment)'),
    ]
    pricing_mode = models.CharField(
        max_length=10, choices=PRICING_MODE_CHOICES, default='SLAB'
    )

    # Flat charges applied on top of weight-based pricing
    cod_charge_flat = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Flat COD fee per shipment (₹)"
    )
    cod_charge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="% of order value for COD — final COD = max(flat, percent × order_value)"
    )
    fuel_surcharge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Fuel surcharge % added on base freight (e.g., 12.5)"
    )
    fuel_surcharge_mode = models.CharField(
        max_length=30,
        choices=[('STATIC', 'Static Percent'), ('DYNAMIC_OFF_MECHANISM', 'Dynamic off Mechanism')],
        default='STATIC'
    )
    fuel_surcharge_offset = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage to deduct from mechanism fuel surcharge (e.g., 30.0 for mechanism - 30%)"
    )
    caf_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Carrier Adjustment Factor (CAF) % added on base freight (e.g., 10.0)"
    )
    caf_mode = models.CharField(
        max_length=30,
        choices=[('STATIC', 'Static Percent'), ('DYNAMIC_OFF_MECHANISM', 'Dynamic off Mechanism')],
        default='STATIC'
    )
    caf_offset = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage to deduct from mechanism CAF (e.g., 5.0 for mechanism - 5%)"
    )
    efss_surcharge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Elevated Freight Stability Surcharge % (e.g. 5.0 or 7.0)"
    )
    rto_charge_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.0,
        help_text="RTO cost = forward cost × this multiplier (1.0 = same as forward)"
    )
    ndr_reattempt_charge = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Per-reattempt delivery charge (₹)"
    )
    reverse_pickup_charge = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Flat reverse pickup / To Pay charges per AWB for returns/exchanges (₹)"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.courier_partner} / {self.shipping_mode} / {self.pricing_mode})"

    class Meta:
        app_label = 'core'
        ordering = ['courier_partner', 'name']


# ==============================================================================
# 8. RATE SLAB (Weight × Zone Pricing)
# ==============================================================================
class RateSlab(models.Model):
    """
    Pricing slab for a specific zone within a rate card.

    For SLAB mode:
        weight_from_kg=0, weight_to_kg=0.5, rate=65 → 0-500g costs ₹65

    For BASE_PLUS mode:
        weight_from_kg=0, weight_to_kg=0.5, rate=65 → Base rate for first 500g is ₹65
        weight_from_kg=0.5, weight_to_kg=99, rate=30 → Each additional 500g costs ₹30
        (increment_kg field defines the step, e.g., 0.5)
    """
    rate_card = models.ForeignKey(
        CourierRateCard, on_delete=models.CASCADE, related_name='slabs'
    )

    ZONE_CHOICES = [
        ('Local', 'Local'),
        ('Intra-City', 'Intra-City'),
        ('Within State', 'Within State'),
        ('Regional', 'Regional'),
        ('Metro', 'Metro-to-Metro'),
        ('National', 'National'),
        ('Special', 'Special / Remote'),
    ]
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)

    weight_from_kg = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="Start of weight range in KG (inclusive)"
    )
    weight_to_kg = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text="End of weight range in KG (exclusive). Use 99 for 'and above'."
    )
    rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price in ₹ — for SLAB=total price, for BASE_PLUS=per-increment price"
    )
    increment_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.50,
        help_text="For BASE_PLUS mode: weight increment step (e.g., 0.5 = per 500g)"
    )

    def __str__(self):
        return f"{self.rate_card.name} → {self.zone} [{self.weight_from_kg}-{self.weight_to_kg}kg] = ₹{self.rate}"

    class Meta:
        app_label = 'core'
        ordering = ['zone', 'weight_from_kg']
        unique_together = ['rate_card', 'zone', 'weight_from_kg']


# ==============================================================================
# 9. FREIGHT INVOICE (Accounts Payable)
# ==============================================================================
class FreightInvoice(models.Model):
    """
    Consolidated post-paid shipping bill sent by the courier.
    Subject to 15-day credit terms.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    courier_partner = models.CharField(max_length=50)
    
    invoice_date = models.DateField()
    due_date = models.DateField(help_text="invoice_date + 15 days credit period")
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_file = models.FileField(upload_to='freight_invoices/', null=True, blank=True)
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
        ('Seized', 'Seized (COD Offset)'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    paid_date = models.DateField(null=True, blank=True)
    product_type = models.CharField(max_length=50, blank=True, default='', help_text="Invoice classification (COD or Prepaid)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.invoice_date:
            from datetime import timedelta
            self.due_date = self.invoice_date + timedelta(days=15)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.courier_partner} Invoice {self.invoice_number} (₹{self.total_amount})"

    class Meta:
        app_label = 'core'
        ordering = ['-invoice_date']


# ==============================================================================
# 10. SHIPMENT DISPUTE (Pay Now, Argue Later Tracker)
# ==============================================================================
class ShipmentDispute(models.Model):
    """
    Tracks disputes over weight discrepancies or overbilling.
    Must be logged within 30 days of the FreightInvoice date.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name='disputes',
        null=True, blank=True,
        help_text="Optional: null when dispute is raised at invoice-line level only"
    )
    freight_invoice = models.ForeignKey(FreightInvoice, on_delete=models.CASCADE, related_name='disputes')

    disputed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, help_text="e.g. 'Weight Discrepancy (Billed 2kg, Actual 500g)'")

    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Credit Note Issued', 'Credit Note Issued'),
        ('Rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Open', db_index=True)

    credit_note_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    logged_date = models.DateTimeField(auto_now_add=True)
    resolved_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        awb = self.shipment.awb_number if self.shipment else 'Invoice-level'
        return f"Dispute on {awb} (₹{self.disputed_amount}) - {self.status}"

    class Meta:
        app_label = 'core'
        ordering = ['-logged_date']


# ==============================================================================
# 11. COURIER INVOICE LINE (Billing Discrepancy Engine)
# ==============================================================================
class CourierInvoiceLine(models.Model):
    """
    One row per AWB per courier invoice.

    Parsed from the courier's Excel (.xlsb / .xlsx) billing file.
    Covers forward deliveries, RTO returns, exchanges, and credit adjustments.

    Business rule: ALL our orders are <250g product weight → every AWB should
    always be billed at the 0.5 kg slab. Any NCHRGWT > 0.5 is an overcharge.
    """
    org_id          = models.CharField(max_length=50, db_index=True)
    freight_invoice = models.ForeignKey(
        FreightInvoice, on_delete=models.CASCADE, related_name='lines'
    )
    shipment = models.ForeignKey(
        Shipment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoice_lines',
        help_text="Linked Shipment record. Null if AWB not found in our system."
    )

    # --- Identifiers ---
    awb_number   = models.CharField(max_length=100, db_index=True)
    courier_ref  = models.CharField(
        max_length=200, blank=True,
        help_text="CCRCRDREF — our internal order ref (e.g. JANKI39337, JANKI38133RET1064)"
    )
    product_code = models.CharField(
        max_length=20, blank=True,
        help_text="Courier product code: ACL=Air-COD-fwd, APL=Air-Prepaid-fwd, AP/AC=return legs"
    )
    origin_area  = models.CharField(max_length=100, blank=True)
    dest_area    = models.CharField(max_length=100, blank=True)
    dest_pincode = models.CharField(max_length=10, blank=True)
    commodity    = models.TextField(blank=True, help_text="Product description as declared to courier")

    # --- Weight ---
    actual_weight_kg  = models.DecimalField(
        max_digits=8, decimal_places=3, default=0,
        help_text="NACTWGT — weight measured by courier's scale"
    )
    charged_weight_kg = models.DecimalField(
        max_digits=8, decimal_places=3, default=0,
        help_text="NCHRGWT — weight slab billed on"
    )
    pieces = models.IntegerField(default=1)

    # --- Charge breakdown (raw from Excel) ---
    freight               = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NFREIGHT — base freight")
    fsc                   = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NFSAMT — fuel surcharge")
    caf                   = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NCAFAMT — carrier adjustment factor")
    fod_charge            = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NFODCHRG — COD field delivery charge")
    declared_value_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NVALCHGS — declared value / insurance")
    idc_charge            = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NIDCCHGS — in-transit damage cover")
    misc_charges          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    efss                  = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="EFSS — Elevated Freight Stability Surcharge (freight × efss%)")
    total_billed          = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="NTOTAMOUNT — total charged for this AWB (Net)")
    
    # --- GST Breakdown ---
    tax_cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="9% CGST")
    tax_sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="9% SGST")
    total_billed_with_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Net + CGST + SGST")

    # --- Shipment classification ---
    SHIPMENT_TYPE_CHOICES = [
        ('Forward',  'Forward Delivery'),
        ('RTO',      'Return to Origin (RTO)'),
        ('Return',   'Customer Return'),
        ('Exchange', 'Exchange'),
        ('Credit',   'Credit / Adjustment'),
    ]
    shipment_type = models.CharField(
        max_length=20, choices=SHIPMENT_TYPE_CHOICES, default='Forward', db_index=True
    )

    # --- Discrepancy analysis (computed on ingest by discrepancy_engine) ---
    expected_weight_kg = models.DecimalField(
        max_digits=8, decimal_places=3, default=0,
        help_text="Expected slab under business rule (0.5 for all <250g orders)"
    )
    expected_freight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Correct freight at expected slab from rate card"
    )
    expected_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Total we should have been billed (Net)"
    )
    expected_tax_cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expected_tax_sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expected_total_with_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # --- Two-layer billing model (Reconciliation Engine v2) ---
    expected_pdf_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Expected PDF amount = freight + cod + efss"
    )
    expected_net_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Expected Excel net amount = freight + cod + efss + fs + caf"
    )

    BILLING_LAYER_CHOICES = [
        ('excel', 'Excel (decomposable components)'),
        ('pdf', 'PDF (merged charges)'),
        ('credit', 'Credit / Adjustment'),
    ]
    billing_layer = models.CharField(
        max_length=10, choices=BILLING_LAYER_CHOICES, default='excel', blank=True,
        help_text="Which billing layer this line was parsed from"
    )

    overcharge_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="total_billed_with_tax - expected_total_with_tax"
    )

    # --- Anomaly Classification (granular, replaces simple flags) ---
    ANOMALY_CATEGORY_CHOICES = [
        ('exact_match',          'Exact Match'),
        ('minor_rounding',       'Minor Rounding Difference'),
        ('surcharge_mismatch',   'Surcharge Mismatch (FS/CAF)'),
        ('weight_slab_mismatch', 'Weight Slab Mismatch'),
        ('cod_mismatch',         'COD Calculation Mismatch'),
        ('duplicate_charge',     'Duplicate Charge Suspected'),
        ('unknown_pricing',      'Unknown Pricing'),
    ]
    anomaly_category = models.CharField(
        max_length=30, choices=ANOMALY_CATEGORY_CHOICES, default='', blank=True,
        db_index=True, help_text="Granular anomaly classification"
    )

    confidence_score = models.IntegerField(
        default=0,
        help_text="Confidence score (0-100) based on formula match, history, and consistency"
    )

    DISCREPANCY_CHOICES = [
        ('None',          'No Discrepancy'),
        ('WrongSlab',     'Wrong Weight Slab'),
        ('WrongRate',     'Wrong Unit Rate'),
        ('WrongZone',     'Wrong Zone Charged'),
        ('UnexpectedRTO', 'RTO Charged Without Shipment Event'),
        ('UnexpectedFOD', 'FOD on Prepaid Order'),
        ('CreditNote',    'Credit / Adjustment'),
        ('NoMatch',       'AWB Not Found in Our System'),
        ('Multiple',      'Multiple Issues'),
    ]

    discrepancy_type  = models.CharField(
        max_length=30, choices=DISCREPANCY_CHOICES, default='None', db_index=True
    )
    discrepancy_notes = models.TextField(
        blank=True,
        help_text="Human-readable explanation of why this line was flagged"
    )

    # --- Dispute linkage ---
    dispute     = models.ForeignKey(
        ShipmentDispute, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoice_lines'
    )
    is_disputed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.awb_number} ({self.shipment_type}) | billed ₹{self.total_billed} | {self.discrepancy_type}"

    class Meta:
        app_label = 'core'
        unique_together = ['freight_invoice', 'awb_number']
        indexes = [
            models.Index(fields=['org_id', 'discrepancy_type'], name='idx_invline_disc'),
            models.Index(fields=['org_id', 'shipment_type'],    name='idx_invline_type'),
            models.Index(fields=['org_id', 'is_disputed'],      name='idx_invline_disputed'),
        ]


class CourierSurchargeHistory(models.Model):
    """
    Stores the monthly global mechanism Fuel Surcharge and Currency Adjustment Factor (CAF) values.
    For example, Blue Dart's official site:
      - June 2026: Fuel Surcharge = 91.60%, CAF = 22.50%
      - May 2026: Fuel Surcharge = 86.00%, CAF = 21.50%
    """
    org_id = models.CharField(max_length=50, db_index=True)
    courier_partner = models.CharField(
        max_length=50, default='Bluedart', db_index=True,
        help_text="e.g. 'Bluedart'"
    )
    month_date = models.DateField(
        help_text="First day of the month (e.g., 2026-04-01) for this surcharge cycle"
    )
    fuel_surcharge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Official/mechanism Fuel Surcharge percentage"
    )
    caf_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Official/mechanism Currency Adjustment Factor percentage"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.courier_partner} - {self.month_date.strftime('%B %Y')}: Fuel={self.fuel_surcharge_percent}%, CAF={self.caf_percent}%"

    class Meta:
        app_label = 'core'
        unique_together = ('org_id', 'courier_partner', 'month_date')
        ordering = ['-month_date']


class CourierZoneMapping(models.Model):
    """
    Courier-specific pincode-to-zone mappings (e.g. Bluedart's custom matrix).
    """
    org_id = models.CharField(max_length=50, db_index=True)
    courier_partner = models.CharField(max_length=50, default='Bluedart', db_index=True)
    pincode = models.CharField(max_length=10, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=50, blank=True)
    zone_code = models.CharField(max_length=10, db_index=True)  # e.g., 'A', 'B', 'C'
    hub_name = models.CharField(
        max_length=200, blank=True,
        help_text="Official courier hub name serving this pincode (e.g., 'Jaipur Hub', 'Delhi NCR Hub'). "
                  "Populated when courier shares hub-level mapping. Used by Hub Analytics."
    )
    hub_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    hub_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pincode_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pincode_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'core'
        unique_together = ('org_id', 'courier_partner', 'pincode')
        verbose_name = "Bluedart Zone Mapping"
        verbose_name_plural = "Bluedart Zone Mappings"



# ==============================================================================
# 14. BILLING PATTERN (Pattern Learning Engine)
# ==============================================================================
class BillingPattern(models.Model):
    """
    Historical billing pattern for the learning engine.

    Stores observed billing amounts per pincode/zone/weight combination.
    Clusters are built from these records to discover hidden pricing buckets.

    Design principle: learn clusters, infer pricing, classify patterns.
    The system becomes smarter with more invoices.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    courier_partner = models.CharField(
        max_length=50, default='Bluedart', db_index=True
    )
    city = models.CharField(max_length=100, blank=True, db_index=True)
    pincode = models.CharField(max_length=10, blank=True, db_index=True)
    zone = models.CharField(max_length=20, blank=True)
    weight_slab = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.50,
        help_text="Charged weight slab in KG"
    )
    billed_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Total billed amount observed for this pattern"
    )

    # Breakdown components
    freight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    efss = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    caf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_type = models.CharField(max_length=20, blank=True)

    # Learning metrics
    occurrence_count = models.IntegerField(
        default=1, help_text="How many times this exact pattern has been seen"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.city or self.pincode} | {self.zone} | "
            f"{self.weight_slab}kg | ₹{self.billed_amount} "
            f"(×{self.occurrence_count})"
        )

    class Meta:
        app_label = 'core'
        unique_together = [
            'org_id', 'courier_partner', 'pincode', 'zone',
            'weight_slab', 'billed_amount',
        ]
        indexes = [
            models.Index(
                fields=['org_id', 'courier_partner', 'city'],
                name='idx_billingpat_city',
            ),
            models.Index(
                fields=['org_id', 'courier_partner', 'pincode'],
                name='idx_billingpat_pin',
            ),
        ]
        ordering = ['-occurrence_count']


# ==============================================================================
# 15. COURIER SLA CONTRACT (SLA Dashboard)
# ==============================================================================
class CourierSLAContract(models.Model):
    """
    Contractual SLA commitments per courier per zone/shipping mode.
    Defines expected delivery days so the SLA Dashboard can detect breaches
    and calculate penalty recovery.

    SLA Breach: actual delivery days (delivery_date - dispatch_date) > promised_days
    Penalty Recovery: breach_days × penalty_per_day
    """
    org_id = models.CharField(max_length=50, db_index=True)
    courier_partner = models.CharField(max_length=50, db_index=True)

    ZONE_CHOICES = [
        ('Local', 'Local'),
        ('Intra-City', 'Intra-City'),
        ('Within State', 'Within State'),
        ('Regional', 'Regional'),
        ('Metro', 'Metro-to-Metro'),
        ('National', 'National'),
        ('Special', 'Special / Remote'),
    ]
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)

    SHIPPING_MODE_CHOICES = [
        ('Surface', 'Surface'),
        ('Air', 'Air'),
        ('Apex', 'Apex / Air Express'),
    ]
    shipping_mode = models.CharField(
        max_length=10, choices=SHIPPING_MODE_CHOICES, default='Surface'
    )

    promised_days = models.IntegerField(
        help_text="SLA: delivery within N business days"
    )
    penalty_per_day = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Penalty owed per day of SLA breach (₹). 0 = no penalty clause."
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(
        blank=True, default='',
        help_text="Optional: Contract reference, agreement date, etc."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.courier_partner} / {self.zone} / {self.shipping_mode} — SLA: {self.promised_days} days"

    class Meta:
        app_label = 'core'
        unique_together = ['org_id', 'courier_partner', 'zone', 'shipping_mode']
        ordering = ['courier_partner', 'zone']


# ==============================================================================
# 16. SHIPMENT EXCEPTION (Exception Management Center)
# ==============================================================================
class ShipmentException(models.Model):
    """
    Centralized exception record for any shipment abnormality.

    Workflow:
        Open → InvestigationPending → ResolutionPending → ClaimRecovery / Closed
        (or Rejected at any stage)

    Auto-detection (daily Celery task) creates records for:
        - Lost: In Transit > 15 days
        - Delayed: Past SLA promised_days from CourierSLAContract
        - MissingScan: No TrackingEvent in > 3 days for in-transit shipment
    """
    EXCEPTION_TYPE_CHOICES = [
        ('Lost', 'Lost Shipment'),
        ('Damaged', 'Damaged Shipment'),
        ('Delayed', 'Delayed Shipment'),
        ('MissingScan', 'Missing Scan (>3 days no update)'),
        ('WrongDelivery', 'Wrong Delivery'),
        ('WeightDispute', 'Weight Dispute'),
        ('FraudAlert', 'Fraud Alert'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('InvestigationPending', 'Courier Investigation Pending'),
        ('ResolutionPending', 'Resolution Pending'),
        ('ClaimRecovery', 'Claim Recovery'),
        ('Closed', 'Closed'),
        ('Rejected', 'Rejected'),
    ]

    org_id = models.CharField(max_length=50, db_index=True)
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name='exceptions'
    )
    exception_type = models.CharField(
        max_length=20, choices=EXCEPTION_TYPE_CHOICES, db_index=True
    )
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default='Open', db_index=True
    )
    description = models.TextField(
        blank=True,
        help_text="Details of the exception (auto-filled for auto-detected, manual for agent-created)"
    )
    assigned_to = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_shipment_exceptions',
        help_text="Agent responsible for investigating/resolving this exception"
    )
    claim_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount claimed from courier (₹)"
    )
    recovered_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Amount actually recovered (₹)"
    )
    notes = models.TextField(
        blank=True, default='',
        help_text="Agent notes on investigation progress"
    )
    is_auto_detected = models.BooleanField(
        default=False,
        help_text="True if created by the auto-detection Celery task"
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the exception was closed or rejected"
    )
    audit_trail = models.JSONField(
        default=list, blank=True,
        help_text=(
            'Ordered list of status-change events. '
            'Each entry: {timestamp, actor, from_status, to_status, notes, recovered_amount}'
        )
    )

    def __str__(self):
        return f"{self.exception_type} on {self.shipment.awb_number} [{self.status}]"

    class Meta:
        app_label = 'core'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['org_id', 'status', '-detected_at'], name='idx_exc_org_status'),
            models.Index(fields=['org_id', 'exception_type'], name='idx_exc_org_type'),
            models.Index(fields=['org_id', 'is_auto_detected'], name='idx_exc_org_auto'),
        ]


# ==============================================================================
# 17. CUSTOMER RISK PROFILE (Customer Risk Engine)
# ==============================================================================
class CustomerRiskProfile(models.Model):
    """
    Pre-computed risk profile for each customer (keyed by org + contact_phone).

    Data source: Order.contact_phone + Shipment history

    Risk Formula:
        rto_rate        = rto_count / total_orders
        refusal_rate    = refusal_count / total_orders  (ndr_call_status Refused/Cancel)
        cod_rate        = cod_order_count / total_orders
        delivery_rate   = delivery_success_count / total_orders

        score = (rto_rate * 40 + refusal_rate * 25 + cod_rate * 20 + (1 - delivery_rate) * 15) * 100
        score = min(int(score), 100)

    Risk Levels:
        Low      (0-30)  → no action
        Medium   (31-60) → monitor
        High     (61-85) → OTP + Manual Call
        Blocked  (86+)   → Require Prepaid

    Recomputed weekly via Celery task, or on-demand via API.
    """
    org_id = models.CharField(max_length=50, db_index=True)
    # Keyed on Order.contact_phone
    customer_phone = models.CharField(max_length=30, db_index=True)
    customer_name = models.CharField(max_length=200, blank=True, default='')
    customer_email = models.CharField(max_length=200, blank=True, default='')

    # Raw scoring components (updated on each recompute)
    total_orders = models.IntegerField(default=0)
    rto_count = models.IntegerField(default=0)
    delivery_success_count = models.IntegerField(default=0)
    cod_order_count = models.IntegerField(default=0)
    refusal_count = models.IntegerField(
        default=0,
        help_text="Orders where ndr_call_status contains 'Refused' or 'Cancel'"
    )
    avg_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    # Computed output
    risk_score = models.IntegerField(
        default=0, db_index=True,
        help_text="0-100. Higher = riskier. Computed from rto/refusal/cod/delivery rates."
    )

    RISK_LEVEL_CHOICES = [
        ('Low', 'Low Risk (0-30)'),
        ('Medium', 'Medium Risk (31-60)'),
        ('High', 'High Risk (61-85)'),
        ('Blocked', 'Blocked (86-100)'),
    ]
    risk_level = models.CharField(
        max_length=10, choices=RISK_LEVEL_CHOICES, default='Low', db_index=True
    )

    # Auto-generated action recommendations (JSON list of strings)
    recommended_actions = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["OTP Verification", "Manual Call Verification", "Require Prepaid"]'
    )

    last_computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Manual override — ops team can block a customer regardless of score
    is_manually_blocked = models.BooleanField(
        default=False, db_index=True,
        help_text="Manually blocked by an operator. Overrides computed risk_level."
    )
    blocked_reason = models.TextField(
        blank=True, default='',
        help_text="Reason provided by the operator when manually blocking this customer."
    )

    def __str__(self):
        return f"{self.customer_phone} — {self.risk_level} ({self.risk_score}/100) [{self.org_id}]"

    class Meta:
        app_label = 'core'
        unique_together = ['org_id', 'customer_phone']
        indexes = [
            models.Index(fields=['org_id', 'risk_level', '-risk_score'], name='idx_crp_org_risk'),
            models.Index(fields=['org_id', '-risk_score'], name='idx_crp_org_score'),
        ]


# ==============================================================================
# 18. CONTROL TOWER ENHANCEMENTS MODELS
# ==============================================================================
import uuid

class ShipmentRiskScore(models.Model):
    shipment = models.OneToOneField(
        Shipment, on_delete=models.CASCADE, primary_key=True, related_name='risk_score_detail'
    )
    risk_score = models.DecimalField(max_digits=4, decimal_places=3, default=0.0) # 0.000 to 1.000
    horizon_24h = models.BooleanField(default=False)
    horizon_48h = models.BooleanField(default=False)
    signals = models.JSONField(default=dict, blank=True) # { hub_delay_rate, courier_sla_hist, transit_velocity, weather_flag }
    computed_at = models.DateTimeField(auto_now=True)
    predicted_delay = models.BooleanField(default=False)
    actual_delayed = models.BooleanField(default=False)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.shipment.awb_number} — Risk: {self.risk_score}"


class CourierHealthScore(models.Model):
    courier_id = models.CharField(max_length=50, db_index=True)
    score_date = models.DateField(db_index=True)
    composite_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    sla_adherence_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    ndr_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    avg_delay_hrs = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    scan_quality_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    dispute_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    status = models.CharField(
        max_length=10, 
        choices=[('green', 'Green'), ('amber', 'Amber'), ('red', 'Red')],
        default='green'
    )

    class Meta:
        app_label = 'core'
        unique_together = ['courier_id', 'score_date']
        ordering = ['-score_date', 'courier_id']

    def __str__(self):
        return f"{self.courier_id} on {self.score_date}: {self.composite_score} ({self.status})"


class ControlTowerActionAuditLog(models.Model):
    action_type = models.CharField(max_length=50, db_index=True) # REASSIGN, RESCUE, FLAG_HUB, ESCALATE, NOTIFY
    operator = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    awbs = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action_type} by {self.operator.username if self.operator else 'System'} at {self.timestamp}"


class PenaltyTicket(models.Model):
    ticket_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.CharField(max_length=50, db_index=True)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='penalty_tickets')
    contract = models.ForeignKey(CourierSLAContract, on_delete=models.SET_NULL, null=True, blank=True, related_name='penalties')
    courier_id = models.CharField(max_length=50, db_index=True)
    sla_deadline = models.DateTimeField(db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    breach_days = models.IntegerField(default=0)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(
        max_length=20,
        choices=[('open', 'Open'), ('claimed', 'Claimed'), ('recovered', 'Recovered'), ('disputed', 'Disputed')],
        default='open',
        db_index=True
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Penalty claim for {self.shipment.awb_number} — {self.currency} {self.penalty_amount} [{self.status}]"


class WeatherAlert(models.Model):
    state_name = models.CharField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=False)
    alert_type = models.CharField(max_length=100, blank=True, default='')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-last_updated']

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"Weather Warning for {self.state_name.title()}: {self.alert_type or 'None'} [{status}]"


class NDRPlaybook(models.Model):
    """
    Playbooks for reason-specific NDR routing. Configured per merchant (org_id).
    """
    org_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=200)
    reason_category = models.CharField(
        max_length=50,
        choices=[
            ('CUSTOMER_UNAVAILABLE', 'Customer Unavailable'),
            ('ADDRESS_ISSUE', 'Address Issue'),
            ('REFUSED_DELIVERY', 'Refused Delivery'),
            ('PREMISES_CLOSED', 'Premises Closed'),
            ('COD_NOT_READY', 'COD Not Ready'),
            ('OTHERS', 'Others')
        ],
        db_index=True
    )
    priority = models.IntegerField(default=0, help_text="Higher priority playbooks are run first")
    is_active = models.BooleanField(default=True)
    
    # Store custom conditions like pincode exclusions or cod thresholds
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON describing matching conditions, e.g. {"min_value": 1000}'
    )
    
    # Sequence of action playbook steps: e.g. [{"action": "whatsapp", "template": "addr"}, {"action": "wait", "hours": 24}]
    actions = models.JSONField(
        default=list,
        blank=True,
        help_text='List of step actions to execute'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-priority', 'name']
        unique_together = ('org_id', 'reason_category', 'priority')

    def __str__(self):
        return f"{self.name} (Org: {self.org_id}, Category: {self.reason_category}, Priority: {self.priority})"


class NDRFraudFlag(models.Model):
    """
    Flags shipments exhibiting patterns of fake courier delivery attempts.
    """
    FLAG_TYPE_CHOICES = [
        ('SCAN_GAP', 'Impossible scan-to-attempt time gap'),
        ('LOCATION_MISMATCH', 'Geographic coordinates mismatch (Fake Attempt)'),
        ('DUPLICATE_ATTEMPT', 'Duplicate attempt back-to-back'),
    ]
    
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='fraud_flags')
    flag_type = models.CharField(max_length=30, choices=FLAG_TYPE_CHOICES, db_index=True)
    details = models.JSONField(default=dict, blank=True, help_text="Detailed analysis proving physical impossibility")
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Fraud flag [{self.flag_type}] on Shipment {self.shipment.awb_number}"


class PrepaidRemittance(models.Model):
    """
    Identical twin of CODRemittance for prepaid orders.
    Tracks payment gateway settlements, fees, status, delay days, and reconciliation status.
    """
    order = models.ForeignKey(
        'core.Order', on_delete=models.CASCADE, related_name='prepaid_remittances'
    )
    order_number = models.CharField(max_length=100, blank=True)
    gateway_name = models.CharField(max_length=100, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    gateway_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expected_settlement_date = models.DateField(null=True, blank=True)
    actual_settlement_date = models.DateField(null=True, blank=True)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    delay_days = models.IntegerField(default=0)
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Received', 'Received'),
        ('Overdue', 'Overdue'),
        ('Mismatch', 'Mismatch'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate delay_days
        if self.expected_settlement_date and self.actual_settlement_date:
            delta = (self.actual_settlement_date - self.expected_settlement_date).days
            self.delay_days = max(delta, 0)
        elif self.expected_settlement_date and not self.actual_settlement_date:
            from django.utils import timezone
            delta = (timezone.now().date() - self.expected_settlement_date).days
            self.delay_days = max(delta, 0)
            if self.delay_days > 0 and self.status == 'Pending':
                self.status = 'Overdue'

        # Detect amount mismatch
        if (self.received_amount > 0 and self.net_amount > 0 and
                self.received_amount != self.net_amount):
            self.status = 'Mismatch'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Prepaid Remittance for {self.order_number} ({self.status})"

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['status', '-expected_settlement_date'], name='idx_pp_status_date'),
        ]


class PaymentGatewayFeeRule(models.Model):
    """
    Configurable fee rules per payment gateway per organization.
    """
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    gateway_name = models.CharField(max_length=100)
    fee_type = models.CharField(
        max_length=20, 
        choices=[('percentage', 'Percentage'), ('flat', 'Flat')], 
        default='percentage'
    )
    fee_value = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
    settlement_days = models.IntegerField(default=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"Fee Rule: {self.gateway_name} ({self.fee_value} {self.fee_type}) [{status}] (Org: {self.org_id})"

    class Meta:
        app_label = 'core'
        unique_together = [['org_id', 'gateway_name']]

