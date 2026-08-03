"""
DevAutoAuthMiddleware + DevForceAuth
======================================
LOCAL DEVELOPMENT ONLY — never enabled in production (DEBUG=False).

Automatically authenticates every incoming request as the local dev admin user
(seeded by `python manage.py seed_local_dev`) so all API views receive a
fully-authenticated user with a valid org_id — eliminating the need for a
login flow in the no-auth frontend setup.

The middleware and DRF class are only added when DEBUG=True (see settings.py).
"""
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication

logger = logging.getLogger(__name__)

LOCAL_DEV_EMAIL = "admin@local.dev"

_cached_user = None  # module-level cache so we only hit the DB once per process


def _get_local_user():
    global _cached_user
    if _cached_user is not None:
        return _cached_user
    try:
        User = get_user_model()
        _cached_user = User.objects.get(email=LOCAL_DEV_EMAIL)
        return _cached_user
    except Exception:
        logger.warning(
            "DevAutoAuth: local dev user not found. "
            "Run: python manage.py seed_local_dev"
        )
        return None


class DevAutoAuthMiddleware:
    """
    Django middleware — attaches the local dev admin to request.user.
    Runs AFTER AuthenticationMiddleware in the middleware stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            user = _get_local_user()
            if user and not (hasattr(request, "user") and request.user.is_authenticated):
                request.user = user
        return self.get_response(request)


class DevForceAuth(BaseAuthentication):
    """
    DRF authentication class — tells DRF that the request is authenticated
    as the local dev admin user, bypassing JWT/session checks.

    This is placed first in DEFAULT_AUTHENTICATION_CLASSES in DEBUG mode so
    DRF's request wrapper sees an authenticated user immediately.
    """

    def authenticate(self, request):
        if not settings.DEBUG:
            return None  # Safety: do nothing in production
        user = _get_local_user()
        if user:
            return (user, None)  # (user, auth_token) — token is None for dev
        return None
