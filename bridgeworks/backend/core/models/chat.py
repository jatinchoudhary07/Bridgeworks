from django.db import models
from django.conf import settings
import uuid

class ChatMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_chat_messages'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    meet_link = models.URLField(blank=True, default='')
    event_title = models.CharField(blank=True, default='', max_length=255)
    event_tagged_names = models.CharField(blank=True, default='', max_length=512)
    is_event = models.BooleanField(default=False)
    is_broadcast = models.BooleanField(default=False)
    room = models.ForeignKey(
        'core.ChatRoom',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    channel = models.ForeignKey(
        'core.ChatChannel',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    reply_to = models.ForeignKey(
        'self',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='replies',
    )
    parent_message = models.ForeignKey(
        'self',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='thread_replies',
    )
    thread_reply_count = models.IntegerField(default=0)
    last_reply_at = models.DateTimeField(blank=True, null=True)
    last_reply_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='last_replied_messages',
    )
    edited_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    
    # Task fields
    is_task = models.BooleanField(default=False)
    task_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='assigned_chat_tasks'
    )
    task_description = models.TextField(blank=True, default='')
    task_due_date = models.DateTimeField(blank=True, null=True)
    task_source_message_id = models.IntegerField(blank=True, null=True)
    task_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('completed', 'Completed')],
        default='pending'
    )
    task_title = models.CharField(blank=True, default='', max_length=255)
    task_priority = models.CharField(
        max_length=15,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )
    
    # Attachment fields
    attachment = models.FileField(blank=True, null=True, upload_to='chat_attachments/')
    attachment_kind = models.CharField(blank=True, default='', max_length=20)
    attachment_mime_type = models.CharField(blank=True, default='', max_length=100)
    attachment_name = models.CharField(blank=True, default='', max_length=255)
    vault_item = models.ForeignKey(
        'core.GalleryItem',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='chat_messages',
    )

    class Meta:
        app_label = 'core'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'created_at'], name='chatmsg_sender_created_idx'),
            models.Index(fields=['is_broadcast', 'created_at'], name='chatmsg_broadcast_created_idx'),
            models.Index(fields=['room', 'created_at'], name='chatmsg_room_created_idx'),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"


class ChatRoom(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    organization = models.ForeignKey(
        'core.ShopCredentials',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    icon = models.ImageField(upload_to='chat_room_icons/', blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_chat_rooms',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        app_label = 'core'
        ordering = ['name']
        indexes = [
            models.Index(fields=['organization', 'is_deleted'], name='chatroom_org_deleted_idx'),
            models.Index(fields=['room_id'], name='chatroom_roomid_idx'),
        ]

    def __str__(self):
        return self.name


class ChatRoomMember(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_room_memberships')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='added_chat_room_members',
    )

    class Meta:
        app_label = 'core'
        unique_together = [('room', 'user')]
        indexes = [
            models.Index(fields=['room', 'role'], name='chatroommem_room_role_idx'),
            models.Index(fields=['user', 'role'], name='chatroommem_user_role_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.room.name} as {self.role}"


class ChatRoomSettings(models.Model):
    room = models.OneToOneField(ChatRoom, on_delete=models.CASCADE, related_name='settings')
    allow_member_messages = models.BooleanField(default=True)
    announcement_mode = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='updated_chat_room_settings',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"Settings for {self.room.name}"


class ChatCommunity(models.Model):
    workspace = models.ForeignKey(
        'core.ShopCredentials',
        on_delete=models.CASCADE,
        related_name='chat_communities',
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_chat_communities',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    # Public communities are viewable without membership; private ones require an explicit membership.
    is_public = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']
        unique_together = [('workspace', 'name')]

    def __str__(self):
        return self.name


class ChatCommunityMember(models.Model):
    """Tracks who belongs to a community and at what role."""
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    community = models.ForeignKey(ChatCommunity, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_community_memberships')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = [('community', 'user')]
        indexes = [
            models.Index(fields=['community', 'role'], name='chatcommmem_comm_role_idx'),
            models.Index(fields=['user', 'role'], name='chatcommmem_user_role_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.community.name} as {self.role}"


class ChatChannel(models.Model):
    TYPE_PUBLIC = 'public'
    TYPE_RESTRICTED = 'restricted'
    TYPE_ADMIN = 'admin'
    TYPE_PRIVATE = 'private'
    TYPE_CHOICES = [
        (TYPE_PUBLIC, 'Public'),
        (TYPE_RESTRICTED, 'Restricted'),
        (TYPE_ADMIN, 'Admin'),
        (TYPE_PRIVATE, 'Private'),
    ]

    workspace = models.ForeignKey(
        'core.ShopCredentials',
        on_delete=models.CASCADE,
        related_name='chat_channels',
    )
    community = models.ForeignKey(
        ChatCommunity,
        on_delete=models.CASCADE,
        related_name='channels',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PUBLIC)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_chat_channels',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    
    # Permissions
    can_post = models.BooleanField(default=True)
    can_react = models.BooleanField(default=True)
    can_upload = models.BooleanField(default=True)
    can_invite = models.BooleanField(default=False)
    show_in_directory = models.BooleanField(default=True)
    everyone_allowed = models.CharField(max_length=20, default='admins')

    class Meta:
        app_label = 'core'
        ordering = ['name']
        unique_together = [('workspace', 'name')]
        indexes = [
            models.Index(fields=['workspace', 'is_archived'], name='chatchannel_ws_arch_idx'),
        ]

    def __str__(self):
        return f"#{self.name}"


class ChatChannelMember(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_channel_memberships')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = [('channel', 'user')]
        indexes = [
            models.Index(fields=['channel', 'role'], name='chatchanmem_chan_role_idx'),
            models.Index(fields=['user', 'role'], name='chatchanmem_user_role_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.channel.name} as {self.role}"


class ChatPinnedMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='pinned_messages', null=True, blank=True)
    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='pinned_messages', null=True, blank=True)
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='pin_entries')
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pinned_chat_messages',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['room', 'message'], name='unique_room_message_pin', condition=models.Q(room__isnull=False)),
            models.UniqueConstraint(fields=['channel', 'message'], name='unique_channel_message_pin', condition=models.Q(channel__isnull=False)),
        ]

    def __str__(self):
        dest = f"room {self.room_id}" if self.room_id else f"channel {self.channel_id}"
        return f"Pinned message {self.message_id} in {dest}"


class ChatMessageReaction(models.Model):
    REACTION_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('heart', 'Heart'),
        ('laugh', 'Laugh'),
        ('party', 'Party'),
        ('fire', 'Fire'),
        ('clap', 'Clap'),
    ]

    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_message_reactions')
    reaction = models.CharField(max_length=30, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = [('message', 'user', 'reaction')]
        indexes = [
            models.Index(fields=['message', 'reaction'], name='chatreact_msg_react_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} reacted {self.reaction} to {self.message_id}"


class ChatMessageMention(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='mentions')
    mentioned_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_mentions')
    mention_type = models.CharField(max_length=20, default='user', choices=[
        ('user', 'User'),
        ('team', 'Team'),
        ('channel', 'Channel'),
        ('everyone', 'Everyone'),
    ])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = [('message', 'mentioned_user')]
        indexes = [
            models.Index(fields=['mentioned_user', 'created_at'], name='chatmention_user_created_idx'),
        ]

    def __str__(self):
        return f"{self.mentioned_user.username} mentioned in {self.message_id}"


class ChatMessageRecipient(models.Model):
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='recipient_entries'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_chat_messages'
    )
    is_archived = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Chat Message Recipient'
        verbose_name_plural = 'Chat Message Recipients'
        unique_together = [('message', 'recipient')]
        indexes = [
            models.Index(fields=['recipient', 'is_read'], name='chatmsgrecip_rcpt_read_idx'),
            models.Index(fields=['recipient', 'is_archived'], name='chatmsgrecip_rcpt_arch_idx'),
            models.Index(fields=['recipient'], name='chatmsgrecip_rcpt_idx'),
        ]

    def __str__(self):
        return f"Recipient entry for {self.recipient.username}"
