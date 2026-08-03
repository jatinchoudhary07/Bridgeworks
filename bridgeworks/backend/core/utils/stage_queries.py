from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from ..models import Order, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES, NDR_STATUSES

# Stages whose Q filters involve a JOIN (fulfillments__*) and therefore
# require distinct=True on Count() to avoid row multiplication.
STAGES_REQUIRING_DISTINCT = {
    "confirmed but awb not generated",
    "label generated but not fulfilled",
}


def get_q_filter_for_stage(stage_name):
    """
    Returns a Q object representing the filter criteria for the given stage.
    Returns None for stages that are placeholders (always empty).

    Used to build a single conditional-aggregation query instead of N separate
    queryset.filter(...).aggregate(...) calls.
    """
    if not stage_name:
        return None

    stage = stage_name.lower().strip()

    # 1. Order Placed but not confirmed
    if stage == "order placed but not confirmed":
        return Q(status='Pending')

    # 2. Confirmed but AWB not generated  (JOIN-based – mark for distinct)
    elif stage == "confirmed but awb not generated":
        return (
            Q(status='Confirmed') &
            (Q(fulfillments__tracking_info__number__isnull=True) |
             Q(fulfillments__tracking_info__number=''))
        )

    # 3. Label Generated but not fulfilled  (JOIN-based – mark for distinct)
    elif stage == "label generated but not fulfilled":
        return (
            Q(fulfillments__tracking_info__number__isnull=False) &
            ~Q(fulfillments__tracking_info__number='') &
            ~Q(fulfillment_status__iexact='Fulfilled')
        )

    # 4. Fulfilled but not packed
    elif stage == "fulfilled but not packed":
        return (
            Q(fulfillment_status__iexact='Fulfilled') &
            ~Q(internal_fulfillment_status__in=['Packaged', 'On Hold'])
        )

    # 5. Packed but not manifested
    elif stage == "packed but not manifested":
        return (
            Q(internal_fulfillment_status='Packaged') &
            ~Q(current_status__iexact='Manifested')
        )

    # 6. Manifested
    elif stage == "manifested":
        return Q(current_status__iexact='Manifested')

    # 7. Dispatched
    elif stage == "dispatched":
        return Q(current_status__iexact='Dispatched')

    # 8. In Transit
    elif stage == "in transit":
        return Q(current_status__iexact='In Transit')

    # 9. NDR (Failed Delivery)
    elif stage == "ndr (failed delivery)" or stage == "ndr":
        return Q(is_ndr=True)

    # 10. Delivered Orders
    elif stage == "delivered orders" or stage == "delivered":
        return Q(current_status__iexact='Delivered')

    # 11. RTO Intransit
    elif stage == "rto intransit":
        return Q(current_status__in=RTO_TRANSIT_STATUSES)

    # 12. RTO Delivered
    elif stage == "rto delivered":
        return Q(current_status__in=RTO_DELIVERED_STATUSES)

    # 13. RTO Dispute/FRAUD – placeholder
    elif stage == "rto dispute/fraud":
        return None

    # 14. Returns
    elif stage == "returns":
        return ~Q(rto_internal_status='Pending')

    # 15. Exchange
    elif stage == "exchange":
        return Q(tags__icontains='exchange')

    # 16. Restocked
    elif stage == "restocked":
        return Q(rto_internal_status='Restocked')

    # 17. Cancelled
    elif stage == "cancelled":
        return Q(status='Cancelled')

    # 18. New Order Created (last 24 h – computed at call time)
    elif stage == "new order created":
        yesterday = timezone.now() - timedelta(days=1)
        return Q(created_at__gte=yesterday)

    # 19. Compensation Received – placeholder
    elif stage == "compensation received":
        return None

    return None

def get_queryset_for_stage(base_qs, stage_name):
    """
    Returns a filtered queryset based on the stage name.
    base_qs: The filtered queryset (by date, etc.) to apply stage logic to.
    """
    if not stage_name:
        return base_qs.none()
    
    stage = stage_name.lower().strip()
    
    # 1. Order Placed but not confirmed
    if stage == "order placed but not confirmed":
        return base_qs.filter(status='Pending')
        
    # 2. Confirmed but AWB not generated
    elif stage == "confirmed but awb not generated":
        return base_qs.filter(status='Confirmed').filter(
            Q(fulfillments__tracking_info__number__isnull=True) | 
            Q(fulfillments__tracking_info__number='')
        )

    # 3. Label Generated but not fulfilled
    elif stage == "label generated but not fulfilled":
        return base_qs.filter(
            fulfillments__tracking_info__number__isnull=False
        ).exclude(fulfillments__tracking_info__number='').filter(
            ~Q(fulfillment_status__iexact='Fulfilled')
        )

    # 4. Fulfilled but not packed
    elif stage == "fulfilled but not packed":
        return base_qs.filter(
            fulfillment_status__iexact='Fulfilled'
        ).exclude(
            internal_fulfillment_status__in=['Packaged', 'On Hold'] # Assuming 'Packaged' is the next step
        )

    # 5. Packed but not manifested
    elif stage == "packed but not manifested":
        return base_qs.filter(
            internal_fulfillment_status='Packaged'
        ).exclude(
            current_status__iexact='Manifested'
        )

    # 6. Manifested
    elif stage == "manifested":
        return base_qs.filter(current_status__iexact='Manifested')

    # 7. Dispatched
    elif stage == "dispatched":
        return base_qs.filter(current_status__iexact='Dispatched')

    # 8. In Transit
    elif stage == "in transit":
        return base_qs.filter(current_status__iexact='In Transit')

    # 9. NDR (Failed Delivery)
    elif stage == "ndr (failed delivery)" or stage == "ndr":
        return base_qs.filter(is_ndr=True)

    # 10. Delivered Orders
    elif stage == "delivered orders" or stage == "delivered":
        return base_qs.filter(current_status__iexact='Delivered')

    # 11. RTO Intransit
    elif stage == "rto intransit":
        return base_qs.filter(current_status__in=RTO_TRANSIT_STATUSES)

    # 12. RTO Delivered
    elif stage == "rto delivered":
        return base_qs.filter(current_status__in=RTO_DELIVERED_STATUSES)

    # 13. RTO Dispute/FRAUD
    elif stage == "rto dispute/fraud":
        return base_qs.none() # Placeholder

    # 14. Returns
    elif stage == "returns":
        return base_qs.exclude(rto_internal_status='Pending')

    # 15. Exchange
    elif stage == "exchange":
        return base_qs.filter(tags__icontains='exchange')

    # 16. Restocked
    elif stage == "restocked":
        return base_qs.filter(rto_internal_status='Restocked')

    # 17. Cancelled
    elif stage == "cancelled":
        return base_qs.filter(status='Cancelled')

    # 18. New Order Created
    elif stage == "new order created":
        # Orders created in the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        return base_qs.filter(created_at__gte=yesterday)

    # 19. Compensation Received
    elif stage == "compensation received":
        return base_qs.none() # Placeholder

    return base_qs.none()
