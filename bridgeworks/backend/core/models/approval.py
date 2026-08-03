from django.db import models
from django.contrib.auth import get_user_model
from core.models.store import ShopCredentials

User = get_user_model()

class ApprovalPolicy(models.Model):
    ENTITY_CHOICES = [
        ('quote', 'Quote'),
        ('discount', 'Discount'),
        ('custom', 'Custom'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='approval_policies')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    entity_type = models.CharField(max_length=50, choices=ENTITY_CHOICES, default='quote')
    trigger_conditions = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Criteria under which this policy applies: e.g. {'field': 'total_value', 'operator': 'gte', 'value': 500000}"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_entity_type_display()})"


class ApprovalStep(models.Model):
    policy = models.ForeignKey(ApprovalPolicy, on_delete=models.CASCADE, related_name='steps')
    sequence = models.IntegerField(default=1, help_text="Sequence index of the step (1-indexed)")
    approvers = models.ManyToManyField(User, related_name='approval_steps')
    min_approvals_required = models.IntegerField(default=1)
    sla_hours = models.IntegerField(null=True, blank=True, help_text="SLA hours before escalation triggers")
    escalate_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='escalated_approval_steps'
    )

    class Meta:
        app_label = 'core'
        ordering = ['sequence']

    def __str__(self):
        return f"Step {self.sequence} for {self.policy.name}"


class ApprovalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
        ('cancelled', 'Cancelled'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='approval_requests')
    policy = models.ForeignKey(ApprovalPolicy, on_delete=models.SET_NULL, null=True, blank=True, related_name='requests')
    entity_type = models.CharField(max_length=50, help_text="e.g. quote")
    entity_id = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    current_step_sequence = models.IntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_approval_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"Approval Request for {self.entity_type}#{self.entity_id}: {self.status}"


class ApprovalHistory(models.Model):
    ACTION_CHOICES = [
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
        ('reassigned', 'Reassigned'),
    ]

    request = models.ForeignKey(ApprovalRequest, on_delete=models.CASCADE, related_name='history')
    step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, blank=True)
    sequence = models.IntegerField(default=1)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='approved')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acted_approvals')
    comments = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.action} step {self.sequence} by {self.approver} at {self.created_at}"
