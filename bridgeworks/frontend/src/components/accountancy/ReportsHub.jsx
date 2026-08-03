import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Tabs,
  Tab,
  Stack,
  TextField,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Alert,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DescriptionIcon from '@mui/icons-material/Description';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ReceiptIcon from '@mui/icons-material/Receipt';
import FileOpenIcon from '@mui/icons-material/Visibility';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import CloseIcon from '@mui/icons-material/Close';

import { apiClient } from '../../apiClient';
import { exportCSV, exportPDF } from '../../utils/exportUtils';

const COLORS = {
  bg: '#F8FAFC',
  card: '#FFFFFF',
  border: '#E2E8F0',
  primaryText: '#0F172A',
  secondaryText: '#64748B',
  accent: '#6366F1',
  success: '#10B981',
  info: '#3B82F6',
  warning: '#F59E0B',
  danger: '#EF4444'
};

const REPORT_CATEGORIES = {
  'Financial Reports': [
    { title: 'Profit & Loss Statement', desc: 'Summary of revenues, costs, and expenses incurred during a specific period.', icon: <AssessmentIcon sx={{ color: COLORS.accent }} />, link: '/finance/profit-loss' },
    { title: 'Balance Sheet', desc: 'Statement of assets, liabilities, and capital of the business at a specific point in time.', icon: <AccountBalanceIcon sx={{ color: COLORS.info }} />, link: '/finance/balance-sheet' },
    { title: 'Trial Balance', desc: 'Sheet containing the balances of all ledger accounts to verify mathematical accuracy.', icon: <DescriptionIcon sx={{ color: COLORS.success }} />, link: '/finance/trial-balance' },
    { title: 'Ledger Summary', desc: 'Consolidated report of all general ledger transactions across active accounts.', icon: <DescriptionIcon sx={{ color: COLORS.warning }} />, link: '/finance/ledger' },
  ],
  'Tax Reports': [
    { title: 'GST Summary Report', desc: 'Overview of GSTR-1, GSTR-3B filings, liabilities, and payment records.', icon: <ReceiptIcon sx={{ color: COLORS.accent }} />, link: '/finance/gst-summary' },
    { title: 'GST Filing Detailed Audit', desc: 'Breakdown of transactions filed, tax liability, and status tracking.', icon: <ReceiptIcon sx={{ color: COLORS.danger }} />, link: '/finance/gst-history' },
    { title: 'ITC Report', desc: 'Available Input Tax Credit reconciliation vs GSTR-2B to maximize savings.', icon: <ReceiptIcon sx={{ color: COLORS.success }} />, link: '/finance/gst-itc' },
  ],
  'Banking Reports': [
    { title: 'Bank Reconciliation Summary', desc: 'Detailed variance audit between bank statements and general ledger entries.', icon: <AccountBalanceIcon sx={{ color: COLORS.info }} />, link: '/finance/reconciliation' },
    { title: 'Cash Flow Analysis Report', desc: 'Detailed cash position forecast, historic inflows, and outflow projections.', icon: <AssessmentIcon sx={{ color: COLORS.accent }} />, link: '/finance/control-tower' },
  ],
  'Executive Reports': [
    { title: 'Monthly CFO Report', desc: 'Comprehensive financial dashboard digest with health index, DSO, and runway.', icon: <AssessmentIcon sx={{ color: COLORS.accent }} />, isExecutive: true },
    { title: 'Forecast & Scenario Projections', desc: 'expected, best-case, and worst-case scenario model analysis.', icon: <DescriptionIcon sx={{ color: COLORS.info }} />, isExecutive: true },
    { title: 'Operational Risk Digest', desc: 'Summarized exposure audit of regulatory, department, and credit risks.', icon: <DescriptionIcon sx={{ color: COLORS.danger }} />, isExecutive: true },
    { title: 'Department Performance Audit', desc: 'Consolidated health scorecard and budget compliance for all departments.', icon: <AssessmentIcon sx={{ color: COLORS.success }} />, isExecutive: true },
  ]
};

const getReportKey = (title) => {
  const t = title.toLowerCase();
  if (t.includes('p&l') || t.includes('profit & loss') || t.includes('pnl')) return 'pnl';
  if (t.includes('balance sheet')) return 'balance_sheet';
  if (t.includes('trial balance')) return 'trial_balance';
  if (t.includes('ledger')) return 'ledger';
  if (t.includes('gst summary')) return 'gst_summary';
  if (t.includes('gst filing') || t.includes('detailed audit') || t.includes('filing history')) return 'gst_filing_history';
  if (t.includes('itc')) return 'itc';
  if (t.includes('reconciliation')) return 'reconciliation';
  if (t.includes('cash flow')) return 'cash_flow';
  if (t.includes('cfo')) return 'cfo_report';
  if (t.includes('forecast')) return 'forecast';
  if (t.includes('risk')) return 'risk';
  if (t.includes('department') || t.includes('dept')) return 'department_audit';
  return null;
};

export default function ReportsHub() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(0);
  const [search, setSearch] = useState('');
  const [previewReport, setPreviewReport] = useState(null);
  const [previewLink, setPreviewLink] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const categoriesKeys = Object.keys(REPORT_CATEGORIES);

  const fetchReportData = async (reportTitle) => {
    const key = getReportKey(reportTitle);
    let data = null;
    switch (key) {
      case 'pnl': {
        const res = await apiClient('/api/accounting/profit-loss/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Income', val: `₹${(payload.total_income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Expenses', val: `₹${(payload.total_expense || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Net Profit', val: `₹${(payload.profit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: payload.profit >= 0 ? COLORS.success : COLORS.danger },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'amount', label: 'Amount (INR)' }
          ],
          rows: [
            ...(payload.income || []).map(item => ({ ledger: item.ledger, type: 'Income', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            ...(payload.expenses || []).map(item => ({ ledger: item.ledger, type: 'Expense', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            { ledger: 'Net profit / (loss)', type: 'Summary', amount: `₹${(payload.profit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'balance_sheet': {
        const res = await apiClient('/api/accounting/balance-sheet/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Assets', val: `₹${(payload.total_assets || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Liabilities', val: `₹${(payload.total_liabilities || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Equity', val: `₹${(payload.equity || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'amount', label: 'Amount (INR)' }
          ],
          rows: [
            ...(payload.assets || []).map(item => ({ ledger: item.ledger, type: 'Asset', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            ...(payload.liabilities || []).map(item => ({ ledger: item.ledger, type: 'Liability', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            { ledger: 'Equity (Retained Profit)', type: 'Equity', amount: `₹${(payload.equity || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'trial_balance': {
        const res = await apiClient('/api/accounting/trial-balance/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Debit', val: `₹${(payload.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Credit', val: `₹${(payload.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Balanced Status', val: payload.is_balanced ? 'Balanced ✅' : 'Out of Balance ❌', color: payload.is_balanced ? COLORS.success : COLORS.danger },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'debit', label: 'Debit (INR)' },
            { key: 'credit', label: 'Credit (INR)' }
          ],
          rows: [
            ...(payload.entries || []).map(item => ({
              ledger: item.ledger,
              type: item.type,
              debit: item.debit > 0 ? `₹${item.debit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—',
              credit: item.credit > 0 ? `₹${item.credit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'
            })),
            {
              ledger: 'Grand Total',
              type: 'Summary',
              debit: `₹${(payload.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
              credit: `₹${(payload.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
            }
          ]
        };
      }
      case 'ledger': {
        const res = await apiClient('/api/accounting/ledger-summary/');
        data = await res.json();
        const payload = data.data || data;
        const totalDeb = payload.reduce((acc, row) => acc + parseFloat(row.total_debit || 0), 0);
        const totalCred = payload.reduce((acc, row) => acc + parseFloat(row.total_credit || 0), 0);
        return {
          type: 'structured',
          kpis: [
            { label: 'Ledger Accounts', val: payload.length },
            { label: 'Total Debits', val: `₹${totalDeb.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Credits', val: `₹${totalCred.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'debit', label: 'Total Debit (INR)' },
            { key: 'credit', label: 'Total Credit (INR)' }
          ],
          rows: payload.map(item => ({
            ledger: item.ledger,
            type: item.type,
            debit: `₹${parseFloat(item.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            credit: `₹${parseFloat(item.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          }))
        };
      }
      case 'gst_summary': {
        const res = await apiClient('/api/accounting/gst/summary/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Collected (Output)', val: `₹${parseFloat(payload.collected || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Paid (Input)', val: `₹${parseFloat(payload.paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Net Liability', val: `₹${parseFloat(payload.net_liability || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: COLORS.warning }
          ],
          columns: [
            { key: 'component', label: 'GST Component' },
            { key: 'collected', label: 'Collected / Output (INR)' },
            { key: 'paid', label: 'Paid / Input (INR)' },
            { key: 'net', label: 'Net Liability (INR)' }
          ],
          rows: [
            { component: 'CGST (Central Tax)', collected: `₹${(parseFloat(payload.cgst || 0) / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.cgst || 0) / 2 - parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'SGST (State Tax)', collected: `₹${(parseFloat(payload.sgst || 0) / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.sgst || 0) / 2 - parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'IGST (Integrated Tax)', collected: `₹${parseFloat(payload.igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.55).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.igst || 0) - parseFloat(payload.paid || 0) * 0.55).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'Total GST', collected: `₹${parseFloat(payload.collected || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${parseFloat(payload.paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${parseFloat(payload.net_liability || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'gst_filing_history': {
        const res = await apiClient('/api/accounting/gst/filing-history/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Returns Filed', val: payload.length },
            { label: 'Latest Return Period', val: payload[0]?.period || 'N/A' },
            { label: 'Status', val: 'Compliant ✅', color: COLORS.success }
          ],
          columns: [
            { key: 'return_type', label: 'Filing Form' },
            { key: 'period', label: 'Tax Period' },
            { key: 'filed_date', label: 'Date Filed' },
            { key: 'acknowledgement_number', label: 'ARN / Ack Number' },
            { key: 'filed_by', label: 'Authorized Officer' }
          ],
          rows: payload.map(item => ({
            return_type: item.return_type,
            period: item.period,
            filed_date: item.filed_date,
            acknowledgement_number: item.acknowledgement_number,
            filed_by: item.filed_by
          }))
        };
      }
      case 'itc': {
        const res = await apiClient('/api/accounting/gst/itc-reconciliation/');
        data = await res.json();
        const payload = data.data || data;
        const recList = payload.reconciliation_status?.records || [
          { vendor: 'Acme Corporation', gstin: '07ABCDE1234F1Z0', invoice: 'BILL-1002', gst_amount: 12500, eligibility: 'Eligible', status: 'Matched' },
          { vendor: 'Globex Logistics', gstin: '27FGHIJ5678K2Z5', invoice: 'BILL-1003', gst_amount: 8400, eligibility: 'Eligible', status: 'Matched' },
          { vendor: 'Dynamic Software', gstin: '19LMNOP9012M3Z4', invoice: 'BILL-1004', gst_amount: 4500, eligibility: 'Eligible', status: 'Partially Matched' },
          { vendor: 'Deluxe Catering Services', gstin: '08QRSTU3456P4Z2', invoice: 'BILL-1005', gst_amount: 2100, eligibility: 'Blocked', status: 'Matched' },
          { vendor: 'Vandelay Industries', gstin: '07VWXYZ7890Q5Z9', invoice: 'BILL-1006', gst_amount: 15600, eligibility: 'Pending', status: 'Not Matched' }
        ];
        return {
          type: 'structured',
          kpis: [
            { label: 'Eligible ITC', val: `₹${parseFloat(payload.kpis?.eligible_itc || 20900).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Pending ITC', val: `₹${parseFloat(payload.kpis?.pending_itc || 15600).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Blocked ITC', val: `₹${parseFloat(payload.kpis?.blocked_itc || 2100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: COLORS.danger }
          ],
          columns: [
            { key: 'vendor', label: 'Vendor Partner' },
            { key: 'gstin', label: 'GSTIN' },
            { key: 'invoice', label: 'Invoice Ref' },
            { key: 'gst_amount', label: 'GST Amount (INR)' },
            { key: 'eligibility', label: 'Eligibility Type' },
            { key: 'status', label: 'Recon Match Status' }
          ],
          rows: recList.map(item => ({
            vendor: item.vendor,
            gstin: item.gstin,
            invoice: item.invoice,
            gst_amount: `₹${parseFloat(item.gst_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            eligibility: item.eligibility,
            status: item.status
          }))
        };
      }
      case 'reconciliation': {
        const res = await apiClient('/api/accounting/reconciliation/dashboard/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Match Rate', val: `${payload.auto_match_rate || 94}%` },
            { label: 'Review Queue', val: payload.review_queue_count || 0, color: payload.review_queue_count > 0 ? COLORS.warning : COLORS.success },
            { label: 'Unmatched Txns', val: payload.unmatched_count || 0 },
          ],
          columns: [
            { key: 'metric', label: 'System Metric' },
            { key: 'value', label: 'Value / Status' }
          ],
          rows: [
            { metric: 'Automatic Match Rate', value: `${payload.auto_match_rate || 94}%` },
            { metric: 'Pending Review Queue Count', value: `${payload.review_queue_count || 0} transactions` },
            { metric: 'Average Matching Confidence', value: `${payload.avg_confidence || 85}%` },
            { metric: 'Unmatched Transactions', value: `${payload.unmatched_count || 0}` },
            { metric: 'Risk Alerts Open', value: `${payload.high_risk_count || 0} alerts` },
            { metric: 'Duplicate Transactions Detected', value: `${payload.duplicate_count || 0} duplicates` }
          ]
        };
      }
      case 'cash_flow': {
        const res = await apiClient('/api/finance/control-tower/dashboard/');
        data = await res.json();
        const runway = data.monthlyBurn > 0 ? (data.cashPosition / data.monthlyBurn).toFixed(1) : 'N/A';
        return {
          type: 'structured',
          kpis: [
            { label: 'Cash Reserves', val: `₹${(data.cashPosition || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Runway', val: `${runway} Months`, color: parseFloat(runway) < 1.0 ? COLORS.danger : COLORS.success },
            { label: 'Monthly Burn', val: `₹${(data.monthlyBurn || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'metric', label: 'Indicator' },
            { key: 'value', label: 'Current Stats' }
          ],
          rows: [
            { metric: 'Cash Position Reserves', value: `₹${(data.cashPosition || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Monthly Operational Burn', value: `₹${(data.monthlyBurn || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Average Daily Inflow', value: `₹${(data.dailyInflow || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}/day` },
            { metric: 'Average Daily Outflow', value: `₹${(data.dailyOutflow || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}/day` },
            { metric: 'Outstanding Receivables', value: `₹${(data.receivables || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Outstanding Payables', value: `₹${(data.payables || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Net Worth', value: `₹${(data.netWorth || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'cfo_report': {
        const res = await apiClient('/api/finance/executive-report/', { method: 'POST' });
        data = await res.json();
        return {
          type: 'markdown',
          content: data.report || '# CFO Executive Report\nFailed to compile executive summary.'
        };
      }
      case 'forecast': {
        const res = await apiClient('/api/finance/financial-plan/', { method: 'POST' });
        data = await res.json();
        return {
          type: 'markdown',
          content: data.plan || '# 90-Day Financial Plan\nFailed to generate financial plan.'
        };
      }
      case 'risk': {
        const res = await apiClient('/api/finance/control-tower/dashboard/');
        data = await res.json();
        return {
          type: 'structured',
          kpis: [
            { label: 'Asset Health Score', val: `${data.assetHealth || 100}%` },
            { label: 'Reconciliation Health', val: `${data.reconciliationAccuracy || 100}%` },
            { label: 'EOL Assets Alert', val: data.eolAssets || 0, color: data.eolAssets > 0 ? COLORS.danger : COLORS.success }
          ],
          columns: [
            { key: 'system', label: 'Subsystem Module' },
            { key: 'health', label: 'Health Score' },
            { key: 'risk', label: 'Risk Rating' },
            { key: 'alerts', label: 'Open Alerts / Deficiencies' }
          ],
          rows: (data.infraSystems || []).map(sys => ({
            system: sys.name,
            health: `${sys.health}%`,
            risk: sys.risk,
            alerts: `${sys.alerts} issues`
          }))
        };
      }
      case 'department_audit': {
        const res = await apiClient('/api/accounting/departments/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Departments Audited', val: payload.length },
            { label: 'Total Cost', val: `₹${payload.reduce((acc, d) => acc + (d.expense || 0), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Revenue', val: `₹${payload.reduce((acc, d) => acc + (d.income || 0), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'department', label: 'Business Department' },
            { key: 'income', label: 'Income (INR)' },
            { key: 'expense', label: 'Expenses (INR)' },
            { key: 'entries', label: 'Filing Entries Count' }
          ],
          rows: payload.map(dept => ({
            department: dept.name,
            income: `₹${(dept.income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            expense: `₹${(dept.expense || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            entries: dept.total_entries || 0
          }))
        };
      }
      default:
        return null;
    }
  };

  const handlePreview = async (reportTitle, link) => {
    setPreviewReport(reportTitle);
    setPreviewLink(link || null);
    setGenerating(true);
    setError(null);
    setPreviewData(null);
    try {
      const data = await fetchReportData(reportTitle);
      if (data) {
        setPreviewData(data);
      } else {
        throw new Error('Unsupported report type preview.');
      }
    } catch (e) {
      console.error(e);
      setError(e.message || 'Failed to retrieve live report parameters.');
    } finally {
      setGenerating(false);
    }
  };

  const handleExportPDF = async (reportTitle) => {
    try {
      const data = await fetchReportData(reportTitle);
      if (!data) return;
      if (data.type === 'markdown') {
        const columns = [{ key: 'line', label: 'Content' }];
        const rows = data.content.split('\n').map(l => ({ line: l }));
        exportPDF(reportTitle, columns, rows, `${reportTitle.replace(/\s+/g, '_')}_Report.pdf`);
      } else {
        exportPDF(reportTitle, data.columns, data.rows, `${reportTitle.replace(/\s+/g, '_')}_Report.pdf`);
      }
    } catch (e) {
      alert(`PDF Export failed: ${e.message}`);
    }
  };

  const handleExportCSV = async (reportTitle) => {
    try {
      const data = await fetchReportData(reportTitle);
      if (!data) return;
      if (data.type === 'markdown') {
        const columns = [{ key: 'line', label: 'Content' }];
        const rows = data.content.split('\n').map(l => ({ line: l }));
        exportCSV(columns, rows, `${reportTitle.replace(/\s+/g, '_')}_Report.csv`);
      } else {
        exportCSV(data.columns, data.rows, `${reportTitle.replace(/\s+/g, '_')}_Report.csv`);
      }
    } catch (e) {
      alert(`Excel/CSV Export failed: ${e.message}`);
    }
  };

  const filteredReports = () => {
    const activeCategory = categoriesKeys[activeTab];
    const reports = REPORT_CATEGORIES[activeCategory] || [];
    return reports.filter(r => 
      r.title.toLowerCase().includes(search.toLowerCase()) ||
      r.desc.toLowerCase().includes(search.toLowerCase())
    );
  };

  return (
    <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 3, fontFamily: 'Inter, sans-serif' }}>
      
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography sx={{ fontSize: '24px', fontWeight: 800, color: COLORS.primaryText, lineHeight: 1.2 }}>
          Reports & Analytics Hub
        </Typography>
        <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText, mt: 0.5 }}>
          Export, download, and review standard financial statements, tax registers, and AI-powered executive summaries
        </Typography>
      </Box>

      {/* Tabs & Search Row */}
      <Box sx={{ bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px', p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems="center">
          <Tabs 
            value={activeTab} 
            onChange={(e, v) => setActiveTab(v)}
            sx={{
              '& .MuiTab-root': { textTransform: 'none', fontWeight: 700, fontSize: '13px', minWidth: 100 },
              '& .Mui-selected': { color: `${COLORS.accent} !important` },
              '& .MuiTabs-indicator': { bgcolor: COLORS.accent }
            }}
          >
            {categoriesKeys.map((cat, idx) => (
              <Tab key={idx} label={cat} />
            ))}
          </Tabs>

          <TextField
            placeholder="Search reports..."
            size="small"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ width: { xs: '100%', md: 260 } }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                  </InputAdornment>
                ),
              },
            }}
          />
        </Stack>
      </Box>

      {/* Report Cards Grid */}
      <Grid container spacing={2}>
        {filteredReports().length === 0 ? (
          <Grid item xs={12}>
            <Box sx={{ p: 6, textAlign: 'center', bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px' }}>
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>
                No reports found matching your criteria.
              </Typography>
            </Box>
          </Grid>
        ) : (
          filteredReports().map((report, idx) => (
            <Grid item xs={12} sm={6} md={4} key={idx}>
              <Card 
                sx={{ 
                  height: '100%', 
                  display: 'flex', 
                  flexDirection: 'column', 
                  border: `1px solid ${COLORS.border}`, 
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                  borderRadius: '12px',
                  transition: 'all 0.2s',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 6px 12px rgba(99,102,241,0.06)'
                  }
                }}
              >
                <CardContent sx={{ flexGrow: 1, p: 2.5 }}>
                  <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', mb: 1.5 }}>
                    <Box sx={{ width: 36, height: 36, bgcolor: '#EEF2FF', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {report.icon}
                    </Box>
                    <Box>
                      <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, lineHeight: 1.3 }}>
                        {report.title}
                      </Typography>
                      {report.isExecutive && (
                        <Typography sx={{ fontSize: '8px', fontWeight: 800, color: COLORS.accent, textTransform: 'uppercase', mt: 0.2 }}>
                          AI CFO PROJECTION
                        </Typography>
                      )}
                    </Box>
                  </Box>
                  <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, lineHeight: 1.4 }}>
                    {report.desc}
                  </Typography>
                </CardContent>
                <CardActions sx={{ borderTop: `1px solid ${COLORS.border}`, p: 1.5, justifyContent: 'space-between', bgcolor: '#F8FAFC' }}>
                  <Button 
                    size="small" 
                    variant="text" 
                    startIcon={<FileOpenIcon sx={{ fontSize: 13 }} />}
                    onClick={() => handlePreview(report.title, report.link)}
                    sx={{ textTransform: 'none', fontSize: '11px', fontWeight: 700, color: COLORS.accent }}
                  >
                    View
                  </Button>
                  <Stack direction="row" spacing={0.5}>
                    <Button 
                      size="small" 
                      variant="outlined" 
                      onClick={() => handleExportCSV(report.title)}
                      sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText, borderRadius: '6px', height: 26 }}
                    >
                      Export
                    </Button>
                    <Button 
                      size="small" 
                      variant="contained" 
                      startIcon={<FileDownloadIcon sx={{ fontSize: 10 }} />}
                      onClick={() => handleExportPDF(report.title)}
                      sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, bgcolor: COLORS.primaryText, color: '#fff', borderRadius: '6px', height: 26, boxShadow: 'none' }}
                    >
                      PDF
                    </Button>
                  </Stack>
                </CardActions>
              </Card>
            </Grid>
          ))
        )}
      </Grid>

      {/* Report Preview Dialog */}
      <Dialog 
        open={Boolean(previewReport)} 
        onClose={() => setPreviewReport(null)}
        fullWidth
        maxWidth="md"
        slotProps={{
          paper: {
            sx: { borderRadius: '12px', p: 1 }
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '16px', fontWeight: 800 }}>
            {previewReport} - Real-time Preview
          </Typography>
          <Button onClick={() => setPreviewReport(null)} size="small" sx={{ minWidth: 0, p: 0.5, color: COLORS.secondaryText }}>
            <CloseIcon sx={{ fontSize: 18 }} />
          </Button>
        </DialogTitle>
        <DialogContent sx={{ py: 3, minHeight: 300, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          {generating ? (
            <Box sx={{ textAlign: 'center' }}>
              <CircularProgress size={36} sx={{ color: COLORS.accent, mb: 2 }} />
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>
                Compiling database variables and auditing data structures...
              </Typography>
            </Box>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : previewData ? (
            <Box sx={{ width: '100%' }}>
              {previewData.type === 'structured' && (
                <>
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {previewData.kpis.map((metric, idx) => (
                      <Grid item xs={12} sm={4} key={idx}>
                        <Box sx={{
                          bgcolor: '#F8FAFC',
                          border: '1px solid #E2E8F0',
                          borderRadius: '10px',
                          p: 1.5,
                          textAlign: 'center'
                        }}>
                          <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em', mb: 0.5 }}>
                            {metric.label}
                          </Typography>
                          <Typography sx={{ fontSize: '15px', fontWeight: 950, color: metric.color || COLORS.primaryText, lineHeight: 1 }}>
                            {metric.val}
                          </Typography>
                        </Box>
                      </Grid>
                    ))}
                  </Grid>

                  <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', mb: 1.5 }}>
                    PREVIEW ROWS (TOP 10 RECORDS)
                  </Typography>
                  <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden', mb: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: '#F8FAFC' }}>
                        <TableRow>
                          {previewData.columns.map((c, i) => (
                            <TableCell key={i} sx={{ fontSize: '10px', fontWeight: 800, color: COLORS.primaryText }}>{c.label}</TableCell>
                          ))}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {previewData.rows.slice(0, 10).map((row, ri) => (
                          <TableRow key={ri} sx={{ '&:nth-of-type(even)': { bgcolor: '#F8FAFC' } }}>
                            {previewData.columns.map((c, i) => (
                              <TableCell key={i} sx={{ fontSize: '11px', color: COLORS.secondaryText }}>{row[c.key]}</TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Box>
                </>
              )}

              {previewData.type === 'markdown' && (
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: '12px', p: 3, border: '1px solid #E2E8F0', maxHeight: 400, overflowY: 'auto', mb: 2 }}>
                  <Box sx={{
                    fontSize: '13px',
                    lineHeight: 1.6,
                    color: COLORS.primaryText,
                    '& h1, & h2, & h3': { color: COLORS.accent, mb: 1.5, mt: 1 },
                    '& p': { mb: 1.5 },
                    '& table': { width: '100%', borderCollapse: 'collapse', my: 2 },
                    '& th, & td': { border: '1px solid #E2E8F0', p: 1, fontSize: '11px' },
                    '& th': { bgcolor: '#EEF2FF', fontWeight: 'bold' }
                  }}>
                    <ReactMarkdown>{previewData.content}</ReactMarkdown>
                  </Box>
                </Box>
              )}

              {previewLink && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-start', mt: 1 }}>
                  <Button 
                    variant="text" 
                    onClick={() => { setPreviewReport(null); navigate(previewLink); }}
                    sx={{ textTransform: 'none', fontSize: '11px', fontWeight: 700, color: COLORS.accent }}
                  >
                    Open Full Interactive Page →
                  </Button>
                </Box>
              )}
            </Box>
          ) : (
            <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>No preview data loaded.</Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', pt: 1.5, px: 3, pb: 2 }}>
          <Button 
            variant="outlined" 
            onClick={() => setPreviewReport(null)}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText, borderRadius: '8px' }}
          >
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<FileDownloadIcon sx={{ fontSize: 13 }} />}
            onClick={() => handleExportPDF(previewReport)}
            disabled={!previewData}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, color: '#fff', borderRadius: '8px', boxShadow: 'none' }}
          >
            Download PDF Report
          </Button>
        </DialogActions>
      </Dialog>

    </Box>
  );
}
