"""
delivery_services.py — Core Business Logic for the Delivery Module
==================================================================
Services:
  1. Cost Engine: Calculate true cost per shipment
  2. COD Remittance Tracker: Match collected vs expected COD
  3. Reconciliation Engine: Cross-match system vs courier vs payment data
  4. NDR Analytics: Reattempt success % and RTO conversion %
  5. Shipment Sync: Auto-populate Shipment from Order/Fulfillment data
"""

import logging
from decimal import Decimal
from datetime import timedelta

from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, DecimalField, IntegerField, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Order, Fulfillment, TrackingInfo, TrackingEvent
from core.models.delivery import Shipment, ShipmentCost, CODRemittance, FreightInvoice
from core.models.constants import NDR_STATUSES, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

logger = logging.getLogger(__name__)


# ==============================================================================
# HELPER: Derive payment type from Order
# ==============================================================================
def derive_payment_type(order):
    """Derive payment type string from Order's financial_status and gateway names using OPM detection."""
    from core.utils.payment_utils import derive_payment_type_from_fields
    return derive_payment_type_from_fields(
        order.payment_gateway_names,
        order.financial_status,
        getattr(order, 'tags', ''),
        getattr(order, 'raw_data', None)
    )


# ==============================================================================
# HELPER: Normalize courier name to standard choices
# ==============================================================================
def normalize_courier(company_name):
    """Map TrackingInfo.company to standard courier partner choices."""
    if not company_name:
        return 'Other'
    name = company_name.lower().strip()
    if 'bluedart' in name or 'blue dart' in name:
        return 'Bluedart'
    if 'delhivery' in name:
        return 'Delhivery'
    if 'shiprocket' in name or 'clickpost' in name or 'shipway' in name:
        return 'Aggregator'
    return 'Other'


# ==============================================================================
# HELPER: Map tracking status to Shipment stage
# ==============================================================================
def map_status_to_stage(current_status):
    """Map Order.current_status to Shipment.current_stage."""
    if not current_status:
        return 'Order'
    status = current_status.lower()
    if 'undelivered' in status or 'attempted' in status:
        return 'Undelivered'
    if 'delivered' in status and 'rto' not in status and 'return' not in status:
        return 'Delivered'
    if any(s.lower() in status for s in ['rto', 'return']):
        return 'RTO'
    if 'out for delivery' in status or 'ofd' in status:
        return 'OFD'
    if 'transit' in status or 'dispatched' in status:
        return 'In Transit'
    if 'picked' in status:
        return 'Picked'
    if 'manifested' in status or 'booked' in status:
        return 'Manifested'
    if 'packed' in status or 'packaged' in status:
        return 'Packed'
    if 'lost' in status:
        return 'Lost'
    return 'Order'


# ==============================================================================
# 1. SHIPMENT SYNC SERVICE
# ==============================================================================
def sync_shipment_from_order(order):
    """
    Create or update a Shipment record from an Order and its Fulfillment/Tracking data.
    Called by signals and the backfill management command.
    Returns the Shipment instance or None if no tracking data exists.

    For multi-fulfillment orders, picks the most recently created fulfillment
    that has a non-empty tracking number. This avoids the non-determinism of
    .first() which was silently skipping orders in production.
    """
    # Pick the best fulfillment: most recent one with a real tracking number
    fulfillment = None
    tracking_info = None
    for f in order.fulfillments.order_by('-created_at'):
        ti = f.tracking_info.exclude(number='').filter(number__isnull=False).first()
        if ti and ti.number:
            fulfillment = f
            tracking_info = ti
            break

    if not fulfillment or not tracking_info:
        return None

    # Get or create Shipment
    shipment, created = Shipment.objects.get_or_create(
        order=order,
        defaults={'org_id': order.org_id}
    )

    # Update from tracking info
    shipment.org_id = order.org_id
    shipment.awb_number = tracking_info.number or ''
    shipment.courier_partner = normalize_courier(tracking_info.company)
    
    new_payment_type = derive_payment_type(order)
    if shipment.pk and shipment.payment_type in ['COD', 'Partially Paid'] and new_payment_type == 'PrePaid':
        # Do not overwrite COD/Partially Paid to PrePaid just because the order was marked paid later
        pass
    else:
        shipment.payment_type = new_payment_type
        
    shipment.current_stage = map_status_to_stage(order.current_status)

    # Dispatch date: strictly from fulfillment created_at
    if fulfillment.created_at:
        shipment.dispatch_date = fulfillment.created_at

    # Delivery date: from tracking events (earliest delivered event)
    delivered_event = TrackingEvent.objects.filter(
        fulfillment__order=order,
        status__icontains='delivered'
    ).exclude(
        status__icontains='rto'
    ).exclude(
        status__icontains='return'
    ).exclude(
        status__icontains='undelivered'
    ).order_by('datetime').first()

    if delivered_event:
        shipment.delivery_date = delivered_event.datetime

    # NDR / attempt counting
    ndr_events = TrackingEvent.objects.filter(
        fulfillment__order=order
    ).filter(
        Q(status__in=NDR_STATUSES) | Q(details__in=NDR_STATUSES)
    )
    shipment.total_delivery_attempts = ndr_events.count()
    first_attempt = ndr_events.order_by('datetime').first()
    if first_attempt:
        shipment.first_attempt_date = first_attempt.datetime
        shipment.ndr_reason = first_attempt.status

    shipment.save()
    
    # Run fake attempt/fraud audit check
    try:
        from core.services.fraud_detector import audit_shipment_attempts
        audit_shipment_attempts(shipment)
    except Exception as e:
        logger.error(f"Failed to audit shipment {shipment.id} for fake attempts: {e}")

    # Try to auto-generate COD Remittance if applicable
    if shipment.current_stage == 'Delivered' and shipment.payment_type in ['COD', 'Partially Paid']:
        sync_cod_remittance_from_shipment(shipment)
        
    return shipment


# ==============================================================================
# 2. COST ENGINE
# ==============================================================================
def get_rto_probability(courier_partner, zone='National', payment_type='PrePaid'):
    """
    Calculate historical RTO probability for a given courier/zone/payment_type combo.
    Returns a Decimal between 0 and 1.
    """
    total = Shipment.objects.filter(
        courier_partner=courier_partner,
        zone=zone,
        payment_type=payment_type,
        current_stage__in=['Delivered', 'RTO'],
    ).count()

    if total == 0:
        # Fallback: assume 10% RTO for COD, 3% for PrePaid
        return Decimal('0.10') if payment_type == 'COD' else Decimal('0.03')

    rto_count = Shipment.objects.filter(
        courier_partner=courier_partner,
        zone=zone,
        payment_type=payment_type,
        current_stage='RTO',
    ).count()

    return Decimal(str(round(rto_count / total, 4)))


def calculate_true_cost(shipment_cost):
    """
    True Cost Per Order = Forward Cost + (RTO probability × RTO cost)
    Updates the ShipmentCost.true_cost field in-place.
    """
    shipment = shipment_cost.shipment
    rto_prob = get_rto_probability(
        shipment.courier_partner,
        shipment.zone,
        shipment.payment_type,
    )
    shipment_cost.true_cost = (
        shipment_cost.forward_cost +
        (rto_prob * shipment_cost.rto_cost)
    )
    shipment_cost.save(update_fields=['true_cost'])
    return shipment_cost.true_cost


# ==============================================================================
# 3. COD REMITTANCE TRACKER
# ==============================================================================
def calculate_expected_remittance_date(delivery_date):
    """
    Apply the 15-day fortnightly cycle:
    - Cycle 1: Deliveries 1st-15th -> Expected Last Day of the same month
    - Cycle 2: Deliveries 16th-End -> Expected 15th of the next month
    """
    import calendar
    from datetime import date
    if isinstance(delivery_date, date):
        d_date = delivery_date
    else:
        d_date = delivery_date.date()
        
    year = d_date.year
    month = d_date.month
    
    if d_date.day <= 15:
        # Last day of current month
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    else:
        # 15th of next month
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year
        return date(next_year, next_month, 15)


def get_prepaid_amount_from_shopify(order):
    """
    Fetch transactions for the order and find the prepaid amount (usually 'sale' kind).
    """
    try:
        from core.models import ShopCredentials
        from core.utils import _get_decrypted_credentials
        import requests
        
        shop = ShopCredentials.objects.filter(organization_id=order.org_id).first()
        if not shop: 
            # Fallback for old data where org_id might not match organization_id
            shop = ShopCredentials.objects.first()
            
        if not shop: return Decimal('0')
        
        creds = _get_decrypted_credentials(shop.organization_id)
        if not creds: return Decimal('0')
        
        shop_url = creds['shop_url'].rstrip('/')
        api_key = creds['api_key']
        password = creds['password']
        api_version = creds['api_version']
        
        url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders/{order.shopify_id}/transactions.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            txns = resp.json().get('transactions', [])
            # For PPCOD, 'sale' is the prepaid part
            for t in txns:
                if t.get('kind') == 'sale' and t.get('status') == 'success' and 'razorpay' in t.get('gateway', '').lower():
                    return Decimal(str(t.get('amount', '0')))
        return Decimal('0')
    except Exception:
        return Decimal('0')


def sync_cod_remittance_from_shipment(shipment):
    """
    Ensure CODRemittance exists for COD shipments that are Delivered.
    """
    if shipment.payment_type not in ['COD', 'Partially Paid']:
        return None
        
    if shipment.current_stage != 'Delivered':
        return None

    # Use delivery_date, fall back to dispatch_date, then order.created_at
    ref_date = shipment.delivery_date or shipment.dispatch_date
    if not ref_date and hasattr(shipment, 'order') and shipment.order:
        ref_date = shipment.order.created_at
    if not ref_date:
        return None

    expected_date = calculate_expected_remittance_date(ref_date)
    
    # Calculate expected amount for COD
    order_total = Decimal(str(shipment.order.total_price or '0'))
    expected_amount = order_total
    
    if shipment.payment_type == 'Partially Paid':
        # 1. Try total_outstanding from raw_data (works if order is still 'partially_paid')
        raw_data = shipment.order.raw_data or {}
        outstanding = raw_data.get('total_outstanding')
        if outstanding and float(outstanding) > 0:
            expected_amount = Decimal(str(outstanding))
        else:
            # 2. Fallback: Fetch from Shopify transactions to find the split
            prepaid = get_prepaid_amount_from_shopify(shipment.order)
            if prepaid > 0:
                expected_amount = order_total - prepaid
            else:
                # 3. Last resort: Heuristic (e.g., check tags for amount)
                # For now, we stay at order_total if nothing found
                pass

    # Check if a Remittance record exists for this shipment
    remittance, created = CODRemittance.objects.get_or_create(
        shipment=shipment,
        defaults={
            'expected_amount': expected_amount,
            'expected_remittance_date': expected_date,
            'status': 'Pending'
        }
    )
    
    # Always ensure the amount is correct if it was previously set to full price
    if not created:
        if remittance.expected_amount != expected_amount and expected_amount > 0:
            remittance.expected_amount = expected_amount
            remittance.save(update_fields=['expected_amount'])
        if remittance.expected_remittance_date != expected_date:
            remittance.expected_remittance_date = expected_date
            remittance.save(update_fields=['expected_remittance_date'])
        
    return remittance


def check_cod_remittances(org_id):
    """
    Scan all pending COD remittances for an org.
    Returns summary of overdue, mismatched, and pending counts.
    """
    today = timezone.now().date()
    remittances = CODRemittance.objects.filter(
        shipment__org_id=org_id,
        status__in=['Pending', 'Overdue'],
    )

    overdue_count = 0
    mismatch_count = 0
    pending_amount = Decimal('0')

    for r in remittances:
        if r.expected_remittance_date and r.expected_remittance_date < today:
            if r.status != 'Overdue':
                r.status = 'Overdue'
                r.delay_days = (today - r.expected_remittance_date).days
                r.save(update_fields=['status', 'delay_days'])
            overdue_count += 1

        if r.received_amount > 0 and r.received_amount != r.expected_amount:
            if r.status != 'Mismatch':
                r.status = 'Mismatch'
                r.save(update_fields=['status'])
            mismatch_count += 1

        pending_amount += (r.expected_amount - r.received_amount)

    return {
        'total_pending': remittances.count(),
        'overdue_count': overdue_count,
        'mismatch_count': mismatch_count,
        'pending_amount': float(pending_amount),
    }


def check_freight_invoices(org_id):
    """
    Scan all pending freight invoices for an org.
    Updates status to 'Overdue' if due_date has passed.
    """
    today = timezone.now().date()
    invoices = FreightInvoice.objects.filter(
        org_id=org_id,
        status='Pending',
        due_date__lt=today
    )
    count = invoices.update(status='Overdue')
    return count


# ==============================================================================
# 4. RECONCILIATION ENGINE
# ==============================================================================
def reconcile_orders(org_id, start_date=None, end_date=None):
    """
    Cross-match: System Orders vs Courier Data vs Payment Data.
    Flags anomalies.
    """
    filters = Q(org_id=org_id)
    if start_date:
        filters &= Q(dispatch_date__date__gte=start_date)
    if end_date:
        filters &= Q(dispatch_date__date__lte=end_date)

    shipments = Shipment.objects.filter(filters).select_related('order', 'cost')

    flags = {
        'missing_shipments': [],     # Orders with no shipment record
        'extra_billing': [],         # Overbilled shipments
        'weight_mismatch': [],       # Weight discrepancy charges > 0
        'fake_rto_charges': [],      # RTO cost charged but order was delivered
        'delivered_unpaid_cod': [],   # Delivered COD but no remittance received
    }

    for shipment in shipments:
        cost = getattr(shipment, 'cost', None)

        # Extra billing detection
        if cost and cost.is_overbilled:
            flags['extra_billing'].append({
                'awb': shipment.awb_number,
                'order_number': shipment.order.order_number,
                'expected': float(cost.expected_cost),
                'actual': float(cost.actual_billed_cost),
                'diff': float(cost.overbilling_amount),
            })

        # Weight mismatch
        if cost and cost.weight_discrepancy_charges > 0:
            flags['weight_mismatch'].append({
                'awb': shipment.awb_number,
                'order_number': shipment.order.order_number,
                'charges': float(cost.weight_discrepancy_charges),
            })

        # Fake RTO charges (Delivered but RTO cost charged)
        if cost and cost.rto_cost > 0 and shipment.current_stage == 'Delivered':
            flags['fake_rto_charges'].append({
                'awb': shipment.awb_number,
                'order_number': shipment.order.order_number,
                'rto_cost': float(cost.rto_cost),
            })

        # Delivered COD but no remittance
        if (shipment.current_stage == 'Delivered' and
                shipment.payment_type in ['COD', 'Partially Paid']):
            has_remittance = shipment.remittances.filter(
                status='Received'
            ).exists()
            if not has_remittance:
                flags['delivered_unpaid_cod'].append({
                    'awb': shipment.awb_number,
                    'order_number': shipment.order.order_number,
                    'amount': float(shipment.order.total_price or 0),
                })

    # Missing shipments: Orders with fulfillment but no Shipment record
    missing_orders = Order.objects.filter(
        org_id=org_id,
        fulfillments__isnull=False,
        shipment__isnull=True,
    ).distinct()

    if start_date:
        missing_orders = missing_orders.filter(created_at__date__gte=start_date)
    if end_date:
        missing_orders = missing_orders.filter(created_at__date__lte=end_date)

    flags['missing_shipments'] = list(
        missing_orders.values_list('order_number', flat=True)[:100]
    )

    return {
        'flags': flags,
        'summary': {
            'missing_shipments': len(flags['missing_shipments']),
            'extra_billing': len(flags['extra_billing']),
            'weight_mismatch': len(flags['weight_mismatch']),
            'fake_rto_charges': len(flags['fake_rto_charges']),
            'delivered_unpaid_cod': len(flags['delivered_unpaid_cod']),
        }
    }


# ==============================================================================
# 5. NDR ANALYTICS SERVICE
# ==============================================================================
def get_ndr_analytics(org_id, start_date=None, end_date=None):
    """
    Compute NDR reattempt success %, RTO conversion %, and breakdown by reason.
    Leverages existing Order.is_ndr and Order.ndr_call_status fields.
    """
    filters = Q(org_id=org_id)
    if start_date:
        filters &= Q(created_at__date__gte=start_date)
    if end_date:
        filters &= Q(created_at__date__lte=end_date)

    # All orders that were ever NDR (have NDR tracking events)
    ndr_orders = Order.objects.filter(filters).filter(
        Q(is_ndr=True) |
        Q(fulfillments__tracking_events__status__in=NDR_STATUSES)
    ).distinct()

    total_ndr = ndr_orders.count()
    if total_ndr == 0:
        return {
            'total_ndr': 0,
            'reattempt_success_pct': 0,
            'rto_conversion_pct': 0,
            'delivered_after_ndr': 0,
            'rto_from_ndr': 0,
            'pending_ndr': 0,
        }

    # Delivered after NDR (success)
    delivered_after_ndr = ndr_orders.filter(
        current_status='Delivered'
    ).count()

    # RTO from NDR
    rto_statuses = RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES
    rto_from_ndr = ndr_orders.filter(
        current_status__in=rto_statuses
    ).count()

    # Still pending NDR
    pending_ndr = ndr_orders.filter(is_ndr=True).count()

    reattempt_success_pct = round((delivered_after_ndr / total_ndr) * 100, 1) if total_ndr > 0 else 0
    rto_conversion_pct = round((rto_from_ndr / total_ndr) * 100, 1) if total_ndr > 0 else 0

    return {
        'total_ndr': total_ndr,
        'reattempt_success_pct': reattempt_success_pct,
        'rto_conversion_pct': rto_conversion_pct,
        'delivered_after_ndr': delivered_after_ndr,
        'rto_from_ndr': rto_from_ndr,
        'pending_ndr': pending_ndr,
    }

# ==============================================================================
# 6. PDF INVOICE PARSING
# ==============================================================================

import re
AWB_RE = re.compile(r'^\d{11}$')  # Bluedart AWBs are exactly 11 digits
INV_RE = re.compile(r'Invoice No\.[\s:]+([A-Z0-9]+)')
INV_DATE_RE = re.compile(r'Invoice Date[\s:]+([0-9]{2}/[0-9]{2}/[0-9]{4})')
GRAND_TOTAL_RE = re.compile(r'Grand Total\s+([0-9,.]+)', re.IGNORECASE)
FUEL_RE = re.compile(r'(?:Fuel Surcharge|FSC)\s+([0-9,.]+)', re.IGNORECASE)
CAF_RE = re.compile(r'(?:Currency Adjustment Factor|CAF)\s+([0-9,.]+)', re.IGNORECASE)

def parse_bluedart_pdf(pdf_path):
    """
    Parse a Bluedart freight invoice PDF.
    Returns a tuple: (invoice_number, invoice_date_str, summary_dict, results)
    """
    try:
        import pdfplumber
    except ImportError:
        raise Exception("pdfplumber is not installed. Run: pip install pdfplumber")

    results = []
    invoice_number = None
    invoice_date_str = None
    
    summary_dict = {
        'grand_total': Decimal('0'),
        'fuel_total': Decimal('0'),
        'caf_total': Decimal('0'),
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''

            if not invoice_number:
                m = INV_RE.search(text)
                if m:
                    invoice_number = m.group(1)
            
            if not invoice_date_str:
                md = INV_DATE_RE.search(text)
                if md:
                    invoice_date_str = md.group(1)
                    
            m_gt = GRAND_TOTAL_RE.search(text)
            if m_gt:
                summary_dict['grand_total'] = Decimal(m_gt.group(1).replace(',', ''))
            m_fuel = FUEL_RE.search(text)
            if m_fuel:
                summary_dict['fuel_total'] = Decimal(m_fuel.group(1).replace(',', ''))
            m_caf = CAF_RE.search(text)
            if m_caf:
                summary_dict['caf_total'] = Decimal(m_caf.group(1).replace(',', ''))

            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                
                # Robustly search first 3 rows for the column containing 'AWB' to find header row
                header_idx = None
                for idx, r in enumerate(table[:3]):
                    if r and any('AWB' in str(cell) for cell in r if cell):
                        header_idx = idx
                        break
                
                if header_idx is None:
                    continue

                for data_row in table[header_idx + 1:]:
                    if not data_row:
                        continue

                    cols = [str(c or '').split('\n') for c in data_row]

                    side_configs = [
                        (2, 6, 3, 4, 5),  # Side 1: AWB, Amount, Dest, Type, Chrg Wt
                        (9, 13, 10, 11, 12)  # Side 2: AWB, Amount, Dest, Type, Chrg Wt
                    ]

                    for awb_col, amt_col, dest_col, type_col, chrg_wt_col in side_configs:
                        awbs = cols[awb_col] if len(cols) > awb_col else []
                        amts = cols[amt_col] if len(cols) > amt_col else []
                        dests = cols[dest_col] if len(cols) > dest_col else []
                        types = cols[type_col] if len(cols) > type_col else []
                        chrg_wts = cols[chrg_wt_col] if len(cols) > chrg_wt_col else []

                        for idx, (awb_val, amt_val) in enumerate(zip(awbs, amts)):
                            awb_val = awb_val.strip()
                            amt_val = amt_val.strip().replace(',', '')
                            
                            # Clean AWB by keeping only digits for checking
                            clean_awb = re.sub(r'\D', '', awb_val)

                            if not AWB_RE.match(clean_awb) or not amt_val:
                                continue

                            try:
                                forward_cost = Decimal(amt_val)
                            except Exception:
                                continue

                            # Append 'R' suffix if original AWB starts with (R) (RTO / return legs)
                            is_return = False
                            if '(R)' in awb_val.upper():
                                is_return = True
                                clean_awb = clean_awb + 'R'

                            dest_val = dests[idx] if idx < len(dests) else (dests[0] if dests else '')
                            type_val = types[idx] if idx < len(types) else (types[0] if types else '')
                            chrg_wt_val = chrg_wts[idx] if idx < len(chrg_wts) else (chrg_wts[0] if chrg_wts else '0.5')

                            try:
                                chrg_wt_dec = Decimal(chrg_wt_val.strip())
                            except Exception:
                                chrg_wt_dec = Decimal('0.5')

                            results.append({
                                'awb': clean_awb,
                                'awb_original': awb_val,
                                'forward_cost': forward_cost,
                                'dest': dest_val.strip(),
                                'type': type_val.strip(),
                                'chrg_wt': chrg_wt_dec,
                                'is_return': is_return,
                            })

    return invoice_number, invoice_date_str, summary_dict, results


def sync_prepaid_remittance(order):
    """
    Ensure PrepaidRemittance exists for prepaid shipments/orders that are Paid.
    Uses PaymentGatewayFeeRule configurations to calculate gateway fee.
    """
    payment_type = derive_payment_type(order)
    if payment_type != 'PrePaid' or order.financial_status != 'paid':
        return None

    import json
    from datetime import date, datetime
    from core.models.delivery import PrepaidRemittance, PaymentGatewayFeeRule

    gws = order.payment_gateway_names or []
    if isinstance(gws, str):
        try:
            gws = json.loads(gws)
        except Exception:
            gws = [gws]
    elif not isinstance(gws, list):
        gws = [gws]
        
    gateway_name = gws[0] if gws else 'Shopify Payments'
    if not gateway_name:
        gateway_name = 'Shopify Payments'

    # Check if any rules exist for this org, if not, seed defaults
    if not PaymentGatewayFeeRule.objects.filter(org_id=order.org_id).exists():
        defaults = [
            ('Razorpay', 'percentage', 2.0),
            ('PayU', 'percentage', 2.2),
            ('PhonePe', 'percentage', 1.8),
            ('Easebuzz', 'percentage', 2.0),
            ('Cashfree', 'percentage', 1.75),
            ('GoKwik', 'percentage', 2.0),
        ]
        for gw, f_type, val in defaults:
            PaymentGatewayFeeRule.objects.get_or_create(
                org_id=order.org_id,
                gateway_name=gw,
                defaults={'fee_type': f_type, 'fee_value': Decimal(str(val)), 'active': True}
            )

    # Find matching rule case-insensitively
    rule = PaymentGatewayFeeRule.objects.filter(
        org_id=order.org_id,
        gateway_name__iexact=gateway_name,
        active=True
    ).first()

    if not rule:
        fee_type = 'percentage'
        fee_value = Decimal('2.0')
        settlement_days = 2
    else:
        fee_type = rule.fee_type
        fee_value = rule.fee_value
        settlement_days = rule.settlement_days

    gross_amount = Decimal(str(order.total_price or '0'))
    if fee_type == 'percentage':
        gateway_fee = (gross_amount * fee_value) / Decimal('100.0')
    else:
        gateway_fee = fee_value
    
    # Cap gateway fee at gross_amount
    gateway_fee = min(gateway_fee, gross_amount)
    net_amount = gross_amount - gateway_fee

    if order.created_at:
        if isinstance(order.created_at, (date, datetime)):
            ref_date = order.created_at
        else:
            try:
                ref_date = datetime.strptime(str(order.created_at).split('T')[0], '%Y-%m-%d')
            except Exception:
                ref_date = date.today()
    else:
        ref_date = date.today()

    if isinstance(ref_date, datetime):
        ref_date = ref_date.date()
    
    expected_settlement_date = ref_date + timedelta(days=settlement_days)

    remittance, created = PrepaidRemittance.objects.get_or_create(
        order=order,
        defaults={
            'order_number': order.order_number or f"#{order.id}",
            'gateway_name': gateway_name,
            'gross_amount': gross_amount,
            'gateway_fee': gateway_fee,
            'net_amount': net_amount,
            'expected_settlement_date': expected_settlement_date,
            'status': 'Pending'
        }
    )

    if not created and remittance.status == 'Pending':
        remittance.order_number = order.order_number or f"#{order.id}"
        remittance.gateway_name = gateway_name
        remittance.gross_amount = gross_amount
        remittance.gateway_fee = gateway_fee
        remittance.net_amount = net_amount
        remittance.expected_settlement_date = expected_settlement_date
        remittance.save()

    return remittance

