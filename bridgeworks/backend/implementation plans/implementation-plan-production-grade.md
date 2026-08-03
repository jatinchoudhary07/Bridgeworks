# Production-Grade Implementation Plan
## Optimize Tracking, Logistics Dashboard, Sales & Shopify Carts Persistence

> **Version:** 2.0 — Production Hardened
> **Supersedes:** v1.0 (internal draft)
> **Focus Areas Added:** Security Hardening · Cost Management · Observability · Zero-Downtime Deployment · Rollback Strategy

---

## Table of Contents

1. [Risk & Compatibility Overview](#1-risk--compatibility-overview)
2. [Security Hardening](#2-security-hardening)
3. [Cost Management Strategy](#3-cost-management-strategy)
4. [Component Changes — Hardened](#4-component-changes--hardened)
   - 4.1 Core Orders & Dispatch Views
   - 4.2 Logistics Analytics Views
   - 4.3 Sales Views & Shopify Carts Persistence
   - 4.4 Webhook Receivers
   - 4.5 Analytics Views
   - 4.6 Frontend Integration
   - 4.7 URL Routes
   - 4.8 Database Migrations
5. [Async Task Architecture (Celery)](#5-async-task-architecture-celery)
6. [Caching Strategy](#6-caching-strategy)
7. [Observability & Alerting](#7-observability--alerting)
8. [Zero-Downtime Deployment Strategy](#8-zero-downtime-deployment-strategy)
9. [Rollback Plan](#9-rollback-plan)
10. [Verification Plan](#10-verification-plan)
11. [Checklist Before Go-Live](#11-checklist-before-go-live)

---

## 1. Risk & Compatibility Overview

| Item | Status | Notes |
|---|---|---|
| Frontend API payload signatures | ✅ No breaking change | All existing contracts preserved |
| Database schema | ⚠️ Migration required | Additive only — indexes + new table. See §4.8 for zero-downtime migration strategy. |
| Shopify REST API version | ⚠️ Pin required | Always pin to a specific API version (e.g., `2024-01`). Unpinned calls auto-upgrade and can break silently. |
| Webhook idempotency | ⚠️ Must implement | Shopify may deliver the same webhook more than once. |
| Daphne workers | ✅ Improves stability | Offloading Shopify sync to Celery removes long-running requests from Daphne. |

---

## 2. Security Hardening

### 2.1 Shopify Webhook Signature Verification (CRITICAL)

Every inbound Shopify webhook **must** be verified before processing. Failure to do so allows any actor on the internet to inject fake checkout data.

```python
# core/views/webhooks.py

import hmac
import hashlib
import base64
from django.conf import settings

class ShopifyWebhookView(View):

    def _verify_signature(self, request) -> bool:
        """
        Verify HMAC-SHA256 signature sent by Shopify.
        Reject immediately if verification fails.
        """
        shopify_hmac = request.headers.get("X-Shopify-Hmac-Sha256", "")
        secret = settings.SHOPIFY_WEBHOOK_SECRET.encode("utf-8")
        digest = hmac.new(secret, request.body, hashlib.sha256).digest()
        computed = base64.b64encode(digest).decode("utf-8")
        # Use hmac.compare_digest to prevent timing attacks
        return hmac.compare_digest(computed, shopify_hmac)

    def post(self, request, *args, **kwargs):
        if not self._verify_signature(request):
            # Log the failure with IP — useful for detecting probing
            logger.warning(
                "Shopify webhook signature mismatch",
                extra={"ip": request.META.get("REMOTE_ADDR")}
            )
            return HttpResponse(status=401)
        # ... continue processing
```

### 2.2 Sync Endpoint Authentication & Authorization

The new `POST /api/sales/shopify/abandoned-checkouts/sync/` endpoint must be protected.

```python
# Must require both login AND explicit permission
@login_required
@permission_required("core.can_sync_shopify_checkouts", raise_exception=True)
def shopify_sync_abandoned_checkouts(request):
    ...
```

- Assign the `can_sync_shopify_checkouts` permission only to admin/ops roles.
- Rate-limit this endpoint — see §2.3.
- Log every invocation with the calling user's ID and timestamp for audit trail.

### 2.3 Rate Limiting on the Sync Endpoint

Prevent abuse (accidental or intentional) of the sync endpoint with Django's throttling or `django-ratelimit`.

```python
# Using django-ratelimit (pip install django-ratelimit)
from ratelimit.decorators import ratelimit

@ratelimit(key="user", rate="5/h", method="POST", block=True)
@login_required
@permission_required("core.can_sync_shopify_checkouts", raise_exception=True)
def shopify_sync_abandoned_checkouts(request):
    """
    Max 5 manual syncs per user per hour.
    Prevents hammering Shopify API and running up API costs.
    """
    ...
```

### 2.4 Secrets Management

**Never hardcode API keys.** All secrets must flow through environment variables and be validated at startup.

```python
# settings/production.py

import os

SHOPIFY_API_KEY      = os.environ["SHOPIFY_API_KEY"]       # Raises KeyError if missing — intentional
SHOPIFY_API_SECRET   = os.environ["SHOPIFY_API_SECRET"]
SHOPIFY_WEBHOOK_SECRET = os.environ["SHOPIFY_WEBHOOK_SECRET"]
SHOPIFY_STORE_DOMAIN = os.environ["SHOPIFY_STORE_DOMAIN"]
SHOPIFY_API_VERSION  = os.environ.get("SHOPIFY_API_VERSION", "2024-01")  # Pin the version
```

Use a secrets manager (AWS Secrets Manager / HashiCorp Vault / GCP Secret Manager) in production. Never commit `.env` files to source control.

### 2.5 Django CSRF Protection

The new sync endpoint uses `POST`. Ensure it:
- Is protected by Django's CSRF middleware (default for session-authenticated views).
- Uses `@csrf_protect` explicitly if `@csrf_exempt` is anywhere in the middleware stack.
- The frontend sends the CSRF token in the `X-CSRFToken` header (standard Django SPA pattern).

### 2.6 Input Validation on Webhook Payloads

Never trust incoming webhook JSON directly. Validate before inserting.

```python
REQUIRED_CHECKOUT_FIELDS = {"id", "token", "email", "total_price", "created_at", "updated_at"}

def _parse_checkout_payload(payload: dict) -> dict:
    missing = REQUIRED_CHECKOUT_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Checkout payload missing fields: {missing}")
    return {
        "shopify_id":    str(payload["id"])[:100],         # Bound field lengths
        "token":         str(payload["token"])[:255],
        "email":         str(payload.get("email") or "")[:254],
        "total_price":   Decimal(str(payload["total_price"])),  # Avoid float precision errors
        "created_at_shopify": parse_datetime(payload["created_at"]),
        "updated_at_shopify": parse_datetime(payload["updated_at"]),
        "raw_payload":   payload,  # Store original for debugging / re-processing
    }
```

### 2.7 SQL Injection — ORM Discipline

All existing and new queries must exclusively use the Django ORM or parameterized queries. **No raw string interpolation into `.raw()` or `cursor.execute()`.**

```python
# ❌ NEVER DO THIS
cursor.execute(f"SELECT * FROM orders WHERE status = '{status}'")

# ✅ Always do this
cursor.execute("SELECT * FROM orders WHERE status = %s", [status])
```

---

## 3. Cost Management Strategy

### 3.1 Shopify API — Rate Limit Awareness

Shopify REST API enforces a **2 requests/second** leaky-bucket limit (40 bucket size). Violating this results in `429 Too Many Requests`.

```python
# core/services/shopify_client.py

import time
import requests
from django.conf import settings

SHOPIFY_RATE_LIMIT_SLEEP = 0.6   # Stay comfortably under 2 req/s
MAX_RETRIES = 3

def shopify_get_paginated(endpoint: str, params: dict) -> list:
    """
    Fetches all pages from a Shopify REST endpoint.
    Respects rate limits and retries on transient failures.
    Tracks and logs API call count to manage quota costs.
    """
    results = []
    url = f"https://{settings.SHOPIFY_STORE_DOMAIN}/admin/api/{settings.SHOPIFY_API_VERSION}/{endpoint}.json"
    call_count = 0

    while url:
        for attempt in range(MAX_RETRIES):
            resp = requests.get(url, params=params,
                                headers={"X-Shopify-Access-Token": settings.SHOPIFY_API_KEY},
                                timeout=10)
            call_count += 1

            if resp.status_code == 429:
                # Shopify tells us to back off — respect it
                retry_after = float(resp.headers.get("Retry-After", 2.0))
                logger.warning("Shopify rate limit hit", extra={"retry_after": retry_after})
                time.sleep(retry_after)
                continue

            if resp.status_code >= 500:
                # Transient server error — exponential backoff
                time.sleep(2 ** attempt)
                continue

            resp.raise_for_status()
            break
        else:
            raise RuntimeError(f"Shopify API failed after {MAX_RETRIES} retries")

        data = resp.json()
        results.extend(data.get("checkouts", []))

        # Pagination via Link header
        link = resp.headers.get("Link", "")
        url = _parse_next_link(link)
        params = {}  # Subsequent pages encode params in the URL

        time.sleep(SHOPIFY_RATE_LIMIT_SLEEP)

    logger.info("Shopify sync complete", extra={"api_calls_made": call_count, "records_fetched": len(results)})
    return results
```

### 3.2 Sync Scope — Reduce Unnecessary API Calls

Instead of syncing **all** checkouts on every manual trigger, only fetch records updated since the last successful sync.

```python
# Store last sync timestamp in cache or a SyncState model
def shopify_sync_abandoned_checkouts(request):
    last_sync = SyncState.objects.get_or_create(key="shopify_abandoned_checkouts")[0]
    since = last_sync.last_synced_at  # Only fetch changed records

    params = {
        "limit": 250,
        "status": "open",
        "updated_at_min": since.isoformat() if since else None,
    }
    checkouts = shopify_get_paginated("checkouts", params)
    # ... upsert into ChannelAbandonedCheckout
    last_sync.last_synced_at = now()
    last_sync.save()
```

This turns a 500-record API crawl into a 5-record delta fetch after the first sync — **drastically reducing API call volume and sync time**.

### 3.3 Database — Index Cost vs. Query Speed Balance

Adding `db_index=True` has a write-time cost. Every `INSERT`/`UPDATE` on indexed fields incurs overhead.

| Index | Read benefit | Write cost | Verdict |
|---|---|---|---|
| `Order.created_at` | Very high (used in many range filters) | Low (rarely updated after creation) | ✅ Add |
| `Order.current_status_date` | High (NDR tab filter) | Medium (updated on status change) | ✅ Add (benefit > cost) |
| `Shipment.dispatch_date` | High (logistics analytics) | Low | ✅ Existing — ensure BRIN or BTREE index |
| `WebhookLog.created_at` | Medium | Low | ✅ Add |
| `ChannelAbandonedCheckout.shopify_id` | Required for upsert | One-time | ✅ Add (unique index) |
| `ChannelAbandonedCheckout.updated_at_shopify` | Required for delta sync | Low | ✅ Add |

### 3.4 Caching — Reduce Database Load

See detailed caching strategy in §6. The key principle: **views that are hit on every dashboard page load should be cached; Shopify sync results should not bypass the cache**.

### 3.5 Query Cost Monitoring

Add slow-query logging to catch regressions.

```python
# settings/production.py
LOGGING = {
    "loggers": {
        "django.db.backends": {
            "level": "WARNING",  # Logs queries taking > SLOW_QUERY_THRESHOLD
        }
    }
}

# Optionally, use django-silk or django-debug-toolbar in staging
# to measure query counts before and after each change.
```

---

## 4. Component Changes — Hardened

### 4.1 Core Orders & Dispatch Views

**File:** `core/views/dispatch.py`

**Change:** Replace `Exists(TrackingEvent...)` subquery with direct `current_status_date` filter.

**Production addition:** Add a structured log entry measuring query duration before vs. after so the improvement is verifiable in production metrics.

```python
# Before (expensive subquery — keep as comment for reference during code review)
# .filter(Exists(TrackingEvent.objects.filter(fulfillment__order=OuterRef('pk')).filter(...)))

# After (uses index on current_status_date)
.filter(
    current_status_date__gte=ndr_cutoff_dt,
    current_status_date__lte=now()
)
```

**Guard:** Ensure `ndr_cutoff_dt` is always timezone-aware. Add assertion:

```python
assert is_aware(ndr_cutoff_dt), "ndr_cutoff_dt must be timezone-aware"
```

---

### 4.2 Logistics Analytics Views

**File:** `core/views_logistics_analytics.py`

**Changes (all four from v1.0 preserved):**

1. `dispatch_date__date__gte/lte` → timezone-aware `dispatch_date__gte/lte`
2. `created_at__date__gte` → timezone-aware `created_at__gte`
3. Courier aggregation → datetime boundary filter
4. Trend queries → `TruncDate` + conditional aggregation

**Production additions:**

- Wrap the trend query in a `try/except` and return a degraded (cached) response if the DB is slow, rather than timing out entirely.
- Add a `Cache-Control: private, max-age=300` header to the response so the browser doesn't re-request within 5 minutes.

```python
# Trend query optimization — replaces 21 separate queries
from django.db.models import Count, Q
from django.db.models.functions import TruncDate

trend_data = (
    Shipment.objects
    .filter(dispatch_date__gte=window_start, dispatch_date__lte=window_end)
    .annotate(day=TruncDate("dispatch_date"))
    .values("day")
    .annotate(
        total=Count("id"),
        delivered=Count("id", filter=Q(current_status="delivered")),
        rto=Count("id", filter=Q(current_status="rto")),
    )
    .order_by("day")
)
# 1 query replaces 21
```

---

### 4.3 Sales Views & Shopify Carts Persistence

**File:** `core/views_sales.py`

#### sales_overview Optimisation (unchanged from v1.0)

```python
# Single DB-side aggregation replaces Python loop
new_customers_count = (
    Order.objects
    .values("customer")
    .annotate(first_order=Min("created_at"))
    .filter(first_order__gte=d_from_dt, first_order__lte=d_to_dt)
    .count()
)
```

#### shopify_analytics Optimisation (unchanged from v1.0)

Merge 6 separate `COUNT` queries into one `.aggregate()` call.

#### shopify_abandoned_checkouts — Hardened

```python
@login_required
def shopify_abandoned_checkouts(request):
    """
    Reads from local ChannelAbandonedCheckout table only.
    No live Shopify call. Response time: <50ms.
    """
    checkouts = (
        ChannelAbandonedCheckout.objects
        .filter(channel=request.user.active_channel)
        .order_by("-updated_at_shopify")
        .values(
            "shopify_id", "email", "total_price",
            "created_at_shopify", "updated_at_shopify",
            "checkout_url", "line_items_count",
        )
    )
    # Apply pagination — never return unbounded querysets
    paginator = Paginator(checkouts, per_page=50)
    page = paginator.get_page(request.GET.get("page", 1))
    return JsonResponse({
        "results": list(page.object_list),
        "total": paginator.count,
        "page": page.number,
        "total_pages": paginator.num_pages,
        "last_synced_at": SyncState.objects.filter(
            key="shopify_abandoned_checkouts"
        ).values_list("last_synced_at", flat=True).first(),
    })
```

#### shopify_sync_abandoned_checkouts [NEW — Hardened]

```python
@login_required
@permission_required("core.can_sync_shopify_checkouts", raise_exception=True)
@ratelimit(key="user", rate="5/h", method="POST", block=True)
def shopify_sync_abandoned_checkouts(request):
    """
    Enqueues a Celery task for background sync.
    Returns immediately — does NOT block the Daphne worker.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    task = sync_shopify_checkouts_task.delay(
        channel_id=request.user.active_channel_id,
        triggered_by=request.user.id,
    )

    logger.info(
        "Shopify checkout sync enqueued",
        extra={
            "task_id": task.id,
            "user_id": request.user.id,
            "channel_id": request.user.active_channel_id,
        }
    )
    return JsonResponse({"task_id": task.id, "status": "queued"}, status=202)
```

> **Why 202 Accepted instead of 200 OK?** The sync runs asynchronously. Returning 202 is semantically correct and tells the frontend to poll for completion rather than assume it's done.

---

### 4.4 Webhook Receivers

**File:** `core/views/webhooks.py`

**Hardened changes beyond v1.0:**

#### Idempotency

Shopify may deliver the same webhook multiple times. Use `update_or_create` keyed on `shopify_id` to ensure idempotency.

```python
def _handle_checkout_webhook(self, topic: str, payload: dict):
    try:
        parsed = _parse_checkout_payload(payload)  # Validates fields (see §2.6)
    except (ValueError, KeyError) as e:
        logger.error("Invalid checkout webhook payload", extra={"error": str(e), "topic": topic})
        return  # Return 200 to Shopify anyway — do NOT return 4xx or Shopify will retry forever

    ChannelAbandonedCheckout.objects.update_or_create(
        shopify_id=parsed["shopify_id"],
        defaults={**parsed, "last_webhook_topic": topic}
    )
```

> **Critical:** Always return HTTP 200 to Shopify even on parse errors. Returning 4xx/5xx causes Shopify to retry the webhook for 48 hours, creating noise and wasted processing. Log the error internally and move on.

#### Webhook Topic Guard

```python
HANDLED_TOPICS = {"checkouts/create", "checkouts/update", "checkouts/delete"}

def post(self, request, *args, **kwargs):
    if not self._verify_signature(request):
        return HttpResponse(status=401)

    topic = request.headers.get("X-Shopify-Topic", "")
    if topic not in HANDLED_TOPICS:
        return HttpResponse(status=200)  # Silently accept — we don't handle other topics

    payload = json.loads(request.body)
    # Enqueue for async processing — never process inline in webhook handler
    process_checkout_webhook_task.delay(topic=topic, payload=payload)
    return HttpResponse(status=200)  # Respond fast; Shopify has a 5s timeout
```

---

### 4.5 Analytics Views

**File:** `core/views_analytics.py`

**Change (unchanged from v1.0):** Replace `__date__` filter lookups with timezone-aware boundaries.

**Production addition:** Cache `get_stage_summary` results for 10 minutes since this is a read-heavy, write-light view.

```python
from django.core.cache import cache

def get_stage_summary(channel_id, d_from, d_to):
    cache_key = f"stage_summary:{channel_id}:{d_from}:{d_to}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = _compute_stage_summary(channel_id, d_from, d_to)
    cache.set(cache_key, result, timeout=600)  # 10 minutes
    return result
```

---

### 4.6 Frontend Integration

**File:** `frontend/src/components/sales/AbandonedCartRecovery.jsx`

**Hardened changes beyond v1.0:**

```jsx
const SyncButton = ({ onSyncComplete }) => {
  const [status, setStatus] = useState("idle"); // idle | queued | polling | done | error
  const [taskId, setTaskId] = useState(null);

  const handleSync = async () => {
    setStatus("queued");
    try {
      const res = await api.post("/api/sales/shopify/abandoned-checkouts/sync/");
      setTaskId(res.data.task_id);
      setStatus("polling");
      // Poll task status every 3 seconds
      pollTaskStatus(res.data.task_id);
    } catch (err) {
      // Surface rate-limit errors clearly
      if (err.response?.status === 429) {
        setStatus("error");
        toast.error("Sync limit reached. Max 5 syncs per hour.");
      } else {
        setStatus("error");
        toast.error("Sync failed. Please try again.");
      }
    }
  };

  return (
    <Button onClick={handleSync} disabled={status === "queued" || status === "polling"}>
      {status === "polling" ? "Syncing…" : "Sync Shopify Carts"}
    </Button>
  );
};
```

**Show last sync timestamp** next to the button so users know how stale the data is — reduces unnecessary manual syncs.

---

### 4.7 URL Routes

**File:** `backend/bridgeworks_backend/urls.py`

```python
from core.views.sales import shopify_abandoned_checkouts, shopify_sync_abandoned_checkouts

urlpatterns = [
    # Existing
    path("api/sales/shopify/abandoned-checkouts/", shopify_abandoned_checkouts, name="shopify-abandoned-checkouts"),
    # New
    path("api/sales/shopify/abandoned-checkouts/sync/", shopify_sync_abandoned_checkouts, name="shopify-sync-abandoned-checkouts"),
    # New: task status polling endpoint
    path("api/tasks/<str:task_id>/status/", celery_task_status, name="celery-task-status"),
]
```

---

### 4.8 Database Migrations

**File:** `core/models/orders.py` + new migration

#### Zero-Downtime Migration Strategy

Adding indexes to large tables locks the table during migration in some databases. Use `CONCURRENTLY` via Django's `AddIndex` with `concurrently=True`.

```python
# migrations/00XX_add_performance_indexes.py

from django.db import migrations, models

class Migration(migrations.Migration):
    atomic = False  # Required for CONCURRENTLY

    dependencies = [("core", "00XX_previous")]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["created_at"], name="order_created_at_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["current_status_date"], name="order_status_date_idx"),
        ),
        migrations.CreateModel(
            name="ChannelAbandonedCheckout",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("channel", models.ForeignKey("Channel", on_delete=models.CASCADE, db_index=True)),
                ("shopify_id", models.CharField(max_length=100, unique=True)),  # Unique ensures idempotent upserts
                ("token", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True)),
                ("total_price", models.DecimalField(max_digits=12, decimal_places=2)),
                ("checkout_url", models.URLField(max_length=1000, blank=True)),
                ("line_items_count", models.PositiveIntegerField(default=0)),
                ("raw_payload", models.JSONField(default=dict)),  # For debugging / re-processing
                ("last_webhook_topic", models.CharField(max_length=50, blank=True)),
                ("created_at_shopify", models.DateTimeField()),
                ("updated_at_shopify", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="SyncState",
            fields=[
                ("key", models.CharField(max_length=100, primary_key=True)),
                ("last_synced_at", models.DateTimeField(null=True)),
                ("last_sync_records", models.PositiveIntegerField(default=0)),
                ("last_sync_status", models.CharField(max_length=20, default="never")),
            ],
        ),
    ]
```

> **Run migration during low-traffic window.** Even with `CONCURRENTLY`, test on a database clone with production data volumes first to estimate duration.

---

## 5. Async Task Architecture (Celery)

**Why:** The v1.0 plan proposed calling Shopify synchronously inside the Django view. This blocks a Daphne worker for the entire duration of the API call (potentially 10–60 seconds for large stores), which is exactly what this project aims to fix.

### Task: sync_shopify_checkouts_task

```python
# core/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,          # Retry after 60 seconds
    soft_time_limit=300,             # Warn after 5 minutes
    time_limit=360,                  # Kill after 6 minutes
    acks_late=True,                  # Don't acknowledge until done (prevents lost tasks on worker crash)
)
def sync_shopify_checkouts_task(self, channel_id: int, triggered_by: int):
    from core.services.shopify_client import shopify_get_paginated
    from core.models import ChannelAbandonedCheckout, SyncState

    sync_state, _ = SyncState.objects.get_or_create(key=f"shopify_checkouts:{channel_id}")

    try:
        params = {
            "limit": 250,
            "status": "open",
            "updated_at_min": sync_state.last_synced_at.isoformat() if sync_state.last_synced_at else None,
        }
        checkouts = shopify_get_paginated("checkouts", params)

        # Bulk upsert using update_or_create in batches
        upserted = 0
        for batch in _batched(checkouts, 100):
            for c in batch:
                ChannelAbandonedCheckout.objects.update_or_create(
                    shopify_id=str(c["id"]),
                    defaults=_parse_checkout_payload(c),
                )
                upserted += 1

        sync_state.last_synced_at   = now()
        sync_state.last_sync_records = upserted
        sync_state.last_sync_status = "success"
        sync_state.save()

        logger.info("Checkout sync complete", extra={"channel_id": channel_id, "upserted": upserted})

    except Exception as exc:
        sync_state.last_sync_status = "failed"
        sync_state.save()
        raise self.retry(exc=exc)


@shared_task
def process_checkout_webhook_task(topic: str, payload: dict):
    """Separate task for individual webhook events — lightweight."""
    from core.views.webhooks import _handle_checkout_webhook
    _handle_checkout_webhook(topic, payload)
```

### Task Status Polling Endpoint

```python
from celery.result import AsyncResult

def celery_task_status(request, task_id):
    result = AsyncResult(task_id)
    return JsonResponse({
        "task_id": task_id,
        "status": result.status,       # PENDING | STARTED | SUCCESS | FAILURE | RETRY
        "result": str(result.result) if result.failed() else None,
    })
```

---

## 6. Caching Strategy

Use Redis as the cache backend (already required for Celery broker).

```python
# settings/production.py
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "bridgeworks",
        "TIMEOUT": 300,  # Default: 5 minutes
    }
}
```

| View | Cache Key | TTL | Invalidation |
|---|---|---|---|
| `get_stage_summary` | `stage_summary:{channel}:{from}:{to}` | 10 min | None (time-based) |
| `logistics_analytics` | `logistics:{channel}:{from}:{to}` | 5 min | None (time-based) |
| `sales_overview` | `sales_overview:{channel}:{from}:{to}` | 5 min | None (time-based) |
| `abandoned_checkouts` | `abandoned:{channel}:page:{n}` | 1 min | On sync task complete |

**Cache invalidation on sync:**

```python
# In sync_shopify_checkouts_task, after successful upsert:
from django.core.cache import cache
cache.delete_pattern(f"bridgeworks:abandoned:{channel_id}:*")
```

---

## 7. Observability & Alerting

### 7.1 Structured Logging

Use structured logging throughout (JSON format in production for log aggregators like Datadog, CloudWatch, or ELK).

```python
import logging
logger = logging.getLogger(__name__)

# Every significant event includes context fields
logger.info("Shopify sync complete", extra={
    "event":      "shopify_sync_complete",
    "channel_id": channel_id,
    "records":    upserted,
    "duration_s": (now() - start).total_seconds(),
    "triggered_by": triggered_by,
})
```

### 7.2 Key Metrics to Track

| Metric | Alert threshold |
|---|---|
| Shopify sync task duration | > 120 seconds |
| Shopify API 429 rate | > 5 in 10 minutes |
| Webhook verification failures | > 3 in 1 minute |
| Celery queue depth | > 50 tasks |
| DB query duration (slow query log) | > 1 second |
| Daphne worker timeout rate | Any increase post-deploy |

### 7.3 Health Check Endpoint

```python
# api/health/
def health_check(request):
    checks = {}
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
    try:
        cache.set("health", "1", timeout=5)
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    status = 200 if all(v == "ok" for v in checks.values()) else 503
    return JsonResponse(checks, status=status)
```

---

## 8. Zero-Downtime Deployment Strategy

### Step 1 — Pre-deployment (no traffic impact)

1. Run migration with `CONCURRENTLY` indexes on a cloned DB first, measure time.
2. Deploy new code to staging; run full test suite.
3. Ensure Celery workers are deployed **before** the web layer (tasks must be registered before they can be enqueued).

### Step 2 — Deployment order

```
1. Apply database migrations (additive-only, backward-compatible)
2. Deploy Celery worker containers with new task definitions
3. Deploy Django web containers (rolling restart — Daphne keeps serving)
4. Verify health check endpoint returns 200
5. Monitor slow query logs and Sentry for 15 minutes post-deploy
```

### Step 3 — Feature flag (optional but recommended)

Gate the "Sync Shopify Carts" button behind a feature flag. Roll out to internal users first, then 10%, then 100%. This limits exposure if there's a Shopify API misconfiguration.

---

## 9. Rollback Plan

| Scenario | Rollback action |
|---|---|
| Migration causes table lock | Migration is `CONCURRENTLY`; can be cancelled safely. Drop index, restore previous migration state. |
| New sync endpoint errors | Disable URL route via feature flag or nginx block. |
| Celery task failures | Tasks have `max_retries=3`. If all fail, disable the sync button via feature flag. Data in `ChannelAbandonedCheckout` is stale but still served — no outage. |
| Cache poisoning | `cache.clear()` on the Redis keyspace prefix. Views fall back to DB queries. |
| Webhook failures | Shopify retries for 48 hours. Fix the bug and re-deploy. All webhooks will eventually succeed. |
| Full rollback needed | Previous release reads from Shopify live API (v1.0 behavior). `ChannelAbandonedCheckout` table is unused but harmless. |

---

## 10. Verification Plan

### 10.1 Automated Tests

```bash
# Core regression suite
python backend/manage.py test core.tests_logistics_enterprise --verbosity=2

# New tests required (must be written as part of this PR)
python backend/manage.py test core.tests_shopify_sync
python backend/manage.py test core.tests_webhook_security
```

**New test coverage required:**

- `test_webhook_rejects_invalid_hmac` — verify 401 on bad signature
- `test_webhook_accepts_valid_hmac` — verify 200 on valid signature
- `test_sync_endpoint_requires_login` — verify 302/401 for anonymous user
- `test_sync_endpoint_requires_permission` — verify 403 for user without permission
- `test_sync_endpoint_rate_limited` — verify 429 after 5 requests/hour
- `test_checkout_upsert_idempotency` — send same webhook twice, verify single DB record
- `test_delta_sync_uses_last_synced_at` — verify `updated_at_min` param is sent to Shopify

### 10.2 Performance Benchmarking

Before merging, benchmark each modified view with [django-silk](https://github.com/jazzband/django-silk) in staging:

| View | Target p95 response time |
|---|---|
| `TrackingPageOrderListView` (NDR tab) | < 300ms |
| `logistics_analytics` | < 500ms |
| `sales_overview` | < 400ms |
| `shopify_abandoned_checkouts` | < 100ms |
| `sync` endpoint | < 50ms (async, just enqueues) |

### 10.3 Manual Verification Steps

1. Click "Sync Shopify Carts" → verify task appears in Celery Flower dashboard.
2. Verify `ChannelAbandonedCheckout` table is populated after task completes.
3. Reload the abandoned checkouts page → verify data is served from DB (check query count via silk/debug-toolbar).
4. Trigger a Shopify `checkouts/create` webhook (use Shopify's webhook test tool) → verify HMAC validation passes and record appears in DB.
5. Send same webhook again → verify record count stays at 1 (idempotency check).
6. Attempt sync as user without permission → verify 403.
7. Trigger sync 6 times in 1 hour as same user → verify 6th attempt returns 429.

---

## 11. Checklist Before Go-Live

**Security**
- [ ] `SHOPIFY_WEBHOOK_SECRET` set in production environment (not `.env`)
- [ ] `SHOPIFY_API_VERSION` pinned (e.g., `2024-01`)
- [ ] Webhook HMAC verification tested end-to-end in staging with real Shopify test webhooks
- [ ] Sync endpoint 403/429 behavior verified
- [ ] No secrets in source code or logs

**Cost Management**
- [ ] Delta sync confirmed working (`updated_at_min` sent on subsequent syncs)
- [ ] Shopify API call count logged and within expected range
- [ ] Rate limit of 5 syncs/user/hour enforced
- [ ] Celery task time limits set (`time_limit=360`)

**Reliability**
- [ ] Celery workers deployed and `sync_shopify_checkouts_task` registered
- [ ] Task retry behavior tested (kill worker mid-task → verify retry)
- [ ] All new code paths have `try/except` with structured logging
- [ ] Health check endpoint returns 200 with DB and Redis connectivity

**Performance**
- [ ] Migration run on production-volume DB clone — duration acceptable
- [ ] p95 benchmarks met on all modified views in staging
- [ ] Slow query log clean post-deploy (no new slow queries introduced)

**Observability**
- [ ] Alerts configured for sync task duration, 429 rate, webhook verification failures
- [ ] Celery Flower (or equivalent) accessible for task monitoring

**Rollback**
- [ ] Previous release artifact tagged and available for immediate rollback
- [ ] Rollback procedure documented and shared with on-call engineer
- [ ] Feature flag in place for "Sync Shopify Carts" button

---

*End of Production-Grade Implementation Plan v2.0*
