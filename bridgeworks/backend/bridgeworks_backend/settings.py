"""
Django settings for bridgeworks_backend project.
"""

import os
import sys
from datetime import timedelta
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv
from corsheaders.defaults import default_headers  # Importing default CORS headers
import cloudinary as _cloudinary_sdk

# --- Load environment variables ---
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Default to False in production (Render), True locally
DEBUG = 'RENDER' not in os.environ

# --- SECURITY & SECRETS ASSERTIONS ---
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DJANGO_SECRET_KEY") or "your-default-dev-secret-key"

# Fallback to dynamically generated secure key if default or empty
if not SECRET_KEY or SECRET_KEY == "your-default-dev-secret-key":
    secret_file = BASE_DIR / ".django_secret_key"
    if secret_file.exists():
        try:
            with open(secret_file, "r") as f:
                SECRET_KEY = f.read().strip()
        except Exception:
            pass
    if not SECRET_KEY or SECRET_KEY == "your-default-dev-secret-key":
        import secrets
        SECRET_KEY = secrets.token_urlsafe(50)
        try:
            with open(secret_file, "w") as f:
                f.write(SECRET_KEY)
        except Exception:
            pass

FERNET_KEY = os.getenv("FERNET_KEY")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY") or os.getenv("FERNET_KEY")

# Check if currently building or running migrations to prevent blocking build processes
IS_BUILDING = any(x in sys.argv for x in ['collectstatic', 'compilemessages', 'makemigrations', 'migrate', 'assets'])

# Startup check for production environment sanity
if not DEBUG and not IS_BUILDING:
    if not os.getenv("SECRET_KEY") and not os.getenv("DJANGO_SECRET_KEY"):
        raise ValueError("SECRET_KEY or DJANGO_SECRET_KEY environment variable must be set in production to ensure stable sessions!")
    if SECRET_KEY == "your-default-dev-secret-key":
        raise ValueError("SECRET_KEY must be a unique secure value in production!")
    if not FERNET_KEY:
        raise ValueError("FERNET_KEY must be set in production!")
    if not SHOPIFY_API_KEY:
        raise ValueError("SHOPIFY_API_KEY must be set in production!")
    if not SHOPIFY_API_SECRET:
        raise ValueError("SHOPIFY_API_SECRET must be set in production!")

# --- HTTPS PROXY FIX (For Render / Google OAuth) ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'

# --- ALLOWED HOSTS ---
ALLOWED_HOSTS = ['*']

RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)


# --- APPLICATIONS ---
_BASE_APPS = [
    "daphne",  # must be before staticfiles for ASGI runserver
    "channels",

    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",

    # Third Party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "invitations",
    "django_q",
    "axes",
    "encrypted_model_fields",
    "csp",

    # Local
    "core",
    "accounting",
    "inventory",
    "activity_logs",
    "hiring",
    "presence",
    "hr.training",
]

# Only register Cloudinary apps when credentials are available (production)
_CLOUDINARY_APPS = (
    ['cloudinary_storage', 'cloudinary']
    if all([
        os.getenv('CLOUDINARY_CLOUD_NAME'),
        os.getenv('CLOUDINARY_API_KEY'),
        os.getenv('CLOUDINARY_API_SECRET'),
    ])
    else []
)

INSTALLED_APPS = _CLOUDINARY_APPS + _BASE_APPS

# --- MIDDLEWARE ---
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # Must be near the top
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.security_logging.SecurityLoggingMiddleware",  # security logging early
    "csp.middleware.CSPMiddleware",  # CSP early
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",  # Compress responses > 200 bytes
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # Django's built-in CSRF protection
    "django.middleware.http.ConditionalGetMiddleware",  # ETag / 304 support
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.rls_middleware.RLSMiddleware",  # RLS dynamic settings
    "axes.middleware.AxesMiddleware",  # Lockout tracking
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.monitoring.MetricsMiddleware",  # Prometheus request metrics
    "activity_logs.middleware.ActivityLoggerMiddleware",  # Auto-capture API_CALL events
]

# Local dev only: auto-authenticate every request as the seeded admin user
if DEBUG:
    MIDDLEWARE.append("core.middleware.dev_auto_auth.DevAutoAuthMiddleware")

ROOT_URLCONF = "bridgeworks_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bridgeworks_backend.wsgi.application"
ASGI_APPLICATION = "bridgeworks_backend.asgi.application"

# --- CHANNEL LAYERS ---
# Dev/default: in-memory (no Redis needed).
# Prod multi-instance realtime: set TEAM_CHAT_REDIS_URL or CHANNEL_REDIS_URL.
#
# Do not silently reuse REDIS_URL here. The cache Redis connection often has
# short socket timeouts, which makes Channels disconnect WebSockets with
# "Timeout reading from <redis-host>:6379" during deploy/runtime on Render.
_CHANNEL_REDIS_URL = os.getenv("TEAM_CHAT_REDIS_URL") or os.getenv("CHANNEL_REDIS_URL", "")
if _CHANNEL_REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [{
                    "address": _CHANNEL_REDIS_URL,
                    "socket_connect_timeout": int(os.getenv("CHANNEL_REDIS_CONNECT_TIMEOUT", "5")),
                    "socket_timeout": int(os.getenv("CHANNEL_REDIS_SOCKET_TIMEOUT", "30")),
                    "health_check_interval": int(os.getenv("CHANNEL_REDIS_HEALTH_CHECK_INTERVAL", "30")),
                }],
                "capacity": int(os.getenv("CHANNEL_LAYER_CAPACITY", "1000")),
                "expiry": int(os.getenv("CHANNEL_LAYER_EXPIRY", "60")),
                "group_expiry": int(os.getenv("CHANNEL_LAYER_GROUP_EXPIRY", "86400")),
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }



import typing
_db_config = typing.cast(typing.Dict[str, typing.Any], dj_database_url.config(
    default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
    # conn_max_age=0: release connections immediately.
    # SQLite requires 0 to avoid ASGI write-lock contention.
    # Render Postgres also uses 0 for stability on small plans.
    conn_max_age=0
))

# Force SQLite during test suite run to bypass remote DB connection flaky errors
import sys
if 'test' in sys.argv:
    _db_config = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

_db_engine = _db_config.get('ENGINE', '')

# SQLite Concurrency Fix: Extend lock timeout to prevent "database is locked" errors
if 'sqlite' in _db_engine:
    _db_config.setdefault('OPTIONS', {})
    _db_config['OPTIONS']['timeout'] = 30

# PostgreSQL Performance Options
if 'postgresql' in _db_engine or 'postgis' in _db_engine:
    _db_config['ATOMIC_REQUESTS'] = True  # Enabled for database integrity and consistency
    _db_config.setdefault('OPTIONS', {})
    _db_config['OPTIONS'].update({
        'connect_timeout': 10,
        'application_name': 'bridgeworks_api',
        'options': '-c statement_timeout=30000',  # 30s query timeout
        'sslmode': 'require',
    })

    # IPv6/NAT64 Windows DNS Fix: Resolve host to IPv4 to prevent "SSL connection has been closed unexpectedly"
    _db_host = _db_config.get('HOST', '')
    if _db_host and not _db_host.startswith('127.0.0.1') and not _db_host.startswith('localhost'):
        import socket
        try:
            _addr_info = socket.getaddrinfo(_db_host, None, socket.AF_INET)
            if _addr_info:
                _db_config['HOST'] = _addr_info[0][4][0]
        except Exception:
            pass


DATABASES = {
    'default': _db_config,
}

# Expose DB engine name for runtime checks (e.g., full-text search feature gating)
DB_IS_POSTGRES = 'postgresql' in _db_engine or 'postgis' in _db_engine


# --- CACHE CONFIGURATION ---
_CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", os.getenv("REDIS_URL", ""))
if _CACHE_REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _CACHE_REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            },
            'KEY_PREFIX': 'bridgeworks',
            'TIMEOUT': 300,  # Default TTL: 5 minutes
        }
    }
else:
    # Dev fallback: in-memory cache to avoid Windows file locking and latency bottlenecks
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'bridgeworks-locmem-cache',
            'TIMEOUT': 86400,
        }
    }



# --- AUTHENTICATION & PASSWORD VALIDATION ---
AUTHENTICATION_BACKENDS = (
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

SITE_ID = 1


# --- INTERNATIONALIZATION ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# --- STATIC & MEDIA FILES ---
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Force Django to look in App directories (like Admin)
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# =========================================================
# --- STORAGE CONFIGURATION (LOCAL or CLOUDINARY) ---
# =========================================================

_USE_CLOUDINARY = all([
    os.getenv('CLOUDINARY_CLOUD_NAME'),
    os.getenv('CLOUDINARY_API_KEY'),
    os.getenv('CLOUDINARY_API_SECRET'),
])

if _USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
        'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
        'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
    }
    _cloudinary_sdk.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        api_proxy=None,
        timeout=int(os.getenv('CLOUDINARY_API_TIMEOUT', '5')),
    )
    STORAGES = {
        "default": {
            "BACKEND": "core.storage.AutoResourceCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    # LOCAL DEV: serve media from local filesystem — no cloud account needed
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- REST FRAMEWORK ---
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",          # Unauthenticated
        "user": "2000/hour",        # JWT-authenticated users
        "api_key": "10000/hour",    # External API key clients
        "ai_chat": "30/hour",       # AI agent
        "auth": "10/minute",        # login / token-refresh endpoints
        "sensitive": "10/minute",   # strict limits on invite/onboarding
        "session_start": "15/hour", # rate limit for starting attendance sessions
    },
    "NUM_PROXIES": 1,              # Trust first proxy (Render/load balancer) for client IP
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# Local dev overrides — disable throttling and open all API endpoints
if DEBUG:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
    # Allow all requests without authentication in local dev
    REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [
        "rest_framework.permissions.AllowAny",
    ]
    # Add DevForceAuth so DRF wraps request.user properly from middleware
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
        "core.middleware.dev_auto_auth.DevForceAuth",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ]
    # Long-lived tokens so you don't have to re-login during a dev session
    SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=30)
    SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=90)


# Allauth configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_ADAPTER = "core.adapter.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "core.adapter.CustomSocialAccountAdapter"

# Redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173" if DEBUG else "https://bridgeworks-1.onrender.com")
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL", FRONTEND_URL)
ACCOUNT_LOGOUT_REDIRECT_URL = os.getenv("ACCOUNT_LOGOUT_REDIRECT_URL", FRONTEND_URL)

SOCIALACCOUNT_STORE_TOKENS = True  # Store OAuth tokens so Calendar integration can reuse them
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Request calendar.events and gmail scopes at login so we get a single token covering
        # both login, Calendar/Meet, and Gmail. No separate login popups needed.
        "SCOPE": [
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
        "AUTH_PARAMS": {
            "access_type": "offline",  # Get a refresh_token so we can make API calls later
            "prompt": "consent",       # Force consent screen so refresh_token is always returned
        },
    }
}

# --- GMAIL ---
GMAIL_REDIRECT_URI = os.getenv(
    'GMAIL_REDIRECT_URI',
    'http://localhost:8000/api/emails/auth/callback/'
)

# --- GOOGLE CALENDAR / MEET ---
GOOGLE_CALENDAR_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]
GOOGLE_CALENDAR_REDIRECT_URI = os.getenv(
    'GOOGLE_CALENDAR_REDIRECT_URI',
    'http://localhost:8000/api/calendar/callback/'
)


# --- DJANGO Q (Worker) ---
Q_CLUSTER = {
    'name': 'bridgeworks_worker',
    'workers': 2,  # Reduced from 4 to minimize SQLite write contention
    'timeout': 300,  # 5 min — enough for 200-500 order batch fetches
    'retry': 360,    # Must be > timeout
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}


# --- INVITATIONS ---
INVITATIONS_INVITE_ONLY = True
INVITATION_EXPIRY = 7

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'BridgeWorks Ops <ops@jankijewels.com>')

if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")


# =========================================================
# --- CORS & CSRF CONFIGURATION (CRITICAL) ---
# =========================================================

# 1. Who can talk to the API? (CORS)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://bridgeworks-1.onrender.com",
    "http://host.docker.internal:8000",
]
CORS_ALLOW_CREDENTIALS = True

# 2. ALLOW CUSTOM HEADERS (THE FIX)
# We must explicitly allow the timezone header your frontend is sending.
CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-user-timezone",
]

# 3. Who can send cookies/forms? (CSRF)
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://bridgeworks-1.onrender.com",
    "https://bridgeworks-8ba1.onrender.com",
]

# Dynamically trust any allowed hosts to ensure ngrok/local setups bypass CSRF origin checks
for _host in ALLOWED_HOSTS:
    if _host != "*":
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")
        CSRF_TRUSTED_ORIGINS.append(f"http://{_host}")

# --- CRITICAL COOKIE FIX FOR RENDER MULTI-DOMAIN ---
if not DEBUG:
    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = 'None'
    CSRF_COOKIE_SECURE = True
else:
    # Need regular cookies locally via HTTP
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SECURE = False

# Also ensure CORS allows all temporarily to rule out whitelist misconfiguration
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
# (CORS_ALLOW_CREDENTIALS already set above)

# --- SHOPIFY APP CONFIG ---
# (SHOPIFY_API_KEY and SHOPIFY_API_SECRET are set and checked at the top of settings.py)
SHOPIFY_APP_URL = os.getenv("SHOPIFY_APP_URL", "https://bridgeworks-1.onrender.com")
SHOPIFY_SCOPES = os.getenv("SHOPIFY_SCOPES", "read_customers,write_draft_orders,read_draft_orders,read_inventory,read_orders,write_orders,read_products,write_products,read_checkouts,read_fulfillments,write_fulfillments,read_merchant_managed_fulfillment_orders,read_third_party_fulfillment_orders").split(',')


# --- GEMINI AI AGENT ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- CHATWOOT OMNICHANNEL INTEGRATION ---
CHATWOOT_API_URL = os.getenv("CHATWOOT_API_URL", "http://localhost:3000")
CHATWOOT_PLATFORM_KEY = os.getenv("CHATWOOT_PLATFORM_KEY", "")

# --- FLEXYPE INTEGRATION ---
FLEXYPE_WEBHOOK_SECRET = os.getenv("FLEXYPE_WEBHOOK_SECRET", "")


# --- SENTRY ERROR TRACKING ---
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,  # 10% of requests for performance monitoring
        send_default_pii=False,
    )

# ── Axes (Brute force lockout) ────────────────────────────────────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_ENABLE_ADMIN = False  # Don't lock admin UI
AXES_DISABLE_ACCESS_LOG = True

# ── Content Security Policy (CSP) ──────────────────────────────────────────────
# Maintain dynamic script compatibility for the dashboard
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
        'style-src': ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com"),
        'img-src': ("'self'", "https:", "data:", "https://res.cloudinary.com"),
        'connect-src': ("'self'", "https://api.anthropic.com"),
        'font-src': ("'self'", "https://fonts.gstatic.com"),
        'frame-src': ("'none'",),
    }
}


# ── Security Event Logging ────────────────────────────────────────────────────
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
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "axes": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django_q": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}


# ── Attendance Geofence Settings ─────────────────────────────────────────────
ATTENDANCE_LOCATION_JUMP_KM = 100
ATTENDANCE_LOCATION_JUMP_TIME_SECONDS = 3600

# ── Trusted Proxy IPs (Security §1.1) ─────────────────────────────────────────
# List of proxy IPs or CIDR networks that are trusted to set client IP headers.
# If empty, all headers are trusted (default backwards compatibility).
TRUSTED_PROXY_IPS = []


USE_SATURDAY_POLICY = False
USE_HOLIDAY_CALENDAR = False
USE_GRANULAR_DEDUCTIONS = False

