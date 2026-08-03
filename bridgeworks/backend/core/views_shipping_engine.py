"""
views_shipping_engine.py — Warehouse, Rate Card & Zone API Views
================================================================
Endpoints:
  Warehouses:
    GET/POST   /api/delivery/warehouses/
    PUT/DELETE /api/delivery/warehouses/<id>/
    POST       /api/delivery/warehouses/<id>/set-default/

  Rate Cards:
    GET/POST   /api/delivery/rate-cards/
    DELETE     /api/delivery/rate-cards/<id>/
    POST       /api/delivery/rate-cards/upload/

  Zone:
    GET        /api/delivery/zone-check/?pincode=<pincode>

  Recalculate:
    POST       /api/delivery/recalculate-costs/
"""

import csv
import io
import logging
from decimal import Decimal, InvalidOperation

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.permissions import HasModulePermission

from rest_framework.parsers import MultiPartParser, FormParser
from core.models.delivery import Warehouse, CourierRateCard, RateSlab, CourierSurchargeHistory, CourierZoneMapping
from core.services.zone_engine import get_zone, get_mapped_zone, calculate_shipment_cost, backfill_zones_and_costs

logger = logging.getLogger(__name__)


def _get_org_id(request):
    """Resolve org_id from the authenticated user."""
    user = request.user
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    if hasattr(user, 'team_settings') and user.team_settings.organization:
        return user.team_settings.organization.organization_id
    return None


# ==============================================================================
# WAREHOUSE CRUD
# ==============================================================================

class WarehouseListView(APIView):
    """
    GET  /api/delivery/warehouses/ — List all warehouses
    POST /api/delivery/warehouses/ — Create a warehouse
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:warehouse_manager:view',
        'POST': 'logistics:warehouse_manager:create',
    }
    
    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        warehouses = Warehouse.objects.filter(org_id=org_id, is_active=True).order_by('-is_default', 'name')
        data = []
        for w in warehouses:
            data.append({
                'id': w.id,
                'name': w.name,
                'pincode': w.pincode,
                'address': w.address,
                'city': w.city,
                'state': w.state,
                'contact_name': w.contact_name,
                'contact_phone': w.contact_phone,
                'is_default': w.is_default,
                'is_active': w.is_active,
                'created_at': w.created_at.isoformat() if w.created_at else None,
            })
        return Response({'warehouses': data})

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        d = request.data
        name = (d.get('name') or '').strip()
        pincode = (d.get('pincode') or '').strip()

        if not name or not pincode:
            return Response({'error': 'Name and pincode are required'}, status=400)
        if len(pincode) != 6 or not pincode.isdigit():
            return Response({'error': 'Pincode must be exactly 6 digits'}, status=400)

        # If this is the first warehouse, auto-set as default
        is_first = not Warehouse.objects.filter(org_id=org_id).exists()
        is_default = d.get('is_default', is_first)

        warehouse = Warehouse.objects.create(
            org_id=org_id,
            name=name,
            pincode=pincode,
            address=d.get('address', ''),
            city=d.get('city', ''),
            state=d.get('state', ''),
            contact_name=d.get('contact_name', ''),
            contact_phone=d.get('contact_phone', ''),
            is_default=is_default,
        )

        return Response({
            'message': f'Warehouse "{warehouse.name}" created',
            'id': warehouse.id,
            'is_default': warehouse.is_default,
        }, status=201)


class WarehouseDetailView(APIView):
    """
    PUT    /api/delivery/warehouses/<id>/ — Update warehouse
    DELETE /api/delivery/warehouses/<id>/ — Deactivate warehouse
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PUT': 'logistics:warehouse_manager:edit',
        'DELETE': 'logistics:warehouse_manager:delete',
    }
    
    def put(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            warehouse = Warehouse.objects.get(pk=pk, org_id=org_id)
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found'}, status=404)

        d = request.data
        for field in ['name', 'pincode', 'address', 'city', 'state', 'contact_name', 'contact_phone']:
            val = d.get(field)
            if val is not None:
                setattr(warehouse, field, val.strip() if isinstance(val, str) else val)

        if d.get('is_default'):
            warehouse.is_default = True

        warehouse.save()
        return Response({'message': f'Warehouse "{warehouse.name}" updated'})

    def delete(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            warehouse = Warehouse.objects.get(pk=pk, org_id=org_id)
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found'}, status=404)

        warehouse.is_active = False
        warehouse.is_default = False
        warehouse.save()
        return Response({'message': f'Warehouse "{warehouse.name}" deactivated'})


class WarehouseSetDefaultView(APIView):
    """POST /api/delivery/warehouses/<id>/set-default/"""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:warehouse_manager:edit',
    }
    
    def post(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            warehouse = Warehouse.objects.get(pk=pk, org_id=org_id)
        except Warehouse.DoesNotExist:
            return Response({'error': 'Warehouse not found'}, status=404)

        warehouse.is_default = True
        warehouse.save()  # The model's save() auto-unsets other defaults
        return Response({'message': f'"{warehouse.name}" set as default warehouse'})


# ==============================================================================
# RATE CARD CRUD
# ==============================================================================

class RateCardListView(APIView):
    """
    GET  /api/delivery/rate-cards/ — List all rate cards with slabs
    POST /api/delivery/rate-cards/ — Create a rate card with slabs
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:rate_card_manager:view',
        'POST': 'logistics:rate_card_manager:create',
    }
    
    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        cards = CourierRateCard.objects.filter(org_id=org_id).prefetch_related('slabs').order_by('-is_active', 'courier_partner')
        data = []
        for card in cards:
            slabs = []
            for s in card.slabs.all():
                slabs.append({
                    'id': s.id,
                    'zone': s.zone,
                    'weight_from_kg': float(s.weight_from_kg),
                    'weight_to_kg': float(s.weight_to_kg),
                    'rate': float(s.rate),
                    'increment_kg': float(s.increment_kg),
                })
            data.append({
                'id': card.id,
                'name': card.name,
                'courier_partner': card.courier_partner,
                'shipping_mode': card.shipping_mode,
                'pricing_mode': card.pricing_mode,
                'cod_charge_flat': float(card.cod_charge_flat),
                'cod_charge_percent': float(card.cod_charge_percent),
                'fuel_surcharge_percent': float(card.fuel_surcharge_percent),
                'fuel_surcharge_mode': card.fuel_surcharge_mode,
                'fuel_surcharge_offset': float(card.fuel_surcharge_offset),
                'caf_percent': float(card.caf_percent),
                'caf_mode': card.caf_mode,
                'caf_offset': float(card.caf_offset),
                'efss_surcharge_percent': float(card.efss_surcharge_percent),
                'rto_charge_multiplier': float(card.rto_charge_multiplier),
                'ndr_reattempt_charge': float(card.ndr_reattempt_charge),
                'reverse_pickup_charge': float(card.reverse_pickup_charge),
                'is_active': card.is_active,
                'created_at': card.created_at.isoformat() if card.created_at else None,
                'slabs': slabs,
                'slab_count': len(slabs),
            })
        return Response({'rate_cards': data})

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        d = request.data
        name = (d.get('name') or '').strip()
        courier = (d.get('courier_partner') or '').strip()

        if not name or not courier:
            return Response({'error': 'Name and courier_partner are required'}, status=400)

        card = CourierRateCard.objects.create(
            org_id=org_id,
            name=name,
            courier_partner=courier,
            shipping_mode=d.get('shipping_mode', 'Surface'),
            pricing_mode=d.get('pricing_mode', 'SLAB'),
            cod_charge_flat=Decimal(str(d.get('cod_charge_flat', 0))),
            cod_charge_percent=Decimal(str(d.get('cod_charge_percent', 0))),
            fuel_surcharge_percent=Decimal(str(d.get('fuel_surcharge_percent', 0))),
            fuel_surcharge_mode=d.get('fuel_surcharge_mode', 'STATIC'),
            fuel_surcharge_offset=Decimal(str(d.get('fuel_surcharge_offset', 0))),
            caf_percent=Decimal(str(d.get('caf_percent', 0))),
            caf_mode=d.get('caf_mode', 'STATIC'),
            caf_offset=Decimal(str(d.get('caf_offset', 0))),
            efss_surcharge_percent=Decimal(str(d.get('efss_surcharge_percent', 0))),
            rto_charge_multiplier=Decimal(str(d.get('rto_charge_multiplier', 1.0))),
            ndr_reattempt_charge=Decimal(str(d.get('ndr_reattempt_charge', 0))),
            reverse_pickup_charge=Decimal(str(d.get('reverse_pickup_charge', 0))),
        )

        # Create slabs if provided
        slabs_data = d.get('slabs', [])
        created_slabs = 0
        for slab in slabs_data:
            try:
                RateSlab.objects.create(
                    rate_card=card,
                    zone=slab['zone'],
                    weight_from_kg=Decimal(str(slab['weight_from_kg'])),
                    weight_to_kg=Decimal(str(slab['weight_to_kg'])),
                    rate=Decimal(str(slab['rate'])),
                    increment_kg=Decimal(str(slab.get('increment_kg', 0.5))),
                )
                created_slabs += 1
            except (KeyError, InvalidOperation) as e:
                logger.warning(f"Skipping invalid slab: {e}")

        return Response({
            'message': f'Rate card "{card.name}" created with {created_slabs} slabs',
            'id': card.id,
        }, status=201)


class RateCardDetailView(APIView):
    """PUT/DELETE /api/delivery/rate-cards/<id>/"""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PUT': 'logistics:rate_card_manager:create',
        'DELETE': 'logistics:rate_card_manager:delete',
    }
    
    def put(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            card = CourierRateCard.objects.get(pk=pk, org_id=org_id)
        except CourierRateCard.DoesNotExist:
            return Response({'error': 'Rate card not found'}, status=404)

        d = request.data
        if 'name' in d:
            card.name = d['name']
        if 'courier_partner' in d:
            card.courier_partner = d['courier_partner']
        if 'shipping_mode' in d:
            card.shipping_mode = d['shipping_mode']
        if 'pricing_mode' in d:
            card.pricing_mode = d['pricing_mode']
        
        # Decimal fields
        for field in [
            'cod_charge_flat', 'cod_charge_percent', 'fuel_surcharge_percent',
            'fuel_surcharge_offset', 'caf_percent', 'caf_offset',
            'efss_surcharge_percent', 'rto_charge_multiplier', 'ndr_reattempt_charge',
            'reverse_pickup_charge'
        ]:
            if field in d:
                try:
                    setattr(card, field, Decimal(str(d[field])))
                except (InvalidOperation, ValueError, TypeError):
                    return Response({'error': f'Invalid value for field {field}'}, status=400)
        
        # Modes
        if 'fuel_surcharge_mode' in d:
            card.fuel_surcharge_mode = d['fuel_surcharge_mode']
        if 'caf_mode' in d:
            card.caf_mode = d['caf_mode']
        if 'is_active' in d:
            card.is_active = bool(d['is_active'])

        card.save()
        return Response({
            'message': f'Rate card "{card.name}" updated successfully',
            'id': card.id
        })
    
    def delete(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            card = CourierRateCard.objects.get(pk=pk, org_id=org_id)
        except CourierRateCard.DoesNotExist:
            return Response({'error': 'Rate card not found'}, status=404)

        card_name = card.name
        card.delete()
        return Response({'message': f'Rate card "{card_name}" deleted'})


class RateCardUploadView(APIView):
    """
    POST /api/delivery/rate-cards/upload/
    Upload a CSV to create rate slabs for an existing or new rate card.

    Expected CSV columns: zone, weight_from_kg, weight_to_kg, rate, increment_kg (optional)

    Query params: rate_card_id (optional — if not provided, creates a new card)
    Body: file (CSV), and optionally name, courier_partner, shipping_mode, pricing_mode
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:rate_card_manager:create',
    }
    
    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'error': 'No CSV file provided'}, status=400)

        rate_card_id = request.data.get('rate_card_id')
        card = None

        if rate_card_id:
            try:
                card = CourierRateCard.objects.get(pk=rate_card_id, org_id=org_id)
            except CourierRateCard.DoesNotExist:
                return Response({'error': 'Rate card not found'}, status=404)
        else:
            # Create a new rate card from form data
            name = (request.data.get('name') or '').strip()
            courier = (request.data.get('courier_partner') or '').strip()
            if not name or not courier:
                return Response({'error': 'name and courier_partner required for new rate card'}, status=400)

            card = CourierRateCard.objects.create(
                org_id=org_id,
                name=name,
                courier_partner=courier,
                shipping_mode=request.data.get('shipping_mode', 'Surface'),
                pricing_mode=request.data.get('pricing_mode', 'SLAB'),
                cod_charge_flat=Decimal(str(request.data.get('cod_charge_flat', 0))),
                cod_charge_percent=Decimal(str(request.data.get('cod_charge_percent', 0))),
                fuel_surcharge_percent=Decimal(str(request.data.get('fuel_surcharge_percent', 0))),
                fuel_surcharge_mode=request.data.get('fuel_surcharge_mode', 'STATIC'),
                fuel_surcharge_offset=Decimal(str(request.data.get('fuel_surcharge_offset', 0))),
                caf_percent=Decimal(str(request.data.get('caf_percent', 0))),
                caf_mode=request.data.get('caf_mode', 'STATIC'),
                caf_offset=Decimal(str(request.data.get('caf_offset', 0))),
                efss_surcharge_percent=Decimal(str(request.data.get('efss_surcharge_percent', 0))),
                rto_charge_multiplier=Decimal(str(request.data.get('rto_charge_multiplier', 1.0))),
                ndr_reattempt_charge=Decimal(str(request.data.get('ndr_reattempt_charge', 0))),
                reverse_pickup_charge=Decimal(str(request.data.get('reverse_pickup_charge', 0))),
            )

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))

            created = 0
            errors = []

            for row_num, row in enumerate(reader, start=2):
                zone = (row.get('zone') or '').strip()
                if not zone:
                    errors.append(f"Row {row_num}: Missing zone")
                    continue

                try:
                    slab, was_created = RateSlab.objects.update_or_create(
                        rate_card=card,
                        zone=zone,
                        weight_from_kg=Decimal(row.get('weight_from_kg', '0').strip()),
                        defaults={
                            'weight_to_kg': Decimal(row.get('weight_to_kg', '0.5').strip()),
                            'rate': Decimal(row.get('rate', '0').strip()),
                            'increment_kg': Decimal(row.get('increment_kg', '0.5').strip() or '0.5'),
                        }
                    )
                    created += 1
                except (InvalidOperation, ValueError) as e:
                    errors.append(f"Row {row_num}: Invalid number — {e}")

            return Response({
                'message': f'{created} slabs loaded into "{card.name}"',
                'rate_card_id': card.id,
                'errors': errors[:20],
            })

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RateCardVisionScanView(APIView):
    """
    POST /api/delivery/rate-cards/vision-scan/
    Uploads a rate card image/PDF and returns a structured AI-parsed JSON extraction of slabs and surcharges.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:rate_card_manager:create',
    }

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        from core.services.vision_parser import parse_rate_card_image
        try:
            # We pass the file stream directly to PIL through the parser
            parsed_data = parse_rate_card_image(file)
            return Response({'success': True, 'data': parsed_data})
        except Exception as e:
            logger.error(f"Vision Parsing Error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# ZONE PREVIEW
# ==============================================================================

class ZoneCheckView(APIView):
    """
    GET /api/delivery/zone-check/?pincode=560001
    Returns the zone for a given pincode relative to the default warehouse.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        dest_pincode = request.query_params.get('pincode', '').strip()
        if not dest_pincode or len(dest_pincode) != 6:
            return Response({'error': 'Valid 6-digit pincode required'}, status=400)

        warehouse = Warehouse.objects.filter(
            org_id=org_id, is_default=True, is_active=True
        ).first()

        if not warehouse:
            warehouse = Warehouse.objects.filter(
                org_id=org_id, is_active=True
            ).first()

        if not warehouse:
            return Response({'error': 'No warehouse configured. Add a warehouse first.'}, status=400)

        zone = get_mapped_zone(org_id, warehouse.pincode, dest_pincode, 'Bluedart')

        # Also lookup rate if available
        rate_info = {}
        cards = CourierRateCard.objects.filter(org_id=org_id, is_active=True).prefetch_related('slabs')
        for card in cards:
            c_zone = get_mapped_zone(org_id, warehouse.pincode, dest_pincode, card.courier_partner)
            slab = card.slabs.filter(zone=c_zone).order_by('weight_from_kg').first()
            if slab:
                rate_info[card.courier_partner] = {
                    'rate_card': card.name,
                    'resolved_zone': c_zone,
                    'base_rate': float(slab.rate),
                    'fuel_surcharge': float(card.fuel_surcharge_percent),
                    'rto_multiplier': float(card.rto_charge_multiplier),
                }

        return Response({
            'origin_pincode': warehouse.pincode,
            'origin_warehouse': warehouse.name,
            'destination_pincode': dest_pincode,
            'zone': zone,
            'courier_rates': rate_info,
        })


# ==============================================================================
# BATCH RECALCULATE
# ==============================================================================

class RecalculateCostsView(APIView):
    """
    POST /api/delivery/recalculate-costs/
    Trigger backfill/recalculation of zones and costs for all shipments.
    Body: { "recalculate_all": true/false }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:rate_card_manager:edit',
    }
    
    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        recalculate_all = request.data.get('recalculate_all', False)
        result = backfill_zones_and_costs(org_id, recalculate_all=recalculate_all)

        if 'error' in result:
            return Response({'error': result['error']}, status=400)

        return Response({
            'message': 'Cost recalculation complete',
            'stats': result,
        })


class CourierSurchargeHistoryView(APIView):
    """
    GET/POST/DELETE /api/delivery/surcharge-history/
    Manage monthly Fuel Surcharge / CAF values.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:rate_card_manager:view',
        'POST': 'logistics:rate_card_manager:create',
        'DELETE': 'logistics:rate_card_manager:delete',
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        history = CourierSurchargeHistory.objects.filter(org_id=org_id).order_by('-month_date')
        data = []
        for item in history:
            data.append({
                'id': item.id,
                'courier_partner': item.courier_partner,
                'month_date': item.month_date.isoformat(),
                'fuel_surcharge_percent': float(item.fuel_surcharge_percent),
                'caf_percent': float(item.caf_percent),
            })
        return Response({'surcharge_history': data})

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        d = request.data
        courier = d.get('courier_partner', 'Bluedart')
        month_str = d.get('month_date') # e.g. "2026-04-01"
        if not month_str:
            return Response({'error': 'month_date is required'}, status=400)

        try:
            from datetime import datetime
            month_date = datetime.strptime(month_str[:10], '%Y-%m-%d').date()
            # Set to 1st day of the month to standardize
            month_date = month_date.replace(day=1)
        except ValueError:
            return Response({'error': 'Invalid date format, use YYYY-MM-DD'}, status=400)

        try:
            fuel = Decimal(str(d.get('fuel_surcharge_percent', 0)))
            caf = Decimal(str(d.get('caf_percent', 0)))
        except (InvalidOperation, ValueError, TypeError):
            return Response({'error': 'Invalid decimal formats for fuel_surcharge_percent or caf_percent'}, status=400)

        # Update or create
        item, created = CourierSurchargeHistory.objects.update_or_create(
            org_id=org_id,
            courier_partner=courier,
            month_date=month_date,
            defaults={
                'fuel_surcharge_percent': fuel,
                'caf_percent': caf,
            }
        )

        return Response({
            'message': 'Surcharge history saved successfully',
            'id': item.id,
            'created': created
        }, status=201 if created else 200)

    def delete(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        pk = request.data.get('id')
        if not pk:
            return Response({'error': 'ID is required to delete'}, status=400)

        try:
            item = CourierSurchargeHistory.objects.get(pk=pk, org_id=org_id)
            item.delete()
            return Response({'message': 'Surcharge history entry deleted successfully'})
        except CourierSurchargeHistory.DoesNotExist:
            return Response({'error': 'Surcharge history entry not found'}, status=404)


class CourierZoneMappingUploadView(APIView):
    """
    POST /api/delivery/zone-mappings/upload/
    Uploads and parses a courier zone mappings file.

    Supported formats (auto-detected):
      - CODPIN.xls  — tab-separated text, zone column = ZONE
      - JAIPUR TAT.xlsx — proper Excel, zone column = DPZONE
      - Any .xlsx with ZONE or NEWZONE column

    Auto-detects zone column with priority: DPZONE > ZONE > NEWZONE.
    After a successful import, immediately re-analyses ALL FreightInvoices
    for this org so discrepancy results reflect the new zones.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        import pandas as pd
        from django.db import transaction

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        courier_partner = request.data.get('courier_partner', 'Bluedart')

        try:
            filename = file_obj.name.lower()

            # ── 1. Parse into DataFrame ──────────────────────────────────────
            df = None
            if filename.endswith(('.xlsx', '.xls')):
                # Try proper Excel first (handles JAIPUR TAT.xlsx with DPZONE)
                try:
                    engine = 'openpyxl' if filename.endswith('.xlsx') else None
                    excel_file = pd.ExcelFile(file_obj, engine=engine)
                    # Scan sheets; pick the first that has CPINCODE
                    for sheet_name in excel_file.sheet_names:
                        candidate = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str)
                        candidate.columns = [str(c).strip().upper() for c in candidate.columns]
                        if 'CPINCODE' in candidate.columns:
                            df = candidate
                            break
                    if df is None:
                        df = pd.read_excel(excel_file, sheet_name=0, dtype=str)
                        df.columns = [str(c).strip().upper() for c in df.columns]
                except Exception:
                    pass  # Fall through to TSV parsing

            if df is None:
                # TSV/CSV path — also handles .xls files that are actually TSV
                file_obj.seek(0)
                content_bytes = file_obj.read()
                try:
                    decoded = content_bytes.decode('utf-8-sig')
                except Exception:
                    decoded = content_bytes.decode('latin-1', errors='ignore')

                try:
                    df = pd.read_csv(io.StringIO(decoded), sep='\t', dtype=str)
                    df.columns = [str(c).strip().upper() for c in df.columns]
                    if 'CPINCODE' not in df.columns:
                        raise ValueError('CPINCODE not found in tab-separated parse')
                except Exception:
                    df = pd.read_csv(io.StringIO(decoded), sep=',', dtype=str)
                    df.columns = [str(c).strip().upper() for c in df.columns]

            # ── 2. Auto-detect zone column ───────────────────────────────────
            # Priority: DPZONE (JAIPUR TAT) > ZONE (CODPIN 2024) > NEWZONE
            ZONE_COLUMN_PRIORITY = ['DPZONE', 'ZONE', 'NEWZONE']
            zone_col = None
            for candidate_col in ZONE_COLUMN_PRIORITY:
                if candidate_col in df.columns:
                    zone_col = candidate_col
                    break

            if 'CPINCODE' not in df.columns:
                return Response({
                    'error': (
                        "Invalid format. Could not find 'CPINCODE' column. "
                        f"Columns found: {', '.join(list(df.columns)[:25])}"
                    )
                }, status=400)

            if zone_col is None:
                return Response({
                    'error': (
                        f"Invalid format. Could not find a zone column "
                        f"(tried: {', '.join(ZONE_COLUMN_PRIORITY)}). "
                        f"Columns found: {', '.join(list(df.columns)[:25])}"
                    )
                }, status=400)

            # ── 3. Build and import mappings ─────────────────────────────────
            has_city   = 'CITY'   in df.columns
            has_state  = 'STATE'  in df.columns
            has_region = 'REGION' in df.columns

            seen_pincodes = {}   # pincode -> (zone_code, city, state, region)
            skipped = 0
            zone_distribution = {}

            for _, row in df.iterrows():
                pincode = str(row.get('CPINCODE', '')).strip()
                if not pincode or pincode.lower() == 'nan':
                    skipped += 1
                    continue
                if '.' in pincode:
                    pincode = pincode.split('.')[0]
                if pincode.isdigit() and len(pincode) < 6:
                    pincode = pincode.zfill(6)
                if not pincode.isdigit() or len(pincode) != 6:
                    skipped += 1
                    continue
                if pincode in seen_pincodes:
                    continue  # deduplicate — keep first

                zone_code = str(row.get(zone_col, '')).strip()
                if not zone_code or zone_code.lower() == 'nan':
                    skipped += 1
                    continue

                city_val   = str(row.get('CITY',   '')).strip() if has_city   else ''
                state_val  = str(row.get('STATE',  '')).strip() if has_state  else ''
                region_val = str(row.get('REGION', '')).strip() if has_region else ''

                seen_pincodes[pincode] = (
                    zone_code[:10],
                    city_val[:100]  if city_val  and city_val  != 'nan' else '',
                    state_val[:100] if state_val and state_val != 'nan' else '',
                    region_val[:50] if region_val and region_val != 'nan' else '',
                )
                zone_distribution[zone_code] = zone_distribution.get(zone_code, 0) + 1

            with transaction.atomic():
                CourierZoneMapping.objects.filter(
                    org_id=org_id, courier_partner=courier_partner
                ).delete()

                bulk_data = [
                    CourierZoneMapping(
                        org_id=org_id,
                        courier_partner=courier_partner,
                        pincode=pincode,
                        zone_code=vals[0],
                        city=vals[1],
                        state=vals[2],
                        region=vals[3],
                    )
                    for pincode, vals in seen_pincodes.items()
                ]
                CourierZoneMapping.objects.bulk_create(bulk_data, batch_size=2000)

            imported = len(bulk_data)

            # ── 4. Re-analyse ALL invoices with the new zone data ────────────
            reanalyse_stats = _reanalyse_all_invoices(org_id)

            return Response({
                'message': (
                    f'Successfully imported {imported:,} pincode mappings for {courier_partner} '
                    f'(zone column: {zone_col}).'
                ),
                'imported': imported,
                'skipped': skipped,
                'zone_column_used': zone_col,
                'zone_distribution': dict(sorted(zone_distribution.items())),
                'reanalyse': reanalyse_stats,
            })

        except Exception as e:
            logger.error(f'Failed to parse or save zone mappings file: {e}', exc_info=True)
            return Response({'error': f'Failed to parse or save file: {str(e)}'}, status=400)


def _reanalyse_all_invoices(org_id: str) -> dict:
    """
    Re-run discrepancy analysis on every FreightInvoice for this org.
    ALL lines are re-analysed (including disputed ones) so that updated
    zone mappings are immediately reflected in every invoice.

    Returns a combined summary dict.
    """
    from core.models.delivery import FreightInvoice
    from core.services.discrepancy_engine import analyse_invoice
    from decimal import Decimal

    invoices = FreightInvoice.objects.filter(org_id=org_id)
    total_invoices = invoices.count()
    if total_invoices == 0:
        return {'invoices_reanalysed': 0, 'message': 'No invoices found.'}

    combined = {
        'invoices_reanalysed': 0,
        'total_lines': 0,
        'discrepancies_found': 0,
        'total_overcharge': '0.00',
        'errors': 0,
    }
    total_overcharge = Decimal('0')

    for invoice in invoices.iterator():
        try:
            stats = analyse_invoice(invoice.id, org_id)
            combined['invoices_reanalysed'] += 1
            combined['total_lines']         += stats.get('total', 0)
            combined['discrepancies_found'] += (
                stats.get('wrong_rate', 0)
                + stats.get('wrong_slab', 0)
                + stats.get('unexpected_fod', 0)
                + stats.get('unexpected_rto', 0)
            )
            total_overcharge += Decimal(str(stats.get('total_overcharge', '0')))
        except Exception as e:
            logger.warning(f'Re-analyse failed for invoice {invoice.id}: {e}')
            combined['errors'] += 1

    combined['total_overcharge'] = str(total_overcharge.quantize(Decimal('0.01')))
    return combined

