import requests
import json
import base64
import logging
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from core.models import Fulfillment, TrackingEvent, Order, TrackingInfo
from core.utils import _get_decrypted_credentials

# ==============================================================================
# RETRY DELAYS for Smart Retry (Exponential Backoff)
# ==============================================================================
RETRY_DELAYS = {
    1: 10,   # After attempt 1 fails → retry in 10 minutes
    2: 30,   # After attempt 2 fails → retry in 30 minutes
}
MAX_ATTEMPTS = 3


def _is_address_empty(addr):
    """Check if an address is effectively empty (None, blank, or just commas/spaces)."""
    if not addr:
        return True
    cleaned = str(addr).replace(',', '').replace('None', '').strip()
    return len(cleaned) == 0


def _maybe_retry(order_id, org_id, current_attempt, reason):
    """
    Helper: Reschedule the PII fetch task with exponential backoff,
    or log final failure if max attempts reached.
    """
    from django_q.tasks import schedule
    from datetime import timedelta

    if current_attempt >= MAX_ATTEMPTS:
        print(
            f"[PII-TASK] ❌ FINAL FAILURE for Order ID {order_id} after {MAX_ATTEMPTS} attempts. "
            f"Reason: {reason}. Will not retry."
        )
        return

    next_attempt = current_attempt + 1
    delay_minutes = RETRY_DELAYS.get(current_attempt, 30)

    print(
        f"[PII-TASK] Scheduling retry (attempt {next_attempt}) for Order ID {order_id} "
        f"in {delay_minutes} minutes. Reason: {reason}"
    )

    schedule(
        'core.tasks.fetch_missing_pii_task',
        order_id,
        org_id,
        next_attempt,
        next_run=timezone.now() + timedelta(minutes=delay_minutes),
    )


def fetch_missing_pii_task(order_id, org_id, attempt=1):
    """
    Background Task (django-q): Fetches customer PII from Shipway's getorders API.
    
    Shopify redacts customer PII (name, phone, address) in webhook payloads.
    This task fetches the unredacted data from Shipway and updates the Order.
    
    Smart Retry: If Shipway hasn't synced yet (returns "Not Found"),
    the task reschedules itself with exponential backoff.
    """
    from django_q.tasks import schedule
    from datetime import timedelta

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        print(f"[PII-TASK] Order ID {order_id} not found. Aborting.")
        return

    # Auto-detect: If customer PII details are already fully present, skip fetching from Shipway
    if order.customer_first_name and order.contact_phone and order.shipping_address:
        print(f"[PII-TASK] Order #{order.order_number} already has customer PII. Skipping Shipway fetch.")
        return

    # Check explicit configuration toggle to skip Shipway PII sync
    from core.models import ShopCredentials
    try:
        shop_cred = ShopCredentials.objects.get(organization_id=org_id)
        if shop_cred.skip_shipway_pii_sync:
            print(f"[PII-TASK] Shipway PII sync is disabled for org {org_id} (skip_shipway_pii_sync=True). Skipping.")
            return
    except ShopCredentials.DoesNotExist:
        pass

    print(f"[PII-TASK] Fetching PII for Order #{order.order_number} (attempt {attempt}/{MAX_ATTEMPTS}, org: {org_id})")

    creds = _get_decrypted_credentials(org_id)
    if not creds:
        print(f"[PII-TASK] No credentials for org {org_id}. Aborting.")
        return

    shipway_email = creds.get('shipway_email')
    shipway_license_key = creds.get('shipway_license_key')
    order_prefix = creds.get('order_prefix', '')

    if not shipway_email or not shipway_license_key:
        print(f"[PII-TASK] Shipway credentials missing for org {org_id}. Aborting.")
        return

    full_order_id = f"{order_prefix}{order.order_number}" if order_prefix else str(order.order_number)
    
    credentials_str = f"{shipway_email}:{shipway_license_key}"
    encoded_creds = base64.b64encode(credentials_str.encode()).decode()
    headers = {'Authorization': f'Basic {encoded_creds}'}

    url = "https://app.shipway.com/api/getorders"

    try:
        resp = requests.get(url, params={'orderid': full_order_id}, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"[PII-TASK] Network error for Order #{order.order_number}: {e}")
        _maybe_retry(order_id, org_id, attempt, f"Network error: {e}")
        return

    if not resp.ok:
        print(f"[PII-TASK] Shipway returned HTTP {resp.status_code} for Order #{order.order_number}")
        _maybe_retry(order_id, org_id, attempt, f"HTTP {resp.status_code}")
        return

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(f"[PII-TASK] Invalid JSON from Shipway for Order #{order.order_number}")
        _maybe_retry(order_id, org_id, attempt, "Invalid JSON response")
        return

    success = data.get('success')
    messages = data.get('message', [])

    if not success or not isinstance(messages, list) or len(messages) == 0:
        print(f"[PII-TASK] Shipway has no data for Order #{order.order_number} yet.")
        _maybe_retry(order_id, org_id, attempt, "Order not found in Shipway")
        return

    shipway_order = messages[0]

    first_name = (shipway_order.get('s_firstname') or shipway_order.get('b_firstname') or '').strip()
    last_name = (shipway_order.get('s_lastname') or shipway_order.get('b_lastname') or '').strip()
    phone = (shipway_order.get('s_phone') or shipway_order.get('b_phone') or '').strip()
    email = (shipway_order.get('email') or '').strip()

    addr_parts = [
        f"{first_name} {last_name}".strip(),
        shipway_order.get('s_address', ''),
        shipway_order.get('s_address_2', ''),
        shipway_order.get('s_city', ''),
        shipway_order.get('s_state', ''),
        shipway_order.get('s_zipcode', ''),
        shipway_order.get('s_country', ''),
    ]
    shipping_address_text = ', '.join(part for part in addr_parts if part and part.strip())

    print(f"[PII-TASK] Shipway data for #{order.order_number}: name={first_name} {last_name}, phone={phone}, addr={shipping_address_text[:80]}...")

    update_fields = []

    if first_name and not order.customer_first_name:
        order.customer_first_name = first_name
        update_fields.append('customer_first_name')

    if last_name and not order.customer_last_name:
        order.customer_last_name = last_name
        update_fields.append('customer_last_name')

    if phone:
        order.contact_phone = phone
        update_fields.append('contact_phone')

    if email and not order.contact_email:
        order.contact_email = email
        update_fields.append('contact_email')

    if shipping_address_text and not _is_address_empty(shipping_address_text):
        order.shipping_address = shipping_address_text
        update_fields.append('shipping_address')

    state = (shipway_order.get('s_state') or shipway_order.get('b_state') or '').strip()
    pincode = (shipway_order.get('s_zipcode') or shipway_order.get('b_zipcode') or '').strip()

    if state:
        order.shipping_state = state
        update_fields.append('shipping_state')
    if pincode:
        order.shipping_pincode = pincode
        update_fields.append('shipping_pincode')

    if update_fields:
        order.save(update_fields=update_fields)
        print(f"[PII-TASK] ✅ PII updated for Order #{order.order_number}: {update_fields}")
    else:
        print(f"[PII-TASK] No PII data from Shipway for Order #{order.order_number}. Nothing to update.")

    if phone:
        from core.models import Customer
        clean_phone = phone.strip()
        
        customer, created = Customer.objects.get_or_create(
            org_id=org_id,
            phone=clean_phone,
            defaults={
                'name': f"{first_name} {last_name}".strip() or email or "Unknown",
                'email': email,
                'address': shipping_address_text
            }
        )
        
        if order.customer_id != customer.id:
            order.customer = customer
            order.save(update_fields=['customer'])
            print(f"[PII-TASK] 🔗 Linked Order #{order.order_number} to Customer Profile: {customer.name} ({customer.phone})")


def fetch_and_save_shipway_history(order_id, fulfillment_id, org_id):
    """
    Robust Background Task:
    1. Tries to fetch real-time status from api/tracking (via AWB).
    2. Falls back to api/getorders (via Order ID).
    3. Merges data, maps status codes, and updates the Order status.
    """
    try:
        order = Order.objects.get(id=order_id)
        fulfillment = Fulfillment.objects.get(id=fulfillment_id)
        
        print(f"[TASK] Syncing Order #{order.order_number} (Org: {org_id})")

        creds = _get_decrypted_credentials(org_id)
        if not creds:
            print(f"[TASK] No credentials for org {org_id}.")
            return

        shipway_email = creds['shipway_email']
        shipway_license_key = creds['shipway_license_key']
        order_prefix = creds['order_prefix']

        # Build auth header (same as backfill_shipway_pii.py)
        encoded = base64.b64encode(f"{shipway_email}:{shipway_license_key}".encode()).decode()
        shipway_headers = {'Authorization': f'Basic {encoded}'}

        url_getorders = "https://app.shipway.com/api/getorders"
        url_tracking = "https://app.shipway.com/api/tracking"

        SHIPWAY_CODE_MAP = {
            "DEL": "Delivered", "DELIVERED": "Delivered",
            "INT": "In Transit", "IN TRANSIT": "In Transit",
            "OOD": "Out For Delivery", "OUT FOR DELIVERY": "Out For Delivery",
            "PUP": "Picked Up", "PICKED UP": "Picked Up",
            "SCH": "Shipment Booked", "Booked": "Shipment Booked",
            "RTO": "RTO Initiated", "RTD": "RTO Delivered",
            "RINT": "Return In Transit", "RDEL": "Return Delivered",
            "SHNDR1": "Consignee Uncontactable", "SHNDR2": "Wrong Address",
            "SHNDR3": "COD Not Ready", "SHNDR4": "Customer Asked For Future Delivery",
            "SHNDR5": "Customer Asked For Self Collect", "SHNDR6": "Customer Refused",
            "SHNDR7": "Auto Reattempt", "SHNDR8": "Office/Residence Closed",
            "SHNDR9": "Others", "SHNDR10": "Entry Restricted Area",
            "SHNDR11": "Out of Delivery Area", "SHNDR12": "Payment/Qty/Bill/OTP Dispute",
            "SHNDR13": "Reattempt Next Day", "SHNDR14": "Customer Requested Open Delivery",
            "SHNDR15": "Customer did not show ID card", "SHNDR16": "Customer Not Available",
            "SHNDR17": "COVID - Access Restricted", "SHNDR18": "Customer Refused - OTP Verified",
            "SHNDR19": "Customer Refused - IVR Verified", "SHNDR20": "Delivery Not Attempted",
            "SHNDR21": "Customer Not Ready with Exchange Item", "SHNDR22": "Doubtful Order",
            "SHPFR0": "Pickup Exception - Others", "SHPFR1": "Seller Not Available / Phone Not Contactable",
            "SHPFR2": "Incomplete Address / Vendor Shifted", "SHPFR3": "No Pickup / Shipment Not Ready",
            "SHPFR4": "Vehicle Issue / Space Constraint", "SHPFR5": "Regulatory Not Compliant",
            "SHPFR6": "Pickup Request Cancelled by Seller", "SHPFR7": "Seller Requested Future Pickup",
            "SHPFR8": "AWB Rejected", "SHPFR9": "Duplicate Pickup Request",
            "SHPFR10": "No Attempt / Pickup Delay", "SHPFR11": "Non Serviceable Location",
            "SHPFR12": "Pickup Failed - Dangerous Goods", "SHPFR13": "Product Packaging Issue",
            "SHPFR14": "RTO", "SHPFR15": "Handed Over to Other Courier",
            "SHPFR16": "Shipper Premises Closed", "SHPFR17": "Barcode Issue",
            "SHPRF18": "Seller Closed", "SHPRF19": "COVID - Access Restricted",
            "SHPRF20": "Pickup Request Expired",
            "RTONDR1": "Seller Wants Open Delivery", "RTONDR2": "Seller Premise Closed",
            "RTONDR3": "Seller Not Contactable", "RTONDR4": "Address Not Correct",
            "RTONDR5": "Seller Refused Delivery", "RTONDR6": "RTO - Other",
            "RTONDR7": "RTO - Wrong Address", "RTONDR8": "Seller Refused - Damaged",
            "RTONDR9": "Seller Refused - Content Missing", "RTONDR10": "Seller Refused - Invoice Missing",
            "RTONDR11": "Seller Uncontactable", "RTONDR12": "Seller Not Available"
        }

        merged_scans = []
        history_data = None
        latest_data = None

        try:
            full_id = f"{order_prefix}{order.order_number}"
            resp_hist = requests.get(url_getorders, params={'orderid': full_id}, headers=shipway_headers, timeout=15)
            if resp_hist.ok:
                data = resp_hist.json()
                if isinstance(data, dict):
                    if 'message' in data and isinstance(data['message'], list):
                        history_data = data['message'][0]
                    else:
                        history_data = data
        except Exception as e:
            print(f"[TASK] History fetch failed: {e}")

        awb = None
        if history_data and history_data.get('tracking_number'):
            awb = history_data.get('tracking_number')
        else:
            ti = fulfillment.tracking_info.first()
            if ti and ti.number and ti.number != "N/A":
                awb = ti.number

        if awb:
            try:
                resp_track = requests.get(url_tracking, params={"awb_numbers": awb, "tracking_history": 1}, headers=shipway_headers, timeout=15)
                if resp_track.ok:
                    raw = resp_track.json()
                    if isinstance(raw, list) and len(raw) > 0:
                        latest_data = raw[0].get('tracking_details')
            except Exception as e:
                print(f"[TASK] Tracking fetch failed: {e}")

        if history_data:
            raw_scans = history_data.get('shipment_status_scan', [])
            for scan in raw_scans:
                merged_scans.append({
                    'status': scan.get('status'),
                    'date_str': scan.get('datetime'),
                    'details': scan.get('sub_status', '')
                })

        if latest_data:
            raw_code = latest_data.get('shipment_status')
            readable_status = SHIPWAY_CODE_MAP.get(raw_code, raw_code)
            if readable_status: readable_status = readable_status.title()

            details_arr = latest_data.get('shipment_details', [{}])
            extra_details = ""
            inner_status = ""
            
            if details_arr:
                inner_status = details_arr[0].get('current_status') or ""
                extra_details = inner_status

            if inner_status and ("rto" in inner_status.lower() or "return" in inner_status.lower()):
                if not readable_status.lower().startswith("rto"):
                    readable_status = f"RTO - {readable_status}"

            real_date = timezone.now()
            if details_arr:
                det = details_arr[0]
                if "delivered" in readable_status.lower() and det.get('delivered_date'):
                    real_date = det.get('delivered_date')
                elif "picked up" in readable_status.lower() and det.get('pickup_date'):
                    real_date = det.get('pickup_date')

            if readable_status:
                last_status = merged_scans[-1]['status'].title() if merged_scans else ""
                if readable_status != last_status:
                    print(f"[TASK] Injecting status '{readable_status}' for #{order.order_number}")
                    merged_scans.append({
                        'status': readable_status,
                        'date_str': real_date,
                        'details': extra_details
                    })

        if merged_scans or latest_data:
            if latest_data:
                raw_code_main = latest_data.get('shipment_status')
                main_status = SHIPWAY_CODE_MAP.get(raw_code_main, raw_code_main).title()
                
                details_arr = latest_data.get('shipment_details', [{}])
                inner_status = details_arr[0].get('current_status') if details_arr else ""
                if inner_status and ("rto" in inner_status.lower() or "return" in inner_status.lower()):
                     if not main_status.lower().startswith("rto"):
                        main_status = f"RTO - {main_status}"

                main_service = details_arr[0].get('courier_name') if details_arr else "Unknown"
            else:
                main_status = history_data.get('shipment_status_name') if history_data else "Unknown"
                main_service = history_data.get('carrier_title') if history_data else "Unknown"

            fulfillment.shipment_status = main_status
            fulfillment.service = main_service
            fulfillment.save()

            if awb:
                ti, created = TrackingInfo.objects.get_or_create(fulfillment=fulfillment)
                ti.number = awb
                ti.company = main_service
                if created or not ti.url or "track.shipway.com" in ti.url:
                    ti.url = f"https://track.shipway.com/t/{awb}"
                ti.save()

            fulfillment.tracking_events.all().delete()
            events_to_create = []
            for scan in merged_scans:
                dt_val = None
                d_input = scan['date_str']
                if isinstance(d_input, timezone.datetime):
                    dt_val = d_input
                elif d_input:
                    try:
                        cln = str(d_input).replace(" ", "T")
                        dt_val = parse_datetime(cln)
                        if dt_val and dt_val.tzinfo is None: dt_val = make_aware(dt_val)
                    except:
                        dt_val = timezone.now()
                
                if dt_val:
                    events_to_create.append(TrackingEvent(
                        fulfillment=fulfillment,
                        status=scan['status'],
                        datetime=dt_val,
                        details=scan['details']
                    ))
            
            if events_to_create:
                TrackingEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)

            order.update_tracking_status()
            print(f"[TASK] Successfully synced #{order.order_number}")

    except Exception as e:
        print(f"[TASK] Critical Error syncing #{order_id}: {e}")


def book_shipment_on_shipway(order, creds, carrier_id):
    """
    Calls Shipway API to book a shipment and generate AWB.
    URL: POST https://app.shipway.com/api/v2orders
    """
    shipway_email = creds.get('shipway_email')
    shipway_license_key = creds.get('shipway_license_key')
    order_prefix = creds.get('order_prefix', '')

    if not shipway_email or not shipway_license_key:
        return False, "Shipway credentials missing"

    # Full alphanumeric ID matching Shopify prefix if any (e.g. JANKI35192)
    full_order_id = f"{order_prefix}{order.order_number}" if order_prefix else str(order.order_number)

    # Basic Auth
    credentials_str = f"{shipway_email}:{shipway_license_key}"
    encoded_creds = base64.b64encode(credentials_str.encode()).decode()
    headers = {
        'Authorization': f'Basic {encoded_creds}',
        'Content-Type': 'application/json'
    }

    # Map payment type: Prepaid -> P, COD / Partially Paid -> C
    from core.utils.payment_utils import derive_payment_type_from_fields
    ptype = derive_payment_type_from_fields(
        payment_gateway_names=order.payment_gateway_names,
        financial_status=order.financial_status,
        tags=order.tags,
        raw_data=order.raw_data
    )
    shipway_payment_type = "C" if ptype in ['COD', 'Partially Paid'] else "P"

    # Construct line items
    products = []
    for item in order.line_items.all():
        products.append({
            "product": item.title or "Jewelry Item",
            "price": str(item.price),
            "product_code": item.sku or "NO-SKU",
            "product_quantity": item.quantity
        })
    if not products:
        products.append({
            "product": "Jewelry Item",
            "price": str(order.total_price or 0.00),
            "product_code": "NO-SKU",
            "product_quantity": 1
        })

    # Extract configurable parameters with robust fallbacks
    warehouse_id = creds.get('shipway_warehouse_id')
    if warehouse_id is None:
        warehouse_id = 39842

    return_warehouse_id = creds.get('shipway_return_warehouse_id')
    if return_warehouse_id is None:
        return_warehouse_id = 39842

    order_weight = creds.get('shipway_order_weight')
    if order_weight is None:
        order_weight = 500

    box_length = creds.get('shipway_box_length')
    if box_length is None:
        box_length = 10

    box_breadth = creds.get('shipway_box_breadth')
    if box_breadth is None:
        box_breadth = 10

    box_height = creds.get('shipway_box_height')
    if box_height is None:
        box_height = 10

    invoice_number_prefix = creds.get('shipway_invoice_number_prefix') or "N"
    
    store_code = creds.get('shipway_store_code')
    if store_code is None:
        store_code = 44180

    # Prepare request payload matching Variation 2
    payload = {
        "order_id": full_order_id,
        "warehouse_id": int(warehouse_id),
        "return_warehouse_id": int(return_warehouse_id),
        "products": products,
        "payment_type": shipway_payment_type,
        "carrier_id": int(carrier_id),
        "invoice_number_prefix": invoice_number_prefix,
        "invoice_number": full_order_id,
        "order_weight": int(order_weight),
        "box_length": int(box_length),
        "box_breadth": int(box_breadth),
        "box_height": int(box_height),
        "shipping_firstname": order.customer_first_name or "",
        "shipping_lastname": order.customer_last_name or "",
        "shipping_phone": order.contact_phone or "",
        "shipping_zipcode": order.shipping_pincode or "",
        "shipping_address": order.shipping_address or "",
        "shipping_state": order.shipping_state or "",
        "shipping_country": "India",
        "email": order.contact_email or "",
        "order_total": str(order.total_price or 0.00),
        "store_code": int(store_code)
    }

    url = "https://app.shipway.com/api/v2orders"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
    except Exception as e:
        return False, f"Network error: {str(e)}"

    if not resp.ok:
        return False, f"HTTP Error {resp.status_code}: {resp.text}"

    try:
        data = resp.json()
    except Exception:
        return False, f"Invalid JSON response: {resp.text}"

    if not data.get('success'):
        return False, data.get('message') or "Failed to push order to Shipway"

    awb_resp = data.get('awb_response', {})
    if not awb_resp.get('success'):
        err_msg = ""
        if 'error' in awb_resp:
            err = awb_resp['error']
            if isinstance(err, list):
                err_msg = " | ".join(str(e) for e in err if e)
            else:
                err_msg = str(err)
        if not err_msg:
            err_msg = awb_resp.get('message') or "Failed to assign AWB"
        return False, err_msg

    awb = awb_resp.get('AWB')
    if not awb:
        return False, "Shipway success but AWB number missing in response"

    return True, {
        "awb": awb,
        "carrier_id": awb_resp.get('carrier_id') or carrier_id,
        "shipping_url": awb_resp.get('shipping_url') or ""
    }


def auto_generate_awb_for_orders_task(order_ids, org_id, recipient_emails=None, is_manual=False, user_id=None):
    """
    Background Task:
    1. Loop through each order ID.
    2. Fetch shipping platform configuration.
    3. Route shipping booking dynamically to either Shipway or Shiprocket provider strategy.
    4. If succeeds:
       - Save Fulfillment, TrackingInfo, TrackingEvent.
       - Clear order.awb_error.
       - Batch the order and mark order.status = 'Batched'.
    5. Finally, dispatch the picklist email to recipient_emails.
    """
    from django.db import transaction
    from core.models import Batch, ShopCredentials
    from django.contrib.auth import get_user_model
    from core.services.picklist_service import send_picklist_email
    from core.services.shipping.factory import get_shipping_provider

    print(f"[AUTO-AWB] Starting for {len(order_ids)} orders (Org: {org_id})")

    creds = _get_decrypted_credentials(org_id)
    if not creds:
        print(f"[AUTO-AWB] Credentials not found for org {org_id}")
        return

    try:
        shop_creds = ShopCredentials.objects.get(organization_id=org_id)
    except ShopCredentials.DoesNotExist:
        print(f"[AUTO-AWB] ShopCredentials not found for org {org_id}")
        return

    # Check if courier auto-assignment is enabled
    if not getattr(shop_creds, 'enable_auto_assign_couriers', True):
        print(f"[AUTO-AWB] Auto AWB/courier assignment is disabled in settings for org {org_id}. Skipping booking loop.")
        if recipient_emails:
            try:
                orders_qs = Order.objects.filter(id__in=order_ids)
                send_picklist_email(
                    org_id=org_id,
                    recipient_emails=recipient_emails,
                    orders_queryset=orders_qs,
                    is_manual=is_manual
                )
                print(f"[AUTO-AWB] Dispatched picklist email directly (auto-assign skipped) to {recipient_emails}")
            except Exception as e:
                print(f"[AUTO-AWB] Failed to send picklist email after auto-assign skip: {e}")
        return

    provider = get_shipping_provider(shop_creds)
    shipping_platform = getattr(shop_creds, 'shipping_platform', 'shipway').lower()

    # Attempt to fetch User if user_id is provided
    user = None
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    successful_order_ids = []

    for oid in order_ids:
        try:
            order = Order.objects.get(id=oid, org_id=org_id)
        except Order.DoesNotExist:
            print(f"[AUTO-AWB] Order {oid} not found. Skipping.")
            continue

        print(f"[AUTO-AWB] Processing Order #{order.order_number} using platform: {shipping_platform}...")

        success = False
        res = {}
        carrier_title = "Courier"

        if shipping_platform == 'shipway':
            # Get configurable carrier details for Shipway
            primary_carrier_id = creds.get('shipway_primary_carrier_id') or "82600"
            primary_carrier_title = creds.get('shipway_primary_carrier_title') or "Bluedart Direct - Surface"
            fallback_carrier_id = creds.get('shipway_fallback_carrier_id') or "2"
            fallback_carrier_title = creds.get('shipway_fallback_carrier_title') or "Direct Delhivery"

            # Step A: Try Primary Carrier
            success, res = provider.book_shipment(order, carrier_id=primary_carrier_id)
            carrier_title = primary_carrier_title

            if not success:
                primary_error = res.get("error", "Unknown error")
                print(f"[AUTO-AWB] {primary_carrier_title} failed for Order #{order.order_number}: {primary_error}. Trying fallback...")

                # Step B: Try Fallback Carrier
                success, res = provider.book_shipment(order, carrier_id=fallback_carrier_id)
                carrier_title = fallback_carrier_title

                if not success:
                    fallback_error = res.get("error", "Unknown error")
                    final_error = f"{primary_carrier_title} failed: {primary_error} | {fallback_carrier_title} failed: {fallback_error}"
                    print(f"[AUTO-AWB] Fallback also failed for Order #{order.order_number}: {fallback_error}")

                    # Save final error message to DB
                    order.awb_error = final_error
                    order.save(update_fields=['awb_error'])
                    continue
        else:
            # Shiprocket routing
            # For Shiprocket, we do not require manual fallback logic because passing None lets Shiprocket auto-allocate based on merchant rules.
            success, res = provider.book_shipment(order, carrier_id=None)
            if not success:
                error_msg = res.get("error", "Unknown error")
                print(f"[AUTO-AWB] Shiprocket failed for Order #{order.order_number}: {error_msg}")
                order.awb_error = f"Shiprocket failed: {error_msg}"
                order.save(update_fields=['awb_error'])
                continue

        # Successful booking
        awb = res["awb"]
        carrier_title = res.get("carrier_name") or carrier_title
        tracking_url = res.get("tracking_url") or f"https://track.shipway.com/t/{awb}"

        print(f"[AUTO-AWB] Successfully booked Order #{order.order_number}: AWB={awb}, Courier={carrier_title}")

        try:
            with transaction.atomic():
                # Clear any old fulfillment to avoid duplicate tracking
                order.fulfillments.all().delete()

                fulfillment_obj = Fulfillment.objects.create(
                    order=order,
                    shipment_status="Shipment Booked",
                    service=carrier_title,
                    status='success',
                    created_at=timezone.now()
                )

                TrackingInfo.objects.create(
                    fulfillment=fulfillment_obj,
                    number=awb,
                    company=carrier_title,
                    url=tracking_url
                )

                # Clear AWB error & set tracking status
                order.awb_error = ""
                order.fulfillment_status = 'Tracking_added'
                order.save(update_fields=['awb_error', 'fulfillment_status'])

                TrackingEvent.objects.create(
                    fulfillment=fulfillment_obj,
                    status="Shipment Booked",
                    datetime=timezone.now(),
                    details=f"Shipment booked via BridgeWorks Auto AWB ({shipping_platform.upper()})"
                )

                order.update_tracking_status()
                successful_order_ids.append(order.id)

        except Exception as e:
            print(f"[AUTO-AWB] Database transaction failed for Order #{order.order_number}: {e}")
            order.awb_error = f"DB transaction failed: {str(e)}"
            order.save(update_fields=['awb_error'])

    # Create batch for successful bookings
    if successful_order_ids:
        try:
            batch_name = f"printed_AWB_batch_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            new_batch = Batch.objects.create(name=batch_name, created_by=user)
            
            orders_to_batch = Order.objects.filter(id__in=successful_order_ids)
            new_batch.orders.set(orders_to_batch)
            orders_to_batch.update(status='Batched')

            print(f"[AUTO-AWB] Created Batch #{new_batch.id} with {len(successful_order_ids)} orders.")
        except Exception as e:
            print(f"[AUTO-AWB] Failed to create batch for successful orders: {e}")

    # Finally, trigger picklist email dispatch if recipients exist
    if recipient_emails:
        try:
            # Query the original order set to include both successful (batched) and failed (unbatched) orders
            orders_qs = Order.objects.filter(id__in=order_ids)
            send_picklist_email(
                org_id=org_id,
                recipient_emails=recipient_emails,
                orders_queryset=orders_qs,
                is_manual=is_manual
            )
            print(f"[AUTO-AWB] Dispatched picklist email to {recipient_emails}")
        except Exception as e:
            print(f"[AUTO-AWB] Failed to send picklist email: {e}")

