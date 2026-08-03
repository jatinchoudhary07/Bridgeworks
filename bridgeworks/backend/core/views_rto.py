from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.permissions import HasModulePermission
from rest_framework import status
from django.utils import timezone
from django.db.models import Q
from .models import Order, RTOBatch, LineItem, TrackingInfo

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

class RTOReceiveScanView(APIView):
    """
    Handles scanning of RTO packets at the warehouse gate.
    CRITICAL: Checks for 'Cross-Docking' requirements.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'rto_module:rto_in_transit:create'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        scan_input = request.data.get('scan_input', '').strip()
        if not scan_input:
            return Response({"error": "Scan input is required"}, status=400)

        # 1. Find the Order (by AWB or Order Number or Tracking Number or Shopify ID)
        # Check tracking_number in fulfillments OR order_number OR shopify_id
        # We need to be flexible as users might scan any barcode on the box
        
        # Try finding by Order Number first (fastest)
        order = None
        if scan_input.isdigit():
             order = Order.objects.filter(order_number=scan_input, org_id=org_id).first()
        
        if not order:
             # Try tracking number in fulfillments (fast index-based lookup)
             ti = TrackingInfo.objects.filter(
                 Q(number=scan_input) | Q(number=scan_input.upper())
             ).select_related('fulfillment__order').filter(fulfillment__order__org_id=org_id).first()
             if ti:
                 order = ti.fulfillment.order
             else:
                 # Fallback to slow case-insensitive lookup
                 ti_fallback = TrackingInfo.objects.filter(
                     number__iexact=scan_input
                 ).select_related('fulfillment__order').filter(fulfillment__order__org_id=org_id).first()
                 if ti_fallback:
                     order = ti_fallback.fulfillment.order
        
        if not order:
             return Response({"error": "Order not found. Please check the AWB or Order ID."}, status=404)

        # 1.5 Check if already scanned
        if order.rto_internal_status != 'Pending':
             # Allow re-scanning if status is 'Received' AND it hasn't been batched yet
             # This handles the case where user refreshes the page and loses their "session list"
             if order.rto_internal_status == 'Received' and not order.rto_batch:
                 pass # Proceed to return success (idempotent)
             else:
                 return Response({
                     "error": f"Order #{order.order_number} is already {order.rto_internal_status}!",
                     "order": {
                        "id": order.id,
                        "order_number": order.order_number,
                        "status": order.rto_internal_status,
                        "customer": f"{order.customer_first_name} {order.customer_last_name}",
                     }
                 }, status=400)

        # 2. Update RTO Status
        # Start tracking the internal movement
        order.rto_internal_status = 'Received'
        order.rto_received_at = timezone.now()
        order.save()

        # 3. Cross-Dock Alert Logic (The "Killer Feature")
        # Optimization: Check if any PENDING order needs the items inside this returned packet.
        urgent_requirement = False
        urgent_reason = ""
        
        # Get SKUs in this return
        # Adjust related_name if needed based on models.py, assuming 'line_items'
        returned_items = order.line_items.all()
        returned_skus = [item.sku for item in returned_items if item.sku]

        if returned_skus:
            # Search for other orders that are PENDING and need these SKUs
            # Exclude the current order itself obviously
            pending_orders = Order.objects.filter(
                org_id=org_id,
                status='Pending',
                fulfillment_status__in=[None, '', 'Unfulfilled', 'unfulfilled'],
                line_items__sku__in=returned_skus
            ).exclude(id=order.id).distinct()

            if pending_orders.exists():
                urgent_requirement = True
                count = pending_orders.count()
                first_match = pending_orders.first()
                urgent_reason = f"⚠️ CROSS-DOCK ALERT: This item is needed for {count} pending orders! (e.g. Order #{first_match.order_number})"

        # 4. Serialize Response
        # Return necessary details for the UI card
        return Response({
            "message": "Order Received",
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "customer": f"{order.customer_first_name} {order.customer_last_name}",
                "status": order.rto_internal_status,
                "received_at": order.rto_received_at,
                "created_at": order.created_at,
                "line_items": [{"sku": i.sku, "name": i.name, "quantity": i.quantity} for i in returned_items],
                "urgent_requirement": urgent_requirement,
                "urgent_reason": urgent_reason
            }
        })

class RTOBatchCreateView(APIView):
    """
    Groups 'Received' orders into a physical 'Batch' for unpacking.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'rto_module:rto_in_transit:create'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        order_ids = request.data.get('order_ids', [])
        if not order_ids:
            return Response({"error": "No orders selected for batching"}, status=400)

        # Generate Batch Name (e.g., RTO-YYYYMMDD-01)
        today_str = timezone.now().strftime('%Y%m%d')
        # Simple counter for batch suffix
        count = RTOBatch.objects.filter(org_id=org_id, name__startswith=f"RTO-{today_str}").count()
        batch_name = f"RTO-{today_str}-{count + 1:02d}"

        # Create Batch
        batch = RTOBatch.objects.create(
            name=batch_name,
            org_id=org_id,
            created_by=request.user,
            status='Open'
        )

        # Link Orders to Batch and update status
        orders_to_update = Order.objects.filter(id__in=order_ids, org_id=org_id)
        updated_count = orders_to_update.update(rto_batch=batch, rto_internal_status='Batched')

        return Response({
            "message": f"Batch {batch.name} created successfully with {updated_count} orders.",
            "batch_id": batch.id,
            "batch_name": batch.name
        })

class RTOUnpackListView(APIView):
    """
    Lists 'Open' batches and their contents for the Unpacking Station.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'rto_module:rto_manager:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        # 1. Get Open Batches
        batches = RTOBatch.objects.filter(org_id=org_id, status='Open').order_by('-created_at')
        
        data = []
        for batch in batches:
            # Get orders in this batch
            # Prefetch line_items for display
            orders_in_batch = batch.orders.all().prefetch_related('line_items')
            
            batch_data = {
                "id": batch.id,
                "name": batch.name,
                "created_at": batch.created_at,
                "created_by": batch.created_by.email if batch.created_by else "Unknown",
                "status": batch.status,
                "orders": []
            }

            for o in orders_in_batch:
                batch_data["orders"].append({
                    "id": o.id,
                    "order_number": o.order_number,
                    "customer": f"{o.customer_first_name} {o.customer_last_name}",
                    "created_at": o.created_at,
                    "rto_internal_status": o.rto_internal_status,
                    "rto_remarks": o.rto_remarks,
                    "line_items": [{"sku": i.sku, "name": i.name, "quantity": i.quantity} for i in o.line_items.all()]
                })
            
            data.append(batch_data)
            
        return Response(data)

class RTORestockActionView(APIView):
    """
    Handles the final action: Restock (Good Condition) or Discard (Bad Condition).
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'rto_module:rto_manager:edit'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        order_id = request.data.get('order_id')
        action = request.data.get('action') # 'Restock' or 'Discard'
        remarks = request.data.get('remarks', '')

        if not order_id or action not in ['Restock', 'Discard', 'Update Remarks']:
            return Response({"error": "Invalid input. Action must be Restock, Discard, or Update Remarks."}, status=400)

        try:
            order = Order.objects.get(id=order_id, org_id=org_id)
            
            # Action Logic
            if action == 'Restock':
                order.rto_internal_status = 'Restocked'
                order.rto_restocked_at = timezone.now()
                # FUTURE: Trigger Inventory Increment here
            elif action == 'Discard':
                order.rto_internal_status = 'Discarded'
                # Remarks mandatory for discard? Optional for now.
            elif action == 'Update Remarks':
                pass # Just update remarks
            
            order.rto_remarks = remarks
            order.save()

            # Check if Batch is fully processed
            if order.rto_batch:
                batch = order.rto_batch
                # Check if any orders in this batch are NOT yet processed (i.e., still Batched/Unpacked/Pending/Received)
                # 'Restocked' and 'Discarded' are the terminal states
                pending_in_batch = batch.orders.exclude(rto_internal_status__in=['Restocked', 'Discarded']).exists()
                
                if not pending_in_batch:
                    batch.status = 'Processed'
                    batch.save()
                    batch_completed = True
                else:
                    batch_completed = False

            return Response({
                "message": f"Order {action}ed successfully.",
                "status": order.rto_internal_status,
                "batch_completed": batch_completed if order.rto_batch else False
            })

        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
