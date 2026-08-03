import logging
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import Order, RTOEngineItem, LineItem, RTOEngineBatch, TrackingInfo, Shipment
from .permissions import HasModulePermission

logger = logging.getLogger(__name__)


def _get_org_id_from_user(user):
    """Return the organisation ID for the authenticated user."""
    if hasattr(user, 'shop_credentials'):
        try:
            return user.shop_credentials.organization_id
        except Exception:
            pass
    try:
        membership = user.workspace_memberships.first()
        if membership and membership.workspace:
            return membership.workspace.organization_id
    except Exception:
        pass
    try:
        return user.team_settings.organization.organization_id
    except Exception:
        return None


def _send_items_to_inventory(org_id, rto_items):
    """
    For each RTOEngineItem in rto_items, find the matching InventoryItem
    in the product_inventory table (matched by line_item.sku against
    final_sku / master_sku) and increment actual_quantity by the
    line item quantity.
    """
    if not org_id:
        raise ValueError("Organization ID is required to update inventory.")

    from inventory.models import InventoryTable, InventoryItem

    table, _ = InventoryTable.objects.get_or_create(
        organization_id=org_id,
        table_key='product_inventory',
        defaults={'columns': [
            {'id': 'master_sku', 'label': 'Master SKU', 'type': 'text', 'visible': True},
            {'id': 'final_sku', 'label': 'Final SKU', 'type': 'text', 'visible': True},
            {'id': 'actual_quantity', 'label': 'Actual Quantity', 'type': 'number', 'visible': True},
            {'id': 'unit', 'label': 'Unit', 'type': 'text', 'visible': True},
            {'id': 'location', 'label': 'Location', 'type': 'text', 'visible': True},
        ]},
    )

    inv_items = list(InventoryItem.objects.filter(table=table))

    def normalize(v):
        return str(v or '').strip().upper()

    def normalize_name(v):
        return str(v or '').strip().lower()

    # Build map: normalized SKU → InventoryItem (first match wins)
    sku_map = {}
    name_map = {}
    for inv in inv_items:
        d = inv.data or {}
        for key in ['final_sku', 'master_sku', 'sku']:
            k = normalize(d.get(key))
            if k and k not in sku_map:
                sku_map[k] = inv
        # Also build name map for fallback
        for key in ['name', 'product_name', 'title']:
            n = normalize_name(d.get(key))
            if n and n not in name_map:
                name_map[n] = inv

    with transaction.atomic():
        for item in rto_items:
            li = item.line_item
            if not li:
                continue
            qty = li.quantity or 1

            # Try SKU match first, then fall back to product name
            inv_item = None
            if li.sku:
                inv_item = sku_map.get(normalize(li.sku))
            if inv_item is None:
                # Fallback: match by product full name (title or name field)
                for name_val in [li.title, li.name]:
                    if name_val:
                        inv_item = name_map.get(normalize_name(name_val))
                        if inv_item:
                            break

            # If SKU is not present yet in product_inventory, create a row so
            # RTO movements can immediately reflect in Actual Quantity.
            if inv_item is None and li.sku:
                inv_item = InventoryItem.objects.create(
                    table=table,
                    data={
                        'master_sku': '',
                        'final_sku': str(li.sku).strip(),
                        'actual_quantity': 0,
                        'unit': 'PCS',
                        'location': '',
                        'name': li.title or li.name or '',
                    },
                )
                sku_map[normalize(li.sku)] = inv_item
                if li.title:
                    name_map[normalize_name(li.title)] = inv_item
                if li.name:
                    name_map[normalize_name(li.name)] = inv_item

            if inv_item:
                current = 0
                try:
                    current = int(inv_item.data.get('actual_quantity') or 0)
                except (ValueError, TypeError):
                    current = 0
                inv_item.data['actual_quantity'] = current + qty
                inv_item.save(update_fields=['data', 'updated_at'])


# ─── helpers ────────────────────────────────────────────────────────────────

def _find_order(inp, org_id):
    """
    Look up an Order by scan input (order number or AWB), scoped to org_id.
    Returns (order, courier_partner_str).

    Lookup priority:
      1. Pure-digit (len < 8) → Order.order_number (indexed integer lookup)
      2. Shipment.awb_number (indexed, single JOIN to Order, prefetch line items)
      3. TrackingInfo.number exact match (indexed, prefetch line items)
    """
    if not org_id:
        return None, ""

    order = None
    courier = ""

    # 1) Order number (digits-only, len < 8 to skip AWB matches and avoid full table scan)
    if inp.isdigit() and len(inp) < 8:
        try:
            val = int(inp)
            order = (
                Order.objects
                .defer('raw_data')
                .filter(order_number=val, org_id=org_id)
                .prefetch_related('line_items')
                .first()
            )
            if order:
                # Try to get courier from Shipment relation
                try:
                    courier = order.shipment.courier_partner or ""
                except Exception:
                    pass
                # Fallback: get courier from TrackingInfo.company
                if not courier:
                    ti = TrackingInfo.objects.filter(
                        fulfillment__order=order, company__isnull=False
                    ).exclude(company='').values_list('company', flat=True).first()
                    if ti:
                        courier = ti
                return order, courier
        except ValueError:
            pass

    # 2) Shipment.awb_number — single JOIN to Order, gives courier_partner
    shp = (
        Shipment.objects
        .filter(awb_number__iexact=inp, order__org_id=org_id)
        .select_related('order')
        .defer('order__raw_data')
        .prefetch_related('order__line_items')
        .first()
    )
    if shp:
        order = shp.order
        courier = shp.courier_partner or ""
        return order, courier

    # 3) TrackingInfo.number — exact match, get courier from .company
    ti = (
        TrackingInfo.objects
        .filter(number__iexact=inp, fulfillment__order__org_id=org_id)
        .select_related('fulfillment__order')
        .defer('fulfillment__order__raw_data')
        .prefetch_related('fulfillment__order__line_items')
        .first()
    )
    if ti:
        order = ti.fulfillment.order
        courier = ti.company or ti.fulfillment.service or ""
        return order, courier

    return None, ""


def _order_detail(order, courier_partner=""):
    """
    Serialize an order into the payload needed by the scanner UI.
    Accepts an optional pre-resolved courier_partner string.
    """
    items = [
        {
            "title": li.title,
            "sku": li.sku or "",
            "quantity": li.quantity,
            "price": str(li.price),
        }
        for li in order.line_items.all()
    ]
    awb = order.awb_number

    # If courier_partner wasn't passed, try to resolve it
    if not courier_partner:
        try:
            courier_partner = order.shipment.courier_partner or ""
        except Exception:
            # Get from TrackingInfo.company as last resort
            try:
                ti = TrackingInfo.objects.filter(
                    fulfillment__order=order, company__isnull=False
                ).exclude(company='').values_list('company', flat=True).first()
                if ti:
                    courier_partner = ti
            except Exception:
                pass

    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer": f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        "phone": order.contact_phone or "",
        "email": order.contact_email or "",
        "awb": awb or "",
        "total_price": str(order.total_price or 0),
        "payment": ", ".join(order.payment_gateway_names) if order.payment_gateway_names else "",
        "financial_status": order.financial_status or "",
        "current_status": order.current_status or "",
        "items": items,
        "rto_internal_status": order.rto_internal_status,
        "shipping_state": order.shipping_state or "",
        "shipping_pincode": order.shipping_pincode or "",
        "courier_partner": courier_partner,
    }


def _engine_item_detail(item):
    li = item.line_item
    batch = item.rto_engine_batch
    courier_partner = ""
    payment_type = ""
    try:
        if hasattr(item.order, 'shipment') and item.order.shipment:
            courier_partner = item.order.shipment.courier_partner or ""
            payment_type = item.order.shipment.payment_type or ""
    except Exception:
        pass

    # Fallback to TrackingInfo for courier_partner
    if not courier_partner:
        try:
            ti = TrackingInfo.objects.filter(
                fulfillment__order=item.order
            ).only('company', 'fulfillment__service').first()
            if ti:
                courier_partner = ti.company or ti.fulfillment.service or ""
        except Exception:
            pass

    if not courier_partner:
        courier_partner = "Unknown"

    if not payment_type:
        try:
            gws = [g.lower() for g in item.order.payment_gateway_names if g]
            if any('cod' in gw or 'cash' in gw for gw in gws):
                payment_type = "COD"
            elif any('partial' in gw or 'ppcod' in gw for gw in gws):
                payment_type = "PPCOD"
            else:
                payment_type = "Prepaid"
        except Exception:
            payment_type = "Prepaid"

    # Normalize payment_type
    p_type_lower = (payment_type or "").strip().lower()
    if "ppcod" in p_type_lower or "partial" in p_type_lower:
        payment_type = "PPCOD"
    elif "cod" in p_type_lower or "cash" in p_type_lower:
        payment_type = "COD"
    else:
        payment_type = "Prepaid"


    return {
        "id": item.id,
        "order_number": item.order.order_number,
        "order_id": item.order.id,
        "order_date": item.order.created_at.isoformat() if item.order.created_at else None,
        "customer": f"{item.order.customer_first_name or ''} {item.order.customer_last_name or ''}".strip(),
        "phone": item.order.contact_phone or "",
        "awb": item.order.awb_number or "",
        "total_price": str(item.order.total_price or 0),
        "payment": ", ".join(item.order.payment_gateway_names) if item.order.payment_gateway_names else "",
        "courier_partner": courier_partner,
        "payment_type": payment_type,
        # Line-item level fields
        "product_title": li.title if li else "",
        "product_sku": li.sku or "" if li else "",
        "product_quantity": li.quantity if li else 0,
        "product_price": str(li.price) if li else "",
        "product_variant": li.name or li.title if li else "",
        "scan_status": item.scan_status,
        "scanned_at": item.scanned_at.isoformat() if item.scanned_at else None,
        "scanned_by": item.scanned_by.get_full_name() if item.scanned_by else "",
        "scan_notes": item.scan_notes or "",
        "qc_notes": item.qc_notes or "",
        "qc_by": item.qc_by.get_full_name() if item.qc_by else "",
        "qc_at": item.qc_at.isoformat() if item.qc_at else None,
        "investigation_notes": item.investigation_notes or "",
        "investigation_status": item.investigation_status or "",
        "resolved_by": item.resolved_by.get_full_name() if item.resolved_by else "",
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "write_off_reason": item.write_off_reason or "",
        "repair_stage": item.repair_stage or "",
        "repair_stage_label": item.get_repair_stage_display() if item.repair_stage else "",
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        # Batch grouping
        "batch_id": batch.id if batch else None,
        "batch_number": batch.batch_number if batch else None,
        "batch_display_name": batch.display_name if batch else None,
    }


def _apply_common_filters(qs, request):
    """Apply search, date-range and sort to an RTOEngineItem queryset."""
    search = request.query_params.get("search", "").strip()
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    sort = request.query_params.get("sort", "-scanned_at")

    if search:
        # Match order fields, AWB number, customer name, contact phone, or tracking number
        q_filter = Q(
            Q(order__order_number__icontains=search)
            | Q(order__customer_first_name__icontains=search)
            | Q(order__customer_last_name__icontains=search)
            | Q(order__contact_phone__icontains=search)
            | Q(order__awb_number__icontains=search)
            | Q(order__fulfillments__tracking_info__number__icontains=search)
        )

        # Batch matching logic:
        # Check if the search matches a batch display name or batch number.
        # Extract number if they search "batch 12", "rto batch 12", "b12", or just "12".
        import re
        norm = search.lower()
        
        # Check if search contains "janki" followed by digits (e.g. "janki23456" or "janki 23456")
        janki_match = re.search(r'janki\D*(\d+)', norm)
        if janki_match:
            order_num = janki_match.group(1)
            q_filter |= Q(order__order_number__icontains=order_num)

        match = re.search(r'(?:batch|b)?\s*(\d+)', norm)
        if match:
            try:
                batch_num = int(match.group(1))
                q_filter |= Q(rto_engine_batch__batch_number=batch_num)
            except ValueError:
                pass

        qs = qs.filter(q_filter).distinct()
    if date_from:
        qs = qs.filter(scanned_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(scanned_at__date__lte=date_to)

    allowed_sorts = {
        "scanned_at", "-scanned_at", "order__order_number", "-order__order_number",
        "updated_at", "-updated_at",
    }
    if sort in allowed_sorts:
        qs = qs.order_by(sort)

    return qs

def _cache_rto_scan_payload(org_id, order, courier_partner=""):
    from django.core.cache import cache
    payload = _order_detail(order, courier_partner)
    keys = [
        f"org:{org_id}:rto_scan:ident:{order.order_number}",
        f"org:{org_id}:rto_scan:ident:{order.id}",
    ]
    if payload.get("awb"):
        keys.append(f"org:{org_id}:rto_scan:ident:{payload['awb']}")
        keys.append(f"org:{org_id}:rto_scan:ident:{payload['awb'].upper()}")
    try:
        ti_numbers = TrackingInfo.objects.filter(fulfillment__order=order).values_list('number', flat=True)
        for num in ti_numbers:
            if num:
                keys.append(f"org:{org_id}:rto_scan:ident:{num}")
                keys.append(f"org:{org_id}:rto_scan:ident:{num.upper()}")
    except Exception:
        pass
    for k in keys:
        if k:
            cache.set(k, payload, timeout=86400)
    return payload


def _get_rto_item_status(order_id):
    from django.core.cache import cache
    cache_key = f"rto_item_status:order_id:{order_id}"
    status_data = cache.get(cache_key)
    if status_data is not None:
        return status_data

    existing = RTOEngineItem.objects.filter(order_id=order_id).order_by('-scanned_at').first()
    if existing:
        status_data = {
            "already_scanned": True,
            "existing_status": existing.get_scan_status_display(),
            "scanned_at": existing.scanned_at.isoformat() if existing.scanned_at else None,
        }
    else:
        status_data = {
            "already_scanned": False,
        }
    cache.set(cache_key, status_data, timeout=86400)
    return status_data


# ─── views ──────────────────────────────────────────────────────────────────

class RTOEngineScanView(APIView):
    """
    POST { scan_input } → returns order details for the scanner tab.
    Looks up by AWB / order number.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        scan_input = request.data.get("scan_input", "").strip()
        if not scan_input:
            return Response({"error": "scan_input is required"}, status=400)

        # ── Fast path: Cache ──
        from django.core.cache import cache
        cached_payload = cache.get(f"org:{org_id}:rto_scan:ident:{scan_input}")
        if cached_payload:
            return Response({"order": cached_payload})

        # ── Slow path: DB ──
        order, courier = _find_order(scan_input, org_id)
        if not order:
            return Response({"error": "Order not found. Check the AWB or Order number."}, status=404)

        payload = _cache_rto_scan_payload(org_id, order, courier)
        return Response({"order": payload})


class RTOEngineDispatchView(APIView):
    """
    POST { order_id, action, notes }
    action ∈ { pending_qc | suspicious | damaged }
    Creates (or updates) an RTOEngineItem for this order.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': [
            'rto_module:rto_engine:create',
            'rto_module:rto_engine:edit',
            'rto_module:rto_manager:edit',
            'rto_module:rto_manager:create',
            'rto_module:rto_in_transit:create',
            'rto_module:rto_in_transit:edit',
        ],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        order_id = request.data.get("order_id")
        action = request.data.get("action", "").strip()
        notes = request.data.get("notes", "").strip()
        write_off_reason = request.data.get("write_off_reason", "").strip()
        repair_stage = request.data.get("repair_stage", "").strip()

        VALID_ACTIONS = {"pending_qc", "suspicious", "damaged", "send_for_repair", "write_off"}
        if action not in VALID_ACTIONS:
            return Response(
                {"error": f"action must be one of {VALID_ACTIONS}"}, status=400
            )

        if action == "write_off":
            valid_reasons = {"not_our_product", "fraud"}
            if write_off_reason not in valid_reasons:
                return Response({"error": "write_off_reason must be not_our_product or fraud"}, status=400)
        if action == "send_for_repair" and repair_stage:
            valid_stages = {value for value, _ in RTOEngineItem.REPAIR_STAGE_CHOICES}
            if repair_stage not in valid_stages:
                return Response({"error": "Invalid repair_stage"}, status=400)

        ACTION_STATUS = {
            "pending_qc":     "pending_qc",
            "suspicious":     "suspicious",
            "damaged":        "damaged",
            "send_for_repair": "sent_for_repair",
            "write_off":      "written_off",
        }
        scan_status = ACTION_STATUS[action]

        try:
            order = Order.objects.prefetch_related('line_items').get(pk=order_id, org_id=org_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        line_items = list(order.line_items.all())
        if not line_items:
            return Response({"error": "This order has no line items."}, status=400)

        # Prevent duplicate: if any active entry already exists for this order, block
        active_statuses = ["pending_qc", "suspicious", "damaged", "qc_passed", "qc_failed", "under_investigation", "sent_for_repair", "written_off"]
        existing_qs = RTOEngineItem.objects.filter(order=order, scan_status__in=active_statuses)
        existing_count = existing_qs.count()
        if existing_count > 0:
            # Auto-upgrade: if ALL existing entries are old-style (line_item=null), delete and recreate
            null_count = existing_qs.filter(line_item__isnull=True).count()
            if null_count == existing_count:
                existing_qs.delete()
            else:
                return Response(
                    {"error": f"This order already has {existing_count} active RTO Engine item(s). Each product is tracked individually."},
                    status=400,
                )

        # Create one RTOEngineItem per line item in the order
        created_items = []
        # Resolve batch (passed from stack dispatch when use_batch=true)
        batch_id = request.data.get("batch_id")
        batch = None
        if batch_id:
            try:
                batch = RTOEngineBatch.objects.get(pk=batch_id, org_id=org_id)
            except RTOEngineBatch.DoesNotExist:
                pass

        for li in line_items:
            item = RTOEngineItem.objects.create(
                order=order,
                line_item=li,
                scan_status=scan_status,
                scanned_by=request.user,
                scan_notes=notes,
                write_off_reason=write_off_reason if action == "write_off" else None,
                rto_engine_batch=batch,
                repair_stage=repair_stage if action == "send_for_repair" else None,
            )
            created_items.append(_engine_item_detail(item))
        return Response({"items": created_items, "count": len(created_items)}, status=201)


class RTOEngineBatchScanView(APIView):
    """
    POST { scan_inputs: ["AWB1", "AWB2", ...] }
    → Returns { results: [{input, order?, error?}] } for each input.
    Accepts comma/newline-separated AWBs or order numbers.
    Max 100 inputs per request.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        raw = request.data.get("scan_inputs", [])
        if not raw or not isinstance(raw, list):
            return Response({"error": "scan_inputs must be a non-empty list"}, status=400)

        scan_inputs = [str(s).strip() for s in raw[:100] if str(s).strip()]
        if not scan_inputs:
            return Response({"error": "No valid inputs provided"}, status=400)

        results = []
        from django.core.cache import cache
        for inp in scan_inputs:
            cached_order = cache.get(f"org:{org_id}:rto_scan:ident:{inp}")
            if cached_order:
                order_id = cached_order.get("id")
                status_data = _get_rto_item_status(order_id)
                if status_data.get("already_scanned"):
                    results.append({
                        "input": inp,
                        "order": cached_order,
                        "error": None,
                        "already_scanned": True,
                        "existing_status": status_data["existing_status"],
                        "scanned_at": status_data["scanned_at"],
                    })
                else:
                    results.append({"input": inp, "order": cached_order, "error": None, "already_scanned": False})
                continue

            order, courier = _find_order(inp, org_id)
            if order:
                payload = _cache_rto_scan_payload(org_id, order, courier)
                status_data = _get_rto_item_status(order.id)
                if status_data.get("already_scanned"):
                    results.append({
                        "input": inp,
                        "order": payload,
                        "error": None,
                        "already_scanned": True,
                        "existing_status": status_data["existing_status"],
                        "scanned_at": status_data["scanned_at"],
                    })
                else:
                    results.append({"input": inp, "order": payload, "error": None, "already_scanned": False})
            else:
                results.append({"input": inp, "order": None, "error": "Order not found", "already_scanned": False})

        return Response({"results": results})


class RTOEngineBatchDispatchView(APIView):
    """
    POST { order_ids: [id, ...], action, notes?, write_off_reason?, repair_stage? }
    Dispatches multiple orders in one call. Returns per-order results.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': [
            'rto_module:rto_engine:create',
            'rto_module:rto_engine:edit',
            'rto_module:rto_manager:edit',
            'rto_module:rto_manager:create',
            'rto_module:rto_in_transit:create',
            'rto_module:rto_in_transit:edit',
        ],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        order_ids = request.data.get("order_ids", [])
        action = request.data.get("action", "").strip()
        notes = request.data.get("notes", "").strip()
        write_off_reason = request.data.get("write_off_reason", "").strip()
        repair_stage = request.data.get("repair_stage", "").strip()

        VALID_ACTIONS = {"pending_qc", "suspicious", "damaged", "send_for_repair", "write_off"}
        if action not in VALID_ACTIONS:
            return Response({"error": f"action must be one of {VALID_ACTIONS}"}, status=400)
        if action == "write_off" and write_off_reason not in {"not_our_product", "fraud"}:
            return Response({"error": "write_off_reason must be not_our_product or fraud"}, status=400)
        if action == "send_for_repair" and repair_stage:
            valid_stages = {value for value, _ in RTOEngineItem.REPAIR_STAGE_CHOICES}
            if repair_stage not in valid_stages:
                return Response({"error": "Invalid repair_stage"}, status=400)

        ACTION_STATUS = {
            "pending_qc":      "pending_qc",
            "suspicious":      "suspicious",
            "damaged":         "damaged",
            "send_for_repair": "sent_for_repair",
            "write_off":       "written_off",
        }
        scan_status = ACTION_STATUS[action]
        active_statuses = [
            "pending_qc", "suspicious", "damaged", "qc_passed",
            "qc_failed", "under_investigation", "sent_for_repair", "written_off",
        ]

        # ── Create a batch if 1+ orders are being dispatched together ──────────
        batch = None
        if len(order_ids) >= 1:
            with transaction.atomic():
                last = RTOEngineBatch.objects.filter(org_id=org_id).order_by('-batch_number').first()
                next_num = (last.batch_number + 1) if last else 1
                batch = RTOEngineBatch.objects.create(
                    org_id=org_id,
                    batch_number=next_num,
                    created_by=request.user,
                )

        results = []
        for order_id in order_ids[:100]:
            try:
                order = Order.objects.prefetch_related('line_items').get(pk=order_id, org_id=org_id)
            except Order.DoesNotExist:
                results.append({"order_id": order_id, "success": False, "error": "Order not found"})
                continue

            line_items = list(order.line_items.all())
            if not line_items:
                results.append({"order_id": order_id, "success": False, "error": "No line items on this order"})
                continue

            existing_qs = RTOEngineItem.objects.filter(order=order, scan_status__in=active_statuses)
            existing_count = existing_qs.count()
            if existing_count > 0:
                null_count = existing_qs.filter(line_item__isnull=True).count()
                if null_count == existing_count:
                    existing_qs.delete()
                else:
                    results.append({
                        "order_id": order_id,
                        "order_number": order.order_number,
                        "success": False,
                        "error": f"Order #{order.order_number} already has {existing_count} active item(s)",
                    })
                    continue

            for li in line_items:
                RTOEngineItem.objects.create(
                    order=order,
                    line_item=li,
                    scan_status=scan_status,
                    scanned_by=request.user,
                    scan_notes=notes,
                    write_off_reason=write_off_reason if action == "write_off" else None,
                    rto_engine_batch=batch,
                    repair_stage=repair_stage if action == "send_for_repair" else None,
                )
            results.append({
                "order_id": order_id,
                "order_number": order.order_number,
                "success": True,
                "items_created": len(line_items),
            })

        return Response({
            "results": results,
            "batch_id": batch.id if batch else None,
            "batch_number": batch.batch_number if batch else None,
            "batch_display_name": batch.display_name if batch else None,
        })


class RTOEngineQCListView(APIView):
    """
    GET list of items in QC queue (pending_qc, qc_passed, qc_failed, sent_to_inventory).
    Supports: search, date_from, date_to, status filter, sort.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        qs = RTOEngineItem.objects.filter(
            scan_status__in=["pending_qc", "qc_passed", "qc_failed", "sent_to_inventory"],
            order__org_id=org_id
        ).select_related("order", "line_item", "scanned_by", "qc_by", "rto_engine_batch")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(scan_status=status_filter)

        qs = _apply_common_filters(qs, request)
        return Response({"items": [_engine_item_detail(i) for i in qs]})


class RTOEngineQCActionView(APIView):
    """
    POST { item_id, action, notes }
    action ∈ { pass | fail | send_to_inventory }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        item_id = request.data.get("item_id")
        action = request.data.get("action", "").strip()
        notes = request.data.get("notes", "").strip()

        try:
            item = RTOEngineItem.objects.select_related("order").get(pk=item_id, order__org_id=org_id)
        except RTOEngineItem.DoesNotExist:
            return Response({"error": "Item not found."}, status=404)

        now = timezone.now()

        if action == "pass":
            item.scan_status = "qc_passed"
            item.qc_by = request.user
            item.qc_at = now
            item.qc_notes = notes
            item.save()
            return Response({"item": _engine_item_detail(item)})
        elif action == "fail":
            item.scan_status = "qc_failed"
            item.qc_by = request.user
            item.qc_at = now
            item.qc_notes = notes
            # Failed QC → move to investigation
            item.scan_status = "under_investigation"
            item.investigation_status = "open"
            item.investigation_notes = notes
            item.save()
            return Response({"item": _engine_item_detail(item)})
        elif action == "send_to_inventory":
            if item.scan_status != "qc_passed":
                return Response(
                    {"error": "Only qc_passed items can be sent to inventory."}, status=400
                )
            try:
                with transaction.atomic():
                    item.scan_status = "sent_to_inventory"
                    item.qc_notes = notes or item.qc_notes
                    item.save()
                    _send_items_to_inventory(org_id, [item])
            except Exception as e:
                logger.exception("Failed to send RTO items to inventory.")
                return Response({"error": f"Failed to increment inventory: {str(e)}"}, status=500)
            return Response({"item": _engine_item_detail(item)})
        else:
            return Response({"error": "action must be pass, fail, or send_to_inventory"}, status=400)


class RTOEngineQCBulkInventoryView(APIView):
    """
    POST { item_ids: [int] }  →  bulk send qc_passed items to inventory.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        ids = request.data.get("item_ids", [])
        if not ids:
            return Response({"error": "item_ids is required"}, status=400)

        try:
            with transaction.atomic():
                rto_items = list(
                    RTOEngineItem.objects.select_related('line_item')
                    .filter(pk__in=ids, scan_status="qc_passed", order__org_id=org_id)
                )
                count = RTOEngineItem.objects.filter(pk__in=ids, scan_status="qc_passed", order__org_id=org_id).update(
                    scan_status="sent_to_inventory", updated_at=timezone.now()
                )
                _send_items_to_inventory(org_id, rto_items)
        except Exception as e:
            logger.exception("Failed bulk sending RTO items to inventory.")
            return Response({"error": f"Failed to bulk increment inventory: {str(e)}"}, status=500)

        return Response({"updated": count})


class RTOEngineQCBulkActionView(APIView):
    """
    POST { item_ids: [int], action: "pass" | "fail" }
    Bulk pass or fail pending_qc items.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        ids = request.data.get("item_ids", [])
        action = request.data.get("action", "").strip()
        notes = request.data.get("notes", "").strip()

        if not ids:
            return Response({"error": "item_ids is required"}, status=400)
        if action not in ("pass", "fail"):
            return Response({"error": "action must be pass or fail"}, status=400)

        now = timezone.now()
        items = RTOEngineItem.objects.filter(pk__in=ids, scan_status="pending_qc", order__org_id=org_id)
        if action == "pass":
            count = items.update(
                scan_status="qc_passed",
                qc_by=request.user,
                qc_at=now,
                qc_notes=notes,
                updated_at=now,
            )
        else:  # fail → under_investigation
            count = items.update(
                scan_status="under_investigation",
                qc_by=request.user,
                qc_at=now,
                qc_notes=notes,
                investigation_status="open",
                investigation_notes=notes,
                updated_at=now,
            )
        return Response({"updated": count, "action": action})


class RTOEngineInvestigationListView(APIView):
    """
    GET list of items in investigation (suspicious, damaged, under_investigation, investigation_resolved).
    """
    permission_classes = [IsAuthenticated]

    ACTIVE_STATUSES = ["suspicious", "damaged", "under_investigation"]
    ALL_STATUSES = ["suspicious", "damaged", "under_investigation", "investigation_resolved", "sent_for_repair", "written_off"]

    def get(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        status_filter = request.query_params.get("status")

        if status_filter:
            qs = RTOEngineItem.objects.filter(
                scan_status=status_filter, order__org_id=org_id
            ).select_related("order", "line_item", "scanned_by", "resolved_by", "rto_engine_batch")
        else:
            # Default: only show active (unresolved) investigation items
            qs = RTOEngineItem.objects.filter(
                scan_status__in=self.ACTIVE_STATUSES, order__org_id=org_id
            ).select_related("order", "line_item", "scanned_by", "resolved_by", "rto_engine_batch")

        qs = _apply_common_filters(qs, request)
        return Response({"items": [_engine_item_detail(i) for i in qs]})


class RTOEngineInvestigationActionView(APIView):
    """
    POST { item_id, action, notes, repair_stage?, write_off_reason? }
    action ∈ { resolve | send_for_repair | write_off }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        item_id = request.data.get("item_id")
        action = request.data.get("action", "").strip()
        notes = request.data.get("notes", "").strip()
        write_off_reason = request.data.get("write_off_reason", "").strip()
        repair_stage = request.data.get("repair_stage", "").strip()

        try:
            item = RTOEngineItem.objects.get(pk=item_id, order__org_id=org_id)
        except RTOEngineItem.DoesNotExist:
            return Response({"error": "Item not found."}, status=404)

        now = timezone.now()

        if action == "resolve":
            item.scan_status = "qc_passed"
            item.investigation_status = "resolved"
            item.resolved_by = request.user
            item.resolved_at = now
            item.investigation_notes = notes or item.investigation_notes
        elif action == "send_for_repair":
            if repair_stage:
                valid_stages = {value for value, _ in RTOEngineItem.REPAIR_STAGE_CHOICES}
                if repair_stage not in valid_stages:
                    return Response({"error": "Invalid repair_stage"}, status=400)
            item.scan_status = "sent_for_repair"
            item.investigation_status = "resolved"
            item.resolved_by = request.user
            item.resolved_at = now
            item.investigation_notes = notes or item.investigation_notes
            item.repair_stage = repair_stage or item.repair_stage
        elif action == "write_off":
            valid_reasons = {"not_our_product", "fraud"}
            if write_off_reason not in valid_reasons:
                return Response({"error": "write_off_reason must be not_our_product or fraud"}, status=400)
            item.scan_status = "written_off"
            item.investigation_status = "resolved"
            item.resolved_by = request.user
            item.resolved_at = now
            item.investigation_notes = notes or item.investigation_notes
            item.write_off_reason = write_off_reason
        else:
            return Response({"error": "action must be resolve, send_for_repair, or write_off"}, status=400)

        item.save()
        return Response({"item": _engine_item_detail(item)})


class RTOEngineInvestigationBulkActionView(APIView):
    """
    POST { item_ids: [int], action, write_off_reason? }
    action ∈ { resolve | send_for_repair | write_off }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        ids = request.data.get("item_ids", [])
        action = request.data.get("action", "").strip()
        write_off_reason = request.data.get("write_off_reason", "").strip()
        repair_stage = request.data.get("repair_stage", "").strip()

        if not ids:
            return Response({"error": "item_ids is required"}, status=400)

        qs = RTOEngineItem.objects.filter(pk__in=ids, order__org_id=org_id)
        now = timezone.now()

        if action == "resolve":
            count = qs.update(scan_status="qc_passed", investigation_status="resolved",
                              resolved_by=request.user, resolved_at=now)
        elif action == "send_for_repair":
            if repair_stage:
                valid_stages = {value for value, _ in RTOEngineItem.REPAIR_STAGE_CHOICES}
                if repair_stage not in valid_stages:
                    return Response({"error": "Invalid repair_stage"}, status=400)
            update_fields = {
                "scan_status": "sent_for_repair",
                "investigation_status": "resolved",
                "resolved_by": request.user,
                "resolved_at": now,
            }
            if repair_stage:
                update_fields["repair_stage"] = repair_stage
            count = qs.update(**update_fields)
        elif action == "write_off":
            valid_reasons = {"not_our_product", "fraud"}
            if write_off_reason not in valid_reasons:
                return Response({"error": "write_off_reason must be not_our_product or fraud"}, status=400)
            count = qs.update(scan_status="written_off", investigation_status="resolved",
                               resolved_by=request.user, resolved_at=now, write_off_reason=write_off_reason)
        else:
            return Response({"error": "action must be resolve, send_for_repair, or write_off"}, status=400)

        return Response({"updated": count})


class RTOEngineRepairBulkCompleteView(APIView):
    """
    POST { item_ids: [int] }  →  bulk mark sent_for_repair items as sent_to_inventory (repair done).
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': ['rto_module:rto_engine:edit', 'rto_module:rto_manager:edit'],
    }

    def post(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        ids = request.data.get("item_ids", [])
        if not ids:
            return Response({"error": "item_ids is required"}, status=400)

        items = RTOEngineItem.objects.filter(pk__in=ids, scan_status="sent_for_repair", order__org_id=org_id)
        count = items.update(scan_status="sent_to_inventory", updated_at=timezone.now())
        return Response({"updated": count})


class RTOEngineLogView(APIView):
    """
    GET all RTOEngineItems across ALL statuses — the master RTO log sheet.
    Supports: search, date_from, date_to, status, sort.
    Default date range: last 2 days (yesterday + today).
    """
    permission_classes = [IsAuthenticated]

    ALL_STATUSES = [
        "pending_qc", "qc_passed", "qc_failed", "sent_to_inventory",
        "suspicious", "damaged", "under_investigation", "investigation_resolved",
        "sent_for_repair", "written_off",
    ]

    def get(self, request):
        org_id = _get_org_id_from_user(request.user)
        if not org_id:
            return Response({"error": "Unauthorized: Organization not found"}, status=403)

        qs = RTOEngineItem.objects.filter(
            scan_status__in=self.ALL_STATUSES,
            order__org_id=org_id
        ).select_related(
            "order", "line_item", "scanned_by", "qc_by", "resolved_by", "rto_engine_batch"
        )

        # Status filter
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(scan_status=status_filter)

        # Date filters — default to last 2 days if no date_from given
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if not date_from and not date_to:
            yesterday = (timezone.now() - timedelta(days=1)).date()
            qs = qs.filter(scanned_at__date__gte=yesterday)
        else:
            if date_from:
                qs = qs.filter(scanned_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(scanned_at__date__lte=date_to)

        # Search
        search = request.query_params.get("search", "").strip()
        if search:
            import re
            q_filter = Q(
                Q(order__order_number__icontains=search)
                | Q(order__customer_first_name__icontains=search)
                | Q(order__customer_last_name__icontains=search)
                | Q(order__contact_phone__icontains=search)
                | Q(order__fulfillments__tracking_info__number__icontains=search)
            )
            match = re.search(r'(?:batch|b)?\s*(\d+)', search.lower())
            if match:
                try:
                    q_filter |= Q(rto_engine_batch__batch_number=int(match.group(1)))
                except ValueError:
                    pass
            qs = qs.filter(q_filter).distinct()

        # Sort
        sort = request.query_params.get("sort", "-scanned_at")
        allowed_sorts = {
            "scanned_at", "-scanned_at",
            "order__order_number", "-order__order_number",
            "updated_at", "-updated_at",
        }
        if sort in allowed_sorts:
            qs = qs.order_by(sort)

        return Response({"items": [_engine_item_detail(i) for i in qs]})

