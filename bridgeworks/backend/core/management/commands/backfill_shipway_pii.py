"""
One-time management command to backfill missing customer PII from Shipway.

Usage:
    python manage.py backfill_shipway_pii              # All orgs, all orders missing phone
    python manage.py backfill_shipway_pii --org janki-jewels   # Specific org only
    python manage.py backfill_shipway_pii --dry-run    # Preview without saving
    python manage.py backfill_shipway_pii --delay 1.0  # Slower rate (1s between calls)
"""

import time
import base64
import requests
from django.core.management.base import BaseCommand
from core.models import Order
from core.utils import _get_decrypted_credentials


class Command(BaseCommand):
    help = 'Backfill missing customer PII (name, phone, address) from Shipway API for existing orders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org', type=str, default=None,
            help='Only process orders for this specific org_id (e.g. "janki-jewels")'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview what would be updated without saving to DB'
        )
        parser.add_argument(
            '--delay', type=float, default=0.5,
            help='Delay in seconds between API calls (default: 0.5s to avoid rate limiting)'
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Max number of orders to process (useful for testing)'
        )
        parser.add_argument(
            '--refill', action='store_true',
            help='Re-fetch orders that have phone but are missing state/pincode (for orders backfilled before these fields existed)'
        )

    def handle(self, *args, **options):
        org_filter = options['org']
        dry_run = options['dry_run']
        delay = options['delay']
        limit = options['limit']
        refill = options['refill']

        # --- 1. FIND ORDERS MISSING PII ---
        if refill:
            # Target orders that already have phone but are missing state or pincode
            from django.db.models import Q
            queryset = Order.objects.exclude(
                contact_phone__isnull=True
            ).exclude(
                contact_phone=''
            ).filter(
                Q(shipping_state__isnull=True) | Q(shipping_state='') |
                Q(shipping_pincode__isnull=True) | Q(shipping_pincode='')
            )
            self.stdout.write(self.style.WARNING('REFILL MODE: Targeting orders with phone but missing state/pincode'))
        else:
            # Default: target orders missing phone entirely
            queryset = Order.objects.filter(
                contact_phone__isnull=True
            ) | Order.objects.filter(contact_phone='')

        if org_filter:
            queryset = queryset.filter(org_id=org_filter)

        # CHANGED: Sort by descending order_number to fetch the most recent orders first.
        # Note: If your model has a creation date, you can also use '-created_at'
        queryset = queryset.order_by('-order_number')

        if limit:
            queryset = queryset[:limit]

        orders = list(queryset)
        total = len(orders)

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No orders with missing PII found. Nothing to do!'))
            return

        self.stdout.write(self.style.WARNING(
            f'\n{"=" * 60}\n'
            f'  BACKFILL SHIPWAY PII\n'
            f'  Orders to process: {total}\n'
            f'  Delay between calls: {delay}s\n'
            f'  Dry run: {"YES" if dry_run else "NO"}\n'
            f'{"=" * 60}\n'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE — No changes will be saved.\n'))

        # --- 2. GROUP BY ORG AND FETCH CREDENTIALS ---
        creds_cache = {}
        updated_count = 0
        skipped_count = 0
        not_found_count = 0
        error_count = 0

        for i, order in enumerate(orders, 1):
            org_id = order.org_id

            # Cache credentials per org
            if org_id not in creds_cache:
                creds = _get_decrypted_credentials(org_id)
                if not creds:
                    self.stdout.write(self.style.ERROR(
                        f'  [{i}/{total}] ✗ No credentials for org "{org_id}". Skipping all its orders.'
                    ))
                    creds_cache[org_id] = None
                else:
                    email = creds.get('shipway_email', '')
                    license_key = creds.get('shipway_license_key', '')
                    prefix = creds.get('order_prefix', '')

                    if not email or not license_key:
                        self.stdout.write(self.style.ERROR(
                            f'  [{i}/{total}] ✗ Shipway credentials missing for org "{org_id}". Skipping.'
                        ))
                        creds_cache[org_id] = None
                    else:
                        encoded = base64.b64encode(f"{email}:{license_key}".encode()).decode()
                        creds_cache[org_id] = {
                            'headers': {'Authorization': f'Basic {encoded}'},
                            'prefix': prefix,
                        }

            org_creds = creds_cache.get(org_id)
            if not org_creds:
                skipped_count += 1
                continue

            # --- 3. CALL SHIPWAY API ---
            full_order_id = f"{org_creds['prefix']}{order.order_number}" if org_creds['prefix'] else str(order.order_number)

            try:
                resp = requests.get(
                    'https://app.shipway.com/api/getorders',
                    params={'orderid': full_order_id},
                    headers=org_creds['headers'],
                    timeout=15
                )

                if not resp.ok:
                    self.stdout.write(self.style.WARNING(
                        f'  [{i}/{total}] ⚠ HTTP {resp.status_code} for #{order.order_number}. Skipping.'
                    ))
                    error_count += 1
                    time.sleep(delay)
                    continue

                data = resp.json()
                success = data.get('success')
                messages = data.get('message', [])

                if not success or not isinstance(messages, list) or len(messages) == 0:
                    self.stdout.write(
                        f'  [{i}/{total}] — #{order.order_number} not found in Shipway yet.'
                    )
                    not_found_count += 1
                    time.sleep(delay)
                    continue

                # --- 4. MAP PII ---
                sw = messages[0]

                first_name = (sw.get('s_firstname') or sw.get('b_firstname') or '').strip()
                last_name = (sw.get('s_lastname') or sw.get('b_lastname') or '').strip()
                phone = (sw.get('s_phone') or sw.get('b_phone') or '').strip()
                email_addr = (sw.get('email') or '').strip()

                addr_parts = [
                    f"{first_name} {last_name}".strip(),
                    sw.get('s_address', ''),
                    sw.get('s_address_2', ''),
                    sw.get('s_city', ''),
                    sw.get('s_state', ''),
                    sw.get('s_zipcode', ''),
                    sw.get('s_country', ''),
                ]
                address = ', '.join(part for part in addr_parts if part and part.strip())

                # --- 5. SAVE ---
                update_fields = []

                if first_name:
                    order.customer_first_name = first_name
                    update_fields.append('customer_first_name')
                if last_name:
                    order.customer_last_name = last_name
                    update_fields.append('customer_last_name')
                if phone:
                    order.contact_phone = phone
                    update_fields.append('contact_phone')
                if email_addr and not order.contact_email:
                    order.contact_email = email_addr
                    update_fields.append('contact_email')
                if address:
                    order.shipping_address = address
                    update_fields.append('shipping_address')

                # Save state and pincode separately
                state = (sw.get('s_state') or sw.get('b_state') or '').strip()
                pincode = (sw.get('s_zipcode') or sw.get('b_zipcode') or '').strip()
                if state:
                    order.shipping_state = state
                    update_fields.append('shipping_state')
                if pincode:
                    order.shipping_pincode = pincode
                    update_fields.append('shipping_pincode')

                if update_fields:
                    if not dry_run:
                        order.save(update_fields=update_fields)

                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  [{i}/{total}] ✓ #{order.order_number} → {first_name} {last_name}, {phone} ({len(update_fields)} fields)'
                    ))
                else:
                    skipped_count += 1
                    self.stdout.write(
                        f'  [{i}/{total}] — #{order.order_number} has no PII in Shipway either.'
                    )

            except requests.exceptions.Timeout:
                self.stdout.write(self.style.WARNING(
                    f'  [{i}/{total}] ⚠ Timeout for #{order.order_number}. Skipping.'
                ))
                error_count += 1
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(
                    f'  [{i}/{total}] ✗ Network error for #{order.order_number}: {e}. Skipping.'
                ))
                error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  [{i}/{total}] ✗ Unexpected error for #{order.order_number}: {e}. Skipping.'
                ))
                error_count += 1

            # --- RATE LIMIT ---
            time.sleep(delay)

        # --- 6. SUMMARY ---
        self.stdout.write(self.style.WARNING(
            f'\n{"=" * 60}\n'
            f'  BACKFILL COMPLETE {"(DRY RUN)" if dry_run else ""}\n'
            f'  ✓ Updated:    {updated_count}\n'
            f'  — Skipped:    {skipped_count}\n'
            f'  — Not Found:  {not_found_count}\n'
            f'  ✗ Errors:     {error_count}\n'
            f'  Total:        {total}\n'
            f'{"=" * 60}\n'
        ))
