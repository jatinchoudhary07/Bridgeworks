import json
from django.db.models import Q
from core.models import PaymentMethodRule

def get_original_payment_method(raw_data):
    """
    Extract the original payment gateway from order raw_data note_attributes.
    Returns the value of the "Payment Gateway" attribute (e.g. 'RAZORPAY' or '-'),
    or None if not found/empty.
    """
    if not raw_data:
        return None
    raw = raw_data
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, dict):
        return None
        
    note_attrs = raw.get('note_attributes', [])
    if not isinstance(note_attrs, list):
        return None
        
    for attr in note_attrs:
        if isinstance(attr, dict) and attr.get('name') == 'Payment Gateway':
            return attr.get('value')
    return None

def derive_payment_type_from_fields(payment_gateway_names, financial_status, tags, raw_data):
    """
    Core business logic to classify order payment method.
    Returns 'COD', 'Partially Paid', or 'PrePaid'.
    """
    opm = get_original_payment_method(raw_data)
    
    gateways = str(payment_gateway_names or []).lower()
    fin_status = (financial_status or '').lower()
    tags_str = str(tags or '').lower()

    # Parse raw_data to check for draft order status, total price, and payment terms
    total_price = None
    is_draft = False
    has_receipt_payment_terms = False
    
    if raw_data:
        raw = raw_data
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        if isinstance(raw, dict):
            tp = raw.get('total_price')
            if tp is not None:
                try:
                    total_price = float(tp)
                except ValueError:
                    pass
            
            # Identify draft orders
            sn = raw.get('source_name')
            app_id = raw.get('app_id')
            if sn in ('shopify_draft_order', '146388910081') or app_id in (1354745, 146388910081):
                is_draft = True
                
            # Check payment_terms
            pt = raw.get('payment_terms')
            if isinstance(pt, dict):
                pt_type = str(pt.get('payment_terms_type') or '').lower()
                pt_name = str(pt.get('payment_terms_name') or '').lower()
                if pt_type == 'receipt' or 'receipt' in pt_name:
                    has_receipt_payment_terms = True

    # 1. Check explicit payment mode tag set during draft creation
    if 'payment_mode:prepaid' in tags_str:
        return 'PrePaid'
    if 'payment_mode:cod' in tags_str:
        return 'COD'
    if 'payment_mode:partially_paid' in tags_str or 'payment_mode:partial' in tags_str:
        return 'Partially Paid'

    # 2. Partially Paid Check (evaluate early to preserve Partially Paid status)
    is_partially_paid = (
        'partially_paid' in fin_status or
        'ppcod' in gateways or
        'gokwik ppcod' in gateways or
        'ppcod' in tags_str or
        'partially_paid' in tags_str or
        'partially paid' in tags_str or
        'partial payment' in tags_str
    )
    if is_partially_paid:
        return 'Partially Paid'

    # 3. Payment Terms Due on Receipt Rule (often used for COD draft orders)
    if has_receipt_payment_terms and total_price and total_price > 0:
        return 'COD'

    # Explicit COD gateway or tag checks (so COD orders don't get misclassified as PrePaid by total price or replacement tag rules)
    if 'cash' in gateways or 'cod' in gateways or 'cod' in tags_str:
        return 'COD'

    # 4. Total Price Zero Rule (a free order has no money to collect at delivery)
    if total_price == 0.0:
        return 'PrePaid'

    # 5. Replacement / Free Reshipment Rule (tags indicating reshipment/warranty replacement)
    replacement_keywords = ('missing-item', 'damaged-received', 'faded jewelry', 'warranty', 'complimentary', 'reship', 'duplicate', 'replacement')
    if any(k in tags_str for k in replacement_keywords):
        return 'PrePaid'

    # 6. Exchange COD Rule: ReturnPrime exchange orders with shipping fees are COD
    is_exchange = 'exchange_order' in tags_str or 'exchange' in tags_str or 'return_prime' in tags_str or 'returnprime' in gateways
    if is_exchange and total_price and total_price > 0:
        # Gateway must be ReturnPrime or empty to be COD, and must not have prepaid gateways
        has_prepaid_gateway = any(pg in gateways for pg in ('razorpay', 'gokwik', 'easebuzz', 'payu', 'phonepe', 'upi'))
        is_rp_or_empty = not payment_gateway_names or not gateways or gateways == '[]' or 'returnprime' in gateways or 'manual' in gateways
        if is_rp_or_empty and not has_prepaid_gateway and opm != 'RAZORPAY':
            return 'COD'

    # 7. OPM Check (Original Payment Method)
    if opm:
        opm = opm.upper()
        if opm == 'RAZORPAY':
            return 'PrePaid'
        elif opm == '-':
            return 'COD'

    # 8. Fallback checks
    if 'cash' in gateways or 'cod' in gateways or 'cod' in tags_str:
        return 'COD'
    if 'pending' in fin_status and 'paid' not in fin_status:
        # For draft orders, do not default to COD unless explicitly marked COD
        if is_draft and not ('cod' in gateways or 'cod' in tags_str or 'cash' in gateways):
            return 'PrePaid'
        return 'COD'
    return 'PrePaid'

def get_payment_q_objects(prefix=''):
    """
    Returns a dictionary of Q objects for 'cod', 'partial', and 'prepaid'
    based on the PaymentMethodRule model and OPM note attributes.
    If `prefix` is provided (e.g., 'order__'), it will be prepended to the field name.
    """
    from django.db import connection, models
    from django.db.models.expressions import RawSQL

    field_name = f"{prefix}payment_gateway_names"
    
    # Pre-define subqueries checking note_attributes for OPM
    if connection.vendor == 'sqlite':
        table_name = "core_order"
        sql_rz = f"EXISTS (SELECT 1 FROM json_each({table_name}.raw_data, '$.note_attributes') WHERE json_extract(value, '$.name') = 'Payment Gateway' AND json_extract(value, '$.value') = 'RAZORPAY')"
        sql_cod = f"EXISTS (SELECT 1 FROM json_each({table_name}.raw_data, '$.note_attributes') WHERE json_extract(value, '$.name') = 'Payment Gateway' AND json_extract(value, '$.value') = '-')"
        opm_razorpay_q = Q(RawSQL(sql_rz, [], output_field=models.BooleanField()))
        opm_cod_q = Q(RawSQL(sql_cod, [], output_field=models.BooleanField()))
    else:
        opm_razorpay_q = Q(**{f"{prefix}raw_data__note_attributes__contains": [{"name": "Payment Gateway", "value": "RAZORPAY"}]})
        opm_cod_q = Q(**{f"{prefix}raw_data__note_attributes__contains": [{"name": "Payment Gateway", "value": "-"}]})

    rules = PaymentMethodRule.objects.all()
    
    cod_q_base = Q()
    partial_q_base = Q()
    explicit_prepaid_q = Q()
    
    has_cod = False
    has_partial = False
    has_explicit_prepaid = False
    
    for rule in rules:
        if rule.gateway_name.lower() == 'razorpay':
            partial_q_base |= Q(
                **{f"{field_name}__icontains": rule.gateway_name}, 
                **{f"{prefix}financial_status__icontains": 'partially_paid'}
            )
            partial_q_base |= Q(
                **{f"{field_name}__icontains": rule.gateway_name},
                **{f"{prefix}tags__icontains": 'Partial Payment'}
            )
            partial_q_base |= Q(
                **{f"{field_name}__icontains": 'Razorpay PPCOD'}
            )
            has_partial = True
            
            explicit_prepaid_q |= Q(
                **{f"{field_name}__icontains": rule.gateway_name}
            ) & ~Q(**{f"{prefix}financial_status__icontains": 'partially_paid'}) & ~Q(**{f"{prefix}tags__icontains": 'Partial Payment'}) & ~Q(**{f"{field_name}__icontains": 'Razorpay PPCOD'})
            has_explicit_prepaid = True
            continue

        if rule.payment_type == 'cod':
            cod_q_base |= Q(**{f"{field_name}__icontains": rule.gateway_name})
            has_cod = True
        elif rule.payment_type == 'partial':
            partial_q_base |= Q(**{f"{field_name}__icontains": rule.gateway_name})
            has_partial = True
        elif rule.payment_type == 'prepaid':
            explicit_prepaid_q |= Q(**{f"{field_name}__icontains": rule.gateway_name})
            has_explicit_prepaid = True
            
    # Fallback to the original hardcoded COD logic + financial_status
    if not has_cod:
        cod_q_base |= (
            Q(**{f"{field_name}__icontains": 'cash_on_delivery'}) | 
            Q(**{f"{field_name}__icontains": 'CASH ON DELIVERY'}) | 
            Q(**{f"{field_name}__icontains": 'Cash on Delivery (COD)'}) |
            Q(**{f"{prefix}financial_status__icontains": 'pending'})
        )
        
    # Fallback to the original hardcoded Partial logic + financial_status
    if not has_partial:
        partial_q_base |= (
            Q(**{f"{field_name}__icontains": 'Gokwik PPCOD'}) | 
            Q(**{f"{field_name}__icontains": 'ppcod'}) |
            Q(**{f"{prefix}financial_status__icontains": 'partially_paid'})
        )

    # 1. Partially Paid (PPCOD) Q
    # Match both explicitly detected PPCOD gateways/tags, or OPM Razorpay that has a partial status/tag
    partial_q = partial_q_base

    # 2. COD Q
    # Match if explicitly marked as OPM '-' or has a COD indicator, excluding any OPM Razorpay ones
    cod_q = (opm_cod_q | cod_q_base) & ~opm_razorpay_q & ~partial_q

    # 3. Prepaid Q
    # Explicitly excludes COD and Partial
    prepaid_exclusion_q = ~cod_q & ~partial_q
    
    if has_explicit_prepaid:
        prepaid_q = (prepaid_exclusion_q | explicit_prepaid_q | (Q(**{f"{prefix}financial_status__iexact": 'paid'}) & ~Q(**{f"{prefix}financial_status__icontains": 'partially'}))) & ~cod_q & ~partial_q
    else:
        prepaid_q = (prepaid_exclusion_q | (Q(**{f"{prefix}financial_status__iexact": 'paid'}) & ~Q(**{f"{prefix}financial_status__icontains": 'partially'}))) & ~cod_q & ~partial_q
        
    return {
        'cod': cod_q,
        'partial': partial_q,
        'prepaid': prepaid_q
    }

