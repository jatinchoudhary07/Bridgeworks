"""
Management command: sync_shopify_cache
=======================================
Fetches all Shopify products and collections for every organisation that has
Shopify credentials configured and stores them in the Django database
(ShopifyProductCache / ShopifyCollectionCache).

Usage
-----
# Sync all organisations
python manage.py sync_shopify_cache

# Sync a single organisation
python manage.py sync_shopify_cache --org-id <org_id>

# Force re-sync even if cache is fresh
python manage.py sync_shopify_cache --force

Schedule this with a cron job or Celery beat task (e.g. every 30 minutes)
to keep the cache warm without blocking real-time requests.
"""

import logging
import re
import base64
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync Shopify products and collections into the Django DB cache."

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=str,
            default=None,
            help='Sync only this organisation ID (default: all orgs).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Force re-sync even if the cache is already fresh.',
        )
        parser.add_argument(
            '--max-age',
            type=int,
            default=30,
            help='Consider cache stale if older than this many minutes (default: 30).',
        )

    def handle(self, *args, **options):
        from core.models import ShopCredentials

        org_id_filter = options['org_id']
        force         = options['force']
        max_age_mins  = options['max_age']

        qs = ShopCredentials.objects.all()
        if org_id_filter:
            qs = qs.filter(organization_id=org_id_filter)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No Shopify credentials found."))
            return

        for creds in qs:
            org_id = creds.organization_id
            self.stdout.write(f"[{org_id}] Starting sync …")
            try:
                synced_products, synced_collections = _sync_org(
                    creds, force=force, max_age_mins=max_age_mins
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{org_id}] Done — {synced_products} products, "
                        f"{synced_collections} collections cached."
                    )
                )
            except Exception as exc:
                logger.exception(f"[{org_id}] Sync failed")
                self.stdout.write(self.style.ERROR(f"[{org_id}] FAILED: {exc}"))


# ---------------------------------------------------------------------------
# Core sync logic (also callable from views for on-demand refresh)
# ---------------------------------------------------------------------------

def _sync_org(creds, *, force=False, max_age_mins=30):
    """
    Sync products and collections for one organisation.
    Returns (product_count, collection_count).
    """
    import requests as http_requests
    from inventory.models import ShopifyProductCache, ShopifyCollectionCache
    from django.utils import timezone
    from datetime import timedelta

    org_id = creds.organization_id

    # ── Resolve shop domain ─────────────────────────────────────────────────
    shop_url = (
        creds.get_shopify_shop_url()
        or getattr(creds, 'myshopify_domain', None)
        or ''
    )
    if not shop_url:
        raise ValueError(f"Shopify shop URL not configured for org {org_id}")

    clean_domain = shop_url.replace('https://', '').replace('http://', '').strip('/')
    api_version  = getattr(creds, 'shopify_api_version', None) or '2024-07'
    headers      = _build_auth_headers(creds)
    stale_before = timezone.now() - timedelta(minutes=max_age_mins)

    # ── Products ────────────────────────────────────────────────────────────
    if force or not ShopifyProductCache.objects.filter(
        organization_id=org_id, synced_at__gte=stale_before
    ).exists():
        base_url     = f"https://{clean_domain}/admin/api/{api_version}/products.json"
        raw_products = _paginate_all(base_url, headers, http_requests)

        now = timezone.now()
        product_rows = []
        for p in raw_products:
            variant   = p.get('variants', [{}])[0]
            image_src = p.get('image', {}).get('src', '') if p.get('image') else ''
            product_rows.append(ShopifyProductCache(
                organization_id=org_id,
                shopify_id=p['id'],
                synced_at=now,
                data={
                    'id':           p.get('id'),
                    'name':         p.get('title', ''),
                    'sku':          variant.get('sku', ''),
                    'category':     p.get('product_type', '') or p.get('vendor', ''),
                    'price':        variant.get('price', '0'),
                    'stock':        variant.get('inventory_quantity', 0),
                    'status':       p.get('status', '').capitalize(),
                    'shopifyId':    str(p.get('id', '')),
                    'handle':       p.get('handle', ''),
                    'image':        image_src,
                    'vendor':       p.get('vendor', ''),
                    'tags':         p.get('tags', ''),
                    'createdAt':    p.get('created_at', ''),
                    'updatedAt':    p.get('updated_at', ''),
                    'variantsCount': len(p.get('variants', [])),
                    'variants':     [
                        {
                            'id':    v.get('id'),
                            'sku':   v.get('sku', ''),
                            'price': v.get('price', '0'),
                            'stock': v.get('inventory_quantity', 0),
                            'title': v.get('title', ''),
                            'inventory_item_id': v.get('inventory_item_id'),
                        }
                        for v in p.get('variants', [])
                    ],
                },
            ))

        # Bulk upsert via update_or_create batches
        _bulk_upsert_products(org_id, product_rows)
        product_count = len(product_rows)
    else:
        product_count = ShopifyProductCache.objects.filter(organization_id=org_id).count()

    # ── Collections ─────────────────────────────────────────────────────────
    if force or not ShopifyCollectionCache.objects.filter(
        organization_id=org_id, synced_at__gte=stale_before
    ).exists():
        now = timezone.now()
        collection_rows = []
        for col_type in ['custom_collections', 'smart_collections']:
            base_url = f"https://{clean_domain}/admin/api/{api_version}/{col_type}.json"
            raw = _paginate_all(base_url, headers, http_requests)
            for c in raw:
                product_count_val = _collection_product_count(
                    clean_domain, api_version, c['id'], headers, http_requests
                )
                collection_rows.append(ShopifyCollectionCache(
                    organization_id=org_id,
                    shopify_id=c['id'],
                    synced_at=now,
                    data={
                        'id':           c.get('id'),
                        'name':         c.get('title', ''),
                        'shopifyId':    str(c.get('id', '')),
                        'handle':       c.get('handle', ''),
                        'type':         'smart' if col_type == 'smart_collections' else 'custom',
                        'productCount': product_count_val,
                        'status':       'Active' if c.get('published_at') else 'Draft',
                        'image':        c.get('image', {}).get('src', '') if c.get('image') else '',
                        'updatedAt':    c.get('updated_at', ''),
                        'sortOrder':    c.get('sort_order', ''),
                    },
                ))

        _bulk_upsert_collections(org_id, collection_rows)
        collection_count = len(collection_rows)
    else:
        collection_count = ShopifyCollectionCache.objects.filter(organization_id=org_id).count()

    return product_count, collection_count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_auth_headers(creds):
    from core.models import decrypt_data
    if getattr(creds, 'auth_method', None) == 'oauth' and getattr(creds, 'shopify_access_token_encrypted', None):
        token = decrypt_data(creds.shopify_access_token_encrypted)
        return {'X-Shopify-Access-Token': token, 'Content-Type': 'application/json'}
    import os
    api_key  = creds.get_shopify_api_key() if hasattr(creds, 'get_shopify_api_key') else os.getenv('SHOPIFY_API_KEY', '')
    password = creds.get_shopify_password() if hasattr(creds, 'get_shopify_password') else os.getenv('SHOPIFY_API_PASSWORD', '')
    encoded  = base64.b64encode(f"{api_key}:{password}".encode()).decode()
    return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}


def _paginate_all(base_url, headers, http_requests, extra_params=None):
    """Cursor-based pagination for Shopify REST endpoints."""
    import requests as _requests
    all_items  = []
    params     = {'limit': 250, **(extra_params or {})}
    page_info  = None
    while True:
        req_params = {'limit': 250, 'page_info': page_info} if page_info else params
        try:
            resp = http_requests.get(base_url, headers=headers, params=req_params, timeout=30)
        except _requests.exceptions.ConnectionError as exc:
            domain = base_url.split('/')[2] if '/' in base_url else base_url
            raise Exception(
                f"Cannot reach Shopify ({domain}): DNS resolution or network failure. "
                f"Check that the server has outbound internet access. Details: {exc}"
            ) from exc
        except _requests.exceptions.Timeout:
            raise Exception(f"Shopify API timed out after 30s: {base_url}")
        if not resp.ok:
            raise Exception(f"Shopify API {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
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


def _collection_product_count(clean_domain, api_version, collection_id, headers, http_requests):
    """
    Count collection membership from /collections/{id}/products.json. This is
    the endpoint the UI already uses for collection filters and avoids cached
    zeroes from unsupported nested count routes.
    """
    base_url = f"https://{clean_domain}/admin/api/{api_version}/collections/{collection_id}/products.json"
    return len(_paginate_all(base_url, headers, http_requests, extra_params={'fields': 'id'}))


def _bulk_upsert_products(org_id, rows):
    """Upsert a list of ShopifyProductCache objects."""
    from inventory.models import ShopifyProductCache
    from django.db import transaction

    if not rows:
        return

    existing_ids = set(
        ShopifyProductCache.objects.filter(organization_id=org_id)
        .values_list('shopify_id', flat=True)
    )

    to_create = [r for r in rows if r.shopify_id not in existing_ids]
    to_update = [r for r in rows if r.shopify_id in existing_ids]

    with transaction.atomic():
        if to_create:
            ShopifyProductCache.objects.bulk_create(to_create, batch_size=200)
        for row in to_update:
            ShopifyProductCache.objects.filter(
                organization_id=org_id, shopify_id=row.shopify_id
            ).update(data=row.data, synced_at=row.synced_at)


def _bulk_upsert_collections(org_id, rows):
    """Upsert a list of ShopifyCollectionCache objects."""
    from inventory.models import ShopifyCollectionCache
    from django.db import transaction

    if not rows:
        return

    existing_ids = set(
        ShopifyCollectionCache.objects.filter(organization_id=org_id)
        .values_list('shopify_id', flat=True)
    )

    to_create = [r for r in rows if r.shopify_id not in existing_ids]
    to_update = [r for r in rows if r.shopify_id in existing_ids]

    with transaction.atomic():
        if to_create:
            ShopifyCollectionCache.objects.bulk_create(to_create, batch_size=200)
        for row in to_update:
            ShopifyCollectionCache.objects.filter(
                organization_id=org_id, shopify_id=row.shopify_id
            ).update(data=row.data, synced_at=row.synced_at)
