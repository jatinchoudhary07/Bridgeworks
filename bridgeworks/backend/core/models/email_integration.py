from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models.store import ShopCredentials

class EmailThread(models.Model):
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='email_threads')
    subject = models.CharField(max_length=255)
    
    # Generic Foreign Key to parent entity (Lead, Company, Quote, Customer)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['shop', 'last_message_at']),
        ]

    def __str__(self):
        return f"Thread: {self.subject} ({self.content_object})"


class EmailMessage(models.Model):
    thread = models.ForeignKey(EmailThread, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=255, blank=True, null=True, help_text="Internet Message-ID RFC 2822")
    sender = models.EmailField()
    recipient = models.EmailField()
    cc = models.TextField(blank=True, help_text="Comma separated CC addresses")
    bcc = models.TextField(blank=True, help_text="Comma separated BCC addresses")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Body content, max 65535 characters")
    sent_at = models.DateTimeField()
    is_incoming = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['thread', 'sent_at']),
            models.Index(fields=['message_id']),
        ]

    def save(self, *args, **kwargs):
        # Enforce character limit of 65535 for email bodies
        if self.body and len(self.body) > 65535:
            self.body = self.body[:65535]
        super().save(*args, **kwargs)

    def __str__(self):
        direction = "Incoming" if self.is_incoming else "Outgoing"
        return f"{direction} email from {self.sender} to {self.recipient} on {self.sent_at}"
