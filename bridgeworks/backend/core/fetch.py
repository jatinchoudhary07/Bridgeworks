import requests
import base64
import logging
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from .models import Order, Fulfillment, TrackingInfo, TrackingEvent, Batch
from .utils import _get_decrypted_credentials

logger = logging.getLogger(__name__)

# --- STATUS MAPPING (Shared) ---
SHIPWAY_CODE_MAP = {
    "DEL": "Delivered", "DELIVERED": "Delivered",
    "INT": "In Transit", "IN TRANSIT": "In Transit",
    "UND": "Undelivered",
    "RTO": "RTO Initiated",
    "RTD": "RTO Delivered",
    "CAN": "Cancelled",
    "SCH": "Shipment Booked", "Booked": "Shipment Booked",
    "PKP": "Picked Up", "PUP": "Picked Up", "PICKED UP": "Picked Up",
    "PKF": "Pick up Failed",
    "PCAN": "Pick up Cancelled",
    "ONH": "On Hold",
    "OOD": "Out For Delivery", "OUT FOR DELIVERY": "Out For Delivery",
    "NWI": "Network Issue",
    "DNB": "Delivery Next Day",
    "NFI": "No Information Yet",
    "ODA": "Out of Delivery Area",
    "OTH": "Others",
    "SMD": "Delivery Delayed",
    "22": "Address Incorrect",
    "23": "Delivery Attempted",
    "24": "Pending - Undelivered",
    "25": "Delivery Attempted-Premises Closed",
    "CRTA": "Customer Refused",
    "DEX": "Delivery Exception",
    "DRE": "Delivery Rescheduled",
    "PNR": "COD Payment Not Ready",
    "RAD": "Reached at Destination",
    "RINT": "Return In Transit",
    "RDEL": "Return Delivered",
    "SHNDR1": "Consignee Uncontactable",
    "SHNDR2": "Wrong Address",
    "SHNDR3": "COD Not Ready",
    "SHNDR4": "Customer Asked For Future Delivery",
    "SHNDR5": "Customer Asked For Self Collect",
    "SHNDR6": "Customer Refused",
    "SHNDR7": "Auto Reattempt",
    "SHNDR8": "Office/Residence Closed",
    "SHNDR9": "Others",
    "SHNDR10": "Entry Restricted Area",
    "SHNDR11": "Out of Delivery Area",
    "SHNDR12": "Payment/Qty/Bill/OTP Dispute",
    "SHNDR13": "Reattempt Next Day",
    "SHNDR14": "Customer Requested Open Delivery",
    "SHNDR15": "Customer did not show ID card",
    "SHNDR16": "Customer Not Available",
    "SHNDR17": "COVID - Access Restricted",
    "SHNDR18": "Customer Refused - OTP Verified",
    "SHNDR19": "Customer Refused - IVR Verified",
    "SHNDR20": "Delivery Not Attempted",
    "SHNDR21": "Customer Not Ready with Exchange Item",
    "SHNDR22": "Doubtful Order",
    "SHPFR0": "Pickup Exception - Others",
    "SHPFR1": "Seller Not Available / Phone Not Contactable",
    "SHPFR2": "Incomplete Address / Vendor Shifted",
    "SHPFR3": "No Pickup / Shipment Not Ready",
    "SHPFR4": "Vehicle Issue / Space Constraint",
    "SHPFR5": "Regulatory Not Compliant",
    "SHPFR6": "Pickup Request Cancelled by Seller",
    "SHPFR7": "Seller Requested Future Pickup",
    "SHPFR8": "AWB Rejected",
    "SHPFR9": "Duplicate Pickup Request",
    "SHPFR10": "No Attempt / Pickup Delay",
    "SHPFR11": "Non Serviceable Location",
    "SHPFR12": "Pickup Failed - Dangerous Goods",
    "SHPFR13": "Product Packaging Issue",
    "SHPFR14": "RTO",
    "SHPFR15": "Handed Over to Other Courier",
    "SHPFR16": "Shipper Premises Closed",
    "SHPFR17": "Barcode Issue",
    "SHPRF18": "Seller Closed",
    "SHPRF19": "COVID - Access Restricted",
    "SHPRF20": "Pickup Request Expired",
    "RTONDR1": "Seller Wants Open Delivery",
    "RTONDR2": "Seller Premise Closed",
    "RTONDR3": "Seller Not Contactable",
    "RTONDR4": "Address Not Correct",
    "RTONDR5": "Seller Refused Delivery",
    "RTONDR6": "RTO - Other",
    "RTONDR7": "RTO - Wrong Address",
    "RTONDR8": "Seller Refused - Damaged",
    "RTONDR9": "Seller Refused - Content Missing",
    "RTONDR10": "Seller Refused - Invoice Missing",
    "RTONDR11": "Seller Uncontactable",
    "RTONDR12": "Seller Not Available"
}


def fetch_tracking_and_batch_task(order_ids, org_id, user_id):
    """
    Async Task (2-Phase):
      Phase 1: Fetch ALL tracking data from Shipway API using threads (network only, no DB)
      Phase 2: Save ALL results to DB sequentially (no locking issues)
      Phase 3: Auto-batch successful orders
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from django.db import transaction
    from django.conf import settings

    total_requested = len(order_ids)
    logger.info(f"🚀 FETCH V4: Starting for {total_requested} orders (Org: {org_id})")

    # --- 1. SETUP CREDENTIALS ---
    creds = _get_decrypted_credentials(org_id)
    if not creds:
        return {"status": "failed", "reason": "No credentials"}

    shipway_login = creds.get('shipway_email')
    shipway_password = creds.get('shipway_license_key')
    order_prefix = creds.get('order_prefix', '')

    if not shipway_login or not shipway_password:
        return {"status": "failed", "reason": "Shipway Login Missing"}

    # Auth header (same as backfill_shipway_pii.py - proven working)
    encoded = base64.b64encode(f"{shipway_login}:{shipway_password}".encode()).decode()
    shipway_headers = {'Authorization': f'Basic {encoded}'}

    logger.info(f"🔑 FETCH V4: Auth ready. Email: {shipway_login[:5]}..., Prefix: '{order_prefix}'")

    url_getorders = "https://app.shipway.com/api/getorders"
    url_tracking = "https://app.shipway.com/api/tracking"

    # Load orders from DB (one query, main thread)
    orders = list(Order.objects.filter(id__in=order_ids, org_id=org_id))
    logger.info(f"📦 Found {len(orders)} orders in DB")

    detailed_failures = []

    # =====================================================================
    # PHASE 1: FETCH FROM SHIPWAY API (Parallel threads, NO DB writes)
    # =====================================================================
    def fetch_one_order_from_shipway(order):
        """Pure network call — returns dict with tracking data, no DB access."""
        full_id = f"{order_prefix}{order.order_number}"
        result = {
            'order_id': order.id,
            'order_number': order.order_number,
            'history_data': None,
            'latest_data': None,
            'awb': None,
            'error': None,
        }

        # --- A. FETCH HISTORY from getorders API ---
        try:
            resp = requests.get(
                url_getorders,
                params={'orderid': full_id},
                headers=shipway_headers,
                timeout=15
            )
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict):
                    msgs = data.get('message', [])
                    if isinstance(msgs, list) and len(msgs) > 0:
                        result['history_data'] = msgs[0]
                    elif data.get('success'):
                        result['history_data'] = data
            else:
                result['error'] = f"History API {resp.status_code}"
                return result
        except Exception as e:
            result['error'] = f"History Network Error: {str(e)}"
            return result

        # --- B. EXTRACT AWB ---
        if result['history_data']:
            result['awb'] = result['history_data'].get('tracking_number')

        if not result['awb']:
            result['error'] = "No AWB in Shipway"
            return result

        # --- C. FETCH TRACKING DETAILS (via AWB) ---
        try:
            resp2 = requests.get(
                url_tracking,
                params={"awb_numbers": result['awb'], "tracking_history": 1},
                headers=shipway_headers,
                timeout=15
            )
            if resp2.ok:
                raw = resp2.json()
                if isinstance(raw, list) and len(raw) > 0:
                    result['latest_data'] = raw[0].get('tracking_details')
        except Exception as e:
            logger.warning(f"Tracking API warning for {order.order_number}: {e}")

        return result

    # --- Execute API calls in parallel ---
    is_sqlite = 'sqlite' in settings.DATABASES['default']['ENGINE'].lower()
    workers = 4 if is_sqlite else 10
    api_results = []

    logger.info(f"🧵 Phase 1: Fetching from Shipway with {workers} threads...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(fetch_one_order_from_shipway, o): o for o in orders}
        for future in as_completed(future_map):
            try:
                api_results.append(future.result())
            except Exception as e:
                order = future_map[future]
                logger.error(f"Thread crash for order {order.order_number}: {e}")
                detailed_failures.append({"order": order.order_number, "reason": f"Thread Error: {str(e)}"})

    logger.info(f"✅ Phase 1 complete: {len(api_results)} API responses collected")

    # =====================================================================
    # PHASE 2: SAVE TO DB (Sequential — no locking issues)
    # =====================================================================
    updated_order_ids = []
    order_map = {o.id: o for o in orders}

    logger.info(f"💾 Phase 2: Saving to DB sequentially...")

    for result in api_results:
        order_number = result['order_number']
        order_id = result['order_id']

        # Skip failed fetches
        if result['error']:
            detailed_failures.append({"order": order_number, "reason": result['error']})
            continue

        history_data = result['history_data']
        latest_data = result['latest_data']
        awb = result['awb']

        if not awb:
            detailed_failures.append({"order": order_number, "reason": "No AWB"})
            continue

        # --- Build merged scans ---
        merged_scans = []

        if history_data:
            for scan in history_data.get('shipment_status_scan', []):
                merged_scans.append({
                    'status': scan.get('status'),
                    'date_str': scan.get('datetime'),
                    'details': scan.get('sub_status', '')
                })

        inner_status = ""
        if latest_data:
            raw_code = latest_data.get('shipment_status')
            readable_status = SHIPWAY_CODE_MAP.get(raw_code, raw_code) or raw_code
            if readable_status:
                readable_status = readable_status.title()

            details_arr = latest_data.get('shipment_details', [{}])
            inner_status = details_arr[0].get('current_status') or "" if details_arr else ""

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
                    merged_scans.append({'status': readable_status, 'date_str': real_date, 'details': inner_status})

        # --- Determine main status & service ---
        if latest_data:
            raw_code_main = latest_data.get('shipment_status')
            main_status = SHIPWAY_CODE_MAP.get(raw_code_main, raw_code_main) or "Unknown"
            main_status = main_status.title()
            details_arr = latest_data.get('shipment_details', [{}])
            if inner_status and ("rto" in inner_status.lower() or "return" in inner_status.lower()):
                if not main_status.lower().startswith("rto"):
                    main_status = f"RTO - {main_status}"
            main_service = details_arr[0].get('courier_name') if details_arr else "Unknown"
        elif history_data:
            main_status = history_data.get('shipment_status_name') or "Unknown"
            main_service = history_data.get('carrier_title') or "Unknown"
        else:
            detailed_failures.append({"order": order_number, "reason": "No Data from Shipway"})
            continue

        # --- SAVE TO DB (Sequential, atomic per order) ---
        try:
            order = order_map.get(order_id)
            if not order:
                continue

            with transaction.atomic():
                # Extract existing label URL if it is a valid PDF label
                existing_label_url = None
                for f in order.fulfillments.all():
                    for t in f.tracking_info.all():
                        if t.url and "track.shipway.com" not in t.url:
                            existing_label_url = t.url
                            break
                    if existing_label_url:
                        break

                order.fulfillments.all().delete()

                fulfillment_obj = Fulfillment.objects.create(
                    order=order, shipment_status=main_status,
                    service=main_service, status='success', created_at=timezone.now()
                )

                TrackingInfo.objects.create(
                    fulfillment=fulfillment_obj, number=awb,
                    company=main_service,
                    url=existing_label_url or f"https://track.shipway.com/t/{awb}"
                )

                order.fulfillment_status = 'Tracking_added'
                order.save()

                events_to_create = []
                for scan in merged_scans:
                    dt_val = None
                    d_input = scan['date_str']
                    if isinstance(d_input, str):
                        try:
                            cln = str(d_input).replace(" ", "T")
                            dt_val = parse_datetime(cln)
                            if dt_val and dt_val.tzinfo is None:
                                dt_val = make_aware(dt_val)
                        except:
                            dt_val = timezone.now()
                    elif hasattr(d_input, 'isoformat'):
                        dt_val = d_input
                    else:
                        dt_val = timezone.now()

                    if dt_val:
                        events_to_create.append(TrackingEvent(
                            fulfillment=fulfillment_obj,
                            status=scan['status'],
                            datetime=dt_val,
                            details=scan['details']
                        ))

                if events_to_create:
                    TrackingEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)

                order.update_tracking_status()

            updated_order_ids.append(order_id)
            logger.info(f"✅ Saved Order #{order_number}: AWB={awb}, Status={main_status}, Courier={main_service}")

        except Exception as e:
            logger.error(f"DB save failed for Order #{order_number}: {e}")
            detailed_failures.append({"order": order_number, "reason": f"DB Error: {str(e)}"})

    logger.info(f"💾 Phase 2 complete: {len(updated_order_ids)} saved, {len(detailed_failures)} failed")

    # =====================================================================
    # PHASE 3: BATCHING
    # =====================================================================
    batch_id = None
    if updated_order_ids:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user = None

            batch_name = f"printed_AWB_batch_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            new_batch = Batch.objects.create(name=batch_name, created_by=user)

            orders_to_batch = Order.objects.filter(id__in=updated_order_ids)
            new_batch.orders.set(orders_to_batch)
            orders_to_batch.update(status='Batched')

            batch_id = new_batch.id
            logger.info(f"📦 Created Batch #{new_batch.id} with {orders_to_batch.count()} orders.")
        except Exception as e:
            logger.error(f"Failed to create batch: {e}")

    # --- RETURN ---
    return {
        "success_count": len(updated_order_ids),
        "failed_count": len(detailed_failures),
        "batch_id": batch_id,
        "failures": detailed_failures
    }