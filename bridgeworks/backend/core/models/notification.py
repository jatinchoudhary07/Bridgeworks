from django.db import models
from django.contrib.auth import get_user_model
from core.models.store import ShopCredentials

User = get_user_model()

class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('leadership', 'Leadership & Strategy'),
        ('product', 'Product & Merchandising'),
        ('branding', 'Branding & Creative'),
        ('marketing', 'Marketing & Growth'),
        ('ecommerce', 'E-Commerce & Website'),
        ('operations', 'Operations & Fulfilment'),
        ('tracking', 'Logistics'),
        ('rto_management', 'Reverse Shipment'),
        ('taskmanager', 'My Desk'),
        ('customerExperience', 'Customer Experience'),
        ('intelligence', 'Intelligence'),
        ('webhooks', 'Webhooks'),
        ('finance', 'Finance & Accounting'),
        ('hr', 'Human Resources'),
        ('it', 'IT & Data'),
        ('production', 'Production / Manufacturing'),
        ('sales', 'Sales & Business Dev'),
    ]



    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='notifications_new')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications_sent')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='sales_overview')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Backward compatible fields for existing frontend bells
    module = models.CharField(max_length=50, blank=True, default='')
    action = models.CharField(max_length=50, blank=True, default='')
    title = models.CharField(max_length=255, blank=True, default='')
    message = models.TextField()
    preview = models.CharField(max_length=255, blank=True, default='')
    
    entity_type = models.CharField(max_length=50, blank=True, default='')
    entity_id = models.CharField(max_length=64, blank=True, default='')
    deep_link = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['shop', 'recipient']),
        ]

    def __str__(self):
        return f"{self.category} -> {self.recipient.username} (read={self.is_read})"


class NotificationPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_preferences')
    category = models.CharField(max_length=50, choices=Notification.CATEGORY_CHOICES)
    email_delivery = models.BooleanField(default=True)
    in_app_delivery = models.BooleanField(default=True)
    push_delivery = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'
        unique_together = ('user', 'category')

    def __str__(self):
        return f"{self.user.username} - {self.category} (Email: {self.email_delivery}, In-App: {self.in_app_delivery}, Push: {self.push_delivery})"


class NotificationDeliveryLog(models.Model):
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('in_app', 'In-App'),
    ]
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_logs')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-sent_at']

    def __str__(self):
        return f"Delivery to {self.notification.recipient.username} via {self.channel}: {self.status}"
