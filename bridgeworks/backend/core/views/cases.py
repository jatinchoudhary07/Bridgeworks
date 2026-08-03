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
# 8. CUSTOMER CARE (CASE FILE) VIEWS
# ==============================================================================

class CaseFileListCreateView(generics.ListCreateAPIView):
    """
    GET: The Case File Sheet (List cases filtered by Active/Resolved).
    POST: The FIR Registration (Create a new case).
    """
    serializer_class = CaseFileSerializer
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'customer_experience:case_file_sheet:view',
        'POST': 'customer_experience:case_file_sheet:create'
    } 
    
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        # 1. Filter cases by the user's organization via the related Order
        requesting_org_id = _get_org_id_or_none(self.request)
        if not requesting_org_id:
            return CaseFile.objects.none()

        queryset = CaseFile.objects.filter(
            order__org_id=requesting_org_id
        ).select_related('order', 'registered_by', 'assigned_to')

        # 2. Apply View Type Filter (Active vs Resolved)
        view_type = self.request.query_params.get('view_type', 'active') # Default to active

        if view_type == 'resolved':
            # Show only Resolved/Closed cases, ordered by when they were resolved
            queryset = queryset.filter(status__in=['RESOLVED', 'CLOSED']).order_by('-resolved_at')
        else:
            # Show Active cases (New, Investigating, Pending), ordered by newest first
            queryset = queryset.exclude(status__in=['RESOLVED', 'CLOSED']).order_by('-created_at')

        return queryset

    def perform_create(self, serializer):
        """ Handles FIR registration (POST request). """
        order_number = self.request.data.get('order_number') 
        order_instance = None
        
        if order_number:
            try:
                queryset = Order.objects.filter(order_number=order_number)
                order_instance = _filter_orders_by_org_id(self.request, queryset).first()
                if not order_instance:
                    raise Order.DoesNotExist
            except Order.DoesNotExist:
                raise ValidationError({'order_number': f'Order {order_number} not found in your organization.'})
        
        first_place_of_contact = self.request.data.get('first_place_of_contact')
        
        serializer.save(
            registered_by=self.request.user, 
            order=order_instance,
            status='NEW_FIR',
            first_place_of_contact=first_place_of_contact
        )


class CaseFileRetrieveUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CaseFileSerializer
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'customer_experience:case_file_sheet:view',
        'PATCH': 'customer_experience:case_file_sheet:edit',
        'PUT': 'customer_experience:case_file_sheet:edit',
        'DELETE': 'customer_experience:case_file_sheet:delete'
    }
    lookup_field = 'case_number' 

    def get_queryset(self):
        requesting_org_id = _get_org_id_or_none(self.request)
        if not requesting_org_id:
            return CaseFile.objects.none()

        return CaseFile.objects.filter(
            order__org_id=requesting_org_id
        ).select_related('order', 'registered_by', 'assigned_to')
    def perform_update(self, serializer):
        # 1. Get the new status sent from Frontend
        new_status = self.request.data.get('status')
        
        # 2. Get the current status from Database
        instance = self.get_object()

        # 3. Check if we are marking it as Resolved/Closed for the first time
        if new_status in ['RESOLVED', 'CLOSED'] and instance.status not in ['RESOLVED', 'CLOSED']:
            # Save with the current time
            serializer.save(resolved_at=timezone.now())
        else:
            # Just save normally
            serializer.save()

class IssueCommentListCreateView(generics.ListCreateAPIView):
    serializer_class = IssueCommentSerializer
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'customer_experience:case_file_sheet:view',
        'POST': 'customer_experience:case_file_sheet:create'
    } 

    def get_queryset(self):
        case_number = self.kwargs.get('case_number')
        if not case_number:
            return IssueComment.objects.none()
        
        requesting_org_id = _get_org_id_or_none(self.request)
        if not requesting_org_id:
            return IssueComment.objects.none()

        # Verify access to the case first
        if not CaseFile.objects.filter(case_number=case_number, order__org_id=requesting_org_id).exists():
            raise NotFound("Case File not found or access denied.") 

        return IssueComment.objects.filter(
            case__case_number=case_number
        ).select_related('user', 'case')

    def perform_create(self, serializer):
        case_number = self.kwargs.get('case_number')
        requesting_org_id = _get_org_id_or_none(self.request)
        
        # Ensure we are getting the case that belongs to the user's org
        case = get_object_or_404(CaseFile, case_number=case_number, order__org_id=requesting_org_id)
        
        serializer.save(case=case, user=self.request.user)
        
class OrderLookupView(generics.RetrieveAPIView):
    """
    Lookup a single order by order_number with full details for modals.
    Usage: GET /api/orders/lookup/?order_number=12345
    Also accepts 'number' for backward compatibility.
    """
    serializer_class = OrderSerializer 
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'customer_experience:case_file_sheet:view'
    }

    def get_object(self):
        # Accept both 'order_number' and 'number' for flexibility
        order_number = self.request.query_params.get('order_number') or self.request.query_params.get('number')
        
        if not order_number:
            raise NotFound("Order number is required")

        queryset = Order.objects.filter(order_number=order_number).prefetch_related(
            'line_items',
            'fulfillments__tracking_info',
            'fulfillments__tracking_events',
            'packaging_images',
            'case_files',
        ).select_related('packaged_by', 'confirmed_by')
        
        queryset = _filter_orders_by_org_id(self.request, queryset)
        
        order = queryset.first()
        if not order:
            raise NotFound(f"Order #{order_number} not found")
        
        return order

class CustomerHistoryView(APIView):
    """
    Fetches previous orders for a specific customer from Shopify based on phone number.
    Usage: GET /api/orders/history/?phone=+919876543210
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'customer_experience:case_file_sheet:view'
    }

    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "Phone parameter is required."}, status=400)

        # 1. Get Organization Context
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "User not linked to an organization."}, status=403)

        # 2. Get Shopify Credentials
        creds = _get_decrypted_credentials(org_id)
        if not creds:
            return Response({"error": "Shop credentials not found."}, status=404)

        shop_url = creds['shop_url']
        api_key = creds['api_key']
        password = creds['password']
        api_version = creds.get('api_version', '2024-01') # Default if missing

        # Base Authenticated URL
        base_shopify_url = f"https://{api_key}:{password}@{shop_url}/admin/api/{api_version}"

        try:
            # 3. Search for Customer by Phone
            # NOTE: Shopify requires exact phone matching. 
            # If your DB has "9876543210" but Shopify has "+919876543210", this might fail.
            # We try searching exactly as provided first.
            search_response = requests.get(
                f"{base_shopify_url}/customers/search.json",
                params={"query": f"phone:{phone}"},
                timeout=10
            )
            
            if not search_response.ok:
                print(f"Shopify Customer Search Failed: {search_response.text}")
                return Response([], status=200) # Fail gracefully with empty list

            customers = search_response.json().get("customers", [])

            if not customers:
                # OPTIONAL: Retry with/without country code if strict matching fails
                # For now, we return empty if not found.
                return Response([], status=200)

            customer_id = customers[0]['id']

            # 4. Fetch Orders for this Customer ID
            orders_response = requests.get(
                f"{base_shopify_url}/orders.json",
                params={
                    "customer_id": customer_id,
                    "status": "any", # Get open, closed, and cancelled
                    "limit": 10,     # Limit to last 10 orders for performance
                    "fields": "id,order_number,created_at,total_price,currency,financial_status,fulfillment_status,line_items,tags" 
                },
                timeout=10
            )

            if not orders_response.ok:
                return Response([], status=200)

            orders = orders_response.json().get("orders", [])
            
            # Map 'fulfillment_status' null to 'Pending' for UI consistency
            for o in orders:
                if o['fulfillment_status'] is None:
                    o['status'] = 'Pending' # UI expects 'status' field
                else:
                    o['status'] = o['fulfillment_status'].capitalize()

            return Response(orders, status=200)

        except Exception as e:
            print(f"Error fetching customer history: {e}")
            return Response({"error": str(e)}, status=500)

# =========================================================
