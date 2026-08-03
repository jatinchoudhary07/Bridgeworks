"""
Centralized cache key management and invalidation for BridgeWorks.

Usage:
    from core.cache import CacheManager
    
    # Check cache before querying
    cache_key = CacheManager.order_list_key(org_id, filters_dict)
    cached = cache.get(cache_key)
    
    # Invalidate when data changes
    CacheManager.invalidate_org(org_id)
"""

from django.core.cache import cache
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Centralized cache key management with deterministic hashing."""

    # Cache durations (seconds)
    SHORT = 60           # 1 minute  (volatile data: search results)
    MEDIUM = 5 * 60      # 5 minutes (order lists with filters)
    LONG = 60 * 60       # 1 hour    (KPI aggregations)
    VERY_LONG = 24 * 3600  # 24 hours (daily reports, rarely-changing data)

    # ------------------------------------------------------------------ keys
    @staticmethod
    def _hash_filters(filters_dict: dict) -> str:
        """Create a short, deterministic hash from a filters dictionary."""
        raw = json.dumps(filters_dict, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @classmethod
    def order_list_key(cls, org_id: str, filters_dict: dict) -> str:
        """Cache key for a paginated order list with specific filters."""
        return f"orders:{org_id}:{cls._hash_filters(filters_dict)}"

    @staticmethod
    def kpi_key(org_id: str, date_str: str) -> str:
        """Cache key for KPI calculations per organization per day."""
        return f"kpi:{org_id}:{date_str}"

    @classmethod
    def logistics_matrix_key(cls, org_id: str, filters_dict: dict) -> str:
        """Cache key for the logistics analytics aggregation."""
        return f"logistics:{org_id}:{cls._hash_filters(filters_dict)}"

    @staticmethod
    def overview_key(org_id: str) -> str:
        """Cache key for the All Orders Overview."""
        return f"overview:{org_id}"

    # ----------------------------------------------------------- invalidation
    @staticmethod
    def invalidate_org(org_id: str):
        """
        Invalidate all cached data for an organization.
        Uses key-prefix pattern delete when available (django-redis),
        falls back to version-bump for other backends.
        """
        patterns = [
            f"orders:{org_id}:*",
            f"kpi:{org_id}:*",
            f"logistics:{org_id}:*",
            f"overview:{org_id}:*",  # New pattern for AllOrdersView
        ]
        # django-redis supports delete_pattern; LocMemCache does not.
        if hasattr(cache, 'delete_pattern'):
            for pattern in patterns:
                try:
                    cache.delete_pattern(f"*{pattern}")
                except Exception as e:
                    logger.warning("Cache pattern delete failed for %s: %s", pattern, e)
        else:
            # Fallback: can't do wildcard with LocMemCache, just clear all
            try:
                cache.clear()
            except Exception:
                pass

    @staticmethod
    def invalidate_order(order):
        """When a single order changes, invalidate its org's caches."""
        if order and hasattr(order, 'org_id') and order.org_id:
            CacheManager.invalidate_org(order.org_id)
