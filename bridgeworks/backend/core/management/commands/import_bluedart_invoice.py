"""
import_bluedart_invoice.py
==========================
Parses a Bluedart freight invoice PDF and upserts ShipmentCost records
for each AWB found. Works for both Prepaid and COD invoice PDFs —
we only care about AWB numbers and the per-shipment freight amount.

Usage:
    python manage.py import_bluedart_invoice path/to/invoice.pdf
    python manage.py import_bluedart_invoice path/to/invoice.pdf --org-id janki-jewels
    python manage.py import_bluedart_invoice path/to/invoice.pdf --dry-run

What it does:
    1. Parses the PDF using pdfplumber (dual-column table layout)
    2. Extracts: AWB, forward_cost (freight), weight_slab (charged weight)
    3. For each AWB, finds the matching Shipment in DB
    4. Creates or updates ShipmentCost with forward_cost populated
    5. Logs matched / not-found / already-costed counts
"""

import os
import re
import logging
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models.delivery import Shipment, ShipmentCost
from core.services.delivery_services import parse_bluedart_pdf

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Import a Bluedart freight invoice PDF and upsert ShipmentCost records "
        "for each AWB. Works for both Prepaid and COD invoice PDFs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'pdf_path',
            type=str,
            help='Path to the Bluedart invoice PDF file.',
        )
        parser.add_argument(
            '--org-id',
            type=str,
            default=None,
            help='Restrict AWB lookups to a specific organization ID.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse the PDF and show matches without writing to the database.',
        )

    def handle(self, *args, **options):
        pdf_path = options['pdf_path']
        org_id   = options['org_id']
        dry_run  = options['dry_run']

        if not os.path.exists(pdf_path):
            raise CommandError(f"File not found: {pdf_path}")

        # ── Step 1: Parse the PDF ──────────────────────────────────────────
        self.stdout.write(self.style.NOTICE(f"\nParsing: {os.path.basename(pdf_path)}"))
        invoice_number, parsed_invoice_date_str, summary_dict, rows = parse_bluedart_pdf(pdf_path)

        self.stdout.write(f"  Invoice Number : {invoice_number or 'Not found'}")
        self.stdout.write(f"  Invoice Date   : {parsed_invoice_date_str or 'Not found'}")
        self.stdout.write(f"  AWBs extracted : {len(rows)}")

        if not rows:
            self.stdout.write(self.style.WARNING("  No AWBs found in PDF. Exiting."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] No database writes will be made.\n"))

        # ── Step 2: Match to Shipments and upsert ShipmentCost ───────────
        matched   = 0
        not_found = 0
        created   = 0
        updated   = 0
        skipped   = 0

        awb_list = [r['awb'] for r in rows]

        # Bulk-fetch matching shipments to minimise DB queries
        shipment_qs = Shipment.objects.filter(awb_number__in=awb_list)
        if org_id:
            shipment_qs = shipment_qs.filter(org_id=org_id)

        shipment_map = {s.awb_number: s for s in shipment_qs.select_related('cost')}

        not_found_awbs = []

        with transaction.atomic():
            for row in rows:
                awb          = row['awb']
                forward_cost = row['forward_cost']

                shipment = shipment_map.get(awb)
                if not shipment:
                    not_found += 1
                    not_found_awbs.append(awb)
                    continue

                matched += 1

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] AWB {awb} -> Shipment #{shipment.id} "
                        f"forward_cost=Rs{forward_cost}"
                    )
                    continue

                cost, was_created = ShipmentCost.objects.get_or_create(
                    shipment=shipment,
                    defaults={
                        'forward_cost': forward_cost,
                        'actual_billed_cost': forward_cost,
                    }
                )

                if was_created:
                    created += 1
                else:
                    # Update freight cost fields; don't touch COD charges, RTO, etc.
                    cost.forward_cost       = forward_cost
                    cost.actual_billed_cost = forward_cost
                    cost.save(update_fields=['forward_cost', 'actual_billed_cost'])
                    updated += 1

        # ── Step 3: Summary ───────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 55)
        self.stdout.write(self.style.SUCCESS("Import Complete!"))
        self.stdout.write(f"  AWBs in invoice  : {len(rows)}")
        self.stdout.write(f"  Matched Shipments: {matched}")
        self.stdout.write(f"  Not in DB        : {not_found}")
        if not dry_run:
            self.stdout.write(f"  Cost Records Created : {created}")
            self.stdout.write(f"  Cost Records Updated : {updated}")
        self.stdout.write("=" * 55)

        if not_found_awbs:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  {not_found} AWBs not found in your database "
                    f"(may be from other orgs or not yet synced):"
                )
            )
            for awb in not_found_awbs[:20]:
                self.stdout.write(f"    {awb}")
            if len(not_found_awbs) > 20:
                self.stdout.write(f"    ... and {len(not_found_awbs) - 20} more")
