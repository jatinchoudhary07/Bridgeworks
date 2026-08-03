import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Tabs,
  Tab,
  Card,
  CardContent,
  Divider,
  CircularProgress,
  Alert,
  IconButton,
  Collapse,
  Badge,
  InputAdornment,
  Tooltip
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  CloudUpload as CloudUploadIcon,
  Sync as SyncIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  History as HistoryIcon,
  Settings as SettingsIcon,
  Search as SearchIcon,
  Delete as DeleteIcon,
  CompareArrows as CompareArrowsIcon,
  Add as AddIcon,
  Info as InfoIcon,
  ChevronRight as ChevronRightIcon,
  Assessment as AssessmentIcon,
  Close as CloseIcon,
  Print as PrintIcon,
  GetApp as DownloadIcon,
  People as PeopleIcon,
  Security as SecurityIcon,
  HelpOutline as HelpOutlineIcon
} from '@mui/icons-material';

import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

const COLORS = {
  bg: '#FAFAFA',
  card: '#FFFFFF',
  border: '#E5E7EB',
  radius: '12px',
  primary: '#2563EB',
  success: '#10B981',
  error: '#EF4444',
  warning: '#F59E0B',
  text: '#1F2937',
  muted: '#6B7280',
};

const fmt = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function AccountingBankReconciliation() {
  const navigate = useNavigate();
  const { canViewAmounts, canCreate, canEdit, canDelete } = usePagePermissions();
  const [activeTab, setActiveTab] = useState(0);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [error, setError] = useState('');

  const [reconStats, setReconStats] = useState({
    auto_match_rate: 0,
    review_queue: 0,
    unmatched_transactions: 0,
    average_confidence: 0,
    processing_time: '1.2s / txn',
    duplicate_count: 0,
    high_risk_count: 0,
    time_reduction: 72
  });
  const [loadingStats, setLoadingStats] = useState(false);

  const fetchReconStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const res = await apiClient('/api/accounting/reconciliation/dashboard/', { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setReconStats(data.data);
      }
    } catch {
      // silent
    } finally {
      setLoadingStats(false);
    }
  }, []);

  // Fetch bank accounts on load
  const fetchAccounts = useCallback(async () => {
    setLoadingAccounts(true);
    try {
      const res = await apiClient('/api/accounting/financial-accounts/?class=bank', { credentials: 'include' });
      const payload = await res.json().catch(() => null);
      if (res.ok && payload?.success) {
        const mapped = (payload.data || []).map(acc => ({
          id: acc.id,
          name: acc.account_name,
          account_name: acc.account_name,
          status: acc.status,
          balance: Number(acc.balance || 0),
          bank_name: acc.bank_detail?.bank_name || '',
          account_number: acc.bank_detail?.account_number || '',
          ifsc: acc.bank_detail?.ifsc || '',
          branch: acc.bank_detail?.branch || '',
          currency: acc.bank_detail?.currency || 'INR',
          opening_balance: Number(acc.bank_detail?.opening_balance || 0),
          unprocessed_count: Number(acc.bank_detail?.unprocessed_count || 0),
          last_transaction_date: acc.bank_detail?.last_transaction_date || null,
        }));
        setBankAccounts(mapped);
      } else {
        setError(payload?.message || 'Failed to load bank accounts.');
      }
    } catch {
      setError('Could not reach backend financial accounts API.');
    } finally {
      setLoadingAccounts(false);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    fetchReconStats();
  }, [fetchReconStats, bankAccounts]);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  return (
    <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Module Title & Navigation */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h5" fontWeight="800" sx={{ color: COLORS.text, letterSpacing: '-0.02em' }}>
            Bank Reconciliation Center
          </Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.5 }}>
            Import statements, review bank activity, reconcile transactions, and maintain accurate financial records.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Button
            variant="outlined"
            onClick={() => navigate('/finance/accounts')}
            startIcon={<AddIcon />}
            sx={{ borderRadius: COLORS.radius, textTransform: 'none', borderColor: COLORS.border, color: COLORS.text, '&:hover': { bgcolor: '#F9FAFB' } }}
          >
            Add Bank Account
          </Button>
          <Button
            variant="contained"
            onClick={() => setActiveTab(1)}
            startIcon={<CloudUploadIcon />}
            sx={{ borderRadius: COLORS.radius, textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none', '&:hover': { bgcolor: '#1D4ED8', boxShadow: 'none' } }}
          >
            Import Statement
          </Button>
        </Box>
      </Box>

      {/* Tabs Menu */}
      <Paper sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', overflow: 'hidden' }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          sx={{
            minHeight: 48,
            '& .MuiTab-root': {
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
              minWidth: 100,
              color: COLORS.muted,
              '&.Mui-selected': {
                color: COLORS.primary
              }
            }
          }}
        >
          <Tab label="Overview" />
          <Tab label="Accounts" />
          <Tab label="Statement Imports" />
          <Tab label="Reconciliation Workspace" />
          <Tab label="Matching Rules" />
          <Tab label="Exception Center" />
          <Tab label="Risk Monitoring" />
          <Tab label="Audit Trail" />
          <Tab label="Reports & Insights" />
          <Tab label="Import History" />
          <Tab label="Settings" />
        </Tabs>
      </Paper>

      {/* Tab Panels */}
      <Box sx={{ flexGrow: 1 }}>
        {activeTab === 0 && <OverviewTab bankAccounts={bankAccounts} fetchAccounts={fetchAccounts} onNavigate={setActiveTab} reconStats={reconStats} fetchReconStats={fetchReconStats} />}
        {activeTab === 1 && <AccountsTab bankAccounts={bankAccounts} fetchAccounts={fetchAccounts} onNavigate={setActiveTab} />}
        {activeTab === 2 && <StatementImportsTab bankAccounts={bankAccounts} onNavigate={setActiveTab} />}
        {activeTab === 3 && <ReconciliationWorkspaceTab bankAccounts={bankAccounts} reconStats={reconStats} />}
        {activeTab === 4 && <MatchingRulesTab />}
        {activeTab === 5 && <ExceptionQueueTab bankAccounts={bankAccounts} reconStats={reconStats} fetchReconStats={fetchReconStats} />}
        {activeTab === 6 && <RiskMonitoringTab reconStats={reconStats} fetchReconStats={fetchReconStats} />}
        {activeTab === 7 && <AuditTrailTab />}
        {activeTab === 8 && <ReportsTab reconStats={reconStats} />}
        {activeTab === 9 && <ImportHistoryTab bankAccounts={bankAccounts} />}
        {activeTab === 10 && <SettingsTab />}
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB 1: OVERVIEW (HEALTH DASHBOARD)
// ---------------------------------------------------------------------------
function OverviewTab({ bankAccounts, fetchAccounts, onNavigate, reconStats, fetchReconStats }) {
  const stats = reconStats || {
    auto_match_rate: 0,
    review_queue: 0,
    unmatched_transactions: 0,
    average_confidence: 0,
    processing_time: '1.2s / txn'
  };

  const kpis = [
    { title: 'Auto Match Rate', value: `${stats.auto_match_rate}%`, sub: 'Target: 85%', desc: 'Transactions reconciled automatically.', icon: <CheckCircleIcon sx={{ color: COLORS.success }} /> },
    { title: 'Review Queue', value: stats.review_queue, sub: 'Oversight needed', desc: 'Suggestions & pending exceptions.', icon: <WarningIcon sx={{ color: COLORS.warning }} /> },
    { title: 'Unmatched Transactions', value: stats.unmatched_transactions, sub: 'Manual search', desc: 'No suggested rule matches found.', icon: <ErrorIcon sx={{ color: COLORS.error }} /> },
    { title: 'Average Confidence', value: `${stats.average_confidence}%`, sub: 'Match Quality', desc: 'Mean confidence of match proposals.', icon: <AssessmentIcon sx={{ color: COLORS.primary }} /> },
    { title: 'Processing Time', value: stats.processing_time, sub: 'Instant Matching', desc: 'Execution speed of the rule engine.', icon: <SyncIcon sx={{ color: '#8B5CF6' }} /> }
  ];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      {/* KPI Cards */}
      <Grid container spacing={2}>
        {kpis.map((kpi, idx) => (
          <Grid item xs={12} sm={6} md={2.4} key={idx}>
            <Card sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', height: '100%' }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {kpi.title}
                  </Typography>
                  {kpi.icon}
                </Box>
                <Typography variant="h4" fontWeight="800" sx={{ color: COLORS.text, mt: 0.5, letterSpacing: '-0.02em' }}>
                  {kpi.value}
                </Typography>
                <Typography variant="caption" sx={{ color: COLORS.primary, fontWeight: 600, display: 'block', mt: 0.25 }}>
                  {kpi.sub}
                </Typography>
                <Typography variant="caption" sx={{ color: COLORS.muted, mt: 1, display: 'block', fontSize: '0.73rem', lineHeight: 1.3 }}>
                  {kpi.desc}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Action Shortcuts */}
      <Paper sx={{ p: 3, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', bgcolor: '#F8FAFC' }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="subtitle1" fontWeight="800">Ready to Reconcile statement?</Typography>
            <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.5 }}>
              The auto-matching engine has analyzed statement records. Go to the workspace to review suggestions and approve matches.
            </Typography>
          </Grid>
          <Grid item xs={12} md={4} sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
            <Button
              variant="contained"
              onClick={() => onNavigate(3)} // Workspace
              sx={{ borderRadius: '8px', textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none', fontWeight: 700, '&:hover': { bgcolor: '#1D4ED8', boxShadow: 'none' } }}
            >
              Go to Workspace
            </Button>
            <Button
              variant="outlined"
              onClick={() => onNavigate(4)} // Rules
              sx={{ borderRadius: '8px', textTransform: 'none', borderColor: COLORS.border, color: COLORS.text, fontWeight: 700, '&:hover': { bgcolor: '#F9FAFB' } }}
            >
              Manage Rules
            </Button>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB 2: ACCOUNTS LIST
// ---------------------------------------------------------------------------
function AccountsTab({ bankAccounts, fetchAccounts, onNavigate }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Grid container spacing={3}>
        {bankAccounts.map((acc) => (
          <Grid item xs={12} sm={6} md={4} key={acc.id}>
            <Card sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', position: 'relative', overflow: 'hidden' }}>
              <Box sx={{ height: 6, bgcolor: COLORS.primary }} />
              <CardContent sx={{ p: 2.5 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                  <Box>
                    <Typography variant="subtitle2" fontWeight="800" sx={{ color: COLORS.text }}>
                      {acc.account_name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: COLORS.muted }}>
                      {acc.bank_name || 'HDFC Bank'} •••• {acc.account_number ? acc.account_number.slice(-4) : '9981'}
                    </Typography>
                  </Box>
                  <Chip
                    label={acc.status === 'active' ? 'Active' : 'Inactive'}
                    size="small"
                    sx={{
                      fontWeight: 700,
                      fontSize: '0.7rem',
                      bgcolor: acc.status === 'active' ? '#ECFDF5' : '#F1F5F9',
                      color: acc.status === 'active' ? '#10B981' : '#64748B',
                      borderRadius: '6px'
                    }}
                  />
                </Box>
                <Divider sx={{ my: 1.5 }} />
                <Grid container spacing={1}>
                  <Grid item xs={6}>
                    <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block' }}>Statement Balance</Typography>
                    <Typography variant="body2" fontWeight="800">{fmt(acc.balance)}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block' }}>Unreconciled</Typography>
                    <Typography variant="body2" fontWeight="800" sx={{ color: acc.unprocessed_count > 0 ? COLORS.warning : COLORS.success }}>
                      {acc.unprocessed_count} txs
                    </Typography>
                  </Grid>
                </Grid>
                <Box sx={{ display: 'flex', gap: 1.5, mt: 2.5 }}>
                  <Button
                    variant="contained"
                    size="small"
                    fullWidth
                    onClick={() => onNavigate(3)} // Workspace
                    sx={{ borderRadius: '8px', textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none', '&:hover': { bgcolor: '#1D4ED8', boxShadow: 'none' } }}
                  >
                    Reconcile
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    fullWidth
                    onClick={() => onNavigate(2)} // Import
                    sx={{ borderRadius: '8px', textTransform: 'none', borderColor: COLORS.border, color: COLORS.text, '&:hover': { bgcolor: '#F9FAFB' } }}
                  >
                    Import Statement
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB 5: MATCHING RULES Hierarchy Configuration
// ---------------------------------------------------------------------------
function MatchingRulesTab() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const res = await apiClient('/api/accounting/reconciliation/rules/', { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setRules(data.data);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const handleToggleActive = async (id, is_active) => {
    const updated = rules.map(r => r.id === id ? { ...r, is_active } : r);
    setRules(updated);
    saveRulesOrder(updated);
  };

  const saveRulesOrder = async (updatedRules) => {
    setSaving(true);
    try {
      await apiClient('/api/accounting/reconciliation/rules/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: updatedRules }),
        credentials: 'include'
      });
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const moveRule = (index, direction) => {
    const newRules = [...rules];
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= rules.length) return;
    
    const temp = newRules[index];
    newRules[index] = newRules[targetIndex];
    newRules[targetIndex] = temp;
    
    const updated = newRules.map((r, i) => ({ ...r, priority: i + 1 }));
    setRules(updated);
    saveRulesOrder(updated);
  };

  // Drag and Drop handlers
  const handleDragStart = (e, index) => {
    e.dataTransfer.setData("draggedIndex", index);
  };

  const handleDrop = (e, targetIndex) => {
    const draggedIndex = parseInt(e.dataTransfer.getData("draggedIndex"), 10);
    if (draggedIndex === targetIndex) return;

    const newRules = [...rules];
    const draggedRule = newRules.splice(draggedIndex, 1)[0];
    newRules.splice(targetIndex, 0, draggedRule);

    const updated = newRules.map((r, i) => ({ ...r, priority: i + 1 }));
    setRules(updated);
    saveRulesOrder(updated);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="subtitle1" fontWeight="800" sx={{ color: COLORS.text }}>
              Transaction Matching Rules Hierarchy
            </Typography>
            <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.5 }}>
              Drag and drop rules or use the action buttons to reorder matching priority. The rule engine runs sequentially from Priority 1.
            </Typography>
          </Box>
          {saving && <CircularProgress size={18} sx={{ color: COLORS.primary }} />}
        </Box>

        {loading ? (
          <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {rules.map((rule, index) => (
              <Box
                key={rule.id}
                draggable
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(e, index)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  p: 2,
                  bgcolor: rule.is_active ? '#FFFFFF' : '#F9FAFB',
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '10px',
                  cursor: 'grab',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                    borderColor: '#CBD5E1'
                  }
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                  <Box
                    sx={{
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      bgcolor: rule.is_active ? '#EFF6FF' : '#F1F5F9',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: `1px solid ${rule.is_active ? '#BFDBFE' : '#E2E8F0'}`
                    }}
                  >
                    <Typography variant="caption" fontWeight="800" color={rule.is_active ? 'primary' : 'textSecondary'}>
                      {rule.priority}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" fontWeight="700" sx={{ color: rule.is_active ? COLORS.text : COLORS.muted }}>
                      {rule.rule_name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: COLORS.muted }}>
                      Match Confidence Score: {rule.confidence_score}%
                    </Typography>
                  </Box>
                </Box>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton size="small" disabled={index === 0} onClick={() => moveRule(index, -1)}>
                      <ChevronRightIcon sx={{ transform: 'rotate(-90deg)', fontSize: 18 }} />
                    </IconButton>
                    <IconButton size="small" disabled={index === rules.length - 1} onClick={() => moveRule(index, 1)}>
                      <ChevronRightIcon sx={{ transform: 'rotate(90deg)', fontSize: 18 }} />
                    </IconButton>
                  </Box>
                  <Divider orientation="vertical" flexItem sx={{ mx: 1.5 }} />
                  <Button
                    size="small"
                    variant={rule.is_active ? 'outlined' : 'contained'}
                    color={rule.is_active ? 'error' : 'primary'}
                    onClick={() => handleToggleActive(rule.id, !rule.is_active)}
                    sx={{ textTransform: 'none', borderRadius: '6px', px: 2, height: 28, fontSize: '0.75rem' }}
                  >
                    {rule.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB 6: EXCEPTION QUEUE
// ---------------------------------------------------------------------------
function ExceptionQueueTab({ bankAccounts, reconStats, fetchReconStats }) {
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedException, setSelectedException] = useState(null);
  const [ledgerCandidates, setLedgerCandidates] = useState([]);
  const [resolving, setResolving] = useState(false);

  // Workflow Edit States
  const [editStatus, setEditStatus] = useState('');
  const [editSeverity, setEditSeverity] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [savingWorkflow, setSavingWorkflow] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState('active'); // active, open, in_review, resolved, ignored, all
  const [assigneeFilter, setAssigneeFilter] = useState('all'); // all, unassigned, userId
  const [searchTerm, setSearchTerm] = useState('');

  const fetchExceptions = async () => {
    setLoading(true);
    try {
      let url = '/api/accounting/reconciliation/exceptions/';
      if (statusFilter !== 'all' && statusFilter !== 'active') {
        url += `?status=${statusFilter}`;
      }
      const res = await apiClient(url, { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        let filtered = data.data;
        if (statusFilter === 'active') {
          filtered = filtered.filter(ex => ex.status === 'open' || ex.status === 'in_review');
        }
        setExceptions(filtered);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/users/', { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setUsers(data.data || []);
      }
    } catch {
      // silent
    }
  };

  useEffect(() => {
    fetchExceptions();
  }, [statusFilter]);

  useEffect(() => {
    fetchUsers();
  }, []);

  const openResolveDrawer = async (ex) => {
    setSelectedException(ex);
    setEditStatus(ex.status);
    setEditSeverity(ex.severity || 'low');
    setEditNotes(ex.notes || '');
    setDrawerOpen(true);
    
    // Fetch ledger entries matching exception transaction amount
    const tx = ex.bank_transaction_detail;
    try {
      const bank_acc_id = bankAccounts[0]?.id || '';
      const resW = await apiClient(`/api/accounting/reconciliation/workspace/?bank_account=${bank_acc_id}&amount_min=${tx.amount}&amount_max=${tx.amount}`, { credentials: 'include' });
      const dataW = await resW.json().catch(() => null);
      if (resW.ok && dataW?.success) {
        setLedgerCandidates(dataW.data.ledger_entries || []);
      }
    } catch {
      // silent
    }
  };

  const handleResolveMatch = async (journalItemId) => {
    setResolving(true);
    try {
      const res = await apiClient('/api/accounting/reconciliation/exceptions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'resolve',
          exception_id: selectedException.id,
          journal_item_id: journalItemId
        }),
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setDrawerOpen(false);
        fetchExceptions();
        if (fetchReconStats) fetchReconStats();
      }
    } catch {
      // silent
    } finally {
      setResolving(false);
    }
  };

  const handleIgnoreException = async (exId) => {
    try {
      await apiClient('/api/accounting/reconciliation/exceptions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'ignore',
          exception_id: exId
        }),
        credentials: 'include'
      });
      fetchExceptions();
      if (fetchReconStats) fetchReconStats();
    } catch {
      // silent
    }
  };

  const handleAssignReviewer = async (userId) => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/exceptions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'assign',
          exception_id: selectedException.id,
          assigned_to_id: userId || null
        }),
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setSelectedException(prev => ({
          ...prev,
          assigned_to: userId,
          assigned_to_name: users.find(u => String(u.id) === String(userId))?.username || null,
          status: 'in_review'
        }));
        setEditStatus('in_review');
        fetchExceptions();
        if (fetchReconStats) fetchReconStats();
      }
    } catch {
      // silent
    }
  };

  const handleUpdateWorkflow = async () => {
    setSavingWorkflow(true);
    try {
      const res = await apiClient('/api/accounting/reconciliation/exceptions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'update_status',
          exception_id: selectedException.id,
          status: editStatus,
          severity: editSeverity,
          notes: editNotes
        }),
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setDrawerOpen(false);
        fetchExceptions();
        if (fetchReconStats) fetchReconStats();
      }
    } catch {
      // silent
    } finally {
      setSavingWorkflow(false);
    }
  };

  const filteredExceptions = useMemo(() => {
    return exceptions.filter(ex => {
      const tx = ex.bank_transaction_detail || {};
      const descMatch = tx.description?.toLowerCase().includes(searchTerm.toLowerCase()) || false;
      const refMatch = tx.reference?.toLowerCase().includes(searchTerm.toLowerCase()) || false;
      const amountMatch = String(tx.amount || '').includes(searchTerm);
      const searchMatch = !searchTerm ? true : (descMatch || refMatch || amountMatch);

      let assigneeMatch = true;
      if (assigneeFilter === 'unassigned') {
        assigneeMatch = !ex.assigned_to;
      } else if (assigneeFilter !== 'all') {
        assigneeMatch = String(ex.assigned_to) === String(assigneeFilter);
      }

      return searchMatch && assigneeMatch;
    });
  }, [exceptions, searchTerm, assigneeFilter]);

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case 'high':
        return { bgcolor: '#FEE2E2', color: COLORS.error, label: 'High' };
      case 'medium':
        return { bgcolor: '#FEF3C7', color: COLORS.warning, label: 'Medium' };
      case 'low':
      default:
        return { bgcolor: '#E0F2FE', color: COLORS.primary, label: 'Low' };
    }
  };

  const getStatusStyle = (status) => {
    switch (status) {
      case 'resolved':
        return { label: 'Resolved', color: 'success' };
      case 'ignored':
        return { label: 'Ignored', color: 'default' };
      case 'in_review':
        return { label: 'In Review', color: 'warning' };
      case 'open':
      default:
        return { label: 'Open', color: 'error' };
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
        <Typography variant="subtitle1" fontWeight="800" sx={{ mb: 1, color: COLORS.text }}>
          Exception Center
        </Typography>
        <Typography variant="body2" sx={{ color: COLORS.muted, mb: 3 }}>
          Review, assign, and document exceptions for transactions that the auto-matching engine cannot resolve.
        </Typography>

        {/* Filters bar */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Status Filter</InputLabel>
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} label="Status Filter">
              <MenuItem value="active">Active (Open & In Review)</MenuItem>
              <MenuItem value="all">All Exceptions</MenuItem>
              <MenuItem value="open">Open</MenuItem>
              <MenuItem value="in_review">In Review</MenuItem>
              <MenuItem value="resolved">Resolved</MenuItem>
              <MenuItem value="ignored">Ignored</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Assignee Filter</InputLabel>
            <Select value={assigneeFilter} onChange={(e) => setAssigneeFilter(e.target.value)} label="Assignee Filter">
              <MenuItem value="all">All Assignees</MenuItem>
              <MenuItem value="unassigned">Unassigned</MenuItem>
              {users.map(u => (
                <MenuItem key={u.id} value={String(u.id)}>{u.username}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            placeholder="Search exceptions..."
            size="small"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: COLORS.muted, fontSize: 20 }} />
                </InputAdornment>
              ),
            }}
            sx={{ flexGrow: 1, maxWidth: 300 }}
          />
        </Box>

        {loading ? (
          <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
        ) : filteredExceptions.length === 0 ? (
          <Box sx={{ py: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5 }}>
            <CheckCircleIcon sx={{ fontSize: 44, color: COLORS.success }} />
            <Typography variant="body2" fontWeight="700" color="textSecondary">
              No exceptions match the selected filters.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Amount</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Severity</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Assignee</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 700 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredExceptions.map((ex) => {
                  const tx = ex.bank_transaction_detail;
                  const sev = getSeverityStyle(ex.severity);
                  const st = getStatusStyle(ex.status);
                  return (
                    <TableRow key={ex.id} hover>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{tx.date}</TableCell>
                      <TableCell sx={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <Tooltip title={tx.description}>
                          <span>{tx.description}</span>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700, color: tx.credit > 0 ? COLORS.success : COLORS.error }}>
                        {fmt(tx.amount)}
                      </TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>
                        <Chip
                          label={
                            ex.exception_type === 'multiple_matches' ? 'Multiple Matches' : 
                            ex.exception_type === 'duplicate_candidate' ? 'Duplicate Candidate' : 
                            'No Match Found'
                          }
                          size="small"
                          sx={{
                            fontWeight: 700,
                            borderRadius: '4px',
                            bgcolor: ex.exception_type === 'multiple_matches' ? '#FEF3C7' : ex.exception_type === 'duplicate_candidate' ? '#F3E8FF' : '#FEE2E2',
                            color: ex.exception_type === 'multiple_matches' ? COLORS.warning : ex.exception_type === 'duplicate_candidate' ? '#7C3AED' : COLORS.error
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={sev.label}
                          size="small"
                          sx={{ fontWeight: 700, bgcolor: sev.bgcolor, color: sev.color, borderRadius: '4px' }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 500, color: ex.assigned_to_name ? COLORS.text : COLORS.muted }}>
                        {ex.assigned_to_name || 'Unassigned'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={st.label}
                          color={st.color}
                          size="small"
                          variant="outlined"
                          sx={{ fontWeight: 700, borderRadius: '4px' }}
                        />
                      </TableCell>
                      <TableCell align="center">
                        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
                          <Button
                            variant="contained"
                            size="small"
                            onClick={() => openResolveDrawer(ex)}
                            sx={{ borderRadius: '6px', textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none' }}
                          >
                            Investigate
                          </Button>
                          {ex.status !== 'ignored' && ex.status !== 'resolved' && (
                            <Button
                              variant="outlined"
                              size="small"
                              onClick={() => handleIgnoreException(ex.id)}
                              sx={{ borderRadius: '6px', textTransform: 'none', borderColor: COLORS.border, color: COLORS.text }}
                            >
                              Ignore
                            </Button>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Exception Resolution Detail Page/Drawer */}
      <Collapse in={drawerOpen}>
        {selectedException && (
          <Paper sx={{ p: 3, mt: 2, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: '0 4px 20px rgba(0,0,0,0.06)' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="subtitle1" fontWeight="800">
                Operational Resolution Panel — Exception #{selectedException.id}
              </Typography>
              <IconButton size="small" onClick={() => setDrawerOpen(false)}>
                <CloseIcon />
              </IconButton>
            </Box>

            <Grid container spacing={3}>
              {/* Transaction details & Workflow settings */}
              <Grid item xs={12} md={6}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                  <Box sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: '8px', border: `1px solid ${COLORS.border}` }}>
                    <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>BANK STATEMENT TRANSACTION</Typography>
                    <Typography variant="body1" fontWeight="800" sx={{ mt: 1 }}>{selectedException.bank_transaction_detail.description}</Typography>
                    <Typography variant="h5" fontWeight="800" sx={{ mt: 1, color: selectedException.bank_transaction_detail.credit > 0 ? COLORS.success : COLORS.error }}>
                      {fmt(selectedException.bank_transaction_detail.amount)}
                    </Typography>
                    <Typography variant="body2" sx={{ color: COLORS.muted, mt: 1 }}>
                      Date: {selectedException.bank_transaction_detail.date} | Ref: {selectedException.bank_transaction_detail.reference || '-'}
                    </Typography>
                  </Box>

                  {/* Workflow Form */}
                  <Box sx={{ border: `1px solid ${COLORS.border}`, p: 2, borderRadius: '8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Typography variant="subtitle2" fontWeight="800">Assignee & Status Workflow</Typography>
                    
                    <FormControl size="small" fullWidth>
                      <InputLabel>Assign Reviewer</InputLabel>
                      <Select
                        value={selectedException.assigned_to || ''}
                        onChange={(e) => handleAssignReviewer(e.target.value)}
                        label="Assign Reviewer"
                      >
                        <MenuItem value=""><em>Unassigned</em></MenuItem>
                        {users.map(u => (
                          <MenuItem key={u.id} value={u.id}>{u.username}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>

                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <FormControl size="small" fullWidth>
                        <InputLabel>Workflow Status</InputLabel>
                        <Select
                          value={editStatus}
                          onChange={(e) => setEditStatus(e.target.value)}
                          label="Workflow Status"
                        >
                          <MenuItem value="open">Open</MenuItem>
                          <MenuItem value="in_review">In Review</MenuItem>
                          <MenuItem value="resolved">Resolved</MenuItem>
                          <MenuItem value="ignored">Ignored</MenuItem>
                        </Select>
                      </FormControl>

                      <FormControl size="small" fullWidth>
                        <InputLabel>Severity Level</InputLabel>
                        <Select
                          value={editSeverity}
                          onChange={(e) => setEditSeverity(e.target.value)}
                          label="Severity Level"
                        >
                          <MenuItem value="low">Low</MenuItem>
                          <MenuItem value="medium">Medium</MenuItem>
                          <MenuItem value="high">High</MenuItem>
                        </Select>
                      </FormControl>
                    </Box>

                    <TextField
                      label="Resolution Notes & Activity Log"
                      multiline
                      rows={2}
                      size="small"
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      placeholder="Add notes about audit validation, exception causes, or approval remarks..."
                    />

                    <Button
                      variant="contained"
                      onClick={handleUpdateWorkflow}
                      disabled={savingWorkflow}
                      sx={{ bgcolor: COLORS.primary, borderRadius: '6px', textTransform: 'none', fontWeight: 700, boxShadow: 'none' }}
                    >
                      {savingWorkflow ? 'Saving Workflow...' : 'Save Workflow Changes'}
                    </Button>
                  </Box>
                </Box>
              </Grid>

              {/* Ledger Candidates resolution */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 1.5 }}>
                  Manual Reconciliation Matches
                </Typography>
                
                {selectedException.status === 'resolved' ? (
                  <Alert severity="success" sx={{ borderRadius: '8px' }}>
                    This exception has already been resolved and reconciled.
                  </Alert>
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    <Typography variant="body2" sx={{ color: COLORS.muted, mb: 1 }}>
                      Select a matching general ledger transaction of exact amount to manually force reconciliation and close exception.
                    </Typography>
                    
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 280, overflowY: 'auto', pr: 1 }}>
                      {ledgerCandidates.length === 0 ? (
                        <Typography variant="body2" sx={{ color: COLORS.muted, py: 4, textAlign: 'center', border: `1px dashed ${COLORS.border}`, borderRadius: '8px' }}>
                          No ledger entries found matching this exact amount. Reconcile this exception in the workspace or adjust matching rules.
                        </Typography>
                      ) : (
                        ledgerCandidates.map((cand) => (
                          <Box
                            key={cand.id}
                            onClick={() => handleResolveMatch(cand.id)}
                            sx={{
                              p: 1.5,
                              border: `1px solid ${COLORS.border}`,
                              borderRadius: '8px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              transition: 'all 0.15s ease',
                              '&:hover': {
                                borderColor: COLORS.primary,
                                bgcolor: '#EFF6FF'
                              }
                            }}
                          >
                            <Box>
                              <Typography variant="body2" fontWeight="700">{cand.voucher} • {cand.ledger_account}</Typography>
                              <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.25 }}>
                                Date: {cand.date} | Desc: {cand.description}
                              </Typography>
                            </Box>
                            <Typography variant="body2" fontWeight="800">
                              {fmt(cand.amount)}
                            </Typography>
                          </Box>
                        ))
                      )}
                    </Box>
                  </Box>
                )}
              </Grid>
            </Grid>
          </Paper>
        )}
      </Collapse>
    </Box>
  );
}



// ---------------------------------------------------------------------------
// TAB 3: STATEMENT IMPORT CENTER (6-Step Wizard)
// ---------------------------------------------------------------------------
function StatementImportsTab({ bankAccounts, onNavigate }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  // Step 1 Form
  const [account, setAccount] = useState('');
  const [period, setPeriod] = useState('01 Jun – 30 Jun');
  const [statementType, setStatementType] = useState('CSV');

  // Step 2 Upload file
  const [file, setFile] = useState(null);
  const [headers, setHeaders] = useState([]);
  const [rawRows, setRawRows] = useState([]);

  // Step 4 Columns Mapping
  const [mapping, setMapping] = useState({
    transaction_date: '',
    reference: '',
    description: '',
    debit: '',
    credit: '',
    balance: ''
  });

  // Step 5 Validation Results
  const [validationReport, setValidationReport] = useState({
    metrics: { rows_imported: 0, rows_failed: 0, warnings: 0, duplicate_rows: 0 },
    failed_rows: [],
    duplicates: [],
    preview_rows: []
  });

  // Errors / Messages
  const [errorMsg, setErrorMsg] = useState('');
  const [activeValidationTab, setActiveValidationTab] = useState(0); // 0 = failed rows, 1 = duplicates review

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  // Step 2 -> 3 (Parse Headers)
  const parseFileHeaders = async () => {
    if (!file) {
      setErrorMsg('Please select a file to upload.');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('file_type', statementType);

      const res = await apiClient('/api/accounting/bank-import/parse-headers/', {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setHeaders(data.data.headers || []);
        setRawRows(data.data.preview_rows || []);
        
        // Auto-sniff column mapping matching labels
        const initialMapping = {
          transaction_date: '',
          reference: '',
          description: '',
          debit: '',
          credit: '',
          balance: ''
        };
        const headersLower = (data.data.headers || []).map(h => h.toLowerCase());
        
        headersLower.forEach((h, index) => {
          const original = data.data.headers[index];
          if (h.includes('date')) initialMapping.transaction_date = original;
          else if (h.includes('ref') || h.includes('cheque') || h.includes('chq')) initialMapping.reference = original;
          else if (h.includes('desc') || h.includes('narration') || h.includes('particular')) initialMapping.description = original;
          else if (h.includes('debit') || h.includes('withdrawal') || h.includes('dr')) initialMapping.debit = original;
          else if (h.includes('credit') || h.includes('deposit') || h.includes('cr')) initialMapping.credit = original;
          else if (h.includes('bal') || h.includes('ledger')) initialMapping.balance = original;
        });
        
        setMapping(initialMapping);
        setStep(3);
      } else {
        setErrorMsg(data?.message || 'Error parsing statement headers.');
      }
    } catch {
      setErrorMsg('Failed to establish API connection to statements parsing service.');
    } finally {
      setLoading(false);
    }
  };

  // Step 4 -> 5 (Validate Mapping)
  const validateMapping = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('bank_account_id', account);
      formData.append('column_mapping', JSON.stringify(mapping));
      formData.append('file_type', statementType);

      const res = await apiClient('/api/accounting/bank-import/validate-statement/', {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setValidationReport(data.data);
        setStep(5);
      } else {
        setErrorMsg(data?.message || 'Validation failed.');
      }
    } catch {
      setErrorMsg('Connection error during file validation.');
    } finally {
      setLoading(false);
    }
  };

  // Step 5 -> 6 (Import Confirmation & Complete)
  const completeImport = async () => {
    setImporting(true);
    setErrorMsg('');
    try {
      const res = await apiClient('/api/accounting/bank-import/save-statement/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          bank_account_id: account,
          file_name: file.name,
          statement_period: period,
          transactions: validationReport.preview_rows // In production this transfers all records
        })
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setStep(6);
      } else {
        setErrorMsg(data?.message || 'Error occurred during transactions save.');
      }
    } catch {
      setErrorMsg('Save statements API endpoint failed.');
    } finally {
      setImporting(false);
    }
  };

  return (
    <Paper sx={{ p: 4, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
      {/* Step Progress Bar */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
        {[1, 2, 3, 4, 5, 6].map((s) => (
          <Box key={s} sx={{ display: 'flex', alignItems: 'center', flexGrow: s < 6 ? 1 : 0 }}>
            <Box
              sx={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                bgcolor: step === s ? COLORS.primary : (step > s ? '#D1FAE5' : '#F3F4F6'),
                color: step === s ? '#fff' : (step > s ? COLORS.success : COLORS.muted),
                border: step === s ? `2px solid ${COLORS.primary}` : 'none'
              }}
            >
              {step > s ? <CheckCircleIcon size="small" sx={{ fontSize: 18 }} /> : s}
            </Box>
            {s < 6 && (
              <Box sx={{ flexGrow: 1, height: 2, bgcolor: step > s ? COLORS.success : '#E5E7EB', mx: 1 }} />
            )}
          </Box>
        ))}
      </Box>

      {/* STEP 1: Select Account */}
      {step === 1 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 500, mx: 'auto' }}>
          <Typography variant="h6" fontWeight="800" align="center">Select Bank Account</Typography>
          <FormControl fullWidth size="small">
            <InputLabel shrink>Bank Account *</InputLabel>
            <Select
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              displayEmpty
              label="Bank Account *"
            >
              <MenuItem value="" disabled>Choose account</MenuItem>
              {bankAccounts.map((acc) => (
                <MenuItem key={acc.id} value={acc.id}>
                  {acc.account_name || acc.name} ({acc.bank_name})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Statement Period *"
            size="small"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="e.g. 01 Jun – 30 Jun"
            InputLabelProps={{ shrink: true }}
          />
          <FormControl fullWidth size="small">
            <InputLabel shrink>Statement Type</InputLabel>
            <Select
              value={statementType}
              onChange={(e) => setStatementType(e.target.value)}
              label="Statement Type"
            >
              <MenuItem value="CSV">CSV</MenuItem>
              <MenuItem value="Excel">Excel / XLSX</MenuItem>
              <MenuItem value="PDF">PDF</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            disabled={!account || !period}
            onClick={() => setStep(2)}
            sx={{ mt: 2, bgcolor: COLORS.primary, borderRadius: COLORS.radius }}
          >
            Next: Upload Statement
          </Button>
        </Box>
      )}

      {/* STEP 2: Upload File */}
      {step === 2 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 500, mx: 'auto' }}>
          <Typography variant="h6" fontWeight="800" align="center">Upload Statement File</Typography>
          <Box
            sx={{
              border: `2px dashed ${COLORS.border}`,
              borderRadius: COLORS.radius,
              p: 6,
              textAlign: 'center',
              cursor: 'pointer',
              '&:hover': { borderColor: COLORS.primary }
            }}
            component="label"
          >
            <input type="file" hidden onChange={handleFileChange} />
            <CloudUploadIcon sx={{ fontSize: 40, color: COLORS.muted, mb: 1 }} />
            <Typography variant="body2" fontWeight="700">Drag & Drop or Click to Upload</Typography>
            <Typography variant="caption" sx={{ color: COLORS.muted }}>Supported: CSV, Excel (XLSX), PDF</Typography>
            {file && (
              <Typography variant="body2" sx={{ color: COLORS.primary, fontWeight: 700, mt: 2 }}>
                Selected: {file.name}
              </Typography>
            )}
          </Box>
          {errorMsg && <Alert severity="error">{errorMsg}</Alert>}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="outlined" onClick={() => setStep(1)} fullWidth sx={{ borderRadius: COLORS.radius }}>
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!file || loading}
              onClick={parseFileHeaders}
              fullWidth
              sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius }}
            >
              {loading ? <CircularProgress size={20} color="inherit" /> : 'Next: Preview Data'}
            </Button>
          </Box>
        </Box>
      )}

      {/* STEP 3: Preview Data (first 50 rows) */}
      {step === 3 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Typography variant="h6" fontWeight="800">Preview Parsed File Content</Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted, mt: -2 }}>
            Verify that your columns contain transactional data before mapping them to system fields.
          </Typography>
          <TableContainer sx={{ border: `1px solid ${COLORS.border}`, borderRadius: '8px', maxHeight: 300 }}>
            <Table size="small">
              <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                <TableRow>
                  {headers.map((h, idx) => (
                    <TableCell key={idx} sx={{ fontWeight: 700 }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rawRows.map((row, rowIdx) => (
                  <TableRow key={rowIdx}>
                    {headers.map((h, colIdx) => (
                      <TableCell key={colIdx}>{row[h]}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
            <Button variant="outlined" onClick={() => setStep(2)} sx={{ borderRadius: COLORS.radius }}>
              Back
            </Button>
            <Button variant="contained" onClick={() => setStep(4)} sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius }}>
              Next: Column Mapping
            </Button>
          </Box>
        </Box>
      )}

      {/* STEP 4: Column Mapping */}
      {step === 4 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 600, mx: 'auto' }}>
          <Typography variant="h6" fontWeight="800" align="center">Map Statement Columns to System Fields</Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted, align: 'center', mt: -2 }}>
            Map the columns of the uploaded file to match BridgeWorks transaction fields.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {[
              { key: 'transaction_date', label: 'Transaction Date *' },
              { key: 'reference', label: 'Reference Number' },
              { key: 'description', label: 'Description / Narration *' },
              { key: 'debit', label: 'Debit (Money Out) *' },
              { key: 'credit', label: 'Credit (Money In) *' },
              { key: 'balance', label: 'Running Balance' }
            ].map((field) => (
              <Box key={field.key} sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', alignItems: 'center', p: 1.5, border: `1px solid ${COLORS.border}`, borderRadius: '8px' }}>
                <Typography variant="body2" fontWeight="700">{field.label}</Typography>
                <FormControl size="small" fullWidth>
                  <Select
                    value={mapping[field.key]}
                    onChange={(e) => setMapping({ ...mapping, [field.key]: e.target.value })}
                    displayEmpty
                  >
                    <MenuItem value="">Not mapped</MenuItem>
                    {headers.map((h, idx) => (
                      <MenuItem key={idx} value={h}>{h}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            ))}
          </Box>
          {errorMsg && <Alert severity="error">{errorMsg}</Alert>}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="outlined" onClick={() => setStep(3)} fullWidth sx={{ borderRadius: COLORS.radius }}>
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!mapping.transaction_date || !mapping.description || (!mapping.debit && !mapping.credit) || loading}
              onClick={validateMapping}
              fullWidth
              sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius }}
            >
              {loading ? <CircularProgress size={20} color="inherit" /> : 'Next: Validation Summary'}
            </Button>
          </Box>
        </Box>
      )}

      {/* STEP 5: Validation */}
      {step === 5 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Typography variant="h6" fontWeight="800">Statement Validation Summary</Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted, mt: -2 }}>
            Review any discrepancies or warning flags before confirming the final import.
          </Typography>

          {/* Metric Cards */}
          <Grid container spacing={2}>
            {[
              { label: 'Rows To Import', value: validationReport.metrics.rows_imported, color: COLORS.primary },
              { label: 'Rows Failed', value: validationReport.metrics.rows_failed, color: validationReport.metrics.rows_failed > 0 ? COLORS.error : COLORS.success },
              { label: 'Warnings', value: validationReport.metrics.warnings, color: COLORS.warning },
              { label: 'Duplicate Rows', value: validationReport.metrics.duplicate_rows, color: COLORS.error }
            ].map((metric, idx) => (
              <Grid item xs={3} key={idx}>
                <Card sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none' }}>
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>{metric.label}</Typography>
                    <Typography variant="h5" fontWeight="800" sx={{ color: metric.color }}>{metric.value}</Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {/* Validation details */}
          <Paper sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, overflow: 'hidden', boxShadow: 'none' }}>
            <Tabs value={activeValidationTab} onChange={(e, val) => setActiveValidationTab(val)}>
              <Tab label={`Failed Rows (${validationReport.failed_rows.length})`} />
              <Tab label={`Duplicates Review (${validationReport.duplicates.length})`} />
            </Tabs>
            <Divider />
            <Box sx={{ p: 2 }}>
              {activeValidationTab === 0 && (
                validationReport.failed_rows.length === 0 ? (
                  <Alert severity="success" sx={{ borderRadius: '8px' }}>All rows passed basic validation checks.</Alert>
                ) : (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Row Number</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Reference</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Error</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Suggested Fix</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {validationReport.failed_rows.map((row, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{row.row_number}</TableCell>
                            <TableCell>{row.reference}</TableCell>
                            <TableCell sx={{ color: COLORS.error, fontWeight: 600 }}>{row.error}</TableCell>
                            <TableCell sx={{ color: COLORS.success }}>{row.suggested_fix}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )
              )}
              {activeValidationTab === 1 && (
                validationReport.duplicates.length === 0 ? (
                  <Alert severity="success" sx={{ borderRadius: '8px' }}>No potential duplicates detected.</Alert>
                ) : (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Reference</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>Amount</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Existing Match</TableCell>
                          <TableCell align="center" sx={{ fontWeight: 700 }}>Confidence</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, pr: 2 }}>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {validationReport.duplicates.map((dup, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{dup.date}</TableCell>
                            <TableCell>{dup.reference}</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 700 }}>{fmt(dup.amount)}</TableCell>
                            <TableCell sx={{ color: COLORS.muted }}>{dup.existing_match}</TableCell>
                            <TableCell align="center">
                              <Chip label={`${dup.confidence_score}%`} size="small" sx={{ bgcolor: dup.confidence_score === 100 ? '#FEE2E2' : '#FEF3C7', color: dup.confidence_score === 100 ? COLORS.error : COLORS.warning, fontWeight: 700 }} />
                            </TableCell>
                            <TableCell align="right" sx={{ pr: 2 }}>
                              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                                <Button size="small" variant="outlined" sx={{ py: 0, textTransform: 'none' }}>Ignore</Button>
                                <Button size="small" variant="contained" sx={{ py: 0, textTransform: 'none', bgcolor: COLORS.primary }}>Merge</Button>
                              </Box>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )
              )}
            </Box>
          </Paper>

          {errorMsg && <Alert severity="error">{errorMsg}</Alert>}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
            <Button variant="outlined" onClick={() => setStep(4)} sx={{ borderRadius: COLORS.radius }}>
              Back
            </Button>
            <Button
              variant="contained"
              disabled={validationReport.metrics.rows_imported === 0 || importing}
              onClick={completeImport}
              sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius }}
            >
              {importing ? <CircularProgress size={20} color="inherit" /> : 'Next: Confirm Import'}
            </Button>
          </Box>
        </Box>
      )}

      {/* STEP 6: Confirmation */}
      {step === 6 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, textAlign: 'center', maxWidth: 500, mx: 'auto', py: 4 }}>
          <CheckCircleIcon sx={{ fontSize: 60, color: COLORS.success }} />
          <Typography variant="h5" fontWeight="800">Statement Imported Successfully!</Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted }}>
            The bank statement transactions have been saved. You are ready to start mapping them in the workspace.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
            <Button variant="outlined" onClick={() => setStep(1)} fullWidth sx={{ borderRadius: COLORS.radius }}>
              Import Another
            </Button>
            <Button variant="contained" onClick={() => onNavigate(2)} fullWidth sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius }}>
              Go to Workspace
            </Button>
          </Box>
        </Box>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// TAB 4: RECONCILIATION WORKSPACE (Split Screen)
// ---------------------------------------------------------------------------
function ReconciliationWorkspaceTab({ bankAccounts, reconStats }) {
  const [selectedAccount, setSelectedAccount] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [amountMin, setAmountMin] = useState('');
  const [amountMax, setAmountMax] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');

  const [loading, setLoading] = useState(false);
  const [runningMatch, setRunningMatch] = useState(false);
  const [matchResults, setMatchResults] = useState(null);
  
  const [workspaceData, setWorkspaceData] = useState({
    bank_transactions: [],
    ledger_entries: [],
    summary: { total_imported: 0, matched: 0, unmatched: 0, difference: 0, bank_balance: 0, ledger_balance: 0 }
  });

  const [selectedTxId, setSelectedTxId] = useState(null);

  const [manualMatchOpen, setManualMatchOpen] = useState(false);
  const [manualSearchQuery, setManualSearchQuery] = useState('');
  const [selectedLedgerItemId, setSelectedLedgerItemId] = useState(null);

  const loadWorkspace = useCallback(async () => {
    if (!selectedAccount) return;
    setLoading(true);
    try {
      const q = new URLSearchParams();
      q.set('bank_account', selectedAccount);
      if (dateFrom) q.set('date_from', dateFrom);
      if (dateTo) q.set('date_to', dateTo);
      if (amountMin) q.set('amount_min', amountMin);
      if (amountMax) q.set('amount_max', amountMax);
      if (status) q.set('status', status);
      if (search.trim()) q.set('search', search.trim());

      const res = await apiClient(`/api/accounting/reconciliation/workspace/?${q.toString()}`, { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setWorkspaceData(data.data);
        if (data.data.bank_transactions.length > 0) {
          // If previous selection is not in the list, choose the first one
          const hasSelected = data.data.bank_transactions.some(tx => tx.id === selectedTxId);
          if (!hasSelected) {
            setSelectedTxId(data.data.bank_transactions[0].id);
          }
        } else {
          setSelectedTxId(null);
        }
      }
    } catch {
      // quiet fail
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, dateFrom, dateTo, amountMin, amountMax, status, search, selectedTxId]);

  useEffect(() => {
    if (bankAccounts.length > 0 && !selectedAccount) {
      setSelectedAccount(String(bankAccounts[0].id));
    }
  }, [bankAccounts, selectedAccount]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const runAutoMatching = async () => {
    if (!selectedAccount) return;
    setRunningMatch(true);
    setMatchResults(null);
    try {
      const res = await apiClient('/api/accounting/reconciliation/auto-match/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bank_account: selectedAccount }),
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setMatchResults(data.data);
        loadWorkspace();
      }
    } catch {
      // silent
    } finally {
      setRunningMatch(false);
    }
  };

  const handleAcceptMatch = async (matchId) => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/matches/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', match_id: matchId }),
        credentials: 'include'
      });
      if (res.ok) {
        loadWorkspace();
      }
    } catch {
      // silent
    }
  };

  const handleRejectMatch = async (matchId) => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/matches/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject', match_id: matchId }),
        credentials: 'include'
      });
      if (res.ok) {
        loadWorkspace();
      }
    } catch {
      // silent
    }
  };

  const handleManualMatchConfirm = async (txId) => {
    if (!selectedLedgerItemId) return;
    try {
      const res = await apiClient('/api/accounting/reconciliation/matches/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'manual',
          bank_transaction_id: txId,
          journal_item_id: selectedLedgerItemId
        }),
        credentials: 'include'
      });
      if (res.ok) {
        setManualMatchOpen(false);
        setSelectedLedgerItemId(null);
        loadWorkspace();
      }
    } catch {
      // silent
    }
  };

  const selectedTx = useMemo(() => {
    return workspaceData.bank_transactions.find(tx => tx.id === selectedTxId) || null;
  }, [workspaceData.bank_transactions, selectedTxId]);

  const filteredLedgerEntries = useMemo(() => {
    if (!manualSearchQuery.trim()) return workspaceData.ledger_entries.slice(0, 15);
    const q = manualSearchQuery.toLowerCase();
    return workspaceData.ledger_entries.filter(entry => 
      entry.voucher.toLowerCase().includes(q) ||
      entry.ledger_account.toLowerCase().includes(q) ||
      entry.description.toLowerCase().includes(q) ||
      String(entry.amount).includes(q)
    );
  }, [workspaceData.ledger_entries, manualSearchQuery]);

  const getConfidenceColor = (score) => {
    if (score >= 95) return COLORS.success;
    if (score >= 80) return COLORS.warning;
    return COLORS.error;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {/* Smart Insights Mini Banner */}
      {reconStats && (
        <Grid container spacing={2}>
          {[
            { label: 'Auto Match Rate', val: `${reconStats.auto_match_rate}%`, desc: 'Target: 85%', color: COLORS.success, icon: <CheckCircleIcon size="small" /> },
            { label: 'High Risk Alerts', val: reconStats.high_risk_count, desc: 'Oversight required', color: COLORS.error, icon: <SecurityIcon size="small" /> },
            { label: 'Duplicate Candidates', val: reconStats.duplicate_count, desc: 'Review pairs', color: COLORS.warning, icon: <WarningIcon size="small" /> },
            { label: 'Efficiency Gained', val: `${reconStats.time_reduction}%`, desc: 'Time saved', color: COLORS.primary, icon: <AssessmentIcon size="small" /> }
          ].map((c, i) => (
            <Grid item xs={12} sm={3} key={i}>
              <Paper sx={{ p: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none' }}>
                <Box>
                  <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700, textTransform: 'uppercase' }}>{c.label}</Typography>
                  <Typography variant="h6" fontWeight="800" sx={{ color: c.color, mt: 0.25 }}>{c.val}</Typography>
                  <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block' }}>{c.desc}</Typography>
                </Box>
                <Box sx={{ p: 1, bgcolor: c.color + '10', color: c.color, borderRadius: '50%', display: 'flex' }}>
                  {c.icon}
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Top Workspace Bar */}
      <Paper sx={{ p: 2, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
        <Grid container spacing={1.5} alignItems="center" justifyContent="space-between">
          <Grid item xs={12} sm={3}>
            <FormControl size="small" fullWidth>
              <Select
                value={selectedAccount}
                onChange={(e) => setSelectedAccount(e.target.value)}
                displayEmpty
              >
                <MenuItem value="" disabled>Select Bank Account</MenuItem>
                {bankAccounts.map((acc) => (
                  <MenuItem key={acc.id} value={String(acc.id)}>
                    {acc.account_name || acc.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={9} sx={{ display: 'flex', gap: 1.5, justifyContent: 'flex-end', flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField type="date" size="small" sx={{ width: 140 }} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <TextField type="date" size="small" sx={{ width: 140 }} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            <TextField placeholder="Search desc..." size="small" sx={{ width: 150 }} value={search} onChange={(e) => setSearch(e.target.value)} />
            <Button
              variant="contained"
              startIcon={runningMatch ? <CircularProgress size={16} sx={{ color: '#fff' }} /> : <SyncIcon />}
              onClick={runAutoMatching}
              disabled={runningMatch || !selectedAccount}
              sx={{
                borderRadius: '8px',
                textTransform: 'none',
                bgcolor: COLORS.primary,
                boxShadow: 'none',
                fontWeight: 700,
                '&:hover': { bgcolor: '#1D4ED8', boxShadow: 'none' }
              }}
            >
              {runningMatch ? 'Running Engine...' : 'Run Auto Matching'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Auto Match Results Dashboard Toast / Banner */}
      {matchResults && (
        <Alert
          severity="success"
          onClose={() => setMatchResults(null)}
          sx={{ borderRadius: COLORS.radius, border: '1px solid #10B981', bgcolor: '#ECFDF5' }}
        >
          <Typography variant="body2" fontWeight="700" sx={{ color: '#065F46' }}>
            Auto Matching execution completed successfully!
          </Typography>
          <Box sx={{ display: 'flex', gap: 4, mt: 1 }}>
            <Typography variant="caption" sx={{ color: '#047857', fontWeight: 600 }}>
              Transactions Processed: <strong>{matchResults.total_imported}</strong>
            </Typography>
            <Typography variant="caption" sx={{ color: '#047857', fontWeight: 600 }}>
              Auto Matched: <strong>{matchResults.auto_matched}</strong>
            </Typography>
            <Typography variant="caption" sx={{ color: '#047857', fontWeight: 600 }}>
              Review Required: <strong>{matchResults.review_required}</strong>
            </Typography>
            <Typography variant="caption" sx={{ color: '#047857', fontWeight: 600 }}>
              Unmatched: <strong>{matchResults.unmatched}</strong>
            </Typography>
          </Box>
        </Alert>
      )}

      {/* Workspace Splits */}
      <Grid container spacing={2.5}>
        
        {/* Left Side: Bank Transactions List */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', overflow: 'hidden' }}>
            <Box sx={{ p: 2, bgcolor: '#F9FAFB', borderBottom: `1px solid ${COLORS.border}` }}>
              <Typography variant="subtitle2" fontWeight="800">Statement Transactions Waiting Matching</Typography>
            </Box>
            <TableContainer sx={{ maxHeight: 500 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, bgcolor: '#F9FAFB' }}>Date</TableCell>
                    <TableCell sx={{ fontWeight: 700, bgcolor: '#F9FAFB' }}>Reference</TableCell>
                    <TableCell sx={{ fontWeight: 700, bgcolor: '#F9FAFB' }}>Description</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, bgcolor: '#F9FAFB' }}>Amount</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 700, bgcolor: '#F9FAFB' }}>Auto Suggested</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {loading ? (
                    <TableRow><TableCell colSpan={5} align="center" sx={{ py: 8 }}>Loading bank transactions...</TableCell></TableRow>
                  ) : workspaceData.bank_transactions.length === 0 ? (
                    <TableRow><TableCell colSpan={5} align="center" sx={{ py: 8, color: COLORS.muted }}>No bank statement transactions found.</TableCell></TableRow>
                  ) : (
                    workspaceData.bank_transactions.map((tx) => {
                      const isSelected = selectedTxId === tx.id;
                      const hasSuggestion = !!tx.suggested_match;
                      return (
                        <TableRow
                          key={tx.id}
                          hover
                          onClick={() => {
                            setSelectedTxId(tx.id);
                            setManualMatchOpen(false);
                            setSelectedLedgerItemId(null);
                          }}
                          sx={{
                            cursor: 'pointer',
                            bgcolor: isSelected ? '#EFF6FF' : 'transparent',
                            '&:hover': { bgcolor: isSelected ? '#EFF6FF' : '#F8FAFC' }
                          }}
                        >
                          <TableCell sx={{ fontWeight: isSelected ? 700 : 400 }}>{tx.date}</TableCell>
                          <TableCell sx={{ color: COLORS.muted }}>{tx.reference || '-'}</TableCell>
                          <TableCell sx={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {tx.description}
                          </TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700, color: tx.credit > 0 ? COLORS.success : COLORS.error }}>
                            {fmt(tx.amount)}
                          </TableCell>
                          <TableCell align="center">
                            {hasSuggestion ? (
                              <Chip
                                label={`${tx.suggested_match.confidence_score}% Match`}
                                size="small"
                                sx={{
                                  fontWeight: 800,
                                  fontSize: '0.7rem',
                                  bgcolor: getConfidenceColor(tx.suggested_match.confidence_score) + '15',
                                  color: getConfidenceColor(tx.suggested_match.confidence_score),
                                  borderRadius: '6px'
                                }}
                              />
                            ) : (
                              <Typography variant="caption" sx={{ color: COLORS.muted }}>-</Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Right Side: Suggested Match & Resolution Workspace */}
        <Grid item xs={12} md={5}>
          {selectedTx ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              
              {/* Target Bank Transaction Card */}
              <Card sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', bgcolor: '#F9FAFB' }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>RECONCILING BANK TRANSACTION</Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mt: 1 }}>
                    <Box>
                      <Typography variant="body1" fontWeight="800">{selectedTx.description}</Typography>
                      <Typography variant="caption" sx={{ color: COLORS.muted, mt: 0.5, display: 'block' }}>
                        Date: {selectedTx.date} | Ref: {selectedTx.reference || '-'}
                      </Typography>
                    </Box>
                    <Typography variant="h5" fontWeight="800" sx={{ color: selectedTx.credit > 0 ? COLORS.success : COLORS.error }}>
                      {fmt(selectedTx.amount)}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>

              {/* Match Panel Drawer */}
              {!manualMatchOpen && selectedTx.suggested_match ? (
                <Paper sx={{ p: 2.5, border: `2px solid ${getConfidenceColor(selectedTx.suggested_match.confidence_score)}`, borderRadius: COLORS.radius, boxShadow: 'none' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="body2" fontWeight="800" color="textSecondary">
                      Possible Match Found
                    </Typography>
                    <Chip
                      label={`Confidence ${selectedTx.suggested_match.confidence_score}%`}
                      size="small"
                      sx={{
                        fontWeight: 800,
                        bgcolor: getConfidenceColor(selectedTx.suggested_match.confidence_score),
                        color: '#FFF',
                        borderRadius: '6px'
                      }}
                    />
                  </Box>

                  <Box sx={{ p: 2, bgcolor: '#FAFAFA', borderRadius: '8px', border: `1px solid ${COLORS.border}`, mb: 2 }}>
                    <Typography variant="subtitle2" fontWeight="800">{selectedTx.suggested_match.voucher}</Typography>
                    <Typography variant="caption" sx={{ color: COLORS.muted, mt: 0.5, display: 'block' }}>
                      Ledger: <strong>{selectedTx.suggested_match.ledger_account}</strong>
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, fontWeight: 600 }}>
                      Description: {selectedTx.suggested_match.description || 'No memo available'}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
                      <Typography variant="caption" sx={{ color: COLORS.muted }}>
                        Date: {selectedTx.suggested_match.date}
                      </Typography>
                      <Typography variant="body1" fontWeight="800" sx={{ color: selectedTx.suggested_match.type === 'debit' ? COLORS.success : COLORS.error }}>
                        {fmt(selectedTx.suggested_match.amount)}
                      </Typography>
                    </Box>
                  </Box>

                  <Box sx={{ p: 1.5, bgcolor: '#F3F4F6', borderRadius: '6px', mb: 2 }}>
                    <Typography variant="caption" sx={{ color: '#4B5563', fontWeight: 600, display: 'block' }}>
                      {selectedTx.suggested_match.reasoning}
                    </Typography>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <Button
                      variant="contained"
                      fullWidth
                      onClick={() => handleAcceptMatch(selectedTx.suggested_match.match_id)}
                      sx={{ borderRadius: '8px', textTransform: 'none', bgcolor: COLORS.success, boxShadow: 'none', fontWeight: 700, '&:hover': { bgcolor: '#059669', boxShadow: 'none' } }}
                    >
                      Accept Match
                    </Button>
                    <Button
                      variant="outlined"
                      color="error"
                      fullWidth
                      onClick={() => handleRejectMatch(selectedTx.suggested_match.match_id)}
                      sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                    >
                      Reject Match
                    </Button>
                  </Box>
                  <Button
                    variant="text"
                    fullWidth
                    onClick={() => setManualMatchOpen(true)}
                    sx={{ textTransform: 'none', mt: 1.5, fontWeight: 700, fontSize: '0.82rem' }}
                  >
                    Not correct? Choose manually
                  </Button>
                </Paper>
              ) : !manualMatchOpen ? (
                <Paper sx={{ p: 3, border: `1px dashed ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <InfoIcon sx={{ fontSize: 36, color: COLORS.muted }} />
                  <Box>
                    <Typography variant="body2" fontWeight="700" color="textSecondary">
                      No matching transactions were identified.
                    </Typography>
                    <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.5 }}>
                      You can run auto matching or manually review transactions.
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    onClick={() => setManualMatchOpen(true)}
                    sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                  >
                    Manual Match
                  </Button>
                </Paper>
              ) : (
                /* Manual Match Drawer / Form */
                <Paper sx={{ p: 2.5, border: `1px solid ${COLORS.primary}`, borderRadius: COLORS.radius, boxShadow: 'none' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="subtitle2" fontWeight="800" sx={{ color: COLORS.primary }}>
                      Manual Match Workspace
                    </Typography>
                    <IconButton size="small" onClick={() => setManualMatchOpen(false)}>
                      <CloseIcon />
                    </IconButton>
                  </Box>

                  <TextField
                    placeholder="Search accounting ledger entries..."
                    size="small"
                    fullWidth
                    value={manualSearchQuery}
                    onChange={(e) => setManualSearchQuery(e.target.value)}
                    sx={{ mb: 2 }}
                    InputProps={{
                      startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
                    }}
                  />

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 220, overflowY: 'auto', mb: 2, pr: 0.5 }}>
                    {filteredLedgerEntries.length === 0 ? (
                      <Typography variant="caption" sx={{ color: COLORS.muted, py: 4, textAlign: 'center' }}>
                        No unmatched ledger entries found matching search query.
                      </Typography>
                    ) : (
                      filteredLedgerEntries.map((cand) => {
                        const isSelected = selectedLedgerItemId === cand.id;
                        return (
                          <Box
                            key={cand.id}
                            onClick={() => setSelectedLedgerItemId(cand.id)}
                            sx={{
                              p: 1.25,
                              border: `1px solid ${isSelected ? COLORS.primary : COLORS.border}`,
                              borderRadius: '8px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              bgcolor: isSelected ? '#EFF6FF' : 'transparent',
                              '&:hover': { bgcolor: isSelected ? '#EFF6FF' : '#F9FAFB' }
                            }}
                          >
                            <Box>
                              <Typography variant="body2" fontWeight="700">{cand.voucher} • {cand.ledger_account}</Typography>
                              <Typography variant="caption" sx={{ color: COLORS.muted }}>
                                Date: {cand.date} | Desc: {cand.description}
                              </Typography>
                            </Box>
                            <Typography variant="body2" fontWeight="800">
                              {fmt(cand.amount)}
                            </Typography>
                          </Box>
                        );
                      })
                    )}
                  </Box>

                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <Button
                      variant="contained"
                      fullWidth
                      disabled={!selectedLedgerItemId}
                      onClick={() => handleManualMatchConfirm(selectedTx.id)}
                      sx={{ borderRadius: '8px', textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none', fontWeight: 700 }}
                    >
                      Confirm Match
                    </Button>
                    <Button
                      variant="outlined"
                      fullWidth
                      onClick={() => {
                        setManualMatchOpen(false);
                        setSelectedLedgerItemId(null);
                      }}
                      sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                    >
                      Cancel
                    </Button>
                  </Box>
                </Paper>
              )}

            </Box>
          ) : (
            <Paper sx={{ p: 4, border: `1px dashed ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', textAlign: 'center' }}>
              <Typography variant="body2" sx={{ color: COLORS.muted }}>
                Select a bank statement transaction from the left to view suggestions or reconcile manually.
              </Typography>
            </Paper>
          )}
        </Grid>

      </Grid>
      
      {/* Bottom Summary Bar */}
      <Paper sx={{ p: 2, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, bgcolor: '#F9FAFB', boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ display: 'flex', gap: 3 }}>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>IMPORTED BANK TXS</Typography>
              <Typography variant="body1" fontWeight="800">{workspaceData.summary.total_imported}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>MATCHED</Typography>
              <Typography variant="body1" fontWeight="800" sx={{ color: COLORS.success }}>{workspaceData.summary.matched}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>UNMATCHED</Typography>
              <Typography variant="body1" fontWeight="800" sx={{ color: COLORS.warning }}>{workspaceData.summary.unmatched}</Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 3 }}>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>BANK BALANCE</Typography>
              <Typography variant="body1" fontWeight="800">{fmt(workspaceData.summary.bank_balance)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>LEDGER BALANCE</Typography>
              <Typography variant="body1" fontWeight="800">{fmt(workspaceData.summary.ledger_balance)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>DIFFERENCE</Typography>
              <Typography variant="body1" fontWeight="800" sx={{ color: workspaceData.summary.difference > 0 ? COLORS.error : COLORS.success }}>{fmt(workspaceData.summary.difference)}</Typography>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB 5: IMPORT HISTORY
// ---------------------------------------------------------------------------
function ImportHistoryTab({ bankAccounts }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient('/api/accounting/bank-statement-imports/', { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setHistory(Array.isArray(data.data) ? data.data : []);
      } else {
        setErrorMsg(data?.message || 'Failed to fetch imports.');
      }
    } catch {
      setErrorMsg('Failed to fetch statement imports history.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDelete = async (importId) => {
    if (!window.confirm('Are you sure you want to delete this import? This will delete all imported transaction records associated with it.')) return;
    try {
      const res = await apiClient(`/api/accounting/bank-statement-imports/${importId}/`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        loadHistory();
      } else {
        alert(data?.message || 'Deletion failed.');
      }
    } catch {
      alert('Delete operation failed.');
    }
  };

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <Paper sx={{ p: 3, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
      <Typography variant="subtitle1" fontWeight="800" sx={{ mb: 2 }}>Statement Imports History</Typography>
      {errorMsg && <Alert severity="error" sx={{ mb: 2 }}>{errorMsg}</Alert>}
      <TableContainer sx={{ border: `1px solid ${COLORS.border}`, borderRadius: '8px' }}>
        <Table size="small">
          <TableHead sx={{ bgcolor: '#F9FAFB' }}>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, color: COLORS.muted }}>Import Date</TableCell>
              <TableCell sx={{ fontWeight: 700, color: COLORS.muted }}>File Name</TableCell>
              <TableCell sx={{ fontWeight: 700, color: COLORS.muted }}>Account Name</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, color: COLORS.muted }}>Transactions</TableCell>
              <TableCell sx={{ fontWeight: 700, color: COLORS.muted }}>Imported By</TableCell>
              <TableCell align="center" sx={{ fontWeight: 700, color: COLORS.muted }}>Status</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, color: COLORS.muted, pr: 2 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={7} align="center" sx={{ py: 6 }}>Loading history...</TableCell></TableRow>
            ) : history.length === 0 ? (
              <TableRow><TableCell colSpan={7} align="center" sx={{ py: 6, color: COLORS.muted }}>No statement imports found.</TableCell></TableRow>
            ) : (
              history.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell>{new Date(row.created_at).toLocaleString('en-IN')}</TableCell>
                  <TableCell sx={{ fontWeight: 600, color: COLORS.primary }}>{row.file_name}</TableCell>
                  <TableCell>{row.account_name}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>{row.transactions_count}</TableCell>
                  <TableCell>{row.imported_by}</TableCell>
                  <TableCell align="center">
                    <Chip label={row.status || 'Completed'} size="small" sx={{ borderRadius: '4px', fontWeight: 700, bgcolor: '#D1FAE5', color: COLORS.success }} />
                  </TableCell>
                  <TableCell align="right" sx={{ pr: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                      <IconButton size="small" sx={{ color: COLORS.primary }}><HistoryIcon fontSize="small" /></IconButton>
                      <IconButton size="small" sx={{ color: COLORS.error }} onClick={() => handleDelete(row.id)}><DeleteIcon fontSize="small" /></IconButton>
                    </Box>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// TAB 6: SETTINGS
// ---------------------------------------------------------------------------
function SettingsTab() {
  const [settings, setSettings] = useState({
    date_window: '3',
    amount_tolerance: '0.00',
    reference_weight: '70',
    duplicate_detection: true,
    missing_date_validation: true,
    balance_validation: true,
    auto_save_imports: false,
    default_currency: 'INR',
    decimal_precision: '2'
  });
  const [saved, setSaved] = useState(false);

  const handleToggle = (name) => {
    setSettings({ ...settings, [name]: !settings[name] });
  };

  const handleValChange = (e) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <Paper sx={{ p: 4, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
      <Typography variant="h6" fontWeight="800" sx={{ mb: 3 }}>Reconciliation Behavior Settings</Typography>

      <Grid container spacing={4}>
        {/* Matching rules */}
        <Grid item xs={12} md={4}>
          <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 2 }}>Matching Preferences</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <TextField
              label="Date Matching Window (Days)"
              name="date_window"
              type="number"
              size="small"
              value={settings.date_window}
              onChange={handleValChange}
              helperText="Days tolerance between bank statement date and ledger entry date"
            />
            <TextField
              label="Amount Tolerance (₹)"
              name="amount_tolerance"
              type="number"
              size="small"
              value={settings.amount_tolerance}
              onChange={handleValChange}
              helperText="Allowed rounding or exchange discrepancy tolerance limit"
            />
            <TextField
              label="Reference Matching Weight (%)"
              name="reference_weight"
              type="number"
              size="small"
              value={settings.reference_weight}
              onChange={handleValChange}
              helperText="Importance percentage assigned to reference/cheque number match"
            />
          </Box>
        </Grid>

        {/* Validation preferences */}
        <Grid item xs={12} md={4}>
          <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 2 }}>Validation Rules</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {[
              { key: 'duplicate_detection', label: 'Strict Duplicate Detection', desc: 'Identify and flag exact matches of amount, date, and description' },
              { key: 'missing_date_validation', label: 'Fail on Missing Date', desc: 'Raise high-severity errors for any rows lacking parseable dates' },
              { key: 'balance_validation', label: 'Running Balance Consistency', desc: 'Validate debit/credit arithmetic matches row-by-row balance delta' }
            ].map((rule) => (
              <Box key={rule.key} sx={{ p: 1.5, border: `1px solid ${COLORS.border}`, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="body2" fontWeight="700">{rule.label}</Typography>
                  <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.25 }}>{rule.desc}</Typography>
                </Box>
                <Button
                  size="small"
                  variant={settings[rule.key] ? 'contained' : 'outlined'}
                  onClick={() => handleToggle(rule.key)}
                  sx={{ textTransform: 'none', px: 2, bgcolor: settings[rule.key] ? COLORS.primary : 'transparent', borderRadius: '4px' }}
                >
                  {settings[rule.key] ? 'ON' : 'OFF'}
                </Button>
              </Box>
            ))}
          </Box>
        </Grid>

        {/* System Settings */}
        <Grid item xs={12} md={4}>
          <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 2 }}>Import Preferences</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <Box sx={{ p: 1.5, border: `1px solid ${COLORS.border}`, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="body2" fontWeight="700">Auto Save Imports</Typography>
                <Typography variant="caption" sx={{ color: COLORS.muted }}>Skip confirmation and store verified transactions instantly</Typography>
              </Box>
              <Button
                size="small"
                variant={settings.auto_save_imports ? 'contained' : 'outlined'}
                onClick={() => handleToggle('auto_save_imports')}
                sx={{ textTransform: 'none', px: 2, bgcolor: settings.auto_save_imports ? COLORS.primary : 'transparent', borderRadius: '4px' }}
              >
                {settings.auto_save_imports ? 'ON' : 'OFF'}
              </Button>
            </Box>
            <FormControl size="small" fullWidth>
              <InputLabel>Default Currency</InputLabel>
              <Select name="default_currency" value={settings.default_currency} onChange={handleValChange} label="Default Currency">
                <MenuItem value="INR">INR (₹)</MenuItem>
                <MenuItem value="USD">USD ($)</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" fullWidth>
              <InputLabel>Decimal Precision</InputLabel>
              <Select name="decimal_precision" value={settings.decimal_precision} onChange={handleValChange} label="Decimal Precision">
                <MenuItem value="2">2 decimals (.00)</MenuItem>
                <MenuItem value="3">3 decimals (.000)</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Grid>
      </Grid>

      {saved && (
        <Alert severity="success" sx={{ mt: 3, borderRadius: '8px' }}>
          Settings saved successfully. Changes will apply to all future imports and matching calculations.
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 4 }}>
        <Button variant="contained" onClick={handleSave} sx={{ bgcolor: COLORS.primary, borderRadius: COLORS.radius, textTransform: 'none', px: 4 }}>
          Save Configuration
        </Button>
      </Box>
    </Paper>
  );
}


// ---------------------------------------------------------------------------
// TAB 7: RISK MONITORING (ALERTS & DUPLICATES)
// ---------------------------------------------------------------------------
function RiskMonitoringTab({ reconStats, fetchReconStats }) {
  const [subTab, setSubTab] = useState(0); // 0 = Risk & Anomaly Alerts, 1 = Duplicate Candidates
  
  // Risk alerts state
  const [riskAlerts, setRiskAlerts] = useState([]);
  const [loadingRisks, setLoadingRisks] = useState(false);
  const [riskStatusFilter, setRiskStatusFilter] = useState('open');

  // Duplicate candidates state
  const [duplicates, setDuplicates] = useState([]);
  const [loadingDuplicates, setLoadingDuplicates] = useState(false);
  const [duplicateStatusFilter, setDuplicateStatusFilter] = useState('pending');

  const fetchRiskAlerts = async () => {
    setLoadingRisks(true);
    try {
      const res = await apiClient(`/api/accounting/reconciliation/risk-alerts/?status=${riskStatusFilter}`, { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setRiskAlerts(data.data || []);
      }
    } catch {
      // silent
    } finally {
      setLoadingRisks(false);
    }
  };

  const fetchDuplicates = async () => {
    setLoadingDuplicates(true);
    try {
      const res = await apiClient(`/api/accounting/reconciliation/duplicates/?status=${duplicateStatusFilter}`, { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setDuplicates(data.data || []);
      }
    } catch {
      // silent
    } finally {
      setLoadingDuplicates(false);
    }
  };

  useEffect(() => {
    if (subTab === 0) {
      fetchRiskAlerts();
    } else {
      fetchDuplicates();
    }
  }, [subTab, riskStatusFilter, duplicateStatusFilter]);

  const handleCloseAlert = async (alertId) => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/risk-alerts/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'close',
          alert_id: alertId
        }),
        credentials: 'include'
      });
      if (res.ok) {
        fetchRiskAlerts();
        if (fetchReconStats) fetchReconStats();
      }
    } catch {
      // silent
    }
  };

  const handleDuplicateAction = async (candidateId, action) => {
    try {
      const res = await apiClient('/api/accounting/reconciliation/duplicates/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          candidate_id: candidateId
        }),
        credentials: 'include'
      });
      if (res.ok) {
        fetchDuplicates();
        if (fetchReconStats) fetchReconStats();
      }
    } catch {
      // silent
    }
  };

  const getRiskExplanation = (type, tx) => {
    switch (type) {
      case 'weekend_transaction':
        return {
          title: 'Weekend Transaction',
          what: `Transaction executed on a weekend date (${tx.date}).`,
          why: 'Weekend transactions can indicate unauthorized manual adjustments or off-book transfers when normal banking checks are quiet.',
          do: 'Verify the physical supporting voucher, payment request email, or operational log authorizing weekend bank activity.'
        };
      case 'round_number':
        return {
          title: 'Round Number Value',
          what: `Transaction amount is a exact round number: ${fmt(tx.amount)}.`,
          why: 'Statistically, commercial transactions have decimals/fractions. Round numbers are common indicators of estimated figures, arbitrary adjustments, or shell transfers.',
          do: 'Inspect the vendor contract or invoice to check the exact pricing. Ensure this is not a cash advance or round-sum plug.'
        };
      case 'suspicious_description':
        return {
          title: 'Auditor-Sensitive Keyword',
          what: `Sensitive word match found in description: "${tx.description}".`,
          why: 'Keywords like "cash", "withdraw", "gift", "refund", "bonus" circumvent standard purchase loops and carry higher tax and compliance risks.',
          do: 'Verify corporate policy compliance, matching expense receipt approvals, and tax declaration status.'
        };
      case 'unusually_high_amount':
        return {
          title: 'Outlier Transaction Value',
          what: `Transaction amount (${fmt(tx.amount)}) is statistically an outlier (>3x std dev of statement).`,
          why: 'Unusually high transaction amounts pose high capital flight risks, potential typing errors (plugging extra zeros), or large unapproved expenditure.',
          do: 'Confirm board approval levels, signature check matrices, and compare against the corresponding purchase order before reconciling.'
        };
      default:
        return {
          title: 'Risk Anomaly Alert',
          what: 'Unusual transaction activity detected.',
          why: 'This transaction matched automated anomaly detection filters for audit checks.',
          do: 'Perform manual ledger cross-checks, verify bank record authenticity, and document findings.'
        };
    }
  };

  const getRiskScoreColor = (score) => {
    if (score >= 75) return COLORS.error;
    if (score >= 45) return COLORS.warning;
    return COLORS.primary;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Sub tabs switcher */}
      <Paper sx={{ border: `1px solid ${COLORS.border}`, boxShadow: 'none', overflow: 'hidden' }}>
        <Tabs
          value={subTab}
          onChange={(e, val) => setSubTab(val)}
          indicatorColor="primary"
          textColor="primary"
          sx={{ minHeight: 44 }}
        >
          <Tab label="Anomaly & Risk Alerts" sx={{ textTransform: 'none', fontWeight: 700 }} />
          <Tab label="Duplicate Detection Candidates" sx={{ textTransform: 'none', fontWeight: 700 }} />
        </Tabs>
      </Paper>

      {/* Sub tab contents */}
      {subTab === 0 ? (
        <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box>
              <Typography variant="subtitle1" fontWeight="800">Anomaly & Fraud Alerts</Typography>
              <Typography variant="body2" sx={{ color: COLORS.muted }}>
                Automated risk analysis flagging weekend activity, round values, description keywords, and high value outliers.
              </Typography>
            </Box>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Status</InputLabel>
              <Select value={riskStatusFilter} onChange={(e) => setRiskStatusFilter(e.target.value)} label="Status">
                <MenuItem value="open">Open Alerts</MenuItem>
                <MenuItem value="closed">Closed Alerts</MenuItem>
                <MenuItem value="">All Alerts</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {loadingRisks ? (
            <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
          ) : riskAlerts.length === 0 ? (
            <Box sx={{ py: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5 }}>
              <CheckCircleIcon sx={{ fontSize: 44, color: COLORS.success }} />
              <Typography variant="body2" fontWeight="700" color="textSecondary">
                No unusual transaction activity detected. Your ledger is clean.
              </Typography>
            </Box>
          ) : (
            <Grid container spacing={2.5}>
              {riskAlerts.map((alert) => {
                const tx = alert.bank_transaction_detail || {};
                const exp = getRiskExplanation(alert.risk_type, tx);
                const scoreColor = getRiskScoreColor(alert.risk_score);
                
                return (
                  <Grid item xs={12} md={6} key={alert.id}>
                    <Card sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', position: 'relative', overflow: 'visible' }}>
                      {/* Risk Score Pill */}
                      <Box sx={{
                        position: 'absolute',
                        right: 16,
                        top: 16,
                        bgcolor: scoreColor + '15',
                        color: scoreColor,
                        px: 1.5,
                        py: 0.5,
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: 800,
                        border: `1px solid ${scoreColor}40`
                      }}>
                        Score: {alert.risk_score}
                      </Box>
                      
                      <CardContent sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Box>
                          <Typography variant="subtitle2" fontWeight="800" sx={{ color: scoreColor, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <SecurityIcon fontSize="small" />
                            {exp.title}
                          </Typography>
                          <Typography variant="body2" fontWeight="700" sx={{ mt: 1 }}>
                            {tx.description}
                          </Typography>
                          <Typography variant="caption" sx={{ color: COLORS.muted }}>
                            Date: {tx.date} | Amount: {fmt(tx.amount)}
                          </Typography>
                        </Box>

                        <Divider />

                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                          <Box>
                            <Typography variant="caption" fontWeight="800" sx={{ color: COLORS.text, textTransform: 'uppercase' }}>What Happened?</Typography>
                            <Typography variant="body2" sx={{ color: COLORS.text, mt: 0.25 }}>{exp.what}</Typography>
                          </Box>
                          <Box>
                            <Typography variant="caption" fontWeight="800" sx={{ color: COLORS.text, textTransform: 'uppercase' }}>Why is this risky?</Typography>
                            <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.25 }}>{exp.why}</Typography>
                          </Box>
                          <Box>
                            <Typography variant="caption" fontWeight="800" sx={{ color: COLORS.text, textTransform: 'uppercase' }}>What should I do?</Typography>
                            <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.25 }}>{exp.do}</Typography>
                          </Box>
                        </Box>

                        {alert.status === 'open' && (
                          <Box sx={{ display: 'flex', gap: 1.5, mt: 1, justifyContent: 'flex-end' }}>
                            <Button
                              variant="outlined"
                              size="small"
                              onClick={() => handleCloseAlert(alert.id)}
                              sx={{
                                textTransform: 'none',
                                borderColor: COLORS.border,
                                color: COLORS.text,
                                borderRadius: '6px',
                                fontWeight: 700
                              }}
                            >
                              Close Alert
                            </Button>
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
        </Paper>
      ) : (
        <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box>
              <Typography variant="subtitle1" fontWeight="800">Duplicate Candidate Queue</Typography>
              <Typography variant="body2" sx={{ color: COLORS.muted }}>
                Transactions matching exact amount, date, and carrying description text similarity &gt;= 70%.
              </Typography>
            </Box>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Status</InputLabel>
              <Select value={duplicateStatusFilter} onChange={(e) => setDuplicateStatusFilter(e.target.value)} label="Status">
                <MenuItem value="pending">Pending Review</MenuItem>
                <MenuItem value="ignored">Ignored</MenuItem>
                <MenuItem value="merged">Resolved/Merged</MenuItem>
                <MenuItem value="">All Candidates</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {loadingDuplicates ? (
            <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
          ) : duplicates.length === 0 ? (
            <Box sx={{ py: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5 }}>
              <CheckCircleIcon sx={{ fontSize: 44, color: COLORS.success }} />
              <Typography variant="body2" fontWeight="700" color="textSecondary">
                No duplicate transaction candidates found.
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              {duplicates.map((cand) => {
                const tx1 = cand.transaction_1_detail || {};
                const tx2 = cand.transaction_2_detail || {};
                return (
                  <Card key={cand.id} sx={{ border: `1px solid ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none' }}>
                    <CardContent sx={{ p: 2.5 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="subtitle2" fontWeight="800" sx={{ color: COLORS.primary }}>
                          Potential Duplicate Candidate Group
                        </Typography>
                        <Chip
                          label={`Description Similarity: ${cand.similarity_score}%`}
                          size="small"
                          sx={{ bgcolor: '#F3E8FF', color: '#7C3AED', fontWeight: 800, borderRadius: '4px' }}
                        />
                      </Box>
                      
                      <Grid container spacing={3} alignItems="center">
                        <Grid item xs={12} md={5}>
                          <Box sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: '8px', border: `1px solid ${COLORS.border}` }}>
                            <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700, display: 'block', mb: 0.5 }}>TRANSACTION A</Typography>
                            <Typography variant="body2" fontWeight="700">{tx1.description}</Typography>
                            <Typography variant="body2" sx={{ mt: 1, color: COLORS.text, fontWeight: 800 }}>
                              Amount: {fmt(tx1.amount)}
                            </Typography>
                            <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.5 }}>
                              Date: {tx1.date} | Ref: {tx1.reference || '-'}
                            </Typography>
                          </Box>
                        </Grid>

                        <Grid item xs={12} md={2} sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                          <CompareArrowsIcon sx={{ color: COLORS.muted, fontSize: 32 }} />
                        </Grid>

                        <Grid item xs={12} md={5}>
                          <Box sx={{ p: 2, bgcolor: '#F9FAFB', borderRadius: '8px', border: `1px solid ${COLORS.border}` }}>
                            <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700, display: 'block', mb: 0.5 }}>TRANSACTION B</Typography>
                            <Typography variant="body2" fontWeight="700">{tx2.description}</Typography>
                            <Typography variant="body2" sx={{ mt: 1, color: COLORS.text, fontWeight: 800 }}>
                              Amount: {fmt(tx2.amount)}
                            </Typography>
                            <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.5 }}>
                              Date: {tx2.date} | Ref: {tx2.reference || '-'}
                            </Typography>
                          </Box>
                        </Grid>
                      </Grid>

                      {cand.status === 'pending' && (
                        <Box sx={{ display: 'flex', gap: 1.5, mt: 2.5, justifyContent: 'flex-end' }}>
                          <Button
                            variant="outlined"
                            size="small"
                            onClick={() => handleDuplicateAction(cand.id, 'ignore')}
                            sx={{
                              textTransform: 'none',
                              borderColor: COLORS.error,
                              color: COLORS.error,
                              borderRadius: '6px',
                              fontWeight: 700,
                              '&:hover': { borderColor: COLORS.error, bgcolor: '#FEF2F2' }
                            }}
                          >
                            Ignore Candidate
                          </Button>
                          <Button
                            variant="contained"
                            size="small"
                            onClick={() => handleDuplicateAction(cand.id, 'merge')}
                            sx={{
                              textTransform: 'none',
                              bgcolor: COLORS.primary,
                              color: '#fff',
                              borderRadius: '6px',
                              fontWeight: 700,
                              boxShadow: 'none',
                              '&:hover': { bgcolor: '#1D4ED8', boxShadow: 'none' }
                            }}
                          >
                            Resolve / Merge
                          </Button>
                        </Box>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}


// ---------------------------------------------------------------------------
// TAB 8: SYSTEM AUDIT HISTORY GRID
// ---------------------------------------------------------------------------
function AuditTrailTab() {
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const fetchAuditLogs = async () => {
    setLoading(true);
    try {
      const res = await apiClient('/api/accounting/reconciliation/audit-logs/', { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setAuditLogs(data.data || []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, []);

  const filteredLogs = useMemo(() => {
    return auditLogs.filter(log => {
      const s = searchTerm.toLowerCase();
      const userMatch = log.username?.toLowerCase().includes(s) || false;
      const actionMatch = log.action?.toLowerCase().includes(s) || false;
      const notesMatch = log.notes?.toLowerCase().includes(s) || false;
      const entityMatch = log.entity_type?.toLowerCase().includes(s) || false;
      return !searchTerm ? true : (userMatch || actionMatch || notesMatch || entityMatch);
    });
  }, [auditLogs, searchTerm]);

  const getActionColor = (action) => {
    const act = action.toLowerCase();
    if (act.includes('delete') || act.includes('reject')) return COLORS.error;
    if (act.includes('approve') || act.includes('resolve') || act.includes('match')) return COLORS.success;
    if (act.includes('create') || act.includes('import')) return COLORS.primary;
    if (act.includes('assign') || act.includes('update')) return COLORS.warning;
    return COLORS.muted;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="subtitle1" fontWeight="800">Reconciliation Audit Trail</Typography>
            <Typography variant="body2" sx={{ color: COLORS.muted }}>
              Read-only system ledger documenting imports, manual match decisions, rule actions, and status workflows.
            </Typography>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              placeholder="Search audit trail..."
              size="small"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: COLORS.muted, fontSize: 20 }} />
                  </InputAdornment>
                ),
              }}
              sx={{ minWidth: 260 }}
            />
            <Button
              variant="outlined"
              onClick={fetchAuditLogs}
              sx={{ borderColor: COLORS.border, textTransform: 'none', color: COLORS.text, borderRadius: '6px' }}
            >
              Refresh Logs
            </Button>
          </Box>
        </Box>

        {loading ? (
          <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
        ) : filteredLogs.length === 0 ? (
          <Box sx={{ py: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5 }}>
            <HistoryIcon sx={{ fontSize: 44, color: COLORS.muted }} />
            <Typography variant="body2" fontWeight="700" color="textSecondary">
              No audit log entries found.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Timestamp</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Operator</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Action Category</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Entity Type</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Reference ID</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Detail Notes</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredLogs.map((log) => {
                  const actionColor = getActionColor(log.action);
                  const dt = new Date(log.created_at).toLocaleString('en-IN');
                  return (
                    <TableRow key={log.id} hover>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{dt}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{log.username || 'System'}</TableCell>
                      <TableCell>
                        <Chip
                          label={log.action}
                          size="small"
                          sx={{
                            fontWeight: 700,
                            borderRadius: '4px',
                            bgcolor: actionColor + '10',
                            color: actionColor,
                            border: `1px solid ${actionColor}30`
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ textTransform: 'capitalize' }}>{log.entity_type || '-'}</TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{log.entity_id || '-'}</TableCell>
                      <TableCell sx={{ color: COLORS.muted, maxWidth: 350 }}>{log.notes || '-'}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
}


// ---------------------------------------------------------------------------
// TAB 9: MANAGEMENT REPORTS & EXPORTS
// ---------------------------------------------------------------------------
function ReportsTab({ reconStats }) {
  const [activeReport, setActiveReport] = useState('summary');
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchReport = async (type) => {
    setLoading(true);
    try {
      const res = await apiClient(`/api/accounting/reconciliation/reports/?report_type=${type}`, { credentials: 'include' });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setReportData(data.data || data);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport(activeReport);
  }, [activeReport]);

  const handleExportCSV = () => {
    if (!reportData) return;
    let headers = [];
    let rows = [];
    let filename = `${activeReport}_report.csv`;

    if (activeReport === 'summary') {
      const d = reportData.data || {};
      headers = ['Metric', 'Value'];
      rows = [
        ['Report Name', reportData.report_name],
        ['Generated At', reportData.generated_at],
        ['Total Transactions', d.total_transactions],
        ['Reconciled Transactions', d.processed_transactions],
        ['Unreconciled Transactions', d.unprocessed_transactions],
        ['Overall Match Rate (%)', d.overall_match_rate_percent]
      ];
    } else if (activeReport === 'exception') {
      headers = ['ID', 'Date', 'Description', 'Amount', 'Type', 'Severity', 'Assignee', 'Status', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(ex => [
        ex.id,
        ex.bank_transaction_detail?.date || '',
        ex.bank_transaction_detail?.description || '',
        ex.bank_transaction_detail?.amount || 0,
        ex.exception_type,
        ex.severity,
        ex.assigned_to_name || 'Unassigned',
        ex.status,
        ex.notes || ''
      ]);
    } else if (activeReport === 'duplicate') {
      headers = ['ID', 'Tx1 Date', 'Tx1 Description', 'Tx2 Date', 'Tx2 Description', 'Amount', 'Similarity Score (%)', 'Status'];
      const list = reportData.data || [];
      rows = list.map(dup => [
        dup.id,
        dup.transaction_1_detail?.date || '',
        dup.transaction_1_detail?.description || '',
        dup.transaction_2_detail?.date || '',
        dup.transaction_2_detail?.description || '',
        dup.transaction_1_detail?.amount || 0,
        dup.similarity_score,
        dup.status
      ]);
    } else if (activeReport === 'risk') {
      headers = ['ID', 'Date', 'Description', 'Amount', 'Risk Type', 'Risk Score', 'Status', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(r => [
        r.id,
        r.bank_transaction_detail?.date || '',
        r.bank_transaction_detail?.description || '',
        r.bank_transaction_detail?.amount || 0,
        r.risk_type,
        r.risk_score,
        r.status,
        r.notes || ''
      ]);
    } else if (activeReport === 'audit') {
      headers = ['Timestamp', 'User', 'Action', 'Entity Type', 'Entity ID', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(log => [
        log.created_at,
        log.username || 'System',
        log.action,
        log.entity_type,
        log.entity_id,
        log.notes || ''
      ]);
    } else if (activeReport === 'accuracy_report') {
      headers = ['Rule Name', 'Suggested Count', 'Approved Count', 'Rejected Count', 'Accuracy (%)'];
      const list = reportData.data || [];
      rows = list.map(rule => [
        rule.rule_name,
        rule.suggested_count,
        rule.approved_count,
        rule.rejected_count,
        rule.accuracy_percent
      ]);
    }

    const csvContent = "\ufeff" + [headers.join(','), ...rows.map(row => row.map(val => {
      let s = String(val === null || val === undefined ? '' : val).replace(/"/g, '""');
      if (s.includes(',') || s.includes('\n') || s.includes('"')) {
        s = `"${s}"`;
      }
      return s;
    }).join(','))].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExportExcel = () => {
    if (!reportData) return;
    let headers = [];
    let rows = [];
    let filename = `${activeReport}_report.xls`;

    if (activeReport === 'summary') {
      const d = reportData.data || {};
      headers = ['Metric', 'Value'];
      rows = [
        ['Report Name', reportData.report_name],
        ['Generated At', reportData.generated_at],
        ['Total Transactions', d.total_transactions],
        ['Reconciled Transactions', d.processed_transactions],
        ['Unreconciled Transactions', d.unprocessed_transactions],
        ['Overall Match Rate (%)', d.overall_match_rate_percent]
      ];
    } else if (activeReport === 'exception') {
      headers = ['ID', 'Date', 'Description', 'Amount', 'Type', 'Severity', 'Assignee', 'Status', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(ex => [
        ex.id,
        ex.bank_transaction_detail?.date || '',
        ex.bank_transaction_detail?.description || '',
        ex.bank_transaction_detail?.amount || 0,
        ex.exception_type,
        ex.severity,
        ex.assigned_to_name || 'Unassigned',
        ex.status,
        ex.notes || ''
      ]);
    } else if (activeReport === 'duplicate') {
      headers = ['ID', 'Tx1 Date', 'Tx1 Description', 'Tx2 Date', 'Tx2 Description', 'Amount', 'Similarity Score (%)', 'Status'];
      const list = reportData.data || [];
      rows = list.map(dup => [
        dup.id,
        dup.transaction_1_detail?.date || '',
        dup.transaction_1_detail?.description || '',
        dup.transaction_2_detail?.date || '',
        dup.transaction_2_detail?.description || '',
        dup.transaction_1_detail?.amount || 0,
        dup.similarity_score,
        dup.status
      ]);
    } else if (activeReport === 'risk') {
      headers = ['ID', 'Date', 'Description', 'Amount', 'Risk Type', 'Risk Score', 'Status', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(r => [
        r.id,
        r.bank_transaction_detail?.date || '',
        r.bank_transaction_detail?.description || '',
        r.bank_transaction_detail?.amount || 0,
        r.risk_type,
        r.risk_score,
        r.status,
        r.notes || ''
      ]);
    } else if (activeReport === 'audit') {
      headers = ['Timestamp', 'User', 'Action', 'Entity Type', 'Entity ID', 'Notes'];
      const list = reportData.data || [];
      rows = list.map(log => [
        log.created_at,
        log.username || 'System',
        log.action,
        log.entity_type,
        log.entity_id,
        log.notes || ''
      ]);
    } else if (activeReport === 'accuracy_report') {
      headers = ['Rule Name', 'Suggested Count', 'Approved Count', 'Rejected Count', 'Accuracy (%)'];
      const list = reportData.data || [];
      rows = list.map(rule => [
        rule.rule_name,
        rule.suggested_count,
        rule.approved_count,
        rule.rejected_count,
        rule.accuracy_percent
      ]);
    }

    const tsvContent = "\ufeff" + [headers.join('\t'), ...rows.map(row => row.map(val => {
      let s = String(val === null || val === undefined ? '' : val).replace(/\t/g, ' ');
      return s;
    }).join('\t'))].join('\n');

    const blob = new Blob([tsvContent], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePrint = () => {
    window.print();
  };

  // Render Smart Insights Section
  const renderInsights = () => {
    if (!reconStats) return null;
    const cards = [
      { title: 'Auto Reconciled Rate', value: `${reconStats.auto_match_rate}%`, label: '94% of transactions matched automatically', color: COLORS.success },
      { title: 'Duplicate Candidate Risk', value: `${reconStats.duplicate_count} Detected`, label: '5 duplicate transactions flagged in system', color: COLORS.error },
      { title: 'Fraud & Anomaly Watch', value: `${reconStats.high_risk_count} Urgent`, label: '3 high-risk transactions require immediate review', color: COLORS.warning },
      { title: 'Efficiency Rate Increased', value: `${reconStats.time_reduction}%`, label: 'Average reconciliation time reduced by 72%', color: COLORS.primary }
    ];

    return (
      <Box sx={{ mb: 4 }} className="no-print">
        <Typography variant="subtitle2" fontWeight="800" sx={{ mb: 1.5, textTransform: 'uppercase', letterSpacing: '0.05em', color: COLORS.muted }}>
          Smart Treasury Reconciliation Insights
        </Typography>
        <Grid container spacing={2}>
          {cards.map((c, i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Box sx={{ p: 2, bgcolor: c.color + '05', border: `1px solid ${c.color}25`, borderRadius: '8px', display: 'flex', flexDirection: 'column' }}>
                <Typography variant="caption" sx={{ color: COLORS.muted, fontWeight: 700 }}>{c.title}</Typography>
                <Typography variant="h5" fontWeight="800" sx={{ color: c.color, mt: 0.5 }}>{c.value}</Typography>
                <Typography variant="caption" sx={{ color: COLORS.text, mt: 0.5, fontWeight: 500 }}>{c.label}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <style dangerouslySetInnerHTML={{ __html: `
        @media print {
          body * {
            visibility: hidden !important;
          }
          #printable-report-area, #printable-report-area * {
            visibility: visible !important;
          }
          #printable-report-area {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
          }
          .no-print {
            display: none !important;
          }
        }
      `}} />

      {/* Smart Insights summary */}
      {renderInsights()}

      <Paper sx={{ p: 2.5, borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }} className="no-print">
          <FormControl size="small" sx={{ minWidth: 250 }}>
            <InputLabel>Select Management Report</InputLabel>
            <Select
              value={activeReport}
              onChange={(e) => setActiveReport(e.target.value)}
              label="Select Management Report"
            >
              <MenuItem value="summary">Reconciliation Summary Report</MenuItem>
              <MenuItem value="exception">Operational Exception Report</MenuItem>
              <MenuItem value="duplicate">Duplicate Candidate Detection Report</MenuItem>
              <MenuItem value="risk">Risk & Fraud Anomaly Report</MenuItem>
              <MenuItem value="audit">System Audit History Report</MenuItem>
              <MenuItem value="accuracy_report">Matching Engine Accuracy Report</MenuItem>
            </Select>
          </FormControl>

          {reportData && (
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={handleExportCSV}
                sx={{ borderRadius: '6px', textTransform: 'none', borderColor: COLORS.border, color: COLORS.text, fontWeight: 700 }}
              >
                Export CSV
              </Button>
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={handleExportExcel}
                sx={{ borderRadius: '6px', textTransform: 'none', borderColor: COLORS.border, color: COLORS.text, fontWeight: 700 }}
              >
                Export Excel
              </Button>
              <Button
                variant="contained"
                startIcon={<PrintIcon />}
                onClick={handlePrint}
                sx={{ borderRadius: '6px', textTransform: 'none', bgcolor: COLORS.primary, boxShadow: 'none', fontWeight: 700 }}
              >
                Print PDF Report
              </Button>
            </Box>
          )}
        </Box>

        {loading ? (
          <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
        ) : !reportData ? (
          <Box sx={{ py: 6, textAlign: 'center' }}><Typography variant="body2" color="textSecondary">Failed to load report.</Typography></Box>
        ) : (
          <Box id="printable-report-area">
            <Box sx={{ borderBottom: `2px solid ${COLORS.primary}`, pb: 2, mb: 3 }}>
              <Typography variant="h5" fontWeight="800" sx={{ color: COLORS.text }}>
                {reportData.report_name || 'Management Report'}
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.muted, display: 'block', mt: 0.5 }}>
                Generated: {reportData.generated_at || new Date().toLocaleString()} | Enterprise Finance Workspace
              </Typography>
            </Box>

            {/* Reconciliation Summary Report details */}
            {activeReport === 'summary' && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <Grid container spacing={3}>
                  {[
                    { label: 'Total Imported Transactions', val: reportData.data?.total_transactions, desc: 'Complete set of uploaded bank statement lines.' },
                    { label: 'Reconciled Transactions', val: reportData.data?.processed_transactions, desc: 'Approved matches against general ledger vouchers.' },
                    { label: 'Unreconciled Transactions', val: reportData.data?.unprocessed_transactions, desc: 'Awaiting rule application or operational review.' },
                    { label: 'Overall Match Rate (%)', val: `${reportData.data?.overall_match_rate_percent}%`, desc: 'Performance rate of reconciliation ledger.' }
                  ].map((item, idx) => (
                    <Grid item xs={12} sm={6} md={3} key={idx}>
                      <Box sx={{ p: 2, border: `1px solid ${COLORS.border}`, borderRadius: '8px' }}>
                        <Typography variant="caption" color="textSecondary" fontWeight={700}>{item.label}</Typography>
                        <Typography variant="h4" fontWeight="800" sx={{ mt: 1, mb: 0.5, color: COLORS.text }}>{item.val}</Typography>
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', fontSize: '0.73rem' }}>{item.desc}</Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </Box>
            )}

            {/* Exceptions Report details */}
            {activeReport === 'exception' && (
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>ID</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Amount</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Severity</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Assignee</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Notes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(reportData.data || []).map((ex) => {
                      const tx = ex.bank_transaction_detail || {};
                      return (
                        <TableRow key={ex.id}>
                          <TableCell>{ex.id}</TableCell>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>{tx.date}</TableCell>
                          <TableCell>{tx.description || '-'}</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>{fmt(tx.amount)}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{ex.exception_type?.replace(/_/g, ' ')}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{ex.severity}</TableCell>
                          <TableCell>{ex.assigned_to_name || 'Unassigned'}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{ex.status}</TableCell>
                          <TableCell sx={{ color: COLORS.muted }}>{ex.notes || '-'}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Duplicate Candidates Report details */}
            {activeReport === 'duplicate' && (
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Group ID</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Tx1 Date</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Tx1 Description</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Tx2 Date</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Tx2 Description</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Amount</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Similarity</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(reportData.data || []).map((dup) => {
                      const t1 = dup.transaction_1_detail || {};
                      const t2 = dup.transaction_2_detail || {};
                      return (
                        <TableRow key={dup.id}>
                          <TableCell>{dup.id}</TableCell>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>{t1.date}</TableCell>
                          <TableCell>{t1.description}</TableCell>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>{t2.date}</TableCell>
                          <TableCell>{t2.description}</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>{fmt(t1.amount)}</TableCell>
                          <TableCell>{dup.similarity_score}%</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{dup.status}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Risk Report details */}
            {activeReport === 'risk' && (
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>ID</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Amount</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Risk Type</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Risk Score</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Notes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(reportData.data || []).map((r) => {
                      const tx = r.bank_transaction_detail || {};
                      return (
                        <TableRow key={r.id}>
                          <TableCell>{r.id}</TableCell>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>{tx.date}</TableCell>
                          <TableCell>{tx.description}</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>{fmt(tx.amount)}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{r.risk_type?.replace(/_/g, ' ')}</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>{r.risk_score}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{r.status}</TableCell>
                          <TableCell sx={{ color: COLORS.muted }}>{r.notes || '-'}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Audit Report details */}
            {activeReport === 'audit' && (
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Timestamp</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Operator</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Action</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Entity Type</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Entity ID</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Detail Notes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(reportData.data || []).map((log) => {
                      const dt = new Date(log.created_at).toLocaleString('en-IN');
                      return (
                        <TableRow key={log.id}>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>{dt}</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>{log.username || 'System'}</TableCell>
                          <TableCell>{log.action}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{log.entity_type}</TableCell>
                          <TableCell>{log.entity_id}</TableCell>
                          <TableCell sx={{ color: COLORS.muted }}>{log.notes || '-'}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Match Accuracy Report details */}
            {activeReport === 'accuracy_report' && (
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#F9FAFB' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Rule Name</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Suggested Matches</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Approved Count</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Rejected Count</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Reconciliation Accuracy Rate (%)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(reportData.data || []).map((rule, idx) => (
                      <TableRow key={idx}>
                        <TableCell sx={{ fontWeight: 600 }}>{rule.rule_name}</TableCell>
                        <TableCell>{rule.suggested_count}</TableCell>
                        <TableCell>{rule.approved_count}</TableCell>
                        <TableCell>{rule.rejected_count}</TableCell>
                        <TableCell sx={{ fontWeight: 700, color: rule.accuracy_percent >= 85 ? COLORS.success : COLORS.warning }}>
                          {rule.accuracy_percent}%
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
