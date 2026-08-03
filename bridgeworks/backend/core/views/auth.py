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
    PackagingImage, ShopCredentials, TeamMemberSettings, Invitation, TrackingEvent, CaseFile, IssueComment, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES,
    WorkspaceMembership
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
# 2. AUTHENTICATION & ONBOARDING VIEWS
# ==============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_csrf_token(request):
    token = get_token(request)
    return JsonResponse({'csrftoken': token})


class OnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_is_co_founder = WorkspaceMembership.objects.filter(user=request.user, is_co_founder=True).exists()
        is_founder = hasattr(request.user, 'shop_credentials') or user_is_co_founder or (hasattr(request.user, "team_settings") and request.user.team_settings.role == "founder")
        has_creds = ShopCredentials.objects.filter(owner=request.user).exists()

        response_data = {
            "onboarding_needed": is_founder and not has_creds,
            "is_founder": is_founder,
        }

        if has_creds:
            creds = ShopCredentials.objects.get(owner=request.user)
            response_data.update({
                "shopify_shop_url": creds.get_shopify_shop_url() or "",
                "shopify_api_key": creds.get_shopify_api_key() or "",
                "shopify_api_password": creds.get_shopify_password() or "",
                "shopify_webhook_secret": creds.get_shopify_webhook_secret() or "",
                "shopify_order_prefix": creds.shopify_order_prefix or "",
                "shipping_platform": getattr(creds, "shipping_platform", "shipway"),
                "shipway_email": creds.get_shipway_email() or "",
                "shipway_license_key": creds.get_shipway_license_key() or "",
                "shiprocket_email": creds.get_shiprocket_email() or "",
                "shiprocket_password": creds.get_shiprocket_password() or "",
                "shiprocket_pickup_location": creds.shiprocket_pickup_location or "",
                "shiprocket_order_weight": creds.shiprocket_order_weight,
                "shiprocket_box_length": creds.shiprocket_box_length,
                "shiprocket_box_breadth": creds.shiprocket_box_breadth,
                "shiprocket_box_height": creds.shiprocket_box_height,
                "return_prime_token": creds.get_return_prime_token() or "",
                "auth_method": getattr(creds, "auth_method", "legacy"),
                "shipway_warehouse_id": creds.shipway_warehouse_id,
                "shipway_return_warehouse_id": creds.shipway_return_warehouse_id,
                "shipway_order_weight": creds.shipway_order_weight,
                "shipway_box_length": creds.shipway_box_length,
                "shipway_box_breadth": creds.shipway_box_breadth,
                "shipway_box_height": creds.shipway_box_height,
                "shipway_invoice_number_prefix": creds.shipway_invoice_number_prefix or "",
                "shipway_primary_carrier_id": creds.shipway_primary_carrier_id or "",
                "shipway_primary_carrier_title": creds.shipway_primary_carrier_title or "",
                "shipway_fallback_carrier_id": creds.shipway_fallback_carrier_id or "",
                "shipway_fallback_carrier_title": creds.shipway_fallback_carrier_title or "",
                "shipway_store_code": creds.shipway_store_code,
                "bluedart_client_id": creds.bluedart_client_id or "",
                "bluedart_client_secret": creds.bluedart_client_secret or "",
                "bluedart_login_id": creds.bluedart_login_id or "",
                "bluedart_licence_key": creds.bluedart_licence_key or "",
                "bluedart_api_type": creds.bluedart_api_type or "S",
                "skip_shipway_pii_sync": creds.skip_shipway_pii_sync,
                "enable_auto_confirm_orders": creds.enable_auto_confirm_orders,
                "enable_auto_assign_couriers": creds.enable_auto_assign_couriers,
                "enable_auto_send_picklists": creds.enable_auto_send_picklists,
            })

        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request):
        user_is_co_founder = WorkspaceMembership.objects.filter(user=request.user, is_co_founder=True).exists()
        is_founder = hasattr(request.user, 'shop_credentials') or user_is_co_founder or (hasattr(request.user, "team_settings") and request.user.team_settings.role == "founder")

        if not is_founder:
            return Response({"error": "Only founders can complete onboarding."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        try:
            credentials = ShopCredentials.objects.get(owner=request.user)
        except ShopCredentials.DoesNotExist:
            return Response({"detail": "Organization not initialized."}, status=404)

        if "shopify_shop_url" in data:
            clean_shop_url = _clean_shopify_url(data.get("shopify_shop_url"))
            if not clean_shop_url:
                return Response({"detail": "Invalid Shopify Shop URL."}, status=400)
            credentials.organization_id = clean_shop_url.split('.')[0]
            credentials.myshopify_domain = clean_shop_url
            credentials.set_shopify_shop_url(clean_shop_url)

        if "shopify_api_key" in data:
            credentials.set_shopify_api_key(data.get("shopify_api_key"))
        if "shopify_api_password" in data:
            credentials.set_shopify_password(data.get("shopify_api_password"))
        if "shopify_webhook_secret" in data:
            credentials.set_shopify_webhook_secret(data.get("shopify_webhook_secret"))
        if "shopify_order_prefix" in data:
            credentials.shopify_order_prefix = data.get("shopify_order_prefix")
        
        if "shipping_platform" in data:
            credentials.shipping_platform = data.get("shipping_platform")
            
        if "shipway_email" in data:
            credentials.set_shipway_email(data.get("shipway_email"))
        if "shipway_license_key" in data:
            credentials.set_shipway_license_key(data.get("shipway_license_key"))
            
        if "shiprocket_email" in data:
            credentials.set_shiprocket_email(data.get("shiprocket_email"))
        if "shiprocket_password" in data:
            credentials.set_shiprocket_password(data.get("shiprocket_password"))
        if "shiprocket_pickup_location" in data:
            credentials.shiprocket_pickup_location = data.get("shiprocket_pickup_location")
        if "shiprocket_order_weight" in data:
            credentials.shiprocket_order_weight = data.get("shiprocket_order_weight")
        if "shiprocket_box_length" in data:
            credentials.shiprocket_box_length = data.get("shiprocket_box_length")
        if "shiprocket_box_breadth" in data:
            credentials.shiprocket_box_breadth = data.get("shiprocket_box_breadth")
        if "shiprocket_box_height" in data:
            credentials.shiprocket_box_height = data.get("shiprocket_box_height")
            
        if "return_prime_token" in data:
            credentials.set_return_prime_token(data.get("return_prime_token"))
        
        # Save configurable Shipway settings if present
        if "shipway_warehouse_id" in data:
            credentials.shipway_warehouse_id = data.get("shipway_warehouse_id")
        if "shipway_return_warehouse_id" in data:
            credentials.shipway_return_warehouse_id = data.get("shipway_return_warehouse_id")
        if "shipway_order_weight" in data:
            credentials.shipway_order_weight = data.get("shipway_order_weight")
        if "shipway_box_length" in data:
            credentials.shipway_box_length = data.get("shipway_box_length")
        if "shipway_box_breadth" in data:
            credentials.shipway_box_breadth = data.get("shipway_box_breadth")
        if "shipway_box_height" in data:
            credentials.shipway_box_height = data.get("shipway_box_height")
        if "shipway_invoice_number_prefix" in data:
            credentials.shipway_invoice_number_prefix = data.get("shipway_invoice_number_prefix")
        if "shipway_primary_carrier_id" in data:
            credentials.shipway_primary_carrier_id = data.get("shipway_primary_carrier_id")
        if "shipway_primary_carrier_title" in data:
            credentials.shipway_primary_carrier_title = data.get("shipway_primary_carrier_title")
        if "shipway_fallback_carrier_id" in data:
            credentials.shipway_fallback_carrier_id = data.get("shipway_fallback_carrier_id")
        if "shipway_fallback_carrier_title" in data:
            credentials.shipway_fallback_carrier_title = data.get("shipway_fallback_carrier_title")
        if "shipway_store_code" in data:
            credentials.shipway_store_code = data.get("shipway_store_code")
        if "skip_shipway_pii_sync" in data:
            credentials.skip_shipway_pii_sync = data.get("skip_shipway_pii_sync")
            
        if "enable_auto_confirm_orders" in data:
            credentials.enable_auto_confirm_orders = bool(data.get("enable_auto_confirm_orders"))
        if "enable_auto_assign_couriers" in data:
            credentials.enable_auto_assign_couriers = bool(data.get("enable_auto_assign_couriers"))
        if "enable_auto_send_picklists" in data:
            credentials.enable_auto_send_picklists = bool(data.get("enable_auto_send_picklists"))
            
        # Save configurable Blue Dart settings if present
        if "bluedart_client_id" in data:
            credentials.bluedart_client_id = data.get("bluedart_client_id")
        if "bluedart_client_secret" in data:
            credentials.bluedart_client_secret = data.get("bluedart_client_secret")
        if "bluedart_login_id" in data:
            credentials.bluedart_login_id = data.get("bluedart_login_id")
        if "bluedart_licence_key" in data:
            credentials.bluedart_licence_key = data.get("bluedart_licence_key")
        if "bluedart_api_type" in data:
            credentials.bluedart_api_type = data.get("bluedart_api_type")
        
        auth_method = data.get("auth_method")
        if auth_method in ["legacy", "oauth"]:
            credentials.auth_method = auth_method
            
        credentials.onboarding_complete = True
        credentials.save()

        return Response({"detail": "Shop credentials saved successfully."}, status=200)


# ==============================================================================
