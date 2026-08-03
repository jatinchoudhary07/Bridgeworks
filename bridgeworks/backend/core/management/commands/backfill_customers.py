import logging
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import transaction
from core.models import Order, Customer, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Backfill the Customer table based on historical Order data.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Customer Data Backfill..."))

        # Orders with an explicit contact phone
        orders_with_phone = Order.objects.exclude(contact_phone__isnull=True).exclude(contact_phone="")
        self.stdout.write(f"Found {orders_with_phone.count()} orders with phone numbers.")

        processed = 0
        created_customers = 0
        updated_orders = 0

        # We need a robust way to group orders by phone.
        phone_groups = orders_with_phone.values('org_id', 'contact_phone').annotate(order_count=Count('id'))

        self.stdout.write(f"Aggregated {phone_groups.count()} unique Customer phone profiles.")

        for group in phone_groups:
            org_id = group['org_id']
            phone = group['contact_phone'].strip()
            if not phone:
                continue

            with transaction.atomic():
                # Get the orders for this phone & org
                customer_orders = Order.objects.filter(org_id=org_id, contact_phone=phone)
                
                # Get the most recent order to extract the best name, email, address
                latest_order = customer_orders.order_by('-created_at').first()

                name = f"{latest_order.customer_first_name or ''} {latest_order.customer_last_name or ''}".strip()
                if not name:
                    name = latest_order.contact_email or "Unknown"
                
                email = latest_order.contact_email
                address = latest_order.shipping_address

                customer, created = Customer.objects.get_or_create(
                    org_id=org_id,
                    phone=phone,
                    defaults={
                        'name': name,
                        'email': email,
                        'address': address
                    }
                )

                if created:
                    created_customers += 1

                # Calculate metrics
                total_orders = customer_orders.count()
                
                delivered_orders = customer_orders.filter(
                    Q(status__iexact='Delivered') |
                    Q(current_status__iexact='Delivered') |
                    Q(fulfillments__shipment_status__iexact='Delivered')
                ).distinct().count()

                rto_orders = customer_orders.filter(
                    Q(current_status__in=RTO_TRANSIT_STATUSES) |
                    Q(current_status__in=RTO_DELIVERED_STATUSES) |
                    Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) |
                    Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES)
                ).distinct().count()

                cancelled_orders = customer_orders.filter(
                    status__iexact='Cancelled'
                ).distinct().count()

                # Save metrics directly avoiding signals where possible, but here we just save
                customer.total_orders = total_orders
                customer.delivered_orders = delivered_orders
                customer.rto_orders = rto_orders
                customer.cancelled_orders = cancelled_orders
                customer.save()

                # Link all these orders to this customer
                updated = customer_orders.update(customer=customer)
                updated_orders += updated
                
            processed += 1
            if processed % 100 == 0:
                self.stdout.write(f"Processed {processed}/{phone_groups.count()} customer groups...")

        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS(f"Backfill Complete!"))
        self.stdout.write(f"Created {created_customers} distinct Customers.")
        self.stdout.write(f"Linked/Updated {updated_orders} total Orders.")
        self.stdout.write("="*40 + "\n")
