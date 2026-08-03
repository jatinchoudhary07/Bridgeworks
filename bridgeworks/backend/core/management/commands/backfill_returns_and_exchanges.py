import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Order
from core.models.delivery import CourierInvoiceLine, Shipment, FreightInvoice
from core.services.discrepancy_engine import analyse_line, EXPECTED_SLAB_KG

class Command(BaseCommand):
    help = 'Backfill return/exchange AWBs to orders and re-analyse invoice lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=str,
            required=False,
            help='Filter by Organization ID'
        )
        parser.add_argument(
            '--invoice-number',
            type=str,
            required=False,
            help='Filter by specific FreightInvoice number'
        )

    def handle(self, *args, **options):
        org_id = options.get('org_id')
        invoice_number = options.get('invoice_number')

        self.stdout.write("Starting backfill for returns & exchanges...")

        # 1. Fetch relevant lines
        lines_qs = CourierInvoiceLine.objects.all()
        if org_id:
            lines_qs = lines_qs.filter(org_id=org_id)
        if invoice_number:
            lines_qs = lines_qs.filter(freight_invoice__invoice_number=invoice_number)

        self.stdout.write(f"Scanning {lines_qs.count()} invoice lines...")

        reclassified_count = 0
        order_linked_count = 0
        shipment_linked_count = 0
        recalculated_count = 0

        # We pre-fetch rate cards and slabs to optimize analyse_line inside loops
        from core.models.delivery import CourierRateCard, RateSlab
        rate_cards_cache = {}
        slabs_cache = {}

        def get_rate_card_and_slabs(l_org_id):
            if l_org_id not in rate_cards_cache:
                rc = CourierRateCard.objects.filter(
                    org_id=l_org_id, 
                    courier_partner__icontains='Bluedart', 
                    is_active=True
                ).first()
                rate_cards_cache[l_org_id] = rc
                slabs_cache[l_org_id] = list(RateSlab.objects.filter(rate_card=rc)) if rc else []
            return rate_cards_cache[l_org_id], slabs_cache[l_org_id]

        for line in lines_qs:
            awb = line.awb_number
            awb_upper = awb.upper()
            ref_upper = (line.courier_ref or '').upper()

            is_customer_return = 'RET' in ref_upper
            is_exchange = 'EXC' in ref_upper
            is_rto = not is_customer_return and not is_exchange and (
                awb_upper.endswith('R') or awb_upper.startswith('R') or ref_upper.endswith('R') or ref_upper.startswith('R')
            )

            # Try to link shipment first so we can check order status
            shipment_changed = False
            shipment = line.shipment
            if not shipment:
                # Strip prefix/suffix R to search forward AWB
                clean_awb = awb
                if clean_awb.upper().endswith('R'):
                    clean_awb = clean_awb[:-1]
                elif clean_awb.upper().startswith('R'):
                    clean_awb = clean_awb[1:]
                
                # Try finding matching shipment
                shipment = Shipment.objects.filter(org_id=line.org_id, awb_number=clean_awb).first()
                if not shipment and line.courier_ref:
                    # Try reference extraction
                    cleaned_ref = re.sub(r'(RET|EXC)\d+$', '', line.courier_ref).strip()
                    digits = re.sub(r'\D', '', cleaned_ref)
                    if digits:
                        shipment = Shipment.objects.filter(org_id=line.org_id, order__order_number=int(digits)).first()

                if shipment:
                    self.stdout.write(f"AWB {awb}: Linking to forward shipment (AWB {shipment.awb_number})")
                    line.shipment = shipment
                    line.save(update_fields=['shipment'])
                    shipment_linked_count += 1
                    shipment_changed = True

            # Refined target type: determine RTO vs Return vs Exchange
            from core.models.constants import RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
            combined_rto_statuses = RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES

            target_type = None
            if is_customer_return:
                target_type = 'Return'
            elif is_exchange:
                target_type = 'Exchange'
            elif is_rto:
                target_type = 'RTO'
            elif shipment and shipment.order and shipment.order.current_status in combined_rto_statuses:
                target_type = 'RTO'
            elif line.shipment_type == 'Return' and not is_customer_return and not is_exchange:
                # Fallback: if it was originally 'Return' but has no RET prefix/suffix and no EXCHANGE, it's RTO
                target_type = 'RTO'

            # Update shipment_type in database if not set correctly
            type_changed = False
            if target_type and line.shipment_type != target_type:
                self.stdout.write(f"AWB {awb}: Re-classifying shipment_type from '{line.shipment_type}' to '{target_type}'")
                line.shipment_type = target_type
                line.save(update_fields=['shipment_type'])
                reclassified_count += 1
                type_changed = True

            # If shipment is linked, update return/exchange fields on the associated Order (only for customer Return/Exchange)
            if shipment and shipment.order:
                order = shipment.order
                order_changed = False

                if target_type == 'Return':
                    if order.return_awb != awb:
                        order.return_awb = awb
                        order.return_shipping_company = line.freight_invoice.courier_partner
                        order_changed = True
                elif target_type == 'Exchange':
                    if order.exchange_awb != awb:
                        order.exchange_awb = awb
                        order.exchange_shipping_company = line.freight_invoice.courier_partner
                        order_changed = True
                elif target_type == 'RTO':
                    # Clean up return_awb if it was incorrectly set to RTO AWB
                    if order.return_awb == awb:
                        order.return_awb = ''
                        order.return_shipping_company = ''
                        order_changed = True

                if order_changed:
                    order.save(update_fields=['return_awb', 'return_shipping_company', 'exchange_awb', 'exchange_shipping_company'])
                    if target_type == 'RTO':
                        self.stdout.write(f"AWB {awb}: Cleaned return details from standard RTO Order {order.order_number}")
                    else:
                        self.stdout.write(f"AWB {awb}: Backfilled return/exchange details to Order {order.order_number}")
                    order_linked_count += 1

            # Recalculate discrepancy analysis if re-classified, shipment linked, or if return leg needs COD charge fix
            if type_changed or shipment_changed or line.shipment_type in ('RTO', 'Return', 'Exchange'):
                rc, slabs = get_rate_card_and_slabs(line.org_id)
                analyse_line(line, line.org_id, rate_card=rc, slabs=slabs)
                line.save(update_fields=[
                    'expected_weight_kg', 'expected_freight', 'expected_total',
                    'expected_tax_cgst', 'expected_tax_sgst', 'expected_total_with_tax',
                    'tax_cgst', 'tax_sgst', 'total_billed_with_tax',
                    'overcharge_amount', 'discrepancy_type', 'discrepancy_notes',
                ])
                recalculated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Backfill Completed!\n"
            f"  Re-classified lines: {reclassified_count}\n"
            f"  Linked shipments:    {shipment_linked_count}\n"
            f"  Linked orders:       {order_linked_count}\n"
            f"  Recalculated lines:  {recalculated_count}"
        ))
