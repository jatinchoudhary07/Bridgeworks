import logging
from rest_framework.permissions import BasePermission
from .models import TeamMemberSettings

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. CENTRALIZED HELPER (The Brain)
# ==============================================================================

# Mapping from legacy (business_area, feature_key) pairs to the new
# Enterprise RBAC permission identifiers used in the Role Editor.
# Format: (legacy_area, legacy_feature) -> 'module:page:action'
LEGACY_TO_RBAC_MAP = {
    # Operations & Fulfillment
    ('operations_fulfillment', 'calling_sheet'):     'operations_fulfillment:calling_sheet',
    ('operations_fulfillment', 'packaging_sheet'):   'operations_fulfillment:packaging_sheet',
    ('operations_fulfillment', 'batch_creation'):    'operations_fulfillment:confirmation',
    ('operations_fulfillment', 'awb_sheet'):         'operations_fulfillment:awb_sheet',
    ('operations_fulfillment', 'confirmation_sheet'):'operations_fulfillment:confirmation',
    ('operations_fulfillment', 'pending_orders'):    'operations_fulfillment:pending_orders',
    ('operations_fulfillment', 'manifest_sheet'):    'operations_fulfillment:manifest_sheet',
    ('operations_fulfillment', 'confirmation_stats'): 'operations_fulfillment:confirmation',
    # Analytics & Reporting
    ('analytics_reporting', 'view_kpis'):            'analytics_reporting:view_kpis',
    ('analytics_reporting', 'view_audit_logs'):      'analytics_reporting:view_audit_logs',
    ('analytics_reporting', 'analytics'):            'analytics_reporting:view_kpis',
    # Customer Experience
    ('customer_experience', 'case_file_sheet'):      'customer_experience:case_file_sheet',
    # Marketing & Growth
    ('marketing_growth', 'view_marketing'):          'marketing_growth:overview',
    # Tracking / Logistics
    ('tracking_module', 'view_tracking'):            'logistics:lm_sheet',
    ('tracking_module', 'ndr_action'):               'logistics:ndr_action',
    # Human Resources
    ('human_resources', 'workforce'):                'human_resources:workforce_sheet',
    ('human_resources', 'master_task_tracker'):      'human_resources:master_task_tracker',
    # Production
    ('production_module', 'view_production'):        'production_module:view_production',
    # Finance COD Remittance relocation
    ('finance_accounting', 'cod_reconciliation'):    'finance:cod_reconciliation',
}


def is_org_owner(user):
    """
    Returns True if the user has full owner-level access.
    This includes: superusers, the original founder (shop_credentials owner),
    and co-founders (WorkspaceMembership.is_co_founder=True).
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if hasattr(user, 'shop_credentials'):
        return True
    # Check co-founder status via WorkspaceMembership
    try:
        from core.models.users import WorkspaceMembership
        if WorkspaceMembership.objects.filter(user=user, is_co_founder=True).exists():
            return True
    except Exception:
        pass
    return False


def _check_granular_permission(user, business_area, feature_key, method='GET'):
    """
    Hybrid permission check: grants access if the user is authorized
    through EITHER the legacy JSON permissions OR the new Role-based
    RBAC system.
    
    The check is action-aware: it determines whether to check for
    :view, :create, :edit, or :delete based on the HTTP method.
    """
    if not user or not user.is_authenticated:
        return False

    if is_org_owner(user):
        return True

    # --- 1. Map Method to Action ---
    action = 'view'
    if method == 'POST':
        action = 'create'
    elif method in ['PUT', 'PATCH']:
        action = 'edit'
    elif method == 'DELETE':
        action = 'delete'

    # --- 2. Check Legacy JSON permissions (TeamMemberSettings) ---
    # Legacy system was mostly binary (Yes/No for an entire page),
    # so we treat any True value as having all permissions in legacy mode.
    try:
        settings = getattr(user, 'team_settings', None)
        if settings:
            perms = settings.granular_permissions or {}
            area = perms.get(business_area, {})
            if isinstance(area, dict) and area.get(feature_key, False):
                return True
    except Exception:
        pass

    # --- 3. Check New Enterprise RBAC (WorkspaceMembership -> Role -> Permission) ---
    try:
        from core.models.users import WorkspaceMembership

        membership = (
            WorkspaceMembership.objects
            .filter(user=user)
            .select_related('role')
            .first()
        )
        if membership and membership.role:
            role_perms = set(
                membership.role.permissions.values_list('identifier', flat=True)
            )

            # Wildcard — full access
            if '*:*:*' in role_perms:
                return True

            # Direct RBAC identifier via the mapping table + action
            prefix = LEGACY_TO_RBAC_MAP.get((business_area, feature_key))
            if prefix:
                rbac_id = f"{prefix}:{action}"
                if rbac_id in role_perms:
                    return True

            # Fallback: auto-derive identifier as "area:feature:action"
            derived_id = f"{business_area}:{feature_key}:{action}"
            if derived_id in role_perms:
                return True

    except Exception as e:
        logger.debug(f"RBAC permission check error: {e}")

    return False


# ==============================================================================
# 2. PERMISSION CLASSES (The Gatekeepers)
# ==============================================================================

class IsOrganizationOwner(BasePermission):
    """
    Strict access: Only for the Founder (Owner) or Superuser.
    Used for: Team Management, Billing, Sensitive Settings.
    """
    message = "Access denied: This feature is for Organization Owners only."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return is_org_owner(user)


class IsAllowedToCall(BasePermission):
    """Calling Sheet Access (Operations)"""
    message = "Access denied: You do not have permission for the Calling Sheet."
    
    def has_permission(self, request, view):
        return _check_granular_permission(request.user, 'operations_fulfillment', 'calling_sheet', request.method)


class IsAllowedToBatch(BasePermission):
    """Batch Creation Access (Operations) - REWRITTEN FOR EFFICIENCY"""
    message = "Access denied: You do not have permission to create Batches."

    def has_permission(self, request, view):
        # Now uses the standard helper instead of manual checks
        return _check_granular_permission(request.user, 'operations_fulfillment', 'batch_creation', request.method)


class IsPackagingAgent(BasePermission):
    """Packaging Sheet Access"""
    message = "Access denied: You do not have permission for the Packaging Workflow."

    def has_permission(self, request, view):
        return _check_granular_permission(request.user, 'operations_fulfillment', 'packaging_sheet', request.method)


class IsFinanceAnalyst(BasePermission):
    """Analytics & KPI Access"""
    message = "Access denied: You do not have access to Financial Analytics."

    def has_permission(self, request, view):
        return _check_granular_permission(request.user, 'analytics_reporting', 'view_kpis', request.method)


class IsAllowedCustomerExperience(BasePermission):
    """Customer Case File Access"""
    message = 'You do not have permission to access the Customer Experience module.'

    def has_permission(self, request, view):
        return _check_granular_permission(request.user, 'customer_experience', 'case_file_sheet', request.method)


class IsMarketingAnalyst(BasePermission):
    """Marketing & Growth Module Access"""
    message = "Access denied: You do not have permission for the Marketing & Growth module."

    def has_permission(self, request, view):
        return _check_granular_permission(request.user, 'marketing_growth', 'view_marketing', request.method)


# ==============================================================================
# 3. ENTERPRISE RBAC (NEW STRING-BASED LOGIC)
# ==============================================================================

# ── New Logistics Enterprise Permission Identifiers ───────────────────────────
# These are used by HasModulePermission on the new logistics views.
# Must be seeded as RolePermission records to grant access to non-owner users.
#
# SLA Dashboard:
#   logistics:sla_dashboard:view     — View SLA KPIs, performance tables, contracts
#   logistics:sla_dashboard:manage   — Create / update / delete SLA contracts
#
# Exception Management Center:
#   logistics:exception_center:view  — View exceptions, summary
#   logistics:exception_center:manage — Create, update, assign, auto-detect
#
# Customer Risk Engine:
#   logistics:customer_risk:view     — View risk profiles, distribution, check
#   logistics:customer_risk:recompute — Trigger bulk recompute
#
# Hub Analytics:
#   logistics:hub_analytics:view     — View hub metrics and bottlenecks
#
# Logistics Control Tower:
#   logistics:control_tower:view     — View live snapshot, courier health, alerts
#
# Finance — COD Reconciliation (moved from delivery):
#   finance:cod_reconciliation:view  — View COD remittance data under Finance module
# ─────────────────────────────────────────────────────────────────────────────
LOGISTICS_ENTERPRISE_PERMISSIONS = [
    'logistics:sla_dashboard:view',
    'logistics:sla_dashboard:manage',
    'logistics:exception_center:view',
    'logistics:exception_center:manage',
    'logistics:customer_risk:view',
    'logistics:customer_risk:recompute',
    'logistics:hub_analytics:view',
    'logistics:control_tower:view',
    'finance:cod_reconciliation:view',
]

class HasModulePermission(BasePermission):
    """
    Granular Role-Based Access Control Gatekeeper.
    Expects the view to define `required_permissions = {'GET': 'module:view', 'POST': 'module:create', ...}`
    Supports OR logic: 'GET': ['module1:view', 'module2:view'] allows access if the user has EITHER.
    """
    message = "Access denied: You do not have the required permissions for this action."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        # 1. Superusers, Founders, and Co-Founders have full access
        if is_org_owner(user):
            return True

        # 2. Determine Required Permission for this HTTP Method
        required_perms_map = getattr(view, 'required_permissions', {})
        required_perm = required_perms_map.get(request.method)

        if not required_perm:
            # If the view doesn't specify a permission for this method, 
            # we default to False for safety in an Enterprise environment.
            return False

        # 3. Check the User's Custom Role via WorkspaceMembership
        from core.models.users import WorkspaceMembership
        
        try:
            membership = WorkspaceMembership.objects.filter(user=user).select_related('role').first()
            if not membership or not membership.role:
                return False
            
            # Normalize to list for easy iteration
            if isinstance(required_perm, str):
                required_perm_list = [required_perm]
            else:
                required_perm_list = required_perm

            # 4. Success if user has WILDCARD or ANY of the required permissions
            has_wildcard = membership.role.permissions.filter(identifier='*:*:*').exists()
            if has_wildcard:
                return True

            return membership.role.permissions.filter(identifier__in=required_perm_list).exists()

        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"RBAC Error: {e}")
            return False