import logging
from datetime import timedelta, date
from django.utils import timezone
import shopify as shopify_lib
from core.models import Order, ShopCredentials
from core.models.sales import ChannelAbandonedCheckout, AbandonedCart
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

def sync_shopify_checkouts_task(shop_id, org_id, date_from=None, date_to=None):
    """
    Background task to sync shopify checkouts and save them locally.
    """
    try:
        shop = ShopCredentials.objects.get(id=shop_id)
    except ShopCredentials.DoesNotExist:
        logger.error(f"Shop credentials with id {shop_id} not found.")
        return {'success': False, 'error': 'ShopCredentials not found'}

    # Default to last 30 days
    if not date_from:
        date_from = str(date.today() - timedelta(days=30))

    try:
        from core.shopify_utils import get_shopify_session
        session = get_shopify_session(shop.myshopify_domain, org_id=org_id, shop_creds=shop)
        shopify_lib.ShopifyResource.activate_session(session)

        from datetime import datetime, time as dt_time
        tz = timezone.get_current_timezone()

        params = {'limit': 250}
        if date_from:
            try:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                df_aware = timezone.make_aware(datetime.combine(df, dt_time.min), tz)
                params['created_at_min'] = df_aware.isoformat()
            except ValueError:
                params['created_at_min'] = date_from
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                dt_aware = timezone.make_aware(datetime.combine(dt, dt_time.max), tz)
                params['created_at_max'] = dt_aware.replace(microsecond=0).isoformat()
            except ValueError:
                params['created_at_max'] = date_to + 'T23:59:59'

        checkouts = shopify_lib.Checkout.find(**params)

        # Build customer mapping
        cust_ids = []
        for c in checkouts:
            cd = c.to_dict()
            cust_id = (cd.get('customer') or {}).get('id')
            if cust_id:
                cust_ids.append(cust_id)

        cust_map = {}
        if cust_ids:
            matching_orders = Order.objects.filter(
                org_id=shop.organization_id,
                raw_data__customer__id__in=cust_ids
            ).exclude(raw_data__isnull=True).values(
                'raw_data__customer__id', 'customer_first_name', 'customer_last_name', 'contact_email', 'contact_phone',
                'shipping_state', 'shipping_pincode'
            )
            for r in matching_orders:
                try:
                    cid = r.get('raw_data__customer__id')
                    if cid:
                        cid_str = str(cid)
                        if cid_str not in cust_map:
                            first = r.get('customer_first_name') or ''
                            last = r.get('customer_last_name') or ''
                            cust_map[cid_str] = {
                                'name': f"{first} {last}".strip(),
                                'email': r.get('contact_email'),
                                'phone': r.get('contact_phone'),
                                'state': r.get('shipping_state'),
                                'zip': r.get('shipping_pincode')
                            }
                except Exception:
                    continue

        sync_count = 0
        from core.views_sales import _derive_shopify_checkout_stage
        
        for c in checkouts:
            cd = c.to_dict()
            token = cd.get('token')
            if not token:
                continue

            customer_obj = cd.get('customer') or {}
            addr = cd.get('shipping_address') or {}
            billing = cd.get('billing_address') or {}

            email = cd.get('email') or customer_obj.get('email', '')
            first = addr.get('first_name') or billing.get('first_name') or customer_obj.get('first_name', '')
            last = addr.get('last_name') or billing.get('last_name') or customer_obj.get('last_name', '')
            customer_name = f"{first} {last}".strip()
            phone = (cd.get('phone') or addr.get('phone') or billing.get('phone')
                     or customer_obj.get('phone', ''))

            # Enrich from maps
            cust_id = customer_obj.get('id')
            db_state = ''
            db_zip = ''
            if cust_id and str(cust_id) in cust_map:
                m_data = cust_map[str(cust_id)]
                db_state = m_data.get('state') or ''
                db_zip = m_data.get('zip') or ''
                if not customer_name or customer_name.lower() == 'guest':
                    customer_name = m_data.get('name') or customer_name
                if not email:
                    email = m_data.get('email') or ''
                if not phone:
                    phone = m_data.get('phone') or ''

            # Enrich from local AbandonedCart webhook payload
            cid_val = cd.get('id')
            local_cart = None
            if token:
                local_cart = AbandonedCart.objects.filter(shop=shop, flexype_checkout_id=str(token)).first()
            if not local_cart and cid_val:
                local_cart = AbandonedCart.objects.filter(shop=shop, flexype_checkout_id=str(cid_val)).first()
            
            if not local_cart and cd.get('created_at'):
                created_at = parse_datetime(cd.get('created_at'))
                if created_at:
                    val = float(cd.get('total_price') or cd.get('subtotal_price') or 0)
                    local_cart = AbandonedCart.objects.filter(
                        shop=shop,
                        cart_value__gte=val - 1,
                        cart_value__lte=val + 1,
                        abandoned_at__gte=created_at - timedelta(hours=1),
                        abandoned_at__lte=created_at + timedelta(hours=1)
                    ).first()

            if local_cart:
                if not customer_name or customer_name.lower() == 'guest':
                    customer_name = local_cart.customer_name or customer_name
                if not email:
                    email = local_cart.customer_email or ''
                if not phone:
                    phone = local_cart.customer_phone or ''

            if not customer_name:
                customer_name = 'Guest'

            # Build a dict from ALL note_attributes for easy lookup
            note_attrs = {
                a.get('name'): a.get('value', '')
                for a in (cd.get('note_attributes') or [])
                if isinstance(a, dict) and a.get('name')
            }

            flexype_drop_off_state = note_attrs.get('flexype_checkout_drop_off_state', '')
            if not flexype_drop_off_state and local_cart and local_cart.session_state:
                session_st = local_cart.session_state.upper()
                if "PAYMENT" in session_st:
                    flexype_drop_off_state = "PAYMENT_INITIATED"
                elif "ADDRESS" in session_st:
                    flexype_drop_off_state = "ADDRESS_UPDATED"
                elif "LOGIN" in session_st:
                    flexype_drop_off_state = "LOGGED_IN"
                else:
                    flexype_drop_off_state = local_cart.session_state

            checkout_stage = _derive_shopify_checkout_stage(cd)

            created_at_str = cd.get('created_at')
            abandoned_at = parse_datetime(created_at_str) if created_at_str else timezone.now()

            # Save or update local database
            obj, created_local = ChannelAbandonedCheckout.objects.update_or_create(
                shop=shop,
                shopify_token=token,
                defaults={
                    'channel': 'shopify',
                    'checkout_url': cd.get('abandoned_checkout_url', '') or '',
                    'customer_name': customer_name,
                    'customer_email': email or '',
                    'customer_phone': phone or '',
                    'cart_value': float(cd.get('total_price') or cd.get('subtotal_price') or 0),
                    'item_count': len(cd.get('line_items', [])),
                    'line_items': [
                        {'title': i.get('title'), 'qty': i.get('quantity'), 'price': i.get('price')}
                        for i in cd.get('line_items', [])
                    ],
                    'checkout_stage': checkout_stage,
                    'abandoned_at': abandoned_at,
                    'channel_meta': {
                        'id': cd.get('id'),
                        'flexype_drop_off_state': flexype_drop_off_state,
                        'province': addr.get('province') or billing.get('province') or db_state or '',
                        'zip': addr.get('zip') or billing.get('zip') or db_zip or '',
                        'city': addr.get('city') or billing.get('city') or '',
                        'orders_count': customer_obj.get('orders_count') or 0,
                        # Marketing attribution — from Shopify note_attributes
                        'utm_source': note_attrs.get('utm_source', ''),
                        'utm_medium': note_attrs.get('utm_medium', ''),
                        'utm_campaign': note_attrs.get('utm_campaign', ''),
                        'utm_content': note_attrs.get('utm_content', ''),
                        'utm_term': note_attrs.get('utm_term', ''),
                        'fbclid': note_attrs.get('fbclid', ''),
                        'flexype_checkout_url': note_attrs.get('flexype_checkout', ''),
                        # Shopify built-in tracking fields
                        'referring_site': cd.get('referring_site', '') or '',
                        'landing_site': cd.get('landing_site', '') or '',
                        'source_name': cd.get('source_name', '') or '',
                    }
                }
            )
            sync_count += 1

        logger.info(f"Successfully synced {sync_count} shopify checkouts for shop {shop_id}")
        return {'success': True, 'synced': sync_count}
    except Exception as e:
        logger.exception("Failed to sync Shopify checkouts")
        return {'success': False, 'error': str(e)}
    finally:
        try:
            shopify_lib.ShopifyResource.clear_session()
        except Exception:
            pass
