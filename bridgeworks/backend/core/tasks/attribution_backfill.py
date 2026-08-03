"""
Historical Attribution Backfill Engine
======================================
Fetches historical orders from Shopify REST API, extracts landing_site
UTMs/click IDs, classifies channels, and cross-references against
stored Meta/Google campaign data.

Uses django-q2 (async_task) for background execution.
Uses `requests` directly for explicit cursor pagination and rate control.

This module does NOT modify the Order model or any existing logic.
It only creates/updates OrderAttribution records.
"""
import time
import logging
import requests as http_requests
from datetime import datetime, date
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 1. Shopify API Fetcher (Cursor-Based Pagination)
# ─────────────────────────────────────────────────────────────────────

class ShopifyOrderFetcher:
    """
    Fetches historical orders from Shopify REST Admin API with:
    - Cursor-based pagination (Link header)
    - Rate limiting (0.5s sleep between pages)
    - Only fetches fields needed for attribution
    """

    # Only request the fields we actually need — minimizes payload and API cost
    FIELDS = 'id,landing_site,referring_site,created_at,order_number,note_attributes'
    PAGE_SIZE = 250  # Shopify max

    def __init__(self, shop_credentials):
        """
        Args:
            shop_credentials: ShopCredentials model instance
        """
        self.creds = shop_credentials
        self.api_version = shop_credentials.shopify_api_version or '2024-07'

        # Build base URL and auth header
        self._setup_auth()

    def _setup_auth(self):
        """Configure HTTP auth based on shop's auth_method."""
        from core.models import decrypt_data

        if self.creds.auth_method == 'oauth' and self.creds.shopify_access_token_encrypted:
            # OAuth: use access token as X-Shopify-Access-Token header
            token = decrypt_data(self.creds.shopify_access_token_encrypted)
            domain = self.creds.myshopify_domain
            self.base_url = f"https://{domain}/admin/api/{self.api_version}"
            self.headers = {
                'X-Shopify-Access-Token': token,
                'Content-Type': 'application/json',
            }
        else:
            # Legacy: use API key + password as Basic Auth
            api_key = decrypt_data(self.creds.shopify_api_key_encrypted)
            password = decrypt_data(self.creds.shopify_api_password_encrypted)
            shop_url = decrypt_data(self.creds.shopify_shop_url_encrypted)

            # Clean URL
            clean_url = shop_url.replace('https://', '').replace('http://', '').strip('/')
            self.base_url = f"https://{api_key}:{password}@{clean_url}/admin/api/{self.api_version}"
            self.headers = {'Content-Type': 'application/json'}

    def fetch_orders(self, start_date=None, end_date=None):
        """
        Generator that yields orders in pages, handling cursor pagination.

        Args:
            start_date: Optional date or ISO string (inclusive)
            end_date: Optional date or ISO string (inclusive, end of day)

        Yields:
            list of order dicts per page
        """
        params = {
            'limit': self.PAGE_SIZE,
            'fields': self.FIELDS,
            'status': 'any',  # Include cancelled, archived orders too
        }

        # Apply date filters
        if start_date:
            if isinstance(start_date, (date, datetime)):
                start_date = start_date.isoformat()
            params['created_at_min'] = f"{start_date}T00:00:00+05:30"

        if end_date:
            if isinstance(end_date, (date, datetime)):
                end_date = end_date.isoformat()
            params['created_at_max'] = f"{end_date}T23:59:59+05:30"

        url = f"{self.base_url}/orders.json"
        page_num = 0

        while url:
            page_num += 1
            try:
                response = http_requests.get(
                    url,
                    params=params if page_num == 1 else None,  # params only on first request
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 429:
                    # Rate limited — respect Retry-After header
                    retry_after = float(response.headers.get('Retry-After', '2.0'))
                    logger.warning(f"Rate limited by Shopify. Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue  # Retry same URL

                response.raise_for_status()
                data = response.json()
                orders = data.get('orders', [])

                if orders:
                    logger.info(f"Page {page_num}: fetched {len(orders)} orders")
                    yield orders

                # Cursor pagination: extract next page URL from Link header
                url = self._get_next_page_url(response)

                # Rate limiting: 0.5s between pages (Shopify allows 2 req/s)
                if url:
                    time.sleep(0.5)

            except http_requests.exceptions.HTTPError as e:
                logger.error(f"Shopify API HTTP error on page {page_num}: {e}")
                break
            except Exception as e:
                logger.error(f"Shopify API error on page {page_num}: {e}")
                break

    @staticmethod
    def _get_next_page_url(response):
        """
        Parse the Link header for cursor-based pagination.
        Shopify returns: Link: <url>; rel="next", <url>; rel="previous"
        """
        link_header = response.headers.get('Link', '')
        if not link_header:
            return None

        for part in link_header.split(','):
            part = part.strip()
            if 'rel="next"' in part:
                # Extract URL from angle brackets
                url = part.split(';')[0].strip().strip('<>')
                return url

        return None


# ─────────────────────────────────────────────────────────────────────
# 2. Campaign Matcher (Cross-reference UTMs to stored Meta/Google data)
# ─────────────────────────────────────────────────────────────────────

class CampaignMatcher:
    """
    Matches UTM campaign/content/term values against stored
    Meta and Google campaign data for the shop.
    
    Matching strategy (in priority order):
      1. Exact match on lowercase campaign name
      2. Substring match: UTM campaign name contains stored name (or vice versa)
      3. Direct ID match: utm_term often contains the Meta Ad ID directly
    
    Lazy-loads campaign names on first use and caches them
    for the duration of the backfill run.
    """

    def __init__(self, shop_credentials):
        self.shop = shop_credentials
        self._meta_campaigns = None
        self._meta_adsets = None
        self._meta_ads = None
        self._meta_ad_ids = None       # ad_id → ad_id (for direct ID matching)
        self._google_campaigns = None

    def _load_meta_data(self):
        """Load and cache Meta campaign hierarchy for this shop."""
        if self._meta_campaigns is not None:
            return

        from core.models import MetaCampaign, MetaAdSet, MetaAd

        # Build lookup dicts: lowercase name → id
        self._meta_campaigns = {}
        for c in MetaCampaign.objects.filter(credential__shop=self.shop):
            self._meta_campaigns[c.name.lower().strip()] = c.campaign_id

        self._meta_adsets = {}
        for a in MetaAdSet.objects.filter(credential__shop=self.shop):
            self._meta_adsets[a.name.lower().strip()] = a.adset_id

        self._meta_ads = {}
        self._meta_ad_ids = set()
        for ad in MetaAd.objects.filter(credential__shop=self.shop):
            self._meta_ads[ad.name.lower().strip()] = ad.ad_id
            self._meta_ad_ids.add(str(ad.ad_id).strip())

        logger.info(
            f"CampaignMatcher loaded: {len(self._meta_campaigns)} campaigns, "
            f"{len(self._meta_adsets)} adsets, {len(self._meta_ads)} ads"
        )

    def _load_google_data(self):
        """Load and cache Google campaign names for this shop."""
        if self._google_campaigns is not None:
            return

        from core.models import GoogleCampaignDailyMetric

        self._google_campaigns = set()
        for name in (GoogleCampaignDailyMetric.objects
                     .filter(credential__shop=self.shop)
                     .values_list('campaign_name', flat=True)
                     .distinct()):
            self._google_campaigns.add(name.lower().strip())

    def _fuzzy_match_campaign(self, campaign_name, lookup_dict):
        """
        Try to find a campaign match using substring matching.
        Returns the matched ID or empty string.
        
        Strategy:
          1. Exact match (already checked before calling this)
          2. UTM name contains a stored campaign name
          3. A stored campaign name contains the UTM name
        """
        # 2. UTM campaign contains a stored name
        for stored_name, stored_id in lookup_dict.items():
            if stored_name and len(stored_name) > 5 and stored_name in campaign_name:
                return stored_id
        
        # 3. Stored name contains the UTM campaign
        if len(campaign_name) > 5:
            for stored_name, stored_id in lookup_dict.items():
                if campaign_name in stored_name:
                    return stored_id
        
        return ''

    def match(self, utm_data, channel):
        """
        Attempt to match UTM parameters against stored campaign data.

        Returns:
            dict with matched_campaign_id, matched_adset_id,
                 matched_ad_id, matched_platform
        """
        result = {
            'matched_campaign_id': '',
            'matched_adset_id': '',
            'matched_ad_id': '',
            'matched_platform': '',
        }

        campaign_name = (utm_data.get('utm_campaign') or '').lower().strip()
        content = (utm_data.get('utm_content') or '').lower().strip()
        term = (utm_data.get('utm_term') or '').lower().strip()

        # Try Meta first if channel suggests it (or always as fallback)
        meta_channels = ('meta_paid', 'organic_social', 'unknown', 'whatsapp')
        if channel in meta_channels or not result['matched_platform']:
            self._load_meta_data()

            # 1. Direct Ad ID match via utm_term (utm_term often IS the ad ID)
            if term and term in self._meta_ad_ids:
                result['matched_ad_id'] = term
                result['matched_platform'] = 'meta'

            # 2. Campaign matching (exact then fuzzy)
            if campaign_name:
                if campaign_name in self._meta_campaigns:
                    result['matched_campaign_id'] = self._meta_campaigns[campaign_name]
                    result['matched_platform'] = 'meta'
                else:
                    # Fuzzy match
                    fuzzy_id = self._fuzzy_match_campaign(campaign_name, self._meta_campaigns)
                    if fuzzy_id:
                        result['matched_campaign_id'] = fuzzy_id
                        result['matched_platform'] = 'meta'

            # 3. Adset matching via utm_content
            if content:
                if content in self._meta_adsets:
                    result['matched_adset_id'] = self._meta_adsets[content]
                else:
                    fuzzy_adset = self._fuzzy_match_campaign(content, self._meta_adsets)
                    if fuzzy_adset:
                        result['matched_adset_id'] = fuzzy_adset

            # 4. Ad matching via utm_term (by name, not ID)
            if term and not result['matched_ad_id']:
                if term in self._meta_ads:
                    result['matched_ad_id'] = self._meta_ads[term]

            if result['matched_platform']:
                return result

        # Try Google if channel suggests it
        if channel in ('google_paid', 'organic_search', 'unknown'):
            self._load_google_data()

            if campaign_name:
                if campaign_name in self._google_campaigns:
                    result['matched_campaign_id'] = campaign_name
                    result['matched_platform'] = 'google'
                    return result

        # Final fallback: try Meta even if channel didn't suggest it
        if not result['matched_platform'] and campaign_name:
            self._load_meta_data()
            if campaign_name in self._meta_campaigns:
                result['matched_campaign_id'] = self._meta_campaigns[campaign_name]
                result['matched_platform'] = 'meta'
            else:
                fuzzy_id = self._fuzzy_match_campaign(campaign_name, self._meta_campaigns)
                if fuzzy_id:
                    result['matched_campaign_id'] = fuzzy_id
                    result['matched_platform'] = 'meta'

        return result


# ─────────────────────────────────────────────────────────────────────
# 3. Main Backfill Task (django-q2 entry point)
# ─────────────────────────────────────────────────────────────────────

def run_historical_attribution_backfill(shop_id, start_date=None, end_date=None, force=False):
    """
    Main backfill function — designed to be called via django-q2's async_task.

    For each historical order fetched from Shopify:
      1. Find the matching local Order by shopify_id
      2. Extract UTMs from landing_site
      3. Classify channel
      4. Cross-reference against Meta/Google campaigns
      5. update_or_create OrderAttribution

    Args:
        shop_id: ShopCredentials.id (int)
        start_date: Optional ISO date string or date object
        end_date: Optional ISO date string or date object
        force: If True, overwrite existing attributions. If False, skip them.

    Returns:
        dict with stats: total_fetched, matched_local, created, updated,
                         skipped, errors, duration_seconds
    """
    from core.models import ShopCredentials, Order, OrderAttribution
    from core.utils.url_parser import extract_and_classify

    start_time = time.time()

    stats = {
        'total_fetched': 0,
        'matched_local': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'no_landing_site': 0,
        'errors': 0,
        'duration_seconds': 0,
    }

    try:
        shop = ShopCredentials.objects.get(id=shop_id)
    except ShopCredentials.DoesNotExist:
        logger.error(f"ShopCredentials with id={shop_id} not found.")
        return {**stats, 'error': f'Shop {shop_id} not found'}

    org_id = shop.organization_id
    logger.info(f"🚀 Attribution Backfill starting for org={org_id}, "
                f"date_range={start_date} to {end_date}, force={force}")

    # Initialize fetcher and matcher
    fetcher = ShopifyOrderFetcher(shop)
    matcher = CampaignMatcher(shop)

    # Pre-load local shopify_ids for fast lookup
    local_shopify_ids = set(
        Order.objects.filter(org_id=org_id)
        .values_list('shopify_id', flat=True)
    )
    logger.info(f"📦 {len(local_shopify_ids)} local orders loaded for matching")

    # If not forcing, get existing attribution order IDs to skip
    existing_attr_order_ids = set()
    if not force:
        existing_attr_order_ids = set(
            OrderAttribution.objects
            .filter(order__org_id=org_id)
            .values_list('order__shopify_id', flat=True)
        )
        logger.info(f"⏭️ {len(existing_attr_order_ids)} orders already have attribution (will skip)")

    # Process pages from Shopify API
    for page_orders in fetcher.fetch_orders(start_date, end_date):
        stats['total_fetched'] += len(page_orders)

        for shopify_order in page_orders:
            shopify_id = shopify_order.get('id')
            if not shopify_id:
                continue

            # Skip if not in our local DB
            if shopify_id not in local_shopify_ids:
                continue

            stats['matched_local'] += 1

            # Skip if already has attribution (unless forced)
            if not force and shopify_id in existing_attr_order_ids:
                stats['skipped'] += 1
                continue

            # Extract landing_site and referring_site
            landing_site = shopify_order.get('landing_site') or ''
            referring_site_value = shopify_order.get('referring_site') or ''

            # ── CRITICAL FIX: ALWAYS extract note_attributes FIRST ────────
            # Shopify's headless/AJAX checkout often leaves landing_site empty,
            # but the FlexyPe tracking script stores full UTM data in
            # note_attributes. We must read these BEFORE deciding if an order
            # is truly "direct".
            # ──────────────────────────────────────────────────────────────────
            _NOTE_ATTR_KEYS = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
                'utm_term', 'fbclid', 'gclid', 'ttclid', 'epik', 'sclid',
            }
            _EXTRA_ATTR_KEYS = {'fp_id', 'referer', 'shori_session_id', 'bridgeworks_session_id'}

            override_utm_data = {}
            extra_data = {}  # fp_id, referer — not UTM but useful metadata

            # 1. Try Shopify API note_attributes (from the fetched order)
            note_attrs = shopify_order.get('note_attributes', [])
            if isinstance(note_attrs, list):
                for attr in note_attrs:
                    name = attr.get('name', '').lower().strip()
                    val = attr.get('value', '')
                    if isinstance(val, str) and val.strip():
                        if name in _NOTE_ATTR_KEYS:
                            override_utm_data[name] = val.strip()
                        elif name in _EXTRA_ATTR_KEYS:
                            extra_data[name] = val.strip()

            # 2. Also check local order's raw_data (webhook may have
            #    captured note_attributes that the REST fetch missed)
            if not override_utm_data:
                try:
                    local_order_for_raw = Order.objects.get(shopify_id=shopify_id, org_id=org_id)
                    raw = local_order_for_raw.raw_data or {}
                    local_note_attrs = raw.get('note_attributes', [])
                    if isinstance(local_note_attrs, list):
                        for attr in local_note_attrs:
                            name = attr.get('name', '').lower().strip()
                            val = attr.get('value', '')
                            if isinstance(val, str) and val.strip():
                                if name in _NOTE_ATTR_KEYS:
                                    override_utm_data[name] = val.strip()
                                elif name in _EXTRA_ATTR_KEYS and name not in extra_data:
                                    extra_data[name] = val.strip()
                except Order.DoesNotExist:
                    pass

            # ── NOW decide: is this truly "direct"? ──────────────────────
            has_any_signal = (
                landing_site or
                referring_site_value or
                any(override_utm_data.values())
            )

            if not has_any_signal:
                stats['no_landing_site'] += 1
                # No signals at all — genuinely direct traffic
                try:
                    local_order = Order.objects.get(shopify_id=shopify_id, org_id=org_id)
                    OrderAttribution.objects.update_or_create(
                        order=local_order,
                        defaults={
                            'channel': 'direct',
                            'source': 'backfill',
                            'fp_id': extra_data.get('fp_id', '')[:255],
                            'referer': extra_data.get('referer', '')[:500],
                        }
                    )
                    stats['created'] += 1
                except Order.DoesNotExist:
                    pass
                except Exception as e:
                    logger.warning(f"Error creating direct attribution for {shopify_id}: {e}")
                    stats['errors'] += 1
                continue

            # ── Classify channel using ALL available signals ──────────────
            attribution_data = extract_and_classify(landing_site, referring_site_value, override_utm_data)
            channel = attribution_data['channel']

            # Cross-reference against stored campaigns
            match_result = matcher.match(attribution_data, channel)

            # Save to DB
            try:
                local_order = Order.objects.get(shopify_id=shopify_id, org_id=org_id)

                _, created = OrderAttribution.objects.update_or_create(
                    order=local_order,
                    defaults={
                        'utm_source': attribution_data.get('utm_source', '')[:255],
                        'utm_medium': attribution_data.get('utm_medium', '')[:255],
                        'utm_campaign': attribution_data.get('utm_campaign', '')[:500],
                        'utm_content': attribution_data.get('utm_content', '')[:500],
                        'utm_term': attribution_data.get('utm_term', '')[:500],
                        'fbclid': attribution_data.get('fbclid', '')[:500],
                        'gclid': attribution_data.get('gclid', '')[:500],
                        'ttclid': attribution_data.get('ttclid', '')[:500],
                        'epik': attribution_data.get('epik', '')[:500],
                        'sclid': attribution_data.get('sclid', '')[:500],
                        'landing_page': landing_site[:2000],
                        'referring_site': referring_site_value[:2000],
                        'channel': channel,
                        'matched_campaign_id': match_result['matched_campaign_id'][:255],
                        'matched_adset_id': match_result['matched_adset_id'][:255],
                        'matched_ad_id': match_result['matched_ad_id'][:255],
                        'matched_platform': match_result['matched_platform'][:20],
                        'fp_id': extra_data.get('fp_id', '')[:255],
                        'referer': extra_data.get('referer', '')[:500],
                        'source': 'backfill',
                    }
                )

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

            except Order.DoesNotExist:
                pass
            except Exception as e:
                logger.warning(f"Error saving attribution for shopify_id={shopify_id}: {e}")
                stats['errors'] += 1

    stats['duration_seconds'] = round(time.time() - start_time, 1)

    logger.info(
        f"✅ Attribution Backfill complete for org={org_id}: "
        f"fetched={stats['total_fetched']}, matched={stats['matched_local']}, "
        f"created={stats['created']}, updated={stats['updated']}, "
        f"skipped={stats['skipped']}, no_landing={stats['no_landing_site']}, "
        f"errors={stats['errors']}, took={stats['duration_seconds']}s"
    )

    return stats
