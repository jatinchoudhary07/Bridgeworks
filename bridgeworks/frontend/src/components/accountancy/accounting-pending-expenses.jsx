'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import PaymentsIcon from '@mui/icons-material/Payments';
import RefreshIcon from '@mui/icons-material/Refresh';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import FilterListIcon from '@mui/icons-material/FilterList';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

// ── Constants ─────────────────────────────────────────────────────────────────

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'upi', label: 'UPI' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'neft', label: 'NEFT' },
  { value: 'other', label: 'Other' },
];

// Statuses that Finance still needs to pay out.
// Only HR-approved entries ('Dept Head Approved' and beyond) are visible here.
const UNPAID_STATUSES = new Set(['Dept Head Approved', 'Partially Approved', 'Finance Reviewed']);

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return '—';
  const parsed = new Date(value + 'T00:00:00');
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function statusColor(st) {
  const v = String(st || '').toLowerCase();
  if (v === 'paid') return 'success';
  if (v === 'rejected') return 'error';
  if (v === 'submitted') return 'info';
  if (v === 'dept head approved') return 'warning';
  if (v === 'partially approved') return 'warning';
  if (v === 'finance reviewed') return 'secondary';
  return 'default';
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ title, amount, subtitle, color }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: '3px solid', borderTopColor: color, flex: 1, minWidth: 160 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
        {title}
      </Typography>
      <Typography variant="h5" sx={{ fontWeight: 700, color, mt: 0.75 }}>
        {formatCurrency(amount)}
      </Typography>
      <Typography variant="caption" color="text.secondary">{subtitle}</Typography>
    </Paper>
  );
}

function WorkflowTrail({ steps }) {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  return (
    <Stack spacing={0.5} sx={{ mt: 0.5 }}>
      {steps.map((step, idx) => (
        <Stack key={idx} direction="row" spacing={0.75} alignItems="flex-start">
          <CheckCircleIcon fontSize="small" color="success" sx={{ mt: 0.1, fontSize: 13 }} />
          <Box>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>{step.step || step.action || step.status}</Typography>
            {step.actor && <Typography variant="caption" color="text.secondary"> by {step.actor}</Typography>}
            {step.at && (
              <Typography variant="caption" color="text.secondary">
                {' · '}
                {new Date(step.at).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })}
              </Typography>
            )}
            {step.rejection_reason && (
              <Typography variant="caption" color="error.main"> — {step.rejection_reason}</Typography>
            )}
          </Box>
        </Stack>
      ))}
    </Stack>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AccountingPendingExpenses() {
  const { canEdit, canViewAmounts } = usePagePermissions();

  const formatCurrency = (value) => {
    if (!canViewAmounts) return '₹ ****';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(Number(value || 0));
  };

  // ── Overview state ──────────────────────────────────────────────
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overview, setOverview] = useState({ summary: {}, members: [], recent_submissions: [] });

  // ── Member detail state ─────────────────────────────────────────
  const [activeMemberId, setActiveMemberId] = useState(null);
  const [memberLoading, setMemberLoading] = useState(false);
  const [memberDetail, setMemberDetail] = useState({ profile: {}, quick_stats: {}, category_breakdown: [], expenses: [], available_categories: ['all'] });
  const [memberTab, setMemberTab] = useState('unpaid'); // 'unpaid' | 'paid' | 'all'
  const [categoryFilter, setCategoryFilter] = useState('all');

  const [showMemberFilters, setShowMemberFilters] = useState(false);
  const [memberTimelineFilter, setMemberTimelineFilter] = useState('all');
  const [memberStartDate, setMemberStartDate] = useState('');
  const [memberEndDate, setMemberEndDate] = useState('');
  const [memberSortBy, setMemberSortBy] = useState('spent_on');
  const [memberSortOrder, setMemberSortOrder] = useState('desc');

  // ── Overview filters ────────────────────────────────────────────
  const [overviewDepartmentFilter, setOverviewDepartmentFilter] = useState('all');
  const [overviewCategoryFilter, setOverviewCategoryFilter] = useState('all');
  const [overviewTimelineFilter, setOverviewTimelineFilter] = useState('all');
  const [overviewSortBy, setOverviewSortBy] = useState('date_desc');
  const [overviewStatusFilter] = useState('all');

  // ── Dialogs ─────────────────────────────────────────────────────
  const [payDialog, setPayDialog] = useState({ open: false, expenseId: null, payment_date: '', payment_method: 'bank_transfer' });
  const [rejectDialog, setRejectDialog] = useState({ open: false, expenseId: null, reason: '' });
  const [busyId, setBusyId] = useState(null);

  // ── Toast / message ─────────────────────────────────────────────
  const [toast, setToast] = useState({ open: false, type: 'success', text: '' });
  const showToast = (type, text) => setToast({ open: true, type, text });
  const closeToast = () => setToast(p => ({ ...p, open: false }));

  // ── Load overview ─────────────────────────────────────────────────
  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const res = await apiClient('/api/finance/pending-expenses/');
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) throw new Error(data?.message || 'Failed to load');
      setOverview(data);
    } catch (err) {
      showToast('error', err.message || 'Failed to load expenses.');
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  useEffect(() => { loadOverview(); }, [loadOverview]);

  // ── Load member detail ─────────────────────────────────────────────
  const loadMemberDetail = useCallback(async (userId, tab = 'unpaid', timeline = 'all', start_date = '', end_date = '', sort_by = 'spent_on', sort_order = 'desc', category = 'all') => {
    if (!userId) return;
    setMemberLoading(true);
    try {
      const qParams = new URLSearchParams({
        tab,
        timeline,
        start_date,
        end_date,
        sort_by,
        sort_order,
        category,
      }).toString();
      const res = await apiClient(`/api/finance/pending-expenses/member/${userId}/?${qParams}`);
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) throw new Error(data?.detail || 'Failed to load member');
      setMemberDetail(data);
    } catch (err) {
      showToast('error', err.message || 'Failed to load member detail.');
    } finally {
      setMemberLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeMemberId) {
      loadMemberDetail(
        activeMemberId,
        memberTab,
        memberTimelineFilter,
        memberStartDate,
        memberEndDate,
        memberSortBy,
        memberSortOrder,
        categoryFilter
      );
    }
  }, [
    activeMemberId,
    memberTab,
    memberTimelineFilter,
    memberStartDate,
    memberEndDate,
    memberSortBy,
    memberSortOrder,
    categoryFilter,
    loadMemberDetail
  ]);

  const openMember = (userId) => {
    setActiveMemberId(userId);
    setMemberTab('unpaid');
    setCategoryFilter('all');
    setMemberTimelineFilter('all');
    setMemberStartDate('');
    setMemberEndDate('');
    setMemberSortBy('spent_on');
    setMemberSortOrder('desc');
    setShowMemberFilters(false);
  };
  const backToOverview = () => {
    setActiveMemberId(null);
    setMemberTab('unpaid');
    setCategoryFilter('all');
    setMemberTimelineFilter('all');
    setMemberStartDate('');
    setMemberEndDate('');
    setMemberSortBy('spent_on');
    setMemberSortOrder('desc');
    setShowMemberFilters(false);
    setMemberDetail({ profile: {}, quick_stats: {}, category_breakdown: [], expenses: [], available_categories: ['all'] });
  };

  // ── Mark as Paid ──────────────────────────────────────────────────
  const openPayDialog = (id) => {
    setPayDialog({ open: true, expenseId: id, payment_date: new Date().toISOString().split('T')[0], payment_method: 'bank_transfer' });
  };
  const handlePayConfirm = async () => {
    const { expenseId, payment_date, payment_method } = payDialog;
    setPayDialog(p => ({ ...p, open: false }));
    setBusyId(expenseId);
    try {
      const res = await apiClient(`/api/finance/pending-expenses/${expenseId}/approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_date, payment_method }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) throw new Error(data?.message || 'Payment failed');
      showToast('success', 'Expense marked as Paid. GL entry created.');
      loadOverview();
      if (activeMemberId) loadMemberDetail(activeMemberId, memberTab);
    } catch (err) {
      showToast('error', err.message || 'Could not mark as paid.');
    } finally {
      setBusyId(null);
    }
  };

  // ── Reject ────────────────────────────────────────────────────────
  const openRejectDialog = (id) => setRejectDialog({ open: true, expenseId: id, reason: '' });
  const handleRejectConfirm = async () => {
    const { expenseId, reason } = rejectDialog;
    setRejectDialog(p => ({ ...p, open: false }));
    setBusyId(expenseId);
    try {
      const res = await apiClient(`/api/finance/pending-expenses/${expenseId}/reject/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rejection_reason: reason }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) throw new Error(data?.message || 'Rejection failed');
      showToast('success', 'Expense rejected.');
      loadOverview();
      if (activeMemberId) loadMemberDetail(activeMemberId, memberTab);
    } catch (err) {
      showToast('error', err.message || 'Could not reject expense.');
    } finally {
      setBusyId(null);
    }
  };

  // ── Overview Dynamic Filter Options ───────────────────────────────────────────
  const overviewDepartments = useMemo(() => {
    const departments = new Set();
    const rows = Array.isArray(overview.recent_submissions) ? overview.recent_submissions : [];
    const members = Array.isArray(overview.members) ? overview.members : [];
    rows.forEach(r => { if (r.department) departments.add(r.department); });
    members.forEach(m => { if (m.department) departments.add(m.department); });
    return ['all', ...Array.from(departments).sort()];
  }, [overview.recent_submissions, overview.members]);

  const overviewCategories = useMemo(() => {
    const categories = new Set();
    const rows = Array.isArray(overview.recent_submissions) ? overview.recent_submissions : [];
    rows.forEach(r => { if (r.category) categories.add(r.category.toLowerCase()); });
    return ['all', ...Array.from(categories).sort()];
  }, [overview.recent_submissions]);

  // ── Client-side filtering & sorting overview ───────────────────
  const filteredRows = useMemo(() => {
    const rows = Array.isArray(overview.recent_submissions) ? [...overview.recent_submissions] : [];
    const now = new Date(); now.setHours(0, 0, 0, 0);
    const timelineDays = { '7d': 7, '30d': 30, '90d': 90, '180d': 180 };
    const parsedTimelineDays = timelineDays[overviewTimelineFilter];
    const thresholdDate = parsedTimelineDays
      ? new Date(now.getTime() - parsedTimelineDays * 24 * 60 * 60 * 1000)
      : null;

    const visibleRows = rows.filter((row) => {
      const rowStatus = String(row?.status || '').trim();
      const category = String(row?.category || '').trim().toLowerCase();
      const dept = String(row?.department || '').trim();

      if (overviewStatusFilter !== 'all' && rowStatus !== overviewStatusFilter) return false;
      if (overviewCategoryFilter !== 'all' && category !== overviewCategoryFilter) return false;
      if (overviewDepartmentFilter !== 'all' && dept !== overviewDepartmentFilter) return false;
      if (thresholdDate) {
        const spentDate = row?.spent_on ? new Date(row.spent_on + 'T00:00:00') : null;
        if (!spentDate || Number.isNaN(spentDate.getTime()) || spentDate < thresholdDate) return false;
      }
      return true;
    });

    return visibleRows.sort((a, b) => {
      const da = a.spent_on ? new Date(a.spent_on + 'T00:00:00').getTime() : 0;
      const db = b.spent_on ? new Date(b.spent_on + 'T00:00:00').getTime() : 0;
      const amountA = Number(a?.amount || 0);
      const amountB = Number(b?.amount || 0);
      const memberA = String(a?.member_name || '').toLowerCase();
      const memberB = String(b?.member_name || '').toLowerCase();
      const statusA = String(a?.status || '').toLowerCase();
      const statusB = String(b?.status || '').toLowerCase();

      if (overviewSortBy === 'date_asc') return da - db;
      if (overviewSortBy === 'amount_desc') return amountB - amountA;
      if (overviewSortBy === 'amount_asc') return amountA - amountB;
      if (overviewSortBy === 'member_asc') return memberA.localeCompare(memberB);
      if (overviewSortBy === 'status_asc') return statusA.localeCompare(statusB);
      return db - da; // date_desc is default
    });
  }, [overview.recent_submissions, overviewStatusFilter, overviewCategoryFilter, overviewDepartmentFilter, overviewTimelineFilter, overviewSortBy]);

  const filteredMembers = useMemo(() => {
    const members = Array.isArray(overview.members) ? overview.members : [];
    if (overviewDepartmentFilter === 'all') return members;
    return members.filter(m => String(m.department || '').trim() === overviewDepartmentFilter);
  }, [overview.members, overviewDepartmentFilter]);

  // ── Member Detail Filters ──────────────────────────────────────────────────────
  const availableCategories = memberDetail.available_categories || ['all'];

  const filteredMemberExpenses = memberDetail.expenses || [];

  // ── Row action buttons ─────────────────────────────────────────────
  const renderActions = (row) => {
    const st = String(row.status || '').trim();
    const isBusy = busyId === row.id;
    if (!UNPAID_STATUSES.has(st)) {
      return <Typography variant="caption" color="text.secondary">{st || '—'}</Typography>;
    }
    return (
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
        <Button size="small" variant="contained" color="success"
          startIcon={isBusy ? <CircularProgress size={12} sx={{ color: '#fff' }} /> : <PaymentsIcon fontSize="small" />}
          disabled={isBusy || !canEdit} onClick={() => openPayDialog(row.id)}
          sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
          Mark Paid
        </Button>
        <Button size="small" variant="outlined" color="error"
          startIcon={<CloseIcon fontSize="small" />}
          disabled={isBusy || !canEdit} onClick={() => openRejectDialog(row.id)}
          sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
          Reject
        </Button>
      </Stack>
    );
  };

  // ── PDF helpers ────────────────────────────────────────────────────
  const exportOverviewPdf = () => {
    const rowHtml = filteredRows.map((r, i) =>
      `<tr><td>${i + 1}</td><td>${r.member_name || '-'}</td><td>${r.category || '-'}</td><td>${formatCurrency(r.amount)}</td><td>${r.spent_on || '-'}</td><td>${r.status || '-'}</td></tr>`
    ).join('');
    const html = `<html><head><title>Finance Expenses</title><style>body{font-family:Arial;margin:18px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ccc;padding:6px}th{background:#f2f2f2}</style></head><body><h1>Pending Expenses</h1><table><thead><tr><th>#</th><th>Member</th><th>Category</th><th>Amount</th><th>Date</th><th>Status</th></tr></thead><tbody>${rowHtml}</tbody></table></body></html>`;
    const popup = window.open('', '_blank', 'width=980,height=700');
    if (!popup) return;
    popup.document.open(); popup.document.write(html); popup.document.close(); popup.focus(); popup.print();
  };

  const exportMemberPdf = () => {
    const profile = memberDetail.profile || {};
    const rows = filteredMemberExpenses;
    const rowHtml = rows.map((r, i) =>
      `<tr><td>${i + 1}</td><td>${r.category || '-'}</td><td>${formatCurrency(r.amount)}</td><td>${r.spent_on || '-'}</td><td>${r.status || '-'}</td><td>${r.notes || '-'}</td></tr>`
    ).join('');
    const html = `<html><head><title>${profile.employee_name || 'Member'} Expenses</title><style>body{font-family:Arial;margin:18px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ccc;padding:6px}th{background:#f2f2f2}</style></head><body><h1>${profile.employee_name || 'Member'}</h1><table><thead><tr><th>#</th><th>Category</th><th>Amount</th><th>Date</th><th>Status</th><th>Notes</th></tr></thead><tbody>${rowHtml}</tbody></table></body></html>`;
    const popup = window.open('', '_blank', 'width=980,height=700');
    if (!popup) return;
    popup.document.open(); popup.document.write(html); popup.document.close(); popup.focus(); popup.print();
  };

  // ── OVERVIEW ───────────────────────────────────────────────────────
  const renderOverview = () => {
    const s = overview.summary || {};

    return (
      <Stack spacing={2}>
        {/* Toolbar */}
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Button variant="outlined" size="small" startIcon={<RefreshIcon />}
              onClick={loadOverview} disabled={overviewLoading}>
              Refresh
            </Button>
            <Button variant="outlined" size="small" startIcon={<DownloadIcon />} onClick={exportOverviewPdf}>
              Export PDF
            </Button>

            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Department</InputLabel>
              <Select
                label="Department"
                value={overviewDepartmentFilter}
                onChange={e => setOverviewDepartmentFilter(String(e.target.value || 'all'))}
              >
                {overviewDepartments.map(dept => (
                  <MenuItem key={dept} value={dept}>
                    {dept === 'all' ? 'All Departments' : dept}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Category</InputLabel>
              <Select
                label="Category"
                value={overviewCategoryFilter}
                onChange={e => setOverviewCategoryFilter(String(e.target.value || 'all'))}
              >
                {overviewCategories.map(cat => (
                  <MenuItem key={cat} value={cat}>
                    {cat === 'all' ? 'All Categories' : cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Timeline</InputLabel>
              <Select
                label="Timeline"
                value={overviewTimelineFilter}
                onChange={e => setOverviewTimelineFilter(String(e.target.value || 'all'))}
              >
                <MenuItem value="all">All Time</MenuItem>
                <MenuItem value="7d">Last 7 Days</MenuItem>
                <MenuItem value="30d">Last 30 Days</MenuItem>
                <MenuItem value="90d">Last 90 Days</MenuItem>
                <MenuItem value="180d">Last 180 Days</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 175 }}>
              <InputLabel>Sort By</InputLabel>
              <Select label="Sort By" value={overviewSortBy} onChange={e => setOverviewSortBy(e.target.value)}>
                <MenuItem value="date_desc">Date: Newest</MenuItem>
                <MenuItem value="date_asc">Date: Oldest</MenuItem>
                <MenuItem value="amount_desc">Amount: High to Low</MenuItem>
                <MenuItem value="amount_asc">Amount: Low to High</MenuItem>
                <MenuItem value="member_asc">Member: A to Z</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        {/* Stat cards */}
        <Grid container spacing={1.5}>
          {[
            { title: 'Total (HR Approved)', amount: s.total_amount || 0, subtitle: `${s.total_entries || 0} approved entries`, color: '#3949ab' },
            { title: 'Pending Payment', amount: s.unpaid_amount || 0, subtitle: `${s.unpaid_entries || 0} awaiting payment`, color: '#ef6c00' },
            { title: 'Paid', amount: s.paid_amount || 0, subtitle: `${s.paid_entries || 0} entries cleared`, color: '#2e7d32' },
            { title: 'Rejected', amount: s.rejected_amount || 0, subtitle: `${s.rejected_entries || 0} entries declined`, color: '#c62828' },
          ].map((card) => (
            <Grid item xs={12} sm={6} md={3} key={card.title}>
              <StatCard {...card} />
            </Grid>
          ))}
        </Grid>

        {/* Member cards */}
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.25, color: 'text.secondary', fontWeight: 600 }}>
            Team Members
          </Typography>
          {overviewLoading ? (
            <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
              <CircularProgress size={28} />
            </Box>
          ) : (
            <Grid container spacing={1.5}>
              {filteredMembers.map(member => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={member.user_id}>
                  <Paper variant="outlined" sx={{
                    p: 1.25, borderRadius: 2, cursor: 'pointer', height: '100%',
                    transition: 'border-color 0.15s, box-shadow 0.15s',
                    '&:hover': { borderColor: 'primary.main', boxShadow: 2 },
                  }} onClick={() => openMember(member.user_id)}>
                    <Stack spacing={1}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                          {member.member_name || 'Unknown'}
                        </Typography>
                        {member.unpaid_count > 0 && (
                          <Chip size="small" color="warning" label={`${member.unpaid_count} pending`} />
                        )}
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        {member.department || 'No department'}
                      </Typography>
                      <Stack direction="row" justifyContent="space-between" spacing={1}>
                        <Stack spacing={0.25} flex={1}>
                          <Typography variant="h6" sx={{ fontWeight: 700, color: '#ef6c00' }}>
                            {formatCurrency(member.unpaid_amount)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">unpaid</Typography>
                        </Stack>
                        <Stack spacing={0.25} flex={1} alignItems="flex-end">
                          <Typography variant="h6" sx={{ fontWeight: 700, color: '#2e7d32' }}>
                            {formatCurrency(member.paid_amount)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">paid</Typography>
                        </Stack>
                      </Stack>
                      <Stack direction="row" spacing={0.75}>
                        <Chip size="small" label={`Paid ${member.paid_count || 0}`} color="success" variant="outlined" />
                        <Chip size="small" label={`Pending ${member.unpaid_count || 0}`} color="warning" variant="outlined" />
                        <Chip size="small" label={`Entries ${member.entries_count || 0}`} variant="outlined" />
                      </Stack>
                    </Stack>
                  </Paper>
                </Grid>
              ))}
              {!filteredMembers.length && (
                <Grid item xs={12}>
                  <Typography variant="body2" color="text.secondary">
                    No HR-approved expenses found. Expenses approved by HR will appear here for payment.
                  </Typography>
                </Grid>
              )}
            </Grid>
          )}
        </Paper>

        {/* Awaiting Payment table */}
        <Paper variant="outlined" sx={{ borderRadius: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Awaiting Payment</Typography>
              {filteredRows.length > 0 && (
                <Chip
                  size="small"
                  label={`${filteredRows.length} transactions`}
                  color="warning"
                  sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                />
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">HR approved · not yet paid</Typography>
          </Stack>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {['Member', 'Category', 'Amount', 'Date', 'Status', 'Actions', 'Receipt'].map(h => (
                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b', bgcolor: '#f8fafc' }}>
                      {h}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredRows.map(row => (
                  <TableRow key={row.id} hover>
                    <TableCell>
                      <Stack>
                        <Typography variant="body2" sx={{ fontWeight: 600, cursor: 'pointer', color: 'primary.main' }}
                          onClick={() => openMember(row.user_id)}>
                          {row.member_name || '—'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">{row.department || 'No department'}</Typography>
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ textTransform: 'capitalize' }}>{String(row.category || '').replace(/_/g, ' ') || '—'}</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>
                      {row.approved_amount !== null && row.approved_amount !== undefined && String(row.status || '').toLowerCase() === 'partially approved'
                        ? formatCurrency(row.approved_amount)
                        : formatCurrency(row.amount)}
                    </TableCell>
                    <TableCell>
                      <Stack>
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>{formatDate(row.spent_on)}</Typography>
                        {row.bill_date && row.bill_date !== row.spent_on && (
                          <Typography variant="caption" color="text.secondary">Bill: {formatDate(row.bill_date)}</Typography>
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Stack spacing={0.25}>
                        <Chip size="small" label={row.status || '—'} color={statusColor(row.status)} variant="outlined" />
                        {row.finance_entry_id && (
                          <Chip
                            size="small"
                            label={`GL #${row.finance_entry_id}`}
                            color="primary"
                            variant="outlined"
                            clickable
                            onClick={() => window.open('/finance/ledger', '_blank', 'noopener,noreferrer')}
                          />
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>{renderActions(row)}</TableCell>
                    <TableCell>
                      <Tooltip title={row.receipt_url ? 'Open receipt' : 'No receipt'}>
                        <span>
                          <IconButton
                            size="small"
                            disabled={!row.receipt_url}
                            onClick={() => row.receipt_url && window.open(row.receipt_url, '_blank', 'noopener,noreferrer')}
                          >
                            <OpenInNewIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {!filteredRows.length && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                        🎉 All HR-approved expenses have been paid. Nothing pending!
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </Stack>
    );
  };

  // ── MEMBER DETAIL ──────────────────────────────────────────────────
  const renderMemberDetail = () => {
    const profile = memberDetail.profile || {};
    const stats = memberDetail.quick_stats || {};

    return (
      <Stack spacing={2}>
        {/* Back and PDF Actions */}
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button variant="text" startIcon={<ArrowBackIcon />} onClick={backToOverview}>
              Back to Overview
            </Button>
          </Stack>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button
              variant={showMemberFilters ? 'contained' : 'outlined'}
              size="small"
              startIcon={<FilterListIcon />}
              onClick={() => setShowMemberFilters(!showMemberFilters)}
            >
              Filter
            </Button>
            <Button variant="outlined" size="small" startIcon={<DownloadIcon />} onClick={exportMemberPdf}>
              Export PDF
            </Button>
          </Stack>
        </Stack>

        {/* Member Profile & Stats Card */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Stack spacing={1.5}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800 }}>{profile.employee_name || '—'}</Typography>
            </Box>

            <Divider />

            <Grid container spacing={1.5}>
              {[
                { title: 'Total Figures', amount: stats.total_amount, subtitle: `${stats.entries || 0} entries`, color: '#3949ab' },
                { title: 'Pending Payment', amount: stats.unpaid_amount, subtitle: `${stats.unpaid || 0} entries`, color: '#ef6c00' },
                { title: 'Total Paid', amount: stats.paid_amount, subtitle: `${stats.paid || 0} entries`, color: '#2e7d32' },
                { title: 'Total Rejected', amount: stats.rejected_amount, subtitle: `${stats.rejected || 0} entries`, color: '#c62828' },
                { title: 'Department', subtitle: profile.department || 'No Department', color: '#0288d1', isTextOnly: true },
                { title: 'Email', subtitle: profile.email || 'No Email', color: '#7b1fa2', isTextOnly: true },
              ].map((card, idx) => (
                <Grid item xs={6} sm={4} md={2} key={idx}>
                  <Paper variant="outlined" sx={{
                    p: 1.25,
                    borderRadius: 1.5,
                    borderLeft: '3px solid',
                    borderLeftColor: card.color,
                    bgcolor: 'action.hover',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                  }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: 0.5 }}>
                      {card.title}
                    </Typography>
                    {card.amount !== undefined && card.amount !== null ? (
                      <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 0.25 }}>
                        {formatCurrency(card.amount)}
                      </Typography>
                    ) : (
                      <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 0.25, fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {card.subtitle}
                      </Typography>
                    )}
                    {(card.amount !== undefined && card.amount !== null) && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                        {card.subtitle}
                      </Typography>
                    )}
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </Stack>
        </Paper>

        {/* Filter Panel */}
        {showMemberFilters && (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center" useFlexGap flexWrap="wrap">
              <FormControl size="small" sx={{ minWidth: 150, flexGrow: { xs: 1, sm: 0 } }}>
                <InputLabel>Timeline</InputLabel>
                <Select label="Timeline" value={memberTimelineFilter} onChange={(e) => setMemberTimelineFilter(e.target.value)}>
                  <MenuItem value="all">All Time</MenuItem>
                  <MenuItem value="today">Today</MenuItem>
                  <MenuItem value="7d">Last 7 Days</MenuItem>
                  <MenuItem value="30d">Last 30 Days</MenuItem>
                  <MenuItem value="this_month">This Month</MenuItem>
                  <MenuItem value="last_month">Last Month</MenuItem>
                  <MenuItem value="custom">Custom Range</MenuItem>
                </Select>
              </FormControl>

              {memberTimelineFilter === 'custom' && (
                <>
                  <TextField
                    type="date"
                    size="small"
                    label="From"
                    InputLabelProps={{ shrink: true }}
                    value={memberStartDate}
                    onChange={(e) => setMemberStartDate(e.target.value)}
                    sx={{ flexGrow: { xs: 1, sm: 0 } }}
                  />
                  <TextField
                    type="date"
                    size="small"
                    label="To"
                    InputLabelProps={{ shrink: true }}
                    value={memberEndDate}
                    onChange={(e) => setMemberEndDate(e.target.value)}
                    sx={{ flexGrow: { xs: 1, sm: 0 } }}
                  />
                </>
              )}

              <FormControl size="small" sx={{ minWidth: 140, flexGrow: { xs: 1, sm: 0 } }}>
                <InputLabel>Sort By</InputLabel>
                <Select label="Sort By" value={memberSortBy} onChange={(e) => setMemberSortBy(e.target.value)}>
                  <MenuItem value="spent_on">Date</MenuItem>
                  <MenuItem value="amount">Amount</MenuItem>
                  <MenuItem value="created_at">Created</MenuItem>
                  <MenuItem value="category">Category</MenuItem>
                  <MenuItem value="transaction_type">Type</MenuItem>
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 140, flexGrow: { xs: 1, sm: 0 } }}>
                <InputLabel>Order</InputLabel>
                <Select label="Order" value={memberSortOrder} onChange={(e) => setMemberSortOrder(e.target.value)}>
                  <MenuItem value="desc">Descending</MenuItem>
                  <MenuItem value="asc">Ascending</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </Paper>
        )}

        {/* Category filtering chips */}
        {availableCategories.length > 1 && (
          <Box>
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              {availableCategories.map((category) => {
                const value = String(category || 'all').toLowerCase();
                const isActive = value === categoryFilter;
                const label = value === 'all' ? 'All Categories' : value.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
                return (
                  <Chip
                    key={value}
                    clickable
                    color={isActive ? 'primary' : 'default'}
                    variant={isActive ? 'filled' : 'outlined'}
                    onClick={() => setCategoryFilter(value)}
                    label={label}
                  />
                );
              })}
            </Stack>
          </Box>
        )}

        {/* Expense entries list */}
        <Paper variant="outlined" sx={{ borderRadius: 2 }}>
          <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 2 }}>
            <Tabs value={memberTab} onChange={(_, v) => { setMemberTab(v); setCategoryFilter('all'); }}
              sx={{
                '& .MuiTab-root': { textTransform: 'none', fontSize: '0.85rem', fontWeight: 600 },
                '& .Mui-selected': { color: '#3949ab' },
                '& .MuiTabs-indicator': { bgcolor: '#3949ab' },
              }}>
              <Tab value="unpaid" label={
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <span>Unpaid</span>
                  <Chip size="small" label={stats.unpaid || 0} color="warning" sx={{ height: 18, fontSize: '0.65rem' }} />
                </Stack>
              } />
              <Tab value="paid" label={
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <span>Paid</span>
                  <Chip size="small" label={stats.paid || 0} color="success" sx={{ height: 18, fontSize: '0.65rem' }} />
                </Stack>
              } />
              <Tab value="all" label="All" />
            </Tabs>
            <Typography variant="caption" color="text.secondary">
              Showing {filteredMemberExpenses.length} entries
            </Typography>
          </Box>

          {memberLoading ? (
            <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {['Category', 'Amount', 'Date', 'Status & Trail', 'Notes / GL', 'Actions', 'Receipt'].map(h => (
                      <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b', bgcolor: '#f8fafc' }}>
                        {h}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredMemberExpenses.map(row => (
                    <TableRow key={row.id} hover>
                      <TableCell sx={{ textTransform: 'capitalize' }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {String(row.category || '').replace(/_/g, ' ')}
                        </Typography>
                        {row.department && (
                          <Typography variant="caption" color="text.secondary">{row.department}</Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>
                        {row.approved_amount !== null && row.approved_amount !== undefined && String(row.status || '').toLowerCase() === 'partially approved'
                          ? formatCurrency(row.approved_amount)
                          : formatCurrency(row.amount)}
                      </TableCell>
                      <TableCell>
                        <Stack>
                          <Typography variant="caption" sx={{ fontWeight: 600 }}>{formatDate(row.spent_on)}</Typography>
                          {row.bill_date && row.bill_date !== row.spent_on && (
                            <Typography variant="caption" color="text.secondary">Bill: {formatDate(row.bill_date)}</Typography>
                          )}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.5}>
                          <Box>
                            <Chip size="small" label={row.status || '—'} color={statusColor(row.status)} variant="outlined" />
                            {row.finance_entry_id && (
                              <Chip
                                size="small"
                                label={`GL #${row.finance_entry_id}`}
                                color="primary"
                                variant="outlined"
                                clickable
                                sx={{ ml: 0.5 }}
                                onClick={() => window.open('/finance/ledger', '_blank', 'noopener,noreferrer')}
                              />
                            )}
                          </Box>
                          <WorkflowTrail steps={row.workflow_steps} />
                        </Stack>
                      </TableCell>
                      <TableCell sx={{ maxWidth: 180 }}>
                        <Tooltip title={row.notes || ''}>
                          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                            {row.notes || '—'}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell>{renderActions(row)}</TableCell>
                      <TableCell>
                        <Tooltip title={row.receipt_url ? 'Open receipt' : 'No receipt'}>
                          <span>
                            <IconButton
                              size="small"
                              disabled={!row.receipt_url}
                              onClick={() => row.receipt_url && window.open(row.receipt_url, '_blank', 'noopener,noreferrer')}
                            >
                              <OpenInNewIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!filteredMemberExpenses.length && (
                    <TableRow>
                      <TableCell colSpan={7}>
                        <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                          {memberTab === 'unpaid'
                            ? 'No unpaid expenses — all settled!'
                            : memberTab === 'paid'
                              ? 'No paid expenses yet.'
                              : 'No expense entries found.'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </Stack>
    );
  };

  // ── Dialogs ────────────────────────────────────────────────────────
  const renderPayDialog = () => (
    <Dialog open={payDialog.open} onClose={() => setPayDialog(p => ({ ...p, open: false }))} maxWidth="xs" fullWidth>
      <DialogTitle>Mark as Paid</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField label="Payment Date" type="date" size="small" fullWidth
            value={payDialog.payment_date}
            onChange={e => setPayDialog(p => ({ ...p, payment_date: e.target.value }))}
            InputLabelProps={{ shrink: true }} />
          <FormControl size="small" fullWidth>
            <InputLabel>Payment Method</InputLabel>
            <Select label="Payment Method" value={payDialog.payment_method}
              onChange={e => setPayDialog(p => ({ ...p, payment_method: e.target.value }))}>
              {PAYMENT_METHODS.map(pm => <MenuItem key={pm.value} value={pm.value}>{pm.label}</MenuItem>)}
            </Select>
          </FormControl>
          <Typography variant="caption" color="text.secondary">
            This will mark the expense as Paid and create a GL journal entry.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setPayDialog(p => ({ ...p, open: false }))}>Cancel</Button>
        <Button variant="contained" color="success" onClick={handlePayConfirm} startIcon={<PaymentsIcon />}>
          Confirm Payment
        </Button>
      </DialogActions>
    </Dialog>
  );

  const renderRejectDialog = () => (
    <Dialog open={rejectDialog.open} onClose={() => setRejectDialog(p => ({ ...p, open: false }))} maxWidth="xs" fullWidth>
      <DialogTitle>Reject Expense</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>Optionally provide a reason for rejection.</DialogContentText>
        <TextField label="Rejection Reason" multiline rows={3} size="small" fullWidth
          value={rejectDialog.reason}
          onChange={e => setRejectDialog(p => ({ ...p, reason: e.target.value }))}
          placeholder="e.g. Missing receipt, duplicate entry…" />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setRejectDialog(p => ({ ...p, open: false }))}>Cancel</Button>
        <Button variant="contained" color="error" onClick={handleRejectConfirm}>Reject</Button>
      </DialogActions>
    </Dialog>
  );

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <Box sx={{ width: '100%' }}>
      {overviewLoading && !activeMemberId && <LinearProgress sx={{ mb: 1 }} />}
      {activeMemberId ? renderMemberDetail() : renderOverview()}
      {renderPayDialog()}
      {renderRejectDialog()}
      <Snackbar open={toast.open} autoHideDuration={4000} onClose={closeToast}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Alert severity={toast.type} onClose={closeToast} variant="filled" sx={{ width: '100%' }}>
          {toast.text}
        </Alert>
      </Snackbar>
    </Box>
  );
}
