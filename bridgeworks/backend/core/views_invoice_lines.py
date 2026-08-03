"""
views_invoice_lines.py — Billing Discrepancy Engine API Views
=============================================================
New views that power the Excel invoice upload and discrepancy drill-down.

Views:
  InvoiceExcelUploadView   — POST /api/delivery/invoices/upload-excel/
  InvoiceLineListView      — GET  /api/delivery/invoices/<id>/lines/
  InvoiceLineDisputeView   — POST /api/delivery/invoices/<id>/lines/<lid>/dispute/
  InvoiceDisputeAllView    — POST /api/delivery/invoices/<id>/dispute-all/
  InvoiceDisputeReportView — GET  /api/delivery/invoices/<id>/dispute-report/
"""
import logging
import re
import tempfile
import os
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, Value, DecimalField, F, ExpressionWrapper, Case, When
from django.db.models.functions import Coalesce

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from core.models.delivery import (
    Shipment, FreightInvoice, ShipmentDispute, CourierInvoiceLine, Warehouse,
)
from core.services.zone_engine import get_mapped_zone
from core.services.discrepancy_engine import infer_zone_from_freight
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. INVOICE EXCEL UPLOAD
# ==============================================================================
class InvoiceExcelUploadView(APIView):
    """
    POST /api/delivery/invoices/upload-excel/
    Pipeline: Parse → Match AWBs → Bulk-create lines → Analyse discrepancies
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        from core.services.invoice_parser   import parse_invoice_file
        from core.services.discrepancy_engine import analyse_invoice

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        file_obj        = request.FILES.get('file')
        courier_partner = request.data.get('courier_partner', 'Bluedart')
        invoice_date_str = request.data.get('invoice_date', '')

        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        suffix = '.xlsb' if file_obj.name.lower().endswith('.xlsb') else '.xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in file_obj.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            # ── 1. Parse ────────────────────────────────────────────────────
            rows = parse_invoice_file(tmp_path, courier_partner)
            if not rows:
                return Response({'error': 'No rows found in file.'}, status=400)

            # ── 2. Resolve FreightInvoice ────────────────────────────────────
            from datetime import datetime, date as date_cls
            inv_date = date_cls.today()
            if invoice_date_str:
                try:
                    inv_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            total_with_tax = Decimal('0')
            for r in rows:
                tb = r['total_billed']
                cgst = (tb * Decimal('0.09')).quantize(Decimal('0.01'))
                sgst = (tb * Decimal('0.09')).quantize(Decimal('0.01'))
                total_with_tax += tb + cgst + sgst
            # Use filename as invoice number (without extension); user can rename later
            invoice_number = os.path.splitext(file_obj.name)[0]

            invoice, inv_created = FreightInvoice.objects.get_or_create(
                org_id         = org_id,
                invoice_number = invoice_number,
                defaults={
                    'courier_partner': courier_partner,
                    'invoice_date':    inv_date,
                    'total_amount':    total_with_tax,
                }
            )
            if not inv_created:
                # Re-upload: wipe existing lines
                CourierInvoiceLine.objects.filter(freight_invoice=invoice).delete()
                invoice.total_amount = total_with_tax
                invoice.save(update_fields=['total_amount'])

            # ── 3. Build AWB → Shipment / Order maps ─────────────────────────
            awb_list = set()
            for r in rows:
                awb_list.add(r['awb_number'])
                if r['awb_number'].upper().endswith('R'):
                    awb_list.add(r['awb_number'][:-1])

            shipments = Shipment.objects.filter(
                org_id=org_id, awb_number__in=awb_list
            ).select_related('order')
            shipment_map = {s.awb_number: s for s in shipments}

            # Fetch return & exchange mapping orders
            from core.models import Order
            orders_with_return_exchange_awb = Order.objects.filter(
                org_id=org_id
            ).filter(
                Q(return_awb__in=awb_list) | Q(exchange_awb__in=awb_list)
            )

            # Map order_id -> forward Shipment
            order_ids = [o.id for o in orders_with_return_exchange_awb]
            forward_shipments_for_orders = Shipment.objects.filter(
                org_id=org_id, order_id__in=order_ids
            ).select_related('order')
            order_to_shipment_map = {}
            for s in forward_shipments_for_orders:
                if s.order_id not in order_to_shipment_map:
                    order_to_shipment_map[s.order_id] = s

            return_awb_map = {}
            exchange_awb_map = {}
            for o in orders_with_return_exchange_awb:
                sh = order_to_shipment_map.get(o.id)
                if o.return_awb:
                    return_awb_map[o.return_awb] = (o, sh)
                if o.exchange_awb:
                    exchange_awb_map[o.exchange_awb] = (o, sh)

            # Also match via our internal order reference (CCRCRDREF)
            base_refs = []
            for r in rows:
                if r['courier_ref']:
                    cleaned = re.sub(r'(RET|EXC)\d+$', '', r['courier_ref']).strip()
                    digits = re.sub(r'\D', '', cleaned)
                    if digits:
                        base_refs.append(int(digits))
            base_refs = list(set(base_refs))
            ref_to_shipment = {}
            for s in Shipment.objects.filter(
                org_id=org_id,
                order__order_number__in=base_refs,
            ).select_related('order'):
                if s.order:
                    ref_to_shipment[s.order.order_number] = s

            # ── 4. Build line objects ────────────────────────────────────────
            line_objects = []
            type_counts  = {'Forward': 0, 'RTO': 0, 'Return': 0, 'Exchange': 0, 'Credit': 0}
            unmatched    = 0

            for row in rows:
                awb = row['awb_number']
                shipment = None
                order = None
                
                # Check direct match
                if awb in shipment_map:
                    shipment = shipment_map[awb]
                    order = shipment.order
                # Check return AWB map
                elif awb in return_awb_map:
                    order, shipment = return_awb_map[awb]
                # Check exchange AWB map
                elif awb in exchange_awb_map:
                    order, shipment = exchange_awb_map[awb]
                # Strip 'R' suffix
                elif awb.upper().endswith('R') and (awb[:-1] in shipment_map):
                    shipment = shipment_map[awb[:-1]]
                    order = shipment.order
                # Fallback to internal order reference mapping
                elif row['courier_ref']:
                    cleaned = re.sub(r'(RET|EXC)\d+$', '', row['courier_ref']).strip()
                    digits = re.sub(r'\D', '', cleaned)
                    if digits:
                        shipment = ref_to_shipment.get(int(digits))
                        if shipment:
                            order = shipment.order

                if not shipment:
                    unmatched += 1

                stype = row.get('shipment_type', 'Forward')
                
                awb_upper = awb.upper()
                ref_upper = (row.get('courier_ref') or '').upper()
                dest_area_upper = (row.get('dest_area') or '').upper()
                
                # ── Classification Logic ──
                if awb in return_awb_map:
                    stype = 'Return'
                elif awb in exchange_awb_map:
                    stype = 'Exchange'
                elif 'RET' in ref_upper:
                    stype = 'Return'
                elif 'EXC' in ref_upper:
                    stype = 'Exchange'
                elif awb_upper.endswith('R') or awb_upper.startswith('R') or ref_upper.endswith('R') or ref_upper.startswith('R'):
                    stype = 'RTO'
                elif awb in shipment_map:
                    # Explicitly matches a forward shipment - keep Forward
                    stype = 'Forward'
                elif 'JAIPUR' in dest_area_upper:
                    # Destination Jaipur and unmatched to any forward shipment - class as Return
                    stype = 'Return'
                
                # RTO conversion check
                if stype == 'Return' and shipment and shipment.order:
                    from core.models.constants import RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
                    combined_rto_statuses = RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES
                    if shipment.order.current_status in combined_rto_statuses:
                        stype = 'RTO'

                type_counts[stype] = type_counts.get(stype, 0) + 1

                line_objects.append(CourierInvoiceLine(
                    org_id                = org_id,
                    freight_invoice       = invoice,
                    shipment              = shipment,
                    awb_number            = awb,
                    courier_ref           = row['courier_ref'],
                    product_code          = row['product_code'],
                    origin_area           = row['origin_area'],
                    dest_area             = row['dest_area'],
                    dest_pincode          = row.get('dest_pincode') or (order.shipping_pincode if order else ''),
                    commodity             = row['commodity'],
                    actual_weight_kg      = row['actual_weight_kg'],
                    charged_weight_kg     = row['charged_weight_kg'],
                    expected_weight_kg    = row['expected_weight_kg'],
                    pieces                = row['pieces'],
                    freight               = row['freight'],
                    fsc                   = row['fsc'],
                    caf                   = row['caf'],
                    efss                  = row.get('efss', Decimal('0')),
                    fod_charge            = row['fod_charge'],
                    declared_value_charge = row['declared_value_charge'],
                    idc_charge            = row['idc_charge'],
                    misc_charges          = row.get('misc_charges', Decimal('0')),
                    total_billed          = row['total_billed'],
                    shipment_type         = stype,
                ))

            # ── 5. Bulk save ─────────────────────────────────────────────────
            with transaction.atomic():
                CourierInvoiceLine.objects.bulk_create(
                    line_objects,
                    ignore_conflicts=True,   # skip duplicates on re-upload
                )

            # ── 6. Discrepancy analysis ──────────────────────────────────────
            disc_stats = analyse_invoice(invoice.id, org_id)

            # Calculate and save product type
            cod_count = invoice.lines.filter(shipment__payment_type__in=['COD', 'Partially Paid']).count()
            matched_count = invoice.lines.exclude(shipment=None).count()
            if matched_count > 0:
                invoice.product_type = 'COD' if (cod_count / matched_count > 0.5) else 'Prepaid'
            else:
                # Fallback if no shipments matched: check product codes
                cod_code_count = invoice.lines.filter(Q(product_code__icontains='C') | Q(product_code__icontains='COD')).count()
                total_count = invoice.lines.count()
                invoice.product_type = 'COD' if (total_count > 0 and cod_code_count / total_count > 0.5) else 'Prepaid'
            invoice.save(update_fields=['product_type'])

            return Response({
                'invoice_id':       invoice.id,
                'invoice_number':   invoice.invoice_number,
                'courier_partner':  courier_partner,
                'total_rows':       len(rows),
                'forward':          type_counts.get('Forward', 0),
                'rto':              type_counts.get('RTO', 0),
                'returns':          type_counts.get('Return',  0),
                'exchanges':        type_counts.get('Exchange',0),
                'credits':          type_counts.get('Credit',  0),
                'unmatched_awbs':   unmatched,
                'discrepancies':    disc_stats,
            })

        except NotImplementedError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.exception("InvoiceExcelUploadView error: %s", e)
            return Response({'error': str(e)}, status=500)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# ==============================================================================
# 2. INVOICE LINE LIST
# ==============================================================================
class InvoiceLineListView(APIView):
    """
    GET /api/delivery/invoices/<invoice_id>/lines/
    Filters: discrepancy_type, shipment_type, min_overcharge, page, limit
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        page   = int(request.query_params.get('page', 1))
        limit  = min(int(request.query_params.get('limit', 50)), 200)
        offset = (page - 1) * limit

        disc_filter    = request.query_params.get('discrepancy_type', '')
        type_filter    = request.query_params.get('shipment_type', '')
        min_overcharge = request.query_params.get('min_overcharge', '')
        is_disputed_filter = request.query_params.get('is_disputed', '')

        # The base queryset for the invoice
        base_qs = CourierInvoiceLine.objects.filter(
            freight_invoice=invoice, org_id=org_id,
        )

        qs = base_qs.select_related('shipment', 'shipment__order', 'dispute').order_by('-overcharge_amount', 'awb_number')

        if disc_filter:
            if disc_filter == 'all_discrepancies':
                qs = qs.exclude(discrepancy_type='None')
            else:
                qs = qs.filter(discrepancy_type=disc_filter)
        if type_filter:
            if ',' in type_filter:
                types = [t.strip() for t in type_filter.split(',') if t.strip()]
                qs = qs.filter(shipment_type__in=types)
            else:
                qs = qs.filter(shipment_type=type_filter)
        if min_overcharge:
            try:
                qs = qs.filter(overcharge_amount__gte=Decimal(min_overcharge))
            except Exception:
                pass
        if is_disputed_filter:
            is_disp = is_disputed_filter.lower() == 'true'
            qs = qs.filter(is_disputed=is_disp)

        total_count = qs.count()
        
        # Aggregate on the UNFILTERED base_qs so the KPI strip stays consistent
        agg = base_qs.aggregate(
            agg_total_billed=Coalesce(Sum('total_billed'), Value(0), output_field=DecimalField()),
            total_overcharge=Coalesce(Sum('overcharge_amount'), Value(0), output_field=DecimalField()),
            wrong_slab_count=Count('id', filter=Q(discrepancy_type='WrongSlab', overcharge_amount__gt=0)),
            no_match_count  =Count('id', filter=Q(discrepancy_type='NoMatch', overcharge_amount__gt=0)),
            disputed_count  =Count('id', filter=Q(is_disputed=True)),
            total_lines     =Count('id'),
            rto_count       =Count('id', filter=Q(shipment_type='RTO')),
            return_count    =Count('id', filter=Q(shipment_type__in=['Return', 'Exchange'])),
            discrepancy_count=Count('id', filter=~Q(discrepancy_type='None') & Q(overcharge_amount__gt=0)),
        )
        # Resolve rate card and surcharges once at the view level
        from core.models.delivery import CourierRateCard
        rate_card = CourierRateCard.objects.filter(
            org_id=org_id,
            courier_partner__icontains=invoice.courier_partner,
            is_active=True,
        ).first()

        from core.services.zone_engine import resolve_surcharges
        fs_percent, caf_percent = (
            resolve_surcharges(rate_card, org_id, invoice.invoice_date)
            if rate_card
            else (Decimal('0'), Decimal('0'))
        )

        from core.services.billing_strategy import get_billing_strategy
        try:
            strategy = get_billing_strategy(invoice.courier_partner)
        except Exception:
            strategy = None

        warehouse = Warehouse.objects.filter(org_id=org_id, is_default=True, is_active=True).first()
        if not warehouse:
            warehouse = Warehouse.objects.filter(org_id=org_id, is_active=True).first()

        lines = qs[offset:offset + limit]

        # Bulk query zone mappings to avoid N+1 queries
        from core.models.delivery import CourierZoneMapping
        
        line_pincodes = {}
        dest_pincodes_set = set()
        for ln in lines:
            pcode = ln.dest_pincode
            if not pcode and ln.shipment and ln.shipment.order and ln.shipment.order.shipping_pincode:
                pcode = ln.shipment.order.shipping_pincode
            if pcode:
                line_pincodes[ln.id] = pcode
                dest_pincodes_set.add(pcode)

        mappings = CourierZoneMapping.objects.filter(
            org_id=org_id,
            courier_partner=invoice.courier_partner,
            pincode__in=list(dest_pincodes_set)
        )
        mapping_dict = {m.pincode: m.zone_code.upper() for m in mappings}

        data = []
        for ln in lines:
            pcode = line_pincodes.get(ln.id)
            zone = None
            if warehouse and pcode:
                zone = get_mapped_zone(org_id, warehouse.pincode, pcode, invoice.courier_partner)
            if not zone and ln.shipment and ln.shipment.zone:
                zone = ln.shipment.zone
            if not zone:
                zone = infer_zone_from_freight(ln.freight, ln.charged_weight_kg)

            zone_code = mapping_dict.get(pcode) if pcode else None

            # Compute dynamic expected breakdowns for UI drilldown side-by-side
            expected_fsc = 0.0
            expected_caf = 0.0
            expected_efss = 0.0
            expected_cod = 0.0
            expected_rvp_charge = 0.0

            if rate_card and strategy and zone:
                is_cod = ln.shipment is not None and ln.shipment.payment_type in ('COD', 'Partially Paid')
                is_forward_cod = is_cod and ln.shipment_type not in ('RTO', 'Return', 'Exchange')
                invoice_value = Decimal(str(ln.shipment.order.total_price or 0)) if (is_cod and ln.shipment and ln.shipment.order) else Decimal('0')

                breakdown = strategy.compute_full_breakdown(
                    zone=zone,
                    weight_kg=Decimal('0.5'),
                    service_type=ln.product_code or '',
                    is_cod=is_forward_cod,
                    invoice_value=invoice_value,
                    rate_card=rate_card,
                    slabs=[],
                    fs_percent=fs_percent,
                    caf_percent=caf_percent
                )
                if breakdown:
                    expected_fsc = float(breakdown.fs)
                    expected_caf = float(breakdown.caf)
                    expected_efss = float(breakdown.efss)
                    expected_cod = float(breakdown.cod)

                if rate_card and ln.shipment_type in ('Return', 'Exchange'):
                    expected_rvp_charge = float(rate_card.reverse_pickup_charge)

            data.append({
                'id':                   ln.id,
                'awb_number':           ln.awb_number,
                'courier_ref':          ln.courier_ref,
                'product_code':         ln.product_code,
                'shipment_type':        ln.shipment_type,
                'dest_area':            ln.dest_area,
                'dest_pincode':         ln.dest_pincode,
                'commodity':            (ln.commodity or '')[:80],
                'actual_weight_kg':     float(ln.actual_weight_kg),
                'charged_weight_kg':    float(ln.charged_weight_kg),
                'expected_weight_kg':   float(ln.expected_weight_kg),
                'pieces':               ln.pieces,
                'freight':              float(ln.freight),
                'fsc':                  float(ln.fsc),
                'caf':                  float(ln.caf),
                'efss':                 float(ln.efss),
                'fod_charge':           float(ln.fod_charge),
                'declared_value_charge':float(ln.declared_value_charge),
                'misc_charges':         float(ln.misc_charges),
                'total_billed':         float(ln.total_billed),
                'tax_cgst':             float(ln.tax_cgst),
                'tax_sgst':             float(ln.tax_sgst),
                'total_billed_with_tax': float(ln.total_billed_with_tax),
                'expected_freight':     float(ln.expected_freight)  if ln.expected_freight is not None else None,
                'expected_total':       float(ln.expected_total)    if ln.expected_total   is not None else None,
                'expected_pdf_amount':  float(ln.expected_pdf_amount) if ln.expected_pdf_amount is not None else None,
                'expected_net_amount':  float(ln.expected_net_amount) if ln.expected_net_amount is not None else None,
                'expected_fsc':         expected_fsc,
                'expected_caf':         expected_caf,
                'expected_efss':        expected_efss,
                'expected_cod':         expected_cod,
                'expected_rvp_charge':  expected_rvp_charge,
                'expected_tax_cgst':    float(ln.expected_tax_cgst),
                'expected_tax_sgst':    float(ln.expected_tax_sgst),
                'expected_total_with_tax': float(ln.expected_total_with_tax),
                'overcharge_amount':    float(ln.overcharge_amount),
                'discrepancy_type':     ln.discrepancy_type,
                'discrepancy_notes':    ln.discrepancy_notes,
                'anomaly_category':     ln.anomaly_category or '',
                'confidence_score':     ln.confidence_score or 0,
                'billing_layer':        ln.billing_layer or '',
                'is_disputed':          ln.is_disputed,
                'dispute_id':           ln.dispute_id,
                'dispute_status':       ln.dispute.status if ln.dispute else None,
                'order_number':         (ln.shipment.order.order_number if ln.shipment and ln.shipment.order else None),
                'current_stage':        ln.shipment.current_stage if ln.shipment else None,
                'payment_type':         ln.shipment.payment_type  if ln.shipment else None,
                'zone':                 zone,
                'zone_code':            zone_code,
            })

        return Response({
            'lines': data, 'count': total_count, 'page': page, 'limit': limit,
            'invoice': {
                'id': invoice.id, 'invoice_number': invoice.invoice_number,
                'courier_partner': invoice.courier_partner,
                'invoice_date': str(invoice.invoice_date), 'status': invoice.status,
            },
            'summary': {
                'total_billed':     float(agg['agg_total_billed']),
                'total_overcharge': float(agg['total_overcharge']),
                'wrong_slab_count': agg['wrong_slab_count'],
                'no_match_count':   agg['no_match_count'],
                'disputed_count':   agg['disputed_count'],
                'total_lines':      agg['total_lines'],
                'rto_count':        agg['rto_count'],
                'return_count':     agg['return_count'],
                'discrepancy_count': agg['discrepancy_count'],
            },
        })


# ==============================================================================
# 3. SINGLE LINE DISPUTE / DISMISS
# ==============================================================================
class InvoiceLineDisputeView(APIView):
    """
    POST /api/delivery/invoices/<invoice_id>/lines/<line_id>/dispute/
    body: { "action": "file" | "dismiss" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id, line_id):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
            line    = CourierInvoiceLine.objects.get(
                id=line_id, freight_invoice=invoice, org_id=org_id
            )
        except (FreightInvoice.DoesNotExist, CourierInvoiceLine.DoesNotExist):
            return Response({'error': 'Not found'}, status=404)

        action = request.data.get('action', 'file')

        if action == 'dismiss':
            line.is_disputed = False
            line.dispute     = None
            line.discrepancy_notes += ' [Accepted — no dispute filed]'
            line.save(update_fields=['is_disputed', 'dispute', 'discrepancy_notes'])
            return Response({'message': 'Line accepted, no dispute filed.'})

        if action == 'file':
            if line.is_disputed:
                return Response({'message': 'Dispute already filed.', 'dispute_id': line.dispute_id})
            if line.overcharge_amount <= 0:
                return Response({'error': 'No overcharge to dispute.'}, status=400)

            reason_map = {
                'WrongSlab':     f"Wrong weight slab: Billed {line.charged_weight_kg}kg slab, should be {line.expected_weight_kg}kg (product <250g). Overcharge ₹{line.overcharge_amount}",
                'UnexpectedFOD': f"FOD ₹{line.fod_charge} charged on Prepaid order",
                'UnexpectedRTO': f"RTO billed but shipment stage is not RTO",
                'NoMatch':       f"AWB {line.awb_number} not in our system",
                'Multiple':      line.discrepancy_notes[:255],
            }
            reason = reason_map.get(line.discrepancy_type, line.discrepancy_notes[:255])

            dispute = ShipmentDispute.objects.create(
                org_id=org_id, shipment=line.shipment, freight_invoice=invoice,
                disputed_amount=line.overcharge_amount, reason=reason, status='Open',
            )
            line.dispute = dispute
            line.is_disputed = True
            line.save(update_fields=['dispute', 'is_disputed'])

            return Response({
                'message': 'Dispute filed.', 'dispute_id': dispute.id,
                'disputed_amount': float(dispute.disputed_amount),
            })

        return Response({'error': f'Unknown action: {action}'}, status=400)


# ==============================================================================
# 4. BULK DISPUTE ALL FLAGGED LINES
# ==============================================================================
class InvoiceDisputeAllView(APIView):
    """
    POST /api/delivery/invoices/<invoice_id>/dispute-all/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        lines = CourierInvoiceLine.objects.filter(
            freight_invoice=invoice, org_id=org_id,
            is_disputed=False, overcharge_amount__gt=0,
        ).exclude(discrepancy_type__in=['None', 'CreditNote'])

        created  = 0
        disputed = Decimal('0')

        with transaction.atomic():
            for ln in lines:
                reason = (
                    f"{ln.discrepancy_type}: Billed ₹{ln.total_billed}, "
                    f"Expected ₹{ln.expected_total or 0}. AWB: {ln.awb_number}"
                )[:255]
                d = ShipmentDispute.objects.create(
                    org_id=org_id, shipment=ln.shipment, freight_invoice=invoice,
                    disputed_amount=ln.overcharge_amount, reason=reason, status='Open',
                )
                ln.dispute = d
                ln.is_disputed = True
                ln.save(update_fields=['dispute', 'is_disputed'])
                created  += 1
                disputed += ln.overcharge_amount

        return Response({
            'message': f'{created} disputes filed.',
            'disputes_filed': created,
            'total_disputed': float(disputed),
        })


# ==============================================================================
# 5. DISPUTE REPORT CSV EXPORT
# ==============================================================================
class InvoiceDisputeReportView(APIView):
    """
    GET /api/delivery/invoices/<invoice_id>/dispute-report/
    Returns a CSV for the courier SPOC.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        import csv, io

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        lines = CourierInvoiceLine.objects.filter(
            freight_invoice=invoice, org_id=org_id,
            overcharge_amount__gt=0
        ).exclude(discrepancy_type__in=['None', 'CreditNote']).order_by('-overcharge_amount')

        output = io.StringIO()
        w = csv.writer(output)
        w.writerow([
            'AWB Number', 'Our Reference', 'Type',
            'Destination', 'Pincode', 'Product',
            'Our Actual Wt (kg)', 'Bluedart Actual Wt (kg)', 'Bluedart Charged Slab (kg)',
            'Billed Freight', 'Correct Freight',
            'Total Billed', 'Expected Total', 'Overcharge (Rs)',
            'Issue', 'Notes',
        ])

        tb = Decimal('0')
        te = Decimal('0')
        to = Decimal('0')

        for ln in lines:
            pcode = ln.dest_pincode or (ln.shipment.order.shipping_pincode if ln.shipment and ln.shipment.order else '')
            w.writerow([
                ln.awb_number, ln.courier_ref, ln.shipment_type,
                ln.dest_area, pcode, (ln.commodity or '')[:80],
                float(ln.expected_weight_kg), float(ln.actual_weight_kg), float(ln.charged_weight_kg),
                float(ln.freight), float(ln.expected_freight) if ln.expected_freight else '',
                float(ln.total_billed), float(ln.expected_total) if ln.expected_total else '',
                float(ln.overcharge_amount),
                ln.discrepancy_type, ln.discrepancy_notes[:200],
            ])
            tb += ln.total_billed
            te += ln.expected_total or Decimal('0')
            to += ln.overcharge_amount

        w.writerow([])
        w.writerow(['TOTAL', '', '', '', '', '', '', '', '',
                    '', '', float(tb), float(te), float(to), '', ''])

        filename = f"dispute_{invoice.courier_partner}_{invoice.invoice_number}.csv"
        
        # Add UTF-8 BOM prefix to ensure Excel reads the currency symbols correctly
        csv_content = "\ufeff" + output.getvalue()
        
        resp = HttpResponse(csv_content.encode('utf-8'), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ==============================================================================
# 6. BILLING PATTERNS (Pattern Learning Dashboard)
# ==============================================================================
class BillingPatternsView(APIView):
    """
    GET /api/delivery/billing-patterns/
    Returns learned billing clusters by city/zone for the dashboard.

    Query params:
        city   — filter by city name (partial match)
        zone   — filter by zone
        limit  — max clusters to return (default 50)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        city = request.query_params.get('city', '')
        zone = request.query_params.get('zone', '')

        from core.services.pattern_learning import PatternLearningEngine
        engine = PatternLearningEngine(org_id)
        clusters = engine.get_billing_clusters(city=city or None, zone=zone or None)

        return Response({
            'clusters': clusters,
            'total_cities': len(clusters),
        })


# ==============================================================================
# 7. RECONCILIATION DASHBOARD (Aggregated Stats)
# ==============================================================================
class ReconciliationDashboardView(APIView):
    """
    GET /api/delivery/reconciliation-dashboard/
    Returns aggregated reconciliation statistics across all invoices.

    Query params:
        invoice_id — optional, restrict to a single invoice
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        invoice_id = request.query_params.get('invoice_id')

        from django.db.models import Avg

        qs = CourierInvoiceLine.objects.filter(org_id=org_id)
        if invoice_id:
            qs = qs.filter(freight_invoice_id=invoice_id)

        # Anomaly category breakdown
        anomaly_agg = qs.values('anomaly_category').annotate(
            count=Count('id')
        ).order_by('-count')

        anomaly_breakdown = {}
        for row in anomaly_agg:
            cat = row['anomaly_category'] or 'unclassified'
            anomaly_breakdown[cat] = row['count']

        # Discrepancy type breakdown
        disc_agg = qs.values('discrepancy_type').annotate(
            count=Count('id')
        ).order_by('-count')

        disc_breakdown = {}
        for row in disc_agg:
            disc_breakdown[row['discrepancy_type']] = row['count']

        # Confidence distribution
        conf_agg = qs.aggregate(
            avg_confidence=Avg('confidence_score'),
            total_lines=Count('id'),
            high_confidence=Count('id', filter=Q(confidence_score__gte=80)),
            medium_confidence=Count('id', filter=Q(confidence_score__gte=50, confidence_score__lt=80)),
            low_confidence=Count('id', filter=Q(confidence_score__lt=50)),
        )

        # Billing layer breakdown
        layer_agg = qs.values('billing_layer').annotate(
            count=Count('id')
        ).order_by('-count')

        layer_breakdown = {}
        for row in layer_agg:
            layer_breakdown[row['billing_layer'] or 'unknown'] = row['count']

        # Financial summary
        financial_agg = qs.aggregate(
            total_billed=Sum('total_billed'),
            total_expected=Sum('expected_total'),
            total_overcharge=Sum('overcharge_amount'),
            total_freight=Sum('freight'),
            total_fsc=Sum('fsc'),
            total_caf=Sum('caf'),
            total_fod=Sum('fod_charge'),
        )

        return Response({
            'anomaly_breakdown': anomaly_breakdown,
            'discrepancy_breakdown': disc_breakdown,
            'confidence': {
                'average': round(conf_agg['avg_confidence'] or 0),
                'total_lines': conf_agg['total_lines'],
                'high': conf_agg['high_confidence'],
                'medium': conf_agg['medium_confidence'],
                'low': conf_agg['low_confidence'],
            },
            'billing_layers': layer_breakdown,
            'financials': {
                'total_billed': float(financial_agg['total_billed'] or 0),
                'total_expected': float(financial_agg['total_expected'] or 0),
                'total_overcharge': float(financial_agg['total_overcharge'] or 0),
                'total_freight': float(financial_agg['total_freight'] or 0),
                'total_fsc': float(financial_agg['total_fsc'] or 0),
                'total_caf': float(financial_agg['total_caf'] or 0),
                'total_fod': float(financial_agg['total_fod'] or 0),
            },
        })


# ==============================================================================
# 8. SINGLE INVOICE RE-ANALYSE
# ==============================================================================
class InvoiceReanalyseView(APIView):
    """
    POST /api/delivery/invoices/<invoice_id>/reanalyse/

    Re-runs the full discrepancy analysis on a single existing invoice.
    ALL lines are re-analysed — including previously disputed ones — so
    updated zone mappings are reflected immediately without re-uploading
    the invoice file.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        from core.services.discrepancy_engine import analyse_invoice

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        try:
            stats = analyse_invoice(invoice.id, org_id)
            return Response({
                'message': f'Re-analysis complete for invoice {invoice.invoice_number}.',
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'stats': stats,
            })
        except Exception as e:
            logger.exception('InvoiceReanalyseView error: %s', e)
            return Response({'error': str(e)}, status=500)


# ==============================================================================
# 9. BULK RE-ANALYSE ALL INVOICES
# ==============================================================================
class InvoiceBulkReanalyseView(APIView):
    """
    POST /api/delivery/invoices/reanalyse-all/

    Re-runs discrepancy analysis on ALL FreightInvoices for this org,
    regardless of their current status. ALL lines are re-analysed —
    including disputed ones — so that updated zone mappings (e.g. after
    uploading a new JAIPUR TAT.xlsx) are reflected across every invoice.

    Called automatically by the zone mapping upload endpoint, but can
    also be triggered manually from the frontend.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from core.services.discrepancy_engine import analyse_invoice
        from decimal import Decimal

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        invoices = FreightInvoice.objects.filter(org_id=org_id)
        total = invoices.count()

        if total == 0:
            return Response({
                'message': 'No invoices found for this organization.',
                'invoices_reanalysed': 0,
            })

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
                logger.warning('Re-analyse failed for invoice %s: %s', invoice.id, e)
                combined['errors'] += 1

        combined['total_overcharge'] = str(total_overcharge.quantize(Decimal('0.01')))

        return Response({
            'message': (
                f"Re-analysis complete. {combined['invoices_reanalysed']} of {total} "
                f"invoices processed, {combined['errors']} errors."
            ),
            **combined,
        })

