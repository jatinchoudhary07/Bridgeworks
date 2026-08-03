from django.db import models
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class UserPresence(models.Model):
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('in_meeting', 'In a Meeting'),
        ('on_leave', 'On Leave'),
        ('working_remotely', 'Working Remotely'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='presence'
    )
    resolved_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='offline'
    )
    leave_active = models.BooleanField(default=False)
    meeting_active = models.BooleanField(default=False)
    manual_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        null=True,
        blank=True
    )
    activity_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='offline'
    )
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.user.username} - {self.resolved_status}"

    def resolve_status(self):
        """
        Pure method to compute the status based on priority:
        1. on_leave (leave_active == True)
        2. in_meeting (meeting_active == True)
        3. manual_status (if set)
        4. activity_status (default fallback)
        """
        if self.leave_active:
            self.resolved_status = 'on_leave'
        elif self.meeting_active:
            self.resolved_status = 'in_meeting'
        elif self.manual_status:
            self.resolved_status = self.manual_status
        else:
            self.resolved_status = self.activity_status
        return self.resolved_status

    def save_and_broadcast(self, source='unknown', broadcast=True):
        # Check if resolved status or last_seen changed
        old_status = None
        if self.pk:
            try:
                old_status = UserPresence.objects.only('resolved_status').get(pk=self.pk).resolved_status
            except UserPresence.DoesNotExist:
                pass

        # Resolve status just in case it wasn't called before saving
        self.resolve_status()
        self.save()

        # Log to StatusHistory if status changed
        if old_status != self.resolved_status:
            StatusHistory.objects.create(
                user=self.user,
                status=self.resolved_status,
                source=source
            )

        # Broadcast via Channel Layer
        if broadcast:
            channel_layer = get_channel_layer()
            if channel_layer:
                # 1. Broadcast to presence-specific subscription group
                async_to_sync(channel_layer.group_send)(
                    f'presence_{self.user.id}',
                    {
                        'type': 'presence_update',
                        'user_id': self.user.id,
                        'status': self.resolved_status,
                        'last_seen': self.last_seen.isoformat() if self.last_seen else None
                    }
                )

                # 2. Broadcast to organization chat channels (backwards compatibility)
                org_id = None
                if hasattr(self.user, 'shop_credentials'):
                    org_id = self.user.shop_credentials.organization_id
                else:
                    try:
                        org_id = self.user.team_settings.organization.organization_id
                    except AttributeError:
                        pass

                if org_id:
                    is_online = (self.resolved_status in ('online', 'in_meeting'))
                    async_to_sync(channel_layer.group_send)(
                        f'chat_org_{org_id}',
                        {
                            'type': 'presence.update',
                            'user_id': self.user.id,
                            'is_online': is_online,
                        }
                    )
                    async_to_sync(channel_layer.group_send)(
                        f'presence_org_{org_id}',
                        {
                            'type': 'presence_update',
                            'user_id': self.user.id,
                            'status': self.resolved_status,
                            'last_seen': self.last_seen.isoformat() if self.last_seen else None
                        }
                    )



class StatusHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='presence_history'
    )
    status = models.CharField(max_length=20, choices=UserPresence.STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.user.username} -> {self.status} ({self.source}) at {self.changed_at}"
