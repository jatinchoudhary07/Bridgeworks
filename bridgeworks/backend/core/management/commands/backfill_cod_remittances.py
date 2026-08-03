"""
backfill_cod_remittances.py
===========================
Two-phase backfill:
  Phase 1: Ensure all fulfilled orders have a Shipment record
  Phase 2: Ensure all delivered COD/Partial shipments have a CODRemittance record

Usage:
    python manage.py backfill_cod_remittances
    python manage.py backfill_cod_remittances --org-id janki-jewels
    python manage.py backfill_cod_remittances --skip-shipments   # Only do phase 2
"""

import time
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from core.models import Order, Fulfillment
from core.models.delivery import Shipment, CODRemittance
from core.services.delivery_services import (
    sync_shipment_from_order,
    sync_cod_remittance_from_shipment,
)


class Command(BaseCommand):
    help = "Backfills Shipment + CODRemittance records for all delivered COD orders."

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id', type=str, default=None,
            help='Only process for a specific organization ID.',
        )
        parser.add_argument(
            '--skip-shipments', action='store_true',
            help='Skip Phase 1 (Shipment creation) and only do COD remittance backfill.',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print every error instead of just counts.',
        )

    def handle(self, *args, **options):
        org_id = options['org_id']
        skip_shipments = options['skip_shipments']
        verbose = options['verbose']

        # ============================================================
        # PHASE 1: Backfill missing Shipment records
        # ============================================================
        if not skip_shipments:
            self.stdout.write(self.style.NOTICE(
                "\n[PHASE 1] Backfilling missing Shipment records..."
            ))

            # Orders that have fulfillments with tracking but no Shipment
            has_tracking = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                tracking_info__isnull=False,
            ).exclude(tracking_info__number='')

            orders_qs = Order.objects.filter(
                Exists(has_tracking),
                shipment__isnull=True,
            ).prefetch_related(
                'fulfillments__tracking_info',
                'fulfillments__tracking_events',
            )

            if org_id:
                orders_qs = orders_qs.filter(org_id=org_id)

            total_orders = orders_qs.count()
            self.stdout.write(f"  Found {total_orders} orders without Shipment records")

            if total_orders > 0:
                created = 0
                errors = 0
                error_samples = []
                start = time.time()

                for i, order in enumerate(orders_qs.iterator(chunk_size=200), 1):
                    try:
                        shipment = sync_shipment_from_order(order)
                        if shipment:
                            created += 1
                    except Exception as e:
                        errors += 1
                        msg = f"    [ERR] Order #{order.order_number}: {type(e).__name__}: {e}"
                        if verbose:
                            self.stderr.write(msg)
                        elif len(error_samples) < 10:
                            error_samples.append(msg)

                    if i % 200 == 0 or i == total_orders:
                        elapsed = time.time() - start
                        rate = i / elapsed if elapsed > 0 else 0
                        self.stdout.write(
                            f"  [{i}/{total_orders}] "
                            f"Created={created}  Errors={errors}  "
                            f"({rate:.0f}/sec)"
                        )

                if error_samples and not verbose:
                    self.stderr.write("  First errors (use --verbose for all):")
                    for msg in error_samples:
                        self.stderr.write(msg)

                self.stdout.write(self.style.SUCCESS(
                    f"  Phase 1 done: {created} Shipments created, {errors} errors"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "  All orders already have Shipments"
                ))

            self.stdout.write(self.style.NOTICE(
                "\n[PHASE 1.5] Re-evaluating payment_types for PrePaid shipments..."
            ))
            from core.services.delivery_services import derive_payment_type
            
            prepaid_qs = Shipment.objects.filter(payment_type='PrePaid').select_related('order')
            if org_id:
                prepaid_qs = prepaid_qs.filter(org_id=org_id)
                
            total_prepaid = prepaid_qs.count()
            self.stdout.write(f"  Found {total_prepaid} PrePaid shipments to re-evaluate")
            fixed_count = 0
            
            for i, shipment in enumerate(prepaid_qs.iterator(chunk_size=500), 1):
                if shipment.order:
                    correct_type = derive_payment_type(shipment.order)
                    if correct_type != 'PrePaid':
                        shipment.payment_type = correct_type
                        shipment.save(update_fields=['payment_type'])
                        fixed_count += 1
                        
            self.stdout.write(self.style.SUCCESS(
                f"  Phase 1.5 done: Fixed {fixed_count} shipments from PrePaid to their correct COD/Partially Paid type"
            ))


        # ============================================================
        # PHASE 2: Backfill CODRemittance for delivered COD shipments
        # ============================================================
        self.stdout.write(self.style.NOTICE(
            "\n[PHASE 2] Backfilling CODRemittance records..."
        ))

        cod_qs = Shipment.objects.filter(
            current_stage='Delivered',
            payment_type__in=['COD', 'Partially Paid'],
        ).select_related('order').order_by('-delivery_date')

        if org_id:
            cod_qs = cod_qs.filter(org_id=org_id)

        total_cod = cod_qs.count()
        self.stdout.write(f"  Found {total_cod} delivered COD/Partially Paid shipments")

        if total_cod == 0:
            self.stdout.write(self.style.SUCCESS("  No COD shipments to process"))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = 0
        start = time.time()

        for i, shipment in enumerate(cod_qs.iterator(chunk_size=200), 1):
            try:
                already_exists = CODRemittance.objects.filter(
                    shipment=shipment
                ).exists()
                remittance = sync_cod_remittance_from_shipment(shipment)

                if remittance is None:
                    # No date available at all
                    skipped += 1
                    if verbose:
                        self.stderr.write(
                            f"    [SKIP] {shipment.awb_number}: "
                            f"no delivery/dispatch/order date"
                        )
                elif not already_exists:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1
                if verbose:
                    self.stderr.write(
                        f"    [ERR] {shipment.awb_number}: {e}"
                    )

            if i % 200 == 0 or i == total_cod:
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  [{i}/{total_cod}] "
                    f"Created={created}  Updated={updated}  "
                    f"Skipped={skipped}  Errors={errors}  "
                    f"({rate:.0f}/sec)"
                )

        elapsed = time.time() - start

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Backfill Complete!"))
        self.stdout.write(f"  Delivered COD Shipments: {total_cod}")
        self.stdout.write(f"  New Remittances:        {created}")
        self.stdout.write(f"  Existing Updated:       {updated}")
        self.stdout.write(f"  Skipped (no date):      {skipped}")
        self.stdout.write(f"  Errors:                 {errors}")
        self.stdout.write(f"  Time:                   {elapsed:.1f}s")
        self.stdout.write("=" * 60)
