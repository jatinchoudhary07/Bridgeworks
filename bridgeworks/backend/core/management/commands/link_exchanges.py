from django.core.management.base import BaseCommand
from core.models import Order, ReturnRequest
from django.db.models import Q

class Command(BaseCommand):
    help = 'Auto-links Exchange orders from Return Prime back to their original parent orders via tags and customer fuzzy matching.'

    def handle(self, *args, **kwargs):
        # 1. Identify all potential exchange orders
        # We look for 'Associated order:' or 'Exchange' in tags
        exchange_candidates = Order.objects.filter(
            Q(tags__icontains='Associated order:#') | Q(tags__icontains='Exchange')
        ).filter(parent_order__isnull=True)
        
        self.stdout.write(f"Analyzing {exchange_candidates.count()} potential unlinked Exchange Orders...")

        tag_linked = 0
        fuzzy_linked = 0
        already_is_exchange = 0

        for ex_order in exchange_candidates:
            tags_str = str(ex_order.tags or '')
            parent_order = None
            method = None

            # --- METHOD 1: Direct Tag Match ---
            if 'Associated order:#' in tags_str:
                try:
                    parts = tags_str.split('Associated order:#')
                    if len(parts) > 1:
                        target = parts[1].split(',')[0].strip()
                        clean_num = ''.join(filter(str.isdigit, target))
                        if clean_num:
                            parent_order = Order.objects.filter(order_number=clean_num).first()
                            if parent_order:
                                method = "Tag"
                except Exception:
                    pass

            # --- METHOD 2: Fuzzy Customer Match ---
            if not parent_order and 'Exchange' in tags_str:
                try:
                    # Look for the most recent Exchange request from this customer
                    q = Q(request_type__iexact='EXCHANGE')
                    c_filter = Q()
                    if ex_order.customer_id: c_filter |= Q(order__customer_id=ex_order.customer_id)
                    if ex_order.contact_email: c_filter |= Q(order__contact_email=ex_order.contact_email)
                    if ex_order.contact_phone: c_filter |= Q(order__contact_phone=ex_order.contact_phone)
                    
                    if c_filter:
                        ret_req = ReturnRequest.objects.filter(q & c_filter).order_by('-created_at').first()
                        if ret_req:
                            parent_order = ret_req.order
                            method = "Fuzzy"
                except Exception:
                    pass

            # --- Apply Linkage ---
            if parent_order:
                ex_order.parent_order = parent_order
                ex_order.is_exchange_order = True
                ex_order.save(update_fields=['parent_order', 'is_exchange_order'])
                if method == "Tag": tag_linked += 1
                else: fuzzy_linked += 1
                self.stdout.write(f"Linked Order #{ex_order.order_number} -> Parent #{parent_order.order_number} ({method})")
            elif 'Exchange' in tags_str:
                # Even if we can't find the parent, mark it as an exchange order
                if not ex_order.is_exchange_order:
                    ex_order.is_exchange_order = True
                    ex_order.save(update_fields=['is_exchange_order'])
                    already_is_exchange += 1

        self.stdout.write(self.style.SUCCESS(
            f"Summary:\n"
            f"- Tag Linked: {tag_linked}\n"
            f"- Fuzzy Linked: {fuzzy_linked}\n"
            f"- Marked as Exchange (Parent not found): {already_is_exchange}"
        ))
