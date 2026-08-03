from django.utils import timezone
from datetime import timedelta, datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.db.models import Prefetch, Q, Sum, TextField, Count, F, Case, When, DecimalField, OuterRef, Prefetch, Exists
from core.utils.payment_utils import get_payment_q_objects
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination

from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import close_old_connections


# Custom authentication class that exempts CSRF for session auth
class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF enforcement for API endpoints."""
    def enforce_csrf(self, request):
        return  # Skip CSRF check


from django_q.tasks import async_task, schedule
import zoneinfo
import json
import hmac
import hashlib
import base64
import os
import requests
from django.conf import settings
import re

# --- Models ---
from core.models import (
    Order, LineItem, Fulfillment, TrackingInfo, Batch, PackagingBatch,
    PackagingImage, ShopCredentials, TeamMemberSettings, Invitation, TrackingEvent, CaseFile, IssueComment, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES,
    ChannelDraftOrder
)

# --- Utils ---
from core.utils import (
    _clean_shopify_url,
    _get_decrypted_credentials,
    _get_org_id_or_none,
    _get_or_create_order_from_api,
    STATUS_MAP
)
from core.utils.stage_queries import get_queryset_for_stage

# --- Serializers ---
from core.serializers import (
    OrderSerializer, BatchSerializer, PackagingBatchSerializer, 
    CaseFileSerializer, IssueCommentSerializer, SimpleOrderSerializer,
    AWBBatchSerializer
)

# --- Permissions ---
from core.permissions import (
    IsAllowedToCall, IsAllowedToBatch, IsPackagingAgent, 
    IsOrganizationOwner, IsAllowedCustomerExperience
)

User = get_user_model()




from .helpers import _get_org_id_or_none, _filter_orders_by_org_id, _clean_shopify_url
# 7. SHOPIFY WEBHOOK
# ==============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class ShopifyWebhookView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request, *args, **kwargs):
        shop_domain = request.headers.get('X-Shopify-Shop-Domain')
        cleaned_domain = _clean_shopify_url(shop_domain) if shop_domain else ''
        try:
            from core.models import ShopCredentials
            shop_cred = ShopCredentials.objects.get(myshopify_domain=shop_domain)
            org_id = shop_cred.organization_id
        except Exception:
            # Fallback for older hardcoded stores like janki-jewels
            try:
                org_id = cleaned_domain.split('.')[0]
            except Exception:
                return HttpResponse('Bad Request: Invalid Domain', status=400)

        creds = _get_decrypted_credentials(org_id)
        if not creds: return HttpResponse(status=200)

        # Use the stored webhook secret for legacy apps, or the global partner secret for OAuth apps
        webhook_secret_str = creds.get('webhook_secret') or settings.SHOPIFY_API_SECRET
        if not webhook_secret_str:
            return HttpResponse('Unauthorized: Webhook secret not configured.', status=401)
        
        shopify_hmac = request.headers.get('X-Shopify-Hmac-Sha256')
        if not shopify_hmac: return HttpResponse('Unauthorized: Missing HMAC header', status=401)
        
        try:
            # 1. Primary secret (from DB)
            digest_primary = hmac.new(webhook_secret_str.encode('utf-8'), request.body, hashlib.sha256).digest()
            computed_primary = base64.b64encode(digest_primary)
            
            # 2. Partner App Global Secret (for OAuth apps - fallback)
            digest_partner = hmac.new(settings.SHOPIFY_API_SECRET.encode('utf-8'), request.body, hashlib.sha256).digest()
            computed_partner = base64.b64encode(digest_partner)

            # 3. Dynamic Custom App Secret
            from core.utils.shopify_credentials import get_app_credentials
            _, dynamic_secret = get_app_credentials(shop_domain)
            digest_dynamic = hmac.new(dynamic_secret.encode('utf-8'), request.body, hashlib.sha256).digest()
            computed_dynamic = base64.b64encode(digest_dynamic)

            # 4. Try legacy janki secret from settings
            legacy_sec = getattr(settings, 'LEGACY_SHOPIFY_WEBHOOK_SECRET', '')
            digest_legacy = hmac.new(legacy_sec.encode('utf-8'), request.body, hashlib.sha256).digest() if legacy_sec else b''
            computed_legacy = base64.b64encode(digest_legacy) if legacy_sec else b''
            
            if hmac.compare_digest(computed_primary, shopify_hmac.encode('utf-8')):
                print(f"HMAC VERIFIED USING PRIMARY SECRET for {shop_domain}!")
            elif hmac.compare_digest(computed_partner, shopify_hmac.encode('utf-8')):
                print(f"HMAC VERIFIED USING PARTNER API SECRET for {shop_domain}!")
            elif hmac.compare_digest(computed_dynamic, shopify_hmac.encode('utf-8')):
                print(f"HMAC VERIFIED USING DYNAMIC APP SECRET for {shop_domain}!")
            elif legacy_sec and hmac.compare_digest(computed_legacy, shopify_hmac.encode('utf-8')):
                print(f"HMAC VERIFIED USING LEGACY SECRET for {shop_domain}!")
            else:
                print(f"HMAC FAILED for {shop_domain}! Sent: {shopify_hmac}")
                return HttpResponse('Unauthorized: Invalid HMAC signature', status=401)
        except Exception as e:
            print(f"HMAC Exception: {e}")
            return HttpResponse('Unauthorized: HMAC verification process failed.', status=401)

        topic = request.headers.get('X-Shopify-Topic')
        webhook_data = json.loads(request.body)

        import threading
        thread = threading.Thread(
            target=self._process_webhook_async,
            args=(topic, webhook_data, org_id, creds, cleaned_domain)
        )
        thread.start()

        return HttpResponse(status=200)

    def _process_webhook_async(self, topic, webhook_data, org_id, creds, cleaned_domain):
        try:
            shop_url = creds['shop_url']
            api_key = creds['api_key']
            password = creds['password']
            api_version = creds['api_version']
            access_token = creds.get('access_token')
            auth_method = creds.get('auth_method')

            def fetch_shopify_data(url_path):
                url = f"https://{shop_url}{url_path}"
                if auth_method == 'oauth' and access_token:
                    headers = {"X-Shopify-Access-Token": access_token}
                    return requests.get(url, headers=headers)
                else:
                    legacy_url = f"https://{api_key}:{password}@{shop_url}{url_path}"
                    return requests.get(legacy_url)

            if topic in ['orders/create', 'orders/updated', 'orders/paid', 'orders/fulfilled']:
                shopify_order_id = webhook_data.get('id')
                if not shopify_order_id: return
                print(f"Processing '{topic}' for order ID: {shopify_order_id} (Org: {org_id})")
                
                response = fetch_shopify_data(f"/admin/api/{api_version}/orders/{shopify_order_id}.json")
                if not response.ok: return
                api_order = response.json()['order']
                customer_data = api_order.get('customer') or {}
                previous_order_count = 0
                p_email = (customer_data.get('email') or '').strip().lower()
                shipping_address = api_order.get('shipping_address')
                p_phone = (shipping_address or {}).get('phone') or customer_data.get('phone')
                
                def clean_phone_inline(val):
                    if not val:
                        return None
                    s = str(val).strip("'").strip('"').strip()
                    if not s:
                        return None
                    digits = ''.join(filter(str.isdigit, s))
                    if len(digits) == 10:
                        return f"+91{digits}"
                    elif len(digits) > 10:
                        if s.startswith('+'):
                            return s
                        else:
                            return f"+{digits}"
                    return s
                
                p_phone_cleaned = clean_phone_inline(p_phone)
                
                q_filter = Q()
                if p_email:
                    q_filter |= Q(contact_email=p_email)
                if p_phone_cleaned:
                    q_filter |= Q(contact_phone=p_phone_cleaned)
                    
                if q_filter:
                    previous_order_count = Order.objects.filter(
                        q_filter,
                        org_id=org_id,
                        created_at__lt=api_order.get('created_at')
                    ).count()
                shipping_address_text = f"{(shipping_address or {}).get('first_name','')} {(shipping_address or {}).get('last_name','')}, {(shipping_address or {}).get('address1','')}, {(shipping_address or {}).get('city','')}, {(shipping_address or {}).get('zip','')}" if shipping_address else None
                billing_address = api_order.get('billing_address')
                billing_address_text = f"{(billing_address or {}).get('first_name','')} {(billing_address or {}).get('last_name','')}, {(billing_address or {}).get('address1','')}, {(billing_address or {}).get('city','')}, {(billing_address or {}).get('zip','')}" if billing_address else None
                order_obj, created = Order.objects.get_or_create(
                    shopify_id=api_order['id'],
                    defaults={'org_id': org_id}
                )

                # Base fields (always update)
                order_obj.order_number = api_order.get('order_number')
                order_obj.created_at = api_order.get('created_at')
                order_obj.updated_at = api_order.get('updated_at')
                order_obj.total_price = api_order.get('total_price')
                order_obj.financial_status = api_order.get('financial_status')
                order_obj.fulfillment_status = api_order.get('fulfillment_status')
                order_obj.tags = api_order.get('tags', '')
                order_obj.payment_gateway_names = api_order.get('payment_gateway_names', [])
                order_obj.discount_codes = api_order.get('discount_codes', [])
                order_obj.previous_order_count = previous_order_count
                order_obj.raw_data = api_order

                # PII fields (PROTECT FROM REDACTION: Only update if new value is not empty)
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

                if shipping_address:
                    if shipping_address.get('province'):
                        order_obj.shipping_state = shipping_address.get('province')
                    if shipping_address.get('zip'):
                        order_obj.shipping_pincode = shipping_address.get('zip')

                order_obj.save()

                if created and order_obj.financial_status != 'voided':
                    order_obj.status = 'Pending'
                    order_obj.internal_fulfillment_status = 'Pending'
                    order_obj.save()
                # SAFE line item sync: NEVER delete existing items unless Shopify returns
                # a non-empty replacement list. Shopify can return line_items=[] for redacted
                # or permission-limited orders (missing read_products scope), which would
                # permanently wipe all items from the order.
                incoming_line_items = api_order.get('line_items', [])
                if incoming_line_items:
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
                            name=item.get('name'),
                        )
                        for item in incoming_line_items
                    ]
                    LineItem.objects.bulk_create(line_items_to_create)
                else:
                    existing_count = order_obj.line_items.count()
                    logger.warning(
                        f"⚠️ Shopify returned 0 line_items for order #{api_order.get('order_number')} "
                        f"(topic={topic}, org={org_id}). "
                        f"Keeping existing {existing_count} line item(s) to prevent data loss. "
                        f"Check Shopify app scopes (read_products may be missing)."
                    )

                # Process fulfillments included in the order payload (since app lacks read_fulfillments scope for webhook)
                # Extract existing label URL if it is a valid PDF label
                existing_label_url = None
                for f in order_obj.fulfillments.all():
                    for t in f.tracking_info.all():
                        if t.url and "track.shipway.com" not in t.url:
                            existing_label_url = t.url
                            break
                    if existing_label_url:
                        break

                order_obj.fulfillments.all().delete()
                for api_fulfillment in api_order.get('fulfillments', []):
                    f_obj = Fulfillment.objects.create(
                        order=order_obj,
                        shopify_id=api_fulfillment.get('id'),
                        status=api_fulfillment.get('status'),
                        shipment_status=api_fulfillment.get('shipment_status'),
                        created_at=api_fulfillment.get('created_at'),
                        updated_at=api_fulfillment.get('updated_at'),
                        service=api_fulfillment.get('service'),
                        fulfillment_order_id=api_fulfillment.get('fulfillment_order_id')
                    )
                    tracking_to_create = []
                    tracking_numbers = api_fulfillment.get('tracking_numbers', [])
                    tracking_urls = api_fulfillment.get('tracking_urls', [])
                    tracking_company = api_fulfillment.get('tracking_company')
                    for i, number in enumerate(tracking_numbers):
                        url = existing_label_url or (tracking_urls[i] if i < len(tracking_urls) else None)
                        tracking_to_create.append(TrackingInfo(
                            fulfillment=f_obj, 
                            company=tracking_company, 
                            number=number, 
                            url=url
                        ))
                    if tracking_to_create:
                        TrackingInfo.objects.bulk_create(tracking_to_create)

                print(f"Successfully processed order #{api_order.get('order_number')} for {org_id}")

                # ── LIVE ATTRIBUTION ─────────────────────────────────────
                # Extract UTMs from note_attributes and landing_site, classify
                # channel, and create OrderAttribution record immediately.
                try:
                    from core.utils.url_parser import extract_and_classify
                    from core.models import OrderAttribution, PixelEvent

                    _NOTE_ATTR_KEYS = {
                        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
                        'utm_term', 'fbclid', 'gclid', 'ttclid', 'epik', 'sclid',
                    }
                    _EXTRA_ATTR_KEYS = {'fp_id', 'referer', 'shori_session_id', 'bridgeworks_session_id'}

                    override_utm_data = {}
                    extra_data = {}

                    note_attrs = api_order.get('note_attributes', [])
                    if isinstance(note_attrs, list):
                        for attr in note_attrs:
                            name = attr.get('name', '').lower().strip()
                            val = attr.get('value', '')
                            if isinstance(val, str) and val.strip():
                                if name in _NOTE_ATTR_KEYS:
                                    override_utm_data[name] = val.strip()
                                elif name in _EXTRA_ATTR_KEYS:
                                    extra_data[name] = val.strip()

                    landing_site = api_order.get('landing_site') or ''
                    referring_site_val = api_order.get('referring_site') or ''

                    has_any_signal = landing_site or referring_site_val or any(override_utm_data.values())

                    if has_any_signal:
                        attr_data = extract_and_classify(landing_site, referring_site_val, override_utm_data)
                        channel = attr_data['channel']
                    else:
                        attr_data = {k: '' for k in _NOTE_ATTR_KEYS}
                        channel = 'direct'

                    # ── PIXEL ENRICHMENT ─────────────────────────────────────
                    # Look up first-party pixel data using shori_session_id, bridgeworks_session_id, or cart_token
                    shori_session_id = extra_data.get('shori_session_id') or extra_data.get('bridgeworks_session_id')
                    cart_token = api_order.get('cart_token')
                    
                    pixel_events = []
                    if shori_session_id:
                        pixel_events = list(PixelEvent.objects.filter(session_id=shori_session_id).order_by('timestamp'))
                    if not pixel_events and cart_token:
                        pixel_events = list(PixelEvent.objects.filter(cart_token=cart_token).order_by('timestamp'))
                    
                    # Build journey from pixel events
                    touch_journey = []
                    for pe in pixel_events:
                        touch_journey.append({
                            'source': pe.utm_source or 'direct',
                            'medium': pe.utm_medium,
                            'campaign': pe.utm_campaign,
                            'content': pe.utm_content,
                            'term': pe.utm_term,
                            'ts': pe.timestamp.isoformat(),
                            'url': pe.url
                        })

                    # If pixel found data, it might be more accurate than Shopify's landing_site
                    if pixel_events:
                        last_pixel = pixel_events[-1] # Use the most recent hit for the primary attribution
                        attr_data.update({
                            'utm_source': last_pixel.utm_source or attr_data.get('utm_source', ''),
                            'utm_medium': last_pixel.utm_medium or attr_data.get('utm_medium', ''),
                            'utm_campaign': last_pixel.utm_campaign or attr_data.get('utm_campaign', ''),
                            'fbclid': last_pixel.fbclid or attr_data.get('fbclid', ''),
                            'gclid': last_pixel.gclid or attr_data.get('gclid', ''),
                        })
                        channel = extract_and_classify(landing_site, referring_site_val, attr_data)['channel']

                    OrderAttribution.objects.update_or_create(
                        order=order_obj,
                        defaults={
                            'utm_source': attr_data.get('utm_source', '')[:255],
                            'utm_medium': attr_data.get('utm_medium', '')[:255],
                            'utm_campaign': attr_data.get('utm_campaign', '')[:500],
                            'utm_content': attr_data.get('utm_content', '')[:500],
                            'utm_term': attr_data.get('utm_term', '')[:500],
                            'fbclid': attr_data.get('fbclid', '')[:500],
                            'gclid': attr_data.get('gclid', '')[:500],
                            'ttclid': attr_data.get('ttclid', '')[:500],
                            'epik': attr_data.get('epik', '')[:500],
                            'sclid': attr_data.get('sclid', '')[:500],
                            'landing_page': landing_site[:2000] if landing_site else '',
                            'referring_site': referring_site_val[:2000] if referring_site_val else '',
                            'channel': channel,
                            'fp_id': extra_data.get('fp_id', '')[:255],
                            'referer': extra_data.get('referer', '')[:500],
                            'touch_journey': touch_journey,
                            'source': 'pixel' if pixel_events else 'webhook',
                        }
                    )
                    print(f"✅ Live attribution: Order #{order_obj.order_number} → {channel}")
                except Exception as attr_err:
                    logger.warning(f"Live attribution failed for order #{order_obj.order_number}: {attr_err}")

                # Schedule PII fetch from Shipway (only for newly created orders if PII is missing)
                # Shopify redacts customer PII — Shipway has the unredacted data.
                # We wait 4 minutes to give Shipway time to sync.
                if created:
                    has_pii = bool(order_obj.customer_first_name and order_obj.contact_phone and order_obj.shipping_address)
                    skip_sync = creds.get('skip_shipway_pii_sync', False)
                    if skip_sync:
                        print(f"Shipway PII sync is explicitly disabled for organization {org_id} (skip_shipway_pii_sync=True).")

                    if has_pii:
                        print(f"Order #{order_obj.order_number} already has customer PII from Shopify. Skipping Shipway PII fetch scheduling.")
                    elif skip_sync:
                        pass
                    else:
                        print(f"Scheduling PII fetch for order #{order_obj.order_number} in 4 minutes...")
                        schedule(
                            'core.tasks.fetch_missing_pii_task',
                            order_obj.id,
                            org_id,
                            1,  # attempt=1
                            next_run=timezone.now() + timedelta(minutes=4)
                        )

                    # Trigger AI Agent evaluation
                    # If PII is already present or sync is skipped, run evaluation in 15 seconds.
                    # Otherwise, wait 6 minutes to ensure PII fetch task completes first.
                    delay_seconds = 15 if (has_pii or skip_sync) else 360
                    print(f"Scheduling AI agent evaluation for order #{order_obj.order_number} in {delay_seconds} seconds...")
                    schedule(
                        'core.tasks.evaluate_order_task',
                        order_obj.id,
                        next_run=timezone.now() + timedelta(seconds=delay_seconds)
                    )

            elif topic == 'orders/cancelled':
                shopify_order_id = webhook_data.get('id')
                if not shopify_order_id: return
                print(f"Processing '{topic}' for order ID: {shopify_order_id} (Org: {org_id})")
                try:
                    order_obj = Order.objects.get(shopify_id=shopify_order_id, org_id=org_id)
                except Order.DoesNotExist:
                    return
                order_obj.status = 'Cancelled'
                order_obj.internal_fulfillment_status = 'Cancelled'
                order_obj.financial_status = webhook_data.get('financial_status', 'voided') 
                order_obj.save()
                print(f"Successfully marked order #{order_obj.order_number} as CANCELLED.")

            elif topic in ['fulfillments/create', 'fulfillments/update']:
                shopify_order_id = webhook_data.get('order_id')
                print(f"Processing '{topic}' for order ID: {shopify_order_id} (Org: {org_id})")
                
                order_obj = _get_or_create_order_from_api(shopify_order_id, org_id, creds)
                if not order_obj:
                    return

                fulfillment_obj = Fulfillment.objects.create(
                    order=order_obj, 
                    shopify_id=webhook_data.get('id'),
                    status=webhook_data.get('status'), 
                    shipment_status=webhook_data.get('shipment_status'), 
                    created_at=webhook_data.get('created_at'), 
                    updated_at=webhook_data.get('updated_at'), 
                    service=webhook_data.get('service'), 
                    fulfillment_order_id=webhook_data.get('fulfillment_order_id')
                )
                
                tracking_to_create = []
                tracking_numbers = webhook_data.get('tracking_numbers', [])
                tracking_urls = webhook_data.get('tracking_urls', [])
                tracking_company = webhook_data.get('tracking_company')
                for i, number in enumerate(tracking_numbers):
                    tracking_to_create.append(TrackingInfo(fulfillment=fulfillment_obj, company=tracking_company, number=number, url=tracking_urls[i] if i < len(tracking_urls) else None))
                if tracking_to_create: TrackingInfo.objects.bulk_create(tracking_to_create)
                
                if fulfillment_obj.status == 'success': order_obj.fulfillment_status = 'fulfilled'
                elif fulfillment_obj.status == 'cancelled': order_obj.fulfillment_status = 'unfulfilled'
                else: order_obj.fulfillment_status = 'partial'
                order_obj.save()
                
                print(f"Successfully CREATED NEW fulfillment log for order #{order_obj.order_number}")

                print(f"Scheduling Shipway scan for order {order_obj.id}...")
                schedule(
                    'core.tasks.fetch_and_save_shipway_history',
                    order_obj.id,
                    fulfillment_obj.id,
                    org_id,
                    next_run=timezone.now() + timedelta(minutes=3)
                )

            elif topic == 'fulfillment_orders/cancelled':
                fulfillment_order_data = webhook_data.get('fulfillment_order', {})
                shopify_order_gid = fulfillment_order_data.get('order_id')
                if not shopify_order_gid: return
                numeric_order_id = re.search(r'\d+$', shopify_order_gid)
                if not numeric_order_id: return
                shopify_order_id = int(numeric_order_id.group())
                try:
                    order_obj = Order.objects.get(shopify_id=shopify_order_id, org_id=org_id)
                except Order.DoesNotExist:
                    return
                cancelled_fo_id = fulfillment_order_data.get('id')
                deleted_count, _ = Fulfillment.objects.filter(fulfillment_order_id=cancelled_fo_id).delete()
                response = fetch_shopify_data(f"/admin/api/{api_version}/orders/{shopify_order_id}.json")
                if response.status_code == 200:
                    api_order = response.json()['order']
                    new_status = api_order.get('fulfillment_status')
                    if order_obj.fulfillment_status != new_status:
                        order_obj.fulfillment_status = new_status
                        order_obj.save()
                
            elif topic == 'refunds/create':
                shopify_order_id = webhook_data.get('order_id')
                if not shopify_order_id: return
                try:
                    order_obj = Order.objects.get(shopify_id=shopify_order_id, org_id=org_id)
                except Order.DoesNotExist:
                    return
                response = fetch_shopify_data(f"/admin/api/{api_version}/orders/{shopify_order_id}.json")
                if response.ok:
                    api_order = response.json().get('order')
                    if api_order:
                        new_financial_status = api_order.get('financial_status')
                        if order_obj.financial_status != new_financial_status:
                            order_obj.financial_status = new_financial_status
                            order_obj.raw_data = api_order
                            order_obj.save()
                            print(f"Updated order #{order_obj.order_number} financial status to '{new_financial_status}' after refund.")

            elif topic in ['draft_orders/create', 'draft_orders/update']:
                draft_id = webhook_data.get('id')
                if not draft_id: return
                
                customer = webhook_data.get('customer') or {}
                shipping = webhook_data.get('shipping_address') or {}
                billing = webhook_data.get('billing_address') or {}
                
                email = webhook_data.get('email') or customer.get('email') or ''
                first_name = customer.get('first_name') or shipping.get('first_name') or billing.get('first_name') or ''
                last_name = customer.get('last_name') or shipping.get('last_name') or billing.get('last_name') or ''
                
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = shipping.get('name') or billing.get('name') or email or 'Guest'

                # ── Parse order_type and reference_order_id from Shopify tags ──
                raw_tags = webhook_data.get('tags') or ''
                parsed_order_type = 'new'
                parsed_reference_order_id = ''
                import re as _re
                for _tag in [t.strip() for t in raw_tags.split(',')]:
                    _m = _re.match(r'^Exchange\(against (.+)\)$', _tag)
                    if _m:
                        parsed_order_type = 'exchange'
                        parsed_reference_order_id = _m.group(1)
                        break
                    _m = _re.match(r'^Reship\(against (.+)\)$', _tag)
                    if _m:
                        parsed_order_type = 'reship'
                        parsed_reference_order_id = _m.group(1)
                        break
                    _m = _re.match(r'^Duplicate\((.+)\)$', _tag)
                    if _m:
                        parsed_order_type = 'duplicate'
                        parsed_reference_order_id = _m.group(1)
                        break
                    if _tag == 'New order':
                        parsed_order_type = 'new'
                        break

                ChannelDraftOrder.objects.update_or_create(
                    shop=ShopCredentials.objects.get(myshopify_domain=cleaned_domain),
                    shopify_draft_id=str(draft_id),
                    defaults={
                        'channel': 'shopify',
                        'customer_name': full_name,
                        'customer_email': email or None,
                        'customer_phone': customer.get('phone') or shipping.get('phone') or billing.get('phone') or None,
                        'line_items': webhook_data.get('line_items', []),
                        'shipping_address': shipping,
                        'total': webhook_data.get('total_price', 0),
                        'status': 'completed' if webhook_data.get('completed_at') else 'draft',
                        'note': webhook_data.get('note') or '',
                        'tags': raw_tags,
                        'invoice_url': webhook_data.get('invoice_url') or None,
                        'shopify_created_at': webhook_data.get('created_at'),
                        'order_type': parsed_order_type,
                        'reference_order_id': parsed_reference_order_id,
                    }
                )
                print(f"Successfully synced Draft Order {draft_id} for {org_id}")

            elif topic == 'draft_orders/delete':
                draft_id = webhook_data.get('id')
                if draft_id:
                    ChannelDraftOrder.objects.filter(shopify_draft_id=str(draft_id), channel='shopify').delete()
                    print(f"Deleted Draft Order {draft_id} for {org_id}")

            # ── SHOPIFY PRODUCT & INVENTORY WEBHOOKS ─────────────────────
            elif topic in ['products/create', 'products/update']:
                shopify_product_id = webhook_data.get('id')
                if not shopify_product_id:
                    return

                from inventory.models import ShopifyProductCache
                from django.core.cache import cache as django_cache

                variants_data = webhook_data.get('variants', [])
                first_variant = variants_data[0] if variants_data else {}

                # Resolve image
                image_src = ''
                if webhook_data.get('image'):
                    image_src = webhook_data['image'].get('src', '')
                elif webhook_data.get('images'):
                    image_src = webhook_data['images'][0].get('src', '') if webhook_data['images'] else ''

                cache_data = {
                    'id':           webhook_data.get('id'),
                    'name':         webhook_data.get('title', ''),
                    'sku':          first_variant.get('sku', ''),
                    'category':     webhook_data.get('product_type', '') or webhook_data.get('vendor', ''),
                    'price':        first_variant.get('price', '0'),
                    'stock':        first_variant.get('inventory_quantity', 0),
                    'status':       (webhook_data.get('status', '') or '').capitalize(),
                    'shopifyId':    str(webhook_data.get('id', '')),
                    'handle':       webhook_data.get('handle', ''),
                    'image':        image_src,
                    'vendor':       webhook_data.get('vendor', ''),
                    'tags':         webhook_data.get('tags', ''),
                    'createdAt':    webhook_data.get('created_at', ''),
                    'updatedAt':    webhook_data.get('updated_at', ''),
                    'variantsCount': len(variants_data),
                    'variants': [
                        {
                            'id':    v.get('id'),
                            'sku':   v.get('sku', ''),
                            'price': v.get('price', '0'),
                            'stock': v.get('inventory_quantity', 0),
                            'title': v.get('title', ''),
                            'inventory_item_id': v.get('inventory_item_id'),
                        }
                        for v in variants_data
                    ],
                }

                ShopifyProductCache.objects.update_or_create(
                    organization_id=org_id,
                    shopify_id=shopify_product_id,
                    defaults={
                        'data': cache_data,
                        'synced_at': timezone.now(),
                    }
                )
                # Bust the hot cache so the inventory page picks up changes immediately
                django_cache.delete(f'shopify_products_{org_id}')
                print(f"✅ Cached product '{webhook_data.get('title', '')}' for {org_id} (topic: {topic})")

            elif topic == 'products/delete':
                shopify_product_id = webhook_data.get('id')
                if shopify_product_id:
                    from inventory.models import ShopifyProductCache
                    from django.core.cache import cache as django_cache
                    deleted, _ = ShopifyProductCache.objects.filter(
                        organization_id=org_id,
                        shopify_id=shopify_product_id,
                    ).delete()
                    django_cache.delete(f'shopify_products_{org_id}')
                    print(f"🗑️ Deleted product cache {shopify_product_id} for {org_id} (deleted={deleted})")

            elif topic == 'inventory_levels/update':
                inventory_item_id = webhook_data.get('inventory_item_id')
                available = webhook_data.get('available')
                if inventory_item_id is not None and available is not None:
                    from inventory.models import ShopifyProductCache
                    from django.core.cache import cache as django_cache

                    # Find the cached product containing this variant
                    products = ShopifyProductCache.objects.filter(organization_id=org_id)
                    matched = False
                    for product_cache in products:
                        data = product_cache.data or {}
                        variants = data.get('variants', [])
                        for i, variant in enumerate(variants):
                            if variant.get('inventory_item_id') == inventory_item_id:
                                variant['stock'] = available
                                # Update top-level stock if this is the first variant
                                if i == 0:
                                    data['stock'] = available
                                product_cache.data = data
                                product_cache.synced_at = timezone.now()
                                product_cache.save(update_fields=['data', 'synced_at'])
                                matched = True
                                print(f"📦 Inventory updated: '{data.get('name', '')}' variant '{variant.get('title', '')}' → {available} units")
                                break
                        if matched:
                            break

                    if not matched:
                        print(f"⚠️ inventory_levels/update: No cached variant with inventory_item_id={inventory_item_id}")

            elif topic in ['checkouts/create', 'checkouts/update']:
                print(f"Processing '{topic}' checkout webhook (Org: {org_id})")
                from core.models.sales import ChannelAbandonedCheckout
                from django.utils.dateparse import parse_datetime
                from core.views_sales import _derive_shopify_checkout_stage
                from core.models import ShopCredentials

                checkout_id = webhook_data.get('id')
                token = webhook_data.get('token')
                if not token:
                    return

                try:
                    shop_cred = ShopCredentials.objects.get(myshopify_domain=cleaned_domain)
                except ShopCredentials.DoesNotExist:
                    print(f"Shop credentials not found for domain {cleaned_domain}")
                    return

                customer_obj = webhook_data.get('customer') or {}
                addr = webhook_data.get('shipping_address') or {}
                billing = webhook_data.get('billing_address') or {}

                email = webhook_data.get('email') or customer_obj.get('email', '')
                first = addr.get('first_name') or billing.get('first_name') or customer_obj.get('first_name', '')
                last = addr.get('last_name') or billing.get('last_name') or customer_obj.get('last_name', '')
                customer_name = f"{first} {last}".strip()
                if not customer_name:
                    customer_name = 'Guest'
                phone = (webhook_data.get('phone') or addr.get('phone') or billing.get('phone')
                         or customer_obj.get('phone', ''))

                cart_value = float(webhook_data.get('total_price') or webhook_data.get('subtotal_price') or 0)
                item_count = len(webhook_data.get('line_items', []))
                line_items = [
                    {'title': i.get('title'), 'qty': i.get('quantity'), 'price': i.get('price')}
                    for i in webhook_data.get('line_items', [])
                ]

                # Note attributes for flexype state
                flexype_drop_off_state = next(
                    (a.get('value') for a in (webhook_data.get('note_attributes') or [])
                     if isinstance(a, dict) and a.get('name') == 'flexype_checkout_drop_off_state'),
                    ''
                )

                checkout_stage = _derive_shopify_checkout_stage(webhook_data)

                # Date
                abandoned_at_str = webhook_data.get('created_at') or webhook_data.get('updated_at')
                abandoned_at = parse_datetime(abandoned_at_str) if abandoned_at_str else timezone.now()

                # Get or create local record
                checkout_obj, created = ChannelAbandonedCheckout.objects.get_or_create(
                    shop=shop_cred,
                    shopify_token=token,
                    defaults={
                        'channel': 'shopify',
                        'abandoned_at': abandoned_at
                    }
                )

                # Update fields
                checkout_obj.checkout_url = webhook_data.get('abandoned_checkout_url', '') or ''
                checkout_obj.customer_name = customer_name
                checkout_obj.customer_email = email or ''
                checkout_obj.customer_phone = phone or ''
                checkout_obj.cart_value = cart_value
                checkout_obj.item_count = item_count
                checkout_obj.line_items = line_items
                checkout_obj.checkout_stage = checkout_stage
                checkout_obj.abandoned_at = abandoned_at
                
                # Store extra metadata in channel_meta
                checkout_obj.channel_meta = {
                    'id': checkout_id,
                    'flexype_drop_off_state': flexype_drop_off_state,
                    'province': addr.get('province') or billing.get('province') or '',
                    'zip': addr.get('zip') or billing.get('zip') or '',
                    'city': addr.get('city') or billing.get('city') or '',
                    'orders_count': customer_obj.get('orders_count') or 0,
                }
                checkout_obj.save()
                print(f"Saved/Updated Shopify Abandoned Checkout {token} from webhook topic '{topic}'")

            else:
                print(f"Received and ignored unhandled webhook topic: {topic}")

        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                pass
            else:
                print(f"Error processing webhook for topic {topic} (Org: {org_id}): {e}")
        finally:
            close_old_connections()


# ==============================================================================
