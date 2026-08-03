import requests
from django.core.management.base import BaseCommand
from django.core.cache import cache
from core.models import ShopCredentials, Order
from core.utils import _get_decrypted_credentials, _get_or_create_order_from_api
from core.tasks.shipway_sync import fetch_missing_pii_task


def find_shopify_order_by_number(order_number, shop_url, api_version, headers, auth_method=None, api_key=None, password=None):
    """
    Robust helper to search Shopify API for an order by its name/number.
    """
    search_queries = [
        str(order_number),
        f"#{order_number}" if not str(order_number).startswith("#") else str(order_number),
        str(order_number).replace("#", "") if str(order_number).startswith("#") else str(order_number)
    ]
    search_queries = list(dict.fromkeys(search_queries))
    
    # Try exact name matching first
    for query in search_queries:
        if auth_method == 'oauth' and headers:
            api_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&name={query}"
            response = requests.get(api_url, headers=headers, timeout=10)
        else:
            legacy_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders.json?status=any&name={query}"
            response = requests.get(legacy_url, timeout=10)
            
        if response.ok:
            orders = response.json().get('orders', [])
            if orders:
                return orders[0]
                
    # Fallback to general query search
    for query in search_queries:
        if auth_method == 'oauth' and headers:
            api_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&query=name:{query}"
            response = requests.get(api_url, headers=headers, timeout=10)
        else:
            legacy_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders.json?status=any&query=name:{query}"
            response = requests.get(legacy_url, timeout=10)
            
        if response.ok:
            orders = response.json().get('orders', [])
            if orders:
                return orders[0]
                
    return None


class Command(BaseCommand):
    help = 'Syncs a specific order from Shopify and triggers Shipway customer details (PII) retrieval.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=str,
            help='Shopify Order ID (e.g. 6626150744276)',
            required=False
        )
        parser.add_argument(
            '--order-number',
            type=str,
            help='Customer-facing Order Number (e.g. 42187 or #42187)',
            required=False
        )
        parser.add_argument(
            '--org-id',
            type=str,
            help='Organization ID to sync for (e.g. janki-jewels)',
            required=True
        )

    def handle(self, *args, **options):
        org_id = options.get('org_id')
        order_id = options.get('order_id')
        order_number = options.get('order_number')

        if not order_id and not order_number:
            self.stdout.write(self.style.ERROR('You must provide either --order-id or --order-number.'))
            return

        self.stdout.write(self.style.WARNING(f'Retrieving credentials for organization: {org_id}...'))
        creds = _get_decrypted_credentials(org_id)
        if not creds:
            self.stdout.write(self.style.ERROR(f'No ShopCredentials found or decryption failed for org: {org_id}'))
            return

        shopify_order_id = order_id

        if not shopify_order_id:
            # We must search Shopify API by order number
            self.stdout.write(self.style.WARNING(f'Searching Shopify API for order number: {order_number}...'))
            
            shop_url = creds.get('shop_url')
            api_key = creds.get('api_key')
            password = creds.get('password')
            access_token = creds.get('access_token')
            api_version = creds.get('api_version', '2024-07')
            auth_method = creds.get('auth_method')
            
            headers = None
            if auth_method == 'oauth' and access_token:
                headers = {"X-Shopify-Access-Token": access_token}

            api_order = find_shopify_order_by_number(
                order_number, shop_url, api_version, headers,
                auth_method, api_key, password
            )
            if not api_order:
                self.stdout.write(self.style.ERROR(f'Order with number "{order_number}" not found on Shopify.'))
                return
            
            shopify_order_id = str(api_order['id'])
            self.stdout.write(self.style.SUCCESS(f'Found order on Shopify! Shopify Order ID: {shopify_order_id}'))

        self.stdout.write(self.style.WARNING(f'Syncing order {shopify_order_id} from Shopify Admin API...'))
        order = _get_or_create_order_from_api(shopify_order_id, org_id, creds)
        if not order:
            self.stdout.write(self.style.ERROR('Failed to retrieve or save order details from Shopify API.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Successfully saved Order #{order.order_number} to DB (BridgeWorks PK ID: {order.id})!'))

        # Fetch Shipway customer data
        self.stdout.write(self.style.WARNING('Triggering customer details (PII) fetch from Shipway...'))
        try:
            fetch_missing_pii_task(order.id, org_id)
            order.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(
                f'Sync Complete! Customer details: '
                f'Name: {order.customer_first_name} {order.customer_last_name}, '
                f'Phone: {order.contact_phone}, Pincode: {order.shipping_pincode}'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching Shipway customer details: {e}'))

        # Clear Django Cache
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('Cleared order cache.'))
        except Exception:
            pass
