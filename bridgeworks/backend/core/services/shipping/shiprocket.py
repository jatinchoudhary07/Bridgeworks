import requests
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from .base import BaseShippingProvider
from core.utils.payment_utils import derive_payment_type_from_fields

logger = logging.getLogger(__name__)

class ShiprocketProvider(BaseShippingProvider):
    """
    Adapter class for the Shiprocket shipping platform.
    Implements authentication token caching and order booking.
    """

    def _get_token(self) -> str:
        """
        Retrieves a cached token or fetches a fresh JWT token from Shiprocket.
        """
        # 1. Check database cache first
        if self.credentials.shiprocket_token and self.credentials.shiprocket_token_expiry:
            # Check if token is still valid (with a 30-minute buffer)
            if timezone.now() < (self.credentials.shiprocket_token_expiry - timedelta(minutes=30)):
                return self.credentials.shiprocket_token

        # 2. Fetch new token from API
        email = self.credentials.get_shiprocket_email()
        password = self.credentials.get_shiprocket_password()

        if not email or not password:
            raise ValueError("Shiprocket API credentials (email or password) are not configured.")

        url = "https://apiv2.shiprocket.in/v1/external/auth/login"
        payload = {
            "email": email,
            "password": password
        }
        
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if not resp.ok:
                raise Exception(f"HTTP Error {resp.status_code} during login: {resp.text}")
            
            data = resp.json()
            token = data.get("token")
            if not token:
                raise ValueError("Shiprocket response succeeded but 'token' was missing.")
            
            # Cache the token in the DB (valid for 10 days, we set cache expiry to 9 days)
            self.credentials.shiprocket_token = token
            self.credentials.shiprocket_token_expiry = timezone.now() + timedelta(days=9)
            self.credentials.save(update_fields=['shiprocket_token', 'shiprocket_token_expiry'])
            
            return token
            
        except Exception as e:
            logger.error(f"[SHIPROCKET-AUTH] Authentication failed: {e}", exc_info=True)
            raise e

    def validate_credentials(self) -> bool:
        try:
            token = self._get_token()
            return bool(token)
        except Exception:
            return False

    def book_shipment(self, order, carrier_id) -> tuple[bool, dict]:
        try:
            token = self._get_token()
            
            # Derive payment method: Prepaid or COD
            ptype = derive_payment_type_from_fields(
                payment_gateway_names=order.payment_gateway_names,
                financial_status=order.financial_status,
                tags=order.tags,
                raw_data=order.raw_data
            )
            shiprocket_payment_method = "COD" if ptype in ['COD', 'Partially Paid'] else "Prepaid"

            # Parse shipping address details with raw_data fallbacks
            raw_addr = (order.raw_data or {}).get("shipping_address", {})
            
            first_name = raw_addr.get("first_name") or order.customer_first_name or "Valued"
            last_name = raw_addr.get("last_name") or order.customer_last_name or "Customer"
            phone = raw_addr.get("phone") or order.contact_phone or ""
            email = order.contact_email or "no-email@bridgeworks.com"
            
            # Address lines
            address1 = raw_addr.get("address1") or ""
            address2 = raw_addr.get("address2") or ""
            if not address1:
                # Fallback: slice the unified address field
                address1 = order.shipping_address or "Address details"
                if len(address1) > 90:
                    address2 = address1[90:180]
                    address1 = address1[:90]

            city = raw_addr.get("city") or "Mumbai"
            state = raw_addr.get("province") or order.shipping_state or "Maharashtra"
            pincode = raw_addr.get("zip") or order.shipping_pincode or "400001"

            # Compile line items
            order_items = []
            for item in order.line_items.all():
                order_items.append({
                    "name": item.title or "Jewelry Item",
                    "sku": item.sku or "NO-SKU",
                    "units": item.quantity or 1,
                    "selling_price": str(item.price)
                })

            if not order_items:
                order_items.append({
                    "name": "Jewelry Item",
                    "sku": "NO-SKU",
                    "units": 1,
                    "selling_price": str(order.total_price or 0.00)
                })

            # Format default dimensions and weights
            weight = self.credentials.shiprocket_order_weight or 0.5
            length = self.credentials.shiprocket_box_length or 10
            breadth = self.credentials.shiprocket_box_breadth or 10
            height = self.credentials.shiprocket_box_height or 10

            # Full order ID matching prefix if any
            prefix = self.credentials.shopify_order_prefix or ""
            full_order_id = f"{prefix}{order.order_number}" if prefix else str(order.order_number)

            payload = {
                "order_id": full_order_id,
                "order_date": order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else timezone.now().strftime("%Y-%m-%d %H:%M"),
                "pickup_location": self.credentials.shiprocket_pickup_location or "Primary",
                "billing_customer_name": first_name,
                "billing_last_name": last_name,
                "billing_address": address1,
                "billing_address_2": address2,
                "billing_city": city,
                "billing_pincode": pincode,
                "billing_state": state,
                "billing_country": "India",
                "billing_email": email,
                "billing_phone": phone,
                "shipping_is_billing": True,
                "order_items": order_items,
                "payment_method": shiprocket_payment_method,
                "sub_total": float(order.total_price or 0.0),
                "length": int(length),
                "breadth": int(breadth),
                "height": int(height),
                "weight": float(weight)
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            url = "https://apiv2.shiprocket.in/v1/external/orders/create/adhoc"
            
            # 1. Create order on Shiprocket
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if not resp.ok:
                return False, {
                    "error": f"Shiprocket returned HTTP {resp.status_code}: {resp.text}",
                    "code": f"SHIPROCKET_HTTP_{resp.status_code}"
                }

            data = resp.json()
            shipment_id = data.get("shipment_id")
            sr_order_id = data.get("order_id")

            if not shipment_id:
                return False, {
                    "error": data.get("message") or "Order pushed to Shiprocket but shipment_id is missing.",
                    "code": "SHIPROCKET_ORDER_CREATE_FAILED"
                }

            # 2. Auto-generate AWB / Ship order
            # If carrier_id is provided, we attempt to assign courier via Shiprocket API
            # Else, we can let Shiprocket auto-allocate based on client settings.
            # Here we assign via standard courier assignment POST /v1/external/courier/assign/awb
            assign_url = "https://apiv2.shiprocket.in/v1/external/courier/assign/awb"
            assign_payload = {
                "shipment_id": int(shipment_id)
            }
            if carrier_id and str(carrier_id).isdigit():
                assign_payload["courier_id"] = int(carrier_id)

            assign_resp = requests.post(assign_url, json=assign_payload, headers=headers, timeout=20)
            if not assign_resp.ok:
                return False, {
                    "error": f"Order created (ID: {sr_order_id}) but AWB assignment failed: {assign_resp.text}",
                    "code": "SHIPROCKET_AWB_ASSIGN_FAILED"
                }

            assign_data = assign_resp.json()
            awb_info = assign_data.get("response", {}).get("data", {})
            awb = awb_info.get("awb_code")

            if not awb:
                return False, {
                    "error": assign_data.get("message") or "Courier assignment request succeeded but AWB code was empty.",
                    "code": "SHIPROCKET_AWB_EMPTY"
                }

            courier_name = awb_info.get("courier_name") or "Shiprocket Courier"

            return True, {
                "awb": awb,
                "carrier_name": courier_name,
                "tracking_url": f"https://track.shiprocket.in/r/{awb}"
            }

        except Exception as e:
            logger.error(f"[SHIPROCKET-BOOKING] Booking failed: {e}", exc_info=True)
            return False, {
                "error": str(e),
                "code": "SHIPROCKET_EXCEPTION"
            }
