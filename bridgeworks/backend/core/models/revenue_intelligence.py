from django.db import models
from core.models.store import ShopCredentials

class DealRisk(models.Model):
    ENTITY_CHOICES = [
        ('lead', 'Wholesale Lead'),
        ('company', 'Company / Retail Store'),
        ('quote', 'Quotation'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='deal_risks')
    entity_type = models.CharField(max_length=50, choices=ENTITY_CHOICES)
    entity_id = models.CharField(max_length=64)
    risk_score = models.IntegerField(default=0, help_text="Calculated risk score from 0 (low) to 100 (critical)")
    risk_factors = models.JSONField(default=list, blank=True, help_text="Identified risk reasons")
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'entity_type', 'entity_id')
        indexes = [
            models.Index(fields=['shop', 'risk_score']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"{self.entity_type}#{self.entity_id} Risk: {self.risk_score}"
