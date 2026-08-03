from rest_framework.exceptions import PermissionDenied, NotFound
from core.views.helpers import _get_org_id_or_none

def _resolve_org_id(request) -> str:
    """
    Resolves the organization ID for the current request context.
    Supports standard JWT/Session auth and external API tokens.
    """
    # 1. Resolve standard user session / JWT auth
    org_id = _get_org_id_or_none(request)
    if org_id:
        return org_id

    # 2. Check if external auth attached org_id
    if hasattr(request, 'org_id') and request.org_id:
        return request.org_id

    raise PermissionDenied("Could not determine organization.")


class OrgScopedMixin:
    """
    Mixin for DRF APIViews.
    Enforces that all queryset and detail queries are scoped to the user's organization.
    """
    def get_org_id(self) -> str:
        if not hasattr(self, "_cached_org_id"):
            self._cached_org_id = _resolve_org_id(self.request)
        return self._cached_org_id

    def get_org_qs(self, model_class, org_field: str = "org_id"):
        """Filters a queryset by org_id."""
        return model_class.objects.filter(**{org_field: self.get_org_id()})

    def get_org_object(self, model_class, pk, org_field: str = "org_id"):
        """Gets a single object belonging to the organization or raises NotFound (404)."""
        try:
            return model_class.objects.get(pk=pk, **{org_field: self.get_org_id()})
        except model_class.DoesNotExist:
            raise NotFound("Not found.")
