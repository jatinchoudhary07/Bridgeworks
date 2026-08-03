"""
ASGI config for bridgeworks_backend project.

Handles both HTTP (Django) and WebSocket (Django Channels) connections.
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridgeworks_backend.settings')

# CRITICAL: We MUST call django.setup() before importing anything from core or channels!
# This prevents the AppRegistryNotReady error.
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from core.jwt_auth_middleware import JwtAuthMiddlewareStack
import core.routing

application = ProtocolTypeRouter({
    # Standard Django HTTP requests
    "http": get_asgi_application(),

    # WebSocket connections – authenticated via JWT ?token= query param
    "websocket": AllowedHostsOriginValidator(
        JwtAuthMiddlewareStack(
            AuthMiddlewareStack(
                URLRouter(core.routing.websocket_urlpatterns)
            )
        )
    ),
})
