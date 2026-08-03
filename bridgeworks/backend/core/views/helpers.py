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
    IsOrganizationOwner, IsAllowedCustomerExperience
)

User = get_user_model()



# ==============================================================================
# 1. MULTI-TENANCY CORE HELPERS
# ==============================================================================

def _get_org_id_or_none(request):
    """Retrieves the organization ID for the logged-in user (Founder OR Teammate)."""
    if not request.user.is_authenticated:
        return None
    
    # 1. Check if user is the Founder (Owner of ShopCredentials)
    if hasattr(request.user, 'shop_credentials'):
        return request.user.shop_credentials.organization_id
        
    # 2. Check if user is a Teammate via new WorkspaceMembership
    try:
        membership = request.user.workspace_memberships.first()
        if membership and membership.workspace:
            return membership.workspace.organization_id
    except Exception:
        pass

    # 3. Check if user is a Teammate (Linked via legacy TeamMemberSettings)
    try:
        return request.user.team_settings.organization.organization_id
    except Exception:
        return None

def _filter_orders_by_org_id(request, queryset):
    """Filters the given queryset based on the logged-in user's organization_id."""
    org_id = _get_org_id_or_none(request)
    if org_id:
        return queryset.filter(org_id=org_id)
    return Order.objects.none()

def _clean_shopify_url(url_input):
    if not url_input:
        return None
    clean_url = re.sub(r'^(https?://)?(www\.)?', '', str(url_input))
    clean_url = clean_url.split('/')[0]
    if '.myshopify.com' in clean_url:
        return clean_url
    return None


# ==============================================================================
