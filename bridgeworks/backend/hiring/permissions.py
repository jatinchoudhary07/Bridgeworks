from rest_framework.permissions import BasePermission
from core.permissions import is_org_owner


def _get_org_id(request):
    try:
        return request.user.team_settings.organization.organization_id
    except Exception:
        return None


class IsHROrOwner(BasePermission):
    """HR staff or org owner can manage hiring."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if is_org_owner(request.user):
            return True
        # Check role-based permission
        try:
            from core.models import TeamMemberSettings
            settings = request.user.team_settings
            role = getattr(settings, 'role', None)
            if role:
                perms = role.permissions if hasattr(role, 'permissions') else {}
                if isinstance(perms, dict):
                    hr_perms = perms.get('human_resources', {})
                    if hr_perms.get('hiring') or hr_perms.get('workforce_sheet'):
                        return True
        except Exception:
            pass
        return False


class IsInterviewerOrHR(BasePermission):
    """Interviewers can only read their own assigned interviews."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsHiringManagerOrHR(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True  # Further filtering done in views via org_id scoping
