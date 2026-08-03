from django.core.management.base import BaseCommand
from core.models import Customer, Order, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
from django.db.models import Q, Count
from django.db import transaction

class Command(BaseCommand):
    help = 'Backfill customer metrics (total, delivered, RTO, and cancelled orders) based on actual orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org',
            type=str,
            default=None,
            help='Filter by organization ID'
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply changes to database (turns off dry-run)'
        )

    def handle(self, *args, **options):
        org_id = options['org']
        dry_run = not options['apply']

        self.stdout.write("--- Customer Metrics Backfill ---")
        self.stdout.write(f"Filtering by Org: {org_id if org_id else 'All Organizations'}")
        self.stdout.write(f"Dry Run Mode: {dry_run}\n")

        # Fetch customers
        customers = Customer.objects.all()
        if org_id:
            customers = customers.filter(org_id=org_id)

        total_customers = customers.count()
        self.stdout.write(f"Found {total_customers} customers in database.")

        # Calculate stats grouped by customer_id
        order_filter = Q(customer__isnull=False)
        if org_id:
            order_filter &= Q(org_id=org_id)

        stats = Order.objects.filter(order_filter).values('customer_id').annotate(
            total_distinct=Count('id', distinct=True),
            delivered_distinct=Count('id', filter=Q(status__iexact='Delivered') | Q(current_status__iexact='Delivered') | Q(fulfillments__shipment_status__iexact='Delivered'), distinct=True),
            rto_distinct=Count('id', filter=Q(current_status__in=RTO_TRANSIT_STATUSES) | Q(current_status__in=RTO_DELIVERED_STATUSES) | Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) | Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES), distinct=True),
            cancelled_distinct=Count('id', filter=Q(status__iexact='Cancelled') | Q(current_status__iexact='Cancelled'), distinct=True)
        )

        stats_map = {s['customer_id']: s for s in stats}
        self.stdout.write(f"Calculated stats for {len(stats_map)} customers who have linked orders in the DB.\n")

        to_update = []
        updates_count = 0

        for c in customers:
            old_vals = (c.total_orders, c.delivered_orders, c.rto_orders, c.cancelled_orders)
            
            if c.id in stats_map:
                s = stats_map[c.id]
                new_total = s['total_distinct']
                new_delivered = s['delivered_distinct']
                new_rto = s['rto_distinct']
                new_cancelled = s['cancelled_distinct']
            else:
                new_total = 0
                new_delivered = 0
                new_rto = 0
                new_cancelled = 0

            new_vals = (new_total, new_delivered, new_rto, new_cancelled)

            if old_vals != new_vals:
                if old_vals[0] > 10:  # Highlight likely corrupted ones
                    self.stdout.write(f"Customer ID {c.id} ({c.name or c.email or c.phone}):")
                    self.stdout.write(f"  Old: Total={old_vals[0]}, Delivered={old_vals[1]}, RTO={old_vals[2]}, Cancelled={old_vals[3]}")
                    self.stdout.write(f"  New: Total={new_vals[0]}, Delivered={new_vals[1]}, RTO={new_vals[2]}, Cancelled={new_vals[3]}")
                
                c.total_orders = new_total
                c.delivered_orders = new_delivered
                c.rto_orders = new_rto
                c.cancelled_orders = new_cancelled
                to_update.append(c)
                updates_count += 1

        self.stdout.write(f"\nTotal customers requiring updates: {updates_count}")

        if not dry_run:
            if to_update:
                with transaction.atomic():
                    Customer.objects.bulk_update(
                        to_update, 
                        fields=['total_orders', 'delivered_orders', 'rto_orders', 'cancelled_orders'], 
                        batch_size=2000
                    )
                self.stdout.write(self.style.SUCCESS(f"Successfully updated {updates_count} customers in database."))
            else:
                self.stdout.write("No customers to update.")
        else:
            self.stdout.write("[Dry Run] No updates were written to the database.")
