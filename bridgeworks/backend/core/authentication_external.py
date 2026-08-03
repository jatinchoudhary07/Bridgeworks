import logging
from django.core.cache import cache
from django.utils import timezone
from rest_framework import authentication, exceptions
from .models import ShopAPIKey

logger = logging.getLogger("security")

MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 3600  # 1 hour


class ExternalAPITokenAuthentication(authentication.BaseAuthentication):
    """
    Validates external API tokens securely:
    - Lockout IP after repeated failures to prevent brute force.
    - Resolves shop_id in the URL matching the API Key's organization_id.
    - Attach credentials/shop details to request.
    """
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        # ── Brute-force protection ────────────────────────────────────────────
        ip = self._get_client_ip(request)
        lock_key = f"api_auth_lockout:{ip}"
        fail_key = f"api_auth_fails:{ip}"

        if cache.get(lock_key):
            logger.warning("API_AUTH_LOCKED_OUT ip=%s", ip)
            raise exceptions.AuthenticationFailed("Too many failed attempts. Try again later.")

        parts = auth_header.split(' ')
        if len(parts) != 2:
            self._record_failure(ip, fail_key, lock_key)
            raise exceptions.AuthenticationFailed('Invalid Authorization header format.')

        raw_key = parts[1]
        
        # Keys are structured as: {prefix}{token} (prefix is exactly 16 characters)
        if len(raw_key) < 16:
            self._record_failure(ip, fail_key, lock_key)
            raise exceptions.AuthenticationFailed('Invalid API Key format.')

        prefix = raw_key[:16]

        try:
            api_key = ShopAPIKey.objects.select_related('shop__owner', 'shop').get(prefix=prefix, is_active=True)
        except ShopAPIKey.DoesNotExist:
            self._record_failure(ip, fail_key, lock_key)
            logger.warning("API_AUTH_FAIL_UNKNOWN_PREFIX prefix=%s ip=%s", prefix, ip)
            raise exceptions.AuthenticationFailed('Invalid or inactive API Key.')

        if not api_key.verify_key(raw_key):
            self._record_failure(ip, fail_key, lock_key)
            logger.warning("API_AUTH_FAIL_BAD_KEY api_key_id=%s ip=%s", api_key.id, ip)
            raise exceptions.AuthenticationFailed('Invalid API Key.')

        # ── shop_id URL parameter validation ──────────────────────────────────
        # Validate that the token belongs to the shop_id provided in the request URL
        if request.resolver_match:
            shop_id_from_url = request.resolver_match.kwargs.get("shop_id")
            if shop_id_from_url and str(api_key.shop.organization_id) != str(shop_id_from_url):
                logger.warning(
                    "API_AUTH_SHOP_MISMATCH api_key_id=%s url_shop=%s token_shop=%s ip=%s",
                    api_key.id, shop_id_from_url, api_key.shop.organization_id, ip,
                )
                raise exceptions.AuthenticationFailed("Token does not match the requested shop.")

        # Attach context to the request
        request.shop_auth_context = api_key.shop
        request.org_id = api_key.shop.organization_id

        # Update last used timestamp
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])

        # Reset failure counter on success
        cache.delete(fail_key)
        logger.info("API_AUTH_SUCCESS api_key_id=%s shop_id=%s ip=%s", api_key.id, api_key.shop.organization_id, ip)

        # Return the shop owner as the user
        return (api_key.shop.owner, api_key)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def _record_failure(self, ip, fail_key, lock_key):
        fails = cache.get(fail_key, 0) + 1
        cache.set(fail_key, fails, timeout=3600)
        if fails >= MAX_FAILED_ATTEMPTS:
            cache.set(lock_key, True, timeout=LOCKOUT_SECONDS)
            logger.error("API_AUTH_LOCKOUT_TRIGGERED ip=%s", ip)

    @staticmethod
    def _get_client_ip(request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

