from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class DiaryEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('work', 'Work'),
        ('meeting', 'Meeting'),
        ('learning', 'Learning'),
        ('review', 'Review'),
        ('issue', 'Issue'),
    ]

   

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='diary_entries')
    title = models.CharField(max_length=255)
    note = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default='work')
    entry_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return f"DiaryEntry {self.id} - {self.user}"


class DiaryAttachment(models.Model):
    entry = models.ForeignKey(DiaryEntry, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='diary_attachments/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True, default='')
    mime_type = models.CharField(max_length=120, blank=True, default='')
    file_size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return self.original_name or f"Attachment {self.id}"
