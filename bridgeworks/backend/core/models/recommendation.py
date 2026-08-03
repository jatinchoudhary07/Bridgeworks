from django.db import models
from core.models.store import ShopCredentials

class Recommendation(models.Model):
    TYPE_CHOICES = [
        ('stale_lead', 'Stale Lead'),
        ('expiring_quote', 'Expiring Quote'),
        ('overdue_task', 'Overdue Task'),
        ('inactive_company', 'Inactive Company'),
        ('high_value_opportunity', 'High Value Opportunity'),
        ('revenue_decline', 'Revenue Decline'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dismissed', 'Dismissed'),
        ('resolved', 'Resolved'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='recommendations')
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    entity_type = models.CharField(max_length=50, help_text="e.g. lead, company, quote, customer, task")
    entity_id = models.CharField(max_length=64)
    score = models.FloatField(default=0.0, help_text="Priority rank weight score")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-score', '-created_at']
        indexes = [
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_severity_display()}) — {self.status}"
