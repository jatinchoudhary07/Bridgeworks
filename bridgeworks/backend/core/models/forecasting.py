from django.db import models
from django.contrib.auth import get_user_model
from core.models.store import ShopCredentials

User = get_user_model()

class SalesQuota(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='sales_quotas')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales_quotas')
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    year = models.IntegerField()
    month = models.IntegerField(help_text="Month of the quota (1-12)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'user', 'year', 'month')

    def __str__(self):
        return f"{self.user.username} Quota: ₹{self.target_amount} ({self.month}/{self.year})"
