from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models.store import ShopCredentials

User = get_user_model()

class CustomerHealthScore(models.Model):
    CHURN_RISK_CHOICES = [
        ('low', 'Low Churn Risk'),
        ('medium', 'Medium Churn Risk'),
        ('high', 'High Churn Risk'),
        ('critical', 'Critical Churn Risk'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='customer_health_scores')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    health_score = models.IntegerField(default=100, help_text="Overall health score (0-100)")
    engagement_score = models.IntegerField(default=100, help_text="Engagement rating (0-100)")
    support_ticket_count = models.IntegerField(default=0, help_text="Number of unresolved support tickets")
    churn_risk = models.CharField(max_length=20, choices=CHURN_RISK_CHOICES, default='low')
    metrics = models.JSONField(default=dict, blank=True, help_text="Detailed engagement metrics")
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['shop', 'health_score']),
        ]

    def __str__(self):
        return f"Health: {self.health_score} ({self.churn_risk}) for {self.content_object}"


class RenewalTracker(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in_negotiation', 'In Negotiation'),
        ('renewed', 'Renewed'),
        ('churned', 'Churned'),
        ('suspended', 'Suspended'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='renewal_trackers')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    annual_recurring_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    monthly_recurring_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    upsell_opportunity_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.0)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='active')
    renewal_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['shop', 'contract_end_date']),
        ]

    def __str__(self):
        return f"Renewal Tracker ({self.status}) ends: {self.contract_end_date} for {self.content_object}"


class SuccessTask(models.Model):
    TYPE_CHOICES = [
        ('onboarding', 'Onboarding Step'),
        ('check_in', 'Scheduled Check-in'),
        ('renewal', 'Renewal Preparation'),
        ('escalation', 'Escalation / Save Playbook'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='success_tasks')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=25, choices=TYPE_CHOICES, default='onboarding')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_success_tasks')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['due_date', '-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['shop', 'status']),
        ]

    def __str__(self):
        return f"SuccessTask: {self.title} ({self.status})"
