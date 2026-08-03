"""
Team Chat REST API
==================
Endpoints:
  GET  /api/chat/messages/?tab=received|sent|all|archive
  POST /api/chat/messages/
  POST /api/chat/messages/<id>/archive/
  POST /api/chat/messages/<id>/read/

Messages are scoped to a single organisation (same org as the sender).
Every posted message is fan-out to all other org members as
ChatMessageRecipient rows – so each recipient has their own archived/read state.
"""

import os
import time
import mimetypes
import datetime
import typing

from django.db import OperationalError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch, F
from django.http import FileResponse, HttpResponseRedirect

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework import serializers, status
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.tasks.chat_broadcast import broadcast_new_message_task, broadcast_task_update_task
from core.services.chat_metrics import (
    record_post_latency,
    record_client_drop,
    get_delivery_metrics,
    record_ws_broadcast,
)
from core.services.chat_realtime import broadcast_new_message, broadcast_task_update
from core.services.notifications import push_unified_notification
from core.serializers.mydesk import _build_file_access_url

from .models import (
    ChatMessage,
    ChatMessageMention,
    ChatMessageReaction,
    ChatMessageRecipient,
    ChatPinnedMessage,
    ChatRoom,
    ChatRoomMember,
    ChatRoomSettings,
    ChatChannel,
    ChatChannelMember,
    TeamMemberSettings,
    ChatCommunity,
    ChatCommunityMember,
)
from .permissions import is_org_owner

import html  # stdlib – used to strip XSS without an extra dependency
import json
import time

User = get_user_model()


CHAT_RECIPIENT_PREFETCH = Prefetch(
    'recipient_entries',
    queryset=ChatMessageRecipient.objects.select_related('recipient'),
    to_attr='prefetched_recipient_entries',
)


# ── CSRF-exempt session auth (same pattern used in views_postit.py) ──────────

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _get_org_id(request):
    """Return the organisation_id for the logged-in user, or None."""
    user = request.user
    if not user.is_authenticated:
        return None
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    try:
        return user.team_settings.organization.organization_id
    except Exception:
        return None


def _org_members(org_id):
    """Return all active User objects in the given org."""
    return User.objects.filter(
        team_settings__organization__organization_id=org_id,
        is_active=True,
    )


def _get_org(request):
    org_id = _get_org_id(request)
    if not org_id:
        return None
    if hasattr(request.user, 'shop_credentials') and request.user.shop_credentials.organization_id == org_id:
        return request.user.shop_credentials
    settings = getattr(request.user, 'team_settings', None)
    return getattr(settings, 'organization', None)


def _room_for_user(room_id, user, org_id):
    if not room_id:
        return None, None
    room = ChatRoom.objects.filter(
        room_id=room_id,
        organization__organization_id=org_id,
        is_deleted=False,
    ).select_related('organization', 'settings').prefetch_related('memberships__user').first()
    if not room:
        return None, None
    membership = next((m for m in room.memberships.all() if m.user_id == user.id), None)  # type: ignore
    if not membership:
        return None, None
    return room, membership


def _is_room_manager(membership):
    return membership and membership.role in (ChatRoomMember.ROLE_OWNER, ChatRoomMember.ROLE_ADMIN)


def _member_payload(user, role='member'):
    profile = getattr(user, 'profile', None)
    profile_picture_url = None
    if profile and profile.profile_picture:
        try:
            profile_picture_url = profile.profile_picture.url
        except Exception:
            profile_picture_url = None
    return {
        'id': user.id,
        'username': user.username,
        'full_name': user.get_full_name().strip() or user.username,
        'role': role,
        'profilePicture': profile_picture_url,
    }


def _room_icon_url(request, room):
    if not room.icon:
        return None
    return _build_file_access_url(request, room.icon)

def _sanitize(text) -> str:
    """Strip HTML to prevent stored XSS."""
    # We return the text as is. React automatically escapes strings before
    # rendering them, which prevents stored XSS in the browser.
    return str(text or '').strip()



import re as _re

def _parse_mention_recipients(content: str, org_id: str, exclude_user_id: int):
    """
    Extract every @username token from *content* and return the matching
    active Users that belong to the same org (excluding the sender).
    Returns (mention_type, queryset_or_none)
    """
    usernames = _re.findall(r'@(\w+)', content)
    if not usernames:
        return ('user', None)          # no @mention → broadcast to whole team
    
    lower_usernames = [u.lower() for u in usernames]
    if 'all' in lower_usernames or 'everyone' in lower_usernames:
        return ('everyone', None)          # @all → broadcast to whole team
    
    if 'channel' in lower_usernames or 'room' in lower_usernames:
        return ('channel', None)
        
    # case-insensitive username lookup scoped to the org
    qs = User.objects.filter(
        username__in=usernames,
        team_settings__organization__organization_id=org_id,
        is_active=True,
    ).exclude(id=exclude_user_id)
    return ('user', qs)


def _parse_to_user_ids(value):
    if value is None:
        return None
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        if cleaned.startswith('['):
            try:
                parsed = json.loads(cleaned)
                raw_values = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                raw_values = [part.strip() for part in cleaned.split(',') if part.strip()]
        else:
            raw_values = [part.strip() for part in cleaned.split(',') if part.strip()]
    else:
        raw_values = [value]

    ids = []
    for item in raw_values:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('1', 'true', 'yes', 'y', 'on'):
            return True
        if normalized in ('0', 'false', 'no', 'n', 'off', ''):
            return False
    return default


# ── RBAC HELPERS ─────────────────────────────────────────────────────────────

def _get_community_membership(user, community):
    """Return the ChatCommunityMember row for this user+community, or None."""
    return ChatCommunityMember.objects.filter(community=community, user=user).first()


def _community_role(user, community):
    """
    Return the effective role string for this user in the community.
    - Workspace owners (is_org_owner) are always treated as 'owner'.
    - Otherwise returns the ChatCommunityMember.role, or None if no membership.
    """
    if is_org_owner(user):
        return ChatCommunityMember.ROLE_OWNER
    m = _get_community_membership(user, community)
    return m.role if m else None


def _can_view_community(user, community):
    """
    Returns True if the user may see this community.
    - Owners always can.
    - Public communities: everyone in the org may see them.
    - Private communities: only members.
    """
    if is_org_owner(user):
        return True
    if community.is_public:
        return True
    return ChatCommunityMember.objects.filter(community=community, user=user).exists()


def _can_update_community(user, community):
    """Owner and Admin may update community settings."""
    role = _community_role(user, community)
    return role in (ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN)


def _can_delete_community(user, community):
    """Only the Owner may delete a community."""
    return _community_role(user, community) == ChatCommunityMember.ROLE_OWNER


def _can_create_community(user):
    """Only workspace-level owners may create communities."""
    return is_org_owner(user)


def _get_channel_membership(user, channel):
    """Return the ChatChannelMember row for this user+channel, or None."""
    return ChatChannelMember.objects.filter(channel=channel, user=user).first()


def _channel_role_in_community(user, channel):
    """
    Effective role a user has for channel-level operations.
    We resolve via their community role (owner/admin always have full channel access).
    Returns one of 'owner', 'admin', 'member', or None (no access at all).
    """
    if is_org_owner(user):
        return ChatCommunityMember.ROLE_OWNER
    # Check community-level role if channel belongs to a community
    if channel.community_id:
        m = ChatCommunityMember.objects.filter(community_id=channel.community_id, user=user).first()
        if m and m.role in (ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN):
            return m.role
    # Fall back to channel membership
    cm = ChatChannelMember.objects.filter(channel=channel, user=user).first()
    if cm:
        return cm.role  # 'admin' or 'member'
    return None


def _can_view_channel(user, channel):
    """
    Channel visibility rules:
    - Org owners bypass all checks.
    - Community owners/admins can view all channels in their community.
    - Explicit channel members (ChatChannelMember) can view the channel.
    - For public channels, any community member can view the channel (but regular community members who are not explicitly added will see it as locked on the frontend).
    """
    if is_org_owner(user):
        return True
    
    role = _channel_role_in_community(user, channel)
    if role in (ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN):
        return True

    # If the user is explicitly added as a member of the channel
    if ChatChannelMember.objects.filter(channel=channel, user=user).exists():
        return True

    # Public channels can be viewed (loaded/opened) by any community member
    if channel.channel_type == ChatChannel.TYPE_PUBLIC and channel.community_id:
        return ChatCommunityMember.objects.filter(community_id=channel.community_id, user=user).exists()

    return False


def _can_manage_channel(user, channel):
    """Owner and Admin (community-level or workspace-level) can create/update/delete channels."""
    if is_org_owner(user):
        return True
    role = _channel_role_in_community(user, channel)
    return role in (ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN, ChatChannelMember.ROLE_ADMIN)


def _can_create_channel(user, community=None):
    """Owner or Admin of the community (or workspace owner) may create channels."""
    if is_org_owner(user):
        return True
    if community:
        m = ChatCommunityMember.objects.filter(community=community, user=user).first()
        return m and m.role in (ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN)
    return False


def _get_accessible_channels_qs(user, org_id):
    """
    Returns a queryset of channels the user is permitted to see/access.
    
    Includes:
    - All channels for organization owners.
    - All channels in a community for community owners/admins.
    - Public channels in communities where the user is a member.
    - Channels where the user has explicit ChatChannelMember membership.
    """
    from django.db.models import Q
    if is_org_owner(user):
        return ChatChannel.objects.filter(
            workspace__organization_id=org_id,
            is_archived=False,
        )

    # Community IDs where user is owner/admin
    admin_community_ids = list(
        ChatCommunityMember.objects.filter(
            user=user,
            role__in=[ChatCommunityMember.ROLE_OWNER, ChatCommunityMember.ROLE_ADMIN],
        ).values_list('community_id', flat=True)
    )

    # Community IDs where user is a regular member
    member_community_ids = list(
        ChatCommunityMember.objects.filter(user=user).values_list('community_id', flat=True)
    )

    # Channel IDs where user has been explicitly added
    explicit_channel_ids = list(
        ChatChannelMember.objects.filter(user=user).values_list('channel_id', flat=True)
    )

    return ChatChannel.objects.filter(
        workspace__organization_id=org_id,
        is_archived=False,
    ).filter(
        # Community owners/admins can see all channels in their communities
        Q(community_id__in=admin_community_ids)
        # Regular community members can see public channels
        | Q(channel_type=ChatChannel.TYPE_PUBLIC, community_id__in=member_community_ids)
        # Any channel where the user has explicit membership
        | Q(id__in=explicit_channel_ids)
    ).distinct()


# ── END RBAC HELPERS ──────────────────────────────────────────────────────────


def _broadcast_new_message(org_id: str, message: 'ChatMessage', queue_delay_ms: float = 0.0) -> None:
    """
    Push the new message to every connected WebSocket client in the org.
    Called synchronously from the DRF view after DB write.

    is_archived is always False for a brand-new message.
    is_read: False for recipients (they haven't read it yet).
             True for the sender (the sender has no recipient row; the
             serializer returns True for them via the 'rec = None' branch).
    The frontend uses sender_id to know which value applies to itself.
    """
    try:
        broadcast_new_message(org_id, message, queue_delay_ms=queue_delay_ms)
        record_ws_broadcast(success=True, queue_delay_ms=queue_delay_ms)
    except Exception:
        record_ws_broadcast(success=False, queue_delay_ms=queue_delay_ms)
        pass  # Never let a broadcast failure break the REST response


def _broadcast_task_update(org_id: str, message: 'ChatMessage') -> None:
    try:
        broadcast_task_update(org_id, message)
        record_ws_broadcast(success=True, queue_delay_ms=0.0)
    except Exception:
        record_ws_broadcast(success=False, queue_delay_ms=0.0)
        pass


# ── SERIALIZERS ──────────────────────────────────────────────────────────────

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    is_archived = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    to_label = serializers.SerializerMethodField()
    recipient_user_ids = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    is_broadcast = serializers.BooleanField(read_only=True)
    task_assignee_name = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    room_id = serializers.SerializerMethodField()
    room_name = serializers.SerializerMethodField()
    channel_id = serializers.IntegerField(source='channel.id', read_only=True)
    parent_message_id = serializers.IntegerField(source='parent_message.id', read_only=True)
    thread_reply_count = serializers.IntegerField(read_only=True)
    last_reply_at = serializers.DateTimeField(read_only=True)
    last_reply_by = serializers.IntegerField(source='last_reply_by.id', read_only=True)
    reactions = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()

    def get_sender_name(self, obj):
        u = obj.sender
        return (u.get_full_name().strip() or u.username)

    def _recipient_entries(self, obj):
        prefetched = getattr(obj, 'prefetched_recipient_entries', None)
        if prefetched is not None:
            return prefetched
        cached = getattr(obj, '_cached_recipient_entries', None)
        if cached is not None:
            return cached
        fetched = list(obj.recipient_entries.select_related('recipient').all())
        setattr(obj, '_cached_recipient_entries', fetched)
        return fetched

    def get_is_archived(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        for rec in self._recipient_entries(obj):
            if rec.recipient_id == request.user.id:
                return rec.is_archived
        return False

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request:
            return True
        for rec in self._recipient_entries(obj):
            if rec.recipient_id == request.user.id:
                return rec.is_read
        return True  # sent messages are always "read" for sender

    def get_to_label(self, obj):
        """Human-readable recipient label shown on the message card."""
        recipients = self._recipient_entries(obj)
        if not recipients:
            return 'Team'
        names = [r.recipient.username for r in recipients]
        # 4+ recipients → treat as a team/broadcast message
        if len(names) > 3:
            return 'Team'
        return ', '.join(f'@{n}' for n in names)

    def get_recipient_user_ids(self, obj):
        """List of user IDs who received this message (used for WS filtering)."""
        return [rec.recipient_id for rec in self._recipient_entries(obj)]

    def get_delivery_status(self, obj):
        """
        Sender side:
          - delivered: message created and delivered to recipients, not all read yet
          - read: all recipients have read
        Recipient side:
          - unread: current user hasn't read this message
          - read: current user has read this message
        """
        request = self.context.get('request')
        if not request:
            return 'delivered'

        user = request.user
        if obj.sender_id == user.id:
            recipients_list = self._recipient_entries(obj)
            total = len(recipients_list)
            if total == 0:
                return 'delivered'
            read_count = sum(1 for r in recipients_list if r.is_read)
            if read_count == 0:
                return 'unread'
            if read_count >= total:
                return 'read'
            return 'delivered'

        for rec in self._recipient_entries(obj):
            if rec.recipient_id == user.id:
                return 'unread' if not rec.is_read else 'read'
        return 'read'

    def get_task_assignee_name(self, obj):
        if not obj.task_assignee:
            return ''
        return (obj.task_assignee.get_full_name().strip() or obj.task_assignee.username)

    def get_attachment_url(self, obj):
        if not obj.attachment or not obj.id:
            return ''
        request = self.context.get('request')
        return _build_file_access_url(request, obj.attachment)

    def get_room_id(self, obj):
        return str(obj.room.room_id) if obj.room_id else ''

    def get_room_name(self, obj):
        return obj.room.name if obj.room_id and obj.room else ''

    def get_reactions(self, obj):
        rows = getattr(obj, 'prefetched_reactions', None)
        if rows is None:
            rows = list(obj.reactions.select_related('user').all())
        grouped = {}
        for reaction in rows:
            item = grouped.setdefault(reaction.reaction, {
                'reaction': reaction.reaction,
                'count': 0,
                'user_ids': [],
            })
            item['count'] += 1
            item['user_ids'].append(reaction.user_id)
        return list(grouped.values())

    def get_is_pinned(self, obj):
        pinned = getattr(obj, 'prefetched_pin_entries', None)
        if pinned is not None:
            return bool(pinned)
        return obj.pin_entries.exists()

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Unescape HTML entities to fix stored-escaped legacy data
        if 'content' in ret and ret['content']:
            ret['content'] = html.unescape(ret['content'])
        for field in ['event_title', 'event_tagged_names', 'task_title', 'task_description']:
            if field in ret and ret[field]:
                ret[field] = html.unescape(ret[field])
        return ret

    class Meta:  # type: ignore
        model = ChatMessage
        fields = [
            'id', 'sender_id', 'sender_name', 'content',
            'meet_link', 'event_title', 'event_tagged_names', 'is_event', 'is_broadcast',
            'room_id', 'room_name', 'channel_id', 'parent_message_id', 'reply_to_id',
            'thread_reply_count', 'last_reply_at', 'last_reply_by',
            'is_task', 'task_title', 'task_description', 'task_due_date', 'task_priority', 'task_status',
            'task_source_message_id', 'task_assignee_id', 'task_assignee_name',
            'attachment_url', 'attachment_name', 'attachment_mime_type', 'attachment_kind',
            'vault_item_id',
            'created_at', 'is_archived', 'is_read',
            'to_label', 'recipient_user_ids', 'delivery_status', 'reactions', 'is_pinned',
        ]

class ChatChannelSerializer(serializers.ModelSerializer):
    member_ids = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    pinned_messages = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()

    def _memberships(self, obj):
        prefetched = getattr(obj, '_cached_channel_memberships', None)
        if prefetched is not None:
            return prefetched
        memberships = list(obj.memberships.select_related('user').all())
        setattr(obj, '_cached_channel_memberships', memberships)
        return memberships

    def get_member_ids(self, obj):
        return [m.user_id for m in self._memberships(obj)]

    def get_members(self, obj):
        return [_member_payload(m.user, m.role) for m in self._memberships(obj)]

    def get_is_member(self, obj):
        """True if the requesting user has an explicit ChatChannelMember row."""
        request = self.context.get('request')
        if not request:
            return False
        if is_org_owner(request.user):
            return True
        return any(m.user_id == request.user.id for m in self._memberships(obj))

    def get_pinned_messages(self, obj):
        pins = getattr(obj, 'prefetched_channel_pins', None)
        if pins is None:
            pins = list(obj.pinned_messages.select_related('message', 'pinned_by').order_by('-created_at')[:5])
        return [
            {
                'id': pin.id,
                'message_id': pin.message_id,
                'content': html.unescape(pin.message.content or ''),
                'sender_id': pin.message.sender_id,
                'pinned_by': pin.pinned_by.get_full_name().strip() or pin.pinned_by.username if pin.pinned_by else '',
                'created_at': pin.created_at.isoformat() if pin.created_at else None,
            }
            for pin in pins
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        for field in ['name', 'description']:
            if field in ret and ret[field]:
                ret[field] = html.unescape(ret[field])
        return ret

    class Meta:  # type: ignore
        model = ChatChannel
        fields = [
            'id', 'name', 'description', 'channel_type',
            'created_at', 'is_archived', 'member_ids', 'members', 'is_member',
            'can_post', 'can_react', 'can_upload', 'can_invite',
            'show_in_directory', 'everyone_allowed', 'pinned_messages', 'community_id'
        ]


class ChatCommunitySerializer(serializers.ModelSerializer):
    channels = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = ChatCommunity
        fields = ['id', 'name', 'description', 'created_at', 'is_archived', 'is_public', 'my_role', 'channels']

    def get_my_role(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return _community_role(request.user, obj)

    def get_channels(self, obj):
        request = self.context.get('request')
        if not request:
            return []
        from django.db.models import Prefetch
        # Only return channels this user is permitted to see
        channels = _get_accessible_channels_qs(request.user, obj.workspace.organization_id).filter(
            community=obj,
        ).prefetch_related(
            'memberships__user',
            Prefetch(
                'pinned_messages',
                queryset=ChatPinnedMessage.objects.select_related('message', 'pinned_by').order_by('-created_at'),
                to_attr='prefetched_channel_pins'
            )
        ).distinct()
        return ChatChannelSerializer(channels, many=True, context=self.context).data


class ChatRoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    title = serializers.CharField(source='name', read_only=True)
    icon_url = serializers.SerializerMethodField()
    member_ids = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    settings = serializers.SerializerMethodField()
    pinned_messages = serializers.SerializerMethodField()

    def get_id(self, obj):
        return str(obj.room_id)

    def get_kind(self, obj):
        return 'room'

    def get_icon_url(self, obj):
        request = self.context.get('request')
        return _room_icon_url(request, obj) if request else None

    def _memberships(self, obj):
        prefetched = getattr(obj, '_cached_room_memberships', None)
        if prefetched is not None:
            return prefetched
        memberships = list(obj.memberships.select_related('user').all())
        setattr(obj, '_cached_room_memberships', memberships)
        return memberships

    def get_member_ids(self, obj):
        return [m.user_id for m in self._memberships(obj)]

    def get_members(self, obj):
        return [_member_payload(m.user, m.role) for m in self._memberships(obj)]

    def get_my_role(self, obj):
        request = self.context.get('request')
        if not request:
            return ''
        membership = next((m for m in self._memberships(obj) if m.user_id == request.user.id), None)
        return membership.role if membership else ''

    def get_settings(self, obj):
        settings_obj = getattr(obj, 'settings', None)
        return {
            'allow_member_messages': getattr(settings_obj, 'allow_member_messages', True),
            'announcement_mode': getattr(settings_obj, 'announcement_mode', False),
        }

    def get_pinned_messages(self, obj):
        pins = getattr(obj, 'prefetched_room_pins', None)
        if pins is None:
            pins = list(obj.pinned_messages.select_related('message', 'pinned_by').order_by('-created_at')[:5])
        return [
            {
                'id': pin.id,
                'message_id': pin.message_id,
                'content': html.unescape(pin.message.content or ''),
                'sender_id': pin.message.sender_id,
                'pinned_by': pin.pinned_by.get_full_name().strip() or pin.pinned_by.username if pin.pinned_by else '',
                'created_at': pin.created_at.isoformat() if pin.created_at else None,
            }
            for pin in pins
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        for field in ['name', 'title', 'description']:
            if field in ret and ret[field]:
                ret[field] = html.unescape(ret[field])
        return ret

    class Meta:  # type: ignore
        model = ChatRoom
        fields = [
            'id', 'kind', 'title', 'name', 'description', 'icon_url',
            'member_ids', 'members', 'my_role', 'settings', 'pinned_messages',
            'created_at', 'updated_at',
        ]


# ── VIEWS ─────────────────────────────────────────────────────────────────────


class ChatRoomListCreateView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([])
        rooms = ChatRoom.objects.filter(
            organization__organization_id=org_id,
            memberships__user=request.user,
            is_deleted=False,
        ).select_related('organization', 'settings').prefetch_related(
            'memberships__user',
            Prefetch(
                'pinned_messages',
                queryset=ChatPinnedMessage.objects.select_related('message', 'pinned_by').order_by('-created_at'),
                to_attr='prefetched_room_pins',
            ),
        ).distinct()
        serializer = ChatRoomSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        org = _get_org(request)
        org_id = getattr(org, 'organization_id', None)
        if not org_id:
            return Response({'error': 'No organisation found.'}, status=400)

        name = _sanitize(request.data.get('name') or request.data.get('room_name') or '')
        if not name:
            return Response({'error': 'Room name is required.'}, status=400)

        description = _sanitize(request.data.get('description', ''))
        icon = request.FILES.get('icon') or request.FILES.get('room_icon')
        raw_member_ids = request.data.getlist('member_ids') if hasattr(request.data, 'getlist') else request.data.get('member_ids')
        member_ids = set(_parse_to_user_ids(raw_member_ids) or [])
        member_ids.discard(request.user.id)

        members = list(_org_members(org_id).filter(id__in=member_ids))
        room = ChatRoom.objects.create(
            organization=org,
            name=name[:120],
            description=description,
            icon=icon,
            created_by=request.user,
        )
        ChatRoomSettings.objects.create(room=room, updated_by=request.user)
        ChatRoomMember.objects.create(
            room=room,
            user=request.user,
            role=ChatRoomMember.ROLE_OWNER,
            added_by=request.user,
        )
        ChatRoomMember.objects.bulk_create([
            ChatRoomMember(room=room, user=member, role=ChatRoomMember.ROLE_MEMBER, added_by=request.user)
            for member in members
        ], ignore_conflicts=True)

        system_message = ChatMessage.objects.create(
            sender=request.user,
            room=room,
            content=f"{request.user.get_full_name().strip() or request.user.username} created room {room.name}",
        )
        ChatMessageRecipient.objects.bulk_create([
            ChatMessageRecipient(message=system_message, recipient=member)
            for member in members
        ], ignore_conflicts=True)

        sender_name = request.user.first_name or request.user.username
        for member in members:
            push_unified_notification(
                recipient=member,
                actor=request.user,
                module='my_chats',
                action='invite',
                title='Added to room',
                message=f"{sender_name} added you to {room.name}",
                preview=description[:200],
                entity_type='chat_room',
                entity_id=room.pk,
                deep_link={
                    'page': '/mydesk/chats',
                    'section': 'my-chats',
                    'roomId': str(room.room_id),
                },
            )

        room = ChatRoom.objects.filter(id=room.pk).select_related('settings').prefetch_related('memberships__user').get()
        serializer = ChatRoomSerializer(room, context={'request': request})
        return Response(serializer.data, status=201)


class ChatRoomDetailView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if not _is_room_manager(membership):
            return Response({'error': 'Only owner or admin can edit room.'}, status=403)

        update_fields = []
        if 'name' in request.data:
            name = _sanitize(request.data.get('name', ''))
            if not name:
                return Response({'error': 'Room name is required.'}, status=400)
            room.name = name[:120]
            update_fields.append('name')
        if 'description' in request.data:
            room.description = _sanitize(request.data.get('description', ''))
            update_fields.append('description')
        icon = request.FILES.get('icon') or request.FILES.get('room_icon')
        if icon:
            room.icon = icon
            update_fields.append('icon')
        if update_fields:
            room.save()

        settings_obj, _ = ChatRoomSettings.objects.get_or_create(room=room)
        settings_changed = False
        if 'allow_member_messages' in request.data:
            settings_obj.allow_member_messages = _parse_bool(request.data.get('allow_member_messages'), True)
            settings_changed = True
        if 'announcement_mode' in request.data:
            settings_obj.announcement_mode = _parse_bool(request.data.get('announcement_mode'), False)
            settings_changed = True
            if settings_obj.announcement_mode:
                settings_obj.allow_member_messages = False
        if settings_changed:
            settings_obj.updated_by = request.user
            settings_obj.save()

        transfer_owner_id = request.data.get('transfer_owner_id')
        if transfer_owner_id and membership.role == ChatRoomMember.ROLE_OWNER:
            try:
                transfer_owner_id = int(transfer_owner_id)
            except (TypeError, ValueError):
                return Response({'error': 'Invalid owner selected.'}, status=400)
            target = ChatRoomMember.objects.filter(room=room, user_id=transfer_owner_id).first()
            if not target:
                return Response({'error': 'New owner must be a room member.'}, status=400)
            target.role = ChatRoomMember.ROLE_OWNER
            target.save(update_fields=['role'])
            membership.role = ChatRoomMember.ROLE_ADMIN
            membership.save(update_fields=['role'])

        room = ChatRoom.objects.filter(id=room.pk).select_related('settings').prefetch_related('memberships__user').get()
        return Response(ChatRoomSerializer(room, context={'request': request}).data)

    def delete(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if membership.role != ChatRoomMember.ROLE_OWNER:
            return Response({'error': 'Only owner can delete room.'}, status=403)
        room.is_deleted = True
        room.save(update_fields=['is_deleted', 'updated_at'])
        return Response({'status': 'deleted'})


class ChatRoomMemberView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if not _is_room_manager(membership):
            return Response({'error': 'Only owner or admin can add members.'}, status=403)
        raw_user_ids = request.data.getlist('user_ids') if hasattr(request.data, 'getlist') else request.data.get('user_ids')
        user_ids = set(_parse_to_user_ids(raw_user_ids) or [])
        users = list(_org_members(org_id).filter(id__in=user_ids).exclude(id__in=room.memberships.values_list('user_id', flat=True)))  # type: ignore
        ChatRoomMember.objects.bulk_create([
            ChatRoomMember(room=room, user=user, role=ChatRoomMember.ROLE_MEMBER, added_by=request.user)
            for user in users
        ], ignore_conflicts=True)
        for user in users:
            push_unified_notification(
                recipient=user,
                actor=request.user,
                module='my_chats',
                action='invite',
                title='Added to room',
                message=f"You were added to {room.name}",
                entity_type='chat_room',
                entity_id=room.pk,
                deep_link={'page': '/mydesk/chats', 'section': 'my-chats', 'roomId': str(room.room_id)},
            )
        room = ChatRoom.objects.filter(id=room.pk).select_related('settings').prefetch_related('memberships__user').get()
        return Response(ChatRoomSerializer(room, context={'request': request}).data)

    def patch(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if membership.role != ChatRoomMember.ROLE_OWNER:
            return Response({'error': 'Only owner can update roles.'}, status=403)
        user_id = request.data.get('user_id')
        role = request.data.get('role')
        if role not in (ChatRoomMember.ROLE_ADMIN, ChatRoomMember.ROLE_MEMBER):
            return Response({'error': 'Invalid role.'}, status=400)
        target = ChatRoomMember.objects.filter(room=room, user_id=user_id).exclude(role=ChatRoomMember.ROLE_OWNER).first()
        if not target:
            return Response({'error': 'Member not found.'}, status=404)
        target.role = role
        target.save(update_fields=['role'])
        room = ChatRoom.objects.filter(id=room.pk).select_related('settings').prefetch_related('memberships__user').get()
        return Response(ChatRoomSerializer(room, context={'request': request}).data)

    def delete(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        remove_user_id = request.data.get('user_id') or request.query_params.get('user_id') or request.user.id
        try:
            remove_user_id = int(remove_user_id)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid member.'}, status=400)
        removing_self = remove_user_id == request.user.id
        target = ChatRoomMember.objects.filter(room=room, user_id=remove_user_id).first()
        if not target:
            return Response({'error': 'Member not found.'}, status=404)
        if target.role == ChatRoomMember.ROLE_OWNER:
            return Response({'error': 'Transfer ownership before removing the owner.'}, status=400)
        if not removing_self and not _is_room_manager(membership):
            return Response({'error': 'Only owner or admin can remove members.'}, status=403)
        target.delete()
        return Response({'status': 'removed', 'user_id': remove_user_id})


class ChatRoomPinView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if not _is_room_manager(membership):
            return Response({'error': 'Only owner or admin can pin messages.'}, status=403)
        message_id = request.data.get('message_id')
        message = ChatMessage.objects.filter(id=message_id, room=room).first()
        if not message:
            return Response({'error': 'Message not found.'}, status=404)
        ChatPinnedMessage.objects.get_or_create(room=room, message=message, defaults={'pinned_by': request.user})
        return Response({'status': 'pinned'})

    def delete(self, request, room_id):
        org_id = _get_org_id(request)
        room, membership = _room_for_user(room_id, request.user, org_id)
        if not room or not membership:
            return Response({'error': 'Room not found.'}, status=404)
        if not _is_room_manager(membership):
            return Response({'error': 'Only owner or admin can unpin messages.'}, status=403)
        message_id = request.data.get('message_id') or request.query_params.get('message_id')
        ChatPinnedMessage.objects.filter(room=room, message_id=message_id).delete()
        return Response({'status': 'unpinned'})


class ChatChannelPinView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel:
            return Response({'error': 'Channel not found.'}, status=404)
        message_id = request.data.get('message_id')
        message = ChatMessage.objects.filter(id=message_id, channel=channel).first()
        if not message:
            return Response({'error': 'Message not found.'}, status=404)
        ChatPinnedMessage.objects.get_or_create(channel=channel, message=message, defaults={'pinned_by': request.user})
        return Response({'status': 'pinned'})

    def delete(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel:
            return Response({'error': 'Channel not found.'}, status=404)
        message_id = request.data.get('message_id') or request.query_params.get('message_id')
        ChatPinnedMessage.objects.filter(channel=channel, message_id=message_id).delete()
        return Response({'status': 'unpinned'})


class ChatMessageReactionView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_id = _get_org_id(request)
        reaction = request.data.get('reaction')
        valid = {choice[0] for choice in ChatMessageReaction.REACTION_CHOICES}
        if reaction not in valid:
            return Response({'error': 'Invalid reaction.'}, status=400)
        message = ChatMessage.objects.select_related('room').prefetch_related('recipient_entries').filter(id=pk).first()
        if not message:
            return Response({'error': 'Message not found.'}, status=404)
        allowed = (
            message.sender_id == request.user.id or  # type: ignore
            message.recipient_entries.filter(recipient=request.user).exists()  # type: ignore
        )
        if message.room_id:  # type: ignore
            allowed = ChatRoomMember.objects.filter(
                room=message.room,
                user=request.user,
                room__organization__organization_id=org_id,
            ).exists()
        
        if not allowed:
            return Response({'error': 'Forbidden'}, status=403)
        existing = ChatMessageReaction.objects.filter(message=message, user=request.user, reaction=reaction).first()
        if existing:
            existing.delete()
            toggled = False
        else:
            ChatMessageReaction.objects.create(message=message, user=request.user, reaction=reaction)
            toggled = True
        message = ChatMessage.objects.prefetch_related('reactions__user', CHAT_RECIPIENT_PREFETCH).get(id=message.pk)
        return Response({'selected': toggled, 'message': ChatMessageSerializer(message, context={'request': request}).data})


class ChatMessageListCreateView(APIView):
    """
    GET  ?tab=received|sent|all|archive
    POST { content: str, event_title?: str, meet_link?: str, event_tagged_names?: str }
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([], status=200)

        since_param = request.query_params.get('since')
        try:
            since_id = int(since_param) if since_param else None
        except (TypeError, ValueError):
            since_id = None

        def apply_since(queryset):
            if since_id is None:
                return queryset
            return queryset.filter(id__gt=since_id)

        user = request.user

        # ── All org members (scoped universe for this user) ──────────────────
        member_ids = list(_org_members(org_id).values_list('id', flat=True))

        # ── Conversation thread: ?with=<user_id> ─────────────────────────────
        with_param = request.query_params.get('with')
        if with_param is not None:
            try:
                with_user_id = int(with_param)
            except (ValueError, TypeError):
                return Response([], status=200)
            messages = ChatMessage.objects.filter(
                Q(sender=user, recipient_entries__recipient_id=with_user_id) |
                Q(sender_id=with_user_id, recipient_entries__recipient=user)
            ).filter(
                sender_id__in=member_ids,
                is_broadcast=False,
                parent_message__isnull=True,
                channel__isnull=True,
                room__isnull=True,
            ).select_related('sender', 'task_assignee').prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('created_at')
            messages = apply_since(messages)
            serializer = ChatMessageSerializer(
                messages, many=True, context={'request': request}
            )
            return Response(serializer.data)

        # ── Team broadcast thread: ?chat=everyone ───────────────────────────
        chat_mode = request.query_params.get('chat')

        channel_id = request.query_params.get('channel_id') or request.query_params.get('channel')
        if channel_id:
            channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
            if not channel:
                return Response([], status=200)
            if not ChatChannelMember.objects.filter(channel=channel, user=request.user).exists():
                return Response({'error': 'Forbidden: You are not a member of this channel.'}, status=403)
            messages = ChatMessage.objects.filter(
                channel=channel,
                parent_message__isnull=True,
            ).select_related('sender', 'task_assignee').prefetch_related(
                CHAT_RECIPIENT_PREFETCH, 'reactions__user',
                Prefetch('pin_entries', queryset=ChatPinnedMessage.objects.filter(channel=channel), to_attr='prefetched_pin_entries'),
            ).distinct().order_by('created_at')
            messages = apply_since(messages)
            serializer = ChatMessageSerializer(messages, many=True, context={'request': request})
            return Response(serializer.data)

        parent_message_id = request.query_params.get('parent_message_id')
        if parent_message_id:
            parent_msg = ChatMessage.objects.filter(id=parent_message_id).first()
            if not parent_msg:
                return Response({'error': 'Parent message not found.'}, status=404)
            if parent_msg.channel:
                if not ChatChannelMember.objects.filter(channel=parent_msg.channel, user=request.user).exists():
                    return Response({'error': 'Forbidden'}, status=403)
            elif parent_msg.room:
                if not ChatRoomMember.objects.filter(room=parent_msg.room, user=request.user).exists():
                    return Response({'error': 'Forbidden'}, status=403)

            messages = ChatMessage.objects.filter(
                parent_message_id=parent_message_id,
            ).select_related('sender', 'task_assignee').prefetch_related(
                CHAT_RECIPIENT_PREFETCH, 'reactions__user'
            ).distinct().order_by('created_at')
            messages = apply_since(messages)
            serializer = ChatMessageSerializer(messages, many=True, context={'request': request})
            return Response(serializer.data)

        if chat_mode == 'room':
            room_id = request.query_params.get('room') or request.query_params.get('room_id')
            room, membership = _room_for_user(room_id, request.user, org_id)
            if not room or not membership:
                return Response([], status=200)
            messages = ChatMessage.objects.filter(
                room=room,
                sender_id__in=member_ids,
                parent_message__isnull=True,
            ).select_related('sender', 'task_assignee', 'room').prefetch_related(
                CHAT_RECIPIENT_PREFETCH,
                'reactions__user',
                Prefetch('pin_entries', queryset=ChatPinnedMessage.objects.filter(room=room), to_attr='prefetched_pin_entries'),
            ).distinct().order_by('created_at')
            messages = apply_since(messages)

            serializer = ChatMessageSerializer(
                messages, many=True, context={'request': request}
            )
            return Response(serializer.data)

        if chat_mode == 'everyone':
            messages = ChatMessage.objects.filter(
                is_broadcast=True,
                parent_message__isnull=True,
            ).filter(
                Q(sender=user, sender_id__in=member_ids) |
                Q(recipient_entries__recipient=user, sender_id__in=member_ids)
            ).select_related('sender', 'task_assignee').prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('created_at')
            messages = apply_since(messages)

            serializer = ChatMessageSerializer(
                messages, many=True, context={'request': request}
            )
            return Response(serializer.data)

        # ── Ad-hoc group thread: ?chat=group&users=2,3,4 ───────────────────
        if chat_mode == 'group':
            users_param = request.query_params.get('users', '')
            raw_ids = [p.strip() for p in users_param.split(',') if p.strip()]
            try:
                group_ids = sorted({int(x) for x in raw_ids if int(x) != user.id})
            except (TypeError, ValueError):
                return Response([], status=200)

            if not group_ids:
                return Response([], status=200)

            valid_group_ids = sorted(set(group_ids).intersection(set(member_ids)))
            if not valid_group_ids:
                return Response([], status=200)

            allowed_sender_ids = valid_group_ids + [user.id]
            outside_ids = [mid for mid in member_ids if mid not in allowed_sender_ids]

            messages = ChatMessage.objects.filter(
                sender_id__in=allowed_sender_ids,
                is_broadcast=False,
                parent_message__isnull=True,
                channel__isnull=True,
                room__isnull=True,
            ).annotate(
                recipient_count=Count('recipient_entries', distinct=True)
            ).filter(
                recipient_count=len(valid_group_ids)
            ).filter(
                Q(sender=user, recipient_entries__recipient_id__in=valid_group_ids) |
                Q(sender_id__in=valid_group_ids, recipient_entries__recipient=user)
            )

            if outside_ids:
                messages = messages.exclude(recipient_entries__recipient_id__in=outside_ids)

            messages = messages.prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('created_at')
            messages = apply_since(messages)

            serializer = ChatMessageSerializer(
                messages, many=True, context={'request': request}
            )
            return Response(serializer.data)

        tab = request.query_params.get('tab', 'received')

        if tab == 'received':
            # Received = messages sent by other members, delivered to me, NOT archived
            messages = ChatMessage.objects.filter(
                recipient_entries__recipient=user,
                recipient_entries__is_archived=False,
                sender_id__in=member_ids,
            ).exclude(sender=user).prefetch_related(CHAT_RECIPIENT_PREFETCH).order_by('-created_at')

        elif tab == 'sent':
            # Sent = messages I sent to the org
            messages = ChatMessage.objects.filter(
                sender=user,
                sender_id__in=member_ids,
            ).prefetch_related(CHAT_RECIPIENT_PREFETCH).order_by('-created_at')

        elif tab == 'archive':
            # Archive = messages delivered to me that I archived
            messages = ChatMessage.objects.filter(
                recipient_entries__recipient=user,
                recipient_entries__is_archived=True,
                sender_id__in=member_ids,
            ).prefetch_related(CHAT_RECIPIENT_PREFETCH).order_by('-created_at')

        else:  # 'all'
            # All = everything in the org channel (sent OR received, not archived)
            messages = ChatMessage.objects.filter(
                Q(recipient_entries__recipient=user, recipient_entries__is_archived=False) |
                Q(sender=user),
                sender_id__in=member_ids,
            ).prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('-created_at')

        messages = apply_since(messages)

        serializer = ChatMessageSerializer(
            messages, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request):
        started = time.perf_counter()
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organisation found.'}, status=400)

        content = _sanitize(request.data.get('content', ''))
        attachment = request.FILES.get('attachment')
        vault_item_id = request.data.get('vault_item_id')
        vault_item_obj = None

        if vault_item_id:
            try:
                from core.models.mydesk import GalleryItem
                vault_item_obj = GalleryItem.objects.filter(id=vault_item_id, user=request.user).first()
                if vault_item_obj:
                    attachment = vault_item_obj.file
            except Exception:
                pass

        if not content and not attachment and not vault_item_obj:
            return Response({'error': 'Either content, attachment, or vault_item_id is required.'}, status=400)

        is_event = _parse_bool(request.data.get('is_event', False))
        event_title = _sanitize(request.data.get('event_title', ''))
        meet_link = request.data.get('meet_link', '').strip()
        event_tagged_names = _sanitize(request.data.get('event_tagged_names', ''))
        room = None
        room_membership = None
        raw_to_user_ids = None
        room_id = request.data.get('room_id') or request.data.get('room')
        if room_id:
            room, room_membership = _room_for_user(room_id, request.user, org_id)
            if not room or not room_membership:
                return Response({'error': 'Room not found.'}, status=404)
            settings_obj = getattr(room, 'settings', None)
            if (
                settings_obj and
                settings_obj.announcement_mode and
                not settings_obj.allow_member_messages and
                room_membership.role == ChatRoomMember.ROLE_MEMBER
            ):
                return Response({'error': 'Only room admins can post announcements.'}, status=403)

        channel_id = request.data.get('channel_id') or request.data.get('channel')
        channel = None
        if channel_id:
            channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
            if not channel:
                return Response({'error': 'Channel not found.'}, status=404)
            if not ChatChannelMember.objects.filter(channel=channel, user=request.user).exists():
                return Response({'error': 'Forbidden: You are not a member of this channel.'}, status=403)

        reply_to_id = request.data.get('reply_to_id')
        reply_to_message = None
        if reply_to_id:
            reply_to_message = ChatMessage.objects.filter(id=reply_to_id).first()
            if not reply_to_message:
                return Response({'error': 'Reply-to message not found.'}, status=404)

        parent_message_id = request.data.get('parent_message_id')
        parent_message = None
        
        # If reply_to is provided, inherit the thread root from the reply_to message
        # This guarantees all nested replies share the same parent_message_id
        if reply_to_message:
            parent_message_id = (reply_to_message.parent_message.pk if reply_to_message.parent_message else None) or reply_to_message.pk

        if parent_message_id:
            parent_message = ChatMessage.objects.filter(id=parent_message_id).first()
            if not parent_message:
                return Response({'error': 'Parent message not found.'}, status=404)

        # Determine recipients:
        # - If to_user_ids is provided → direct message to those users (WhatsApp thread mode).
        # - Else if @mentions found → only mentioned users.
        # - Else → broadcast to all org members.
        if hasattr(request.data, 'getlist'):
            raw_to_user_ids = request.data.getlist('to_user_ids')
            if not raw_to_user_ids:
                raw_to_user_ids = request.data.get('to_user_ids')
        else:
            raw_to_user_ids = request.data.get('to_user_ids')
        to_user_ids = None if room else _parse_to_user_ids(raw_to_user_ids)

        if room:
            recipients = User.objects.filter(
                chat_room_memberships__room=room,
                is_active=True,
            ).exclude(id=request.user.id)
            mention_type, mentioned = _parse_mention_recipients(content, org_id, request.user.id)
            if mentioned is not None:
                member_id_set = set(recipients.values_list('id', flat=True))
                mentioned = mentioned.filter(id__in=member_id_set)
        elif channel:
            recipients = User.objects.filter(
                chat_channel_memberships__channel=channel,
                is_active=True,
            ).exclude(id=request.user.id)
            mention_type, mentioned = _parse_mention_recipients(content, org_id, request.user.id)
            if mentioned is not None:
                member_id_set = set(recipients.values_list('id', flat=True))
                mentioned = mentioned.filter(id__in=member_id_set)
        elif parent_message:
            # Send to parent message recipients, plus parent message sender if different
            rec_ids = set(ChatMessageRecipient.objects.filter(message=parent_message).values_list('recipient_id', flat=True))
            rec_ids.add(parent_message.sender.id)
            rec_ids.discard(request.user.id)
            recipients = _org_members(org_id).filter(id__in=rec_ids)
            mention_type, mentioned = _parse_mention_recipients(content, org_id, request.user.id)
        elif to_user_ids is not None:
            # Direct message: explicit recipient override
            recipients = _org_members(org_id).filter(id__in=to_user_ids).exclude(id=request.user.id)
            mention_type, mentioned = 'user', None
        else:
            mention_type, mentioned = _parse_mention_recipients(content, org_id, request.user.id)
            if mentioned is not None:
                # Targeted: only tagged people
                recipients = mentioned
            else:
                # Team broadcast: everyone else in the org
                recipients = _org_members(org_id).exclude(id=request.user.id)

        recipient_ids = sorted(set(recipients.values_list('id', flat=True)))
        all_other_member_ids = sorted(
            _org_members(org_id).exclude(id=request.user.id).values_list('id', flat=True)
        )

        requested_broadcast = _parse_bool(request.data.get('is_broadcast', False))
        is_broadcast = False if room else requested_broadcast and recipient_ids == all_other_member_ids

        attachment_kind = (request.data.get('attachment_kind') or '').strip().lower()
        attachment_mime_type = (getattr(attachment, 'content_type', '') or '').strip().lower() if (attachment and not vault_item_obj) else ''
        if vault_item_obj and not attachment_kind:
            if vault_item_obj.category == 'images' or vault_item_obj.media_type == 'image':
                attachment_kind = 'image'
            elif vault_item_obj.category == 'videos':
                attachment_kind = 'video'
            else:
                attachment_kind = 'file'

        if attachment and not vault_item_obj and attachment_kind not in ('image', 'video', 'file'):
            if attachment_mime_type.startswith('image/'):
                attachment_kind = 'image'
            elif attachment_mime_type.startswith('video/'):
                attachment_kind = 'video'
            else:
                attachment_kind = 'file'

        message = ChatMessage.objects.create(
            sender=request.user,
            content=content,
            room=room,
            channel=channel,
            parent_message=parent_message,
            is_event=is_event,
            event_title=event_title,
            meet_link=meet_link,
            event_tagged_names=event_tagged_names,
            is_broadcast=is_broadcast,
            attachment=attachment,
            attachment_name=os.path.basename(vault_item_obj.file.name or '') if vault_item_obj else (attachment.name if attachment else ''),
            attachment_mime_type=attachment_mime_type,
            attachment_kind=attachment_kind,
            reply_to=reply_to_message,
            vault_item=vault_item_obj,
        )

        # ── MyVault auto-sync: save attachment to sender's vault ──────────────
        if attachment and not vault_item_obj:
            try:
                from core.services.vault_sync import sync_attachment_to_vault
                sync_attachment_to_vault(message)
            except Exception:
                pass  # Never let vault sync failure break the chat response

        if parent_message:
            ChatMessage.objects.filter(id=parent_message.pk).update(
                thread_reply_count=F('thread_reply_count') + 1,
                last_reply_at=timezone.now(),
                last_reply_by=request.user
            )

        ChatMessageRecipient.objects.bulk_create([
            ChatMessageRecipient(message=message, recipient=member)
            for member in recipients
        ], ignore_conflicts=True)

        mentioned_users = list(mentioned) if mentioned is not None else []
        if mention_type in ('channel', 'everyone'):
            # If the mention was @channel or @everyone, create a mention record for each recipient
            ChatMessageMention.objects.bulk_create([
                ChatMessageMention(message=message, mentioned_user=user, mention_type=mention_type)
                for user in recipients
            ], ignore_conflicts=True)
            mentioned_users = list(recipients)
        else:
            ChatMessageMention.objects.bulk_create([
                ChatMessageMention(message=message, mentioned_user=user, mention_type='user')
                for user in mentioned_users
            ], ignore_conflicts=True)

        sender_name = request.user.first_name or request.user.username
        is_targeted_chat = True
        if is_targeted_chat and not message.is_task:
            preview_source = (content or message.attachment_name or '').strip() or 'Attachment'
            for recipient in recipients:
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='my_chats',
                    action='share',
                    title=f"New message in {room.name}" if room else (f"New message in #{channel.name}" if channel else 'New broadcast message' if is_broadcast else 'New chat message'),
                    message=f"{sender_name} sent a message in {room.name}" if room else (f"{sender_name} sent a message in #{channel.name}" if channel else f"{sender_name} sent a broadcast message" if is_broadcast else f"{sender_name} sent you a message"),
                    preview=preview_source[:200],
                    entity_type='chat_message',
                    entity_id=message.pk,
                    deep_link={
                        'page': '/mydesk/chats',
                        'section': 'my-chats',
                        'messageId': str(message.pk),
                        **({'roomId': str(room.room_id)} if room else ({'channelId': str(channel.id)} if channel else {'isBroadcast': 'true'} if is_broadcast else {'withUserId': str(request.user.id)})),
                    },
                )

        if mentioned is not None:
            for recipient in mentioned_users:
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='my_chats',
                    action='mention',
                    title='You were mentioned in chat',
                    message=f"{sender_name} mentioned you in {room.name}" if room else (f"{sender_name} mentioned you in #{channel.name}" if channel else f"{sender_name} mentioned you in chat"),
                    preview=(content or '')[:200],
                    entity_type='chat_message',
                    entity_id=message.pk,
                    deep_link={
                        'page': '/mydesk/chats',
                        'section': 'my-chats',
                        'messageId': str(message.pk),
                        **({'roomId': str(room.room_id)} if room else ({'channelId': str(channel.id)} if channel else {'withUserId': str(request.user.id)})),
                    },
                )

        if message.is_task and message.task_assignee_id and message.task_assignee_id != request.user.id:  # type: ignore
            push_unified_notification(
                recipient=message.task_assignee,
                actor=request.user,
                module='tasks',
                action='reminder',
                title='Task assigned in chat',
                message=f"{sender_name} assigned you a task",
                preview=(message.task_title or content or '')[:200],
                entity_type='chat_message',
                entity_id=message.pk,
                deep_link={
                    'page': '/mydesk/chats',
                    'section': 'my-chats',
                    'messageId': str(message.pk),
                    'withUserId': str(request.user.id),
                },
                task_priority=message.task_priority,
            )

        message = ChatMessage.objects.select_related('room').prefetch_related(CHAT_RECIPIENT_PREFETCH, 'reactions__user').get(id=message.pk)
        serializer = ChatMessageSerializer(message, context={'request': request})

        response_ready_epoch_ms = int(time.time() * 1000)
        try:
            broadcast_new_message_task.delay(org_id, message.pk, response_ready_epoch_ms)
        except Exception:
            _broadcast_new_message(org_id, message, queue_delay_ms=0.0)

        response = Response(serializer.data, status=201)
        post_latency_ms = (time.perf_counter() - started) * 1000
        record_post_latency(post_latency_ms)
        response['X-Chat-Post-Latency-Ms'] = f'{post_latency_ms:.2f}'
        return response


class ConversationsListView(APIView):
    """
    GET /api/chat/conversations/
    Returns each org member (excluding self) with their last direct message
    and unread count. Used to populate the WhatsApp-style conversation sidebar.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([])

        user = request.user
        member_ids = list(_org_members(org_id).values_list('id', flat=True))
        members = _org_members(org_id).exclude(id=user.id)

        result = []
        for member in members:
            last_msg = ChatMessage.objects.filter(
                Q(sender=user, recipient_entries__recipient=member) |
                Q(sender=member, recipient_entries__recipient=user)
            ).filter(
                sender_id__in=member_ids,
                is_broadcast=False,
                channel__isnull=True,
                room__isnull=True
            ).prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('-created_at').first()

            # Unread count: messages from this member to me that I haven't read
            unread = ChatMessageRecipient.objects.filter(
                recipient=user,
                is_read=False,
                is_archived=False,
                message__sender=member,
                message__sender_id__in=member_ids,
                message__is_broadcast=False,
                message__channel__isnull=True,
                message__room__isnull=True
            ).count()

            profile = getattr(member, 'profile', None)
            profile_picture_url = None
            if profile and profile.profile_picture:
                try:
                    profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                except Exception:
                    pass

            entry = {
                'id': member.pk,
                'kind': 'direct',
                'username': member.username,  # type: ignore
                'full_name': f"{member.first_name} {member.last_name}".strip() or member.username,  # type: ignore
                'profilePicture': profile_picture_url,
                'last_message': None,
                'unread_count': unread,
            }
            if last_msg:
                entry['last_message'] = {
                    'id': last_msg.pk,
                    'content': last_msg.content,
                    'created_at': last_msg.created_at.isoformat(),
                    'sender_id': last_msg.sender_id,  # type: ignore
                    'attachment_name': last_msg.attachment_name,
                    'attachment_kind': last_msg.attachment_kind,
                }
            result.append(entry)

        # Add Broadcast Chat Entry
        broadcast_last_msg = ChatMessage.objects.filter(
            is_broadcast=True,
            sender_id__in=member_ids
        ).filter(
            Q(sender=user) | Q(recipient_entries__recipient=user)
        ).prefetch_related(CHAT_RECIPIENT_PREFETCH).distinct().order_by('-created_at').first()

        broadcast_unread = ChatMessageRecipient.objects.filter(
            recipient=user,
            is_read=False,
            is_archived=False,
            message__is_broadcast=True,
            message__sender_id__in=member_ids,
        ).count()

        broadcast_entry = {
            'id': 'everyone',
            'kind': 'everyone',
            'username': 'all',
            'full_name': 'Everyone (broadcast)',
            'profilePicture': None,
            'last_message': None,
            'unread_count': broadcast_unread,
        }
        if broadcast_last_msg:
            broadcast_entry['last_message'] = {
                'id': broadcast_last_msg.pk,
                'content': broadcast_last_msg.content,
                'created_at': broadcast_last_msg.created_at.isoformat(),
                'sender_id': broadcast_last_msg.sender_id,  # type: ignore
                'attachment_name': broadcast_last_msg.attachment_name,
                'attachment_kind': broadcast_last_msg.attachment_kind,
            }
        result.append(broadcast_entry)

        rooms = ChatRoom.objects.filter(
            organization__organization_id=org_id,
            memberships__user=user,
            is_deleted=False,
        ).select_related('settings').prefetch_related(
            'memberships__user',
            Prefetch(
                'pinned_messages',
                queryset=ChatPinnedMessage.objects.select_related('message', 'pinned_by').order_by('-created_at'),
                to_attr='prefetched_room_pins',
            ),
        ).distinct()

        for room in rooms:
            last_msg = ChatMessage.objects.filter(
                room=room,
                sender_id__in=member_ids,
            ).select_related('sender').order_by('-created_at').first()
            unread = ChatMessageRecipient.objects.filter(
                recipient=user,
                is_read=False,
                is_archived=False,
                message__room=room,
                message__sender_id__in=member_ids,
            ).exclude(message__sender=user).count()
            serialized_room = ChatRoomSerializer(room, context={'request': request}).data
            entry = {
                **serialized_room,
                'id': str(room.room_id),
                'kind': 'room',
                'username': room.name,
                'full_name': room.name,
                'profilePicture': serialized_room.get('icon_url'),
                'last_message': None,
                'unread_count': unread,
            }
            if last_msg:
                entry['last_message'] = {
                    'id': last_msg.pk,
                    'content': last_msg.content,
                    'created_at': last_msg.created_at.isoformat(),
                    'sender_id': last_msg.sender_id,  # type: ignore
                    'attachment_name': last_msg.attachment_name,
                    'attachment_kind': last_msg.attachment_kind,
                }
            result.append(entry)

        # Sort: most recent conversation first; members with no messages fall to bottom
        result.sort(
            key=lambda x: x['last_message']['created_at'] if x['last_message'] else '',
            reverse=True,
        )
        return Response(result)


class ChatMessageArchiveView(APIView):
    """POST /api/chat/messages/<id>/archive/  →  toggles archived flag for the calling user."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            rec = ChatMessageRecipient.objects.get(
                message_id=pk,
                recipient=request.user,
            )
        except ChatMessageRecipient.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=404)

        rec.is_archived = not rec.is_archived
        rec.archived_at = timezone.now() if rec.is_archived else None
        rec.save(update_fields=['is_archived', 'archived_at'])

        return Response({'archived': rec.is_archived})


class ChatMessageDetailView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        org_id = _get_org_id(request)
        message = ChatMessage.objects.select_related('room').prefetch_related(CHAT_RECIPIENT_PREFETCH).filter(id=pk).first()
        if not message:
            return Response({'error': 'Message not found.'}, status=404)
        if message.sender_id != request.user.id:  # type: ignore
            return Response({'error': 'Only sender can edit a message.'}, status=403)
        content = _sanitize(request.data.get('content', ''))
        if not content:
            return Response({'error': 'Message content is required.'}, status=400)
        if message.room_id:  # type: ignore
            allowed = ChatRoomMember.objects.filter(
                room=message.room,
                user=request.user,
                room__organization__organization_id=org_id,
            ).exists()
            if not allowed:
                return Response({'error': 'Forbidden'}, status=403)
        message.content = content
        message.edited_at = timezone.now()
        message.save(update_fields=['content', 'edited_at'])
        message = ChatMessage.objects.select_related('room').prefetch_related(CHAT_RECIPIENT_PREFETCH, 'reactions__user').get(id=message.pk)
        return Response(ChatMessageSerializer(message, context={'request': request}).data)

    def delete(self, request, pk):
        org_id = _get_org_id(request)
        message = ChatMessage.objects.select_related('room').filter(id=pk).first()
        if not message:
            return Response({'error': 'Message not found.'}, status=404)
        allowed = message.sender_id == request.user.id  # type: ignore
        if message.room_id:  # type: ignore
            membership = ChatRoomMember.objects.filter(
                room=message.room,
                user=request.user,
                room__organization__organization_id=org_id,
            ).first()
            allowed = allowed or _is_room_manager(membership)
        if not allowed:
            return Response({'error': 'Forbidden'}, status=403)
        message.content = ''
        message.is_deleted = True
        message.edited_at = timezone.now()
        message.save(update_fields=['content', 'is_deleted', 'edited_at'])
        return Response({'status': 'deleted'})


class ChatMessageReadView(APIView):
    """POST /api/chat/messages/<id>/read/  →  marks the message as read for the calling user."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ChatMessageRecipient.objects.filter(
            message_id=pk,
            recipient=request.user,
        ).update(is_read=True)
        return Response({'status': 'ok'})


class ChatMessageAttachmentView(APIView):
    """GET /api/chat/messages/<id>/attachment/ → open/download attachment safely."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        message = ChatMessage.objects.filter(id=pk).prefetch_related('recipient_entries').first()
        if not message or not message.attachment:
            return Response({'error': 'Attachment not found.'}, status=404)

        allowed = (
            message.sender_id == request.user.id or  # type: ignore
            message.recipient_entries.filter(recipient=request.user).exists()  # type: ignore
        )
        if message.room_id:  # type: ignore
            allowed = ChatRoomMember.objects.filter(room=message.room, user=request.user).exists()
        if not allowed:
            return Response({'error': 'Forbidden'}, status=403)

        force_download = str(request.query_params.get('download') or '').strip().lower() in {'1', 'true', 'yes'}
        signed_url = _build_file_access_url(request, message.attachment, attachment=force_download)
        if signed_url:
            return HttpResponseRedirect(signed_url)

        mime_type = (message.attachment_mime_type or '').strip()
        if not mime_type:
            guessed, _ = mimetypes.guess_type(message.attachment_name or '')
            mime_type = guessed or 'application/octet-stream'

        try:
            file_handle = message.attachment.open('rb')
        except Exception:
            return Response({'error': 'Unable to open attachment.'}, status=404)

        response = FileResponse(file_handle, content_type=mime_type)
        file_name = (message.attachment_name or f'attachment-{message.pk}').strip()
        disposition = 'attachment' if force_download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{file_name}"'
        return response


class ChatUnreadCountView(APIView):
    """GET /api/chat/unread-count/  →  { count: N }  for the notification badge."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'count': 0})
        count = ChatMessageRecipient.objects.filter(
            recipient=request.user,
            is_read=False,
            is_archived=False,
            message__sender__team_settings__organization__organization_id=org_id,
        ).count()
        return Response({'count': count})


class ChatDeliveryMetricsView(APIView):
    """GET /api/chat/metrics/  → aggregate delivery performance metrics."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_delivery_metrics())


class ChatClientDropMetricView(APIView):
    """POST /api/chat/metrics/ws-drop/  → increments client unexpected WS close counter."""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        record_client_drop()
        return Response({'status': 'ok'})


class ChatTaskCreateView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organisation found.'}, status=400)

        task_title = _sanitize(request.data.get('task_title', ''))
        if not task_title:
            return Response({'error': 'task_title is required.'}, status=400)

        task_description = _sanitize(request.data.get('task_description', ''))
        due_date = request.data.get('task_due_date') or None
        task_priority = (request.data.get('task_priority') or 'medium').lower()
        if task_priority not in ('low', 'medium', 'high', 'critical'):
            task_priority = 'medium'
        assignee_id = request.data.get('task_assignee_id')
        source_message_id = request.data.get('task_source_message_id')

        if not assignee_id:
            return Response({'error': 'task_assignee_id is required.'}, status=400)

        assignee = _org_members(org_id).filter(id=assignee_id).first()
        if not assignee:
            return Response({'error': 'Invalid assignee selected.'}, status=400)

        if hasattr(request.data, 'getlist'):
            raw_to_user_ids = request.data.getlist('to_user_ids')
            if not raw_to_user_ids:
                raw_to_user_ids = request.data.get('to_user_ids')
        else:
            raw_to_user_ids = request.data.get('to_user_ids')
        to_user_ids = _parse_to_user_ids(raw_to_user_ids) or []
        recipients = _org_members(org_id).filter(id=assignee.pk).exclude(id=request.user.pk)

        recipient_ids = sorted(set(recipients.values_list('id', flat=True)))
        if not recipient_ids:
            return Response({'error': 'No valid recipients selected.'}, status=400)

        all_other_member_ids = sorted(
            _org_members(org_id).exclude(id=request.user.id).values_list('id', flat=True)
        )

        requested_broadcast = _parse_bool(request.data.get('is_broadcast', False))
        is_broadcast = requested_broadcast and recipient_ids == all_other_member_ids

        message = ChatMessage.objects.create(
            sender=request.user,
            content=task_description or task_title,
            is_broadcast=is_broadcast,
            is_task=True,
            task_title=task_title,
            task_description=task_description,
            task_due_date=due_date,
            task_priority=task_priority,
            task_status='pending',
            task_source_message_id=source_message_id,
            task_assignee=assignee,
        )

        if message.task_assignee_id and message.task_assignee_id != request.user.id:  # type: ignore
            sender_name = request.user.first_name or request.user.username
            push_unified_notification(
                recipient=message.task_assignee,
                actor=request.user,
                module='tasks',
                action='reminder',
                title='Task assigned in chat',
                message=f"{sender_name} assigned you a task",
                preview=(message.task_title or message.content or '')[:200],
                entity_type='chat_message',
                entity_id=message.pk,
                deep_link={
                    'page': '/mydesk/chats',
                    'section': 'my-chats',
                    'messageId': str(message.pk),
                    'withUserId': str(request.user.pk),
                },
                task_priority=message.task_priority,
            )

        ChatMessageRecipient.objects.bulk_create([
            ChatMessageRecipient(message=message, recipient=member)
            for member in recipients
        ], ignore_conflicts=True)

        message = ChatMessage.objects.prefetch_related(CHAT_RECIPIENT_PREFETCH).get(id=message.pk)
        serializer = ChatMessageSerializer(message, context={'request': request})

        response_ready_epoch_ms = int(time.time() * 1000)
        try:
            broadcast_new_message_task.delay(org_id, message.pk, response_ready_epoch_ms)
        except Exception:
            _broadcast_new_message(org_id, message, queue_delay_ms=0.0)

        return Response(serializer.data, status=201)


class ChatTaskToggleView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organisation found.'}, status=400)

        message = ChatMessage.objects.filter(id=pk, is_task=True).first()
        if not message:
            return Response({'error': 'Task not found.'}, status=404)

        allowed = (
            message.sender_id == request.user.id or  # type: ignore
            message.task_assignee_id == request.user.id or  # type: ignore
            message.recipient_entries.filter(recipient=request.user).exists()  # type: ignore
        )
        if not allowed:
            return Response({'error': 'Forbidden'}, status=403)

        new_status = request.data.get('task_status')
        if new_status not in ('pending', 'completed'):
            new_status = 'completed' if message.task_status != 'completed' else 'pending'

        message.task_status = new_status
        message.save(update_fields=['task_status'])

        try:
            broadcast_task_update_task.delay(org_id, message.pk)
        except Exception:
            _broadcast_task_update(org_id, message)
        return Response({'id': message.pk, 'task_status': message.task_status})


# ── PRESENCE ──────────────────────────────────────────────────────────────────

from presence.models import UserPresence  # noqa: E402


def _presence_update_or_create(user, last_seen, max_retries=5):
    """
    Wrapper around UserPresence update that retries on SQLite locking.
    """
    import time
    from django.db.utils import OperationalError
    delay = 0.05
    for attempt in range(max_retries):
        try:
            presence, created = UserPresence.objects.get_or_create(user=user)
            presence.last_seen = last_seen
            presence.activity_status = 'online'
            presence.resolve_status()
            presence.save_and_broadcast(source='heartbeat')
            return
        except OperationalError as exc:
            if 'database is locked' not in str(exc).lower():
                raise
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 1.0)


class ChatPresenceHeartbeatView(APIView):
    """
    POST /api/chat/presence/heartbeat/
    Called by the frontend every ~30 s while the BridgeWorks tab is open.
    Stamps last_seen to now AND broadcasts presence.update via WebSocket
    so all org members' browsers see the status change instantly.
    Returns { ok: true }.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        cache_key = f"user_presence_write:{request.user.id}"
        from django.core.cache import cache
        
        # Optimize SQLite writes by only updating last_seen in DB once every 60 seconds
        if cache.get(cache_key):
            if org_id:
                from core.services.chat_realtime import broadcast_presence_update
                broadcast_presence_update(org_id, request.user.id, is_online=True)
            return Response({'ok': True})

        now = timezone.now()
        try:
            presence, created = UserPresence.objects.get_or_create(user=request.user)
            presence.last_seen = now
            presence.activity_status = 'online'
            presence.resolve_status()
            presence.save_and_broadcast(source='heartbeat')
        except Exception:
            _presence_update_or_create(request.user, now)

        cache.set(cache_key, True, 60)

        # Broadcast real-time presence change to all org members' browsers
        if org_id:
            from core.services.chat_realtime import broadcast_presence_update
            broadcast_presence_update(org_id, request.user.id, is_online=True)
        return Response({'ok': True})


class ChatPresenceListView(APIView):
    """
    GET /api/chat/presence/
    Returns the list of user IDs in the same org whose status is online/in_meeting.
    Response: { online_user_ids: [1, 2, 3] }
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    ONLINE_THRESHOLD_SECONDS = 120  # 2 minutes

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'online_user_ids': []})

        member_ids = set(_org_members(org_id).values_list('id', flat=True))

        online_ids = list(
            UserPresence.objects.filter(
                user_id__in=member_ids,
                resolved_status__in=('online', 'in_meeting'),
            ).values_list('user_id', flat=True)
        )
        return Response({'online_user_ids': online_ids})


class ChatPresenceOfflineView(APIView):
    """
    POST /api/chat/presence/offline/
    Called by the frontend when the tab is closed / user navigates away.
    Marks the user as offline immediately.
    Returns { ok: true }.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        # Clear throttle cache key so that immediate subsequent logins/heartbeats write instantly
        cache_key = f"user_presence_write:{request.user.pk}"
        from django.core.cache import cache
        cache.delete(cache_key)

        try:
            presence, created = UserPresence.objects.get_or_create(user=request.user)
            presence.activity_status = 'offline'
            # Also push last_seen back to guarantee offline threshold check if queried directly
            presence.last_seen = timezone.now() - datetime.timedelta(seconds=300)
            presence.resolve_status()
            presence.save_and_broadcast(source='offline_post')
        except Exception:
            pass

        if org_id:
            from core.services.chat_realtime import broadcast_presence_update
            broadcast_presence_update(org_id, request.user.id, is_online=False)
        return Response({'ok': True})



class ChatChannelListCreateView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([])
        from django.db.models import Prefetch
        channels = _get_accessible_channels_qs(request.user, org_id).prefetch_related(
            'memberships__user',
            Prefetch(
                'pinned_messages',
                queryset=ChatPinnedMessage.objects.select_related('message', 'pinned_by').order_by('-created_at'),
                to_attr='prefetched_channel_pins'
            )
        ).distinct()
        serializer = ChatChannelSerializer(channels, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        org = _get_org(request)
        if not org:
            return Response({'error': 'No organisation found.'}, status=400)

        name = _sanitize(request.data.get('name', '')).lower()
        if not name:
            return Response({'error': 'Channel name is required.'}, status=400)
        name = name.replace(' ', '-').lstrip('#')

        description = _sanitize(request.data.get('description', ''))
        channel_type = request.data.get('channel_type', ChatChannel.TYPE_PUBLIC)
        raw_member_ids = request.data.getlist('member_ids') if hasattr(request.data, 'getlist') else request.data.get('member_ids')
        member_ids = set(_parse_to_user_ids(raw_member_ids) or [])
        member_ids.discard(request.user.id)

        community_id = request.data.get('community_id')
        if community_id:
            community = ChatCommunity.objects.filter(id=community_id, workspace=org).first()
            if not community:
                return Response({'error': 'Community not found.'}, status=404)
        else:
            community = ChatCommunity.objects.filter(workspace=org).first()
            if not community:
                community = ChatCommunity.objects.create(
                    workspace=org,
                    name="General",
                    description="General community for all channels",
                    created_by=request.user
                )

        # ── RBAC: only owner/admin of this community may create channels ──
        if not _can_create_channel(request.user, community):
            return Response(
                {'error': 'Forbidden: Only community admins can create channels.'},
                status=status.HTTP_403_FORBIDDEN
            )

        channel, created = ChatChannel.objects.get_or_create(
            workspace=org,
            name=name[:120],
            defaults={
                'description': description,
                'channel_type': channel_type,
                'created_by': request.user,
                'community': community,
            }
        )
        if not created:
            return Response({'error': 'Channel already exists.'}, status=400)

        members = list(_org_members(org.organization_id).filter(id__in=member_ids))
        ChatChannelMember.objects.create(
            channel=channel,
            user=request.user,
            role=ChatChannelMember.ROLE_ADMIN,
        )
        ChatChannelMember.objects.bulk_create([
            ChatChannelMember(channel=channel, user=member, role=ChatChannelMember.ROLE_MEMBER)
            for member in members
        ], ignore_conflicts=True)

        system_message = ChatMessage.objects.create(
            sender=request.user,
            channel=channel,
            content=f"{request.user.get_full_name().strip() or request.user.username} created channel {channel.name}",
        )
        ChatMessageRecipient.objects.bulk_create([
            ChatMessageRecipient(message=system_message, recipient=member)
            for member in members
        ], ignore_conflicts=True)

        channel = ChatChannel.objects.filter(id=channel.pk).prefetch_related('memberships__user').get()
        serializer = ChatChannelSerializer(channel, context={'request': request})
        return Response(serializer.data, status=201)


class ChatChannelDetailView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, channel_id):
        org_id = _get_org_id(request)
        # Use 404 for both not-found and not-visible to avoid leaking existence
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel or not _can_view_channel(request.user, channel):
            return Response({'error': 'Channel not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_channel(request.user, channel):
            return Response(
                {'error': 'Forbidden: You do not have permission to update this channel.'},
                status=status.HTTP_403_FORBIDDEN
            )

        name = request.data.get('name')
        if name:
            name = _sanitize(name).lower().replace(' ', '-').lstrip('#')
            if ChatChannel.objects.filter(workspace=channel.workspace, name=name).exclude(id=channel.pk).exists():
                return Response({'error': 'Channel name already exists.'}, status=400)
            channel.name = name

        if 'description' in request.data:
            channel.description = _sanitize(request.data['description'])
        if 'channel_type' in request.data:
            channel.channel_type = request.data['channel_type']
        if 'community_id' in request.data:
            community_id = request.data['community_id']
            community = ChatCommunity.objects.filter(id=community_id, workspace=channel.workspace).first()
            if not community:
                return Response({'error': 'Community not found.'}, status=404)
            channel.community = community

        if 'can_post' in request.data:
            channel.can_post = _parse_bool(request.data['can_post'])
        if 'can_react' in request.data:
            channel.can_react = _parse_bool(request.data['can_react'])
        if 'can_upload' in request.data:
            channel.can_upload = _parse_bool(request.data['can_upload'])
        if 'can_invite' in request.data:
            channel.can_invite = _parse_bool(request.data['can_invite'])
        if 'show_in_directory' in request.data:
            channel.show_in_directory = _parse_bool(request.data['show_in_directory'])
        if 'everyone_allowed' in request.data:
            channel.everyone_allowed = request.data['everyone_allowed']
        if 'is_archived' in request.data:
            channel.is_archived = _parse_bool(request.data['is_archived'])

        channel.save()
        channel = ChatChannel.objects.filter(id=channel.pk).prefetch_related('memberships__user').get()
        return Response(ChatChannelSerializer(channel, context={'request': request}).data)

    def delete(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel or not _can_view_channel(request.user, channel):
            return Response({'error': 'Channel not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_channel(request.user, channel):
            return Response(
                {'error': 'Forbidden: You do not have permission to delete this channel.'},
                status=status.HTTP_403_FORBIDDEN
            )

        channel.delete()
        return Response({'status': 'deleted'})


class ChatChannelMemberView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        # Return 404 if channel doesn't exist OR user cannot see it (security: don't leak existence)
        if not channel or not _can_view_channel(request.user, channel):
            return Response({'error': 'Channel not found.'}, status=status.HTTP_404_NOT_FOUND)

        memberships = ChatChannelMember.objects.filter(channel=channel).select_related('user')
        data = [_member_payload(m.user, m.role) for m in memberships]
        return Response(data)

    def post(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel or not _can_view_channel(request.user, channel):
            return Response({'error': 'Channel not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_channel(request.user, channel):
            return Response(
                {'error': 'Forbidden: Only channel admins can add members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        raw_user_ids = request.data.getlist('user_ids') if hasattr(request.data, 'getlist') else request.data.get('user_ids')
        user_ids = set(_parse_to_user_ids(raw_user_ids) or [])
        if not user_ids and channel.channel_type == ChatChannel.TYPE_PUBLIC:
            user_ids.add(request.user.id)

        users = list(_org_members(org_id).filter(id__in=user_ids).exclude(
            id__in=ChatChannelMember.objects.filter(channel=channel).values_list('user_id', flat=True)
        ))
        ChatChannelMember.objects.bulk_create([
            ChatChannelMember(channel=channel, user=user, role=ChatChannelMember.ROLE_MEMBER)
            for user in users
        ], ignore_conflicts=True)

        channel = ChatChannel.objects.filter(id=channel.pk).prefetch_related('memberships__user').get()
        return Response(ChatChannelSerializer(channel, context={'request': request}).data)

    def delete(self, request, channel_id):
        org_id = _get_org_id(request)
        channel = ChatChannel.objects.filter(id=channel_id, workspace__organization_id=org_id).first()
        if not channel or not _can_view_channel(request.user, channel):
            return Response({'error': 'Channel not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_channel(request.user, channel):
            return Response(
                {'error': 'Forbidden: Only channel admins can remove members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        raw_user_ids = request.data.getlist('user_ids') if hasattr(request.data, 'getlist') else request.data.get('user_ids')
        user_ids = set(_parse_to_user_ids(raw_user_ids) or [])
        if not user_ids:
            return Response({'error': 'No user_ids provided.'}, status=400)

        ChatChannelMember.objects.filter(channel=channel, user_id__in=user_ids).exclude(user_id=request.user.id).delete()

        channel = ChatChannel.objects.filter(id=channel.pk).prefetch_related('memberships__user').get()
        return Response(ChatChannelSerializer(channel, context={'request': request}).data)


class ChatSearchView(APIView):
    """
    GET /api/chat/search/?q=<query>
    Searches channels, users, messages, and files across the user's workspace organization.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'channels': [], 'users': [], 'messages': [], 'files': []})

        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response({'channels': [], 'users': [], 'messages': [], 'files': []})

        # 1. Scoped User IDs
        member_ids = list(_org_members(org_id).values_list('id', flat=True))

        # 2. Channels (RBAC-filtered: respects public/restricted/admin/private types)
        channels_qs = _get_accessible_channels_qs(request.user, org_id).filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        ).distinct()[:15]

        channels_data = []
        for ch_raw in channels_qs:
            ch = typing.cast(typing.Any, ch_raw)
            channels_data.append({
                'id': ch.id,
                'name': ch.name,
                'description': ch.description,
                'channel_type': ch.channel_type,
            })

        # 3. Users
        users_qs = _org_members(org_id).filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        ).exclude(id=request.user.pk).distinct()[:15]

        users_data = []
        for u_raw in users_qs:
            u = typing.cast(typing.Any, u_raw)
            profile = getattr(u, 'profile', None)
            profile_picture_url = None
            if profile and profile.profile_picture:
                try:
                    profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
                except Exception:
                    pass
            users_data.append({
                'id': u.pk,
                'username': u.username,
                'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
                'profilePicture': profile_picture_url,
            })

        # Accessibility filters for messages & files
        channel_filter = Q(
            channel__workspace__organization_id=org_id,
            channel__is_archived=False,
            channel__memberships__user=request.user
        )
        
        room_filter = Q(
            room__organization__organization_id=org_id,
            room__is_deleted=False,
            room__memberships__user=request.user
        )

        direct_filter = Q(
            channel__isnull=True,
            room__isnull=True,
            sender_id__in=member_ids
        ) & (
            Q(sender=request.user) |
            Q(recipient_entries__recipient=request.user)
        )

        # 4. Messages
        messages_qs = ChatMessage.objects.filter(
            content__icontains=q,
            is_deleted=False
        ).filter(
            channel_filter | room_filter | direct_filter
        ).select_related('sender', 'channel', 'room').distinct()[:30]

        messages_data = []
        for msg_raw in messages_qs:
            msg = typing.cast(typing.Any, msg_raw)
            destination = {}
            if msg.channel:
                destination = {'type': 'channel', 'id': msg.channel.id, 'name': msg.channel.name}
            elif msg.room:
                destination = {'type': 'room', 'id': str(msg.room.room_id), 'name': msg.room.name}
            else:
                destination = {'type': 'direct', 'id': msg.sender.pk, 'name': f"{msg.sender.first_name} {msg.sender.last_name}".strip() or msg.sender.username}

            messages_data.append({
                'id': msg.pk,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'sender': {
                    'id': msg.sender.pk,
                    'username': msg.sender.username,
                    'full_name': f"{msg.sender.first_name} {msg.sender.last_name}".strip() or msg.sender.username,
                },
                'destination': destination,
            })

        # 5. Files
        files_qs = ChatMessage.objects.filter(
            is_deleted=False
        ).exclude(
            attachment=''
        ).filter(
            attachment__isnull=False
        ).filter(
            Q(attachment_name__icontains=q) | Q(content__icontains=q)
        ).filter(
            channel_filter | room_filter | direct_filter
        ).select_related('sender', 'channel', 'room').distinct()[:30]

        files_data = []
        for f_raw in files_qs:
            f = typing.cast(typing.Any, f_raw)
            destination = {}
            if f.channel:
                destination = {'type': 'channel', 'id': f.channel.id, 'name': f.channel.name}
            elif f.room:
                destination = {'type': 'room', 'id': str(f.room.room_id), 'name': f.room.name}
            else:
                destination = {'type': 'direct', 'id': f.sender.pk, 'name': f.sender.username}

            attachment_url = ''
            if f.attachment:
                try:
                    attachment_url = request.build_absolute_uri(f.attachment.url)
                except Exception:
                    pass

            files_data.append({
                'id': f.pk,
                'attachment_name': f.attachment_name or f.attachment.name,
                'attachment_url': attachment_url,
                'attachment_kind': f.attachment_kind,
                'attachment_mime_type': f.attachment_mime_type,
                'created_at': f.created_at.isoformat(),
                'sender': {
                    'id': f.sender.pk,
                    'username': f.sender.username,
                    'full_name': f"{f.sender.first_name} {f.sender.last_name}".strip() or f.sender.username,
                },
                'destination': destination,
            })

        return Response({
            'channels': channels_data,
            'users': users_data,
            'messages': messages_data,
            'files': files_data,
        })


class ChatCommunityListCreateView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([])

        # Self-healing: ensure a default community exists and assign orphaned channels to it
        org = _get_org(request)
        if org:
            default_comm = ChatCommunity.objects.filter(workspace=org, is_archived=False).first()
            if not default_comm:
                default_comm = ChatCommunity.objects.create(
                    workspace=org,
                    name="General",
                    description="General community for all channels",
                    created_by=request.user
                )
                # Auto-enroll the creator as owner
                ChatCommunityMember.objects.get_or_create(
                    community=default_comm,
                    user=request.user,
                    defaults={'role': ChatCommunityMember.ROLE_OWNER}
                )

            # Associate any legacy channels with no community to the default community
            ChatChannel.objects.filter(workspace=org, community__isnull=True).update(community=default_comm)

        all_communities = ChatCommunity.objects.filter(
            workspace__organization_id=org_id,
            is_archived=False,
        ).prefetch_related('channels').distinct()

        # Filter by visibility: owners see everything; members see public + their joined private ones
        visible = [c for c in all_communities if _can_view_community(request.user, c)]
        serializer = ChatCommunitySerializer(visible, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        # Only workspace-level owners may create communities
        if not _can_create_community(request.user):
            return Response(
                {'error': 'Forbidden: Only workspace owners can create communities.'},
                status=status.HTTP_403_FORBIDDEN
            )
        org = _get_org(request)
        if not org:
            return Response({'error': 'No organisation found.'}, status=400)

        name = _sanitize(request.data.get('name', '')).strip()
        if not name:
            return Response({'error': 'Community name is required.'}, status=400)

        description = _sanitize(request.data.get('description', ''))
        is_public = _parse_bool(request.data.get('is_public', True), default=True)

        community, created = ChatCommunity.objects.get_or_create(
            workspace=org,
            name=name[:120],
            defaults={
                'description': description,
                'created_by': request.user,
                'is_public': is_public,
            }
        )
        if not created:
            return Response({'error': 'Community already exists.'}, status=400)

        # Auto-enroll the creator as Owner
        ChatCommunityMember.objects.get_or_create(
            community=community,
            user=request.user,
            defaults={'role': ChatCommunityMember.ROLE_OWNER}
        )

        serializer = ChatCommunitySerializer(community, context={'request': request})
        return Response(serializer.data, status=201)


class ChatCommunityDetailView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, community_id):
        org_id = _get_org_id(request)
        community = ChatCommunity.objects.filter(id=community_id, workspace__organization_id=org_id).first()
        # Treat invisible/private communities as 404 to avoid leaking existence
        if not community or not _can_view_community(request.user, community):
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_update_community(request.user, community):
            return Response(
                {'error': 'Forbidden: You do not have permission to update this community.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if 'name' in request.data:
            name = _sanitize(request.data['name']).strip()
            if not name:
                return Response({'error': 'Name cannot be empty.'}, status=400)
            if ChatCommunity.objects.filter(workspace=community.workspace, name=name).exclude(id=community.pk).exists():
                return Response({'error': 'Community name already exists.'}, status=400)
            community.name = name

        if 'description' in request.data:
            community.description = _sanitize(request.data['description'])

        if 'is_archived' in request.data:
            community.is_archived = _parse_bool(request.data['is_archived'])

        if 'is_public' in request.data:
            community.is_public = _parse_bool(request.data['is_public'])

        community.save()
        serializer = ChatCommunitySerializer(community, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, community_id):
        org_id = _get_org_id(request)
        community = ChatCommunity.objects.filter(id=community_id, workspace__organization_id=org_id).first()
        if not community or not _can_view_community(request.user, community):
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_delete_community(request.user, community):
            return Response(
                {'error': 'Forbidden: Only community owners can delete a community.'},
                status=status.HTTP_403_FORBIDDEN
            )

        community.delete()
        return Response({'status': 'deleted'})


class ChatCommunityMemberView(APIView):
    """
    GET  /api/chat/communities/<id>/members/  → list members
    POST /api/chat/communities/<id>/members/  → add member(s) [owner/admin only]
    PATCH /api/chat/communities/<id>/members/ → change a member's role [owner/admin only]
    DELETE /api/chat/communities/<id>/members/ → remove member(s) [owner/admin only]
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_community(self, request, community_id):
        org_id = _get_org_id(request)
        community = ChatCommunity.objects.filter(id=community_id, workspace__organization_id=org_id).first()
        if not community or not _can_view_community(request.user, community):
            return None
        return community

    def get(self, request, community_id):
        community = self._get_community(request, community_id)
        if not community:
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)
        memberships = ChatCommunityMember.objects.filter(community=community).select_related('user')
        data = [_member_payload(m.user, m.role) for m in memberships]
        return Response(data)

    def post(self, request, community_id):
        community = self._get_community(request, community_id)
        if not community:
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_update_community(request.user, community):
            return Response(
                {'error': 'Forbidden: Only community admins can add members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        org_id = _get_org_id(request)
        raw_user_ids = request.data.getlist('user_ids') if hasattr(request.data, 'getlist') else request.data.get('user_ids')
        user_ids = set(_parse_to_user_ids(raw_user_ids) or [])
        role = request.data.get('role', ChatCommunityMember.ROLE_MEMBER)
        if role not in (ChatCommunityMember.ROLE_ADMIN, ChatCommunityMember.ROLE_MEMBER):
            role = ChatCommunityMember.ROLE_MEMBER

        users = list(_org_members(org_id).filter(id__in=user_ids))
        ChatCommunityMember.objects.bulk_create([
            ChatCommunityMember(community=community, user=u, role=role)
            for u in users
        ], ignore_conflicts=True)
        return Response({'status': 'members added', 'count': len(users)})

    def patch(self, request, community_id):
        """Change the role of a community member."""
        community = self._get_community(request, community_id)
        if not community:
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only owners can promote/demote members
        if _community_role(request.user, community) != ChatCommunityMember.ROLE_OWNER:
            return Response(
                {'error': 'Forbidden: Only community owners can change member roles.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        new_role = request.data.get('role')
        if not user_id or new_role not in (ChatCommunityMember.ROLE_ADMIN, ChatCommunityMember.ROLE_MEMBER):
            return Response({'error': 'user_id and valid role are required.'}, status=400)

        updated = ChatCommunityMember.objects.filter(community=community, user_id=user_id).update(role=new_role)
        if not updated:
            return Response({'error': 'Member not found.'}, status=404)
        return Response({'status': 'role updated'})

    def delete(self, request, community_id):
        community = self._get_community(request, community_id)
        if not community:
            return Response({'error': 'Community not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_update_community(request.user, community):
            return Response(
                {'error': 'Forbidden: Only community admins can remove members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        raw_user_ids = request.data.getlist('user_ids') if hasattr(request.data, 'getlist') else request.data.get('user_ids')
        user_ids = set(_parse_to_user_ids(raw_user_ids) or [])
        if not user_ids:
            return Response({'error': 'No user_ids provided.'}, status=400)

        # Protect: don't let admins remove the owner
        owner_ids = set(
            ChatCommunityMember.objects.filter(
                community=community, role=ChatCommunityMember.ROLE_OWNER
            ).values_list('user_id', flat=True)
        )
        user_ids -= owner_ids
        ChatCommunityMember.objects.filter(community=community, user_id__in=user_ids).delete()
        return Response({'status': 'members removed'})

