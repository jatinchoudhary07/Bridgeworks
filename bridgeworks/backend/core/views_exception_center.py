"""
views_exception_center.py — Exception Management Center API
===========================================================
Endpoints for the Exception Management Center enterprise feature.

Endpoints:
    GET    /api/logistics/exceptions/             → Paginated list (filterable)
    POST   /api/logistics/exceptions/             → Create exception
    GET    /api/logistics/exceptions/summary/     → Dashboard KPIs
    POST   /api/logistics/exceptions/auto-detect/ → Trigger auto-detection
    GET    /api/logistics/exceptions/<pk>/        → Exception detail (with audit trail)
    PATCH  /api/logistics/exceptions/<pk>/        → Update status/assign/notes (appends audit trail)
"""
import logging
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone

from core.permissions import HasModulePermission
from core.models.delivery import Shipment, ShipmentException
from core.services.exception_service import auto_detect_exceptions, get_exception_summary
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS = {
    'Open': ['InvestigationPending', 'Closed', 'Rejected'],
    'InvestigationPending': ['ResolutionPending', 'Closed', 'Rejected'],
    'ResolutionPending': ['ClaimRecovery', 'Closed', 'Rejected'],
    'ClaimRecovery': ['Closed', 'Rejected'],
    'Closed': [],
    'Rejected': [],
}


def _serialize_exception(exc) -> dict:
    return {
        'id': exc.id,
        'shipment': {
            'id': exc.shipment_id,
            'awb_number': exc.shipment.awb_number,
            'courier_partner': exc.shipment.courier_partner,
            'current_stage': exc.shipment.current_stage,
            'order_number': exc.shipment.order.order_number if exc.shipment.order else None,
        },
        'exception_type': exc.exception_type,
        'status': exc.status,
        'description': exc.description,
        'assigned_to': exc.assigned_to.get_full_name() if exc.assigned_to else None,
        'assigned_to_id': exc.assigned_to_id,
        'claim_amount': float(exc.claim_amount),
        'recovered_amount': float(exc.recovered_amount),
        'notes': exc.notes,
        'is_auto_detected': exc.is_auto_detected,
        'detected_at': exc.detected_at.isoformat(),
        'resolved_at': exc.resolved_at.isoformat() if exc.resolved_at else None,
        'audit_trail': exc.audit_trail if exc.audit_trail else [],
    }


class ExceptionListCreateView(APIView):
    """
    GET  /api/logistics/exceptions/   → Paginated exception list
    POST /api/logistics/exceptions/   → Create exception manually
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:exception_center:view',
        'POST': 'logistics:exception_center:manage',
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        qs = ShipmentException.objects.filter(org_id=org_id).select_related(
            'shipment', 'shipment__order', 'assigned_to'
        )

        # Filters
        exc_type = request.query_params.get('exception_type')
        status_filter = request.query_params.get('status')
        courier = request.query_params.get('courier')
        is_auto = request.query_params.get('is_auto_detected')
        awb = request.query_params.get('awb')
        q = request.query_params.get('q', '').strip()

        if exc_type:
            qs = qs.filter(exception_type=exc_type)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if courier:
            qs = qs.filter(shipment__courier_partner__icontains=courier)
        if is_auto in ('true', '1'):
            qs = qs.filter(is_auto_detected=True)
        elif is_auto in ('false', '0'):
            qs = qs.filter(is_auto_detected=False)
        if awb:
            qs = qs.filter(shipment__awb_number__icontains=awb)
        if q:
            qs = qs.filter(shipment__awb_number__icontains=q) | \
                 ShipmentException.objects.filter(org_id=org_id, shipment__order__order_number__icontains=q).select_related('shipment', 'shipment__order', 'assigned_to')

        # Pagination
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, int(request.query_params.get('page_size', 20)))
        total = qs.count()
        offset = (page - 1) * page_size
        exceptions = qs.order_by('-detected_at')[offset: offset + page_size]

        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
            'results': [_serialize_exception(e) for e in exceptions],
        })

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        d = request.data
        required = ['shipment_id', 'exception_type']
        missing = [f for f in required if not d.get(f)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=400)

        try:
            shipment = Shipment.objects.get(id=d['shipment_id'], org_id=org_id)
        except Shipment.DoesNotExist:
            return Response({'error': 'Shipment not found'}, status=404)

        exc_type = d['exception_type']
        valid_types = [t[0] for t in ShipmentException.EXCEPTION_TYPE_CHOICES]
        if exc_type not in valid_types:
            return Response({'error': f'Invalid exception_type. Valid: {valid_types}'}, status=400)

        actor_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else 'System'

        initial_trail_entry = {
            'timestamp': timezone.now().isoformat(),
            'actor': actor_name,
            'from_status': None,
            'to_status': 'Open',
            'notes': d.get('description', 'Exception logged manually.'),
            'recovered_amount': 0,
        }

        try:
            exc = ShipmentException.objects.create(
                org_id=org_id,
                shipment=shipment,
                exception_type=exc_type,
                status='Open',
                description=d.get('description', ''),
                claim_amount=d.get('claim_amount', 0),
                notes=d.get('notes', ''),
                is_auto_detected=False,
                audit_trail=[initial_trail_entry],
            )
            return Response(_serialize_exception(exc), status=201)
        except Exception as e:
            logger.error(f"[EXCEPTION-CENTER] Create failed: {e}")
            return Response({'error': str(e)}, status=400)


class ExceptionSummaryView(APIView):
    """
    GET /api/logistics/exceptions/summary/

    Returns dashboard KPIs: counts by type, by status, total open,
    total claim amount, total recovered, recovery rate.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:exception_center:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        return Response(get_exception_summary(org_id))


class ExceptionAutoDetectView(APIView):
    """
    POST /api/logistics/exceptions/auto-detect/

    Triggers the auto-detection scan immediately (on-demand).
    Also available as a scheduled Celery task.

    Returns:
        { created: int, skipped: int }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'logistics:exception_center:manage'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            created, skipped = auto_detect_exceptions(org_id)
            return Response({
                'message': f'Auto-detection complete. {created} exceptions created, {skipped} skipped.',
                'created': created,
                'skipped': skipped,
            })
        except Exception as e:
            logger.error(f"[EXCEPTION-CENTER] Auto-detect failed for org {org_id}: {e}")
            return Response({'error': str(e)}, status=500)


class ExceptionDetailView(APIView):
    """
    GET   /api/logistics/exceptions/<pk>/   → Exception detail (includes audit_trail)
    PATCH /api/logistics/exceptions/<pk>/   → Update status / assign / add notes
                                              Each PATCH appends a new audit trail entry.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:exception_center:view',
        'PATCH': 'logistics:exception_center:manage',
    }

    def _get_exception(self, org_id, pk):
        try:
            return ShipmentException.objects.select_related(
                'shipment', 'shipment__order', 'assigned_to'
            ).get(id=pk, org_id=org_id)
        except ShipmentException.DoesNotExist:
            return None

    def get(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        exc = self._get_exception(org_id, pk)
        if not exc:
            return Response({'error': 'Exception not found'}, status=404)

        return Response(_serialize_exception(exc))

    def patch(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        exc = self._get_exception(org_id, pk)
        if not exc:
            return Response({'error': 'Exception not found'}, status=404)

        d = request.data
        update_fields = []
        actor_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else 'Agent'

        # Build audit trail entry
        trail_entry = {
            'timestamp': timezone.now().isoformat(),
            'actor': actor_name,
            'from_status': exc.status,
            'to_status': exc.status,  # may be overridden below
            'notes': d.get('notes', exc.notes or ''),
            'recovered_amount': float(d.get('recovered_amount', exc.recovered_amount or 0)),
        }

        # Status transition
        if 'status' in d:
            new_status = d['status']
            allowed = VALID_TRANSITIONS.get(exc.status, [])
            if new_status not in allowed:
                return Response({
                    'error': f"Invalid status transition: {exc.status} → {new_status}. "
                             f"Allowed: {allowed or 'None (terminal state)'}",
                }, status=400)
            trail_entry['to_status'] = new_status
            exc.status = new_status
            update_fields.append('status')

            # Auto-set resolved_at on close/reject
            if new_status in ('Closed', 'Rejected') and not exc.resolved_at:
                exc.resolved_at = timezone.now()
                update_fields.append('resolved_at')

        if 'description' in d:
            exc.description = d['description']
            update_fields.append('description')

        if 'notes' in d:
            exc.notes = d['notes']
            update_fields.append('notes')

        if 'claim_amount' in d:
            exc.claim_amount = d['claim_amount']
            update_fields.append('claim_amount')

        if 'recovered_amount' in d:
            exc.recovered_amount = d['recovered_amount']
            update_fields.append('recovered_amount')

        if 'assigned_to_id' in d:
            exc.assigned_to_id = d['assigned_to_id'] or None
            update_fields.append('assigned_to_id')

        # Append audit trail entry
        trail = list(exc.audit_trail or [])
        trail.append(trail_entry)
        exc.audit_trail = trail
        update_fields.append('audit_trail')

        if update_fields:
            exc.save(update_fields=update_fields)

        return Response(_serialize_exception(exc))
