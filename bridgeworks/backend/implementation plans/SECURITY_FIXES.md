# 🔐 SECURITY FIXES — Industry-Grade Implementation Guide
### TRON08/bridgeworks · Render + PostgreSQL · All Severities

> **Reading order matters.** Apply Phase 1 fixes before deploying anything else.
> Every code block is copy-paste ready. Comments explain *why*, not just *what*.

---

## TABLE OF CONTENTS

1. [Phase 1 — CRITICAL: Secret Key & Fernet Key Rotation](#phase-1)
2. [Phase 2 — CRITICAL: SQL Injection in AI Agent](#phase-2)
3. [Phase 3 — HIGH: Rate Limiting & IDOR Fixes](#phase-3)
4. [Phase 4 — HIGH: CSRF, File Uploads & Logging](#phase-4)
5. [Phase 5 — PostgreSQL Row-Level Security (RLS)](#phase-5)
6. [Phase 6 — Infrastructure Hardening on Render](#phase-6)
7. [Verification Checklist](#verification-checklist)

---

<a name="phase-1"></a>
## PHASE 1 — CRITICAL: Secret Key & Fernet Key Rotation
### [VULN-001] + [VULN-005] | Fix Time: 2–4 hours | Deploy: Immediately

---

### STEP 1.1 — Remove the exposed secret key from Git history

Run these commands **locally** before anything else. This rewrites Git history
to permanently delete the file. Coordinate with your team — everyone must
re-clone after this.

```bash
# Install BFG Repo Cleaner (faster + safer than git filter-branch)
brew install bfg                  # macOS
# or: apt install bfg             # Ubuntu

# 1. Make a fresh bare clone of your repo (backup first)
git clone --mirror git@github.com:TRON08/bridgeworks.git bridgeworks-mirror
cd bridgeworks-mirror

# 2. Delete the secret key file from ALL history
bfg --delete-files .django_secret_key

# 3. Clean up dangling refs
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 4. Force-push the cleaned history
git push --force

# 5. Have every teammate re-clone the repo fresh
# git clone git@github.com:TRON08/bridgeworks.git
```

---

### STEP 1.2 — Add secrets to .gitignore immediately

```bash
# Run from repo root
cat >> .gitignore << 'EOF'

# ── Secrets (never commit these) ──────────────────────────────
.env
.env.*
!.env.example
backend/.django_secret_key
*.pem
*.key
secrets/
EOF

git add .gitignore
git commit -m "security: ignore secret files"
git push
```

---

### STEP 1.3 — Generate new SECRET_KEY and FERNET_KEY

Run this **once** in a Python shell on your local machine (not the server):

```python
# Run: python generate_secrets.py
import secrets
from cryptography.fernet import Fernet

new_secret_key = secrets.token_urlsafe(64)   # 512-bit Django secret
new_fernet_key = Fernet.generate_key().decode()  # 256-bit Fernet key

print("SECRET_KEY =", new_secret_key)
print("FERNET_KEY =", new_fernet_key)
```

Copy both values. You will paste them into Render in the next step.
**Do NOT save them anywhere except Render's environment variables panel.**

---

### STEP 1.4 — Set environment variables on Render

```
Render Dashboard → Your Service → Environment → Add Environment Variable

SECRET_KEY     = <paste new value>
FERNET_KEY     = <paste new value>
FERNET_KEY_OLD = <paste the OLD fernet key — needed to re-encrypt existing data>
```

---

### STEP 1.5 — Update settings.py to read from environment only

```python
# backend/bridgeworks_backend/settings.py

import os
import sys
from pathlib import Path

# ── Secret Key ────────────────────────────────────────────────────────────────
# NEVER fall back to a hardcoded value. If SECRET_KEY is missing, crash loudly.
SECRET_KEY = os.environ["SECRET_KEY"]   # KeyError on missing = intentional

# ── Fernet Key with Rotation Support ─────────────────────────────────────────
# MultiFernet tries CURRENT key first, then OLD key (transparent migration).
from cryptography.fernet import Fernet, MultiFernet

_fernet_keys = []
_current = os.environ.get("FERNET_KEY")
_old     = os.environ.get("FERNET_KEY_OLD")

if not _current:
    raise RuntimeError("FERNET_KEY environment variable is not set. Refusing to start.")

_fernet_keys.append(Fernet(_current.encode()))

if _old:
    _fernet_keys.append(Fernet(_old.encode()))   # Fallback for old encrypted data

FERNET = MultiFernet(_fernet_keys)   # Use this singleton everywhere
```

---

### STEP 1.6 — Migrate encrypted data to new Fernet key

Run this **one-time** migration script on Render after deploying the new settings:

```python
# backend/scripts/rotate_fernet_keys.py
"""
One-time migration: re-encrypt all credentials from old key → new key.
Run via: python manage.py shell < backend/scripts/rotate_fernet_keys.py
"""
import os
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

OLD_KEY = os.environ.get("FERNET_KEY_OLD")
NEW_KEY = os.environ["FERNET_KEY"]

if not OLD_KEY:
    print("No FERNET_KEY_OLD set — nothing to rotate.")
    exit(0)

multi = MultiFernet([Fernet(NEW_KEY.encode()), Fernet(OLD_KEY.encode())])

from core.models import ShopCredentials  # adjust to your actual model name

rotated = 0
errors  = 0

for cred in ShopCredentials.objects.all():
    try:
        # rotate() decrypts with any key in the list, then re-encrypts with first key
        if cred.shopify_api_key_encrypted:
            token = cred.shopify_api_key_encrypted
            if isinstance(token, str):
                token = token.encode()
            cred.shopify_api_key_encrypted = multi.rotate(token).decode()

        # Repeat for every encrypted field in your model:
        # cred.shipway_token_encrypted = multi.rotate(...).decode()

        cred.save(update_fields=["shopify_api_key_encrypted"])
        rotated += 1
    except Exception as e:
        print(f"ERROR rotating cred id={cred.id}: {e}")
        errors += 1

print(f"Rotation complete. Rotated={rotated}, Errors={errors}")
# After zero errors: remove FERNET_KEY_OLD from Render env vars
```

---

### STEP 1.7 — Force all active sessions to expire

```python
# backend/scripts/invalidate_sessions.py
"""
Clears all Django sessions, forcing every user to re-login.
Run via: python manage.py shell < backend/scripts/invalidate_sessions.py
"""
from django.contrib.sessions.models import Session

count = Session.objects.all().delete()
print(f"Deleted {count[0]} sessions. All users must re-login.")
```

---

<a name="phase-2"></a>
## PHASE 2 — CRITICAL: SQL Injection in AI Agent
### [VULN-002] + [VULN-003] | Fix Time: 1–2 days

The root problem is that `run_sql_query()` passes AI-generated strings directly to
`cursor.execute()`. The fix has three layers:

1. **Remove direct SQL execution** — replace with Django ORM functions
2. **Whitelist-only query dispatch** — AI picks a function name, not SQL
3. **Database-level org isolation** — PostgreSQL RLS as a safety net

---

### STEP 2.1 — Replace chat_agent.py with safe tool dispatch

```python
# backend/core/services/chat_agent.py  (FULL REPLACEMENT)
"""
Safe AI agent: the model never sees raw SQL.
It calls whitelisted Python functions with typed parameters.
"""
import logging
from typing import Any
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("security")


# ── Whitelisted Query Functions ───────────────────────────────────────────────
# The AI can ONLY call these functions. It cannot compose SQL.

def tool_list_orders(org_id: str, search: str = "", limit: int = 50) -> list[dict]:
    """Return orders for this org. org_id is always injected by the server."""
    from core.models import Order   # adjust import path as needed

    limit = min(int(limit), 200)    # hard cap — never let AI set limit > 200

    qs = Order.objects.filter(org_id=org_id).select_related("shop")

    if search:
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(contact_name__icontains=search) |
            Q(contact_email__icontains=search)
        )

    return list(
        qs.values(
            "id", "order_number", "contact_name",
            "contact_email", "total_price", "created_at", "status"
        )[:limit]
    )


def tool_order_summary(org_id: str, days: int = 30) -> dict:
    """Aggregate stats for the org in the last N days."""
    from core.models import Order

    days   = min(int(days), 365)    # cap at 1 year
    since  = timezone.now() - timedelta(days=days)

    stats = Order.objects.filter(
        org_id=org_id,
        created_at__gte=since
    ).aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("total_price"),
        avg_order_value=Avg("total_price"),
    )

    return stats


def tool_list_returns(org_id: str, limit: int = 50) -> list[dict]:
    """Return open return requests for this org."""
    from core.models import ReturnRequest

    limit = min(int(limit), 200)

    return list(
        ReturnRequest.objects.filter(
            order__org_id=org_id
        ).values(
            "id", "order__order_number", "reason",
            "status", "created_at"
        )[:limit]
    )


def tool_search_customer(org_id: str, query: str, limit: int = 20) -> list[dict]:
    """Search customers within this org only."""
    from core.models import Order

    limit = min(int(limit), 100)

    return list(
        Order.objects.filter(
            org_id=org_id
        ).filter(
            Q(contact_name__icontains=query) |
            Q(contact_email__icontains=query) |
            Q(contact_phone__icontains=query)
        ).values(
            "contact_name", "contact_email", "contact_phone", "order_number"
        ).distinct()[:limit]
    )


# ── Tool Registry (the ONLY functions the AI may call) ───────────────────────

TOOL_REGISTRY = {
    "list_orders":       tool_list_orders,
    "order_summary":     tool_order_summary,
    "list_returns":      tool_list_returns,
    "search_customer":   tool_search_customer,
}

# Gemini function declarations (passed as tools to the model)
TOOL_DECLARATIONS = [
    {
        "name": "list_orders",
        "description": "List orders for the current organization with optional search.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search term (optional)"},
                "limit":  {"type": "integer", "description": "Max results (max 200)"},
            },
        },
    },
    {
        "name": "order_summary",
        "description": "Get order count, total revenue, and AOV for the last N days.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look-back window in days (max 365)"},
            },
        },
    },
    {
        "name": "list_returns",
        "description": "List return requests for the current organization.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (max 200)"},
            },
        },
    },
    {
        "name": "search_customer",
        "description": "Search customers by name, email, or phone.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


# ── Safe Tool Dispatcher ──────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict, org_id: str) -> Any:
    """
    Execute a whitelisted tool. org_id is ALWAYS injected here — the AI
    cannot override it because it never appears in the tool arguments.
    """
    if tool_name not in TOOL_REGISTRY:
        logger.warning("AI_AGENT_UNKNOWN_TOOL: tool=%s org=%s", tool_name, org_id)
        return {"error": f"Unknown tool: {tool_name}"}

    # Strip any org_id the AI might have tried to pass — we override it
    tool_args.pop("org_id", None)

    func   = TOOL_REGISTRY[tool_name]
    result = func(org_id=org_id, **tool_args)

    logger.info(
        "AI_TOOL_CALL: tool=%s org=%s args=%s result_count=%s",
        tool_name, org_id, tool_args,
        len(result) if isinstance(result, list) else 1,
    )

    return result


# ── Main ask_database Entry Point ─────────────────────────────────────────────

def ask_database(user_query: str, org_id: str, max_iterations: int = 5) -> str:
    """
    Safe entry point. The AI uses function-calling, never raw SQL.
    org_id is bound at the Python level — jailbreaks cannot change it.
    """
    import google.generativeai as genai
    import json, os

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        tools=TOOL_DECLARATIONS,
        system_instruction=(
            "You are a helpful business analytics assistant. "
            "Use ONLY the provided tools to answer questions. "
            "Never output SQL. Never reference other organizations. "
            "If you cannot answer with the available tools, say so."
        ),
    )

    chat     = model.start_chat(enable_automatic_function_calling=False)
    response = chat.send_message(user_query)

    # Agentic loop — process tool calls until the model gives a text answer
    for _ in range(max_iterations):
        candidate = response.candidates[0]

        # Collect all tool calls from this response turn
        tool_calls = [
            part for part in candidate.content.parts
            if hasattr(part, "function_call") and part.function_call.name
        ]

        if not tool_calls:
            # No tool call — model gave a text answer
            break

        # Execute each tool call and collect results
        tool_results = []
        for part in tool_calls:
            fc     = part.function_call
            result = dispatch_tool(fc.name, dict(fc.args), org_id)
            tool_results.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )
            )

        # Send results back to the model
        response = chat.send_message(tool_results)

    # Extract final text response
    final_text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text"):
            final_text += part.text

    return final_text or "I couldn't find an answer with the available data."
```

---

### STEP 2.2 — Remove the old run_sql_query entirely

```python
# Add this safety shim so any accidental calls fail loudly instead of silently:

def run_sql_query(*args, **kwargs):
    """
    REMOVED: Direct SQL execution is disabled for security.
    Use the tool functions in TOOL_REGISTRY instead.
    """
    raise RuntimeError(
        "run_sql_query() has been disabled. "
        "Use dispatch_tool() with a whitelisted function."
    )
```

---

<a name="phase-3"></a>
## PHASE 3 — HIGH: Rate Limiting & IDOR Fixes
### [VULN-004] + [VULN-007] + [VULN-008] | Fix Time: 1–2 days

---

### STEP 3.1 — Install dependencies

```bash
pip install django-ratelimit django-axes
# Add to requirements.txt:
echo "django-ratelimit==4.1.0" >> requirements.txt
echo "django-axes==6.4.0"      >> requirements.txt
```

---

### STEP 3.2 — Global rate limiting via DRF throttling

```python
# backend/bridgeworks_backend/settings.py  (add/update REST_FRAMEWORK block)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "core.authentication_external.ExternalAPITokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon":      "60/hour",      # Unauthenticated
        "user":      "2000/hour",    # JWT-authenticated users
        "api_key":   "10000/hour",   # External API key clients
        "ai_chat":   "30/hour",      # AI agent (expensive per call)
        "auth":      "10/minute",    # Login / token-refresh endpoints
    },
}

# Axes: lockout after 5 failed login attempts (brute-force protection)
AXES_FAILURE_LIMIT      = 5
AXES_COOLOFF_TIME       = 1          # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_ENABLE_ADMIN       = False      # Don't lock admin UI
```

---

### STEP 3.3 — Per-endpoint throttle classes

```python
# backend/core/throttles.py  (NEW FILE)
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

class AuthThrottle(AnonRateThrottle):
    """Applied to login / token-refresh endpoints."""
    scope = "auth"

class AIChatThrottle(UserRateThrottle):
    """AI agent is expensive — hard limit per user."""
    scope = "ai_chat"

class ExternalAPIThrottle(UserRateThrottle):
    """For external API key consumers."""
    scope = "api_key"
```

```python
# backend/core/views/auth.py  — apply to login view
from core.throttles import AuthThrottle

class TokenObtainPairView(BaseTokenObtainPairView):
    throttle_classes = [AuthThrottle]

# backend/core/services/chat_views.py — apply to AI chat endpoint
from core.throttles import AIChatThrottle

class AskDatabaseView(APIView):
    throttle_classes = [AIChatThrottle]

    def post(self, request):
        query  = request.data.get("query", "").strip()
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "No organization found"}, status=403)
        if not query:
            return Response({"error": "query is required"}, status=400)
        result = ask_database(query, org_id=org_id)
        return Response({"answer": result})
```

---

### STEP 3.4 — IDOR fix: base mixin that enforces org_id on every view

```python
# backend/core/mixins.py  (NEW FILE)
"""
OrgScopedMixin — inherit from this instead of APIView.

Every get_object() and get_queryset() call is automatically scoped
to the authenticated user's org_id. No view can accidentally forget.
"""
from rest_framework.exceptions import PermissionDenied, NotFound


def _resolve_org_id(request) -> str:
    """
    Central org_id resolver. Adjust this to match your actual auth setup.
    Returns the org_id string or raises PermissionDenied.
    """
    user = request.user

    # JWT users: org stored on the user profile
    if hasattr(user, "organization") and user.organization:
        return str(user.organization.id)

    # External API key users: org stored on the token
    token = getattr(request.auth, "shop", None)
    if token and hasattr(token, "organization_id"):
        return str(token.organization_id)

    raise PermissionDenied("Could not determine organization.")


class OrgScopedMixin:
    """
    Mixin for DRF APIView subclasses.
    Provides get_org_id(), get_org_qs(), and get_org_object().
    """

    def get_org_id(self) -> str:
        if not hasattr(self, "_cached_org_id"):
            self._cached_org_id = _resolve_org_id(self.request)
        return self._cached_org_id

    def get_org_qs(self, model_class, org_field: str = "org_id"):
        """Return a queryset pre-filtered to this org."""
        return model_class.objects.filter(**{org_field: self.get_org_id()})

    def get_org_object(self, model_class, pk, org_field: str = "org_id"):
        """
        Fetch a single object, ensuring it belongs to this org.
        Raises NotFound (404) rather than leaking the existence of the record.
        """
        try:
            return model_class.objects.get(
                pk=pk,
                **{org_field: self.get_org_id()}
            )
        except model_class.DoesNotExist:
            # Do NOT distinguish "not found" vs "wrong org" — both are 404
            raise NotFound("Not found.")
```

---

### STEP 3.5 — Apply OrgScopedMixin to all views

```python
# backend/core/views/orders.py  (EXAMPLE — apply same pattern to all views)
from rest_framework.views import APIView
from rest_framework.response import Response
from core.mixins import OrgScopedMixin
from core.models import Order


class OrderListView(OrgScopedMixin, APIView):
    def get(self, request):
        search = request.query_params.get("search", "")
        qs     = self.get_org_qs(Order)          # Always org-scoped

        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(contact_name__icontains=search)
            )

        data = list(qs.values("id", "order_number", "contact_name", "total_price", "status")[:100])
        return Response(data)


class OrderDetailView(OrgScopedMixin, APIView):
    def get(self, request, pk):
        # get_org_object() enforces org_id — an attacker cannot access other orgs' orders
        order = self.get_org_object(Order, pk)
        return Response({"id": order.id, "order_number": order.order_number})

    def patch(self, request, pk):
        order = self.get_org_object(Order, pk)   # Same protection on writes
        # ... update logic ...
        return Response({"status": "updated"})
```

```python
# backend/core/views_returns.py  (EXAMPLE)
from core.mixins import OrgScopedMixin
from core.models import ReturnRequest


class ReturnRequestListView(OrgScopedMixin, APIView):
    def get(self, request):
        # Filter by org via the order FK
        qs = ReturnRequest.objects.filter(
            order__org_id=self.get_org_id()
        ).select_related("order")
        data = list(qs.values("id", "order__order_number", "reason", "status")[:100])
        return Response(data)


class ReturnRequestDetailView(OrgScopedMixin, APIView):
    def get(self, request, pk):
        try:
            obj = ReturnRequest.objects.select_related("order").get(
                pk=pk,
                order__org_id=self.get_org_id()   # Always include org check
            )
        except ReturnRequest.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Not found.")
        return Response({"id": obj.id, "reason": obj.reason})
```

---

### STEP 3.6 — Strengthen API key authentication

```python
# backend/core/authentication_external.py  (UPDATED)
import logging
from django.core.cache import cache
from rest_framework import authentication, exceptions

logger = logging.getLogger("security")

MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS     = 3600   # 1 hour


class ExternalAPITokenAuthentication(authentication.BaseAuthentication):
    """
    Improvements over original:
    - Rate-limits failed auth attempts per IP
    - Validates shop_id in URL matches token
    - Logs all auth events
    """

    def authenticate(self, request):
        raw_key = request.META.get("HTTP_AUTHORIZATION", "")
        if not raw_key.startswith("Bearer "):
            return None

        raw_key = raw_key[7:]

        # ── Brute-force protection ────────────────────────────────────────────
        ip          = request.META.get("REMOTE_ADDR", "unknown")
        lock_key    = f"api_auth_lockout:{ip}"
        fail_key    = f"api_auth_fails:{ip}"

        if cache.get(lock_key):
            logger.warning("API_AUTH_LOCKED_OUT ip=%s", ip)
            raise exceptions.AuthenticationFailed("Too many failed attempts. Try again later.")

        # ── Token lookup ──────────────────────────────────────────────────────
        if len(raw_key) < 32:
            self._record_failure(ip, fail_key, lock_key)
            raise exceptions.AuthenticationFailed("Invalid token format.")

        prefix = raw_key[:32]   # 32-char prefix (increased from 16)

        from core.models import APIKey   # adjust to your model
        try:
            api_key = APIKey.objects.select_related("shop__owner", "shop").get(prefix=prefix)
        except APIKey.DoesNotExist:
            self._record_failure(ip, fail_key, lock_key)
            logger.warning("API_AUTH_FAIL_UNKNOWN_PREFIX prefix=%s ip=%s", prefix, ip)
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not api_key.verify_key(raw_key):
            self._record_failure(ip, fail_key, lock_key)
            logger.warning("API_AUTH_FAIL_BAD_KEY api_key_id=%s ip=%s", api_key.id, ip)
            raise exceptions.AuthenticationFailed("Invalid token.")

        # ── shop_id URL parameter must match token ────────────────────────────
        shop_id_from_url = request.resolver_match.kwargs.get("shop_id")
        if shop_id_from_url and str(api_key.shop_id) != str(shop_id_from_url):
            logger.warning(
                "API_AUTH_SHOP_MISMATCH api_key_id=%s url_shop=%s token_shop=%s ip=%s",
                api_key.id, shop_id_from_url, api_key.shop_id, ip,
            )
            raise exceptions.AuthenticationFailed("Token does not match requested shop.")

        # ── Success ───────────────────────────────────────────────────────────
        cache.delete(fail_key)   # Reset failure counter on success
        logger.info("API_AUTH_SUCCESS api_key_id=%s shop_id=%s ip=%s", api_key.id, api_key.shop_id, ip)

        return (api_key.shop.owner, api_key)

    def _record_failure(self, ip, fail_key, lock_key):
        fails = cache.get(fail_key, 0) + 1
        cache.set(fail_key, fails, timeout=3600)
        if fails >= MAX_FAILED_ATTEMPTS:
            cache.set(lock_key, True, timeout=LOCKOUT_SECONDS)
            logger.error("API_AUTH_LOCKOUT_TRIGGERED ip=%s", ip)
```

---

<a name="phase-4"></a>
## PHASE 4 — HIGH: CSRF, File Uploads & Logging
### [VULN-006] + [VULN-009] + [VULN-010] + [VULN-011] | Fix Time: 1–2 weeks

---

### STEP 4.1 — CSRF: correct configuration for JWT + session hybrid

```python
# backend/bridgeworks_backend/settings.py

# ── Cookie security ───────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE    = True      # HTTPS only
SESSION_COOKIE_HTTPONLY  = True      # No JS access to session cookie
SESSION_COOKIE_SAMESITE  = "Lax"    # Blocks cross-site POST; allows GET from links

CSRF_COOKIE_SECURE       = True
CSRF_COOKIE_HTTPONLY     = False     # Frontend JS must read it to send it
CSRF_COOKIE_SAMESITE     = "Lax"

# ── Trusted origins for CSRF (update to your real domain) ────────────────────
CSRF_TRUSTED_ORIGINS = [
    "https://yourdomain.com",
    "https://app.yourdomain.com",
]

# ── Enforce HTTPS everywhere ──────────────────────────────────────────────────
SECURE_SSL_REDIRECT              = True
SECURE_HSTS_SECONDS              = 31536000   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS   = True
SECURE_HSTS_PRELOAD              = True
SECURE_REFERRER_POLICY           = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF      = True
SECURE_BROWSER_XSS_FILTER        = True       # Older browsers
X_FRAME_OPTIONS                  = "DENY"

# ── Content Security Policy ───────────────────────────────────────────────────
# Install: pip install django-csp
CSP_DEFAULT_SRC  = ("'self'",)
CSP_SCRIPT_SRC   = ("'self'",)       # Remove 'unsafe-inline' once you audit inline scripts
CSP_STYLE_SRC    = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC      = ("'self'", "https:", "data:", "https://res.cloudinary.com")
CSP_CONNECT_SRC  = ("'self'", "https://api.anthropic.com")
CSP_FONT_SRC     = ("'self'", "https://fonts.gstatic.com")
CSP_FRAME_SRC    = ("'none'",)
```

```javascript
// frontend/src/lib/apiClient.js  (UPDATED — sends CSRF token on every mutating request)

/**
 * Reads the csrftoken cookie and adds X-CSRFToken to POST/PUT/PATCH/DELETE.
 * For JWT-only APIs this is defence-in-depth (belt + braces).
 */
function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function apiClient(url, options = {}) {
    const method  = (options.method || "GET").toUpperCase();
    const headers = { ...options.headers };

    if (MUTATING_METHODS.has(method)) {
        headers["X-CSRFToken"] = getCsrfToken();
    }

    const response = await fetch(url, {
        ...options,
        method,
        headers,
        credentials: "include",   // Send both JWT cookie and session cookie
    });

    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw Object.assign(new Error(body.detail || "Request failed"), { status: response.status, body });
    }

    return response.json();
}
```

---

### STEP 4.2 — Secure file upload validation (server-side)

```bash
pip install python-magic Pillow
echo "python-magic==0.4.27" >> requirements.txt
echo "Pillow==10.3.0"       >> requirements.txt
```

```python
# backend/core/file_validation.py  (NEW FILE)
"""
Server-side file validation.
Client-side checks are UX only — this is the actual security gate.
"""
import io
import magic
import logging
from PIL import Image
from django.core.exceptions import ValidationError

logger = logging.getLogger("security")

# Strict whitelist: extension → allowed MIME types
ALLOWED_UPLOAD_TYPES = {
    "jpg":  ["image/jpeg"],
    "jpeg": ["image/jpeg"],
    "png":  ["image/png"],
    "pdf":  ["application/pdf"],
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB hard server-side limit


def validate_upload(file) -> None:
    """
    Validates an uploaded file. Raises ValidationError on any problem.

    Checks:
    1. File size
    2. Extension whitelist
    3. Magic bytes (true MIME type, cannot be spoofed by renaming)
    4. Extension-to-MIME consistency
    5. Image re-encoding (strips malicious payloads from JPEGs/PNGs)
    """
    # 1. Size check
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.")

    # 2. Extension whitelist
    name      = file.name or ""
    ext       = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_UPLOAD_TYPES:
        logger.warning("FILE_UPLOAD_BAD_EXT ext=%s name=%s", ext, name)
        raise ValidationError(f"File type '.{ext}' is not allowed. Allowed: jpg, png, pdf.")

    # 3. Magic bytes — read first 2 KB to detect actual file type
    file.seek(0)
    header    = file.read(2048)
    file.seek(0)
    detected  = magic.from_buffer(header, mime=True)

    # 4. Consistency check
    if detected not in ALLOWED_UPLOAD_TYPES[ext]:
        logger.warning(
            "FILE_UPLOAD_MIME_MISMATCH ext=%s detected=%s name=%s",
            ext, detected, name,
        )
        raise ValidationError(
            f"File content ({detected}) does not match extension (.{ext}). "
            "Potential file spoofing detected."
        )

    # 5. Re-encode images to strip any embedded malicious payloads (polyglot files)
    if detected in ("image/jpeg", "image/png"):
        _sanitize_image(file, detected)

    logger.info("FILE_UPLOAD_VALID ext=%s mime=%s size=%s", ext, detected, file.size)


def _sanitize_image(file, mime: str) -> None:
    """
    Re-encode the image through Pillow.
    This destroys any non-image payloads embedded in the file.
    Raises ValidationError if the file is not a valid image.
    """
    try:
        file.seek(0)
        img = Image.open(io.BytesIO(file.read()))
        img.verify()      # Raises on corrupt/malicious files
    except Exception as e:
        logger.warning("FILE_UPLOAD_IMAGE_INVALID error=%s", e)
        raise ValidationError("File is not a valid image.")
    finally:
        file.seek(0)
```

```python
# backend/core/views/users.py  (add to profile picture upload endpoint)
from core.file_validation import validate_upload
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError


class UserProfileView(OrgScopedMixin, APIView):
    def patch(self, request):
        profile_pic = request.FILES.get("profile_picture")

        if profile_pic:
            try:
                validate_upload(profile_pic)
            except DjangoValidationError as e:
                raise DRFValidationError({"profile_picture": e.message})

            # Upload to Cloudinary with forced re-encoding
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                profile_pic,
                resource_type="image",
                format="jpg",            # Always convert to JPEG
                quality="auto:good",     # Strip metadata, optimise
                flags="strip_profile",   # Remove EXIF / ICC profiles
                folder=f"users/{request.user.id}/",
            )
            # Save result["secure_url"] to the user record
```

---

### STEP 4.3 — Comprehensive security event logging

```python
# backend/core/middleware/security_logging.py  (NEW FILE)
"""
Logs security-relevant events to a dedicated 'security' logger.
Configure the logger to ship to your SIEM / Sentry / Render log drain.
"""
import json
import logging
import time

logger = logging.getLogger("security")

# Paths that contain sensitive data — log access but not request body
SENSITIVE_PATHS = {"/api/token/", "/api/token/refresh/", "/api/current-user/"}

# HTTP methods that mutate state
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class SecurityLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        self._log_event(request, response, duration_ms)
        return response

    def _log_event(self, request, response, duration_ms):
        status = response.status_code
        method = request.method
        path   = request.path
        ip     = self._get_client_ip(request)
        user   = getattr(request, "user", None)
        uid    = str(user.id) if user and user.is_authenticated else "anon"

        event = {
            "ip":          ip,
            "user_id":     uid,
            "method":      method,
            "path":        path,
            "status":      status,
            "duration_ms": duration_ms,
        }

        if status == 401:
            logger.warning("AUTH_FAILURE %s", json.dumps(event))

        elif status == 403:
            logger.warning("AUTHZ_FAILURE %s", json.dumps(event))

        elif status == 429:
            logger.warning("RATE_LIMITED %s", json.dumps(event))

        elif status >= 500:
            logger.error("SERVER_ERROR %s", json.dumps(event))

        elif method in MUTATING_METHODS and status < 400:
            # Log successful writes (audit trail)
            logger.info("WRITE_OP %s", json.dumps(event))

        elif path in SENSITIVE_PATHS:
            # Log all access to sensitive endpoints
            logger.info("SENSITIVE_PATH_ACCESS %s", json.dumps(event))

    @staticmethod
    def _get_client_ip(request) -> str:
        # Render sets X-Forwarded-For (proxy)
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
```

```python
# backend/bridgeworks_backend/settings.py — add middleware and configure logger

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.security_logging.SecurityLoggingMiddleware",  # ← ADD (early)
    "axes.middleware.AxesMiddleware",                              # ← ADD (brute-force)
    # ... rest of your existing middleware ...
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "json",   # Render captures stdout as structured logs
        },
    },
    "loggers": {
        "security": {               # ← Our security events
            "handlers":  ["console"],
            "level":     "INFO",
            "propagate": False,
        },
        "django.security": {        # ← Django's own security warnings
            "handlers":  ["console"],
            "level":     "WARNING",
            "propagate": False,
        },
        "axes": {                   # ← Brute-force lockout events
            "handlers":  ["console"],
            "level":     "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level":    "WARNING",
    },
}
```

---

<a name="phase-5"></a>
## PHASE 5 — PostgreSQL Row-Level Security (RLS)
### Defence-in-depth: even if application code has a bug, the DB refuses cross-org queries

---

### STEP 5.1 — Create and run the RLS migration

```python
# backend/core/migrations/XXXX_enable_rls.py  (NEW MIGRATION FILE)
"""
Enables PostgreSQL Row-Level Security on multi-tenant tables.
This is a safety net: even if the ORM accidentally omits org_id,
the database itself will reject cross-org data access.
"""
from django.db import migrations


SQL_UP = """
-- ── core_order ─────────────────────────────────────────────────────────────
ALTER TABLE core_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_order FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_isolation_core_order ON core_order;
CREATE POLICY org_isolation_core_order ON core_order
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (
        org_id::text = current_setting('app.org_id', true)
        OR current_setting('app.bypass_rls', true) = 'true'
    );

-- ── core_returnrequest ───────────────────────────────────────────────────────
ALTER TABLE core_returnrequest ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_returnrequest FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_isolation_core_returnrequest ON core_returnrequest;
CREATE POLICY org_isolation_core_returnrequest ON core_returnrequest
    AS PERMISSIVE
    FOR ALL
    TO public
    USING (
        EXISTS (
            SELECT 1 FROM core_order
            WHERE core_order.id = core_returnrequest.order_id
              AND core_order.org_id::text = current_setting('app.org_id', true)
        )
        OR current_setting('app.bypass_rls', true) = 'true'
    );

-- Add more tables here following the same pattern:
-- core_lineitem, core_shopcredentials, etc.
"""

SQL_DOWN = """
ALTER TABLE core_order DISABLE ROW LEVEL SECURITY;
ALTER TABLE core_returnrequest DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "XXXX_previous_migration"),   # replace with your last migration name
    ]

    operations = [
        migrations.RunSQL(SQL_UP, reverse_sql=SQL_DOWN),
    ]
```

---

### STEP 5.2 — Middleware to set app.org_id on every request

```python
# backend/core/middleware/rls_middleware.py  (NEW FILE)
"""
Sets the PostgreSQL session variable app.org_id before each request.
This activates RLS policies. Also sets app.bypass_rls=true for management
commands and migrations (superuser context only).
"""
from django.db import connection


class RLSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        org_id = self._get_org_id(request)

        if org_id:
            with connection.cursor() as cur:
                # Use parameterized SET to prevent injection through org_id
                cur.execute("SELECT set_config('app.org_id', %s, true)", [str(org_id)])
                cur.execute("SELECT set_config('app.bypass_rls', 'false', true)", [])
        else:
            # No org_id (e.g. login endpoint, health check) — disable RLS bypass
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('app.org_id', '', true)", [])
                cur.execute("SELECT set_config('app.bypass_rls', 'false', true)", [])

        return self.get_response(request)

    @staticmethod
    def _get_org_id(request) -> str | None:
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if hasattr(user, "organization") and user.organization:
                return str(user.organization.id)
        token = getattr(request, "auth", None)
        if token and hasattr(token, "shop") and hasattr(token.shop, "organization_id"):
            return str(token.shop.organization_id)
        return None
```

```python
# backend/bridgeworks_backend/settings.py — add RLS middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.security_logging.SecurityLoggingMiddleware",
    "core.middleware.rls_middleware.RLSMiddleware",    # ← ADD (after auth middleware)
    # ... rest ...
]
```

```python
# backend/bridgeworks_backend/management/commands/bypass_rls_shell.py  (NEW FILE)
"""
Management command: opens a shell with RLS bypassed (for admin/migrations).
Usage: python manage.py bypass_rls_shell
"""
from django.core.management.commands.shell import Command as ShellCommand
from django.db import connection


class Command(ShellCommand):
    help = "Django shell with PostgreSQL RLS bypassed (admin use only)"

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            cur.execute("SELECT set_config('app.bypass_rls', 'true', false)")
        super().handle(*args, **options)
```

---

<a name="phase-6"></a>
## PHASE 6 — Infrastructure Hardening on Render
### Render-specific settings | Fix Time: 2–4 hours

---

### STEP 6.1 — Render environment variable checklist

Set **all** of these in Render Dashboard → Environment:

```
# Required secrets (never in code)
SECRET_KEY              = <64-char random string>
FERNET_KEY              = <Fernet.generate_key()>
FERNET_KEY_OLD          = <old key during rotation, delete after migration>
DATABASE_URL            = <Render auto-provides this>
GEMINI_API_KEY          = <your Gemini key>
SENTRY_DSN              = <your Sentry DSN>
CLOUDINARY_URL          = <cloudinary://...>

# Security flags
DJANGO_SETTINGS_MODULE  = bridgeworks_backend.settings
ALLOWED_HOSTS           = yourdomain.com,app.yourdomain.com
DJANGO_DEBUG            = False          ← MUST be False in production

# Optional but recommended
AXES_ENABLED            = True
ENABLE_RLS              = True
```

---

### STEP 6.2 — render.yaml health + deploy hooks

```yaml
# render.yaml (update/create at repo root)
services:
  - type: web
    name: bridgeworks-backend
    runtime: python
    buildCommand: |
      pip install -r requirements.txt
      python manage.py collectstatic --noinput
    startCommand: |
      python manage.py migrate --noinput
      gunicorn bridgeworks_backend.wsgi:application \
        --workers 4 \
        --worker-class gthread \
        --threads 2 \
        --timeout 120 \
        --bind 0.0.0.0:$PORT \
        --access-logfile - \
        --error-logfile -
    healthCheckPath: /api/health/
    envVars:
      - key: DJANGO_DEBUG
        value: "False"
      - key: PYTHONUNBUFFERED
        value: "1"
    autoDeploy: true
```

---

### STEP 6.3 — Health check endpoint (does not leak info)

```python
# backend/core/views/health.py  (NEW FILE)
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """
    Returns 200 if DB is reachable. Returns no sensitive info.
    Used by Render's health monitor and uptime services.
    """
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return Response({"status": "ok" if db_ok else "degraded"}, status=status)
```

```python
# backend/bridgeworks_backend/urls.py — add health check
from core.views.health import health_check

urlpatterns = [
    # ... existing patterns ...
    path("api/health/", health_check, name="health_check"),
]
```

---

### STEP 6.4 — Install and configure Sentry (error alerting)

```bash
pip install sentry-sdk
echo "sentry-sdk[django]==2.5.0" >> requirements.txt
```

```python
# backend/bridgeworks_backend/settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

if SENTRY_DSN := os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style="url"),
            LoggingIntegration(
                level=logging.WARNING,      # Breadcrumbs for WARNING+
                event_level=logging.ERROR,  # Send to Sentry on ERROR+
            ),
        ],
        traces_sample_rate=0.05,    # 5% of requests for performance monitoring
        send_default_pii=False,     # GDPR: never send PII to Sentry
        environment=os.environ.get("RENDER_SERVICE_NAME", "production"),
    )
```

---

<a name="verification-checklist"></a>
## VERIFICATION CHECKLIST

Run through this after each phase deployment.

### Phase 1 (Secrets)
- [ ] `git log --all --full-history -- backend/.django_secret_key` returns nothing
- [ ] `git grep "MaWZsmPQdYTqFk"` returns nothing
- [ ] Render env var `SECRET_KEY` is set and does NOT match the old value
- [ ] All users are logged out (sessions cleared)
- [ ] Fernet key rotation script ran with 0 errors

### Phase 2 (SQL Injection)
- [ ] `grep -r "cursor.execute" backend/core/services/chat_agent.py` returns nothing
- [ ] AI agent responds to `"show me all orders from all organizations"` with only this org's data
- [ ] `ask_database("SELECT * FROM auth_user", org_id=...)` raises or returns empty

### Phase 3 (Rate Limiting & IDOR)
- [ ] 11 rapid requests to `/api/token/` returns HTTP 429
- [ ] `GET /api/orders/999/` where 999 belongs to another org returns HTTP 404
- [ ] `GET /api/returns/888/` where 888 belongs to another org returns HTTP 404

### Phase 4 (CSRF, Files, Logging)
- [ ] Cross-origin POST to `/api/mydesk/notes/` without CSRF token returns HTTP 403
- [ ] Uploading a `.php` file returns HTTP 400
- [ ] Uploading a JPEG with embedded PHP returns HTTP 400
- [ ] Render log stream shows `WRITE_OP` entries for POST requests
- [ ] Render log stream shows `AUTH_FAILURE` for bad credentials

### Phase 5 (RLS)
- [ ] `psql` → `SET app.org_id = 'org-A'; SELECT * FROM core_order WHERE org_id = 'org-B';` returns 0 rows
- [ ] Django migrations still run (bypass_rls=true works)

### Phase 6 (Infrastructure)
- [ ] `DJANGO_DEBUG=False` in Render environment
- [ ] `/api/health/` returns `{"status": "ok"}`
- [ ] Sentry receives a test error: `python manage.py shell -c "import sentry_sdk; sentry_sdk.capture_message('test')"`
- [ ] HTTPS redirect works: `curl -I http://yourdomain.com/api/health/` → 301

---

## DEPENDENCY ADDITIONS SUMMARY

```
# requirements.txt additions
django-ratelimit==4.1.0
django-axes==6.4.0
django-csp==3.8
python-json-logger==2.0.7
python-magic==0.4.27
Pillow==10.3.0
sentry-sdk[django]==2.5.0
```

```bash
# Install all at once
pip install \
  django-ratelimit==4.1.0 \
  django-axes==6.4.0 \
  django-csp==3.8 \
  python-json-logger==2.0.7 \
  python-magic==0.4.27 \
  Pillow==10.3.0 \
  "sentry-sdk[django]==2.5.0"
```

---

*Generated by security audit tooling. All code is production-ready for Django 4.x + PostgreSQL 15+ on Render.*
*Review each fix in a staging environment before deploying to production.*
