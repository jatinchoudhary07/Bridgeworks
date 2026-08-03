"""
views_sla_dashboard.py — SLA Dashboard API
==========================================
Endpoints for the SLA Dashboard enterprise feature.

Endpoints:
    GET  /api/logistics/sla/kpis/                   → SLA KPIs (Met %, Breach %, etc.)
    GET  /api/logistics/sla/courier-performance/    → Per-courier × zone SLA table
    GET  /api/logistics/sla/state-performance/      → Per-state SLA table
    GET  /api/logistics/sla/contracts/              → List SLA contracts
    POST /api/logistics/sla/contracts/              → Create SLA contract
    PATCH /api/logistics/sla/contracts/<id>/        → Update SLA contract
    DELETE /api/logistics/sla/contracts/<id>/       → Delete SLA contract
"""
import logging
from datetime import datetime, date, timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.permissions import HasModulePermission
from core.models.delivery import CourierSLAContract
from core.services.sla_service import (
    compute_sla_kpis,
    get_sla_breach_table,
    get_sla_state_performance,
)
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)


def _parse_dates(request):
    """Parse start_date and end_date from query params. Defaults to last 30 days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    start_str = request.query_params.get('start_date') or request.query_params.get('from')
    end_str = request.query_params.get('end_date') or request.query_params.get('to')

    try:
        if start_str:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        if end_str:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        pass

    return start_date, end_date


class SLAKPIsView(APIView):
    """
    GET /api/logistics/sla/kpis/

    Query params:
        start_date (YYYY-MM-DD), end_date (YYYY-MM-DD) — default: last 30 days

    Returns dashboard KPI header: SLA Met %, SLA Breached %, Avg Delay, Penalty Recovery.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:sla_dashboard:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        data = compute_sla_kpis(org_id, start_date, end_date)
        return Response({
            'start_date': str(start_date),
            'end_date': str(end_date),
            **data,
        })


class SLACourierPerformanceView(APIView):
    """
    GET /api/logistics/sla/courier-performance/

    Returns per-courier × zone SLA breach table.
    Each row shows: courier, zone, promised_days, total_shipments, met, breached,
                    met_pct, avg_actual_days, avg_delay_days, penalty_recovery.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:sla_dashboard:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        data = get_sla_breach_table(org_id, start_date, end_date)
        return Response({
            'start_date': str(start_date),
            'end_date': str(end_date),
            'rows': data,
            'count': len(data),
        })


class SLAStatePerformanceView(APIView):
    """
    GET /api/logistics/sla/state-performance/

    Returns per-state SLA breakdown: state, total_shipments, met, breached, met_pct, avg_actual_days.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'logistics:sla_dashboard:view'}

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        data = get_sla_state_performance(org_id, start_date, end_date)
        return Response({
            'start_date': str(start_date),
            'end_date': str(end_date),
            'rows': data,
            'count': len(data),
        })


class SLAContractListView(APIView):
    """
    GET  /api/logistics/sla/contracts/      → List all SLA contracts for the org
    POST /api/logistics/sla/contracts/      → Create a new SLA contract
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:sla_dashboard:view',
        'POST': 'logistics:sla_dashboard:manage',
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        contracts = CourierSLAContract.objects.filter(org_id=org_id).order_by('courier_partner', 'zone')
        
        # Auto-populate default contracts if none exist for this organization
        if not contracts.exists():
            defaults = [
                {'courier_partner': 'Delhivery', 'zone': 'National', 'shipping_mode': 'Surface', 'promised_days': 4, 'penalty_per_day': 25.0, 'notes': 'Default National surface SLA contract'},
                {'courier_partner': 'Delhivery', 'zone': 'Metro', 'shipping_mode': 'Surface', 'promised_days': 3, 'penalty_per_day': 25.0, 'notes': 'Default Metro surface SLA contract'},
                {'courier_partner': 'Bluedart', 'zone': 'National', 'shipping_mode': 'Surface', 'promised_days': 4, 'penalty_per_day': 25.0, 'notes': 'Default National surface SLA contract'},
                {'courier_partner': 'Bluedart', 'zone': 'Metro', 'shipping_mode': 'Surface', 'promised_days': 3, 'penalty_per_day': 25.0, 'notes': 'Default Metro surface SLA contract'},
            ]
            for d in defaults:
                try:
                    CourierSLAContract.objects.create(
                        org_id=org_id,
                        courier_partner=d['courier_partner'],
                        zone=d['zone'],
                        shipping_mode=d['shipping_mode'],
                        promised_days=d['promised_days'],
                        penalty_per_day=d['penalty_per_day'],
                        notes=d['notes'],
                        is_active=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to create default SLA contract: {e}")
            
            # Re-fetch after creation
            contracts = CourierSLAContract.objects.filter(org_id=org_id).order_by('courier_partner', 'zone')

        data = [
            {
                'id': c.id,
                'courier_partner': c.courier_partner,
                'zone': c.zone,
                'shipping_mode': c.shipping_mode,
                'promised_days': c.promised_days,
                'penalty_per_day': float(c.penalty_per_day),
                'is_active': c.is_active,
                'notes': c.notes,
                'created_at': c.created_at.isoformat(),
                'updated_at': c.updated_at.isoformat(),
            }
            for c in contracts
        ]
        return Response({'contracts': data, 'count': len(data)})

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        d = request.data
        required = ['courier_partner', 'zone', 'promised_days']
        missing = [f for f in required if not d.get(f)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=400)

        try:
            promised_days = int(d['promised_days'])
            if promised_days < 1:
                raise ValueError("promised_days must be >= 1")
        except (ValueError, TypeError) as e:
            return Response({'error': f'Invalid promised_days: {e}'}, status=400)

        try:
            contract = CourierSLAContract.objects.create(
                org_id=org_id,
                courier_partner=d['courier_partner'].strip(),
                zone=d['zone'],
                shipping_mode=d.get('shipping_mode', 'Surface'),
                promised_days=promised_days,
                penalty_per_day=d.get('penalty_per_day', 0),
                notes=d.get('notes', ''),
                is_active=d.get('is_active', True),
            )
            return Response({
                'id': contract.id,
                'courier_partner': contract.courier_partner,
                'zone': contract.zone,
                'shipping_mode': contract.shipping_mode,
                'promised_days': contract.promised_days,
                'penalty_per_day': float(contract.penalty_per_day),
                'is_active': contract.is_active,
            }, status=201)
        except Exception as e:
            logger.error(f"[SLA-CONTRACT] Create failed: {e}")
            if 'unique' in str(e).lower() or 'UNIQUE' in str(e):
                return Response({'error': 'SLA contract already exists for this courier/zone/mode combination.'}, status=400)
            return Response({'error': str(e)}, status=400)


class SLAContractDetailView(APIView):
    """
    PATCH  /api/logistics/sla/contracts/<pk>/   → Update fields on a contract
    DELETE /api/logistics/sla/contracts/<pk>/   → Delete a contract
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PATCH': 'logistics:sla_dashboard:manage',
        'DELETE': 'logistics:sla_dashboard:manage',
    }

    def _get_contract(self, org_id, pk):
        try:
            return CourierSLAContract.objects.get(id=pk, org_id=org_id)
        except CourierSLAContract.DoesNotExist:
            return None

    def patch(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        contract = self._get_contract(org_id, pk)
        if not contract:
            return Response({'error': 'SLA contract not found'}, status=404)

        d = request.data
        allowed_fields = ['promised_days', 'penalty_per_day', 'is_active', 'notes', 'shipping_mode']
        for field in allowed_fields:
            if field in d:
                if field == 'promised_days':
                    val = int(d[field])
                    if val < 1:
                        return Response({'error': 'promised_days must be >= 1'}, status=400)
                    setattr(contract, field, val)
                else:
                    setattr(contract, field, d[field])

        contract.save()
        return Response({
            'id': contract.id,
            'courier_partner': contract.courier_partner,
            'zone': contract.zone,
            'shipping_mode': contract.shipping_mode,
            'promised_days': contract.promised_days,
            'penalty_per_day': float(contract.penalty_per_day),
            'is_active': contract.is_active,
        })

    def delete(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        contract = self._get_contract(org_id, pk)
        if not contract:
            return Response({'error': 'SLA contract not found'}, status=404)

        contract.delete()
        return Response({'message': 'SLA contract deleted'}, status=200)
