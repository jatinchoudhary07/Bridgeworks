from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Exists, OuterRef, Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from .models import Order, TrackingInfo, TrackingEvent, ReturnRequest
from .models.constants import NDR_STATUSES, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES

def categorize_payment(order_data, cod_qs_dict, partial_qs_dict, explicit_prepaid_qs_dict):
    gateways = str(order_data.get('payment_gateway_names', [])).lower()
    fin_status = str(order_data.get('financial_status', '')).lower()
    
    if 'partially_paid' in fin_status: return 'partial'
    if 'ppcod' in gateways: return 'partial'
    if 'gokwik ppcod' in gateways: return 'partial'
    if 'razorpay' in gateways and 'partially_paid' in fin_status: return 'partial'
    if 'cash' in gateways or 'cod' in gateways: return 'cod'
    if 'pending' in fin_status and not ('paid' in fin_status): return 'cod'
    if 'paid' in fin_status and not 'partially' in fin_status: return 'prepaid'
    return 'prepaid'

def safe_parse(dt_str):
    if not dt_str: return None
    dt = parse_datetime(dt_str)
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def build_aggregation_payload(base_orders, global_start, global_end, overrides=None, extract_target=None):
    if overrides is None: overrides = {}

    def get_bounds(prefix):
        s_val = overrides.get(f'{prefix}_start')
        e_val = overrides.get(f'{prefix}_end')
        if s_val and e_val:
            return safe_parse(s_val), safe_parse(e_val)
        return global_start, global_end

    aov_s, aov_e = global_start, global_end
    status_s, status_e = get_bounds('status_summary')
    full_s, full_e = get_bounds('fulfillment')
    ndr_s, ndr_e = get_bounds('ndr')
    ret_s, ret_e = get_bounds('returns')
    exc_s, exc_e = get_bounds('exchanges')

    # Query Helpers
    def apply_base(qs, s, e):
        if s and e: return qs.filter(created_at__gte=s, created_at__lte=e)
        elif s: return qs.filter(created_at__gte=s)
        return qs

    def build_fast_cohort(qs):
        return qs.annotate(
            has_awb=Exists(TrackingInfo.objects.filter(
                fulfillment__order=OuterRef('pk'),
                number__isnull=False
            ).exclude(number=''))
        ).values(
            'id', 'order_number', 'created_at', 'customer_first_name', 'customer_last_name',
            'total_price', 'payment_gateway_names', 'financial_status', 'status',
            'internal_fulfillment_status', 'current_status', 'is_ndr', 'has_awb'
        )

    # 1. AOV Query
    aov_data = build_fast_cohort(apply_base(base_orders, aov_s, aov_e))
    # 2. Status Query
    status_data = build_fast_cohort(apply_base(base_orders, status_s, status_e))
    # 3. Fulfillment Query
    full_data = build_fast_cohort(apply_base(base_orders, full_s, full_e))

    # 4. NDR Tracking
    ndr_qs = base_orders.filter(is_ndr=True)
    if ndr_s and ndr_e:
        date_filter_qs = TrackingEvent.objects.filter(fulfillment__order=OuterRef('pk'), datetime__date__gte=ndr_s.date(), datetime__date__lte=ndr_e.date())
        ndr_qs = ndr_qs.filter(Exists(date_filter_qs))
    elif ndr_s:
        date_filter_qs = TrackingEvent.objects.filter(fulfillment__order=OuterRef('pk'), datetime__date__gte=ndr_s.date())
        ndr_qs = ndr_qs.filter(Exists(date_filter_qs))
    
    ndr_data = ndr_qs.values('id', 'order_number', 'created_at', 'customer_first_name', 'customer_last_name', 'total_price', 'payment_gateway_names', 'financial_status', 'current_status', 'ndr_call_status')

    # 5. Returns + Exchanges tracking
    # Switch to Event-Based: filter RMAs by their own creation date range
    ret_reqs = ReturnRequest.objects.filter(order__in=base_orders, created_at__gte=ret_s, created_at__lte=ret_e)
    ret_data = ret_reqs.values(
        'request_type', 'status', 'stocked_at', 'created_at',
        'order__id', 'order__order_number', 'order__created_at', 'order__customer_first_name', 'order__customer_last_name', 'order__total_price', 'order__payment_gateway_names', 'order__financial_status'
    )
 
    # 6. Exchange Fulfillment (Sent/Delivered) Tracking
    # Switch to Event-Based: filter Exchange orders by their own creation date range
    exc_fulfillment_qs = Order.objects.filter(
        parent_order__in=base_orders, 
        is_exchange_order=True,
        created_at__gte=exc_s,
        created_at__lte=exc_e
    )
    exc_fulfillment_data = exc_fulfillment_qs.values(
        'current_status', 'parent_order_id', 
        'parent_order__order_number', 'parent_order__created_at', 'parent_order__customer_first_name', 'parent_order__customer_last_name', 'parent_order__total_price', 'parent_order__payment_gateway_names', 'parent_order__financial_status'
    )

    # Structure Initialization
    PAYMENTS = ['total', 'cod', 'partial', 'prepaid']
    def make_metrics(): return {p: {'qty': 0, 'amt': 0.0} for p in PAYMENTS}

    metrics_aov = make_metrics()
    metrics_status = { k: make_metrics() for k in ['unconfirmed', 'cancelled', 'confirmed', 'batched', 'label_generated', 'in_transit', 'delivered', 'ndr', 'rto_delivered'] }
    metrics_ndr = { k: make_metrics() for k in ['total_ndr', 'ndr_cancelled_rto', 'ndr_pending', 'ndr_will_accept', 'ndr_in_transit', 'ndr_delivered', 'ndr_will_accept_pending'] }
    metrics_fulfillment = { k: make_metrics() for k in ['base', 'batched', 'sent_packaging', 'packaged', 'dispatched'] }
    metrics_returns = { k: make_metrics() for k in ['applied', 'accepted', 'rejected', 'picked_up', 'received'] }
    metrics_exchange = { k: make_metrics() for k in ['applied', 'accepted', 'rejected', 'picked_up', 'received', 'sent', 'delivered'] }

    extracted_orders = []

    def add(group_dict, key, ptype, amt, od, section):
        target = group_dict[key]
        target['total']['qty'] += 1
        target['total']['amt'] += amt
        target[ptype]['qty'] += 1
        target[ptype]['amt'] += amt

        if extract_target and extract_target.get('section') == section and extract_target.get('column') == key:
            if extract_target.get('payment') in ['all', ptype, None]:
                oid = od.get('id') or od.get('order__id') or od.get('parent_order_id')
                if not any(eo.get('id') == oid for eo in extracted_orders):
                    date_val = od.get('created_at') or od.get('order__created_at') or od.get('parent_order__created_at')
                    extracted_orders.append({
                        'id': oid,
                        'order_number': od.get('order_number') or od.get('order__order_number') or od.get('parent_order__order_number'),
                        'date': date_val.isoformat() if date_val else None,
                        'customer': f"{od.get('customer_first_name') or od.get('order__customer_first_name') or od.get('parent_order__customer_first_name') or ''} {od.get('customer_last_name') or od.get('order__customer_last_name') or od.get('parent_order__customer_last_name') or ''}".strip(),
                        'total_price': od.get('total_price') or od.get('order__total_price') or od.get('parent_order__total_price'),
                        'payment': ptype
                    })

    # -> Iterate AOV
    for od in aov_data:
        ptype = categorize_payment(od, None, None, None)
        amt = float(od['total_price'] or 0.0)
        metrics_aov['total']['qty'] += 1
        metrics_aov['total']['amt'] += amt
        metrics_aov[ptype]['qty'] += 1
        metrics_aov[ptype]['amt'] += amt

    # -> Iterate Status
    # Priority: NDR > RTO > Delivered > In Transit > Label Generated (Batched+not-sent-to-pack) > Batched > Confirmed > Cancelled > Unconfirmed
    # "Label Generated" = orders in the Confirmation Sheet = status='Batched' AND internal_fulfillment_status in [Pending, Fulfilled, On Hold]
    for od in status_data:
        ptype = categorize_payment(od, None, None, None)
        amt = float(od['total_price'] or 0.0)
        status_str = str(od['status'] or '')
        int_full = str(od['internal_fulfillment_status'] or '')
        curr_status = str(od['current_status'] or '')
        b_ndr = od['is_ndr'] == True

        lower_status = status_str.lower()
        lower_curr = curr_status.lower()
        lower_int = int_full.lower()

        # Confirmation sheet visible statuses
        CONFIRMATION_SHEET_STATUSES = ['pending', 'fulfilled', 'on hold', '']

        if b_ndr: add(metrics_status, 'ndr', ptype, amt, od, 'status_summary')
        elif lower_curr in [s.lower() for s in RTO_DELIVERED_STATUSES]: add(metrics_status, 'rto_delivered', ptype, amt, od, 'status_summary')
        elif 'delivered' in lower_curr: add(metrics_status, 'delivered', ptype, amt, od, 'status_summary')
        elif any(t in lower_curr for t in ['transit', 'dispatched', 'picked up', 'out for delivery', 'reached', 'shipped']): add(metrics_status, 'in_transit', ptype, amt, od, 'status_summary')
        # Label Generated = what's visible in the Confirmation Sheet (Batched orders not yet sent to packaging)
        elif lower_status == 'batched' and lower_int in CONFIRMATION_SHEET_STATUSES: add(metrics_status, 'label_generated', ptype, amt, od, 'status_summary')
        elif lower_status == 'batched': add(metrics_status, 'batched', ptype, amt, od, 'status_summary')
        elif lower_status == 'confirmed': add(metrics_status, 'confirmed', ptype, amt, od, 'status_summary')
        elif lower_status == 'cancelled': add(metrics_status, 'cancelled', ptype, amt, od, 'status_summary')
        else: add(metrics_status, 'unconfirmed', ptype, amt, od, 'status_summary')

    # -> Iterate Fulfillment
    # Mirrors Confirmation Sheet: Label Gen = Batched + [Pending/Fulfilled/On Hold]
    for od in full_data:
        ptype = categorize_payment(od, None, None, None)
        amt = float(od['total_price'] or 0.0)
        status_str = str(od['status'] or '')
        int_full = str(od['internal_fulfillment_status'] or '')
        curr_status = str(od['current_status'] or '')

        lower_curr = curr_status.lower()
        lower_int = int_full.lower()
        lower_status = status_str.lower()

        dispatched_states = ['dispatched', 'picked up', 'intransit', 'in transit', 'in_transit', 'out for delivery', 'delivered', 'rto', 'undelivered', 'reached']
        is_dispatched = any(d in lower_curr for d in dispatched_states)
        CONFIRMATION_SHEET_STATUSES = ['pending', 'fulfilled', 'on hold', '']

        if is_dispatched: add(metrics_fulfillment, 'dispatched', ptype, amt, od, 'fulfillment')
        elif lower_int == 'packaged' or 'manifested' in lower_curr: add(metrics_fulfillment, 'packaged', ptype, amt, od, 'fulfillment')
        elif lower_int == 'sent for packaging': add(metrics_fulfillment, 'sent_packaging', ptype, amt, od, 'fulfillment')
        # Label Gen = Confirmation Sheet orders
        elif lower_status == 'batched' and lower_int in CONFIRMATION_SHEET_STATUSES: add(metrics_fulfillment, 'base', ptype, amt, od, 'fulfillment')
        elif lower_status == 'batched': add(metrics_fulfillment, 'batched', ptype, amt, od, 'fulfillment')

    # -> Iterate NDR
    for nd in ndr_data:
        ptype = categorize_payment(nd, None, None, None)
        amt = float(nd['total_price'] or 0.0)
        curr_status = str(nd['current_status'] or '')
        lower_ndr_call = str(nd['ndr_call_status'] or '').lower().strip()

        add(metrics_ndr, 'total_ndr', ptype, amt, nd, 'ndr')
        if 'RTO' in curr_status or 'cancelled' in lower_ndr_call: add(metrics_ndr, 'ndr_cancelled_rto', ptype, amt, nd, 'ndr')
        if lower_ndr_call == '' or 'pending' in lower_ndr_call: add(metrics_ndr, 'ndr_pending', ptype, amt, nd, 'ndr')
        if 'will accept' in lower_ndr_call: add(metrics_ndr, 'ndr_will_accept', ptype, amt, nd, 'ndr')
        if curr_status == 'In Transit': add(metrics_ndr, 'ndr_in_transit', ptype, amt, nd, 'ndr')
        if curr_status == 'Delivered': add(metrics_ndr, 'ndr_delivered', ptype, amt, nd, 'ndr')
        if 'will accept' in lower_ndr_call and curr_status != 'Delivered': add(metrics_ndr, 'ndr_will_accept_pending', ptype, amt, nd, 'ndr')

    # -> Iterate Returns & Exchanges
    # In-memory date check to avoid multiple DB queries across the same model
    seen_returns = set()
    seen_exchanges = set()

    for rd in ret_data:
        oid = rd['order__id']
        pseudo_od = { 'total_price': rd['order__total_price'], 'payment_gateway_names': rd['order__payment_gateway_names'], 'financial_status': rd['order__financial_status'] }
        ptype = categorize_payment(pseudo_od, None, None, None)
        amt = float(pseudo_od['total_price'] or 0.0)
        
        req_type = rd['request_type']
        status = rd['status']
        stocked_at = rd['stocked_at']
        c_at = rd['created_at']

        # Determine if it falls in target periods
        if req_type == 'RETURN':
            # Remove c_at filter to anchor to the order's cohort
            def try_add(key):
                if (oid, key) not in seen_returns:
                    seen_returns.add((oid, key))
                    add(metrics_returns, key, ptype, amt, rd, 'returns')
            
            try_add('applied')
            if status in ['APPROVED', 'RECEIVED', 'INSPECTED', 'REFUNDED']: try_add('accepted')
            if status == 'REJECTED': try_add('rejected')
            if status in ['RECEIVED', 'INSPECTED', 'REFUNDED']: try_add('picked_up')
            if status in ['INSPECTED', 'REFUNDED'] or stocked_at is not None: try_add('received')

        elif req_type == 'EXCHANGE':
            # Remove c_at filter to anchor to the order's cohort
            def try_add_exc(key):
                if (oid, key) not in seen_exchanges:
                    seen_exchanges.add((oid, key))
                    add(metrics_exchange, key, ptype, amt, rd, 'exchanges')

            try_add_exc('applied')
            if status in ['APPROVED', 'RECEIVED', 'INSPECTED', 'REFUNDED']: try_add_exc('accepted')
            if status == 'REJECTED': try_add_exc('rejected')
            if status in ['RECEIVED', 'INSPECTED', 'REFUNDED']: try_add_exc('picked_up')
            if status in ['INSPECTED', 'REFUNDED'] or stocked_at is not None: try_add_exc('received')

    # -> Iterate Exchange Fulfillment
    seen_exc_sent = set()
    seen_exc_del = set()

    for ed in exc_fulfillment_data:
        poid = ed['parent_order_id']
        # We categorize based on the PARENT order's payment info
        pseudo_od = { 'total_price': ed['parent_order__total_price'], 'payment_gateway_names': ed['parent_order__payment_gateway_names'], 'financial_status': ed['parent_order__financial_status'] }
        ptype = categorize_payment(pseudo_od, None, None, None)
        amt = float(pseudo_od['total_price'] or 0.0)
        curr_status = str(ed['current_status'] or '').lower()

        if 'delivered' in curr_status:
            if poid not in seen_exc_del:
                seen_exc_del.add(poid)
                add(metrics_exchange, 'delivered', ptype, amt, ed, 'exchanges')
        
        if 'transit' in curr_status or 'dispatched' in curr_status or 'shipped' in curr_status or 'delivered' in curr_status:
             if poid not in seen_exc_sent:
                seen_exc_sent.add(poid)
                add(metrics_exchange, 'sent', ptype, amt, ed, 'exchanges')

    payload = {
        'aov': metrics_aov,
        'status_summary': metrics_status,
        'ndr': metrics_ndr,
        'fulfillment': metrics_fulfillment,
        'returns': metrics_returns,
        'exchanges': metrics_exchange
    }
    
    if extract_target:
        payload['extracted_orders'] = extracted_orders

    return payload

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def operations_analytics(request):
    user = request.user
    if hasattr(user, 'shop_credentials'): org = user.shop_credentials
    elif hasattr(user, 'team_settings') and user.team_settings.organization: org = user.team_settings.organization
    else: return Response({"selected_period": None, "compare_period": None})
    
    orders = Order.objects.filter(org_id=org.organization_id)

    s1, e1 = None, None
    s2, e2 = None, None
    
    start_date = request.GET.get('start_date')
    if start_date: s1 = safe_parse(start_date)
    end_date = request.GET.get('end_date')
    if end_date: e1 = safe_parse(end_date)
        
    compare_start = request.GET.get('compare_start_date')
    if compare_start: s2 = safe_parse(compare_start)
    compare_end = request.GET.get('compare_end_date')
    if compare_end: e2 = safe_parse(compare_end)

    overrides = {}
    for key, val in request.GET.items():
        if key.endswith('_start') or key.endswith('_end'):
            if not key.startswith('compare_'):
                overrides[key] = val

    extract_section = request.GET.get('extract_section')
    extract_column = request.GET.get('extract_column')
    extract_payment = request.GET.get('extract_payment')
    extract_target = None
    if extract_section and extract_column:
        extract_target = {
            'section': extract_section,
            'column': extract_column,
            'payment': extract_payment or 'all'
        }

    selected_period_data = build_aggregation_payload(orders, s1, e1, overrides, extract_target)
    
    # If it's a dedicated extraction request, we just return the orders to save bandwidth over the whole dashboard state!
    if extract_target:
        return Response({"extracted_orders": selected_period_data.get('extracted_orders', [])})

    compare_period_data = build_aggregation_payload(orders, s2, e2, {}) if s2 and e2 else None

    return Response({
        "selected_period": selected_period_data,
        "compare_period": compare_period_data
    })
