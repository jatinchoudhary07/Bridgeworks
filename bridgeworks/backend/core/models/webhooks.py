from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class WebhookLog(models.Model):
    """
    Logs each incoming webhook request from external sources (e.g. Sagepilot).
    Used to track NDR action outcomes on the Webhooks dashboard.
    """

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('sop', 'SOP (As Per Schedule)'),
        ('failed', 'Failed'),
    ]

    source = models.CharField(max_length=100, default='sagepilot', db_index=True)
    awb = models.CharField(max_length=100, blank=True)
    action_code = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=30, blank=True)
    landmark = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='failed', db_index=True)
    response_message = models.TextField(blank=True)
    payload_json = models.JSONField(null=True, blank=True, help_text="Stores the entire raw JSON payload of the webhook.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Webhook Log"
        verbose_name_plural = "Webhook Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.source.upper()}] {self.awb} — {self.status} @ {self.created_at.strftime('%d %b %Y %H:%M')}"


class WebhookSubscription(models.Model):
    shop = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='webhook_subscriptions')
    target_url = models.URLField(max_length=500)
    event_type = models.CharField(max_length=100, db_index=True) # e.g., lead.created, quote.approved, task.assigned, task.overdue
    is_active = models.BooleanField(default=True, db_index=True)
    secret_token = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'event_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.target_url} ({'Active' if self.is_active else 'Inactive'})"


class OutboundWebhookLog(models.Model):
    shop = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='outbound_webhook_logs')
    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    event_type = models.CharField(max_length=100, db_index=True)
    target_url = models.URLField(max_length=500)
    payload = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    duration_ms = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='pending', db_index=True) # success, failed, pending
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} to {self.target_url} - {self.status} ({self.response_status})"


class OAuthApp(models.Model):
    shop = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='oauth_apps')
    name = models.CharField(max_length=255)
    client_id = models.CharField(max_length=100, unique=True, db_index=True)
    client_secret = models.CharField(max_length=255)
    redirect_uris = models.TextField(help_text="Newline separated list of allowed redirect URIs")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.client_id})"


class IntegrationConnection(models.Model):
    shop = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='integration_connections')
    provider = models.CharField(max_length=50, db_index=True) # e.g. shopify, gmail, outlook, slack, teams, zapier
    connection_type = models.CharField(max_length=50, default='oauth') # oauth, apikey, webhook
    is_active = models.BooleanField(default=True, db_index=True)
    credentials_json = models.JSONField(default=dict, blank=True, help_text="OAuth tokens or API key configurations")
    metadata = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        unique_together = ('shop', 'provider')

    def __str__(self):
        return f"{self.provider} connection for {self.shop} ({'Active' if self.is_active else 'Inactive'})"

