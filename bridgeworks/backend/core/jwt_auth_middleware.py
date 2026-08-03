"""
JWT WebSocket Middleware for Django Channels
=============================================
Django's AuthMiddlewareStack uses session cookies, but this app uses JWT tokens.
This middleware reads a `?token=<access_token>` query parameter from the
WebSocket URL, validates it with SimpleJWT, and populates scope["user"].

Usage in asgi.py:
    URLRouter(core.routing.websocket_urlpatterns)
    wrapped by JwtAuthMiddleware instead of AuthMiddlewareStack.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


@database_sync_to_async
def _get_user_from_token(token_key: str):
    """Validate the JWT access token and return the User, or AnonymousUser."""
    try:
        token = AccessToken(token_key)
        user_id = token["user_id"]
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Reads the `token` query-string parameter from the WebSocket URL and
    authenticates the user via SimpleJWT before the consumer runs.

    Frontend usage:
        new WebSocket(`ws://127.0.0.1:8000/ws/chat/?token=${accessToken}`)
    """

    async def __call__(self, scope, receive, send):
        # Parse ?token= from the query string
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", []) or params.get("access_token", [])

        if token_list:
            raw_token = token_list[0]
            if isinstance(raw_token, str) and raw_token.lower().startswith("bearer "):
                raw_token = raw_token[7:]
            scope["user"] = await _get_user_from_token(raw_token)
        elif "user" not in scope:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """Convenience wrapper matching the AuthMiddlewareStack signature."""
    return JwtAuthMiddleware(inner)
