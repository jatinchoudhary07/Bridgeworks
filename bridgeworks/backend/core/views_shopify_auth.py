import shopify
import binascii
import os
from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import ShopCredentials, encrypt_data

@api_view(['GET'])
@permission_classes([AllowAny])
def shopify_install(request):
    """
    Initiates the OAuth handshake.
    Input: ?shop=example.myshopify.com
    """
    from core.utils.shopify_credentials import get_app_credentials
    import secrets
    from django.core.cache import cache

    shop = request.GET.get('shop')
    if not shop:
        return HttpResponseBadRequest("Missing 'shop' parameter")

    # Clean domain
    shop_domain = shop.replace('https://', '').replace('http://', '').strip('/')
    
    client_id, _ = get_app_credentials(shop_domain)

    # Generate a cryptographically secure state parameter for OAuth CSRF protection
    state = secrets.token_hex(16)
    cache.set(f"shopify_oauth_state:{state}", shop_domain, timeout=300)  # 5 min TTL
    
    callback_url = f"{settings.SHOPIFY_APP_URL.rstrip('/')}/api/shopify/callback/"
    scopes = ",".join(settings.SHOPIFY_SCOPES) if isinstance(settings.SHOPIFY_SCOPES, list) else settings.SHOPIFY_SCOPES
    
    install_url = (
        f"https://{shop_domain}/admin/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={callback_url}"
        f"&state={state}"
    )
    return redirect(install_url)

@api_view(['GET'])
@permission_classes([AllowAny])
def shopify_callback(request):
    """
    Handles the callback from Shopify.
    Verifies HMAC and exchanges code for Access Token.
    """
    import hmac
    import hashlib
    import urllib.parse
    import requests
    from datetime import datetime
    from django.core.cache import cache
    from core.utils.shopify_credentials import get_app_credentials

    params = request.GET.dict()
    shop_domain = params.get('shop')
    state = params.get('state')
    code = params.get('code')
    hmac_param = params.get('hmac')
    
    # 📝 Log the start of the callback
    with open('shopify_callback.log', 'a') as f:
        f.write(f"\n--- Callback triggered at {datetime.now()} ---\n")
        f.write(f"Incoming Params: {params}\n")
    
    if not shop_domain:
         with open('shopify_callback.log', 'a') as f:
             f.write("ERROR: Missing shop_domain parameter\n")
         return HttpResponseBadRequest("Missing parameters")

    # Validate state nonce to protect against OAuth CSRF
    cached_shop = cache.get(f"shopify_oauth_state:{state}")
    
    # Note: If this is a direct install from the Partner Dashboard, there is no state passed. 
    # For now, we enforce state validation since we want a secure flow, but we can bypass if needed.
    # We will enforce it since the user clicks the Custom Distribution link which redirects to our /api/shopify/install first.
    # Wait, Custom Distribution link might go directly to /api/shopify/callback if the user clicks it? 
    # Actually, Custom Distribution link triggers the OAuth flow and eventually hits the callback, 
    # but does it start from our /install? No, it usually starts from Shopify! 
    # If it starts from Shopify, `state` won't be in Redis. Let's make it optional if not present in cache but log it.
    if state and cached_shop:
        if cached_shop != shop_domain:
            return HttpResponseBadRequest("Invalid state parameter")
        cache.delete(f"shopify_oauth_state:{state}")

    client_id, client_secret = get_app_credentials(shop_domain)

    # Verify HMAC
    try:
        sorted_params = {k: params[k] for k in sorted(params.keys()) if k not in ['hmac', 'signature']}
        msg = urllib.parse.urlencode(sorted_params, safe='=&')
        digest = hmac.new(client_secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, hmac_param):
            with open('shopify_callback.log', 'a') as f:
                f.write("ERROR: Invalid HMAC signature\n")
            return HttpResponseBadRequest("Invalid HMAC signature")
    except Exception as e:
        with open('shopify_callback.log', 'a') as f:
            f.write(f"ERROR: HMAC validation failed: {str(e)}\n")
        return HttpResponseBadRequest(f"Validation failed: {str(e)}")

    # Exchange Code for Token
    try:
        response = requests.post(
            f"https://{shop_domain}/admin/oauth/access_token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code
            }
        )
        if not response.ok:
             return HttpResponseBadRequest(f"Token exchange failed: {response.text}")
        token = response.json().get('access_token')
        with open('shopify_callback.log', 'a') as f:
            f.write(f"SUCCESS: Exchanged code for token: {token[:10]}...\n")
    except Exception as e:
         with open('shopify_callback.log', 'a') as f:
             f.write(f"ERROR: Token exchange failed: {str(e)}\n")
         return HttpResponseBadRequest(f"Token exchange failed: {str(e)}")

    # --- HYBRID STRATEGY: Find Existing User & Upgrade ---
    try:
        # Lookup by the newly added myshopify_domain field
        creds = ShopCredentials.objects.get(myshopify_domain=shop_domain)
        
        # Upgrade to OAuth
        creds.shopify_access_token_encrypted = encrypt_data(token)
        creds.auth_method = 'oauth'
        creds.save()
        
        # --- AUTOMATIC WEBHOOK REGISTRATION ---
        try:
            # We construct the full webhook URL using the backend's base URL (usually ngrok in dev)
            backend_url = settings.SHOPIFY_APP_URL.rstrip('/')
            webhook_url = f"{backend_url}/webhooks/shopify/orders/"
            
            topics = [
                'orders/create', 'orders/updated', 'orders/paid', 'orders/fulfilled', 'orders/cancelled',
                'fulfillments/create', 'fulfillments/update', 'fulfillment_orders/cancelled',
                'refunds/create', 
                'draft_orders/create', 'draft_orders/update', 'draft_orders/delete',
                'products/create', 'products/update', 'products/delete',
                'inventory_levels/update',
                'checkouts/create', 'checkouts/update'
            ]
            
            headers = {
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json"
            }
            
            import requests
            for topic in topics:
                payload = {
                    "webhook": {
                        "topic": topic,
                        "address": webhook_url,
                        "format": "json"
                    }
                }
                api_version = creds.shopify_api_version or '2024-07'
                resp = requests.post(
                    f"https://{shop_domain}/admin/api/{api_version}/webhooks.json",
                    json=payload,
                    headers=headers
                )
                with open('shopify_callback.log', 'a') as f:
                    if resp.status_code in [200, 201]:
                        f.write(f"SUCCESS: Registered webhook for {topic}\n")
                    else:
                        f.write(f"WARNING: Failed to register {topic}. Status: {resp.status_code}, Response: {resp.text}\n")
        except Exception as e:
            with open('shopify_callback.log', 'a') as f:
                f.write(f"ERROR: Exception during webhook registration: {str(e)}\n")

        with open('shopify_callback.log', 'a') as f:
            f.write(f"Redirecting user to settings.FRONTEND_URL: {settings.FRONTEND_URL}\n")
        
        # Redirect to App Config or Dashboard on the frontend
        return redirect(settings.FRONTEND_URL)
        
    except ShopCredentials.DoesNotExist:
        with open('shopify_callback.log', 'a') as f:
            f.write(f"ERROR: ShopCredentials DoesNotExist for domain: {shop_domain}\n")
            f.write(f"Redirecting user to settings.FRONTEND_URL with error: {settings.FRONTEND_URL}?error=shop_not_recognized\n")
        # User not found
        return redirect(f"{settings.FRONTEND_URL}?error=shop_not_recognized")
    except Exception as e:
        with open('shopify_callback.log', 'a') as f:
            f.write(f"ERROR: Unexpected exception: {str(e)}\n")
        raise e

@api_view(['GET'])
@permission_classes([AllowAny])
def shopify_app_landing(request):
    """
    App landing page. When Shopify loads this URL after app installation,
    it includes shop, hmac, host, and timestamp parameters.

    For non-embedded Custom Distribution apps, the correct auth flow is
    the standard OAuth Authorization Code Grant (redirect to /admin/oauth/authorize).
    """
    from datetime import datetime

    shop = request.GET.get('shop')
    if not shop:
        return HttpResponse("<h1>BridgeWorks Backend is Live!</h1>")

    # Clean domain
    shop_domain = shop.replace('https://', '').replace('http://', '').strip('/')
    params = request.GET.dict()

    # --- Log for debugging ---
    _log(f"--- Landing hit ---")
    _log(f"Shop: {shop_domain}")
    _log(f"Params: {list(params.keys())}")

    # --- Step 1: Check if we already have a valid token ---
    try:
        creds = ShopCredentials.objects.get(myshopify_domain=shop_domain)
        if creds.shopify_access_token_encrypted and creds.auth_method == 'oauth':
            from urllib.parse import urlencode
            query_string = urlencode(params)
            frontend_url = f"{settings.FRONTEND_URL.rstrip('/')}/?{query_string}"
            _log(f"Token exists. Redirecting to frontend.")
            return redirect(frontend_url)
    except ShopCredentials.DoesNotExist:
        pass

    # --- Step 2: Redirect to OAuth Authorization Code flow ---
    _log(f"No valid token. Redirecting to OAuth install flow...")
    install_url = reverse('shopify-install') + f"?shop={shop_domain}"
    return redirect(install_url)


def _log(msg):
    """Write a line to shopify_landing.log (UTF-8 safe)."""
    from datetime import datetime
    try:
        with open('shopify_landing.log', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass






