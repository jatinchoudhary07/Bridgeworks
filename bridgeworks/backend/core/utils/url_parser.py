"""
URL Parser & Channel Classifier Utilities
==========================================
Pure functions for extracting UTM parameters and click IDs from URLs,
and deterministically classifying them into marketing channels.

No Django imports — these are stateless, testable utility functions.
"""
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)

# ─── Known UTM/click ID parameter names ─────────────────────────────
_UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
_CLICK_ID_KEYS = ['fbclid', 'gclid', 'ttclid', 'epik', 'sclid']
_ALL_KEYS = _UTM_KEYS + _CLICK_ID_KEYS


def extract_utms_from_url(url_string):
    """
    Extract UTM parameters and click IDs from a URL string.

    Safely handles:
      - None / empty strings
      - Malformed URLs
      - URLs with no query parameters
      - Duplicate parameters (takes first value)
      - URL-encoded characters (urllib handles automatically)

    Returns:
        dict with keys: utm_source, utm_medium, utm_campaign, utm_content,
                        utm_term, fbclid, gclid, ttclid
        All values are strings (empty string if not present).

    Example:
        >>> extract_utms_from_url(
        ...     'https://thejanki.com/products/shirt?fbclid=123&utm_campaign=summer_sale&utm_term=ad_456'
        ... )
        {
            'utm_source': '', 'utm_medium': '', 'utm_campaign': 'summer_sale',
            'utm_content': '', 'utm_term': 'ad_456',
            'fbclid': '123', 'gclid': '', 'ttclid': ''
        }
    """
    # Default: all empty
    result = {key: '' for key in _ALL_KEYS}

    if not url_string or not isinstance(url_string, str):
        return result

    url_string = url_string.strip()
    if not url_string:
        return result

    try:
        # Handle URLs that might be just a path (e.g., "/products/shirt?utm_source=fb")
        # by prepending a scheme if missing
        if not url_string.startswith(('http://', 'https://', '//')):
            # Check if it's a relative URL with query params
            if '?' in url_string:
                url_string = 'https://placeholder.com' + (
                    url_string if url_string.startswith('/') else '/' + url_string
                )
            else:
                # No query params — nothing to extract
                return result

        parsed = urlparse(url_string)

        if not parsed.query:
            return result

        # parse_qs returns {key: [list_of_values]}
        query_params = parse_qs(parsed.query, keep_blank_values=False)

        for key in _ALL_KEYS:
            values = query_params.get(key, [])
            if values:
                # Take first value, strip whitespace
                result[key] = values[0].strip()

    except Exception as e:
        logger.warning(f"Failed to parse URL '{url_string[:100]}': {e}")

    return result


def merge_utm_dicts(base_dict, override_dict):
    """
    Merges two UTM dictionaries, taking non-empty values from override_dict.
    Used to merge URL params with Shopify note_attributes.
    """
    result = base_dict.copy()
    for key, value in override_dict.items():
        if value and isinstance(value, str):
            result[key] = value.strip()
    return result


def classify_channel(utm_data, referring_site=''):
    """
    Deterministic channel classification using Boolean signal cascade.

    Priority order (highest to lowest signal strength):
      1. Click IDs (strongest signal — platform-verified click)
      2. UTM source + medium combination
      3. UTM medium alone
      4. Referring site domain
      5. Fallback to 'unknown'

    Args:
        utm_data: dict from extract_utms_from_url()
        referring_site: raw referring_site string from Shopify

    Returns:
        str: one of the CHANNEL_CHOICES values
    """
    fbclid = utm_data.get('fbclid', '')
    gclid = utm_data.get('gclid', '')
    ttclid = utm_data.get('ttclid', '')
    epik = utm_data.get('epik', '')
    sclid = utm_data.get('sclid', '')

    source = utm_data.get('utm_source', '').lower().strip()
    medium = utm_data.get('utm_medium', '').lower().strip()

    ref = (referring_site or '').lower().strip()

    # ── 1. Click IDs (Strongest Signal) ──────────────────────────────
    if fbclid:
        return 'meta_paid'
    if gclid:
        return 'google_paid'
    if ttclid:
        return 'tiktok_paid'
    if epik:
        return 'pinterest_paid'
    if sclid:
        return 'snapchat_paid'

    # ── 2. UTM Source + Medium Combinations ──────────────────────────
    paid_mediums = {
        'cpc', 'paid', 'ppc', 'paidsocial', 'paid_social',
        'retargeting', 'remarketing',
        'oxb',          # Custom Janki brand code for paid Meta campaigns
        'whatsapp',     # WhatsApp marketing campaigns
        'automation',   # Automated marketing campaigns
    }

    # Meta / Facebook / Instagram
    meta_sources = {'facebook', 'fb', 'ig', 'instagram', 'meta', 'fbig', 'fb/ig'}
    if source in meta_sources:
        if medium in paid_mediums:
            return 'meta_paid'
        return 'organic_social'

    # Google
    google_sources = {'google', 'adwords', 'google_ads', 'googleads'}
    if source in google_sources:
        if medium in paid_mediums:
            return 'google_paid'
        if medium == 'organic':
            return 'organic_search'
        return 'google_paid' if medium else 'organic_search'

    # TikTok
    tiktok_sources = {'tiktok', 'tik_tok', 'tt'}
    if source in tiktok_sources:
        if medium in paid_mediums:
            return 'tiktok_paid'
        return 'organic_social'

    # Pinterest
    pinterest_sources = {'pinterest', 'pin', 'pinterestads'}
    if source in pinterest_sources:
        if medium in paid_mediums:
            return 'pinterest_paid'
        return 'organic_social'

    # Snapchat
    snapchat_sources = {'snapchat', 'snap', 'snapchatads'}
    if source in snapchat_sources:
        if medium in paid_mediums:
            return 'snapchat_paid'
        return 'organic_social'

    # YouTube (YouTube Ads are Google Ads)
    youtube_sources = {'youtube', 'yt'}
    if source in youtube_sources:
        if medium in paid_mediums:
            return 'google_paid'
        return 'organic_social'

    # WhatsApp / Chatbot
    whatsapp_sources = {'whatsapp', 'kwikchat', 'wati', 'sagepilot-ai', 'sagepilot'}
    if source in whatsapp_sources:
        return 'whatsapp'

    # ── 3. UTM Medium Alone ──────────────────────────────────────────
    if medium == 'email':
        return 'email'
    if medium in ('social', 'organic_social'):
        return 'organic_social'
    if medium == 'organic':
        return 'organic_search'
    if medium == 'referral':
        return 'referral'
    if medium in paid_mediums:
        # Paid but unknown platform
        return 'unknown'

    # ── 4. Referring Site Analysis ───────────────────────────────────
    if ref:
        # Social platforms
        social_domains = [
            'facebook.com', 'fb.com', 'instagram.com',
            'twitter.com', 'x.com', 'pinterest.com',
            'youtube.com', 'linkedin.com', 'tiktok.com',
        ]
        for domain in social_domains:
            if domain in ref:
                return 'organic_social'

        # Search engines
        search_domains = [
            'google.com', 'google.co.in', 'bing.com',
            'yahoo.com', 'duckduckgo.com', 'baidu.com',
        ]
        for domain in search_domains:
            if domain in ref:
                return 'organic_search'

        # Email providers (webmail)
        email_domains = ['mail.google.com', 'outlook.live.com', 'mail.yahoo.com']
        for domain in email_domains:
            if domain in ref:
                return 'email'

        # If there's a referrer but we can't classify it, it's a referral
        return 'referral'

    # ── 5. Check if we have ANY UTM data at all ─────────────────────
    has_any_utm = any([
        utm_data.get('utm_source'), utm_data.get('utm_medium'),
        utm_data.get('utm_campaign'), utm_data.get('utm_content'),
        utm_data.get('utm_term'),
    ])

    if has_any_utm:
        # We have UTMs but couldn't classify — still better than 'direct'
        return 'unknown'

    # ── 6. No signals at all ─────────────────────────────────────────
    # No UTMs, no click IDs, no referrer → Direct traffic
    return 'direct'


def extract_and_classify(landing_site, referring_site='', override_utm_data=None):
    """
    Convenience wrapper: extract UTMs, merge with overrides, and classify channel.

    Returns:
        dict with all UTM fields + 'channel' key
    """
    utm_data = extract_utms_from_url(landing_site)
    
    if override_utm_data:
        utm_data = merge_utm_dicts(utm_data, override_utm_data)

    channel = classify_channel(utm_data, referring_site)

    return {
        **utm_data,
        'channel': channel,
        'landing_page': landing_site or '',
        'referring_site': referring_site or '',
    }
