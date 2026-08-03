from django.core.management.base import BaseCommand
from core.models import Batch, TrackingInfo

class Command(BaseCommand):
    help = "Update all tracking info URLs in a specific AWB batch to a custom PDF/S3 URL"

    def add_arguments(self, parser):
        parser.add_argument('--batch-id', type=int, required=True, help='ID of the batch to update')
        parser.add_argument('--url', type=str, required=True, help='The custom S3/PDF label URL to apply')

    def handle(self, *args, **options):
        batch_id = options['batch_id']
        custom_url = options['url'].strip()

        try:
            batch = Batch.objects.get(id=batch_id)
        except Batch.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Batch with ID {batch_id} does not exist."))
            return

        orders = batch.orders.all()
        self.stdout.write(f"Found {orders.count()} orders in Batch #{batch_id}. Updating tracking info URLs...")

        updated_count = 0
        for order in orders:
            for f in order.fulfillments.all():
                for t in f.tracking_info.all():
                    t.url = custom_url
                    t.save()
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully updated {updated_count} tracking info records to point to: {custom_url}"
        ))
