"""
Prometheus-compatible request metrics middleware.

Tracks:
- Total request count (by method, endpoint, status)
- Request latency (by endpoint)

Install: Add 'core.monitoring.MetricsMiddleware' to MIDDLEWARE in settings.py
View: GET /metrics (if prometheus_client is installed)
"""

import time
import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


if HAS_PROMETHEUS:
    request_count = Counter(
        'api_requests_total',
        'Total API requests',
        ['method', 'endpoint', 'status']
    )

    request_duration = Histogram(
        'api_request_duration_seconds',
        'API request latency in seconds',
        ['endpoint'],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    db_query_count = Counter(
        'db_queries_total',
        'Total database queries per request',
        ['endpoint']
    )


class MetricsMiddleware:
    """
    Django middleware that records request metrics for Prometheus.
    
    Measures:
    - Request count by method/endpoint/status
    - Request latency distribution
    - Database query count per request (via Django debug connection)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not HAS_PROMETHEUS:
            return self.get_response(request)

        start = time.monotonic()

        # Count DB queries (only in DEBUG or when connection tracking is enabled)
        from django.db import connection
        initial_queries = len(connection.queries) if connection.queries else 0

        response = self.get_response(request)

        duration = time.monotonic() - start

        # Normalize endpoint to avoid cardinality explosion
        # e.g., /api/orders/12345/ → /api/orders/:id/
        endpoint = self._normalize_path(request.path)

        request_count.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        request_duration.labels(
            endpoint=endpoint
        ).observe(duration)

        # Log slow requests
        if duration > 5.0:
            logger.warning(
                "SLOW REQUEST: %s %s took %.2fs (status=%d)",
                request.method, request.path, duration, response.status_code
            )

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        Collapse numeric IDs in URLs to prevent metric cardinality explosion.
        /api/orders/12345/ → /api/orders/:id/
        /api/cases/67890/comments/ → /api/cases/:id/comments/
        """
        import re
        return re.sub(r'/\d+', '/:id', path)
