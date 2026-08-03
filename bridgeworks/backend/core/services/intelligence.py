"""
Order Intelligence Engine
=========================
Analyzes orders for Fraud Risk and Logistics Efficiency using
a multi-dimensional scoring strategy based on historical data.
"""
import re
import logging
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone

from core.models import Order, Fulfillment, TrackingInfo, TrackingEvent
from core.models import RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

logger = logging.getLogger(__name__)


class OrderIntelligenceBot:
    """
    The core intelligence engine. Provides:
      - Component A: Multi-Dimensional Risk Scoring
      - Component B: Logistics / Courier Recommender
    """

    # Weight configuration (must sum to 1.0)
    WEIGHT_USER_IDENTITY = 0.60
    WEIGHT_ADDRESS = 0.25
    WEIGHT_PINCODE = 0.15

    # Pincode thresholds
    PINCODE_MIN_USERS = 5
    PINCODE_RTO_THRESHOLD = 0.40  # 40%

    # Address quality indicators
    LANDMARK_KEYWORDS = ['near', 'opp', 'beside', 'behind', 'next to', 'opposite', 'adjacent']
    VAGUE_ADDRESS_MAX_LEN = 30

    # =========================================================================
    # COMPONENT A: Multi-Dimensional Risk Engine
    # =========================================================================

    def calculate_risk_score(self, order):
        """
        Returns a trust score from 0 to 100 based on:
          1. User Identity (60%)
          2. Address Intelligence (25%)
          3. Pincode Reputation (15%)
        """
        user_score = self._score_user_identity(order)
        address_score = self._score_address(order)
        pincode_score = self._score_pincode(order)

        weighted = (
            user_score * self.WEIGHT_USER_IDENTITY +
            address_score * self.WEIGHT_ADDRESS +
            pincode_score * self.WEIGHT_PINCODE
        )

        return max(0, min(100, int(round(weighted))))

    def _score_user_identity(self, order):
        """
        Searches past orders by contact_phone or email.
        - 2+ Delivered orders  -> 100 (loyal customer override)
        - Any RTO/Cancelled    -> 0
        - 1 Delivered          -> 70
        - No history           -> 40 (new customer, neutral)
        """
        # Build a filter for "same customer" (by phone or email)
        customer_q = Q()
        if order.contact_phone:
            customer_q |= Q(contact_phone=order.contact_phone)
        if order.contact_email:
            customer_q |= Q(contact_email=order.contact_email)

        if not customer_q:
            return 40  # No identifiable info, treat as new

        # Exclude this order itself, scope to same org
        past_orders = Order.objects.filter(
            customer_q,
            org_id=order.org_id,
        ).exclude(pk=order.pk)

        if not past_orders.exists():
            return 40  # Brand new customer

        # Check for RTO / Cancelled history
        rto_statuses_lower = [s.lower() for s in RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES]

        has_rto = past_orders.filter(
            Q(status__iexact='Cancelled') |
            Q(current_status__in=RTO_TRANSIT_STATUSES) |
            Q(current_status__in=RTO_DELIVERED_STATUSES) |
            Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) |
            Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES)
        ).distinct().exists()

        if has_rto:
            return 0  # Past RTO/Cancelled = high risk

        # Count delivered orders
        delivered_count = past_orders.filter(
            Q(current_status__iexact='Delivered') |
            Q(fulfillments__shipment_status__iexact='Delivered')
        ).distinct().count()

        if delivered_count >= 2:
            return 100  # Loyal customer
        elif delivered_count == 1:
            return 70   # One successful delivery
        else:
            return 40   # Has history but no deliveries yet

    def _score_address(self, order):
        """
        Analyzes the shipping_address string for quality indicators.
        - Contains house/flat number -> 80
        - Contains landmark keywords -> 60
        - Very short/vague (<30 chars) -> 20
        - Otherwise -> 50
        """
        address = (order.shipping_address or '').strip()

        if not address:
            return 20  # No address at all

        if len(address) < self.VAGUE_ADDRESS_MAX_LEN:
            return 20  # Too short, likely vague

        # Check for house/flat numbers (digits in the address)
        has_number = bool(re.search(r'\d+', address))

        # Check for landmark keywords
        address_lower = address.lower()
        has_landmark = any(kw in address_lower for kw in self.LANDMARK_KEYWORDS)

        if has_number:
            return 80
        elif has_landmark:
            return 60
        else:
            return 50

    def _score_pincode(self, order):
        """
        Analyzes pincode reputation based on historical RTO rate.
        - < 5 unique users in this pincode -> 50 (insufficient data)
        - >= 5 users AND RTO rate > 40% -> 10 (high risk area)
        - >= 5 users AND RTO rate <= 40% -> 80 (good area)
        """
        pincode = (order.shipping_pincode or '').strip()
        if not pincode:
            return 50  # No pincode, neutral

        # Get all orders from the same pincode and same org
        pincode_orders = Order.objects.filter(
            shipping_pincode=pincode,
            org_id=order.org_id,
        ).exclude(pk=order.pk)

        # Count unique users (by phone)
        unique_users = pincode_orders.exclude(
            contact_phone__isnull=True
        ).exclude(
            contact_phone=''
        ).values('contact_phone').distinct().count()

        if unique_users < self.PINCODE_MIN_USERS:
            return 50  # Insufficient data, neutral

        total_orders = pincode_orders.count()
        if total_orders == 0:
            return 50

        # Count RTO orders
        rto_count = pincode_orders.filter(
            Q(current_status__in=RTO_TRANSIT_STATUSES) |
            Q(current_status__in=RTO_DELIVERED_STATUSES) |
            Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) |
            Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES)
        ).distinct().count()

        rto_rate = rto_count / total_orders

        if rto_rate > self.PINCODE_RTO_THRESHOLD:
            return 10  # High risk area
        else:
            return 80  # Good area

    # =========================================================================
    # COMPONENT B: Logistics Recommender
    # =========================================================================

    def recommend_courier(self, order):
        """
        Recommends the best courier for this order's region based on
        historical delivery speed.

        Returns a dict: {"courier": "BlueDart", "avg_days": 3.2}
        or None if insufficient data.
        """
        pincode = (order.shipping_pincode or '').strip()
        if not pincode or len(pincode) < 3:
            return None

        region_prefix = pincode[:3]

        # Find all delivered orders in the same region (same 3-digit prefix)
        delivered_orders = Order.objects.filter(
            org_id=order.org_id,
            shipping_pincode__startswith=region_prefix,
        ).filter(
            Q(current_status__iexact='Delivered') |
            Q(fulfillments__shipment_status__iexact='Delivered')
        ).distinct()

        if not delivered_orders.exists():
            return None

        # For each order, find the courier (from TrackingInfo) and delivery time
        courier_stats = {}  # {courier_name: [delivery_days_list]}

        for o in delivered_orders.prefetch_related(
            'fulfillments__tracking_info',
            'fulfillments__tracking_events',
        ):
            if not o.created_at:
                continue

            for fulfillment in o.fulfillments.all():
                # Get courier name
                tracking_info = fulfillment.tracking_info.first()
                if not tracking_info or not tracking_info.company:
                    continue

                courier_name = tracking_info.company.strip()
                if not courier_name:
                    continue

                # Get delivered event datetime
                delivered_event = fulfillment.tracking_events.filter(
                    status__iexact='Delivered'
                ).order_by('-datetime').first()

                if not delivered_event:
                    continue

                # Calculate delivery days
                delta = delivered_event.datetime - o.created_at
                delivery_days = delta.total_seconds() / 86400  # Convert to days

                if delivery_days <= 0:
                    continue

                if courier_name not in courier_stats:
                    courier_stats[courier_name] = []
                courier_stats[courier_name].append(delivery_days)

        if not courier_stats:
            return None

        # Calculate averages and pick the best
        best_courier = None
        best_avg = float('inf')

        for courier, days_list in courier_stats.items():
            avg = sum(days_list) / len(days_list)
            if avg < best_avg:
                best_avg = avg
                best_courier = courier

        return {
            "courier": best_courier,
            "avg_days": round(best_avg, 1),
            "sample_size": len(courier_stats.get(best_courier, [])),
        }


# =============================================================================
# PHASE 3: The Bot Automation
# =============================================================================

def run_order_bot(order_id):
    """
    The main entry point. Fetches an order, runs the Intelligence Bot,
    and persists the results.

    Returns a dict with the analysis results.
    """
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(f"run_order_bot: Order {order_id} not found.")
        return None

    bot = OrderIntelligenceBot()

    # 1. Calculate Risk Score
    risk_score = bot.calculate_risk_score(order)

    # 2. Get Courier Recommendation
    courier_rec = bot.recommend_courier(order)

    # 3. Apply Smart Action Logic
    if risk_score > 75:
        flag = 'GREEN'
        courier_text = f"Assign {courier_rec['courier']} (~{courier_rec['avg_days']}d)" if courier_rec else "No courier data for region"
        suggestion = f"Low Risk (Score: {risk_score}). {courier_text}."

        # Auto-confirm if not already confirmed or cancelled
        if order.status not in ('Confirmed', 'Cancelled', 'Batched'):
            order.status = 'Confirmed'
            order.confirmed_at = timezone.now()

    elif risk_score >= 30:
        flag = 'YELLOW'
        suggestion = f"Medium Risk (Score: {risk_score}). Verify via WhatsApp/Call before confirming."
        if courier_rec:
            suggestion += f" If confirmed, assign {courier_rec['courier']} (~{courier_rec['avg_days']}d)."

    else:
        flag = 'RED'
        suggestion = f"High Risk (Score: {risk_score}). Recommend converting to Prepaid or Partial COD."
        if courier_rec:
            suggestion += f" Region courier: {courier_rec['courier']} (~{courier_rec['avg_days']}d)."

    # 4. Persist results
    order.risk_score = risk_score
    order.intelligence_flag = flag
    order.system_suggestion = suggestion
    order.save(update_fields=[
        'risk_score', 'intelligence_flag', 'system_suggestion',
        'status', 'confirmed_at',
    ])

    logger.info(f"Order #{order.order_number}: Score={risk_score}, Flag={flag}")

    return {
        "order_number": order.order_number,
        "risk_score": risk_score,
        "flag": flag,
        "suggestion": suggestion,
        "courier_recommendation": courier_rec,
    }
