"""
views_customer_risk.py — Customer Risk Engine API
=================================================
Endpoints for the Customer Risk Engine enterprise feature.

Endpoints:
    GET  /api/logistics/customer-risk/              → Paginated risk profiles
    GET  /api/logistics/customer-risk/distribution/ → Risk level histogram
    POST /api/logistics/customer-risk/recompute/    → Bulk recompute all profiles
    POST /api/logistics/customer-risk/check/        → Check a single phone's risk
    GET  /api/logistics/customer-risk/<phone>/      → Single customer risk profile
"""
import logging

from rest_framework.views import APIView
from rest_framework.response import Response

from core.permissions import HasModulePermission
from core.models import CustomerRiskProfile
from core.services.customer_risk_service import (
    compute_risk_profile,
    bulk_recompute,
    get_risk_distribution,
    check_order_risk,
)
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)


def _serialize_profile(p: CustomerRiskProfile) -> dict:
    total = p.total_orders
    return {
        'phone': p.customer_phone,
        'name': p.customer_name,
        'email': p.customer_email,
        'risk_score': p.risk_score,
        'risk_level': p.risk_level,
        'recommended_actions': p.recommended_actions,
        'total_orders': total,
        'rto_count': p.rto_count,
        'delivery_success_count': p.delivery_success_count,
        'cod_order_count': p.cod_order_count,
        'refusal_count': p.refusal_count,
        'rto_rate': round((p.rto_count / total) * 100, 1) if total else 0,
        'delivery_rate': round((p.delivery_success_count / total) * 100, 1) if total else 0,
        'avg_order_value': float(p.avg_order_value),
        'last_computed_at': p.last_computed_at.isoformat(),
        'is_manually_blocked': p.is_manually_blocked,
        'blocked_reason': p.blocked_reason or '',
    }


class CustomerRiskListView(APIView):
    """
    GET /api/logistics/customer-risk/

    Returns paginated list of CustomerRiskProfile records, filterable by risk_level.

    Query params:
        risk_level  (Low | Medium | High | Blocked)
        search      (phone or name partial match)
        page, page_size
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:customer_risk:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        qs = CustomerRiskProfile.objects.filter(org_id=org_id)

        risk_level = request.query_params.get('risk_level')
        search = request.query_params.get('search', '').strip()

        if risk_level:
            qs = qs.filter(risk_level=risk_level)
        if search:
            qs = qs.filter(
                customer_phone__icontains=search
            ) | CustomerRiskProfile.objects.filter(
                org_id=org_id, customer_name__icontains=search
            )
            if risk_level:
                qs = qs.filter(risk_level=risk_level)

        qs = qs.order_by('-risk_score', '-total_orders')

        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, int(request.query_params.get('page_size', 25)))
        total = qs.count()
        offset = (page - 1) * page_size
        profiles = qs[offset: offset + page_size]

        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
            'results': [_serialize_profile(p) for p in profiles],
        })


class CustomerRiskDistributionView(APIView):
    """
    GET /api/logistics/customer-risk/distribution/

    Returns risk level histogram: {Low: N, Medium: N, High: N, Blocked: N, total: N}
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:customer_risk:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        return Response(get_risk_distribution(org_id))


class CustomerRiskRecomputeView(APIView):
    """
    POST /api/logistics/customer-risk/recompute/

    Triggers bulk recompute of all customer risk profiles for the org.
    Processes customers with order activity in the last 90 days.

    Optionally pass: { "days_back": 180 } to extend the lookback window.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'logistics:customer_risk:recompute'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        days_back = int(request.data.get('days_back', 90))

        try:
            count = bulk_recompute(org_id, days_back=days_back)
            return Response({
                'message': f'Bulk recompute complete. {count} customer profiles updated.',
                'profiles_updated': count,
                'days_back': days_back,
            })
        except Exception as e:
            logger.error(f"[CUSTOMER-RISK] Bulk recompute failed for org {org_id}: {e}")
            return Response({'error': str(e)}, status=500)


class CustomerRiskCheckView(APIView):
    """
    POST /api/logistics/customer-risk/check/

    Pre-dispatch risk check for a phone number.
    Computes risk score on-demand (updates stored profile).

    Body: { "phone": "+91XXXXXXXXXX" }

    Returns risk score, level, recommended actions, and allow_cod flag.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'logistics:customer_risk:view'}

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        phone = (request.data.get('phone') or '').strip()
        if not phone:
            return Response({'error': 'phone is required'}, status=400)

        try:
            result = check_order_risk(org_id, phone)
            return Response(result)
        except Exception as e:
            logger.error(f"[CUSTOMER-RISK] Check failed for {phone} (org {org_id}): {e}")
            return Response({'error': str(e)}, status=500)


class CustomerRiskDetailView(APIView):
    """
    GET   /api/logistics/customer-risk/<phone>/  → Single customer risk profile
    PATCH /api/logistics/customer-risk/<phone>/  → Manually block or unblock a customer

    PATCH body:
        { "is_manually_blocked": true, "blocked_reason": "Repeated fraud" }
        { "is_manually_blocked": false }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:customer_risk:view',
        'PATCH': 'logistics:customer_risk:recompute',  # reuse manage permission
    }

    def get(self, request, phone):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            profile = CustomerRiskProfile.objects.get(org_id=org_id, customer_phone=phone)
        except CustomerRiskProfile.DoesNotExist:
            return Response({
                'error': f'No risk profile found for {phone}. Use POST /customer-risk/check/ to create one.'
            }, status=404)

        return Response(_serialize_profile(profile))

    def patch(self, request, phone):
        """Manually block or unblock a customer."""
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            profile = CustomerRiskProfile.objects.get(org_id=org_id, customer_phone=phone)
        except CustomerRiskProfile.DoesNotExist:
            return Response({'error': f'No risk profile found for {phone}.'}, status=404)

        d = request.data
        update_fields = []

        if 'is_manually_blocked' in d:
            profile.is_manually_blocked = bool(d['is_manually_blocked'])
            update_fields.append('is_manually_blocked')
            # If unblocking, clear the reason
            if not profile.is_manually_blocked:
                profile.blocked_reason = ''
                update_fields.append('blocked_reason')

        if 'blocked_reason' in d:
            profile.blocked_reason = d['blocked_reason'] or ''
            update_fields.append('blocked_reason')

        if update_fields:
            profile.save(update_fields=update_fields)

        return Response(_serialize_profile(profile))
