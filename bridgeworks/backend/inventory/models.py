from django.db import models
from django.utils import timezone


class ShopifyProductCache(models.Model):
    """
    Database-level cache for Shopify product data per organisation.
    Eliminates repeated API round-trips for 924+ products by persisting the
    full product payload.  Survives server restarts and works across all
    worker processes.
    """
    organization_id = models.CharField(max_length=50, db_index=True)
    shopify_id      = models.BigIntegerField()
    data            = models.JSONField(default=dict)
    synced_at       = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label    = "inventory"
        unique_together = ("organization_id", "shopify_id")
        indexes = [
            models.Index(fields=["organization_id", "synced_at"]),
        ]

    def __str__(self):
        return f"Product {self.shopify_id} [{self.organization_id}]"


class ShopifyCollectionCache(models.Model):
    """
    Database-level cache for Shopify collection (category) data per organisation.
    """
    organization_id = models.CharField(max_length=50, db_index=True)
    shopify_id      = models.BigIntegerField()
    data            = models.JSONField(default=dict)
    synced_at       = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label    = "inventory"
        unique_together = ("organization_id", "shopify_id")
        indexes = [
            models.Index(fields=["organization_id", "synced_at"]),
        ]

    def __str__(self):
        return f"Collection {self.shopify_id} [{self.organization_id}]"


class InventoryTable(models.Model):
    """
    Stores column configuration for a specific inventory table per org.
    One record per (org, table_key) pair.
    """
    organization_id = models.CharField(max_length=50, db_index=True)
    table_key = models.CharField(max_length=100)
    columns = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "inventory"
        unique_together = ("organization_id", "table_key")

    def __str__(self):
        return f"{self.organization_id}/{self.table_key}"


class InventoryItem(models.Model):
    """
    One row in an inventory table. Stores arbitrary key-value data as JSON
    so the frontend can freely add/remove columns without schema migrations.
    """
    table = models.ForeignKey(
        InventoryTable,
        on_delete=models.CASCADE,
        related_name="items",
    )
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "inventory"
        ordering = ["created_at"]

    def __str__(self):
        return f"Item {self.pk} in {self.table}"


class Vendor(models.Model):
    """
    Represents a supplier/vendor in the system.
    """
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive')]

    organization_id = models.CharField(max_length=50, db_index=True)
    name            = models.CharField(max_length=255)
    contact_person  = models.CharField(max_length=255, blank=True, default='')
    email           = models.EmailField(blank=True, default='')
    phone           = models.CharField(max_length=50, blank=True, default='')
    address         = models.TextField(blank=True, default='')
    gst_number      = models.CharField(max_length=20, blank=True, default='')
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    notes           = models.TextField(blank=True, default='')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "inventory"
        ordering  = ["name"]

    def __str__(self):
        return f"{self.name} [{self.organization_id}]"


class PurchaseOrder(models.Model):
    """
    A purchase order sent to a vendor.
    Status flow: order_placed → in_process → dispatched → received
    When status becomes 'received', stock is automatically updated.
    """
    STATUS_CHOICES = [
        ('order_placed', 'Order Placed'),
        ('in_process',   'In Process'),
        ('dispatched',   'Dispatched'),
        ('received',     'Received'),
    ]

    organization_id      = models.CharField(max_length=50, db_index=True)
    po_number            = models.CharField(max_length=50, unique=True)
    vendor               = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='purchase_orders')
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='order_placed')
    products             = models.JSONField(default=list)  # [{shopify_id, name, sku, qty, unit, price}]
    total_amount         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_delivery    = models.DateField(null=True, blank=True)
    notes                = models.TextField(blank=True, default='')
    # GRN fields (Goods Receipt Note)
    received_qty         = models.JSONField(default=dict)  # {shopify_id: qty}
    damaged_qty          = models.JSONField(default=dict)  # {shopify_id: qty}
    qc_status            = models.CharField(max_length=20, blank=True, default='')  # pending / approved / rejected
    received_date        = models.DateField(null=True, blank=True)
    stock_updated        = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "inventory"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"PO-{self.po_number} → {self.vendor.name} [{self.status}]"
