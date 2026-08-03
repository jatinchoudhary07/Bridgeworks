from django.utils import timezone
from datetime import timedelta, datetime, time
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import base64

logger = logging.getLogger(__name__)
from django.http import HttpResponse, JsonResponse
from django.db import models, transaction
from django.db.models import Prefetch, Q, Sum, TextField, Count, F, Case, When, DecimalField, OuterRef, Prefetch, Exists
from core.utils.payment_utils import get_payment_q_objects
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime, parse_date
from django.utils.timezone import make_aware
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate, Coalesce

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
import re

# --- Models ---
from core.models import (
    Order, LineItem, Fulfillment, TrackingInfo, Batch, PackagingBatch,
    PackagingImage, ShopCredentials, TeamMemberSettings, Invitation, TrackingEvent, CaseFile, IssueComment, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
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
    IsOrganizationOwner, IsAllowedCustomerExperience,
    HasModulePermission
)

User = get_user_model()




from .helpers import _get_org_id_or_none, _filter_orders_by_org_id, _clean_shopify_url
# 6. MANIFEST / DISPATCH VIEWS
# ==============================================================================

class ManifestSheetView(generics.ListAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:manifest_sheet:view'
    } 
    serializer_class = OrderSerializer 

    def get_queryset(self):
        org_id = _get_org_id_or_none(self.request)
        if not org_id:
            return Order.objects.none()

        return Order.objects.filter(
            org_id=org_id,
            fulfillments__isnull=False 
        ).exclude(
            financial_status__in=['refunded', 'voided'] 
        ).exclude(
            status='Cancelled'
        ).distinct().order_by('-created_at')
        
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 100

class PaginatedManifestOrderListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:manifest_sheet:view'
    }

    def get(self, request):
        # 1. Base Query - Start clean on Order model
        # We perform filters here, but avoid joining related tables in the main SELECT clause.
        queryset = Order.objects.exclude(
            financial_status__in=['refunded', 'voided']
        ).exclude(
            status='Cancelled'
        )

        # Apply Organization Filter
        queryset = _filter_orders_by_org_id(request, queryset)

        # ---------------------------------------------------------
        # OPTIMIZATION 1: Replace fulfillments__isnull=False with Exists
        # This checks for existence without joining/multiplying rows.
        # ---------------------------------------------------------
        has_fulfillment = Fulfillment.objects.filter(order=OuterRef('pk'))
        queryset = queryset.filter(Exists(has_fulfillment))

        # ---------------------------------------------------------
        # OPTIMIZATION 2: Fix Date Filtering (Index Friendly)
        # Instead of TruncDate (which kills indexes), we calculate the 
        # specific start/end timestamps in Python.
        # ---------------------------------------------------------
        tz_name = request.headers.get('X-User-Timezone')
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = timezone.get_current_timezone()

        start_date_str = request.query_params.get("startDate")
        end_date_str = request.query_params.get("endDate")

        if start_date_str:
            s_date = parse_date(start_date_str)
            if s_date:
                # Create a timezone-aware datetime for 00:00:00 user time
                s_datetime = datetime.combine(s_date, time.min).replace(tzinfo=user_tz)
                queryset = queryset.filter(created_at__gte=s_datetime)

        if end_date_str:
            e_date = parse_date(end_date_str)
            if e_date:
                # Create a timezone-aware datetime for 23:59:59 user time
                e_datetime = datetime.combine(e_date, time.max).replace(tzinfo=user_tz)
                queryset = queryset.filter(created_at__lte=e_datetime)

        # ---------------------------------------------------------
        # Filter: Payment Gateway (Local field, standard filter)
        # ---------------------------------------------------------
        payment_gateways = request.query_params.getlist("paymentGateway")
        if payment_gateways:
            q_pay = Q()
            for gw in payment_gateways:
                if gw == 'Razorpay PPCOD':
                    q_pay |= Q(payment_gateway_names__icontains='Razorpay', financial_status__iexact='partially_paid')
                else:
                    q_pay |= Q(payment_gateway_names__icontains=gw)
            queryset = queryset.filter(q_pay)

        # ---------------------------------------------------------
        # OPTIMIZATION 3: Delivery Partner via Subquery
        # ---------------------------------------------------------
        delivery_partners = request.query_params.getlist("deliveryPartner")
        if delivery_partners:
            # We want orders where *at least one* fulfillment uses these partners
            partner_match = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                tracking_info__company__in=delivery_partners
            )
            queryset = queryset.filter(Exists(partner_match))

        # ---------------------------------------------------------
        # OPTIMIZATION 4: Shipment Status via Subquery
        # ---------------------------------------------------------
        STATUS_MAP = {
            "Delivered": ["DEL", "delivered", "Delivered"],
            "In Transit": ["INT", "in_transit", "In Transit"],
            "Undelivered": ["UND", "undelivered", "Undelivered"],
            "RTO": ["RTO", "rto", "RTO Initiated"],
            "RTO Delivered": ["RTD", "rto_delivered", "RTO Delivered"],
            "Canceled": ["CAN", "cancelled", "Cancelled"],
            "Shipment Booked": ["SCH", "booked", "Booked", "Pending", "0"],
            "On Hold": ["ONH", "on_hold", "On Hold"],
            "Out For Delivery": ["OOD", "out_for_delivery", "Out For Delivery"],
            "Status Pending": ["NFI", "nfi", "Status Pending"],
            "NFID": ["NFIDS"],
            "Pickup Scheduled": ["RSCH", "pickup_scheduled"],
            "Out for Pickup": ["ROOP", "out_for_pickup"],
            "Shipment Picked Up": ["RPKP", "shipment_picked_up", "Picked Up"],
            "Return Delivered": ["RDEL", "return_delivered"],
            "Return In Transit": ["RINT", "return_in_transit"],
            "Pickup Rescheduled": ["RPSH", "pickup_rescheduled"],
            "Return Request Cancelled": ["RCAN"],
            "Return Request Closed": ["RCLO"],
            "Pickup Delayed": ["RSMD", "pickup_delayed"],
            "Pickup Cancelled": ["PCAN", "pickup_cancelled"],
            "Others": ["ROTH", "others"],
            "Pickup Failed": ["RPF", "pickup_failed"],
            "Manifested": ["0", "manifested", "Manifested"],
        }

        shipment_statuses = request.query_params.getlist("shipmentStatus")
        if shipment_statuses:
            status_codes = []
            for label in shipment_statuses:
                status_codes.extend(STATUS_MAP.get(label, [label]))
            
            # Use Exists to check if ANY fulfillment matches the status codes
            status_match = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                shipment_status__in=status_codes
            )
            queryset = queryset.filter(Exists(status_match))

        # ---------------------------------------------------------
        # OPTIMIZATION 5: Search
        # ---------------------------------------------------------
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            search_q = Q()
            
            # Local fields (fast)
            if search_query.isdigit():
                search_q |= Q(order_number=search_query)
            
            search_q |= Q(customer_first_name__icontains=search_query)
            search_q |= Q(customer_last_name__icontains=search_query)

            # Related fields (moved to Exists subqueries to avoid joins)
            # 1. Search in Tracking Number
            tracking_match = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                tracking_info__number__icontains=search_query
            )
            search_q |= Exists(tracking_match)

            # 2. Search in Service Name
            service_match = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                service__icontains=search_query
            )
            search_q |= Exists(service_match)

            queryset = queryset.filter(search_q)

        # ---------------------------------------------------------
        # FINAL STEPS: Ordering & Pagination
        # We removed .distinct() because we are no longer joining!
        # ---------------------------------------------------------
        queryset = queryset.order_by("-created_at")

        queryset = (
            queryset
            .select_related('customer', 'shipment')   # ← eliminates FK N+1 per row
            .prefetch_related(
                "line_items",
                "fulfillments__tracking_info",
            )
        )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)

        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return Response({
                "count": paginator.page.paginator.count,
                "num_pages": paginator.page.paginator.num_pages,
                "orders": serializer.data,
                "kpi": { "orders": paginator.page.paginator.count } 
            })

        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data)


def get_rto_risk_breakdown(order, profile=None, weather_alert=None, profile_fetched=False, weather_alert_fetched=False):
    """
    Build RTO risk breakdown for a single order.
    Pass pre-fetched `profile` and `weather_alert` to avoid N+1 DB queries.
    If not provided, falls back to a DB lookup (legacy, slow path).
    """
    from core.models import CustomerRiskProfile, WeatherAlert
    from django.utils import timezone
    
    breakdown = []
    
    # 1. Customer Risk Profile (use pre-fetched, or fallback to DB)
    if profile is None and not profile_fetched:
        profile = CustomerRiskProfile.objects.filter(
            org_id=order.org_id,
            customer_phone=order.contact_phone
        ).first()

    rto_rate = 0.0
    refusal_rate = 0.0
    if profile and profile.total_orders > 0:
        rto_rate = float(profile.rto_count) / profile.total_orders
        refusal_rate = float(profile.refusal_count) / profile.total_orders

    # Signal 1: Customer Lifetime RTO Rate
    if rto_rate > 0.5:
        breakdown.append(f"High lifetime RTO rate ({round(rto_rate*100)}%): +20")
    elif rto_rate > 0.3:
        breakdown.append(f"Moderate lifetime RTO rate ({round(rto_rate*100)}%): +15")
    elif rto_rate > 0.1:
        breakdown.append(f"Low lifetime RTO rate ({round(rto_rate*100)}%): +10")

    # Signal 2: Customer Lifetime Refusal Rate
    if refusal_rate > 0.3:
        breakdown.append(f"High lifetime delivery refusal rate ({round(refusal_rate*100)}%): +15")
    elif refusal_rate > 0.1:
        breakdown.append(f"Moderate lifetime delivery refusal rate ({round(refusal_rate*100)}%): +10")

    # Signal 3: Payment Method
    fs = (order.financial_status or '').lower()
    is_cod = 'cod' in fs or 'pending' in fs or 'partially_paid' in fs or 'partial payment' in str(order.tags or '').lower()
    if is_cod:
        breakdown.append("COD Payment Method: +15")
    else:
        breakdown.append("Prepaid Payment Method: +0")

    # Fetch related shipment (already select_related'd in the main query)
    shipment = getattr(order, 'shipment', None)

    # Signal 4: Current Shipment Delivery Attempts
    attempts = shipment.total_delivery_attempts if shipment else 0
    if attempts >= 3:
        breakdown.append(f"Multiple failed delivery attempts ({attempts}): +15")
    elif attempts == 2:
        breakdown.append("Two failed delivery attempts: +10")
    elif attempts == 1:
        breakdown.append("One failed delivery attempt: +5")

    # Signal 5: Time Elapsed Since First Attempt
    if shipment and shipment.first_attempt_date:
        days_elapsed = (timezone.now() - shipment.first_attempt_date).days
        if days_elapsed > 5:
            breakdown.append(f"Over 5 days since first attempt ({days_elapsed} days): +10")
        elif days_elapsed > 3:
            breakdown.append(f"Over 3 days since first attempt ({days_elapsed} days): +5")

    # Signal 6: AI-Classified NDR Category
    category = order.ndr_reason_category
    if category == 'REFUSED_DELIVERY':
        breakdown.append("Reason: Delivery Refused by Customer: +15")
    elif category == 'ADDRESS_ISSUE':
        breakdown.append("Reason: Incorrect/Incomplete Address: +12")
    elif category in ('COD_NOT_READY', 'CUSTOMER_UNAVAILABLE'):
        breakdown.append("Reason: Customer Unavailable or COD Not Ready: +8")
    elif category == 'PREMISES_CLOSED':
        breakdown.append("Reason: Premises Closed: +5")
    elif category == 'OTHERS':
        breakdown.append("Reason: General Exception / Unclassified: +3")

    # Signal 7: Weather / Regional Disruption Alert (use pre-fetched)
    state = order.shipping_state or ''
    if weather_alert is None and not weather_alert_fetched and state:
        # Fallback: only if not pre-fetched
        from core.models import WeatherAlert as _WA
        weather_alert = _WA.objects.filter(state_name__iexact=state.strip(), is_active=True).first()
    if weather_alert:
        breakdown.append(f"Active regional disruption alert in {state}: +10")

    # Signal 8: Customer Responsiveness adjustment
    call_status = (order.ndr_call_status or '').lower()
    if call_status == 'will accept':
        breakdown.append("Customer confirmed reattempt (Will Accept): -30")
    elif call_status in ('not answering', 'switch off', 'busy', 'rejected call', 'asked to call back'):
        breakdown.append(f"Customer unreachable (Call status: {order.ndr_call_status}): +10")
    elif call_status in ('refused', 'cancelled', 'rto'):
        breakdown.append(f"Customer requested cancellation/RTO: +30")

    if not breakdown:
        breakdown.append("Stable order. No risk signals detected: +0")
        
    return breakdown


class TrackingPageOrderListView(APIView):
    pagination_class = StandardResultsSetPagination
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': [
            'logistics:lm_sheet:view',
            'logistics:ndr_action:view',
            'logistics:delivered_orders:view',
            'rto_module:rto_in_transit:view',
            'rto_module:rto_delivered:view',
            'rto_module:rto_manager:view',
            'orders:rto:view'
        ]
    }

    def _parse_shipping_address(self, shipping_address):
        """Parse shipping_address which might be a JSON string or dict"""
        if not shipping_address:
            return None
        
        import json
        addr = shipping_address
        if isinstance(addr, str):
            try:
                addr = json.loads(addr)
            except (json.JSONDecodeError, TypeError):
                return addr
        
        if isinstance(addr, dict):
            return {
                "address1": addr.get('address1', '') or addr.get('address_1', ''),
                "address2": addr.get('address2', '') or addr.get('address_2', ''),
                "province": addr.get('province', '') or addr.get('state', ''),
                "province_code": addr.get('province_code', '') or addr.get('state', ''),
                "city": addr.get('city', ''),
                "zip": addr.get('zip', '') or addr.get('pincode', ''),
            }
        return None

    def _get_best_shipping_address(self, order):
        """Find the best shipping address for an order, with fallbacks to Customer table or linked customer"""
        addr = order.shipping_address
        if addr:
            if isinstance(addr, str):
                import re
                cleaned = re.sub(r'[\s,]+', '', addr).strip()
                if cleaned:
                    return addr
            else:
                return addr

        # Fallback 1: Query Customer table by exact phone or suffix matching
        phone = order.contact_phone
        if phone and phone != '-':
            from core.models import Customer
            clean_phone = phone.strip()
            q_phone = Q(phone=clean_phone)
            if len(clean_phone) >= 10:
                q_phone |= Q(phone__endswith=clean_phone[-10:])

            # Exclude customers with empty or ' , , , ' addresses
            cust = Customer.objects.filter(org_id=order.org_id).filter(q_phone).exclude(address__isnull=True).exclude(address='').first()
            if cust and cust.address:
                import re
                if isinstance(cust.address, str):
                    cleaned = re.sub(r'[\s,]+', '', cust.address).strip()
                    if cleaned:
                        return cust.address
                else:
                    return cust.address

        # Fallback 2: Order linked customer address
        if order.customer and order.customer.address:
            import re
            c_addr = order.customer.address
            if isinstance(c_addr, str):
                cleaned = re.sub(r'[\s,]+', '', c_addr).strip()
                if cleaned:
                    return c_addr
            else:
                return c_addr

        return None

    def get(self, request):
        # ─── Extract EARLY — used to choose the optimal base query ───────────
        tab_filter = request.GET.get('tab', 'all')

        # Subquery: Check if fulfillment has valid tracking info
        has_tracking_subquery = Fulfillment.objects.filter(
            order=OuterRef('pk'),
            tracking_info__isnull=False
        ).exclude(tracking_info__number='')

        # FIX A: For NDR, apply is_ndr=True FIRST (hits a boolean index on the
        # already-small NDR subset), then run the correlated Exists subquery only
        # on those rows.
        if tab_filter == 'ndr':
            orders = (
                Order.objects
                .filter(is_ndr=True)                    # index scan first
                .filter(Exists(has_tracking_subquery))  # correlated subquery
                .order_by('-created_at')
            )
        else:
            orders = Order.objects.filter(Exists(has_tracking_subquery)).order_by('-created_at')
        
        # Apply Organization Filter (CRITICAL: Filter by org_id)
        orders = _filter_orders_by_org_id(request, orders)

        # ------------------------------------------------------------------
        # 1.1 STAGE FILTER (Must be applied early)
        # ------------------------------------------------------------------
        
        # Capture the queryset regardless of Stage Filter for the Logistics Matrix
        # This ensures the Matrix shows the full pipeline even when a specific stage is selected.
        orders_for_matrix = orders 

        stage_filter = request.GET.get('stage')
        if stage_filter:
            orders = get_queryset_for_stage(orders, stage_filter).distinct()

        # ------------------------------------------------------------------
        # 2. FILTERS
        # ------------------------------------------------------------------

        # A. Search Filter
        search_query = request.GET.get('search')
        if search_query:
            match_tracking_number = Fulfillment.objects.filter(
                order=OuterRef('pk'), 
                tracking_info__number__icontains=search_query
            )
            q_search = (
                Q(order_number__icontains=search_query) |
                Q(shipping_address__icontains=search_query) |
                Q(contact_phone__icontains=search_query) |
                Q(customer_first_name__icontains=search_query) |
                Q(customer_last_name__icontains=search_query) |
                Exists(match_tracking_number)
            )
            orders = orders.filter(q_search)
            orders_for_matrix = orders_for_matrix.filter(q_search)

        # B. Date Filters
        tz_name = request.headers.get('X-User-Timezone')
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = timezone.get_current_timezone()

        start_date_str = request.GET.get('startDate')
        end_date_str = request.GET.get('endDate')
        
        if start_date_str or end_date_str:
            s_datetime = None
            if start_date_str:
                s_date = parse_date(start_date_str)
                if s_date:
                    s_datetime = datetime.combine(s_date, time.min).replace(tzinfo=user_tz)

            e_datetime = None
            if end_date_str:
                e_date = parse_date(end_date_str)
                if e_date:
                    e_datetime = datetime.combine(e_date, time.max).replace(tzinfo=user_tz)

            if tab_filter == 'ndr':
                if s_datetime:
                    orders = orders.filter(current_status_date__gte=s_datetime)
                    orders_for_matrix = orders_for_matrix.filter(current_status_date__gte=s_datetime)
                if e_datetime:
                    orders = orders.filter(current_status_date__lte=e_datetime)
                    orders_for_matrix = orders_for_matrix.filter(current_status_date__lte=e_datetime)
            else:
                # Default behavior: filter by order created_at date
                if s_datetime:
                    orders = orders.filter(created_at__gte=s_datetime)
                    orders_for_matrix = orders_for_matrix.filter(created_at__gte=s_datetime)
                if e_datetime:
                    orders = orders.filter(created_at__lte=e_datetime)
                    orders_for_matrix = orders_for_matrix.filter(created_at__lte=e_datetime)

        # B.1. NDR Call Status Filter
        call_statuses = request.GET.getlist('ndr_call_status')
        if call_statuses:
            orders = orders.filter(ndr_call_status__in=call_statuses)
            orders_for_matrix = orders_for_matrix.filter(ndr_call_status__in=call_statuses)

        # C. Tab Filters
        # NOTE: NDR branch is intentionally omitted — is_ndr=True is already in the
        # base query (Fix A above). Filtering it twice is harmless but wastes a WHERE
        # clause; more importantly, the comment documents the intent.
        if tab_filter == 'rto_transit':
            # RTO Transit and Delivered statuses
            combined_rto_statuses = RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES
            orders = orders.filter(current_status__in=combined_rto_statuses)
            orders_for_matrix = orders_for_matrix.filter(current_status__in=combined_rto_statuses)
        elif tab_filter in ('returns', 'rto_returns_exchanges'):
            # Customer initiated Returns & Exchanges
            returns_q = (
                ~Q(return_awb='') |
                ~Q(exchange_awb='') |
                Q(return_awb__isnull=False) |
                Q(exchange_awb__isnull=False)
            )
            orders = orders.filter(returns_q)
            orders_for_matrix = orders_for_matrix.filter(returns_q)

        # D. Courier Filter
        courier_list = request.GET.getlist('courier')
        if courier_list:
            courier_q = Q()
            for courier in courier_list:
                courier_q |= Q(tracking_info__company__icontains=courier)
            
            has_courier = Fulfillment.objects.filter(
                order=OuterRef('pk')
            ).filter(courier_q)
            
            orders = orders.filter(Exists(has_courier))
            orders_for_matrix = orders_for_matrix.filter(Exists(has_courier))

        # E. Status Filter - Use same bucket logic as table aggregation (icontains for case-insensitivity)
        status_list = request.GET.getlist('status')
        if status_list:
            # Define status buckets matching the table aggregation
            STATUS_BUCKETS = {
                'Manifested': ['manifested', '0', 'awb_assigned', 'label created'],
                'Shipment Booked': ['booked', 'pickup scheduled', 'scheduled', 'shipment booked'],
                'Shipment Pickedup': ['picked up', 'pickup', 'shipment picked up'],
                'In Transit': ['intransit', 'in transit', 'dispatched'],
                'Out for Delivery': ['out for delivery'],
                'Delivered': ['delivered'],
                'RTO initiated': ['rto initiated', 'return initiated'],
                'RTO Delivered': ['rto delivered'],
                'Returns intransit': ['return in transit', 'rto in transit'],
                'Returns Delivered': ['return delivered'],
            }
            
            # Build Q object for selected statuses
            q_status_filter = Q()
            
            for status_label in status_list:
                # Special handling for 'Undelivered' - use is_ndr flag
                if status_label == 'Undelivered':
                    q_status_filter |= Q(is_ndr=True)
                elif status_label == 'Delivered':
                    # Delivered but NOT NDR, RTO, or Return
                    q_status_filter |= (
                        Q(current_status__icontains='delivered') &
                        ~Q(is_ndr=True) &
                        ~Q(current_status__icontains='rto') &
                        ~Q(current_status__icontains='return')
                    )
                elif status_label in STATUS_BUCKETS:
                    # Use icontains for case-insensitive matching
                    keywords = STATUS_BUCKETS[status_label]
                    for kw in keywords:
                        q_status_filter |= Q(current_status__icontains=kw)
                else:
                    # Fallback for unknown statuses
                    q_status_filter |= Q(current_status__iexact=status_label)
            
            orders = orders.filter(q_status_filter)
            orders_for_matrix = orders_for_matrix.filter(q_status_filter)

        # F. Payment Method Filter
        payment_list = request.GET.getlist('payment_method')
        if payment_list:
            payment_qs = get_payment_q_objects()
            q_payment = Q()
            if 'cod' in payment_list:
                q_payment |= payment_qs['cod']
            if 'partial' in payment_list:
                q_payment |= payment_qs['partial']
            if 'prepaid' in payment_list:
                q_payment |= payment_qs['prepaid']
            orders = orders.filter(q_payment)
            orders_for_matrix = orders_for_matrix.filter(q_payment)

        # ==============================================================================
        # 3. DATA PREPARATION - Calculate Payment Breakdown BEFORE pagination
        #    OPTIMIZATION: Skip for NDR tab (NDRSheet doesn't display these KPIs)
        # ==============================================================================

        def get_payment_label(pg_names, fin_status, tags, raw_data=None):
            from core.utils.payment_utils import derive_payment_type_from_fields
            derived = derive_payment_type_from_fields(pg_names, fin_status, tags, raw_data)
            if derived == 'COD':
                return "cod"
            elif derived == 'Partially Paid':
                return "ppcod"
            else:
                return "prepaid"

        total_remittance = 0.0
        prepaid_qty = 0
        prepaid_amount = 0.0
        ppcod_qty = 0
        ppcod_amount = 0.0
        cod_qty = 0
        cod_amount = 0.0
        payment_breakdown = {}

        if tab_filter != 'ndr':  # Skip expensive aggregation for NDR tab
            # Pull values for KPI breakdown (dependent on stage filter) in ONE fast query
            kpi_orders_data = list(orders.values('total_price', 'payment_gateway_names', 'financial_status', 'tags', 'raw_data'))

            for order in kpi_orders_data:
                price = float(order['total_price'] or 0)
                total_remittance += price
                pay_label = get_payment_label(order['payment_gateway_names'], order['financial_status'], order['tags'], order.get('raw_data'))
                if pay_label == "cod":
                    cod_qty += 1
                    cod_amount += price
                elif pay_label == "ppcod":
                    ppcod_qty += 1
                    ppcod_amount += price
                else:
                    prepaid_qty += 1
                    prepaid_amount += price

            payment_breakdown = {
                "prepaid": {"qty": prepaid_qty, "amount": prepaid_amount},
                "ppcod": {"qty": ppcod_qty, "amount": ppcod_amount},
                "cod": {"qty": cod_qty, "amount": cod_amount}
            }

        # Check for analytics mode - bypass pagination for bulk data fetch
        analytics_mode = request.GET.get('analytics', '').lower() == 'true'

        # Prefetch related data sorted correctly (DB optimization)
        events_prefetch = Prefetch(
            'tracking_events',
            queryset=TrackingEvent.objects.order_by('-datetime')
        )
        fulfillments_prefetch = Prefetch(
            'fulfillments',
            queryset=Fulfillment.objects.prefetch_related('tracking_info', events_prefetch)
        )

        # line_items are only serialized in analytics mode; NDR never uses them.
        # Dropping the prefetch removes one extra JOIN from every NDR page load.
        if tab_filter == 'ndr' and not analytics_mode:
            orders = orders.select_related('shipment', 'customer').prefetch_related(
                fulfillments_prefetch
            )
        else:
            orders = orders.select_related('shipment', 'customer').prefetch_related(
                fulfillments_prefetch, 'line_items'
            )
        
        if analytics_mode:
            # For analytics, return all orders without pagination (capped at 5000 for safety)
            result_page = list(orders[:5000])
            total_count = len(result_page)
        else:
            paginator = self.pagination_class()
            result_page = paginator.paginate_queryset(orders, request)
            total_count = paginator.page.paginator.count

        # ==============================================================================
        # 4. PRE-FETCH NDR RISK DATA IN BULK (Critical: eliminates N+1 DB queries)
        #    For 100 NDR orders, the old code did 200 DB queries here.
        #    Now we do exactly 2 queries total for the whole page.
        # ==============================================================================
        from core.models import CustomerRiskProfile, WeatherAlert

        # Build lookup maps keyed by phone number
        page_phones = [o.contact_phone for o in result_page if o.contact_phone]
        page_org_id = _get_org_id_or_none(request)

        # Batch-load all risk profiles for phones in this page (1 query)
        risk_profiles_map = {}
        if page_phones and page_org_id:
            profiles_qs = CustomerRiskProfile.objects.filter(
                org_id=page_org_id,
                customer_phone__in=page_phones
            )
            for p in profiles_qs:
                risk_profiles_map[p.customer_phone] = p

        # Batch-load all active weather alerts (1 query, tiny table)
        page_states = list({o.shipping_state for o in result_page if o.shipping_state})
        weather_alerts_map = {}
        if page_states:
            for wa in WeatherAlert.objects.filter(state_name__in=page_states, is_active=True):
                weather_alerts_map[wa.state_name.lower()] = wa

        # ==============================================================================
        # 5. SERIALIZATION (With Normalization & NDR Fields)
        # ==============================================================================
        data = []
        for order in result_page:
            # Manually extract data to avoid N+1 queries from serializers
            fulfillments = list(order.fulfillments.all())
            
            # 1. Get Tracking Info
            tracking_number = "N/A"
            tracking_company = "N/A"
            tracking_url = ""
            
            for f in fulfillments:
                ti_list = list(f.tracking_info.all())
                if ti_list:
                    ti = ti_list[0]
                    tracking_number = ti.number
                    tracking_company = ti.company
                    tracking_url = ti.url
                    break 
            
            # 2. Merge Events
            events_list = []
            seen_events = set()
            for f in fulfillments:
                for event in f.tracking_events.all():
                    unique_key = f"{event.status}_{event.datetime}"
                    if unique_key not in seen_events:
                        events_list.append({
                            "status": event.status,
                            "details": event.details,
                            "datetime": event.datetime,
                        })
                        seen_events.add(unique_key)
            events_list.sort(key=lambda x: x['datetime'], reverse=True)

            # 3. Payment Label (must match get_payment_q_objects logic)
            from core.utils.payment_utils import derive_payment_type_from_fields
            derived = derive_payment_type_from_fields(
                order.payment_gateway_names,
                order.financial_status,
                order.tags,
                order.raw_data
            )
            if derived == 'PrePaid':
                opm_label = "Prepaid"
            else:
                opm_label = derived

            # 4. STATUS NORMALIZATION
            raw_status = order.current_status or "Pending"
            display_status = raw_status.replace("_", " ")

            # 5. Resolve NDR risk data using pre-fetched maps (ZERO extra DB queries)
            order_profile = risk_profiles_map.get(order.contact_phone)
            order_state_lower = (order.shipping_state or '').strip().lower()
            order_weather_alert = weather_alerts_map.get(order_state_lower)

            # 6. Shipping address: use select_related customer (no extra query)
            addr = order.shipping_address
            if not addr and order.customer and order.customer.address:
                addr = order.customer.address
            parsed_addr = self._parse_shipping_address(addr)

            data.append({
                "id": order.id,
                "order_number": order.order_number,
                "total_price": order.total_price,
                "created_at": order.created_at,
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                    "url": tracking_url
                },
                "computedStatus": display_status, 
                "computedDetails": order.current_status_details or "",
                "payment_method": opm_label,
                "tracking_events": events_list,
                "customer_name": f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip() or "-",
                "contact_phone": order.contact_phone or "-",

                # NDR Fields
                "ndr_call_status": order.ndr_call_status,
                "ndr_remarks": order.ndr_remarks,
                "ndr_last_called_at": order.ndr_last_called_at,
                "ndr_reason_category": order.ndr_reason_category,
                "ndr_classification_confidence": order.ndr_classification_confidence,
                "ndr_conversion_status": order.ndr_conversion_status,
                "ndr_rto_risk_score": order.ndr_rto_risk_score,
                # Uses pre-fetched profile + weather alert: 0 extra DB queries
                "ndr_rto_risk_breakdown": get_rto_risk_breakdown(
                    order,
                    profile=order_profile,
                    weather_alert=order_weather_alert,
                    profile_fetched=True,
                    weather_alert_fetched=True
                ),
                "ndr_last_scan_time": order.ndr_last_scan_time.isoformat() if order.ndr_last_scan_time else None,
                
                # Line Items for Analytics
                "line_items": [
                    {
                        "sku": item.sku or "-",
                        "title": item.name or "Unknown Product",
                        "quantity": item.quantity or 1,
                        "variant_id": item.variant_id,
                    }
                    for item in order.line_items.all()
                ],

                # Additional fields for Analytics
                "shipping_address": parsed_addr,
                "shipping_state": order.shipping_state or "-",
                "shipping_pincode": order.shipping_pincode or "-",
                "updated_at": order.updated_at,
                "current_tracking_status": order.current_status,
                "confirmed_at": order.confirmed_at,
                "packaged_at": order.packaged_at,
            })

        # ==============================================================================
        # 5. LOGISTICS MATRIX AGGREGATION (Dynamic based on filters - In-Memory)
        #    OPTIMIZATION: Skip for NDR tab (NDRSheet doesn't display logistics matrix)
        # ==============================================================================
        logistics_matrix = {}
        courier_matrix = {}

        if tab_filter != 'ndr':  # Skip expensive aggregation for NDR tab
            matrix_buckets = {
                'Manifested': ['manifested', '0', 'awb_assigned', 'label created'], 
                'Shipment Booked': ['booked', 'pickup scheduled', 'scheduled', 'shipment booked'],
                'Shipment Pickedup': ['picked up', 'pickup', 'shipment picked up'],
                'Dispatched': ['dispatched'],
                'Intransit': ['intransit', 'in transit'],
                'Out for Delivery': ['out for delivery'],
                'Delivered': ['delivered'],
                'Undelivered': [
                    'future delivery requested', 'customer refused', 'delivery attempted-premises closed',
                    'attempted delivery', 'consignee unavailable', 'cod payment not ready', 'undelivered',
                    'address incorrect', 'pickup failed', 'exception', 'cod not ready', 'crta',
                    'consignee refused to accept', 'und', 'entry restricted area', 
                    'customer refused - otp verified', 'office/residence closed', 'consignee not available',
                    'customer not available', 'cna', 'oda', '22', '25'
                ],
                'RTO initiated': ['rto initiated', 'return initiated'],
                'RTO Delivered': ['rto delivered', 'return delivered'],
                'Returns intransit': ['return in transit', 'rto in transit'],
                'Returns Delivered': ['return delivered'] 
            }

            # Initialize the logistics matrix structure
            logistics_matrix = {
                'Prepaid': {b: {'qty': 0, 'amount': 0.0} for b in matrix_buckets},
                'PPCOD': {b: {'qty': 0, 'amount': 0.0} for b in matrix_buckets},
                'COD': {b: {'qty': 0, 'amount': 0.0} for b in matrix_buckets},
                'Total': {b: {'qty': 0, 'amount': 0.0} for b in matrix_buckets}
            }

            # Pull values for matrix aggregation (independent of stage filter)
            matrix_orders_data = list(orders_for_matrix.values('total_price', 'current_status', 'is_ndr', 'payment_gateway_names', 'financial_status', 'tags', 'raw_data'))

            for order in matrix_orders_data:
                price = float(order['total_price'] or 0)
                
                # Map pay label to match structural keys ('Prepaid', 'PPCOD', 'COD')
                raw_pay = get_payment_label(order['payment_gateway_names'], order['financial_status'], order['tags'], order.get('raw_data'))
                if raw_pay == "cod":
                    pay_label = "COD"
                elif raw_pay == "ppcod":
                    pay_label = "PPCOD"
                else:
                    pay_label = "Prepaid"
                    
                status_raw = str(order['current_status'] or "").lower()
                is_ndr = bool(order['is_ndr'])

                matched_buckets = []
                
                # 1. Undelivered is based on is_ndr flag
                if is_ndr:
                    matched_buckets.append('Undelivered')

                # 2. Check each bucket's keywords
                for bucket_name, keywords in matrix_buckets.items():
                    if bucket_name == 'Undelivered':
                        continue
                    
                    matched = False
                    for kw in keywords:
                        if kw in status_raw:
                            matched = True
                            break
                    
                    if matched:
                        # Exclusion logic for Delivered
                        if bucket_name == 'Delivered':
                            if is_ndr or 'rto' in status_raw or 'return' in status_raw:
                                continue
                        matched_buckets.append(bucket_name)

                # Populate matrix
                for b in matched_buckets:
                    logistics_matrix[pay_label][b]['qty'] += 1
                    logistics_matrix[pay_label][b]['amount'] += price
                    
                    logistics_matrix['Total'][b]['qty'] += 1
                    logistics_matrix['Total'][b]['amount'] += price

        # Return response - different format for analytics vs paginated
        response_data = {
            "orders": data,
            "count": total_count,
            "total_remittance": total_remittance,
            "payment_breakdown": payment_breakdown,
            "logistics_matrix": logistics_matrix,
            "courier_matrix": courier_matrix
        }
        
        if analytics_mode:
            return Response({"results": response_data})
        else:
            return paginator.get_paginated_response(response_data)

class FetchTrackingDataView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:create'
    }

    def post(self, request, *args, **kwargs):
        # 1. Setup Context (Must be done in main thread)
        org_id = _get_org_id_or_none(request)
        if not org_id:
             return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)

        creds = _get_decrypted_credentials(org_id)
        if not creds:
             return Response({"error": "Shop credentials configuration missing."}, status=status.HTTP_404_NOT_FOUND)

        # Extract credentials to pass into threads
        shipway_email = creds['shipway_email']
        shipway_license_key = creds['shipway_license_key']
        order_prefix = creds['order_prefix']

        # Build auth header (same as backfill_shipway_pii.py)
        encoded = base64.b64encode(f"{shipway_email}:{shipway_license_key}".encode()).decode()
        shipway_headers = {'Authorization': f'Basic {encoded}'}
        
        order_numbers = request.data.get('order_numbers', [])
        
        # 2. Define the Worker Function (Runs in parallel)
        def process_single_order(order_number):
            # Django opens a new DB connection for this thread. 
            # We must ensure it's clean to avoid connection leaks.
            close_old_connections()
            
            result_status = "failed"
            
            url_getorders = "https://app.shipway.com/api/getorders"
            url_tracking = "https://app.shipway.com/api/tracking"
            
            # --- STATUS MAPPING (Copied from your original logic) ---
            SHIPWAY_CODE_MAP = {
            "DEL": "Delivered", "DELIVERED": "Delivered",
            "INT": "In Transit", "IN TRANSIT": "In Transit",
            "UND": "Undelivered",
            "RTO": "RTO Initiated",
            "RTD": "RTO Delivered",
            "CAN": "Cancelled",
            "SCH": "Shipment Booked", "Booked": "Shipment Booked",
            "PKP": "Picked Up", "PUP": "Picked Up", "PICKED UP": "Picked Up",
            "PKF": "Pick up Failed",
            "PCAN": "Pick up Cancelled",
            "ONH": "On Hold",
            "OOD": "Out For Delivery", "OUT FOR DELIVERY": "Out For Delivery",
            "NWI": "Network Issue",
            "DNB": "Delivery Next Day",
            "NFI": "No Information Yet",
            "ODA": "Out of Delivery Area",
            "OTH": "Others",
            "SMD": "Delivery Delayed",
            "22": "Address Incorrect",
            "23": "Delivery Attempted",
            "24": "Pending - Undelivered",
            "25": "Delivery Attempted-Premises Closed",
            "CRTA": "Customer Refused",
            "DEX": "Delivery Exception",
            "DRE": "Delivery Rescheduled",
            "PNR": "COD Payment Not Ready",
            "RAD": "Reached at Destination",
            "RINT": "Return In Transit",
            "RDEL": "Return Delivered",
            "SHNDR1": "Consignee Uncontactable",
            "SHNDR2": "Wrong Address",
            "SHNDR3": "COD Not Ready",
            "SHNDR4": "Customer Asked For Future Delivery",
            "SHNDR5": "Customer Asked For Self Collect",
            "SHNDR6": "Customer Refused",
            "SHNDR7": "Auto Reattempt",
            "SHNDR8": "Office/Residence Closed",
            "SHNDR9": "Others",
            "SHNDR10": "Entry Restricted Area",
            "SHNDR11": "Out of Delivery Area",
            "SHNDR12": "Payment/Qty/Bill/OTP Dispute",
            "SHNDR13": "Reattempt Next Day",
            "SHNDR14": "Customer Requested Open Delivery",
            "SHNDR15": "Customer did not show ID card",
            "SHNDR16": "Customer Not Available",
            "SHNDR17": "COVID - Access Restricted",
            "SHNDR18": "Customer Refused - OTP Verified",
            "SHNDR19": "Customer Refused - IVR Verified",
            "SHNDR20": "Delivery Not Attempted",
            "SHNDR21": "Customer Not Ready with Exchange Item",
            "SHNDR22": "Doubtful Order",
            "SHPFR0": "Pickup Exception - Others",
            "SHPFR1": "Seller Not Available / Phone Not Contactable",
            "SHPFR2": "Incomplete Address / Vendor Shifted",
            "SHPFR3": "No Pickup / Shipment Not Ready",
            "SHPFR4": "Vehicle Issue / Space Constraint",
            "SHPFR5": "Regulatory Not Compliant",
            "SHPFR6": "Pickup Request Cancelled by Seller",
            "SHPFR7": "Seller Requested Future Pickup",
            "SHPFR8": "AWB Rejected",
            "SHPFR9": "Duplicate Pickup Request",
            "SHPFR10": "No Attempt / Pickup Delay",
            "SHPFR11": "Non Serviceable Location",
            "SHPFR12": "Pickup Failed - Dangerous Goods",
            "SHPFR13": "Product Packaging Issue",
            "SHPFR14": "RTO",
            "SHPFR15": "Handed Over to Other Courier",
            "SHPFR16": "Shipper Premises Closed",
            "SHPFR17": "Barcode Issue",
            "SHPRF18": "Seller Closed",
            "SHPRF19": "COVID - Access Restricted",
            "SHPRF20": "Pickup Request Expired",
            "RTONDR1": "Seller Wants Open Delivery",
            "RTONDR2": "Seller Premise Closed",
            "RTONDR3": "Seller Not Contactable",
            "RTONDR4": "Address Not Correct",
            "RTONDR5": "Seller Refused Delivery",
            "RTONDR6": "RTO - Other",
            "RTONDR7": "RTO - Wrong Address",
            "RTONDR8": "Seller Refused - Damaged",
            "RTONDR9": "Seller Refused - Content Missing",
            "RTONDR10": "Seller Refused - Invoice Missing",
            "RTONDR11": "Seller Uncontactable",
            "RTONDR12": "Seller Not Available"
        }

            try:
                # Re-fetch order inside thread to ensure fresh DB state
                order_obj = Order.objects.get(order_number=order_number, org_id=org_id)
                
                merged_scans = [] 
                history_data = None  
                latest_data = None    
                
                # --- A: FETCH HISTORY ---
                try:
                    full_id = f"{order_prefix}{order_number}"
                    # Timeout is safe here because this runs in its own thread
                    resp_hist = requests.get(url_getorders, params={'orderid': full_id}, headers=shipway_headers, timeout=15)
                    if resp_hist.ok:
                        data = resp_hist.json()
                        if isinstance(data, dict):
                            if 'message' in data and isinstance(data['message'], list):
                                history_data = data['message'][0]
                            else:
                                history_data = data
                except Exception as e:
                    print(f"[Thread] History fetch failed for {order_number}: {e}")

                # --- B: LOOK FOR AWB ---
                awb = None
                if history_data and history_data.get('tracking_number'):
                    awb = history_data.get('tracking_number')
                else:
                    # Check DB existing info
                    tf = order_obj.fulfillments.first()
                    if tf:
                        ti = tf.tracking_info.first()
                        if ti: awb = ti.number

                # --- C: FETCH TRACKING ---
                if awb:
                    try:
                        resp_track = requests.get(url_tracking, params={"awb_numbers": awb, "tracking_history": 1}, headers=shipway_headers, timeout=15)
                        if resp_track.ok:
                            raw = resp_track.json()
                            if isinstance(raw, list) and len(raw) > 0:
                                latest_data = raw[0].get('tracking_details')
                    except Exception as e:
                        print(f"[Thread] Tracking fetch failed for {order_number}: {e}")

                # --- D: PROCESS DATA ---
                if history_data:
                    raw_scans = history_data.get('shipment_status_scan', [])
                    for scan in raw_scans:
                        merged_scans.append({
                            'status': scan.get('status'),
                            'date_str': scan.get('datetime'),
                            'details': scan.get('sub_status', '')
                        })

                if latest_data:
                    raw_code = latest_data.get('shipment_status')
                    readable_status = SHIPWAY_CODE_MAP.get(raw_code, raw_code) 
                    if readable_status: readable_status = readable_status.title()

                    details_arr = latest_data.get('shipment_details', [{}])
                    extra_details = ""
                    inner_status = ""
                    
                    if details_arr:
                        inner_status = details_arr[0].get('current_status') or ""
                        extra_details = inner_status

                    if inner_status and ("rto" in inner_status.lower() or "return" in inner_status.lower()):
                        if not readable_status.lower().startswith("rto"):
                            readable_status = f"RTO - {readable_status}"

                    real_date = timezone.now()
                    if details_arr:
                        det = details_arr[0]
                        if "delivered" in readable_status.lower() and det.get('delivered_date'):
                            real_date = det.get('delivered_date')
                        elif "picked up" in readable_status.lower() and det.get('pickup_date'):
                            real_date = det.get('pickup_date')

                    if readable_status:
                        last_status = merged_scans[-1]['status'].title() if merged_scans else ""
                        if readable_status != last_status:
                            merged_scans.append({
                                'status': readable_status,
                                'date_str': real_date,
                                'details': extra_details 
                            })

                # --- E: SAVE ---
                if merged_scans or latest_data:
                    with transaction.atomic():
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

                        if latest_data:
                            raw_code_main = latest_data.get('shipment_status')
                            main_status = SHIPWAY_CODE_MAP.get(raw_code_main, raw_code_main).title()
                            
                            details_arr = latest_data.get('shipment_details', [{}])
                            inner_status = details_arr[0].get('current_status') if details_arr else ""
                            if inner_status and ("rto" in inner_status.lower() or "return" in inner_status.lower()):
                                if not main_status.lower().startswith("rto"):
                                    main_status = f"RTO - {main_status}"
                            main_service = details_arr[0].get('courier_name') if details_arr else "Unknown"
                        else:
                            main_status = history_data.get('shipment_status_name') if history_data else "Unknown"
                            main_service = history_data.get('carrier_title') if history_data else "Unknown"
                        
                        fulfillment_obj = Fulfillment.objects.create(
                            order=order_obj,
                            shipment_status=main_status,
                            service=main_service,
                            status='success',
                            created_at=timezone.now()
                        )

                        TrackingInfo.objects.create(
                            fulfillment=fulfillment_obj,
                            number=awb or "N/A",
                            company=main_service,
                            url=existing_label_url or (f"https://track.shipway.com/t/{awb}" if awb else "")
                        )
                        
                        order_obj.fulfillment_status = 'Tracking_added'
                        order_obj.save()

                        events_to_create = []
                        for scan in merged_scans:
                            dt_val = None
                            d_input = scan['date_str']
                            if isinstance(d_input, datetime):
                                dt_val = d_input
                            elif d_input:
                                try:
                                    cln = str(d_input).replace(" ", "T")
                                    dt_val = parse_datetime(cln)
                                    if dt_val and dt_val.tzinfo is None: dt_val = make_aware(dt_val)
                                except:
                                    dt_val = timezone.now()
                            
                            if dt_val:
                                events_to_create.append(TrackingEvent(
                                    fulfillment=fulfillment_obj,
                                    status=scan['status'],
                                    datetime=dt_val,
                                    details=scan['details']
                                ))
                        
                        if events_to_create:
                            TrackingEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)

                        order_obj.update_tracking_status()
                    result_status = "success"

            except Exception as e:
                print(f"[Thread] Critical error processing {order_number}: {e}")
            
            # Close connection before finishing thread
            close_old_connections()
            return (order_number, result_status)

        # 3. Execute Threads
        successful_orders = []
        failed_orders = []

        # Safe Workers Count
        # SQLite: 3 workers (buffered by transaction.atomic)
        # Postgres (Render): 8 workers (high performance)
        from django.conf import settings
        is_sqlite = 'sqlite' in settings.DATABASES['default']['ENGINE'].lower()
        max_workers = 3 if is_sqlite else 8

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks
            future_to_order = {executor.submit(process_single_order, num): num for num in order_numbers}
            
            # Wait for completion
            for future in as_completed(future_to_order):
                ord_num, status_result = future.result()
                if status_result == "success":
                    successful_orders.append(ord_num)
                else:
                    failed_orders.append(ord_num)

        return Response({
            "successful_orders": successful_orders, 
            "failed_orders": failed_orders,
            "status": f"Sync Complete. Updated: {len(successful_orders)}"
        }, status=200)

# ==============================================================================
# MANIFEST FLOW VIEWS
# ==============================================================================

class BulkManifestOrdersView(APIView):
    """
    POST /api/orders/manifest-bulk/
    Body: { "order_numbers": [40412, 40413, ...] }

    Moves selected orders from 'Packaged' → 'Manifested' status.
    Only orders with internal_fulfillment_status='Packaged' are updated.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'operations_fulfillment:manifest_sheet:view'
    }

    def post(self, request):
        order_numbers = request.data.get('order_numbers', [])
        if not order_numbers or not isinstance(order_numbers, list):
            return Response({"error": "No order numbers provided."}, status=status.HTTP_400_BAD_REQUEST)

        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "No organization found."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            updated_count = Order.objects.filter(
                org_id=org_id,
                order_number__in=order_numbers,
                internal_fulfillment_status__in=['Packaged', 'Sent for Packaging']
            ).update(
                internal_fulfillment_status='Manifested',
                manifested_at=timezone.now()
            )

        return Response({
            "success": True,
            "manifested_count": updated_count,
            "requested_count": len(order_numbers),
        }, status=status.HTTP_200_OK)


class ManifestOrdersListView(APIView):
    """
    GET /api/orders/manifested-orders/
    Returns paginated orders with internal_fulfillment_status='Manifested'.
    These are orders that were pushed from the Packaging Sheet.

    Query params:
      - page (int, default 1)
      - limit (int, default 25)
      - search (str) — searches order_number, customer name
      - startDate (YYYY-MM-DD)
      - endDate (YYYY-MM-DD)
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:manifest_sheet:view'
    }

    def get(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "No organization found."}, status=status.HTTP_403_FORBIDDEN)

        queryset = Order.objects.filter(
            org_id=org_id,
            internal_fulfillment_status='Manifested'
        ).annotate(
            manifest_date=Coalesce('manifested_at', 'created_at')
        ).prefetch_related(
            Prefetch('fulfillments', queryset=Fulfillment.objects.prefetch_related('tracking_info'))
        )

        # Search
        search = request.query_params.get('search', '').strip()
        if search:
            search_q = Q()
            if search.isdigit():
                search_q |= Q(order_number=int(search))
            search_q |= Q(customer_first_name__icontains=search)
            search_q |= Q(customer_last_name__icontains=search)
            # Also search AWB via subquery
            awb_match = Fulfillment.objects.filter(
                order=OuterRef('pk'),
                tracking_info__number__icontains=search
            )
            search_q |= Exists(awb_match)
            queryset = queryset.filter(search_q)

        # Date filters (on manifest_date)
        start_date = request.query_params.get('startDate', '').strip()
        end_date = request.query_params.get('endDate', '').strip()
        if start_date:
            queryset = queryset.filter(manifest_date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(manifest_date__date__lte=end_date)

        queryset = queryset.order_by('-manifest_date')

        # Pagination
        page = max(1, int(request.query_params.get('page', 1)))
        limit = min(100, max(1, int(request.query_params.get('limit', 25))))
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)

        orders_data = []
        for order in page_obj:
            # Get first available tracking info
            tracking_info = None
            for f in order.fulfillments.all():
                ti_list = list(f.tracking_info.all())
                if ti_list:
                    tracking_info = ti_list[0]
                    break

            # Payment label
            pg_names = str(order.payment_gateway_names or '').lower()
            fin_status = (order.financial_status or '').lower()
            if 'cash_on_delivery' in pg_names or fin_status == 'pending':
                payment_label = 'COD'
            elif 'ppcod' in pg_names or fin_status == 'partially_paid':
                payment_label = 'PPCOD'
            else:
                payment_label = 'Prepaid'

            orders_data.append({
                'id': order.id,
                'order_number': order.order_number,
                'created_at': order.created_at,
                'manifested_at': order.manifested_at,
                'customer_name': f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip() or '-',
                'payment_label': payment_label,
                'total_price': str(order.total_price or '0'),
                'internal_fulfillment_status': order.internal_fulfillment_status,
                'courier': tracking_info.company if tracking_info else 'N/A',
                'awb': tracking_info.number if tracking_info else None,
                'awb_url': tracking_info.url if tracking_info else None,
                'current_status': order.current_status or 'Manifested',
                'current_status_date': order.current_status_date,
                'packaged_at': order.packaged_at,
            })

        from django.utils import timezone
        today = timezone.localtime().date()
        
        manifested_today = 0
        cod = 0
        ppcod = 0
        prepaid = 0
        total_amount = 0
        courier_map = {}
        seen_orders = set()

        kpi_qs = queryset.values(
            'id',
            'total_price',
            'payment_gateway_names',
            'financial_status',
            'manifest_date',
            'fulfillments__tracking_info__company'
        )

        for row in kpi_qs:
            order_id = row['id']
            if order_id in seen_orders:
                continue
            seen_orders.add(order_id)

            m_date = row['manifest_date']
            is_today = bool(m_date and m_date.date() == today)
            
            pg_names = str(row['payment_gateway_names'] or '').lower()
            fin_status = str(row['financial_status'] or '').lower()
            if 'cash_on_delivery' in pg_names or fin_status == 'pending':
                payment_label = 'COD'
            elif 'ppcod' in pg_names or fin_status == 'partially_paid':
                payment_label = 'PPCOD'
            else:
                payment_label = 'Prepaid'

            if is_today:
                manifested_today += 1
            
            if payment_label == 'COD':
                cod += 1
            elif payment_label == 'PPCOD':
                ppcod += 1
            else:
                prepaid += 1
            
            try:
                total_amount += float(row['total_price'] or 0)
            except:
                pass
            
            company = row['fulfillments__tracking_info__company'] or 'N/A'
            
            if company not in courier_map:
                courier_map[company] = {'company': company, 'total': 0, 'cod': 0, 'ppcod': 0, 'prepaid': 0}
            
            courier_map[company]['total'] += 1
            if payment_label == 'COD':
                courier_map[company]['cod'] += 1
            elif payment_label == 'PPCOD':
                courier_map[company]['ppcod'] += 1
            else:
                courier_map[company]['prepaid'] += 1

        rows = sorted(list(courier_map.values()), key=lambda x: x['total'], reverse=True)
        totals = {
            'total': sum(r['total'] for r in rows),
            'cod': sum(r['cod'] for r in rows),
            'ppcod': sum(r['ppcod'] for r in rows),
            'prepaid': sum(r['prepaid'] for r in rows),
        }

        return Response({
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page': page,
            'orders': orders_data,
            'manifestedKpis': {
                'total': paginator.count,
                'manifestedToday': manifested_today,
                'cod': cod,
                'ppcod': ppcod,
                'prepaid': prepaid,
                'totalAmount': total_amount
            },
            'shippingSummary': {
                'rows': rows,
                'totals': totals
            }
        }, status=status.HTTP_200_OK)

# ==============================================================================
