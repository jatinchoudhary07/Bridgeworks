import os
import requests
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from dotenv import load_dotenv

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from core.models import Order, LineItem, Fulfillment, TrackingInfo




class Command(BaseCommand):
    help = 'Syncs up to 2000 recent orders from Shopify to the local database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            help='Number of days to sync orders from. Defaults to recent 2000.',
            required=False
        )

    def handle(self, *args, **options):
        load_dotenv()
        self.stdout.write(self.style.SUCCESS('Starting Shopify data sync...'))

        shop_url = os.getenv("SHOPIFY_SHOP_URL")
        access_token = os.getenv("SHOPIFY_API_PASSWORD")
        api_version = "2024-07"

        if not all([shop_url, access_token]):
            self.stdout.write(self.style.ERROR('Shopify credentials not found in .env file.'))
            return

        org_id = shop_url.split('.')[0] if shop_url else 'janki-jewels'

        days_to_sync = options.get('days')
        if days_to_sync:
            date_ago = (timezone.now() - timedelta(days=days_to_sync)).strftime("%Y-%m-%dT%H:%M:%SZ")
            next_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&limit=250&created_at_min={date_ago}"
            self.stdout.write(self.style.WARNING(f"Syncing orders from the last {days_to_sync} days."))
        else:
            next_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&limit=250"
            self.stdout.write(self.style.WARNING("Syncing up to 2000 recent orders."))

        headers = {'X-Shopify-Access-Token': access_token}

        def get_next_url(link_header):
            if not link_header:
                return None
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    return link.split(";")[0].strip(" <>")
            return None

        total_synced = 0

        while next_url and total_synced < 2000:
            response = requests.get(next_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            api_orders = data.get('orders', [])

            self.stdout.write(self.style.WARNING(f"Fetched {len(api_orders)} orders from this page."))

            with transaction.atomic():
                line_items_to_create = []
                tracking_to_create = []

                for api_order in api_orders:
                    customer_data = api_order.get('customer') or {}

                    # Calculate previous order count
                    previous_order_count = 0
                    p_email = (customer_data.get('email') or '').strip().lower()
                    shipping_address = api_order.get('shipping_address')
                    p_phone = (shipping_address or {}).get('phone') or customer_data.get('phone')
                    
                    def clean_phone_inline(val):
                        if not val:
                            return None
                        s = str(val).strip("'").strip('"').strip()
                        if not s:
                            return None
                        digits = ''.join(filter(str.isdigit, s))
                        if len(digits) == 10:
                            return f"+91{digits}"
                        elif len(digits) > 10:
                            if s.startswith('+'):
                                return s
                            else:
                                return f"+{digits}"
                        return s
                    
                    p_phone_cleaned = clean_phone_inline(p_phone)
                    
                    q_filter = Q()
                    if p_email:
                        q_filter |= Q(contact_email=p_email)
                    if p_phone_cleaned:
                        q_filter |= Q(contact_phone=p_phone_cleaned)
                        
                    if q_filter:
                        previous_order_count = Order.objects.filter(
                            q_filter,
                            org_id=org_id,
                            created_at__lt=api_order.get('created_at')
                        ).count()

                    # Prepare shipping and billing addresses as text
                    shipping_address = api_order.get('shipping_address')
                    shipping_address_text = None
                    if shipping_address:
                        shipping_address_text = f"{shipping_address.get('first_name','')} {shipping_address.get('last_name','')}, " \
                                                f"{shipping_address.get('address1','')}, {shipping_address.get('address2','')}, " \
                                                f"{shipping_address.get('city','')}, {shipping_address.get('province','')}, " \
                                                f"{shipping_address.get('zip','')}, {shipping_address.get('country','')}, " \
                                                f"Phone: {shipping_address.get('phone','')}"

                    billing_address = api_order.get('billing_address')
                    billing_address_text = None
                    if billing_address:
                        billing_address_text = f"{billing_address.get('first_name','')} {billing_address.get('last_name','')}, " \
                                               f"{billing_address.get('address1','')}, {billing_address.get('address2','')}, " \
                                               f"{billing_address.get('city','')}, {billing_address.get('province','')}, " \
                                               f"{billing_address.get('zip','')}, {billing_address.get('country','')}, " \
                                               f"Phone: {billing_address.get('phone','')}"

                    order_obj, created = Order.objects.get_or_create(
                        shopify_id=api_order['id'],
                        defaults={'org_id': org_id}
                    )

                    # Base fields (always update)
                    order_obj.order_number = api_order.get('order_number')
                    order_obj.created_at = parse_datetime(api_order.get('created_at')) if api_order.get('created_at') else None
                    order_obj.updated_at = parse_datetime(api_order.get('updated_at')) if api_order.get('updated_at') else None
                    order_obj.currency = api_order.get('currency')
                    order_obj.total_price = api_order.get('total_price')
                    order_obj.subtotal_price = api_order.get('subtotal_price')
                    order_obj.total_discounts = api_order.get('total_discounts')
                    order_obj.financial_status = api_order.get('financial_status')
                    order_obj.fulfillment_status = api_order.get('fulfillment_status')
                    order_obj.payment_gateway_names = api_order.get('payment_gateway_names', [])
                    order_obj.discount_codes = api_order.get('discount_codes', [])
                    order_obj.tags = api_order.get('tags', '')
                    order_obj.previous_order_count = previous_order_count
                    order_obj.raw_data = api_order

                    # PII fields (PROTECT FROM REDACTION: Only update if new value is not empty)
                    p_first_name = customer_data.get('first_name')
                    p_last_name = customer_data.get('last_name')
                    p_phone = shipping_address.get('phone') if shipping_address else None
                    p_email = customer_data.get('email')

                    if p_first_name: order_obj.customer_first_name = p_first_name
                    if p_last_name: order_obj.customer_last_name = p_last_name
                    if p_phone: order_obj.contact_phone = p_phone
                    if p_email: order_obj.contact_email = p_email
                    if shipping_address_text: order_obj.shipping_address = shipping_address_text
                    if billing_address_text: order_obj.billing_address = billing_address_text

                    order_obj.save()

                    # ── DELIVERY ANALYTICS SYNC ──────────────────────────────────────
                    # Auto-create/update the Shipment record for this order so that
                    # the Delivery Dashboard always has up-to-date data for ALL months.
                    # Without this, orders only get Shipments when TrackingEvents are saved,
                    # leaving gaps in months where tracking hasn't been fetched yet.
                    try:
                        from core.services.delivery_services import sync_shipment_from_order
                        sync_shipment_from_order(order_obj)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠ Shipment sync failed for Order #{order_obj.order_number}: {e}'
                        ))

                    # Line items
                    order_obj.line_items.all().delete()
                    for item in api_order.get('line_items', []):
                        line_items_to_create.append(
                            LineItem(
                                order=order_obj,
                                product_id=item.get('product_id'),
                                variant_id=item.get('variant_id'),
                                quantity=item.get('quantity'),
                                price=item.get('price'),
                                title=item.get('title'),
                                vendor=item.get('vendor'),
                                sku=item.get('sku'),
                            )
                        )

                    # Fulfillments + tracking
                    for fulfillment_data in api_order.get('fulfillments', []):
                        fid = fulfillment_data.get('id')
                        dups = list(Fulfillment.objects.filter(shopify_id=fid))
                        if len(dups) > 1:
                            fulfillment_obj = dups[0]
                            for d in dups[1:]:
                                d.delete()
                        elif len(dups) == 1:
                            fulfillment_obj = dups[0]
                        else:
                            fulfillment_obj = Fulfillment(shopify_id=fid)

                        fulfillment_obj.order = order_obj
                        fulfillment_obj.status = fulfillment_data.get('status')
                        fulfillment_obj.shipment_status = fulfillment_data.get('shipment_status')
                        fulfillment_obj.created_at = parse_datetime(fulfillment_data.get('created_at')) if fulfillment_data.get('created_at') else None
                        fulfillment_obj.updated_at = parse_datetime(fulfillment_data.get('updated_at')) if fulfillment_data.get('updated_at') else None
                        fulfillment_obj.service = fulfillment_data.get('service')
                        fulfillment_obj.save()


                        fulfillment_obj.tracking_info.all().delete()
                        tracking_numbers = fulfillment_data.get('tracking_numbers', [])
                        tracking_urls = fulfillment_data.get('tracking_urls', [])

                        for i, tracking_number in enumerate(tracking_numbers):
                            tracking_to_create.append(
                                TrackingInfo(
                                    fulfillment=fulfillment_obj,
                                    company=fulfillment_data.get('tracking_company'),
                                    number=tracking_number,
                                    url=tracking_urls[i] if i < len(tracking_urls) else None
                                )
                            )

                # Bulk inserts
                if line_items_to_create:
                    LineItem.objects.bulk_create(line_items_to_create, ignore_conflicts=True)
                if tracking_to_create:
                    TrackingInfo.objects.bulk_create(tracking_to_create, ignore_conflicts=True)

                total_synced += len(api_orders)

            # Move to next page
            next_url = get_next_url(response.headers.get("Link"))

        self.stdout.write(self.style.SUCCESS(f'Shopify data sync complete! Total orders synced/updated: {total_synced}'))
