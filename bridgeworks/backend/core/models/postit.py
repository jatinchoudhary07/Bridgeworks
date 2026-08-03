from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class StickyNote(models.Model):
    content = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_notes')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_notes')
    
    color = models.CharField(max_length=20, default='#ffeb3b')
    x_position = models.IntegerField(default=100)
    y_position = models.IntegerField(default=100)
    
    is_completed = models.BooleanField(default=False)
    shared_with_names = models.TextField(blank=True, default="")
    
    parent_note = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='copies')
    
    attachment = models.FileField(upload_to='postit_attachments/', blank=True, null=True)
    attachment_filename = models.CharField(max_length=255, blank=True, default="")
    
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes_sent')
    
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes_completed')
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='notes_deleted')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return f"Note {self.id} for {self.assigned_to}"

    class Meta:
        app_label = 'core'


class PostItComment(models.Model):
    note = models.ForeignKey(StickyNote, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postit_comments')
    text = models.TextField()
    mentioned_users = models.ManyToManyField(User, blank=True, related_name='mentioned_in_comments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on Note {self.note_id}"


class PostItNotification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postit_notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='postit_notifications_sent')
    note = models.ForeignKey(StickyNote, on_delete=models.CASCADE, related_name='notifications')
    comment = models.ForeignKey(PostItComment, null=True, blank=True, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient}: {self.message[:50]}"
