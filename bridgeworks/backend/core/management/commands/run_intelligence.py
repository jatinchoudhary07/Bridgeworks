from django.core.management.base import BaseCommand
from core.models import Order
from core.tasks import evaluate_order_task
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Evalaute orders synchronously using the RTO Intelligence AI Agent.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of recent orders to evaluate'
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only evaluate orders that do not have a risk score yet'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        missing_only = options['missing_only']

        query = Order.objects.all().order_by('-created_at')
        
        if missing_only:
            query = query.filter(risk_score__isnull=True)
            
        orders = query[:limit]

        if not orders.exists():
            self.stdout.write(self.style.WARNING("No orders found to evaluate."))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting synchronous evaluation of {orders.count()} orders..."))
        
        success_count = 0
        fail_count = 0

        for idx, order in enumerate(orders, 1):
            self.stdout.write(f"[{idx}/{orders.count()}] Evaluating Order #{order.order_number}...")
            try:
                # We call the task directly as a standard Python function, NOT via async_task.
                # This guarantees it runs synchronously on the spot in this terminal window.
                result = evaluate_order_task(order.id, attempt=MAX_ATTEMPTS_FLAG) # We'll just pass attempt=3 so it doesn't trigger a background retry if phone is missing
            except NameError:
                # If MAX_ATTEMPTS_FLAG is not available, we use 3 explicitly to avoid the 10-min background retry logic
                result = evaluate_order_task(order.id, attempt=3)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error executing evaluate_order_task for #{order.order_number}: {e}"))
                fail_count += 1
                continue

            if "✅" in str(result) or "SUCCESS" in str(result) or str(result).startswith("✅") or "Order" in str(result):
                # Safely print without emojis
                clean_result = str(result).replace("✅", "[SUCCESS]").replace("❌", "[ERROR]").replace("⏳", "[RETRY]").replace("⚠️", "[WARNING]")
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"  -> {clean_result}"))
            elif "RETRY" in str(result):
                clean_result = str(result).replace("✅", "[SUCCESS]").replace("❌", "[ERROR]").replace("⏳", "[RETRY]").replace("⚠️", "[WARNING]")
                self.stdout.write(self.style.WARNING(f"  -> {clean_result} (Note: Background retry scheduled)"))
            else:
                fail_count += 1
                clean_result = str(result).replace("✅", "[SUCCESS]").replace("❌", "[ERROR]").replace("⏳", "[RETRY]").replace("⚠️", "[WARNING]")
                self.stderr.write(self.style.ERROR(f"  -> {clean_result}"))

        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS(f"Evaluation Complete! successes: {success_count}, failures/retries: {fail_count}"))
        self.stdout.write("="*40 + "\n")
