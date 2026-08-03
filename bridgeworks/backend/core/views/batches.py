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
# 5. BATCHING & PACKAGING VIEWS
# ==============================================================================

class BatchCreateView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:orders:edit', 'operations_fulfillment:confirmation:create', 'operations_fulfillment:awb_sheet:create']
    }
    
    def post(self, request, format=None):
        org_id = _get_org_id_or_none(request)
        if not org_id:
             return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)
             
        order_numbers = request.data.get('order_numbers', [])
        
        if not order_numbers or not isinstance(order_numbers, list):
            return Response({"error": "No valid order numbers provided."}, status=status.HTTP_400_BAD_REQUEST)
             
        orders_to_batch = Order.objects.filter(
            order_number__in=order_numbers, 
            status='Confirmed',
            org_id=org_id
        ).exclude(status='Batched') 
        
        found_count = orders_to_batch.count()
        
        if found_count == 0:
             return Response({
                 "error": "No eligible 'Confirmed' orders found. They might be already batched or belong to another organization."
             }, status=status.HTTP_404_NOT_FOUND)
             
        new_batch = Batch.objects.create()
        new_batch.orders.set(orders_to_batch)
        
        orders_to_batch.update(status='Batched')
        
        return Response({ 
            "batch_id": new_batch.id, 
            "orders_numbers_pushed": found_count 
        }, status=status.HTTP_201_CREATED)

class BatchListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:confirmation:view', 'operations_fulfillment:orders:view', 'operations_fulfillment:awb_sheet:view']
    }

    def get(self, request, format=None):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response([], status=status.HTTP_200_OK)

        # Query Parameters for filtering
        date_filter = request.query_params.get('date', None)  # YYYY-MM-DD format (legacy single date)
        start_date_filter = request.query_params.get('start_date', None)  # YYYY-MM-DD format
        end_date_filter = request.query_params.get('end_date', None)  # YYYY-MM-DD format
        search_query = request.query_params.get('search', None)  # Order number search

        visible_internal_statuses = ['Pending', 'Fulfilled', 'On Hold']

        # Construct single filter condition to avoid multiple joins
        base_query = Q(
            orders__org_id=org_id,
            orders__status='Batched',
            orders__internal_fulfillment_status__in=visible_internal_statuses
        )

        # If searching, search across ALL batches (ignore date filter)
        if search_query:
            # Search by Order Number OR Tracking Number (AWB)
            search_query = search_query.strip()
            base_query &= (
                Q(orders__order_number__icontains=search_query) |
                Q(orders__fulfillments__tracking_info__number__icontains=search_query)
            )
        elif start_date_filter or end_date_filter:
            # Filter by date range
            from datetime import datetime
            try:
                if start_date_filter:
                    start_date = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
                    base_query &= Q(created_at__date__gte=start_date)
                if end_date_filter:
                    end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
                    base_query &= Q(created_at__date__lte=end_date)
            except ValueError:
                pass  # Invalid date format, skip filter
        elif date_filter:
            # Filter by specific date (legacy single date)
            try:
                from datetime import datetime
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                base_query &= Q(created_at__date=filter_date)
            except ValueError:
                pass  # Invalid date format, skip filter
        else:
            # Default to today's date for fast loading
            from datetime import date
            today = date.today()
            base_query &= Q(created_at__date=today)

        batches = Batch.objects.filter(base_query).distinct()

        batches = batches.prefetch_related(
            Prefetch(
                'orders',
                queryset=Order.objects.filter(
                    org_id=org_id,
                    status='Batched'
                ).filter(
                    Q(internal_fulfillment_status__in=visible_internal_statuses) |
                    Q(internal_fulfillment_status__isnull=True) |
                    Q(internal_fulfillment_status='')
                ).prefetch_related(
                    'line_items',
                    'fulfillments__tracking_info',
                    'fulfillments__tracking_events',
                    'packaging_images',
                    'case_files'
                )
            )
        ).order_by('-created_at')

        serializer = BatchSerializer(batches, many=True)
        return Response(serializer.data)

class UserListView(APIView):
    permission_classes = [IsAuthenticated] 
    def get(self, request, format=None):
        requesting_org_id = _get_org_id_or_none(self.request)
        if not requesting_org_id:
            return User.objects.none()
        
        queryset = User.objects.filter(
            team_settings__organization__organization_id=requesting_org_id,
            is_active=True
        ).exclude(is_superuser=True).order_by('username')
        
        # Pre-fetch today's attendance status and work mode
        from django.utils import timezone
        from core.models.mydesk import AttendanceEntry
        today = timezone.localdate()
        attendance_map = {
            entry.user_id: (entry.status, entry.work_mode)
            for entry in AttendanceEntry.objects.filter(
                user__in=queryset,
                entry_date=today,
                is_active=True
            )
        }
        
        users_data = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'today_status': attendance_map.get(user.id)[0] if attendance_map.get(user.id) else None,
                'work_mode': attendance_map.get(user.id)[1] if attendance_map.get(user.id) else None
            }
            for user in queryset
        ]
        return Response(users_data)

class PackagingBatchCreateView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:confirmation:create', 'operations_fulfillment:orders:edit']
    } 
    def post(self, request, *args, **kwargs):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)
             
        order_numbers = request.data.get('order_numbers', [])
        assigned_to_id = request.data.get('assigned_to_id')

        if not order_numbers or not assigned_to_id:
            return Response({'error': 'Missing order numbers or agent ID.'}, status=status.HTTP_400_BAD_REQUEST)

        orders = Order.objects.filter(
            order_number__in=order_numbers,
            internal_fulfillment_status='Fulfilled',
            org_id=org_id
        )
        
        orders_count = orders.count()
        if len(order_numbers) != orders_count:
            return Response({'error': 'One or more selected orders were not in a "Fulfilled" state or do not belong to your shop.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent = User.objects.get(id=assigned_to_id)
        except User.DoesNotExist:
            return Response({"error": "Assigned agent not found."}, status=status.HTTP_404_NOT_FOUND)

        batch = PackagingBatch.objects.create(assigned_to=agent)
        batch.orders.set(orders)
        orders.update(internal_fulfillment_status='Sent for Packaging')

        if agent != request.user:
            try:
                from core.services.notifications import push_unified_notification
                push_unified_notification(
                    recipient=agent,
                    actor=request.user if request.user.is_authenticated else None,
                    module='tasks',
                    action='share',
                    message=f"You have been assigned {orders_count} order(s) for packaging (Batch #{batch.id}).",
                    title="New Packaging Batch Assigned",
                    preview=f"Batch #{batch.id} contains {orders_count} orders.",
                    entity_type="packaging_batch",
                    entity_id=batch.id,
                    deep_link={
                        "pathname": "/operations/packaging",
                        "batchId": str(batch.id)
                    },
                    metadata={
                        "category": "operations",
                        "priority": "medium",
                        "batch_id": batch.id,
                        "orders_count": orders_count,
                        "sound_category": "assign_batch",
                    },
                    sound_category="assign_batch",
                )
            except Exception as e:
                logger.error(f"Failed to send packaging batch assignment notification: {e}", exc_info=True)

        return Response({
            'status': 'Packaging batch created successfully.',
            'batch_id': batch.id,
            'orders_in_batch': orders_count 
        }, status=status.HTTP_201_CREATED)

class PackagingBatchListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'operations_fulfillment:packaging_sheet:view'
    } 
    
    def get(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response([], status=status.HTTP_200_OK)

        # Query Parameters for filtering
        date_filter = request.query_params.get('date', None)  # YYYY-MM-DD format
        search_query = request.query_params.get('search', None)  # Order number search

        relevant_statuses = ['Sent for Packaging', 'Packaged']
        
        # Build single base query to avoid multiple joins
        base_query = Q(
            orders__internal_fulfillment_status__in=relevant_statuses,
            orders__org_id=org_id
        )

        # If searching, search across ALL batches (ignore date filter)
        if search_query:
            search_query = search_query.strip()
            base_query &= Q(orders__order_number__icontains=search_query)
        elif date_filter:
            # Filter by specific date
            try:
                from datetime import datetime
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                base_query &= Q(created_at__date=filter_date)
            except ValueError:
                pass  # Invalid date format, skip filter
        else:
            # Default to today's date for fast loading
            from datetime import date
            today = date.today()
            base_query &= Q(created_at__date=today)

        batches = PackagingBatch.objects.filter(base_query).distinct()

        batches = batches.prefetch_related(
            Prefetch('orders', queryset=Order.objects.filter(
                internal_fulfillment_status__in=relevant_statuses, 
                org_id=org_id
            ).prefetch_related(
                'line_items',
                'fulfillments__tracking_info',
                'fulfillments__tracking_events',
                'packaging_images',
                'case_files'
            ))
        ).order_by('-created_at')

        serializer = PackagingBatchSerializer(batches, many=True)
        return Response(serializer.data)


class OnHoldOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    def get_queryset(self):
        queryset = Order.objects.filter(internal_fulfillment_status='On Hold').order_by('-updated_at')
        return _filter_orders_by_org_id(self.request, queryset)

class PackagingImageView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'operations_fulfillment:packaging_sheet:edit'
    } 
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, order_number):
        org_id = _get_org_id_or_none(request)
        if not org_id:
             return Response({"error": "User profile not linked to an organization."}, status=status.HTTP_403_FORBIDDEN)
             
        try:
            order = Order.objects.get(order_number=order_number, org_id=org_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found or does not belong to your shop.'}, status=status.HTTP_404_NOT_FOUND)

        images = request.FILES.getlist('images')
        if not images:
            return Response({'error': 'No files were provided in the request.'}, status=status.HTTP_400_BAD_REQUEST)

        created_images = []
        for image in images:
            img_obj = PackagingImage.objects.create(order=order, image=image)
            created_images.append({'id': img_obj.id, 'url': request.build_absolute_uri(img_obj.image.url)})
        
        return Response({
            'success': f'{len(created_images)} files uploaded successfully',
            'images': created_images
            }, status=status.HTTP_201_CREATED)


# ==============================================================================
