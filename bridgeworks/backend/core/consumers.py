"""
WebSocket Consumer for Team Chat
=================================
Each authenticated user connects to ws://<host>/ws/chat/ and is placed into
the channel group "chat_org_<org_id>".

When a REST POST to /api/chat/messages/ succeeds, views_chat.py broadcasts
a "chat.message" event to that group.  This consumer forwards it to the
browser – so all connected org members receive the message instantly
instead of waiting for the 30-second polling cycle.

Clients send their messages via REST (POST /api/chat/messages/), NOT via
WebSocket.  The WS connection is receive-only from the browser side.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self):
        user = self.scope.get("user")

        # Reject unauthenticated connections immediately
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        org_id = await self._get_org_id(user)
        if not org_id:
            await self.close(code=4002)
            return

        # Each org has its own broadcast group
        self.org_id = org_id
        self.org_group = f"chat_org_{org_id}"
        self.user_id = user.id

        try:
            await self.channel_layer.group_add(self.org_group, self.channel_name)
        except Exception:
            await self.close(code=1011)
            return

        await self.accept()

        # Announce that this user just came online to everyone in the org
        try:
            await self.channel_layer.group_send(
                self.org_group,
                {
                    "type": "presence.update",
                    "user_id": self.user_id,
                    "is_online": True,
                },
            )
        except Exception:
            pass

    async def disconnect(self, code):
        if hasattr(self, "org_group"):
            # Mark user offline in DB first
            resolved_status, last_seen = await self._mark_offline()

            # Broadcast presence updates asynchronously
            if resolved_status:
                # 1. Broadcast to presence-specific subscription group
                try:
                    await self.channel_layer.group_send(
                        f'presence_{self.user_id}',
                        {
                            'type': 'presence_update',
                            'user_id': self.user_id,
                            'status': resolved_status,
                            'last_seen': last_seen.isoformat() if last_seen else None
                        }
                    )
                except Exception:
                    pass

                # 2. Broadcast to organization chat channels and presence org channel
                if hasattr(self, "org_id") and self.org_id:
                    is_online = (resolved_status in ('online', 'in_meeting'))
                    try:
                        await self.channel_layer.group_send(
                            f'chat_org_{self.org_id}',
                            {
                                "type": "presence.update",
                                "user_id": self.user_id,
                                "is_online": is_online,
                            },
                        )
                    except Exception:
                        pass

                    try:
                        await self.channel_layer.group_send(
                            f'presence_org_{self.org_id}',
                            {
                                'type': 'presence_update',
                                'user_id': self.user_id,
                                'status': resolved_status,
                                'last_seen': last_seen.isoformat() if last_seen else None
                            }
                        )
                    except Exception:
                        pass

            # Remove self from the group last
            try:
                await self.channel_layer.group_discard(self.org_group, self.channel_name)
            except Exception:
                pass

    # ── Incoming from browser (not used – sends go through REST) ─────────────

    async def receive(self, text_data=None, bytes_data=None):
        # Ignored: clients post messages via REST, not via WebSocket
        pass

    # ── Outgoing: server-side events broadcast by views_chat.py ─────────────

    async def chat_message(self, event):
        """
        Triggered by channel_layer.group_send(..., {"type": "chat.message", ...}).
        Forwards the payload straight to the connected browser tab.
        """
        await self.send(text_data=json.dumps({
            "type": "chat.message",
            "message": event["message"],
        }))

    async def chat_typing(self, event):
        """Optional: forward typing indicator events."""
        await self.send(text_data=json.dumps({
            "type": "chat.typing",
            "user_id": event["user_id"],
            "username": event.get("username", ""),
        }))

    async def chat_task_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat.task_update",
            "task": event["task"],
        }))

    async def presence_update(self, event):
        """
        Triggered by broadcast_presence_update() in chat_realtime.py.
        Forwards the presence change instantly to every connected browser tab.
        Payload: { type: "presence.update", user_id: N, is_online: true/false }
        """
        await self.send(text_data=json.dumps({
            "type": "presence.update",
            "user_id": event["user_id"],
            "is_online": event["is_online"],
        }))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_org_id(self, user):
        """Return the organisation_id for the user (same logic as views_chat.py)."""
        if hasattr(user, "shop_credentials"):
            return user.shop_credentials.organization_id
        try:
            return user.team_settings.organization.organization_id
        except Exception:
            return None

    @database_sync_to_async
    def _mark_offline(self):
        """
        Set activity_status to offline, resolve status and broadcast.
        """
        from presence.models import UserPresence
        try:
            presence, created = UserPresence.objects.get_or_create(user_id=self.user_id)
            presence.activity_status = 'offline'
            presence.resolve_status()
            presence.save_and_broadcast(source='chat_websocket_disconnect', broadcast=False)
            return presence.resolved_status, presence.last_seen
        except Exception:
            return None, None



class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.notification_group = f"notifications_user_{user.id}"
        try:
            await self.channel_layer.group_add(self.notification_group, self.channel_name)
        except Exception:
            await self.close(code=1011)
            return

        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "notification_group"):
            try:
                await self.channel_layer.group_discard(self.notification_group, self.channel_name)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def notification_created(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification.created",
            "notification": event["notification"],
        }))

    async def notification_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification.read",
            "notification_id": event.get("notification_id"),
        }))

    async def notification_all_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification.all_read",
            "notification_ids": event.get("notification_ids", []),
            "read_at": event.get("read_at", ""),
        }))
