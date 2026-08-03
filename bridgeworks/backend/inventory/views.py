import logging
import os
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import InventoryTable, InventoryItem, Vendor, PurchaseOrder
from .serializers import InventoryTableSerializer, InventoryItemSerializer

logger = logging.getLogger(__name__)

RETIRED_TABLE_KEYS = frozenset({
    'production_log',
    'low_stock',
    'die_inventory',
})


def _retired_table_response(table_key):
    if table_key in RETIRED_TABLE_KEYS:
        return Response(
            {"error": f"Inventory section '{table_key}' has been removed."},
            status=status.HTTP_410_GONE,
        )
    return None


def _get_production_software_creds(org_id=None):
    """Return (api_url, api_key) from DB for the given org, falling back to env vars."""
    if org_id:
        try:
            from core.models import ShopCredentials
            shop = ShopCredentials.objects.get(organization_id=org_id)
            cred = shop.production_software_credential  # type: ignore[attr-defined]
            db_url = (cred.api_url or '').strip()
            db_key = cred.get_api_key() or ''
            if db_url and db_key:
                return db_url, db_key
        except Exception:
            pass
    return (
        os.getenv('PRODUCTION_SOFTWARE_API_URL', '').strip(),
        os.getenv('PRODUCTION_SOFTWARE_API_KEY', '').strip(),
    )


def _normalize_sku(value):
    return str(value or '').strip().lower()


def _pick_first(source, keys, default=''):
    for key in keys:
        if key in source and source.get(key) not in (None, ''):
            return source.get(key)
    return default


def _build_local_inventory_map(org_id):
    """
    Build a SKU → enrichment-dict map from the local InventoryItem rows
    stored under table_key='product_inventory' for the given org.
    Supports any of these keys in item.data:
      final_sku / sku  → lookup key
      master_sku, actual_quantity / quantity, unit, location
    """
    try:
        table = InventoryTable.objects.filter(
            organization_id=org_id,
            table_key='product_inventory',
        ).first()
        if not table:
            return {}
        items = InventoryItem.objects.filter(table=table)
        sku_map = {}
        for item in items:
            d = item.data or {}
            final_sku  = str(d.get('final_sku') or d.get('sku') or '').strip()
            master_sku = str(d.get('master_sku') or '').strip()
            name = _pick_first(d, ['name', 'product_name', 'title'])
            actual_qty = d.get('actual_quantity') or d.get('quantity') or ''
            unit       = str(d.get('unit') or '').strip()
            location   = str(d.get('location') or '').strip()
            mapped = {
                'masterSku':      master_sku,
                'finalSku':       final_sku,
                'actualQuantity': actual_qty,
                'unit':           unit,
                'location':       location,
                'name':           name,
            }
            for key in [final_sku, master_sku, name]:
                k = _normalize_sku(key)
                if k:
                    sku_map[k] = mapped
        return sku_map
    except Exception:
        logger.exception('Failed to build local inventory map')
        return {}


def _fetch_and_save_production_inventory(org_id):
    """
    Fetch inventory from the external production software API and persist
    results into the local InventoryItem table (table_key='product_inventory').

    API structure:
      GET /api/v1/inventory/  → {"success": true, "data": [{stage, quantity, location, product, ...}]}
      GET /api/v1/products/   → {"success": true, "data": [{id, master_sku, weight_unit, ...}]}

    stage = "final_stock__<final_sku>" encodes the final SKU.
    Records arrive latest-first; we take the most recent non-location record per sku.

    Returns (items_saved, error_message).
    """
    import requests as http_requests
    from urllib.parse import urlparse

    api_url, api_key = _get_production_software_creds(org_id)

    if not api_url or not api_key:
        return 0, 'Production software API URL / API key not configured'

    parsed = urlparse(api_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        'X-API-Key': api_key,
        'Accept': 'application/json',
    }

    # --- Fetch products ---
    product_map = {}
    try:
        resp = http_requests.get(f"{base_url}/api/v1/products/", headers=headers, timeout=20)
        if resp.ok:
            payload = resp.json()
            products = payload.get('data') or payload.get('results') or (payload if isinstance(payload, list) else [])
            for p in products:
                pid = p.get('id')
                if pid:
                    product_map[pid] = {
                        'master_sku': str(p.get('master_sku') or '').strip(),
                        'unit': str(p.get('weight_unit') or 'PCS').strip(),
                    }
    except Exception:
        logger.exception('Failed to fetch products for sync')

    # --- Fetch inventory transactions ---
    try:
        resp = http_requests.get(api_url, headers=headers, timeout=20)
        if not resp.ok:
            return 0, f'External API returned HTTP {resp.status_code}'
        payload = resp.json()
    except Exception as exc:
        return 0, str(exc)

    rows = payload.get('data') or payload.get('results') or (payload if isinstance(payload, list) else [])
    if not isinstance(rows, list):
        return 0, 'Unexpected response format from external API'

    STAGE_PREFIX = 'final_stock__'
    qty_map = {}
    location_map = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage = str(row.get('stage') or '')
        if not stage.startswith(STAGE_PREFIX):
            continue
        final_sku = stage[len(STAGE_PREFIX):].upper()
        if not final_sku:
            continue
        location = str(row.get('location') or '').strip()
        remark = str(row.get('remark') or '').lower()
        if location and final_sku not in location_map:
            location_map[final_sku] = location
        if remark.rstrip().endswith('location'):
            continue
        if final_sku not in qty_map:
            qty_map[final_sku] = {'quantity': row.get('quantity', 0), 'product_id': row.get('product')}

    table, _ = InventoryTable.objects.get_or_create(
        organization_id=org_id,
        table_key='product_inventory',
        defaults={'columns': [
            {'id': 'master_sku',      'label': 'Master SKU',      'type': 'text',   'visible': True},
            {'id': 'final_sku',       'label': 'Final SKU',       'type': 'text',   'visible': True},
            {'id': 'actual_quantity', 'label': 'Actual Quantity',  'type': 'number', 'visible': True},
            {'id': 'unit',            'label': 'Unit',             'type': 'text',   'visible': True},
            {'id': 'location',        'label': 'Location',         'type': 'text',   'visible': True},
        ]},
    )

    saved = 0
    with transaction.atomic():
        for final_sku, entry in qty_map.items():
            product_id = entry['product_id']
            product_info = product_map.get(product_id, {})
            data = {
                'master_sku':      product_info.get('master_sku', ''),
                'final_sku':       final_sku,
                'actual_quantity': entry['quantity'],
                'unit':            product_info.get('unit', 'PCS'),
                'location':        location_map.get(final_sku, ''),
            }
            InventoryItem.objects.update_or_create(
                table=table,
                data__final_sku=final_sku,
                defaults={'data': data},
            )
            saved += 1

    return saved, None


def _fetch_production_inventory_map(org_id=None):
    """
    Fetch inventory data from the production software API.

    The API returns:
      GET /api/v1/inventory/  → {"success": true, "data": [{"stage": "final_stock__<sku>",
                                   "quantity": N, "location": "...", "product": <id>, ...}]}
      GET /api/v1/products/   → {"success": true, "data": [{"id": ..., "master_sku": "...",
                                   "weight_unit": "...", ...}]}

    We cross-reference by product id to get master_sku, and extract final_sku from stage.
    Records are returned in descending id order (latest first).  We take the latest
    non-location record per stage as the current actual_quantity.
    """
    import requests as http_requests
    from urllib.parse import urlparse, urljoin

    api_url, api_key = _get_production_software_creds(org_id)

    if not api_url or not api_key:
        return {}

    parsed = urlparse(api_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        'X-API-Key': api_key,
        'Accept': 'application/json',
    }

    # ------------------------------------------------------------------
    # 1. Fetch products → build {product_id: {master_sku, unit}}
    # ------------------------------------------------------------------
    product_map = {}
    try:
        resp = http_requests.get(f"{base_url}/api/v1/products/", headers=headers, timeout=20)
        if resp.ok:
            payload = resp.json()
            products = payload.get('data') or payload.get('results') or (payload if isinstance(payload, list) else [])
            for p in products:
                pid = p.get('id')
                if pid:
                    product_map[pid] = {
                        'master_sku': str(p.get('master_sku') or '').strip(),
                        'unit': str(p.get('weight_unit') or 'PCS').strip(),
                        'name': _pick_first(p, ['name', 'title', 'product_name', 'display_name', 'label']),
                    }
        else:
            logger.warning('Production products API returned %s', resp.status_code)
    except Exception:
        logger.exception('Failed to fetch products from production API')

    # ------------------------------------------------------------------
    # 2. Fetch inventory transactions → group by stage (= final_sku)
    # ------------------------------------------------------------------
    try:
        resp = http_requests.get(api_url, headers=headers, timeout=20)
        if not resp.ok:
            logger.warning('Production inventory API returned %s: %s', resp.status_code, resp.text[:200])
            return {}
        payload = resp.json()
    except Exception:
        logger.exception('Failed to fetch production software inventory data')
        return {}

    rows = payload.get('data') or payload.get('results') or (payload if isinstance(payload, list) else [])
    if not isinstance(rows, list):
        return {}

    # Keyed by final_sku (uppercase).  Records arrive latest-first.
    STAGE_PREFIX = 'final_stock__'
    qty_map = {}      # final_sku → {quantity, product_id}
    location_map = {} # final_sku → location string

    for row in rows:
        if not isinstance(row, dict):
            continue
        stage = str(row.get('stage') or '')
        if not stage.startswith(STAGE_PREFIX):
            continue

        final_sku = stage[len(STAGE_PREFIX):].upper()
        if not final_sku:
            continue

        location = str(row.get('location') or '').strip()
        remark = str(row.get('remark') or '').lower()
        product_id = row.get('product')
        quantity = row.get('quantity', 0)

        # Capture location from any record for this sku (they share the same location)
        if location and final_sku not in location_map:
            location_map[final_sku] = location

        # Skip records that are location-only entries (remark ends with "location")
        if remark.rstrip().endswith('location'):
            continue

        # Take the LATEST (first in descending list) quantity record per final_sku
        if final_sku not in qty_map:
            qty_map[final_sku] = {'quantity': quantity, 'product_id': product_id}

    # ------------------------------------------------------------------
    # 3. Build enrichment map keyed by normalised SKU
    # ------------------------------------------------------------------
    sku_map = {}
    for final_sku, data in qty_map.items():
        product_id = data['product_id']
        product_info = product_map.get(product_id, {})
        master_sku = product_info.get('master_sku', '')
        unit = product_info.get('unit', 'PCS')
        location = location_map.get(final_sku, '')

        mapped = {
            'masterSku': master_sku,
            'finalSku': final_sku,
            'actualQuantity': data['quantity'],
            'unit': unit,
            'location': location,
            'name': product_info.get('name', ''),
        }

        # Index by normalised final_sku (matches Shopify variant SKU)
        key = _normalize_sku(final_sku)
        if key:
            sku_map[key] = mapped

        # Also index by normalised master_sku for fallback matching
        if master_sku:
            mkey = _normalize_sku(master_sku)
            if mkey and mkey not in sku_map:
                sku_map[mkey] = mapped

        # Also index by normalised product name if available
        name_key = _normalize_sku(mapped.get('name'))
        if name_key and name_key not in sku_map:
            sku_map[name_key] = mapped

    logger.info('Production inventory map built: %d SKUs', len(sku_map))
    return sku_map


def _fetch_wip_map(org_id=None):

    import requests as http_requests
    from urllib.parse import urlparse

    api_url, api_key = _get_production_software_creds(org_id)
    if not api_url or not api_key:
        return {}

    parsed = urlparse(api_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    headers = {'X-API-Key': api_key, 'Accept': 'application/json'}

    # 1. Products → {product_id: master_sku}
    product_map = {}
    try:
        resp = http_requests.get(f"{base_url}/api/v1/products/", headers=headers, timeout=20)
        if resp.ok:
            for p in (resp.json().get('data') or []):
                pid = p.get('id')
                if pid:
                    product_map[pid] = str(p.get('master_sku') or '').strip()
    except Exception:
        logger.exception('WIP map: failed to fetch products')

    # 2. Inventory → final_sku per product_id + WIP qty per product_id
    try:
        resp = http_requests.get(api_url, headers=headers, timeout=20)
        if not resp.ok:
            return {}
        rows = resp.json().get('data') or []
    except Exception:
        logger.exception('WIP map: failed to fetch inventory')
        return {}

    STAGE_PREFIX = 'final_stock__'
    pid_to_final_sku = {}   # first-seen final_sku per product_id
    wip_by_pid = {}         # cumulative WIP qty per product_id (all non-final-stock stages)

    for row in rows:
        if not isinstance(row, dict):
            continue
        stage = str(row.get('stage') or '')
        pid = row.get('product')
        qty = row.get('quantity') or 0

        if stage.startswith(STAGE_PREFIX):
            final_sku = stage[len(STAGE_PREFIX):].upper()
            if final_sku and pid and pid not in pid_to_final_sku:
                pid_to_final_sku[pid] = final_sku
        else:
            # Any non-final-stock stage contributes to WIP
            if pid is not None and qty:
                wip_by_pid[pid] = wip_by_pid.get(pid, 0) + qty

    # 3. Build normalised SKU → wipQty map
    sku_map = {}
    for pid, wip_qty in wip_by_pid.items():
        if not wip_qty:
            continue
        master_sku = product_map.get(pid, '')
        final_sku = pid_to_final_sku.get(pid, '')
        entry = {'wipQty': wip_qty, 'masterSku': master_sku, 'finalSku': final_sku}

        if final_sku:
            sku_map[_normalize_sku(final_sku)] = entry
        if master_sku:
            mkey = _normalize_sku(master_sku)
            if mkey and mkey not in sku_map:
                sku_map[mkey] = entry

    logger.info('WIP map built: %d SKUs', len(sku_map))
    return sku_map


def _get_org_id(request):
    """Return the organisation ID for the authenticated user."""
    user = request.user
    if hasattr(user, "shop_credentials"):
        return user.shop_credentials.organization_id
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


def _get_or_create_table(org_id, table_key, default_columns=None):
    """Fetch or create an InventoryTable record."""
    if table_key in RETIRED_TABLE_KEYS:
        raise ValueError(f"Inventory section '{table_key}' has been removed.")
    table, _ = InventoryTable.objects.get_or_create(
        organization_id=org_id,
        table_key=table_key,
        defaults={"columns": default_columns or []},
    )
    return table


# ---------------------------------------------------------------------------
# /api/inventory/<table_key>/          GET · PATCH (columns)
# ---------------------------------------------------------------------------
class InventoryTableView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, table_key):
        retired = _retired_table_response(table_key)
        if retired:
            return retired
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        # Accept optional default_columns from query-string (JSON-encoded)
        default_columns = request.query_params.get("default_columns")
        if default_columns:
            import json
            try:
                default_columns = json.loads(default_columns)
            except Exception:
                default_columns = []

        table = _get_or_create_table(org_id, table_key, default_columns)
        serializer = InventoryTableSerializer(table)
        return Response(serializer.data)

    def patch(self, request, table_key):
        """Update column configuration for this table."""
        retired = _retired_table_response(table_key)
        if retired:
            return retired
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        columns = request.data.get("columns")
        if columns is None:
            return Response({"error": "columns field is required."}, status=status.HTTP_400_BAD_REQUEST)

        table = _get_or_create_table(org_id, table_key)
        table.columns = columns
        table.save(update_fields=["columns", "updated_at"])
        return Response({"columns": table.columns})


# ---------------------------------------------------------------------------
# /api/inventory/<table_key>/items/     POST
# /api/inventory/<table_key>/items/<id>/  PATCH · DELETE
# ---------------------------------------------------------------------------
class InventoryItemListCreateView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request, table_key):
        retired = _retired_table_response(table_key)
        if retired:
            return retired
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        table = _get_or_create_table(org_id, table_key)
        data = request.data.get("data", {})
        item = InventoryItem.objects.create(table=table, data=data)
        return Response(InventoryItemSerializer(item).data, status=status.HTTP_201_CREATED)


class InventoryItemDetailView(APIView):
    # permission_classes = [IsAuthenticated]

    def _get_item(self, request, table_key, item_id):
        retired = _retired_table_response(table_key)
        if retired:
            return None, retired
        org_id = _get_org_id(request)
        if not org_id:
            return None, Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)
        item = get_object_or_404(
            InventoryItem,
            pk=item_id,
            table__organization_id=org_id,
            table__table_key=table_key,
        )
        return item, None

    def patch(self, request, table_key, item_id):
        item, err = self._get_item(request, table_key, item_id)
        if err:
            return err
        assert item is not None
        data = request.data.get("data", {})
        item.data = {**item.data, **data}
        item.save(update_fields=["data", "updated_at"])
        return Response(InventoryItemSerializer(item).data)

    def delete(self, request, table_key, item_id):
        item, err = self._get_item(request, table_key, item_id)
        if err:
            return err
        assert item is not None
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /api/inventory/<table_key>/items/bulk-delete/   POST
# ---------------------------------------------------------------------------
class InventoryBulkDeleteView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request, table_key):
        retired = _retired_table_response(table_key)
        if retired:
            return retired
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids", [])
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count, _ = InventoryItem.objects.filter(
            pk__in=ids,
            table__organization_id=org_id,
            table__table_key=table_key,
        ).delete()

        return Response({"deleted": deleted_count})


# ---------------------------------------------------------------------------
# /api/inventory/analytics/best-selling/   GET
# ---------------------------------------------------------------------------
FESTIVAL_MULTS = {
    'Diwali': 2.8, 'Wedding Season': 2.4, 'Navratri': 2.1,
    'Holi': 1.7, 'Eid': 1.8, 'Christmas': 1.6, 'All': 1.0,
}
SEASON_MULTS = {
    'Summer': 1.2, 'Winter': 1.4, 'Monsoon': 0.9, 'Festive': 2.2, 'All Seasons': 1.0,
}

SEASON_MONTHS = {
    'Summer':  [3, 4, 5, 6],
    'Monsoon': [7, 8, 9],
    'Winter':  [10, 11, 12, 1, 2],
    'Festive': [10, 11],
}

PERIOD_DAYS = {
    'daily': 1,
    'weekly': 7,
    'monthly': 30,
    'seasonal': 90,
    'festival': 60,
}


class BestSellingView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import datetime, time
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncWeek
        from core.models import LineItem
        from inventory.models import ShopifyProductCache
        from django.core.cache import cache

        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        period = request.query_params.get('period', 'daily')
        festival = request.query_params.get('festival', 'All')
        season = request.query_params.get('season', 'All Seasons')
        category_filter = request.query_params.get('category', 'All')
        search = request.query_params.get('search', '').strip().lower()
        month = request.query_params.get('month')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        def _parse_date(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except Exception:
                return None

        now = timezone.now()
        range_start = None
        range_end = None

        if start_date and end_date:
            start_parsed = _parse_date(start_date)
            end_parsed = _parse_date(end_date)
            if start_parsed and end_parsed and start_parsed <= end_parsed:
                range_start = timezone.make_aware(datetime.combine(start_parsed, time.min))
                range_end = timezone.make_aware(datetime.combine(end_parsed, time.max))

        if period == 'monthly' and month is not None and range_start is None:
            try:
                month_num = int(month)
                year = now.year
                start_month = datetime(year, month_num + 1, 1)
                next_month = datetime(year + (month_num == 11), (month_num + 2) if month_num < 11 else 1, 1)
                range_start = timezone.make_aware(start_month)
                range_end = timezone.make_aware(next_month - timedelta(seconds=1))
            except Exception:
                range_start = None
                range_end = None

        if range_start is None or range_end is None:
            days = PERIOD_DAYS.get(period, 30)
            range_end = now
            range_start = now - timedelta(days=days)
        else:
            days = max(1, (range_end.date() - range_start.date()).days + 1)

        cache_key = (
            f"best_selling_v2:{org_id}:{period}:{festival}:{season}:{month}:"
            f"{range_start.date().isoformat()}:{range_end.date().isoformat()}:{search}"
        )
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        mult = FESTIVAL_MULTS.get(festival, 1.0) * SEASON_MULTS.get(season, 1.0)
        season_months = SEASON_MONTHS.get(season) if period == 'seasonal' else None

        base_filter = {
            'order__org_id': org_id,
            'order__created_at__gte': range_start,
            'order__created_at__lte': range_end,
        }
        if season_months:
            base_filter['order__created_at__month__in'] = season_months

        qs = (
            LineItem.objects
            .filter(**base_filter)
            .values('title', 'sku')
            .annotate(total_qty=Sum('quantity'), order_count=Count('order', distinct=True))
            .order_by('-total_qty')
        )
        production_stock_map = _fetch_production_inventory_map(org_id)
        production_source = bool(production_stock_map)
        if not production_stock_map:
            production_stock_map = _build_local_inventory_map(org_id)

        data_source = 'production_software' if production_source else 'db'

        stock_by_sku = {}
        stock_by_name = {}
        for rec in ShopifyProductCache.objects.filter(organization_id=org_id):
            data = rec.data or {}
            sku = (data.get('sku') or '').lower()
            name = (data.get('name') or '').lower()
            # Try multiple field names — Shopify stores as 'stock' in our cache,
            # but raw API uses 'inventory_quantity'; production enrichment adds 'actualQuantity'
            raw_stock = (
                data.get('stock')
                or data.get('inventory_quantity')
                or data.get('actualQuantity')
                or 0
            )
            try:
                stock_val = int(float(raw_stock or 0))
            except (ValueError, TypeError):
                stock_val = 0
            if sku:
                stock_by_sku[sku] = stock_val
            if name:
                stock_by_name[name] = stock_val

        week_dates = []
        weekly_labels = None
        if period == 'weekly':
            week_end = range_end.date()
            week_start = range_start.date()
            total_weeks = max(1, ((week_end - week_start).days // 7) + 1)
            week_dates = [week_start + timedelta(days=i * 7) for i in range(total_weeks)]
            weekly_labels = [d.strftime('%Y-%m-%d') for d in week_dates]

        def _load_shopify_order_aggregates():
            from core.models import ShopCredentials
            from datetime import datetime
            import requests as http_requests

            try:
                creds = ShopCredentials.objects.get(organization_id=org_id)
            except ShopCredentials.DoesNotExist:
                return [], {}

            shop_url = (
                creds.get_shopify_shop_url()
                or creds.myshopify_domain
                or os.getenv('SHOPIFY_SHOP_URL', '')
            )
            if not shop_url:
                return [], {}

            clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
            api_version = creds.shopify_api_version or '2024-07'
            headers = _shopify_auth_headers(creds)
            fallback_headers = _shopify_alt_auth_headers(creds)
            base_url = f"https://{clean_domain}/admin/api/{api_version}/orders.json"
            params = {
                'status': 'any',
                'limit': 250,
                'created_at_min': range_start.isoformat(),
                'created_at_max': range_end.isoformat(),
            }

            try:
                orders = _shopify_paginate_all(base_url, headers, extra_params=params)
            except ShopifyAPIError as e:
                if e.status_code == 403 and fallback_headers:
                    orders = _shopify_paginate_all(base_url, fallback_headers, extra_params=params)
                else:
                    raise

            totals = {}
            weekly_series = {}

            def _parse_dt(value):
                if not value:
                    return None
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except Exception:
                    return None

            for order in orders:
                order_id = order.get('id') or order.get('order_number')
                order_dt = _parse_dt(order.get('created_at'))
                if season_months and order_dt and order_dt.month not in season_months:
                    continue
                week_key = None
                if order_dt and period == 'weekly':
                    week_key = order_dt.date()
                    week_key = week_key - timedelta(days=week_key.weekday())

                for item in order.get('line_items', []) or []:
                    sku = str(item.get('sku') or '').strip()
                    name = str(item.get('title') or '').strip()
                    key = sku.lower() or name.lower()
                    if not key:
                        continue
                    entry = totals.setdefault(key, {'sku': sku, 'name': name, 'total_qty': 0, 'order_ids': set()})
                    entry['total_qty'] += int(item.get('quantity') or 0)
                    if order_id:
                        entry['order_ids'].add(order_id)
                    if period == 'weekly' and week_key:
                        weekly_series.setdefault(key, {})[week_key] = weekly_series.get(key, {}).get(week_key, 0) + int(item.get('quantity') or 0)

            items_list = []
            for entry in totals.values():
                items_list.append({
                    'title': entry['name'],
                    'sku': entry['sku'],
                    'total_qty': entry['total_qty'],
                    'order_count': len(entry['order_ids']),
                })
            items_list.sort(key=lambda r: r.get('total_qty', 0), reverse=True)
            return items_list, weekly_series

        items = list(qs)
        weekly_series_by_key = {}
        if not items:
            try:
                items, weekly_series_by_key = _load_shopify_order_aggregates()
                if items:
                    data_source = 'shopify_live'
                    if production_stock_map:
                        data_source = 'shopify_live+production_software'
            except ShopifyAPIError as e:
                logger.error("Shopify orders API error %s: %s", e.status_code, e.message)
        elif period == 'weekly':
            weekly_qs = (
                LineItem.objects
                .filter(order__org_id=org_id, order__created_at__gte=range_start, order__created_at__lte=range_end)
                .annotate(week=TruncWeek('order__created_at'))
                .values('title', 'sku', 'week')
                .annotate(total_qty=Sum('quantity'))
            )
            for row in weekly_qs:
                key = (row.get('sku') or '').lower() or (row.get('title') or '').lower()
                if not key:
                    continue
                week_key = row['week'].date()
                weekly_series_by_key.setdefault(key, {})[week_key] = row['total_qty'] or 0

        results = []
        for item in items:
            name = item.get('title') or ''
            sku = item.get('sku') or ''

            if category_filter != 'All':
                # Category isn't stored on LineItem — skip server-side filter;
                # the frontend keeps category filter purely on its side.
                pass
            if search and search not in name.lower() and search not in sku.lower():
                continue

            velocity = round(item.get('total_qty', 0) / days, 2) if days else 0
            predicted_7 = max(0, round(velocity * mult * 7))
            predicted_15 = max(0, round(velocity * mult * 15))
            predicted_30 = max(0, round(velocity * mult * 30))
            # Confidence grows with order volume; cap at 97
            confidence = min(97, round(55 + min(item.get('order_count', 0), 42) * 1.0))

            # ── Resolve both stock sources independently ───────────────────────
            shopify_stock = stock_by_sku.get(sku.lower()) or stock_by_name.get(name.lower()) or 0

            production_stock_entry = None
            if sku:
                production_stock_entry = production_stock_map.get(_normalize_sku(sku))
            if production_stock_entry is None and name:
                production_stock_entry = production_stock_map.get(_normalize_sku(name))

            product_name = name
            if production_stock_entry is not None:
                prod_name = production_stock_entry.get('name')
                if prod_name:
                    product_name = prod_name
                try:
                    prod_stock: int | None = int(float(production_stock_entry.get('actualQuantity', 0) or 0))
                except (ValueError, TypeError):
                    prod_stock = 0
            else:
                # No production match — keep as None so we can distinguish "no data" from "zero"
                prod_stock = None

            # primary current_stock (production preferred, else shopify)
            current_stock = prod_stock if prod_stock is not None else shopify_stock

            weekly_series = None
            if period == 'weekly':
                key = sku.lower() or name.lower()
                weekly_map = weekly_series_by_key.get(key, {})
                weekly_series = [weekly_map.get(d, 0) for d in week_dates]

            # ── Shared AI params (same across both sources) ────────────────────
            velocity_per_day = velocity
            if velocity_per_day >= 1.5:
                velocity_trend = 'up'
            elif velocity_per_day <= 0.3 and item.get('order_count', 0) > 0:
                velocity_trend = 'down'
            else:
                velocity_trend = 'flat'

            trend_mult = {'up': 1.15, 'flat': 1.0, 'down': 0.85}.get(velocity_trend, 1.0)
            adjusted_demand_30 = max(0, round(predicted_30 * trend_mult))
            is_peak = season in ('Festive', 'Winter') or mult > 1.5
            safety_buffer_rate = 0.35 if is_peak else 0.20
            safety_buffer = round(adjusted_demand_30 * safety_buffer_rate)
            lead_time_days = 7
            cover_needed = round(velocity_per_day * lead_time_days)
            trend_desc = {'up': 'rising', 'flat': 'stable', 'down': 'declining'}.get(velocity_trend, 'stable')

            # ── Stock sync discrepancy warning (shared) ────────────────────────
            sync_warning = None
            if production_stock_entry is not None and prod_stock is not None and shopify_stock > 0:
                discrepancy = abs(shopify_stock - prod_stock)
                ref_val = max(shopify_stock, prod_stock, 1)
                if discrepancy > ref_val * 0.15:
                    pct = round(discrepancy / ref_val * 100)
                    sync_warning = (
                        f'Stock sync warning: Shopify shows {shopify_stock} units vs production {prod_stock} units '
                        f'({pct}% discrepancy). Please reconcile before reordering.'
                    )

            def _compute_ai(stock_val, source_label: str):
                """Run the full AI reorder engine for a given stock value.
                Returns None if stock_val is None (source has no data for this SKU).
                """
                if stock_val is None:
                    return None  # No data for this source

                warns: list[str] = []
                conf_adj = False

                base = max(0, adjusted_demand_30 - stock_val + safety_buffer)
                if stock_val < cover_needed:
                    base += cover_needed
                if confidence < 70:
                    base = round(base * 0.90)
                    conf_adj = True
                    warns.append(
                        f'Low confidence ({confidence}%) — suggestion reduced by 10%. Verify with recent order data.'
                    )
                if sync_warning:
                    warns.append(sync_warning)

                qty = max(0, base)
                days_left = round(stock_val / velocity_per_day) if velocity_per_day > 0 else 999

                if days_left <= 7 or (stock_val == 0 and qty > 0):
                    urg = 'high'
                elif days_left <= 20:
                    urg = 'medium'
                elif qty > 0:
                    urg = 'low'
                else:
                    urg = 'none'

                if qty == 0:
                    reason = (
                        f"[{source_label}] Current stock of {stock_val} units comfortably covers the "
                        f"predicted 30-day demand of {adjusted_demand_30} units at a {trend_desc} "
                        f"velocity of {velocity_per_day}/day. No reorder is needed at this time."
                    )
                else:
                    reason = (
                        f"[{source_label}] With a {trend_desc} velocity of {velocity_per_day} units/day and a "
                        f"{'peak-season' if is_peak else 'standard'} safety buffer of {int(safety_buffer_rate * 100)}%, "
                        f"you need ~{adjusted_demand_30} units over 30 days but only have {stock_val} in stock. "
                        f"Ordering {qty} units covers demand plus the {lead_time_days}-day lead-time buffer."
                    )

                return {
                    'suggestedQty': qty,
                    'urgency': urg,
                    'aiReason': reason,
                    'warnings': warns,
                    'confidenceAdjusted': conf_adj,
                    'daysOfStockRemaining': days_left if days_left < 999 else None,
                }

            ai_shopify = _compute_ai(shopify_stock, 'Shopify')
            ai_production = _compute_ai(prod_stock, 'Production')

            # primary AI = production if it has data, else shopify
            primary_ai = (ai_production or ai_shopify) or {
                'suggestedQty': 0, 'urgency': 'none', 'aiReason': '',
                'warnings': [], 'confidenceAdjusted': False, 'daysOfStockRemaining': None,
            }

            results.append({
                'sku': sku,
                'name': name,
                'velocity': velocity,
                'totalQty': item.get('total_qty', 0),
                'predicted7': predicted_7,
                'predicted15': predicted_15,
                'predictedDemand': predicted_30,
                'confidenceScore': confidence,
                'orderCount': item.get('order_count', 0),
                'currentStock': current_stock,
                'weeklySeries': weekly_series,
                'velocityTrend': velocity_trend,
                # Both stock sources — None means "no data from this source"
                'stockShopify': shopify_stock,
                'stockProduction': prod_stock,   # None when production API had no match
                'hasProductionData': production_stock_entry is not None,
                # AI reorder for each source — None when source has no stock data
                'aiShopify': ai_shopify,
                'aiProduction': ai_production,
                # Primary (backward-compat) — same as primary_ai
                'suggestedQty': primary_ai['suggestedQty'],
                'urgency': primary_ai['urgency'],
                'aiReason': primary_ai['aiReason'],
                'warnings': primary_ai['warnings'],
                'confidenceAdjusted': primary_ai['confidenceAdjusted'],
                'daysOfStockRemaining': primary_ai['daysOfStockRemaining'],
            })

        payload = {
            'results': results,
            'period': period,
            'days': days,
            'multiplier': round(mult, 2),
            'has_data': len(results) > 0,
            'rangeStart': range_start.date().isoformat() if range_start else None,
            'rangeEnd': range_end.date().isoformat() if range_end else None,
            'weeklyLabels': weekly_labels,
            'source': data_source,
        }
        cache.set(cache_key, payload, 4 * 60 * 60)
        return Response(payload)


# ---------------------------------------------------------------------------
# /api/inventory/production-orders/   POST
# ---------------------------------------------------------------------------
class ProductionOrderRequestView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        sku = str(request.data.get('sku', '') or '').strip()
        name = str(request.data.get('name', '') or '').strip()
        try:
            qty = int(request.data.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0

        if qty <= 0:
            return Response({"error": "quantity must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'date': timezone.now().date().isoformat(),
            'inventory_type': 'WIP',
            'sku': sku,
            'product_name': name,
            'qty': qty,
            'unit': request.data.get('unit') or 'units',
            'status': 'Pending',
            'source': request.data.get('source') or 'best_selling',
            'notes': request.data.get('notes') or '',
        }

        table = _get_or_create_table(org_id, 'production_orders')
        item = InventoryItem.objects.create(table=table, data=payload)
        return Response({'id': item.id, 'data': item.data}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# /api/inventory/analytics/ai-stock/   GET
# Combines product_inventory items with real order velocity.
# ---------------------------------------------------------------------------

def _classify_sku(velocity, current_stock, min_stock):
    # Negative stock is always low risk regardless of min_stock setting
    if current_stock < 0:
        return 'low_risk'
    # Fast moving: >= 1/day average, or borderline with stock below minimum
    if velocity >= 1 or (velocity >= 0.3 and min_stock > 0 and current_stock < min_stock):
        return 'fast'
    # Low stock risk: below configured minimum threshold
    if min_stock > 0 and current_stock < min_stock:
        return 'low_risk'
    # Overstock: well above minimum with slow movement
    if min_stock > 0 and current_stock >= min_stock * 3 and velocity < 1:
        return 'overstock'
    # Overstock fallback when no min_stock: >6 months of stock at current velocity
    if min_stock == 0 and velocity > 0 and current_stock >= 20 and (current_stock / velocity) > 180:
        return 'overstock'
    # Non-Moving / Dead stock: zero movement with meaningful inventory
    if velocity == 0 and current_stock >= max(min_stock * 2, 15):
        return 'non_moving'
    return 'slow'


def _suggest_action(sku_type, velocity, current_stock, min_stock):
    if sku_type in ('fast', 'low_risk'):
        target = max(min_stock * 2, velocity * 14) - current_stock
        qty = max(10, round(target))
        return {
            'action': 'Restock',
            'qty': qty,
            'priority': 'Urgent' if sku_type == 'fast' else 'Medium',
            'color': '#ef4444',
        }
    if sku_type == 'overstock':
        reduce_target = round(min_stock * 1.5) if min_stock > 0 else round(current_stock * 0.5)
        return {
            'action': 'Reduce',
            'qty': max(0, current_stock - reduce_target),
            'priority': 'Low',
            'color': '#f59e0b',
        }
    if sku_type == 'slow':
        return {'action': 'Monitor', 'qty': 0, 'priority': 'Low', 'color': '#64748b'}
    if sku_type in ('dead', 'non_moving'):
        return {'action': 'Clear Stock', 'qty': current_stock, 'priority': 'Low', 'color': '#8b5cf6'}
    return {'action': 'Monitor', 'qty': 0, 'priority': 'Low', 'color': '#64748b'}


class AIStockKeeperView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import datetime, time
        from django.db.models import Sum, Count
        from core.models import LineItem
        from inventory.models import ShopifyProductCache

        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "Organisation not found."}, status=status.HTTP_403_FORBIDDEN)

        api_url, api_key = _get_production_software_creds(org_id)
        production_map = _fetch_production_inventory_map(org_id)
        production_source = bool(production_map)
        api_error = None
        if api_url and not production_map:
            api_error = 'Production Software API access denied or failed. Showing Shopify and local inventory only.'
            production_map = _build_local_inventory_map(org_id)
        elif not production_map:
            production_map = _build_local_inventory_map(org_id)

        # ── 1. Fetch inventory items from product_inventory table ──
        try:
            table = InventoryTable.objects.get(
                organization_id=org_id, table_key='product_inventory'
            )
            items = list(InventoryItem.objects.filter(table=table))
        except InventoryTable.DoesNotExist:
            items = []

        # Build a unified base list from product_inventory table rows.
        base_rows = []
        seen_keys = set()
        source_param = request.query_params.get('source', 'production')
        prod_only_count = 0

        # 1. Base list always starts with Shopify Products for consistency in naming and categories
        from inventory.models import ShopifyProductCache
        shopify_added = 0
        for rec in ShopifyProductCache.objects.filter(organization_id=org_id):
            prod_data = rec.data or {}
            name = str(prod_data.get('name') or '').strip()
            sku = str(prod_data.get('sku') or '').strip()
            
            quantity = 0
            location = 'Shopify'
            
            if source_param == 'production':
                production_entry = None
                for key in [sku, name]:
                    if key:
                        production_entry = production_map.get(_normalize_sku(key))
                        if production_entry:
                            break
                if production_entry:
                    quantity = production_entry.get('actualQuantity', 0)
                    location = production_entry.get('location', 'Production')
                else:
                    # check if in items (product_inventory table)
                    for item in items:
                        idata = item.data or {}
                        isku = str(idata.get('sku') or idata.get('final_sku') or idata.get('master_sku') or '').strip()
                        iname = str(idata.get('name') or idata.get('product_name') or idata.get('title') or '').strip()
                        if (sku and _normalize_sku(sku) == _normalize_sku(isku)) or (name and _normalize_sku(name) == _normalize_sku(iname)):
                            try:
                                quantity = int(float(idata.get('actual_quantity') or idata.get('quantity') or 0))
                            except:
                                quantity = 0
                            location = idata.get('location', 'Production')
                            break
                    if not location or location == 'Shopify':
                        location = 'Production'
            else:
                quantity = prod_data.get('stock', 0)

            data = {
                'name': name,
                'sku': sku,
                'category': str(prod_data.get('category') or ''),
                'quantity': quantity,
                'min_stock': 0,
                'location': location,
            }
            
            # Using rec.id for dedupe ensures we don't drop products with duplicate SKUs in Shopify
            dedupe_key = f"shopify_{rec.id}"
            seen_keys.add(dedupe_key)
            # Also keep track of SKUs/Names so we don't add them twice from items
            if sku:
                seen_keys.add(_normalize_sku(sku))
            if name:
                seen_keys.add(_normalize_sku(name))
                
            base_rows.append((rec.id, data))
            shopify_added += 1

        # 2. Add any remaining items from local production inventory that were NOT in Shopify
        for item in items:
            data = item.data or {}
            sku = str(data.get('sku') or data.get('final_sku') or data.get('master_sku') or '').strip()
            name = str(data.get('name') or data.get('product_name') or data.get('title') or '').strip()

            if sku and _normalize_sku(sku) in seen_keys:
                continue
            if name and _normalize_sku(name) in seen_keys:
                continue

            if source_param == 'production':
                production_entry = None
                for key in [sku, str(data.get('final_sku') or ''), str(data.get('master_sku') or ''), name]:
                    if key:
                        production_entry = production_map.get(_normalize_sku(key))
                        if production_entry:
                            break

                if production_entry:
                    if not name and production_entry.get('name'):
                        name = production_entry.get('name')
                    if not sku:
                        sku = production_entry.get('finalSku') or production_entry.get('masterSku') or sku
                    if data.get('quantity') in (None, ''):
                        data['quantity'] = production_entry.get('actualQuantity')
                    if not data.get('location'):
                        data['location'] = production_entry.get('location')
                    if not data.get('unit'):
                        data['unit'] = production_entry.get('unit')
                    if production_entry.get('name'):
                        data['name'] = production_entry.get('name')
                    if sku:
                        data['sku'] = sku

            if sku:
                seen_keys.add(_normalize_sku(sku))
            if name:
                seen_keys.add(_normalize_sku(name))
            base_rows.append((item.id, data))

        if source_param == 'production':
            for prod_key, prod_entry in production_map.items():
                sku = str(prod_entry.get('finalSku') or prod_entry.get('masterSku') or '').strip()
                name = str(prod_entry.get('name') or '').strip()

                if (sku and _normalize_sku(sku) in seen_keys) or (name and _normalize_sku(name) in seen_keys):
                    continue

                if not sku and not name:
                    continue

                if sku:
                    seen_keys.add(_normalize_sku(sku))
                if name:
                    seen_keys.add(_normalize_sku(name))

                data = {
                    'name': name,
                    'sku': sku,
                    'category': str(prod_entry.get('category') or ''),
                    'quantity': 0,
                    'min_stock': 0,
                    'location': prod_entry.get('location', 'Production'),
                }
                try:
                    data['quantity'] = int(float(prod_entry.get('actualQuantity', 0) or 0))
                except:
                    pass
                
                base_rows.append((f'prod_{prod_key}', data))
                prod_only_count += 1

        # ── 2. Resolve analysis window & filters ──
        def _parse_date(value):
            try:
                return datetime.strptime(value, '%Y-%m-%d').date()
            except Exception:
                return None

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        category_filter = request.query_params.get('category', 'All')
        search = (request.query_params.get('search', '') or '').strip().lower()

        now = timezone.now()
        if start_date and end_date:
            s = _parse_date(start_date)
            e = _parse_date(end_date)
            if s and e and s <= e:
                analysis_start = timezone.make_aware(datetime.combine(s, time.min))
                analysis_end = timezone.make_aware(datetime.combine(e, time.max))
            else:
                analysis_end = now
                analysis_start = now - timedelta(days=30)
        else:
            analysis_end = now
            analysis_start = now - timedelta(days=30)

        window_days = max(1, (analysis_end.date() - analysis_start.date()).days + 1)

        # ── 3. Compute sales velocity and order counts from orders ──
        raw_velocity = (
            LineItem.objects
            .filter(order__org_id=org_id, order__created_at__gte=analysis_start, order__created_at__lte=analysis_end)
            .values('title', 'sku')
            .annotate(total_qty=Sum('quantity'), order_count=Count('order', distinct=True))
        )

        # Build lookup maps (normalised to lowercase for fuzzy matching)
        vel_by_sku = {}
        vel_by_name = {}
        qty_by_sku = {}
        qty_by_name = {}
        order_count_by_sku = {}
        order_count_by_name = {}
        for v in raw_velocity:
            qty_total = v['total_qty'] or 0
            qty_per_day = qty_total / window_days
            order_count = v.get('order_count') or 0
            if v['sku']:
                sku_key = v['sku'].lower()
                vel_by_sku[sku_key] = qty_per_day
                qty_by_sku[sku_key] = qty_total
                order_count_by_sku[sku_key] = order_count
            if v['title']:
                name_key = v['title'].lower()
                vel_by_name[name_key] = qty_per_day
                qty_by_name[name_key] = qty_total
                order_count_by_name[name_key] = order_count

        # ── 4. Build classified result list ──
        results = []
        for row_id, data in base_rows:
            # Product inventory rows can carry different key names depending on source/sync.
            name = str(
                data.get('name')
                or data.get('product_name')
                or data.get('title')
                or ''
            )
            sku = str(
                data.get('sku')
                or data.get('final_sku')
                or data.get('master_sku')
                or ''
            )
            category = str(data.get('category', '') or '')
            location = str(data.get('location', '') or '')

            production_entry = None
            for key in [sku, str(data.get('final_sku') or ''), str(data.get('master_sku') or ''), name]:
                if key:
                    production_entry = production_map.get(_normalize_sku(key))
                    if production_entry:
                        break

            if production_entry:
                if production_entry.get('name'):
                    name = production_entry.get('name')
                if not sku:
                    sku = production_entry.get('finalSku') or production_entry.get('masterSku') or sku

            if category_filter != 'All' and category != category_filter:
                continue
            if search and search not in name.lower() and search not in sku.lower():
                continue

            current_stock = None
            for key in [
                sku,
                str(data.get('final_sku') or ''),
                str(data.get('master_sku') or ''),
            ]:
                if key:
                    entry = production_map.get(_normalize_sku(key))
                    if entry is not None:
                        try:
                            current_stock = int(float(entry.get('actualQuantity', 0) or 0))
                        except (ValueError, TypeError):
                            current_stock = 0
                        break

            if current_stock is None:
                try:
                    current_stock = int(float(
                        data.get('quantity')
                        or data.get('actual_quantity')
                        or data.get('stock')
                        or 0
                    ))
                except (ValueError, TypeError):
                    current_stock = 0
            try:
                min_stock = int(float(
                    data.get('min_stock')
                    or data.get('safety_stock')
                    or data.get('reorder_level')
                    or 0
                ))
            except (ValueError, TypeError):
                min_stock = 0

            # Match velocity: try SKU first, then product name
            velocity = float(vel_by_sku.get(sku.lower(), vel_by_name.get(name.lower(), 0.0)) or 0.0)
            velocity = round(velocity, 2)
            sold_qty = int(qty_by_sku.get(sku.lower(), qty_by_name.get(name.lower(), 0)) or 0)
            order_count = int(order_count_by_sku.get(sku.lower(), order_count_by_name.get(name.lower(), 0)) or 0)
            current_stock_int: int = current_stock if isinstance(current_stock, int) else int(current_stock or 0)

            avg_sales = round(velocity * 0.85, 2)  # rough 85% of current velocity
            trend = 'up' if velocity >= 10 else ('down' if velocity <= 2 else 'stable')

            days_left = round(current_stock_int / velocity, 1) if velocity > 0 else None
            stockout_date = None
            if days_left is not None:
                stockout_date = (timezone.now().date() + timedelta(days=max(0, int(days_left)))).isoformat()

            low_stock_alert = current_stock_int < 0 or (days_left is not None and days_left <= 10) or (min_stock > 0 and current_stock_int < min_stock)
            stock_turnover_ratio = round(sold_qty / max(current_stock_int, 1), 2)
            confidence = min(97, round(55 + min(order_count, 42) * 1.0))

            sku_type = _classify_sku(velocity, current_stock, min_stock)
            suggestion = _suggest_action(sku_type, velocity, current_stock, min_stock)

            results.append({
                'id': row_id,
                'sku': sku,
                'name': name,
                'category': category,
                'location': location,
                'currentStock': current_stock,
                'minStock': min_stock,
                'salesVelocity': velocity,
                'avgSales': avg_sales,
                'totalSoldQty': sold_qty,
                'predicted7': max(0, round(velocity * 7)),
                'predicted15': max(0, round(velocity * 15)),
                'predicted30': max(0, round(velocity * 30)),
                'daysOfStockRemaining': days_left,
                'stockoutDate': stockout_date,
                'lowStockAlert': low_stock_alert,
                'stockTurnoverRatio': stock_turnover_ratio,
                'confidenceScore': confidence,
                'orderCount': order_count,
                'trend': trend,
                'skuType': sku_type,
                'suggestion': suggestion,
            })

        # Sort: fast/low_risk first
        priority_order = {'fast': 0, 'low_risk': 1, 'overstock': 2, 'slow': 3, 'dead': 4, 'non_moving': 4}
        results.sort(key=lambda r: (priority_order.get(r['skuType'], 4), -r['salesVelocity']))

        result_source = 'production_software' if production_source else 'product_inventory'
        return Response({
            'results': results,
            'has_data': len(results) > 0,
            'rangeStart': analysis_start.date().isoformat(),
            'rangeEnd': analysis_end.date().isoformat(),
            'windowDays': window_days,
            'source': result_source,
            'inventoryRows': len(items),
            'shopifyRowsAdded': shopify_added,
            'totalRows': len(base_rows),
            'prod_only_count': prod_only_count,
            'api_error': api_error
        })


# ---------------------------------------------------------------------------
# Helpers shared by both Shopify views
# ---------------------------------------------------------------------------
SHOPIFY_CACHE_TTL = 300  # 5 minutes


class ShopifyAPIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Shopify API {status_code}: {message}")


def _shopify_auth_headers(creds):
    """Return HTTP auth headers for the org's Shopify credentials."""
    from core.models import decrypt_data
    import base64
    if creds.auth_method == 'oauth' and creds.shopify_access_token_encrypted:
        token = decrypt_data(creds.shopify_access_token_encrypted)
        return {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
    api_key  = creds.get_shopify_api_key() or os.getenv('SHOPIFY_API_KEY', '')
    password = creds.get_shopify_password() or os.getenv('SHOPIFY_API_PASSWORD', '')

    # Modern Shopify Custom Apps provide an Admin API access token starting with 'shpat_'
    # If the user put this into the Legacy Password field, use it properly as an access token.
    if password and password.startswith('shpat_'):
        return {'X-Shopify-Access-Token': password, 'Content-Type': 'application/json'}

    encoded  = base64.b64encode(f"{api_key}:{password}".encode()).decode()
    return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}


def _shopify_alt_auth_headers(creds):
    """Return alternate auth headers if the primary auth method fails."""
    from core.models import decrypt_data
    import base64
    if creds.auth_method == 'oauth':
        api_key = creds.get_shopify_api_key() or os.getenv('SHOPIFY_API_KEY', '')
        password = creds.get_shopify_password() or os.getenv('SHOPIFY_API_PASSWORD', '')
        if api_key and password:
            if password.startswith('shpat_'):
                return {'X-Shopify-Access-Token': password, 'Content-Type': 'application/json'}
            encoded = base64.b64encode(f"{api_key}:{password}".encode()).decode()
            return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}
    else:
        if creds.shopify_access_token_encrypted:
            token = decrypt_data(creds.shopify_access_token_encrypted)
            return {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
    return None


def _shopify_paginate_all(base_url, headers, extra_params=None):
    """
    Walk all cursor-based pages from a Shopify REST endpoint.
    Returns a flat list of all items.
    """
    import requests as http_requests, re
    all_items = []
    params = {'limit': 250, **(extra_params or {})}
    page_info = None
    while True:
        req_params = {'limit': 250, 'page_info': page_info} if page_info else params
        resp = http_requests.get(base_url, headers=headers, params=req_params, timeout=30)
        if not resp.ok:
            raise ShopifyAPIError(resp.status_code, resp.text[:1000])
        data = resp.json()
        # Works for both products and collections endpoints
        for key in ('products', 'custom_collections', 'smart_collections'):
            if key in data:
                all_items.extend(data[key])
                break
        link_header = resp.headers.get('Link', '')
        if 'rel="next"' not in link_header:
            break
        m = re.search(r'page_info=([^&>]+)[^>]*>;\s*rel="next"', link_header)
        page_info = m.group(1) if m else None
        if not page_info:
            break
    return all_items


def _shopify_collection_product_count(clean_domain, api_version, collection_id, headers, fallback_headers=None):
    """
    Count products in a collection using the same membership endpoint used by
    collection filtering. The nested /products/count endpoint is not reliable
    for all Shopify REST versions/scopes and can quietly produce cached zeroes.
    """
    base_url = f"https://{clean_domain}/admin/api/{api_version}/collections/{collection_id}/products.json"
    try:
        return len(_shopify_paginate_all(base_url, headers, extra_params={'fields': 'id'}))
    except ShopifyAPIError as e:
        if e.status_code == 403 and fallback_headers:
            return len(_shopify_paginate_all(base_url, fallback_headers, extra_params={'fields': 'id'}))
        raise


def _refresh_zero_collection_counts(org_id, all_results, clean_domain, api_version, headers, fallback_headers=None):
    """Repair cached collection rows whose productCount is missing or all zero."""
    if not all_results or any((row.get('productCount') or 0) > 0 for row in all_results):
        return all_results

    from .models import ShopifyCollectionCache as _SCC

    now_ts = timezone.now()
    refreshed = []
    changed = False
    for row in all_results:
        collection_id = row.get('id') or row.get('shopifyId')
        if not collection_id:
            refreshed.append(row)
            continue
        try:
            product_count = _shopify_collection_product_count(
                clean_domain, api_version, collection_id, headers, fallback_headers
            )
        except Exception:
            logger.exception('Failed to refresh Shopify collection product count for %s', collection_id)
            product_count = row.get('productCount') or 0

        updated = {**row, 'productCount': product_count}
        changed = changed or product_count != (row.get('productCount') or 0)
        refreshed.append(updated)

    if changed:
        with transaction.atomic():
            for row in refreshed:
                sid = row.get('id') or row.get('shopifyId')
                if sid:
                    _SCC.objects.update_or_create(
                        organization_id=org_id,
                        shopify_id=int(sid),
                        defaults={'data': row, 'synced_at': now_ts},
                    )
        logger.info('Shopify collection product counts refreshed from membership endpoint for org %s', org_id)

    return refreshed


# ---------------------------------------------------------------------------
# /api/inventory/shopify/products/     GET
# Query params:
#   page        int   Page number (1-based, default 1)
#   page_size   int   Rows per page (default 50, max 250)
#   search      str   Filter by name/sku/category
#   status      str   Filter by status ('All' = no filter)
#   refresh     bool  Bust cache and re-fetch from Shopify
# ---------------------------------------------------------------------------
class ShopifyProductsView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache
        from core.models import ShopCredentials

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Fetch shop credentials
        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            return Response({'error': 'Shopify credentials not configured.'}, status=status.HTTP_404_NOT_FOUND)

        # Resolve shop domain — DB first, then env fallback
        shop_url = (
            creds.get_shopify_shop_url()
            or creds.myshopify_domain
            or os.getenv('SHOPIFY_SHOP_URL', '')
        )
        if not shop_url:
            return Response(
                {'error': 'Shopify shop URL not configured. Please save your credentials in Settings.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
        api_version = creds.shopify_api_version or '2024-07'
        cache_key = f'shopify_products_{org_id}'

        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(250, max(1, int(request.query_params.get('page_size', 50))))
        except (ValueError, TypeError):
            page, page_size = 1, 50

        search          = request.query_params.get('search', '').strip().lower()
        status_filter   = request.query_params.get('status', 'All').strip()
        category_filter = request.query_params.get('category', 'All').strip()
        collection_filter = request.query_params.get('collection', 'All').strip()
        do_refresh      = request.query_params.get('refresh', '').lower() in ('1', 'true', 'yes')

        # ── Fetch full list (in-memory cache → DB cache → Shopify API) ─────────
        all_results = None if do_refresh else cache.get(cache_key)

        # Initialize auth headers (needed for collection filtering)
        headers = _shopify_auth_headers(creds)
        fallback_headers = _shopify_alt_auth_headers(creds)

        # Fall back to DB cache if in-memory cache missed
        if all_results is None and not do_refresh:
            from .models import ShopifyProductCache as _SPC
            db_qs = _SPC.objects.filter(organization_id=org_id).order_by('shopify_id')
            if db_qs.exists():
                all_results = [rec.data for rec in db_qs]
                cache.set(cache_key, all_results, SHOPIFY_CACHE_TTL)
                logger.info('Shopify products loaded from DB cache (%d records) for org %s', len(all_results), org_id)

        if all_results is None:
            base_url = f"https://{clean_domain}/admin/api/{api_version}/products.json"

            try:
                all_products = _shopify_paginate_all(base_url, headers, extra_params={'status': 'any'})
            except ShopifyAPIError as e:
                if e.status_code == 403 and fallback_headers:
                    logger.warning("Primary Shopify auth failed with 403, trying alternate auth headers.")
                    try:
                        all_products = _shopify_paginate_all(base_url, fallback_headers, extra_params={'status': 'any'})
                    except ShopifyAPIError as e2:
                        logger.error("Shopify products API error %s: %s", e2.status_code, e2.message)
                        return Response(
                            {'error': f'Shopify API error: {e2.status_code}', 'details': e2.message},
                            status=e2.status_code,
                        )
                else:
                    logger.error("Shopify products API error %s: %s", e.status_code, e.message)
                    return Response(
                        {'error': f'Shopify API error: {e.status_code}', 'details': e.message},
                        status=e.status_code,
                    )
            except Exception as e:
                logger.exception("Error fetching Shopify products")
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            all_results = []
            for p in all_products:
                variant = p.get('variants', [{}])[0]
                image_src = p.get('image', {}).get('src', '') if p.get('image') else ''
                all_results.append({
                    'id': p.get('id'),
                    'name': p.get('title', ''),
                    'sku': variant.get('sku', ''),
                    'category': p.get('product_type', '') or p.get('vendor', ''),
                    'price': variant.get('price', '0'),
                    'stock': variant.get('inventory_quantity', 0),
                    'status': p.get('status', '').capitalize(),
                    'shopifyId': str(p.get('id', '')),
                    'handle': p.get('handle', ''),
                    'image': image_src,
                    'vendor': p.get('vendor', ''),
                    'tags': p.get('tags', ''),
                    'createdAt': p.get('created_at', ''),
                    'updatedAt': p.get('updated_at', ''),
                    'variantsCount': len(p.get('variants', [])),
                })

            cache.set(cache_key, all_results, SHOPIFY_CACHE_TTL)

            # Persist to DB cache (ShopifyProductCache) for cross-restart durability
            try:
                from .models import ShopifyProductCache as _SPC
                now_ts = timezone.now()
                with transaction.atomic():
                    for row in all_results:
                        sid = row.get('id')
                        if sid:
                            _SPC.objects.update_or_create(
                                organization_id=org_id,
                                shopify_id=int(sid),
                                defaults={'data': row, 'synced_at': now_ts},
                            )
                logger.info('Shopify products saved to DB cache (%d records) for org %s', len(all_results), org_id)
            except Exception:
                logger.exception('Failed to save Shopify products to DB cache')

        # Enrichment: try external production API first, fall back to local DB
        production_map = _fetch_production_inventory_map(org_id)
        if not production_map:
            production_map = _build_local_inventory_map(org_id)

        if production_map:
            for row in all_results:
                sku_key = _normalize_sku(row.get('sku'))
                if not sku_key:
                    continue
                extra = production_map.get(sku_key)
                if not extra:
                    continue
                row['masterSku'] = extra.get('masterSku', '')
                row['finalSku'] = extra.get('finalSku', '')
                row['actualQuantity'] = extra.get('actualQuantity', '')
                row['unit'] = extra.get('unit', '')
                row['location'] = extra.get('location', '')

        # ── Enrich with real WIP from production software ────────────────────
        wip_map = _fetch_wip_map(org_id)
        if wip_map:
            for row in all_results:
                # Try Shopify SKU first, then finalSku, then masterSku
                wip_entry = (
                    wip_map.get(_normalize_sku(row.get('sku'))) or
                    wip_map.get(_normalize_sku(row.get('finalSku', ''))) or
                    wip_map.get(_normalize_sku(row.get('masterSku', '')))
                )
                row['wipQty'] = wip_entry['wipQty'] if wip_entry else None

        # ── Enrich with order demand data (latest day + last 90 days) ─────────
        latest_order_date_str = None
        try:
            from django.db.models import Sum, Count as DCount, Q, Max
            from core.models import LineItem, Order

            now          = timezone.now()
            demand_start = now - timedelta(days=90)

            # Find the most recent day that has ANY orders so "1-day" always has data
            latest_ts = Order.objects.aggregate(latest=Max('created_at'))['latest']
            if latest_ts:
                latest_day_start = latest_ts.replace(hour=0, minute=0, second=0, microsecond=0)
                latest_day_end   = latest_day_start + timedelta(days=1)
                latest_order_date_str = latest_ts.strftime('%b %d')
            else:
                latest_day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                latest_day_end   = now

            # Collect all Shopify product IDs from the current result set.
            shopify_pids = set()
            for row in all_results:
                pid = row.get('id') or row.get('shopifyId')
                if pid:
                    try:
                        shopify_pids.add(int(pid))
                    except (ValueError, TypeError):
                        pass

            def _build_demand_maps(qs):
                """Return (by_pid, by_sku, by_name) dicts from a LineItem queryset."""
                by_pid, by_sku, by_name = {}, {}, {}
                if shopify_pids:
                    for d in (
                        qs.filter(product_id__in=shopify_pids)
                          .values('product_id')
                          .annotate(total_qty=Sum('quantity'), order_count=DCount('order', distinct=True))
                    ):
                        by_pid[str(d['product_id'])] = {
                            'demandQty': d['total_qty'] or 0,
                            'demandOrders': d['order_count'] or 0,
                        }
                _results  = all_results or []
                all_skus  = [r.get('sku', '').lower() for r in _results if r.get('sku')]
                all_names = [r.get('name', '').lower() for r in _results if r.get('name')]
                if all_skus or all_names:
                    sku_q  = Q(sku__in=all_skus)   if all_skus  else Q()
                    name_q = Q(title__in=all_names) if all_names else Q()
                    for d in (
                        qs.filter(sku_q | name_q)
                          .values('sku', 'title')
                          .annotate(total_qty=Sum('quantity'), order_count=DCount('order', distinct=True))
                    ):
                        entry = {'demandQty': d['total_qty'] or 0, 'demandOrders': d['order_count'] or 0}
                        if d['sku']:   by_sku[d['sku'].lower()]    = entry
                        if d['title']: by_name[d['title'].lower()] = entry
                return by_pid, by_sku, by_name

            base_qs  = LineItem.objects.filter(order__created_at__gte=demand_start)
            today_qs = LineItem.objects.filter(
                order__created_at__gte=latest_day_start,
                order__created_at__lt=latest_day_end,
            )

            pid90, sku90, name90 = _build_demand_maps(base_qs)
            pid1,  sku1,  name1  = _build_demand_maps(today_qs)

            for row in all_results:
                shopify_pid = str(row.get('id') or row.get('shopifyId') or '')
                sku_key     = (row.get('sku') or '').lower()
                name_key    = (row.get('name') or '').lower()

                d90 = pid90.get(shopify_pid) or sku90.get(sku_key) or name90.get(name_key)
                d1  = pid1.get(shopify_pid)  or sku1.get(sku_key)  or name1.get(name_key)

                row['demandQty']         = d90['demandQty']    if d90 else 0
                row['demandOrders']      = d90['demandOrders'] if d90 else 0
                row['todayDemandQty']    = d1['demandQty']     if d1  else 0
                row['todayDemandOrders'] = d1['demandOrders']  if d1  else 0

        except Exception:
            logger.exception('Failed to enrich products with demand data')
            for row in all_results:
                row.setdefault('demandQty', 0)
                row.setdefault('demandOrders', 0)
                row.setdefault('todayDemandQty', 0)
                row.setdefault('todayDemandOrders', 0)

        # ── Extract available statuses & categories ─────────────────────────
        statuses   = sorted(list({r['status'] for r in all_results if r.get('status')}))
        categories = sorted(list({r['category'] for r in all_results if r.get('category')}))

        # ── Filter ──────────────────────────────────────────────────────────
        filtered = all_results
        if search:
            filtered = [
                r for r in filtered
                if search in (r['name'] or '').lower()
                or search in (r['sku'] or '').lower()
                or search in (r['category'] or '').lower()
            ]
        
        if status_filter and status_filter != 'All':
            filtered = [r for r in filtered if r.get('status') == status_filter]

        if category_filter and category_filter != 'All':
            filtered = [r for r in filtered if r.get('category') == category_filter]

        if collection_filter and collection_filter != 'All':
            try:
                collect_url = f"https://{clean_domain}/admin/api/{api_version}/collections/{collection_filter}/products.json?fields=id"
                try:
                    collection_products = _shopify_paginate_all(collect_url, headers)
                except ShopifyAPIError as e:
                    if e.status_code == 403 and fallback_headers:
                        collection_products = _shopify_paginate_all(collect_url, fallback_headers)
                    else:
                        raise
                collection_ids = {str(p.get('id')) for p in collection_products}
                filtered = [r for r in filtered if str(r.get('shopifyId')) in collection_ids]
            except Exception:
                logger.exception('Failed to filter products by Shopify collection %s', collection_filter)
                filtered = []

        # ── Sort: best-selling first; archived/draft last ─────────────────
        def _status_rank(status_value):
            status_norm = (status_value or '').strip().lower()
            if status_norm == 'active':
                return 0
            if status_norm in ('archived', 'draft'):
                return 2
            return 1

        filtered = sorted(
            filtered,
            key=lambda r: (
                _status_rank(r.get('status')),
                -(r.get('demandQty') or 0),
                -(r.get('demandOrders') or 0),
                (r.get('name') or '').lower(),
            ),
        )

        # ── Paginate ────────────────────────────────────────────────────────
        total      = len(filtered)
        start      = (page - 1) * page_size
        end        = start + page_size
        page_items = filtered[start:end]
        has_next   = end < total

        return Response({
            'results':          page_items,
            'total':            total,
            'page':             page,
            'page_size':        page_size,
            'has_next':         has_next,
            'shop':             clean_domain,
            'statuses':         statuses,
            'categories':       categories,
            'cached':           not do_refresh,
            'latestOrderDate':  latest_order_date_str,
        })


# ---------------------------------------------------------------------------
# /api/inventory/shopify/categories/   GET
# Query params:
#   page        int   Page number (1-based, default 1)
#   page_size   int   Rows per page (default 50, max 250)
#   search      str   Filter by name/handle
#   refresh     bool  Bust cache
# ---------------------------------------------------------------------------
class ShopifyCategoriesView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        import requests as http_requests
        from django.core.cache import cache
        from core.models import ShopCredentials

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            return Response({'error': 'Shopify credentials not configured.'}, status=status.HTTP_404_NOT_FOUND)

        shop_url     = (
            creds.get_shopify_shop_url()
            or creds.myshopify_domain
            or os.getenv('SHOPIFY_SHOP_URL', '')
        )
        if not shop_url:
            return Response(
                {'error': 'Shopify shop URL not configured. Please save your credentials in Settings.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
        api_version  = creds.shopify_api_version or '2024-07'
        cache_key    = f'shopify_categories_{org_id}'

        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(250, max(1, int(request.query_params.get('page_size', 50))))
        except (ValueError, TypeError):
            page, page_size = 1, 50

        search     = request.query_params.get('search', '').strip().lower()
        do_refresh = request.query_params.get('refresh', '').lower() in ('1', 'true', 'yes')

        # ── Fetch full list (in-memory cache → DB cache → Shopify API) ─────────
        all_results = None if do_refresh else cache.get(cache_key)
        loaded_from_memory_cache = all_results is not None

        # Fall back to DB cache if in-memory cache missed
        headers     = _shopify_auth_headers(creds)
        fallback_headers = _shopify_alt_auth_headers(creds)

        if loaded_from_memory_cache:
            all_results = _refresh_zero_collection_counts(
                org_id, all_results, clean_domain, api_version, headers, fallback_headers
            )
            cache.set(cache_key, all_results, SHOPIFY_CACHE_TTL)

        if all_results is None and not do_refresh:
            from .models import ShopifyCollectionCache as _SCC
            db_qs = _SCC.objects.filter(organization_id=org_id).order_by('shopify_id')
            if db_qs.exists():
                all_results = [rec.data for rec in db_qs]
                all_results = _refresh_zero_collection_counts(
                    org_id, all_results, clean_domain, api_version, headers, fallback_headers
                )
                cache.set(cache_key, all_results, SHOPIFY_CACHE_TTL)
                logger.info('Shopify collections loaded from DB cache (%d records) for org %s', len(all_results), org_id)

        if all_results is None:
            all_results = []
            try:
                for col_type in ['custom_collections', 'smart_collections']:
                    base_url = f"https://{clean_domain}/admin/api/{api_version}/{col_type}.json"
                    try:
                        raw = _shopify_paginate_all(base_url, headers)
                    except ShopifyAPIError as e:
                        if e.status_code == 403 and fallback_headers:
                            logger.warning("Primary Shopify auth failed for categories with 403, trying alternate auth headers.")
                            raw = _shopify_paginate_all(base_url, fallback_headers)
                        else:
                            raise
                    for c in raw:
                        product_count = _shopify_collection_product_count(
                            clean_domain, api_version, c['id'], headers, fallback_headers
                        )
                        all_results.append({
                            'id':           c.get('id'),
                            'name':         c.get('title', ''),
                            'shopifyId':    str(c.get('id', '')),
                            'handle':       c.get('handle', ''),
                            'type':         'smart' if col_type == 'smart_collections' else 'custom',
                            'productCount': product_count,
                            'status':       'Active' if c.get('published_at') else 'Draft',
                            'image':        c.get('image', {}).get('src', '') if c.get('image') else '',
                            'updatedAt':    c.get('updated_at', ''),
                            'sortOrder':    c.get('sort_order', ''),
                        })
            except ShopifyAPIError as e:
                logger.error("Shopify categories API error %s: %s", e.status_code, e.message)
                return Response(
                    {'error': f'Shopify API error: {e.status_code}', 'details': e.message},
                    status=e.status_code,
                )
            except Exception as e:
                logger.exception("Error fetching Shopify categories")
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            cache.set(cache_key, all_results, SHOPIFY_CACHE_TTL)

            # Persist to ShopifyCollectionCache DB
            try:
                from .models import ShopifyCollectionCache as _SCC
                now_ts = timezone.now()
                with transaction.atomic():
                    for row in all_results:
                        sid = row.get('id')
                        if sid:
                            _SCC.objects.update_or_create(
                                organization_id=org_id,
                                shopify_id=int(sid),
                                defaults={'data': row, 'synced_at': now_ts},
                            )
                logger.info('Shopify collections saved to DB cache (%d records) for org %s', len(all_results), org_id)
            except Exception:
                logger.exception('Failed to save Shopify collections to DB cache')

        # ── Filter ──────────────────────────────────────────────────────────
        filtered = all_results
        if search:
            filtered = [
                r for r in filtered
                if search in (r['name'] or '').lower()
                or search in (r['handle'] or '').lower()
            ]

        # ── Paginate ────────────────────────────────────────────────────────
        total      = len(filtered)
        start      = (page - 1) * page_size
        end        = start + page_size
        page_items = filtered[start:end]
        has_next   = end < total

        return Response({
            'results':   page_items,
            'total':     total,
            'page':      page,
            'page_size': page_size,
            'has_next':  has_next,
            'shop':      clean_domain,
            'cached':    not do_refresh,
        })


# ---------------------------------------------------------------------------
# /api/inventory/shopify/sync/   POST
# Clears the Shopify product/category cache so the next request re-fetches
# fresh data from the Shopify API.
# ---------------------------------------------------------------------------
class ShopifyCacheSyncView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return DB cache stats: count + last synced time."""
        from .models import ShopifyProductCache as _SPC
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        qs = _SPC.objects.filter(organization_id=org_id)
        count = qs.count()
        last_synced = None
        if count:
            latest = qs.order_by('-synced_at').first()
            if latest is not None:
                last_synced = latest.synced_at.isoformat()

        return Response({
            'db_product_count': count,
            'last_synced': last_synced,
            'detail': f'{count} products cached in DB.' + (f' Last synced: {last_synced}' if last_synced else ''),
        })

    def post(self, request):
        """Full sync: fetch all products from Shopify and save to ShopifyProductCache DB."""
        import requests as http_requests
        from django.core.cache import cache
        from core.models import ShopCredentials, decrypt_data
        from .models import ShopifyProductCache as _SPC

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            creds = ShopCredentials.objects.get(organization_id=org_id)
        except ShopCredentials.DoesNotExist:
            return Response({'error': 'Shopify credentials not configured.'}, status=status.HTTP_404_NOT_FOUND)

        shop_url = (
            creds.get_shopify_shop_url()
            or creds.myshopify_domain
            or os.getenv('SHOPIFY_SHOP_URL', '')
        )
        if not shop_url:
            return Response({'error': 'Shopify shop URL not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
        api_version = creds.shopify_api_version or '2024-07'

        if creds.auth_method == 'oauth' and creds.shopify_access_token_encrypted:
            token = decrypt_data(creds.shopify_access_token_encrypted)
            headers = {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
        else:
            import base64
            api_key = creds.get_shopify_api_key() or os.getenv('SHOPIFY_API_KEY', '')
            password = creds.get_shopify_password() or os.getenv('SHOPIFY_API_PASSWORD', '')
            encoded = base64.b64encode(f"{api_key}:{password}".encode()).decode()
            headers = {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}
        fallback_headers = _shopify_alt_auth_headers(creds)

        all_products = []
        base_url = f"https://{clean_domain}/admin/api/{api_version}/products.json"
        params = {'limit': 250, 'status': 'active,draft'}
        page_info = None

        try:
            while True:
                req_params = {'limit': 250, 'page_info': page_info} if page_info else params
                resp = http_requests.get(base_url, headers=headers, params=req_params, timeout=30)
                if not resp.ok:
                    return Response({'error': f'Shopify API error: {resp.status_code}'}, status=resp.status_code)
                data = resp.json()
                all_products.extend(data.get('products', []))
                link_header = resp.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    import re
                    match = re.search(r'page_info=([^&>]+)[^>]*>;\s*rel="next"', link_header)
                    page_info = match.group(1) if match else None
                else:
                    break
                if not page_info:
                    break
        except Exception as e:
            logger.exception('ShopifyCacheSyncView: failed to fetch products')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        now_ts = timezone.now()
        all_results = []
        for p in all_products:
            variant = p.get('variants', [{}])[0]
            image_src = p.get('image', {}).get('src', '') if p.get('image') else ''
            all_results.append({
                'id': p.get('id'),
                'name': p.get('title', ''),
                'sku': variant.get('sku', ''),
                'category': p.get('product_type', '') or p.get('vendor', ''),
                'price': variant.get('price', '0'),
                'stock': variant.get('inventory_quantity', 0),
                'status': p.get('status', '').capitalize(),
                'shopifyId': str(p.get('id', '')),
                'handle': p.get('handle', ''),
                'image': image_src,
                'vendor': p.get('vendor', ''),
                'tags': p.get('tags', ''),
                'createdAt': p.get('created_at', ''),
                'updatedAt': p.get('updated_at', ''),
                'variantsCount': len(p.get('variants', [])),
            })

        saved = 0
        with transaction.atomic():
            for row in all_results:
                sid = row.get('id')
                if sid:
                    _SPC.objects.update_or_create(
                        organization_id=org_id,
                        shopify_id=int(sid),
                        defaults={'data': row, 'synced_at': now_ts},
                    )
                    saved += 1

        # Also sync collections to ShopifyCollectionCache DB
        collections_saved = 0
        try:
            from .models import ShopifyCollectionCache as _SCC
            all_collections = []
            for col_type in ['custom_collections', 'smart_collections']:
                col_url = f"https://{clean_domain}/admin/api/{api_version}/{col_type}.json"
                col_resp = http_requests.get(col_url, headers=headers, params={'limit': 250}, timeout=30)
                if col_resp.ok:
                    for c in col_resp.json().get(col_type, []):
                        product_count = _shopify_collection_product_count(
                            clean_domain, api_version, c['id'], headers, fallback_headers
                        )
                        all_collections.append({
                            'id':           c.get('id'),
                            'name':         c.get('title', ''),
                            'shopifyId':    str(c.get('id', '')),
                            'handle':       c.get('handle', ''),
                            'type':         'smart' if col_type == 'smart_collections' else 'custom',
                            'productCount': product_count,
                            'status':       'Active' if c.get('published_at') else 'Draft',
                            'image':        c.get('image', {}).get('src', '') if c.get('image') else '',
                            'updatedAt':    c.get('updated_at', ''),
                            'sortOrder':    c.get('sort_order', ''),
                        })
            with transaction.atomic():
                for row in all_collections:
                    sid = row.get('id')
                    if sid:
                        _SCC.objects.update_or_create(
                            organization_id=org_id,
                            shopify_id=int(sid),
                            defaults={'data': row, 'synced_at': now_ts},
                        )
                        collections_saved += 1
        except Exception:
            logger.exception('ShopifyCacheSyncView: failed to sync collections to DB')

        # Bust in-memory cache so next GET picks up fresh DB data
        cache.delete(f'shopify_products_{org_id}')
        cache.delete(f'shopify_categories_{org_id}')

        logger.info('Shopify sync to DB: %d products, %d collections saved for org %s', saved, collections_saved, org_id)
        return Response({
            'saved': saved,
            'collections_saved': collections_saved,
            'synced_at': now_ts.isoformat(),
            'message': f'Synced {saved} products and {collections_saved} collections to local DB.',
        })


# ---------------------------------------------------------------------------
# /api/inventory/production-software/sync/   POST
# Sync inventory data from the external production software API into local DB.
# GET  → returns current status (local row count + external API reachability)
# POST → triggers a sync from the external API
# ---------------------------------------------------------------------------
class ProductSheetSyncView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return local inventory count + whether external API is reachable."""
        import requests as http_requests

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        local_count = 0
        try:
            table = InventoryTable.objects.filter(
                organization_id=org_id, table_key='product_inventory'
            ).first()
            if table:
                local_count = InventoryItem.objects.filter(table=table).count()
        except Exception:
            pass

        api_url, api_key = _get_production_software_creds(org_id)
        api_status = 'not_configured'
        if api_url and api_key:
            try:
                r = http_requests.get(api_url, headers={'X-API-Key': api_key}, timeout=10)
                api_status = 'online' if r.ok else f'error_{r.status_code}'
            except Exception as e:
                api_status = f'unreachable: {str(e)[:80]}'

        return Response({
            'local_inventory_count': local_count,
            'external_api_status': api_status,
            'external_api_url': api_url or '(not set)',
        })

    def post(self, request):
        """Pull all inventory rows from external API and save to local DB."""
        import requests as http_requests

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Pre-check: ping the API before attempting sync so we give a clear error
        api_url, api_key = _get_production_software_creds(org_id)

        if not api_url or not api_key:
            return Response(
                {'error': 'Production software API URL / API key not configured. Please set them in Settings.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            ping = http_requests.get(api_url, headers={'X-API-Key': api_key}, timeout=15)
            if ping.status_code == 404:
                render_routing = ping.headers.get('x-render-routing', '')
                if render_routing == 'no-server':
                    return Response(
                        {'error': 'External API returned HTTP 404 (Render: no-server). '
                                  'The product-sheet-backend service is not deployed or has been stopped on Render. '
                                  'Go to render.com → your service → Deploy to restart it.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                return Response(
                    {'error': f'External API returned HTTP 404. Check that PRODUCTION_SOFTWARE_API_URL is correct: {api_url}'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if not ping.ok:
                return Response(
                    {'error': f'External API returned HTTP {ping.status_code}'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        except Exception as exc:
            return Response(
                {'error': f'Cannot reach external API: {exc}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        saved, error = _fetch_and_save_production_inventory(org_id)
        if error:
            return Response({'error': error, 'saved': 0}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'saved': saved, 'message': f'Synced {saved} inventory rows from production software.'})


# ─────────────────────────────────────────────────────────────────────────────
# VENDOR MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class VendorListCreateView(APIView):
    """GET /api/inventory/vendors/  – list all vendors for the org.
       POST /api/inventory/vendors/ – create a new vendor."""

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        vendors = Vendor.objects.filter(organization_id=org_id)
        data = [{
            'id': v.id,
            'name': v.name,
            'contact_person': v.contact_person,
            'email': v.email,
            'phone': v.phone,
            'address': v.address,
            'gst_number': v.gst_number,
            'status': v.status,
            'notes': v.notes,
            'created_at': v.created_at.isoformat(),
        } for v in vendors]
        return Response({'results': data, 'total': len(data)})

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        d = request.data
        vendor = Vendor.objects.create(
            organization_id=org_id,
            name=d.get('name', '').strip(),
            contact_person=d.get('contact_person', '').strip(),
            email=d.get('email', '').strip(),
            phone=d.get('phone', '').strip(),
            address=d.get('address', '').strip(),
            gst_number=d.get('gst_number', '').strip(),
            status=d.get('status', 'active'),
            notes=d.get('notes', '').strip(),
        )
        return Response({'id': vendor.id, 'name': vendor.name}, status=status.HTTP_201_CREATED)


class VendorDetailView(APIView):
    """GET/PATCH/DELETE /api/inventory/vendors/<id>/"""

    def _get_vendor(self, request, vendor_id):
        org_id = _get_org_id(request)
        if not org_id:
            return None, Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        vendor = get_object_or_404(Vendor, pk=vendor_id, organization_id=org_id)
        return vendor, None

    def get(self, request, vendor_id):
        vendor, err = self._get_vendor(request, vendor_id)
        if err:
            return err
        return Response({
            'id': vendor.id,
            'name': vendor.name,
            'contact_person': vendor.contact_person,
            'email': vendor.email,
            'phone': vendor.phone,
            'address': vendor.address,
            'gst_number': vendor.gst_number,
            'status': vendor.status,
            'notes': vendor.notes,
            'created_at': vendor.created_at.isoformat(),
        })

    def patch(self, request, vendor_id):
        vendor, err = self._get_vendor(request, vendor_id)
        if err:
            return err
        d = request.data
        for field in ['name', 'contact_person', 'email', 'phone', 'address', 'gst_number', 'status', 'notes']:
            if field in d:
                setattr(vendor, field, d[field])
        vendor.save()
        return Response({'id': vendor.id, 'name': vendor.name})

    def delete(self, request, vendor_id):
        vendor, err = self._get_vendor(request, vendor_id)
        if err:
            return err
        vendor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────────────────────────────
# PURCHASE ORDER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def _po_to_dict(po):
    return {
        'id': po.id,
        'po_number': po.po_number,
        'vendor_id': po.vendor_id,
        'vendor_name': po.vendor.name,
        'status': po.status,
        'products': po.products,
        'total_amount': str(po.total_amount),
        'expected_delivery': po.expected_delivery.isoformat() if po.expected_delivery else None,
        'notes': po.notes,
        'received_qty': po.received_qty,
        'damaged_qty': po.damaged_qty,
        'qc_status': po.qc_status,
        'received_date': po.received_date.isoformat() if po.received_date else None,
        'stock_updated': po.stock_updated,
        'created_at': po.created_at.isoformat(),
        'updated_at': po.updated_at.isoformat(),
    }


class PurchaseOrderListCreateView(APIView):
    """GET /api/inventory/purchase-orders/   – list POs.
       POST /api/inventory/purchase-orders/  – create a PO."""

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        vendor_id = request.query_params.get('vendor_id')
        status_filter = request.query_params.get('status')
        qs = PurchaseOrder.objects.filter(organization_id=org_id).select_related('vendor')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        if status_filter and status_filter != 'all':
            qs = qs.filter(status=status_filter)
        return Response({'results': [_po_to_dict(po) for po in qs], 'total': qs.count()})

    def post(self, request):
        import datetime
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        d = request.data
        vendor_id = d.get('vendor_id')
        if not vendor_id:
            return Response({'error': 'vendor_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        vendor = get_object_or_404(Vendor, pk=vendor_id, organization_id=org_id)

        # Generate PO number: PO-YYYYMMDD-XXXXX
        today = timezone.now().strftime('%Y%m%d')
        last_po = PurchaseOrder.objects.filter(
            organization_id=org_id,
            po_number__startswith=f'PO-{today}'
        ).order_by('-po_number').first()
        seq = 1
        if last_po:
            try:
                seq = int(last_po.po_number.split('-')[-1]) + 1
            except Exception:
                seq = PurchaseOrder.objects.filter(organization_id=org_id).count() + 1
        po_number = f'PO-{today}-{seq:04d}'

        expected = None
        if d.get('expected_delivery'):
            try:
                expected = datetime.date.fromisoformat(d['expected_delivery'])
            except Exception:
                pass

        po = PurchaseOrder.objects.create(
            organization_id=org_id,
            po_number=po_number,
            vendor=vendor,
            status='order_placed',
            products=d.get('products', []),
            total_amount=d.get('total_amount', 0),
            expected_delivery=expected,
            notes=d.get('notes', ''),
        )
        return Response(_po_to_dict(po), status=status.HTTP_201_CREATED)


class PurchaseOrderDetailView(APIView):
    """GET/PATCH /api/inventory/purchase-orders/<id>/
       PATCH with status='received' auto-updates inventory stock."""

    def _get_po(self, request, po_id):
        org_id = _get_org_id(request)
        if not org_id:
            return None, Response({'error': 'Organisation not found.'}, status=status.HTTP_403_FORBIDDEN)
        po = get_object_or_404(PurchaseOrder, pk=po_id, organization_id=org_id)
        return po, None

    def get(self, request, po_id):
        po, err = self._get_po(request, po_id)
        if err:
            return err
        return Response(_po_to_dict(po))

    def patch(self, request, po_id):
        import datetime
        po, err = self._get_po(request, po_id)
        if err:
            return err
        d = request.data
        prev_status = po.status

        # Update allowed fields
        for field in ['notes', 'total_amount', 'qc_status']:
            if field in d:
                setattr(po, field, d[field])

        if 'expected_delivery' in d and d['expected_delivery']:
            try:
                po.expected_delivery = datetime.date.fromisoformat(d['expected_delivery'])
            except Exception:
                pass

        if 'status' in d:
            po.status = d['status']

        if 'received_qty' in d:
            po.received_qty = d['received_qty']
        if 'damaged_qty' in d:
            po.damaged_qty = d['damaged_qty']
        if 'received_date' in d and d['received_date']:
            try:
                po.received_date = datetime.date.fromisoformat(d['received_date'])
            except Exception:
                pass

        # Auto-update inventory when status changes to 'received'
        if po.status == 'received' and prev_status != 'received' and not po.stock_updated:
            _apply_grn_stock_update(po)
            po.stock_updated = True
            if not po.received_date:
                po.received_date = timezone.now().date()

        po.save()
        return Response(_po_to_dict(po))


def _apply_grn_stock_update(po):
    """
    When a PO is marked as 'received', increment actualQuantity in the
    local InventoryItem table for each product in the PO.
    Uses received_qty if present, otherwise falls back to ordered qty.
    """
    org_id = po.organization_id
    try:
        table = InventoryTable.objects.filter(
            organization_id=org_id,
            table_key='product_inventory',
        ).first()
        if not table:
            return

        for item_info in po.products:
            shopify_id = str(item_info.get('shopify_id', ''))
            sku = str(item_info.get('sku') or item_info.get('finalSku') or '').strip()
            ordered_qty = int(item_info.get('qty', 0))
            received = int((po.received_qty or {}).get(shopify_id, ordered_qty))
            damaged = int((po.damaged_qty or {}).get(shopify_id, 0))
            net_qty = max(0, received - damaged)

            if not net_qty:
                continue

            # Try to find by final_sku or sku
            matched = None
            for inv_item in InventoryItem.objects.filter(table=table):
                d = inv_item.data or {}
                item_sku = str(d.get('final_sku') or d.get('sku') or '').strip()
                if item_sku and item_sku.lower() == sku.lower():
                    matched = inv_item
                    break

            if matched:
                current = int(matched.data.get('actual_quantity') or 0)
                matched.data = {**matched.data, 'actual_quantity': current + net_qty}
                matched.save(update_fields=['data', 'updated_at'])
            else:
                # Create a new inventory item record
                InventoryItem.objects.create(
                    table=table,
                    data={
                        'final_sku': sku,
                        'actual_quantity': net_qty,
                        'source': 'grn',
                        'po_number': po.po_number,
                    }
                )
        logger.info('GRN stock update applied for PO %s', po.po_number)
    except Exception:
        logger.exception('Failed to apply GRN stock update for PO %s', po.po_number)
