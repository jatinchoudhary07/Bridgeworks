"""
import_shopify_orders
=====================
Bulk-import historical orders from Shopify CSV exports.

Usage:
    python manage.py import_shopify_orders --dir "D:\\JANKI\\All_Orders\\Exports" --org-id "org-1"

Shopify CSV quirk:  The first row of an order contains customer/order info,
but subsequent rows for the same order (extra line items) leave those
columns blank.  We use pandas forward-fill to fix this.
"""

import os
import re
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Order, LineItem, Customer

logger = logging.getLogger(__name__)

# ── Shopify CSV Column -> Django Model Field mapping ──────────────────────────
# These are the standard Shopify "Orders" export headers.
# Adjust if your export uses slightly different names.
ORDER_FIELD_MAP = {
    'Name':                   '_order_name',           # e.g. "#JANKI39280" – parsed into order_number
    'Email':                  'contact_email',
    'Phone':                  'contact_phone',
    'Financial Status':       'financial_status',
    'Fulfillment Status':     'fulfillment_status',
    'Currency':               'currency',
    'Subtotal':               'subtotal_price',
    'Total':                  'total_price',
    'Discount Amount':        'total_discounts',
    'Discount Code':          '_discount_code',
    'Created at':             'created_at',
    'Tags':                   'tags',
    'Payment Method':         '_payment_method',
    'Shipping Name':          '_shipping_name',
    'Shipping Street':        '_shipping_street',
    'Shipping Address1':      '_shipping_addr1',
    'Shipping Address2':      '_shipping_addr2',
    'Shipping City':          '_shipping_city',
    'Shipping Province':      'shipping_state',
    'Shipping Province Name': '_shipping_province_name',
    'Shipping Zip':           'shipping_pincode',
    'Shipping Country':       '_shipping_country',
    'Shipping Phone':         '_shipping_phone',
    'Billing Name':           '_billing_name',
    'Billing Street':         '_billing_street',
    'Billing Address1':       '_billing_addr1',
    'Billing Address2':       '_billing_addr2',
    'Billing City':           '_billing_city',
    'Billing Province':       '_billing_province',
    'Billing Zip':            '_billing_zip',
    'Billing Country':        '_billing_country',
    'Notes':                  '_notes',
    'Cancelled at':           '_cancelled_at',
    'Id':                     'shopify_id',
}

LINEITEM_FIELD_MAP = {
    'Lineitem name':     'title',
    'Lineitem quantity':  'quantity',
    'Lineitem price':     'price',
    'Lineitem sku':       'sku',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_nan(val):
    """Convert pandas NaN / NaT to None."""
    if pd.isna(val):
        return None
    return val


def _to_decimal(val):
    """Safely convert a value to Decimal."""
    val = _clean_nan(val)
    if val is None:
        return None
    try:
        return Decimal(str(val).replace(',', ''))
    except (InvalidOperation, ValueError):
        return None


def _parse_datetime(val):
    """Parse common Shopify date formats into a timezone-aware datetime."""
    val = _clean_nan(val)
    if val is None:
        return None
    if isinstance(val, pd.Timestamp):
        dt = val.to_pydatetime()
    else:
        for fmt in (
            '%Y-%m-%dT%H:%M:%S%z',      # ISO with tz
            '%Y-%m-%d %H:%M:%S %z',      # space-separated tz
            '%Y-%m-%d %H:%M:%S',          # naive
            '%d-%m-%Y %H:%M',             # DD-MM-YYYY HH:MM
        ):
            try:
                dt = datetime.strptime(str(val).strip(), fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _extract_order_number(name_str):
    """
    Extract the numeric order number from a Shopify 'Name' field.
    e.g.  "#JANKI39280"  ->  39280
          "#1234"         ->  1234
    """
    if not name_str:
        return None
    match = re.search(r'(\d+)', str(name_str))
    return int(match.group(1)) if match else None


def _extract_shopify_id(val):
    """Extract shopify_id from the 'Id' column (it's a large integer)."""
    val = _clean_nan(val)
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _build_full_address(*parts):
    """Join non-empty address fragments with ', '."""
    return ', '.join(str(p).strip() for p in parts if _clean_nan(p) and str(p).strip())


class Command(BaseCommand):
    help = 'Bulk-import historical orders from Shopify CSV exports into BridgeWorks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            type=str,
            required=True,
            help='Path to a folder containing one or more Shopify .csv export files.',
        )
        parser.add_argument(
            '--org-id',
            type=str,
            default='org-1',
            help='Organization ID to assign to all imported orders (default: org-1).',
        )

    def handle(self, *args, **options):
        csv_dir = options['dir']
        org_id = options['org_id'].strip()

        if not os.path.isdir(csv_dir):
            self.stderr.write(self.style.ERROR(f"Directory not found: {csv_dir}"))
            return

        csv_files = sorted([
            f for f in os.listdir(csv_dir)
            if f.lower().endswith('.csv')
        ])

        if not csv_files:
            self.stderr.write(self.style.ERROR(f"No .csv files found in {csv_dir}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Found {len(csv_files)} CSV file(s) in {csv_dir}. Starting import..."
        ))

        total_orders = 0
        total_lineitems = 0
        total_skipped = 0
        total_errors = 0

        for file_idx, filename in enumerate(csv_files, 1):
            filepath = os.path.join(csv_dir, filename)
            self.stdout.write(f"\n[{file_idx}/{len(csv_files)}] Processing: {filename}")

            try:
                orders, items, skipped, errors = self._process_csv(filepath, org_id)
                total_orders += orders
                total_lineitems += items
                total_skipped += skipped
                total_errors += errors
                self.stdout.write(self.style.SUCCESS(
                    f"  -> {orders} orders imported, {items} line items, "
                    f"{skipped} duplicates skipped, {errors} errors"
                ))
            except Exception as e:
                total_errors += 1
                self.stderr.write(self.style.ERROR(
                    f"  -> FATAL error processing {filename}: {e}"
                ))
                logger.exception(f"Error processing CSV {filename}")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Import Complete!"))
        self.stdout.write(f"  Total Orders Imported:  {total_orders}")
        self.stdout.write(f"  Total Line Items:       {total_lineitems}")
        self.stdout.write(f"  Duplicates Skipped:     {total_skipped}")
        self.stdout.write(f"  Errors:                 {total_errors}")
        self.stdout.write("=" * 60)

    def _process_csv(self, filepath, org_id):
        """Read one CSV, forward-fill, group by order Name, and import."""
        df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
        df.replace('', pd.NA, inplace=True)

        # ── Forward-fill the order-level columns ─────────────────────────
        # CRITICAL: Exclude 'Cancelled at' from forward-fill!
        # Otherwise one cancelled order leaks its date into ALL subsequent rows.
        no_fill_cols = {'Cancelled at', 'Notes', 'Refunded Amount'}
        order_cols = [c for c in df.columns if 'Lineitem' not in c and c not in no_fill_cols]
        df[order_cols] = df[order_cols].ffill()

        orders_created = 0
        items_created = 0
        skipped = 0
        errors = 0

        # Group rows by the order Name (e.g. "#JANKI39280")
        grouped = df.groupby('Name', sort=False)

        for order_name, group in grouped:
            try:
                first_row = group.iloc[0]

                shopify_id = _extract_shopify_id(first_row.get('Id'))
                order_number = _extract_order_number(order_name)

                if not shopify_id and not order_number:
                    self.stderr.write(self.style.WARNING(
                        f"  Skipping row with no identifiable order: {order_name}"
                    ))
                    skipped += 1
                    continue

                with transaction.atomic():
                    # ── Build Order fields ────────────────────────────
                    # Construct the full shipping address
                    shipping_addr = _build_full_address(
                        first_row.get('Shipping Name'),
                        first_row.get('Shipping Street') or first_row.get('Shipping Address1'),
                        first_row.get('Shipping Address2'),
                        first_row.get('Shipping City'),
                        first_row.get('Shipping Province Name') or first_row.get('Shipping Province'),
                        first_row.get('Shipping Zip'),
                        first_row.get('Shipping Country'),
                    )

                    billing_addr = _build_full_address(
                        first_row.get('Billing Name'),
                        first_row.get('Billing Street') or first_row.get('Billing Address1'),
                        first_row.get('Billing Address2'),
                        first_row.get('Billing City'),
                        first_row.get('Billing Province'),
                        first_row.get('Billing Zip'),
                        first_row.get('Billing Country'),
                    )

                    # Name splitting
                    shipping_name = _clean_nan(first_row.get('Shipping Name')) or ''
                    name_parts = shipping_name.split(' ', 1)
                    first_name = name_parts[0] if name_parts else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''

                    # Payment / discount as JSON lists
                    payment_method = _clean_nan(first_row.get('Payment Method'))
                    payment_list = [payment_method] if payment_method else []

                    discount_code = _clean_nan(first_row.get('Discount Code'))
                    discount_list = [discount_code] if discount_code else []

                    # Phone number
                    phone = _clean_nan(first_row.get('Phone')) or _clean_nan(first_row.get('Shipping Phone'))

                    # Cancelled?
                    cancelled_at = _parse_datetime(first_row.get('Cancelled at'))
                    order_status = 'Cancelled' if cancelled_at else 'Confirmed'

                    # ── Upsert the Order (idempotent) ────────────────
                    lookup = {}
                    if shopify_id:
                        lookup['shopify_id'] = shopify_id
                    else:
                        lookup['order_number'] = order_number
                        lookup['org_id'] = org_id

                    order, created = Order.objects.update_or_create(
                        **lookup,
                        defaults={
                            'org_id':                org_id,
                            'order_number':          order_number,
                            'created_at':            _parse_datetime(first_row.get('Created at')),
                            'currency':              _clean_nan(first_row.get('Currency')) or 'INR',
                            'total_price':           _to_decimal(first_row.get('Total')),
                            'subtotal_price':        _to_decimal(first_row.get('Subtotal')),
                            'total_discounts':       _to_decimal(first_row.get('Discount Amount')),
                            'financial_status':      _clean_nan(first_row.get('Financial Status')),
                            'fulfillment_status':    _clean_nan(first_row.get('Fulfillment Status')),
                            'contact_email':         _clean_nan(first_row.get('Email')),
                            'contact_phone':         phone,
                            'customer_first_name':   first_name,
                            'customer_last_name':    last_name,
                            'shipping_address':      shipping_addr or None,
                            'shipping_state':        _clean_nan(first_row.get('Shipping Province Name') or first_row.get('Shipping Province')),
                            'shipping_pincode':      _clean_nan(first_row.get('Shipping Zip')),
                            'billing_address':       billing_addr or None,
                            'payment_gateway_names': payment_list,
                            'discount_codes':        discount_list,
                            'tags':                  _clean_nan(first_row.get('Tags')),
                            'status':                order_status,
                        },
                    )

                    if not created:
                        skipped += 1
                        continue

                    # ── Link/Create Customer Profile ─────────────────
                    if phone:
                        customer, _ = Customer.objects.get_or_create(
                            org_id=org_id,
                            phone=phone.strip(),
                            defaults={
                                'name': f"{first_name} {last_name}".strip() or 'Unknown',
                                'email': _clean_nan(first_row.get('Email')),
                                'address': shipping_addr,
                            }
                        )
                        order.customer = customer
                        order.save(update_fields=['customer'])

                    # ── Create Line Items ────────────────────────────
                    for _, row in group.iterrows():
                        title = _clean_nan(row.get('Lineitem name'))
                        if not title:
                            continue

                        LineItem.objects.create(
                            order=order,
                            title=title,
                            name=title,
                            quantity=int(float(row.get('Lineitem quantity', 1) or 1)),
                            price=_to_decimal(row.get('Lineitem price')) or Decimal('0.00'),
                            sku=_clean_nan(row.get('Lineitem sku')),
                        )
                        items_created += 1

                    orders_created += 1

            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(
                    f"  Error importing order {order_name}: {e}"
                ))
                logger.exception(f"Failed to import order {order_name}")

        return orders_created, items_created, skipped, errors
