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

        try:
            self._log_event(request, response, duration_ms)
        except Exception:
            pass
        return response

    def _log_event(self, request, response, duration_ms):
        status = response.status_code
        method = request.method
        path = request.path
        ip = self._get_client_ip(request)
        user = getattr(request, "user", None)
        
        is_auth = False
        if user:
            try:
                is_auth = user.is_authenticated
            except Exception:
                is_auth = False

        if is_auth:
            try:
                uid = str(user.id)
            except Exception:
                uid = "anon"
        else:
            uid = "anon"

        event = {
            "ip": ip,
            "user_id": uid,
            "method": method,
            "path": path,
            "status": status,
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
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
