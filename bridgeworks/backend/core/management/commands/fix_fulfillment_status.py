"""
Management command to fix orders incorrectly marked as 'fulfilled' that only
have Shipway-fetched fulfillments (no shopify_id).

These orders should be 'Tracking_added' instead of 'fulfilled' because
the real Shopify fulfillment webhook hasn't come in yet.

Usage:
    python manage.py fix_fulfillment_status          # dry-run (preview)
    python manage.py fix_fulfillment_status --apply   # actually fix
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Exists, OuterRef
from core.models import Order, Fulfillment


class Command(BaseCommand):
    help = "Fix orders marked 'fulfilled' that have no real Shopify fulfillment (only Shipway-fetched)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply the fix. Without this flag, only a dry-run preview is shown.',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        # Orders that are marked 'fulfilled' in fulfillment_status
        fulfilled_orders = Order.objects.filter(fulfillment_status='fulfilled')

        # Subquery: order has at least one fulfillment WITH a real Shopify ID
        has_shopify_fulfillment = Fulfillment.objects.filter(
            order=OuterRef('pk'),
            shopify_id__isnull=False,
        )

        # Orders marked 'fulfilled' but with NO real Shopify fulfillment
        bad_orders = fulfilled_orders.exclude(Exists(has_shopify_fulfillment))

        count = bad_orders.count()
        self.stdout.write(f"\nFound {count} orders marked 'fulfilled' without a real Shopify fulfillment.\n")

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to fix!"))
            return

        # Preview
        for order in bad_orders[:50]:
            fulfillments = order.fulfillments.all()
            f_info = ", ".join(
                f"[id={f.id}, shopify_id={f.shopify_id or 'NONE'}, service={f.service}]"
                for f in fulfillments
            )
            self.stdout.write(
                f"  Order #{order.order_number} (id={order.id}) — "
                f"fulfillment_status='{order.fulfillment_status}' — "
                f"fulfillments: {f_info or 'NONE'}"
            )

        if count > 50:
            self.stdout.write(f"  ... and {count - 50} more.\n")

        if apply:
            updated = bad_orders.update(fulfillment_status='Tracking_added')
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Fixed {updated} orders: fulfillment_status changed from 'fulfilled' → 'Tracking_added'."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  DRY RUN — no changes made. Run with --apply to fix these {count} orders."
            ))
