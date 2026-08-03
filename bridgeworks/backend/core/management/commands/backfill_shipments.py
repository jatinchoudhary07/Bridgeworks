"""
backfill_shipments.py
=====================
Management command to backfill Shipment records from existing Order + Fulfillment data.

Usage:
    python manage.py backfill_shipments
    python manage.py backfill_shipments --org-id org-123
    python manage.py backfill_shipments --batch-size 500
    python manage.py backfill_shipments --since 2026-05-01 --force   ← fix May data
"""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils.dateparse import parse_date

from core.models import Order, Fulfillment, TrackingInfo
from core.services.delivery_services import sync_shipment_from_order


class Command(BaseCommand):
    help = 'Backfill Shipment records from existing Order/Fulfillment/TrackingInfo data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=str,
            default=None,
            help='Filter by organization ID (optional)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Number of orders to process per batch (default: 200)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-sync even if Shipment already exists'
        )
        parser.add_argument(
            '--since',
            type=str,
            default=None,
            help='Only process orders created on or after this date (YYYY-MM-DD). Example: --since 2026-05-01'
        )

    def handle(self, *args, **options):
        org_id = options['org_id']
        batch_size = options['batch_size']
        force = options['force']
        since_str = options.get('since')

        self.stdout.write(self.style.NOTICE('[START] Starting Shipment backfill...'))

        # Find orders that have fulfillments with tracking info
        has_tracking = Fulfillment.objects.filter(
            order=OuterRef('pk'),
            tracking_info__isnull=False,
        ).exclude(tracking_info__number='')

        orders = Order.objects.filter(
            Exists(has_tracking)
        ).select_related('customer').order_by('id')

        if org_id:
            orders = orders.filter(org_id=org_id)
            self.stdout.write(f'  Filtering to org: {org_id}')

        if since_str:
            since_date = parse_date(since_str)
            if since_date:
                # OPTIMIZATION: Use created_at__gte instead of created_at__date__gte
                # __date causes a full table scan by bypassing the DB index
                orders = orders.filter(created_at__gte=since_date)
                self.stdout.write(self.style.WARNING(f'  Only processing orders created since {since_date}'))
            else:
                self.stdout.write(self.style.ERROR(f'  Invalid --since date: {since_str}. Use YYYY-MM-DD format.'))
                return

        if not force:
            # Only process orders without existing Shipment
            orders = orders.filter(shipment__isnull=True)
            self.stdout.write('  Skipping orders with existing Shipment (use --force to re-sync)')

        total = orders.count()
        self.stdout.write(f'  Found {total} orders to process')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ No orders to backfill. All done!'))
            return

        created = 0
        errors = 0
        processed = 0

        from django.db import close_old_connections

        # Process in batches to avoid memory issues
        for i in range(0, total, batch_size):
            close_old_connections()
            batch = orders[i:i + batch_size]
            for order in batch:
                try:
                    shipment = sync_shipment_from_order(order)
                    if shipment:
                        created += 1
                    processed += 1
                except Exception as e:
                    errors += 1
                    self.stderr.write(
                        self.style.WARNING(
                            f'  ⚠ Error processing Order #{order.order_number}: {e}'
                        )
                    )

            self.stdout.write(
                f'  Progress: {min(i + batch_size, total)}/{total} '
                f'(Synced: {created}, Errors: {errors})'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n[OK] Backfill complete!\n'
                f'   Processed: {processed}\n'
                f'   Synced:    {created}\n'
                f'   Errors:    {errors}'
            )
        )
