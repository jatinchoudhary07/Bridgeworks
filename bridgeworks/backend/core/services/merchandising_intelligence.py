"""
Merchandising Intelligence Service
====================================
Product-level analysis engine for the Marketing AURA AI.
Provides deep product performance metrics, inventory-performance correlation,
and size-level sales data across two comparison periods.

This module is consumed by `ai_marketing_agent.py` and feeds structured
product data into the Gemini payload for intelligent segmentation.
"""
import logging
import json
from decimal import Decimal
from datetime import timedelta, date
from collections import defaultdict
from django.db.models import Sum, Count, F, Q, Avg
from django.conf import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 1. PRODUCT PERFORMANCE — Order-based metrics per product for a period
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_product_performance(org, start_date, end_date):
    """
    Per-product revenue, orders, units sold, and top variant/size breakdown.
    Uses LineItem joined with Order for accurate Shopify-side metrics.
    """
    try:
        from core.models import Order, LineItem

        # Base filter: confirmed/paid orders in the period
        base_filter = Q(
            order__org_id=org.organization_id,
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date,
        ) & ~Q(order__financial_status__in=['voided', 'refunded'])

        products = (
            LineItem.objects.filter(base_filter)
            .values('product_id', 'title')
            .annotate(
                revenue=Sum(F('price') * F('quantity')),
                orders=Count('order', distinct=True),
                units_sold=Sum('quantity'),
            )
            .order_by('-revenue')[:50]
        )

        result = []
        total_revenue = 0
        total_orders = 0

        for p in products:
            rev = float(p['revenue'] or 0)
            total_revenue += rev
            total_orders += p['orders']

            # Get variant/size breakdown for this product
            variants = (
                LineItem.objects.filter(
                    base_filter,
                    product_id=p['product_id'],
                )
                .values('sku', 'name')
                .annotate(
                    qty=Sum('quantity'),
                    rev=Sum(F('price') * F('quantity'))
                )
                .order_by('-qty')[:10]
            )

            result.append({
                'product_id': p['product_id'],
                'title': p['title'],
                'revenue': rev,
                'orders': p['orders'],
                'units_sold': p['units_sold'],
                'top_sizes': [
                    {
                        'name': v['name'] or 'Default',
                        'sku': v['sku'] or '',
                        'qty': v['qty'],
                        'revenue': float(v['rev'] or 0),
                    }
                    for v in variants
                ],
            })

        return {
            'products': result,
            'total_revenue': total_revenue,
            'total_orders': total_orders,
        }

    except Exception as e:
        logger.error(f"Failed to fetch product performance: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 2. SHOPIFY PRODUCT SESSIONS — Via ShopifyQL (API 2024-04+)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_product_sessions_shopify(org, start_date, end_date):
    """
    Fetch product-level online store sessions and conversion rates
    via Shopify's ShopifyQL endpoint.

    Gracefully returns None if the store plan doesn't support ShopifyQL
    or the API call fails, allowing the AI to fall back to order-based metrics.
    """
    try:
        from core.shopify_utils import get_shopify_session
        import shopify

        session = get_shopify_session(None, org_id=org.organization_id)
        shopify.ShopifyResource.activate_session(session)

        # ShopifyQL query for product-level sessions
        shopifyql = (
            f"FROM products "
            f"SHOW product_title, sessions, orders, conversion_rate "
            f"SINCE {start_date.strftime('%Y-%m-%d')} "
            f"UNTIL {end_date.strftime('%Y-%m-%d')} "
            f"ORDER BY sessions DESC "
            f"LIMIT 50"
        )

        query = """
        {
          shopifyqlQuery(query: "%s") {
            __typename
            ... on TableResponse {
              tableData {
                rowData
                columns {
                  name
                  dataType
                }
              }
            }
            ... on PolarisVizResponse {
              data {
                key
                data {
                  key
                  value
                }
              }
            }
          }
        }
        """ % shopifyql.replace('"', '\\"')

        result = shopify.GraphQL().execute(query)
        shopify.ShopifyResource.clear_session()

        data = json.loads(result)
        
        if 'errors' in data:
            logger.info("ShopifyQL not available or returned errors. Falling back to basic metrics.")
            return None
            
        data_block = data.get('data') or {}
        ql_result = data_block.get('shopifyqlQuery') or {}

        typename = ql_result.get('__typename')

        # Parse TableResponse format
        if typename == 'TableResponse':
            table = ql_result.get('tableData', {})
            columns = [c['name'] for c in table.get('columns', [])]
            rows = table.get('rowData', [])

            products_sessions = []
            for row in rows:
                entry = {}
                for i, col in enumerate(columns):
                    if i < len(row):
                        entry[col] = row[i]
                products_sessions.append({
                    'product_title': entry.get('product_title', ''),
                    'sessions': int(float(entry.get('sessions', 0) or 0)),
                    'orders': int(float(entry.get('orders', 0) or 0)),
                    'conversion_rate': float(entry.get('conversion_rate', 0) or 0),
                })
            return products_sessions

        if typename:
            logger.warning(f"ShopifyQL returned unexpected type: {typename}")
        return None

    except Exception as e:
        logger.warning(f"ShopifyQL product sessions unavailable: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 3. INVENTORY DATA — Shopify GraphQL for current stock levels
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_inventory_data(org):
    """
    Fetch product-level inventory and size-wise availability from the local
    ShopifyProductCache (kept fresh via webhooks + periodic sync).
    Falls back to triggering an initial sync if no cached data exists.
    """
    try:
        from inventory.models import ShopifyProductCache

        cached_products = list(
            ShopifyProductCache.objects.filter(
                organization_id=org.organization_id
            ).values_list('data', flat=True)
        )

        # Auto-sync if the cache is completely empty (first run)
        if not cached_products:
            logger.info("No cached Shopify products found — triggering initial sync...")
            try:
                from core.models import ShopCredentials
                from inventory.management.commands.sync_shopify_cache import _sync_org
                creds = ShopCredentials.objects.get(organization_id=org.organization_id)
                _sync_org(creds, force=True)
                cached_products = list(
                    ShopifyProductCache.objects.filter(
                        organization_id=org.organization_id
                    ).values_list('data', flat=True)
                )
            except Exception as sync_err:
                logger.warning(f"Initial Shopify sync failed: {sync_err}")
                return None

        if not cached_products:
            return None

        products = []
        for data in cached_products:
            if not isinstance(data, dict):
                continue

            variants = []
            total_stock = 0
            oos_sizes = []
            low_stock_sizes = []
            key_sizes_status = {}

            for v in data.get('variants', []):
                qty = v.get('stock', 0) or 0
                total_stock += qty
                size_name = v.get('title', 'Default')

                if qty <= 0:
                    oos_sizes.append(size_name)
                elif qty < 5:
                    low_stock_sizes.append(size_name)

                # Track key sizes (S, M, L, XL, XXL)
                for key_size in ['S', 'M', 'L', 'XL', 'XXL', 'Free Size']:
                    if key_size.lower() in size_name.lower():
                        key_sizes_status[key_size] = qty

                variants.append({
                    'size': size_name,
                    'sku': v.get('sku', ''),
                    'stock': qty,
                    'price': v.get('price', '0'),
                })

            products.append({
                'title': data.get('name', ''),
                'handle': data.get('handle', ''),
                'status': data.get('status', 'Active'),
                'total_stock': total_stock,
                'oos_sizes': oos_sizes,
                'low_stock_sizes': low_stock_sizes,
                'key_sizes_status': key_sizes_status,
                'variants': variants,
            })
        return products

    except Exception as e:
        logger.warning(f"Failed to fetch inventory data from cache: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 4. UNIFIED MERCHANDISING INTELLIGENCE — Cross-references everything
# ═══════════════════════════════════════════════════════════════════════════

def _cross_reference_products(current_perf, previous_perf, inventory, sessions_current, sessions_previous):
    """
    Cross-reference product performance, inventory, and sessions data
    to build a unified product intelligence map.
    """
    # Build lookup dicts by product title (normalized lowercase)
    inv_map = {}
    if inventory:
        for p in inventory:
            inv_map[p['title'].strip().lower()] = p

    sess_curr_map = {}
    if sessions_current:
        for s in sessions_current:
            sess_curr_map[s['product_title'].strip().lower()] = s

    sess_prev_map = {}
    if sessions_previous:
        for s in sessions_previous:
            sess_prev_map[s['product_title'].strip().lower()] = s

    prev_map = {}
    if previous_perf and previous_perf.get('products'):
        for p in previous_perf['products']:
            prev_map[p['title'].strip().lower()] = p

    unified = []
    seen_titles = set()

    # Start from current period products
    if current_perf and current_perf.get('products'):
        for p in current_perf['products']:
            key = p['title'].strip().lower()
            seen_titles.add(key)

            prev = prev_map.get(key, {})
            inv = inv_map.get(key, {})
            sess_c = sess_curr_map.get(key, {})
            sess_p = sess_prev_map.get(key, {})

            # Revenue change
            curr_rev = p.get('revenue', 0)
            prev_rev = prev.get('revenue', 0)
            rev_change_pct = round(((curr_rev - prev_rev) / prev_rev) * 100, 1) if prev_rev > 0 else None

            # Order change
            curr_orders = p.get('orders', 0)
            prev_orders = prev.get('orders', 0)
            order_change_pct = round(((curr_orders - prev_orders) / prev_orders) * 100, 1) if prev_orders > 0 else None

            # Session change
            curr_sessions = sess_c.get('sessions', 0)
            prev_sessions = sess_p.get('sessions', 0)
            session_change_pct = round(((curr_sessions - prev_sessions) / prev_sessions) * 100, 1) if prev_sessions > 0 else None

            # Conversion rate
            curr_cvr = sess_c.get('conversion_rate', 0)
            prev_cvr = sess_p.get('conversion_rate', 0)
            cvr_change_pct = round(((curr_cvr - prev_cvr) / prev_cvr) * 100, 1) if prev_cvr > 0 else None

            product_card = {
                'title': p['title'],
                'product_id': p.get('product_id'),
                # Current period
                'current': {
                    'revenue': curr_rev,
                    'orders': curr_orders,
                    'units_sold': p.get('units_sold', 0),
                    'sessions': curr_sessions,
                    'conversion_rate': curr_cvr,
                    'top_sizes': p.get('top_sizes', []),
                },
                # Previous period
                'previous': {
                    'revenue': prev_rev,
                    'orders': prev_orders,
                    'units_sold': prev.get('units_sold', 0),
                    'sessions': prev_sessions,
                    'conversion_rate': prev_cvr,
                    'top_sizes': prev.get('top_sizes', []),
                },
                # Trends
                'trends': {
                    'revenue_change_pct': rev_change_pct,
                    'order_change_pct': order_change_pct,
                    'session_change_pct': session_change_pct,
                    'cvr_change_pct': cvr_change_pct,
                },
                # Inventory
                'inventory': {
                    'total_stock': inv.get('total_stock', 'N/A'),
                    'oos_sizes': inv.get('oos_sizes', []),
                    'low_stock_sizes': inv.get('low_stock_sizes', []),
                    'key_sizes_status': inv.get('key_sizes_status', {}),
                    'variants': inv.get('variants', []),
                },
            }
            unified.append(product_card)

    # Add products that were in previous period but NOT in current (fully dropped off)
    if previous_perf and previous_perf.get('products'):
        for p in previous_perf['products']:
            key = p['title'].strip().lower()
            if key not in seen_titles:
                inv = inv_map.get(key, {})
                unified.append({
                    'title': p['title'],
                    'product_id': p.get('product_id'),
                    'current': {
                        'revenue': 0, 'orders': 0, 'units_sold': 0,
                        'sessions': 0, 'conversion_rate': 0, 'top_sizes': [],
                    },
                    'previous': {
                        'revenue': p.get('revenue', 0),
                        'orders': p.get('orders', 0),
                        'units_sold': p.get('units_sold', 0),
                        'sessions': sess_prev_map.get(key, {}).get('sessions', 0),
                        'conversion_rate': sess_prev_map.get(key, {}).get('conversion_rate', 0),
                        'top_sizes': p.get('top_sizes', []),
                    },
                    'trends': {
                        'revenue_change_pct': -100.0,
                        'order_change_pct': -100.0,
                        'session_change_pct': -100.0,
                        'cvr_change_pct': -100.0,
                    },
                    'inventory': {
                        'total_stock': inv.get('total_stock', 'N/A'),
                        'oos_sizes': inv.get('oos_sizes', []),
                        'low_stock_sizes': inv.get('low_stock_sizes', []),
                        'key_sizes_status': inv.get('key_sizes_status', {}),
                        'variants': inv.get('variants', []),
                    },
                    '_dropped_off': True,
                })

    return unified


def fetch_merchandising_intelligence(org, start_date, end_date):
    """
    PUBLIC API: Unified product intelligence with dual-period comparison.
    Auto-calculates the previous period based on the given date range.

    Returns a comprehensive payload that the AI can use to segment products
    into Winners, Declining Winners, Low Inventory Alerts, and Emerging Winners.
    """
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from django.db import close_old_connections

        # Calculate previous period (same duration, immediately before)
        period_days = (end_date - start_date).days
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days)

        # Parallel fetch all data sources
        results = {}

        def _safe_fetch(name, fn):
            try:
                close_old_connections()
                return name, fn()
            except Exception as e:
                logger.warning(f"Merchandising fetch '{name}' failed: {e}")
                return name, None

        tasks = {
            'current_perf': lambda: _fetch_product_performance(org, start_date, end_date),
            'previous_perf': lambda: _fetch_product_performance(org, prev_start, prev_end),
            'inventory': lambda: _fetch_inventory_data(org),
            'sessions_current': lambda: _fetch_product_sessions_shopify(org, start_date, end_date),
            'sessions_previous': lambda: _fetch_product_sessions_shopify(org, prev_start, prev_end),
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_safe_fetch, n, fn): n for n, fn in tasks.items()}
            for future in as_completed(futures):
                name, result = future.result()
                results[name] = result

        # Cross-reference all data
        unified_products = _cross_reference_products(
            current_perf=results.get('current_perf'),
            previous_perf=results.get('previous_perf'),
            inventory=results.get('inventory'),
            sessions_current=results.get('sessions_current'),
            sessions_previous=results.get('sessions_previous'),
        )

        # Compute store-level averages for the AI to use as benchmarks
        curr = results.get('current_perf') or {}
        prev = results.get('previous_perf') or {}

        curr_total_rev = curr.get('total_revenue', 0)
        prev_total_rev = prev.get('total_revenue', 0)

        # Store average CVR from sessions data
        all_cvrs = []
        if results.get('sessions_current'):
            all_cvrs = [s['conversion_rate'] for s in results['sessions_current'] if s.get('conversion_rate', 0) > 0]
        store_avg_cvr = round(sum(all_cvrs) / len(all_cvrs), 2) if all_cvrs else 0

        return {
            'current_period': f"{start_date} to {end_date}",
            'previous_period': f"{prev_start} to {prev_end}",
            'period_days': period_days,
            'store_totals': {
                'current_revenue': curr_total_rev,
                'previous_revenue': prev_total_rev,
                'revenue_change_pct': round(((curr_total_rev - prev_total_rev) / prev_total_rev) * 100, 1) if prev_total_rev > 0 else None,
                'current_orders': curr.get('total_orders', 0),
                'previous_orders': prev.get('total_orders', 0),
                'store_avg_conversion_rate': store_avg_cvr,
            },
            'products': unified_products,
            'sessions_available': results.get('sessions_current') is not None,
            'product_count': len(unified_products),
        }

    except Exception as e:
        logger.error(f"Merchandising intelligence failed: {e}", exc_info=True)
        return None
