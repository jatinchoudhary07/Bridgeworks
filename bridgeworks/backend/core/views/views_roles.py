from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.models import Role, Permission, ShopCredentials, WorkspaceMembership
from core.permissions import IsOrganizationOwner, HasModulePermission

# ──────────────────────────────────────────────────────────────
# Master list of ALL permission identifiers in the platform.
# Used to auto-seed the built-in "Administrator" role.
# Format: "module:page:action"
# ──────────────────────────────────────────────────────────────
SYSTEM_ROLE_NAME = "Administrator"

ALL_PERMISSIONS = []

_MODULES = {
    'orders': ['all_orders', 'ndr'],
    'operations_fulfillment': [
        'analytics', 'orders', 'calling_sheet', 'awb_sheet', 'confirmation',
        'packaging_sheet', 'manifest_sheet', 'pending_orders',
        'unfulfilled_orders', 'tracking_added', 'confirmed'
    ],
    'logistics': [
        'lm_sheet', 'analytics', 'delivery_analytics', 'ndr_analytics', 'delivered_orders', 'ndr_action', 'returns',
        'exchanges', 'returns_scanner', 'ret_exc_stocking', 'webhook_logs',
        'warehouse_manager', 'rate_card_manager', 'cost_management', 'logistics_aura', 'aura',
        'cod_remittance', 'dept_expenses', 'logistics_analytics'
    ],
    'rto_module': [
        'rto_in_transit', 'rto_delivered', 'rto_manager', 'rto_engine'
    ],
    'marketing_growth': [
        'overview', 'meta_ads', 'google_ads', 'marketing_aura',
        'youtube_ads', 'pinterest_ads', 'snapchat_ads',
        'amazon_ads', 'flipkart_ads', 'etsy_ads', 'ajio_ads', 'tatacliq_ads', 'myntra_ads', 'nykaa_ads',
        'blinkit_ads', 'instamart_ads', 'zepto_ads',
        'social_calendar', 'social_posts', 'social_analytics',
        'influencer_database', 'influencer_campaigns',
        'offline_events', 'offline_leads', 'offline_analytics',
        'pr_coverage', 'pr_outreach', 'celebrity_spottings', 'celebrity_campaigns',
        'brand_monitoring', 'campaigns_hub', 'attribution',
    ],
    'intelligence': ['rto_intelligence', 'marketing_aura', 'logistics_aura', 'ai_context', 'ndr_escalations'],
    'customer_experience': ['case_file_sheet'],
    'human_resources': ['team_directory', 'workforce_sheet', 'roles_permissions', 'attendance_dashboard', 'master_task_tracker', 'meeting_manager', 'payroll', 'expenses', 'diary_logbooks'],
    'analytics_reporting': ['view_kpis', 'view_audit_logs'],
    'inventory': ['stock_management', 'purchase_orders'],
    'settings': ['general_settings', 'users_roles', 'billing', 'api_management'],
    'finance_accounting': [
        'dashboard', 'income', 'expense', 'orders_payments',
        'channels_fees', 'vendors_cogs', 'shipping', 'gst_tax',
        'international', 'departments', 'pnl_statement',
        # Sidebar features — must match FinanceSidebar.jsx navigationItems
        'journal', 'ledger', 'trial_balance', 'balance_sheet',
        'pending_expenses', 'finance', 'payroll', 'dept_expenses'
    ],
    'sales_business': [
        'overview', 'leads', 'crm', 'quotations', 'funnel', 'recovery',
        'forecasting', 'ai_recommendations', 'analytics', 'marketplace',
        'shopify', 'retail', 'draft_orders', 'attribution'
    ],
    'product_merch': [
        'inventory', 'stock_log', 'best_selling',
        'ai_stock_keeper', 'office_supplies','machines',
        'tools', 'packaging', 'miscellaneous', 'master_table',
        'shopify_listed', 'repair'
    ],
    'production_module': ['view_production']
}

_ACTIONS = ['view', 'create', 'edit', 'delete', 'view_amounts', 'export']

for mod_id, pages in _MODULES.items():
    for page_id in pages:
        for action in _ACTIONS:
            ALL_PERMISSIONS.append(f"{mod_id}:{page_id}:{action}")


def _ensure_admin_role(workspace):
    """
    Ensure the built-in Administrator role exists for this workspace.
    ALWAYS syncs permissions to stay up-to-date with _MODULES.
    When you add a new module to _MODULES above, the Admin role
    will automatically pick up the new permissions on next page load.
    """
    role, created = Role.objects.get_or_create(
        workspace=workspace,
        name=SYSTEM_ROLE_NAME,
        defaults={}
    )
    
    # Always sync — ensures new modules are auto-included
    current_perm_count = role.permissions.count()
    expected_perm_count = len(ALL_PERMISSIONS)
    
    if created or current_perm_count != expected_perm_count:
        perm_objects = []
        for perm_str in ALL_PERMISSIONS:
            perm_obj, _ = Permission.objects.get_or_create(identifier=perm_str)
            perm_objects.append(perm_obj)
        role.permissions.set(perm_objects)
    
    return role


class RoleListCreateView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view'],
        'POST': 'human_resources:roles_permissions:create'
    }

    def get_workspace(self, user):
        """Robustly retrieve the workspace for a user."""
        # 1. Check if user is the Owner (Founder)
        try:
            if hasattr(user, 'shop_credentials') and user.shop_credentials:
                return user.shop_credentials
        except Exception:
            pass

        # 2. Check WorkspaceMembership (New Enterprise System)
        membership = WorkspaceMembership.objects.filter(user=user).select_related('workspace').first()
        if membership:
            return membership.workspace

        # 3. Check TeamMemberSettings (Legacy System)
        try:
            if hasattr(user, 'team_settings') and user.team_settings.organization:
                return user.team_settings.organization
        except Exception:
            pass
            
        # 4. Global Superuser Fallback (for admin usage)
        if user.is_superuser:
            return ShopCredentials.objects.first()

        return None

    def get(self, request):
        """
        Fetch all custom roles for the current Workspace.
        Auto-seeds the built-in Administrator role if it doesn't exist.
        """
        workspace = self.get_workspace(request.user)
        if not workspace:
            return Response({
                "error": f"No Workspace found for user {request.user.username}.",
                "details": "User is not linked to any Organization/Shop Credentials."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Auto-seed the built-in Administrator role
        _ensure_admin_role(workspace)

        roles = Role.objects.filter(workspace=workspace).prefetch_related('permissions')
        
        data = []
        for role in roles:
            perms_list = [p.identifier for p in role.permissions.all()]
            data.append({
                "id": role.id,
                "name": role.name,
                "permissions": perms_list,
                "created_at": getattr(role, 'created_at', None),
                "is_system": role.name == SYSTEM_ROLE_NAME  # Flag for frontend
            })
            
        return Response({"roles": data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create or Update a custom role with a set of permissions.
        """
        name = request.data.get('name')
        permissions_payload = request.data.get('permissions', [])
        
        if not name:
            return Response({"error": "Role name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent creating a role with the reserved system name
        if name == SYSTEM_ROLE_NAME:
            return Response(
                {"error": f"'{SYSTEM_ROLE_NAME}' is a system role and cannot be created manually."},
                status=status.HTTP_400_BAD_REQUEST
            )

        workspace = self.get_workspace(request.user)
        if not workspace:
            return Response({"error": "No Workspace found to assign this role to."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Check if role exists in this workspace
                role = Role.objects.filter(workspace=workspace, name=name).first()
                if not role:
                    role = Role(workspace=workspace, name=name)
                    role.save()
                
                perm_objects = []
                for p_str in permissions_payload:
                    perm_obj, _ = Permission.objects.get_or_create(identifier=p_str)
                    perm_objects.append(perm_obj)
                
                role.permissions.set(perm_objects)
                
            return Response(
                {"message": f"Role '{name}' saved successfully.", "role_id": role.id}, 
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RoleDetailView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view'],
        'PUT': ['human_resources:roles_permissions:edit', 'human_resources:roles_permissions:create'],
        'DELETE': 'human_resources:roles_permissions:delete'
    }

    def put(self, request, pk):
        """
        Update an existing Role.
        """
        try:
            workspace = getattr(request.user, 'shop_credentials', None)
            if not workspace:
                membership = WorkspaceMembership.objects.filter(user=request.user).first()
                if membership:
                    workspace = membership.workspace
            
            if not workspace:
                settings = getattr(request.user, 'team_settings', None)
                if settings:
                    workspace = settings.organization

            if not workspace:
                return Response({"error": "No Workspace found for current user."}, status=status.HTTP_400_BAD_REQUEST)

            role = get_object_or_404(Role, pk=pk, workspace=workspace)

            # Block renaming the system Administrator role
            new_name = request.data.get('name')
            if role.name == SYSTEM_ROLE_NAME and new_name and new_name != SYSTEM_ROLE_NAME:
                return Response(
                    {"error": "The Administrator role cannot be renamed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            permissions_payload = request.data.get('permissions', [])
            
            with transaction.atomic():
                if new_name and role.name != SYSTEM_ROLE_NAME:
                    role.name = new_name
                
                if permissions_payload is not None:
                    perm_objects = []
                    for p_str in permissions_payload:
                        perm_obj, _ = Permission.objects.get_or_create(identifier=p_str)
                        perm_objects.append(perm_obj)
                    role.permissions.set(perm_objects)
                
                role.save()
                
            return Response({"message": "Role updated successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        """
        Delete a role. System roles (Administrator) cannot be deleted.
        """
        try:
            workspace = getattr(request.user, 'shop_credentials', None)
            if not workspace:
                membership = WorkspaceMembership.objects.filter(user=request.user).first()
                if membership:
                    workspace = membership.workspace
            
            if not workspace:
                settings = getattr(request.user, 'team_settings', None)
                if settings:
                    workspace = settings.organization

            if not workspace:
                return Response({"error": "No Workspace found for current user."}, status=status.HTTP_400_BAD_REQUEST)

            role = get_object_or_404(Role, pk=pk, workspace=workspace)

            # Protect the built-in Administrator role from deletion
            if role.name == SYSTEM_ROLE_NAME:
                return Response(
                    {"error": "The Administrator role is a system role and cannot be deleted."},
                    status=status.HTTP_403_FORBIDDEN
                )

            role.delete()
            return Response({"message": "Role deleted successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
