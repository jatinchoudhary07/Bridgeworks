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
from .orders import StandardResultsSetPagination
# --- INTELLIGENCE MODULE VIEWS ---
# =========================================================

# Existing API Views...


class ChatAnalyticsView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'analytics_reporting:analytics:view'
    }

    def post(self, request):
        try:
            from core.services.chat_agent import ask_database
            from core.models import ThorfinnChatSession, ThorfinnChatMessage, ShopCredentials
            
            question = request.data.get('question')
            session_id = request.data.get('session_id')
            history = request.data.get('history', [])
            
            if not question:
                return Response({'error': 'Question is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            org_id = _get_org_id_or_none(request)
            if not org_id:
                return Response({'error': 'Organization not found'}, status=400)
                
            shop = ShopCredentials.objects.filter(organization_id=org_id).first()
            if not shop:
                return Response({"error": "Shop credentials not found for this organization."}, status=404)
            
            # Load or create session
            if session_id:
                session = ThorfinnChatSession.objects.filter(
                    id=session_id,
                    user=user,
                    shop__organization_id=org_id
                ).first()
                if not session:
                    return Response({'error': 'Chat session not found'}, status=404)
            else:
                # Create a new session
                title = question[:40] + ("..." if len(question) > 40 else "")
                session = ThorfinnChatSession.objects.create(
                    user=user,
                    shop=shop,
                    title=title
                )
            
            # Save user message to DB
            ThorfinnChatMessage.objects.create(
                session=session,
                role='user',
                content=question
            )
            
            # If session is new or title is default/untitled, update title based on question
            if not session_id and session.title == "New Chat":
                session.title = question[:40] + ("..." if len(question) > 40 else "")
                session.save(update_fields=['title', 'updated_at'])
            
            # Get previous messages for history if not provided by frontend
            if session_id and not history:
                db_messages = ThorfinnChatMessage.objects.filter(session=session).order_by('created_at')
                history = []
                for db_msg in db_messages:
                    history.append({
                        'role': 'user' if db_msg.role == 'user' else 'model',
                        'content': db_msg.content
                    })
            
            # Get response from AI agent
            answer, actions = ask_database(question, history=history, user=user, org_id=org_id)
            
            # Save AI message to DB
            ThorfinnChatMessage.objects.create(
                session=session,
                role='ai',
                content=answer,
                actions=actions
            )
            
            # Force update of updated_at on session to bubble it to the top
            session.save(update_fields=['updated_at'])
            
            return Response({
                'answer': answer,
                'actions': actions,
                'session_id': str(session.id),
                'session_title': session.title
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Chat Analytics Error: {str(e)}", exc_info=True)
            return Response({'error': 'I could not process your query right now.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThorfinnChatSessionListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'analytics_reporting:analytics:view',
        'POST': 'analytics_reporting:analytics:view'
    }
    
    def get(self, request):
        from core.models import ThorfinnChatSession
        from core.serializers.intelligence import ThorfinnChatSessionSerializer
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
        
        sessions = ThorfinnChatSession.objects.filter(
            user=request.user,
            shop__organization_id=org_id
        ).order_by('-updated_at')
        
        serializer = ThorfinnChatSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        from core.models import ThorfinnChatSession, ShopCredentials
        from core.serializers.intelligence import ThorfinnChatSessionSerializer
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if not shop:
            return Response({"error": "Shop credentials not found for this organization."}, status=404)
            
        title = request.data.get('title', 'New Chat')
        session = ThorfinnChatSession.objects.create(
            user=request.user,
            shop=shop,
            title=title
        )
        serializer = ThorfinnChatSessionSerializer(session)
        return Response(serializer.data, status=201)


class ThorfinnChatSessionDetailView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'analytics_reporting:analytics:view',
        'DELETE': 'analytics_reporting:analytics:view',
        'PATCH': 'analytics_reporting:analytics:view',
    }
    
    def get(self, request, session_id):
        from core.models import ThorfinnChatSession
        from core.serializers.intelligence import ThorfinnChatSessionSerializer
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        session = ThorfinnChatSession.objects.filter(
            id=session_id,
            user=request.user,
            shop__organization_id=org_id
        ).first()
        
        if not session:
            return Response({"error": "Session not found."}, status=404)
            
        serializer = ThorfinnChatSessionSerializer(session)
        return Response(serializer.data)
    
    def patch(self, request, session_id):
        from core.models import ThorfinnChatSession
        from core.serializers.intelligence import ThorfinnChatSessionSerializer
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        session = ThorfinnChatSession.objects.filter(
            id=session_id,
            user=request.user,
            shop__organization_id=org_id
        ).first()
        
        if not session:
            return Response({"error": "Session not found."}, status=404)
        
        title = request.data.get('title')
        if title:
            session.title = title[:255]
            session.save(update_fields=['title', 'updated_at'])
            
        serializer = ThorfinnChatSessionSerializer(session)
        return Response(serializer.data)
    
    def delete(self, request, session_id):
        from core.models import ThorfinnChatSession
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        session = ThorfinnChatSession.objects.filter(
            id=session_id,
            user=request.user,
            shop__organization_id=org_id
        ).first()
        
        if not session:
            return Response({"error": "Session not found."}, status=404)
            
        session.delete()
        return Response({"status": "deleted"}, status=200)


class ThorfinnChatMessageListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'analytics_reporting:analytics:view'
    }
    
    def get(self, request, session_id):
        from core.models import ThorfinnChatSession, ThorfinnChatMessage
        from core.serializers.intelligence import ThorfinnChatMessageSerializer
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        session = ThorfinnChatSession.objects.filter(
            id=session_id,
            user=request.user,
            shop__organization_id=org_id
        ).first()
        
        if not session:
            return Response({"error": "Session not found."}, status=404)
            
        messages = ThorfinnChatMessage.objects.filter(session=session).order_by('created_at')
        serializer = ThorfinnChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

class LogNDRCallView(APIView):
    """
    Logs a call specifically for NDR (Action) Tab.
    Expects: { "order_id": 123, "status": "Will Accept", "remark": "Customer said..." }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:edit'
    }
    
    def post(self, request):
        order_id = request.data.get('order_id')
        call_status = request.data.get('status', '')  # e.g. "RNR", "Connected"
        remark = request.data.get('remark', '')
        
        if not order_id:
            return Response({"error": "Order ID is required"}, status=400)
        
        if not call_status and not remark:
            return Response({"error": "Status or Remark is required"}, status=400)

        try:
            order = Order.objects.get(id=order_id)
            user = request.user.username if request.user.is_authenticated else "System"
            now = timezone.now()

            # Update fields based on what was provided
            if call_status:
                order.ndr_call_status = call_status
                order.ndr_last_called_at = now
                order.ndr_call_attempts += 1
            
            if remark or remark == '':  # Allow clearing remarks too
                order.ndr_remarks = remark

            # Only log to history if a status was provided
            if call_status:
                log_entry = {
                    "datetime": now.isoformat(),
                    "status": call_status,
                    "remark": remark,
                    "agent": user
                }

                if not isinstance(order.ndr_call_history, list):
                    order.ndr_call_history = []
                
                order.ndr_call_history.insert(0, log_entry)

            order.save()

            return Response({
                "message": "NDR Call Logged",
                "ndr_call_status": order.ndr_call_status,
                "ndr_remarks": order.ndr_remarks,
                "ndr_call_history": order.ndr_call_history
            }, status=200)

        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class GenerateAWBAndBatchView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:orders:edit', 'operations_fulfillment:awb_sheet:create']
    }
    """
    1. Filters for orders that HAVE an AWB.
    2. Creates a 'printed_AWB_batch'.
    3. AUTO-PUSH: Updates status to 'Batched' immediately so they appear in Confirmation Sheet.
    """
    
    def post(self, request):
        order_ids = request.data.get('order_ids', [])
        if not order_ids:
            return Response({"error": "No orders selected"}, status=400)

        # 1. Fetch Orders that match selection AND have Tracking Info
        successful_orders = Order.objects.filter(
            id__in=order_ids,
            fulfillments__tracking_info__number__isnull=False
        ).distinct()

        successful_ids = list(successful_orders.values_list('id', flat=True))
        failed_ids = list(set(order_ids) - set(successful_ids))

        batch_info = None

        if successful_orders.exists():
            # --- De-duplication (Safety) ---
            # Remove from any old batches to ensure they only exist in this new one
            for order in successful_orders:
                old_batches = order.batches.filter(name__startswith='printed_AWB_batch_')
                for old_batch in old_batches:
                    old_batch.orders.remove(order)
                    if old_batch.orders.count() == 0:
                        old_batch.delete()
            # -------------------------------

            timestamp = timezone.now().strftime("%Y%m%d_%H%M")
            batch_name = f"printed_AWB_batch_{timestamp}"
            
            new_batch = Batch.objects.create(
                name=batch_name,
                created_by=request.user if request.user.is_authenticated else None
            )
            
            new_batch.orders.set(successful_orders)
            
            # >>> CRITICAL CHANGE: AUTO-PUSH <<<
            # We set status='Batched' immediately. 
            # This makes them show up in the Confirmation Sheet instantly.
            successful_orders.update(status='Batched') 
            # >>> END CHANGE <<<

            batch_info = {
                "id": new_batch.id,
                "name": new_batch.name,
                "size": successful_orders.count(),
                "created_by": new_batch.created_by.username if new_batch.created_by else "System"
            }

        return Response({
            "message": "Batching Complete",
            "created_batch": batch_info,
            "success_count": len(successful_ids),
            "failed_count": len(failed_ids),
            "failed_ids": failed_ids,
            "note": "Orders marked as Batched and moved to Confirmation Sheet."
        }, status=200)

# In backend/core/views.py

class AWBBatchListView(generics.ListAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['operations_fulfillment:orders:view', 'operations_fulfillment:awb_sheet:view']
    }
    """
    Returns AWB batches - OPTIMIZED VERSION.
    - Uses AWBBatchSerializer (lightweight, no heavy nested relations)
    - Proper prefetch_related to eliminate N+1 queries
    - Pagination for large datasets
    """
    serializer_class = AWBBatchSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        org_id = _get_org_id_or_none(self.request)
        if not org_id:
            return Batch.objects.none()

        search_query = self.request.query_params.get('search', '').strip()

        # Base filter: AWB batches only
        base_filter = Q(name__startswith='printed_AWB_batch_')

        if search_query:
            # --- SEARCH MODE ---
            order_q = Q(org_id=org_id)
            
            # Build Search Filter for Orders
            search_cond = Q(order_number__icontains=search_query) | \
                          Q(customer_first_name__icontains=search_query) | \
                          Q(customer_last_name__icontains=search_query) | \
                          Q(fulfillments__tracking_info__number__icontains=search_query)
            
            # Exact match for numeric Order # is faster
            if search_query.isdigit():
                search_cond |= Q(order_number=search_query)

            # Get IDs of Batches that contain matching Orders
            matching_batch_ids = list(
                Order.objects.filter(order_q & search_cond)
                .values_list('batches__id', flat=True)
                .distinct()
            )

            # Also find Batches where the Batch Name matches
            name_match_ids = list(
                Batch.objects.filter(
                    base_filter,
                    name__icontains=search_query,
                    orders__org_id=org_id
                ).values_list('id', flat=True).distinct()
            )

            final_batch_ids = set(matching_batch_ids + name_match_ids)
            final_batch_ids.discard(None)

            queryset = Batch.objects.filter(id__in=final_batch_ids)
        else:
            # --- NO SEARCH (DEFAULT VIEW) ---
            # Optimized: Direct filter on Batch using joins (DB handles this better than huge ID lists)
            queryset = Batch.objects.filter(
                orders__org_id=org_id,
                name__startswith='printed_AWB_batch_'
            ).distinct()

        # CRITICAL: Prefetch to avoid N+1 queries
        queryset = queryset.prefetch_related(
            Prefetch(
                'orders',
                queryset=Order.objects.select_related('confirmed_by').only(
                    'id', 'order_number', 'customer_first_name', 'customer_last_name',
                    'total_price', 'status', 'current_status', 'confirmed_at', 'confirmed_by',
                    'financial_status', 'is_test_order', 'is_auto_confirmed', 'picklist_generated_at'
                ).prefetch_related(
                    Prefetch(
                        'fulfillments',
                        queryset=Fulfillment.objects.only('id', 'order_id').prefetch_related(
                            Prefetch(
                                'tracking_info',
                                queryset=TrackingInfo.objects.only('id', 'number', 'company', 'url', 'fulfillment_id')
                            )
                        )
                    )
                )
            ),
            'created_by'
        ).order_by('-created_at')

        return queryset

class FetchTrackingAndBatchView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['operations_fulfillment:orders:edit', 'operations_fulfillment:awb_sheet:create']
    }
    """
    Async Endpoint: Triggers background task to Auto Generate AWB & Create Batch.
    Solves Gunicorn Timeout by offloading the API calls to Django-Q.
    """

    def post(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found"}, status=400)

        # The frontend sends 'order_ids' (database IDs), not numbers
        order_ids = request.data.get('order_ids', [])
        if not order_ids:
            return Response({"error": "No orders selected"}, status=400)

        # TRIGGER BACKGROUND TASK
        # This returns immediately with a Task ID
        task_id = async_task(
            'core.tasks.shipway_sync.auto_generate_awb_for_orders_task',
            order_ids,                                                 # Arg 1
            org_id,                                                    # Arg 2
            None,                                                      # recipient_emails (None for Fetch & Batch)
            True,                                                      # is_manual
            request.user.id,                                           # user_id
            task_name=f"auto_awb_batch_{request.user.id}_{len(order_ids)}"
        )

        return Response({
            "message": "Auto AWB generation and batching started in background. The batch will appear in the list shortly.",
            "status": "queued",
            "task_id": task_id
        }, status=200)


# ==============================================================================
# INTELLIGENCE MODULE — AGENT CONFIGURATION API
# ==============================================================================

class AgentConfigurationView(APIView):
    permission_classes = [IsOrganizationOwner]
    """
    GET: Returns the active AgentConfiguration (system prompt, status).
    PUT: Updates the active AgentConfiguration from the Intelligence frontend.
    """

    def get(self, request):
        from core.models import AgentConfiguration
        from core.serializers import AgentConfigurationSerializer

        config = AgentConfiguration.objects.filter(is_active=True).order_by('-updated_at').first()
        if not config:
            return Response({
                "id": None,
                "name": "Default",
                "is_active": False,
                "system_prompt": "",
                "updated_at": None,
                "exists": False,
            })

        serializer = AgentConfigurationSerializer(config)
        data = serializer.data
        data["exists"] = True
        return Response(data)

    def put(self, request):
        from core.models import AgentConfiguration
        from core.serializers import AgentConfigurationSerializer

        config = AgentConfiguration.objects.filter(is_active=True).order_by('-updated_at').first()

        if not config:
            # Create a new one if none exists
            config = AgentConfiguration.objects.create(
                name=request.data.get('name', 'RTO Intelligence Agent'),
                is_active=True,
                system_prompt=request.data.get('system_prompt', ''),
            )
            serializer = AgentConfigurationSerializer(config)
            return Response(serializer.data, status=201)

        serializer = AgentConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class AgentActivityView(APIView):
    """
    Returns recent AI Agent task executions from Django-Q's task history.
    Shows the last 20 evaluations with their results.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'analytics_reporting:analytics:view'
    }
    def get(self, request):
        from django_q.models import Success, Failure
        from core.models import Order
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'tasks': [], 'total_success': 0, 'total_failed': 0})

        results = []

        # Fetch more to allow for filtering in Python
        successes_raw = Success.objects.filter(func='core.tasks.evaluate_order_task').order_by('-stopped')[:200]
        failures_raw = Failure.objects.filter(func='core.tasks.evaluate_order_task').order_by('-stopped')[:100]

        all_args = [t.args[0] for t in successes_raw if t.args] + [t.args[0] for t in failures_raw if t.args]
        valid_orders = set(Order.objects.filter(id__in=all_args, org_id=org_id).values_list('id', flat=True))

        success_count = 0
        for task in successes_raw:
            if not task.args or task.args[0] not in valid_orders:
                continue
            results.append({
                'id': str(task.id),
                'order_args': task.args,
                'status': 'success',
                'result': str(task.result) if task.result else 'No result',
                'started': task.started.isoformat() if task.started else None,
                'stopped': task.stopped.isoformat() if task.stopped else None,
                'attempt_count': task.attempt_count if hasattr(task, 'attempt_count') else 1,
            })
            success_count += 1
            if success_count >= 15:
                break

        failure_count = 0
        for task in failures_raw:
            if not task.args or task.args[0] not in valid_orders:
                continue
            results.append({
                'id': str(task.id),
                'order_args': task.args,
                'status': 'failed',
                'result': str(task.result) if task.result else 'Task failed',
                'started': task.started.isoformat() if task.started else None,
                'stopped': task.stopped.isoformat() if task.stopped else None,
            })
            failure_count += 1
            if failure_count >= 5:
                break

        # Sort by stopped time  
        results.sort(key=lambda x: x.get('stopped') or '', reverse=True)

        return Response({
            'tasks': results[:20],
            'total_success': success_count,
            'total_failed': failure_count,
        })

class ReevaluateOrderView(APIView):
    """
    POST: Manually trigger the AI Agent evaluation for a specific order number.
    Expects {"order_number": "12345"}
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'analytics_reporting:analytics:create'
    }
    def post(self, request):
        order_number = request.data.get('order_number')
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found."}, status=400)
            
        if not order_number:
            return Response({"error": "Order number is required."}, status=400)

        from core.models import Order
        from django_q.tasks import async_task
        
        try:
            # Handle both string (e.g. "#12345") and int formats
            if isinstance(order_number, str) and order_number.startswith('#'):
                order_number = order_number[1:]
                
            order = Order.objects.filter(order_number=order_number, org_id=org_id).first()
            if not order:
                return Response({"error": f"Order #{order_number} not found in the database."}, status=404)
            
            # Trigger the standard task via Django-Q
            # We set attempt=3 to force the agent to run even if PII is missing
            async_task('core.tasks.evaluate_order_task', order.id, 3)
            
            return Response({
                "message": f"Successfully queued order #{order_number} for evaluation. Check the activity log in a few seconds."
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class AnalyticsAgentConfigurationView(APIView):
    permission_classes = [IsOrganizationOwner]
    """
    GET: Returns the active AnalyticsAgentConfiguration (or creates a default one if none exists).
    PUT: Updates the active AnalyticsAgentConfiguration.
    """

    def get(self, request):
        from core.models import AnalyticsAgentConfiguration
        from core.serializers import AnalyticsAgentConfigurationSerializer
        config = AnalyticsAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            # Create default if missing
            default_prompt = (
                "You are Thorfinn, the BridgeWorks Data Analyst. You answer questions about the database. "
                "You have access to the following tables: 'core_order', 'core_lineitem', 'core_fulfillment' and 'core_casefile'.\n"
                "Always return the final answer in a friendly, conversational tone.\n\n"
                "CRITICAL INSTRUCTIONS FOR DATE AND TIME QUERIES:\n"
                "- All dates in the database are stored in naive UTC format.\n"
                "- When calculating 'today' or any specific date, you MUST account for the Asia/Kolkata timezone (+05:30).\n"
                "- Example: Today in IST is DATE('now', '+5 hours', '+30 minutes').\n"
                "- Query ranges for 'today' must filter created_at correctly using modifiers.\n\n"
                "CRITICAL INSTRUCTIONS FOR PAYMENT TYPES (COD vs PREFIX vs PPCOD):\n"
                "- The column `payment_gateway_names` (JSON array) determines the payment type.\n"
                "- \"Cash on Delivery\" (COD): If the array contains 'Cash on Delivery (COD)', 'cash_on_delivery', or 'CASH ON DELIVERY'.\n"
                "- \"Partially Paid\" (PPCOD): If the array contains 'Gokwik PPCOD'.\n"
                "- \"Prepaid\": If it's NOT COD and NOT PPCOD (e.g., contains Razorpay, Gokwik UPI, Wallets, Cards).\n"
                "- Do NOT use financial_status to determine COD/Prepaid. financial_status=\"pending\" does not mean COD.\n\n"
                "CRITICAL INSTRUCTIONS FOR DELIVERY STATUS:\n"
                "- The `current_status` column in `core_order` dictates the delivery state.\n"
                "- An order is \"Delivered\" successfully if `current_status` starts with 'Delivered' (case-insensitive) OR equals 'DELIVERED', AND does NOT contain 'RTO'.\n"
                "- An order is \"RTO\" (Returned to Origin) if `current_status` contains 'RTO'.\n\n"
                "Do not expose raw SQL to the user unless they ask.\n"
                "If you cannot answer the question, or if it asks to modify/delete data, politely decline."
            )
            config = AnalyticsAgentConfiguration.objects.create(
                name="Default Thorfinn Config",
                system_prompt=default_prompt,
                model_name="gemini-2.5-flash-lite"
            )
        serializer = AnalyticsAgentConfigurationSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        from core.models import AnalyticsAgentConfiguration
        from core.serializers import AnalyticsAgentConfigurationSerializer
        config = AnalyticsAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            return Response({"error": "No active configuration found."}, status=404)
        
        serializer = AnalyticsAgentConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class MarketingAgentConfigurationView(APIView):
    permission_classes = [IsOrganizationOwner]
    """
    GET: Returns the active MarketingAgentConfiguration (or creates a default one if none exists).
    PUT: Updates the active MarketingAgentConfiguration.
    """

    def get(self, request):
        from core.models import MarketingAgentConfiguration
        from core.serializers.intelligence import MarketingAgentConfigurationSerializer

        config = MarketingAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            # Default Prompt logic fetched from original code
            default_audit_prompt = (
                "You are an expert performance marketing analyst for an Indian D2C brand.\n"
                "Analyze the provided Meta Ads data (Campaign, AdSet, and Ad level) meticulously.\n"
                "Identify top performers, areas of improvement, and the most effective creatives.\n\n"
                "Provide your response strictly as valid JSON with these exact keys:\n"
                "{\n"
                "    \"summary\": \"A 3-5 sentence executive summary of the overall performance during this period.\",\n"
                "    \"key_metrics\": {\n"
                "        \"total_spend\": 250000, \"total_revenue\": 1000000,\n"
                "        \"overall_roas\": 4.0, \"avg_cpa\": 300, \"total_purchases\": 830\n"
                "    },\n"
                "    \"best_campaigns\": [\n"
                "        {\"name\": \"campaign name\", \"reason\": \"Specific data-backed reason for success (e.g. high CVR)\", \"roas\": 5.2, \"spend\": 50000}\n"
                "    ],\n"
                "    \"worst_campaigns\": [\n"
                "        {\"name\": \"campaign name\", \"reason\": \"Why this campaign is underperforming\", \"roas\": 0.3, \"spend\": 20000}\n"
                "    ],\n"
                "    \"audience_insights\": \"Detailed analysis of audience performance. Which AdSets are performing best?\",\n"
                "    \"ad_level_insights\": \"Deep dive into the ads. Which creative is driving the most value?\",\n"
                "    \"funnel_bottlenecks\": \"Where is the funnel falling off? (VC -> ATC -> IC -> Purchase). Identify points of friction.\",\n"
                "    \"ad_fatigue_warnings\": \"Identify ads that are experiencing ad fatigue (dropping CTRs/high CPCs).\",\n"
                "    \"scaling_opportunities\": \"Concrete, data-backed recommendations on which campaigns/ads to scale.\",\n"
                "    \"budget_recommendations\": [\n"
                "        {\"action\": \"INCREASE\", \"target_name\": \"Campaign or AdSet name\", \"reason\": \"Why this budget should be increased\"},\n"
                "        {\"action\": \"DECREASE\", \"target_name\": \"Campaign or AdSet name\", \"reason\": \"Why this budget should be decreased\"}\n"
                "    ]\n"
                "}\n\n"
                "Rules:\n"
                "- All monetary values are in Indian Rupees (₹).\n"
                "- Use specific names from the JSON.\n"
                "- Output ONLY valid JSON, no markdown formatting.\n"
                "- The response MUST parse directly via json.loads()."
            )
            
            default_general_prompt = (
                "You currently have NO data payload loaded.\n"
                "1. If they ask for metrics, request that they specify a timeframe (e.g. 'for Today' or 'for the Last 30 Days') so you can fetch the adequate data.\n"
                "2. Example response: \"I would be happy to check that for you, but I need a timeframe (like Today or the Last 7 Days) to pull the correct data.\"\n"
                "3. You can still give general performance marketing advice or creative strategies."
            )
            config = MarketingAgentConfiguration.objects.create(
                name="Default Marketing Aura Config",
                system_prompt=default_audit_prompt,
                general_prompt=default_general_prompt,
                model_name="gemini-2.5-pro"
            )
        serializer = MarketingAgentConfigurationSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        from core.models import MarketingAgentConfiguration
        from core.serializers.intelligence import MarketingAgentConfigurationSerializer

        config = MarketingAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            return Response({"error": "No active configuration found."}, status=404)
        
        serializer = MarketingAgentConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class LogisticsAgentConfigurationView(APIView):
    permission_classes = [IsOrganizationOwner]
    """
    GET: Returns the active LogisticsAgentConfiguration (or creates a default one).
    PUT: Updates the active LogisticsAgentConfiguration.
    """

    def get(self, request):
        from core.models import LogisticsAgentConfiguration
        from core.serializers.intelligence import LogisticsAgentConfigurationSerializer

        config = LogisticsAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            default_system_prompt = (
                "You are an elite logistics analyst for an Indian D2C brand.\n"
                "Analyze the provided logistics data meticulously.\n"
                "Identify delivery performance issues, NDR patterns, RTO drivers, COD reconciliation gaps, and shipping cost anomalies.\n\n"
                "When producing a full report, respond strictly as valid JSON with these exact keys:\n"
                "{\n"
                "    \"summary\": \"A 3-5 sentence executive summary of logistics performance.\",\n"
                "    \"key_metrics\": {\n"
                "        \"total_orders\": 1000, \"delivered\": 800, \"delivery_rate\": 80.0,\n"
                "        \"rto\": 100, \"rto_rate\": 10.0, \"ndr\": 80, \"ndr_rate\": 8.0,\n"
                "        \"cod_orders\": 600, \"cod_pct\": 60.0\n"
                "    },\n"
                "    \"ndr_insights\": \"Analysis of NDR patterns — which couriers have highest NDR, most common reasons.\",\n"
                "    \"rto_drivers\": \"What's driving RTO — geography, courier, product category, fake address patterns.\",\n"
                "    \"delivery_trends\": \"Day-over-day or week-over-week delivery rate trends.\",\n"
                "    \"courier_performance\": \"Which couriers are outperforming / underperforming on delivery rate and SLA.\",\n"
                "    \"cost_analysis\": \"Shipping cost per order, excess weight charges, zone-wise cost breakdown.\",\n"
                "    \"problem_locations\": [\n"
                "        {\"pincode\": \"110001\", \"city\": \"Delhi\", \"issue\": \"High NDR — fake address\", \"orders\": 15}\n"
                "    ],\n"
                "    \"recommendations\": [\n"
                "        {\"action\": \"SWITCH_COURIER\", \"target\": \"Courier name\", \"reason\": \"NDR rate > 20%\"},\n"
                "        {\"action\": \"BLACKLIST_PINCODE\", \"target\": \"560001\", \"reason\": \"High RTO, 0% delivery rate\"}\n"
                "    ]\n"
                "}\n\n"
                "Rules:\n"
                "- All monetary values are in Indian Rupees (₹).\n"
                "- Delivery Rate benchmark: 85%. RTO benchmark: 12%. NDR benchmark: 8%.\n"
                "- Output ONLY valid JSON when producing a report, no markdown formatting.\n"
                "- The response MUST parse directly via json.loads()."
            )
            default_general_prompt = (
                "You currently have NO logistics data payload loaded.\n"
                "1. If they ask for metrics, request that they specify a timeframe so you can fetch the data.\n"
                "2. Example: 'I'd love to check that — just tell me a timeframe (Today, Last 7 Days, etc.) to pull the right data.'\n"
                "3. You can still give general logistics strategy advice (NDR reduction, RTO prevention, courier selection)."
            )
            config = LogisticsAgentConfiguration.objects.create(
                name="Default Logistics Aura Config",
                system_prompt=default_system_prompt,
                general_prompt=default_general_prompt,
                model_name="gemini-2.5-flash-lite"
            )
        serializer = LogisticsAgentConfigurationSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        from core.models import LogisticsAgentConfiguration
        from core.serializers.intelligence import LogisticsAgentConfigurationSerializer

        config = LogisticsAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            return Response({"error": "No active configuration found."}, status=404)

        serializer = LogisticsAgentConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class ServiceAgentConfigurationView(APIView):
    permission_classes = [IsOrganizationOwner]
    """
    GET: Returns the active ServiceAgentConfiguration (or creates a default one).
    PUT: Updates the active ServiceAgentConfiguration.
    """

    def get(self, request):
        from core.models import ServiceAgentConfiguration
        from core.serializers.intelligence import ServiceAgentConfigurationSerializer

        config = ServiceAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            default_system_prompt = (
                "You are a professional, polite, and helpful Customer Service Agent for an Indian e-commerce company.\n"
                "Your role is to assist customers with tracking order status, managing refunds, handling cancellations, "
                "addressing delivery complaints, and answering general store policies.\n\n"
                "When responding, adhere to these guidelines:\n"
                "1. Core Communication Rules:\n"
                "   - Be polite, warm, helpful, and concise.\n"
                "   - Always address the customer with respect.\n"
                "   - Keep answers straightforward; do not overwhelm customers with dry technical details.\n\n"
                "2. Specific Policies & Actions:\n"
                "   - Tracking Status: Check the current status of order and shipping updates. If an order is delivered, "
                "     confirm delivery. If it's in transit, explain estimated delivery times (normally 3-5 business days).\n"
                "   - NDR/Delays: If the order delivery is delayed or has experienced a non-delivery report (NDR), reassure "
                "     the customer that you will contact the logistics team and get their order delivered as a priority.\n"
                "   - Cancellations: If the customer requests cancellation before shipment, process it immediately. If the "
                "     order is already shipped, explain that they can refuse delivery at their doorstep, and a refund will "
                "     be processed upon arrival at our warehouse.\n"
                "   - Refunds: For Cash on Delivery (COD) orders, ask for their bank details or UPI ID to initiate the refund. "
                "     For Prepaid orders, inform them that the refund will be credited back to the original payment source "
                "     within 5-7 business days.\n\n"
                "3. Response Structure:\n"
                "   - Start with a pleasant greeting.\n"
                "   - Address their direct question with clear bullet points or short paragraphs.\n"
                "   - Finish with a warm and supportive sign-off."
            )
            default_general_prompt = (
                "You currently have NO customer/order payload loaded.\n"
                "1. Politely ask the customer to provide their order number, tracking number, or registered email address so you can pull up their details.\n"
                "2. Example response: \"I would be glad to look into that for you! Could you please provide your order number or tracking number so I can check your status?\"\n"
                "3. You can still answer general FAQs about delivery times, returns, and refund durations without a payload loaded."
            )
            config = ServiceAgentConfiguration.objects.create(
                name="Default Service Aura Config",
                system_prompt=default_system_prompt,
                general_prompt=default_general_prompt,
                model_name="gemini-2.5-flash-lite"
            )
        serializer = ServiceAgentConfigurationSerializer(config)
        return Response(serializer.data)

    def put(self, request):
        from core.models import ServiceAgentConfiguration
        from core.serializers.intelligence import ServiceAgentConfigurationSerializer

        config = ServiceAgentConfiguration.objects.filter(is_active=True).first()
        if not config:
            return Response({"error": "No active configuration found."}, status=404)

        serializer = ServiceAgentConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class MergeLabelsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import io
        import requests
        from PyPDF2 import PdfMerger
        from core.models import Order
        
        order_ids = request.data.get('order_ids', [])
        if not order_ids:
            return Response({"error": "No order IDs provided"}, status=400)
            
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization not found"}, status=400)

        orders = Order.objects.filter(id__in=order_ids, org_id=org_id)
        
        merger = PdfMerger()
        has_pdfs = False
        
        for order in orders:
            label_url = None
            for f in order.fulfillments.all():
                for t in f.tracking_info.all():
                    if t.url:
                        label_url = t.url
                        break
                if label_url:
                    break
            
            if not label_url:
                continue
                
            try:
                resp = requests.get(label_url, timeout=15)
                if resp.ok:
                    merger.append(io.BytesIO(resp.content))
                    has_pdfs = True
            except Exception as e:
                print(f"Error downloading PDF from {label_url}: {e}")
                
        if not has_pdfs:
            return Response({"error": "No valid labels found to download"}, status=400)
            
        merged_pdf = io.BytesIO()
        merger.write(merged_pdf)
        merged_pdf.seek(0)
        
        response = HttpResponse(merged_pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="merged_labels.pdf"'
        return response
