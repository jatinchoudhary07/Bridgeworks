import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from presence.models import UserPresence
from core.views_chat import _get_org_id

class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if self.user is None or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.org_id = await self._get_user_org_id()
        if not self.org_id:
            await self.close(code=4002)
            return

        # Connect to organization presence group
        self.org_group_name = f"presence_org_{self.org_id}"
        await self.channel_layer.group_add(
            self.org_group_name,
            self.channel_name
        )

        # Connect to user-specific group
        self.user_group_name = f"presence_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

        # Mark user as online in activity_status
        resolved_status, last_seen = await self._set_user_online()
        if resolved_status:
            await self._broadcast_presence(resolved_status, last_seen)

    async def disconnect(self, code):
        if hasattr(self, 'org_group_name'):
            await self.channel_layer.group_discard(
                self.org_group_name,
                self.channel_name
            )
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

        # Mark user as offline
        if hasattr(self, 'user') and self.user and self.user.is_authenticated:
            resolved_status, last_seen = await self._set_user_offline()
            if resolved_status:
                await self._broadcast_presence(resolved_status, last_seen)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        try:
            data = json.loads(text_data)
            if data.get("type") == "heartbeat":
                should_broadcast, resolved_status, last_seen = await self._update_last_seen()
                if should_broadcast:
                    await self._broadcast_presence(resolved_status, last_seen)
        except Exception:
            pass

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence_update',
            'user_id': event['user_id'],
            'status': event['status'],
            'last_seen': event['last_seen']
        }))

    async def _broadcast_presence(self, status, last_seen):
        if not self.channel_layer:
            return

        # 1. Broadcast to presence-specific group
        try:
            await self.channel_layer.group_send(
                f'presence_{self.user.id}',
                {
                    'type': 'presence_update',
                    'user_id': self.user.id,
                    'status': status,
                    'last_seen': last_seen.isoformat() if last_seen else None
                }
            )
        except Exception:
            pass

        # 2. Broadcast to organization chat channels (backwards compatibility)
        if self.org_id:
            is_online = (status in ('online', 'in_meeting'))
            try:
                await self.channel_layer.group_send(
                    f'chat_org_{self.org_id}',
                    {
                        'type': 'presence.update',
                        'user_id': self.user.id,
                        'is_online': is_online,
                    }
                )
            except Exception:
                pass

            try:
                await self.channel_layer.group_send(
                    f'presence_org_{self.org_id}',
                    {
                        'type': 'presence_update',
                        'user_id': self.user.id,
                        'status': status,
                        'last_seen': last_seen.isoformat() if last_seen else None
                    }
                )
            except Exception:
                pass

    @database_sync_to_async
    def _update_last_seen(self):
        try:
            presence, created = UserPresence.objects.get_or_create(user=self.user)
            presence.last_seen = timezone.now()
            if presence.activity_status != 'online':
                presence.activity_status = 'online'
                presence.resolve_status()
                presence.save_and_broadcast(source='websocket_heartbeat', broadcast=False)
                return True, presence.resolved_status, presence.last_seen
            else:
                presence.save(update_fields=['last_seen'])
                return False, None, None
        except Exception:
            return False, None, None

    @database_sync_to_async
    def _get_user_org_id(self):
        class DummyRequest:
            def __init__(self, user):
                self.user = user
        return _get_org_id(DummyRequest(self.user))

    @database_sync_to_async
    def _set_user_online(self):
        try:
            presence, created = UserPresence.objects.get_or_create(user=self.user)
            presence.activity_status = 'online'
            presence.last_seen = timezone.now()
            presence.resolve_status()
            presence.save_and_broadcast(source='websocket_connect', broadcast=False)
            return presence.resolved_status, presence.last_seen
        except Exception:
            return None, None

    @database_sync_to_async
    def _set_user_offline(self):
        try:
            presence, created = UserPresence.objects.get_or_create(user=self.user)
            presence.activity_status = 'offline'
            presence.resolve_status()
            presence.save_and_broadcast(source='websocket_disconnect', broadcast=False)
            return presence.resolved_status, presence.last_seen
        except Exception:
            return None, None
