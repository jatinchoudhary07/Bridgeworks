"""
Management command: analyze_all_orders
=======================================
Loops through all existing orders and backfills their
risk_score, intelligence_flag, and system_suggestion
using the Order Intelligence Bot.

Usage:
    python manage.py analyze_all_orders
    python manage.py analyze_all_orders --org-id janki-jewels
    python manage.py analyze_all_orders --limit 100
"""
import time
from django.core.management.base import BaseCommand
from core.models import Order
from core.services.intelligence import run_order_bot


class Command(BaseCommand):
    help = "Analyze all orders with the Intelligence Bot and backfill scores."

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=str,
            default=None,
            help='Only analyze orders for a specific organization ID.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of orders to process.',
        )
        parser.add_argument(
            '--reanalyze',
            action='store_true',
            help='Re-analyze orders that already have a score (default: skip them).',
        )

    def handle(self, *args, **options):
        org_id = options['org_id']
        limit = options['limit']
        reanalyze = options['reanalyze']

        queryset = Order.objects.all().order_by('-created_at')

        if org_id:
            queryset = queryset.filter(org_id=org_id)
            self.stdout.write(f"Filtering to org: {org_id}")

        if not reanalyze:
            queryset = queryset.filter(intelligence_flag='NONE')
            self.stdout.write("Skipping already-analyzed orders (use --reanalyze to override)")

        if limit:
            queryset = queryset[:limit]
            self.stdout.write(f"Limiting to {limit} orders")

        order_ids = list(queryset.values_list('id', flat=True))
        total = len(order_ids)

        self.stdout.write(self.style.WARNING(f"\nStarting analysis of {total} orders...\n"))

        green = yellow = red = errors = 0
        start_time = time.time()

        for i, order_id in enumerate(order_ids, 1):
            try:
                result = run_order_bot(order_id)

                if result:
                    flag = result['flag']
                    if flag == 'GREEN':
                        green += 1
                    elif flag == 'YELLOW':
                        yellow += 1
                    elif flag == 'RED':
                        red += 1

                    if i % 100 == 0 or i == total:
                        elapsed = time.time() - start_time
                        rate = i / elapsed if elapsed > 0 else 0
                        self.stdout.write(
                            f"  [{i}/{total}] "
                            f"GREEN={green}  YELLOW={yellow}  RED={red}  "
                            f"({rate:.1f} orders/sec)"
                        )
                else:
                    errors += 1

            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error on order ID {order_id}: {e}")

        elapsed = time.time() - start_time

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Analysis Complete!"))
        self.stdout.write(f"  Total Processed: {total}")
        self.stdout.write(f"  [GREEN]  Low Risk:   {green}")
        self.stdout.write(f"  [YELLOW] Medium Risk:  {yellow}")
        self.stdout.write(f"  [RED]    High Risk:    {red}")
        self.stdout.write(f"  [ERROR]  Errors:       {errors}")
        self.stdout.write(f"  Time: {elapsed:.1f}s")
        self.stdout.write("=" * 60)
