import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridgeworks_backend.settings')
django.setup()

from core.models import ShopCredentials
from django.conf import settings
from core.utils import _get_decrypted_credentials

try:
    c = ShopCredentials.objects.get(myshopify_domain='shori-test.myshopify.com')
    creds = _get_decrypted_credentials(c.organization_id)
    token = creds.get('access_token')
    api_version = creds.get('api_version', '2024-07')

    backend_url = settings.SHOPIFY_APP_URL.rstrip('/')
    webhook_url = f"{backend_url}/webhooks/shopify/orders/"
    
    topics = [
        'orders/create', 'orders/updated', 'orders/paid', 'orders/fulfilled', 'orders/cancelled',
        'fulfillments/create', 'fulfillments/update', 'fulfillment_orders/cancelled',
        'refunds/create', 
        'draft_orders/create', 'draft_orders/update', 'draft_orders/delete',
        'products/create', 'products/update', 'products/delete',
        'inventory_levels/update'
    ]
    
    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }
    
    for topic in topics:
        payload = {
            "webhook": {
                "topic": topic,
                "address": webhook_url,
                "format": "json"
            }
        }
        resp = requests.post(
            f"https://shori-test.myshopify.com/admin/api/{api_version}/webhooks.json",
            json=payload,
            headers=headers
        )
        if resp.status_code in [200, 201]:
            print(f"SUCCESS: Registered webhook for {topic}")
        else:
            print(f"WARNING: Failed to register {topic}. Status: {resp.status_code}, Response: {resp.text}")

except Exception as e:
    print(f"Error: {e}")
