import shopify
from django.conf import settings
from .models import ShopCredentials, decrypt_data


def _clean_domain(url):
    """Strip protocol and trailing slashes from a URL to get a bare domain."""
    if not url:
        return None
    return url.replace('https://', '').replace('http://', '').strip('/')


def get_shopify_session(shop_url, org_id=None, shop_creds=None):
    """
    Build an authenticated Shopify session.

    Lookup priority:
      1. shop_creds  — ShopCredentials instance passed directly (no DB query)
      2. shop_url    — looked up by myshopify_domain, then by shopify_shop_url_encrypted
      3. org_id      — looked up by organization_id (final fallback)

    Auth priority:
      1. oauth        — use shopify_access_token_encrypted
      2. legacy       — use shopify_api_password_encrypted (the Private App password)
    """
    # ── 1. Resolve the ShopCredentials record ─────────────────────────────────
    creds = None

    if shop_creds is not None:
        creds = shop_creds
    elif shop_url:
        clean_domain = _clean_domain(shop_url)
        try:
            creds = ShopCredentials.objects.get(myshopify_domain=clean_domain)
        except ShopCredentials.DoesNotExist:
            # Fall through to org_id lookup below
            pass

    if creds is None and org_id:
        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            pass

    if creds is None:
        raise Exception(
            f"No Shopify credentials found. "
            f"Please save your store credentials in Settings → Onboarding."
        )

    # ── 2. Derive the myshopify domain for the session ────────────────────────
    domain = creds.myshopify_domain
    if not domain:
        # Derive from the encrypted shop URL (e.g., example.myshopify.com)
        raw_url = decrypt_data(creds.shopify_shop_url_encrypted) if creds.shopify_shop_url_encrypted else None
        domain = _clean_domain(raw_url)
    if not domain:
        raise Exception(
            "Shopify store URL is not configured. "
            "Please save your store credentials in Settings → Onboarding."
        )

    api_version = creds.shopify_api_version or '2024-07'

    # ── 3. Build the session based on auth method ─────────────────────────────
    if creds.auth_method == 'oauth' and creds.shopify_access_token_encrypted:
        token = decrypt_data(creds.shopify_access_token_encrypted)
        if not token:
            raise Exception(
                f"OAuth access token is empty for shop: {domain}. "
                "Please reconnect your store via Settings → Onboarding."
            )
        return shopify.Session(domain, api_version, token)

    # Legacy Private App: the API password acts as the access token.
    password = decrypt_data(creds.shopify_api_password_encrypted or '') or None
    if not password:
        raise Exception(
            f"Shopify API credentials are not configured for shop: {domain}. "
            "Please save your API Key and Password in Settings → Onboarding."
        )
    return shopify.Session(domain, api_version, password)
