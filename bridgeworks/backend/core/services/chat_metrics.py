import math
import time
from django.core.cache import cache


KEY_PREFIX = 'chat:metrics:v1'

POST_COUNT_KEY = f'{KEY_PREFIX}:post:count'
POST_LATENCY_TOTAL_KEY = f'{KEY_PREFIX}:post:latency_total_ms'
POST_LAST_LATENCY_KEY = f'{KEY_PREFIX}:post:last_latency_ms'

WS_BROADCAST_ATTEMPTS_KEY = f'{KEY_PREFIX}:ws:broadcast:attempts'
WS_BROADCAST_SUCCESS_KEY = f'{KEY_PREFIX}:ws:broadcast:success'
WS_BROADCAST_FAILURE_KEY = f'{KEY_PREFIX}:ws:broadcast:failure'
WS_QUEUE_DELAY_TOTAL_KEY = f'{KEY_PREFIX}:ws:queue_delay_total_ms'
WS_QUEUE_DELAY_COUNT_KEY = f'{KEY_PREFIX}:ws:queue_delay_count'

WS_CLIENT_DROPS_KEY = f'{KEY_PREFIX}:ws:client_drops'
UPDATED_AT_KEY = f'{KEY_PREFIX}:updated_at_epoch_ms'


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bump_updated_at():
    cache.set(UPDATED_AT_KEY, int(time.time() * 1000), None)


def _incr(key, amount=1):
    amount = int(amount)
    if amount == 0:
        return
    if cache.get(key) is None:
        cache.set(key, 0, None)
    try:
        cache.incr(key, amount)
    except Exception:
        current = _safe_int(cache.get(key), 0)
        cache.set(key, current + amount, None)


def _incr_float(key, amount):
    amount = _safe_float(amount, 0.0)
    if math.isclose(amount, 0.0):
        return
    current = _safe_float(cache.get(key), 0.0)
    cache.set(key, current + amount, None)


def record_post_latency(latency_ms):
    latency = max(0.0, _safe_float(latency_ms, 0.0))
    _incr(POST_COUNT_KEY, 1)
    _incr_float(POST_LATENCY_TOTAL_KEY, latency)
    cache.set(POST_LAST_LATENCY_KEY, latency, None)
    _bump_updated_at()


def record_ws_broadcast(success=True, queue_delay_ms=0.0):
    _incr(WS_BROADCAST_ATTEMPTS_KEY, 1)
    if success:
        _incr(WS_BROADCAST_SUCCESS_KEY, 1)
    else:
        _incr(WS_BROADCAST_FAILURE_KEY, 1)

    queue_delay = max(0.0, _safe_float(queue_delay_ms, 0.0))
    _incr_float(WS_QUEUE_DELAY_TOTAL_KEY, queue_delay)
    _incr(WS_QUEUE_DELAY_COUNT_KEY, 1)
    _bump_updated_at()


def record_client_drop():
    _incr(WS_CLIENT_DROPS_KEY, 1)
    _bump_updated_at()


def get_delivery_metrics():
    post_count = _safe_int(cache.get(POST_COUNT_KEY), 0)
    post_latency_total = _safe_float(cache.get(POST_LATENCY_TOTAL_KEY), 0.0)
    post_last_latency = _safe_float(cache.get(POST_LAST_LATENCY_KEY), 0.0)

    ws_attempts = _safe_int(cache.get(WS_BROADCAST_ATTEMPTS_KEY), 0)
    ws_success = _safe_int(cache.get(WS_BROADCAST_SUCCESS_KEY), 0)
    ws_failure = _safe_int(cache.get(WS_BROADCAST_FAILURE_KEY), 0)

    queue_delay_total = _safe_float(cache.get(WS_QUEUE_DELAY_TOTAL_KEY), 0.0)
    queue_delay_count = _safe_int(cache.get(WS_QUEUE_DELAY_COUNT_KEY), 0)

    ws_client_drops = _safe_int(cache.get(WS_CLIENT_DROPS_KEY), 0)
    updated_at_epoch_ms = _safe_int(cache.get(UPDATED_AT_KEY), 0)

    return {
        'post': {
            'count': post_count,
            'avg_latency_ms': round(post_latency_total / post_count, 2) if post_count else 0.0,
            'last_latency_ms': round(post_last_latency, 2),
        },
        'ws_broadcast': {
            'attempts': ws_attempts,
            'success': ws_success,
            'failure': ws_failure,
            'success_rate': round((ws_success / ws_attempts) * 100, 2) if ws_attempts else 0.0,
            'avg_queue_delay_ms': round(queue_delay_total / queue_delay_count, 2) if queue_delay_count else 0.0,
        },
        'client': {
            'unexpected_ws_close_count': ws_client_drops,
        },
        'updated_at_epoch_ms': updated_at_epoch_ms,
    }
