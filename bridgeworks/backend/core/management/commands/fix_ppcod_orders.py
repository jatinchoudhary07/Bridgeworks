"""
fix_ppcod_orders.py — Fix Partial COD orders misclassified as Prepaid
=====================================================================
This management command identifies orders where:
  1. payment_gateway_names contains "Razorpay" (but NOT "Razorpay PPCOD")
  2. tags contain "Partial Payment"
  3. The order is currently classified as Prepaid

It then:
  a. Updates payment_gateway_names from ["Razorpay"] to ["Razorpay PPCOD"]
  b. Updates linked Shipment.payment_type to "Partially Paid"
  c. Generates COD Remittance records for delivered shipments

Usage:
  python manage.py fix_ppcod_orders              # Dry-run (shows what would change)
  python manage.py fix_ppcod_orders --apply       # Actually applies changes
"""

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q
from decimal import Decimal

from core.models import Order, ShopCredentials
from core.models.delivery import Shipment, CODRemittance
from core.utils import _get_decrypted_credentials
from core.services.delivery_services import (
    derive_payment_type,
    sync_cod_remittance_from_shipment,
)


def get_prepaid_amount_from_shopify(order):
    """
    Fetch transactions for the order and find the prepaid amount (usually 'sale' kind).
    """
    try:
        shop = ShopCredentials.objects.first()
        if not shop: return Decimal('0')
        
        creds = _get_decrypted_credentials(shop.organization_id)
        if not creds: return Decimal('0')
        
        shop_url = creds['shop_url'].rstrip('/')
        api_key = creds['api_key']
        password = creds['password']
        api_version = creds['api_version']
        
        url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders/{order.shopify_id}/transactions.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            txns = resp.json().get('transactions', [])
            # For PPCOD, 'sale' is the prepaid part, 'capture' is the COD part (marked later)
            # We want the 'sale' amount.
            for t in txns:
                if t.get('kind') == 'sale' and t.get('status') == 'success' and 'razorpay' in t.get('gateway', '').lower():
                    return Decimal(str(t.get('amount', '0')))
        return Decimal('0')
    except Exception:
        return Decimal('0')


class Command(BaseCommand):
    help = "Fix Partial COD orders: update payment_gateway_names, Shipment payment_type, and generate COD Remittances."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Actually apply the changes. Without this flag, runs in dry-run mode.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(self.style.NOTICE(f"\n{'='*60}"))
        self.stdout.write(self.style.NOTICE(f"  Fix PPCOD Orders - Mode: {mode}"))
        self.stdout.write(self.style.NOTICE(f"{'='*60}\n"))

        # ──────────────────────────────────────────────────────────
        # PHASE 1: Find affected orders
        # Orders with Razorpay in payment_gateway_names AND
        # "Partial Payment" in tags
        # ──────────────────────────────────────────────────────────
        affected_orders = Order.objects.filter(
            Q(payment_gateway_names__icontains='Razorpay') | Q(payment_gateway_names__icontains='Razorpay PPCOD'),
            Q(tags__icontains='Partial Payment'),
        )

        total = affected_orders.count()
        self.stdout.write(f"[Phase 1] Found {total} orders with Razorpay + 'Partial Payment' tag")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("\nNo orders need fixing. All done!"))
            return

        # Show sample
        self.stdout.write(f"\n  Sample orders:")
        for o in affected_orders[:10]:
            self.stdout.write(
                f"    Order #{o.order_number} | "
                f"financial_status={o.financial_status} | "
                f"gateways={o.payment_gateway_names} | "
                f"tags={o.tags}"
            )
        if total > 10:
            self.stdout.write(f"    ... and {total - 10} more")

        # ──────────────────────────────────────────────────────────
        # PHASE 2: Update payment_gateway_names
        # Replace "Razorpay" with "Razorpay PPCOD" in the list
        # ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(
            f"\n[Phase 2] Updating payment_gateway_names: 'Razorpay' -> 'Razorpay PPCOD'"
        ))

        gateway_updated = 0
        order_ids = list(affected_orders.values_list('id', flat=True))

        for oid in order_ids:
            order = Order.objects.get(id=oid)
            gateways = order.payment_gateway_names or []

            # Handle both list and string formats
            if isinstance(gateways, list):
                new_gateways = []
                changed = False
                for gw in gateways:
                    if isinstance(gw, str) and gw.strip().lower() == 'razorpay':
                        new_gateways.append('Razorpay PPCOD')
                        changed = True
                    else:
                        new_gateways.append(gw)
                
                if changed:
                    if apply:
                        order.payment_gateway_names = new_gateways
                        order.save(update_fields=['payment_gateway_names'])
                    gateway_updated += 1
                    self.stdout.write(
                        f"  Order #{order.order_number}: {gateways} -> {new_gateways}"
                    )
            elif isinstance(gateways, str):
                # String format (unlikely but handle it)
                if 'razorpay' in gateways.lower() and 'ppcod' not in gateways.lower():
                    new_val = gateways.replace('Razorpay', 'Razorpay PPCOD').replace('razorpay', 'Razorpay PPCOD')
                    if apply:
                        order.payment_gateway_names = new_val
                        order.save(update_fields=['payment_gateway_names'])
                    gateway_updated += 1
                    self.stdout.write(
                        f"  Order #{order.order_number}: '{gateways}' -> '{new_val}'"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"  -> {gateway_updated} orders {'updated' if apply else 'would be updated'}"
        ))

        # ──────────────────────────────────────────────────────────
        # PHASE 3: Fix Shipment payment_type
        # ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(
            f"\n[Phase 3] Fixing Shipment.payment_type for affected orders"
        ))

        shipment_updated = 0
        shipments = Shipment.objects.filter(
            order_id__in=order_ids,
            payment_type='PrePaid',
        )

        for s in shipments:
            self.stdout.write(
                f"  AWB {s.awb_number} (Order #{s.order.order_number}): "
                f"payment_type '{s.payment_type}' -> 'Partially Paid'"
            )
            if apply:
                s.payment_type = 'Partially Paid'
                s.save(update_fields=['payment_type'])
            shipment_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"  -> {shipment_updated} shipments {'updated' if apply else 'would be updated'}"
        ))

        # ──────────────────────────────────────────────────────────
        # PHASE 4: Generate/Fix COD Remittance records
        # ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(
            f"\n[Phase 4] Generating/Fixing COD Remittance records for delivered PPCOD shipments"
        ))

        remittance_created = 0
        remittance_fixed = 0
        delivered_shipments = Shipment.objects.filter(
            order_id__in=order_ids,
            current_stage='Delivered',
        )

        for s in delivered_shipments:
            # Calculate the correct COD amount
            # 1. Try total_outstanding from raw_data
            order_total = Decimal(str(s.order.total_price or '0'))
            cod_amount = Decimal('0')
            
            outstanding = s.order.raw_data.get('total_outstanding')
            if outstanding and float(outstanding) > 0:
                cod_amount = Decimal(str(outstanding))
            else:
                # 2. Fetch from Shopify API
                prepaid = get_prepaid_amount_from_shopify(s.order)
                if prepaid > 0:
                    cod_amount = order_total - prepaid
                else:
                    # Fallback to total if we can't find prepaid (safety)
                    cod_amount = order_total

            remittance = CODRemittance.objects.filter(shipment=s).first()
            
            if not remittance:
                self.stdout.write(
                    f"  AWB {s.awb_number} (Order #{s.order.order_number}): "
                    f"Creating COD Remittance (Expected COD: {cod_amount})"
                )
                if apply:
                    # Ensure payment_type is correct
                    if s.payment_type not in ['COD', 'Partially Paid']:
                        s.payment_type = 'Partially Paid'
                        s.save(update_fields=['payment_type'])
                    
                    # Create manually to ensure correct amount
                    import datetime
                    from core.services.delivery_services import calculate_expected_remittance_date
                    ref_date = s.delivery_date or s.dispatch_date or s.order.created_at
                    CODRemittance.objects.create(
                        shipment=s,
                        expected_amount=cod_amount,
                        expected_remittance_date=calculate_expected_remittance_date(ref_date),
                        status='Pending'
                    )
                remittance_created += 1
            else:
                # Fix existing remittance amount
                if remittance.expected_amount != cod_amount:
                    self.stdout.write(
                        f"  AWB {s.awb_number} (Order #{s.order.order_number}): "
                        f"Fixing Amount {remittance.expected_amount} -> {cod_amount}"
                    )
                    if apply:
                        remittance.expected_amount = cod_amount
                        remittance.save(update_fields=['expected_amount'])
                    remittance_fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"  -> {remittance_created} remittance records {'created' if apply else 'would be created'}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  -> {remittance_fixed} remittance records {'fixed' if apply else 'would be fixed'}"
        ))

        # ──────────────────────────────────────────────────────────
        # SUMMARY
        # ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(f"\n{'='*60}"))
        self.stdout.write(self.style.NOTICE(f"  SUMMARY ({mode})"))
        self.stdout.write(self.style.NOTICE(f"{'='*60}"))
        self.stdout.write(f"  Affected Orders:       {total}")
        self.stdout.write(f"  Gateways Updated:      {gateway_updated}")
        self.stdout.write(f"  Shipments Fixed:       {shipment_updated}")
        self.stdout.write(f"  Remittances Created:   {remittance_created}")
        self.stdout.write(f"  Remittances Adjusted:  {remittance_fixed}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                f"\n  WARNING: This was a DRY-RUN. No changes were made."
                f"\n     Run with --apply to execute changes."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n  All changes applied successfully!"))
