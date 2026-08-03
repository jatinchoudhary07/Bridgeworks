from django.core.management.base import BaseCommand
from django.db import close_old_connections
import time

from core.models.delivery import Shipment, CODRemittance
from core.models import TrackingEvent
from core.services.delivery_services import (
    map_status_to_stage, 
    calculate_expected_remittance_date,
    derive_payment_type
)

class Command(BaseCommand):
    help = "One-off script to fix false 'Delivered' shipments and correct delivery dates."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting data correction..."))

        # Part 1: Fix false 'Delivered' (the 'undelivered' substring bug)
        self.stdout.write(self.style.NOTICE("\n[Phase 1] Fixing falsely marked 'Delivered' shipments..."))
        shipments = Shipment.objects.filter(current_stage='Delivered').select_related('order')
        fixed_undelivered = 0
        deleted_remittances = 0

        for s in shipments:
            if not s.order:
                continue
            
            status = s.order.current_status
            if not status:
                continue
                
            correct_stage = map_status_to_stage(status)
            if correct_stage != 'Delivered':
                self.stdout.write(f"  AWB {s.awb_number} -> actually {correct_stage}")
                s.current_stage = correct_stage
                s.save(update_fields=['current_stage'])
                fixed_undelivered += 1
                
                # Delete remittance
                rem_count, _ = CODRemittance.objects.filter(shipment=s).delete()
                deleted_remittances += rem_count

        self.stdout.write(self.style.SUCCESS(
            f"Phase 1 Complete: Fixed {fixed_undelivered} shipments, deleted {deleted_remittances} invalid remittances."
        ))

        # Part 2: Fix Delivery Dates (Earliest event bug)
        self.stdout.write(self.style.NOTICE("\n[Phase 2] Fixing delivery dates (using earliest event)..."))
        
        # Re-fetch only true delivered shipments
        shipment_ids = list(Shipment.objects.filter(current_stage='Delivered').values_list('id', flat=True))
        total = len(shipment_ids)
        updated_dates = 0
        errors = 0

        for i, sid in enumerate(shipment_ids):
            if i % 100 == 0:
                self.stdout.write(f"  Processed {i}/{total}...")
                close_old_connections()
                
            try:
                s = Shipment.objects.get(id=sid)
                if not s.order:
                    continue
                
                earliest_event = TrackingEvent.objects.filter(
                    fulfillment__order=s.order,
                    status__icontains='delivered'
                ).exclude(
                    status__icontains='rto'
                ).exclude(
                    status__icontains='return'
                ).exclude(
                    status__icontains='undelivered'
                ).order_by('datetime').first()
                
                # Update payment type (fixes 'Partial Payment' tag issue)
                new_payment_type = derive_payment_type(s.order)
                if s.payment_type != new_payment_type:
                    self.stdout.write(f"  AWB {s.awb_number}: Payment Type {s.payment_type} -> {new_payment_type}")
                    s.payment_type = new_payment_type
                    s.save(update_fields=['payment_type'])

                if earliest_event and s.delivery_date != earliest_event.datetime:
                    old_date = s.delivery_date
                    s.delivery_date = earliest_event.datetime
                    s.save(update_fields=['delivery_date'])
                    
                    # Also update remittance expected date
                    rem = CODRemittance.objects.filter(shipment=s).first()
                    if rem:
                        rem.expected_remittance_date = calculate_expected_remittance_date(s.delivery_date)
                        rem.save(update_fields=['expected_remittance_date'])
                        
                    updated_dates += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error on shipment {sid}: {e}")
                close_old_connections()
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(
            f"Phase 2 Complete: Updated dates for {updated_dates} shipments. Errors: {errors}"
        ))

        # Final check
        count = CODRemittance.objects.filter(
            shipment__delivery_date__date__gte='2026-04-08',
            shipment__delivery_date__date__lte='2026-04-15',
        ).count()
        
        self.stdout.write(self.style.SUCCESS(
            f"\nAll done! COD Remittances between 2026-04-08 and 2026-04-15: {count}"
        ))
