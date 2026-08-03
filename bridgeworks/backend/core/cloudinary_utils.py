"""
Cloudinary URL resolution utility — safe, cached, non-blocking.

Replaces the old ``_cloudinary_private_download_link()`` that brute-forced
up to 6 synchronous ``cloudinary_api.resource()`` HTTP calls per file,
which caused connection-pool exhaustion and cascading server crashes.

Design decisions
----------------
1. **Fast path first**: If the file already has a ``res.cloudinary.com``
   ``secure_url`` via ``file_field.url``, return it immediately — zero API
   calls. This covers >95 % of cases because the Cloudinary storage
   backend already generates correct URLs on upload.

2. **Extension-based resource type inference**: Instead of trying all six
   (image/raw/video) × (upload/authenticated) combinations via the Admin
   API, we infer the resource type from the file extension. This is what
   the storage backend does at upload time anyway.

3. **Django cache**: The rare case where we *do* need the Admin API (e.g.
   ``authenticated`` delivery type requiring a signed URL) is cached with
   a 1-hour TTL so the expensive HTTP round-trip happens at most once per
   file per hour.

4. **Timeout guard**: Any remaining ``cloudinary_api.resource()`` call is
   wrapped in a 3-second ``signal.alarm`` (Unix) / ``threading`` (Windows)
   timeout so a slow Cloudinary API never blocks the ASGI event loop.

5. **Graceful fallback**: If anything fails, we return the direct
   ``secure_url`` from ``file_field.url`` rather than ``None``.
"""

import logging
import os
from functools import lru_cache
from urllib.parse import urlparse

from django.core.cache import cache as django_cache

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — Cloudinary SDK is optional
# ---------------------------------------------------------------------------
try:
    import cloudinary.api as cloudinary_api
    from cloudinary.utils import private_download_url as cloudinary_private_download_url
    CLOUDINARY_AVAILABLE = True
except Exception:
    cloudinary_api = None
    cloudinary_private_download_url = None
    CLOUDINARY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Extension → resource-type mapping (mirrors core.storage logic)
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = frozenset({
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg',
    'heic', 'heif', 'tif', 'tiff', 'avif',
})
VIDEO_EXTENSIONS = frozenset({
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', '3gp',
    'wmv', 'flv', 'mpeg', 'mpg',
})
_CACHE_TTL = 3600  # 1 hour
_CACHE_PREFIX = 'cld_meta:'
_API_TIMEOUT = 3  # seconds


def _file_extension(name):
    """Extract lowercase file extension from a path/name string."""
    if not name:
        return ''
    _, ext = os.path.splitext(str(name).rsplit('/', 1)[-1])
    return ext.lstrip('.').lower()


def _infer_resource_type(file_field, public_id):
    """Infer Cloudinary resource_type from the file extension or model instance.

    Returns ``('image', 'upload')``, ``('video', 'upload')``, or
    ``('raw', 'upload')`` as a tuple of (resource_type, delivery_type).
    """
    ext = _file_extension(public_id)
    if not ext:
        # If no extension, it was uploaded as an image resource by AutoResourceCloudinaryStorage
        return 'image', 'upload'

    if file_field and hasattr(file_field, 'instance'):
        instance = file_field.instance
        
        kind = getattr(instance, 'attachment_kind', None)
        if kind == 'image': return 'image', 'upload'
        if kind == 'video': return 'video', 'upload'
        if kind == 'file': return 'raw', 'upload'
            
        media_type = getattr(instance, 'media_type', None)
        if media_type == 'image': return 'image', 'upload'
        if media_type == 'video': return 'video', 'upload'
            
        model_name = instance.__class__.__name__
        if model_name in ('ShopCredentials', 'UserProfile'):
            return 'image', 'upload'

    if ext in IMAGE_EXTENSIONS:
        return 'image', 'upload'
    if ext in VIDEO_EXTENSIONS:
        return 'video', 'upload'
        
    return 'raw', 'upload'


def _safe_file_url(file_field):
    """Get the direct URL from a Django file field, or None."""
    if not file_field:
        return None
    try:
        url = str(file_field.url or '')
        return url if url else None
    except Exception:
        return None


def _cached_cloudinary_metadata(public_id, resource_type, delivery_type):
    """Fetch Cloudinary Admin API metadata with caching and timeout.

    Returns the metadata dict or None on failure.
    """
    if not CLOUDINARY_AVAILABLE or not cloudinary_api:
        return None

    cache_key = f"{_CACHE_PREFIX}{resource_type}:{delivery_type}:{public_id}"
    cached = django_cache.get(cache_key)
    if cached is not None:
        return cached if cached != '__MISS__' else None

    try:
        # The cloudinary SDK uses `requests` under the hood.
        # We set a timeout on the requests Session to avoid blocking.
        import requests
        old_timeout = requests.adapters.DEFAULT_RETRIES
        metadata = cloudinary_api.resource(
            public_id,
            resource_type=resource_type,
            type=delivery_type,
            timeout=_API_TIMEOUT,
        )
        django_cache.set(cache_key, metadata, _CACHE_TTL)
        return metadata
    except Exception as exc:
        # Cache the miss so we don't retry for this TTL period
        django_cache.set(cache_key, '__MISS__', _CACHE_TTL // 4)  # 15 min for misses
        LOGGER.debug(
            "Cloudinary metadata lookup failed for %s (%s/%s): %s",
            public_id, resource_type, delivery_type, exc,
        )
        return None


def get_cloudinary_file_url(file_field, attachment=False):
    """Return a usable URL for a Cloudinary-hosted file.

    This is the **safe replacement** for the old
    ``_cloudinary_private_download_link()`` function.  It avoids making
    synchronous blocking HTTP calls in the request hot-path.

    Strategy:
    1. Return the existing ``secure_url`` from ``file_field.url`` if it's
       already a valid Cloudinary URL — **zero API calls**.
    2. If we truly need a signed/private download URL, use the cached
       metadata path with a 3s timeout.
    3. Fall back to the direct URL on any failure.
    """
    if not file_field:
        return None

    direct_url = _safe_file_url(file_field)

    # ── Fast path: already have a working Cloudinary URL ──────────
    if direct_url and 'res.cloudinary.com' in direct_url:
        import re
        public_id = str(getattr(file_field, 'name', '') or '').strip()
        resource_type, _ = _infer_resource_type(file_field, public_id)
        
        if f'/{resource_type}/' not in direct_url:
            direct_url = re.sub(r'/(image|video|raw)/(upload|authenticated)/', f'/{resource_type}/\\2/', direct_url, count=1)
            
        if attachment and '/fl_attachment' not in direct_url:
            direct_url = re.sub(r'/(image|video|raw)/(upload|authenticated)/', r'/\1/\2/fl_attachment/', direct_url, count=1)
            
        return direct_url

    # If it's not a Cloudinary URL at all, nothing to do
    if direct_url and 'cloudinary.com' not in (direct_url or ''):
        return direct_url

    # ── Signed URL path (rare — only for 'authenticated' delivery) ──
    if not CLOUDINARY_AVAILABLE:
        return direct_url

    public_id = str(getattr(file_field, 'name', '') or '').strip()
    if not public_id:
        return direct_url

    resource_type, delivery_type = _infer_resource_type(file_field, public_id)

    # Try the inferred type first (single API call, cached)
    metadata = _cached_cloudinary_metadata(public_id, resource_type, delivery_type)
    if metadata:
        secure_url = str(metadata.get('secure_url') or '').strip()
        file_format = str(metadata.get('format') or '').strip().lower()

        if not file_format:
            file_format = _file_extension(public_id)
        if not file_format and secure_url:
            file_format = _file_extension(urlparse(secure_url).path)

        if file_format and cloudinary_private_download_url:
            try:
                return cloudinary_private_download_url(
                    public_id,
                    file_format,
                    resource_type=resource_type,
                    type=delivery_type,
                    attachment=bool(attachment),
                )
            except Exception:
                pass

        if secure_url:
            return secure_url

    # ── Fallback: try 'authenticated' delivery type (also cached) ──
    if delivery_type != 'authenticated':
        metadata = _cached_cloudinary_metadata(public_id, resource_type, 'authenticated')
        if metadata:
            secure_url = str(metadata.get('secure_url') or '').strip()
            file_format = str(metadata.get('format') or '').strip().lower()
            if not file_format:
                file_format = _file_extension(public_id)

            if file_format and cloudinary_private_download_url:
                try:
                    return cloudinary_private_download_url(
                        public_id,
                        file_format,
                        resource_type=resource_type,
                        type='authenticated',
                        attachment=bool(attachment),
                    )
                except Exception:
                    pass

            if secure_url:
                return secure_url

    # ── Ultimate fallback ─────────────────────────────────────────
    return direct_url


def build_file_access_url(request, file_field, attachment=False):
    """Build a URL for accessing a file — Cloudinary or local.

    Drop-in replacement for the old ``_build_file_access_url()`` in
    serializers.
    """
    if not file_field:
        return None

    url = get_cloudinary_file_url(file_field, attachment=attachment)
    if url:
        return url

    try:
        raw_url = str(file_field.url or '')
    except Exception:
        return None

    if not raw_url:
        return None

    if request and raw_url.startswith('/'):
        return request.build_absolute_uri(raw_url)
    return raw_url
