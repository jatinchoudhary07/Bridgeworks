"""
enrich_orders
=============
Enrich CSV-imported orders by calling the Shopify API for full order details
and then backfilling tracking data from Shipway.

Usage:
    python manage.py enrich_orders --org-id "janki-jewels" --limit 500
    python manage.py enrich_orders --org-id "janki-jewels" --limit 500 --skip-shipway
"""

import time
import logging
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from core.models import Order, LineItem, Fulfillment, TrackingInfo, TrackingEvent
from core.utils import _get_decrypted_credentials

logger = logging.getLogger(__name__)


# Shopify API rate limit: 2 calls/second = 500ms between calls
SHOPIFY_DELAY = 0.55

# Shipway status code mapping (same as fetch.py)
SHIPWAY_CODE_MAP = {
    "DEL": "Delivered", "DELIVERED": "Delivered",
    "INT": "In Transit", "IN TRANSIT": "In Transit",
    "UND": "Undelivered",
    "RTO": "RTO Initiated", "RTD": "RTO Delivered",
    "CAN": "Cancelled",
    "SCH": "Shipment Booked", "Booked": "Shipment Booked",
    "PKP": "Picked Up", "PUP": "Picked Up", "PICKED UP": "Picked Up",
    "OOD": "Out For Delivery", "OUT FOR DELIVERY": "Out For Delivery",
    "RINT": "Return In Transit", "RDEL": "Return Delivered",
}


class Command(BaseCommand):
    help = 'Enrich CSV-imported orders by fetching full data from Shopify API and tracking from Shipway.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id', type=str, required=True,
            help='Organization ID (e.g., "janki-jewels")'
        )
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Number of orders to process (default: 100)'
        )
        parser.add_argument(
            '--skip-shipway', action='store_true',
            help='Skip the Shipway tracking backfill step (only do Shopify enrichment)'
        )
        parser.add_argument(
            '--only-missing', action='store_true',
            help='Only process orders that have no fulfillments yet'
        )

    def handle(self, *args, **options):
        org_id = options['org_id'].strip()
        limit = options['limit']
        skip_shipway = options['skip_shipway']
        only_missing = options['only_missing']

        # --- 1. GET CREDENTIALS ---
        creds = _get_decrypted_credentials(org_id)
        if not creds:
            self.stderr.write(self.style.ERROR(f"No credentials found for org: {org_id}"))
            return

        shop_url = creds['shop_url']
        api_key = creds['api_key']
        password = creds['password']
        api_version = creds['api_version']
        order_prefix = creds.get('order_prefix', '')
        shipway_login = creds.get('shipway_email')
        shipway_password = creds.get('shipway_license_key')

        # --- 2. QUERY ORDERS ---
        query = Order.objects.filter(org_id=org_id, shopify_id__isnull=False).order_by('created_at')

        if only_missing:
            query = query.filter(fulfillments__isnull=True)

        orders = query[:limit]
        total = orders.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No orders found to enrich."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Starting enrichment for {total} orders (Org: {org_id})..."
        ))

        shopify_success = 0
        shopify_skipped = 0
        shopify_errors = 0
        shipway_success = 0
        shipway_errors = 0

        for idx, order in enumerate(orders, 1):
            # --- STEP A: SHOPIFY API ENRICHMENT ---
            self.stdout.write(f"[{idx}/{total}] Order #{order.order_number} (Shopify ID: {order.shopify_id})")

            try:
                api_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders/{order.shopify_id}.json"
                resp = requests.get(api_url, timeout=15)

                if resp.status_code == 404:
                    self.stdout.write(self.style.WARNING(f"  Shopify: 404 - Order not found on Shopify"))
                    shopify_skipped += 1
                    time.sleep(SHOPIFY_DELAY)
                    continue

                if resp.status_code == 429:
                    self.stdout.write(self.style.WARNING(f"  Shopify: Rate limited. Waiting 5s..."))
                    time.sleep(5)
                    resp = requests.get(api_url, timeout=15)

                if not resp.ok:
                    self.stderr.write(self.style.ERROR(f"  Shopify API error: {resp.status_code}"))
                    shopify_errors += 1
                    time.sleep(SHOPIFY_DELAY)
                    continue

                api_order = resp.json().get('order', {})
                if not api_order:
                    shopify_skipped += 1
                    time.sleep(SHOPIFY_DELAY)
                    continue

                with transaction.atomic():
                    # --- Update Order fields ---
                    order.raw_data = api_order
                    order.fulfillment_status = api_order.get('fulfillment_status') or order.fulfillment_status
                    order.financial_status = api_order.get('financial_status') or order.financial_status

                    # Customer data from Shopify (don't overwrite PII we already have)
                    customer_data = api_order.get('customer') or {}
                    if not order.contact_email and customer_data.get('email'):
                        order.contact_email = customer_data['email']
                    if not order.contact_phone:
                        shipping_addr = api_order.get('shipping_address') or {}
                        if shipping_addr.get('phone'):
                            order.contact_phone = shipping_addr['phone']

                    # Discount codes (richer from API)
                    if api_order.get('discount_codes'):
                        order.discount_codes = api_order['discount_codes']

                    order.save()

                    # --- Update Line Items with product_id, variant_id, vendor ---
                    api_line_items = api_order.get('line_items', [])
                    if api_line_items:
                        # Delete old CSV-created line items and recreate with full data
                        order.line_items.all().delete()
                        items_to_create = []
                        for item in api_line_items:
                            items_to_create.append(LineItem(
                                order=order,
                                product_id=item.get('product_id'),
                                variant_id=item.get('variant_id'),
                                title=item.get('title', ''),
                                name=item.get('name', ''),
                                quantity=item.get('quantity', 1),
                                price=item.get('price', '0.00'),
                                sku=item.get('sku', ''),
                                vendor=item.get('vendor', ''),
                            ))
                        LineItem.objects.bulk_create(items_to_create)

                    # --- Create Fulfillments from Shopify API ---
                    api_fulfillments = api_order.get('fulfillments', [])
                    if api_fulfillments:
                        # Extract existing label URL if it is a valid PDF label
                        existing_label_url = None
                        for f in order.fulfillments.all():
                            for t in f.tracking_info.all():
                                if t.url and "track.shipway.com" not in t.url:
                                    existing_label_url = t.url
                                    break
                            if existing_label_url:
                                break

                        # Clear any existing fulfillments first
                        order.fulfillments.all().delete()

                        for f_data in api_fulfillments:
                            fulfillment_obj = Fulfillment.objects.create(
                                order=order,
                                shopify_id=f_data.get('id'),
                                status=f_data.get('status', ''),
                                shipment_status=f_data.get('shipment_status', ''),
                                created_at=f_data.get('created_at'),
                                updated_at=f_data.get('updated_at'),
                                service=f_data.get('service', ''),
                            )

                            # Create TrackingInfo
                            tracking_numbers = f_data.get('tracking_numbers', [])
                            tracking_urls = f_data.get('tracking_urls', [])
                            tracking_company = f_data.get('tracking_company', '')

                            for t_idx, t_num in enumerate(tracking_numbers):
                                default_url = tracking_urls[t_idx] if t_idx < len(tracking_urls) else ''
                                TrackingInfo.objects.create(
                                    fulfillment=fulfillment_obj,
                                    number=t_num,
                                    company=tracking_company,
                                    url=existing_label_url or default_url,
                                )

                    shopify_success += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  Shopify: OK ({len(api_line_items)} items, {len(api_fulfillments)} fulfillments)"
                    ))

            except Exception as e:
                shopify_errors += 1
                self.stderr.write(self.style.ERROR(f"  Shopify error: {e}"))
                logger.exception(f"Shopify enrichment failed for Order #{order.order_number}")

            # --- STEP B: SHIPWAY TRACKING BACKFILL ---
            if not skip_shipway and shipway_login and shipway_password:
                try:
                    # Find the AWB number from the fulfillment we just created
                    tf = order.fulfillments.first()
                    if tf:
                        ti = tf.tracking_info.first()
                        awb = ti.number if ti else None
                    else:
                        awb = None

                    if awb and awb != "N/A":
                        full_order_id = f"{order_prefix}{order.order_number}"

                        # Fetch history from Shipway
                        resp_hist = requests.get(
                            "https://app.shipway.com/api/getorders",
                            params={
                                'orderid': full_order_id,
                                'username': shipway_login,
                                'password': shipway_password,
                            },
                            timeout=15
                        )

                        merged_scans = []
                        if resp_hist.ok:
                            data = resp_hist.json()
                            history_data = None
                            if isinstance(data, dict):
                                if 'message' in data and isinstance(data['message'], list):
                                    history_data = data['message'][0] if data['message'] else None
                                else:
                                    history_data = data

                            if history_data:
                                raw_scans = history_data.get('shipment_status_scan', [])
                                for scan in raw_scans:
                                    merged_scans.append({
                                        'status': scan.get('status', ''),
                                        'date_str': scan.get('datetime'),
                                        'details': scan.get('sub_status', ''),
                                    })

                        # Fetch latest tracking
                        resp_track = requests.get(
                            "https://app.shipway.com/api/tracking",
                            params={
                                'awb_numbers': awb,
                                'tracking_history': 1,
                                'username': shipway_login,
                                'password': shipway_password,
                            },
                            timeout=15
                        )

                        if resp_track.ok:
                            raw = resp_track.json()
                            if isinstance(raw, list) and len(raw) > 0:
                                latest = raw[0].get('tracking_details', {})
                                if latest:
                                    raw_code = latest.get('shipment_status', '')
                                    readable = SHIPWAY_CODE_MAP.get(raw_code, raw_code) or raw_code
                                    if readable:
                                        readable = readable.title()

                                    details_arr = latest.get('shipment_details', [{}])
                                    inner_status = details_arr[0].get('current_status', '') if details_arr else ''

                                    # RTO detection
                                    if inner_status and ('rto' in inner_status.lower() or 'return' in inner_status.lower()):
                                        if not readable.lower().startswith('rto'):
                                            readable = f"RTO - {readable}"

                                    # Update fulfillment shipment_status
                                    if tf and readable:
                                        courier_name = details_arr[0].get('courier_name', '') if details_arr else ''
                                        tf.shipment_status = readable
                                        if courier_name:
                                            tf.service = courier_name
                                        tf.save()

                                    # Add to scans if not duplicate
                                    if readable and (not merged_scans or merged_scans[-1]['status'].title() != readable):
                                        merged_scans.append({
                                            'status': readable,
                                            'date_str': timezone.now().isoformat(),
                                            'details': inner_status,
                                        })

                        # Save tracking events
                        if merged_scans and tf:
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
                                    except Exception:
                                        dt_val = timezone.now()
                                else:
                                    dt_val = timezone.now()

                                if dt_val:
                                    events_to_create.append(TrackingEvent(
                                        fulfillment=tf,
                                        status=scan['status'],
                                        datetime=dt_val,
                                        details=scan['details'],
                                    ))

                            if events_to_create:
                                TrackingEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)

                            order.update_tracking_status()
                            shipway_success += 1
                            self.stdout.write(self.style.SUCCESS(
                                f"  Shipway: OK ({len(merged_scans)} events, status: {order.current_status})"
                            ))
                    else:
                        self.stdout.write(f"  Shipway: Skipped (no AWB)")

                except Exception as e:
                    shipway_errors += 1
                    self.stderr.write(self.style.ERROR(f"  Shipway error: {e}"))

            # Rate limit
            time.sleep(SHOPIFY_DELAY)

            # Progress checkpoint every 50 orders
            if idx % 50 == 0:
                self.stdout.write(self.style.SUCCESS(
                    f"\n--- Checkpoint: {idx}/{total} processed ---\n"
                ))

        # --- SUMMARY ---
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Enrichment Complete!"))
        self.stdout.write(f"  Shopify: {shopify_success} enriched, {shopify_skipped} skipped, {shopify_errors} errors")
        if not skip_shipway:
            self.stdout.write(f"  Shipway: {shipway_success} tracking backfilled, {shipway_errors} errors")
        self.stdout.write("=" * 60)
