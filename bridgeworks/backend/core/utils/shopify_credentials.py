from django.conf import settings
from django.core.cache import cache
from core.models import ShopifyCustomApp
import logging

logger = logging.getLogger(__name__)

def get_app_credentials(shop_domain: str) -> tuple[str, str]:
    """
    Returns (client_id, client_secret) for a given shop_domain.
    Uses Redis caching to avoid DB hits on high-volume webhook endpoints.
    Falls back to settings.SHOPIFY_API_KEY/SECRET if custom app not found.
    """
    if not shop_domain:
        return settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_SECRET

    cache_key = f"shopify_creds:{shop_domain}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        app = ShopifyCustomApp.objects.get(
            shop_domain=shop_domain, 
            is_active=True
        )
        result = (app.client_id, app.client_secret)
        # Cache for 1 hour
        cache.set(cache_key, result, timeout=3600)
        return result
    except ShopifyCustomApp.DoesNotExist:
        # Fallback to default .env values for legacy / single-store deployments
        return settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_SECRET
    except Exception as e:
        logger.error(f"Error fetching Shopify credentials for {shop_domain}: {e}")
        return settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_SECRET
