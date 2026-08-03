from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Order, ReturnRequest

class Command(BaseCommand):
    help = 'Backfill return_awb and exchange_awb on Orders using ReturnRequest tracking numbers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the script without committing changes'
        )
        parser.add_argument(
            '--org-id',
            type=str,
            required=False,
            help='Filter by specific Organization ID'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        org_id = options.get('org_id')

        self.stdout.write("Starting backfill of return and exchange AWBs...")

        # Fetch return requests with a non-empty awb_number
        requests_qs = ReturnRequest.objects.exclude(awb_number='').exclude(awb_number__isnull=True)
        if org_id:
            requests_qs = requests_qs.filter(order__org_id=org_id)

        total_requests = requests_qs.count()
        self.stdout.write(f"Found {total_requests} ReturnRequests with tracking numbers.")

        updated_returns = 0
        updated_exchanges = 0
        skipped = 0

        # We'll run this inside a transaction unless it's dry-run, but dry-run will rollback
        with transaction.atomic():
            for req in requests_qs:
                order = req.order
                awb = req.awb_number.strip()
                req_type = req.request_type

                order_changed = False

                if req_type == 'RETURN':
                    if order.return_awb != awb:
                        self.stdout.write(f"Order #{order.order_number} ({order.org_id}): updating return_awb '{order.return_awb}' -> '{awb}'")
                        if not dry_run:
                            order.return_awb = awb
                        order_changed = True
                        updated_returns += 1
                elif req_type == 'EXCHANGE':
                    if order.exchange_awb != awb:
                        self.stdout.write(f"Order #{order.order_number} ({order.org_id}): updating exchange_awb '{order.exchange_awb}' -> '{awb}'")
                        if not dry_run:
                            order.exchange_awb = awb
                        order_changed = True
                        updated_exchanges += 1

                if order_changed:
                    if not dry_run:
                        # Extract shipping company if available in raw_data/shipping/etc.
                        shipping_company = ''
                        if req.raw_data and isinstance(req.raw_data, dict):
                            line_items = req.raw_data.get('line_items', [])
                            if line_items and isinstance(line_items, list):
                                shipping_data = line_items[0].get('shipping', [])
                                if shipping_data and isinstance(shipping_data, list):
                                    shipping_company = shipping_data[0].get('shipping_company', '')
                        
                        if req_type == 'RETURN':
                            if shipping_company:
                                order.return_shipping_company = shipping_company
                            order.save(update_fields=['return_awb', 'return_shipping_company'])
                        elif req_type == 'EXCHANGE':
                            if shipping_company:
                                order.exchange_shipping_company = shipping_company
                            order.save(update_fields=['exchange_awb', 'exchange_shipping_company'])
                else:
                    skipped += 1

            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN: Rolling back transaction. No changes saved."))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Backfill complete!\n"
            f"Processed requests: {total_requests}\n"
            f"Updated returns:    {updated_returns}\n"
            f"Updated exchanges:  {updated_exchanges}\n"
            f"Skipped (no change): {skipped}"
        ))
