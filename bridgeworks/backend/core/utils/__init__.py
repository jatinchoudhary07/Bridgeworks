import re
import requests
from django.conf import settings
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

# --- Correct Model Imports ---
# These imports now match your models.py file
# Note: using relative import from ..models since this is inside core.utils package
from ..models import (
    Order, 
    LineItem, 
    ShopCredentials, 
    TeamMemberSettings
)

User = get_user_model()


# ==============================================================================
# 1. HELPER FUNCTIONS (UNCHANGED)
# ==============================================================================

def _clean_shopify_url(shop_domain):
    """
    Cleans the Shopify domain to get the base URL.
    e.g., 'janki-jewels.myshopify.com' -> 'janki-jewels'
    """
    if not shop_domain:
        return None
    # Removes .myshopify.com, .com, etc.
    cleaned_domain = re.sub(r'\.myshopify\.com$|\.com$', '', shop_domain)
    return cleaned_domain


# ==============================================================================
# 2. CREDENTIALS & ORG FUNCTIONS (CORRECTED)
# ==============================================================================

def _get_org_id_or_none(request):
    """
    Gets the org_id from the authenticated user.
    
    Checks if the user is a team member first,
    then checks if they are the owner.
    """
    if not request.user.is_authenticated:
        return None
    
    try:
        # 1. Check if they are a team member
        # (Accesses the 'team_settings' related_name from TeamMemberSettings)
        return request.user.team_settings.organization.organization_id
    except TeamMemberSettings.DoesNotExist:
        # 2. If not, check if they are the owner
        # (Accesses the 'shop_credentials' related_name from ShopCredentials)
        try:
            return request.user.shop_credentials.organization_id
        except ShopCredentials.DoesNotExist:
            # 3. User is authenticated but has no org
            return None
    except AttributeError:
        # Catches cases where relationships might be None
        return None


def _get_decrypted_credentials(org_id):
    """
    Fetches and decrypts the shop credentials from the ShopCredentials model.
    """
    if not org_id:
        return None
        
    try:
        # 1. Get the ShopCredentials model
        shop = ShopCredentials.objects.get(organization_id=org_id)
        
        # 2. Get the encryption key from settings.py
        if not settings.FERNET_KEY:
             raise Exception("FERNET_KEY is not set in settings.py")
             
        fernet = Fernet(settings.FERNET_KEY.encode())

        def dec(val):
            if not val:
                return None
            try:
                return fernet.decrypt(val.encode()).decode()
            except Exception:
                return None

        # 3. Decrypt the fields (Field names match your models.py)
        creds = {
            "shop_url": dec(shop.shopify_shop_url_encrypted) or shop.myshopify_domain,
            "api_key": dec(shop.shopify_api_key_encrypted),
            "password": dec(shop.shopify_api_password_encrypted),
            "access_token": dec(shop.shopify_access_token_encrypted),
            "api_version": shop.shopify_api_version or '2024-07',
            "webhook_secret": dec(shop.shopify_webhook_secret_encrypted),
            "shipway_email": dec(shop.shipway_email_encrypted),
            "shipway_license_key": dec(shop.shipway_license_key_encrypted),
            "order_prefix": shop.shopify_order_prefix,
            "return_prime_token": dec(shop.return_prime_token_encrypted),
            "auth_method": shop.auth_method,
            "shipway_warehouse_id": shop.shipway_warehouse_id,
            "shipway_return_warehouse_id": shop.shipway_return_warehouse_id,
            "shipway_order_weight": shop.shipway_order_weight,
            "shipway_box_length": shop.shipway_box_length,
            "shipway_box_breadth": shop.shipway_box_breadth,
            "shipway_box_height": shop.shipway_box_height,
            "shipway_invoice_number_prefix": shop.shipway_invoice_number_prefix,
            "shipway_primary_carrier_id": shop.shipway_primary_carrier_id,
            "shipway_primary_carrier_title": shop.shipway_primary_carrier_title,
            "shipway_fallback_carrier_id": shop.shipway_fallback_carrier_id,
            "shipway_fallback_carrier_title": shop.shipway_fallback_carrier_title,
            "shipway_store_code": shop.shipway_store_code,
            "skip_shipway_pii_sync": shop.skip_shipway_pii_sync,
        }
        return creds
        
    except ShopCredentials.DoesNotExist:
        print(f"CRITICAL: No ShopCredentials found for org_id: {org_id}")
        return None
    except Exception as e:
        print(f"CRITICAL: Error decrypting credentials for {org_id}: {e}")
        return None


# ==============================================================================
# 3. ORDER HELPER FUNCTION (UNCHANGED)
# ==============================================================================

def _get_or_create_order_from_api(shopify_order_id, org_id, creds):
    """
    Tries to get an order. If it fails, it calls the Shopify API
    to create it in our database. This fixes the race condition.
    """
    try:
        # 1. Try to get the order normally
        order_obj = Order.objects.get(shopify_id=shopify_order_id, org_id=org_id)
        return order_obj
    except Order.DoesNotExist:
        # 2. Not found! Call Shopify API to create it right now.
        print(f"Order {shopify_order_id} not in DB. Fetching from Shopify API to create it.")
        
        shop_url = creds.get('shop_url')
        api_key = creds.get('api_key')
        password = creds.get('password')
        api_version = creds.get('api_version', '2024-07')
        access_token = creds.get('access_token')
        auth_method = creds.get('auth_method')

        api_url = f"https://{shop_url}/admin/api/{api_version}/orders/{shopify_order_id}.json"
        
        try:
            if auth_method == 'oauth' and access_token:
                headers = {"X-Shopify-Access-Token": access_token}
                response = requests.get(api_url, headers=headers, timeout=10)
            else:
                legacy_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders/{shopify_order_id}.json"
                response = requests.get(legacy_url, timeout=10)
                
            if not response.ok:
                print(f"API call to fetch missing order {shopify_order_id} failed.")
                return None
            
            api_order = response.json()['order']
            
            # --- This logic matches your 'orders/create' topic ---
            customer_data = api_order.get('customer') or {}
            shipping_address = api_order.get('shipping_address')
            shipping_address_text = f"{(shipping_address or {}).get('first_name','')} {(shipping_address or {}).get('last_name','')}, {(shipping_address or {}).get('address1','')}, {(shipping_address or {}).get('city','')}, {(shipping_address or {}).get('zip','')}" if shipping_address else None
            billing_address = api_order.get('billing_address')
            billing_address_text = f"{(billing_address or {}).get('first_name','')} {(billing_address or {}).get('last_name','')}, {(billing_address or {}).get('address1','')}, {(billing_address or {}).get('city','')}, {(billing_address or {}).get('zip','')}" if billing_address else None

            # Use all fields from your 'orders/create'
            order_obj, created = Order.objects.get_or_create(
                shopify_id=api_order['id'],
                defaults={'org_id': org_id}
            )

            # Base fields (always update)
            order_obj.order_number = api_order.get('order_number')
            order_obj.created_at = api_order.get('created_at')
            order_obj.updated_at = api_order.get('updated_at')
            order_obj.total_price = api_order.get('total_price')
            order_obj.financial_status = api_order.get('financial_status')
            order_obj.fulfillment_status = api_order.get('fulfillment_status')
            order_obj.tags = api_order.get('tags', '')
            order_obj.payment_gateway_names = api_order.get('payment_gateway_names', [])
            order_obj.discount_codes = api_order.get('discount_codes', [])
            order_obj.previous_order_count = 0  # Cannot calculate this here
            order_obj.raw_data = api_order

            # PII fields (PROTECT FROM REDACTION: Only update if new value is not empty)
            p_first_name = customer_data.get('first_name')
            p_last_name = customer_data.get('last_name')
            p_phone = (shipping_address or {}).get('phone')
            p_email = customer_data.get('email')

            if p_first_name: order_obj.customer_first_name = p_first_name
            if p_last_name: order_obj.customer_last_name = p_last_name
            if p_phone: order_obj.contact_phone = p_phone
            if p_email: order_obj.contact_email = p_email
            if shipping_address_text: order_obj.shipping_address = shipping_address_text
            if billing_address_text: order_obj.billing_address = billing_address_text

            order_obj.save()
            
            # Create its line items
            order_obj.line_items.all().delete()
            line_items_to_create = [LineItem(order=order_obj, product_id=item.get('product_id'), variant_id=item.get('variant_id'), title=item.get('title'), quantity=item.get('quantity'), sku=item.get('sku'), vendor=item.get('vendor'), price=item.get('price'), name=item.get('name')) for item in api_order.get('line_items', [])]
            if line_items_to_create: LineItem.objects.bulk_create(line_items_to_create)
            
            print(f"Successfully created missing order {shopify_order_id} from API.")
            return order_obj
            
        except Exception as e:
            print(f"Error creating missing order {shopify_order_id}: {e}")
            return None

# ==============================================================================
# 4. SHARED CONSTANTS
# ==============================================================================

STATUS_MAP = {
    "Delivered": ["DEL", "delivered", "Delivered"],
    "In Transit": ["INT", "in_transit", "In Transit"],
    "Undelivered": ["UND", "undelivered", "Undelivered"],
    "RTO": ["RTO", "rto", "RTO Initiated", "RTO"],
    "RTO Delivered": ["RTD", "rto_delivered", "RTO Delivered"],
    "Canceled": ["CAN", "cancelled", "Cancelled"],
    "Shipment Booked": ["SCH", "booked", "Booked", "Pending", "0", "Shipment Booked"],
    "On Hold": ["ONH", "on_hold", "On Hold"],
    "Out For Delivery": ["OOD", "out_for_delivery", "Out For Delivery"],
    "Status Pending": ["NFI", "nfi", "Status Pending"],
    "NFID": ["NFIDS", "NFID"],
    "Pickup Scheduled": ["RSCH", "pickup_scheduled", "Pickup Scheduled"],
    "Out for Pickup": ["ROOP", "out_for_pickup", "Out for Pickup"],
    "Shipment Picked Up": ["RPKP", "shipment_picked_up", "Picked Up", "Shipment Picked Up"],
    "Return Delivered": ["RDEL", "return_delivered", "Return Delivered"],
    "Return In Transit": ["RINT", "return_in_transit", "Return In Transit"],
    "Pickup Rescheduled": ["RPSH", "pickup_rescheduled", "Pickup Rescheduled"],
    "Return Request Cancelled": ["RCAN", "Return Request Cancelled"],
    "Return Request Closed": ["RCLO", "Return Request Closed"],
    "Pickup Delayed": ["RSMD", "pickup_delayed", "Pickup Delayed"],
    "Pickup Cancelled": ["PCAN", "pickup_cancelled", "Pickup Cancelled"],
    "Others": ["ROTH", "others", "Others"],
    "Pickup Failed": ["RPF", "pickup_failed", "Pickup Failed"],
    "Manifested": ["0", "manifested", "Manifested", "AWB_Assigned", "Label Created"],
}
