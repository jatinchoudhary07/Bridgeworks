from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Customer(models.Model):
    org_id = models.CharField(max_length=50, db_index=True, help_text="The Organization ID this customer belongs to.")
    name = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    email = models.EmailField(max_length=254, null=True, blank=True, db_index=True)
    address = models.TextField(null=True, blank=True)
    
    # Lifetime Metrics
    total_orders = models.IntegerField(default=0)
    delivered_orders = models.IntegerField(default=0)
    rto_orders = models.IntegerField(default=0)
    cancelled_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name or 'Unknown'} ({self.phone or self.email or 'No Contact'})"

    class Meta:
        app_label = 'core'
