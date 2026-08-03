import logging

from rest_framework.permissions import BasePermission

from core.permissions import _check_granular_permission, is_org_owner

logger = logging.getLogger(__name__)


class IsHRManager(BasePermission):
    """
    Grants access to HR Managers.

    Uses the same hybrid RBAC/legacy permission check as the rest of the
    application.  Checks the 'human_resources:workforce_sheet' RBAC identifier
    (which is already in LEGACY_TO_RBAC_MAP) so it works for both old JSON
    permissions and the new Role Editor.
    """

    message = "Access denied: HR Manager role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Org owners always have access
        if is_org_owner(user):
            return True

        return _check_granular_permission(
            user, "human_resources", "workforce", request.method
        )
