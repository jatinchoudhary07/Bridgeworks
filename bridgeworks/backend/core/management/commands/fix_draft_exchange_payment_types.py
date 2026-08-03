from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models.delivery import Shipment, CODRemittance
from core.services.delivery_services import (
    derive_payment_type,
    calculate_expected_remittance_date,
)

class Command(BaseCommand):
    help = "Backfill misclassified Prepaid draft and exchange shipments to COD on production and create COD Remittances."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Actually update the database. Without this, runs in dry-run mode.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        mode = "APPLY" if apply else "DRY-RUN"
        
        self.stdout.write(self.style.NOTICE(f"--- Starting Payment Type Backfill ({mode}) ---"))

        # Fetch prepaid shipments
        shipments = Shipment.objects.filter(payment_type='PrePaid').select_related('order')
        
        to_update = []
        remittances_to_create = []
        
        for s in shipments:
            if not s.order:
                continue
            
            # Use the updated derivation logic to see what it should be
            correct_type = derive_payment_type(s.order)
            if correct_type == 'COD':
                to_update.append((s, correct_type))
                
                # If it's already delivered, we need a COD Remittance record
                if s.current_stage == 'Delivered':
                    has_remittance = CODRemittance.objects.filter(shipment=s).exists()
                    if not has_remittance:
                        ref_date = s.delivery_date or s.dispatch_date or s.order.created_at
                        expected_date = calculate_expected_remittance_date(ref_date)
                        
                        # Extract COD amount from total price
                        cod_amount = s.order.total_price or 0
                        
                        remittances_to_create.append(
                            CODRemittance(
                                shipment=s,
                                expected_amount=cod_amount,
                                expected_remittance_date=expected_date,
                                status='Pending'
                            )
                        )

        self.stdout.write(self.style.WARNING(f"Found {len(to_update)} shipments misclassified as Prepaid."))
        self.stdout.write(self.style.WARNING(f"Will generate {len(remittances_to_create)} missing COD Remittance records for delivered shipments."))

        if apply:
            with transaction.atomic():
                # 1. Update shipments
                for s, correct_type in to_update:
                    s.payment_type = correct_type
                    s.save(update_fields=['payment_type'])
                
                # 2. Bulk create remittances
                if remittances_to_create:
                    CODRemittance.objects.bulk_create(remittances_to_create)
                    
            self.stdout.write(self.style.SUCCESS("Successfully updated shipments and generated COD Remittances on Production!"))
        else:
            self.stdout.write(self.style.NOTICE("Dry-run complete. Run with --apply to apply updates."))
