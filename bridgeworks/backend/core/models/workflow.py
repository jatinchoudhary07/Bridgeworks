from django.db import models
from django.contrib.auth import get_user_model
from core.models.store import ShopCredentials

User = get_user_model()

class Workflow(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='workflows')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.shop.organization_id if self.shop else 'No Shop'})"


class WorkflowTrigger(models.Model):
    ENTITY_CHOICES = [
        ('lead', 'Lead'),
        ('company', 'Company'),
        ('quote', 'Quote'),
        ('customer', 'Customer'),
        ('task', 'Task'),
    ]
    TRIGGER_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('status_changed', 'Status Changed'),
        ('task_overdue', 'Task Overdue'),
        ('quote_accepted', 'Quote Accepted'),
        ('lead_assigned', 'Lead Assigned'),
    ]

    workflow = models.OneToOneField(Workflow, on_delete=models.CASCADE, related_name='trigger')
    entity_type = models.CharField(max_length=50, choices=ENTITY_CHOICES)
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.get_trigger_type_display()} on {self.get_entity_type_display()}"


class WorkflowCondition(models.Model):
    OPERATOR_CHOICES = [
        ('equals', 'Equals'),
        ('contains', 'Contains'),
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('days_since_activity', 'Days Since Activity'),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='conditions')
    field_name = models.CharField(max_length=100)
    operator = models.CharField(max_length=50, choices=OPERATOR_CHOICES)
    value = models.TextField(help_text="Value to compare against.")

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.field_name} {self.get_operator_display()} {self.value}"


class WorkflowAction(models.Model):
    ACTION_CHOICES = [
        ('create_task', 'Create Task'),
        ('create_activity', 'Create Activity'),
        ('assign_user', 'Assign User'),
        ('change_status', 'Change Status'),
        ('send_notification', 'Send In-App Notification'),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    configuration = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Action parameters (e.g. title, description, assignee_id, status_val)"
    )

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.get_action_type_display()}"


class WorkflowExecution(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='executions')
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    logs = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-started_at']

    def __str__(self):
        return f"Execution of {self.workflow.name} on {self.entity_type}#{self.entity_id}: {self.status}"
