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
    WholesaleLead, Quotation
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
# GLOBAL SEARCH VIEW (Shopify-style Omnibox Search)
# ==============================================================================
class GlobalSearchView(APIView):
    """
    Global search endpoint that searches across the entire database:
    - Order Number
    - Customer Name (first + last)
    - Customer Phone
    - Customer Email
    - AWB / Tracking Number
    - Case File Number
    
    Returns grouped results for display in the Omnibox-style dropdown.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        
        if not query or len(query) < 2:
            return Response({"results": [], "query": query})
        
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"results": [], "query": query})
        
        results = []
        
        # --- 1. SEARCH ORDERS ---
        order_q = Q(org_id=org_id)
        search_q = Q()
        
        # Order Number (exact or partial)
        if query.isdigit():
            search_q |= Q(order_number=int(query))
            search_q |= Q(order_number__icontains=query)
        
        # Customer Name
        search_q |= Q(customer_first_name__icontains=query)
        search_q |= Q(customer_last_name__icontains=query)
        
        # Phone Number
        search_q |= Q(contact_phone__icontains=query)
        
        # Email
        search_q |= Q(contact_email__icontains=query)
        
        # Shipping Address
        search_q |= Q(shipping_address__icontains=query)
        
        orders = Order.objects.filter(order_q & search_q).select_related().order_by('-created_at')[:10]
        
        for order in orders:
            customer_name = f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip() or "Unknown"
            results.append({
                "type": "order",
                "id": order.id,
                "order_number": order.order_number,
                "title": f"#{order.order_number}",
                "subtitle": f"{customer_name} • ₹{order.total_price or 0}",
                "status": order.current_status or order.status or "Pending",
                "url": f"/operations/orders?search={order.order_number}"
            })
        
        # --- 2. SEARCH AWB / TRACKING NUMBERS ---
        awb_results = TrackingInfo.objects.filter(
            fulfillment__order__org_id=org_id,
            number__icontains=query
        ).select_related('fulfillment__order')[:5]
        
        for ti in awb_results:
            order = ti.fulfillment.order
            # Avoid duplicate if order already in results
            if not any(r.get('order_number') == order.order_number for r in results):
                results.append({
                    "type": "tracking",
                    "id": order.id,
                    "order_number": order.order_number,
                    "title": f"AWB: {ti.number}",
                    "subtitle": f"Order #{order.order_number} • {ti.company or 'Unknown Courier'}",
                    "status": order.current_status or "In Transit",
                    "url": f"/tracking?search={ti.number}"
                })
        
        # --- 3. SEARCH CASE FILES ---
        cases = CaseFile.objects.filter(
            order__org_id=org_id
        ).filter(
            Q(case_number__icontains=query) |
            Q(subject__icontains=query) |
            Q(order__order_number__icontains=query) if query.isdigit() else Q()
        ).select_related('order')[:5]
        
        for case in cases:
            order_num = case.order.order_number if case.order else "N/A"
            results.append({
                "type": "case",
                "id": case.id,
                "case_number": case.case_number,
                "title": f"Case #{case.case_number}",
                "subtitle": f"{case.subject[:40]}... • Order #{order_num}",
                "status": case.status,
                "url": f"/customer-care/cases/{case.case_number}"
            })
        
        # --- 4. SEARCH BY CUSTOMER (Aggregate) ---
        # Find all orders for a customer by phone or email
        customer_matches = []
        if '@' in query or query.isdigit() or len(query) >= 3:
            # Aggregate orders by phone or email
            customer_orders = Order.objects.filter(order_q).filter(
                Q(contact_phone__icontains=query) | Q(contact_email__icontains=query)
            ).values('contact_phone', 'contact_email', 'customer_first_name', 'customer_last_name').annotate(
                total_orders=Count('id'),
                total_spent=Sum('total_price')
            ).order_by('-total_orders')[:3]
            
            for cust in customer_orders:
                name = f"{cust['customer_first_name'] or ''} {cust['customer_last_name'] or ''}".strip() or "Unknown"
                identifier = cust['contact_phone'] or cust['contact_email'] or "No Contact"
                
                # Avoid duplicates
                if not any(r.get('subtitle', '').startswith(identifier[:10]) for r in results if r.get('type') == 'customer'):
                    results.append({
                        "type": "customer",
                        "title": name,
                        "subtitle": f"{identifier} • {cust['total_orders']} orders • ₹{cust['total_spent'] or 0}",
                        "url": f"/operations/orders?search={identifier}"
                    })

        # --- 5. SEARCH B2B LEADS / COMPANIES ---
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if shop:
            leads = WholesaleLead.objects.filter(
                shop=shop
            ).filter(
                Q(company_name__icontains=query) |
                Q(contact_person__icontains=query) |
                Q(phone__icontains=query) |
                Q(email__icontains=query) |
                Q(industry__icontains=query)
            )[:5]
            
            for lead in leads:
                results.append({
                    "type": "lead",
                    "id": lead.id,
                    "title": lead.company_name,
                    "subtitle": f"B2B Lead • {lead.contact_person or 'No Contact'} • {lead.get_stage_display()}",
                    "status": lead.stage,
                    "url": f"/sales/crm?search={lead.company_name}"
                })

            # --- 6. SEARCH QUOTATIONS ---
            quotes = Quotation.objects.filter(
                shop=shop
            ).filter(
                Q(quote_number__icontains=query) |
                Q(client_name__icontains=query) |
                Q(client_email__icontains=query)
            )[:5]
            
            for quote in quotes:
                results.append({
                    "type": "quote",
                    "id": quote.id,
                    "title": quote.quote_number,
                    "subtitle": f"Quotation • {quote.client_name} • {quote.total_value}",
                    "status": quote.status,
                    "url": f"/sales/quotations?search={quote.quote_number}"
                })
        
        return Response({
            "results": results[:15],  # Limit total results
            "query": query,
            "count": len(results)
        })


# ==============================================================================
