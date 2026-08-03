'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Paper,
  Alert,
  TextField,
  Menu,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  InputAdornment,
  IconButton,
  Grid,
  TablePagination,
  Card,
  CardContent,
  Snackbar,
  Tooltip as MuiTooltip,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  ReceiptLong as ReceiptIcon,
  Dashboard as DashboardIcon,
  CheckCircleOutline as CheckIcon,
  WarningAmber as WarningIcon,
  Assessment as AssessmentIcon,
  AccountBalanceWallet as AccountBalanceWalletIcon,
  UploadFile as UploadFileIcon,
  Description as DescriptionIcon,
  FactCheck as FactCheckIcon,
  CalendarToday as CalendarTodayIcon,
  History as HistoryIcon,
  HealthAndSafety as HealthAndSafetyIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';


export default function AccountingGST({ defaultTab = 'dashboard' }) {
  const { canViewAmounts, canExport } = usePagePermissions();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const location = useLocation();

  // Determine active tab from URL path
  const activeTab = useMemo(() => {
    if (location.pathname.endsWith('/gst-transactions')) return 'transactions';
    if (location.pathname.endsWith('/gst-settings')) return 'settings';
    if (location.pathname.endsWith('/gst-summary')) return 'summary';
    if (location.pathname.endsWith('/gst-liability')) return 'liability';
    if (location.pathname.endsWith('/gst-gstr1')) return 'gstr1';
    if (location.pathname.endsWith('/gst-gstr3b')) return 'gstr3b';
    if (location.pathname.endsWith('/gst-itc')) return 'itc';
    if (location.pathname.endsWith('/gst-calendar')) return 'calendar';
    if (location.pathname.endsWith('/gst-history')) return 'history';
    if (location.pathname.endsWith('/gst-health')) return 'health';
    return 'dashboard';
  }, [location.pathname]);

  const handleTabChange = (tabName) => {
    if (tabName === 'dashboard') navigate('/finance/gst');
    else if (tabName === 'transactions') navigate('/finance/gst-transactions');
    else if (tabName === 'settings') navigate('/finance/gst-settings');
    else if (tabName === 'summary') navigate('/finance/gst-summary');
    else if (tabName === 'liability') navigate('/finance/gst-liability');
    else if (tabName === 'gstr1') navigate('/finance/gst-gstr1');
    else if (tabName === 'gstr3b') navigate('/finance/gst-gstr3b');
    else if (tabName === 'itc') navigate('/finance/gst-itc');
    else if (tabName === 'calendar') navigate('/finance/gst-calendar');
    else if (tabName === 'history') navigate('/finance/gst-history');
    else if (tabName === 'health') navigate('/finance/gst-health');
  };

  // State: Month & Year selector for Dashboard
  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [chartPeriod, setChartPeriod] = useState('6m');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [visibleWidgets, setVisibleWidgets] = useState(() => {
    try {
      const saved = localStorage.getItem('shori_gst_visible_widgets');
      if (saved) return JSON.parse(saved);
    } catch {}
    return {
      kpiOutput: true,
      kpiItc: true,
      kpiNet: true,
      kpiFiling: true,
      kpiAccuracy: true,
      kpiPending: true,
      trendChart: true,
      compositionChart: true,
      calendar: true,
      ledger: true,
      insights: true,
    };
  });
  const [configOpen, setConfigOpen] = useState(false);

  // Dashboard Data State
  const [dashboardData, setDashboardData] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState(null);

  // Transactions State
  const [transactions, setTransactions] = useState([]);
  const [txnTotal, setTxnTotal] = useState(0);
  const [txnPage, setTxnPage] = useState(1);
  const [txnPageSize, setTxnPageSize] = useState(25);
  const [txnSearch, setTxnSearch] = useState('');
  const [txnType, setTxnType] = useState('');
  const [txnStatus, setTxnStatus] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [txnsLoading, setTxnsLoading] = useState(true);
  const [txnsError, setTxnsError] = useState(null);
  const [exportAnchorEl, setExportAnchorEl] = useState(null);
  const isExportMenuOpen = Boolean(exportAnchorEl);
  const handleExportClick = (event) => {
    setExportAnchorEl(event.currentTarget);
  };
  const handleExportClose = () => {
    setExportAnchorEl(null);
  };

  const [anchorElMap, setAnchorElMap] = useState({});
  const handleMenuOpen = (menuKey, event) => {
    setAnchorElMap(prev => ({ ...prev, [menuKey]: event.currentTarget }));
  };
  const handleMenuClose = (menuKey) => {
    setAnchorElMap(prev => ({ ...prev, [menuKey]: null }));
  };

  const [columnVisibility, setColumnVisibility] = useState({
    date: true,
    ref: true,
    type: true,
    taxable: true,
    rate: true,
    amount: true,
    gstType: true,
    status: true,
  });

  const [complianceAlerts, setComplianceAlerts] = useState({
    notify_30: true,
    notify_15: true,
    notify_7: true,
    notify_3: true,
    notify_due: true,
  });

  // Settings State
  const DEFAULT_GST_CONFIG = useMemo(() => ({
    legal_name: '',
    trade_name: '',
    gstin: '',
    pan: '',
    tan: '',
    cin: '',
    constitution: 'private_company',
    state: '',
    state_code: '',
    registration_date: '',
    communication_email: '',
    contact_number: '',
    registration_type: 'regular',
    filing_frequency: 'monthly',
    registration_status: 'active',
    effective_date: '',
    turnover_threshold: '4000000',
    aggregate_turnover: '12000000',
    is_sez_unit: false,
    is_sez_developer: false,
    is_isd: false,
    is_ecom_operator: false,
    tax_slabs: [
      { id: 'slab_1', name: '0% (Nil Rated)', cgst: 0, sgst: 0, igst: 0, cess: 0, description: 'Exempted essential goods and books', status: 'active' },
      { id: 'slab_2', name: '0.25% (Concessional)', cgst: 0.125, sgst: 0.125, igst: 0.25, cess: 0, description: 'Rough precious stones', status: 'active' },
      { id: 'slab_3', name: '3% (Precious Metals)', cgst: 1.5, sgst: 1.5, igst: 3, cess: 0, description: 'Gold, silver, and jewelry', status: 'active' },
      { id: 'slab_4', name: '5% (Concessional)', cgst: 2.5, sgst: 2.5, igst: 5, cess: 0, description: 'Basic foodstuffs, garments < 1000', status: 'active' },
      { id: 'slab_5', name: '12% (Standard Lower)', cgst: 6, sgst: 6, igst: 12, cess: 0, description: 'Processed food, cellphones, standard services', status: 'active' },
      { id: 'slab_6', name: '18% (Standard Higher)', cgst: 9, sgst: 9, igst: 18, cess: 0, description: 'Capital goods, software, professional services', status: 'active' },
      { id: 'slab_7', name: '28% (Luxury & Sin)', cgst: 14, sgst: 14, igst: 28, cess: 12, description: 'Motor vehicles, luxury products', status: 'active' }
    ],
    default_gst_rate: '18.00',
    itc_on_purchases: true,
    itc_on_capital_goods: true,
    itc_on_services: true,
    itc_on_imports: true,
    block_itc_personal: true,
    block_itc_vehicles: true,
    block_itc_food: true,
    block_itc_benefits: true,
    itc_matching_mode: 'gstr2b_reconciliation',
    auto_reversal_rules: 'supplier_unpaid_180_days',
    itc_reclaim_rules: 'on_supplier_payment_reconciliation',
    b2b_gst_treatment: 'apply_standard',
    b2c_gst_treatment: 'apply_standard',
    interstate_gst_treatment: 'apply_igst',
    intrastate_gst_treatment: 'apply_cgst_sgst',
    export_gst_treatment: 'lut_exempt',
    sez_gst_treatment: 'zero_rated',
    default_place_of_supply: 'billing_address',
    interstate_logic: 'shipping_state_different',
    intrastate_logic: 'shipping_state_same',
    export_treatment: 'zero_rated_with_lut',
    import_treatment: 'apply_igst_on_customs',
    invoice_prefix: 'SHORI/GST/',
    invoice_numbering_format: 'prefix-sequence',
    financial_year_format: 'YY-YY',
    hsn_mandatory: true,
    sac_mandatory: true,
    qr_code_enabled: true,
    gst_breakdown_visibility: 'always_show',
    round_off_rules: 'nearest_rupee',
    e_invoicing_enabled: false,
    irp_provider: 'nic',
    api_credentials_username: '',
    api_credentials_password: '',
    auth_key: '',
    auto_generate_irn: true,
    auto_generate_qr_code: true,
    irn_retry_rules: '3_times_exponential',
    e_way_bill_enabled: false,
    distance_threshold: 50000,
    vehicle_validation: true,
    transporter_validation: true,
    auto_generate_e_way_bill: false,
    tds_enabled: false,
    default_tds_rate: 2.0,
    tds_section_mapping: 'sec_51',
    vendor_tds_rules: 'apply_above_250k',
    customer_tds_rules: 'apply_above_250k',
    tds_threshold_limits: 250000,
    tcs_enabled: false,
    marketplace_tcs: 1.0,
    e_commerce_tcs: 1.0,
    tcs_collection_threshold: 250000,
    tcs_collection_frequency: 'monthly',
    rcm_enabled: false,
    rcm_vendor_categories: ['unregistered_vendor', 'gta_services'],
    rcm_expense_categories: ['freight', 'legal_fees'],
    auto_rcm_detection: true,
    rcm_posting_rules: 'create_liability_and_itc',
    gstr1_frequency: 'monthly',
    gstr3b_frequency: 'monthly',
    gstr9_enabled: true,
    gstr9c_enabled: true,
    due_date_alerts: '5_days_prior',
    hsn_sac_codes: [
      { id: 'hs_1', code: '998311', type: 'SAC', description: 'Management consulting and advisory services', rate: '18.00', status: 'active' },
      { id: 'hs_2', code: '847130', type: 'HSN', description: 'Data processing machines, portable (laptops)', rate: '18.00', status: 'active' },
      { id: 'hs_3', code: '998713', type: 'SAC', description: 'Software development and IT support', rate: '18.00', status: 'active' },
    ],
    exempt_products: ['grains', 'salt', 'milk'],
    nil_rated_products: ['books', 'agricultural_tools'],
    non_gst_supplies: ['petrol', 'alcohol'],
    import_goods_treatment: 'apply_igst',
    import_services_treatment: 'apply_igst_rcm',
    export_with_lut: true,
    export_without_lut: false,
    custom_duty_mapping: 'add_to_cost_base',
    igst_treatment: 'claim_itc',
    sez_customer_rules: 'zero_rated_with_lut',
    sez_vendor_rules: 'treat_as_import',
    sez_zero_rated_supply_rules: 'apply_igst_exemption',
    sez_documentation: ['bill_of_export', 'sez_endorsement'],
    credit_note_prefix: 'SHORI/CN/',
    debit_note_prefix: 'SHORI/DN/',
    auto_gst_adjustment: true,
    note_approval_workflow: 'two_manager_signoff',
    automation_rules: [
      { id: 'ar_1', name: 'Apply CGST + SGST for Local Customers', condition: 'Customer State == Shipping State', action: 'CGST 9% + SGST 9%', status: 'active' },
      { id: 'ar_2', name: 'Apply IGST for Inter-state Customers', condition: 'Customer State != Shipping State', action: 'IGST 18%', status: 'active' },
      { id: 'ar_3', name: 'Apply Zero Rate with LUT for SEZ', condition: 'Customer Tags contains SEZ', action: 'IGST 0% (Zero Rated)', status: 'active' },
    ],
    validate_gstin: true,
    validate_pan: true,
    validate_hsn: true,
    duplicate_invoice_detection: true,
    duplicate_gst_filing_detection: true,
    alert_filing_due: true,
    alert_itc_mismatch: true,
    alert_return_rejection: true,
    alert_invoice_failure: true,
    alert_e_invoice_failure: true,
    alert_e_way_bill_failure: true,
    output_cgst_ledger: '100201 - CGST Output Liability',
    output_sgst_ledger: '100202 - SGST Output Liability',
    output_igst_ledger: '100203 - IGST Output Liability',
    input_cgst_ledger: '100301 - CGST Input Credit',
    input_sgst_ledger: '100302 - SGST Input Credit',
    input_igst_ledger: '100303 - IGST Input Credit',
    tds_gst_receivable: '100401 - GST TDS Receivable',
    tcs_gst_receivable: '100402 - GST TCS Receivable',
    auto_posting: true,
    auto_reconciliation: true,
    auto_itc_matching: true,
    auto_filing_prep: false,
    fiscal_year: 'april_march',
    timezone: 'Asia/Kolkata',
    decimal_precision: 2,
    rounding_rules: 'round_half_up',
    audit_log_enabled: true,
  }), []);

  const [settings, setSettings] = useState(DEFAULT_GST_CONFIG);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});
  const [activeSettingsSection, setActiveSettingsSection] = useState('identity');
  const [hasDraft, setHasDraft] = useState(false);

  const [auditLog, setAuditLog] = useState(() => {
    try {
      const stored = localStorage.getItem('shori_gst_settings_audit_log');
      if (stored) return JSON.parse(stored);
    } catch {}
    return [
      { id: 1, timestamp: new Date(Date.now() - 3600000 * 24).toISOString(), user: 'jatin', action: 'Initialize GST Settings', details: 'Initial compliance center configuration' },
      { id: 2, timestamp: new Date(Date.now() - 3600000 * 4).toISOString(), user: 'jatin', action: 'Update Basic Identity', details: 'Updated registered Trade Name and State Code verification defaults' },
    ];
  });

  // Day 2 Compliance States
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(null);

  const [liabilityData, setLiabilityData] = useState(null);
  const [liabilityLoading, setLiabilityLoading] = useState(true);
  const [liabilityError, setLiabilityError] = useState(null);

  const [gstr1Data, setGstr1Data] = useState(null);
  const [gstr1Loading, setGstr1Loading] = useState(true);
  const [gstr1Error, setGstr1Error] = useState(null);
  const [gstr1SubTab, setGstr1SubTab] = useState('b2b');
  const [gstr1Validated, setGstr1Validated] = useState(false);

  const [gstr3bData, setGstr3bData] = useState(null);
  const [gstr3bLoading, setGstr3bLoading] = useState(true);
  const [gstr3bError, setGstr3bError] = useState(null);

  const [itcData, setItcData] = useState(null);
  const [itcLoading, setItcLoading] = useState(true);
  const [itcError, setItcError] = useState(null);
  const [itcVendor, setItcVendor] = useState('');
  const [itcEligibility, setItcEligibility] = useState('');

  const [calendarData, setCalendarData] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [calendarError, setCalendarError] = useState(null);

  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(null);

  const [healthData, setHealthData] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(null);

  // Filters for reports
  const [filterFY, setFilterFY] = useState('2026-2027');
  const [filterMonth, setFilterMonth] = useState('6'); // June as default based on system date
  const [filterQuarter, setFilterQuarter] = useState('all');
  const [filterGSTType, setFilterGSTType] = useState('all');
  const [filterBU, setFilterBU] = useState('all');

  // Settings Categories List
  const settingsCategories = useMemo(() => [
    { key: 'identity', label: 'Business & Tax Identity', desc: 'Verify legal details, registered trade names, and statutory identifiers.' },
    { key: 'registration', label: 'GST Registration', desc: 'Select schemes, CASUAL status, ISD role, or SEZ registrations.' },
    { key: 'rates', label: 'Tax Rates & Slabs', desc: 'Create, modify, and delete active GST slabs and custom tax rates.' },
    { key: 'itc', label: 'Input Tax Credit (ITC)', desc: 'Set eligibility rules, blocked category codes, and automatic reconciliation algorithms.' },
    { key: 'output', label: 'Output Tax Rules', desc: 'Manage tax treatments for B2B/B2C, local splits, and zero-rated outbound sales.' },
    { key: 'pos', label: 'Place of Supply Rules', desc: 'Specify billing versus shipping overrides for CGST/SGST/IGST automation.' },
    { key: 'invoice', label: 'Invoice Configuration', desc: 'Set serial patterns, financial year suffixes, and mandatory HSN fields.' },
    { key: 'einvoice', label: 'E-Invoicing', desc: 'Configure NIC/IRP API connectors, automation triggers, and retry sequences.' },
    { key: 'eway', label: 'E-Way Bill', desc: 'Define threshold rules, validator triggers, and transporter settings.' },
    { key: 'tds', label: 'TDS Settings', desc: 'Configure Section 51 tax deductions, supplier exclusions, and limits.' },
    { key: 'tcs', label: 'TCS Settings', desc: 'Manage e-commerce collection schedules, percentages, and frequency.' },
    { key: 'rcm', label: 'Reverse Charge Mechanism', desc: 'Set RCM expense lists, unregistered vendor postings, and voucher settings.' },
    { key: 'return', label: 'GST Return Settings', desc: 'Set GSTR filing cycles, email alerts, and compliance deadlines.' },
    { key: 'hsn', label: 'HSN/SAC Management', desc: 'Maintain the master database of HSN/SAC codes and default slab mappings.' },
    { key: 'exempt', label: 'Exempt & Nil Rated Supplies', desc: 'Categorize zero-tax or out-of-scope non-GST transaction products.' },
    { key: 'import_export', label: 'Import & Export GST', desc: 'Manage Letter of Undertaking (LUT) files, custom duties, and port codes.' },
    { key: 'sez', label: 'SEZ Transactions', desc: 'Configure zero-rated supply overrides and SEZ documentation checklists.' },
    { key: 'notes', label: 'Credit/Debit Notes', desc: 'Define adjustment rules, prefixes, and multi-tier approval workflows.' },
    { key: 'automation', label: 'GST Automation Rules', desc: 'Configure custom conditional rules to apply specific GST slabs.' },
    { key: 'validation', label: 'Validation Rules', desc: 'Set validation strictness for PAN, GSTIN, and duplicate invoices.' },
    { key: 'alerts', label: 'Alerts & Compliance', desc: 'Toggle instant notifications for ITC mismatches, filing delays, or errors.' },
    { key: 'mapping', label: 'Bank & Payment Mapping', desc: 'Map GST liabilities and credit inputs to double-entry ledger accounts.' },
    { key: 'advanced', label: 'Advanced GST Preferences', desc: 'Set precision levels, rounding math, and default fiscal periods.' },
  ], []);

  // Toast notification
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });

  // 1. Fetch Dashboard API
  const fetchDashboard = async () => {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const res = await apiClient(
        `/api/accounting/gst/dashboard/?month=${selectedMonth}&year=${selectedYear}`,
        { cache: 'no-store' }
      );
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setDashboardError(payload?.message || 'Failed to load GST dashboard metrics.');
        return;
      }
      setDashboardData(payload?.data ?? payload);
    } catch {
      setDashboardError('Could not reach dashboard API.');
    } finally {
      setDashboardLoading(false);
    }
  };

  // 2. Fetch Transactions API
  const fetchTransactions = async (overrides = {}) => {
    const actualOverrides = overrides && typeof overrides === 'object' && !overrides.nativeEvent ? overrides : {};
    setTxnsLoading(true);
    setTxnsError(null);
    try {
      const params = new URLSearchParams({
        page: actualOverrides.page !== undefined ? actualOverrides.page : txnPage,
        page_size: txnPageSize,
        q: actualOverrides.q !== undefined ? actualOverrides.q : txnSearch,
        type: actualOverrides.type !== undefined ? actualOverrides.type : txnType,
        status: actualOverrides.status !== undefined ? actualOverrides.status : txnStatus,
        date_from: actualOverrides.date_from !== undefined ? actualOverrides.date_from : dateFrom,
        date_to: actualOverrides.date_to !== undefined ? actualOverrides.date_to : dateTo,
      });
      const res = await apiClient(`/api/accounting/gst/transactions/?${params.toString()}`, {
        cache: 'no-store',
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setTxnsError(payload?.message || 'Failed to load GST ledger transactions.');
        return;
      }
      const data = payload?.data ?? payload;
      setTransactions(data.results || []);
      setTxnTotal(data.count || 0);
    } catch {
      setTxnsError('Could not reach transactions API.');
    } finally {
      setTxnsLoading(false);
    }
  };

  const handleResetFilters = () => {
    const willTriggerEffect =
      txnType !== '' ||
      txnStatus !== '' ||
      txnPage !== 1;

    setTxnSearch('');
    setTxnType('');
    setTxnStatus('');
    setDateFrom('');
    setDateTo('');
    setTxnPage(1);

    if (!willTriggerEffect) {
      fetchTransactions({
        page: 1,
        q: '',
        type: '',
        status: '',
        date_from: '',
        date_to: '',
      });
    }
  };

  // 3. Fetch Settings API
  const fetchSettings = async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const res = await apiClient('/api/accounting/gst/settings/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setSettingsError(payload?.message || 'Failed to load GST Settings.');
        return;
      }
      const data = payload?.data ?? payload;

      let localData = {};
      try {
        const stored = localStorage.getItem('shori_gst_advanced_settings');
        if (stored) {
          localData = JSON.parse(stored);
        }
      } catch (err) {
        console.error("Failed to parse local storage GST settings", err);
      }

      setSettings({
        ...DEFAULT_GST_CONFIG,
        ...localData,
        gstin: data.gstin || localData.gstin || '',
        legal_name: data.legal_name || localData.legal_name || '',
        state: data.state || localData.state || '',
        registration_type: data.registration_type || localData.registration_type || 'regular',
        filing_frequency: data.filing_frequency || localData.filing_frequency || 'monthly',
        default_gst_rate: String(data.default_gst_rate || localData.default_gst_rate || '18.00'),
      });
    } catch {
      setSettingsError('Could not reach GST settings API.');
    } finally {
      setSettingsLoading(false);
    }
  };

  // Check if draft exists in local storage on load
  useEffect(() => {
    try {
      const draft = localStorage.getItem('shori_gst_advanced_settings_draft');
      if (draft) {
        setHasDraft(true);
      }
    } catch {}
  }, []);

  // Day 2 fetches
  const fetchSummary = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const params = new URLSearchParams({
        year: filterFY.split('-')[0],
        month: filterMonth,
        quarter: filterQuarter,
        gst_type: filterGSTType,
        bu: filterBU
      });
      const res = await apiClient(`/api/accounting/gst/summary/?${params.toString()}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setSummaryError(payload?.message || 'Failed to load GST summary metrics.');
        return;
      }
      setSummaryData(payload?.data ?? payload);
    } catch {
      setSummaryError('Could not reach GST Summary API.');
    } finally {
      setSummaryLoading(false);
    }
  };

  const fetchLiability = async () => {
    setLiabilityLoading(true);
    setLiabilityError(null);
    try {
      const params = new URLSearchParams({
        year: filterFY.split('-')[0],
        month: filterMonth
      });
      const res = await apiClient(`/api/accounting/gst/liability/?${params.toString()}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setLiabilityError(payload?.message || 'Failed to load GST liability metrics.');
        return;
      }
      setLiabilityData(payload?.data ?? payload);
    } catch {
      setLiabilityError('Could not reach GST Liability API.');
    } finally {
      setLiabilityLoading(false);
    }
  };

  const fetchGstr1 = async () => {
    setGstr1Loading(true);
    setGstr1Error(null);
    try {
      const params = new URLSearchParams({
        year: filterFY.split('-')[0],
        month: filterMonth
      });
      const res = await apiClient(`/api/accounting/gst/gstr1/?${params.toString()}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setGstr1Error(payload?.message || 'Failed to load GSTR-1 preparation data.');
        return;
      }
      setGstr1Data(payload?.data ?? payload);
    } catch {
      setGstr1Error('Could not reach GSTR-1 API.');
    } finally {
      setGstr1Loading(false);
    }
  };

  const fetchGstr3b = async () => {
    setGstr3bLoading(true);
    setGstr3bError(null);
    try {
      const params = new URLSearchParams({
        year: filterFY.split('-')[0],
        month: filterMonth
      });
      const res = await apiClient(`/api/accounting/gst/gstr3b/?${params.toString()}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setGstr3bError(payload?.message || 'Failed to load GSTR-3B preparation data.');
        return;
      }
      setGstr3bData(payload?.data ?? payload);
    } catch {
      setGstr3bError('Could not reach GSTR-3B API.');
    } finally {
      setGstr3bLoading(false);
    }
  };

  const fetchItc = async () => {
    setItcLoading(true);
    setItcError(null);
    try {
      const params = new URLSearchParams({
        vendor: itcVendor,
        eligibility: itcEligibility
      });
      const res = await apiClient(`/api/accounting/gst/itc-reconciliation/?${params.toString()}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setItcError(payload?.message || 'Failed to load GSTR-2B ITC reconciliation data.');
        return;
      }
      setItcData(payload?.data ?? payload);
    } catch {
      setItcError('Could not reach ITC Reconciliation API.');
    } finally {
      setItcLoading(false);
    }
  };

  const fetchCalendar = async () => {
    setCalendarLoading(true);
    setCalendarError(null);
    try {
      const res = await apiClient('/api/accounting/gst/compliance-calendar/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setCalendarError(payload?.message || 'Failed to load Compliance Calendar.');
        return;
      }
      setCalendarData(payload?.data ?? payload);
    } catch {
      setCalendarError('Could not reach Calendar API.');
    } finally {
      setCalendarLoading(false);
    }
  };

  const fetchHistory = async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await apiClient('/api/accounting/gst/filing-history/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setHistoryError(payload?.message || 'Failed to load Filing History.');
        return;
      }
      setHistoryData(payload?.data ?? payload);
    } catch {
      setHistoryError('Could not reach Filing History API.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const fetchHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const res = await apiClient('/api/accounting/gst/health/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setHealthError(payload?.message || 'Failed to load Health indicators.');
        return;
      }
      setHealthData(payload?.data ?? payload);
    } catch {
      setHealthError('Could not reach GST Health API.');
    } finally {
      setHealthLoading(false);
    }
  };

  // Trigger data fetching based on active tab
  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchDashboard();
    } else if (activeTab === 'transactions') {
      fetchTransactions();
    } else if (activeTab === 'settings') {
      fetchSettings();
    } else if (activeTab === 'summary') {
      fetchSummary();
    } else if (activeTab === 'liability') {
      fetchLiability();
    } else if (activeTab === 'gstr1') {
      fetchGstr1();
    } else if (activeTab === 'gstr3b') {
      fetchGstr3b();
    } else if (activeTab === 'itc') {
      fetchItc();
    } else if (activeTab === 'calendar') {
      fetchCalendar();
    } else if (activeTab === 'history') {
      fetchHistory();
    } else if (activeTab === 'health') {
      fetchHealth();
    }
  }, [
    activeTab, selectedMonth, selectedYear,
    txnPage, txnPageSize, txnType, txnStatus,
    filterFY, filterMonth, filterQuarter, filterGSTType, filterBU,
    itcVendor, itcEligibility
  ]);

  const handleFieldChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const validateField = (key, value) => {
    let error = '';
    if (key === 'gstin' && value) {
      const regex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
      if (!regex.test(value)) {
        error = 'Invalid GSTIN format (Expected pattern: 22AAAAA1111A1Z1)';
      }
    } else if (key === 'pan' && value) {
      const regex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
      if (!regex.test(value)) {
        error = 'Invalid PAN format (Expected: ABCDE1234F)';
      }
    } else if (key === 'communication_email' && value) {
      const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!regex.test(value)) {
        error = 'Invalid email format';
      }
    } else if (key === 'contact_number' && value) {
      const regex = /^[0-9]{10}$/;
      if (!regex.test(value)) {
        error = 'Invalid contact number (Expected 10 digits)';
      }
    } else if (key === 'tax_slabs' && value) {
      const invalidSlab = value.find(slab => Number(slab.cgst) + Number(slab.sgst) !== Number(slab.igst));
      if (invalidSlab) {
        error = `Invalid slab values in "${invalidSlab.name}": CGST (${invalidSlab.cgst}%) + SGST (${invalidSlab.sgst}%) must equal IGST (${invalidSlab.igst}%)`;
      }
    } else if (key === 'api_credentials_username' && settings.e_invoicing_enabled && !value) {
      error = 'IRP username is required when e-invoicing is enabled';
    } else if (key === 'api_credentials_password' && settings.e_invoicing_enabled && !value) {
      error = 'IRP password is required when e-invoicing is enabled';
    } else if (key === 'irp_provider' && settings.e_invoicing_enabled && !value) {
      error = 'IRP provider is required when e-invoicing is enabled';
    } else if (key === 'distance_threshold' && settings.e_way_bill_enabled) {
      if (Number(value) <= 0) {
        error = 'Valuation limit threshold must be positive';
      }
    } else if (key === 'due_date_alerts' && value && !isNaN(value)) {
      if (Number(value) < 1 || Number(value) > 31) {
        error = 'Return offset reminder days must be between 1 and 31';
      }
    } else if (key === 'default_tds_rate' && settings.tds_enabled && (Number(value) < 0 || Number(value) > 100)) {
      error = 'TDS rate must be between 0% and 100%';
    } else if (key === 'tds_threshold_limits' && settings.tds_enabled && Number(value) <= 0) {
      error = 'TDS threshold must be positive';
    } else if (key === 'marketplace_tcs' && settings.tcs_enabled && (Number(value) < 0 || Number(value) > 100)) {
      error = 'Marketplace TCS rate must be between 0% and 100%';
    } else if (key === 'e_commerce_tcs' && settings.tcs_enabled && (Number(value) < 0 || Number(value) > 100)) {
      error = 'E-commerce TCS rate must be between 0% and 100%';
    } else if (key === 'tcs_collection_threshold' && settings.tcs_enabled && Number(value) <= 0) {
      error = 'TCS threshold must be positive';
    } else if (key === 'hsn_sac_codes' && value) {
      const invalidCode = value.find(item => !/^[0-9]{4}$|^[0-9]{6}$|^[0-9]{8}$/.test(item.code));
      if (invalidCode) {
        error = `Invalid HSN/SAC code "${invalidCode.code}". Must be exactly 4, 6, or 8 digits.`;
      }
    } else if ((key.endsWith('_ledger') || key.endsWith('_receivable')) && !value) {
      error = 'Ledger account mapping is required';
    }

    setValidationErrors(prev => ({
      ...prev,
      [key]: error
    }));
    return !error;
  };

  const fieldTooltips = {
    legal_name: "Statutory name of your registered business entity as per GST portal.",
    trade_name: "Brand name or commercial name of the business operation.",
    gstin: "15-character Goods and Services Tax Identification Number (e.g., 07AAAAA1111A1Z1).",
    pan: "10-character Permanent Account Number linked to the business.",
    tan: "Tax Deduction Account Number for withholding tax collection.",
    cin: "21-character Corporate Identity Number for registered entities.",
    constitution: "Select legal business entity constitution.",
    state: "The primary state where the entity registration is active.",
    state_code: "2-digit statutory state code prefix for GSTIN calculations.",
    registration_date: "Date when your GST registration certificate was issued.",
    communication_email: "Official contact email for tax compliance notifications.",
    contact_number: "Official phone number linked for portal OTP verifications.",
    registration_type: "Regular, Composition, Casual, or Non-resident scheme.",
    filing_frequency: "Filing frequency preference (Monthly or Quarterly QRMP).",
    registration_status: "Active, Suspended, or Cancelled status identifier.",
    turnover_threshold: "Turnover limit boundary above which GST registration is mandatory.",
    aggregate_turnover: "Accumulated sales turnover value across all units this financial year.",
    is_sez_unit: "Toggle if this office/factory is in a Special Economic Zone unit.",
    is_sez_developer: "Toggle if this entity maintains SEZ developer status.",
    is_isd: "Toggle if you distribute input credits to branch networks.",
    is_ecom_operator: "Toggle if you operate an e-commerce platform collecting TCS.",
    default_gst_rate: "The default slab rate used if no code match is specified.",
    itc_matching_mode: "Match strategy (e.g. GSTR-2B automatic reconciliation).",
    auto_reversal_rules: "Automated reversal trigger like unpaid bills past 180 days.",
    itc_reclaim_rules: "Accounting logic for posting reclaimed input tax credit.",
    b2b_gst_treatment: "Output tax logic for registered B2B invoice lines.",
    b2c_gst_treatment: "Output tax logic for B2C consumer invoices.",
    interstate_gst_treatment: "Tax scheme for interstate sales (standard is IGST).",
    intrastate_gst_treatment: "Tax scheme for domestic state sales (standard is CGST+SGST).",
    export_gst_treatment: "Output treatment model for export supply orders.",
    sez_gst_treatment: "Supply rules for Special Economic Zone partners.",
    default_place_of_supply: "Primary address state determinant for tax calculations.",
    interstate_logic: "Rule trigger deciding when a transaction is interstate.",
    intrastate_logic: "Rule trigger deciding when a transaction is domestic.",
    export_treatment: "Tax rates application for export orders.",
    import_treatment: "Rules for import purchases credit.",
    invoice_prefix: "Character prefix used to format sales tax invoice sequences.",
    invoice_numbering_format: "Serial sequence format for tax numbering.",
    financial_year_format: "FY pattern structure (e.g. 26-27 or 2026-27).",
    round_off_rules: "Decimal rounding mode applied to grand invoice tax sums.",
    gst_breakdown_visibility: "Specify if item-level tax splits are fully printed on PDF invoice layouts.",
    e_invoicing_enabled: "Enable government registration and digital signed IRN/QR codes.",
    irp_provider: "Government Invoice Registration Portal endpoint gateway.",
    api_credentials_username: "Your IRP API integration username.",
    api_credentials_password: "Your IRP API integration password.",
    auth_key: "Client secret key generated on government portal.",
    auto_generate_irn: "Request IRN immediately upon invoice finalization.",
    auto_generate_qr_code: "Generate government-signed QR code automatically.",
    irn_retry_rules: "API calling retry rules on network failure.",
    e_way_bill_enabled: "Enable automated E-Way Bill transit registration.",
    distance_threshold: "Transaction valuation limit prompting E-Way Bill requirement.",
    vehicle_validation: "Regex checks validating transport vehicle formatting.",
    transporter_validation: "Verify transporter tax ID against government portal on dispatch.",
    auto_generate_e_way_bill: "Submit transit declaration automatically upon invoice completion.",
    tds_enabled: "Enable withholding tax under CGST Section 51.",
    default_tds_rate: "Percentage rate deducted from contractor supply bills.",
    tds_section_mapping: "Filing act section reference mapping.",
    vendor_tds_rules: "Apply TDS based on contract threshold limits.",
    tds_threshold_limits: "Annual contract amount triggering TDS deduction.",
    tcs_enabled: "Enable Tax Collection at Source for marketplace operator roles.",
    marketplace_tcs: "TCS collection rate for operators.",
    e_commerce_tcs: "TCS collection rate for merchants.",
    tcs_collection_frequency: "Frequency schedule for TCS collections filing.",
    tcs_collection_threshold: "Valuation threshold triggering TCS collection.",
    rcm_enabled: "Enable Reverse Charge Mechanism liability accrual.",
    rcm_posting_rules: "Liabilities and contra assets bookkeeping schedule.",
    auto_rcm_detection: "Derive reverse tax obligation from chart accounts matches.",
    rcm_vendor_categories: "Comma separated supplier category tags subject to RCM.",
    rcm_expense_categories: "Comma separated chart account codes requiring RCM treatment.",
    gstr1_frequency: "GSTR-1 sales filing cycle schedule.",
    gstr3b_frequency: "GSTR-3B tax offset filing schedule.",
    due_date_alerts: "Compliance calendar deadline system reminders trigger threshold.",
    exempt_products: "Product category names exempt from GST tax levy.",
    nil_rated_products: "Categories defined at 0% tax slabs.",
    non_gst_supplies: "Out of scope commodities like petrol or alcohol.",
    import_goods_treatment: "Customs duty logic for imported assets.",
    import_services_treatment: "RCM assessment rules on inbound services.",
    custom_duty_mapping: "Bookkeeping accounts capitalized as part of acquisition cost.",
    igst_treatment: "Assert input credit values on customs declarations.",
    sez_customer_rules: "Customer tax parameters applied to SEZ clients.",
    sez_vendor_rules: "Purchases compliance applied to SEZ suppliers.",
    sez_zero_rated_supply_rules: "Supply exemptions code application.",
    credit_note_prefix: "Prefix formatting sequence for customer refund credits.",
    debit_note_prefix: "Prefix formatting sequence for inbound debits.",
    note_approval_workflow: "Dual signoff or auto approval strategy on note posting.",
    auto_gst_adjustment: "Sync liability balances immediately on note creation.",
    fiscal_year: "Tax fiscal cycle standard.",
    rounding_rules: "Precision rounding rounding logic.",
    decimal_precision: "Ledger decimal accuracy representation (default is 2).",
    timezone: "Location zone settings standard.",
    hsn_mandatory: "Require valid HSN code for all line items in sales invoices before validation.",
    sac_mandatory: "Require valid SAC code for all service line items before posting.",
    qr_code_enabled: "Print dynamic tax verification QR Code on invoice PDF templates.",
    gstr9_enabled: "Track and reconcile data for GSTR-9 annual information returns.",
    gstr9c_enabled: "Perform reconciliation checks for GSTR-9C statutory audited returns.",
    export_with_lut: "Export transactions exempted from IGST using Letter of Undertaking validation.",
    export_without_lut: "Charge integrated tax on exports and claim refund later from custom portal.",
    sez_documentation: "Documents checklist to substantiate tax-exempt supplies made to SEZ clients.",
    validate_gstin: "Validate structural format of client and supplier GSTINs.",
    validate_pan: "Enforce regex checking on all corporate Permanent Account Numbers.",
    validate_hsn: "Enforce HSN database code matches on all order items.",
    duplicate_invoice_detection: "Detect and block duplicate vendor invoice number sequences.",
    duplicate_gst_filing_detection: "Scan system to avoid duplicate filings for overlapping tax periods.",
    alert_filing_due: "Send email alerts and notifications prior to compliance filing due dates.",
    alert_itc_mismatch: "Alert when supplier GSTR-2B filing mismatch is auto-detected.",
    alert_return_rejection: "Alert on official portal response return filing rejections.",
    alert_invoice_failure: "Trigger alerts on invoicing API synchronization failures.",
    alert_e_invoice_failure: "Trigger alerts if real-time E-Invoicing IRN generation fails on save.",
    alert_e_way_bill_failure: "Trigger alerts if E-Way Bill distance/vehicle validation fails.",
    output_cgst_ledger: "Ledger account mapping for central tax liability on sales.",
    output_sgst_ledger: "Ledger account mapping for state tax liability on sales.",
    output_igst_ledger: "Ledger account mapping for integrated tax liability on sales.",
    input_cgst_ledger: "Asset ledger account mapping for CGST credit inputs.",
    input_sgst_ledger: "Asset ledger account mapping for SGST credit inputs.",
    input_igst_ledger: "Asset ledger account mapping for IGST credit inputs.",
    tds_gst_receivable: "Ledger account tracking GST TDS receivables from government clients.",
    tcs_gst_receivable: "Ledger account tracking GST TCS receivables from ecommerce operators.",
    auto_posting: "Post tax ledger entries directly to general ledger on transaction save.",
    auto_reconciliation: "Enable nightly reconciliation engine run for GSTR-2B matching.",
    auto_itc_matching: "Automatically approve matched input tax credits for cash offsets.",
    audit_log_enabled: "Maintain a local revision log track for GST settings updates.",
  };

  const FieldWrapper = ({ fieldKey, children }) => {
    const tooltipText = fieldTooltips[fieldKey];
    if (!tooltipText) return children;
    return (
      <MuiTooltip title={tooltipText} arrow placement="top">
        <div>
          {children}
        </div>
      </MuiTooltip>
    );
  };

  const handleSaveDraft = () => {
    try {
      localStorage.setItem('shori_gst_advanced_settings_draft', JSON.stringify(settings));
      setToast({ open: true, message: 'Settings draft saved to local storage.', severity: 'success' });
      setHasDraft(true);
    } catch {
      setToast({ open: true, message: 'Failed to save settings draft.', severity: 'error' });
    }
  };

  const handleApplyDraft = () => {
    try {
      const draft = localStorage.getItem('shori_gst_advanced_settings_draft');
      if (draft) {
        setSettings(JSON.parse(draft));
        setToast({ open: true, message: 'Settings draft loaded into session.', severity: 'success' });
      }
      setHasDraft(false);
    } catch {
      setToast({ open: true, message: 'Failed to apply settings draft.', severity: 'error' });
    }
  };

  const handleDiscardDraft = () => {
    try {
      localStorage.removeItem('shori_gst_advanced_settings_draft');
      setToast({ open: true, message: 'Settings draft discarded.', severity: 'info' });
      setHasDraft(false);
    } catch {
      setToast({ open: true, message: 'Failed to discard draft.', severity: 'error' });
    }
  };

  const handleResetToDefaults = () => {
    setSettings(DEFAULT_GST_CONFIG);
    setValidationErrors({});
    setToast({ open: true, message: 'Settings reset to standard defaults.', severity: 'info' });
  };

  const handleSaveAllSettings = async (e) => {
    if (e) e.preventDefault();
    
    // Validate all fields
    let allValid = true;
    allValid = validateField('gstin', settings.gstin) && allValid;
    allValid = validateField('pan', settings.pan) && allValid;
    allValid = validateField('communication_email', settings.communication_email) && allValid;
    allValid = validateField('contact_number', settings.contact_number) && allValid;
    allValid = validateField('tax_slabs', settings.tax_slabs) && allValid;
    
    if (settings.e_invoicing_enabled) {
      allValid = validateField('irp_provider', settings.irp_provider) && allValid;
      allValid = validateField('api_credentials_username', settings.api_credentials_username) && allValid;
      allValid = validateField('api_credentials_password', settings.api_credentials_password) && allValid;
    }
    
    if (settings.e_way_bill_enabled) {
      allValid = validateField('distance_threshold', settings.distance_threshold) && allValid;
    }
    
    if (settings.tds_enabled) {
      allValid = validateField('default_tds_rate', settings.default_tds_rate) && allValid;
      allValid = validateField('tds_threshold_limits', settings.tds_threshold_limits) && allValid;
    }
    
    if (settings.tcs_enabled) {
      allValid = validateField('marketplace_tcs', settings.marketplace_tcs) && allValid;
      allValid = validateField('e_commerce_tcs', settings.e_commerce_tcs) && allValid;
      allValid = validateField('tcs_collection_threshold', settings.tcs_collection_threshold) && allValid;
    }
    
    allValid = validateField('hsn_sac_codes', settings.hsn_sac_codes) && allValid;
    
    const ledgers = [
      'output_cgst_ledger', 'output_sgst_ledger', 'output_igst_ledger',
      'input_cgst_ledger', 'input_sgst_ledger', 'input_igst_ledger',
      'tds_gst_receivable', 'tcs_gst_receivable'
    ];
    ledgers.forEach(l => {
      allValid = validateField(l, settings[l]) && allValid;
    });

    if (!allValid) {
      setToast({ open: true, message: 'Please correct validation errors before saving.', severity: 'error' });
      return;
    }

    setSettingsSaving(true);
    try {
      const coreSettings = {
        gstin: settings.gstin,
        legal_name: settings.legal_name,
        state: settings.state,
        registration_type: settings.registration_type,
        filing_frequency: settings.filing_frequency,
        default_gst_rate: settings.default_gst_rate,
      };

      const res = await apiClient('/api/accounting/gst/settings/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(coreSettings),
      });

      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) {
        setToast({
          open: true,
          message: payload?.message || 'Failed to update core settings on server.',
          severity: 'error',
        });
        setSettingsSaving(false);
        return;
      }

      localStorage.setItem('shori_gst_advanced_settings', JSON.stringify(settings));
      localStorage.removeItem('shori_gst_advanced_settings_draft');
      setHasDraft(false);

      const newLog = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        user: 'jatin',
        action: 'Update GST Configurations',
        sectionKey: activeSettingsSection,
        details: `Saved changes to Section: ${settingsCategories.find(c => c.key === activeSettingsSection)?.label || activeSettingsSection}`
      };
      const updatedLog = [newLog, ...auditLog];
      setAuditLog(updatedLog);
      localStorage.setItem('shori_gst_settings_audit_log', JSON.stringify(updatedLog));

      setToast({ open: true, message: 'All GST configurations saved successfully.', severity: 'success' });
    } catch (err) {
      console.error(err);
      setToast({ open: true, message: 'Connection error. Saved changes to local storage.', severity: 'warning' });
    } finally {
      setSettingsSaving(false);
    }
  };

  // CSV Export
  const handleExportCSV = async () => {
    if (!canExport) {
      setToast({ open: true, message: 'You do not have permission to export ledger data.', severity: 'warning' });
      return;
    }
    try {
      const params = new URLSearchParams({
        export: 'true',
        q: txnSearch,
        type: txnType,
        status: txnStatus,
        date_from: dateFrom,
        date_to: dateTo,
      });
      const res = await apiClient(`/api/accounting/gst/transactions/?${params.toString()}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gst_ledger_export_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        setToast({ open: true, message: 'CSV exported successfully.', severity: 'success' });
      } else {
        setToast({ open: true, message: 'Failed to download export file.', severity: 'error' });
      }
    } catch {
      setToast({ open: true, message: 'Error exporting CSV.', severity: 'error' });
    }
  };

  // PDF Export of transactions ledger
  const handleExportPDF = async () => {
    if (!canExport) {
      setToast({ open: true, message: 'You do not have permission to export ledger data.', severity: 'warning' });
      return;
    }
    setToast({ open: true, message: 'Generating Tax Ledger PDF...', severity: 'info' });
    try {
      const params = new URLSearchParams({
        page: 1,
        page_size: 1000,
        q: txnSearch,
        type: txnType,
        status: txnStatus,
        date_from: dateFrom,
        date_to: dateTo,
      });
      const res = await apiClient(`/api/accounting/gst/transactions/?${params.toString()}`);
      const payload = await res.json().catch(() => null);
      if (res.ok && payload?.success !== false) {
        const results = payload?.data?.results || payload?.results || [];
        handleClientExport('tax_ledger_export', results, 'pdf_ledger');
      } else {
        setToast({ open: true, message: 'Failed to retrieve ledger data for PDF.', severity: 'error' });
      }
    } catch (err) {
      console.error(err);
      setToast({ open: true, message: 'Error generating PDF.', severity: 'error' });
    }
  };

  // Formatting helpers
  const fmt = (n) => {
    if (!canViewAmounts) return '****';
    return Number(n || 0).toLocaleString('en-IN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  };

  // Color mappings
  const primaryBg = isDark ? '#1e293b' : '#ffffff';
  const borderCol = isDark ? '#334155' : '#e5e7eb';
  const textPrimary = isDark ? '#f8fafc' : '#0f172a';
  const textSecondary = isDark ? '#94a3b8' : '#64748b';

  // Input styles for a modern, sleek Notion/Stripe look
  const renderSettingsPanel = () => {
    switch (activeSettingsSection) {
      case 'identity':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="legal_name">
                <TextField
                  fullWidth
                  label="Legal Entity Name"
                  size="small"
                  required
                  value={settings.legal_name || ''}
                  onChange={(e) => handleFieldChange('legal_name', e.target.value)}
                  sx={inputStyle}
                  helperText="Statutory name of your registered business entity."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="trade_name">
                <TextField
                  fullWidth
                  label="Trade Name"
                  size="small"
                  value={settings.trade_name || ''}
                  onChange={(e) => handleFieldChange('trade_name', e.target.value)}
                  sx={inputStyle}
                  helperText="Brand name or commercial name of the business operation."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="gstin">
                <TextField
                  fullWidth
                  label="GSTIN"
                  size="small"
                  required
                  error={Boolean(validationErrors.gstin)}
                  helperText={validationErrors.gstin || "15-digit Goods & Services Tax Identification Number."}
                  value={settings.gstin || ''}
                  onChange={(e) => {
                    const val = e.target.value.toUpperCase();
                    handleFieldChange('gstin', val);
                    validateField('gstin', val);
                  }}
                  sx={inputStyle}
                  slotProps={{ input: { maxLength: 15 } }}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="pan">
                <TextField
                  fullWidth
                  label="Permanent Account Number (PAN)"
                  size="small"
                  required
                  error={Boolean(validationErrors.pan)}
                  helperText={validationErrors.pan || "10-digit income tax identifier."}
                  value={settings.pan || ''}
                  onChange={(e) => {
                    const val = e.target.value.toUpperCase();
                    handleFieldChange('pan', val);
                    validateField('pan', val);
                  }}
                  sx={inputStyle}
                  slotProps={{ input: { maxLength: 10 } }}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="tan">
                <TextField
                  fullWidth
                  label="Tax Deduction Account Number (TAN)"
                  size="small"
                  value={settings.tan || ''}
                  onChange={(e) => handleFieldChange('tan', e.target.value.toUpperCase())}
                  sx={inputStyle}
                  helperText="Required for business entities collecting or deducting tax at source."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="cin">
                <TextField
                  fullWidth
                  label="Corporate Identity Number (CIN)"
                  size="small"
                  value={settings.cin || ''}
                  onChange={(e) => handleFieldChange('cin', e.target.value.toUpperCase())}
                  sx={inputStyle}
                  helperText="21-digit identifier for registered corporations."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="constitution">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Constitution Of Business</InputLabel>
                  <Select
                    value={settings.constitution || 'private_company'}
                    label="Constitution Of Business"
                    onChange={(e) => handleFieldChange('constitution', e.target.value)}
                  >
                    <MenuItem value="proprietorship">Sole Proprietorship</MenuItem>
                    <MenuItem value="partnership">Partnership Firm</MenuItem>
                    <MenuItem value="private_company">Private Limited Company</MenuItem>
                    <MenuItem value="public_company">Public Limited Company</MenuItem>
                    <MenuItem value="llp">Limited Liability Partnership (LLP)</MenuItem>
                    <MenuItem value="trust">Trust / Society</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={3}>
              <FieldWrapper fieldKey="state">
                <TextField
                  fullWidth
                  label="Registration State"
                  size="small"
                  required
                  placeholder="e.g. Delhi, Maharashtra"
                  value={settings.state || ''}
                  onChange={(e) => handleFieldChange('state', e.target.value)}
                  sx={inputStyle}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={3}>
              <FieldWrapper fieldKey="state_code">
                <TextField
                  fullWidth
                  label="State Code"
                  size="small"
                  required
                  placeholder="e.g. 07, 27"
                  value={settings.state_code || ''}
                  onChange={(e) => handleFieldChange('state_code', e.target.value.replace(/[^0-9]/g, ''))}
                  sx={inputStyle}
                  slotProps={{ input: { maxLength: 2 } }}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="registration_date">
                <TextField
                  fullWidth
                  type="date"
                  label="GST Registration Date"
                  size="small"
                  slotProps={{ inputLabel: { shrink: true } }}
                  value={settings.registration_date || ''}
                  onChange={(e) => handleFieldChange('registration_date', e.target.value)}
                  sx={inputStyle}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="communication_email">
                <TextField
                  fullWidth
                  label="GST Communication Email"
                  size="small"
                  error={Boolean(validationErrors.communication_email)}
                  helperText={validationErrors.communication_email || "Official contact email for tax filings."}
                  value={settings.communication_email || ''}
                  onChange={(e) => {
                    handleFieldChange('communication_email', e.target.value);
                    validateField('communication_email', e.target.value);
                  }}
                  sx={inputStyle}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="contact_number">
                <TextField
                  fullWidth
                  label="GST Contact Number"
                  size="small"
                  error={Boolean(validationErrors.contact_number)}
                  helperText={validationErrors.contact_number || "Official contact phone for OTP verifications."}
                  value={settings.contact_number || ''}
                  onChange={(e) => {
                    handleFieldChange('contact_number', e.target.value.replace(/[^0-9]/g, ''));
                    validateField('contact_number', e.target.value.replace(/[^0-9]/g, ''));
                  }}
                  sx={inputStyle}
                  slotProps={{ input: { maxLength: 10 } }}
                />
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'registration':
        return (
          <Grid container spacing={3.5}>
            <Grid item xs={12}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>GST Scheme & Taxpayer Profile</Typography>
              <Grid container spacing={2}>
                {[
                  { key: 'registration_type', value: 'regular', label: 'Regular Taxpayer', desc: 'Standard business profile reporting monthly/quarterly tax calculations & claims.' },
                  { key: 'registration_type', value: 'composition', label: 'Composition Scheme', desc: 'Concessional tax scheme for small turnovers (< 1.5 Cr), unable to claim ITC.' },
                  { key: 'registration_type', value: 'casual', label: 'Casual Taxpayer', desc: 'Temporary registration for events/exhibitions valid for up to 90 days.' },
                  { key: 'registration_type', value: 'non_resident', label: 'Non-Resident Taxpayer', desc: 'Taxpayers operating in India without a permanent place of business.' },
                ].map((opt) => (
                  <Grid item xs={12} md={6} key={opt.value}>
                    <FieldWrapper fieldKey="registration_type">
                      <Box
                        onClick={() => handleFieldChange('registration_type', opt.value)}
                        sx={{
                          p: 2,
                          border: `1px solid ${settings.registration_type === opt.value ? textPrimary : '#E5E7EB'}`,
                          borderRadius: '8px',
                          cursor: 'pointer',
                          bgcolor: settings.registration_type === opt.value ? '#f9fafb' : '#ffffff',
                          height: '100%',
                        }}
                      >
                        <Typography variant="subtitle2" fontWeight={700} color={textPrimary} mb={0.5}>{opt.label}</Typography>
                        <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>{opt.desc}</Typography>
                      </Box>
                    </FieldWrapper>
                  </Grid>
                ))}
              </Grid>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="filing_frequency">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Filing Frequency Preference</InputLabel>
                  <Select
                    value={settings.filing_frequency || 'monthly'}
                    label="Filing Frequency Preference"
                    onChange={(e) => handleFieldChange('filing_frequency', e.target.value)}
                  >
                    <MenuItem value="monthly">Monthly Filing cycle</MenuItem>
                    <MenuItem value="quarterly">Quarterly QRMP Scheme</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="registration_status">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Registration Status</InputLabel>
                  <Select
                    value={settings.registration_status || 'active'}
                    label="Registration Status"
                    onChange={(e) => handleFieldChange('registration_status', e.target.value)}
                  >
                    <MenuItem value="active">Active</MenuItem>
                    <MenuItem value="suspended">Suspended</MenuItem>
                    <MenuItem value="cancelled">Cancelled</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="turnover_threshold">
                <TextField
                  fullWidth
                  type="number"
                  label="Turnover Registration Threshold (INR)"
                  size="small"
                  value={settings.turnover_threshold || ''}
                  onChange={(e) => handleFieldChange('turnover_threshold', e.target.value)}
                  sx={inputStyle}
                  helperText="Government registration boundary limit (e.g. 40,000,000 for goods)."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="aggregate_turnover">
                <TextField
                  fullWidth
                  type="number"
                  label="Current Fiscal Aggregate Turnover (INR)"
                  size="small"
                  value={settings.aggregate_turnover || ''}
                  onChange={(e) => handleFieldChange('aggregate_turnover', e.target.value)}
                  sx={inputStyle}
                  helperText="Total collective value of all outward supplies in the financial year."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>Special Registrations & Flags</Typography>
              <Grid container spacing={2}>
                {[
                  { key: 'is_sez_unit', label: 'SEZ Unit Registration', desc: 'Entity is located inside a Special Economic Zone.' },
                  { key: 'is_sez_developer', label: 'SEZ Developer Status', desc: 'Entity develops, operates, or maintains SEZ infrastructures.' },
                  { key: 'is_isd', label: 'Input Service Distributor (ISD)', desc: 'Authorized to distribute collected ITC credits to branches.' },
                  { key: 'is_ecom_operator', label: 'E-Commerce Operator (TCS)', desc: 'Facilitates sales of third-party sellers on digital marketplace portals.' },
                ].map((opt) => (
                  <Grid item xs={12} md={6} key={opt.key}>
                    <FieldWrapper fieldKey={opt.key}>
                      <Box
                        onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                        sx={{
                          p: 2,
                          border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                        }}
                      >
                        <Box>
                          <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>{opt.label}</Typography>
                          <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.72rem', lineHeight: 1.3 }}>{opt.desc}</Typography>
                        </Box>
                        <Box
                          sx={{
                            width: 20,
                            height: 20,
                            borderRadius: '4px',
                            border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                            bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {settings[opt.key] && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                        </Box>
                      </Box>
                    </FieldWrapper>
                  </Grid>
                ))}
              </Grid>
            </Grid>
          </Grid>
        );
      case 'rates':
        return (
          <Box display="flex" flexDirection="column" gap={3}>
            {validationErrors.tax_slabs && (
              <Alert severity="error" sx={{ borderRadius: '8px' }}>
                {validationErrors.tax_slabs}
              </Alert>
            )}
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="body2" fontWeight={600} color={textPrimary}>Active GST Slab Configurations</Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  const rateId = 'slab_' + Date.now();
                  const updatedSlabs = [
                    ...settings.tax_slabs,
                    { id: rateId, name: 'Custom Rate', cgst: 9, sgst: 9, igst: 18, cess: 0, description: 'User created rate description', status: 'active' }
                  ];
                  handleFieldChange('tax_slabs', updatedSlabs);
                }}
                sx={{
                  textTransform: 'none',
                  borderColor: '#E5E7EB',
                  color: textPrimary,
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  borderRadius: '8px',
                  '&:hover': { borderColor: '#cbd5e1', bgcolor: '#f9fafb' },
                }}
              >
                + Add Custom Rate Slab
              </Button>
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: '#f9fafc' }}>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Rate Slab Name</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>CGST (%)</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>SGST (%)</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>IGST (%)</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>CESS (%)</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {settings.tax_slabs.map((slab, index) => (
                    <TableRow key={slab.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <TextField
                          size="small"
                          value={slab.name}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].name = e.target.value;
                            handleFieldChange('tax_slabs', copy);
                            validateField('tax_slabs', copy);
                          }}
                          variant="standard"
                          slotProps={{ input: { style: { fontSize: '0.8rem', fontWeight: 600 } } }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <input
                          type="number"
                          step="0.01"
                          value={slab.cgst}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].cgst = parseFloat(e.target.value) || 0;
                            handleFieldChange('tax_slabs', copy);
                            validateField('tax_slabs', copy);
                          }}
                          style={{ width: '50px', border: 0, textAlign: 'center', fontSize: '0.8rem', fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <input
                          type="number"
                          step="0.01"
                          value={slab.sgst}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].sgst = parseFloat(e.target.value) || 0;
                            handleFieldChange('tax_slabs', copy);
                            validateField('tax_slabs', copy);
                          }}
                          style={{ width: '50px', border: 0, textAlign: 'center', fontSize: '0.8rem', fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <input
                          type="number"
                          step="0.01"
                          value={slab.igst}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].igst = parseFloat(e.target.value) || 0;
                            handleFieldChange('tax_slabs', copy);
                            validateField('tax_slabs', copy);
                          }}
                          style={{ width: '50px', border: 0, textAlign: 'center', fontSize: '0.8rem', fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <input
                          type="number"
                          step="0.01"
                          value={slab.cess}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].cess = parseFloat(e.target.value) || 0;
                            handleFieldChange('tax_slabs', copy);
                          }}
                          style={{ width: '40px', border: 0, textAlign: 'center', fontSize: '0.8rem', fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <TextField
                          size="small"
                          value={slab.description}
                          onChange={(e) => {
                            const copy = [...settings.tax_slabs];
                            copy[index].description = e.target.value;
                            handleFieldChange('tax_slabs', copy);
                          }}
                          variant="standard"
                          slotProps={{ input: { style: { fontSize: '0.75rem', color: textSecondary } } }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <Box
                          component="button"
                          onClick={() => {
                            const copy = [...settings.tax_slabs];
                            copy[index].status = slab.status === 'active' ? 'inactive' : 'active';
                            handleFieldChange('tax_slabs', copy);
                          }}
                          sx={{
                            px: 1,
                            py: 0.25,
                            border: 0,
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            bgcolor: slab.status === 'active' ? '#e6fbf4' : '#fee2e2',
                            color: slab.status === 'active' ? '#10b981' : '#ef4444',
                          }}
                        >
                          {slab.status.toUpperCase()}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>
                        <Button
                          size="small"
                          color="error"
                          onClick={() => {
                            const updated = settings.tax_slabs.filter((_, idx) => idx !== index);
                            handleFieldChange('tax_slabs', updated);
                            validateField('tax_slabs', updated);
                          }}
                          sx={{ textTransform: 'none', fontSize: '0.7rem', p: 0.25 }}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <FieldWrapper fieldKey="default_gst_rate">
              <FormControl fullWidth size="small" sx={inputStyle}>
                <InputLabel>Default Ledger Computation Rate</InputLabel>
                <Select
                  value={settings.default_gst_rate || '18.00'}
                  label="Default Ledger Computation Rate"
                  onChange={(e) => handleFieldChange('default_gst_rate', e.target.value)}
                >
                  <MenuItem value="0.00">0% (Nil Rated / Exempt)</MenuItem>
                  <MenuItem value="5.00">5% (Concessional Goods)</MenuItem>
                  <MenuItem value="12.00">12% (Standard rate - low)</MenuItem>
                  <MenuItem value="18.00">18% (Standard rate - high)</MenuItem>
                  <MenuItem value="28.00">28% (Luxury & sin goods)</MenuItem>
                </Select>
              </FormControl>
            </FieldWrapper>
          </Box>
        );
      case 'itc':
        return (
          <Grid container spacing={3.5}>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>Allowable ITC Assertions</Typography>
              <Box display="flex" flexDirection="column" gap={1.5}>
                {[
                  { key: 'itc_on_purchases', label: 'ITC Eligible on Raw Material Purchases' },
                  { key: 'itc_on_capital_goods', label: 'ITC Eligible on Capital Assets / Machinery' },
                  { key: 'itc_on_services', label: 'ITC Eligible on Inbound Corporate Services' },
                  { key: 'itc_on_imports', label: 'ITC Eligible on Importations (IGST paid at customs)' },
                ].map((opt) => (
                  <FieldWrapper key={opt.key} fieldKey={opt.key}>
                    <Box
                      onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                      sx={{
                        p: 1.5,
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" fontWeight={500} color={textPrimary} sx={{ fontSize: '0.8rem' }}>{opt.label}</Typography>
                      <Box
                        sx={{
                          width: 18,
                          height: 18,
                          borderRadius: '4px',
                          border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings[opt.key] && <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                ))}
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>Blocked ITC Categories (Section 17(5))</Typography>
              <Box display="flex" flexDirection="column" gap={1.5}>
                {[
                  { key: 'block_itc_personal', label: 'Block ITC on Personal/Non-business Expenses' },
                  { key: 'block_itc_vehicles', label: 'Block ITC on Passenger Motor Vehicles (< 13 seats)' },
                  { key: 'block_itc_food', label: 'Block ITC on Food, Beverages, and Catering Invoices' },
                  { key: 'block_itc_benefits', label: 'Block ITC on Mandatory Employee Insurances & Perks' },
                ].map((opt) => (
                  <FieldWrapper key={opt.key} fieldKey={opt.key}>
                    <Box
                      onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                      sx={{
                        p: 1.5,
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" fontWeight={500} color={textPrimary} sx={{ fontSize: '0.8rem' }}>{opt.label}</Typography>
                      <Box
                        sx={{
                          width: 18,
                          height: 18,
                          borderRadius: '4px',
                          border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings[opt.key] && <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                ))}
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <FieldWrapper fieldKey="itc_matching_mode">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>ITC Matching Algorithm Mode</InputLabel>
                  <Select
                    value={settings.itc_matching_mode || 'gstr2b_reconciliation'}
                    label="ITC Matching Algorithm Mode"
                    onChange={(e) => handleFieldChange('itc_matching_mode', e.target.value)}
                  >
                    <MenuItem value="manual">Manual Auditor Review</MenuItem>
                    <MenuItem value="gstr2b_reconciliation">Automated GSTR-2B Matching</MenuItem>
                    <MenuItem value="auto_approve_all">Auto Approve All Valid Inbound Invoices</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={4}>
              <FieldWrapper fieldKey="auto_reversal_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Auto ITC Reversal Trigger</InputLabel>
                  <Select
                    value={settings.auto_reversal_rules || 'supplier_unpaid_180_days'}
                    label="Auto ITC Reversal Trigger"
                    onChange={(e) => handleFieldChange('auto_reversal_rules', e.target.value)}
                  >
                    <MenuItem value="supplier_unpaid_180_days">Unpaid Vendor Invoice &gt; 180 Days</MenuItem>
                    <MenuItem value="none">Disable Auto Reversals</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={4}>
              <FieldWrapper fieldKey="itc_reclaim_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Reclaimed ITC posting logic</InputLabel>
                  <Select
                    value={settings.itc_reclaim_rules || 'on_supplier_payment_reconciliation'}
                    label="Reclaimed ITC posting logic"
                    onChange={(e) => handleFieldChange('itc_reclaim_rules', e.target.value)}
                  >
                    <MenuItem value="on_supplier_payment_reconciliation">Post on Supplier Payment matching</MenuItem>
                    <MenuItem value="manual_journal_entries">Requires manual credit note validation</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'output':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="b2b_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>B2B Output GST Rule</InputLabel>
                  <Select
                    value={settings.b2b_gst_treatment || 'apply_standard'}
                    label="B2B Output GST Rule"
                    onChange={(e) => handleFieldChange('b2b_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_standard">Standard Tax slabs application</MenuItem>
                    <MenuItem value="zero_rated_with_lut">Zero-Rated with export LUT validation</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="b2c_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>B2C Output GST Rule</InputLabel>
                  <Select
                    value={settings.b2c_gst_treatment || 'apply_standard'}
                    label="B2C Output GST Rule"
                    onChange={(e) => handleFieldChange('b2c_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_standard">Standard Tax slabs (IGST or CGST/SGST)</MenuItem>
                    <MenuItem value="flat_exempt">Flat exemption categories</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="interstate_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Interstate Outbound tax rule</InputLabel>
                  <Select
                    value={settings.interstate_gst_treatment || 'apply_igst'}
                    label="Interstate Outbound tax rule"
                    onChange={(e) => handleFieldChange('interstate_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_igst">Apply Integrated Tax (IGST)</MenuItem>
                    <MenuItem value="restricted">Block Inter-state transactions</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="intrastate_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Intrastate Outbound tax rule</InputLabel>
                  <Select
                    value={settings.intrastate_gst_treatment || 'apply_cgst_sgst'}
                    label="Intrastate Outbound tax rule"
                    onChange={(e) => handleFieldChange('intrastate_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_cgst_sgst">Split Central & State Tax (CGST + SGST)</MenuItem>
                    <MenuItem value="flat_igst">Apply IGST directly</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="export_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Export Outbound sales rule</InputLabel>
                  <Select
                    value={settings.export_gst_treatment || 'lut_exempt'}
                    label="Export Outbound sales rule"
                    onChange={(e) => handleFieldChange('export_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="lut_exempt">Exempt Outbound under LUT</MenuItem>
                    <MenuItem value="with_tax_refund">Apply IGST (Refund eligible later)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="sez_gst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>SEZ Outbound sales rule</InputLabel>
                  <Select
                    value={settings.sez_gst_treatment || 'zero_rated'}
                    label="SEZ Outbound sales rule"
                    onChange={(e) => handleFieldChange('sez_gst_treatment', e.target.value)}
                  >
                    <MenuItem value="zero_rated">Zero-Rated supply (Treat as export)</MenuItem>
                    <MenuItem value="apply_igst">Charge standard IGST</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'pos':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="default_place_of_supply">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Default Place Of Supply Determinant</InputLabel>
                  <Select
                    value={settings.default_place_of_supply || 'billing_address'}
                    label="Default Place Of Supply Determinant"
                    onChange={(e) => handleFieldChange('default_place_of_supply', e.target.value)}
                  >
                    <MenuItem value="billing_address">Customer Billing Address state</MenuItem>
                    <MenuItem value="shipping_address">Customer Shipping Address state</MenuItem>
                    <MenuItem value="state_of_incorporation">Merchant Jurisdiction state</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="interstate_logic">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Interstate Logic Trigger</InputLabel>
                  <Select
                    value={settings.interstate_logic || 'shipping_state_different'}
                    label="Interstate Logic Trigger"
                    onChange={(e) => handleFieldChange('interstate_logic', e.target.value)}
                  >
                    <MenuItem value="shipping_state_different">Shipping Address State != Merchant State</MenuItem>
                    <MenuItem value="billing_state_different">Billing Address State != Merchant State</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="intrastate_logic">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Intrastate Logic Trigger</InputLabel>
                  <Select
                    value={settings.intrastate_logic || 'shipping_state_same'}
                    label="Intrastate Logic Trigger"
                    onChange={(e) => handleFieldChange('intrastate_logic', e.target.value)}
                  >
                    <MenuItem value="shipping_state_same">Shipping Address State == Merchant State</MenuItem>
                    <MenuItem value="billing_state_same">Billing Address State == Merchant State</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="export_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Export Tax Treatment Model</InputLabel>
                  <Select
                    value={settings.export_treatment || 'zero_rated_with_lut'}
                    label="Export Tax Treatment Model"
                    onChange={(e) => handleFieldChange('export_treatment', e.target.value)}
                  >
                    <MenuItem value="zero_rated_with_lut">Zero-Rated with active LUT document</MenuItem>
                    <MenuItem value="full_taxation">Standard Integrated IGST Application</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="import_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Import Tax Treatment Model</InputLabel>
                  <Select
                    value={settings.import_treatment || 'apply_igst_on_customs'}
                    label="Import Tax Treatment Model"
                    onChange={(e) => handleFieldChange('import_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_igst_on_customs">Charge Integrated Tax (IGST) at Customs Assessment</MenuItem>
                    <MenuItem value="exempt">Duty Free Import exemption codes</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'invoice':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="invoice_prefix">
                <TextField
                  fullWidth
                  label="Invoice Prefix"
                  size="small"
                  value={settings.invoice_prefix || ''}
                  onChange={(e) => handleFieldChange('invoice_prefix', e.target.value)}
                  sx={inputStyle}
                  helperText="Characters prepended to GST sales invoices."
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="invoice_numbering_format">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Invoice Numbering Format</InputLabel>
                  <Select
                    value={settings.invoice_numbering_format || 'prefix-sequence'}
                    label="Invoice Numbering Format"
                    onChange={(e) => handleFieldChange('invoice_numbering_format', e.target.value)}
                  >
                    <MenuItem value="prefix-sequence">Prefix + Running Sequence (e.g. SHORI/GST/0001)</MenuItem>
                    <MenuItem value="sequence-only">Running Sequence Only (e.g. 0001)</MenuItem>
                    <MenuItem value="prefix-fy-sequence">Prefix + FY Suffix + Sequence (e.g. SHORI/GST/26-27/0001)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="financial_year_format">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Financial Year Format</InputLabel>
                  <Select
                    value={settings.financial_year_format || 'YY-YY'}
                    label="Financial Year Format"
                    onChange={(e) => handleFieldChange('financial_year_format', e.target.value)}
                  >
                    <MenuItem value="YYYY-YY">YYYY-YY (e.g. 2026-27)</MenuItem>
                    <MenuItem value="YY-YY">YY-YY (e.g. 26-27)</MenuItem>
                    <MenuItem value="YYYY">Calendar Year (e.g. 2026)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="round_off_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Invoice Rounding Rules</InputLabel>
                  <Select
                    value={settings.round_off_rules || 'nearest_rupee'}
                    label="Invoice Rounding Rules"
                    onChange={(e) => handleFieldChange('round_off_rules', e.target.value)}
                  >
                    <MenuItem value="nearest_rupee">Round to Nearest Rupee (Round Half Up)</MenuItem>
                    <MenuItem value="truncate">Truncate Decimals</MenuItem>
                    <MenuItem value="no_rounding">Disable rounding (Decimal value)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="gst_breakdown_visibility">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Tax Breakdown Layout Visibility</InputLabel>
                  <Select
                    value={settings.gst_breakdown_visibility || 'always_show'}
                    label="Tax Breakdown Layout Visibility"
                    onChange={(e) => handleFieldChange('gst_breakdown_visibility', e.target.value)}
                  >
                    <MenuItem value="always_show">Always print split table (CGST+SGST/IGST)</MenuItem>
                    <MenuItem value="only_interstate">Show split only on Interstate bills</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6} display="flex" flexDirection="column" gap={1.5} mt={1}>
              {[
                { key: 'hsn_mandatory', label: 'Mandate HSN Codes for Goods Invoices' },
                { key: 'sac_mandatory', label: 'Mandate SAC Codes for Service Invoices' },
                { key: 'qr_code_enabled', label: 'Print Dynamic GST Invoice Verification QR Code' },
              ].map((opt) => (
                <FieldWrapper key={opt.key} fieldKey={opt.key}>
                  <Box
                    onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                    sx={{
                      p: 1,
                      border: '1px solid #E5E7EB',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                    }}
                  >
                    <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.78rem' }}>{opt.label}</Typography>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: '4px',
                        border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                        bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {settings[opt.key] && <Box sx={{ width: 4, height: 4, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                    </Box>
                  </Box>
                </FieldWrapper>
              ))}
            </Grid>
          </Grid>
        );
      case 'einvoice':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="e_invoicing_enabled">
                <Box
                  onClick={() => {
                    const nextVal = !settings.e_invoicing_enabled;
                    handleFieldChange('e_invoicing_enabled', nextVal);
                    if (nextVal) {
                      validateField('api_credentials_username', settings.api_credentials_username);
                      validateField('api_credentials_password', settings.api_credentials_password);
                    } else {
                      setValidationErrors(prev => ({ ...prev, api_credentials_username: '', api_credentials_password: '' }));
                    }
                  }}
                  sx={{
                    p: 2,
                    border: `1px solid ${settings.e_invoicing_enabled ? textPrimary : '#E5E7EB'}`,
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.e_invoicing_enabled ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>Enable Government E-Invoicing System</Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                      Automate generation of Invoice Reference Number (IRN) and signed QR codes via official IRP gateways.
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '6px',
                      border: `1px solid ${settings.e_invoicing_enabled ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.e_invoicing_enabled ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.e_invoicing_enabled && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            {settings.e_invoicing_enabled && (
              <>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="irp_provider">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>IRP Service Provider</InputLabel>
                      <Select
                        value={settings.irp_provider || 'nic'}
                        label="IRP Service Provider"
                        onChange={(e) => handleFieldChange('irp_provider', e.target.value)}
                      >
                        <MenuItem value="nic">NIC (National Informatics Centre)</MenuItem>
                        <MenuItem value="clear_tax">ClearTax API Hub Integration</MenuItem>
                        <MenuItem value="ey">EY GSP Connector</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="irn_retry_rules">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>IRN Generation Timing</InputLabel>
                      <Select
                        value={settings.irn_retry_rules || '3_times_exponential'}
                        label="IRN Generation Timing"
                        onChange={(e) => handleFieldChange('irn_retry_rules', e.target.value)}
                      >
                        <MenuItem value="3_times_exponential">Real-time on Invoice Save (Retry 3x)</MenuItem>
                        <MenuItem value="scheduled_batch">Batch sync (Scheduled task run every hour)</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="api_credentials_username">
                    <TextField
                      fullWidth
                      label="IRP API Username"
                      size="small"
                      required
                      error={Boolean(validationErrors.api_credentials_username)}
                      helperText={validationErrors.api_credentials_username || ''}
                      value={settings.api_credentials_username || ''}
                      onChange={(e) => {
                        handleFieldChange('api_credentials_username', e.target.value);
                        validateField('api_credentials_username', e.target.value);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="api_credentials_password">
                    <TextField
                      fullWidth
                      type="password"
                      label="IRP API Password"
                      size="small"
                      required
                      error={Boolean(validationErrors.api_credentials_password)}
                      helperText={validationErrors.api_credentials_password || ''}
                      value={settings.api_credentials_password || ''}
                      onChange={(e) => {
                        handleFieldChange('api_credentials_password', e.target.value);
                        validateField('api_credentials_password', e.target.value);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12}>
                  <FieldWrapper fieldKey="auth_key">
                    <TextField
                      fullWidth
                      label="Authentication Token Key / Client Secret"
                      size="small"
                      value={settings.auth_key || ''}
                      onChange={(e) => handleFieldChange('auth_key', e.target.value)}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6} display="flex" flexDirection="column" gap={1.5}>
                  <FieldWrapper fieldKey="auto_generate_irn">
                    <Box
                      onClick={() => handleFieldChange('auto_generate_irn', !settings.auto_generate_irn)}
                      sx={{
                        p: 1.5,
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings.auto_generate_irn ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.8rem' }}>Auto-create IRN on Invoice completion</Typography>
                      <Box
                        sx={{
                          width: 18,
                          height: 18,
                          borderRadius: '4px',
                          border: `1px solid ${settings.auto_generate_irn ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings.auto_generate_irn ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings.auto_generate_irn && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="auto_generate_qr_code">
                    <Box
                      onClick={() => handleFieldChange('auto_generate_qr_code', !settings.auto_generate_qr_code)}
                      sx={{
                        p: 1.5,
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings.auto_generate_qr_code ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.8rem' }}>Auto-render gov-signed QR Code on invoices</Typography>
                      <Box
                        sx={{
                          width: 18,
                          height: 18,
                          borderRadius: '4px',
                          border: `1px solid ${settings.auto_generate_qr_code ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings.auto_generate_qr_code ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings.auto_generate_qr_code && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                </Grid>
              </>
            )}
          </Grid>
        );
      case 'eway':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="e_way_bill_enabled">
                <Box
                  onClick={() => handleFieldChange('e_way_bill_enabled', !settings.e_way_bill_enabled)}
                  sx={{
                    p: 2,
                    border: `1px solid ${settings.e_way_bill_enabled ? textPrimary : '#E5E7EB'}`,
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.e_way_bill_enabled ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>Enable E-Way Bill Auto Generation</Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                      Automate dispatch reporting and validation documentation for inter-state cargo movement.
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '6px',
                      border: `1px solid ${settings.e_way_bill_enabled ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.e_way_bill_enabled ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.e_way_bill_enabled && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            {settings.e_way_bill_enabled && (
              <>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="distance_threshold">
                    <TextField
                      fullWidth
                      type="number"
                      label="Consignment Valuation Limit (INR)"
                      size="small"
                      error={Boolean(validationErrors.distance_threshold)}
                      helperText={validationErrors.distance_threshold || "Mandates E-Way Bill above this value (standard: 50,000 INR)."}
                      value={settings.distance_threshold || 50000}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        handleFieldChange('distance_threshold', val);
                        validateField('distance_threshold', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6} display="flex" flexDirection="column" gap={1.5} mt={1}>
                  {[
                    { key: 'vehicle_validation', label: 'Verify Transport Vehicle Number formatting' },
                    { key: 'transporter_validation', label: 'Validate Transporter GSTIN / TransID with government portal' },
                    { key: 'auto_generate_e_way_bill', label: 'Auto-create E-Way Bill on invoice release' },
                  ].map((opt) => (
                    <FieldWrapper key={opt.key} fieldKey={opt.key}>
                      <Box
                        onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                        sx={{
                          p: 1.25,
                          border: '1px solid #E5E7EB',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                        }}
                      >
                        <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.78rem' }}>{opt.label}</Typography>
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: '4px',
                            border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                            bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {settings[opt.key] && <Box sx={{ width: 4, height: 4, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                        </Box>
                      </Box>
                    </FieldWrapper>
                  ))}
                </Grid>
              </>
            )}
          </Grid>
        );
      case 'tds':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="tds_enabled">
                <Box
                  onClick={() => handleFieldChange('tds_enabled', !settings.tds_enabled)}
                  sx={{
                    p: 2,
                    border: `1px solid ${settings.tds_enabled ? textPrimary : '#E5E7EB'}`,
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.tds_enabled ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>Enable GST Tax Deducted at Source (TDS)</Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                      Enable automatic deductions on payments to specific contractor groups according to statutory tax sections.
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '6px',
                      border: `1px solid ${settings.tds_enabled ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.tds_enabled ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.tds_enabled && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            {settings.tds_enabled && (
              <>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="default_tds_rate">
                    <TextField
                      fullWidth
                      type="number"
                      label="Default GST TDS Deduction Rate (%)"
                      size="small"
                      error={Boolean(validationErrors.default_tds_rate)}
                      helperText={validationErrors.default_tds_rate || ''}
                      value={settings.default_tds_rate || 2.0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        handleFieldChange('default_tds_rate', val);
                        validateField('default_tds_rate', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="tds_threshold_limits">
                    <TextField
                      fullWidth
                      type="number"
                      label="Transaction Threshold Limit (INR)"
                      size="small"
                      error={Boolean(validationErrors.tds_threshold_limits)}
                      helperText={validationErrors.tds_threshold_limits || "Mandatory deduction trigger point (default: 250,000 INR)."}
                      value={settings.tds_threshold_limits || 250000}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        handleFieldChange('tds_threshold_limits', val);
                        validateField('tds_threshold_limits', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="tds_section_mapping">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>Statutory Act Section</InputLabel>
                      <Select
                        value={settings.tds_section_mapping || 'sec_51'}
                        label="Statutory Act Section"
                        onChange={(e) => handleFieldChange('tds_section_mapping', e.target.value)}
                      >
                        <MenuItem value="sec_51">Section 51 of CGST Act (Government / PSUs)</MenuItem>
                        <MenuItem value="other">Other custom mapping rules</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="vendor_tds_rules">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>Supplier Assessment Mode</InputLabel>
                      <Select
                        value={settings.vendor_tds_rules || 'apply_above_250k'}
                        label="Supplier Assessment Mode"
                        onChange={(e) => handleFieldChange('vendor_tds_rules', e.target.value)}
                      >
                        <MenuItem value="apply_above_250k">Apply TDS when contract valuation exceeds threshold</MenuItem>
                        <MenuItem value="exclude_all">Decline TDS deduction automatically</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
              </>
            )}
          </Grid>
        );
      case 'tcs':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="tcs_enabled">
                <Box
                  onClick={() => handleFieldChange('tcs_enabled', !settings.tcs_enabled)}
                  sx={{
                    p: 2,
                    border: `1px solid ${settings.tcs_enabled ? textPrimary : '#E5E7EB'}`,
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.tcs_enabled ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>Enable GST Tax Collection at Source (TCS)</Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                      Automate collections on marketplace transactions for digital vendor networks.
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '6px',
                      border: `1px solid ${settings.tcs_enabled ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.tcs_enabled ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.tcs_enabled && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            {settings.tcs_enabled && (
              <>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="marketplace_tcs">
                    <TextField
                      fullWidth
                      type="number"
                      label="Marketplace Operator TCS Rate (%)"
                      size="small"
                      error={Boolean(validationErrors.marketplace_tcs)}
                      helperText={validationErrors.marketplace_tcs || ''}
                      value={settings.marketplace_tcs || 1.0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        handleFieldChange('marketplace_tcs', val);
                        validateField('marketplace_tcs', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="e_commerce_tcs">
                    <TextField
                      fullWidth
                      type="number"
                      label="E-Commerce Merchant TCS Rate (%)"
                      size="small"
                      error={Boolean(validationErrors.e_commerce_tcs)}
                      helperText={validationErrors.e_commerce_tcs || ''}
                      value={settings.e_commerce_tcs || 1.0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        handleFieldChange('e_commerce_tcs', val);
                        validateField('e_commerce_tcs', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="tcs_collection_frequency">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>TCS Collection Schedule</InputLabel>
                      <Select
                        value={settings.tcs_collection_frequency || 'monthly'}
                        label="TCS Collection Schedule"
                        onChange={(e) => handleFieldChange('tcs_collection_frequency', e.target.value)}
                      >
                        <MenuItem value="monthly">Monthly filing cycles</MenuItem>
                        <MenuItem value="realtime">Deduct on payment checkout release</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="tcs_collection_threshold">
                    <TextField
                      fullWidth
                      type="number"
                      label="Annual TCS Threshold limit (INR)"
                      size="small"
                      error={Boolean(validationErrors.tcs_collection_threshold)}
                      helperText={validationErrors.tcs_collection_threshold || ''}
                      value={settings.tcs_collection_threshold || 250000}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        handleFieldChange('tcs_collection_threshold', val);
                        validateField('tcs_collection_threshold', val);
                      }}
                      sx={inputStyle}
                    />
                  </FieldWrapper>
                </Grid>
              </>
            )}
          </Grid>
        );
      case 'rcm':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <FieldWrapper fieldKey="rcm_enabled">
                <Box
                  onClick={() => handleFieldChange('rcm_enabled', !settings.rcm_enabled)}
                  sx={{
                    p: 2,
                    border: `1px solid ${settings.rcm_enabled ? textPrimary : '#E5E7EB'}`,
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.rcm_enabled ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>Enable Reverse Charge Mechanism (RCM)</Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                      Transfer tax reporting liability from the supplier to the corporate buyer for specified categories.
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '6px',
                      border: `1px solid ${settings.rcm_enabled ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.rcm_enabled ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.rcm_enabled && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            {settings.rcm_enabled && (
              <>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="rcm_posting_rules">
                    <FormControl fullWidth size="small" sx={inputStyle}>
                      <InputLabel>RCM Posting Rules</InputLabel>
                      <Select
                        value={settings.rcm_posting_rules || 'create_liability_and_itc'}
                        label="RCM Posting Rules"
                        onChange={(e) => handleFieldChange('rcm_posting_rules', e.target.value)}
                      >
                        <MenuItem value="create_liability_and_itc">Auto-Create Liability + Contra Input Credit (ITC)</MenuItem>
                        <MenuItem value="manual_accrual">Requires manual tax journal allocation</MenuItem>
                      </Select>
                    </FormControl>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6} display="flex" alignItems="center">
                  <FieldWrapper fieldKey="auto_rcm_detection">
                    <Box
                      onClick={() => handleFieldChange('auto_rcm_detection', !settings.auto_rcm_detection)}
                      sx={{
                        p: 1.5,
                        width: '100%',
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings.auto_rcm_detection ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.8rem' }}>Automate RCM triggers from ledger category mappings</Typography>
                      <Box
                        sx={{
                          width: 18,
                          height: 18,
                          borderRadius: '4px',
                          border: `1px solid ${settings.auto_rcm_detection ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings.auto_rcm_detection ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings.auto_rcm_detection && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="rcm_vendor_categories">
                    <TextField
                      fullWidth
                      label="RCM Vendor Tax Categories"
                      size="small"
                      value={(settings.rcm_vendor_categories || []).join(', ')}
                      onChange={(e) => handleFieldChange('rcm_vendor_categories', e.target.value.split(',').map(s => s.trim()))}
                      sx={inputStyle}
                      helperText="Comma separated supplier tags that trigger auto RCM liability."
                    />
                  </FieldWrapper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <FieldWrapper fieldKey="rcm_expense_categories">
                    <TextField
                      fullWidth
                      label="RCM Expense Ledger Codes"
                      size="small"
                      value={(settings.rcm_expense_categories || []).join(', ')}
                      onChange={(e) => handleFieldChange('rcm_expense_categories', e.target.value.split(',').map(s => s.trim()))}
                      sx={inputStyle}
                      helperText="Comma separated chart-of-accounts expense codes subject to RCM."
                    />
                  </FieldWrapper>
                </Grid>
              </>
            )}
          </Grid>
        );
      case 'return':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="gstr1_frequency">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>GSTR-1 Sales Report Frequency</InputLabel>
                  <Select
                    value={settings.gstr1_frequency || 'monthly'}
                    label="GSTR-1 Sales Report Frequency"
                    onChange={(e) => handleFieldChange('gstr1_frequency', e.target.value)}
                  >
                    <MenuItem value="monthly">Monthly filing (due 11th)</MenuItem>
                    <MenuItem value="quarterly">Quarterly filing (due 13th - IFF option)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="gstr3b_frequency">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>GSTR-3B Tax Return Frequency</InputLabel>
                  <Select
                    value={settings.gstr3b_frequency || 'monthly'}
                    label="GSTR-3B Tax Return Frequency"
                    onChange={(e) => handleFieldChange('gstr3b_frequency', e.target.value)}
                  >
                    <MenuItem value="monthly">Monthly payment offset (due 20th)</MenuItem>
                    <MenuItem value="quarterly">Quarterly payment offset (QRMP schedule)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="due_date_alerts">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Compliance Alerts Threshold</InputLabel>
                  <Select
                    value={settings.due_date_alerts || '5_days_prior'}
                    label="Compliance Alerts Threshold"
                    onChange={(e) => handleFieldChange('due_date_alerts', e.target.value)}
                  >
                    <MenuItem value="5_days_prior">Send reminders 5 days prior to filing dates</MenuItem>
                    <MenuItem value="10_days_prior">Send reminders 10 days prior</MenuItem>
                    <MenuItem value="never">Disable system reminders</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6} display="flex" flexDirection="column" gap={1.5}>
              {[
                { key: 'gstr9_enabled', label: 'Include Annual GSTR-9 Reconciliation audits' },
                { key: 'gstr9c_enabled', label: 'Include Certified GSTR-9C audit reports' },
              ].map((opt) => (
                <FieldWrapper key={opt.key} fieldKey={opt.key}>
                  <Box
                    onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                    sx={{
                      p: 1.25,
                      border: '1px solid #E5E7EB',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                    }}
                  >
                    <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.8rem' }}>{opt.label}</Typography>
                    <Box
                      sx={{
                        width: 16,
                        height: 16,
                        borderRadius: '4px',
                        border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                        bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {settings[opt.key] && <Box sx={{ width: 4, height: 4, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                    </Box>
                  </Box>
                </FieldWrapper>
              ))}
            </Grid>
          </Grid>
        );
      case 'hsn':
        return (
          <Box display="flex" flexDirection="column" gap={3}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="body2" fontWeight={600} color={textPrimary}>HSN/SAC Code Master Directory</Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  const newId = 'hs_' + Date.now();
                  const updated = [
                    ...settings.hsn_sac_codes,
                    { id: newId, code: '000000', type: 'HSN', description: 'New custom items catalog code mapping', rate: '18.00', status: 'active' }
                  ];
                  handleFieldChange('hsn_sac_codes', updated);
                }}
                sx={{
                  textTransform: 'none',
                  borderColor: '#E5E7EB',
                  color: textPrimary,
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  borderRadius: '8px',
                  '&:hover': { borderColor: '#cbd5e1', bgcolor: '#f9fafb' },
                }}
              >
                + Register New HSN/SAC Code
              </Button>
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: '#f9fafc' }}>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>HSN / SAC Code</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Default Rate (%)</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Description</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {settings.hsn_sac_codes.map((item, index) => (
                    <TableRow key={item.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <select
                          value={item.type}
                          onChange={(e) => {
                            const copy = [...settings.hsn_sac_codes];
                            copy[index].type = e.target.value;
                            handleFieldChange('hsn_sac_codes', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', fontWeight: 600, background: 'transparent' }}
                        >
                          <option value="HSN">HSN (Goods)</option>
                          <option value="SAC">SAC (Services)</option>
                        </select>
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <input
                          type="text"
                          value={item.code}
                          onChange={(e) => {
                            const copy = [...settings.hsn_sac_codes];
                            copy[index].code = e.target.value.replace(/[^0-9]/g, '');
                            handleFieldChange('hsn_sac_codes', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', width: '90px', fontFamily: 'monospace', fontWeight: 600 }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <select
                          value={item.rate}
                          onChange={(e) => {
                            const copy = [...settings.hsn_sac_codes];
                            copy[index].rate = e.target.value;
                            handleFieldChange('hsn_sac_codes', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', background: 'transparent' }}
                        >
                          <option value="0.00">0%</option>
                          <option value="5.00">5%</option>
                          <option value="12.00">12%</option>
                          <option value="18.00">18%</option>
                          <option value="28.00">28%</option>
                        </select>
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <input
                          type="text"
                          value={item.description}
                          onChange={(e) => {
                            const copy = [...settings.hsn_sac_codes];
                            copy[index].description = e.target.value;
                            handleFieldChange('hsn_sac_codes', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', width: '100%', color: textSecondary }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <Box
                          component="button"
                          onClick={() => {
                            const copy = [...settings.hsn_sac_codes];
                            copy[index].status = item.status === 'active' ? 'inactive' : 'active';
                            handleFieldChange('hsn_sac_codes', copy);
                          }}
                          sx={{
                            px: 1,
                            py: 0.25,
                            border: 0,
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            bgcolor: item.status === 'active' ? '#e6fbf4' : '#fee2e2',
                            color: item.status === 'active' ? '#10b981' : '#ef4444',
                          }}
                        >
                          {item.status.toUpperCase()}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>
                        <Button
                          size="small"
                          color="error"
                          onClick={() => {
                            const updated = settings.hsn_sac_codes.filter((_, idx) => idx !== index);
                            handleFieldChange('hsn_sac_codes', updated);
                          }}
                          sx={{ textTransform: 'none', fontSize: '0.7rem', p: 0.25 }}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        );
      case 'exempt':
        return (
          <Grid container spacing={3.5}>
            {[
              { key: 'exempt_products', label: 'Exempt Goods / Product Categories', desc: 'Statutorily exempt supplies from GST collections (comma separated).' },
              { key: 'nil_rated_products', label: 'Nil-Rated Supply Categories', desc: 'Standard tax items set to concessional 0% rate slabs (comma separated).' },
              { key: 'non_gst_supplies', label: 'Non-GST / Out-of-Scope Categories', desc: 'Items out of the scope of CGST/SGST acts like fuel, petroleum, alcohol (comma separated).' },
            ].map((field) => (
              <Grid item xs={12} key={field.key}>
                <FieldWrapper fieldKey={field.key}>
                  <TextField
                    fullWidth
                    label={field.label}
                    size="small"
                    value={(settings[field.key] || []).join(', ')}
                    onChange={(e) => handleFieldChange(field.key, e.target.value.split(',').map(s => s.trim()))}
                    sx={inputStyle}
                    helperText={field.desc}
                  />
                </FieldWrapper>
              </Grid>
            ))}
          </Grid>
        );
      case 'import_export':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="import_goods_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Import Goods Duty Treatment</InputLabel>
                  <Select
                    value={settings.import_goods_treatment || 'apply_sigst'}
                    label="Import Goods Duty Treatment"
                    onChange={(e) => handleFieldChange('import_goods_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_igst">Assess IGST standard rates on Customs valuation</MenuItem>
                    <MenuItem value="capital_goods_exemption">Exempt capital inputs (EPCG Scheme)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="import_services_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Import Services Tax Treatment</InputLabel>
                  <Select
                    value={settings.import_services_treatment || 'apply_igst_rcm'}
                    label="Import Services Tax Treatment"
                    onChange={(e) => handleFieldChange('import_services_treatment', e.target.value)}
                  >
                    <MenuItem value="apply_igst_rcm">Charge IGST under Reverse Charge Mechanism (RCM)</MenuItem>
                    <MenuItem value="exempt">Exempt (Intra-firm service allocation)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="custom_duty_mapping">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Custom Duty Posting Rule</InputLabel>
                  <Select
                    value={settings.custom_duty_mapping || 'add_to_cost_base'}
                    label="Custom Duty Posting Rule"
                    onChange={(e) => handleFieldChange('custom_duty_mapping', e.target.value)}
                  >
                    <MenuItem value="add_to_cost_base">Capitalize and add to inventory cost base</MenuItem>
                    <MenuItem value="expense_immediately">Debit immediately as import duty expense</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="igst_treatment">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>IGST Credit Claim Logic</InputLabel>
                  <Select
                    value={settings.igst_treatment || 'claim_itc'}
                    label="IGST Credit Claim Logic"
                    onChange={(e) => handleFieldChange('igst_treatment', e.target.value)}
                  >
                    <MenuItem value="claim_itc">Assert full ITC credit on import entry</MenuItem>
                    <MenuItem value="non_claimable">Convert to product acquisition cost</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="export_with_lut">
                <Box
                  onClick={() => handleFieldChange('export_with_lut', !settings.export_with_lut)}
                  sx={{
                    p: 1.5,
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.export_with_lut ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="body2" fontWeight={600} color={textPrimary} sx={{ fontSize: '0.8rem' }}>Exempt Export Taxes under LUT (Letter of Undertaking)</Typography>
                    <Typography variant="caption" color={textSecondary} display="block" sx={{ fontSize: '0.7rem' }}>Enables zero-rated invoicing for outbound overseas shipments.</Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 18,
                      height: 18,
                      borderRadius: '4px',
                      border: `1px solid ${settings.export_with_lut ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.export_with_lut ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.export_with_lut && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="export_without_lut">
                <Box
                  onClick={() => handleFieldChange('export_without_lut', !settings.export_without_lut)}
                  sx={{
                    p: 1.5,
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.export_without_lut ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="body2" fontWeight={600} color={textPrimary} sx={{ fontSize: '0.8rem' }}>Charge Export taxes at standard IGST rates</Typography>
                    <Typography variant="caption" color={textSecondary} display="block" sx={{ fontSize: '0.7rem' }}>Enables claim for refund afterwards (Refund route).</Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 18,
                      height: 18,
                      borderRadius: '4px',
                      border: `1px solid ${settings.export_without_lut ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.export_without_lut ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.export_without_lut && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'sez':
        return (
          <Grid container spacing={3.5}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="sez_customer_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>SEZ Customer Supply Rules</InputLabel>
                  <Select
                    value={settings.sez_customer_rules || 'zero_rated_with_lut'}
                    label="SEZ Customer Supply Rules"
                    onChange={(e) => handleFieldChange('sez_customer_rules', e.target.value)}
                  >
                    <MenuItem value="zero_rated_with_lut">Zero-Rated supply (requires validated LUT file)</MenuItem>
                    <MenuItem value="apply_igst">Charge integrated tax (IGST 18%)</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="sez_vendor_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>SEZ Supplier Procurement Rules</InputLabel>
                  <Select
                    value={settings.sez_vendor_rules || 'treat_as_import'}
                    label="SEZ Supplier Procurement Rules"
                    onChange={(e) => handleFieldChange('sez_vendor_rules', e.target.value)}
                  >
                    <MenuItem value="treat_as_import">Assess procurement as Importation under RCM</MenuItem>
                    <MenuItem value="domestic_zero_rated">Treat as local domestic zero-tax acquisition</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="sez_zero_rated_supply_rules">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>SEZ Tax Exemption Scheme</InputLabel>
                  <Select
                    value={settings.sez_zero_rated_supply_rules || 'apply_igst_exemption'}
                    label="SEZ Tax Exemption Scheme"
                    onChange={(e) => handleFieldChange('sez_zero_rated_supply_rules', e.target.value)}
                  >
                    <MenuItem value="apply_igst_exemption">Exempt under section 16 of IGST Act</MenuItem>
                    <MenuItem value="none">Standard taxation logic</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="sez_documentation">
                <Typography variant="body2" fontWeight={600} mb={1.25} color={textPrimary}>Compliance Document checklist</Typography>
                <Box display="flex" flexDirection="column" gap={1.25}>
                  {[
                    { value: 'bill_of_export', label: 'Mandate Bill of Export validation' },
                    { value: 'sez_endorsement', label: 'Require SEZ Customs officer endorsement document' },
                  ].map((doc) => {
                    const active = (settings.sez_documentation || []).includes(doc.value);
                    return (
                      <Box
                        key={doc.value}
                        onClick={() => {
                          const copy = active
                            ? settings.sez_documentation.filter(d => d !== doc.value)
                            : [...(settings.sez_documentation || []), doc.value];
                          handleFieldChange('sez_documentation', copy);
                        }}
                        sx={{
                          p: 1.25,
                          border: '1px solid #E5E7EB',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          bgcolor: active ? '#f9fafb' : '#ffffff',
                        }}
                      >
                        <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.78rem' }}>{doc.label}</Typography>
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: '4px',
                            border: `1px solid ${active ? textPrimary : '#E5E7EB'}`,
                            bgcolor: active ? textPrimary : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {active && <Box sx={{ width: 4, height: 4, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'notes':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="credit_note_prefix">
                <TextField
                  fullWidth
                  label="Credit Note Number Prefix"
                  size="small"
                  value={settings.credit_note_prefix || ''}
                  onChange={(e) => handleFieldChange('credit_note_prefix', e.target.value)}
                  sx={inputStyle}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="debit_note_prefix">
                <TextField
                  fullWidth
                  label="Debit Note Number Prefix"
                  size="small"
                  value={settings.debit_note_prefix || ''}
                  onChange={(e) => handleFieldChange('debit_note_prefix', e.target.value)}
                  sx={inputStyle}
                />
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6}>
              <FieldWrapper fieldKey="note_approval_workflow">
                <FormControl fullWidth size="small" sx={inputStyle}>
                  <InputLabel>Workflow Approvals Requirement</InputLabel>
                  <Select
                    value={settings.note_approval_workflow || 'two_manager_signoff'}
                    label="Workflow Approvals Requirement"
                    onChange={(e) => handleFieldChange('note_approval_workflow', e.target.value)}
                  >
                    <MenuItem value="two_manager_signoff">Requires Dual Manager verification signoff</MenuItem>
                    <MenuItem value="auto_approve">Instant Approval and Posting</MenuItem>
                  </Select>
                </FormControl>
              </FieldWrapper>
            </Grid>
            <Grid item xs={12} md={6} display="flex" alignItems="center">
              <FieldWrapper fieldKey="auto_gst_adjustment">
                <Box
                  onClick={() => handleFieldChange('auto_gst_adjustment', !settings.auto_gst_adjustment)}
                  sx={{
                    p: 1.5,
                    width: '100%',
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    bgcolor: settings.auto_gst_adjustment ? '#f9fafb' : '#ffffff',
                  }}
                >
                  <Box>
                    <Typography variant="body2" fontWeight={600} color={textPrimary} sx={{ fontSize: '0.8rem' }}>Automate Tax Liability Adjustments</Typography>
                    <Typography variant="caption" color={textSecondary} display="block" sx={{ fontSize: '0.7rem' }}>Adjust ledger liability automatically on CN/DN creation.</Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 18,
                      height: 18,
                      borderRadius: '4px',
                      border: `1px solid ${settings.auto_gst_adjustment ? textPrimary : '#E5E7EB'}`,
                      bgcolor: settings.auto_gst_adjustment ? textPrimary : 'transparent',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {settings.auto_gst_adjustment && <Box sx={{ width: 5, height: 5, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                  </Box>
                </Box>
              </FieldWrapper>
            </Grid>
          </Grid>
        );
      case 'automation':
        return (
          <Box display="flex" flexDirection="column" gap={3}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="body2" fontWeight={600} color={textPrimary}>GST Automation Conditional Rules</Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  const newId = 'ar_' + Date.now();
                  const updated = [
                    ...settings.automation_rules,
                    { id: newId, name: 'New Custom Rule', condition: 'Customer Country != India', action: 'Apply IGST 0% (Export LUT)', status: 'active' }
                  ];
                  handleFieldChange('automation_rules', updated);
                }}
                sx={{
                  textTransform: 'none',
                  borderColor: '#E5E7EB',
                  color: textPrimary,
                  fontWeight: 600,
                  fontSize: '0.75rem',
                  borderRadius: '8px',
                  '&:hover': { borderColor: '#cbd5e1', bgcolor: '#f9fafb' },
                }}
              >
                + Create Custom Rule
              </Button>
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: '#f9fafc' }}>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Rule Name</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>IF Condition</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>THEN Action</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {settings.automation_rules.map((rule, index) => (
                    <TableRow key={rule.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <input
                          type="text"
                          value={rule.name}
                          onChange={(e) => {
                            const copy = [...settings.automation_rules];
                            copy[index].name = e.target.value;
                            handleFieldChange('automation_rules', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', fontWeight: 600, width: '100%' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <input
                          type="text"
                          value={rule.condition}
                          onChange={(e) => {
                            const copy = [...settings.automation_rules];
                            copy[index].condition = e.target.value;
                            handleFieldChange('automation_rules', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', width: '100%', fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB' }}>
                        <input
                          type="text"
                          value={rule.action}
                          onChange={(e) => {
                            const copy = [...settings.automation_rules];
                            copy[index].action = e.target.value;
                            handleFieldChange('automation_rules', copy);
                          }}
                          style={{ border: 0, fontSize: '0.8rem', width: '100%', fontWeight: 600 }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                        <Box
                          component="button"
                          onClick={() => {
                            const copy = [...settings.automation_rules];
                            copy[index].status = rule.status === 'active' ? 'inactive' : 'active';
                            handleFieldChange('automation_rules', copy);
                          }}
                          sx={{
                            px: 1,
                            py: 0.25,
                            border: 0,
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            bgcolor: rule.status === 'active' ? '#e6fbf4' : '#fee2e2',
                            color: rule.status === 'active' ? '#10b981' : '#ef4444',
                          }}
                        >
                          {rule.status.toUpperCase()}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>
                        <Button
                          size="small"
                          color="error"
                          onClick={() => {
                            const updated = settings.automation_rules.filter((_, idx) => idx !== index);
                            handleFieldChange('automation_rules', updated);
                          }}
                          sx={{ textTransform: 'none', fontSize: '0.7rem', p: 0.25 }}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        );
      case 'validation':
        return (
          <Grid container spacing={3.5}>
            {[
              { key: 'validate_gstin', label: 'Statutory GSTIN format checks', desc: 'Perform live structure regex validation matches on user input.' },
              { key: 'validate_pan', label: 'Statutory PAN validity checks', desc: 'Verify PAN formatting rules before ledger entries are committed.' },
              { key: 'validate_hsn', label: 'Mandatory HSN/SAC code validation', desc: 'Prevent invoice saving if product codes are missing or incomplete.' },
              { key: 'duplicate_invoice_detection', label: 'Double Invoicing alert trigger', desc: 'Scan ledger to block duplicate vendor invoice numbers.' },
              { key: 'duplicate_gst_filing_detection', label: 'Duplicate GST Return check', desc: 'Alert if return data is submitted twice for the same tax period.' },
            ].map((opt) => (
              <Grid item xs={12} key={opt.key}>
                <FieldWrapper fieldKey={opt.key}>
                  <Box
                    onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                    sx={{
                      p: 2,
                      border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                    }}
                  >
                    <Box>
                      <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>{opt.label}</Typography>
                      <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>{opt.desc}</Typography>
                    </Box>
                    <Box
                      sx={{
                        width: 20,
                        height: 20,
                        borderRadius: '4px',
                        border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                        bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {settings[opt.key] && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                    </Box>
                  </Box>
                </FieldWrapper>
              </Grid>
            ))}
          </Grid>
        );
      case 'alerts':
        return (
          <Grid container spacing={3.5}>
            <Grid item xs={12}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>Active Compliance Alerts Notifications</Typography>
              <Grid container spacing={2.5}>
                {[
                  { key: 'alert_filing_due', label: 'Filing Due Date Alerts', desc: 'Receive reminders prior to GSTR-1 & 3B compliance deadlines.' },
                  { key: 'alert_itc_mismatch', label: 'ITC Reconcile Mismatch Alerts', desc: 'Triggers when supplier files do not match local purchase credit claims.' },
                  { key: 'alert_return_rejection', label: 'Gov Portal Filing Failures', desc: 'Alerts if GST return is rejected on official tax portals.' },
                  { key: 'alert_invoice_failure', label: 'Invoicing Integration Failures', desc: 'Notify if external sales ledger syncing fails.' },
                  { key: 'alert_e_invoice_failure', label: 'E-Invoice IRN Failure Alerts', desc: 'Alert if Government IRN generation fails on invoice checkout.' },
                  { key: 'alert_e_way_bill_failure', label: 'E-Way Bill Generation Failures', desc: 'Alert if transport distance/vehicle details fail validation.' },
                ].map((opt) => (
                  <Grid item xs={12} md={6} key={opt.key}>
                    <FieldWrapper fieldKey={opt.key}>
                      <Box
                        onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                        sx={{
                          p: 2,
                          border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                          height: '100%',
                        }}
                      >
                        <Box pr={2}>
                          <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>{opt.label}</Typography>
                          <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.72rem', lineHeight: 1.3 }}>{opt.desc}</Typography>
                        </Box>
                        <Box
                          sx={{
                            width: 18,
                            height: 18,
                            borderRadius: '4px',
                            border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                            bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {settings[opt.key] && <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#ffffff' }} />}
                        </Box>
                      </Box>
                    </FieldWrapper>
                  </Grid>
                ))}
              </Grid>
            </Grid>
          </Grid>
        );
      case 'mapping':
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="body2" fontWeight={600} mb={1.5} color={textPrimary}>Chart Of Accounts double-entry mapping</Typography>
            </Grid>
            {[
              { key: 'output_cgst_ledger', label: 'Output CGST Liability account' },
              { key: 'output_sgst_ledger', label: 'Output SGST Liability account' },
              { key: 'output_igst_ledger', label: 'Output IGST Liability account' },
              { key: 'input_cgst_ledger', label: 'Input CGST Asset Credit account' },
              { key: 'input_sgst_ledger', label: 'Input SGST Asset Credit account' },
              { key: 'input_igst_ledger', label: 'Input IGST Asset Credit account' },
              { key: 'tds_gst_receivable', label: 'GST TDS Receivable account' },
              { key: 'tcs_gst_receivable', label: 'GST TCS Receivable account' },
            ].map((ledger) => (
              <Grid item xs={12} md={6} key={ledger.key}>
                <FieldWrapper fieldKey={ledger.key}>
                  <TextField
                    fullWidth
                    label={ledger.label}
                    size="small"
                    error={Boolean(validationErrors[ledger.key])}
                    helperText={validationErrors[ledger.key] || ''}
                    value={settings[ledger.key] || ''}
                    onChange={(e) => {
                      handleFieldChange(ledger.key, e.target.value);
                      validateField(ledger.key, e.target.value);
                    }}
                    sx={inputStyle}
                  />
                </FieldWrapper>
              </Grid>
            ))}
          </Grid>
        );
      case 'advanced':
        return (
          <Box display="flex" flexDirection="column" gap={4.5}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <FieldWrapper fieldKey="fiscal_year">
                  <FormControl fullWidth size="small" sx={inputStyle}>
                    <InputLabel>Compliance Fiscal Period</InputLabel>
                    <Select
                      value={settings.fiscal_year || 'april_march'}
                      label="Compliance Fiscal Period"
                      onChange={(e) => handleFieldChange('fiscal_year', e.target.value)}
                    >
                      <MenuItem value="april_march">April to March (Indian Financial Year)</MenuItem>
                      <MenuItem value="calendar">January to December (Calendar Year)</MenuItem>
                    </Select>
                  </FormControl>
                </FieldWrapper>
              </Grid>
              <Grid item xs={12} md={6}>
                <FieldWrapper fieldKey="rounding_rules">
                  <FormControl fullWidth size="small" sx={inputStyle}>
                    <InputLabel>GST Rounding Calculation Mode</InputLabel>
                    <Select
                      value={settings.rounding_rules || 'round_half_up'}
                      label="GST Rounding Calculation Mode"
                      onChange={(e) => handleFieldChange('rounding_rules', e.target.value)}
                    >
                      <MenuItem value="round_half_up">Round Half Up (Standard Math)</MenuItem>
                      <MenuItem value="round_floor">Always Round Down (Floor)</MenuItem>
                      <MenuItem value="round_ceil">Always Round Up (Ceil)</MenuItem>
                    </Select>
                  </FormControl>
                </FieldWrapper>
              </Grid>
              <Grid item xs={12} md={6}>
                <FieldWrapper fieldKey="decimal_precision">
                  <TextField
                    fullWidth
                    type="number"
                    label="Calculation Decimal Precision"
                    size="small"
                    value={settings.decimal_precision || 2}
                    onChange={(e) => handleFieldChange('decimal_precision', Number(e.target.value) || 2)}
                    sx={inputStyle}
                    helperText="Default precision decimals stored on tax values (standard is 2)."
                  />
                </FieldWrapper>
              </Grid>
              <Grid item xs={12} md={6}>
                <FieldWrapper fieldKey="timezone">
                  <TextField
                    fullWidth
                    label="Organization Jurisdiction Timezone"
                    size="small"
                    value={settings.timezone || 'Asia/Kolkata'}
                    onChange={(e) => handleFieldChange('timezone', e.target.value)}
                    sx={inputStyle}
                  />
                </FieldWrapper>
              </Grid>
              <Grid item xs={12} md={6} display="flex" flexDirection="column" gap={1.5}>
                {[
                  { key: 'auto_posting', label: 'Enable automatic Ledger posting' },
                  { key: 'auto_reconciliation', label: 'Enable automatic Purchase invoice reconciliation' },
                  { key: 'auto_itc_matching', label: 'Enable automatic ITC Credit approvals matching' },
                  { key: 'audit_log_enabled', label: 'Enable Configuration Edit Audit Log History' },
                ].map((opt) => (
                  <FieldWrapper key={opt.key} fieldKey={opt.key}>
                    <Box
                      onClick={() => handleFieldChange(opt.key, !settings[opt.key])}
                      sx={{
                        p: 1.25,
                        border: '1px solid #E5E7EB',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: settings[opt.key] ? '#f9fafb' : '#ffffff',
                      }}
                    >
                      <Typography variant="body2" color={textPrimary} sx={{ fontSize: '0.8rem' }}>{opt.label}</Typography>
                      <Box
                        sx={{
                          width: 16,
                          height: 16,
                          borderRadius: '4px',
                          border: `1px solid ${settings[opt.key] ? textPrimary : '#E5E7EB'}`,
                          bgcolor: settings[opt.key] ? textPrimary : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {settings[opt.key] && <Box sx={{ width: 4, height: 4, bgcolor: '#ffffff', borderRadius: '50%' }} />}
                      </Box>
                    </Box>
                  </FieldWrapper>
                ))}
              </Grid>
            </Grid>

            {/* Audit Log / Edit History Section */}
            {settings.audit_log_enabled && (
              <Box borderTop="1px solid #E5E7EB" pt={3.5}>
                <Typography variant="body2" fontWeight={700} color={textPrimary} mb={2}>
                  Configuration Edit History & Audit Trail Log
                </Typography>
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ bgcolor: '#f9fafc' }}>
                        <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Timestamp</TableCell>
                        <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>User</TableCell>
                        <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Action</TableCell>
                        <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Details</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {auditLog.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                            {new Date(log.timestamp).toLocaleString('en-IN')}
                          </TableCell>
                          <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', fontWeight: 600 }}>
                            {log.user}
                          </TableCell>
                          <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem' }}>
                            {log.action}
                          </TableCell>
                          <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', color: textSecondary }}>
                            {log.details}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            )}
          </Box>
        );
      default:
        return null;
    }
  };

  // Day 2 Compliance Page Renderers

  const renderSummaryPage = () => {
    if (summaryLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (summaryError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{summaryError}</Alert>
      );
    }

    const metrics = summaryData?.metrics || {};
    const composition = summaryData?.composition || {};
    const chartData = summaryData?.chart_data || [];
    const summaryTable = summaryData?.summary_table || [];

    const donutData = [
      { name: 'CGST', value: parseFloat(composition.cgst || 0), color: '#0F172A' },
      { name: 'SGST', value: parseFloat(composition.sgst || 0), color: '#64748B' },
      { name: 'IGST', value: parseFloat(composition.igst || 0), color: '#38bdf8' },
      { name: 'CESS', value: parseFloat(composition.cess || 0), color: '#cbd5e1' },
    ].filter(d => d.value > 0);

    return (
      <Box display="flex" flexDirection="column" gap={3.5}>
        {/* KPI Cards Grid */}
        <Grid container spacing={2.5}>
          {[
            { label: 'GST Collected (Output)', val: `₹${fmt(metrics.collected)}`, sub: 'Tax collected on sales orders' },
            { label: 'GST Paid (Input)', val: `₹${fmt(metrics.paid)}`, sub: 'Tax paid on purchases & expenses' },
            { label: 'Net GST Liability', val: `₹${fmt(metrics.net_liability)}`, sub: 'Output GST - Input GST' },
            { label: 'Available ITC', val: `₹${fmt(metrics.available_itc)}`, sub: 'Total eligible credit available' },
            { label: 'Upcoming Filing', val: `${metrics.upcoming_filing} Days`, sub: 'Days remaining for next deadline' },
            { label: 'GST Accuracy Score', val: `${metrics.accuracy_score}%`, sub: 'Based on reconciled ledger lines' },
          ].map((kpi, i) => (
            <Grid item xs={12} sm={6} md={4} key={i}>
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                  <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.7rem' }}>
                    {kpi.label}
                  </Typography>
                  <Typography variant="h5" fontWeight={700} color={textPrimary} mt={1} mb={0.5} sx={{ fontFamily: '"SF Mono", "JetBrains Mono", monospace', letterSpacing: '-0.02em' }}>
                    {kpi.val}
                  </Typography>
                  <Typography variant="caption" color={textSecondary} sx={{ fontSize: '0.72rem' }}>
                    {kpi.sub}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Filter Bar */}
        <Box p={2} border={`1px solid ${borderCol}`} borderRadius="12px" bgcolor="#ffffff" display="flex" flexWrap="wrap" gap={2} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 120, ...inputStyle }}>
            <InputLabel shrink>FY</InputLabel>
            <Select value={filterFY} label="FY" displayEmpty onChange={(e) => setFilterFY(e.target.value)}>
              <MenuItem value="2026-2027">2026-27</MenuItem>
              <MenuItem value="2025-2026">2025-26</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120, ...inputStyle }}>
            <InputLabel shrink>Month</InputLabel>
            <Select value={filterMonth} label="Month" displayEmpty onChange={(e) => setFilterMonth(e.target.value)}>
              <MenuItem value="">All Months</MenuItem>
              {Array.from({ length: 12 }, (_, i) => (
                <MenuItem key={i + 1} value={String(i + 1)}>
                  {new Date(0, i).toLocaleString('default', { month: 'short' })}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120, ...inputStyle }}>
            <InputLabel shrink>Quarter</InputLabel>
            <Select value={filterQuarter} label="Quarter" displayEmpty onChange={(e) => setFilterQuarter(e.target.value)}>
              <MenuItem value="all">All Quarters</MenuItem>
              <MenuItem value="Q1">Q1 (Apr-Jun)</MenuItem>
              <MenuItem value="Q2">Q2 (Jul-Sep)</MenuItem>
              <MenuItem value="Q3">Q3 (Oct-Dec)</MenuItem>
              <MenuItem value="Q4">Q4 (Jan-Mar)</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120, ...inputStyle }}>
            <InputLabel shrink>GST Type</InputLabel>
            <Select value={filterGSTType} label="GST Type" displayEmpty onChange={(e) => setFilterGSTType(e.target.value)}>
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="cgst">CGST</MenuItem>
              <MenuItem value="sgst">SGST</MenuItem>
              <MenuItem value="igst">IGST</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140, ...inputStyle }}>
            <InputLabel shrink>Business Unit</InputLabel>
            <Select value={filterBU} label="Business Unit" displayEmpty onChange={(e) => setFilterBU(e.target.value)}>
              <MenuItem value="all">All Units</MenuItem>
              <MenuItem value="retail">Retail Division</MenuItem>
              <MenuItem value="b2b">Corporate B2B</MenuItem>
            </Select>
          </FormControl>
          <Box flexGrow={1} />
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={(e) => handleMenuOpen('summary', e)}
            sx={{
              textTransform: 'none',
              borderColor: borderCol,
              color: textPrimary,
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.8rem',
              height: 36,
              bgcolor: isDark ? '#111827' : '#ffffff',
              '&:hover': {
                borderColor: isDark ? '#475569' : '#cbd5e1',
                bgcolor: isDark ? '#1f2937' : '#f8fafc',
              }
            }}
          >
            Export
          </Button>
          <Menu
            anchorEl={anchorElMap['summary']}
            open={Boolean(anchorElMap['summary'])}
            onClose={() => handleMenuClose('summary')}
            slotProps={{
              paper: {
                sx: {
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                  border: `1px solid ${borderCol}`,
                  bgcolor: isDark ? '#1e293b' : '#ffffff',
                  '& .MuiMenuItem-root': {
                    fontSize: '0.8rem',
                    py: 1,
                    px: 2,
                    color: textPrimary,
                    '&:hover': {
                      bgcolor: isDark ? '#334155' : '#f1f5f9',
                    }
                  }
                }
              }
            }}
          >
            <MenuItem onClick={() => { handleMenuClose('summary'); handleClientExport('summary_report', summaryTable, 'csv'); }}>Export CSV</MenuItem>
            <MenuItem onClick={() => { handleMenuClose('summary'); handleClientExport('summary_report', summaryTable, 'pdf'); }}>Export PDF</MenuItem>
          </Menu>
        </Box>

        {/* Charts Grid */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
              <Typography variant="body2" fontWeight={700} color={textPrimary} mb={2.5}>
                Monthly GST Trend (Filing vs Credits)
              </Typography>
              <Box height={260} width="100%">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#334155' : '#f1f5f9'} />
                    <XAxis dataKey="label" stroke={textSecondary} fontSize={11} tickLine={false} />
                    <YAxis stroke={textSecondary} fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ fontSize: '0.8rem', border: `1px solid ${borderCol}`, borderRadius: '8px', background: primaryBg }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '0.75rem' }} />
                    <Line name="Output GST" type="monotone" dataKey="collected" stroke="#0F172A" strokeWidth={2} dot={{ r: 2 }} />
                    <Line name="Input GST" type="monotone" dataKey="input_credit" stroke="#94A3B8" strokeWidth={2} dot={{ r: 2 }} />
                    <Line name="Net Liability" type="monotone" dataKey="net_liability" stroke="#38bdf8" strokeWidth={2} dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none', height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Typography variant="body2" fontWeight={700} color={textPrimary} mb={2.5}>
                GST Component Composition Share
              </Typography>
              {donutData.length > 0 ? (
                <Box display="flex" flex={1} alignItems="center" justifyContent="center" flexDirection="column" gap={2}>
                  <Box width={140} height={140}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={donutData}
                          cx="50%"
                          cy="50%"
                          innerRadius={45}
                          outerRadius={65}
                          paddingAngle={3}
                          dataKey="value"
                        >
                          {donutData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(v) => `₹${fmt(v)}`} />
                      </PieChart>
                    </ResponsiveContainer>
                  </Box>
                  <Box display="flex" flexWrap="wrap" justifyContent="center" gap={1.5} mt={1}>
                    {donutData.map((item, idx) => (
                      <Box key={idx} display="flex" alignItems="center" gap={0.5}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: item.color }} />
                        <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: textPrimary }}>
                          {item.name}: ₹{fmt(item.value)}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              ) : (
                <Box display="flex" flex={1} alignItems="center" justifyContent="center">
                  <Typography variant="body2" color={textSecondary}>No composition data.</Typography>
                </Box>
              )}
            </Card>
          </Grid>
        </Grid>

        {/* Monthly GST Summary Table */}
        <Box>
          <Typography variant="body2" fontWeight={700} color={textPrimary} mb={2}>
            Monthly GST Summary Schedule
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Month</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Output GST (Collected)</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Input GST (Paid)</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Net Liability</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>Filing Returns</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.5, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>Filing Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {summaryTable.map((row, index) => (
                  <TableRow key={index} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontWeight: 600 }}>{row.month}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(row.collected)}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(row.input_credit)}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700, color: parseFloat(row.net_liability) >= 0 ? '#ef4444' : '#10b981' }}>
                      ₹{fmt(Math.abs(parseFloat(row.net_liability)))} {parseFloat(row.net_liability) < 0 && '(Surplus)'}
                    </TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                      {row.returns_filed?.length > 0 ? (
                        row.returns_filed.map((ret, i) => (
                          <Chip key={i} label={ret} size="small" variant="outlined" sx={{ height: 18, fontSize: '0.62rem', mr: 0.5, fontWeight: 700, borderRadius: '4px' }} />
                        ))
                      ) : (
                        <Typography sx={{ fontSize: '0.72rem', color: textSecondary, fontStyle: 'italic' }}>Pending</Typography>
                      )}
                    </TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                      <Box
                        sx={{
                          display: 'inline-block',
                          px: 1,
                          py: 0.25,
                          borderRadius: '4px',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          bgcolor: row.status === 'Filed' ? '#e6fbf4' : '#fef3c7',
                          color: row.status === 'Filed' ? '#10b981' : '#b45309',
                        }}
                      >
                        {row.status.toUpperCase()}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Box>
    );
  };

  const renderLiabilityPage = () => {
    if (liabilityLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (liabilityError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{liabilityError}</Alert>
      );
    }

    const metrics = liabilityData?.metrics || {};
    const breakdown = liabilityData?.breakdown || [];
    const trend = liabilityData?.trend || [];
    const alerts = liabilityData?.alerts || [];

    return (
      <Box display="flex" flexDirection="column" gap={3.5}>
        {/* KPIs */}
        <Grid container spacing={2.5}>
          {[
            { label: 'Total Output Liability', val: `₹${fmt(metrics.collected)}`, desc: 'Accrued sales tax collections' },
            { label: 'Input Credits Offset', val: `₹${fmt(metrics.credit)}`, desc: 'Available tax credits claimed' },
            { label: 'Net Payable Liability', val: `₹${fmt(metrics.net_liability)}`, desc: 'Net balance offset remaining' },
            { label: 'Pending Payment Due', val: `₹${fmt(metrics.pending_liability)}`, desc: 'Unsettled filing liability' },
          ].map((kpi, idx) => (
            <Grid item xs={12} sm={6} md={3} key={idx}>
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', fontSize: '0.68rem', letterSpacing: '0.04em' }}>
                    {kpi.label}
                  </Typography>
                  <Typography variant="h5" fontWeight={700} mt={0.75} mb={0.25} sx={{ fontFamily: '"SF Mono", monospace', letterSpacing: '-0.02em', fontSize: '1.45rem' }}>
                    {kpi.val}
                  </Typography>
                  <Typography sx={{ fontSize: '0.72rem', color: textSecondary }}>{kpi.desc}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Breakdown Table */}
        <Box>
          <Typography variant="body2" fontWeight={700} color={textPrimary} mb={2}>
            Liability Components Breakdown
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, py: 1.25, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Tax Component Type</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.25, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Collected (Output)</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.25, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Utilized Credit (Input)</TableCell>
                  <TableCell sx={{ fontWeight: 600, py: 1.25, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', textAlign: 'right' }}>Net Payable Amount</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {breakdown.map((row, i) => (
                  <TableRow key={i} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontWeight: 600 }}>{row.tax_type}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(row.collected)}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(row.credit)}</TableCell>
                    <TableCell sx={{ py: 1.25, borderBottom: '1px solid #E5E7EB', fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700, color: parseFloat(row.payable) > 0 ? '#ef4444' : '#10b981' }}>
                      ₹{fmt(Math.abs(parseFloat(row.payable)))} {parseFloat(row.payable) < 0 && '(Credit)'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        {/* Charts & Alerts Grid */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={7}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
              <Typography variant="body2" fontWeight={700} mb={2.5}>Net Payable Trend (Last 6 Months)</Typography>
              <Box height={220} width="100%">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#334155' : '#f1f5f9'} />
                    <XAxis dataKey="month" stroke={textSecondary} fontSize={11} tickLine={false} />
                    <YAxis stroke={textSecondary} fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ fontSize: '0.8rem', border: `1px solid ${borderCol}`, borderRadius: '8px', background: primaryBg }} />
                    <Line name="Net Payable (INR)" type="monotone" dataKey="payable" stroke="#0F172A" strokeWidth={2} dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </Card>
          </Grid>
          <Grid item xs={12} md={5}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none', height: '100%' }}>
              <Typography variant="body2" fontWeight={700} mb={2.5}>GST Liability Anomalies & Alerts</Typography>
              <Box display="flex" flexDirection="column" gap={1.5}>
                {alerts.map((alert, idx) => (
                  <Box
                    key={idx}
                    display="flex"
                    gap={1.25}
                    p={1.75}
                    borderRadius="8px"
                    sx={{
                      border: `1px solid ${borderCol}`,
                      borderLeft: '4px solid #f59e0b',
                      bgcolor: isDark ? 'rgba(255,255,255,0.01)' : '#f8fafc',
                    }}
                  >
                    <WarningIcon sx={{ color: '#f59e0b', fontSize: 16, mt: 0.25 }} />
                    <Typography variant="body2" sx={{ fontSize: '0.78rem', lineHeight: 1.4, color: textPrimary }}>
                      {alert}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Card>
          </Grid>
        </Grid>
      </Box>
    );
  };

  const renderGstr1Page = () => {
    if (gstr1Loading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (gstr1Error) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{gstr1Error}</Alert>
      );
    }

    const b2b = gstr1Data?.b2b || [];
    const b2cLarge = gstr1Data?.b2c_large || [];
    const b2cSmall = gstr1Data?.b2c_small || [];
    const exports = gstr1Data?.exports || [];
    const adjustments = gstr1Data?.adjustments || [];

    const activeRows =
      gstr1SubTab === 'b2b' ? b2b :
      gstr1SubTab === 'b2c_large' ? b2cLarge :
      gstr1SubTab === 'b2c_small' ? b2cSmall :
      gstr1SubTab === 'exports' ? exports : adjustments;

    const errorCount = b2b.filter(r => r.status === 'Error').length +
                       b2cLarge.filter(r => r.status === 'Error').length +
                       b2cSmall.filter(r => r.status === 'Error').length +
                       exports.filter(r => r.status === 'Error').length +
                       adjustments.filter(r => r.status === 'Error').length;

    return (
      <Box display="flex" flexDirection="column" gap={3}>
        {/* Status Card & Actions Bar */}
        <Box display="flex" flexWrap="wrap" justifyContent="space-between" alignItems="center" p={2.5} border={`1px solid ${borderCol}`} borderRadius="12px" bgcolor="#ffffff" gap={2}>
          <Box display="flex" alignItems="center" gap={3}>
            <Box>
              <Typography variant="caption" color={textSecondary} sx={{ textTransform: 'uppercase', fontWeight: 600 }}>Filing Period</Typography>
              <Typography variant="subtitle2" fontWeight={700} color={textPrimary}>{gstr1Data?.period || 'N/A'}</Typography>
            </Box>
            <Divider orientation="vertical" flexItem sx={{ borderColor: borderCol }} />
            <Box>
              <Typography variant="caption" color={textSecondary} sx={{ textTransform: 'uppercase', fontWeight: 600 }}>Validation Status</Typography>
              <Box display="flex" alignItems="center" gap={0.5} mt={0.25}>
                <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: errorCount > 0 ? '#ef4444' : '#10b981' }} />
                <Typography variant="subtitle2" fontWeight={700} sx={{ fontSize: '0.78rem', color: errorCount > 0 ? '#ef4444' : '#10b981' }}>
                  {errorCount > 0 ? `${errorCount} Issues Found` : 'Ready to File'}
                </Typography>
              </Box>
            </Box>
          </Box>
          <Box display="flex" gap={1.25}>
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                setGstr1Validated(true);
                setToast({ open: true, message: `Validation complete. ${errorCount} anomalies detected.`, severity: errorCount > 0 ? 'warning' : 'success' });
              }}
              sx={{
                textTransform: 'none',
                borderColor: borderCol,
                color: textPrimary,
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '0.8rem',
                height: 36,
                '&:hover': { borderColor: '#cbd5e1', bgcolor: '#f9fafb' },
              }}
            >
              Validate Return
            </Button>
            <Button
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={(e) => handleMenuOpen('gstr1', e)}
              sx={{
                textTransform: 'none',
                borderColor: borderCol,
                color: textPrimary,
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '0.8rem',
                height: 36,
                bgcolor: isDark ? '#111827' : '#ffffff',
                '&:hover': {
                  borderColor: isDark ? '#475569' : '#cbd5e1',
                  bgcolor: isDark ? '#1f2937' : '#f8fafc',
                }
              }}
            >
              Export
            </Button>
            <Menu
              anchorEl={anchorElMap['gstr1']}
              open={Boolean(anchorElMap['gstr1'])}
              onClose={() => handleMenuClose('gstr1')}
              slotProps={{
                paper: {
                  sx: {
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                    border: `1px solid ${borderCol}`,
                    bgcolor: isDark ? '#1e293b' : '#ffffff',
                    '& .MuiMenuItem-root': {
                      fontSize: '0.8rem',
                      py: 1,
                      px: 2,
                      color: textPrimary,
                      '&:hover': {
                        bgcolor: isDark ? '#334155' : '#f1f5f9',
                      }
                    }
                  }
                }
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose('gstr1');
                if (errorCount > 0) {
                  setToast({ open: true, message: 'Please fix validation errors before export.', severity: 'error' });
                  return;
                }
                setToast({ open: true, message: 'Excel Export started.', severity: 'success' });
                handleClientExport('gstr1_excel_export', activeRows);
              }}>Export CSV</MenuItem>
              <MenuItem onClick={() => {
                handleMenuClose('gstr1');
                setToast({ open: true, message: 'Generating GSTR-1 Draft PDF...', severity: 'info' });
                handleClientExport('gstr1_draft', activeRows, 'pdf_gstr1');
              }}>Export PDF</MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* Validation Engine Errors List */}
        {gstr1Validated && errorCount > 0 && (
          <Alert severity="warning" sx={{ borderRadius: '8px' }}>
            <Typography variant="subtitle2" fontWeight={700} mb={0.5}>Return Warnings & Formatting Anomalies Found</Typography>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.78rem' }}>
              <li>B2B Invoices: <strong>INVALID_GSTIN</strong> has invalid checksum format. Correct to avoid statutory rejection.</li>
              <li>B2B Invoices: <strong>INV-2026-1005</strong> has 0.00% tax mapped on a standard taxable line.</li>
            </ul>
          </Alert>
        )}

        {/* Navigation Categories */}
        <Box display="flex" borderBottom={`1px solid ${borderCol}`} gap={1}>
          {[
            { key: 'b2b', label: `B2B Invoices (${b2b.length})` },
            { key: 'b2c_large', label: `B2C Large (${b2cLarge.length})` },
            { key: 'b2c_small', label: `B2C Small (${b2cSmall.length})` },
            { key: 'exports', label: `Export Supplies (${exports.length})` },
            { key: 'adjustments', label: `Credit/Debit Notes (${adjustments.length})` },
          ].map((cat) => {
            const active = gstr1SubTab === cat.key;
            return (
              <Box
                key={cat.key}
                component="button"
                onClick={() => setGstr1SubTab(cat.key)}
                sx={{
                  py: 1,
                  px: 2,
                  border: 0,
                  borderBottom: `2px solid ${active ? '#0F172A' : 'transparent'}`,
                  bgcolor: 'transparent',
                  cursor: 'pointer',
                  fontWeight: active ? 700 : 500,
                  color: active ? textPrimary : textSecondary,
                  fontSize: '0.82rem',
                }}
              >
                {cat.label}
              </Box>
            );
          })}
        </Box>

        {/* Data Grid */}
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
          <Table size="medium">
            <TableHead>
              {gstr1SubTab === 'b2b' ? (
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Invoice Number</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Buyer GSTIN</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>Taxable Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>GST Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'center' }}>Errors</TableCell>
                </TableRow>
              ) : gstr1SubTab === 'b2c_small' ? (
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Place of Supply</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'center' }}>Tax Rate (%)</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>Taxable Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>GST Amt</TableCell>
                </TableRow>
              ) : gstr1SubTab === 'b2c_large' ? (
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Invoice Number</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Place of Supply</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>Taxable Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>GST Amt</TableCell>
                </TableRow>
              ) : gstr1SubTab === 'exports' ? (
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Invoice Number</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Shipping Bill #</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>Taxable Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>GST Amt</TableCell>
                </TableRow>
              ) : (
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Note Number</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Adjustment Type</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem' }}>Original Invoice</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>Taxable Amt</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', textAlign: 'right' }}>GST Amt</TableCell>
                </TableRow>
              )}
            </TableHead>
            <TableBody>
              {activeRows.length > 0 ? (
                activeRows.map((row) => {
                  const hasErr = row.status === 'Error';
                  return (
                    <TableRow key={row.id} hover sx={{ bgcolor: hasErr ? '#fee2e2' : 'transparent', '&:last-child td': { borderBottom: 0 } }}>
                      {gstr1SubTab === 'b2b' ? (
                        <>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.invoice_number}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontFamily: 'monospace' }}>{row.gstin}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right' }}>₹{fmt(row.taxable_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', fontWeight: 700 }}>₹{fmt(row.gst_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.72rem', textAlign: 'center', color: '#ef4444' }}>
                            {hasErr ? row.errors?.join(', ') : 'None'}
                          </TableCell>
                        </>
                      ) : gstr1SubTab === 'b2c_small' ? (
                        <>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.place_of_supply}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'center' }}>{row.gst_rate}%</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right' }}>₹{fmt(row.taxable_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', fontWeight: 700 }}>₹{fmt(row.gst_amount)}</TableCell>
                        </>
                      ) : gstr1SubTab === 'b2c_large' ? (
                        <>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.invoice_number}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem' }}>{row.place_of_supply}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right' }}>₹{fmt(row.taxable_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', fontWeight: 700 }}>₹{fmt(row.gst_amount)}</TableCell>
                        </>
                      ) : gstr1SubTab === 'exports' ? (
                        <>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.invoice_number}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontFamily: 'monospace' }}>{row.shipping_bill}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right' }}>₹{fmt(row.taxable_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', fontWeight: 700 }}>₹{fmt(row.gst_amount)}</TableCell>
                        </>
                      ) : (
                        <>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.note_number}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem' }}>{row.type}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.invoice_number}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', color: '#ef4444' }}>₹{fmt(row.taxable_amount)}</TableCell>
                          <TableCell sx={{ py: 1.25, fontSize: '0.8rem', textAlign: 'right', fontWeight: 700, color: '#ef4444' }}>₹{fmt(row.gst_amount)}</TableCell>
                        </>
                      )}
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6, color: textSecondary }}>
                    No outward supplies found for the selected filter period.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderGstr3bPage = () => {
    if (gstr3bLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (gstr3bError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{gstr3bError}</Alert>
      );
    }

    const data = gstr3bData || {};
    const kpis = data.kpis || {};
    const sectionA = data.section_a || {};
    const sectionB = data.section_b || {};
    const sectionC = data.section_c || {};
    const sectionD = data.section_d || {};

    return (
      <Box display="flex" flexDirection="column" gap={4}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', pb: 1, borderBottom: `1px solid ${borderCol}`, gap: 2, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', width: '100%' }}>
          <Box>
            <Typography variant="body2" fontWeight={600} color={textPrimary}>GSTR-3B Tax Liability Return Summary</Typography>
            <Typography variant="caption" color={textSecondary}>Review values computed directly from transaction registries.</Typography>
          </Box>
          <Box display="flex" gap={1}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={(e) => handleMenuOpen('gstr3b', e)}
              sx={{
                textTransform: 'none',
                borderColor: borderCol,
                color: textPrimary,
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '0.8rem',
                height: 32,
                bgcolor: isDark ? '#111827' : '#ffffff',
                '&:hover': {
                  borderColor: isDark ? '#475569' : '#cbd5e1',
                  bgcolor: isDark ? '#1f2937' : '#f8fafc',
                }
              }}
            >
              Export
            </Button>
            <Menu
              anchorEl={anchorElMap['gstr3b']}
              open={Boolean(anchorElMap['gstr3b'])}
              onClose={() => handleMenuClose('gstr3b')}
              slotProps={{
                paper: {
                  sx: {
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                    border: `1px solid ${borderCol}`,
                    bgcolor: isDark ? '#1e293b' : '#ffffff',
                    '& .MuiMenuItem-root': {
                      fontSize: '0.8rem',
                      py: 1,
                      px: 2,
                      color: textPrimary,
                      '&:hover': {
                        bgcolor: isDark ? '#334155' : '#f1f5f9',
                      }
                    }
                  }
                }
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose('gstr3b');
                setToast({ open: true, message: 'CSV Export started.', severity: 'success' });
                handleClientExport('gstr3b_csv', data);
              }}>Export CSV</MenuItem>
              <MenuItem onClick={() => {
                handleMenuClose('gstr3b');
                setToast({ open: true, message: 'Generating GSTR-3B Return PDF...', severity: 'info' });
                handleClientExport('gstr3b_return', data, 'pdf_gstr3b');
              }}>Export PDF</MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* KPIs */}
        <Grid container spacing={2.5}>
          {[
            { label: 'Taxable Outward Supplies', val: `₹${fmt(kpis.taxable_supplies)}` },
            { label: 'Zero-Rated Supplies', val: `₹${fmt(kpis.zero_rated_supplies)}` },
            { label: 'Exempt & Nil Outward', val: `₹${fmt(kpis.exempt_supplies)}` },
            { label: 'Net Payable Liability', val: `₹${fmt(kpis.net_liability)}` },
          ].map((kpi, idx) => (
            <Grid item xs={12} sm={6} md={3} key={idx}>
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', fontSize: '0.68rem', letterSpacing: '0.04em' }}>
                    {kpi.label}
                  </Typography>
                  <Typography variant="h6" fontWeight={700} mt={0.5} sx={{ fontFamily: '"SF Mono", monospace', fontSize: '1.2rem' }}>
                    {kpi.val}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Section A: Outward Supplies */}
        <Box>
          <Typography variant="subtitle2" fontWeight={700} color={textPrimary} mb={1.5}>
            3.1 Details of Outward Supplies and inward supplies liable to reverse charge
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25 }}>Supply Nature Category</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>Total Taxable Value</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>IGST (Integrated)</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>CGST (Central)</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>SGST (State)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(a) Outward taxable supplies (other than zero rated)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.taxable?.total_value)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.taxable?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.taxable?.cgst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.taxable?.sgst)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(b) Outward taxable supplies (zero rated)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.zero_rated?.total_value)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.zero_rated?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>—</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>—</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(c) Other outward supplies (Nil rated/exempted)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionA.other_nil?.total_value)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>—</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>—</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>—</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        {/* Section B: Eligible ITC */}
        <Box>
          <Typography variant="subtitle2" fontWeight={700} color={textPrimary} mb={1.5}>
            4. Details of Eligible Input Tax Credit (ITC)
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25 }}>ITC Credit Source</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>IGST</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>CGST</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>SGST</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(1) Import of goods</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.import_goods?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.import_goods?.cgst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.import_goods?.sgst)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(2) Inward supplies liable to reverse charge (RCM)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.rcm_inward?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.rcm_inward?.cgst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.rcm_inward?.sgst)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>(3) Inward supplies from ISD</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.isd_inward?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.isd_inward?.cgst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionB.isd_inward?.sgst)}</TableCell>
                </TableRow>
                <TableRow sx={{ fontWeight: 700 }}>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25, fontWeight: 700 }}>(4) All other ITC (Purchases & Expenses)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700 }}>₹{fmt(sectionB.other_itc?.igst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700 }}>₹{fmt(sectionB.other_itc?.cgst)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700 }}>₹{fmt(sectionB.other_itc?.sgst)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        {/* Section C: Exempt Supplies */}
        <Box>
          <Typography variant="subtitle2" fontWeight={700} color={textPrimary} mb={1.5}>
            5. Values of exempt, nil-rated and non-GST inward supplies
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25 }}>Inward Supply Nature</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>Inter-State Supplies</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>Intra-State Supplies</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>Composition scheme / Nil-rated / Exempt inward supplies</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionC.composition_nil?.inter_state)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionC.composition_nil?.intra_state)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>Non-GST inward supplies</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionC.non_gst?.inter_state)}</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right' }}>₹{fmt(sectionC.non_gst?.intra_state)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        {/* Section D: Net Tax Payable */}
        <Box>
          <Typography variant="subtitle2" fontWeight={700} color={textPrimary} mb={1.5}>
            Net GST Tax Liability Offsets
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: '#f9fafc' }}>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25 }}>Tax Component</TableCell>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.25, textAlign: 'right' }}>Net Payable Amount (Paid via Credit ledger)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>IGST (Integrated Tax)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700, color: parseFloat(sectionD.igst) >= 0 ? '#ef4444' : '#10b981' }}>
                    ₹{fmt(Math.abs(parseFloat(sectionD.igst || 0)))} {parseFloat(sectionD.igst) < 0 && '(Surplus Credit)'}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>CGST (Central Tax)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700, color: parseFloat(sectionD.cgst) >= 0 ? '#ef4444' : '#10b981' }}>
                    ₹{fmt(Math.abs(parseFloat(sectionD.cgst || 0)))} {parseFloat(sectionD.cgst) < 0 && '(Surplus Credit)'}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell sx={{ fontSize: '0.8rem', py: 1.25 }}>SGST (State Tax)</TableCell>
                  <TableCell sx={{ fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 700, color: parseFloat(sectionD.sgst) >= 0 ? '#ef4444' : '#10b981' }}>
                    ₹{fmt(Math.abs(parseFloat(sectionD.sgst || 0)))} {parseFloat(sectionD.sgst) < 0 && '(Surplus Credit)'}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Box>
    );
  };

  const renderItcPage = () => {
    if (itcLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (itcError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{itcError}</Alert>
      );
    }

    const kpis = itcData?.kpis || {};
    const statusCounts = itcData?.reconciliation_status || {};
    const records = itcData?.records || [];
    const health = itcData?.itc_health_score || 'Excellent';

    return (
      <Box display="flex" flexDirection="column" gap={3.5}>
        {/* KPI Cards Grid */}
        <Grid container spacing={2.5}>
          {[
            { label: 'Eligible ITC (Claimed)', val: `₹${fmt(kpis.eligible_itc)}`, color: '#10b981' },
            { label: 'Blocked ITC (Sect 17(5))', val: `₹${fmt(kpis.blocked_itc)}`, color: '#ef4444' },
            { label: 'Pending Vendor Filing', val: `₹${fmt(kpis.pending_itc)}`, color: '#f59e0b' },
            { label: 'Reversed ITC credit', val: `₹${fmt(kpis.reversed_itc)}`, color: '#64748b' },
          ].map((kpi, idx) => (
            <Grid item xs={12} sm={6} md={3} key={idx}>
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', fontSize: '0.68rem', letterSpacing: '0.04em' }}>
                    {kpi.label}
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color={kpi.color} mt={0.5} sx={{ fontFamily: '"SF Mono", monospace', fontSize: '1.25rem' }}>
                    {kpi.val}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Filters and Health Indicator */}
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Box p={2} border={`1px solid ${borderCol}`} borderRadius="12px" bgcolor="#ffffff" display="flex" flexWrap="wrap" gap={2} alignItems="center">
              <TextField
                size="small"
                placeholder="Search vendor name or GSTIN..."
                value={itcVendor}
                onChange={(e) => setItcVendor(e.target.value)}
                sx={{ ...inputStyle, minWidth: 220 }}
                slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 16, color: textSecondary }} /></InputAdornment> } }}
              />
              <FormControl size="small" sx={{ minWidth: 140, ...inputStyle }}>
                <InputLabel shrink>Eligibility</InputLabel>
                <Select value={itcEligibility} label="Eligibility" displayEmpty onChange={(e) => setItcEligibility(e.target.value)}>
                  <MenuItem value="">All Credits</MenuItem>
                  <MenuItem value="Eligible">Eligible Credits</MenuItem>
                  <MenuItem value="Blocked">Blocked Credits</MenuItem>
                  <MenuItem value="Pending">Pending Credits</MenuItem>
                </Select>
              </FormControl>
              <Box display="flex" gap={1} ml={1}>
                <Chip label={`Matched: ${statusCounts.matched}`} size="small" sx={{ bgcolor: '#e6fbf4', color: '#10b981', fontWeight: 600 }} />
                <Chip label={`Partially: ${statusCounts.partially_matched}`} size="small" sx={{ bgcolor: '#fef3c7', color: '#b45309', fontWeight: 600 }} />
                <Chip label={`Unmatched: ${statusCounts.not_matched}`} size="small" sx={{ bgcolor: '#fee2e2', color: '#ef4444', fontWeight: 600 }} />
              </Box>
              <Box flexGrow={1} />
              <Button
                variant="outlined"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={(e) => handleMenuOpen('itc', e)}
                sx={{
                  textTransform: 'none',
                  borderColor: borderCol,
                  color: textPrimary,
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '0.8rem',
                  height: 36,
                  bgcolor: isDark ? '#111827' : '#ffffff',
                  '&:hover': {
                    borderColor: isDark ? '#475569' : '#cbd5e1',
                    bgcolor: isDark ? '#1f2937' : '#f8fafc',
                  }
                }}
              >
                Export
              </Button>
              <Menu
                anchorEl={anchorElMap['itc']}
                open={Boolean(anchorElMap['itc'])}
                onClose={() => handleMenuClose('itc')}
                slotProps={{
                  paper: {
                    sx: {
                      borderRadius: '8px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                      border: `1px solid ${borderCol}`,
                      bgcolor: isDark ? '#1e293b' : '#ffffff',
                      '& .MuiMenuItem-root': {
                        fontSize: '0.8rem',
                        py: 1,
                        px: 2,
                        color: textPrimary,
                        '&:hover': {
                          bgcolor: isDark ? '#334155' : '#f1f5f9',
                        }
                      }
                    }
                  }
                }}
              >
                <MenuItem onClick={() => {
                  handleMenuClose('itc');
                  handleClientExport('itc_reconciliation_report', itcData?.records || []);
                }}>Export CSV</MenuItem>
                <MenuItem onClick={() => {
                  handleMenuClose('itc');
                  handleClientExport('itc_reconciliation_report', itcData, 'pdf_itc');
                }}>Export PDF</MenuItem>
              </Menu>
            </Box>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card variant="outlined" sx={{ p: 2, borderColor: borderCol, borderRadius: 3, boxShadow: 'none', bgcolor: '#f8fafc', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="caption" color={textSecondary} fontWeight={700}>GSTR-2B ITC Health Score</Typography>
                <Typography variant="subtitle1" fontWeight={700} color={health === 'Excellent' ? '#10b981' : '#f59e0b'}>{health}</Typography>
              </Box>
              <Chip label={health === 'Excellent' ? '98.5% Reconciled' : '84.0% Reconciled'} size="small" sx={{ bgcolor: '#0f172a', color: '#ffffff', fontWeight: 700 }} />
            </Card>
          </Grid>
        </Grid>

        {/* Records table */}
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
          <Table size="medium">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f9fafc' }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Supplier Vendor</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Vendor GSTIN</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Invoice Number</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'right' }}>GST Amount</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'center' }}>Eligibility</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'center' }}>Reconciliation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {records.length > 0 ? (
                records.map((row) => (
                  <TableRow key={row.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                    <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontWeight: 600 }}>{row.vendor}</TableCell>
                    <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontFamily: 'monospace' }}>{row.gstin}</TableCell>
                    <TableCell sx={{ py: 1.25, fontSize: '0.8rem' }}>{row.invoice}</TableCell>
                    <TableCell sx={{ py: 1.25, fontSize: '0.8rem', fontFamily: 'monospace', textAlign: 'right', fontWeight: 600 }}>₹{fmt(row.gst_amount)}</TableCell>
                    <TableCell sx={{ py: 1.25, textAlign: 'center' }}>
                      <Chip
                        label={row.eligibility}
                        size="small"
                        sx={{
                          height: 18,
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          borderRadius: '4px',
                          bgcolor: row.eligibility === 'Eligible' ? '#e6fbf4' : row.eligibility === 'Blocked' ? '#fee2e2' : '#fef3c7',
                          color: row.eligibility === 'Eligible' ? '#10b981' : row.eligibility === 'Blocked' ? '#ef4444' : '#b45309',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ py: 1.25, textAlign: 'center' }}>
                      <Box
                        sx={{
                          display: 'inline-block',
                          px: 1,
                          py: 0.25,
                          borderRadius: '4px',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          bgcolor: row.status === 'Matched' ? '#e6fbf4' : row.status === 'Partially Matched' ? '#fef3c7' : '#fee2e2',
                          color: row.status === 'Matched' ? '#10b981' : row.status === 'Partially Matched' ? '#b45309' : '#ef4444',
                        }}
                      >
                        {row.status.toUpperCase()}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6, color: textSecondary }}>
                    No input tax credit records found for the selected query.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderCalendarPage = () => {
    if (calendarLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (calendarError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{calendarError}</Alert>
      );
    }

    const deadlines = calendarData?.deadlines || [];

    return (
      <Box display="flex" flexDirection="column" gap={3.5}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1, borderBottom: `1px solid ${borderCol}`, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', width: '100%' }}>
          <Typography variant="body2" fontWeight={700}>Statutory GST Filing Calendar</Typography>
          <Box display="flex" gap={1.5} alignItems="center">
            <Chip label="Indian Jurisdiction Calendar FY 2026-27" size="small" variant="outlined" sx={{ fontWeight: 700 }} />
            <Button
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={(e) => handleMenuOpen('calendar', e)}
              sx={{
                textTransform: 'none',
                borderColor: borderCol,
                color: textPrimary,
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '0.75rem',
                height: 28,
                bgcolor: isDark ? '#111827' : '#ffffff',
                '&:hover': {
                  borderColor: isDark ? '#475569' : '#cbd5e1',
                  bgcolor: isDark ? '#1f2937' : '#f8fafc',
                }
              }}
            >
              Export
            </Button>
            <Menu
              anchorEl={anchorElMap['calendar']}
              open={Boolean(anchorElMap['calendar'])}
              onClose={() => handleMenuClose('calendar')}
              slotProps={{
                paper: {
                  sx: {
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                    border: `1px solid ${borderCol}`,
                    bgcolor: isDark ? '#1e293b' : '#ffffff',
                    '& .MuiMenuItem-root': {
                      fontSize: '0.8rem',
                      py: 1,
                      px: 2,
                      color: textPrimary,
                      '&:hover': {
                        bgcolor: isDark ? '#334155' : '#f1f5f9',
                      }
                    }
                  }
                }
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose('calendar');
                handleClientExport('compliance_calendar', calendarData?.deadlines || []);
              }}>Export CSV</MenuItem>
              <MenuItem onClick={() => {
                handleMenuClose('calendar');
                handleClientExport('compliance_calendar', calendarData, 'pdf_calendar');
              }}>Export PDF</MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* Deadlines Table */}
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
          <Table size="medium">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f9fafc' }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Filing Return Type</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Due Date Deadline</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'center' }}>Days Remaining</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'center' }}>Compliance Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {deadlines.map((row) => (
                <TableRow key={row.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontWeight: 600 }}>{row.return_type}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontFamily: 'monospace' }}>{row.due_date}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', textAlign: 'center', fontWeight: 700, color: row.days_remaining <= 3 ? '#ef4444' : '#10b981' }}>
                    {row.days_remaining} Days
                  </TableCell>
                  <TableCell sx={{ py: 1.5, textAlign: 'center' }}>
                    <Box
                      sx={{
                        display: 'inline-block',
                        px: 1,
                        py: 0.25,
                        borderRadius: '4px',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        bgcolor: row.status === 'Action Required' ? '#fee2e2' : '#e6fbf4',
                        color: row.status === 'Action Required' ? '#ef4444' : '#10b981',
                      }}
                    >
                      {row.status.toUpperCase()}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Reminder settings config */}
        <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
          <Typography variant="body2" fontWeight={700} mb={1.5}>Compliance Alerts Configuration</Typography>
          <Typography variant="caption" color={textSecondary} display="block" mb={2}>Configure automatic alerts before return deadlines.</Typography>
          <Grid container spacing={2}>
            {[
              { label: 'Notify 30 Days Prior', desc: 'Pre-filing checks alert', key: 'notify_30' },
              { label: 'Notify 15 Days Prior', desc: 'Invoice reconciliation alert', key: 'notify_15' },
              { label: 'Notify 7 Days Prior', desc: 'Validation trigger reminder', key: 'notify_7' },
              { label: 'Notify 3 Days Prior', desc: 'High priority alert warning', key: 'notify_3' },
              { label: 'Notify Due Today', desc: 'Critical alerts', key: 'notify_due' }
            ].map((rule, idx) => {
              const active = complianceAlerts[rule.key];
              return (
                <Grid item xs={12} md={2.4} key={idx}>
                  <Box p={1.5} border={`1px solid ${borderCol}`} borderRadius="8px" display="flex" flexDirection="column" gap={0.5} sx={{ bgcolor: isDark ? 'transparent' : '#f8fafc' }}>
                    <Typography variant="caption" fontWeight={700} color={textPrimary}>{rule.label}</Typography>
                    <Typography sx={{ fontSize: '0.68rem', color: textSecondary }}>{rule.desc}</Typography>
                    <Box 
                      component="button"
                      onClick={() => setComplianceAlerts(prev => ({ ...prev, [rule.key]: !prev[rule.key] }))}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mt: 1.5,
                        border: `1px solid ${borderCol}`,
                        borderRadius: '6px',
                        px: 1,
                        py: 0.5,
                        cursor: 'pointer',
                        bgcolor: active ? (isDark ? '#064e3b' : '#f0fdf4') : (isDark ? '#1e293b' : '#f1f5f9'),
                        color: active ? '#10b981' : textSecondary,
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        width: 'fit-content',
                        transition: 'all 0.15s ease',
                        '&:hover': {
                          bgcolor: active ? (isDark ? '#065f46' : '#dcfce7') : (isDark ? '#334155' : '#e2e8f0'),
                          borderColor: active ? '#10b981' : borderCol,
                        }
                      }}
                    >
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: active ? '#10b981' : '#64748b' }} />
                      <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: 'inherit' }}>
                        {active ? 'Enabled' : 'Disabled'}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
              );
            })}
          </Grid>
        </Card>
      </Box>
    );
  };

  const renderHistoryPage = () => {
    if (historyLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (historyError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{historyError}</Alert>
      );
    }

    return (
      <Box display="flex" flexDirection="column" gap={3}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1, borderBottom: `1px solid ${borderCol}`, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', width: '100%' }}>
          <Box>
            <Typography variant="body2" fontWeight={700}>GST Statutory Filing History</Typography>
            <Typography variant="caption" color={textSecondary}>Audits logs of filed GSTR returns and acknowledgment records.</Typography>
          </Box>
          <Box display="flex" gap={1.5} alignItems="center">
            <Button
              variant="outlined"
              size="small"
              startIcon={<DownloadIcon />}
              onClick={(e) => handleMenuOpen('history', e)}
              sx={{
                textTransform: 'none',
                borderColor: borderCol,
                color: textPrimary,
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '0.75rem',
                height: 32,
                bgcolor: isDark ? '#111827' : '#ffffff',
                '&:hover': {
                  borderColor: isDark ? '#475569' : '#cbd5e1',
                  bgcolor: isDark ? '#1f2937' : '#f8fafc',
                }
              }}
            >
              Export
            </Button>
            <Menu
              anchorEl={anchorElMap['history']}
              open={Boolean(anchorElMap['history'])}
              onClose={() => handleMenuClose('history')}
              slotProps={{
                paper: {
                  sx: {
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                    border: `1px solid ${borderCol}`,
                    bgcolor: isDark ? '#1e293b' : '#ffffff',
                    '& .MuiMenuItem-root': {
                      fontSize: '0.8rem',
                      py: 1,
                      px: 2,
                      color: textPrimary,
                      '&:hover': {
                        bgcolor: isDark ? '#334155' : '#f1f5f9',
                      }
                    }
                  }
                }
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose('history');
                handleClientExport('filing_history', historyData);
              }}>Export CSV</MenuItem>
              <MenuItem onClick={() => {
                handleMenuClose('history');
                handleClientExport('filing_history', historyData, 'pdf_history');
              }}>Export PDF</MenuItem>
            </Menu>
          </Box>
        </Box>

        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
          <Table size="medium">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f9fafc' }}>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Filing Return Type</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Filing Period</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Filed Date</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Acknowledgement Token #</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5 }}>Filed By User</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'center' }}>Filing Status</TableCell>
                <TableCell sx={{ fontWeight: 600, fontSize: '0.75rem', py: 1.5, textAlign: 'right' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {historyData.map((row) => (
                <TableRow key={row.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontWeight: 600 }}>{row.return_type}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontWeight: 600 }}>{row.period}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontFamily: 'monospace' }}>{row.filed_date}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem', fontFamily: 'monospace', color: textSecondary }}>{row.acknowledgement_number}</TableCell>
                  <TableCell sx={{ py: 1.5, fontSize: '0.8rem' }}>{row.filed_by}</TableCell>
                  <TableCell sx={{ py: 1.5, textAlign: 'center' }}>
                    <Chip label="Filed Successfully" size="small" sx={{ bgcolor: '#e6fbf4', color: '#10b981', fontWeight: 700, height: 18, fontSize: '0.62rem' }} />
                  </TableCell>
                  <TableCell sx={{ py: 1.5, textAlign: 'right' }}>
                    <Button
                      size="small"
                      onClick={() => {
                        setToast({ open: true, message: `Generating Receipt...`, severity: 'info' });
                        handleClientExport(`receipt_${row.acknowledgement_number}`, row, 'pdf_receipt');
                      }}
                      sx={{ textTransform: 'none', fontSize: '0.7rem', fontWeight: 600, p: 0.25 }}
                    >
                      Print Receipt
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderHealthPage = () => {
    if (healthLoading) {
      return (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={24} sx={{ color: '#0F172A' }} />
        </Box>
      );
    }
    if (healthError) {
      return (
        <Alert severity="error" sx={{ borderRadius: '8px' }}>{healthError}</Alert>
      );
    }

    const metrics = healthData?.metrics || {};
    const indicators = healthData?.indicators || {};
    const riskLog = healthData?.risk_log || [];

    return (
      <Box display="flex" flexDirection="column" gap={3.5}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1, borderBottom: `1px solid ${borderCol}`, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', width: '100%' }}>
          <Box>
            <Typography variant="body2" fontWeight={700}>GST Executive Compliance & Health Audit</Typography>
            <Typography variant="caption" color={textSecondary}>Audit risk scanning engine metrics & findings.</Typography>
          </Box>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={(e) => handleMenuOpen('health', e)}
            sx={{
              textTransform: 'none',
              borderColor: borderCol,
              color: textPrimary,
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.75rem',
              height: 32,
              bgcolor: isDark ? '#111827' : '#ffffff',
              '&:hover': {
                borderColor: isDark ? '#475569' : '#cbd5e1',
                bgcolor: isDark ? '#1f2937' : '#f8fafc',
              }
            }}
          >
            Export
          </Button>
          <Menu
            anchorEl={anchorElMap['health']}
            open={Boolean(anchorElMap['health'])}
            onClose={() => handleMenuClose('health')}
            slotProps={{
              paper: {
                sx: {
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                  border: `1px solid ${borderCol}`,
                  bgcolor: isDark ? '#1e293b' : '#ffffff',
                  '& .MuiMenuItem-root': {
                    fontSize: '0.8rem',
                    py: 1,
                    px: 2,
                    color: textPrimary,
                    '&:hover': {
                      bgcolor: isDark ? '#334155' : '#f1f5f9',
                    }
                  }
                }
              }
            }}
          >
            <MenuItem onClick={() => {
              handleMenuClose('health');
              handleClientExport('gst_health_report', healthData?.risk_log || []);
            }}>Export CSV</MenuItem>
            <MenuItem onClick={() => {
              handleMenuClose('health');
              handleClientExport('gst_health_report', healthData, 'pdf_health');
            }}>Export PDF</MenuItem>
          </Menu>
        </Box>

        {/* KPI Cards Grid */}
        <Grid container spacing={2.5}>
          {[
            { label: 'Filing Compliance %', val: `${metrics.filing_compliance}%`, status: 'Excellent', color: '#10b981' },
            { label: 'ITC Utilization Rate', val: `${metrics.itc_utilization}%`, status: 'Balanced', color: '#10b981' },
            { label: 'Return Accuracy Score', val: `${metrics.return_accuracy}%`, status: 'High Accuracy', color: '#10b981' },
            { label: 'GST Risk Audit Score', val: `${metrics.gst_risk_score}/100`, status: 'Low Risk', color: '#ef4444' },
          ].map((kpi, idx) => (
            <Grid item xs={12} sm={6} md={3} key={idx}>
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', fontSize: '0.68rem', letterSpacing: '0.04em' }}>
                    {kpi.label}
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color={textPrimary} mt={0.5}>
                    {kpi.val}
                  </Typography>
                  <Box display="flex" alignItems="center" gap={0.5} mt={0.5}>
                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: kpi.color }} />
                    <Typography variant="caption" color={textSecondary}>{kpi.status}</Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Health Meters Grid */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none' }}>
              <Typography variant="body2" fontWeight={700} mb={2.5}>Filing & Reconciliations health parameters</Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                {[
                  { label: 'Filing Health Status', val: indicators.filing_health, p: 100, color: '#10b981' },
                  { label: 'Input Tax Credit matching accuracy', val: indicators.itc_health, p: 92, color: '#10b981' },
                  { label: 'Filing details return accuracy', val: indicators.reconciliation_accuracy, p: 98, color: '#10b981' },
                  { label: 'Total GST compliance readiness', val: indicators.compliance_readiness, p: 100, color: '#10b981' },
                ].map((meter, i) => (
                  <Box key={i}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.75}>
                      <Typography sx={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 500 }}>{meter.label}</Typography>
                      <Typography sx={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700 }}>{meter.val} ({meter.p}%)</Typography>
                    </Box>
                    <Box sx={{ width: '100%', height: 6, bgcolor: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                      <Box sx={{ width: `${meter.p}%`, height: '100%', bgcolor: meter.color }} />
                    </Box>
                  </Box>
                ))}
              </Box>
            </Card>
          </Grid>

          {/* Risk logs list */}
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ p: 2.5, borderColor: borderCol, borderRadius: 3, boxShadow: 'none', height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Typography variant="body2" fontWeight={700} mb={2}>Active Risk Detection & Anomaly Log</Typography>
              <Box display="flex" flexDirection="column" gap={1.5} flex={1} overflowY="auto" maxHeight={250}>
                {riskLog.map((log) => (
                  <Box
                    key={log.id}
                    p={1.5}
                    border={`1px solid ${borderCol}`}
                    borderRadius="8px"
                    display="flex"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    sx={{ bgcolor: log.severity === 'High' ? '#fee2e2' : log.severity === 'Medium' ? '#fef3c7' : '#f8fafc' }}
                  >
                    <Box pr={2}>
                      <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>
                        {log.type}
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: textSecondary, mt: 0.5, lineHeight: 1.3 }}>
                        {log.details}
                      </Typography>
                    </Box>
                    <Chip
                      label={`${log.severity} Risk`}
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: '0.6rem',
                        fontWeight: 700,
                        bgcolor: log.severity === 'High' ? '#ef4444' : log.severity === 'Medium' ? '#f59e0b' : '#64748b',
                        color: '#ffffff',
                      }}
                    />
                  </Box>
                ))}
              </Box>
            </Card>
          </Grid>
        </Grid>
      </Box>
    );
  };

  const handleClientExport = (reportName, dataRows, type = 'csv') => {
    if (!canExport) {
      setToast({ open: true, message: 'You do not have permission to export GST reports.', severity: 'warning' });
      return;
    }
    try {
      if (type === 'csv') {
        let content = '';
        let mimeType = 'text/csv';
        let extension = 'csv';

        if (Array.isArray(dataRows)) {
          const keys = Object.keys(dataRows[0] || {});
          const header = keys.join(',') + '\n';
          const body = dataRows.map(row => keys.map(k => {
            let val = row[k];
            if (typeof val === 'string' && val.includes(',')) {
              val = `"${val}"`;
            }
            return val;
          }).join(',')).join('\n');
          content = header + body;
        } else {
          content = Object.entries(dataRows).map(([k, v]) => `${k},${typeof v === 'object' ? JSON.stringify(v) : v}`).join('\n');
        }

        const blob = new Blob([content], { type: mimeType });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `shori_gst_${reportName}_${new Date().toISOString().split('T')[0]}.${extension}`;
        a.click();
        window.URL.revokeObjectURL(url);
        setToast({ open: true, message: 'Report exported successfully as CSV.', severity: 'success' });
        return;
      }

      // PDF Generation Engine
      const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 40;

      const drawHeader = (title, subtitle) => {
        // Top solid bar
        doc.setFillColor(15, 23, 42);
        doc.rect(0, 0, pageWidth, 8, 'F');

        // Corporate Identity
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(16);
        doc.setTextColor(15, 23, 42);
        doc.text('SHORI', margin, 35);

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8.5);
        doc.setTextColor(100, 116, 139);
        doc.text('GST COMPLIANCE & RETURNS CENTER', margin, 48);

        // Right-aligned report name
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(12);
        doc.setTextColor(15, 23, 42);
        doc.text(title.toUpperCase(), pageWidth - margin, 35, { align: 'right' });

        if (subtitle) {
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(8.5);
          doc.setTextColor(71, 85, 105);
          doc.text(subtitle, pageWidth - margin, 48, { align: 'right' });
        }

        // Horizontal divider line
        doc.setDrawColor(229, 231, 235);
        doc.setLineWidth(1);
        doc.line(margin, 58, pageWidth - margin, 58);
      };

      const drawMetadataBlock = (yStart, metaList) => {
        const colWidth = (pageWidth - (margin * 2)) / 2;

        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(15, 23, 42);
        doc.text('BUSINESS & REPORT METADATA', margin, yStart);
        let y = yStart + 15;

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8);

        for (let i = 0; i < metaList.length; i += 2) {
          const item1 = metaList[i];
          const item2 = metaList[i+1];

          // Column 1
          doc.setTextColor(100, 116, 139);
          doc.text(`${item1.label}:`, margin + 10, y);
          doc.setTextColor(30, 41, 59);
          doc.setFont('helvetica', 'bold');
          doc.text(String(item1.value || 'N/A'), margin + 120, y);
          doc.setFont('helvetica', 'normal');

          // Column 2
          if (item2) {
            doc.setTextColor(100, 116, 139);
            doc.text(`${item2.label}:`, margin + colWidth + 10, y);
            doc.setTextColor(30, 41, 59);
            doc.setFont('helvetica', 'bold');
            doc.text(String(item2.value || 'N/A'), margin + colWidth + 120, y);
            doc.setFont('helvetica', 'normal');
          }

          y += 14;
        }

        // Subline border
        doc.setDrawColor(241, 245, 249);
        doc.line(margin, y, pageWidth - margin, y);

        return y + 15;
      };

      const drawKPICards = (yStart, kpis) => {
        const boxCount = kpis.length;
        const availableWidth = pageWidth - (margin * 2);
        const boxWidth = availableWidth / boxCount;
        const boxHeight = 40;

        doc.setFillColor(248, 250, 252);
        doc.setDrawColor(229, 231, 235);
        doc.rect(margin, yStart, availableWidth, boxHeight, 'FD');

        kpis.forEach((kpi, idx) => {
          const xPos = margin + (idx * boxWidth);

          // Card labels
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7);
          doc.setTextColor(100, 116, 139);
          doc.text(kpi.label.toUpperCase(), xPos + 10, yStart + 15);

          // Card value
          doc.setFont('helvetica', 'bold');
          doc.setFontSize(10);
          doc.setTextColor(15, 23, 42);
          doc.text(String(kpi.value), xPos + 10, yStart + 30);

          // Separators
          if (idx < boxCount - 1) {
            doc.setDrawColor(229, 231, 235);
            doc.line(xPos + boxWidth, yStart, xPos + boxWidth, yStart + boxHeight);
          }
        });

        return yStart + boxHeight + 18;
      };

      const ensureSpace = (y, requiredHeight, title, subtitle) => {
        if (y + requiredHeight > pageHeight - 60) {
          doc.addPage();
          drawHeader(title, subtitle);
          return 80;
        }
        return y;
      };

      const drawFooters = () => {
        const totalPages = doc.internal.getNumberOfPages();
        for (let i = 1; i <= totalPages; i++) {
          doc.setPage(i);
          doc.setDrawColor(229, 231, 235);
          doc.setLineWidth(0.5);
          doc.line(margin, pageHeight - 45, pageWidth - margin, pageHeight - 45);

          doc.setFont('helvetica', 'normal');
          doc.setFontSize(7.5);
          doc.setTextColor(148, 163, 184);
          doc.text('GENERATED BY SHORI GST PORTAL - SECURE STATUTORY REPORT', margin, pageHeight - 30);
          doc.text(`Page ${i} of ${totalPages}`, pageWidth - margin, pageHeight - 30, { align: 'right' });
        }
      };

      const runAutoTable = (startY, headers, body, columnStyles = {}) => {
        const options = {
          startY: startY,
          head: [headers],
          body: body,
          theme: 'grid',
          headStyles: {
            fillColor: [15, 23, 42],
            textColor: [255, 255, 255],
            fontStyle: 'bold',
            fontSize: 8,
            valign: 'middle'
          },
          bodyStyles: {
            textColor: [30, 41, 59],
            fontSize: 7.5,
            valign: 'middle'
          },
          alternateRowStyles: {
            fillColor: [248, 250, 252]
          },
          columnStyles: columnStyles,
          margin: { left: margin, right: margin, top: 80, bottom: 60 },
          styles: {
            overflow: 'linebreak',
            cellPadding: 5,
            lineColor: [229, 231, 235],
            lineWidth: 0.5
          }
        };

        if (typeof doc.autoTable === 'function') {
          doc.autoTable(options);
        } else {
          autoTable(doc, options);
        }
        return doc.lastAutoTable.finalY;
      };

      let currentY = 80;
      let filename = `shori_gst_${reportName}_${new Date().toISOString().split('T')[0]}.pdf`;

      // Report dispatcher
      if (type === 'pdf_ledger') {
        const title = 'GST Audit Trail & Transactions Ledger';
        const subtitle = `Report Generated on ${new Date().toLocaleDateString('en-IN')}`;
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Company Legal Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Registered GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Search Filter Query', value: txnSearch || 'No Active Search' },
          { label: 'Transaction Type Filter', value: txnType || 'All Types' },
          { label: 'Filing Status Filter', value: txnStatus || 'All Statuses' },
          { label: 'Total Exported Rows', value: String(dataRows.length) }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('AUDITED GST LEDGER LINES', margin, currentY);
        currentY += 12;

        const headers = ['Date', 'Reference #', 'Type', 'Taxable Amt', 'GST Rate', 'GST Amt', 'Tax Type', 'Status'];
        const body = dataRows.map(row => [
          new Date(row.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' }),
          row.reference_number || row.transaction_id,
          row.transaction_type?.toUpperCase(),
          `INR ${fmt(row.taxable_amount)}`,
          `${Number(row.gst_rate)}%`,
          `INR ${fmt(row.gst_amount)}`,
          row.gst_type?.toUpperCase(),
          row.status?.toUpperCase()
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          3: { halign: 'right' },
          4: { halign: 'center' },
          5: { halign: 'right' },
          6: { halign: 'center' },
          7: { halign: 'center' }
        });
      }

      else if (type === 'pdf') {
        const title = 'GST Compliance Summary Report';
        const subtitle = `Financial Year ${filterFY}`;
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Company Trade Name', value: settings.trade_name || 'Shori Business' },
          { label: 'Registered Legal Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Business GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Selected Month', value: filterMonth ? new Date(0, parseInt(filterMonth) - 1).toLocaleString('default', { month: 'long' }) : 'All' },
          { label: 'Filing State', value: settings.state || 'Not Configured' },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        const kpiCollected = summaryData?.metrics?.collected || 0;
        const kpiPaid = summaryData?.metrics?.paid || 0;
        const kpiNet = summaryData?.metrics?.net_liability || 0;
        const kpis = [
          { label: 'GST Output (Collected)', value: `INR ${fmt(kpiCollected)}` },
          { label: 'GST Input (Paid Credit)', value: `INR ${fmt(kpiPaid)}` },
          { label: 'Net Payable Liability', value: `INR ${fmt(Math.abs(kpiNet))} ${kpiNet < 0 ? '(Surplus)' : ''}` }
        ];
        currentY = drawKPICards(currentY, kpis);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('MONTHLY GST COMPLIANCE SCHEDULE', margin, currentY);
        currentY += 12;

        const headers = ['Month', 'Output GST (Collected)', 'Input GST (Paid)', 'Net Liability', 'Filing Form', 'Filing Status'];
        const body = (summaryData?.summary_table || []).map(row => [
          row.month,
          `INR ${fmt(row.collected)}`,
          `INR ${fmt(row.input_credit)}`,
          `INR ${fmt(Math.abs(row.net_liability))} ${parseFloat(row.net_liability) < 0 ? '(Surplus)' : ''}`,
          row.returns_filed?.join(', ') || 'Pending',
          row.status.toUpperCase()
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          1: { halign: 'right' },
          2: { halign: 'right' },
          3: { halign: 'right' },
          4: { halign: 'center' },
          5: { halign: 'center' }
        });
      }

      else if (type === 'pdf_gstr1') {
        const title = 'GSTR-1 Outward Supplies Draft Return';
        const subtitle = `Filing Period: ${gstr1Data?.period || 'N/A'}`;
        drawHeader(title, subtitle);

        const b2b = gstr1Data?.b2b || [];
        const b2cLarge = gstr1Data?.b2c_large || [];
        const b2cSmall = gstr1Data?.b2c_small || [];
        const exports = gstr1Data?.exports || [];
        const adjustments = gstr1Data?.adjustments || [];

        const meta = [
          { label: 'Filer Legal Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Business GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Filing Cycle Period', value: gstr1Data?.period || 'N/A' },
          { label: 'Total Active Records', value: String(b2b.length + b2cLarge.length + b2cSmall.length + exports.length + adjustments.length) },
          { label: 'Validation Anomalies', value: String(b2b.filter(r => r.status === 'Error').length + b2cLarge.filter(r => r.status === 'Error').length + b2cSmall.filter(r => r.status === 'Error').length) },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        const kpis = [
          { label: 'B2B Invoices', value: String(b2b.length) },
          { label: 'B2C Small Supplies', value: String(b2cSmall.length) },
          { label: 'B2C Large Invoices', value: String(b2cLarge.length) },
          { label: 'Export Supplies', value: String(exports.length) }
        ];
        currentY = drawKPICards(currentY, kpis);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text(`DETAILED SECTION: ${gstr1SubTab.toUpperCase()} INVOICES`, margin, currentY);
        currentY += 12;

        let headers = [];
        let body = [];
        let colStyles = {};

        if (gstr1SubTab === 'b2b') {
          headers = ['Invoice Number', 'Buyer GSTIN', 'Taxable Amount', 'GST Amount', 'Validation/Errors'];
          body = b2b.map(row => [
            row.invoice_number,
            row.gstin,
            `INR ${fmt(row.taxable_amount)}`,
            `INR ${fmt(row.gst_amount)}`,
            row.status === 'Error' ? row.errors?.join(', ') : 'None (Validated)'
          ]);
          colStyles = { 2: { halign: 'right' }, 3: { halign: 'right' } };
        } else if (gstr1SubTab === 'b2c_small') {
          headers = ['Place of Supply', 'Tax Rate (%)', 'Taxable Amount', 'GST Amount'];
          body = b2cSmall.map(row => [
            row.place_of_supply,
            `${row.gst_rate}%`,
            `INR ${fmt(row.taxable_amount)}`,
            `INR ${fmt(row.gst_amount)}`
          ]);
          colStyles = { 1: { halign: 'center' }, 2: { halign: 'right' }, 3: { halign: 'right' } };
        } else if (gstr1SubTab === 'b2c_large') {
          headers = ['Invoice Number', 'Place of Supply', 'Taxable Amount', 'GST Amount'];
          body = b2cLarge.map(row => [
            row.invoice_number,
            row.place_of_supply,
            `INR ${fmt(row.taxable_amount)}`,
            `INR ${fmt(row.gst_amount)}`
          ]);
          colStyles = { 2: { halign: 'right' }, 3: { halign: 'right' } };
        } else if (gstr1SubTab === 'exports') {
          headers = ['Invoice Number', 'Shipping Bill Number', 'Taxable Amount', 'GST Amount'];
          body = exports.map(row => [
            row.invoice_number,
            row.shipping_bill || '—',
            `INR ${fmt(row.taxable_amount)}`,
            `INR ${fmt(row.gst_amount)}`
          ]);
          colStyles = { 2: { halign: 'right' }, 3: { halign: 'right' } };
        } else {
          headers = ['Note Number', 'Adjustment Type', 'Original Invoice', 'Taxable Amount', 'GST Amount'];
          body = adjustments.map(row => [
            row.note_number,
            row.type,
            row.invoice_number,
            `INR ${fmt(row.taxable_amount)}`,
            `INR ${fmt(row.gst_amount)}`
          ]);
          colStyles = { 3: { halign: 'right' }, 4: { halign: 'right' } };
        }

        currentY = runAutoTable(currentY, headers, body, colStyles);
      }

      else if (type === 'pdf_gstr3b') {
        const title = 'GSTR-3B Self-Assessed Return Summary';
        const subtitle = `Filing Period: Month ${filterMonth}, FY ${filterFY}`;
        drawHeader(title, subtitle);

        const data = gstr3bData || {};
        const kpis = data.kpis || {};
        const sectionA = data.section_a || {};
        const sectionB = data.section_b || {};
        const sectionC = data.section_c || {};
        const sectionD = data.section_d || {};

        const meta = [
          { label: 'Company Legal Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Registered GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Filing Frequency', value: settings.filing_frequency || 'monthly' },
          { label: 'Jurisdiction Code', value: settings.state_code || 'Not Configured' },
          { label: 'Verification Method', value: 'DSC/EVC Authorized' },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        const kpisList = [
          { label: 'Taxable Outward', value: `INR ${fmt(kpis.taxable_supplies)}` },
          { label: 'Zero-Rated Supplies', value: `INR ${fmt(kpis.zero_rated_supplies)}` },
          { label: 'Exempt Inward', value: `INR ${fmt(kpis.exempt_supplies)}` },
          { label: 'Net Payable Tax', value: `INR ${fmt(kpis.net_liability)}` }
        ];
        currentY = drawKPICards(currentY, kpisList);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(15, 23, 42);
        doc.text('3.1 Details of Outward Supplies & Inward Supplies Liable to Reverse Charge (RCM)', margin, currentY);
        currentY += 10;

        let headers = ['Nature of Supply', 'Total Taxable Value', 'IGST (Integrated)', 'CGST (Central)', 'SGST (State)'];
        let body = [
          [
            '(a) Outward taxable supplies (other B2B/B2C)',
            `INR ${fmt(sectionA.taxable?.total_value)}`,
            `INR ${fmt(sectionA.taxable?.igst)}`,
            `INR ${fmt(sectionA.taxable?.cgst)}`,
            `INR ${fmt(sectionA.taxable?.sgst)}`
          ],
          [
            '(b) Outward taxable supplies (Zero Rated)',
            `INR ${fmt(sectionA.zero_rated?.total_value)}`,
            `INR ${fmt(sectionA.zero_rated?.igst)}`,
            '—',
            '—'
          ],
          [
            '(c) Other outward supplies (Nil/Exempt)',
            `INR ${fmt(sectionA.other_nil?.total_value)}`,
            '—',
            '—',
            '—'
          ]
        ];
        currentY = runAutoTable(currentY, headers, body, {
          1: { halign: 'right' },
          2: { halign: 'right' },
          3: { halign: 'right' },
          4: { halign: 'right' }
        }) + 15;

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.text('4. Details of Eligible Input Tax Credit (ITC) Breakdown', margin, currentY);
        currentY += 10;

        headers = ['ITC Source', 'IGST (Integrated)', 'CGST (Central)', 'SGST (State)'];
        body = [
          [
            '(1) Import of Goods',
            `INR ${fmt(sectionB.import_goods?.igst)}`,
            `INR ${fmt(sectionB.import_goods?.cgst)}`,
            `INR ${fmt(sectionB.import_goods?.sgst)}`
          ],
          [
            '(2) Inward Supplies Liable to Reverse Charge',
            `INR ${fmt(sectionB.rcm_inward?.igst)}`,
            `INR ${fmt(sectionB.rcm_inward?.cgst)}`,
            `INR ${fmt(sectionB.rcm_inward?.sgst)}`
          ],
          [
            '(3) Inward Supplies from ISD',
            `INR ${fmt(sectionB.isd_inward?.igst)}`,
            `INR ${fmt(sectionB.isd_inward?.cgst)}`,
            `INR ${fmt(sectionB.isd_inward?.sgst)}`
          ],
          [
            '(4) All Other ITC (Purchases & Expenses)',
            `INR ${fmt(sectionB.other_itc?.igst)}`,
            `INR ${fmt(sectionB.other_itc?.cgst)}`,
            `INR ${fmt(sectionB.other_itc?.sgst)}`
          ]
        ];
        currentY = runAutoTable(currentY, headers, body, {
          1: { halign: 'right' },
          2: { halign: 'right' },
          3: { halign: 'right' }
        }) + 15;

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.text('Net GST Tax Liability Offsets Schedule', margin, currentY);
        currentY += 10;

        headers = ['Tax Component Type', 'Net Payable Offset (After Credit Utilization)'];
        body = [
          ['IGST (Integrated Tax)', `INR ${fmt(Math.abs(parseFloat(sectionD.igst || 0)))} ${parseFloat(sectionD.igst) < 0 ? '(Surplus Credit)' : ''}`],
          ['CGST (Central Tax)', `INR ${fmt(Math.abs(parseFloat(sectionD.cgst || 0)))} ${parseFloat(sectionD.cgst) < 0 ? '(Surplus Credit)' : ''}`],
          ['SGST (State Tax)', `INR ${fmt(Math.abs(parseFloat(sectionD.sgst || 0)))} ${parseFloat(sectionD.sgst) < 0 ? '(Surplus Credit)' : ''}`]
        ];
        currentY = runAutoTable(currentY, headers, body, {
          1: { halign: 'right', fontStyle: 'bold' }
        });
      }

      else if (type === 'pdf_receipt') {
        const title = 'GST Filing Acknowledgment Receipt';
        const subtitle = `Receipt Token: ${dataRows.acknowledgement_number || 'N/A'}`;
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Registered Entity Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Registered GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Return Form Type', value: dataRows.return_type || 'N/A' },
          { label: 'Filing Period Cycle', value: dataRows.period || 'N/A' },
          { label: 'Acknowledgment Number', value: dataRows.acknowledgement_number || 'N/A' },
          { label: 'Jurisdiction Authority', value: settings.state || 'Not Configured' }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        currentY = ensureSpace(currentY, 150, title, subtitle);
        doc.setFillColor(248, 250, 252);
        doc.setDrawColor(16, 185, 129);
        doc.setLineWidth(1.5);
        doc.rect(margin + 50, currentY, pageWidth - (margin * 2) - 100, 150, 'FD');

        doc.setFont('helvetica', 'bold');
        doc.setFontSize(11);
        doc.setTextColor(16, 185, 129);
        doc.text('FILING SUCCESSFUL & CERTIFIED', pageWidth / 2, currentY + 30, { align: 'center' });

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8.5);
        doc.setTextColor(30, 41, 59);

        let cardY = currentY + 55;
        doc.text(`Filer User Agent: ${dataRows.filed_by || 'Not Signed'}`, pageWidth / 2, cardY, { align: 'center' });
        doc.text(`Filing Timestamp: ${dataRows.filed_date || 'N/A'}`, pageWidth / 2, cardY + 15, { align: 'center' });
        doc.text(`Return Acknowledgment Number: ${dataRows.acknowledgement_number || '—'}`, pageWidth / 2, cardY + 30, { align: 'center' });
        doc.setFont('helvetica', 'bold');
        doc.text('Status: TAX_LEDGER_RECORD_POSTED', pageWidth / 2, cardY + 50, { align: 'center' });

        doc.setDrawColor(203, 213, 225);
        doc.rect(pageWidth / 2 - 120, cardY + 65, 240, 25);
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7.5);
        doc.setTextColor(100, 116, 139);
        doc.text('VERIFIED DIGITAL SIGNATURE KEY: SYSTEM_GENERATED_EVC', pageWidth / 2, cardY + 80, { align: 'center' });

        currentY += 180;
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(8);
        doc.setTextColor(100, 116, 139);
        doc.text('Disclaimer: This is an automated digital acknowledgment receipt of the return submitted via Shori.', margin, currentY);
      }

      else if (type === 'pdf_itc') {
        const title = 'GSTR-2B Input Tax Credit Reconciliation';
        const subtitle = 'GST Ledger Credit Audits';
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Company Legal Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Business GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'ITC Health Score', value: itcData?.itc_health_score || 'Excellent' },
          { label: 'Matching Algorithm', value: settings.itc_matching_mode || 'Auto-matching' },
          { label: 'Supplier Record Count', value: String(itcData?.records?.length || 0) },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        const kpis = [
          { label: 'Eligible ITC (Claimed)', value: `INR ${fmt(itcData?.kpis?.eligible_itc)}` },
          { label: 'Blocked ITC (Sect 17(5))', value: `INR ${fmt(itcData?.kpis?.blocked_itc)}` },
          { label: 'Pending Credits', value: `INR ${fmt(itcData?.kpis?.pending_itc)}` },
          { label: 'Reversed ITC', value: `INR ${fmt(itcData?.kpis?.reversed_itc)}` }
        ];
        currentY = drawKPICards(currentY, kpis);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('ITC COMPLIANCE LEDGER RECORDS', margin, currentY);
        currentY += 12;

        const headers = ['Supplier Vendor', 'Vendor GSTIN', 'Invoice Number', 'GST Amount', 'Eligibility', 'Reconciliation Status'];
        const body = (itcData?.records || []).map(row => [
          row.vendor,
          row.gstin,
          row.invoice,
          `INR ${fmt(row.gst_amount)}`,
          row.eligibility,
          row.reconciliation_status
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          3: { halign: 'right' },
          4: { halign: 'center' },
          5: { halign: 'center' }
        });
      }

      else if (type === 'pdf_calendar') {
        const title = 'GST Statutory Compliance Calendar';
        const subtitle = 'Statutory Return Deadlines';
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Registered Entity Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Business GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Default Jurisdiction', value: settings.state || 'Not Configured' },
          { label: 'Return Offset Alerts', value: settings.due_date_alerts || '5 Days Prior' },
          { label: 'Filing Calendar Mode', value: 'Indian Statutory Returns' },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('UPCOMING RETURN DEADLINES & COMPLIANCE ACTIONS', margin, currentY);
        currentY += 12;

        const headers = ['Filing Return Type', 'Due Date Deadline', 'Days Remaining', 'Compliance Action'];
        const body = (calendarData?.deadlines || []).map(row => [
          row.return_type,
          row.due_date,
          `${row.days_remaining} Days`,
          row.action_required.toUpperCase()
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          2: { halign: 'center', fontStyle: 'bold' },
          3: { halign: 'center' }
        });
      }

      else if (type === 'pdf_health') {
        const title = 'GST Compliance Health Audit Report';
        const subtitle = 'Executive Compliance Health Indicator';
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Registered Company Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Tax Filer GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Jurisdiction Authority', value: settings.state || 'Not Configured' },
          { label: 'Active Audit Rules', value: 'PAN/GSTIN/HSN Checkers' },
          { label: 'Risk Logs Scan Count', value: String(healthData?.risk_log?.length || 0) },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        const kpis = [
          { label: 'Filing Compliance %', value: `${healthData?.metrics?.filing_compliance || 100}%` },
          { label: 'ITC Utilization Rate', value: `${healthData?.metrics?.itc_utilization || 0}%` },
          { label: 'Return Accuracy Score', value: `${healthData?.metrics?.return_accuracy || 100}%` },
          { label: 'GST Risk Audit Score', value: `${healthData?.metrics?.gst_risk_score || 0}/100` }
        ];
        currentY = drawKPICards(currentY, kpis);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('AUDIT RISK DETECTION LOGS', margin, currentY);
        currentY += 12;

        const headers = ['Severity', 'Risk Log Category', 'Detailed Audit Findings / Issues Detected'];
        const body = (healthData?.risk_log || []).map(row => [
          row.severity.toUpperCase(),
          row.category,
          row.description
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          0: { halign: 'center', fontStyle: 'bold' }
        });
      }

      else if (type === 'pdf_history') {
        const title = 'GST Statutory Filing History Log';
        const subtitle = 'Filed GSTR Returns Acknowledgment Audit Log';
        drawHeader(title, subtitle);

        const meta = [
          { label: 'Registered Entity Name', value: settings.legal_name || 'Shori Corporation' },
          { label: 'Business GSTIN', value: settings.gstin || 'Not Configured' },
          { label: 'Total Filed Returns', value: String(dataRows?.length || 0) },
          { label: 'Report Generated Date', value: new Date().toLocaleString('en-IN') }
        ];
        currentY = drawMetadataBlock(currentY, meta);

        currentY = ensureSpace(currentY, 30, title, subtitle);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 23, 42);
        doc.text('GST STATUTORY FILING LOG RECORDS', margin, currentY);
        currentY += 12;

        const headers = ['Filing Return Type', 'Filing Period', 'Filed Date', 'Acknowledgement Token #', 'Filed By User', 'Filing Status'];
        const body = (dataRows || []).map(row => [
          row.return_type,
          row.period,
          row.filed_date,
          row.acknowledgement_number,
          row.filed_by,
          'FILED SUCCESSFULLY'
        ]);

        currentY = runAutoTable(currentY, headers, body, {
          1: { halign: 'center' },
          2: { halign: 'center' },
          3: { halign: 'center' },
          5: { halign: 'center', fontStyle: 'bold' }
        });
      }

      drawFooters();
      doc.save(filename);
      setToast({ open: true, message: 'PDF generated and downloaded successfully.', severity: 'success' });
    } catch (err) {
      console.error(err);
      setToast({ open: true, message: 'Failed to generate PDF document.', severity: 'error' });
    }
  };

  const inputStyle = {
    '& .MuiOutlinedInput-root': {
      borderRadius: '8px',
      backgroundColor: isDark ? '#111827' : '#ffffff',
      fontSize: '0.85rem',
      transition: 'all 0.2s ease',
      '& fieldset': {
        borderColor: borderCol,
      },
      '&:hover fieldset': {
        borderColor: isDark ? '#475569' : '#cbd5e1',
      },
      '&.Mui-focused fieldset': {
        borderColor: isDark ? '#94a3b8' : '#0f172a',
        borderWidth: '1px',
      },
    },
    '& .MuiInputLabel-root': {
      fontSize: '0.85rem',
      color: textSecondary,
      '&.Mui-focused': {
        color: isDark ? '#f8fafc' : '#0f172a',
      }
    }
  };

  const COLORS = {
    CGST: '#2563EB',
    SGST: '#60a5fa',
    IGST: '#0F172A',
    CESS: '#64748B'
  };

  const premiumCardStyle = {
    border: isDark ? '1px solid #334155' : '1px solid #E5E7EB',
    borderRadius: '12px',
    background: isDark ? '#1e293b' : 'white',
    boxShadow: 'none',
    transition: 'all 0.2s ease',
  };

  const filteredChartData = useMemo(() => {
    const data = dashboardData?.chart_data || [];
    if (chartPeriod === '3m') {
      return data.slice(-3);
    }
    return data;
  }, [dashboardData?.chart_data, chartPeriod]);

  const compositionData = useMemo(() => {
    const comp = dashboardData?.composition || {};
    const cgst = parseFloat(comp.cgst || 0);
    const sgst = parseFloat(comp.sgst || 0);
    const igst = parseFloat(comp.igst || 0);
    const cess = parseFloat(comp.cess || 0);
    const total = cgst + sgst + igst + cess;
    if (total === 0) return [];
    
    return [
      { name: 'CGST', value: cgst, percent: ((cgst / total) * 100).toFixed(1) + '%' },
      { name: 'SGST', value: sgst, percent: ((sgst / total) * 100).toFixed(1) + '%' },
      { name: 'IGST', value: igst, percent: ((igst / total) * 100).toFixed(1) + '%' },
      { name: 'CESS', value: cess, percent: ((cess / total) * 100).toFixed(1) + '%' },
    ].filter(d => d.value > 0);
  }, [dashboardData?.composition]);

  const totalGSTCollected = useMemo(() => {
    const comp = dashboardData?.composition || {};
    const cgst = parseFloat(comp.cgst || 0);
    const sgst = parseFloat(comp.sgst || 0);
    const igst = parseFloat(comp.igst || 0);
    const cess = parseFloat(comp.cess || 0);
    return cgst + sgst + igst + cess;
  }, [dashboardData?.composition]);

  const upcomingFiling = useMemo(() => {
    const day = now.getDate();
    const monthName = now.toLocaleString('default', { month: 'short' });
    if (day <= 11) {
      const diff = 11 - day;
      return {
        days: `${diff} ${diff === 1 ? 'Day' : 'Days'}`,
        desc: `GSTR-1 due on 11 ${monthName}`
      };
    } else if (day <= 20) {
      const diff = 20 - day;
      return {
        days: `${diff} ${diff === 1 ? 'Day' : 'Days'}`,
        desc: `GSTR-3B due on 20 ${monthName}`
      };
    } else {
      const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      const nextMonthName = nextMonth.toLocaleString('default', { month: 'short' });
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
      const diff = daysInMonth - day + 11;
      return {
        days: `${diff} Days`,
        desc: `GSTR-1 due on 11 ${nextMonthName}`
      };
    }
  }, [now]);

  const tabIcons = {
    dashboard: <DashboardIcon sx={{ fontSize: 16 }} />,
    transactions: <ReceiptIcon sx={{ fontSize: 16 }} />,
    settings: <SettingsIcon sx={{ fontSize: 16 }} />,
    summary: <AssessmentIcon sx={{ fontSize: 16 }} />,
    liability: <AccountBalanceWalletIcon sx={{ fontSize: 16 }} />,
    gstr1: <UploadFileIcon sx={{ fontSize: 16 }} />,
    gstr3b: <DescriptionIcon sx={{ fontSize: 16 }} />,
    itc: <FactCheckIcon sx={{ fontSize: 16 }} />,
    calendar: <CalendarTodayIcon sx={{ fontSize: 16 }} />,
    history: <HistoryIcon sx={{ fontSize: 16 }} />,
    health: <HealthAndSafetyIcon sx={{ fontSize: 16 }} />,
  };

  return (
    <Box width="100%" sx={{ bgcolor: isDark ? 'transparent' : '#FAFAFA', height: '100%', display: 'flex', flexDirection: 'column', p: 0, overflow: 'hidden' }}>
      <Box display="flex" width="100%" sx={{ flex: 1, minHeight: 0, gap: 0 }} flexDirection={{ xs: 'column', md: 'row' }}>
        {/* ── Left Sidebar Navigation ── */}
        <Box
          sx={{
            width: { xs: '100%', md: sidebarCollapsed ? 56 : 210 },
            minWidth: { xs: '100%', md: sidebarCollapsed ? 56 : 210 },
            flexShrink: 0,
            transition: 'width 0.2s ease, min-width 0.2s ease',
            borderRight: { xs: 'none', md: `1px solid ${borderCol}` },
            borderBottom: { xs: `1px solid ${borderCol}`, md: 'none' },
            pr: { xs: 0, md: 0 },
            pb: { xs: 2, md: 0 },
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Box display="flex" flexDirection="column">
            {[
              {
                title: 'GST Center',
                items: [
                  { key: 'dashboard', label: 'Overview' },
                  { key: 'transactions', label: 'Tax Ledger' },
                  { key: 'settings', label: 'Settings' },
                ]
              },
              {
                title: 'Compliance & Returns',
                items: [
                  { key: 'summary', label: 'GST Summary' },
                  { key: 'liability', label: 'GST Liability' },
                  { key: 'gstr1', label: 'GSTR-1 Preparation' },
                  { key: 'gstr3b', label: 'GSTR-3B Preparation' },
                  { key: 'itc', label: 'ITC Reconciliation' },
                  { key: 'calendar', label: 'Compliance Calendar' },
                  { key: 'history', label: 'Filing History' },
                  { key: 'health', label: 'GST Health Center' },
                ]
              }
            ].map((group, groupIdx) => (
              <Box key={groupIdx} mb={0.5}>
                {!sidebarCollapsed && (
                  <Typography
                    variant="caption"
                    fontWeight={600}
                    color={textSecondary}
                    sx={{ px: 2, pt: groupIdx === 0 ? 1.5 : 1, pb: 0.5, display: 'block', textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.64rem' }}
                  >
                    {group.title}
                  </Typography>
                )}
                {group.items.map((item) => {
                  const active = activeTab === item.key;
                  
                  const menuItemBtn = (
                    <Box
                      key={item.key}
                      component="button"
                      onClick={() => handleTabChange(item.key)}
                      sx={{
                        width: '100%',
                        textAlign: sidebarCollapsed ? 'center' : 'left',
                        pl: sidebarCollapsed ? 0 : 2.5,
                        pr: sidebarCollapsed ? 0 : 1.5,
                        py: 0.75,
                        border: 0,
                        borderRadius: 0,
                        backgroundColor: 'transparent',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontWeight: active ? 600 : 400,
                        color: active ? '#2563EB' : textSecondary,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                        gap: 1.25,
                        transition: 'all 0.15s ease',
                        '&:hover': {
                          color: textPrimary,
                          bgcolor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
                        },
                      }}
                    >
                      {!sidebarCollapsed && active && (
                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#2563EB', flexShrink: 0, mr: -0.5 }} />
                      )}
                      
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: active ? '#2563EB' : textSecondary, flexShrink: 0, width: sidebarCollapsed ? '100%' : 'auto' }}>
                        {tabIcons[item.key] || <DashboardIcon sx={{ fontSize: 16 }} />}
                      </Box>
                      
                      {!sidebarCollapsed && (
                        <Typography sx={{ fontSize: '0.8rem', fontWeight: 'inherit', color: 'inherit', whiteSpace: 'nowrap' }}>
                          {item.label}
                        </Typography>
                      )}
                    </Box>
                  );

                  return sidebarCollapsed ? (
                    <MuiTooltip key={item.key} title={item.label} placement="right" arrow>
                      {menuItemBtn}
                    </MuiTooltip>
                  ) : (
                    menuItemBtn
                  );
                })}
              </Box>
            ))}
          </Box>

          {/* Collapse button */}
          <Box
            component="button"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            sx={{
              width: '100%',
              textAlign: 'left',
              pl: sidebarCollapsed ? 0 : 2,
              pr: sidebarCollapsed ? 0 : 1.5,
              py: 1.25,
              border: 0,
              borderTop: `1px solid ${borderCol}`,
              backgroundColor: 'transparent',
              cursor: 'pointer',
              color: textSecondary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
              gap: 1,
              fontSize: '0.8rem',
              fontWeight: 500,
              '&:hover': { color: textPrimary },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', transform: sidebarCollapsed ? 'rotate(0deg)' : 'rotate(180deg)', transition: 'transform 0.2s ease' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </Box>
            {!sidebarCollapsed && (
              <Typography sx={{ fontSize: '0.8rem', color: 'inherit', fontWeight: 'inherit' }}>Collapse</Typography>
            )}
          </Box>
        </Box>

        {/* ── Right Content Workspace Pane ── */}
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 0, height: '100%', minHeight: 0, pt: 2, pb: 2, pr: 2.5, pl: { xs: 1.5, md: 3 }, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
          {/* Dynamic Page Header based on Active Tab */}
          {activeTab === 'dashboard' && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', pb: 2, mb: 2.5, borderBottom: `1px solid ${borderCol}`, flexDirection: { xs: 'column', md: 'row' }, gap: 2, transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
              <Box>
                <Typography variant="h5" fontWeight={700} color={textPrimary} sx={{ letterSpacing: '-0.025em', mb: 0.25, fontSize: '1.35rem' }}>
                  GST Compliance Center
                </Typography>
                <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.8rem' }}>
                  Real-time GST overview, tax summary, compliance status and filing readiness.
                </Typography>
              </Box>
              <Box display="flex" gap={1.5} alignItems="center" flexWrap="wrap" flexShrink={0}>
                {/* Configure Widgets Button */}
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setConfigOpen(true)}
                  sx={{
                    height: 32,
                    textTransform: 'none',
                    borderRadius: '6px',
                    borderColor: borderCol,
                    color: textPrimary,
                    fontWeight: 500,
                    fontSize: '0.78rem',
                    px: 1.5,
                    gap: 0.75,
                    '&:hover': {
                      borderColor: textSecondary,
                      bgcolor: isDark ? 'rgba(255,255,255,0.03)' : '#f8fafc',
                    }
                  }}
                  startIcon={<SettingsIcon sx={{ fontSize: 14 }} />}
                >
                  Configure Widgets
                </Button>
              </Box>
            </Box>
          )}

          {/* ── Tab Panels Content ── */}
          <Box sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflowY: activeTab === 'transactions' ? 'hidden' : 'auto' }}>
            {/* ── TAB PANEL: OVERVIEW (DASHBOARD) ── */}
            {activeTab === 'dashboard' && (
              <Box>
                {dashboardLoading ? (
                  <Box display="flex" justifyContent="center" py={12}>
                    <CircularProgress size={28} sx={{ color: '#2563EB' }} />
                  </Box>
                ) : dashboardError ? (
                  <Box maxWidth={500} mx="auto" my={6} textAlign="center">
                    <Alert severity="error" sx={{ mb: 3, borderRadius: '8px' }}>{dashboardError}</Alert>
                    <Button variant="outlined" size="small" onClick={fetchDashboard} sx={{ textTransform: 'none', borderRadius: '8px' }}>Retry Connection</Button>
                  </Box>
                ) : (
                  <Box>
                    {/* Executive KPI Strip (6 Cards) - with colored icon badges */}
                    <Grid container spacing={1.5} mb={2.5}>
                      {visibleWidgets.kpiOutput && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  Output GST (Sales)
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color={textPrimary} mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                ₹{fmt(dashboardData?.metrics?.collected)}
                              </Typography>
                              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: '#166534', fontWeight: 600 }}>
                                +12.8% vs May 2026 ↑
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      {visibleWidgets.kpiItc && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  Input Tax Credit (ITC)
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#F0FDF4', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color={textPrimary} mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                ₹{fmt(dashboardData?.metrics?.input_credit)}
                              </Typography>
                              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: '#166534', fontWeight: 600 }}>
                                +8.4% vs May 2026 ↑
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      {visibleWidgets.kpiNet && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  Net Tax Liability
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#FFF7ED', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ea580c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M12 6v6l4 2"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color={Number(dashboardData?.metrics?.net_liability) >= 0 ? '#B91C1C' : '#166534'} mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                ₹{fmt(Math.abs(Number(dashboardData?.metrics?.net_liability || 0)))}
                              </Typography>
                              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: '#B91C1C', fontWeight: 600 }}>
                                -15.2% vs May 2026 ↓
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      {visibleWidgets.kpiFiling && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  Upcoming Filing
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#F5F3FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color={textPrimary} mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                {upcomingFiling.days}
                              </Typography>
                              <Typography variant="caption" color={textSecondary} sx={{ fontSize: '0.68rem', fontWeight: 500 }}>
                                {upcomingFiling.desc}
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      {visibleWidgets.kpiAccuracy && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  GST Accuracy Score
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#F0FDF4', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color="#166534" mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                93%
                              </Typography>
                              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: '#166534', fontWeight: 600 }}>
                                ● Excellent
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      {visibleWidgets.kpiPending && (
                        <Grid item xs={12} sm={6} md={2} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                          <Card sx={premiumCardStyle}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                                <Typography variant="caption" fontWeight={600} color={textSecondary} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.62rem', lineHeight: 1.3 }}>
                                  Pending Compliance
                                </Typography>
                                <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="9 15 11 17 15 13"/></svg>
                                </Box>
                              </Box>
                              <Typography variant="h6" fontWeight={700} color={dashboardData?.metrics?.pending_compliance > 0 ? '#B91C1C' : '#166534'} mb={0.25} sx={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>
                                {dashboardData?.metrics?.pending_compliance ?? 2}
                              </Typography>
                              <Typography variant="caption" sx={{ fontSize: '0.68rem', color: dashboardData?.metrics?.pending_compliance > 0 ? '#B91C1C' : '#166534', fontWeight: 600 }}>
                                {dashboardData?.metrics?.pending_compliance > 0 ? 'Action required' : 'Compliant'}
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      )}
                    </Grid>

                    {/* Section 2 & 3: Charts Row - 3 columns: trend, composition, compliance calendar */}
                    {(visibleWidgets.trendChart || visibleWidgets.compositionChart || visibleWidgets.calendar) && (
                      <Grid container spacing={1.5} mb={2}>
                        {/* Trend Line Chart */}
                        {visibleWidgets.trendChart && (
                          <Grid item xs={12} md={(visibleWidgets.compositionChart || visibleWidgets.calendar) ? 6.5 : 12} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                            <Card sx={premiumCardStyle}>
                              <CardContent sx={{ p: 2.5 }}>
                                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                                  <Box>
                                    <Typography variant="subtitle1" fontWeight={700} color={textPrimary} sx={{ fontSize: '0.85rem' }}>
                                      GST Trend – Last 6 Months
                                    </Typography>
                                  </Box>
                                  <Select
                                    size="small"
                                    value={chartPeriod}
                                    onChange={(e) => setChartPeriod(e.target.value)}
                                    variant="outlined"
                                    sx={{
                                      height: 26,
                                      fontSize: '0.72rem',
                                      fontWeight: 500,
                                      borderRadius: '6px',
                                      color: textSecondary,
                                      bgcolor: isDark ? 'transparent' : '#ffffff',
                                      '& .MuiOutlinedInput-notchedOutline': { borderColor: borderCol },
                                      '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: textSecondary },
                                      '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: textPrimary, borderWidth: '1px' }
                                    }}
                                  >
                                    <MenuItem value="6m" sx={{ fontSize: '0.72rem' }}>Last 6 Months</MenuItem>
                                    <MenuItem value="3m" sx={{ fontSize: '0.72rem' }}>Last 3 Months</MenuItem>
                                  </Select>
                                </Box>
                                {/* Manual legend row - fully controlled, no overlap */}
                                <Box display="flex" flexWrap="wrap" gap={2} mb={1.5}>
                                  {[
                                    { label: 'Output GST (Collected)', color: '#2563EB', dashed: false },
                                    { label: 'Input Tax Credit (ITC)', color: '#10b981', dashed: false },
                                    { label: 'Net Tax Liability', color: '#7c3aed', dashed: true },
                                  ].map((item) => (
                                    <Box key={item.label} display="flex" alignItems="center" gap={0.75}>
                                      {item.dashed ? (
                                        <Box sx={{ width: 20, height: 2, borderTop: `2px dashed ${item.color}`, flexShrink: 0 }} />
                                      ) : (
                                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: item.color, flexShrink: 0 }} />
                                      )}
                                      <Typography sx={{ fontSize: '0.7rem', color: textSecondary, whiteSpace: 'nowrap' }}>
                                        {item.label}
                                      </Typography>
                                    </Box>
                                  ))}
                                </Box>
                                <Box height={200} width="100%">
                                  <ResponsiveContainer width="100%" height="100%" debounce={50}>
                                    <LineChart data={filteredChartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? '#334155' : '#f1f5f9'} />
                                      <XAxis dataKey="label" stroke={textSecondary} fontSize={10} tickLine={false} />
                                      <YAxis stroke={textSecondary} fontSize={10} tickLine={false} axisLine={false} />
                                      <Tooltip
                                        contentStyle={{
                                          background: isDark ? '#1e293b' : '#ffffff',
                                          border: `1px solid ${borderCol}`,
                                          borderRadius: '8px',
                                          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
                                          color: textPrimary,
                                          fontSize: '0.78rem',
                                        }}
                                        formatter={(value) => [`₹${fmt(value)}`]}
                                      />
                                      <Line name="Output GST (Collected)" type="monotone" dataKey="collected" stroke="#2563EB" strokeWidth={1.5} dot={{ r: 2 }} activeDot={{ r: 4 }} />
                                      <Line name="Input Tax Credit (ITC)" type="monotone" dataKey="input_credit" stroke="#10b981" strokeWidth={1.5} dot={{ r: 2 }} />
                                      <Line name="Net Tax Liability" type="monotone" dataKey="net_liability" stroke="#7c3aed" strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
                                    </LineChart>
                                  </ResponsiveContainer>
                                </Box>
                              </CardContent>
                            </Card>
                          </Grid>
                        )}

                        {/* Tax Composition Donut Chart */}
                        {visibleWidgets.compositionChart && (
                          <Grid item xs={12} md={visibleWidgets.trendChart ? 2.75 : 6} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                            <Card sx={{ ...premiumCardStyle, height: '100%' }}>
                              <CardContent sx={{ p: 2.5 }}>
                                <Typography variant="subtitle1" fontWeight={700} color={textPrimary} mb={1.5} sx={{ fontSize: '0.85rem' }}>
                                  GST Composition (This Month)
                                </Typography>
                                {totalGSTCollected > 0 ? (
                                  <>
                                    <Box sx={{ position: 'relative', width: '100%', height: 190, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                      <ResponsiveContainer width="100%" height="100%" debounce={50}>
                                        <PieChart>
                                          <Pie data={compositionData} cx="50%" cy="50%" innerRadius={70} outerRadius={82} paddingAngle={2} dataKey="value">
                                            {compositionData.map((entry, index) => (
                                              <Cell key={`cell-${index}`} fill={COLORS[entry.name]} />
                                            ))}
                                          </Pie>
                                        </PieChart>
                                      </ResponsiveContainer>
                                      <Box sx={{ position: 'absolute', textAlign: 'center', width: '130px', px: 1 }}>
                                        <Typography variant="caption" color={textSecondary} fontWeight={600} sx={{ textTransform: 'uppercase', fontSize: '0.55rem', letterSpacing: '0.04em', display: 'block', mb: 0.25 }}>
                                          Total GST
                                        </Typography>
                                        <Typography
                                          variant="subtitle1"
                                          fontWeight={700}
                                          color={textPrimary}
                                          sx={{
                                            fontSize: fmt(totalGSTCollected).length > 12 ? '0.72rem' : '0.88rem',
                                            lineHeight: 1.2,
                                            wordBreak: 'break-all',
                                            display: 'block'
                                          }}
                                        >
                                          ₹{fmt(totalGSTCollected)}
                                        </Typography>
                                      </Box>
                                    </Box>
                                    <Box display="flex" flexDirection="column" gap={0.75} mt={1}>
                                      {compositionData.map((entry) => (
                                        <Box key={entry.name} display="flex" justifyContent="space-between" alignItems="center">
                                          <Box display="flex" alignItems="center" gap={1}>
                                            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLORS[entry.name], flexShrink: 0 }} />
                                            <Typography variant="body2" color={textPrimary} fontWeight={500} sx={{ fontSize: '0.73rem' }}>
                                              {entry.name}
                                            </Typography>
                                          </Box>
                                          <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.73rem' }}>
                                            ₹{fmt(entry.value)} <span style={{ color: textSecondary, fontSize: '0.68rem' }}>({entry.percent})</span>
                                          </Typography>
                                        </Box>
                                      ))}
                                    </Box>
                                  </>
                                ) : (
                                  <Box display="flex" justifyContent="center" alignItems="center" height={180}>
                                    <Typography variant="body2" color={textSecondary}>No composition data</Typography>
                                  </Box>
                                )}
                              </CardContent>
                            </Card>
                          </Grid>
                        )}

                        {/* Compliance Calendar as 3rd column in charts row */}
                        {visibleWidgets.calendar && (
                          <Grid item xs={12} md={visibleWidgets.trendChart || visibleWidgets.compositionChart ? 2.75 : 12} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                            <Card sx={{ ...premiumCardStyle, height: '100%' }}>
                              <CardContent sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column' }}>
                                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                                  <Typography variant="subtitle1" fontWeight={700} color={textPrimary} sx={{ fontSize: '0.85rem' }}>
                                    Compliance Calendar <Typography component="span" variant="caption" color={textSecondary} sx={{ fontSize: '0.72rem', fontWeight: 400, ml: 0.5 }}>(Upcoming)</Typography>
                                  </Typography>
                                </Box>
                                <Box display="flex" flexDirection="column" gap={1.5} flexGrow={1}>
                                  {[
                                    { form: 'GSTR-3B', desc: 'Monthly Return', due: '20 Jun 2026', days: 11, urgent: true },
                                    { form: 'GSTR-1', desc: 'Outward Supplies', due: '11 Jul 2026', days: 32, urgent: false },
                                    { form: 'GSTR-9 (FY 2025–26)', desc: 'Annual Return', due: '31 Dec 2026', days: 205, urgent: false },
                                  ].map((item, idx) => (
                                    <Box key={idx} display="flex" alignItems="flex-start" gap={1.25}>
                                      <Box sx={{ width: 30, height: 30, borderRadius: '8px', bgcolor: isDark ? '#1f2937' : '#f8fafc', border: `1px solid ${borderCol}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={item.urgent ? '#B91C1C' : '#64748B'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                                      </Box>
                                      <Box flex={1} minWidth={0}>
                                        <Box display="flex" justifyContent="space-between" alignItems="baseline">
                                          <Typography variant="subtitle2" fontWeight={700} color={item.urgent ? '#B91C1C' : textPrimary} sx={{ fontSize: '0.78rem' }}>
                                            {item.form}
                                          </Typography>
                                          <Typography variant="caption" fontWeight={700} color={item.urgent ? '#B91C1C' : textSecondary} sx={{ fontSize: '0.68rem', flexShrink: 0, ml: 1 }}>
                                            {item.urgent ? `${item.days} Days` : `${item.days} Days`}
                                          </Typography>
                                        </Box>
                                        <Typography variant="caption" color={textSecondary} sx={{ fontSize: '0.68rem', display: 'block' }}>
                                          {item.desc}
                                        </Typography>
                                        <Typography variant="caption" color={textSecondary} sx={{ fontSize: '0.65rem' }}>
                                          {item.due}
                                        </Typography>
                                      </Box>
                                    </Box>
                                  ))}
                                </Box>
                                <Box mt={2} pt={1} borderTop={`1px solid ${borderCol}`}>
                                  <Button
                                    fullWidth size="small"
                                    onClick={() => handleTabChange('calendar')}
                                    sx={{ textTransform: 'none', fontSize: '0.72rem', fontWeight: 600, color: '#2563EB', justifyContent: 'center', py: 0.25, '&:hover': { bgcolor: 'rgba(37,99,235,0.05)' } }}
                                  >
                                    View Calendar →
                                  </Button>
                                </Box>
                              </CardContent>
                            </Card>
                          </Grid>
                        )}
                      </Grid>
                    )}

                    {/* Bottom: 2-Column – Recent Tax Ledger + Audit Insights */}
                    {(visibleWidgets.ledger || visibleWidgets.insights) && (
                      <Grid container spacing={1.5} mb={2}>
                        {/* Recent Tax Ledger Lines */}
                        {visibleWidgets.ledger && (
                          <Grid item xs={12} md={visibleWidgets.insights ? 7 : 12} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                            <Card sx={premiumCardStyle}>
                              <CardContent sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', width: '100%' }}>
                                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: textPrimary, fontFamily: 'inherit' }}>
                                    Recent Tax Ledger Lines
                                  </span>
                                  <button
                                    onClick={() => handleTabChange('transactions')}
                                    style={{
                                      fontSize: '0.72rem',
                                      fontWeight: 600,
                                      color: '#2563EB',
                                      background: 'none',
                                      border: 'none',
                                      padding: 0,
                                      cursor: 'pointer',
                                      fontFamily: 'inherit',
                                      display: 'inline-flex',
                                      alignItems: 'center'
                                    }}
                                  >
                                    View Full Ledger →
                                  </button>
                                </div>
                                {dashboardData?.recent_activity?.length > 0 ? (
                                  <TableContainer>
                                    <Table size="small">
                                      <TableHead>
                                        <TableRow sx={{ '& th': { py: 0.75, fontSize: '0.68rem', fontWeight: 600, color: textSecondary, borderBottom: `1px solid ${borderCol}` } }}>
                                          <TableCell>Date</TableCell>
                                          <TableCell>Reference</TableCell>
                                          <TableCell>Type</TableCell>
                                          <TableCell align="right">Taxable Amount</TableCell>
                                          <TableCell align="right">GST Amount</TableCell>
                                          <TableCell>GST Type</TableCell>
                                          <TableCell align="center">Status</TableCell>
                                        </TableRow>
                                      </TableHead>
                                      <TableBody>
                                        {dashboardData.recent_activity.map((txn, index) => (
                                          <TableRow key={txn.id || index} hover sx={{ '&:last-child td': { borderBottom: 0 }, cursor: 'pointer' }} onClick={() => navigate('/finance/gst-transactions')}>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: textSecondary }}>{txn.date || new Date().toISOString().split('T')[0]}</TableCell>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: '#2563EB', fontWeight: 600 }}>{txn.reference_number || txn.transaction_id}</TableCell>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: textPrimary }}>{txn.transaction_type === 'sale' ? 'Sales Invoice' : 'Purchase Invoice'}</TableCell>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: textPrimary, textAlign: 'right' }}>₹{fmt(txn.taxable_amount || txn.amount)}</TableCell>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: textPrimary, textAlign: 'right', fontWeight: 600 }}>₹{fmt(txn.gst_amount)}</TableCell>
                                            <TableCell sx={{ py: 1, fontSize: '0.72rem', color: textSecondary }}>{txn.gst_type}</TableCell>
                                            <TableCell sx={{ py: 1, textAlign: 'center' }}>
                                              <Box component="span" sx={{ fontSize: '0.65rem', fontWeight: 700, color: '#166534', bgcolor: '#e6fbf4', px: 0.75, py: 0.2, borderRadius: '4px' }}>Posted</Box>
                                            </TableCell>
                                          </TableRow>
                                        ))}
                                      </TableBody>
                                    </Table>
                                  </TableContainer>
                                ) : (
                                  <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={4}>
                                    <Typography variant="body2" color={textSecondary} textAlign="center" sx={{ fontSize: '0.75rem' }}>
                                      No GST transactions recorded for this period.
                                    </Typography>
                                  </Box>
                                )}
                                <Box mt={1.5} pt={1} borderTop={`1px solid ${borderCol}`} textAlign="center">
                                  <Button size="small" onClick={() => handleTabChange('transactions')} sx={{ textTransform: 'none', fontSize: '0.72rem', fontWeight: 600, color: '#2563EB', '&:hover': { bgcolor: 'rgba(37,99,235,0.05)' } }}>
                                    View all transactions →
                                  </Button>
                                </Box>
                              </CardContent>
                            </Card>
                          </Grid>
                        )}

                        {/* Audit & Reconciliation Insights */}
                        {visibleWidgets.insights && (
                          <Grid item xs={12} md={visibleWidgets.ledger ? 5 : 12} sx={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}>
                            <Card sx={premiumCardStyle}>
                              <CardContent sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column' }}>
                                <Typography variant="subtitle1" fontWeight={700} color={textPrimary} mb={1.5} sx={{ fontSize: '0.85rem' }}>
                                  Audit & Reconciliation Insights
                                </Typography>
                                <Box display="flex" flexDirection="column" gap={1} flexGrow={1} overflow="auto">
                                  {dashboardData?.insights?.map((ins, index) => {
                                    const isWarning = ins.includes('due') || ins.includes('0.0%') || ins.includes('no sales') || ins.includes('No sales') || ins.includes('not') || ins.includes('error');
                                    const isInfo = ins.toLowerCase().includes('no sales') || ins.toLowerCase().includes('no gst');
                                    const dotColor = isWarning ? '#F59E0B' : isInfo ? '#3B82F6' : '#10B981';
                                    return (
                                      <Box
                                        key={index}
                                        onClick={() => setToast({ open: true, message: `Drilldown: ${ins}`, severity: 'info' })}
                                        sx={{
                                          display: 'flex',
                                          gap: 1.25,
                                          alignItems: 'center',
                                          p: 1.25,
                                          borderRadius: '8px',
                                          border: `1px solid ${borderCol}`,
                                          bgcolor: isDark ? 'rgba(255,255,255,0.01)' : '#ffffff',
                                          cursor: 'pointer',
                                          transition: 'all 0.15s ease',
                                          '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.03)' : '#f8fafc' }
                                        }}
                                      >
                                        <Box sx={{ width: 28, height: 28, borderRadius: '6px', bgcolor: isWarning ? '#FEF3C7' : isInfo ? '#EFF6FF' : '#F0FDF4', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                          {isWarning ? (
                                            <WarningIcon sx={{ color: '#F59E0B', fontSize: 14 }} />
                                          ) : isInfo ? (
                                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                                          ) : (
                                            <CheckIcon sx={{ color: '#10B981', fontSize: 14 }} />
                                          )}
                                        </Box>
                                        <Typography variant="body2" color={textPrimary} sx={{ lineHeight: 1.4, fontSize: '0.75rem', fontWeight: 400, flex: 1 }}>
                                          {ins}
                                        </Typography>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={textSecondary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
                                      </Box>
                                    );
                                  })}
                                  {(!dashboardData?.insights || dashboardData.insights.length === 0) && (
                                    <Box display="flex" alignItems="center" justifyContent="center" height="100%" py={4}>
                                      <Typography variant="body2" color={textSecondary} textAlign="center">
                                        No insights available for this period.
                                      </Typography>
                                    </Box>
                                  )}
                                </Box>
                                <Box mt={1.5} pt={1} borderTop={`1px solid ${borderCol}`} textAlign="center">
                                  <Button size="small" onClick={() => handleTabChange('health')} sx={{ textTransform: 'none', fontSize: '0.72rem', fontWeight: 600, color: '#2563EB', '&:hover': { bgcolor: 'rgba(37,99,235,0.05)' } }}>
                                    View all insights →
                                  </Button>
                                </Box>
                              </CardContent>
                            </Card>
                          </Grid>
                        )}
                      </Grid>
                    )}

                    {/* ── DUMMY: Old calendar section kept as hidden so visibleWidgets.calendar still works for chart row ── */}
                    {false && visibleWidgets.calendar && (
                      <Grid container spacing={1.5} mb={2}>
                        {/* Already rendered above in charts row */}
                      </Grid>
                    )}

                    {/* Widget Configuration Dialog */}
                    <Dialog
                      open={configOpen}
                      onClose={() => setConfigOpen(false)}
                      PaperProps={{
                        sx: {
                          borderRadius: '12px',
                          p: 1,
                          maxWidth: '440px',
                          width: '100%',
                          bgcolor: isDark ? '#1e293b' : '#ffffff',
                          border: isDark ? '1px solid #334155' : '1px solid #E5E7EB',
                          boxShadow: '0 20px 50px rgba(0,0,0,0.15)',
                        }
                      }}
                    >
                      <DialogTitle sx={{ fontWeight: 700, fontSize: '1rem', color: textPrimary, pb: 0.5 }}>
                        Configure Overview Widgets
                      </DialogTitle>
                      <DialogContent sx={{ pb: 1.5 }}>
                        <Typography variant="body2" color={textSecondary} sx={{ mb: 2, fontSize: '0.8rem' }}>
                          Toggle dashboard widgets to customize your workspace. Preferences are saved automatically.
                        </Typography>
                        <Typography variant="caption" fontWeight={700} color={textSecondary} sx={{ display: 'block', mb: 1, textTransform: 'uppercase', fontSize: '0.62rem', letterSpacing: '0.06em' }}>
                          KPI Cards
                        </Typography>
                        <Box sx={{ pl: 0.5, mb: 2, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                          {[
                            { key: 'kpiOutput', label: 'Output GST (Sales) Card' },
                            { key: 'kpiItc', label: 'Input Tax Credit (ITC) Card' },
                            { key: 'kpiNet', label: 'Net Tax Liability Card' },
                            { key: 'kpiFiling', label: 'Upcoming Filing Card' },
                            { key: 'kpiAccuracy', label: 'GST Accuracy Score Card' },
                            { key: 'kpiPending', label: 'Pending Compliance Card' },
                          ].map((item) => (
                            <FormControlLabel key={item.key} control={<Checkbox checked={visibleWidgets[item.key]} onChange={(e) => { const next = { ...visibleWidgets, [item.key]: e.target.checked }; setVisibleWidgets(next); localStorage.setItem('shori_gst_visible_widgets', JSON.stringify(next)); }} size="small" sx={{ color: borderCol, '&.Mui-checked': { color: '#2563EB' } }} />} label={<Typography sx={{ fontSize: '0.8rem', color: textPrimary }}>{item.label}</Typography>} sx={{ my: -0.25 }} />
                          ))}
                        </Box>
                        <Typography variant="caption" fontWeight={700} color={textSecondary} sx={{ display: 'block', mb: 1, textTransform: 'uppercase', fontSize: '0.62rem', letterSpacing: '0.06em' }}>
                          Analytics & Charts
                        </Typography>
                        <Box sx={{ pl: 0.5, mb: 2, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                          {[
                            { key: 'trendChart', label: 'GST Trend Line Chart' },
                            { key: 'compositionChart', label: 'GST Composition Donut Chart' },
                          ].map((item) => (
                            <FormControlLabel key={item.key} control={<Checkbox checked={visibleWidgets[item.key]} onChange={(e) => { const next = { ...visibleWidgets, [item.key]: e.target.checked }; setVisibleWidgets(next); localStorage.setItem('shori_gst_visible_widgets', JSON.stringify(next)); }} size="small" sx={{ color: borderCol, '&.Mui-checked': { color: '#2563EB' } }} />} label={<Typography sx={{ fontSize: '0.8rem', color: textPrimary }}>{item.label}</Typography>} sx={{ my: -0.25 }} />
                          ))}
                        </Box>
                        <Typography variant="caption" fontWeight={700} color={textSecondary} sx={{ display: 'block', mb: 1, textTransform: 'uppercase', fontSize: '0.62rem', letterSpacing: '0.06em' }}>
                          Information Cards
                        </Typography>
                        <Box sx={{ pl: 0.5, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
                          {[
                            { key: 'calendar', label: 'Compliance Calendar Card' },
                            { key: 'ledger', label: 'Recent Tax Ledger Lines' },
                            { key: 'insights', label: 'Audit & Reconciliation Insights' },
                          ].map((item) => (
                            <FormControlLabel key={item.key} control={<Checkbox checked={visibleWidgets[item.key]} onChange={(e) => { const next = { ...visibleWidgets, [item.key]: e.target.checked }; setVisibleWidgets(next); localStorage.setItem('shori_gst_visible_widgets', JSON.stringify(next)); }} size="small" sx={{ color: borderCol, '&.Mui-checked': { color: '#2563EB' } }} />} label={<Typography sx={{ fontSize: '0.8rem', color: textPrimary }}>{item.label}</Typography>} sx={{ my: -0.25 }} />
                          ))}
                        </Box>
                      </DialogContent>
                      <DialogActions sx={{ px: 2.5, pb: 2 }}>
                        <Button variant="contained" size="small" onClick={() => setConfigOpen(false)} sx={{ textTransform: 'none', bgcolor: '#2563EB', color: '#ffffff', fontWeight: 600, borderRadius: '8px', px: 3, height: 32, boxShadow: 'none', '&:hover': { bgcolor: '#1d4ed8', boxShadow: 'none' } }}>Done</Button>
                      </DialogActions>
                    </Dialog>
                  </Box>
                )}
              </Box>
            )}





            {/* ── TAB PANEL: TRANSACTIONS (TAX LEDGER) ── */}
            {activeTab === 'transactions' && (
              <Card variant="outlined" sx={{ bgcolor: primaryBg, borderColor: borderCol, borderRadius: 3, boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)', overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                {/* Advanced Toolbar */}
                <Box p={3} borderBottom={`1px solid ${borderCol}`} display="flex" flexDirection="column" gap={2.5}>
                  <Box display="flex" flexWrap="wrap" justifyContent="space-between" alignItems="center" gap={2}>
                    <Typography variant="subtitle1" fontWeight={700} color={textPrimary} sx={{ fontSize: '0.95rem' }}>
                      GST Audit Trail & Transactions Ledger
                    </Typography>
                    <Box display="flex" gap={1.5}>
                      <Button
                        variant="outlined"
                        size="small"
                        startIcon={<DownloadIcon />}
                        onClick={handleExportClick}
                        sx={{ 
                          textTransform: 'none', 
                          color: textPrimary, 
                          borderColor: borderCol,
                          borderRadius: '8px',
                          px: 2,
                          fontSize: '0.8rem',
                          fontWeight: 500,
                          bgcolor: isDark ? '#111827' : '#ffffff',
                          '&:hover': {
                            borderColor: isDark ? '#475569' : '#cbd5e1',
                            bgcolor: isDark ? '#1f2937' : '#f8fafc',
                          }
                        }}
                      >
                        Export
                      </Button>
                      <Menu
                        anchorEl={exportAnchorEl}
                        open={isExportMenuOpen}
                        onClose={handleExportClose}
                        slotProps={{
                          paper: {
                            sx: {
                              borderRadius: '8px',
                              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                              border: `1px solid ${borderCol}`,
                              bgcolor: isDark ? '#1e293b' : '#ffffff',
                              '& .MuiMenuItem-root': {
                                fontSize: '0.8rem',
                                py: 1,
                                px: 2,
                                color: textPrimary,
                                '&:hover': {
                                  bgcolor: isDark ? '#334155' : '#f1f5f9',
                                }
                              }
                            }
                          }
                        }}
                      >
                        <MenuItem onClick={() => { handleExportClose(); handleExportCSV(); }}>Export CSV</MenuItem>
                        <MenuItem onClick={() => { handleExportClose(); handleExportPDF(); }}>Export PDF</MenuItem>
                      </Menu>
                      <IconButton 
                        onClick={() => fetchTransactions()} 
                        size="small" 
                        sx={{ 
                          border: `1px solid ${borderCol}`, 
                          borderRadius: '8px', 
                          p: 0.75, 
                          color: textSecondary,
                          bgcolor: isDark ? '#111827' : '#ffffff',
                          '&:hover': {
                            borderColor: isDark ? '#475569' : '#cbd5e1',
                            bgcolor: isDark ? '#1f2937' : '#f8fafc',
                          }
                        }}
                      >
                        <RefreshIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Box>
                  </Box>

                  {/* Filters */}
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={3}>
                      <TextField
                        fullWidth
                        size="small"
                        placeholder="Search ref # or txn ID..."
                        value={txnSearch}
                        onChange={(e) => setTxnSearch(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            setTxnPage(1);
                            fetchTransactions();
                          }
                        }}
                        sx={{ ...inputStyle, minWidth: '180px' }}
                        slotProps={{
                          input: {
                            startAdornment: (
                              <InputAdornment position="start">
                                <SearchIcon sx={{ fontSize: 16, color: textSecondary }} />
                              </InputAdornment>
                            ),
                          },
                        }}
                      />
                    </Grid>

                    <Grid item xs={6} md={2}>
                      <FormControl fullWidth size="small" sx={{ ...inputStyle, minWidth: '150px' }}>
                        <InputLabel shrink>Type</InputLabel>
                        <Select
                          value={txnType}
                          label="Type"
                          displayEmpty
                          onChange={(e) => { setTxnType(e.target.value); setTxnPage(1); }}
                        >
                          <MenuItem value="">All Types</MenuItem>
                          <MenuItem value="sale">Sale</MenuItem>
                          <MenuItem value="purchase">Purchase Bill</MenuItem>
                          <MenuItem value="expense">Expense</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid item xs={6} md={2}>
                      <FormControl fullWidth size="small" sx={{ ...inputStyle, minWidth: '150px' }}>
                        <InputLabel shrink>Status</InputLabel>
                        <Select
                          value={txnStatus}
                          label="Status"
                          displayEmpty
                          onChange={(e) => { setTxnStatus(e.target.value); setTxnPage(1); }}
                        >
                          <MenuItem value="">All Statuses</MenuItem>
                          <MenuItem value="recorded">Recorded</MenuItem>
                          <MenuItem value="pending">Pending</MenuItem>
                          <MenuItem value="filed">Filed</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid item xs={6} md={1.5}>
                      <TextField
                        fullWidth
                        type="date"
                        label="From Date"
                        size="small"
                        slotProps={{ inputLabel: { shrink: true } }}
                        value={dateFrom}
                        onChange={(e) => { setDateFrom(e.target.value); setTxnPage(1); }}
                        sx={{ ...inputStyle, minWidth: '120px' }}
                      />
                    </Grid>

                    <Grid item xs={6} md={1.5}>
                      <TextField
                        fullWidth
                        type="date"
                        label="To Date"
                        size="small"
                        slotProps={{ inputLabel: { shrink: true } }}
                        value={dateTo}
                        onChange={(e) => { setDateTo(e.target.value); setTxnPage(1); }}
                        sx={{ ...inputStyle, minWidth: '120px' }}
                      />
                    </Grid>

                    <Grid item xs={12} md={2} display="flex" gap={1} sx={{ minWidth: '160px' }}>
                      <Button
                        variant="contained"
                        size="small"
                        onClick={() => { setTxnPage(1); fetchTransactions(); }}
                        sx={{
                          flex: 1,
                          textTransform: 'none',
                          bgcolor: isDark ? '#f8fafc' : '#0F172A',
                          color: isDark ? '#0f172a' : '#ffffff',
                          fontWeight: 600,
                          fontSize: '0.85rem',
                          borderRadius: '8px',
                          height: 38,
                          '&:hover': { bgcolor: isDark ? '#e2e8f0' : '#1E293B' },
                          boxShadow: 'none',
                        }}
                      >
                        Search
                      </Button>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={handleResetFilters}
                        sx={{
                          flex: 1,
                          textTransform: 'none',
                          borderColor: borderCol,
                          color: textPrimary,
                          fontWeight: 600,
                          fontSize: '0.85rem',
                          borderRadius: '8px',
                          height: 38,
                          bgcolor: isDark ? '#111827' : '#ffffff',
                          '&:hover': {
                            borderColor: isDark ? '#475569' : '#cbd5e1',
                            bgcolor: isDark ? '#1f2937' : '#f8fafc',
                          },
                        }}
                      >
                        Reset
                      </Button>
                    </Grid>
                  </Grid>
                </Box>

                {/* Table Container */}
                <TableContainer sx={{ overflowX: 'auto', flex: 1, minHeight: 0 }}>
                  <Table size="medium" sx={{ minWidth: 1050 }}>
                    <TableHead>
                      <TableRow sx={{ bgcolor: isDark ? '#111827' : '#f8fafc', borderBottom: `1px solid ${borderCol}` }}>
                        {columnVisibility.date && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, width: '130px', minWidth: '130px' }}>Date</TableCell>}
                        {columnVisibility.ref && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, width: '180px', minWidth: '180px' }}>Reference #</TableCell>}
                        {columnVisibility.type && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, width: '120px', minWidth: '120px' }}>Type</TableCell>}
                        {columnVisibility.taxable && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, textAlign: 'right', width: '130px', minWidth: '130px' }}>Taxable Amt</TableCell>}
                        {columnVisibility.rate && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, textAlign: 'center', width: '100px', minWidth: '100px' }}>GST Rate</TableCell>}
                        {columnVisibility.amount && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, textAlign: 'right', width: '130px', minWidth: '130px' }}>GST Amt</TableCell>}
                        {columnVisibility.gstType && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, width: '110px', minWidth: '110px' }}>Tax Type</TableCell>}
                        {columnVisibility.status && <TableCell sx={{ fontWeight: 600, color: textSecondary, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', border: 0, width: '120px', minWidth: '120px' }}>Status</TableCell>}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {txnsLoading ? (
                        <TableRow>
                          <TableCell colSpan={8} align="center" sx={{ py: 6, border: 0 }}>
                            <CircularProgress size={20} sx={{ color: '#0F172A' }} />
                          </TableCell>
                        </TableRow>
                      ) : txnsError ? (
                        <TableRow>
                          <TableCell colSpan={8} align="center" sx={{ py: 4, border: 0 }}>
                            <Alert severity="error" sx={{ borderRadius: '8px' }}>{txnsError}</Alert>
                          </TableCell>
                        </TableRow>
                      ) : transactions.length > 0 ? (
                        transactions.map((txn) => (
                          <TableRow key={txn.id} hover sx={{ borderBottom: `1px solid ${borderCol}`, '&:last-child': { borderBottom: 0 } }}>
                            {columnVisibility.date && (
                              <TableCell sx={{ fontSize: '0.8rem', border: 0, width: '130px', minWidth: '130px' }}>
                                {new Date(txn.created_at).toLocaleDateString('en-IN', {
                                  year: 'numeric',
                                  month: 'short',
                                  day: 'numeric',
                                })}
                              </TableCell>
                            )}
                            {columnVisibility.ref && (
                              <TableCell sx={{ fontSize: '0.8rem', fontWeight: 600, border: 0, width: '180px', minWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {txn.reference_number || (
                                  <Typography component="span" sx={{ fontSize: '0.75rem', color: textSecondary, fontFamily: 'monospace' }}>
                                    {txn.transaction_id}
                                  </Typography>
                                )}
                              </TableCell>
                            )}
                            {columnVisibility.type && (
                              <TableCell sx={{ border: 0, width: '120px', minWidth: '120px' }}>
                                <Chip
                                  label={txn.transaction_type?.toUpperCase()}
                                  size="small"
                                  sx={{
                                    height: 20,
                                    fontSize: '0.62rem',
                                    fontWeight: 700,
                                    borderRadius: '4px',
                                    bgcolor:
                                      txn.transaction_type === 'sale'
                                        ? isDark ? alpha('#10b981', 0.15) : '#e6fbf4'
                                        : isDark ? alpha('#3b82f6', 0.15) : '#eff6ff',
                                    color:
                                      txn.transaction_type === 'sale' ? '#10b981' : '#3b82f6',
                                  }}
                                />
                              </TableCell>
                            )}
                            {columnVisibility.taxable && (
                              <TableCell sx={{ textAlign: 'right', fontSize: '0.8rem', fontFamily: '"SF Mono", "JetBrains Mono", "Roboto Mono", monospace', border: 0, width: '130px', minWidth: '130px' }}>
                                ₹{fmt(txn.taxable_amount)}
                              </TableCell>
                            )}
                            {columnVisibility.rate && (
                              <TableCell sx={{ textAlign: 'center', fontSize: '0.8rem', border: 0, width: '100px', minWidth: '100px' }}>
                                {Number(txn.gst_rate)}%
                              </TableCell>
                            )}
                            {columnVisibility.amount && (
                              <TableCell sx={{ textAlign: 'right', fontSize: '0.8rem', fontFamily: '"SF Mono", "JetBrains Mono", "Roboto Mono", monospace', fontWeight: 700, border: 0, width: '130px', minWidth: '130px' }}>
                                ₹{fmt(txn.gst_amount)}
                              </TableCell>
                            )}
                            {columnVisibility.gstType && (
                              <TableCell sx={{ border: 0, width: '110px', minWidth: '110px' }}>
                                <Chip
                                  label={txn.gst_type?.toUpperCase()}
                                  size="small"
                                  variant="outlined"
                                  sx={{
                                    height: 18,
                                    fontSize: '0.62rem',
                                    borderColor: borderCol,
                                    color: textPrimary,
                                    fontWeight: 600,
                                    borderRadius: '4px',
                                  }}
                                />
                              </TableCell>
                            )}
                            {columnVisibility.status && (
                              <TableCell sx={{ border: 0, width: '120px', minWidth: '120px' }}>
                                <Chip
                                  label={txn.status?.toUpperCase()}
                                  size="small"
                                  sx={{
                                    height: 20,
                                    fontSize: '0.62rem',
                                    fontWeight: 700,
                                    borderRadius: '4px',
                                    bgcolor:
                                      txn.status === 'filed'
                                        ? isDark ? alpha('#22c55e', 0.15) : '#dcfce7'
                                        : txn.status === 'recorded'
                                        ? isDark ? alpha('#f59e0b', 0.15) : '#fef3c7'
                                        : isDark ? alpha('#ef4444', 0.15) : '#fee2e2',
                                    color:
                                      txn.status === 'filed'
                                        ? '#22c55e'
                                        : txn.status === 'recorded'
                                        ? '#b45309'
                                        : '#ef4444',
                                  }}
                                />
                              </TableCell>
                            )}
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={8} align="center" sx={{ py: 6, color: textSecondary, border: 0 }}>
                            No ledger lines match the search/filter parameters.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Pagination */}
                <TablePagination
                  component="div"
                  count={txnTotal}
                  page={txnPage - 1}
                  rowsPerPage={txnPageSize}
                  onPageChange={(_, newPage) => setTxnPage(newPage + 1)}
                  onRowsPerPageChange={(e) => {
                    setTxnPageSize(Number(e.target.value));
                    setTxnPage(1);
                  }}
                  rowsPerPageOptions={[25, 50, 100]}
                />
              </Card>
            )}

            {/* ── TAB PANEL: SETTINGS (GST CONFIGURATION) ── */}
            {activeTab === 'settings' && (
              <Box display="flex" gap={3} mt={1} width="100%" sx={{ border: 'none', background: 'transparent' }} flexDirection={{ xs: 'column', lg: 'row' }}>
                {/* Settings Sidebar */}
                <Box
                  sx={{
                    width: { xs: '100%', lg: 280 },
                    flexShrink: 0,
                    bgcolor: '#ffffff',
                    border: '1px solid #E5E7EB',
                    borderRadius: '12px',
                    p: 2,
                    maxHeight: { xs: '300px', lg: 'calc(100vh - 220px)' },
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 0.5,
                  }}
                >
                  <Typography variant="caption" fontWeight={700} color={textSecondary} sx={{ px: 1, pb: 1, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    GST Configuration Hub
                  </Typography>
                  {settingsCategories.map((c) => {
                    const active = activeSettingsSection === c.key;
                    return (
                      <Box
                        key={c.key}
                        component="button"
                        onClick={() => setActiveSettingsSection(c.key)}
                        sx={{
                          textAlign: 'left',
                          px: 1.5,
                          py: 1,
                          border: 0,
                          borderRadius: '8px',
                          backgroundColor: active ? '#f3f4f6' : 'transparent',
                          cursor: 'pointer',
                          fontSize: '0.85rem',
                          fontWeight: active ? 600 : 500,
                          color: active ? textPrimary : textSecondary,
                          transition: 'all 0.15s ease',
                          '&:hover': {
                            backgroundColor: active ? '#f3f4f6' : '#f9fafb',
                            color: textPrimary,
                          },
                        }}
                      >
                        {c.label}
                      </Box>
                    );
                  })}
                </Box>

                {/* Active Settings Detail Panel */}
                <Box
                  sx={{
                    flex: 1,
                    bgcolor: '#ffffff',
                    border: '1px solid #E5E7EB',
                    borderRadius: '12px',
                    p: 3.5,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3.5,
                    minHeight: '500px',
                  }}
                >
                  {hasDraft && (
                    <Alert 
                      severity="warning" 
                      sx={{ 
                        borderRadius: '8px', 
                        mb: 1, 
                        '& .MuiAlert-message': { 
                          width: '100%', 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: 2
                        } 
                      }}
                    >
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        You have an unsaved configuration draft from a previous session.
                      </Typography>
                      <Box display="flex" gap={1}>
                        <Button 
                          variant="contained" 
                          color="warning" 
                          size="small" 
                          onClick={handleApplyDraft}
                          sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.75rem', px: 2 }}
                        >
                          Apply Draft
                        </Button>
                        <Button 
                          variant="outlined" 
                          color="warning" 
                          size="small" 
                          onClick={handleDiscardDraft}
                          sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.75rem', px: 2 }}
                        >
                          Discard Draft
                        </Button>
                      </Box>
                    </Alert>
                  )}

                  {/* Header info for active section */}
                  <Box borderBottom="1px solid #E5E7EB" pb={2.5}>
                    <Typography variant="subtitle1" fontWeight={700} color={textPrimary} sx={{ letterSpacing: '-0.02em', mb: 0.5 }}>
                      {settingsCategories.find(c => c.key === activeSettingsSection)?.label}
                    </Typography>
                    <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.82rem' }}>
                      {settingsCategories.find(c => c.key === activeSettingsSection)?.desc}
                    </Typography>
                  </Box>

                  {/* Dynamic Panel Content */}
                  <Box flex={1}>
                    {settingsLoading ? (
                      <Box display="flex" justifyContent="center" py={8}>
                        <CircularProgress size={24} sx={{ color: '#0F172A' }} />
                      </Box>
                    ) : settingsError ? (
                      <Box textAlign="center" py={4}>
                        <Alert severity="error" sx={{ mb: 3, borderRadius: '8px' }}>{settingsError}</Alert>
                        <Button variant="outlined" size="small" onClick={fetchSettings} sx={{ textTransform: 'none', borderRadius: '8px' }}>Retry</Button>
                      </Box>
                    ) : (
                      renderSettingsPanel()
                    )}
                  </Box>

                  {/* Section Activity Log & Audit Trail */}
                  {!settingsLoading && !settingsError && settings.audit_log_enabled && (
                    <Box borderTop="1px solid #E5E7EB" pt={3.5}>
                      <Typography variant="caption" fontWeight={700} color={textSecondary} sx={{ display: 'block', mb: 1.5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Section Revision History & Audit Trail
                      </Typography>
                      {auditLog.filter(log => log.sectionKey === activeSettingsSection || (!log.sectionKey && activeSettingsSection === 'identity')).length > 0 ? (
                        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: 'none' }}>
                          <Table size="small">
                            <TableHead>
                              <TableRow sx={{ bgcolor: '#f9fafc' }}>
                                <TableCell sx={{ fontWeight: 600, py: 1, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', width: '150px' }}>Timestamp</TableCell>
                                <TableCell sx={{ fontWeight: 600, py: 1, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB', width: '100px' }}>User</TableCell>
                                <TableCell sx={{ fontWeight: 600, py: 1, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Action</TableCell>
                                <TableCell sx={{ fontWeight: 600, py: 1, fontSize: '0.75rem', borderBottom: '1px solid #E5E7EB' }}>Details</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {auditLog
                                .filter(log => log.sectionKey === activeSettingsSection || (!log.sectionKey && activeSettingsSection === 'identity'))
                                .map((log) => (
                                  <TableRow key={log.id}>
                                    <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                      {new Date(log.timestamp).toLocaleString('en-IN')}
                                    </TableCell>
                                    <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', fontWeight: 600 }}>
                                      {log.user}
                                    </TableCell>
                                    <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem' }}>
                                      {log.action}
                                    </TableCell>
                                    <TableCell sx={{ py: 1, borderBottom: '1px solid #E5E7EB', fontSize: '0.75rem', color: textSecondary }}>
                                      {log.details}
                                    </TableCell>
                                  </TableRow>
                                ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      ) : (
                        <Typography variant="body2" color={textSecondary} sx={{ fontSize: '0.75rem', fontStyle: 'italic' }}>
                          No edits have been recorded for this section yet.
                        </Typography>
                      )}
                    </Box>
                  )}

                  {/* Actions Bar */}
                  {!settingsLoading && !settingsError && (
                    <Box borderTop="1px solid #E5E7EB" pt={3} display="flex" justifyContent="space-between" alignItems="center">
                      <Button
                        variant="text"
                        onClick={handleResetToDefaults}
                        sx={{
                          textTransform: 'none',
                          color: '#ef4444',
                          fontWeight: 600,
                          fontSize: '0.85rem',
                          borderRadius: '8px',
                          '&:hover': { bgcolor: 'rgba(239, 68, 68, 0.05)' },
                        }}
                      >
                        Reset to Defaults
                      </Button>
                      <Box display="flex" gap={2}>
                        <Button
                          variant="outlined"
                          onClick={handleSaveDraft}
                          sx={{
                            textTransform: 'none',
                            borderColor: '#E5E7EB',
                            color: textPrimary,
                            fontWeight: 600,
                            fontSize: '0.85rem',
                            borderRadius: '8px',
                            '&:hover': {
                              borderColor: '#cbd5e1',
                              bgcolor: '#f9fafb',
                            },
                          }}
                        >
                          Save Draft
                        </Button>
                        <Button
                          onClick={handleSaveAllSettings}
                          disabled={settingsSaving}
                          variant="contained"
                          sx={{
                            textTransform: 'none',
                            bgcolor: '#0F172A',
                            color: '#ffffff',
                            fontWeight: 600,
                            fontSize: '0.85rem',
                            borderRadius: '8px',
                            boxShadow: 'none',
                            '&:hover': { bgcolor: '#1E293B' },
                          }}
                        >
                          {settingsSaving ? 'Saving...' : 'Save Configurations'}
                        </Button>
                      </Box>
                    </Box>
                  )}
                </Box>
              </Box>
            )}

            {/* ── Day 2 Return Preparation & Compliance Dashboards ── */}
            {activeTab === 'summary' && renderSummaryPage()}
            {activeTab === 'liability' && renderLiabilityPage()}
            {activeTab === 'gstr1' && renderGstr1Page()}
            {activeTab === 'gstr3b' && renderGstr3bPage()}
            {activeTab === 'itc' && renderItcPage()}
            {activeTab === 'calendar' && renderCalendarPage()}
            {activeTab === 'history' && renderHistoryPage()}
            {activeTab === 'health' && renderHealthPage()}
          </Box>
        </Box>
      </Box>

      {/* ── Snackbar Toast Notifications ── */}
      <Snackbar
        open={toast.open}
        autoHideDuration={4000}
        onClose={() => setToast({ ...toast, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setToast({ ...toast, open: false })}
          severity={toast.severity}
          variant="filled"
          sx={{ width: '100%', borderRadius: '8px' }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}

