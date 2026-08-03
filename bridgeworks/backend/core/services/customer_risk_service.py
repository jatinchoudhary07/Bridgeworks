"""
customer_risk_service.py — Customer Risk Engine Service
========================================================
Computes risk profiles for customers based on their Order + Shipment history.
Uses Order.contact_phone as the customer key.

Risk Formula:
    rto_rate        = rto_count / total_orders       (40% weight)
    refusal_rate    = refusal_count / total_orders   (25% weight — from ndr_call_status)
    cod_rate        = cod_order_count / total_orders (20% weight)
    delivery_rate   = delivery_success_count / total_orders

    score = (rto_rate*40 + refusal_rate*25 + cod_rate*20 + (1 - delivery_rate)*15) * 100
    score = min(int(score), 100)

Risk Levels:
    0-30   → Low
    31-60  → Medium
    61-85  → High
    86-100 → Blocked

Key functions:
    - compute_risk_profile(org_id, phone)    → CustomerRiskProfile (created/updated)
    - bulk_recompute(org_id)                 → int count updated
    - get_risk_distribution(org_id)          → {Low: N, Medium: N, ...}
    - check_order_risk(org_id, phone)        → risk dict (for pre-dispatch check)
"""
import logging
from decimal import Decimal
from collections import defaultdict

from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)

# Constants for RTO stage detection
RTO_STAGES = ['RTO Delivered', 'RTO', 'RTO In Transit', 'Returned to Origin']
DELIVERED_STAGES = ['Delivered']

# NDR refusal patterns in ndr_call_status
REFUSAL_STATUSES = ['Refused', 'Cancel', 'Cancelled', 'Reject', 'Rejection']


def _classify_risk_level(score: int) -> str:
    if score <= 30:
        return 'Low'
    elif score <= 60:
        return 'Medium'
    elif score <= 85:
        return 'High'
    return 'Blocked'


def _get_recommended_actions(score: int) -> list:
    actions = []
    if score > 60:
        actions += ['OTP Verification', 'Manual Call Verification']
    if score > 75:
        actions += ['Premium Courier Allocation']
    if score > 85:
        actions += ['Require Prepaid Payment']
    return actions


def _calculate_score(total, rto, delivered, cod, refusals) -> int:
    if total == 0:
        return 0
    rto_rate = rto / total
    refusal_rate = refusals / total
    cod_rate = cod / total
    delivery_rate = delivered / total

    # Weights sum to 100, so this already produces a 0–100 score.
    # DO NOT multiply by 100 — that would cap every customer with even
    # a single RTO to the max score (e.g. 1/3 RTO → 23.3 × 100 = 2330 → Blocked).
    raw_score = (
        rto_rate * 40 +
        refusal_rate * 25 +
        cod_rate * 20 +
        (1 - delivery_rate) * 15
    )
    return min(int(raw_score), 100)


def compute_risk_profile(org_id: str, phone: str):
    """
    Compute or update the CustomerRiskProfile for a single customer phone.
    Fetches all orders for this phone in the org and computes risk score.

    Returns: CustomerRiskProfile instance (created or updated).
    """
    from core.models import CustomerRiskProfile
    from core.models.orders import Order

    orders = Order.objects.filter(
        org_id=org_id,
        contact_phone=phone,
    ).select_related('shipment').values(
        'id',
        'contact_phone',
        'customer_first_name',
        'customer_last_name',
        'contact_email',
        'total_price',
        'financial_status',
        'ndr_call_status',
        'shipment__current_stage',
    )

    total = 0
    rto_count = 0
    delivered_count = 0
    cod_count = 0
    refusal_count = 0
    total_value = Decimal('0')
    name = ''
    email = ''

    for o in orders:
        total += 1
        total_value += Decimal(str(o['total_price'] or 0))
        name = name or f"{o['customer_first_name'] or ''} {o['customer_last_name'] or ''}".strip()
        email = email or (o['contact_email'] or '')

        stage = (o.get('shipment__current_stage') or '').strip()
        if stage in RTO_STAGES or 'rto' in stage.lower():
            rto_count += 1
        if stage in DELIVERED_STAGES:
            delivered_count += 1

        # COD detection: payment_gateway_names / financial_status
        # Check if order was COD (Cash on Delivery)
        fs = (o.get('financial_status') or '').lower()
        if 'cod' in fs or 'cash' in fs:
            cod_count += 1

        # Refusal detection: NDR call status
        ndr = (o.get('ndr_call_status') or '').strip()
        if any(r.lower() in ndr.lower() for r in REFUSAL_STATUSES):
            refusal_count += 1

    score = _calculate_score(total, rto_count, delivered_count, cod_count, refusal_count)
    level = _classify_risk_level(score)
    actions = _get_recommended_actions(score)
    avg_value = total_value / total if total else Decimal('0')

    profile, _ = CustomerRiskProfile.objects.update_or_create(
        org_id=org_id,
        customer_phone=phone,
        defaults={
            'customer_name': name,
            'customer_email': email,
            'total_orders': total,
            'rto_count': rto_count,
            'delivery_success_count': delivered_count,
            'cod_order_count': cod_count,
            'refusal_count': refusal_count,
            'avg_order_value': avg_value,
            'risk_score': score,
            'risk_level': level,
            'recommended_actions': actions,
        }
    )
    return profile


def bulk_recompute(org_id: str, days_back: int = 90) -> int:
    """
    Recompute CustomerRiskProfile for all unique phone numbers that have had
    order activity in the last `days_back` days.

    Returns: number of profiles updated/created.
    """
    from core.models.orders import Order
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days_back)

    phones = (
        Order.objects.filter(
            org_id=org_id,
            created_at__gte=cutoff,
        )
        .exclude(contact_phone__isnull=True)
        .exclude(contact_phone='')
        .values_list('contact_phone', flat=True)
        .distinct()
    )

    count = 0
    for phone in phones:
        try:
            compute_risk_profile(org_id, phone)
            count += 1
        except Exception as e:
            logger.error(f"[RISK-ENGINE] Error computing profile for {phone} (org {org_id}): {e}")

    logger.info(f"[RISK-ENGINE] Org {org_id}: Recomputed {count} profiles")
    return count


def get_risk_distribution(org_id: str) -> dict:
    """
    Returns risk level histogram for the org.

    Returns:
        {
            Low: int,
            Medium: int,
            High: int,
            Blocked: int,
            total: int,
        }
    """
    from core.models import CustomerRiskProfile

    dist = (
        CustomerRiskProfile.objects.filter(org_id=org_id)
        .values('risk_level')
        .annotate(count=Count('id'))
    )

    result = {'Low': 0, 'Medium': 0, 'High': 0, 'Blocked': 0}
    for row in dist:
        result[row['risk_level']] = row['count']

    result['total'] = sum(result.values())
    return result


def check_order_risk(org_id: str, phone: str) -> dict:
    """
    Pre-dispatch risk check for a single phone number.
    Recomputes risk profile on-demand and returns a check result.

    Returns:
        {
            phone: str,
            risk_score: int,
            risk_level: str,
            recommended_actions: list,
            total_orders: int,
            rto_rate: float,
            delivery_rate: float,
            allow_cod: bool,      # False if Blocked or High risk
        }
    """
    profile = compute_risk_profile(org_id, phone)

    rto_rate = round((profile.rto_count / profile.total_orders) * 100, 1) if profile.total_orders else 0
    delivery_rate = round((profile.delivery_success_count / profile.total_orders) * 100, 1) if profile.total_orders else 100

    return {
        'phone': phone,
        'risk_score': profile.risk_score,
        'risk_level': profile.risk_level,
        'recommended_actions': profile.recommended_actions,
        'total_orders': profile.total_orders,
        'rto_count': profile.rto_count,
        'rto_rate': rto_rate,
        'delivery_rate': delivery_rate,
        'cod_order_count': profile.cod_order_count,
        'refusal_count': profile.refusal_count,
        'avg_order_value': float(profile.avg_order_value),
        'allow_cod': profile.risk_level not in ('High', 'Blocked'),
    }


def compute_ndr_rto_score(order) -> int:
    """
    Computes a 0-100 NDR-specific RTO risk score based on 8 weighted signals.
    Re-evaluates dynamically as customer interactions and tracking scans change.
    """
    from core.models import CustomerRiskProfile, WeatherAlert
    from django.utils import timezone

    score = 0

    # 1. Fetch Customer Risk Profile
    profile = CustomerRiskProfile.objects.filter(
        org_id=order.org_id,
        customer_phone=order.contact_phone
    ).first()

    rto_rate = 0.0
    refusal_rate = 0.0
    if profile and profile.total_orders > 0:
        rto_rate = float(profile.rto_count) / profile.total_orders
        refusal_rate = float(profile.refusal_count) / profile.total_orders

    # Signal 1: Customer Lifetime RTO Rate (Max 20 points)
    if rto_rate > 0.5:
        score += 20
    elif rto_rate > 0.3:
        score += 15
    elif rto_rate > 0.1:
        score += 10

    # Signal 2: Customer Lifetime Refusal Rate (Max 15 points)
    if refusal_rate > 0.3:
        score += 15
    elif refusal_rate > 0.1:
        score += 10

    # Signal 3: Payment Method (Max 15 points)
    # COD is riskier than Prepaid
    fs = (order.financial_status or '').lower()
    is_cod = 'cod' in fs or 'pending' in fs or 'partially_paid' in fs or 'partial payment' in str(order.tags or '').lower()
    if is_cod:
        score += 15

    # Fetch related shipment
    shipment = getattr(order, 'shipment', None)

    # Signal 4: Current Shipment Delivery Attempts (Max 15 points)
    attempts = shipment.total_delivery_attempts if shipment else 0
    if attempts >= 3:
        score += 15
    elif attempts == 2:
        score += 10
    elif attempts == 1:
        score += 5

    # Signal 5: Time Elapsed Since First Attempt (Max 10 points)
    if shipment and shipment.first_attempt_date:
        days_elapsed = (timezone.now() - shipment.first_attempt_date).days
        if days_elapsed > 5:
            score += 10
        elif days_elapsed > 3:
            score += 5

    # Signal 6: AI-Classified NDR Category (Max 15 points)
    category = order.ndr_reason_category
    if category == 'REFUSED_DELIVERY':
        score += 15
    elif category == 'ADDRESS_ISSUE':
        score += 12
    elif category in ('COD_NOT_READY', 'CUSTOMER_UNAVAILABLE'):
        score += 8
    elif category == 'PREMISES_CLOSED':
        score += 5
    elif category == 'OTHERS':
        score += 3

    # Signal 7: Weather / Regional Disruption Alert (Max 10 points)
    state = order.shipping_state or ''
    if state:
        alert = WeatherAlert.objects.filter(state_name__iexact=state.strip(), is_active=True).first()
        if alert:
            score += 10

    # Signal 8: Customer Responsiveness adjustment (Max +/- 30 points)
    call_status = (order.ndr_call_status or '').lower()
    if call_status == 'will accept':
        score -= 30  # Risk drops significantly if customer confirms reattempt
    elif call_status in ('not answering', 'switch off', 'busy', 'rejected call', 'asked to call back'):
        score += 10  # Risk rises if unreachable
    elif call_status in ('refused', 'cancelled', 'rto'):
        score += 30  # High risk if explicit cancellation

    # Clamp the final score between 0 and 100
    return max(0, min(int(score), 100))
