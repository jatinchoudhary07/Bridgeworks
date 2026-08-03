import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  TextField,
  Button,
  List,
  ListItemButton,
  ListItemText,
  Divider,
  Snackbar,
  Alert,
  CircularProgress,
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  IconButton,
  alpha
} from '@mui/material';
import {
  Shield as ShieldIcon,
  Settings as SettingsIcon,
  Save as SaveIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  ChevronRight as ChevronRightIcon,
  Info as InfoIcon,
  Lock as LockIcon,
  Star as StarIcon,
  AdminPanelSettings as AdminIcon
} from '@mui/icons-material';

import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

const APP_MODULES = [
  {
    id: 'orders',
    name: 'Orders Dashboard',
    pages: [
      { id: 'all_orders', name: 'All Orders' },
      { id: 'ndr', name: 'NDR Management' }
    ]
  },
  {
    id: 'operations_fulfillment',
    name: 'Operations & Fulfillment',
    pages: [
      { id: 'analytics', name: 'Analytics' },
      { id: 'summary', name: 'Operations Summary' },
      { id: 'orders', name: 'Orders' },
      { id: 'calling_sheet', name: 'Calling Sheet' },
      { id: 'awb_sheet', name: 'AWB Sheet' },
      { id: 'confirmation', name: 'Confirmation' },
      { id: 'packaging_sheet', name: 'Packaging' },
      { id: 'manifest_sheet', name: 'Manifest Sheet' },
      { id: 'pending_orders', name: 'Pending Orders' },
      { id: 'unfulfilled_orders', name: 'Unconfirmed Orders' },
      { id: 'confirmed', name: 'Confirmed' },
      { id: 'tracking_added', name: 'AWB Generated' },
      { id: 'dept_expenses', name: 'Dept Expenses' }
    ]
  },
  {
    id: 'logistics',
    name: 'Logistics & Tracking',
    pages: [
      { id: 'analytics', name: 'Analytics' },
      { id: 'logistics_analytics', name: 'Logistics Analytics' },
      { id: 'delivery_analytics', name: 'Delivery Analytics' },
      { id: 'ndr_analytics', name: 'NDR Analytics' },
      { id: 'delivered_orders', name: 'Delivered Orders' },
      { id: 'ndr_action', name: 'NDR / Action' },
      { id: 'returns', name: 'Returns' },
      { id: 'exchanges', name: 'Exchanges' },
      { id: 'returns_scanner', name: 'Returns Scanner' },
      { id: 'ret_exc_stocking', name: 'RET & EXC Stocking' },
      { id: 'webhook_logs', name: 'Webhook Logs' },
      { id: 'warehouse_manager', name: 'Warehouse Manager' },
      { id: 'rate_card_manager', name: 'Rate Card Manager' },
      { id: 'cost_management', name: 'Cost Management' },
      { id: 'cod_remittance', name: 'COD Remittance' },
      { id: 'dept_expenses', name: 'Dept Expenses' },
      { id: 'logistics_aura', name: 'Logistics Aura' }
    ]
  },
  {
    id: 'rto_module',
    name: 'Reverse Shipment',
    pages: [
      { id: 'rto_in_transit', name: 'RTO In-Transit' },
      { id: 'rto_delivered', name: 'RTO Delivered' },
      { id: 'rto_manager', name: 'RTO Manager' },
      { id: 'rto_engine', name: 'RTO Engine' }
    ]
  },
  {
    id: 'marketing_growth',
    name: 'Marketing & Growth',
    pages: [
      { id: 'overview', name: 'Overview' },
      { id: 'meta_ads', name: 'Meta Ads' },
      { id: 'google_ads', name: 'Google Ads' },
      { id: 'marketing_aura', name: 'Marketing Aura' },
      { id: 'youtube_ads', name: 'YouTube Ads' },
      { id: 'pinterest_ads', name: 'Pinterest Ads' },
      { id: 'snapchat_ads', name: 'Snapchat Ads' },
      { id: 'amazon_ads', name: 'Amazon Ads' },
      { id: 'flipkart_ads', name: 'Flipkart Ads' },
      { id: 'etsy_ads', name: 'Etsy Ads' },
      { id: 'ajio_ads', name: 'Ajio Ads' },
      { id: 'tatacliq_ads', name: 'Tata Cliq Lux' },
      { id: 'myntra_ads', name: 'Myntra' },
      { id: 'nykaa_ads', name: 'Nykaa' },
      { id: 'blinkit_ads', name: 'Blinkit Ads' },
      { id: 'instamart_ads', name: 'Instamart Ads' },
      { id: 'zepto_ads', name: 'Zepto Ads' },
      { id: 'social_calendar', name: 'Content Calendar' },
      { id: 'social_posts', name: 'Posts & Scheduling' },
      { id: 'social_analytics', name: 'Social Analytics' },
      { id: 'influencer_database', name: 'Influencer Database' },
      { id: 'influencer_campaigns', name: 'Influencer Campaigns' },
      { id: 'offline_events', name: 'Events & Exhibitions' },
      { id: 'offline_leads', name: 'Offline Leads' },
      { id: 'offline_analytics', name: 'Offline Analytics' },
      { id: 'pr_coverage', name: 'PR Coverage' },
      { id: 'pr_outreach', name: 'PR Outreach' },
      { id: 'celebrity_spottings', name: 'Celebrity Spottings' },
      { id: 'celebrity_campaigns', name: 'Celebrity Campaigns' },
      { id: 'brand_monitoring', name: 'Brand Monitoring' },
      { id: 'campaigns_hub', name: 'Campaigns Hub' },
      { id: 'attribution', name: 'Attribution' },
      { id: 'youtube_ads', name: 'YouTube Ads' },
      { id: 'pinterest_ads', name: 'Pinterest Ads' },
      { id: 'snapchat_ads', name: 'Snapchat Ads' },
      { id: 'amazon_ads', name: 'Amazon Ads' },
      { id: 'flipkart_ads', name: 'Flipkart Ads' },
      { id: 'etsy_ads', name: 'Etsy Ads' },
      { id: 'ajio_ads', name: 'Ajio Ads' },
      { id: 'tatacliq_ads', name: 'Tata Cliq Lux' },
      { id: 'myntra_ads', name: 'Myntra' },
      { id: 'nykaa_ads', name: 'Nykaa' },
      { id: 'blinkit_ads', name: 'Blinkit Ads' },
      { id: 'instamart_ads', name: 'Instamart Ads' },
      { id: 'zepto_ads', name: 'Zepto Ads' },
      { id: 'dept_expenses', name: 'Dept Expenses' }
    ]
  },
  {
    id: 'intelligence',
    name: 'Intelligence',
    pages: [
      { id: 'rto_intelligence', name: 'RTO Intelligence' },
      { id: 'marketing_aura', name: 'Marketing Aura AI' },
      { id: 'logistics_aura', name: 'Logistics Aura AI' },
      { id: 'ai_context', name: 'AI Analytics Context' },
      { id: 'ndr_escalations', name: 'NDR Escalations' },
      { id: 'dept_expenses', name: 'Dept Expenses' }
    ]
  },
  {
    id: 'customer_experience',
    name: 'Customer Experience',
    pages: [
      { id: 'case_file_sheet', name: 'Customer Case File Sheet' }
    ]
  },
  {
    id: 'human_resources',
    name: 'Human Resources',
    pages: [
      { id: 'team_directory', name: 'Team Directory' },
      { id: 'workforce_sheet', name: 'Master Workforce Sheet' },
      { id: 'roles_permissions', name: 'Roles & Permissions' },
      { id: 'attendance_dashboard', name: 'Attendance Dashboard' },
      { id: 'master_task_tracker', name: 'Master Task Tracker' },
      { id: 'meeting_manager', name: 'Meeting Manager' },
      { id: 'payroll', name: 'Payroll' },
      { id: 'expenses', name: 'Expenses Tracker' },
      { id: 'diary_logbooks', name: 'Diary Logbooks' }
    ]
  },
  {
    id: 'analytics_reporting',
    name: 'Analytics & Reporting',
    pages: [
      { id: 'view_kpis', name: 'View Analytics & KPIs' },
      { id: 'view_audit_logs', name: 'View Audit Logs' }
    ]
  },
  {
    id: 'inventory',
    name: 'Inventory & Stock',
    pages: [
      { id: 'stock_management', name: 'Stock Management' },
      { id: 'purchase_orders', name: 'Purchase Orders' }
    ]
  },
  {
    id: 'settings',
    name: 'Store Settings',
    pages: [
      { id: 'general_settings', name: 'General Settings' },
      { id: 'users_roles', name: 'Users & Roles Management' },
      { id: 'billing', name: 'Billing & Invoices' },
      { id: 'api_management', name: 'API Management & Webhooks' }
    ]
  },
  {
    id: 'finance_accounting',
    name: 'Finance & Accounting',
    pages: [
      { id: 'dashboard', name: 'Finance Dashboard' },
      { id: 'journal', name: 'Journal Entry' },
      { id: 'ledger', name: 'Ledger Summary' },
      { id: 'trial_balance', name: 'Trial Balance' },
      { id: 'pnl_statement', name: 'Profit & Loss' },
      { id: 'balance_sheet', name: 'Balance Sheet' },
      { id: 'pending_expenses', name: 'Pending Expenses' },
      { id: 'finance', name: 'Finance' },
      { id: 'departments', name: 'Departments' },
      { id: 'payroll', name: 'Payroll' },
      { id: 'dept_expenses', name: 'Dept Expenses' },
      { id: 'reconciliation', name: 'Bank Reconciliation' },
      { id: 'accounts_center', name: 'Accounts Center' }
    ]
  },
  {
    id: 'sales_business',
    name: 'Sales & Business Development',
    pages: [
      { id: 'overview', name: 'Sales Overview' },
      { id: 'leads', name: 'B2B Leads' },
      { id: 'crm', name: 'Wholesale CRM' },
      { id: 'quotations', name: 'Quotation Tracker' },
      { id: 'funnel', name: 'Conversion Funnel' },
      { id: 'recovery', name: 'Abandoned Cart Recovery' },
      { id: 'forecasting', name: 'Sales Forecasting' },
      { id: 'ai_recommendations', name: 'AI Recommendations' },
      { id: 'analytics', name: 'Performance Analytics' },
      { id: 'marketplace', name: 'Marketplace Analytics' },
      { id: 'shopify', name: 'Shopify Analytics' },
      { id: 'retail', name: 'Retail Store Analytics' },
      { id: 'draft_orders', name: 'Create Draft Order' },
      { id: 'attribution', name: 'Order Attribution' }
    ]
  },
  {
    id: 'product_merch',
    name: 'Product & Merchandising',
    pages: [
      { id: 'inventory', name: 'Product Inventory' },
      { id: 'stock_log', name: 'Stock Log' },
      { id: 'best_selling', name: 'Best Selling Products' },
      { id: 'ai_stock_keeper', name: 'AI Stock Keeper' },
      { id: 'machines', name: 'Machines' },
      { id: 'tools', name: 'Tools' },
      { id: 'packaging', name: 'Packaging' },
      { id: 'miscellaneous', name: 'Miscellaneous' },
      { id: 'office_supplies', name: 'Office Supplies' },
      { id: 'master_table', name: 'Master Inventory Table' },
      { id: 'shopify_listed', name: 'Listed on Shopify' }
    ]
  },
  {
    id: 'production_module',
    name: 'Production / Manufacturing',
    pages: [
      { id: 'view_production', name: 'Access Production Module' }
    ]
  }
];

const AVAILABLE_ACTIONS = [
  { id: 'view', label: 'View', description: 'Can read data and view this module.' },
  { id: 'create', label: 'Create', description: 'Can create new records in this module.' },
  { id: 'edit', label: 'Edit', description: 'Can modify existing data within this module.' },
  { id: 'delete', label: 'Delete', description: 'Can permanently delete records from this module.' },
  { id: 'view_amounts', label: 'View Amounts', description: 'Can view financial values and prices on this page.' },
  { id: 'export', label: 'Export', description: 'Can download or export data from this page.' }
];

export default function RoleEditor() {
  const [roleName, setRoleName] = useState('');
  const [activeModule, setActiveModule] = useState(APP_MODULES[0].id);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [savedRoles, setSavedRoles] = useState([]);

  // State mapping flat string "module:page:action" -> true/false
  const [permissions, setPermissions] = useState({});
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });
  const [saving, setSaving] = useState(false);
  const [loadingRoles, setLoadingRoles] = useState(true);

  // Fetch roles on mount
  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      const res = await apiClient(`${BACKEND_URL}/api/roles/`);
      if (res.ok) {
        const data = await res.json();
        setSavedRoles(data.roles || []);
      }
    } catch (err) {
      console.error("Failed to fetch roles:", err);
    } finally {
      setLoadingRoles(false);
    }
  };

  // Check if the currently selected role is a system role
  const selectedRole = savedRoles.find(r => r.id === selectedRoleId);
  const isSystemRole = selectedRole?.is_system === true;

  const handleSelectRole = (role) => {
    if (selectedRoleId === role.id) {
      setSelectedRoleId(null);
      setRoleName('');
      setPermissions({});
      return;
    }

    setSelectedRoleId(role.id);
    setRoleName(role.name);
    const newPerms = {};
    role.permissions.forEach(p => {
      newPerms[p] = true;
    });
    setPermissions(newPerms);
  };

  const handleToggle = (moduleId, pageId, actionId) => {
    const key = `${moduleId}:${pageId}:${actionId}`;
    setPermissions((prev) => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Select / deselect all actions for a single page
  const handleSelectAllPage = (moduleId, pageId) => {
    const allKeys = AVAILABLE_ACTIONS.map(a => `${moduleId}:${pageId}:${a.id}`);
    const allChecked = allKeys.every(k => permissions[k]);
    setPermissions(prev => {
      const next = { ...prev };
      allKeys.forEach(k => { next[k] = !allChecked; });
      return next;
    });
  };

  // Select / deselect every permission in the active module
  const handleSelectAllModule = (moduleId) => {
    const module = APP_MODULES.find(m => m.id === moduleId);
    if (!module) return;
    const allKeys = module.pages.flatMap(p => AVAILABLE_ACTIONS.map(a => `${moduleId}:${p.id}:${a.id}`));
    const allChecked = allKeys.every(k => permissions[k]);
    setPermissions(prev => {
      const next = { ...prev };
      allKeys.forEach(k => { next[k] = !allChecked; });
      return next;
    });
  };

  const generatePayload = () => {
    return Object.keys(permissions).filter(key => permissions[key]);
  };

  const handleSaveRole = async () => {
    if (!roleName.trim()) {
      setToast({ open: true, message: 'Please enter a Role Name.', severity: 'error' });
      return;
    }

    const payloadArray = generatePayload();
    if (payloadArray.length === 0) {
      setToast({ open: true, message: 'Please select at least one permission.', severity: 'warning' });
      return;
    }

    setSaving(true);
    try {
      const url = selectedRoleId
        ? `${BACKEND_URL}/api/roles/${selectedRoleId}/`
        : `${BACKEND_URL}/api/roles/`;

      const method = selectedRoleId ? "PUT" : "POST";

      const res = await apiClient(url, {
        method,
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name: roleName, permissions: payloadArray })
      });

      if (!res.ok) throw new Error("Failed to save role");

      setToast({
        open: true,
        message: selectedRoleId ? `Role '${roleName}' updated!` : `Role '${roleName}' created!`,
        severity: 'success'
      });

      if (!selectedRoleId) {
        setRoleName('');
        setPermissions({});
      }
      fetchRoles();
    } catch (err) {
      setToast({ open: true, message: err.message || 'Error saving role', severity: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRole = async (roleId) => {
    if (!window.confirm("Are you sure you want to delete this role?")) return;

    try {
      const res = await apiClient(`${BACKEND_URL}/api/roles/${roleId}/`, {
        method: "DELETE"
      });
      if (res.ok) {
        setToast({ open: true, message: "Role deleted successfully.", severity: 'info' });
        if (selectedRoleId === roleId) {
          setSelectedRoleId(null);
          setRoleName('');
          setPermissions({});
        }
        fetchRoles();
      }
    } catch {
      setToast({ open: true, message: "Error deleting role.", severity: 'error' });
    }
  };

  return (
    <Box sx={{
      width: '100%',
      height: 'calc(100vh - 64px)',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: 'background.default',
      overflow: 'hidden'
    }}>

      {/* Header Bar */}
      <Box sx={{
        p: 2,
        px: 4,
        bgcolor: 'background.paper',
        borderBottom: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: (theme) => theme.palette.mode === 'dark' ? 'none' : '0 1px 3px 0 rgb(0 0 0 / 0.1)'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{
            bgcolor: 'primary.main',
            color: 'white',
            p: 1,
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center'
          }}>
            <ShieldIcon />
          </Box>
          <Box>
            <Typography variant="h5" fontWeight="900" color="text.primary">
              Roles & Permissions
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mt: -0.5 }}>
              MANAGE USER ACCESS LEVELS
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            size="small"
            label="Role Name"
            placeholder="e.g. Fulfillment Manager"
            value={roleName}
            onChange={(e) => setRoleName(e.target.value)}
            disabled={isSystemRole}
            sx={{
              width: 300,
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
                bgcolor: (theme) => isSystemRole
                  ? (theme.palette.mode === 'dark' ? 'rgba(245, 158, 11, 0.15)' : '#fef3c7')
                  : (theme.palette.mode === 'dark' ? 'action.hover' : '#f1f5f9'),
                '&:hover fieldset': { borderColor: 'primary.main' }
              }
            }}
          />
          {isSystemRole && (
            <Box sx={{
              display: 'flex', alignItems: 'center', gap: 0.5,
              bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(245, 158, 11, 0.15)' : '#fef3c7',
              border: '1px solid #f59e0b',
              px: 1.5, py: 0.5, borderRadius: 2
            }}>
              <StarIcon sx={{ fontSize: 16, color: '#f59e0b' }} />
              <Typography variant="caption" sx={{ fontWeight: 700, color: (theme) => theme.palette.mode === 'dark' ? '#f59e0b' : '#92400e' }}>SYSTEM ROLE</Typography>
            </Box>
          )}
          <Divider orientation="vertical" flexItem />
          {selectedRoleId && !isSystemRole && (
            <Button
              startIcon={<DeleteIcon />}
              onClick={() => handleDeleteRole(selectedRoleId)}
              sx={{ color: 'error.main', fontWeight: 700, textTransform: 'none' }}
            >
              Delete
            </Button>
          )}
          <Button
            variant="contained"
            disableElevation
            startIcon={saving ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
            onClick={handleSaveRole}
            disabled={saving}
            sx={{
              bgcolor: '#6366f1',
              fontWeight: 800,
              textTransform: 'none',
              px: 4, py: 1,
              borderRadius: 2,
              '&:hover': { bgcolor: '#4f46e5', transform: 'translateY(-1px)' },
              transition: 'all 0.2s'
            }}
          >
            {selectedRoleId ? 'Update Role' : 'Create Role'}
          </Button>
        </Box>
      </Box>

      {/* Main Container: 3 Panes */}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>

        {/* Pane 1: Existing Roles */}
        <Box sx={{
          width: 280,
          bgcolor: 'background.paper',
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc' }}>
            <Typography variant="subtitle2" color="text.secondary" fontWeight="800" sx={{ letterSpacing: '0.05em' }}>
              SAVED ROLES
            </Typography>
          </Box>
          <Box sx={{ flex: 1, overflowY: 'auto', p: 1 }}>
            <ListItemButton
              selected={!selectedRoleId}
              onClick={() => { setSelectedRoleId(null); setRoleName(''); setPermissions({}); }}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                bgcolor: (theme) => !selectedRoleId ? alpha(theme.palette.primary.main, 0.1) : 'transparent',
                '&.Mui-selected': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1) }
              }}
            >
              <Box sx={{ mr: 2, color: !selectedRoleId ? 'primary.main' : 'text.disabled' }}><AddIcon /></Box>
              <ListItemText
                primary="New Custom Role"
                primaryTypographyProps={{ fontWeight: 700, fontSize: '0.9rem', color: !selectedRoleId ? 'primary.main' : 'text.primary' }}
              />
            </ListItemButton>
            <Divider sx={{ my: 1 }} />
            {savedRoles.map(role => (
              <ListItemButton
                key={role.id}
                selected={selectedRoleId === role.id}
                onClick={() => handleSelectRole(role)}
                sx={{
                  borderRadius: 2,
                  mb: 0.5,
                  bgcolor: (theme) => role.is_system && selectedRoleId !== role.id
                    ? (theme.palette.mode === 'dark' ? alpha('#f59e0b', 0.15) : alpha('#f59e0b', 0.06))
                    : undefined,
                  border: role.is_system ? '1px solid' : 'none',
                  borderColor: role.is_system ? alpha('#f59e0b', 0.3) : 'transparent',
                  '&.Mui-selected': {
                    bgcolor: (theme) => role.is_system ? alpha('#f59e0b', 0.2) : alpha(theme.palette.primary.main, 0.15),
                    '&:hover': { bgcolor: (theme) => role.is_system ? alpha('#f59e0b', 0.25) : alpha(theme.palette.primary.main, 0.2) }
                  }
                }}
              >
                <Box sx={{ mr: 2, color: role.is_system ? '#f59e0b' : (selectedRoleId === role.id ? 'primary.main' : 'text.secondary') }}>
                  {role.is_system ? <AdminIcon fontSize="small" /> : <ShieldIcon fontSize="small" />}
                </Box>
                <ListItemText
                  primary={role.name}
                  secondary={role.is_system ? 'Full Access' : undefined}
                  primaryTypographyProps={{ fontWeight: selectedRoleId === role.id ? 800 : 600, fontSize: '0.85rem' }}
                  secondaryTypographyProps={{ fontSize: '0.7rem', fontWeight: 700, color: '#f59e0b' }}
                />
                {role.is_system && <StarIcon sx={{ fontSize: 16, color: '#f59e0b', mr: 0.5 }} />}
                {selectedRoleId === role.id && <ChevronRightIcon sx={{ color: role.is_system ? '#f59e0b' : 'primary.main' }} />}
              </ListItemButton>
            ))}
            {loadingRoles && <Box sx={{ p: 2, textAlign: 'center' }}><CircularProgress size={30} thickness={5} /></Box>}
          </Box>
        </Box>

        {/* Pane 2: Modules Selection */}
        <Box sx={{
          width: 320,
          bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f1f5f9',
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.paper' : '#e2e8f0' }}>
            <Typography variant="subtitle2" color="text.secondary" fontWeight="800" sx={{ letterSpacing: '0.05em' }}>
              APPLICATION MODULES
            </Typography>
          </Box>
          <Box sx={{ flex: 1, overflowY: 'auto', p: 1 }}>
            {APP_MODULES.map((module) => {
              const isActive = activeModule === module.id;
              const activeCount = Object.keys(permissions).filter(key => key.startsWith(`${module.id}:`) && permissions[key]).length;

              return (
                <ListItemButton
                  key={module.id}
                  onClick={() => setActiveModule(module.id)}
                  sx={{
                    py: 2,
                    px: 3,
                    borderRadius: 3,
                    mb: 1,
                    bgcolor: (theme) => isActive ? (theme.palette.mode === 'dark' ? 'background.paper' : 'white') : 'transparent',
                    boxShadow: (theme) => isActive && theme.palette.mode !== 'dark' ? '0 4px 6px -1px rgb(0 0 0 / 0.1)' : 'none',
                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': { bgcolor: (theme) => isActive ? (theme.palette.mode === 'dark' ? 'background.paper' : 'white') : theme.palette.action.hover }
                  }}
                >
                  <Box sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: isActive ? 'primary.main' : 'transparent',
                    mr: 2,
                    transition: 'all 0.3s'
                  }} />
                  <ListItemText
                    primary={module.name}
                    primaryTypographyProps={{
                      fontWeight: isActive ? 800 : 600,
                      color: isActive ? 'text.primary' : 'text.secondary',
                      fontSize: '0.9rem'
                    }}
                  />
                  {activeCount > 0 && (
                    <Box sx={{
                      bgcolor: isActive ? 'primary.main' : 'action.selected',
                      color: 'white',
                      px: 1.2, py: 0.2,
                      borderRadius: 1.5,
                      fontSize: '0.75rem',
                      fontWeight: 800
                    }}>
                      {activeCount}
                    </Box>
                  )}
                </ListItemButton>
              );
            })}
          </Box>
        </Box>

        {/* Pane 3: Granular Permissions Grid */}
        <Box sx={{ flex: 1, bgcolor: 'background.paper', display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ p: 4, pb: 2 }}>
            <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
              <Typography variant="h5" fontWeight="900" color="text.primary">
                {APP_MODULES.find(m => m.id === activeModule)?.name}
              </Typography>
              <Box sx={{ bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1), color: 'primary.main', px: 1.5, py: 0.5, borderRadius: 2, fontSize: '0.75rem', fontWeight: 800 }}>
                {APP_MODULES.find(m => m.id === activeModule)?.pages.length} PAGES
              </Box>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
              Toggle individual permissions for each sub-page within this module.
            </Typography>
          </Box>

          <Box sx={{ flex: 1, p: 4, pt: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <TableContainer component={Paper} elevation={0} sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 4,
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden'
            }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{
                      fontWeight: 900,
                      color: 'text.primary',
                      py: 2.5,
                      bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc',
                      fontSize: '0.8rem',
                      borderBottom: '2px solid',
                      borderBottomColor: 'divider'
                    }}>
                      {(() => {
                        const mod = APP_MODULES.find(m => m.id === activeModule);
                        const allKeys = mod ? mod.pages.flatMap(p => AVAILABLE_ACTIONS.map(a => `${activeModule}:${p.id}:${a.id}`)) : [];
                        const checkedCount = allKeys.filter(k => permissions[k]).length;
                        const allChecked = allKeys.length > 0 && checkedCount === allKeys.length;
                        const someChecked = checkedCount > 0 && !allChecked;
                        return (
                          <Stack direction="row" alignItems="center" spacing={0.75}>
                            <Tooltip title={allChecked ? 'Deselect all permissions in this module' : 'Select all permissions in this module'} arrow placement="top">
                              <Checkbox
                                size="small"
                                checked={allChecked}
                                indeterminate={someChecked}
                                onChange={() => handleSelectAllModule(activeModule)}
                                disableRipple
                                sx={{
                                  p: 0.5,
                                  color: 'text.disabled',
                                  '&.Mui-checked': { color: 'primary.main' },
                                  '&.MuiCheckbox-indeterminate': { color: 'primary.main' },
                                  '&:hover': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08) }
                                }}
                              />
                            </Tooltip>
                            <span>PAGE / SECTION</span>
                          </Stack>
                        );
                      })()}
                    </TableCell>
                    {AVAILABLE_ACTIONS.map(action => (
                      <TableCell key={action.id} align="center" sx={{
                        fontWeight: 900,
                        color: 'text.primary',
                        py: 2.5,
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc',
                        fontSize: '0.8rem',
                        borderBottom: '2px solid',
                        borderBottomColor: 'divider'
                      }}>
                        <Stack direction="row" alignItems="center" justifyContent="center" spacing={0.5}>
                          {action.label}
                          <Tooltip title={action.description} arrow placement="top">
                            <Box component="span" sx={{ cursor: 'help', display: 'flex', opacity: 0.5 }}><InfoIcon sx={{ fontSize: 14 }} /></Box>
                          </Tooltip>
                        </Stack>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody sx={{ overflowY: 'auto' }}>
                  {APP_MODULES.find(m => m.id === activeModule)?.pages.map(page => {
                    const pageKeys = AVAILABLE_ACTIONS.map(a => `${activeModule}:${page.id}:${a.id}`);
                    const pageCheckedCount = pageKeys.filter(k => permissions[k]).length;
                    const pageAllChecked = pageCheckedCount === pageKeys.length;
                    const pageSomeChecked = pageCheckedCount > 0 && !pageAllChecked;
                    return (
                      <TableRow key={page.id} hover sx={{ '&:hover': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.02) } }}>
                        <TableCell sx={{ fontWeight: 700, color: 'text.primary', py: 2, fontSize: '0.9rem' }}>
                          <Stack direction="row" alignItems="center" spacing={0.5}>
                            <Tooltip title={pageAllChecked ? `Deselect all actions for "${page.name}"` : `Select all actions for "${page.name}"`} arrow placement="right">
                              <Checkbox
                                size="small"
                                checked={pageAllChecked}
                                indeterminate={pageSomeChecked}
                                onChange={() => handleSelectAllPage(activeModule, page.id)}
                                disableRipple
                                sx={{
                                  p: 0.5,
                                  color: 'text.disabled',
                                  '&.Mui-checked': { color: 'primary.main' },
                                  '&.MuiCheckbox-indeterminate': { color: 'primary.main' },
                                  '&:hover': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08) }
                                }}
                              />
                            </Tooltip>
                            <span>{page.name}</span>
                          </Stack>
                        </TableCell>
                        {AVAILABLE_ACTIONS.map(action => {
                          const isChecked = permissions[`${activeModule}:${page.id}:${action.id}`] || false;
                          return (
                            <TableCell key={action.id} align="center" sx={{ py: 2 }}>
                              <Checkbox
                                checked={isChecked}
                                onChange={() => handleToggle(activeModule, page.id, action.id)}
                                disableRipple
                                sx={{
                                  '&.Mui-checked': { color: 'primary.main' },
                                  '&:hover': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05) }
                                }}
                              />
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    );
                  })}
                  {/* Fill empty space if few pages */}
                  {[...Array(Math.max(0, 8 - (APP_MODULES.find(m => m.id === activeModule)?.pages.length || 0)))].map((_, i) => (
                    <TableRow key={`empty-${i}`} sx={{ height: 61 }}>
                      <TableCell colSpan={AVAILABLE_ACTIONS.length + 1} />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Box sx={{ mt: 3, p: 2, bgcolor: (theme) => theme.palette.mode === 'dark' ? alpha('#f59e0b', 0.15) : alpha('#f59e0b', 0.05), border: '1px dashed #f59e0b', borderRadius: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
              <Box sx={{ color: '#f59e0b' }}><LockIcon /></Box>
              <Typography variant="body2" sx={{ fontSize: '0.75rem', fontWeight: 600, color: (theme) => theme.palette.mode === 'dark' ? '#f59e0b' : '#92400e' }}>
                <b>Security Tip:</b> Least privilege approach is recommended. Only grant the specific permissions required for the user to perform their specific role tasks.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Notifications */}
      <Snackbar open={toast.open} autoHideDuration={4000} onClose={() => setToast({ ...toast, open: false })}>
        <Alert severity={toast.severity} variant="filled" sx={{ width: '100%', borderRadius: 3, boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}>
          {toast.message}
        </Alert>
      </Snackbar>

    </Box>
  );
}

function Stack({ children, direction = "row", spacing = 0, alignItems = "stretch", justifyContent = "flex-start", ...props }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: direction,
        gap: spacing,
        alignItems,
        justifyContent,
        ...props.sx
      }}
      {...props}
    >
      {children}
    </Box>
  );
}
