from django.utils import timezone
from datetime import timedelta, datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.db.models import Prefetch, Q, Sum, TextField, Count, F, Case, When, DecimalField, OuterRef, Prefetch, Exists, Value
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
import re

from django.core.cache import cache
from django.conf import settings as django_settings
from core.cache import CacheManager

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
    AWBBatchSerializer, LightweightConfirmedOrderSerializer
)

# --- Permissions ---
from core.permissions import (
    IsAllowedToCall, IsAllowedToBatch, IsPackagingAgent, 
    IsOrganizationOwner, IsAllowedCustomerExperience,
    HasModulePermission
)

User = get_user_model()




from .helpers import _get_org_id_or_none, _filter_orders_by_org_id, _clean_shopify_url
# 4. ORDER LIST & DETAIL VIEWS
# ==============================================================================

def _calculate_stats_for_date_isolated(request, target_date):
    base_queryset = Order.objects.filter(   
        status='Confirmed',
        confirmed_at__date=target_date
    )
    base_queryset = _filter_orders_by_org_id(request, base_queryset)
    
    payment_qs = get_payment_q_objects()
    aggs = base_queryset.aggregate(
        count=Count('id'),
        amount=Sum('total_price'),
        cod_count=Count('id', filter=payment_qs['cod']),
        cod_amount=Sum('total_price', filter=payment_qs['cod']),
        ppcod_count=Count('id', filter=payment_qs['partial']),
        ppcod_amount=Sum('total_price', filter=payment_qs['partial']),
        prepaid_count=Count('id', filter=payment_qs['prepaid']),
        prepaid_amount=Sum('total_price', filter=payment_qs['prepaid']),
    )
    return {
        'count': aggs['count'] or 0,
        'amount': aggs['amount'] or 0,
        'cod_count': aggs['cod_count'] or 0,
        'cod_amount': aggs['cod_amount'] or 0,
        'ppcod_count': aggs['ppcod_count'] or 0,
        'ppcod_amount': aggs['ppcod_amount'] or 0,
        'prepaid_count': aggs['prepaid_count'] or 0,
        'prepaid_amount': aggs['prepaid_amount'] or 0,
    }

@api_view(['GET'])
@permission_classes([HasModulePermission])
def confirmation_stats(request):
    """
    Returns statistics for orders FULFILLED (not just confirmed) on a given date.
    This is what the "Total Orders Fulfilled for the Day" box should display.
    """
    # Force GET mapping for @api_view
    request.required_permissions = {'GET': 'operations_fulfillment:confirmation:view'}
    date_str = request.query_params.get('date', None)
    target_date = None
    
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
    else:
        target_date = timezone.now().date()

    stats = _calculate_fulfillment_stats_for_date(request, target_date)
    
    if not date_str:
        # If no date provided, also return yesterday's for comparison if needed
        yesterday = target_date - timedelta(days=1)
        yesterday_stats = _calculate_fulfillment_stats_for_date(request, yesterday)
        return Response({
            'today_stats': stats,
            'yesterday_stats': yesterday_stats,
            'stats': stats # fallback
        })
    
    return Response({'stats': stats})


def _calculate_fulfillment_stats_for_date(request, target_date):
    """
    Calculates statistics based on the 'fulfilled_at' timestamp.
    """
    base_queryset = Order.objects.filter(   
        fulfilled_at__date=target_date
    )
    base_queryset = _filter_orders_by_org_id(request, base_queryset)
    
    payment_qs = get_payment_q_objects()
    aggs = base_queryset.aggregate(
        count=Count('id'),
        amount=Sum('total_price'),
        cod_count=Count('id', filter=payment_qs['cod']),
        cod_amount=Sum('total_price', filter=payment_qs['cod']),
        ppcod_count=Count('id', filter=payment_qs['partial']),
        ppcod_amount=Sum('total_price', filter=payment_qs['partial']),
        prepaid_count=Count('id', filter=payment_qs['prepaid']),
        prepaid_amount=Sum('total_price', filter=payment_qs['prepaid']),
    )
    return {
        'count': aggs['count'] or 0,
        'amount': float(aggs['amount'] or 0),
        'cod_count': aggs['cod_count'] or 0,
        'cod_amount': float(aggs['cod_amount'] or 0),
        'ppcod_count': aggs['ppcod_count'] or 0,
        'ppcod_amount': float(aggs['ppcod_amount'] or 0),
        'prepaid_count': aggs['prepaid_count'] or 0,
        'prepaid_amount': float(aggs['prepaid_amount'] or 0),
    }


class GetOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:confirmation:view', 'operations_fulfillment:awb_sheet:view']
    }
    def get(self, request):
        try:
            orders_qs = (
                Order.objects.all()
                .select_related('confirmed_by', 'packaged_by')
                .prefetch_related(
                    'line_items',
                    'case_files',
                    'packaging_images',
                    'fulfillments__tracking_info',
                    'fulfillments__tracking_events'
                )
                .order_by('-created_at')
            )
            orders_qs = _filter_orders_by_org_id(request, orders_qs)
            
            fulfillment_filter = request.query_params.get("fulfillment_status")
            if fulfillment_filter == "unfulfilled":
                orders_qs = orders_qs.filter(
                    Q(fulfillment_status__isnull=True) | Q(fulfillment_status='unfulfilled') | Q(status='Pending')
                ).exclude(fulfillment_status='fulfilled').exclude(fulfillment_status='partial')
            elif fulfillment_filter == "fulfilled":
                orders_qs = orders_qs.filter(fulfillment_status__in=['fulfilled', 'Tracking_added'])
            elif fulfillment_filter == "partial":
                orders_qs = orders_qs.filter(fulfillment_status='partial')

            serializer = OrderSerializer(orders_qs, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class PaginatedOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tz_name = request.headers.get('X-User-Timezone')
        default_tz = timezone.get_current_timezone()
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = default_tz

        try:
            page_number = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("limit", 50))
        except ValueError:
            page_number = 1
            page_size = 50

        search_query = request.query_params.get("search", "").strip()

        queryset = (
            Order.objects.all()
            .order_by("-created_at")
            .prefetch_related("line_items", "fulfillments__tracking_info")
            .annotate(created_at_local=TruncDate('created_at', tzinfo=user_tz))
        )
        
        queryset = _filter_orders_by_org_id(request, queryset)

def _apply_order_list_filters(request, queryset):
    start_date_str = request.query_params.get("startDate")
    end_date_str = request.query_params.get("endDate")
    
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(created_at_local__gte=start_date)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(created_at_local__lte=end_date)
    except ValueError:
        pass # Ignore invalid dates or handle upstream

    statuses = request.query_params.getlist("status")
    if statuses:
        queryset = queryset.filter(status__in=statuses)

    financial_statuses = request.query_params.getlist("financialStatus")
    if financial_statuses:
        queryset = queryset.filter(financial_status__in=financial_statuses)

    # --- SPECIAL FILTERS ---
    special_filter = request.query_params.get("specialFilter")
    if special_filter == "all_unfulfilled":
            # 1. Fulfillment Status is NULL, Empty, or 'Unfulfilled'
        q_unfulfilled = (
            Q(fulfillment_status__isnull=True) | 
            Q(fulfillment_status="") | 
            Q(fulfillment_status__iexact="unfulfilled")
        )
        
        # 2. Internal Status is NOT 'Packaged', 'Fulfilled', 'Cancelled', or 'Sent for Packaging'
        q_internal = (
            ~Q(internal_fulfillment_status__iexact="Packaged") & 
            ~Q(internal_fulfillment_status__iexact="Fulfilled") & 
            ~Q(internal_fulfillment_status__iexact="Cancelled") &
            ~Q(internal_fulfillment_status__iexact="Sent for Packaging")
        )

        # 3. Status is NOT 'Cancelled' AND NOT 'Confirmed'
        q_status = (
            ~Q(status__iexact="Cancelled") &
            ~Q(status__iexact="Confirmed")
        )

        queryset = queryset.filter(q_unfulfilled, q_internal, q_status)

    elif special_filter == "unfulfilled_confirmed":
        # 1. Fulfillment Status is Unfulfilled
        q_unfulfilled = (
            Q(fulfillment_status__isnull=True) | 
            Q(fulfillment_status="") | 
            Q(fulfillment_status__iexact="unfulfilled")
        )
        
        # 2. Status is 'Confirmed'
        q_confirmed = Q(status__iexact="Confirmed")

        # 3. Internal Status is NOT 'Packaged', 'Fulfilled', 'Cancelled', or 'Sent for Packaging'
        q_internal = (
            ~Q(internal_fulfillment_status__iexact="Packaged") & 
            ~Q(internal_fulfillment_status__iexact="Fulfilled") & 
            ~Q(internal_fulfillment_status__iexact="Cancelled") &
            ~Q(internal_fulfillment_status__iexact="Sent for Packaging")
        )

        queryset = queryset.filter(q_unfulfilled, q_confirmed, q_internal)

    elif special_filter == "tracking_added":
        queryset = queryset.filter(
            fulfillment_status__in=["Tracking_added", "fulfilled"],
            internal_fulfillment_status__iexact="Pending"
        ).exclude(
            status__iexact="Cancelled"
        )

    fulfillment_statuses = request.query_params.getlist("fulfillmentStatus")
    if fulfillment_statuses:
        q_fulfill = Q()
        f_set = set(fulfillment_statuses)
        if "unfulfilled" in f_set:
            f_set.remove("unfulfilled")
            q_fulfill |= Q(fulfillment_status__isnull=True) | Q(fulfillment_status="")
        if f_set:
            q_fulfill |= Q(fulfillment_status__in=list(f_set))
        queryset = queryset.filter(q_fulfill)

    payment_gateways = request.query_params.getlist("paymentGateway")
    if payment_gateways:
        q_gw = Q()
        for gw in payment_gateways:
            if gw == 'Razorpay PPCOD':
                q_gw |= Q(payment_gateway_names__icontains='Razorpay', financial_status__iexact='partially_paid')
            else:
                q_gw |= Q(payment_gateway_names__icontains=gw)
        queryset = queryset.filter(q_gw)

    delivery_partners = request.query_params.getlist("deliveryPartner")
    if delivery_partners:
        from core.models import Fulfillment
        queryset = queryset.filter(
            Exists(Fulfillment.objects.filter(
                order=OuterRef('pk'), 
                tracking_info__company__in=delivery_partners
            ))
        )

    shipment_statuses = request.query_params.getlist("shipmentStatus")
    if shipment_statuses:
        # Map user-friendly category names to DB value patterns (case-insensitive)
        SHIPMENT_STATUS_GROUPS = {
            "Shipment Booked":    ["Shipment Booked"],
            "AWB Assigned":       ["Awb_Assigned"],
            "Picked Up":          ["Picked Up", "Picked_Up", "Pkp"],
            "In Transit":         ["In Transit", "In_Transit", "INT", "in_transit"],
            "Out for Delivery":   ["Out for Delivery", "Out_For_Delivery", "OOD", "out_for_delivery"],
            "Delivered":          ["Delivered", "DEL", "DELIVERED", "delivered"],
            "Undelivered":        ["Undelivered", "UND", "UNDELIVERED", "Und", "attempted_delivery", "failure"],
            "RTO Initiated":      ["Rto Initiated", "Rto_Initiated"],
            "RTO In Transit":     ["RTO In Transit", "Rto_In_Transit", "RTO - In Transit", "RTO - In_Transit", "RTO IN TRANSIT"],
            "RTO Delivered":      ["Rto Delivered", "Rto_Delivered", "RTO - Delivered"],
            "Reached Destination": ["Reached At Destination", "Reached_At_Destination_Hub", "Rad"],
            "NDR":                ["Customer Refused", "Customer Not Available", "Customer Asked For Future Delivery",
                                   "Address Incorrect", "Entry Restricted Area", "Office/Residence Closed",
                                   "Delivery Attempted-Premises Closed", "Delivery Delayed", "Misrouted",
                                   "RTO - Customer Refused", "RTO - Entry Restricted Area", "No Pickup / Shipment Not Ready"],
            "OFP":                ["OFP", "Ofp", "Out_For_Pickup"],
            "Pending":            ["0"],
        }
        q_shipment = Q()
        for selected in shipment_statuses:
            db_values = SHIPMENT_STATUS_GROUPS.get(selected)
            if db_values:
                q_shipment |= Q(shipment_status__in=db_values)
            else:
                # Fallback: exact match for any status not in groups
                q_shipment |= Q(shipment_status__iexact=selected)
        
        from core.models import Fulfillment
        queryset = queryset.filter(
            Exists(Fulfillment.objects.filter(order=OuterRef('pk')).filter(q_shipment))
        )

    search_query = request.query_params.get("search", "").strip()
    if search_query:
        # --- Full-text search on PostgreSQL, icontains fallback on SQLite ---
        if getattr(django_settings, 'DB_IS_POSTGRES', False):
            try:
                from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
                # Build search vector on-the-fly (no stored column needed)
                sv = SearchVector('order_number', weight='A') + \
                     SearchVector('customer_first_name', weight='B') + \
                     SearchVector('customer_last_name', weight='B') + \
                     SearchVector('contact_email', weight='C') + \
                     SearchVector('contact_phone', weight='C')
                search = SearchQuery(search_query, search_type='websearch')
                queryset = queryset.annotate(
                    search=sv,
                    rank=SearchRank(sv, search)
                ).filter(
                    search=search
                ).order_by('-rank', '-created_at')
            except Exception:
                # Fallback if Postgres search fails for any reason
                from core.models import Fulfillment
                queryset = queryset.filter(
                    Q(order_number__icontains=search_query) |
                    Q(customer_first_name__icontains=search_query) |
                    Q(customer_last_name__icontains=search_query) |
                    Q(contact_email__icontains=search_query) |
                    Q(contact_phone__icontains=search_query) |
                    Exists(Fulfillment.objects.filter(order=OuterRef('pk'), tracking_info__number__icontains=search_query))
                )
        else:
            from core.models import Fulfillment
            queryset = queryset.filter(
                Q(order_number__icontains=search_query) |
                Q(customer_first_name__icontains=search_query) |
                Q(customer_last_name__icontains=search_query) |
                Q(contact_email__icontains=search_query) |
                Q(contact_phone__icontains=search_query) |
                Exists(Fulfillment.objects.filter(order=OuterRef('pk'), tracking_info__number__icontains=search_query))
            )

    # --- NEW: Stage Filter for Dashboard ---
    stage = request.query_params.get('stage')
    if stage:
        # Imported from utils at top of file
        queryset = get_queryset_for_stage(queryset, stage)
        
    return queryset

class PaginatedOrderListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:confirmation:view', 'operations_fulfillment:awb_sheet:view']
    }

    def get(self, request):
        tz_name = request.headers.get('X-User-Timezone')
        default_tz = timezone.get_current_timezone()
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = default_tz

        try:
            page_number = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("limit", 50))
        except ValueError:
            page_number = 1
            page_size = 50

        queryset = (
            Order.objects.all()
            .select_related('confirmed_by', 'packaged_by')
            .prefetch_related(
                "line_items",
                "case_files",
                "packaging_images",
                "fulfillments__tracking_info",
                "fulfillments__tracking_events"
            )
            .order_by("-created_at")
            .annotate(created_at_local=TruncDate('created_at', tzinfo=user_tz))
        )
        
        queryset = _filter_orders_by_org_id(request, queryset)
        queryset = _apply_order_list_filters(request, queryset)

        # --- CACHE CHECK ---
        org_id = _get_org_id_or_none(request)
        filters_dict = {
            'page': page_number,
            'limit': page_size,
            'params': dict(request.query_params),
        }
        cache_key = CacheManager.order_list_key(org_id or 'global', filters_dict)
        cached_response = cache.get(cache_key)
        special_filter = request.query_params.get("specialFilter")
        if cached_response and special_filter == "tracking_added":
            kpi_cached = cached_response.get("kpi", {})
            if "awb_analytics" not in kpi_cached:
                cached_response = None  # Force recalculation to bypass stale cache
        if cached_response:
            return Response(cached_response)

        # KPI Aggregation
        start_date_str = request.query_params.get("startDate")
        end_date_str = request.query_params.get("endDate")
        # Check if we have filters manually again for KPI optimization logic
        # OR just assume we prioritize correctness over slight perf optimization for now
        # The original code had an optimization to limit KPI to 'today' if no filters.
        # Let's preserve that logic.
        
        has_filters = any([
            start_date_str, end_date_str, 
            request.query_params.getlist("status"), 
            request.query_params.getlist("financialStatus"),
            request.query_params.get("specialFilter"), # Added this check
            request.query_params.getlist("fulfillmentStatus"), 
            request.query_params.getlist("paymentGateway"), 
            request.query_params.getlist("deliveryPartner"),
            request.query_params.getlist("shipmentStatus"), 
            request.query_params.get("search", "").strip()
        ])

        if not has_filters:
            now_in_user_tz = timezone.now().astimezone(user_tz)
            today_local = now_in_user_tz.date()
            queryset_for_kpi = queryset.filter(created_at_local=today_local)
        else:
            queryset_for_kpi = queryset

        payment_qs = get_payment_q_objects()
        payment_stats = queryset_for_kpi.aggregate(
            cod_qty=Count('id', filter=payment_qs['cod']),
            cod_amount=Sum('total_price', filter=payment_qs['cod']),
            ppcod_qty=Count('id', filter=payment_qs['partial']),
            ppcod_amount=Sum('total_price', filter=payment_qs['partial']),
            prepaid_qty=Count('id', filter=payment_qs['prepaid']),
            prepaid_amount=Sum('total_price', filter=payment_qs['prepaid']),
        )

        item_stats = queryset_for_kpi.aggregate(
            total_items=Sum("line_items__quantity")
        )

        orders_delivered = queryset_for_kpi.filter(
            fulfillments__shipment_status__iexact="delivered"
        ).distinct().count()

        kpi_data = {
            "orders_count": queryset_for_kpi.count(),
            "items_ordered": item_stats['total_items'] or 0,
            "orders_delivered": orders_delivered,
            "payment_breakdown": {
                "cod": { "qty": payment_stats['cod_qty'] or 0, "amount": payment_stats['cod_amount'] or 0 },
                "ppcod": { "qty": payment_stats['ppcod_qty'] or 0, "amount": payment_stats['ppcod_amount'] or 0 },
                "prepaid": { "qty": payment_stats['prepaid_qty'] or 0, "amount": payment_stats['prepaid_amount'] or 0 }
            }
        }

        special_filter = request.query_params.get("specialFilter")
        if special_filter == "tracking_added" and org_id:
            try:
                now_in_user_tz = timezone.now().astimezone(user_tz)
                today_local = now_in_user_tz.date()
                five_days_ago_local = today_local - timedelta(days=4)
                
                # Initialize daily statistics dict
                stats_by_date = {}
                for i in range(5):
                    d = today_local - timedelta(days=i)
                    stats_by_date[d] = {
                        "date": d.strftime("%Y-%m-%d"),
                        "awbs_generated": 0,
                        "fulfilled": 0,
                        "pending": 0,
                        "seen_orders": set()
                    }
                
                from core.models import Batch
                b_qs = Batch.objects.filter(
                    orders__org_id=org_id,
                    created_at__isnull=False
                ).annotate(
                    created_at_local=TruncDate('created_at', tzinfo=user_tz)
                ).filter(
                    created_at_local__range=[five_days_ago_local, today_local]
                ).prefetch_related('orders').distinct()
                
                for b in b_qs:
                    d = b.created_at_local
                    if d in stats_by_date:
                        for order in b.orders.all():
                            if order.org_id != org_id:
                                continue
                            order_id = order.id
                            if order_id not in stats_by_date[d]["seen_orders"]:
                                stats_by_date[d]["seen_orders"].add(order_id)
                                stats_by_date[d]["awbs_generated"] += 1
                                
                                status_lower = (order.internal_fulfillment_status or '').strip().lower()
                                is_fulfilled = status_lower in ['fulfilled', 'manifested', 'sent for packaging', 'packaged']
                                
                                if is_fulfilled:
                                    stats_by_date[d]["fulfilled"] += 1
                                elif order.status != 'Cancelled':
                                    stats_by_date[d]["pending"] += 1
                
                # Sort chronological: oldest to newest, extracting values to avoid serializing sets
                awb_analytics = []
                for i in range(4, -1, -1):
                    d = today_local - timedelta(days=i)
                    day_data = stats_by_date[d]
                    awb_analytics.append({
                        "date": day_data["date"],
                        "awbs_generated": day_data["awbs_generated"],
                        "fulfilled": day_data["fulfilled"],
                        "pending": day_data["pending"]
                    })
                kpi_data["awb_analytics"] = awb_analytics
            except Exception as e:
                logger.error(f"Error computing AWB 5-day analytics: {e}", exc_info=True)


        paginator = Paginator(queryset, page_size)
        if page_number > paginator.num_pages:
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except Exception:
            page_obj = paginator.page(1)

        serializer = OrderSerializer(page_obj.object_list, many=True)

        response_data = {
            "count": paginator.count,
            "orders": serializer.data,
            "kpi": kpi_data, 
            "num_pages": paginator.num_pages,
        }

        # --- STORE IN CACHE (5 min) ---
        cache.set(cache_key, response_data, CacheManager.MEDIUM)

        return Response(response_data)

class LogisticsAnalyticsView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:analytics:view'
    }

    def get(self, request):
        # 1. Date Filtering
        tz_name = request.headers.get('X-User-Timezone')
        default_tz = timezone.get_current_timezone()
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = default_tz

        org_id = _get_org_id_or_none(request)
        start_date_str = request.query_params.get("startDate")
        end_date_str = request.query_params.get("endDate")

        # --- CACHE CHECK ---
        filters_dict = {'start': start_date_str, 'end': end_date_str}
        cache_key = CacheManager.logistics_matrix_key(org_id or 'global', filters_dict)
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        queryset = _filter_orders_by_org_id(request, Order.objects.all())
        
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                queryset = queryset.annotate(
                    created_date=TruncDate('created_at', tzinfo=user_tz)
                ).filter(created_date__range=[start_date, end_date])
            except ValueError:
                pass # Ignore invalid dates
                
        # 2. Aggregation
        # We need counts for each Status x PaymentType
        # Frontend Statuses:
        # 'Shipment Booked', 'Shipment Pickedup', 'Intransit', 'Out for Delivery', 
        # 'Delivered', 'RTO initiated', 'RTO Delivered', 'Returns intransit', 'Returns Delivered'
        
        # We will utilize 'current_status' from the Order model which is updated by tracking events.
        # Mapping might be needed if ‘current_status’ doesn’t match exactly.
        # For now, we assume simple case-insensitive matching or ‘contains’.
        
        # Payment Types: Prepaid, PPCOD, COD
        
        # Let's perform a group by current_status
        # but since current_status values might be messy, let's do dictionary-based Mapping in Python 
        # OR robust conditional aggregation in SQL. SQL is better for performance.
        
        # Standardize Statuses for Aggregation
        # bucket matches frontend columns
        
        # Helper to build Q objects for payment types
        payment_qs = get_payment_q_objects()
        payment_q = {
            'COD': payment_qs['cod'],
            'PPCOD': payment_qs['partial'],
        }
        
        # Helper to build Q objects for Shipment Statuses
        # Note: These strings must match what shipway/tracking updates provide.
        status_buckets = {
            'Shipment Booked': ['booked', 'manifested'],
            'Shipment Pickedup': ['picked up', 'pickup'],
            'Intransit': ['intransit', 'in transit', 'dispatched'],
            'Out for Delivery': ['out for delivery'],
            'Delivered': ['delivered'],
            'RTO initiated': ['rto initiated', 'return initiated'],
            'RTO Delivered': ['rto delivered', 'return delivered'],
            'Returns intransit': ['return in transit', 'rto in transit'],
            'Returns Delivered': ['return delivered'] # often same as RTO delivered
        }
        
        # We will aggregate specifically for these buckets.
        aggregation_kwargs = {}
        
        for bucket, keywords in status_buckets.items():
            # Build Q for this status bucket
            status_q = Q()
            for kw in keywords:
                status_q |= Q(current_status__icontains=kw) | Q(fulfillments__shipment_status__icontains=kw)
            
            # Sanitize bucket name for alias (replace spaces with underscores)
            safe_bucket = bucket.replace(' ', '_')

            # 1. Total for this status
            # aggregation_kwargs[f'{bucket}__Total'] = Count('id', filter=status_q, distinct=True)
            
            # 2. COD for this status
            aggregation_kwargs[f'{safe_bucket}__COD'] = Count('id', filter=status_q & payment_q['COD'], distinct=True)
            
            # 3. PPCOD for this status
            aggregation_kwargs[f'{safe_bucket}__PPCOD'] = Count('id', filter=status_q & payment_q['PPCOD'], distinct=True)
            
            # 4. Prepaid for this status (Status AND NOT COD AND NOT PPCOD)
            aggregation_kwargs[f'{safe_bucket}__Prepaid'] = Count('id', filter=status_q & ~payment_q['COD'] & ~payment_q['PPCOD'], distinct=True)

        # Run one big aggregation
        results = queryset.aggregate(**aggregation_kwargs)
        
        # Format for Frontend:
        # { 'Prepaid': {'Shipment Booked': 5, ...}, 'COD': {...}, 'PPCOD': {...}, 'Total': {...} }
        
        response_data = {
            'Prepaid': {},
            'PPCOD': {},
            'COD': {},
            'Total': {}
        }
        
        for bucket in status_buckets.keys():
            safe_bucket = bucket.replace(' ', '_')
            
            cod = results.get(f'{safe_bucket}__COD', 0)
            ppcod = results.get(f'{safe_bucket}__PPCOD', 0)
            prepaid = results.get(f'{safe_bucket}__Prepaid', 0)
            total = cod + ppcod + prepaid
            
            response_data['COD'][bucket] = cod
            response_data['PPCOD'][bucket] = ppcod
            response_data['Prepaid'][bucket] = prepaid
            response_data['Total'][bucket] = total

        # --- STORE IN CACHE (1 hour) ---
        cache.set(cache_key, response_data, CacheManager.LONG)

        return Response(response_data)

class PicklistAggregationView(APIView):
    permission_classes = [IsPackagingAgent]

    def post(self, request):
        # 1. Base Queryset
        # We need created_at_local if we are applying filters that depend on it.
        # However, _apply_order_list_filters expects it.
        tz_name = request.headers.get('X-User-Timezone')
        default_tz = timezone.get_current_timezone()
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            user_tz = default_tz
            
        queryset = (
            Order.objects.all()
            .annotate(created_at_local=TruncDate('created_at', tzinfo=user_tz))
        )
        queryset = _filter_orders_by_org_id(request, queryset)
        
        # 2. Filter Logic
        limit_ids = request.data.get('ids', None) # List of Order Numbers or IDs? Order Numbers based on frontend.
        
        if limit_ids and isinstance(limit_ids, list) and len(limit_ids) > 0:
            # Manual Mode: Filter by specific IDs
            # Frontend sends 'ids' which matches 'order_number' usually
            queryset = queryset.filter(order_number__in=limit_ids)
        else:
            # Global Mode: Apply filters from query params
            # NOTE: For global mode, we assume the frontend attaches the filter params 
            # to the URL (even for POST) OR we should look in request.data.
            # _apply_order_list_filters looks at request.query_params.
            queryset = _apply_order_list_filters(request, queryset)

        # 3. Aggregation Logic
        # Items: Group by SKU
        items = (
            queryset
            .values('line_items__sku', 'line_items__title')
            .annotate(totalQuantity=Sum('line_items__quantity'))
            .filter(totalQuantity__gt=0)
            .order_by('line_items__sku')
        )
        
        # Summary: Payment Counts
        payment_qs = get_payment_q_objects()
        payment_stats = queryset.aggregate(
            cod=Count('id', filter=payment_qs['cod']),
            ppcod=Count('id', filter=payment_qs['partial']),
            prepaid=Count('id', filter=payment_qs['prepaid']),
        )
        
        total_count = queryset.count()
        cod_count = payment_stats['cod']
        ppcod_count = payment_stats['ppcod']
        prepaid_count = payment_stats['prepaid']
        
        # Format for frontend
        formatted_items = [
            {
                'sku': item['line_items__sku'] or 'NO-SKU',
                'title': item['line_items__title'],
                'totalQuantity': item['totalQuantity']
            }
            for item in items
        ]
        
        summary = {
            'total': total_count,
            'cod': cod_count,
            'ppcod': ppcod_count,
            'prepaid': prepaid_count
        }
        
        return Response({
            'items': formatted_items,
            'summary': summary
        })


class GetUnfulfilledOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:calling_sheet:view', 'operations_fulfillment:confirmation:view']
    }

    def get(self, request):
        queryset = Order.objects.unfulfilled().exclude(
            financial_status__in=['voided', 'refunded']
        ).order_by('-created_at')
        queryset = _filter_orders_by_org_id(request, queryset)

        # --- Filters ---
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        search = request.query_params.get('search', '').strip()
        payment = request.query_params.get('payment', '').strip()
        risk = request.query_params.get('risk', '').strip()
        order_status = request.query_params.get('status', '').strip()

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(customer_first_name__icontains=search) |
                Q(customer_last_name__icontains=search) |
                Q(contact_phone__icontains=search)
            )
        if payment == 'COD':
            queryset = queryset.filter(financial_status='pending')
        elif payment == 'PPCOD':
            queryset = queryset.filter(financial_status='partially_paid')
        elif payment == 'Prepaid':
            queryset = queryset.exclude(financial_status__in=['pending', 'partially_paid'])
        if risk:
            queryset = queryset.filter(risk_status=risk)
        if order_status:
            queryset = queryset.filter(status=order_status)

        # --- Pagination ---
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 100)), 200)  # max 200 per page
        total_count = queryset.count()

        start = (page - 1) * page_size
        end = start + page_size
        page_qs = (
            queryset[start:end]
            .select_related('confirmed_by', 'packaged_by')
            .prefetch_related(
                'line_items',
                'case_files',
                'packaging_images',
                'fulfillments__tracking_info',
                'fulfillments__tracking_events'
            )
        )

        serializer = OrderSerializer(page_qs, many=True)
        return Response({
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "results": serializer.data,
        })


class UpdateOrderView(RetrieveUpdateAPIView):
    permission_classes = [HasModulePermission] 
    required_permissions = {
        'PATCH': ['operations_fulfillment:orders:edit', 'operations_fulfillment:confirmation:edit', 'operations_fulfillment:awb_sheet:edit', 'operations_fulfillment:calling_sheet:edit'],
        'PUT': ['operations_fulfillment:orders:edit', 'operations_fulfillment:confirmation:edit', 'operations_fulfillment:awb_sheet:edit', 'operations_fulfillment:calling_sheet:edit'],
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:confirmation:view', 'operations_fulfillment:awb_sheet:view', 'operations_fulfillment:calling_sheet:view']
    }
    serializer_class = OrderSerializer
    lookup_field = 'order_number'

    def get_queryset(self):
        queryset = Order.objects.all()
        return _filter_orders_by_org_id(self.request, queryset)

    def perform_update(self, serializer):
        new_internal_status = serializer.validated_data.get('internal_fulfillment_status')
        
        # 1. Handle Fulfillment
        if new_internal_status == 'Fulfilled':
            serializer.instance.internal_fulfillment_status = 'Fulfilled'
            if not serializer.instance.fulfilled_at:
                serializer.instance.fulfilled_at = timezone.now()
            if 'fulfillment_reason' in serializer.validated_data:
                serializer.instance.fulfillment_reason = ""
        elif new_internal_status == 'Pending':
            # Reset fulfillment time if moved back to pending
            serializer.instance.fulfilled_at = None
        
        # 2. Handle Status Changes (Confirm vs Reset)
        # This block now handles both marking as Confirmed AND resetting to Pending
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            
            if new_status == 'Confirmed':
                # Set time if not already set
                if not serializer.instance.confirmed_at: 
                    serializer.instance.confirmed_at = timezone.now()
                
                # Capture the user who confirmed
                if self.request.user.is_authenticated:
                    serializer.instance.confirmed_by = self.request.user
            
            elif new_status == 'Pending':
                # >>> RESET CONFIRMATION DETAILS <<<
                # If moved back to pending, clear who confirmed it
                serializer.instance.confirmed_at = None
                serializer.instance.confirmed_by = None
        
        # 3. Handle Call Logging
        new_call_log = self.request.data.get('new_call_log')
        
        if new_call_log:
            current_attempts = serializer.instance.call_attempts or 0
            serializer.instance.call_attempts = current_attempts + 1
            serializer.instance.last_called_at = timezone.now()
            
            history = serializer.instance.call_history or []
            if not isinstance(history, list): history = []
                
            user_name = self.request.user.username if self.request.user.is_authenticated else 'System'
            
            history.append({
                "remark": new_call_log.get('remark', 'No remark'),
                "timestamp": timezone.now().isoformat(),
                "user": user_name
            })
            
            serializer.instance.call_history = history

        elif 'call_attempts' in serializer.validated_data:
            serializer.instance.last_called_at = timezone.now()
            
        # 4. Handle Packaging
        if new_internal_status == 'Packaged':
            if self.request.user.is_authenticated: 
                serializer.instance.packaged_by = self.request.user
            serializer.instance.packaged_at = timezone.now()
        
        # 4.5. Handle Manifesting
        if new_internal_status == 'Manifested':
            serializer.instance.manifested_at = timezone.now()
        elif new_internal_status in ['Pending', 'Sent for Packaging', 'Packaged']:
            serializer.instance.manifested_at = None
            
        # 5. Handle Holding
        if new_internal_status == 'On Hold':
            reason = self.request.data.get('hold_reason')
            batch_id = self.request.data.get('batch_id')
            if reason and batch_id:
                history = serializer.instance.hold_history or []
                if not isinstance(history, list): history = []
                
                history.append({
                    'reason': reason, 
                    'batch_id': batch_id, 
                    'timestamp': timezone.now().isoformat(), 
                    'user': self.request.user.username if self.request.user.is_authenticated else 'system'
                })
                serializer.instance.hold_history = history
        
        # 6. Special Flag
        if self.request.data.get('resolve_and_fulfill'):
            serializer.instance.internal_fulfillment_status = 'Fulfilled'
            
        serializer.save()

class BulkScanActionView(APIView):
    """
    Optimized endpoint for bulk scanning AWBs and updating order fulfillment statuses.
    Accepts: { awbs: ["Awb1", "Order1"], action: "fulfill" | "revert" }
    """
    permission_classes = [HasModulePermission] 
    required_permissions = {
        'POST': ['operations_fulfillment:confirmation:create', 'operations_fulfillment:orders:edit', 'operations_fulfillment:awb_sheet:create']
    }
    def post(self, request, *args, **kwargs):
        org_id = _get_org_id_or_none(request)
        if not org_id:
             return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)
        
        awbs = request.data.get('awbs', [])
        action = request.data.get('action', 'fulfill') # 'fulfill' or 'revert'
        
        if not awbs or not isinstance(awbs, list):
            return Response({"error": "Please provide a list of awbs."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Clean awbs list
        clean_awbs = [str(a).strip() for a in awbs if str(a).strip()]
        if not clean_awbs:
            return Response({"error": "No valid AWBs found."}, status=status.HTTP_400_BAD_REQUEST)

        # ── OPTIMIZATION: Split lookup into two fast steps ──
        # Step 1: Fast indexed lookup by order_number (uses idx_ord_org_ordernum)
        # Try to parse as integers for order_number match (order_number is IntegerField)
        numeric_awbs = []
        non_numeric_awbs = []
        for awb in clean_awbs:
            try:
                numeric_awbs.append(int(awb))
            except (ValueError, TypeError):
                non_numeric_awbs.append(awb)

        # Only fetch columns needed for the response — skip heavy JSON blobs
        slim_fields = [
            'id', 'order_number', 'customer_first_name', 'customer_last_name',
            'internal_fulfillment_status', 'fulfillment_reason',
            'payment_gateway_names', 'total_price', 'org_id',
        ]

        matched_orders = {}

        if numeric_awbs:
            for order in (
                Order.objects.filter(org_id=org_id, order_number__in=numeric_awbs)
                .only(*slim_fields)
                .prefetch_related('line_items', 'fulfillments__tracking_info')
            ):
                matched_orders[order.pk] = order

        # Step 2: Only join TrackingInfo for AWBs that didn't match as order_number
        remaining_awbs = non_numeric_awbs + [
            str(n) for n in numeric_awbs
            if not any(o.order_number == n for o in matched_orders.values())
        ]

        if remaining_awbs:
            for order in (
                Order.objects.filter(
                    org_id=org_id,
                    fulfillments__tracking_info__number__in=remaining_awbs
                )
                .only(*slim_fields)
                .prefetch_related('line_items', 'fulfillments__tracking_info')
            ):
                matched_orders[order.pk] = order

        matching_orders = list(matched_orders.values())
        
        found_awbs_or_orders = set()
        orders_to_update = []
        response_orders = []
        already_scanned = []

        # States that mean the order has already been processed past the initial pending state
        already_processed_states = ['Fulfilled', 'Sent for Packaging', 'Packaged']
        revert_to_statuses = request.data.get('revert_to_statuses', {})

        for order in matching_orders:
            # Track matched AWBs: add order_number as string and all AWB tracking numbers
            found_awbs_or_orders.add(str(order.order_number))
            tracking_number = "N/A"
            for f in order.fulfillments.all():
                for t in f.tracking_info.all():  # .all() because it's a RelatedManager
                    found_awbs_or_orders.add(t.number or '')  # .number is a field, not .get()
                    if tracking_number == "N/A" and t.number:
                        tracking_number = t.number

            # If action is fulfill, and order is already fulfilled or beyond, skip it
            if action == 'fulfill' and order.internal_fulfillment_status in already_processed_states:
                already_scanned.append({
                    "order_number": order.order_number,
                    "awb_number": tracking_number,
                    "status": order.internal_fulfillment_status,
                    "message": f"Already processed ({order.internal_fulfillment_status})"
                })
                continue

            orders_to_update.append(order.order_number)

            # Determine internal status for the response
            if action == 'fulfill':
                target_status = 'Fulfilled'
            else:
                target_status = revert_to_statuses.get(str(order.order_number), {}).get('status', 'Pending')
                target_reason = revert_to_statuses.get(str(order.order_number), {}).get('reason', '')

            response_orders.append({
                "order_number": order.order_number,
                "customer_first_name": order.customer_first_name,
                "customer_last_name": order.customer_last_name,
                "line_items": [{"title": item.title, "quantity": item.quantity, "sku": item.sku} for item in order.line_items.all()],
                "tracking_number": tracking_number,
                "awb_number": tracking_number,
                "internal_fulfillment_status": target_status,
                "fulfillment_reason": "" if action == 'fulfill' else target_reason,
                "payment_gateway_names": order.payment_gateway_names,
                "total_price": str(order.total_price),
            })

        not_found = [awb for awb in clean_awbs if awb not in found_awbs_or_orders]

        if orders_to_update:
            if action == 'fulfill':
                Order.objects.filter(order_number__in=orders_to_update, org_id=org_id).update(
                    internal_fulfillment_status='Fulfilled',
                    fulfillment_reason="",
                    fulfilled_at=timezone.now()
                )
            elif action == 'revert':
                # If we have specific target statuses, we update in a more granular way
                if revert_to_statuses:
                    from django.db.models import Case, When, Value, CharField
                    # Filter to only the orders we're actually updating
                    qs = Order.objects.filter(order_number__in=orders_to_update, org_id=org_id)
                    
                    status_cases = []
                    reason_cases = []
                    for on, state in revert_to_statuses.items():
                        try:
                            order_num_val = int(on)
                        except (ValueError, TypeError):
                            order_num_val = on
                        status_cases.append(When(order_number=order_num_val, then=Value(state.get('status', 'Pending'))))
                        reason_cases.append(When(order_number=order_num_val, then=Value(state.get('reason', ''))))


                    update_kwargs = {
                        'internal_fulfillment_status': Case(*status_cases, default=Value('Pending'), output_field=CharField()),
                        'fulfillment_reason': Case(*reason_cases, default=Value(''), output_field=CharField()),
                        'fulfilled_at': None,
                        'manifested_at': None
                    }
                    qs.update(**update_kwargs)
                else:
                    Order.objects.filter(order_number__in=orders_to_update, org_id=org_id).update(
                        internal_fulfillment_status='Pending',
                        fulfillment_reason="",
                        fulfilled_at=None,
                        manifested_at=None
                    )

        return Response({
            "success": True,
            "updated_count": len(orders_to_update),
            "updated_orders": response_orders,
            "already_scanned": already_scanned,
            "not_found": not_found
        }, status=status.HTTP_200_OK)

class ConfirmedOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:awb_sheet:view']
    }
    def get(self, request):
        from datetime import timedelta
        # Extended cutoff to 90 days so older orders (e.g. Feb) still show up when confirmed
        cutoff = timezone.now() - timedelta(days=90)
        orders = Order.objects.filter(
            status='Confirmed',
            created_at__gte=cutoff,
        ).exclude(
            financial_status__in=['voided', 'refunded']
        ).order_by('-created_at')
        orders = _filter_orders_by_org_id(request, orders)
        # Hard cap to avoid SQLite's 999 variable limit in prefetch IN clauses
        orders = orders[:400].prefetch_related('fulfillments__tracking_info')
        serializer = LightweightConfirmedOrderSerializer(orders, many=True)
        return Response(serializer.data)


class ReadyForProductionView(ListAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:orders:view'
    }
    serializer_class = OrderSerializer
    def get_queryset(self):
        queryset = (
            Order.objects.filter(status='Confirmed', fulfillments__isnull=False)
            .distinct()
            .select_related('confirmed_by', 'packaged_by')
            .prefetch_related(
                'line_items',
                'case_files',
                'packaging_images',
                'fulfillments__tracking_info',
                'fulfillments__tracking_events'
            )
            .order_by('-confirmed_at')
        )
        return _filter_orders_by_org_id(self.request, queryset)


class AllOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:confirmation:view', 'operations_fulfillment:awb_sheet:view']
    }
    def get(self, request, format=None):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "No valid shop context found."}, status=400)
            
        # --- CACHE CHECK ---
        cache_key = CacheManager.overview_key(org_id)
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        base_qs = Order.objects.select_related('confirmed_by', 'packaged_by').prefetch_related(
            'line_items',
            'case_files',
            'packaging_images',
            'fulfillments__tracking_info',
            'fulfillments__tracking_events'
        )
        
        base_qs = _filter_orders_by_org_id(request, base_qs)

        pending_confirmation = base_qs.filter(
            status='Pending'
        ).exclude(
            Q(fulfillment_status='fulfilled') | Q(fulfillment_status='partial')
        ).order_by('-created_at')

        pending_awb = base_qs.filter(
            status='Confirmed', 
            fulfillments__isnull=True
        ).order_by('-created_at')

        pending_fulfillment = base_qs.filter(
            status='Batched', 
            internal_fulfillment_status='Pending'
        ).order_by('-created_at')

        pending_packaging = base_qs.filter(
            internal_fulfillment_status='Sent for Packaging'
        ).order_by('-created_at')

        on_hold_orders = base_qs.filter(
            internal_fulfillment_status='On Hold'
        ).order_by('-updated_at')
        
        pending_manifest = base_qs.annotate(
            f_count=Count('fulfillments')
        ).filter(
            f_count=1,                        
            fulfillments__shipment_status='0' 
        ).order_by('-created_at')

        data = {
            'pending_confirmation': OrderSerializer(pending_confirmation, many=True).data,
            'pending_awb': OrderSerializer(pending_awb, many=True).data,
            'pending_fulfillment': OrderSerializer(pending_fulfillment, many=True).data,
            'pending_packaging': OrderSerializer(pending_packaging, many=True).data,
            'pending_manifest': OrderSerializer(pending_manifest, many=True).data, 
            'on_hold_orders': OrderSerializer(on_hold_orders, many=True).data,
        }
        
        # --- STORE IN CACHE (5 minutes) ---
        cache.set(cache_key, data, CacheManager.MEDIUM)

        return Response(data)

# ... [Pending Orders View - skipped as unchanged logic] ...

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 100

class PaginatedPendingOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:pending_orders:view'
    }
    def get(self, request):
        # --- 1. Resolve Organization ID ---
        try:
            org_id = request.user.shop_credentials.organization_id
        except AttributeError:
            if hasattr(request.user, 'team_settings') and request.user.team_settings.organization:
                org_id = request.user.team_settings.organization.organization_id
            else:
                return Response({"results": [], "count": 0}, status=200)

        # --- 2. Base Query (No Joins yet) ---
        queryset = Order.objects.filter(org_id=org_id)

        # --- 3. OPTIMIZATION: Prepare Subqueries ---
        # Instead of joining the Fulfillment table (which explodes rows), 
        # we prepare lightweight subqueries to check for existence.
        
        # Checks if ANY fulfillment exists (replaces num_fulfillments > 0)
        has_any_fulfillment = Fulfillment.objects.filter(order=OuterRef('pk'))

        # Checks if a specific 'Pending Manifest' fulfillment exists
        has_pending_manifest_fulfillment = Fulfillment.objects.filter(
            order=OuterRef('pk'),
            shipment_status='0'
        )

        # --- 4. Apply Logic Filters ---
        status_types = request.query_params.getlist('status_type')
        if not status_types:
            status_types = [
                'Pending Confirmation', 'Pending AWB', 'Pending Fulfillment', 
                'Pending Packaging', 'Pending Manifest', 'On Hold'
            ]

        status_q = Q()

        if 'Pending Confirmation' in status_types:
            status_q |= (
                Q(status='Pending') & 
                ~Q(fulfillment_status__iexact='fulfilled')
            )

        if 'Pending AWB' in status_types:
            # Logic: Confirmed AND No Fulfillments
            # Optimized: Use ~Exists instead of num_fulfillments=0
            status_q |= (
                Q(status='Confirmed') & 
                ~Exists(has_any_fulfillment)
            )

        if 'Pending Fulfillment' in status_types:
            # Logic: Batched AND Pending Internal AND No Fulfillments
            status_q |= (
                Q(status='Batched') & 
                Q(internal_fulfillment_status='Pending') & 
                ~Exists(has_any_fulfillment)
            )

        if 'Pending Packaging' in status_types:
            status_q |= Q(internal_fulfillment_status='Sent for Packaging')

        if 'On Hold' in status_types:
            status_q |= Q(internal_fulfillment_status='On Hold')

        if 'Pending Manifest' in status_types:
            # Logic: Has fulfillment AND status is '0'
            # Optimized: Use Exists on the specific condition
            status_q |= Exists(has_pending_manifest_fulfillment)

        if status_q:
            queryset = queryset.filter(status_q)

        # --- 5. Annotate with Overview Status ---
        queryset = queryset.annotate(
            overview_status=Case(
                When(Exists(has_pending_manifest_fulfillment), then=Value('Pending Manifest')),
                When(internal_fulfillment_status='Sent for Packaging', then=Value('Pending Packaging')),
                When(internal_fulfillment_status='On Hold', then=Value('On Hold')),
                When(status='Pending', then=Value('Pending Confirmation')),
                When(status='Confirmed', then=Value('Pending AWB')),
                When(status='Batched', internal_fulfillment_status='Pending', then=Value('Pending Fulfillment')),
                default=Value('Pending'),
                output_field=models.CharField(),
            )
        )

        # --- 6. Search Logic (Local Columns Only) ---
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(order_number__icontains=search_query) |
                Q(customer_first_name__icontains=search_query) |
                Q(customer_last_name__icontains=search_query) |
                Q(contact_email__icontains=search_query) |
                Q(contact_phone__icontains=search_query)
            )

        # --- 6. Sorting & Prefetching ---
        # Note: .distinct() is REMOVED because we used Exists() instead of Joins.
        queryset = queryset.order_by('-created_at')

        # Apply strict prefetching to avoid N+1 queries in the robust OrderSerializer
        queryset = queryset.prefetch_related(
            'line_items',    
            'fulfillments__tracking_info',
            'fulfillments__tracking_events',
            'case_files',
            'packaging_images'
        ).select_related('confirmed_by', 'packaged_by')

        # --- 7. Pagination ---
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data)

# ==============================================================================


def find_shopify_order_by_number(order_number, shop_url, api_version, headers, auth_method=None, api_key=None, password=None):
    """
    Robust helper to search Shopify API for an order by its name/number.
    """
    search_queries = [
        str(order_number),
        f"#{order_number}" if not str(order_number).startswith("#") else str(order_number),
        str(order_number).replace("#", "") if str(order_number).startswith("#") else str(order_number)
    ]
    search_queries = list(dict.fromkeys(search_queries))
    
    # Try exact name matching first
    for query in search_queries:
        if auth_method == 'oauth' and headers:
            api_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&name={query}"
            response = requests.get(api_url, headers=headers, timeout=10)
        else:
            legacy_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders.json?status=any&name={query}"
            response = requests.get(legacy_url, timeout=10)
            
        if response.ok:
            orders = response.json().get('orders', [])
            if orders:
                return orders[0]
                
    # Fallback to general query search
    for query in search_queries:
        if auth_method == 'oauth' and headers:
            api_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&query=name:{query}"
            response = requests.get(api_url, headers=headers, timeout=10)
        else:
            legacy_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders.json?status=any&query=name:{query}"
            response = requests.get(legacy_url, timeout=10)
            
        if response.ok:
            orders = response.json().get('orders', [])
            if orders:
                return orders[0]
                
    return None


def save_shopify_order_payload(api_order, org_id):
    customer_data = api_order.get('customer') or {}
    shipping_address = api_order.get('shipping_address')
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
    # Calculate previous order count
    prev_count = 0
    p_email = (customer_data.get('email') or '').strip().lower()
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
        prev_count = Order.objects.filter(
            q_filter,
            org_id=org_id,
            created_at__lt=api_order.get('created_at')
        ).count()

    order_obj.previous_order_count = prev_count
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

    # SAFE line item sync: only delete+recreate if Shopify returns a non-empty list.
    # Shopify can return line_items=[] for orders with restricted/missing product scopes,
    # which would permanently wipe all items from the order.
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
                name=item.get('name')
            )
            for item in incoming_line_items
        ]
        LineItem.objects.bulk_create(line_items_to_create)
    else:
        existing_count = order_obj.line_items.count()
        import logging as _logging
        _logging.getLogger(__name__).warning(
            f"save_shopify_order_payload: Shopify returned 0 line_items for order "
            f"#{api_order.get('order_number')} (org={org_id}). "
            f"Keeping existing {existing_count} item(s) to prevent data loss."
        )

    # Process fulfillments
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

    # Post-onboarding defaults
    if created and order_obj.financial_status != 'voided':
        order_obj.status = 'Pending'
        order_obj.internal_fulfillment_status = 'Pending'
        order_obj.save()

    return order_obj


class SyncOrderView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:orders:edit', 'operations_fulfillment:confirmation:edit']
    }

    def post(self, request):
        # 1. Get org context
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)

        # 2. Get shop credentials
        creds = _get_decrypted_credentials(org_id)
        if not creds:
            return Response({"error": "Shop credentials not found or invalid."}, status=status.HTTP_404_NOT_FOUND)

        shop_url = creds.get('shop_url')
        api_key = creds.get('api_key')
        password = creds.get('password')
        access_token = creds.get('access_token')
        api_version = creds.get('api_version', '2024-07')
        auth_method = creds.get('auth_method')

        headers = None
        if auth_method == 'oauth' and access_token:
            headers = {"X-Shopify-Access-Token": access_token}

        # 3. Check for timeframe sync vs single sync
        timeframe = request.data.get('timeframe')
        identifier = request.data.get('identifier', '').strip()

        if not timeframe and not identifier:
            return Response({"error": "Either identifier or timeframe is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Cache clear helper
        def clear_kpi_cache():
            try:
                cache.clear()
            except Exception:
                pass

        if timeframe:
            # Timeframe Sync Mode
            timeframe = str(timeframe).lower()
            if timeframe == 'today':
                # Sync orders created in the last 24 hours (or start of today)
                created_at_min = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif timeframe == '1_week':
                created_at_min = (timezone.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif timeframe == '15_days':
                created_at_min = (timezone.now() - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif timeframe == '1_month':
                created_at_min = (timezone.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif timeframe == '2_months':
                created_at_min = (timezone.now() - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                return Response({"error": f"Invalid timeframe: '{timeframe}'"}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch orders since timeframe min
            if auth_method == 'oauth' and access_token:
                next_url = f"https://{shop_url}/admin/api/{api_version}/orders.json?status=any&limit=250&created_at_min={created_at_min}"
            else:
                next_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders.json?status=any&limit=250&created_at_min={created_at_min}"
            
            synced_count = 0
            skipped_count = 0
            
            def get_next_url(link_header):
                if not link_header:
                    return None
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        raw_url = link.split(";")[0].strip(" <>")
                        if auth_method != 'oauth' and api_key and password:
                            raw_url = raw_url.replace(f"https://{shop_url}", f"https://{api_key}:{password}@{shop_url}")
                        return raw_url
                return None

            while next_url:
                if auth_method == 'oauth' and access_token:
                    response = requests.get(next_url, headers=headers, timeout=15)
                else:
                    response = requests.get(next_url, timeout=15)
                    
                if not response.ok:
                    break
                    
                api_orders = response.json().get('orders', [])
                for api_order in api_orders:
                    shopify_id = api_order['id']

                    # 1. Check if order already exists
                    existing_order = Order.objects.filter(shopify_id=shopify_id, org_id=org_id).first()
                    if existing_order:
                        # Re-sync if line items are missing (0 items = broken order from past bug)
                        if existing_order.line_items.count() == 0:
                            logger.info(f"Re-syncing order #{existing_order.order_number} — found 0 line items.")
                        else:
                            skipped_count += 1
                            continue  # Has items already, skip

                    # 2. Save (or re-save) order
                    try:
                        order = save_shopify_order_payload(api_order, org_id)
                        synced_count += 1

                        # Try synchronous Shipway PII fetch if not already populated and not skipped
                        has_pii = bool(order.customer_first_name and order.contact_phone and order.shipping_address)
                        skip_sync = creds.get('skip_shipway_pii_sync', False)
                        pii_fetched = False
                        if has_pii or skip_sync:
                            pii_fetched = True
                        else:
                            try:
                                from core.tasks.shipway_sync import fetch_missing_pii_task
                                fetch_missing_pii_task(order.id, org_id)
                                order.refresh_from_db()
                                if order.contact_phone or order.customer_first_name:
                                    pii_fetched = True
                            except Exception as pii_err:
                                logger.error(f"Error fetching PII for #{order.order_number}: {pii_err}")

                        # 3. Fallback: if fetch failed, schedule task in background
                        if not pii_fetched:
                            from django_q.tasks import schedule
                            schedule(
                                'core.tasks.fetch_missing_pii_task',
                                order.id,
                                org_id,
                                1,
                                next_run=timezone.now() + timedelta(minutes=4)
                            )
                    except Exception as save_err:
                        logger.error(f"Error saving order {shopify_id}: {save_err}")
                
                # Move to next page
                link_header = response.headers.get("Link")
                next_url = get_next_url(link_header) if link_header else None

            clear_kpi_cache()
            return Response({
                "message": f"Sync complete! Synced {synced_count} new orders. Skipped {skipped_count} existing orders.",
                "synced_count": synced_count,
                "skipped_count": skipped_count
            }, status=status.HTTP_200_OK)

        else:
            # Single Sync Mode
            shopify_order_id = None
            if identifier.isdigit() and len(identifier) >= 11:
                shopify_order_id = identifier
            else:
                # Search Shopify by Order Number
                api_order = find_shopify_order_by_number(
                    identifier, shop_url, api_version, headers,
                    auth_method, api_key, password
                )
                if not api_order:
                    return Response({"error": f"Order with number '{identifier}' not found on Shopify."}, status=status.HTTP_404_NOT_FOUND)
                shopify_order_id = str(api_order['id'])

            # Always re-fetch from Shopify API so line items and other data are refreshed.
            # (Orders that already exist but had items wiped must be re-synced.)
            if auth_method == 'oauth' and access_token:
                api_resp = requests.get(
                    f"https://{shop_url}/admin/api/{api_version}/orders/{shopify_order_id}.json",
                    headers=headers, timeout=15
                )
            else:
                api_resp = requests.get(
                    f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}/orders/{shopify_order_id}.json",
                    timeout=15
                )

            if not api_resp.ok:
                return Response({"error": f"Shopify API returned {api_resp.status_code} for order {shopify_order_id}."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            api_order_data = api_resp.json().get('order')
            if not api_order_data:
                return Response({"error": "Shopify returned an empty order payload."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            already_existed = Order.objects.filter(shopify_id=shopify_order_id, org_id=org_id).exists()
            order = save_shopify_order_payload(api_order_data, org_id)
            if not order:
                return Response({"error": "Failed to sync order details from Shopify API."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if already_existed:
                message = f"Order #{order.order_number} re-synced successfully from Shopify (line items refreshed)."
            else:
                message = f"Successfully synced Order #{order.order_number}!"

            # Try synchronous Shipway PII fetch if not already populated and not skipped
            has_pii = bool(order.customer_first_name and order.contact_phone and order.shipping_address)
            skip_sync = creds.get('skip_shipway_pii_sync', False)
            pii_fetched = False
            if has_pii or skip_sync:
                pii_fetched = True
            else:
                try:
                    from core.tasks.shipway_sync import fetch_missing_pii_task
                    fetch_missing_pii_task(order.id, org_id)
                    order.refresh_from_db()
                    if order.contact_phone or order.customer_first_name:
                        pii_fetched = True
                except Exception as e:
                    logger.error(f"Error fetching PII from Shipway synchronously: {e}")

            # Fallback: schedule task in background if sync failed or was incomplete
            if not pii_fetched:
                from django_q.tasks import schedule
                try:
                    schedule(
                        'core.tasks.fetch_missing_pii_task',
                        order.id,
                        org_id,
                        1,
                        next_run=timezone.now() + timedelta(minutes=4)
                    )
                except Exception as sched_err:
                    logger.error(f"Failed to schedule background task: {sched_err}")

            clear_kpi_cache()
            serializer = OrderSerializer(order)
            return Response({
                "message": message,
                "order": serializer.data
            }, status=status.HTTP_200_OK)


class BulkConfirmOrdersView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:confirmation:create', 'operations_fulfillment:orders:edit']
    }

    def post(self, request, *args, **kwargs):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)

        order_numbers = request.data.get('order_numbers', [])
        if not order_numbers or not isinstance(order_numbers, list):
            return Response({"error": "Please provide a list of order numbers to confirm."}, status=status.HTTP_400_BAD_REQUEST)

        # Enqueue the task
        task_id = async_task(
            'core.tasks.order_automation.bulk_confirm_orders_task',
            order_numbers,
            org_id,
            request.user.id if request.user.is_authenticated else None
        )

        return Response({
            "success": True,
            "message": "Bulk order confirmation task queued successfully.",
            "task_id": task_id
        }, status=status.HTTP_202_ACCEPTED)


class BulkConfirmStatusView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:awb_sheet:view']
    }

    def get(self, request, task_id, *args, **kwargs):
        from django_q.models import Success, Failure

        success_task = Success.objects.filter(id=task_id).first()
        if success_task:
            return Response({
                "status": "success",
                "result": success_task.result,
            }, status=status.HTTP_200_OK)

        failure_task = Failure.objects.filter(id=task_id).first()
        if failure_task:
            return Response({
                "status": "failed",
                "error": str(failure_task.result or "Task failed without result trace."),
            }, status=status.HTTP_200_OK)

        try:
            from django_q.models import Task
            task = Task.objects.filter(id=task_id).first()
            if task:
                if task.success:
                    return Response({
                        "status": "success",
                        "result": task.result,
                    }, status=status.HTTP_200_OK)
                elif task.success is False:
                    return Response({
                        "status": "failed",
                        "error": str(task.result or "Task failed."),
                    }, status=status.HTTP_200_OK)
        except Exception:
            pass

        return Response({
            "status": "pending",
        }, status=status.HTTP_200_OK)


class DjangoQTaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id, *args, **kwargs):
        from django_q.models import Success, Failure

        success_task = Success.objects.filter(id=task_id).first()
        if success_task:
            return Response({
                "status": "success",
                "result": success_task.result,
            }, status=status.HTTP_200_OK)

        failure_task = Failure.objects.filter(id=task_id).first()
        if failure_task:
            return Response({
                "status": "failed",
                "error": str(failure_task.result or "Task failed without result trace."),
            }, status=status.HTTP_200_OK)

        try:
            from django_q.models import Task
            task = Task.objects.filter(id=task_id).first()
            if task:
                if task.success:
                    return Response({
                        "status": "success",
                        "result": task.result,
                    }, status=status.HTTP_200_OK)
                elif task.success is False:
                    return Response({
                        "status": "failed",
                        "error": str(task.result or "Task failed."),
                    }, status=status.HTTP_200_OK)
        except Exception:
            pass

        return Response({
            "status": "pending",
        }, status=status.HTTP_200_OK)


