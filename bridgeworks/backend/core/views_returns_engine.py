"""
Returns & Exchange Engine — API Views (Day 1 + Day 2)
=============================================
Endpoints:
  POST /api/returns-engine/scan/                      → Scan Lookup (return AWB or Order #)
  POST /api/returns-engine/move-to-qc/               → Create case + timeline entries
  GET  /api/returns-engine/cases/                     → List all cases (paginated, filterable)
  GET  /api/returns-engine/cases/<id>/               → Case detail with full data
  GET  /api/returns-engine/search/                    → Search cases by order/AWB/customer
  GET  /api/returns-engine/cases/<id>/activity/       → Activity timeline for a case
  POST /api/returns-engine/qc-action/                → QC Pass / QC Fail

IMPORTANT — AWB lookup logic:
  This scanner must ONLY match the RETURN shipment AWB
  (the label the courier assigns when a customer sends a product back),
  NOT the original outgoing dispatch AWB that was assigned when the order was shipped.
"""

import logging
from django.db.models import Q, F
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Order, ReturnExchangeCase, ReturnExchangeActivity, ReturnRequest, TrackingInfo, ReturnExchangeBatch

logger = logging.getLogger(__name__)


# ─── helpers ────────────────────────────────────────────────────────────────────

def _get_org_id(request):
    """Resolve org_id from the authenticated user."""
    user = request.user
    if not user.is_authenticated:
        return None
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    if hasattr(user, 'team_settings') and user.team_settings.organization:
        return user.team_settings.organization.organization_id
    return None

def _get_refund_screenshot_url(case):
    """Return the correct URL for a refund screenshot, fixing Cloudinary raw/upload issues.

    Some files were uploaded to Cloudinary with resource_type='raw' due to
    filenames containing dots in timestamps (e.g. '10.53.24').  For images,
    Cloudinary only serves them correctly from the image/upload path.  This
    helper detects that case and swaps the resource type in the URL.
    """
    if not case.refund_screenshot:
        return None
    url = case.refund_screenshot.url
    if not url:
        return None
    # If it's a Cloudinary URL using raw/upload, check if the underlying
    # file is actually an image (by content type or common screenshot paths)
    # and swap to image/upload so the browser can render it.
    if 'cloudinary.com' in url and '/raw/upload/' in url:
        url = url.replace('/raw/upload/', '/image/upload/')
    return url


def _sync_order_from_shopify_by_number(order_number, org_id):
    """
    Live-fetch the order from Shopify by order number, update the local DB
    record (Order & LineItems) to guarantee it matches Shopify exactly.
    """
    if not org_id or not order_number:
        return None

    # Clean order number to get only digits
    clean_num = ''.join(filter(str.isdigit, str(order_number)))
    if not clean_num:
        return None

    from core.models import ShopCredentials, decrypt_data
    try:
        creds = ShopCredentials.objects.get(organization_id=org_id)
    except ShopCredentials.DoesNotExist:
        return None

    # Get Shopify credentials
    shop_url = (
        creds.get_shopify_shop_url()
        if hasattr(creds, 'get_shopify_shop_url') else None
    ) or getattr(creds, 'myshopify_domain', '') or ''
    clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
    api_version = getattr(creds, 'shopify_api_version', None) or '2024-07'
    order_prefix = creds.shopify_order_prefix or ''

    # Build auth headers
    import base64
    if getattr(creds, 'auth_method', '') == 'oauth' and getattr(creds, 'shopify_access_token_encrypted', None):
        token = decrypt_data(creds.shopify_access_token_encrypted)
        headers = {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
    else:
        api_key = creds.get_shopify_api_key() if hasattr(creds, 'get_shopify_api_key') else ''
        password = creds.get_shopify_password() if hasattr(creds, 'get_shopify_password') else ''
        api_key = api_key or ''
        password = password or ''
        if password and password.startswith('shpat_'):
            headers = {'X-Shopify-Access-Token': password, 'Content-Type': 'application/json'}
        else:
            encoded = base64.b64encode(f"{api_key}:{password}".encode()).decode()
            headers = {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}

    import requests as http_requests
    # Search by order name (e.g. #JANKI38357)
    full_name = f"{order_prefix}{clean_num}"
    names_to_try = [full_name, f"#{clean_num}", clean_num]
    
    api_order = None
    for name_query in names_to_try:
        url = f"https://{clean_domain}/admin/api/{api_version}/orders.json?name={http_requests.utils.quote(name_query)}&status=any"
        try:
            resp = http_requests.get(url, headers=headers, timeout=10)
            if resp.ok:
                orders_data = resp.json().get('orders', [])
                for o in orders_data:
                    if str(o.get('order_number')) == clean_num or o.get('name') == full_name or o.get('name') == f"#{clean_num}":
                        api_order = o
                        break
                if api_order:
                    break
        except Exception as e:
            logger.error(f"Error searching Shopify order {name_query}: {e}")

    if not api_order:
        return None

    # Now we save/update the order in local DB
    from core.models import Order, LineItem
    from django.utils.dateparse import parse_datetime
    try:
        customer_data = api_order.get('customer') or {}
        shipping_address = api_order.get('shipping_address')
        shipping_address_text = f"{(shipping_address or {}).get('first_name','')} {(shipping_address or {}).get('last_name','')}, {(shipping_address or {}).get('address1','')}, {(shipping_address or {}).get('city','')}, {(shipping_address or {}).get('zip','')}" if shipping_address else None
        billing_address = api_order.get('billing_address')
        billing_address_text = f"{(billing_address or {}).get('first_name','')} {(billing_address or {}).get('last_name','')}, {(billing_address or {}).get('address1','')}, {(billing_address or {}).get('city','')}, {(billing_address or {}).get('zip','')}" if billing_address else None

        from django.db import transaction
        with transaction.atomic():
            order_obj, created = Order.objects.get_or_create(
                shopify_id=api_order['id'],
                defaults={'org_id': org_id}
            )

            order_obj.order_number = api_order.get('order_number')
            
            created_at_str = api_order.get('created_at')
            if created_at_str:
                order_obj.created_at = parse_datetime(created_at_str)
            
            updated_at_str = api_order.get('updated_at')
            if updated_at_str:
                order_obj.updated_at = parse_datetime(updated_at_str)
                
            order_obj.total_price = api_order.get('total_price')
            order_obj.financial_status = api_order.get('financial_status')
            order_obj.fulfillment_status = api_order.get('fulfillment_status')
            order_obj.tags = api_order.get('tags', '')
            order_obj.payment_gateway_names = api_order.get('payment_gateway_names', [])
            order_obj.discount_codes = api_order.get('discount_codes', [])
            order_obj.raw_data = api_order

            p_first_name = customer_data.get('first_name')
            p_last_name = customer_data.get('last_name')
            p_phone = (shipping_address or {}).get('phone')
            p_email = customer_data.get('email')

            if p_first_name: order_obj.customer_first_name = p_first_name
            if p_last_name: order_obj.customer_last_name = p_last_name
            if p_phone: order_obj.contact_phone = p_phone
            if p_email: order_obj.contact_email = p_email
            if shipping_address_text: order_obj.shipping_address = shipping_address_text
            if billing_address_text: order_obj.billing_address = billing_address_text

            order_obj.save()

            if created and order_obj.financial_status != 'voided':
                order_obj.status = 'Pending'
                order_obj.internal_fulfillment_status = 'Pending'
                order_obj.save()

            # Refresh line items
            order_obj.line_items.all().delete()
            line_items_to_create = [
                LineItem(
                    order=order_obj,
                    product_id=item.get('product_id'),
                    variant_id=item.get('variant_id'),
                    title=item.get('title'),
                    quantity=item.get('quantity'),
                    sku=item.get('sku'),
                    vendor=item.get('vendor'),
                    price=item.get('price'),
                    name=item.get('name')
                )
                for item in api_order.get('line_items', [])
            ]
            if line_items_to_create:
                LineItem.objects.bulk_create(line_items_to_create)
            
            logger.info(f"Successfully synced order #{order_obj.order_number} from live Shopify API on lookup.")
            return order_obj
    except Exception as e:
        logger.error(f"Error saving/updating order from Shopify API: {e}")
        return None


def _find_return_order(scan_input: str, org_id: str):
    """
    Look up a ReturnRequest (and its linked Order) by a RETURN shipment AWB,
    Return Request ID/number, or Order number, scoped to org_id.
    """
    if not org_id:
        return None, None

    # 1) Try exact matches on return_prime_id, request_number, and awb_number
    # (using both original and uppercase to handle case-insensitivity without slow DB __iexact/ILIKE filters)
    q_filter = (
        Q(return_prime_id=scan_input) |
        Q(request_number=scan_input) |
        Q(awb_number=scan_input)
    )
    if scan_input != scan_input.upper():
        q_filter |= (
            Q(return_prime_id=scan_input.upper()) |
            Q(request_number=scan_input.upper()) |
            Q(awb_number=scan_input.upper())
        )

    rr = (
        ReturnRequest.objects
        .filter(q_filter, order__org_id=org_id)
        .select_related('order')
        .prefetch_related('order__line_items')
        .order_by('-created_at')
        .first()
    )
    if rr:
        return rr, rr.order

    # 2) Order number fallback (manual entry by staff, len < 8 to skip AWBs and prevent full table scan)
    if scan_input.isdigit() and len(scan_input) < 8:
        _sync_order_from_shopify_by_number(scan_input, org_id)
        try:
            val = int(scan_input)
            order = (
                Order.objects
                .defer('raw_data')
                .filter(order_number=val, org_id=org_id)
                .prefetch_related('line_items')
                .first()
            )
            if order:
                rr = order.return_requests.order_by('-created_at').first()
                return rr, order
        except ValueError:
            pass

    # 3) Fast exact JSON key lookups inside raw_data JSON (much faster than icontains)
    rr = (
        ReturnRequest.objects
        .filter(
            Q(raw_data__request_number=scan_input) |
            Q(raw_data__tracking_number=scan_input) |
            Q(raw_data__id=scan_input),
            order__org_id=org_id
        )
        .select_related('order')
        .defer('order__raw_data')
        .prefetch_related('order__line_items')
        .order_by('-created_at')
        .first()
    )
    if rr:
        # Auto-heal request_number or awb_number columns if missing
        changed = False
        raw = rr.raw_data or {}
        req_num = str(raw.get('request_number') or raw.get('id') or '').strip()
        tracking = str(raw.get('tracking_number') or raw.get('awb') or '').strip()
        if req_num and not rr.request_number:
            rr.request_number = req_num
            changed = True
        if tracking and not rr.awb_number:
            rr.awb_number = tracking
            changed = True
        if changed:
            rr.save(update_fields=['request_number', 'awb_number'])
        return rr, rr.order

    # 4) Fallback to substring search (only run as absolute last resort)
    rr = (
        ReturnRequest.objects
        .filter(raw_data__icontains=scan_input, order__org_id=org_id)
        .select_related('order')
        .defer('order__raw_data')
        .prefetch_related('order__line_items')
        .order_by('-created_at')
        .first()
    )
    if rr:
        return rr, rr.order

    return None, None


def _detect_case_type(return_request, order) -> str:
    if return_request:
        return 'exchange' if return_request.request_type == 'EXCHANGE' else 'return'
    if getattr(order, 'is_exchange_order', False):
        return 'exchange'
    tags = (order.tags or '').lower() if order else ''
    if 'exchange' in tags:
        return 'exchange'
    return 'return'

def _get_exchange_details(return_request) -> dict:
    """
    Parse Return Prime raw_data to detect whether a replacement order has
    already been created. Returns a dict of exchange metadata.

    Reads replacement products across all items and tracks order creation details.
    """
    empty = {
        'exchange_exists': False,
        'exchange_order_number': '',
        'exchange_status': '',
        'replacement_order_number': '',
        'replacement_order_status': '',
        'exchange_created_at': None,
        'replacement_products': [],
    }

    if not return_request:
        return empty

    order = return_request.order
    if not order:
        return empty

    # First, find the exchange order identifier (e.g. name or ID) from this return request
    target_exchange_order_name = None
    target_exchange_order_id = None
    raw = return_request.raw_data or {}
    if isinstance(raw, dict):
        if 'exchange' in raw and isinstance(raw['exchange'], dict):
            # Format B: Manual / Internal Exchange Format
            exch_data = raw['exchange']
            exch_order = exch_data.get('order', {}) or {}
            target_exchange_order_name = exch_order.get('name')
            target_exchange_order_id = exch_order.get('id')
        else:
            # Format A: Return Prime webhook format
            for item in raw.get('line_items', []):
                if isinstance(item, dict):
                    exchange_data = item.get('exchange', {}) or {}
                    if exchange_data:
                        item_exch_order = exchange_data.get('order', {}) or {}
                        if item_exch_order:
                            target_exchange_order_name = item_exch_order.get('name')
                            target_exchange_order_id = item_exch_order.get('id')
                            if target_exchange_order_name or target_exchange_order_id:
                                break

    # Now, find all return requests for the same order that are part of the same exchange order.
    # If no exchange order was found, we default to grouping return requests created within a 5-minute window.
    exchange_reqs = []
    if target_exchange_order_name or target_exchange_order_id:
        for req in order.return_requests.filter(request_type='EXCHANGE'):
            req_raw = req.raw_data or {}
            if isinstance(req_raw, dict):
                matched = False
                if 'exchange' in req_raw and isinstance(req_raw['exchange'], dict):
                    exch_data = req_raw['exchange']
                    exch_order_item = exch_data.get('order', {}) or {}
                    name = exch_order_item.get('name')
                    ext_id = exch_order_item.get('id')
                    if (target_exchange_order_name and name == target_exchange_order_name) or \
                       (target_exchange_order_id and ext_id == target_exchange_order_id):
                        matched = True
                else:
                    for item in req_raw.get('line_items', []):
                        if isinstance(item, dict):
                            exchange_data = item.get('exchange', {}) or {}
                            if exchange_data:
                                item_exch_order = exchange_data.get('order', {}) or {}
                                if item_exch_order:
                                    name = item_exch_order.get('name')
                                    ext_id = item_exch_order.get('id')
                                    if (target_exchange_order_name and name == target_exchange_order_name) or \
                                       (target_exchange_order_id and ext_id == target_exchange_order_id):
                                        matched = True
                                        break
                if matched:
                    exchange_reqs.append(req)
    else:
        # Fallback: Group exchange requests created within 5 minutes of this one
        from datetime import timedelta
        t_min = return_request.created_at - timedelta(minutes=5)
        t_max = return_request.created_at + timedelta(minutes=5)
        exchange_reqs = list(order.return_requests.filter(
            request_type='EXCHANGE',
            created_at__gte=t_min,
            created_at__lte=t_max
        ))

    if not exchange_reqs:
        exchange_reqs = [return_request]

    replacement_products = []
    exch_order = {}
    seen_products = set()

    for req in exchange_reqs:
        raw = req.raw_data or {}
        if not isinstance(raw, dict):
            continue

        if 'exchange' in raw and isinstance(raw['exchange'], dict):
            # Format B: Manual / Internal Exchange Format
            exch_data = raw['exchange']
            repl_prods = exch_data.get('replacement_products', [])
            if isinstance(repl_prods, list):
                for item in repl_prods:
                    if not isinstance(item, dict):
                        continue
                    sku_val = item.get('sku') or ''
                    product_key = f"{req.id}_{sku_val}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        
                        img_url = item.get('image', '')
                        if not img_url:
                            from inventory.models import ShopifyProductCache
                            title_val = item.get('title')
                            p_cache = None
                            if sku_val:
                                p_cache = ShopifyProductCache.objects.filter(Q(data__sku=sku_val) | Q(data__sku__icontains=sku_val)).first()
                            if not p_cache and title_val:
                                p_cache = ShopifyProductCache.objects.filter(data__name__icontains=title_val).first()
                            if p_cache:
                                img_url = p_cache.data.get('image') or ''

                        price_val = item.get('discounted_price')
                        if price_val is None or price_val == "":
                            price_val = item.get('price', 0)
                        
                        try:
                            price_val = float(price_val)
                        except (ValueError, TypeError):
                            price_val = 0.0

                        replacement_products.append({
                            'title': item.get('title', ''),
                            'sku': sku_val,
                            'price': price_val,
                            'quantity': item.get('quantity', 1),
                            'image': img_url,
                        })
            if not exch_order:
                exch_order = exch_data.get('order', {}) or {}
        else:
            # Format A: Return Prime webhook format
            li_list = raw.get('line_items', [])
            if not li_list or not isinstance(li_list, list):
                continue

            for item in li_list:
                if not isinstance(item, dict):
                    continue

                # 1. Collect replacement product details
                exchange_product_raw = item.get('exchange_product', {}) or {}
                if exchange_product_raw:
                    item_id = item.get('id') or exchange_product_raw.get('sku')
                    product_key = f"{req.id}_{item_id}"
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        qty = item.get('quantity', 1)
                        img_url = (exchange_product_raw.get('image') or {}).get('src', '')
                        if not img_url:
                            from inventory.models import ShopifyProductCache
                            sku_val = exchange_product_raw.get('sku')
                            title_val = exchange_product_raw.get('title')
                            p_cache = None
                            if sku_val:
                                p_cache = ShopifyProductCache.objects.filter(Q(data__sku=sku_val) | Q(data__sku__icontains=sku_val)).first()
                            if not p_cache and title_val:
                                p_cache = ShopifyProductCache.objects.filter(data__name__icontains=title_val).first()
                            if p_cache:
                                img_url = p_cache.data.get('image') or ''

                        replacement_products.append({
                            'title': exchange_product_raw.get('title', ''),
                            'sku': exchange_product_raw.get('sku', ''),
                            'price': exchange_product_raw.get('price', 0),
                            'quantity': qty,
                            'image': img_url,
                        })

                # 2. Look for exchange order details (take from the first one that has it)
                if not exch_order:
                    exchange_data = item.get('exchange', {}) or {}
                    if exchange_data:
                        item_exch_order = exchange_data.get('order', {}) or {}
                        if item_exch_order:
                            exch_order = item_exch_order

    if not exch_order:
        result = dict(empty)
        result['replacement_products'] = replacement_products
        return result

    exchange_order_name = exch_order.get('name', '') or ''        # e.g. '#JANKI40970'
    exchange_status = exch_order.get('exchanged_status', '') or ''  # e.g. 'success'
    exchange_created_at_str = exch_order.get('created_at', '') or ''

    exchange_created_at = None
    if exchange_created_at_str:
        from django.utils.dateparse import parse_datetime
        try:
            exchange_created_at = parse_datetime(exchange_created_at_str)
        except Exception:
            pass

    # Extract clean order number
    replacement_order_number = ''
    if exchange_order_name:
        clean_num = ''.join(filter(str.isdigit, exchange_order_name))
        if clean_num:
            replacement_order_number = clean_num

    replacement_order_status = ''
    if replacement_order_number:
        try:
            from core.models import Order
            repl_order = Order.objects.filter(order_number=int(replacement_order_number)).first()
            if repl_order:
                replacement_order_status = repl_order.current_status or ''
        except Exception:
            pass

    return {
        'exchange_exists': True,
        'exchange_order_number': exchange_order_name,
        'exchange_status': exchange_status,
        'replacement_order_number': replacement_order_number,
        'replacement_order_status': replacement_order_status,
        'exchange_created_at': exchange_created_at,
        'replacement_products': replacement_products,
    }

def _sync_case_exchange_details(case, return_request=None) -> None:
    """
    Syncs case exchange details by searching for any local Order linked
    to the Case by case number in the notes, falling back to ReturnRequest metadata.
    """
    if case.case_type != 'exchange':
        return

    from core.models import Order
    # 1. Try to find a local Order linked to this Case by Case ID in notes
    linked_exchange_order = Order.objects.filter(
        org_id=case.order.org_id,
        is_exchange_order=True,
        raw_data__note__icontains=f"Case #{case.id}"
    ).order_by('-created_at').first()

    if not linked_exchange_order and return_request:
        # 2. Try to find by ReturnRequest's request_number in tags or note
        if return_request.request_number:
            from django.db.models import Q
            linked_exchange_order = Order.objects.filter(
                org_id=case.order.org_id,
                is_exchange_order=True,
            ).filter(
                Q(tags__icontains=return_request.request_number) |
                Q(raw_data__note__icontains=return_request.request_number)
            ).order_by('-created_at').first()

    if not linked_exchange_order and case.order.order_number:
        # 3. Try to find by parent order name/number in tags or note
        from django.db.models import Q
        parent_name = f"#{case.order.order_number}"
        linked_exchange_order = Order.objects.filter(
            org_id=case.order.org_id,
            is_exchange_order=True,
        ).filter(
            Q(tags__icontains=parent_name) |
            Q(raw_data__note__icontains=parent_name) |
            Q(tags__icontains=str(case.order.order_number)) |
            Q(raw_data__note__icontains=str(case.order.order_number))
        ).order_by('-created_at').first()

    exch = None
    if linked_exchange_order:
        exchange_order_name = linked_exchange_order.raw_data.get('name') or f"#{linked_exchange_order.order_number}"
        replacement_order_number = str(linked_exchange_order.order_number)
        replacement_order_status = linked_exchange_order.current_status or linked_exchange_order.fulfillment_status or ''
        exchange_status = linked_exchange_order.financial_status or ''
        exchange_created_at = linked_exchange_order.created_at
        
        # Fetch replacement products and map original prices
        replacement_products = []
        for li in linked_exchange_order.line_items.all():
            orig_price = 0.0
            from inventory.models import ShopifyProductCache
            from django.db.models import Q
            p_cache = ShopifyProductCache.objects.filter(Q(data__sku=li.sku) | Q(data__sku__icontains=li.sku)).first()
            if p_cache:
                try:
                    orig_price = float(p_cache.data.get('price', 0))
                except (ValueError, TypeError):
                    pass
            
            # Fallback to ReturnRequest
            if not orig_price or orig_price == 0.0:
                if return_request and isinstance(return_request.raw_data, dict):
                    exch_data = return_request.raw_data.get('exchange', {}) or {}
                    for item in exch_data.get('replacement_products', []):
                        if item.get('sku') == li.sku:
                            price_val = item.get('price')
                            try:
                                orig_price = float(price_val)
                            except (ValueError, TypeError):
                                pass
                            break
            
            if not orig_price:
                try:
                    orig_price = float(li.price)
                except (ValueError, TypeError):
                    orig_price = 0.0

            img_url = ''
            if return_request and isinstance(return_request.raw_data, dict):
                exch_data = return_request.raw_data.get('exchange', {}) or {}
                for item in exch_data.get('replacement_products', []):
                    if item.get('sku') == li.sku:
                        img_url = item.get('image', '')
                        break
            
            if not img_url:
                from inventory.models import ShopifyProductCache
                from django.db.models import Q
                p_cache = ShopifyProductCache.objects.filter(Q(data__sku=li.sku) | Q(data__sku__icontains=li.sku)).first()
                if p_cache:
                    img_url = p_cache.data.get('image') or ''

            replacement_products.append({
                'title': li.title,
                'sku': li.sku,
                'price': orig_price,
                'quantity': li.quantity,
                'image': img_url,
            })

        exch = {
            'exchange_exists': True,
            'exchange_order_number': exchange_order_name,
            'exchange_status': exchange_status,
            'replacement_order_number': replacement_order_number,
            'replacement_order_status': replacement_order_status,
            'exchange_created_at': exchange_created_at,
            'replacement_products': replacement_products,
        }
    elif return_request:
        exch = _get_exchange_details(return_request)

    if exch and exch.get('exchange_exists'):
        case.exchange_exists = exch['exchange_exists']
        case.exchange_order_number = exch['exchange_order_number']
        case.exchange_status = exch['exchange_status']
        case.replacement_order_number = exch['replacement_order_number']
        case.replacement_order_status = exch['replacement_order_status']
        case.exchange_created_at = exch['exchange_created_at']
        case.exchange_meta = {'replacement_products': exch['replacement_products']}
        
        if case.status == 'exchange_pending':
            calc = _calculate_exchange_settlement(case)
            settlement_type = calc['settlement_type']

            # ─── IMPORTANT: Only auto-close cases where no money movement is needed.
            # Cases with refund_required or payment_required MUST stay in exchange_pending
            # so that the team can manually review and settle them in the queue.
            if settlement_type == 'no_settlement':
                case.settlement_type = settlement_type
                case.difference_amount = float(calc['difference'])
                case.settlement_completed_at = timezone.now()
                case.settlement_method = 'no_settlement'
                case.status = 'exchange_closed'

                case.save(update_fields=[
                    'exchange_exists', 'exchange_order_number', 'exchange_status',
                    'replacement_order_number', 'replacement_order_status',
                    'exchange_created_at', 'exchange_meta',
                    'status', 'settlement_type', 'difference_amount',
                    'settlement_completed_at', 'settlement_method',
                ])

                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='exchange_initiated',
                    notes=(
                        f'Original product received. Exchange verified. '
                        f'Replacement order {case.replacement_order_number or case.exchange_order_number} '
                        f'was detected as already created (status: {case.replacement_order_status or case.exchange_status or "unknown"}).'
                    ),
                )
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='exchange_closed',
                    notes='Exchange case auto-closed: values matched, no settlement required.',
                )
            else:
                # Refund required or payment required — save exchange details only,
                # keep status as exchange_pending so it appears in the settlement queue.
                case.settlement_type = settlement_type
                case.difference_amount = float(calc['difference'])
                case.save(update_fields=[
                    'exchange_exists', 'exchange_order_number', 'exchange_status',
                    'replacement_order_number', 'replacement_order_status',
                    'exchange_created_at', 'exchange_meta',
                    'settlement_type', 'difference_amount',
                ])

                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='exchange_initiated',
                    notes=(
                        f'Original product received. Exchange verified. '
                        f'Replacement order {case.replacement_order_number or case.exchange_order_number} '
                        f'already created (status: {case.replacement_order_status or case.exchange_status or "unknown"}). '
                        f'Settlement required ({settlement_type.replace("_", " ").title()}). '
                        f'Case kept in settlement queue for manual action.'
                    ),
                )
        else:
            case.save(update_fields=[
                'exchange_exists', 'exchange_order_number', 'exchange_status',
                'replacement_order_number', 'replacement_order_status',
                'exchange_created_at', 'exchange_meta',
            ])

from functools import lru_cache

@lru_cache(maxsize=1024)
def _get_shopify_cached_image(sku_val, title_val):
    from inventory.models import ShopifyProductCache
    from django.db.models import Q
    p_cache = None
    if sku_val:
        p_cache = ShopifyProductCache.objects.filter(Q(data__sku=sku_val) | Q(data__sku__icontains=sku_val)).first()
    if not p_cache and title_val:
        p_cache = ShopifyProductCache.objects.filter(data__name__icontains=title_val).first()
    if p_cache:
        return p_cache.data.get('image') or ''
    return ''


def _get_case_return_requests(case) -> list:
    if not case.order:
        return []
    # If return_requests has been prefetched, list(case.order.return_requests.all()) uses the prefetch cache.
    reqs = list(case.order.return_requests.all())
    if case.return_awb:
        filtered = [r for r in reqs if r.awb_number == case.return_awb]
        if filtered:
            return filtered
    return reqs


def _get_case_returned_products(case) -> list:
    return_reqs = _get_case_return_requests(case)
    products = []
    order = getattr(case, 'order', None)
    
    for req in return_reqs:
        raw = req.raw_data or {}
        if isinstance(raw, dict):
            line_items_raw = raw.get('line_items', [])
            for item in line_items_raw:
                orig_prod = item.get('original_product') or {}
                img_url = ''
                img_obj = orig_prod.get('image')
                if isinstance(img_obj, dict):
                    img_url = img_obj.get('src') or ''
                elif isinstance(img_obj, str):
                    img_url = img_obj
                
                if not img_url:
                    sku_val = orig_prod.get('sku') or item.get('sku')
                    title_val = orig_prod.get('title') or item.get('title')
                    img_url = _get_shopify_cached_image(sku_val, title_val)
                
                # Get the raw price from Return Prime (pre-discount MRP)
                price_info = item.get('shop_price') or item.get('presentment_price') or {}
                rp_price = price_info.get('actual_amount')
                if rp_price is None:
                    rp_price = orig_prod.get('price') or 0

                # --- KEY FIX: cross-reference Shopify order raw_data to get the
                # actual paid (post-discount) unit price, matching by SKU / variant_id.
                sku_val = orig_prod.get('sku') or item.get('sku') or ''
                variant_id_val = orig_prod.get('variant_id') or item.get('variant_id')
                discounted_price = _get_discounted_unit_price_from_order(
                    order, sku_val, variant_id_val, rp_price
                )

                products.append({
                    'title': orig_prod.get('title') or item.get('title') or '',
                    'sku': sku_val,
                    'quantity': item.get('quantity') or 1,
                    'price': str(round(discounted_price, 2)),
                    'variant': orig_prod.get('variant_title') or item.get('variant_title') or '',
                    'image': img_url,
                })
                
    if not products and order:
        # Fallback: read from order line_items — use discounted net prices
        return [
            {
                'title': li.title,
                'sku': li.sku or '',
                'quantity': li.quantity,
                'price': f"{_get_line_item_net_price(li):.2f}",
                'variant': getattr(li, 'variant_title', '') or '',
                'image': getattr(li, 'image_url', '') or _get_shopify_cached_image(li.sku, li.title),
                'variant_id': li.variant_id,
            }
            for li in order.line_items.all()
        ]
        
    return products


def _get_return_request_refund_calculation(return_request, fallback_product_value=0) -> dict:
    if not return_request:
        return {
            'item_price': str(round(fallback_product_value, 2)),
            'incentive': '0.00',
            'tax': '0.00',
            'discount': '0.00',
            'return_fee': '0.00',
            'total_refundable': str(round(fallback_product_value, 2)),
        }

    # Normalize to a list of return requests
    if not isinstance(return_request, (list, tuple)):
        if hasattr(return_request, '__iter__') and not isinstance(return_request, dict):
            reqs = list(return_request)
        else:
            reqs = [return_request]
    else:
        reqs = return_request

    if not reqs:
        return {
            'item_price': str(round(fallback_product_value, 2)),
            'incentive': '0.00',
            'tax': '0.00',
            'discount': '0.00',
            'return_fee': '0.00',
            'total_refundable': str(round(fallback_product_value, 2)),
        }

    item_price_total = 0.0
    discount_total = 0.0
    tax_total = 0.0
    return_fee_total = 0.0
    incentive_total = 0.0

    for req in reqs:
        raw = req.raw_data or {}
        if isinstance(raw, dict):
            line_items_raw = raw.get('line_items', [])
            for item in line_items_raw:
                qty = item.get('quantity') or 1
                
                # Check shop_price first, fallback to presentment_price
                price_info = item.get('shop_price') or item.get('presentment_price') or {}
                price = price_info.get('actual_amount')
                if price is None:
                    price = item.get('original_product', {}).get('price') or 0
                item_price_total += float(price) * qty
                
                disc = price_info.get('total_discount') or 0
                discount_total += float(disc)
                
                tax = price_info.get('total_tax') or 0
                tax_total += float(tax)
                
                fee_obj = item.get('return_fee', {}).get('price_set', {}) or {}
                fee_val = fee_obj.get('shop_money', {}).get('amount')
                if fee_val is None:
                    fee_val = fee_obj.get('presentment_money', {}).get('amount')
                if fee_val is not None:
                    return_fee_total += float(fee_val)

            # Incentive
            incentive_obj = raw.get('incentive')
            if isinstance(incentive_obj, dict):
                inc_val = incentive_obj.get('amount') or 0
                incentive_total += float(inc_val)
            elif incentive_obj is not None:
                try:
                    incentive_total += float(incentive_obj)
                except ValueError:
                    pass

    total_refundable = item_price_total + incentive_total + tax_total - discount_total - return_fee_total

    return {
        'item_price': str(round(item_price_total, 2)),
        'incentive': str(round(incentive_total, 2)),
        'tax': str(round(tax_total, 2)),
        'discount': str(round(discount_total, 2)),
        'return_fee': str(round(return_fee_total, 2)),
        'total_refundable': str(round(total_refundable, 2)),
    }


def _get_line_item_net_price(li):
    base_price = float(li.price)
    order = getattr(li, 'order', None)
    if not order or not order.raw_data:
        return base_price
    
    raw_line_items = order.raw_data.get('line_items', [])
    for raw_item in raw_line_items:
        sku_match = raw_item.get('sku') == li.sku if li.sku and raw_item.get('sku') else False
        var_match = raw_item.get('variant_id') == li.variant_id if li.variant_id and raw_item.get('variant_id') else False
        title_match = raw_item.get('title') == li.title
        
        if sku_match or var_match or (not li.sku and title_match):
            discount_allocations = raw_item.get('discount_allocations', [])
            total_discount = 0.0
            for da in discount_allocations:
                try:
                    total_discount += float(da.get('amount') or 0.0)
                except (ValueError, TypeError):
                    pass
            qty = int(raw_item.get('quantity') or li.quantity or 1)
            if qty <= 0:
                qty = 1
            net_price = base_price - (total_discount / qty)
            return max(0.0, net_price)
            
    return base_price


def _get_discounted_unit_price_from_order(order, sku, variant_id, base_price):
    """
    Given an order and a product identified by sku or variant_id,
    look up the actual paid (post-discount) unit price from Shopify's
    order raw_data by applying discount_allocations.
    Falls back to base_price if no match is found.
    """
    if not order or not order.raw_data:
        return float(base_price)
    raw_line_items = order.raw_data.get('line_items', [])
    for raw_item in raw_line_items:
        raw_sku = raw_item.get('sku') or ''
        raw_var_id = raw_item.get('variant_id')
        sku_match = sku and raw_sku and raw_sku == sku
        var_match = variant_id and raw_var_id and int(raw_var_id) == int(variant_id)
        if sku_match or var_match:
            raw_base = float(raw_item.get('price') or base_price)
            discount_allocations = raw_item.get('discount_allocations', [])
            total_discount = 0.0
            for da in discount_allocations:
                try:
                    total_discount += float(da.get('amount') or 0.0)
                except (ValueError, TypeError):
                    pass
            qty = int(raw_item.get('quantity') or 1)
            if qty <= 0:
                qty = 1
            net_price = raw_base - (total_discount / qty)
            return max(0.0, net_price)
    return float(base_price)


def _serialize_line_item(li):
    img_url = getattr(li, 'image_url', '') or ''
    if not img_url:
        img_url = _get_shopify_cached_image(li.sku, li.title)

    net_price = _get_line_item_net_price(li)

    return {
        'title': li.title,
        'sku': li.sku or '',
        'quantity': li.quantity,
        'price': f"{li.price:.2f}",
        'discounted_price': f"{net_price:.2f}",
        'variant': getattr(li, 'variant_title', '') or '',
        'image': img_url,
        'variant_id': li.variant_id,
    }


def _get_return_awb(case: ReturnExchangeCase) -> str:
    if case.return_awb:
        return case.return_awb
    if case.order:
        reqs = list(case.order.return_requests.all())
        if reqs:
            reqs_sorted = sorted(reqs, key=lambda r: r.created_at, reverse=True)
            rr = reqs_sorted[0]
            if rr and rr.awb_number:
                return rr.awb_number
    return ''


def _serialize_case(case: ReturnExchangeCase) -> dict:
    order = case.order

    # Determine shipping carrier
    shipping_carrier = 'N/A'
    fulfillments = list(order.fulfillments.all())
    if fulfillments:
        tf = fulfillments[0]
        tracking_infos = list(tf.tracking_info.all())
        if tracking_infos:
            ti = tracking_infos[0]
            if ti and ti.company:
                shipping_carrier = ti.company

    # Determine payment method: COD, PPCOD, or Prepaid
    payment_method = 'Prepaid'
    gateways = [g.lower() for g in (order.payment_gateway_names or [])]
    financial_status = (order.financial_status or '').lower()
    tags = (order.tags or '').lower()

    is_cod = False
    if any(x in gateways for x in ['cash_on_delivery', 'cash on delivery (cod)', 'cod']):
        is_cod = True
    elif financial_status == 'pending':
        is_cod = True

    is_partial = False
    if any(x in gateways for x in ['gokwik ppcod', 'ppcod', 'razorpay ppcod']):
        is_partial = True
    elif 'partial payment' in tags or financial_status == 'partially_paid':
        is_partial = True

    if is_partial:
        payment_method = 'PPCOD'
    elif is_cod:
        payment_method = 'COD'
    else:
        payment_method = 'Prepaid'

    returned_prods = _get_case_returned_products(case)
    product_value = sum(float(p['price']) * p['quantity'] for p in returned_prods)
    if case.refund_amount is not None:
        refund_amt = float(case.refund_amount)
    else:
        return_requests = _get_case_return_requests(case)
        calc = _get_return_request_refund_calculation(return_requests, product_value)
        refund_amt = float(calc['total_refundable'])

    return {
        'case_id': case.id,
        'case_type': case.case_type,
        'status': case.status,
        'remarks': case.remarks,
        'return_awb': _get_return_awb(case),
        'created_at': case.created_at.isoformat(),
        'updated_at': case.updated_at.isoformat(),
        'order_number': order.order_number,
        'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        'phone': order.contact_phone or '',
        'total_price': str(order.total_price or 0),
        'current_status': order.current_status or '',
        'products': returned_prods,
        'refund_amount': str(round(refund_amt, 2)),
        'batch': {
            'id': case.batch.id,
            'name': case.batch.name,
            'status': case.batch.status,
            'created_at': case.batch.created_at.isoformat(),
            'created_by': case.batch.created_by.email if case.batch.created_by else 'System',
        } if case.batch else None,
        'shipping_carrier': shipping_carrier,
        'payment_method': payment_method,
        # Source / intake
        'source': case.source or 'return_prime',
        'courier_name': case.courier_name or '',
        'self_shipped_tracking': case.self_shipped_tracking or '',
        'parcel_received_date': case.parcel_received_date.isoformat() if case.parcel_received_date else '',
        'parcel_condition': case.parcel_condition or '',
        'store_location': case.store_location or '',
        'received_by': case.received_by or '',
        'customer_present': case.customer_present,
        'replacement_product': case.replacement_product or '',
        'replacement_product_value': str(case.replacement_product_value) if case.replacement_product_value is not None else '',
        # Conversion
        'converted_to_exchange': case.converted_to_exchange,
    }


def _serialize_case_detail(case: ReturnExchangeCase) -> dict:
    """Full case detail payload including return request info and activities."""
    order = case.order
    return_requests = _get_case_return_requests(case)
    return_request = return_requests[0] if return_requests else None

    # Return request info
    return_request_data = None
    if return_request:
        raw = return_request.raw_data or {}
        exchange_product = raw.get('exchange_product', '') if isinstance(raw, dict) else ''
        
        # Calculate human-readable ref_no
        ref_no = return_request.return_prime_id
        if isinstance(raw, dict):
            ord_name = raw.get('order', {}).get('name', '')
            req_num = raw.get('request_number', '')
            if ord_name and req_num:
                ref_no = f"{ord_name.replace('#', '')}{req_num}"

        # Extract refund mode & details from first line item
        line_items_raw = raw.get('line_items', []) if isinstance(raw, dict) else []
        first_li = line_items_raw[0] if line_items_raw else {}
        refund_info = first_li.get('refund', {}) or {}
        refund_mode = refund_info.get('requested_mode', '') or ''
        refund_others_text = refund_info.get('refund_others_text', '') or ''
        refund_meta = refund_info.get('meta', '') or ''
        # Combine UPI/detail text
        refund_detail = refund_others_text or (str(refund_meta) if refund_meta else '')

        # Bank details from customer
        customer_raw = raw.get('customer', {}) or {} if isinstance(raw, dict) else {}
        bank_raw = customer_raw.get('bank', {}) or {}
        bank_details = {
            'account_holder': bank_raw.get('account_holder_name', '') or '',
            'account_number': bank_raw.get('account_number', '') or '',
            'ifsc_code': bank_raw.get('ifsc_code', '') or '',
        }
        # UPI ID: may be in refund_others_text when mode is 'upi' or 'others'
        upi_id = ''
        if refund_mode in ('upi', 'others') and refund_others_text:
            upi_id = refund_others_text

        # Payment details note (e.g. "Order was originally paid using cash_on_delivery")
        payment_details_raw = raw.get('payment_details', {}) or {}
        payment_details_note = ''
        if isinstance(payment_details_raw, dict):
            payment_details_note = payment_details_raw.get('note', '') or payment_details_raw.get('message', '') or ''
        elif isinstance(payment_details_raw, str):
            payment_details_note = payment_details_raw

        # Payment gateway from order
        pgw_names = order.payment_gateway_names or []
        payment_gateway = ', '.join(pgw_names) if pgw_names else ''

        calc = _get_return_request_refund_calculation(return_requests)

        return_request_data = {
            'id': return_request.id,
            'return_prime_id': return_request.return_prime_id,
            'ref_no': ref_no,
            'request_type': return_request.request_type,
            'status': return_request.status,
            'awb_number': return_request.awb_number or '',
            'refund_amount': str(return_request.refund_amount or 0),
            'customer_notes': return_request.customer_notes or '',
            'exchange_product': exchange_product,
            'created_at': return_request.created_at.isoformat(),
            'refund_mode': refund_mode,
            'refund_detail': refund_detail,
            'payment_gateway': payment_gateway,
            'bank_details': bank_details,
            'upi_id': upi_id,
            'payment_details_note': payment_details_note,
            'item_price': calc['item_price'],
            'incentive': calc['incentive'],
            'tax': calc['tax'],
            'discount': calc['discount'],
            'return_fee': calc['return_fee'],
            'total_refundable': calc['total_refundable'],
        }



    # Activities
    activities = [
        {
            'id': a.id,
            'action': a.action,
            'action_label': a.get_action_display(),
            'notes': a.notes,
            'performed_by': (
                a.performed_by.get_full_name() or a.performed_by.email
                if a.performed_by else 'System'
            ),
            'created_at': a.created_at.isoformat(),
        }
        for a in case.activities.select_related('performed_by').order_by('created_at')
    ]

    # Map returned products to return_items for the frontend detail table
    returned_products = _get_case_returned_products(case)
    return_items = []
    qc_status_val = 'passed' if case.status in ('exchange_pending', 'exchange_closed', 'completed', 'exchange_ready') else 'failed'
    
    # Extract physical condition assessed (choices mapping) and combine with QC notes
    condition_display = dict(case.CONDITION_CHOICES).get(case.condition, case.condition or '')
    qc_remark_parts = []
    if condition_display:
        qc_remark_parts.append(condition_display)
    if case.qc_notes:
        qc_remark_parts.append(case.qc_notes)
    qc_remark_val = ' - '.join(qc_remark_parts) if qc_remark_parts else 'Passed'

    for p in returned_products:
        return_items.append({
            'name': p.get('title') or p.get('name') or '',
            'sku': p.get('sku') or '',
            'price': str(p.get('price') or 0),
            'quantity': p.get('quantity') or 1,
            'qc_status': qc_status_val,
            'qc_remark': qc_remark_val,
            'image': p.get('image') or '',
        })

    # Map replacement products to exchange_items for the frontend
    replacement_products = (case.exchange_meta or {}).get('replacement_products', [])
    exchange_items = []
    for p in replacement_products:
        exchange_items.append({
            'name': p.get('title') or p.get('name') or '',
            'sku': p.get('sku') or '',
            'price': str(p.get('price') or 0),
            'quantity': p.get('quantity') or 1,
            'image': p.get('image') or '',
        })

    return {
        'case_id': case.id,
        'case_type': case.case_type,
        'status': case.status,
        'remarks': case.remarks,
        'return_awb': _get_return_awb(case),
        'created_at': case.created_at.isoformat(),
        'updated_at': case.updated_at.isoformat(),
        'created_by': (
            case.created_by.get_full_name() or case.created_by.email
            if case.created_by else ''
        ),
        # QC result metadata
        'condition': case.condition or '',
        'qc_notes': case.qc_notes or '',
        'qc_completed_at': case.qc_completed_at.isoformat() if case.qc_completed_at else None,
        'qc_completed_by': (
            case.qc_completed_by.get_full_name() or case.qc_completed_by.email
            if case.qc_completed_by else ''
        ),
        # Exchange metadata
        'exchange_exists': case.exchange_exists,
        'exchange_order_number': case.exchange_order_number or '',
        'exchange_status': case.exchange_status or '',
        'replacement_order_number': case.replacement_order_number or '',
        'replacement_order_status': case.replacement_order_status or '',
        'exchange_created_at': case.exchange_created_at.isoformat() if case.exchange_created_at else None,
        'replacement_products': replacement_products,
        'exchange_items': exchange_items,
        # Order / customer
        'order_id': order.id,
        'order_number': order.order_number,
        'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        'customer_first_name': order.customer_first_name or '',
        'customer_last_name': order.customer_last_name or '',
        'phone': order.contact_phone or '',
        'email': order.contact_email or '',
        'total_price': str(order.total_price or 0),
        'current_status': order.current_status or '',
        'financial_status': order.financial_status or '',
        'order_created_at': order.created_at.isoformat() if order.created_at else None,
        'products': returned_products,
        'return_items': return_items,
        'refund_screenshot': case.refund_screenshot.url if case.refund_screenshot else '',
        'refund_method': case.refund_method,
        'transaction_reference': case.transaction_reference or '',
        'wallet_credit_reference': case.wallet_credit_reference or '',
        'return_request': return_request_data,
        'activities': activities,
        'batch': {
            'id': case.batch.id,
            'name': case.batch.name,
            'status': case.batch.status,
            'created_at': case.batch.created_at.isoformat(),
            'created_by': case.batch.created_by.email if case.batch.created_by else 'System',
        } if case.batch else None,
        # Source / intake
        'source': case.source or 'return_prime',
        'courier_name': case.courier_name or '',
        'self_shipped_tracking': case.self_shipped_tracking or '',
        'manual_intake_notes': case.manual_intake_notes or '',
        'parcel_received_date': case.parcel_received_date.isoformat() if case.parcel_received_date else '',
        'parcel_condition': case.parcel_condition or '',
        'store_location': case.store_location or '',
        'received_by': case.received_by or '',
        'customer_present': case.customer_present,
        'replacement_product': case.replacement_product or '',
        'replacement_product_value': str(case.replacement_product_value) if case.replacement_product_value is not None else '',
        # Return → Exchange conversion
        'converted_to_exchange': case.converted_to_exchange,
        'conversion_notes': case.conversion_notes or '',
        'converted_by': (
            case.converted_by.get_full_name() or case.converted_by.email
            if case.converted_by else ''
        ),
        'converted_at': case.converted_at.isoformat() if case.converted_at else None,
        'conversion_product_data': case.conversion_product_data or {},
    }


def _serialize_activity(activity: ReturnExchangeActivity) -> dict:
    return {
        'id': activity.id,
        'action': activity.action,
        'action_label': activity.get_action_display(),
        'notes': activity.notes,
        'performed_by': (
            activity.performed_by.get_full_name() or activity.performed_by.email
            if activity.performed_by else ''
        ),
        'created_at': activity.created_at.isoformat(),
    }


def _calculate_exchange_settlement(case: ReturnExchangeCase) -> dict:
    """
    Compute original product value, replacement product value, difference, and settlement type.
    Difference = Replacement Value - Original Value
    """
    returned_prods = _get_case_returned_products(case)
    original_value = sum(float(p['price']) * p['quantity'] for p in returned_prods)

    replacement_prods = (case.exchange_meta or {}).get('replacement_products', [])
    replacement_value = sum(float(p.get('price', 0)) * p.get('quantity', 1) for p in replacement_prods)

    difference = replacement_value - original_value

    if difference < 0:
        settlement_type = 'refund_required'
    elif difference > 0:
        settlement_type = 'payment_required'
    else:
        settlement_type = 'no_settlement'

    return {
        'original_value': str(round(original_value, 2)),
        'replacement_value': str(round(replacement_value, 2)),
        'difference': str(round(difference, 2)),
        'settlement_type': settlement_type,
    }


def _serialize_exchange_row(case: ReturnExchangeCase, include_closed_fields=False) -> dict:
    order = case.order
    calc = _calculate_exchange_settlement(case)
    returned_prods = _get_case_returned_products(case)
    
    diff_val = float(case.difference_amount) if case.difference_amount is not None else float(calc['difference'])
    sett_type = case.settlement_type if case.settlement_type else calc['settlement_type']

    row = {
        'case_id': case.id,
        'case_type': case.case_type,
        'status': case.status,
        'return_awb': _get_return_awb(case),
        'created_at': case.created_at.isoformat(),
        'order_number': order.order_number,
        'exchange_order_number': case.exchange_order_number or '',
        'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        'phone': order.contact_phone or '',
        'original_value': calc['original_value'],
        'replacement_value': calc['replacement_value'],
        'difference': str(round(diff_val, 2)),
        'settlement_type': sett_type,
        'settlement_method': case.settlement_method or '',
        'batch': {
            'id': case.batch.id,
            'name': case.batch.name,
            'status': case.batch.status,
            'created_at': case.batch.created_at.isoformat(),
            'created_by': case.batch.created_by.email if case.batch.created_by else 'System',
        } if case.batch else None,
        'source': case.source or 'return_prime',
        'courier_name': case.courier_name or '',
        'converted_to_exchange': case.converted_to_exchange,
        'products': returned_prods,
    }
    
    if include_closed_fields:
        row['settlement_completed_at'] = case.settlement_completed_at.isoformat() if case.settlement_completed_at else None
        row['settlement_completed_by'] = (
            case.settlement_completed_by.get_full_name() or case.settlement_completed_by.email
            if case.settlement_completed_by else ''
        )
        row['payment_reference'] = case.payment_reference or ''
        row['settlement_notes'] = case.settlement_notes or ''
        row['settlement_rejection_reason'] = case.settlement_notes if case.status == 'rejected' else ''
        row['settlement_screenshot'] = case.refund_screenshot.url if case.refund_screenshot else ''
        
    return row


def _create_solo_batch(user, org_id):
    import re
    max_num = 1
    existing_batches = ReturnExchangeBatch.objects.filter(org_id=org_id, name__startswith="Batch ")
    for b in existing_batches:
        match = re.match(r"^Batch\s+(\d+)$", b.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    batch_name = f"Batch {max_num + 1}"

    return ReturnExchangeBatch.objects.create(
        name=batch_name,
        org_id=org_id,
        created_by=user,
        status='Open'
    )

def _build_scan_payload(order, return_request=None):
    if not return_request and order:
        return_request = order.return_requests.order_by('-created_at').first()

    case_type = _detect_case_type(return_request, order)
    return_awb = (return_request.awb_number if return_request else None) or ''

    existing_case = (
        ReturnExchangeCase.objects
        .filter(order=order)
        .exclude(status__in=['completed', 'rejected'])
        .select_related('order')
        .prefetch_related('order__line_items')
        .order_by('-created_at')
        .first()
    )

    shipping_carrier = 'N/A'
    tf = order.fulfillments.first()
    if tf:
        ti = tf.tracking_info.first()
        if ti and ti.company:
            shipping_carrier = ti.company

    payment_method = 'Prepaid'
    gateways = [g.lower() for g in (order.payment_gateway_names or [])]
    financial_status = (order.financial_status or '').lower()
    tags = (order.tags or '').lower()

    is_cod = False
    if any(x in gateways for x in ['cash_on_delivery', 'cash on delivery (cod)', 'cod']):
        is_cod = True
    elif financial_status == 'pending':
        is_cod = True

    is_partial = False
    if any(x in gateways for x in ['gokwik ppcod', 'ppcod', 'razorpay ppcod']):
        is_partial = True
    elif 'partial payment' in tags or financial_status == 'partially_paid':
        is_partial = True

    if is_partial:
        payment_method = 'PPCOD'
    elif is_cod:
        payment_method = 'COD'
    else:
        payment_method = 'Prepaid'

    return {
        'order_id': order.id,
        'order_number': order.order_number,
        'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        'phone': order.contact_phone or '',
        'return_awb': return_awb,
        'total_price': str(order.total_price or 0),
        'current_status': order.current_status or '',
        'financial_status': order.financial_status or '',
        'case_type': case_type,
        'products': [_serialize_line_item(li) for li in order.line_items.all()],
        'return_request_id': return_request.id if return_request else None,
        'existing_case': _serialize_case(existing_case) if existing_case else None,
        'shipping_carrier': shipping_carrier,
        'payment_method': payment_method,
    }


def _cache_scan_payload(payload, org_id=None):
    from django.core.cache import cache
    if not org_id:
        order_id = payload.get('order_id')
        if order_id:
            try:
                order = Order.objects.defer('raw_data').get(pk=order_id)
                org_id = order.org_id
            except Exception:
                pass
    if not org_id:
        return

    keys = []
    order_number = payload.get('order_number')
    order_id = payload.get('order_id')
    return_awb = payload.get('return_awb')

    if order_number:
        keys.append(f"returns_scan:org:{org_id}:ident:{order_number}")
    if order_id:
        keys.append(f"returns_scan:org:{org_id}:ident:{order_id}")
    if return_awb:
        keys.append(f"returns_scan:org:{org_id}:ident:{return_awb}")
        keys.append(f"returns_scan:org:{org_id}:ident:{return_awb.upper()}")

    rr_id = payload.get('return_request_id')
    if rr_id:
        try:
            rr = ReturnRequest.objects.get(pk=rr_id)
            if rr.request_number:
                keys.append(f"returns_scan:org:{org_id}:ident:{rr.request_number}")
                keys.append(f"returns_scan:org:{org_id}:ident:{rr.request_number.upper()}")
            if rr.return_prime_id:
                keys.append(f"returns_scan:org:{org_id}:ident:{rr.return_prime_id}")
                keys.append(f"returns_scan:org:{org_id}:ident:{rr.return_prime_id.upper()}")
        except ReturnRequest.DoesNotExist:
            pass

    for k in keys:
        if k:
            cache.set(k, payload, timeout=86400)


def _get_return_case_exists(order_id):
    from django.core.cache import cache
    cache_key = f"return_case_exists:order_id:{order_id}"
    exists = cache.get(cache_key)
    if exists is not None:
        return exists

    exists = ReturnExchangeCase.objects.filter(order_id=order_id).exists()
    cache.set(cache_key, exists, timeout=86400)
    return exists


# ─── views ──────────────────────────────────────────────────────────────────────

class ReturnEngineScanLookupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        scan_input = request.data.get('scan_input', '').strip()
        if not scan_input:
            return Response({'error': 'scan_input is required'}, status=400)

        org_id = _get_org_id(request)

        # ── Fast path: check Cache first ──
        from django.core.cache import cache
        cache_key = f"returns_scan:org:{org_id}:ident:{scan_input}"
        cached_payload = cache.get(cache_key)
        if cached_payload:
            order_id = cached_payload.get('order_id')
            # Check if case has been created in the meantime to avoid double scanning
            if _get_return_case_exists(order_id):
                cache.delete(cache_key)
            else:
                return Response(cached_payload)

        # ── Slow path: DB search ──
        return_request, order = _find_return_order(scan_input, org_id)

        if not order:
            return Response(
                {
                    'error': (
                        'No return/exchange found for this AWB. '
                        'Make sure you are scanning the RETURN shipment label '
                        '(assigned by the courier when the customer sent the parcel back), '
                        'not the original dispatch AWB.'
                    )
                },
                status=404,
            )

        # ── Prevent double scanning of the same order ──
        if _get_return_case_exists(order.id):
            return Response(
                {
                    'error': f'Order #{order.order_number} has already been scanned and processed. It cannot be scanned twice.'
                },
                status=400,
            )

        payload = _build_scan_payload(order, return_request)
        _cache_scan_payload(payload)

        return Response(payload)


class ReturnEngineBatchScanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw = request.data.get('scan_inputs', [])
        if not raw or not isinstance(raw, list):
            return Response({'error': 'scan_inputs must be a non-empty list'}, status=400)

        scan_inputs = [str(s).strip() for s in raw[:100] if str(s).strip()]
        if not scan_inputs:
            return Response({'error': 'No valid inputs provided'}, status=400)

        org_id = _get_org_id(request)
        results = []
        from django.core.cache import cache
        for inp in scan_inputs:
            cache_key = f"returns_scan:org:{org_id}:ident:{inp}"
            cached_payload = cache.get(cache_key)
            if cached_payload:
                order_id = cached_payload.get('order_id')
                if _get_return_case_exists(order_id):
                    cache.delete(cache_key)
                    results.append({
                        'input': inp,
                        'order': None,
                        'error': f"Order #{cached_payload.get('order_number')} has already been scanned and processed. It cannot be scanned twice.",
                        'already_scanned': True,
                    })
                else:
                    results.append({
                        'input': inp,
                        'order': cached_payload,
                        'error': None,
                        'already_scanned': False,
                    })
                continue

            return_request, order = _find_return_order(inp, org_id)
            if not order:
                results.append({
                    'input': inp,
                    'order': None,
                    'error': (
                        'No return/exchange found for this AWB. '
                        'Make sure you are scanning the RETURN shipment label '
                        '(assigned by the courier when the customer sent the parcel back), '
                        'not the original dispatch AWB.'
                    ),
                    'already_scanned': False,
                })
                continue

            if _get_return_case_exists(order.id):
                results.append({
                    'input': inp,
                    'order': None,
                    'error': f"Order #{order.order_number} has already been scanned and processed. It cannot be scanned twice.",
                    'already_scanned': True,
                })
                continue

            payload = _build_scan_payload(order, return_request)
            _cache_scan_payload(payload, org_id)
            results.append({
                'input': inp,
                'order': payload,
                'error': None,
                'already_scanned': False,
            })

        return Response({'results': results})


class ReturnEngineMoveToQCView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        remarks = request.data.get('remarks', '').strip()
        return_awb = request.data.get('return_awb', '').strip()

        if not order_id:
            return Response({'error': 'order_id is required'}, status=400)

        org_id = _get_org_id(request)

        from django.db import transaction
        with transaction.atomic():
            try:
                order = Order.objects.prefetch_related('line_items').get(pk=order_id, org_id=org_id)
            except Order.DoesNotExist:
                return Response({'error': 'Order not found'}, status=404)

            # ── Prevent double scanning of the same order ──
            if ReturnExchangeCase.objects.filter(order=order).exists():
                return Response(
                    {'error': f'Order #{order.order_number} has already been scanned and processed.'},
                    status=400,
                )

            return_request = order.return_requests.order_by('-created_at').first()
            case_type = _detect_case_type(return_request, order)

            if not return_awb and return_request and return_request.awb_number:
                return_awb = return_request.awb_number

            existing = ReturnExchangeCase.objects.filter(order=order, status='pending_qc').first()
            if existing:
                return Response({
                    'case': _serialize_case(existing),
                    'created': False,
                    'message': 'Case already exists in QC queue',
                })

            customer = None
            try:
                customer = order.customer
            except Exception:
                pass

            batch = _create_solo_batch(request.user, org_id)

            case = ReturnExchangeCase.objects.create(
                batch=batch,
                order=order,
                customer=customer,
                case_type=case_type,
                status='pending_qc',
                remarks=remarks,
                return_awb=return_awb,
                created_by=request.user,
            )

        # ── Exchange detection ────────────────────────────────────────────────
        # For exchange cases, check if a replacement order was created
        # so QC operators have visibility before performing inspection.
        if case_type == 'exchange':
            _sync_case_exchange_details(case, return_request)
        # ─────────────────────────────────────────────────────────────────────

        ReturnExchangeActivity.objects.create(
            case=case,
            action='parcel_scanned',
            notes=f'Return parcel scanned at warehouse. Linked to batch: {batch.name}. Return AWB: {return_awb or "N/A"}',
            performed_by=request.user,
        )

        ReturnExchangeActivity.objects.create(
            case=case,
            action='moved_to_qc',
            notes=remarks or f'Moved to QC queue under batch {batch.name}.',
            performed_by=request.user,
        )

        # If exchange already exists, add a detection timeline entry
        if case.exchange_exists:
            ReturnExchangeActivity.objects.create(
                case=case,
                action='exchange_initiated',
                notes=(
                    f'Exchange already created in Return Prime. '
                    f'Order: {case.exchange_order_number or "—"}. '
                    f'Replacement: {case.replacement_order_number or "—"}. '
                    f'Status: {case.exchange_status or "—"}.'
                ),
                performed_by=request.user,
            )

        return Response({
            'case': _serialize_case(case),
            'created': True,
            'message': 'Case moved to QC successfully',
        }, status=201)


class ReturnEngineCasesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        case_type_filter = request.query_params.get('case_type', '').strip().lower()
        source_filter = request.query_params.get('source', '').strip().lower()
        org_id = _get_org_id(request)
        
        # Check if requesting fast aggregated status counts
        get_counts = request.query_params.get('counts', '').strip().lower() == 'true'
        if get_counts:
            from django.db.models import Count
            qs = ReturnExchangeCase.objects.filter(order__org_id=org_id)
            if case_type_filter in ('return', 'exchange'):
                qs = qs.filter(case_type=case_type_filter)
            if source_filter:
                qs = qs.filter(source=source_filter)
            status_counts = qs.values('status').annotate(count=Count('id'))
            counts_dict = {item['status']: item['count'] for item in status_counts}
            return Response(counts_dict)

        status_filter = request.query_params.get('status', '').strip()
        q = request.query_params.get('q', '').strip()
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(10000, int(request.query_params.get('page_size', 50)))

        qs = (
            ReturnExchangeCase.objects
            .filter(order__org_id=org_id)
            .select_related('order', 'customer', 'created_by', 'batch', 'batch__created_by')
            .prefetch_related(
                'order__line_items',
                'order__return_requests',
                'order__fulfillments',
                'order__fulfillments__tracking_info',
            )
            .order_by(F('batch__created_at').desc(nulls_last=True), '-created_at')
        )

        if case_type_filter in ('return', 'exchange'):
            qs = qs.filter(case_type=case_type_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if source_filter:
            qs = qs.filter(source=source_filter)
        if q:
            qs = qs.filter(
                Q(order__order_number__icontains=q)
                | Q(order__customer_first_name__icontains=q)
                | Q(order__customer_last_name__icontains=q)
                | Q(order__contact_phone__icontains=q)
                | Q(return_awb__icontains=q)
                | Q(remarks__icontains=q)
            ).distinct()

        total = qs.count()
        offset = (page - 1) * page_size
        cases = qs[offset: offset + page_size]

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': [_serialize_case(c) for c in cases],
        })


class ReturnEngineCaseDetailView(APIView):
    """
    GET /api/returns-engine/cases/<case_id>/
    Full case detail: customer, products, return request, activities.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        org_id = _get_org_id(request)
        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order', 'customer', 'created_by', 'qc_completed_by')
                .prefetch_related(
                    'order__line_items',
                    'order__return_requests',
                    'activities__performed_by',
                )
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        return Response(_serialize_case_detail(case))


class ReturnEngineQCActionView(APIView):
    """
    POST /api/returns-engine/qc-action/

    Payload: { case_id, action: 'pass'|'fail', condition, notes }

    QC PASS:
      return   → pending_qc → refund_pending
      exchange → pending_qc → exchange_pending

    QC FAIL:
      any      → pending_qc → rejected
    """
    permission_classes = [IsAuthenticated]

    CONDITION_LABELS = {
        'good': 'Good Condition',
        'damaged': 'Damaged',
        'missing_parts': 'Missing Parts',
        'wrong_product': 'Wrong Product',
        'packaging_issue': 'Packaging Issue',
    }

    def post(self, request):
        case_id = request.data.get('case_id')
        action = request.data.get('action', '').strip().lower()
        condition = request.data.get('condition', '').strip()
        notes = request.data.get('notes', '').strip()

        if not case_id:
            return Response({'error': 'case_id is required'}, status=400)
        if action not in ('pass', 'fail'):
            return Response({'error': 'action must be "pass" or "fail"'}, status=400)

        org_id = _get_org_id(request)
        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order', 'created_by')
                .prefetch_related('order__line_items')
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        if case.status != 'pending_qc':
            return Response(
                {'error': f'Case is in status "{case.status}". Only pending_qc cases can be QC-actioned.'},
                status=400,
            )

        condition_label = self.CONDITION_LABELS.get(condition, condition or 'Not specified')
        qc_note = f"QC {'PASSED' if action == 'pass' else 'FAILED'} | Condition: {condition_label}"
        if notes:
            qc_note += f" | Notes: {notes}"

        # Append to remarks
        case.remarks = (case.remarks + '\n' + qc_note).strip() if case.remarks else qc_note

        # Save QC metadata fields
        case.condition = condition
        case.qc_notes = notes
        case.qc_completed_by = request.user
        case.qc_completed_at = timezone.now()

        if action == 'pass':
            calc = None
            if case.case_type == 'exchange':
                calc = _calculate_exchange_settlement(case)

            if case.case_type == 'exchange' and case.exchange_exists:
                sett_type = calc['settlement_type']
                new_status = 'exchange_closed'
                case.settlement_type = sett_type
                case.difference_amount = float(calc['difference'])
                case.settlement_completed_at = timezone.now()
                case.settlement_completed_by = request.user
                case.settlement_method = 'no_settlement' if sett_type == 'no_settlement' else 'auto_settled'
            else:
                new_status = 'refund_pending' if case.case_type == 'return' else 'exchange_pending'
            
            case.status = new_status
            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='qc_passed',
                notes=f"Condition: {condition_label}. {notes}".strip('. '),
                performed_by=request.user,
            )

            if case.case_type == 'return':
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='refund_initiated',
                    notes='Moved to Refund Queue.',
                    performed_by=request.user,
                )
                message = 'QC Passed — moved to Refund Queue'
            else:
                if case.status == 'exchange_closed':
                    # Replacement order already exists — verify, don't re-initiate
                    ReturnExchangeActivity.objects.create(
                        case=case,
                        action='exchange_initiated',
                        notes=(
                            f'Original product received. Exchange verified. '
                            f'Replacement order {case.replacement_order_number or case.exchange_order_number} '
                            f'was already created (status: {case.replacement_order_status or case.exchange_status or "unknown"}).'
                        ),
                        performed_by=request.user,
                    )
                    
                    ReturnExchangeActivity.objects.create(
                        case=case,
                        action='settlement_started',
                        notes='Exchange settlement process started automatically (exchange order already exists).',
                        performed_by=request.user,
                    )
                    
                    if case.settlement_type == 'refund_required':
                        ReturnExchangeActivity.objects.create(
                            case=case,
                            action='refund_processed',
                            notes=f"Refund Difference of ₹{abs(case.difference_amount)} marked as auto-settled because exchange order was already created.",
                            performed_by=request.user,
                        )
                    elif case.settlement_type == 'payment_required':
                        ReturnExchangeActivity.objects.create(
                            case=case,
                            action='payment_collected',
                            notes=f"Additional Payment of ₹{case.difference_amount} marked as auto-collected/auto-settled because exchange order was already created.",
                            performed_by=request.user,
                        )
                    else:
                        ReturnExchangeActivity.objects.create(
                            case=case,
                            action='no_settlement_req',
                            notes='No settlement required. Exchange values matched.',
                            performed_by=request.user,
                        )
                    
                    ReturnExchangeActivity.objects.create(
                        case=case,
                        action='exchange_closed',
                        notes='Exchange case successfully settled and closed automatically.',
                        performed_by=request.user,
                    )
                    message = 'QC Passed — exchange case settled and closed automatically'
                else:
                    # case.status is 'exchange_pending'
                    if case.exchange_exists:
                        # Exchange is already created, but we need to refund difference or collect payment, so it goes to settlement queue
                        diff_amt = abs(float(calc['difference'])) if calc else 0.0
                        sett_type = calc['settlement_type'] if calc else 'refund_required'
                        if sett_type == 'refund_required':
                            note_text = f"Exchange order already exists, but a Refund Difference of ₹{diff_amt} is required. Moved to Exchange Settlement Queue."
                            msg = 'QC Passed — exchange order exists, but refund difference is required. Moved to Exchange Settlement Queue'
                        else:
                            note_text = f"Exchange order already exists, but an Additional Payment of ₹{diff_amt} is required. Moved to Exchange Settlement Queue."
                            msg = 'QC Passed — exchange order exists, but additional payment is required. Moved to Exchange Settlement Queue'

                        ReturnExchangeActivity.objects.create(
                            case=case,
                            action='moved_to_exchange_settlement',
                            notes=note_text,
                            performed_by=request.user,
                        )
                        message = msg
                    else:
                        ReturnExchangeActivity.objects.create(
                            case=case,
                            action='moved_to_exchange_settlement',
                            notes='Moved to Exchange Settlement.',
                            performed_by=request.user,
                        )
                        message = 'QC Passed — moved to Exchange Settlement'

        else:
            case.status = 'rejected'
            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='qc_failed',
                notes=f"Condition: {condition_label}. {notes}".strip('. '),
                performed_by=request.user,
            )
            ReturnExchangeActivity.objects.create(
                case=case,
                action='rejected',
                notes='Case rejected after QC inspection.',
                performed_by=request.user,
            )
            message = 'QC Failed — case rejected'

        # Re-fetch full detail
        case = (
            ReturnExchangeCase.objects
            .select_related('order', 'created_by', 'qc_completed_by')
            .prefetch_related(
                'order__line_items',
                'order__return_requests',
                'activities__performed_by',
            )
            .get(pk=case_id, order__org_id=org_id)
        )
        return Response({
            'case_id': case.id,
            'status': case.status,
            'message': message,
            'case': _serialize_case_detail(case),
        })


class ReturnEngineSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        status_filter = request.query_params.get('status', '').strip()
        case_type_filter = request.query_params.get('case_type', '').strip()
        source_filter = request.query_params.get('source', '').strip().lower()
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(50, int(request.query_params.get('page_size', 20)))

        org_id = _get_org_id(request)
        qs = (
            ReturnExchangeCase.objects
            .filter(order__org_id=org_id)
            .select_related('order', 'customer', 'created_by')
            .prefetch_related('order__line_items')
            .order_by('-created_at')
        )

        if q:
            qs = qs.filter(
                Q(order__order_number__icontains=q)
                | Q(order__customer_first_name__icontains=q)
                | Q(order__customer_last_name__icontains=q)
                | Q(order__contact_phone__icontains=q)
                | Q(return_awb__icontains=q)
                | Q(remarks__icontains=q)
            ).distinct()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if case_type_filter:
            qs = qs.filter(case_type=case_type_filter)
        if source_filter:
            qs = qs.filter(source=source_filter)

        total = qs.count()
        offset = (page - 1) * page_size
        cases = qs[offset: offset + page_size]

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': [_serialize_case(c) for c in cases],
        })


class ReturnEngineActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        org_id = _get_org_id(request)
        try:
            case = ReturnExchangeCase.objects.get(pk=case_id, order__org_id=org_id)
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        activities = case.activities.select_related('performed_by').order_by('created_at')
        return Response({
            'case_id': case.id,
            'status': case.status,
            'activities': [_serialize_activity(a) for a in activities],
        })


# ─────────────────────────────────────────────────────────────────────────────
# DAY 3 — REFUND QUEUE
# ─────────────────────────────────────────────────────────────────────────────

class ReturnEngineRefundListView(APIView):
    """
    GET /api/returns-engine/refunds/

    Supports ?tab=queue (default) or ?tab=closed

    tab=queue  → refund_pending cases + pending summary stats
    tab=closed → completed + rejected cases + closed summary stats

    Supports: ?q= ?page= ?page_size= ?date_from= ?date_to=
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum
        from django.utils import timezone as tz

        tab = request.query_params.get('tab', 'queue').strip().lower()
        q = request.query_params.get('q', '').strip()
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(10000, int(request.query_params.get('page_size', 50)))
        date_from = request.query_params.get('date_from', '').strip()
        date_to = request.query_params.get('date_to', '').strip()
        source_filter = request.query_params.get('source', '').strip().lower()

        def _serialize_refund_row(case, include_closed_fields=False):
            order = case.order
            return_requests = _get_case_return_requests(case)
            return_request = return_requests[0] if return_requests else None
            returned_prods = _get_case_returned_products(case)

            product_value = sum(float(p['price']) * p['quantity'] for p in returned_prods)
            if case.refund_amount is not None:
                refund_amt = float(case.refund_amount)
            else:
                calc = _get_return_request_refund_calculation(return_requests, product_value)
                refund_amt = float(calc['total_refundable'])

            # Extract refund mode — line_items[0].refund.requested_mode
            refund_mode = ''
            if return_request:
                raw = return_request.raw_data or {}
                if isinstance(raw, dict):
                    line_items_raw = raw.get('line_items', [])
                    first_li = line_items_raw[0] if line_items_raw else {}
                    refund_info = first_li.get('refund', {}) or {}
                    refund_mode = refund_info.get('requested_mode', '') or ''

            row = {
                'case_id': case.id,
                'case_type': case.case_type,
                'status': case.status,
                'return_awb': _get_return_awb(case),
                'created_at': case.created_at.isoformat(),
                'order_number': order.order_number,
                'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
                'phone': order.contact_phone or '',
                'total_price': str(order.total_price or 0),
                'refund_amount': str(round(refund_amt, 2)),
                'refund_mode': refund_mode,
                'refund_method': case.refund_method,
                'transaction_reference': case.transaction_reference or '',
                'wallet_credit_reference': case.wallet_credit_reference or '',
                'qc_completed_by': (
                    case.qc_completed_by.get_full_name() or case.qc_completed_by.email
                    if case.qc_completed_by else ''
                ),
                'qc_completed_at': case.qc_completed_at.isoformat() if case.qc_completed_at else None,
                'condition': case.condition or '',
                'products': returned_prods,
                'batch': {
                    'id': case.batch.id,
                    'name': case.batch.name,
                    'status': case.batch.status,
                    'created_at': case.batch.created_at.isoformat(),
                    'created_by': case.batch.created_by.email if case.batch.created_by else 'System',
                } if case.batch else None,
                'source': case.source or 'return_prime',
                'courier_name': case.courier_name or '',
                'converted_to_exchange': case.converted_to_exchange,
            }

            if include_closed_fields:
                row['refund_completed_at'] = case.refund_completed_at.isoformat() if case.refund_completed_at else None
                row['refund_completed_by'] = (
                    case.refund_completed_by.get_full_name() or case.refund_completed_by.email
                    if case.refund_completed_by else ''
                )
                row['refund_rejection_reason'] = case.refund_rejection_reason or ''

            return row

        org_id = _get_org_id(request)

        # ── QUEUE TAB (refund_pending) ────────────────────────────────────────
        if tab == 'queue':
            qs = (
                ReturnExchangeCase.objects
                .filter(case_type='return', status='refund_pending', order__org_id=org_id)
                .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'batch', 'batch__created_by')
                .prefetch_related(
                    'order__line_items',
                    'order__return_requests',
                    'order__fulfillments',
                    'order__fulfillments__tracking_info',
                )
                .order_by(F('batch__created_at').desc(nulls_last=True), '-created_at')
            )

            if q:
                qs = qs.filter(
                    Q(order__order_number__icontains=q)
                    | Q(order__customer_first_name__icontains=q)
                    | Q(order__customer_last_name__icontains=q)
                    | Q(order__contact_phone__icontains=q)
                    | Q(return_awb__icontains=q)
                ).distinct()
            if source_filter:
                qs = qs.filter(source=source_filter)
            if date_from:
                try:
                    qs = qs.filter(created_at__date__gte=date_from)
                except Exception:
                    pass
            if date_to:
                try:
                    qs = qs.filter(created_at__date__lte=date_to)
                except Exception:
                    pass

            total = qs.count()
            offset = (page - 1) * page_size
            cases = qs[offset: offset + page_size]

            # Summary stats across ALL pending (not just this page)
            all_pending = ReturnExchangeCase.objects.filter(
                case_type='return', status='refund_pending', order__org_id=org_id
            ).prefetch_related('order__line_items', 'order__return_requests')
            if source_filter:
                all_pending = all_pending.filter(source=source_filter)
            pending_count = all_pending.count()

            pending_amount = 0
            for case in all_pending:
                if case.refund_amount is not None:
                    pending_amount += float(case.refund_amount)
                elif case.order:
                    return_reqs = _get_case_return_requests(case)
                    fallback = sum(float(li.price) * li.quantity for li in case.order.line_items.all())
                    calc = _get_return_request_refund_calculation(return_reqs, fallback)
                    pending_amount += float(calc['total_refundable'])

            today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_today_qs = ReturnExchangeCase.objects.filter(
                case_type='return', status='completed',
                refund_completed_at__gte=today_start,
                order__org_id=org_id,
            )
            if source_filter:
                completed_today_qs = completed_today_qs.filter(source=source_filter)
            completed_today = completed_today_qs.count()

            all_refunded = ReturnExchangeCase.objects.filter(
                case_type='return', status='completed', refund_amount__isnull=False,
                order__org_id=org_id,
            )
            if source_filter:
                all_refunded = all_refunded.filter(source=source_filter)

            # Combined conditional aggregation
            refund_stats = all_refunded.aggregate(
                total=Sum('refund_amount'),
                bank=Sum('refund_amount', filter=Q(refund_method='bank_transfer')),
                upi=Sum('refund_amount', filter=Q(refund_method='upi')),
                store_credit=Sum('refund_amount', filter=Q(refund_method='store_credit'))
            )
            total_refunded_amount = refund_stats['total'] or 0
            bank_refund_amount = refund_stats['bank'] or 0
            upi_refund_amount = refund_stats['upi'] or 0
            store_credit_amount = refund_stats['store_credit'] or 0

            return Response({
                'tab': 'queue',
                'count': total,
                'page': page,
                'page_size': page_size,
                'summary': {
                    'pending_count': pending_count,
                    'completed_today': completed_today,
                    'pending_amount': str(round(pending_amount, 2)),
                    'total_refunded_amount': str(total_refunded_amount),
                    'bank_refund_amount': str(bank_refund_amount),
                    'upi_refund_amount': str(upi_refund_amount),
                    'store_credit_amount': str(store_credit_amount),
                },
                'results': [_serialize_refund_row(c) for c in cases],
            })

        # ── CLOSED TAB (completed + rejected) ────────────────────────────────
        qs = (
            ReturnExchangeCase.objects
            .filter(case_type='return', status__in=['completed', 'rejected'], order__org_id=org_id)
            .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'refund_completed_by', 'batch', 'batch__created_by')
            .prefetch_related(
                'order__line_items',
                'order__return_requests',
                'order__fulfillments',
                'order__fulfillments__tracking_info',
            )
            .order_by(F('batch__created_at').desc(nulls_last=True), '-refund_completed_at', '-updated_at')
        )

        if q:
            qs = qs.filter(
                Q(order__order_number__icontains=q)
                | Q(order__customer_first_name__icontains=q)
                | Q(order__customer_last_name__icontains=q)
                | Q(order__contact_phone__icontains=q)
                | Q(return_awb__icontains=q)
            ).distinct()
        if source_filter:
            qs = qs.filter(source=source_filter)
        if date_from:
            try:
                qs = qs.filter(refund_completed_at__date__gte=date_from)
            except Exception:
                pass
        if date_to:
            try:
                qs = qs.filter(refund_completed_at__date__lte=date_to)
            except Exception:
                pass

        # status sub-filter for closed tab (completed | rejected)
        closed_status = request.query_params.get('status', '').strip().lower()
        if closed_status in ('completed', 'rejected'):
            qs = qs.filter(status=closed_status)

        total = qs.count()
        offset = (page - 1) * page_size
        cases = qs[offset: offset + page_size]

        # Summary stats for closed tab
        today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_today_qs = ReturnExchangeCase.objects.filter(
            case_type='return', status__in=['completed', 'rejected'],
            refund_completed_at__gte=today_start,
            order__org_id=org_id,
        )
        if source_filter:
            closed_today_qs = closed_today_qs.filter(source=source_filter)
        closed_today = closed_today_qs.count()

        total_closed_qs = ReturnExchangeCase.objects.filter(
            case_type='return', status__in=['completed', 'rejected'],
            order__org_id=org_id,
        )
        if source_filter:
            total_closed_qs = total_closed_qs.filter(source=source_filter)
        total_closed = total_closed_qs.count()

        total_completed_qs = ReturnExchangeCase.objects.filter(
            case_type='return', status='completed',
            order__org_id=org_id,
        )
        if source_filter:
            total_completed_qs = total_completed_qs.filter(source=source_filter)
        total_completed = total_completed_qs.count()

        total_rejected_qs = ReturnExchangeCase.objects.filter(
            case_type='return', status='rejected',
            order__org_id=org_id,
        )
        if source_filter:
            total_rejected_qs = total_rejected_qs.filter(source=source_filter)
        total_rejected = total_rejected_qs.count()

        all_refunded = ReturnExchangeCase.objects.filter(
            case_type='return', status='completed', refund_amount__isnull=False,
            order__org_id=org_id,
        )
        if source_filter:
            all_refunded = all_refunded.filter(source=source_filter)

        # Combined conditional aggregation
        refund_stats = all_refunded.aggregate(
            total=Sum('refund_amount'),
            bank=Sum('refund_amount', filter=Q(refund_method='bank_transfer')),
            upi=Sum('refund_amount', filter=Q(refund_method='upi')),
            store_credit=Sum('refund_amount', filter=Q(refund_method='store_credit'))
        )
        total_refunded_amount = refund_stats['total'] or 0
        bank_refund_amount = refund_stats['bank'] or 0
        upi_refund_amount = refund_stats['upi'] or 0
        store_credit_amount = refund_stats['store_credit'] or 0

        return Response({
            'tab': 'closed',
            'count': total,
            'page': page,
            'page_size': page_size,
            'summary': {
                'closed_today': closed_today,
                'total_closed': total_closed,
                'total_completed': total_completed,
                'total_rejected': total_rejected,
                'total_refunded_amount': str(total_refunded_amount),
                'bank_refund_amount': str(bank_refund_amount),
                'upi_refund_amount': str(upi_refund_amount),
                'store_credit_amount': str(store_credit_amount),
            },
            'results': [_serialize_refund_row(c, include_closed_fields=True) for c in cases],
        })



class ReturnEngineRefundDetailView(APIView):
    """
    GET /api/returns-engine/refunds/<case_id>/
    Full case detail — reuses _serialize_case_detail plus refund fields.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        org_id = _get_org_id(request)
        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'refund_completed_by')
                .prefetch_related(
                    'order__line_items',
                    'order__return_requests',
                    'activities__performed_by',
                )
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        data = _serialize_case_detail(case)

        # Refund-specific fields not in _serialize_case_detail yet
        data['refund_amount'] = str(case.refund_amount) if case.refund_amount else None
        data['refund_notes'] = case.refund_notes or ''
        data['refund_completed_at'] = case.refund_completed_at.isoformat() if case.refund_completed_at else None
        data['refund_completed_by'] = (
            case.refund_completed_by.get_full_name() or case.refund_completed_by.email
            if case.refund_completed_by else ''
        )
        data['refund_rejection_reason'] = case.refund_rejection_reason or ''
        data['refund_screenshot'] = _get_refund_screenshot_url(case)

        # Computed refundable amount = sum of returned product prices
        returned_prods = _get_case_returned_products(case)
        product_value = sum(float(p['price']) * p['quantity'] for p in returned_prods)
        data['product_value'] = str(round(product_value, 2))
        data['order_value'] = str(case.order.total_price or 0)

        # Dynamic Refund Calculation mapping
        return_requests = _get_case_return_requests(case)
        calc = _get_return_request_refund_calculation(return_requests, product_value)
        if case.refund_amount is not None:
            calc['total_refundable'] = str(case.refund_amount)
        data['refund_calculation'] = calc

        return Response(data)


class ReturnEngineRefundActionView(APIView):
    """
    POST /api/returns-engine/refund-action/

    Payload:
      { case_id, action: 'approve'|'reject', refund_amount, notes, rejection_reason }

    approve → status: completed
    reject  → status: rejected
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        case_id = request.data.get('case_id')
        action = request.data.get('action', '').strip().lower()
        refund_amount = request.data.get('refund_amount')
        notes = request.data.get('notes', '').strip()
        rejection_reason = request.data.get('rejection_reason', '').strip()

        if not case_id:
            return Response({'error': 'case_id is required'}, status=400)
        if action not in ('approve', 'reject'):
            return Response({'error': 'action must be "approve" or "reject"'}, status=400)

        org_id = _get_org_id(request)
        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order', 'refund_completed_by')
                .prefetch_related('order__line_items')
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        if case.status != 'refund_pending':
            return Response({'error': f'Case is not in refund_pending status (current: {case.status})'}, status=400)

        now = timezone.now()

        if action == 'approve':
            refund_method = request.data.get('refund_method', 'bank_transfer').strip().lower()
            transaction_reference = request.data.get('transaction_reference', '').strip()

            if refund_method not in ('bank_transfer', 'upi', 'store_credit'):
                return Response({'error': 'Invalid refund_method'}, status=400)

            # Compute final refund amount: use provided or derive from products
            if refund_amount:
                try:
                    amt = round(float(refund_amount), 2)
                    if amt < 0:
                        return Response({'error': 'refund_amount cannot be negative'}, status=400)
                    limit_val = float(case.order.total_price or 0.0)
                    if amt > limit_val:
                        return Response({'error': f'refund_amount cannot exceed order total of ₹{limit_val}'}, status=400)
                except (ValueError, TypeError):
                    return Response({'error': 'Invalid refund_amount'}, status=400)
            else:
                return_requests = _get_case_return_requests(case)
                fallback_val = sum(
                    float(li.price) * li.quantity
                    for li in case.order.line_items.all()
                )
                calc = _get_return_request_refund_calculation(return_requests, fallback_val)
                amt = round(float(calc['total_refundable']), 2)

            case.status = 'completed'
            case.refund_amount = amt
            case.refund_notes = notes
            case.refund_completed_at = now
            case.refund_completed_by = request.user
            case.refund_method = refund_method
            
            if refund_method == 'store_credit':
                import uuid
                case.wallet_credit_reference = f"SC-{case.id}-{uuid.uuid4().hex[:6].upper()}"
            else:
                case.transaction_reference = transaction_reference
                # Save refund screenshot if uploaded
                screenshot = request.FILES.get('refund_screenshot')
                if screenshot:
                    case.refund_screenshot = screenshot

            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='refund_initiated',
                notes=f'Refund approved. Amount: ₹{amt}. {notes}'.strip('. '),
                performed_by=request.user,
            )

            if refund_method == 'store_credit':
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='store_credit_issued',
                    notes=f'Amount: ₹{amt}',
                    performed_by=request.user,
                )
            else:
                method_label = 'Bank Transfer' if refund_method == 'bank_transfer' else 'UPI'
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='refund_completed',
                    notes=f'Method: {method_label}\nAmount: ₹{amt}',
                    performed_by=request.user,
                )
            message = f'Refund of ₹{amt} approved and marked completed'

        else:  # reject
            case.status = 'rejected'
            case.refund_notes = notes
            case.refund_rejection_reason = rejection_reason or notes
            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='rejected',
                notes=f'Refund rejected. Reason: {rejection_reason or notes or "Not specified"}.',
                performed_by=request.user,
            )
            message = 'Refund rejected'

        # Re-fetch for full detail
        case = (
            ReturnExchangeCase.objects
            .select_related('order', 'created_by', 'qc_completed_by', 'refund_completed_by')
            .prefetch_related('order__line_items', 'order__return_requests', 'activities__performed_by')
            .get(pk=case_id, order__org_id=org_id)
        )

        data = _serialize_case_detail(case)
        data['refund_amount'] = str(case.refund_amount) if case.refund_amount else None
        data['refund_notes'] = case.refund_notes or ''
        data['refund_completed_at'] = case.refund_completed_at.isoformat() if case.refund_completed_at else None
        data['refund_completed_by'] = (
            case.refund_completed_by.get_full_name() or case.refund_completed_by.email
            if case.refund_completed_by else ''
        )
        data['refund_rejection_reason'] = case.refund_rejection_reason or ''
        data['refund_screenshot'] = _get_refund_screenshot_url(case)
        
        returned_prods = _get_case_returned_products(case)
        product_value = sum(float(p['price']) * p['quantity'] for p in returned_prods)
        data['product_value'] = str(round(product_value, 2))
        return_requests = _get_case_return_requests(case)
        data['refund_calculation'] = _get_return_request_refund_calculation(return_requests, product_value)

        return Response({'message': message, 'status': case.status, 'case': data})


class ReturnEngineExchangeListView(APIView):
    """
    GET /api/returns-engine/exchange-settlement/

    Supports ?tab=queue (default) or ?tab=closed

    tab=queue  → exchange_pending cases + queue summary stats
    tab=closed → exchange_closed cases + closed summary stats

    Supports: ?q= ?page= ?page_size= ?date_from= ?date_to=
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Sum
        from django.utils import timezone as tz

        tab = request.query_params.get('tab', 'queue').strip().lower()
        q = request.query_params.get('q', '').strip()
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(10000, int(request.query_params.get('page_size', 50)))
        date_from = request.query_params.get('date_from', '').strip()
        date_to = request.query_params.get('date_to', '').strip()
        source_filter = request.query_params.get('source', '').strip().lower()

        org_id = _get_org_id(request)

        # ── QUEUE TAB (exchange_pending) ────────────────────────────────────────
        if tab == 'queue':
            qs = (
                ReturnExchangeCase.objects
                .filter(case_type='exchange', status='exchange_pending', order__org_id=org_id)
                .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'batch', 'batch__created_by')
                .prefetch_related(
                    'order__line_items',
                    'order__return_requests',
                    'order__fulfillments',
                    'order__fulfillments__tracking_info',
                )
                .order_by(F('batch__created_at').desc(nulls_last=True), '-created_at')
            )

            if q:
                qs = qs.filter(
                    Q(order__order_number__icontains=q)
                    | Q(order__customer_first_name__icontains=q)
                    | Q(order__customer_last_name__icontains=q)
                    | Q(order__contact_phone__icontains=q)
                    | Q(return_awb__icontains=q)
                ).distinct()
            if source_filter:
                qs = qs.filter(source=source_filter)
            if date_from:
                try:
                    qs = qs.filter(created_at__date__gte=date_from)
                except Exception:
                    pass
            if date_to:
                try:
                    qs = qs.filter(created_at__date__lte=date_to)
                except Exception:
                    pass

            total = qs.count()
            offset = (page - 1) * page_size
            cases = qs[offset: offset + page_size]

            # Summary stats across ALL pending exchanges (not just this page)
            all_pending = (
                ReturnExchangeCase.objects
                .filter(case_type='exchange', status='exchange_pending', order__org_id=org_id)
                .select_related('order')
                .prefetch_related('order__line_items', 'order__return_requests')
            )
            if source_filter:
                all_pending = all_pending.filter(source=source_filter)
            pending_count = all_pending.count()

            pending_refund_amount = 0
            pending_payment_amount = 0
            for case in all_pending:
                calc = _calculate_exchange_settlement(case)
                diff = float(case.difference_amount) if case.difference_amount is not None else float(calc['difference'])
                if diff < 0:
                    pending_refund_amount += abs(diff)
                elif diff > 0:
                    pending_payment_amount += diff

            today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_today_qs = ReturnExchangeCase.objects.filter(
                case_type='exchange', status__in=['exchange_closed', 'rejected'],
                settlement_completed_at__gte=today_start,
                order__org_id=org_id,
            )
            if source_filter:
                completed_today_qs = completed_today_qs.filter(source=source_filter)
            completed_today = completed_today_qs.count()

            return Response({
                'tab': 'queue',
                'count': total,
                'page': page,
                'page_size': page_size,
                'summary': {
                    'pending_count': pending_count,
                    'completed_today': completed_today,
                    'pending_refund_amount': str(round(pending_refund_amount, 2)),
                    'pending_payment_amount': str(round(pending_payment_amount, 2)),
                },
                'results': [_serialize_exchange_row(c) for c in cases],
            })

        # ── CLOSED TAB (exchange_closed or rejected) ─────────────────────
        qs = (
            ReturnExchangeCase.objects
            .filter(case_type='exchange', status__in=['exchange_closed', 'rejected'], order__org_id=org_id)
            .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'settlement_completed_by', 'batch', 'batch__created_by')
            .prefetch_related(
                'order__line_items',
                'order__return_requests',
                'order__fulfillments',
                'order__fulfillments__tracking_info',
            )
            .order_by(F('batch__created_at').desc(nulls_last=True), '-settlement_completed_at', '-updated_at')
        )

        if q:
            qs = qs.filter(
                Q(order__order_number__icontains=q)
                | Q(order__customer_first_name__icontains=q)
                | Q(order__customer_last_name__icontains=q)
                | Q(order__contact_phone__icontains=q)
                | Q(return_awb__icontains=q)
            ).distinct()
        if source_filter:
            qs = qs.filter(source=source_filter)
        if date_from:
            try:
                qs = qs.filter(settlement_completed_at__date__gte=date_from)
            except Exception:
                pass
        if date_to:
            try:
                qs = qs.filter(settlement_completed_at__date__lte=date_to)
            except Exception:
                pass

        total = qs.count()
        offset = (page - 1) * page_size
        cases = qs[offset: offset + page_size]

        # Summary stats for closed tab
        today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_today_qs = ReturnExchangeCase.objects.filter(
            case_type='exchange', status__in=['exchange_closed', 'rejected'],
            settlement_completed_at__gte=today_start,
            order__org_id=org_id,
        )
        if source_filter:
            closed_today_qs = closed_today_qs.filter(source=source_filter)
        closed_today = closed_today_qs.count()

        total_closed_qs = ReturnExchangeCase.objects.filter(
            case_type='exchange', status__in=['exchange_closed', 'rejected'],
            order__org_id=org_id,
        )
        if source_filter:
            total_closed_qs = total_closed_qs.filter(source=source_filter)
        total_closed = total_closed_qs.count()

        # SQL Aggregate sum calculations to replace Python loops
        from django.db.models import Q
        closed_stats = total_closed_qs.filter(status='exchange_closed').aggregate(
            total_refunded=Sum('difference_amount', filter=Q(difference_amount__lt=0)),
            total_collected=Sum('difference_amount', filter=Q(difference_amount__gt=0))
        )
        total_refunded_amount = abs(float(closed_stats['total_refunded'] or 0.0))
        total_collected_amount = float(closed_stats['total_collected'] or 0.0)

        return Response({
            'tab': 'closed',
            'count': total,
            'page': page,
            'page_size': page_size,
            'summary': {
                'closed_today': closed_today,
                'total_closed': total_closed,
                'total_refunded_amount': str(round(total_refunded_amount, 2)),
                'total_collected_amount': str(round(total_collected_amount, 2)),
            },
            'results': [_serialize_exchange_row(c, include_closed_fields=True) for c in cases],
        })


class ReturnEngineExchangeDetailView(APIView):
    """
    GET /api/returns-engine/exchange-settlement/<case_id>/
    Full case detail for exchange settlement workspace.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, case_id):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Unauthorized: Organization not found'}, status=403)
        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'settlement_completed_by')
                .prefetch_related(
                    'order__line_items',
                    'order__return_requests',
                    'activities__performed_by',
                )
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        # Dynamically sync/refresh exchange details from ReturnRequest or linked Order if they exist
        return_request = case.order.return_requests.order_by('-created_at').first()
        if case.case_type == 'exchange':
            _sync_case_exchange_details(case, return_request)

        data = _serialize_case_detail(case)

        # Exchange-specific fields
        calc = _calculate_exchange_settlement(case)
        data['difference_amount'] = str(case.difference_amount) if case.difference_amount is not None else calc['difference']
        data['settlement_type'] = case.settlement_type if case.settlement_type else calc['settlement_type']
        data['settlement_method'] = case.settlement_method or ''
        data['settlement_notes'] = case.settlement_notes or ''
        data['settlement_completed_at'] = case.settlement_completed_at.isoformat() if case.settlement_completed_at else None
        data['settlement_completed_by'] = (
            case.settlement_completed_by.get_full_name() or case.settlement_completed_by.email
            if case.settlement_completed_by else ''
        )
        data['payment_reference'] = case.payment_reference or ''
        data['product_value'] = calc['original_value']
        data['original_value'] = calc['original_value']
        data['replacement_value'] = calc['replacement_value']
        data['calculated_difference'] = calc['difference']
        data['difference'] = str(case.difference_amount) if case.difference_amount is not None else calc['difference']
        data['settlement_rejection_reason'] = case.settlement_notes if case.status == 'rejected' else ''
        data['settlement_screenshot'] = (
            request.build_absolute_uri(case.refund_screenshot.url)
            if case.refund_screenshot else ''
        )

        return Response(data)


class ReturnEngineExchangeActionView(APIView):
    """
    POST /api/returns-engine/exchange-action/

    Payload:
      {
        case_id,
        action: 'settle' | 'reject' | 'refund_difference' | 'collect_payment' | 'close_without_settlement',
        settlement_method,   # e.g., bank_transfer, upi, store_credit, cash, manual
        payment_reference,   # Txn ID or reference
        notes,
        rejection_reason,
        settlement_screenshot # file upload
      }

    Transitions status from exchange_pending -> exchange_closed or rejected
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Unauthorized: Organization not found'}, status=403)
        import uuid
        case_id = request.data.get('case_id')
        action = request.data.get('action', '').strip().lower()
        settlement_method = request.data.get('settlement_method', '').strip()
        payment_reference = request.data.get('payment_reference', '').strip()
        notes = request.data.get('notes', '').strip()
        rejection_reason = request.data.get('rejection_reason', '').strip()

        if not case_id:
            return Response({'error': 'case_id is required'}, status=400)

        try:
            case = (
                ReturnExchangeCase.objects
                .select_related('order')
                .prefetch_related('order__line_items')
                .get(pk=case_id, order__org_id=org_id)
            )
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        if case.status != 'exchange_pending':
            return Response({'error': f'Case is in status "{case.status}". Only exchange_pending cases can be settled.'}, status=400)

        calc = _calculate_exchange_settlement(case)
        diff_val = float(calc['difference'])
        sett_type = calc['settlement_type']
        now = timezone.now()

        # Handle frontend 'settle' action mapping dynamically based on settlement_type
        if action == 'settle':
            if sett_type == 'refund_required':
                action = 'refund_difference'
            elif sett_type == 'payment_required':
                action = 'collect_payment'
            else:
                action = 'close_without_settlement'

        if action not in ('refund_difference', 'collect_payment', 'close_without_settlement', 'reject'):
            return Response({'error': 'Invalid action'}, status=400)

        # Handle reject
        if action == 'reject':
            case.status = 'rejected'
            case.settlement_notes = rejection_reason or notes
            case.settlement_completed_at = now
            case.settlement_completed_by = request.user
            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='rejected',
                notes=f"Exchange case rejected and voided. Reason: {rejection_reason or notes or 'Not specified'}.",
                performed_by=request.user,
            )
            return Response({
                'message': 'Exchange case rejected and voided successfully.',
                'status': case.status,
                'case': _serialize_exchange_row(case, include_closed_fields=True),
            })

        # Update case fields for successful closure
        case.status = 'exchange_closed'
        case.settlement_type = sett_type
        case.difference_amount = diff_val
        case.settlement_notes = notes
        case.settlement_completed_at = now
        case.settlement_completed_by = request.user

        # Save screenshot if uploaded
        screenshot = request.FILES.get('settlement_screenshot')
        if screenshot:
            case.refund_screenshot = screenshot

        ReturnExchangeActivity.objects.create(
            case=case,
            action='settlement_started',
            notes='Exchange settlement process started.',
            performed_by=request.user,
        )

        if action == 'refund_difference':
            if not settlement_method:
                return Response({'error': 'settlement_method is required for refunds'}, status=400)
            
            case.settlement_method = settlement_method
            if settlement_method == 'store_credit':
                ref = f"SC-{case.id}-{uuid.uuid4().hex[:6].upper()}"
                case.payment_reference = ref
                case.wallet_credit_reference = ref
                act_notes = f"Refund Difference of ₹{abs(diff_val)} issued as Store Credit. Reference: {ref}"
            else:
                case.payment_reference = payment_reference
                act_notes = f"Refund Difference of ₹{abs(diff_val)} processed via {settlement_method.replace('_', ' ').title()}."
                if payment_reference:
                    act_notes += f" Reference: {payment_reference}"

            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='refund_processed',
                notes=act_notes,
                performed_by=request.user,
            )

        elif action == 'collect_payment':
            if not settlement_method:
                return Response({'error': 'settlement_method is required for payment collection'}, status=400)
            
            case.settlement_method = settlement_method
            case.payment_reference = payment_reference
            case.save()

            act_notes = f"Additional Payment of ₹{diff_val} collected via {settlement_method.replace('_', ' ').title()}."
            if payment_reference:
                act_notes += f" Reference: {payment_reference}"

            ReturnExchangeActivity.objects.create(
                case=case,
                action='payment_collected',
                notes=act_notes,
                performed_by=request.user,
            )

        else: # close_without_settlement
            case.settlement_method = 'no_settlement'
            case.save()

            ReturnExchangeActivity.objects.create(
                case=case,
                action='no_settlement_req',
                notes='No settlement required. Exchange values matched.',
                performed_by=request.user,
            )

        ReturnExchangeActivity.objects.create(
            case=case,
            action='exchange_closed',
            notes='Exchange case successfully settled and closed.',
            performed_by=request.user,
        )

        # Return full detail
        case = (
            ReturnExchangeCase.objects
            .select_related('order', 'customer', 'created_by', 'qc_completed_by', 'settlement_completed_by')
            .prefetch_related(
                'order__line_items',
                'order__return_requests',
                'activities__performed_by',
            )
            .get(pk=case_id, order__org_id=org_id)
        )
        return Response({
            'message': 'Exchange case settled and closed successfully.',
            'status': case.status,
            'case': _serialize_exchange_row(case, include_closed_fields=True),
        })


class ReturnEngineBatchCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Unauthorized: Organization not found'}, status=403)
        items = request.data.get('items', [])
        if not items:
            return Response({'error': 'No items selected for batching'}, status=400)

        # Generate Batch Name (e.g., Batch 2, Batch 3, etc. starting from Batch 2)
        import re
        max_num = 1
        existing_batches = ReturnExchangeBatch.objects.filter(org_id=org_id, name__startswith="Batch ")
        for b in existing_batches:
            match = re.match(r"^Batch\s+(\d+)$", b.name)
            if match:
                max_num = max(max_num, int(match.group(1)))
        batch_name = f"Batch {max_num + 1}"

        # Create Batch
        batch = ReturnExchangeBatch.objects.create(
            name=batch_name,
            org_id=org_id,
            created_by=request.user,
            status='Open'
        )

        cases_created = 0
        for item in items:
            order_id = item.get('order_id')
            remarks = item.get('remarks', '').strip()
            return_awb = item.get('return_awb', '').strip()

            if not order_id:
                continue

            try:
                order = Order.objects.prefetch_related('line_items').get(pk=order_id, org_id=org_id)
            except Order.DoesNotExist:
                continue

            # Prevent double scanning
            if ReturnExchangeCase.objects.filter(order=order).exists():
                existing_case = ReturnExchangeCase.objects.filter(order=order).first()
                if existing_case and not existing_case.batch:
                    existing_case.batch = batch
                    existing_case.save()
                    cases_created += 1
                continue

            return_request = order.return_requests.order_by('-created_at').first()
            case_type = _detect_case_type(return_request, order)

            if not return_awb and return_request and return_request.awb_number:
                return_awb = return_request.awb_number

            customer = None
            try:
                customer = order.customer
            except Exception:
                pass

            case = ReturnExchangeCase.objects.create(
                batch=batch,
                order=order,
                customer=customer,
                case_type=case_type,
                status='pending_qc',
                remarks=remarks,
                return_awb=return_awb,
                created_by=request.user,
            )

            # Exchange detection
            if case_type == 'exchange' and return_request:
                exch = _get_exchange_details(return_request)
                case.exchange_exists = exch['exchange_exists']
                case.exchange_order_number = exch['exchange_order_number']
                case.exchange_status = exch['exchange_status']
                case.replacement_order_number = exch['replacement_order_number']
                case.replacement_order_status = exch['replacement_order_status']
                case.exchange_created_at = exch['exchange_created_at']
                case.exchange_meta = {'replacement_products': exch['replacement_products']}
                case.save(update_fields=[
                    'exchange_exists', 'exchange_order_number', 'exchange_status',
                    'replacement_order_number', 'replacement_order_status',
                    'exchange_created_at', 'exchange_meta',
                ])

            ReturnExchangeActivity.objects.create(
                case=case,
                action='parcel_scanned',
                notes=f'Return parcel scanned at warehouse. Linked to batch: {batch_name}. Return AWB: {return_awb or "N/A"}',
                performed_by=request.user,
            )

            ReturnExchangeActivity.objects.create(
                case=case,
                action='moved_to_qc',
                notes=remarks or f'Moved to QC queue under batch {batch_name}.',
                performed_by=request.user,
            )

            if case.exchange_exists:
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='exchange_initiated',
                    notes=(
                        f'Exchange already created in Return Prime. '
                        f'Order: {case.exchange_order_number or "—"}. '
                        f'Replacement: {case.replacement_order_number or "—"}. '
                        f'Status: {case.exchange_status or "—"}.'
                    ),
                    performed_by=request.user,
                )

            cases_created += 1

        return Response({
            'message': f'Batch {batch.name} created successfully with {cases_created} cases.',
            'batch_id': batch.id,
            'batch_name': batch.name,
            'cases_created': cases_created,
        }, status=201)


# ─── Product Search (for Convert-to-Exchange modal autocomplete) ────────────────

class ReturnEngineProductSearchView(APIView):
    """
    GET /api/returns-engine/product-search/?q=<query>

    Searches LineItem records for product suggestions to use in the
    Convert-to-Exchange modal. Returns deduplicated results by (title, sku).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Unauthorized: Organization not found'}, status=403)
        from .models import LineItem
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'results': []})

        qs = (
            LineItem.objects
            .filter(
                Q(title__icontains=q) | Q(sku__icontains=q),
                order__org_id=org_id
            )
            .values('title', 'sku', 'price', 'name')
            .order_by('title')
        )[:80]

        # Deduplicate by (title, sku)
        seen = set()
        results = []
        from .models import ReturnRequest
        for item in qs:
            key = (item['title'], item['sku'] or '')
            if key in seen:
                continue
            seen.add(key)
            
            # Look up matching product image from previous ReturnRequests
            img_url = ''
            sku = item['sku']
            title = item['title']
            matching_req = None
            if sku:
                matching_req = ReturnRequest.objects.filter(raw_data__icontains=sku, order__org_id=org_id).first()
            if not matching_req:
                matching_req = ReturnRequest.objects.filter(raw_data__icontains=title, order__org_id=org_id).first()
                
            if matching_req and isinstance(matching_req.raw_data, dict):
                line_items_raw = matching_req.raw_data.get('line_items', [])
                for li in line_items_raw:
                    orig_prod = li.get('original_product') or {}
                    if (sku and orig_prod.get('sku') == sku) or (orig_prod.get('title') == title):
                        img_obj = orig_prod.get('image')
                        if isinstance(img_obj, dict):
                            img_url = img_obj.get('src') or ''
                        elif isinstance(img_obj, str):
                            img_url = img_obj
                        if img_url:
                            break

            if not img_url:
                from inventory.models import ShopifyProductCache
                p_cache = None
                if sku:
                    p_cache = ShopifyProductCache.objects.filter(Q(data__sku=sku) | Q(data__sku__icontains=sku)).first()
                if not p_cache and title:
                    p_cache = ShopifyProductCache.objects.filter(data__name__icontains=title).first()
                if p_cache:
                    img_url = p_cache.data.get('image') or ''

            results.append({
                'title': item['title'],
                'sku': item['sku'] or '',
                'price': str(item['price']),
                'variant': item['name'] or item['title'],
                'image': img_url,
            })

        return Response({'results': results})


# ─── Convert Return → Exchange ──────────────────────────────────────────────────

class ReturnEngineConvertToExchangeView(APIView):
    """
    POST /api/returns-engine/convert-to-exchange/

    Converts a refund_pending (return) case into an exchange_pending case.
    Operations uses this when a customer changes their mind and prefers an
    exchange instead of a refund.

    Payload:
        case_id                    – required
        replacement_product_name   – required
        replacement_product_sku    – optional
        replacement_product_value  – required (numeric, price per unit)
        replacement_product_variant – optional (variant description)
        replacement_product_qty    – optional (default 1)
        notes                      – optional reason/notes
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Unauthorized: Organization not found'}, status=403)
        from django.utils import timezone

        case_id = request.data.get('case_id')
        notes = (request.data.get('notes') or '').strip()

        # Validate
        if not case_id:
            return Response({'error': 'case_id is required.'}, status=400)

        try:
            case = ReturnExchangeCase.objects.select_related('order', 'batch').get(pk=case_id, order__org_id=org_id)
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found.'}, status=404)

        if case.status not in ('refund_pending', 'pending_qc', 'qc_pending'):
            return Response({
                'error': f'Only refund_pending or pending_qc cases can be converted. Current status: {case.status}.'
            }, status=400)

        replacement_products_input = request.data.get('replacement_products')
        replacement_products = []

        if isinstance(replacement_products_input, list) and len(replacement_products_input) > 0:
            for idx, p in enumerate(replacement_products_input):
                p_name = (p.get('name') or p.get('title') or '').strip()
                p_sku = (p.get('sku') or '').strip()
                p_variant = (p.get('variant') or '').strip()
                p_qty = int(p.get('qty') or p.get('quantity') or 1)
                p_original_price = p.get('price') or p.get('original_price') or 0
                p_discount = str(p.get('discount') or '').strip()
                p_image = (p.get('image') or '').strip()

                if not p_name:
                    return Response({'error': f'Product #{idx+1} name/title is required.'}, status=400)
                try:
                    p_original_price = float(p_original_price)
                except (TypeError, ValueError):
                    return Response({'error': f'Product #{idx+1} price must be a number.'}, status=400)

                # Calculate discount
                discount_amount = 0
                if p_discount:
                    if p_discount.endswith('%'):
                        try:
                            pct = float(p_discount.rstrip('%'))
                            discount_amount = (p_original_price * p_qty) * (pct / 100.0)
                        except ValueError:
                            return Response({'error': f'Product #{idx+1} discount percentage is invalid.'}, status=400)
                    else:
                        try:
                            discount_amount = float(p_discount)
                        except ValueError:
                            return Response({'error': f'Product #{idx+1} discount value is invalid.'}, status=400)

                total_val = (p_original_price * p_qty) - discount_amount
                unit_price = round(max(0.0, total_val) / p_qty, 2)

                if not p_image:
                    from inventory.models import ShopifyProductCache
                    p_cache = None
                    if p_sku:
                        p_cache = ShopifyProductCache.objects.filter(Q(data__sku=p_sku) | Q(data__sku__icontains=p_sku)).first()
                    if not p_cache and p_name:
                        p_cache = ShopifyProductCache.objects.filter(data__name__icontains=p_name).first()
                    if p_cache:
                        p_image = p_cache.data.get('image') or ''

                replacement_products.append({
                    'title': p_name,
                    'sku': p_sku,
                    'price': unit_price,
                    'variant': p_variant,
                    'quantity': p_qty,
                    'original_price': p_original_price,
                    'discount': p_discount,
                    'source': 'manual_conversion',
                    'image': p_image,
                })
        else:
            # Fallback to single product parameters
            product_name = (request.data.get('replacement_product_name') or '').strip()
            product_sku = (request.data.get('replacement_product_sku') or '').strip()
            product_value = request.data.get('replacement_product_value')
            product_variant = (request.data.get('replacement_product_variant') or '').strip()
            product_qty = int(request.data.get('replacement_product_qty') or 1)

            if not product_name:
                return Response({'error': 'replacement_product_name is required.'}, status=400)
            if product_value is None:
                return Response({'error': 'replacement_product_value is required.'}, status=400)

            try:
                product_value = float(product_value)
            except (TypeError, ValueError):
                return Response({'error': 'replacement_product_value must be a number.'}, status=400)

            product_image = ''
            from inventory.models import ShopifyProductCache
            p_cache = None
            if product_sku:
                p_cache = ShopifyProductCache.objects.filter(Q(data__sku=product_sku) | Q(data__sku__icontains=product_sku)).first()
            if not p_cache and product_name:
                p_cache = ShopifyProductCache.objects.filter(data__name__icontains=product_name).first()
            if p_cache:
                product_image = p_cache.data.get('image') or ''

            replacement_products.append({
                'title': product_name,
                'sku': product_sku,
                'price': product_value,
                'variant': product_variant,
                'quantity': product_qty,
                'source': 'manual_conversion',
                'image': product_image,
            })

        # Merge into exchange_meta
        existing_meta = case.exchange_meta or {}
        existing_meta['replacement_products'] = replacement_products
        existing_meta['converted_via'] = 'manual'

        # Update the case
        case.case_type = 'exchange'
        case.status = 'exchange_pending'
        case.exchange_meta = existing_meta
        case.converted_to_exchange = True
        case.conversion_notes = notes
        case.converted_by = request.user
        case.converted_at = timezone.now()
        case.conversion_product_data = {
            'title': replacement_products[0]['title'],
            'sku': replacement_products[0]['sku'],
            'price': replacement_products[0]['price'],
            'variant': replacement_products[0]['variant'],
            'quantity': replacement_products[0]['quantity'],
            'products': replacement_products,
        }
        case.save(update_fields=[
            'case_type', 'status', 'exchange_meta',
            'converted_to_exchange', 'conversion_notes',
            'converted_by', 'converted_at', 'conversion_product_data',
            'updated_at',
        ])

        # Timeline entries
        prod_descriptions = []
        for idx, p in enumerate(replacement_products):
            desc = f"{p['title']} (SKU: {p['sku'] or '—'}) x {p['quantity']} @ ₹{p['price']:.2f}"
            if p.get('discount'):
                desc += f" (discount: {p['discount']})"
            prod_descriptions.append(desc)

        notes_str = "; ".join(prod_descriptions)

        ReturnExchangeActivity.objects.create(
            case=case,
            action='converted_to_exchange',
            notes=(
                f'Case converted from Return to Exchange by {request.user.get_full_name() or request.user.email}. '
                f'Replacement products: {notes_str}. '
                f'Reason: {notes or "No reason provided."}'
            ),
            performed_by=request.user,
        )
        ReturnExchangeActivity.objects.create(
            case=case,
            action='moved_to_exchange_settlement',
            notes='Case moved to Exchange Settlement Queue after return-to-exchange conversion.',
            performed_by=request.user,
        )

        logger.info(
            'Case %s converted from return to exchange by %s',
            case.id, request.user.email,
        )

        return Response({
            'message': f'Case #{case.id} successfully converted to exchange.',
            'case_id': case.id,
            'new_status': case.status,
            'new_case_type': case.case_type,
        }, status=200)


# ─── Order Lookup for Manual Intake ──────────────────────────────────────────

class ReturnEngineOrderLookupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order_number = (request.query_params.get('order_number') or '').strip()
        if not order_number:
            return Response({'error': 'order_number is required'}, status=400)

        org_id = _get_org_id(request)
        _sync_order_from_shopify_by_number(order_number, org_id)

        try:
            clean_num = ''.join(filter(str.isdigit, str(order_number)))
            if clean_num:
                order = Order.objects.prefetch_related('line_items').get(order_number=int(clean_num), org_id=org_id)
            else:
                raise Order.DoesNotExist()
        except Order.DoesNotExist:
            return Response({'error': f'Order #{order_number} not found.'}, status=404)
        except Order.MultipleObjectsReturned:
            order = Order.objects.filter(order_number=int(clean_num), org_id=org_id).order_by('-created_at').first()

        existing_case = ReturnExchangeCase.objects.filter(order=order).first()

        payload = {
            'id': order.id,
            'order_number': order.order_number,
            'customer_name': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
            'phone': order.contact_phone or '',
            'email': order.contact_email or '',
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'total_price': str(order.total_price or 0),
            'products': [_serialize_line_item(li) for li in order.line_items.all()],
            'existing_case': {
                'id': existing_case.id,
                'status': existing_case.status,
                'case_type': existing_case.case_type,
            } if existing_case else None,
        }
        return Response(payload)


# ─── Manual / Self-Shipped & Walk-In Intake ──────────────────────────────────

class ReturnEngineManualIntakeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        source_type = request.data.get('source_type')  # 'self_shipped' or 'walk_in'
        order_number = request.data.get('order_number')
        case_type = request.data.get('case_type', 'return')  # 'return' or 'exchange'
        notes = request.data.get('notes', '').strip()

        # Handle backward compatibility / default for old Self-Shipped endpoint
        if not source_type:
            source_type = 'self_shipped'

        # Validation
        if source_type not in ('self_shipped', 'walk_in'):
            return Response({'error': 'Valid source_type is required ("self_shipped" or "walk_in")'}, status=400)
        if not order_number:
            return Response({'error': 'order_number is required'}, status=400)
        if case_type not in ('return', 'exchange'):
            return Response({'error': 'case_type must be "return" or "exchange"'}, status=400)

        # Source specific fields
        courier_name = request.data.get('courier_name', '').strip()
        tracking_number = request.data.get('tracking_number', '').strip()
        parcel_received_date = request.data.get('parcel_received_date')
        parcel_condition = request.data.get('parcel_condition', '').strip()

        store_location = request.data.get('store_location', '').strip()
        received_by = request.data.get('received_by', '').strip()
        customer_present = bool(request.data.get('customer_present', False))
        refund_amount = request.data.get('refund_amount')

        parsed_refund_amount = None
        if refund_amount is not None and str(refund_amount).strip() != '':
            try:
                parsed_refund_amount = round(float(refund_amount), 2)
            except ValueError:
                pass

        if source_type == 'self_shipped':
            if not courier_name:
                return Response({'error': 'courier_name is required for Self Shipped source'}, status=400)
        elif source_type == 'walk_in':
            if not store_location:
                return Response({'error': 'store_location is required for Walk-In source'}, status=400)
            if not received_by:
                return Response({'error': 'received_by is required for Walk-In source'}, status=400)

        # Lookup order
        org_id = _get_org_id(request)
        _sync_order_from_shopify_by_number(order_number, org_id)

        try:
            clean_num = ''.join(filter(str.isdigit, str(order_number)))
            if clean_num:
                order = Order.objects.prefetch_related('line_items').get(order_number=int(clean_num), org_id=org_id)
            else:
                raise Order.DoesNotExist()
        except Order.DoesNotExist:
            return Response({'error': f'Order #{order_number} not found.'}, status=404)
        except Order.MultipleObjectsReturned:
            order = Order.objects.filter(order_number=int(clean_num), org_id=org_id).order_by('-created_at').first()

        # Prevent double case creation
        if ReturnExchangeCase.objects.filter(order=order).exists():
            existing_case = ReturnExchangeCase.objects.filter(order=order).first()
            return Response({
                'error': f'A case (#{existing_case.id}) already exists for order #{order_number}.',
                'existing_case_id': existing_case.id,
            }, status=400)

        # Parse date
        from datetime import datetime
        parsed_date = None
        if parcel_received_date:
            try:
                parsed_date = datetime.strptime(parcel_received_date, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Resolve customer
        customer = order.customer
        user = request.user
        user_name = user.get_full_name() or user.email

        # Create a new batch for this manual case
        batch = _create_solo_batch(user, org_id)

        # Create case
        case = ReturnExchangeCase.objects.create(
            batch=batch,
            order=order,
            customer=customer,
            case_type=case_type,
            status='pending_qc',
            source=source_type,
            courier_name=courier_name if source_type == 'self_shipped' else '',
            self_shipped_tracking=tracking_number if source_type == 'self_shipped' else '',
            parcel_received_date=parsed_date,
            parcel_condition=parcel_condition if source_type == 'self_shipped' else '',
            store_location=store_location if source_type == 'walk_in' else '',
            received_by=received_by if source_type == 'walk_in' else '',
            customer_present=customer_present if source_type == 'walk_in' else False,
            refund_amount=parsed_refund_amount,
            manual_intake_notes=notes,
            remarks=notes,
            created_by=user,
        )

        replacement_product_data = request.data.get('replacement_product')
        p_title = ''
        p_sku = ''
        p_price = 0.0

        if case_type == 'exchange':
            if replacement_product_data and replacement_product_data.get('title'):
                p_title = replacement_product_data.get('title')
                p_sku = replacement_product_data.get('sku') or ''
                p_variant = replacement_product_data.get('variant') or ''
                p_price = replacement_product_data.get('price') or 0.0
                p_image = replacement_product_data.get('image') or ''

                try:
                    p_price = float(p_price)
                except (TypeError, ValueError):
                    p_price = 0.0

                case.replacement_product = p_title
                case.replacement_product_value = p_price
                case.exchange_meta = {
                    'replacement_products': [{
                        'title': p_title,
                        'sku': p_sku,
                        'price': p_price,
                        'variant': p_variant,
                        'quantity': 1,
                        'image': p_image,
                    }]
                }
                case.save(update_fields=['replacement_product', 'replacement_product_value', 'exchange_meta'])

        # Create Timeline Entries based on type/source
        if source_type == 'self_shipped':
            if case_type == 'return':
                # Self Shipped Case Created
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='self_shipped_case_created',
                    notes=f"Self Shipped Case Created by {user_name}. Linked to batch: {batch.name}.",
                    performed_by=user,
                )
                # Courier Registered
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='courier_registered',
                    notes=f"Courier registered: {courier_name}. Tracking number: {tracking_number or 'N/A'}.",
                    performed_by=user,
                )
            else:  # exchange
                # Self Shipped Exchange Created
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='self_shipped_exchange_created',
                    notes=f"Self Shipped Exchange Created by {user_name}. Linked to batch: {batch.name}.",
                    performed_by=user,
                )
                # Replacement Product Selected
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='replacement_product_selected',
                    notes=f"Replacement product selected: {p_title} (SKU: {p_sku}) @ ₹{p_price:.2f}.",
                    performed_by=user,
                )

            # Common for self_shipped: Parcel Received and Moved to QC
            ReturnExchangeActivity.objects.create(
                case=case,
                action='parcel_received',
                notes=f"Parcel received on {parcel_received_date or 'N/A'}. Condition: {parcel_condition or 'N/A'}.",
                performed_by=user,
            )
            ReturnExchangeActivity.objects.create(
                case=case,
                action='moved_to_qc',
                notes=f"Moved to QC queue under batch {batch.name}.",
                performed_by=user,
            )

        else:  # walk_in
            if case_type == 'return':
                # Walk In Return Registered
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='walk_in_return_registered',
                    notes=f"Walk In Return Registered by {user_name} at {store_location}. Linked to batch: {batch.name}.",
                    performed_by=user,
                )
            else:  # exchange
                # Walk In Exchange Registered
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='walk_in_exchange_registered',
                    notes=f"Walk In Exchange Registered by {user_name} at {store_location}. Linked to batch: {batch.name}.",
                    performed_by=user,
                )
                # Replacement Product Selected
                ReturnExchangeActivity.objects.create(
                    case=case,
                    action='replacement_product_selected',
                    notes=f"Replacement product selected: {p_title} (SKU: {p_sku}) @ ₹{p_price:.2f}.",
                    performed_by=user,
                )

            # Common for walk_in: Received At Store and Moved to QC
            ReturnExchangeActivity.objects.create(
                case=case,
                action='received_at_store',
                notes=f"Received at store by {received_by}. Customer present: {'Yes' if customer_present else 'No'}.",
                performed_by=user,
            )
            ReturnExchangeActivity.objects.create(
                case=case,
                action='moved_to_qc',
                notes=f"Moved to QC queue under batch {batch.name}.",
                performed_by=user,
            )

        logger.info(
            'Manual case %s (source: %s) created for order #%s by %s',
            case.id, source_type, order_number, user.email,
        )

        return Response({
            'message': f'Manual intake case #{case.id} created for order #{order_number}.',
            'case_id': case.id,
            'order_number': order_number,
            'customer': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
            'case_type': case_type,
            'status': case.status,
            'source': case.source,
        }, status=201)

# Alias for backward compatibility
ReturnEngineSelfShippedIntakeView = ReturnEngineManualIntakeView


# ─── Product Variants (for exchange modal variant dropdown) ───────────────────

class ReturnEngineProductVariantsView(APIView):
    """
    GET /api/returns-engine/products/<product_id>/variants/

    Fetches all variants for a Shopify product so the exchange modal can
    display a variant dropdown with title, SKU, price, and inventory quantity.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        import requests as http_requests
        from core.models import ShopCredentials

        user = request.user
        org_id = getattr(user, 'org_id', None)
        if not org_id and hasattr(user, 'organization') and user.organization:
            org_id = user.organization_id

        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            return Response({'error': 'Shopify credentials not configured.'}, status=404)

        from core.models import decrypt_data
        import base64

        shop_url = (
            creds.get_shopify_shop_url()
            if hasattr(creds, 'get_shopify_shop_url') else None
        ) or getattr(creds, 'myshopify_domain', '') or ''
        clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
        api_version = getattr(creds, 'shopify_api_version', None) or '2024-07'

        # Build auth headers
        if getattr(creds, 'auth_method', '') == 'oauth' and getattr(creds, 'shopify_access_token_encrypted', None):
            token = decrypt_data(creds.shopify_access_token_encrypted)
            headers = {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
        else:
            api_key = creds.get_shopify_api_key() if hasattr(creds, 'get_shopify_api_key') else ''
            password = creds.get_shopify_password() if hasattr(creds, 'get_shopify_password') else ''
            api_key = api_key or ''
            password = password or ''
            if password and password.startswith('shpat_'):
                headers = {'X-Shopify-Access-Token': password, 'Content-Type': 'application/json'}
            else:
                encoded = base64.b64encode(f"{api_key}:{password}".encode()).decode()
                headers = {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}

        url = f"https://{clean_domain}/admin/api/{api_version}/products/{product_id}.json?fields=id,title,variants,images"
        try:
            resp = http_requests.get(url, headers=headers, timeout=10)
            if not resp.ok:
                return Response({'error': f'Shopify API error {resp.status_code}'}, status=502)
            product = resp.json().get('product', {})
        except Exception as e:
            logger.exception('Error fetching Shopify product variants for product %s', product_id)
            return Response({'error': str(e)}, status=500)

        # Build image lookup by position
        images = {img.get('id'): img.get('src', '') for img in product.get('images', [])}
        product_image = product.get('image', {}).get('src', '') if product.get('image') else ''

        variants = []
        for v in product.get('variants', []):
            # Pick the image for this variant
            img_id = v.get('image_id')
            img_src = images.get(img_id, product_image)
            variants.append({
                'id': v.get('id'),
                'title': v.get('title', ''),
                'sku': v.get('sku', ''),
                'price': v.get('price', '0'),
                'inventory_quantity': v.get('inventory_quantity', 0),
                'image': img_src,
                'option1': v.get('option1', ''),
                'option2': v.get('option2', ''),
                'option3': v.get('option3', ''),
            })

        return Response({
            'product_id': product_id,
            'product_title': product.get('title', ''),
            'variants': variants,
        })


# ─── Create Shopify Exchange Order from Manual Intake ────────────────────────

class ReturnEngineCreateExchangeOrderView(APIView):
    """
    POST /api/returns-engine/create-exchange-order/

    Creates a REAL Shopify replacement order when the operations team registers
    a manual exchange from the Self Shipped / Walk-In intake corner.

    Payload:
        case_id                 – required
        replacement_products    – list of {variant_id, name, sku, variant_title, price, qty, image}
        notes                   – optional

    Workflow:
        1. Validate the case and fetch parent order (customer/address data).
        2. Build Shopify order payload with replacement line items.
        3. POST to Shopify Admin API → get real order number.
        4. Sync new order into local DB (Order record, linked as exchange order).
        5. Create a mock ReturnRequest of type EXCHANGE with replacement details.
        6. Update ReturnExchangeCase fields (exchange_exists, exchange_order_number, etc.).
        7. Write 6 audit trail activities.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import requests as http_requests
        from django.utils import timezone as tz
        from core.models import ShopCredentials, Order, LineItem, ReturnRequest, decrypt_data
        import base64, uuid, json

        case_id = request.data.get('case_id')
        notes = (request.data.get('notes') or '').strip()
        replacement_products_input = request.data.get('replacement_products') or []
        is_paid_input = request.data.get('is_paid')
        is_paid = True if is_paid_input is None else bool(is_paid_input)

        # ── Validate inputs ───────────────────────────────────────────────────
        if not case_id:
            return Response({'error': 'case_id is required.'}, status=400)
        if not replacement_products_input:
            return Response({'error': 'replacement_products is required.'}, status=400)

        try:
            case = ReturnExchangeCase.objects.select_related('order', 'batch').get(pk=case_id)
        except ReturnExchangeCase.DoesNotExist:
            return Response({'error': 'Case not found.'}, status=404)

        order = case.order
        user = request.user

        # ── Get org Shopify credentials ───────────────────────────────────────
        org_id = order.org_id
        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            return Response({'error': 'Shopify credentials not configured for this organisation.'}, status=404)

        shop_url = (
            creds.get_shopify_shop_url()
            if hasattr(creds, 'get_shopify_shop_url') else None
        ) or getattr(creds, 'myshopify_domain', '') or ''
        clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
        api_version = getattr(creds, 'shopify_api_version', None) or '2024-07'

        if getattr(creds, 'auth_method', '') == 'oauth' and getattr(creds, 'shopify_access_token_encrypted', None):
            token = decrypt_data(creds.shopify_access_token_encrypted)
            headers = {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
        else:
            api_key = creds.get_shopify_api_key() if hasattr(creds, 'get_shopify_api_key') else ''
            password = creds.get_shopify_password() if hasattr(creds, 'get_shopify_password') else ''
            api_key = api_key or ''
            password = password or ''
            if password and password.startswith('shpat_'):
                headers = {'X-Shopify-Access-Token': password, 'Content-Type': 'application/json'}
            else:
                encoded = base64.b64encode(f"{api_key}:{password}".encode()).decode()
                headers = {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}

        # ── Parse replacement products ────────────────────────────────────────
        line_items_payload = []
        replacement_products_meta = []
        total_replacement_value = 0.0

        for idx, p in enumerate(replacement_products_input):
            variant_id = p.get('variant_id')
            p_name = (p.get('name') or p.get('title') or '').strip()
            p_qty = int(p.get('qty') or p.get('quantity') or 1)
            p_price = float(p.get('price') or 0)
            p_sku = (p.get('sku') or '').strip()
            p_variant_title = (p.get('variant_title') or p.get('variant') or '').strip()
            p_image = (p.get('image') or '').strip()
            discount_str = (p.get('discount') or '').strip()

            if not p_name:
                return Response({'error': f'Product #{idx+1} is missing a name.'}, status=400)
            if not variant_id:
                return Response({'error': f'Product #{idx+1} is missing variant_id.'}, status=400)

            # ── Apply discount to compute the post-discount unit price ──────────
            # Percentage discount: "25%" → 25% off each unit
            # Flat discount: "50.00" → total discount across this product's qty
            discount_per_unit = 0.0
            if discount_str:
                try:
                    if discount_str.endswith('%'):
                        pct = float(discount_str.rstrip('%'))
                        discount_per_unit = p_price * (pct / 100.0)
                    else:
                        flat_total = float(discount_str)
                        discount_per_unit = flat_total / p_qty if p_qty > 0 else 0.0
                except (ValueError, TypeError):
                    discount_per_unit = 0.0

            discounted_unit_price = max(0.0, p_price - discount_per_unit)

            line_items_payload.append({
                'variant_id': int(variant_id),
                'quantity': p_qty,
                'price': f'{discounted_unit_price:.2f}',   # post-discount price sent to Shopify
                'requires_shipping': True,
            })
            replacement_products_meta.append({
                'title': p_name,
                'sku': p_sku,
                'variant_id': int(variant_id),
                'variant_title': p_variant_title,
                'price': p_price,
                'discounted_price': discounted_unit_price,
                'discount': discount_str,
                'quantity': p_qty,
                'image': p_image,
            })
            total_replacement_value += discounted_unit_price * p_qty

        # ── Build customer + address data from parent order ───────────────────
        raw = order.raw_data or {}
        customer_data = raw.get('customer') or {}
        shipping_addr = raw.get('shipping_address') or {}
        billing_addr = raw.get('billing_address') or shipping_addr

        shopify_order_payload = {
            'order': {
                'line_items': line_items_payload,
                'customer': {
                    'id': customer_data.get('id'),
                    'email': customer_data.get('email') or order.contact_email or '',
                    'first_name': customer_data.get('first_name') or order.customer_first_name or '',
                    'last_name': customer_data.get('last_name') or order.customer_last_name or '',
                } if customer_data.get('id') else None,
                'email': customer_data.get('email') or order.contact_email or '',
                'shipping_address': shipping_addr if shipping_addr else None,
                'billing_address': billing_addr if billing_addr else None,
                'financial_status': 'paid' if is_paid else 'pending',
                'tags': 'Exchange, Shori',
                'note': (
                    f'Shori-generated exchange order for original order #{order.order_number}. '
                    f'Case #{case.id}. {notes}'
                ).strip('. '),
                'send_receipt': False,
                'send_fulfillment_receipt': False,
                'inventory_behaviour': 'bypass',  # allow out-of-stock
            }
        }
        # Remove None customer key to avoid Shopify error
        if shopify_order_payload['order']['customer'] is None:
            del shopify_order_payload['order']['customer']

        # ── Activity: exchange creation started ───────────────────────────────
        ReturnExchangeActivity.objects.create(
            case=case,
            action='exchange_creation_started',
            notes=f'Exchange order creation initiated by {user.get_full_name() or user.email}.',
            performed_by=user,
        )

        # ── POST order to Shopify ─────────────────────────────────────────────
        shopify_orders_url = f'https://{clean_domain}/admin/api/{api_version}/orders.json'
        try:
            shopify_resp = http_requests.post(
                shopify_orders_url,
                headers=headers,
                json=shopify_order_payload,
                timeout=20,
            )
        except Exception as e:
            logger.exception('Network error creating Shopify exchange order for case %s', case_id)
            return Response({'error': f'Network error calling Shopify: {e}'}, status=502)

        if not shopify_resp.ok:
            err_body = ''
            try:
                err_body = shopify_resp.json()
            except Exception:
                err_body = shopify_resp.text[:500]
            logger.error(
                'Shopify rejected exchange order for case %s: %s %s',
                case_id, shopify_resp.status_code, err_body,
            )
            return Response({
                'error': f'Shopify API error {shopify_resp.status_code}.',
                'details': err_body,
            }, status=shopify_resp.status_code)

        new_shopify_order = shopify_resp.json().get('order', {})
        new_shopify_id = new_shopify_order.get('id')
        new_order_number = new_shopify_order.get('order_number')
        new_order_name = new_shopify_order.get('name', f'#{new_order_number}')

        logger.info(
            'Shopify exchange order %s (%s) created for case %s',
            new_order_name, new_shopify_id, case_id,
        )

        # ── Activity: Shopify order created ───────────────────────────────────
        ReturnExchangeActivity.objects.create(
            case=case,
            action='shopify_order_created',
            notes=f'Shopify replacement order {new_order_name} (ID: {new_shopify_id}) created successfully.',
            performed_by=user,
        )

        # ── Sync new order into local DB ──────────────────────────────────────
        local_exchange_order = None
        try:
            customer_raw = new_shopify_order.get('customer') or {}
            ship_addr = new_shopify_order.get('shipping_address') or {}
            bill_addr = new_shopify_order.get('billing_address') or ship_addr

            def _addr_text(a):
                return f"{a.get('first_name','')} {a.get('last_name','')}, {a.get('address1','')}, {a.get('city','')}, {a.get('zip','')}".strip(', ')

            local_exchange_order, created = Order.objects.get_or_create(
                shopify_id=new_shopify_id,
                defaults={'org_id': org_id},
            )
            local_exchange_order.order_number = new_order_number
            local_exchange_order.org_id = org_id
            local_exchange_order.total_price = new_shopify_order.get('total_price', 0)
            local_exchange_order.financial_status = new_shopify_order.get('financial_status', 'paid')
            local_exchange_order.fulfillment_status = new_shopify_order.get('fulfillment_status')
            local_exchange_order.tags = new_shopify_order.get('tags', '')
            local_exchange_order.raw_data = new_shopify_order
            local_exchange_order.is_exchange_order = True

            # PII from parent order
            if order.customer_first_name:
                local_exchange_order.customer_first_name = order.customer_first_name
            if order.customer_last_name:
                local_exchange_order.customer_last_name = order.customer_last_name
            if order.contact_email:
                local_exchange_order.contact_email = order.contact_email
            if order.contact_phone:
                local_exchange_order.contact_phone = order.contact_phone
            if ship_addr:
                local_exchange_order.shipping_address = _addr_text(ship_addr)
            if bill_addr:
                local_exchange_order.billing_address = _addr_text(bill_addr)

            local_exchange_order.save()

            # Line items
            local_exchange_order.line_items.all().delete()
            lis = [
                LineItem(
                    order=local_exchange_order,
                    product_id=li.get('product_id'),
                    variant_id=li.get('variant_id'),
                    title=li.get('title', ''),
                    quantity=li.get('quantity', 1),
                    sku=li.get('sku', ''),
                    price=li.get('price', 0),
                    name=li.get('name', ''),
                )
                for li in new_shopify_order.get('line_items', [])
            ]
            if lis:
                LineItem.objects.bulk_create(lis)

            logger.info('Exchange order synced to local DB: Order #%s (id=%s)', new_order_number, local_exchange_order.pk)
        except Exception:
            logger.exception('Failed to sync exchange order %s to local DB', new_shopify_id)

        # ── Activity: exchange order generated (local sync) ───────────────────
        ReturnExchangeActivity.objects.create(
            case=case,
            action='exchange_order_generated',
            notes=(
                f'Replacement order {new_order_name} synced to local database.'
                + (f' Local Order ID: {local_exchange_order.pk}.' if local_exchange_order else '')
            ),
            performed_by=user,
        )

        # ── Create mock ReturnRequest of type EXCHANGE ────────────────────────
        mock_rr = None
        try:
            mock_rr = ReturnRequest.objects.create(
                return_prime_id=f"manual_{case.id}_{uuid.uuid4().hex[:8]}",
                order=order,
                request_type='EXCHANGE',
                raw_data={
                    'source': 'erp_manual',
                    'case_id': case.id,
                    'exchange': {
                        'order': {
                            'name': new_order_name,
                            'id': new_shopify_id,
                            'order_number': new_order_number,
                        },
                        'replacement_products': replacement_products_meta,
                        'total_value': total_replacement_value,
                    },
                    'notes': notes,
                    'created_by': user.email,
                },
            )
            logger.info('Mock ReturnRequest EXCHANGE created: id=%s for case %s', mock_rr.pk, case_id)
        except Exception:
            logger.exception('Failed to create mock ReturnRequest for case %s', case_id)

        # ── Activity: Return Prime updated ────────────────────────────────────
        ReturnExchangeActivity.objects.create(
            case=case,
            action='return_prime_updated',
            notes=(
                f'Internal exchange record created'
                + (f' (ReturnRequest #{mock_rr.pk})' if mock_rr else '')
                + f'. Replacement order {new_order_name} linked.'
            ),
            performed_by=user,
        )

        # ── Update the ReturnExchangeCase ─────────────────────────────────────
        existing_meta = case.exchange_meta or {}
        existing_meta['replacement_products'] = replacement_products_meta
        existing_meta['converted_via'] = 'erp_shopify_order'
        existing_meta['shopify_exchange_order_id'] = new_shopify_id
        existing_meta['shopify_exchange_order_name'] = new_order_name

        case.case_type = 'exchange'
        case.exchange_exists = True
        case.exchange_order_number = new_order_name
        case.replacement_order_number = str(new_order_number)
        case.exchange_created_at = tz.now()
        case.exchange_meta = existing_meta
        case.converted_to_exchange = True
        case.conversion_notes = notes
        case.converted_by = user
        case.converted_at = tz.now()
        case.conversion_product_data = {
            'title': replacement_products_meta[0]['title'] if replacement_products_meta else '',
            'sku': replacement_products_meta[0]['sku'] if replacement_products_meta else '',
            'price': replacement_products_meta[0]['price'] if replacement_products_meta else 0,
            'variant': replacement_products_meta[0]['variant_title'] if replacement_products_meta else '',
            'quantity': replacement_products_meta[0]['quantity'] if replacement_products_meta else 1,
            'products': replacement_products_meta,
        }
        
        # Calculate settlement details and set status to exchange_closed
        calc = _calculate_exchange_settlement(case)
        case.settlement_type = calc['settlement_type']
        case.difference_amount = float(calc['difference'])
        case.settlement_completed_at = tz.now()
        case.settlement_completed_by = user
        case.settlement_method = 'no_settlement' if calc['settlement_type'] == 'no_settlement' else 'auto_settled'
        case.status = 'exchange_closed'
        
        case.save(update_fields=[
            'case_type', 'status', 'exchange_exists', 'exchange_order_number',
            'replacement_order_number', 'exchange_created_at', 'exchange_meta',
            'converted_to_exchange', 'conversion_notes', 'converted_by',
            'converted_at', 'conversion_product_data', 'updated_at',
            'settlement_type', 'difference_amount', 'settlement_completed_at',
            'settlement_completed_by', 'settlement_method',
        ])

        # ── Final activity: exchange created successfully ──────────────────────
        prod_summary = ', '.join(
            f"{p['title']} x{p['quantity']}" for p in replacement_products_meta
        )
        ReturnExchangeActivity.objects.create(
            case=case,
            action='exchange_created_successfully',
            notes=(
                f'Exchange order {new_order_name} created on Shopify and registered in ERP. '
                f'Products: {prod_summary}. '
                f'Case status set to exchange_closed.'
            ),
            performed_by=user,
        )

        return Response({
            'message': f'Exchange order {new_order_name} created successfully on Shopify.',
            'case_id': case.id,
            'new_status': case.status,
            'shopify_order_name': new_order_name,
            'shopify_order_id': new_shopify_id,
            'shopify_order_number': new_order_number,
            'local_order_id': local_exchange_order.pk if local_exchange_order else None,
        }, status=201)

