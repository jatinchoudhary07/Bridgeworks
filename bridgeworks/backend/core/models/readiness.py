from django.db import models
from django.contrib.auth import get_user_model
from core.models.store import ShopCredentials

User = get_user_model()

class SystemAuditLog(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='system_audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions')
    action = models.CharField(max_length=50, help_text="e.g. create, update, delete, status_change")
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    changed_fields = models.JSONField(default=dict, blank=True, help_text="Before and after snapshot of modified fields")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'model_name', 'object_id']),
            models.Index(fields=['shop', 'created_at']),
        ]

    def __str__(self):
        actor = self.user.username if self.user else 'System'
        return f"{actor} performed {self.action} on {self.model_name}#{self.object_id} at {self.created_at}"


class SavedFilter(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='saved_filters')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_crm_filters')
    module_name = models.CharField(max_length=50, help_text="e.g. leads, quotes, companies")
    name = models.CharField(max_length=150)
    query_params = models.JSONField(default=dict, help_text="JSON representation of applied filters")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'user', 'module_name', 'name')
        ordering = ['name']

    def __str__(self):
        return f"Filter '{self.name}' for {self.module_name} by {self.user.username}"
