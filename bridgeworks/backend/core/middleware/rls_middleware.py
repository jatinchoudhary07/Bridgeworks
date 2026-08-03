from django.db import connection
from django.db.utils import OperationalError
from django.http import JsonResponse
from core.views.helpers import _get_org_id_or_none


class RLSMiddleware:
    """
    Sets the PostgreSQL session configuration variable 'app.org_id' 
    and 'app.bypass_rls = false' for HTTP request connections.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if connection.vendor == 'postgresql':
                org_id = self._get_org_id(request)
                with connection.cursor() as cur:
                    if org_id:
                        # Use parameterized SELECT to safely pass org_id
                        cur.execute("SELECT set_config('app.org_id', %s, true)", [str(org_id)])
                        cur.execute("SELECT set_config('app.bypass_rls', 'false', true)")
                    else:
                        cur.execute("SELECT set_config('app.org_id', '', true)")
                        cur.execute("SELECT set_config('app.bypass_rls', 'false', true)")
        except OperationalError:
            return JsonResponse(
                {"error": "Database is temporarily unavailable. Please try again later."},
                status=503
            )

        return self.get_response(request)

    @staticmethod
    def _get_org_id(request) -> str | None:
        # 1. Resolve standard session / JWT auth
        org_id = _get_org_id_or_none(request)
        if org_id:
            return org_id

        # 2. Check if external auth attached org_id
        if hasattr(request, "org_id") and request.org_id:
            return request.org_id

        return None
