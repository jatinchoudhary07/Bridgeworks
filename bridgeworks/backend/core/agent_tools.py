"""
AI Agent Tools
================================
These are the 'hands' of the Gemini Agent — callable functions
it uses to query the database for context before making a verdict.

These are plain Python functions with type hints and docstrings.
The google-genai SDK auto-generates tool schemas from these signatures.
"""
import logging
from django.db.models import Q, Avg, F, ExpressionWrapper, DurationField

logger = logging.getLogger(__name__)


def get_customer_history(phone: str, email: str) -> dict:
    """
    Look up a customer's past order history by phone number and/or email.
    Returns counts of Delivered, RTO (returned), and Cancelled orders.
    Use this to determine if the customer is trustworthy or a repeat offender.
    """
    from core.models import Customer
    from django.db.models import Q

    customer_q = Q()
    if phone:
        customer_q |= Q(phone=phone.strip())
    if email:
        customer_q |= Q(email=email.strip())

    if not customer_q:
        return {
            "delivered_count": 0,
            "rto_count": 0,
            "cancelled_count": 0,
            "total_past_orders": 0,
            "note": "No phone or email provided — cannot look up history."
        }

    customer = Customer.objects.filter(customer_q).first()

    if not customer:
        return {
            "delivered_count": 0,
            "rto_count": 0,
            "cancelled_count": 0,
            "total_past_orders": 0,
            "note": f"No customer found with phone {phone} or email {email}."
        }

    return {
        "delivered_count": customer.delivered_orders,
        "rto_count": customer.rto_orders,
        "cancelled_count": customer.cancelled_orders,
        "total_past_orders": customer.total_orders,
        "note": f"Customer lifetime metrics retrieved. Name: {customer.name}"
    }


def get_pincode_health(pincode: str) -> dict:
    """
    Analyze historical delivery performance for a pincode region over the last 30 days.
    Returns the RTO (return) percentage and average delivery days
    broken down by courier company. Falls back to the first 3 digits
    of the pincode if the exact pincode has insufficient data.
    Use this to recommend the best courier for delivery.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Avg, Count, F, ExpressionWrapper, DurationField, Max, Q
    from core.models import Order, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

    if not pincode or len(pincode) < 3:
        return {"error": "Invalid or missing pincode.", "rto_percent": 0, "couriers": {}}

    # Time-Boxing: restrict query to the last 30 days to prevent full table scans
    time_limit = timezone.now() - timedelta(days=30)

    # Try exact match first, fall back to 3-digit prefix
    # Explicitly selecting only 'id' to optimize initial count queries
    exact_orders_qs = Order.objects.filter(
        shipping_pincode=pincode,
        created_at__gte=time_limit
    )

    if exact_orders_qs.count() >= 10:
        region_orders = exact_orders_qs
        match_type = "exact"
    else:
        region_orders = Order.objects.filter(
            shipping_pincode__startswith=pincode[:3],
            created_at__gte=time_limit
        )
        match_type = f"prefix ({pincode[:3]}xxx)"

    total = region_orders.count()
    if total == 0:
        return {
            "pincode": pincode,
            "match_type": match_type,
            "total_orders": 0,
            "rto_percent": 0,
            "couriers": {},
            "note": "No order history for this region in the last 30 days."
        }

    # Calculate RTO % without pulling records into memory
    rto_count = region_orders.filter(
        Q(current_status__in=RTO_TRANSIT_STATUSES) |
        Q(current_status__in=RTO_DELIVERED_STATUSES) |
        Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) |
        Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES)
    ).distinct().count()

    rto_percent = round((rto_count / total) * 100, 1)

    # Calculate avg delivery days per courier via database aggregations
    # No prefetching, handled 100% by the DB
    delivered_qs = region_orders.filter(
        Q(current_status__iexact='Delivered') |
        Q(fulfillments__shipment_status__iexact='Delivered'),
        fulfillments__tracking_info__company__isnull=False,
        fulfillments__tracking_events__status__iexact='Delivered'
    )

    # Group by courier directly and calculate aggregates inline
    # IMPORTANT: We MUST use .order_by('courier_name') to clear the implicit ordering 
    # from TrackingEvent.Meta.ordering, otherwise Django groups by datetime!
    agg_stats = delivered_qs.values(
        courier_name=F('fulfillments__tracking_info__company')
    ).annotate(
        avg_duration=Avg(
            ExpressionWrapper(
                F('fulfillments__tracking_events__datetime') - F('created_at'),
                output_field=DurationField()
            )
        ),
        sample_size=Count('id', distinct=True)
    ).order_by('courier_name')

    # Process and summarize the DB computation
    courier_summary = {}
    for stat in agg_stats:
        courier = stat['courier_name'].strip() if stat['courier_name'] else "Unknown"
        avg_duration_td = stat.get('avg_duration')

        days = 0
        # Postgres returns timedelta, some backends return integers/floats
        if avg_duration_td and hasattr(avg_duration_td, 'total_seconds'):
            days = avg_duration_td.total_seconds() / 86400.0
        elif isinstance(avg_duration_td, (int, float)):
            # Fallback (e.g., SQLite microseconds)
            days = float(avg_duration_td) / 86400000000.0

        if days > 0:
            # If the same courier appears (e.g. slight name variations handled), ensure it overwrites cleanly
            courier_summary[courier] = {
                "avg_delivery_days": round(days, 1),
                "sample_size": stat['sample_size'],
            }

    return {
        "pincode": pincode,
        "match_type": match_type,
        "total_orders": total,
        "rto_percent": rto_percent,
        "couriers": courier_summary,
    }


def put_order_on_hold(order_id: int, reason: str) -> str:
    """
    Place an order on hold with a detailed explanation/reason.
    Use this tool when you detect a high risk of fraud, suspicious customer metrics,
    or other issues that require manual verification.

    Args:
        order_id: The database ID of the order.
        reason: The reason why this order is being placed on hold.
    """
    from core.models import Order
    try:
        order = Order.objects.get(id=order_id)
        order.status = "On Hold"
        order.hold_reason = reason
        order.save(update_fields=["status", "hold_reason"])
        return f"Order #{order_id} successfully placed on hold. Reason: {reason}"
    except Order.DoesNotExist:
        return f"Error: Order #{order_id} not found."

