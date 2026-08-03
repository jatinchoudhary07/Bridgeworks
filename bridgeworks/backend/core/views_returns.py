import json
import hmac
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_q.tasks import async_task
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.paginator import Paginator
from django.db.models import Q
from .models import ReturnRequest

def _get_org_id(request):
    """Resolve org_id from the authenticated user."""
    user = request.user
    if not user.is_authenticated:
        return None
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    if hasattr(user, 'team_settings') and user.team_settings.organization:
        return user.team_settings.organization.organization_id
    return None

class ReturnPrimeWebhookView(APIView):
    """
    Webhook receiver for Return Prime events.
    Returns 200 OK immediately and processes the payload asynchronously.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            expected_secret = getattr(settings, 'RETURN_PRIME_WEBHOOK_SECRET', '')
            if expected_secret:
                incoming_secret = request.headers.get('X-Return-Prime-Secret', '')
                if not incoming_secret or not hmac.compare_digest(expected_secret, incoming_secret):
                    return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

            payload = json.loads(request.body)
            # Dispatch to background task to prevent webhook timeout
            async_task('core.tasks.process_return_prime_webhook', payload)
            return Response({"status": "received"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

def _serialize_return_request(req):
    order = req.order
    db_awb = req.awb_number
    db_courier = None
    db_customer = None
    
    if order:
        if not db_awb:
            db_awb = order.awb_number
            
        tf = order.fulfillments.first()
        if tf and tf.service:
            db_courier = tf.service
            
        customer_name = ""
        if order.customer:
            customer_name = order.customer.name
        elif order.customer_first_name:
            customer_name = f"{order.customer_first_name} {order.customer_last_name or ''}".strip()
            
        db_customer = {
            "name": customer_name,
            "email": order.contact_email or (order.customer.email if order.customer else ""),
            "phone": order.contact_phone or (order.customer.phone if order.customer else ""),
            "address": order.shipping_address or (order.customer.address if order.customer else "")
        }

    stocked_by_name = None
    if req.stocked_by:
        stocked_by_name = f"{req.stocked_by.first_name} {req.stocked_by.last_name}".strip() or req.stocked_by.username

    return {
        "id": req.id,
        "return_prime_id": req.return_prime_id,
        "order_number": req.order.order_number if req.order else None,
        "status": req.status,
        "request_type": req.request_type,
        "awb_number": db_awb,
        "logistic_partner": db_courier,
        "refund_amount": str(req.refund_amount),
        "customer_notes": req.customer_notes,
        "created_at": req.created_at.isoformat(),
        "raw_data": req.raw_data,
        "db_customer": db_customer,
        "stocked_by": stocked_by_name,
        "stocked_at": req.stocked_at.isoformat() if req.stocked_at else None
    }

class ReturnRequestListView(APIView):
    """
    API to list ReturnRequests with filtering and pagination.
    Query params:
    - type: RETURN | EXCHANGE (default: RETURN)
    - status: ALL | REQUEST_CREATED | APPROVED | ...
    - search: string (AWB, Order Number)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        req_type = request.query_params.get('type', 'RETURN').upper()
        status_filter = request.query_params.get('status', 'ALL').upper()
        search_query = request.query_params.get('search', '').strip()
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 25))

        org_id = _get_org_id(request)
        qs = ReturnRequest.objects.select_related('order', 'order__customer').prefetch_related('order__fulfillments', 'order__fulfillments__tracking_info').filter(request_type=req_type, order__org_id=org_id)

        if status_filter != 'ALL':
            if status_filter in ['REQUEST_CREATED', 'REQUESTED']:
                qs = qs.filter(Q(status='REQUEST_CREATED') | Q(status='REQUESTED'))
            else:
                qs = qs.filter(status=status_filter)
            
        if search_query:
            qs = qs.filter(
                Q(awb_number__icontains=search_query) | 
                Q(order__order_number__icontains=search_query) |
                Q(return_prime_id__icontains=search_query) |
                Q(raw_data__icontains=search_query)
            )

        qs = qs.order_by('-created_at')
        
        paginator = Paginator(qs, limit)
        page_obj = paginator.get_page(page)
        
        data = [_serialize_return_request(req) for req in page_obj]
            
        return Response({
            "results": data,
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page
        }, status=status.HTTP_200_OK)

class ReturnScannerView(APIView):
    """
    API for warehouse scanner to fetch returns by AWB.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        awb_number = request.data.get('awb_number')
        if not awb_number:
            return Response({"error": "AWB number is required"}, status=status.HTTP_400_BAD_REQUEST)

        org_id = _get_org_id(request)
        try:
            # 1. Direct AWB match
            return_reqs = list(ReturnRequest.objects.select_related('order', 'order__customer').prefetch_related('order__fulfillments', 'order__fulfillments__tracking_info').filter(awb_number=awb_number, order__org_id=org_id))
            
            # 2. Global TrackingInfo fallback (if the AWB was synced as an order fulfillment)
            if not return_reqs:
                from core.models import TrackingInfo
                tracking = TrackingInfo.objects.filter(number=awb_number, fulfillment__order__org_id=org_id).select_related('fulfillment__order').first()
                if tracking:
                    # Find if this order has a Return/Exchange
                    return_reqs = list(ReturnRequest.objects.filter(order=tracking.fulfillment.order, order__org_id=org_id).order_by('-created_at'))
                    
            # 3. Finally, search raw_data payload just in case it's buried in the JSON
            if not return_reqs:
                return_reqs = list(ReturnRequest.objects.filter(raw_data__icontains=awb_number, order__org_id=org_id))

            if return_reqs:
                valid_reqs = []
                for req in return_reqs:
                    # Filter out ghost entries created by the CSV import (where SKU is empty)
                    if req.return_prime_id and str(req.return_prime_id).startswith('CSV-'):
                        raw = req.raw_data.get('request', req.raw_data) if isinstance(req.raw_data, dict) else {}
                        line_items = raw.get('line_items', [])
                        if line_items and isinstance(line_items, list):
                            sku = line_items[0].get('original_product', {}).get('sku', '')
                            if not sku:
                                continue  # Skip this ghost entry
                    valid_reqs.append(req)

                if valid_reqs:
                    data = [_serialize_return_request(req) for req in valid_reqs]
                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response({"error": "No valid return requests found for this AWB"}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({"error": "No return requests found for this AWB"}, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.utils import timezone

class ReturnActionStockView(APIView):
    """
    Marks a ReturnRequest as RECEIVED & INSPECTED.
    Logs the user who performed the action and the exact time.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        request_ids = request.data.get('request_ids', [])
        
        if not request_ids or not isinstance(request_ids, list):
            return Response({"error": "A list of 'request_ids' is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        org_id = _get_org_id(request)
        # Valid requests
        return_reqs = ReturnRequest.objects.filter(return_prime_id__in=request_ids, order__org_id=org_id)
        
        if not return_reqs.exists():
            return Response({"error": "No valid requests found for the provided IDs"}, status=status.HTTP_404_NOT_FOUND)
        
        # Bulk Update
        now = timezone.now()
        for return_req in return_reqs:
            return_req.status = 'INSPECTED'
            return_req.stocked_by = request.user
            return_req.stocked_at = now
            
        ReturnRequest.objects.bulk_update(return_reqs, ['status', 'stocked_by', 'stocked_at'])
        
        return Response({
            "success": True, 
            "message": f"Successfully Received & Inspected {return_reqs.count()} items.",
            "data": [_serialize_return_request(req) for req in return_reqs]
        }, status=status.HTTP_200_OK)

class ReturnStockingListView(APIView):
    """
    Returns only ReturnRequests that have been marked as stocked (stocked_at is not null).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        org_id = _get_org_id(request)
        page = int(request.GET.get('page', 0)) + 1
        page_size = int(request.GET.get('page_size', 25))
        
        qs = ReturnRequest.objects.filter(order__org_id=org_id).exclude(stocked_at__isnull=True).order_by('-stocked_at')
        
        paginator = Paginator(qs, per_page=page_size)
        try:
            current_page_data = paginator.page(page)
        except Exception:
            return Response({"data": [], "total_count": paginator.count}, status=status.HTTP_200_OK)
            
        data = [_serialize_return_request(req) for req in current_page_data.object_list]
        
        return Response({
            "data": data,
            "total_count": paginator.count
        }, status=status.HTTP_200_OK)
