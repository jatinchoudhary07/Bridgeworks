"""
WebSocket URL routing for the core app.
Imported by bridgeworks_backend/asgi.py.
"""

from django.urls import re_path
from . import consumers

from presence.consumers import PresenceConsumer

import typing
websocket_urlpatterns = [
    re_path(r"ws/chat/$", typing.cast(typing.Any, consumers.ChatConsumer.as_asgi())),
    re_path(r"ws/notifications/$", typing.cast(typing.Any, consumers.NotificationConsumer.as_asgi())),
    re_path(r"ws/presence/$", typing.cast(typing.Any, PresenceConsumer.as_asgi())),
]

