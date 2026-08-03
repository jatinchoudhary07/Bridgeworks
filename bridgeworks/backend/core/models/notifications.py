from django.conf import settings
from django.db import models


class UnifiedNotification(models.Model):
    MODULE_POSTITS = 'postits'
    MODULE_NOTES = 'notes'
    MODULE_TASKS = 'tasks'
    MODULE_CHATS = 'my_chats'
    MODULE_EXPENSES = 'expenses'
    MODULE_LEAVE = 'leave_requests'
    MODULE_GALLERY = 'gallery'
    MODULE_MEETINGS = 'my_meetings'
    MODULE_TRAINING = 'training'

    MODULE_CHOICES = [
        (MODULE_POSTITS, 'PostIts'),
        (MODULE_NOTES, 'My Notes'),
        (MODULE_TASKS, 'Tasks'),
        (MODULE_CHATS, 'My Chats'),
        (MODULE_EXPENSES, 'Expenses'),
        (MODULE_LEAVE, 'Leave Requests'),
        (MODULE_GALLERY, 'Gallery'),
        (MODULE_MEETINGS, 'My Meetings'),
        (MODULE_TRAINING, 'Training'),
    ]

    ACTION_MENTION = 'mention'
    ACTION_SHARE = 'share'
    ACTION_REMINDER = 'reminder'

    ACTION_CHOICES = [
        (ACTION_MENTION, 'Mention'),
        (ACTION_SHARE, 'Share'),
        (ACTION_REMINDER, 'Reminder'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='unified_notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unified_notifications_sent',
    )
    module = models.CharField(max_length=40, choices=MODULE_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    title = models.CharField(max_length=180, blank=True, default='')
    message = models.CharField(max_length=500)
    preview = models.CharField(max_length=280, blank=True, default='')

    entity_type = models.CharField(max_length=60, blank=True, default='')
    entity_id = models.CharField(max_length=64, blank=True, default='')
    sub_entity_type = models.CharField(max_length=60, blank=True, default='')
    sub_entity_id = models.CharField(max_length=64, blank=True, default='')

    deep_link = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='unotif_rcpt_read_created_idx'),
            models.Index(fields=['recipient', 'module', '-created_at'], name='unotif_rcpt_module_created_idx'),
        ]

    def __str__(self):
        return f"{self.module}:{self.action} -> {self.recipient_id}"
