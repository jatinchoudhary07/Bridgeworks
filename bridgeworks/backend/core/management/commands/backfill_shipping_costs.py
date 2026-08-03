"""
backfill_shipping_costs — Management Command
==============================================
Retroactively compute zones and shipping costs for existing shipments.

Usage:
    python manage.py backfill_shipping_costs --org-id=ORG123
    python manage.py backfill_shipping_costs --org-id=ORG123 --recalculate-all
"""

from django.core.management.base import BaseCommand
from core.services.zone_engine import backfill_zones_and_costs


class Command(BaseCommand):
    help = 'Backfill shipping zones and costs for existing shipments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=str,
            required=True,
            help='Organization ID to backfill'
        )
        parser.add_argument(
            '--recalculate-all',
            action='store_true',
            default=False,
            help='Recalculate even for shipments that already have cost records'
        )

    def handle(self, *args, **options):
        org_id = options['org_id']
        recalculate_all = options['recalculate_all']

        self.stdout.write(f'Starting backfill for org: {org_id}')
        if recalculate_all:
            self.stdout.write(self.style.WARNING('  → Recalculating ALL shipments (including existing costs)'))
        else:
            self.stdout.write('  → Only processing shipments without cost records')

        result = backfill_zones_and_costs(org_id, recalculate_all=recalculate_all)

        if 'error' in result:
            self.stdout.write(self.style.ERROR(f'Error: {result["error"]}'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Done! Processed: {result["processed"]}, '
            f'Updated: {result["updated"]}, '
            f'Skipped: {result["skipped"]}, '
            f'Errors: {result["errors"]}'
        ))
