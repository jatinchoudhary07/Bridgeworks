import { useLocation } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';

export const checkActionPermission = (user, area, feature, action = 'view') => {
    // Dev bypass for local testing without authentication
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        return true;
    }

    if (!user) return false;

    // Admins and Workspace Owners (Founders) always have full access
    if (user.is_admin || user.is_founder || user.is_superuser) return true;

    const perms = user.role_permissions || [];

    // Check for specific permission identifier: e.g., "logistics:ndr_action:edit"
    // Also support wildcard access
    return perms.includes(`${area}:${feature}:${action}`) || perms.includes('*:*:*');
};

export const hasAnyPermissionInArea = (user, area, action = 'view') => {
    // Dev bypass for local testing without authentication
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        return true;
    }

    if (!user) return false;
    if (user.is_admin || user.is_founder || user.is_superuser) return true;

    const perms = user.role_permissions || [];
    if (perms.includes('*:*:*')) return true;

    // Check if any permission matches the area and action
    return perms.some(p => p.startsWith(`${area}:`) && p.endsWith(`:${action}`));
};

/**
 * Maps current URL path to the corresponding area:feature permission key.
 */
const getPermissionKeyFromPath = (pathname) => {
    // LOGISTICS (LM) - Entry point
    if (pathname === '/tracking' || pathname === '/tracking/') return { area: 'logistics', isModuleEntry: true };

    // ── NEW nested routes (4-component architecture) ──────────────────────────

    // Forward Shipments
    if (pathname.includes('/tracking/forward/analytics')) return { area: 'logistics', feature: 'delivery_analytics' };
    if (pathname.includes('/tracking/forward/delivered')) return { area: 'logistics', feature: 'delivered_orders' };
    if (pathname.includes('/tracking/forward')) return { area: 'logistics', feature: 'delivered_orders' };

    // Reverse Shipments (both under tracking and the RTO/Reverse Shipment module)
    if (pathname.includes('/tracking/reverse/rto-transit') || pathname.includes('/rto/transit')) return { area: 'logistics', feature: 'rto_in_transit' };
    if (pathname.includes('/tracking/reverse/rto-warehouse') || pathname.includes('/rto/manager')) return { area: 'logistics', feature: 'rto_manager' };
    if (pathname.includes('/tracking/reverse/returns') || pathname.includes('/rto/returns')) return { area: 'logistics', feature: 'returns' };
    if (pathname.includes('/tracking/reverse/exchanges') || pathname.includes('/rto/exchanges')) return { area: 'logistics', feature: 'exchanges' };
    if (pathname.includes('/tracking/reverse/scanner') || pathname.includes('/rto/scanner')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/reverse/engine') || pathname.includes('/rto/engine')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/reverse/case') || pathname.includes('/rto/case')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/reverse/refund') || pathname.includes('/rto/refund')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/reverse/exchange-settlement') || pathname.includes('/rto/exchange-settlement')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/reverse/stocking') || pathname.includes('/rto/stocking')) return { area: 'logistics', feature: 'ret_exc_stocking' };
    if (pathname.includes('/tracking/reverse')) return { area: 'logistics', feature: 'rto_in_transit' };

    // NDR
    if (pathname.includes('/tracking/ndr/analytics')) return { area: 'logistics', feature: 'ndr_analytics' };
    if (pathname.includes('/tracking/ndr/action')) return { area: 'logistics', feature: 'ndr_action' };
    if (pathname.includes('/tracking/ndr')) return { area: 'logistics', feature: 'ndr_action' };

    // Logistics Management
    if (pathname.includes('/tracking/management/analytics')) return { area: 'logistics', feature: 'logistics_analytics' };
    if (pathname.includes('/tracking/management/aura')) return { area: 'logistics', feature: 'aura' };
    if (pathname.includes('/tracking/management/costs')) return { area: 'logistics', feature: 'cost_management' };
    if (pathname.includes('/tracking/management/control-tower')) return { area: 'logistics', feature: 'control_tower' };
    if (pathname.includes('/tracking/management/sla')) return { area: 'logistics', feature: 'sla_dashboard' };
    if (pathname.includes('/tracking/management/exceptions')) return { area: 'logistics', feature: 'exception_center' };
    if (pathname.includes('/tracking/management/customer-risk')) return { area: 'logistics', feature: 'customer_risk' };
    if (pathname.includes('/tracking/management/hub-analytics')) return { area: 'logistics', feature: 'hub_analytics' };
    if (pathname.includes('/tracking/management/webhooks')) return { area: 'logistics', feature: 'webhook_logs' };
    if (pathname.includes('/tracking/management/dept-expenses')) return { area: 'logistics', feature: 'dept_expenses' };
    if (pathname.includes('/tracking/management')) return { area: 'logistics', isModuleEntry: true };

    // ── LEGACY flat routes (kept for backwards-compat redirects) ──────────────
    if (pathname.includes('/tracking/logistics-analytics')) return { area: 'logistics', feature: 'logistics_analytics' };
    if (pathname.includes('/tracking/aura')) return { area: 'logistics', feature: 'logistics_aura' };
    if (pathname.includes('/tracking/ndr-analytics')) return { area: 'logistics', feature: 'ndr_analytics' };
    if (pathname.includes('/tracking/delivery-analytics')) return { area: 'logistics', feature: 'delivery_analytics' };
    if (pathname.includes('/tracking/cod-remittance')) return { area: 'logistics', feature: 'cod_remittance' };
    if (pathname.includes('/tracking/dept-expenses')) return { area: 'logistics', feature: 'dept_expenses' };
    if (pathname.includes('/tracking/cost-management')) return { area: 'logistics', feature: 'cost_management' };
    if (pathname.includes('/tracking/delivered')) return { area: 'logistics', feature: 'delivered_orders' };
    if (pathname.includes('/tracking/returns-scan')) return { area: 'logistics', feature: 'returns_scanner' };
    if (pathname.includes('/tracking/returns-stocking')) return { area: 'logistics', feature: 'ret_exc_stocking' };
    if (pathname.includes('/tracking/returns')) return { area: 'logistics', feature: 'returns' };
    if (pathname.includes('/tracking/exchanges')) return { area: 'logistics', feature: 'exchanges' };
    // RTO MODULE - Entry point
    if (pathname === '/rto' || pathname === '/rto/') return { area: 'rto_module', isModuleEntry: true };
    if (pathname.includes('/rto/rto-engine')) return { area: 'rto_module', feature: 'rto_engine' };
    if (pathname.includes('/rto/dept-expenses')) return { area: 'logistics', feature: 'dept_expenses' };

    // OPERATIONS - Entry point
    if (pathname === '/operations' || pathname === '/operations/') return { area: 'operations_fulfillment', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/operations/analytics')) return { area: 'operations_fulfillment', feature: 'analytics' };
    if (pathname.includes('/operations/summary')) return { area: 'operations_fulfillment', feature: 'analytics' };
    if (pathname.includes('/operations/dept-expenses')) return { area: 'operations_fulfillment', feature: 'dept_expenses' };
    if (pathname.includes('/operations/orders')) return { area: 'operations_fulfillment', feature: 'orders' };
    if (pathname.includes('/operations/calling-sheet')) return { area: 'operations_fulfillment', feature: 'calling_sheet' };
    if (pathname.includes('/operations/awb-sheet')) return { area: 'operations_fulfillment', feature: 'awb_sheet' };
    if (pathname.includes('/operations/confirmation')) return { area: 'operations_fulfillment', feature: 'confirmation' };
    if (pathname.includes('/operations/packaging')) return { area: 'operations_fulfillment', feature: 'packaging_sheet' };
    if (pathname.includes('/operations/manifest-sheet')) return { area: 'operations_fulfillment', feature: 'manifest_sheet' };
    if (pathname.includes('/operations/pending-orders')) return { area: 'operations_fulfillment', feature: 'pending_orders' };
    if (pathname.includes('/operations/morning-report')) return { area: 'operations_fulfillment', feature: 'morning_report' };
    if (pathname.includes('/operations/unfulfilled-orders')) return { area: 'operations_fulfillment', feature: 'unfulfilled_orders' };

    // TEAM / HR - Entry point
    if (pathname === '/team' || pathname === '/team/') return { area: 'human_resources', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/team/directory')) return { area: 'human_resources', feature: 'team_directory' };
    if (pathname.includes('/team/role-editor')) return { area: 'human_resources', feature: 'roles_permissions' };
    if (pathname.includes('/team/master-workforce-sheet')) return { area: 'human_resources', feature: 'workforce_sheet' };
    if (pathname.includes('/team/master-task-tracker')) return { area: 'human_resources', feature: 'master_task_tracker' };
    if (pathname.includes('/team/meeting-manager')) return { area: 'human_resources', feature: 'meeting_manager' };
    if (pathname.includes('/team/attendance')) return { area: 'human_resources', feature: 'attendance_dashboard' };
    if (pathname.includes('/team/org-hierarchy')) return { area: 'human_resources', feature: 'team_directory' };
    if (pathname.includes('/team/payroll')) return { area: 'human_resources', feature: 'payroll' };
    if (pathname.includes('/team/expenses')) return { area: 'human_resources', feature: 'expenses' };
    if (pathname.includes('/team/diary')) return { area: 'human_resources', feature: 'diary_logbooks' };
    if (pathname.includes('/team/hiring/analytics')) return { area: 'human_resources', feature: 'team_directory' };
    if (pathname.includes('/team/hiring/pipeline')) return { area: 'human_resources', feature: 'team_directory' };
    if (pathname.includes('/team/hiring')) return { area: 'human_resources', feature: 'team_directory' };

    // SETTINGS - Entry point
    if (pathname === '/settings' || pathname === '/settings/') return { area: 'settings', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/settings/api-keys')) return { area: 'settings', feature: 'api_management' };

    // INTELLIGENCE - Entry point
    if (pathname === '/intelligence' || pathname === '/intelligence/') return { area: 'intelligence', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/intelligence/rto')) return { area: 'intelligence', feature: 'rto_intelligence' };
    if (pathname.includes('/intelligence/marketing')) return { area: 'intelligence', feature: 'marketing_aura' };
    if (pathname.includes('/intelligence/logistics')) return { area: 'intelligence', feature: 'logistics_aura' };
    if (pathname.includes('/intelligence/service')) return { area: 'intelligence', feature: 'service_agent' };
    if (pathname.includes('/intelligence/analytics')) return { area: 'intelligence', feature: 'ai_context' };

    if (pathname.includes('/intelligence/ndr-escalations')) return { area: 'intelligence', feature: 'ndr_escalations' };

    // MARKETING - Entry point
    if (pathname === '/marketing' || pathname === '/marketing/') return { area: 'marketing_growth', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/marketing/overview')) return { area: 'marketing_growth', feature: 'overview' };
    if (pathname.includes('/marketing/meta')) return { area: 'marketing_growth', feature: 'meta_ads' };
    if (pathname.includes('/marketing/google')) return { area: 'marketing_growth', feature: 'google_ads' };
    if (pathname.includes('/marketing/aura')) return { area: 'marketing_growth', feature: 'marketing_aura' };
    if (pathname.includes('/marketing/atlas') || pathname.includes('/marketing/attribution')) return { area: 'marketing_growth', feature: 'attribution' };

    // CUSTOMER EXPERIENCE - Entry point
    if (pathname === '/customer-care' || pathname === '/customer-care/') return { area: 'customer_experience', isModuleEntry: true };

    // Sub-paths
    if (pathname.includes('/customer-care')) return { area: 'customer_experience', feature: 'case_file_sheet' };

    // FINANCE & ACCOUNTING - Entry point
    if (pathname === '/finance' || pathname === '/finance/') return { area: 'finance_accounting', isModuleEntry: true };

    // SALES & BUSINESS DEVELOPMENT - Entry point
    if (pathname === '/sales' || pathname === '/sales/') return { area: 'sales_business', isModuleEntry: true };

    // Sales sub-paths
    if (pathname.includes('/sales/overview')) return { area: 'sales_business', feature: 'overview' };
    if (pathname.includes('/sales/leads')) return { area: 'sales_business', feature: 'leads' };
    if (pathname.includes('/sales/crm')) return { area: 'sales_business', feature: 'crm' };
    if (pathname.includes('/sales/wholesale')) return { area: 'sales_business', feature: 'crm' };
    if (pathname.includes('/sales/quotations')) return { area: 'sales_business', feature: 'quotations' };
    if (pathname.includes('/sales/funnel')) return { area: 'sales_business', feature: 'funnel' };
    if (pathname.includes('/sales/recovery')) return { area: 'sales_business', feature: 'recovery' };
    if (pathname.includes('/sales/carts')) return { area: 'sales_business', feature: 'recovery' };
    if (pathname.includes('/sales/forecasting')) return { area: 'sales_business', feature: 'forecasting' };
    if (pathname.includes('/sales/ai')) return { area: 'sales_business', feature: 'ai_recommendations' };
    if (pathname.includes('/sales/analytics')) return { area: 'sales_business', feature: 'analytics' };
    // Sales Executive sub-sections
    if (pathname.includes('/sales/se-dashboard')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/se-activities')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/se-approvals')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/se-incentives')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/se-reports')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/se-analytics')) return { area: 'sales_business', feature: 'sales_executive' };
    if (pathname.includes('/sales/marketplace')) return { area: 'sales_business', feature: 'marketplace' };
    if (pathname.includes('/sales/shopify')) return { area: 'sales_business', feature: 'shopify' };
    if (pathname.includes('/sales/retail')) return { area: 'sales_business', feature: 'retail' };
    if (pathname.includes('/sales/draft')) return { area: 'sales_business', feature: 'draft_orders' };
    if (pathname.includes('/sales/attribution')) return { area: 'sales_business', feature: 'attribution' };
    // Multi-channel sub-sections (all map to parent channel feature)
    if (pathname.includes('/sales/marketplace-draft-orders')) return { area: 'sales_business', feature: 'marketplace' };
    if (pathname.includes('/sales/marketplace-abandoned-checkouts')) return { area: 'sales_business', feature: 'marketplace' };
    if (pathname.includes('/sales/marketplace-recovery')) return { area: 'sales_business', feature: 'marketplace' };
    if (pathname.includes('/sales/retail-draft-orders')) return { area: 'sales_business', feature: 'retail' };
    if (pathname.includes('/sales/retail-abandoned-checkouts')) return { area: 'sales_business', feature: 'retail' };
    if (pathname.includes('/sales/retail-recovery')) return { area: 'sales_business', feature: 'retail' };
    if (pathname.includes('/sales/b2b-draft-orders')) return { area: 'sales_business', feature: 'leads' };
    if (pathname.includes('/sales/b2b-abandoned-checkouts')) return { area: 'sales_business', feature: 'leads' };
    if (pathname.includes('/sales/b2b-recovery')) return { area: 'sales_business', feature: 'leads' };
    if (pathname.includes('/sales/wholesale-draft-orders')) return { area: 'sales_business', feature: 'crm' };
    if (pathname.includes('/sales/wholesale-abandoned-checkouts')) return { area: 'sales_business', feature: 'crm' };
    if (pathname.includes('/sales/wholesale-recovery')) return { area: 'sales_business', feature: 'crm' };

    // PRODUCT & MERCHANDISING - Entry point
    if (pathname === '/product' || pathname === '/product/') return { area: 'product_merch', isModuleEntry: true };

    // Product sub-paths
    if (pathname.includes('/product/inventory')) return { area: 'product_merch', feature: 'inventory' };
    if (pathname.includes('/product/stocklog')) return { area: 'product_merch', feature: 'stock_log' };
    if (pathname.includes('/product/bestselling')) return { area: 'product_merch', feature: 'best_selling' };
    if (pathname.includes('/product/ai')) return { area: 'product_merch', feature: 'ai_stock_keeper' };
    if (pathname.includes('/product/machines')) return { area: 'product_merch', feature: 'machines' };
    if (pathname.includes('/product/tools')) return { area: 'product_merch', feature: 'tools' };
    if (pathname.includes('/product/packaging')) return { area: 'product_merch', feature: 'packaging' };
    if (pathname.includes('/product/miscellaneous')) return { area: 'product_merch', feature: 'miscellaneous' };
    if (pathname.includes('/product/master')) return { area: 'product_merch', feature: 'master_table' };
    if (pathname.includes('/product/shopifylisted')) return { area: 'product_merch', feature: 'shopify_listed' };
    if (pathname.includes('/product/repair')) return { area: 'product_merch', feature: 'repair' };
    if (pathname.includes('/product/vendors')) return { area: 'product_merch', feature: 'vendors' };

    // Sub-paths
    if (pathname.includes('/finance/control-tower')) return { area: 'finance_accounting', feature: 'journal' };
    if (pathname.includes('/finance/journal')) return { area: 'finance_accounting', feature: 'journal' };
    if (pathname.includes('/finance/ledger')) return { area: 'finance_accounting', feature: 'ledger' };
    if (pathname.includes('/finance/trial-balance')) return { area: 'finance_accounting', feature: 'trial_balance' };
    if (pathname.includes('/finance/profit-loss')) return { area: 'finance_accounting', feature: 'pnl_statement' };
    if (pathname.includes('/finance/balance-sheet')) return { area: 'finance_accounting', feature: 'balance_sheet' };
    if (pathname.includes('/finance/pending-expenses')) return { area: 'finance_accounting', feature: 'pending_expenses' };
    if (pathname.includes('/finance/cod')) return { area: 'finance_accounting', feature: 'cod_reconciliation' };
    if (pathname.includes('/finance/finance')) return { area: 'finance_accounting', feature: 'finance' };
    if (pathname.includes('/finance/departments')) return { area: 'finance_accounting', feature: 'departments' };
    if (pathname.includes('/finance/payroll')) return { area: 'finance_accounting', feature: 'payroll' };
    if (pathname.includes('/finance/dept-expenses')) return { area: 'finance_accounting', feature: 'dept_expenses' };
    if (pathname.includes('/finance/dashboard')) return { area: 'finance_accounting', feature: 'dashboard' };
    if (pathname.includes('/finance/gst')) return { area: 'finance_accounting', feature: 'gst' };
    if (pathname.includes('/finance/gst-transactions')) return { area: 'finance_accounting', feature: 'gst' };
    if (pathname.includes('/finance/gst-settings')) return { area: 'finance_accounting', feature: 'gst' };
    if (pathname.includes('/finance/reconciliation')) return { area: 'finance_accounting', feature: 'reconciliation' };
    if (pathname.includes('/finance/accounts')) return { area: 'finance_accounting', feature: 'accounts_center' };
    if (pathname.includes('/finance/assets')) return { area: 'finance_accounting', feature: 'assets' };
    if (pathname.includes('/finance/decisions')) return { area: 'finance_accounting', feature: 'journal' };
    if (pathname.includes('/finance/reports')) return { area: 'finance_accounting', feature: 'ledger' };


    // WEBHOOKS
    if (pathname.includes('/webhooks')) return { area: 'logistics', feature: 'webhook_logs' };

    // TASK MANAGER - General access (personal desk)
    if (pathname.includes('/task-manager') || pathname.startsWith('/mydesk')) return { area: 'general', feature: 'task_manager', bypass: true };

    return null;
};

/**
 * Hook to get granular permissions for the current page.
 */
export const usePagePermissions = () => {
    const { user } = useUser();
    const location = useLocation();

    const key = getPermissionKeyFromPath(location.pathname);

    if (!key) {
        // Default to restricted if no mapping exists (for safety)
        const isAdmin = user?.is_admin || user?.is_founder || user?.is_superuser;
        return {
            canView: isAdmin,
            canCreate: isAdmin,
            canEdit: isAdmin,
            canDelete: isAdmin,
            canViewAmounts: isAdmin,
            canExport: isAdmin,
            isLoading: !user
        };
    }

    // Bypass for general components (like Task Manager) if needed
    if (key.bypass) {
        return {
            canView: true,
            canCreate: true,
            canEdit: true,
            canDelete: true,
            canViewAmounts: true,
            canExport: true,
            isLoading: !user
        };
    }

    // Handle Module Entry points (check if user has ANY permission in that area)
    if (key.isModuleEntry) {
        const areas = Array.isArray(key.area) ? key.area : [key.area];
        const canView = areas.some(a => hasAnyPermissionInArea(user, a, 'view'));
        const canViewAmounts = areas.some(a => hasAnyPermissionInArea(user, a, 'view_amounts'));
        const canExport = areas.some(a => hasAnyPermissionInArea(user, a, 'export'));

        return {
            canView,
            canCreate: canView,
            canEdit: canView,
            canDelete: canView,
            canViewAmounts,
            canExport,
            isLoading: !user
        };
    }

    return {
        canView: checkActionPermission(user, key.area, key.feature, 'view'),
        canCreate: checkActionPermission(user, key.area, key.feature, 'create'),
        canEdit: checkActionPermission(user, key.area, key.feature, 'edit'),
        canDelete: checkActionPermission(user, key.area, key.feature, 'delete'),
        canViewAmounts: checkActionPermission(user, key.area, key.feature, 'view_amounts'),
        canExport: checkActionPermission(user, key.area, key.feature, 'export'),
        isLoading: !user
    };
};
