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
    FormControl,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    CheckCircle as CheckCircleIcon,
    Close as CloseIcon,
    Download as DownloadIcon,
    FilterList as FilterListIcon,
    OpenInNew as OpenInNewIcon,
    Refresh as RefreshIcon,
    ThumbUp as ThumbUpIcon,
    ThumbsUpDown as ThumbsUpDownIcon,
} from '@mui/icons-material';

import {
    getHrExpenseTrackerMemberDetail,
    listHrExpenseTrackerOverview,
    requestHrExpenseTrackerApproval,
    updateHrExpenseTrackerApproval,
} from '../mydesk/mydeskService';
import {
    getCachedOverview,
    setCachedOverview,
    getCachedMemberDetail,
    setCachedMemberDetail,
    clearCachedOverview,
    clearAllMemberDetailCache,
} from '../../utils/localExpenseDb';

const EMPTY_OVERVIEW = {
    summary: {
        total_submitted_amount: 0,
        pending_approval_amount: 0,
        approved_amount: 0,
        paid_amount: 0,
        rejected_amount: 0,
        total_entries: 0,
        pending_entries: 0,
        approved_entries: 0,
        paid_entries: 0,
        rejected_entries: 0,
        member_count: 0,
    },
    departments: [{ value: 'all', label: 'All Departments' }],
    members: [],
    recent_submissions: [],
};

const EMPTY_MEMBER_DETAIL = {
    profile: {
        user_id: null,
        employee_name: '',
        employee_id: '',
        email: '',
        phone: '',
        joining_date: '',
        manager: '',
        department: '',
        designation: '',
    },
    quick_stats: {
        total_amount: 0,
        paid_amount: 0,
        total_unpaid_amount: 0,
        unpaid_amount: 0,
        dept_approved_amount: 0,
        pending_amount: 0,
        entries: 0,
        approved: 0,
        paid: 0,
        pending: 0,
        rejected: 0,
    },
    category_breakdown: [],
    available_categories: ['all'],
    status_options: ['all', 'Draft', 'Submitted', 'Dept Head Approved', 'Finance Reviewed', 'Paid', 'Rejected'],
    filters: { category: 'all', status: 'all' },
    expenses: [],
};

const STATUS_DISPLAY_MAP = {
    dept_head_approved: 'Dept Head Approved',
    rejected: 'Rejected',
    paid: 'Paid',
    partially_approved: 'Partially Approved',
    submitted: 'Submitted',
};

// A row is treated as rejected (terminal, no actions) when:
//   • row.status is "Rejected" (any casing), OR
//   • row.rejection_reason is set, OR
//   • the latest workflow step label contains "reject"
function isEffectivelyRejected(row) {
    const status = String(row?.status || '').trim().toLowerCase();
    if (status === 'rejected') return true;
    if (row?.rejection_reason && String(row.rejection_reason).trim().length > 0) return true;
    if (Array.isArray(row?.workflow_steps) && row.workflow_steps.length > 0) {
        const lastStep = row.workflow_steps[row.workflow_steps.length - 1];
        const stepLabel = String(lastStep?.step || lastStep?.action || lastStep?.status || '').toLowerCase();
        if (stepLabel.includes('reject')) return true;
    }
    return false;
}

function formatCurrency(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
    }).format(Number(value || 0));
}

function formatDate(value) {
    if (!value) return '-';
    const parsed = new Date(value + 'T00:00:00');
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDatetime(value) {
    if (!value) return '-';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return (
        parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) +
        ' ' +
        parsed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    );
}

function statusColor(statusValue) {
    const value = String(statusValue || '').toLowerCase();
    if (value === 'paid' || value === 'approved') return 'success';
    if (value === 'rejected') return 'error';
    if (value === 'submitted') return 'info';
    if (value === 'dept head approved') return 'warning';
    if (value === 'partially approved' || value === 'partially_approved') return 'warning';
    if (value === 'finance reviewed') return 'secondary';
    return 'default';
}

function StatCard({ title, amount, subtitle, color }) {
    return (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: '3px solid', borderTopColor: color, minHeight: 120 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}>
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
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                            {step.step || step.action || step.status}
                        </Typography>
                        {step.approved_amount !== undefined && step.approved_amount !== null && (
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'warning.main' }}>
                                {' '}(Approved: {formatCurrency(step.approved_amount)})
                            </Typography>
                        )}
                        {step.actor && (
                            <Typography variant="caption" color="text.secondary"> by {step.actor}</Typography>
                        )}
                        {step.at && (
                            <Typography variant="caption" color="text.secondary"> · {formatDatetime(step.at)}</Typography>
                        )}
                        {step.note && (
                            <Typography variant="caption" color="error.main"> — {step.note}</Typography>
                        )}
                    </Box>
                </Stack>
            ))}
        </Stack>
    );
}

export default function HRExpensesTracker() {
    const [overviewLoading, setOverviewLoading] = useState(true);
    // FIX: Separate "initial load" spinner from silent background refresh.
    // memberLoading=true only when navigating TO a member for the first time.
    // Background refreshes after actions update state directly without spinner.
    const [memberLoading, setMemberLoading] = useState(false);
    const [overview, setOverview] = useState(EMPTY_OVERVIEW);
    const [memberDetail, setMemberDetail] = useState(EMPTY_MEMBER_DETAIL);

    const [department, setDepartment] = useState('all');
    const [activeMemberId, setActiveMemberId] = useState(null);
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [showMemberFilters, setShowMemberFilters] = useState(false);
    const [memberTimelineFilter, setMemberTimelineFilter] = useState('all');
    const [memberStartDate, setMemberStartDate] = useState('');
    const [memberEndDate, setMemberEndDate] = useState('');
    const [memberSortBy, setMemberSortBy] = useState('spent_on');
    const [memberSortOrder, setMemberSortOrder] = useState('desc');
    const [overviewStatusFilter, setOverviewStatusFilter] = useState('all');
    const [overviewCategoryFilter, setOverviewCategoryFilter] = useState('all');
    const [overviewTimelineFilter, setOverviewTimelineFilter] = useState('all');
    const [overviewSortBy, setOverviewSortBy] = useState('date_desc');

    const [message, setMessage] = useState({ type: 'success', text: '' });
    const [approvalBusyId, setApprovalBusyId] = useState(null);
    const [requestApprovalLoading, setRequestApprovalLoading] = useState(false);

    const [rejectDialog, setRejectDialog] = useState({ open: false, expenseId: null, reason: '' });
    const [partialApproveDialog, setPartialApproveDialog] = useState({ open: false, expenseId: null, amount: '', maxAmount: 0 });

    const setErrorMessage = useCallback((error, fallbackText) => {
        const text = typeof error === 'string' ? error : error?.detail || error?.message || fallbackText;
        setMessage({ type: 'error', text: text || fallbackText });
    }, []);

    // ── loadOverview ─────────────────────────────────────────────────────────
    // silent=true → never show full-page spinner; just update data in-place.
    const loadOverview = useCallback(async (forceRefresh = false, silent = false) => {
        if (!silent) {
            if (!forceRefresh) {
                const cached = await getCachedOverview(department);
                if (cached) {
                    setOverview(cached);
                    setOverviewLoading(false);
                } else {
                    setOverviewLoading(true);
                }
            } else {
                // forceRefresh but not silent: keep current data visible, no spinner
            }
        }
        // silent: skip all loading state changes
        try {
            const payload = await listHrExpenseTrackerOverview({ department });
            const data = { ...EMPTY_OVERVIEW, ...(payload || {}) };
            setOverview(data);
            await setCachedOverview(department, data);
        } catch (error) {
            if (!silent) setErrorMessage(error, 'Unable to load HR expense overview.');
        } finally {
            if (!silent) setOverviewLoading(false);
        }
    }, [department, setErrorMessage]);

    // ── loadMemberDetail ─────────────────────────────────────────────────────
    // silent=true → skip spinner, update data in-place (used after actions).
    const loadMemberDetail = useCallback(async (userId, filters = {}, forceRefresh = false, silent = false) => {
        if (!userId) return;

        if (!silent) {
            if (!forceRefresh) {
                const cached = await getCachedMemberDetail(userId, filters);
                if (cached) {
                    setMemberDetail(cached);
                    setMemberLoading(false);
                } else {
                    setMemberLoading(true);
                }
            }
            // forceRefresh && !silent: keep current data, no spinner
        }

        try {
            const payload = await getHrExpenseTrackerMemberDetail(userId, filters);
            const data = { ...EMPTY_MEMBER_DETAIL, ...(payload || {}) };
            setMemberDetail(data);
            await setCachedMemberDetail(userId, filters, data);
        } catch (error) {
            if (!silent) setErrorMessage(error, 'Unable to load member expense details.');
        } finally {
            if (!silent) setMemberLoading(false);
        }
    }, [setErrorMessage]);

    useEffect(() => { loadOverview(false, false); }, [loadOverview]);

    useEffect(() => {
        if (!activeMemberId) return;
        loadMemberDetail(activeMemberId, {
            category: categoryFilter,
            status: statusFilter,
            timeline: memberTimelineFilter,
            start_date: memberStartDate,
            end_date: memberEndDate,
            sort_by: memberSortBy,
            sort_order: memberSortOrder,
        }, false, false);
    }, [
        activeMemberId,
        categoryFilter,
        statusFilter,
        memberTimelineFilter,
        memberStartDate,
        memberEndDate,
        memberSortBy,
        memberSortOrder,
        loadMemberDetail
    ]);

    // ── refreshBoth: SILENT background sync after every action ───────────────
    // Uses silent=true so NO spinner is ever shown. The optimistic update
    // already reflects the change; this call just syncs server state quietly.
    const refreshBoth = useCallback(async () => {
        const overviewPromise = loadOverview(true, true);
        const memberPromise = activeMemberId
            ? loadMemberDetail(activeMemberId, {
                category: categoryFilter,
                status: statusFilter,
                timeline: memberTimelineFilter,
                start_date: memberStartDate,
                end_date: memberEndDate,
                sort_by: memberSortBy,
                sort_order: memberSortOrder,
            }, true, true)
            : Promise.resolve();
        await Promise.all([overviewPromise, memberPromise]);
    }, [
        loadOverview,
        loadMemberDetail,
        activeMemberId,
        categoryFilter,
        statusFilter,
        memberTimelineFilter,
        memberStartDate,
        memberEndDate,
        memberSortBy,
        memberSortOrder
    ]);

    // ── Optimistic update helpers ─────────────────────────────────────────────
    const applyOptimisticUpdate = useCallback((expenseId, updates) => {
        setMemberDetail((prev) => ({
            ...prev,
            expenses: (prev.expenses || []).map((row) =>
                row.id === expenseId ? { ...row, ...updates } : row
            ),
        }));
        setOverview((prev) => ({
            ...prev,
            recent_submissions: (prev.recent_submissions || []).map((row) =>
                row.id === expenseId ? { ...row, ...updates } : row
            ),
        }));
    }, []);

    const revertOptimisticUpdate = useCallback((expenseId, originalRow) => {
        setMemberDetail((prev) => ({
            ...prev,
            expenses: (prev.expenses || []).map((row) =>
                row.id === expenseId ? originalRow : row
            ),
        }));
        setOverview((prev) => ({
            ...prev,
            recent_submissions: (prev.recent_submissions || []).map((row) =>
                row.id === expenseId ? originalRow : row
            ),
        }));
    }, []);

    const invalidateCache = useCallback(() => {
        clearCachedOverview(department).catch(() => { });
        clearAllMemberDetailCache().catch(() => { });
    }, [department]);

    const summary = overview.summary || EMPTY_OVERVIEW.summary;

    const overviewCategories = useMemo(() => {
        const rows = Array.isArray(overview.recent_submissions) ? overview.recent_submissions : [];
        const categories = new Set();
        rows.forEach((row) => {
            const value = String(row?.category || '').trim().toLowerCase();
            if (value) categories.add(value);
        });
        return ['all', ...Array.from(categories).sort()];
    }, [overview.recent_submissions]);

    const filteredOverviewRows = useMemo(() => {
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
            if (overviewStatusFilter !== 'all' && rowStatus !== overviewStatusFilter) return false;
            if (overviewCategoryFilter !== 'all' && category !== overviewCategoryFilter) return false;
            if (thresholdDate) {
                const spentDate = row?.spent_on ? new Date(row.spent_on + 'T00:00:00') : null;
                if (!spentDate || Number.isNaN(spentDate.getTime()) || spentDate < thresholdDate) return false;
            }
            return true;
        });

        return visibleRows.sort((a, b) => {
            const dateA = a?.spent_on ? new Date(a.spent_on + 'T00:00:00').getTime() : 0;
            const dateB = b?.spent_on ? new Date(b.spent_on + 'T00:00:00').getTime() : 0;
            const amountA = Number(a?.amount || 0);
            const amountB = Number(b?.amount || 0);
            const memberA = String(a?.member_name || '').toLowerCase();
            const memberB = String(b?.member_name || '').toLowerCase();
            const statusA = String(a?.status || '').toLowerCase();
            const statusB = String(b?.status || '').toLowerCase();
            if (overviewSortBy === 'date_asc') return dateA - dateB;
            if (overviewSortBy === 'amount_desc') return amountB - amountA;
            if (overviewSortBy === 'amount_asc') return amountA - amountB;
            if (overviewSortBy === 'member_asc') return memberA.localeCompare(memberB);
            if (overviewSortBy === 'status_asc') return statusA.localeCompare(statusB);
            return dateB - dateA;
        });
    }, [overview.recent_submissions, overviewStatusFilter, overviewCategoryFilter, overviewTimelineFilter, overviewSortBy]);

    // ── Action: Approve ───────────────────────────────────────────────────────
    const handleApprovalAction = async (expenseId, nextStatus) => {
        if (!expenseId || !nextStatus) return;
        const originalRow =
            memberDetail.expenses?.find((r) => r.id === expenseId) ??
            overview.recent_submissions?.find((r) => r.id === expenseId);

        applyOptimisticUpdate(expenseId, { status: STATUS_DISPLAY_MAP[nextStatus] ?? nextStatus });
        setApprovalBusyId(expenseId);
        invalidateCache();

        try {
            await updateHrExpenseTrackerApproval(expenseId, { status: nextStatus });
            setMessage({ type: 'success', text: 'Expense status updated.' });
            refreshBoth().catch(() => { });
        } catch (error) {
            if (originalRow) revertOptimisticUpdate(expenseId, originalRow);
            setErrorMessage(error, 'Unable to update expense status.');
        } finally {
            setApprovalBusyId(null);
        }
    };

    const openRejectDialog = (expenseId) => setRejectDialog({ open: true, expenseId, reason: '' });

    // ── Action: Reject ───────────────────────────────────────────────────────
    const handleRejectConfirm = async () => {
        const { expenseId, reason } = rejectDialog;
        setRejectDialog((p) => ({ ...p, open: false }));
        const originalRow =
            memberDetail.expenses?.find((r) => r.id === expenseId) ??
            overview.recent_submissions?.find((r) => r.id === expenseId);

        applyOptimisticUpdate(expenseId, {
            status: STATUS_DISPLAY_MAP.rejected,
            rejection_reason: reason || 'Rejected',
        });
        setApprovalBusyId(expenseId);
        invalidateCache();

        try {
            await updateHrExpenseTrackerApproval(expenseId, { status: 'rejected', rejection_reason: reason });
            setMessage({ type: 'success', text: 'Expense rejected.' });
            refreshBoth().catch(() => { });
        } catch (error) {
            if (originalRow) revertOptimisticUpdate(expenseId, originalRow);
            setErrorMessage(error, 'Unable to reject expense.');
        } finally {
            setApprovalBusyId(null);
        }
    };

    const openPartialApproveDialog = (expenseId, currentAmount) => {
        setPartialApproveDialog({ open: true, expenseId, amount: '', maxAmount: Number(currentAmount || 0) });
    };

    // ── Action: Partially Approve ────────────────────────────────────────────
    const handlePartialApproveConfirm = async () => {
        const { expenseId, amount, maxAmount } = partialApproveDialog;
        const approvedAmount = Number(amount);
        if (Number.isNaN(approvedAmount) || approvedAmount <= 0 || approvedAmount > maxAmount) {
            setMessage({ type: 'error', text: `Please enter a valid amount between 0 and ${maxAmount}.` });
            return;
        }
        setPartialApproveDialog((p) => ({ ...p, open: false }));
        const originalRow =
            memberDetail.expenses?.find((r) => r.id === expenseId) ??
            overview.recent_submissions?.find((r) => r.id === expenseId);

        applyOptimisticUpdate(expenseId, {
            status: STATUS_DISPLAY_MAP.partially_approved,
            approved_amount: approvedAmount,
        });
        setApprovalBusyId(expenseId);
        invalidateCache();

        try {
            await updateHrExpenseTrackerApproval(expenseId, { status: 'partially_approved', approved_amount: approvedAmount });
            setMessage({ type: 'success', text: `Expense partially approved for ${formatCurrency(approvedAmount)}.` });
            refreshBoth().catch(() => { });
        } catch (error) {
            if (originalRow) revertOptimisticUpdate(expenseId, originalRow);
            setErrorMessage(error, 'Unable to partially approve expense.');
        } finally {
            setApprovalBusyId(null);
        }
    };

    const handleRequestApproval = async () => {
        if (!activeMemberId) return;
        setRequestApprovalLoading(true);
        try {
            const response = await requestHrExpenseTrackerApproval(activeMemberId);
            const moved = Number(response?.updated_count || 0);
            setMessage({
                type: 'success',
                text: moved > 0 ? `${moved} entries moved to Submitted.` : 'No draft expenses were available to submit.',
            });
            // Silent refresh after submit-drafts
            await refreshBoth();
        } catch (error) {
            setErrorMessage(error, 'Unable to submit expenses for this member.');
        } finally {
            setRequestApprovalLoading(false);
        }
    };

    const handleOpenMember = async (memberId) => {
        setCategoryFilter('all');
        setStatusFilter('all');
        setMemberTimelineFilter('all');
        setMemberStartDate('');
        setMemberEndDate('');
        setMemberSortBy('spent_on');
        setMemberSortOrder('desc');
        setShowMemberFilters(false);
        const defaultFilters = {
            category: 'all',
            status: 'all',
            timeline: 'all',
            start_date: '',
            end_date: '',
            sort_by: 'spent_on',
            sort_order: 'desc',
        };
        const cached = await getCachedMemberDetail(memberId, defaultFilters);
        if (cached) {
            setMemberDetail(cached);
            setActiveMemberId(memberId);
        } else {
            setMemberLoading(true);
            setMemberDetail(EMPTY_MEMBER_DETAIL);
            setActiveMemberId(memberId);
        }
    };

    const handleBackToOverview = () => {
        setActiveMemberId(null);
        setCategoryFilter('all');
        setStatusFilter('all');
        setMemberTimelineFilter('all');
        setMemberStartDate('');
        setMemberEndDate('');
        setMemberSortBy('spent_on');
        setMemberSortOrder('desc');
        setShowMemberFilters(false);
        setMemberDetail(EMPTY_MEMBER_DETAIL);
    };

    // ── renderActionButtons ───────────────────────────────────────────────────
    // Rules:
    //   Rejected (any form)        → "Rejected" label, no buttons
    //   Dept Head Approved         → "Approved" label, no buttons (terminal for HR)
    //   Partially Approved         → "Partially Approved" label, no buttons (terminal for HR)
    //   Finance Reviewed / Paid    → status label, no buttons (downstream)
    //   Submitted                  → Approve | Partial Approve | Reject buttons
    //   Draft / other              → status label only
    const renderActionButtons = (row) => {
        const rowStatus = String(row.status || '').trim().toLowerCase();
        const isBusy = approvalBusyId === row.id;

        if (isEffectivelyRejected(row)) {
            return (
                <Typography variant="caption" color="error.main" sx={{ fontStyle: 'italic', fontWeight: 600 }}>
                    Rejected
                </Typography>
            );
        }

        if (rowStatus === 'dept head approved') {
            return (
                <Typography variant="caption" color="warning.main" sx={{ fontWeight: 600 }}>
                    Approved
                </Typography>
            );
        }

        if (rowStatus === 'partially approved') {
            return (
                <Typography variant="caption" sx={{ fontWeight: 600, color: 'warning.dark' }}>
                    Partially Approved
                </Typography>
            );
        }

        if (rowStatus === 'finance reviewed' || rowStatus === 'paid') {
            return (
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 600 }}>
                    {row.status}
                </Typography>
            );
        }

        if (rowStatus === 'submitted') {
            return (
                <Stack direction="row" spacing={0.5} alignItems="center">
                    <Tooltip title="Dept Approve">
                        <span>
                            <IconButton
                                size="small"
                                color="success"
                                disabled={isBusy}
                                onClick={() => handleApprovalAction(row.id, 'dept_head_approved')}
                            >
                                <ThumbUpIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Partially Approve">
                        <span>
                            <IconButton
                                size="small"
                                sx={{ color: 'warning.main' }}
                                disabled={isBusy}
                                onClick={() => openPartialApproveDialog(row.id, row.amount)}
                            >
                                <ThumbsUpDownIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Reject">
                        <span>
                            <IconButton
                                size="small"
                                color="error"
                                disabled={isBusy}
                                onClick={() => openRejectDialog(row.id)}
                            >
                                <CloseIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            );
        }

        return (
            <Typography variant="caption" color="text.secondary">{row.status || '-'}</Typography>
        );
    };

    const exportOverviewPdf = () => {
        const rows = filteredOverviewRows;
        const rowHtml = rows.map((row, i) =>
            `<tr><td>${i + 1}</td><td>${row.member_name || '-'}</td><td>${row.department || '-'}</td><td>${row.category || '-'}</td><td>${formatCurrency(row.amount)}</td><td>${row.spent_on || '-'}</td><td>${row.status || '-'}</td></tr>`
        ).join('');
        const html = `<html><head><title>HR Expenses</title><style>body{font-family:Arial;margin:18px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ccc;padding:6px}th{background:#f2f2f2}</style></head><body><h1>HR Expenses Overview</h1><table><thead><tr><th>#</th><th>Member</th><th>Dept</th><th>Category</th><th>Amount</th><th>Date</th><th>Status</th></tr></thead><tbody>${rowHtml}</tbody></table></body></html>`;
        const popup = window.open('', '_blank', 'width=980,height=700');
        if (!popup) return;
        popup.document.open(); popup.document.write(html); popup.document.close(); popup.focus(); popup.print();
    };

    const exportMemberPdf = () => {
        const profile = memberDetail.profile || EMPTY_MEMBER_DETAIL.profile;
        const rows = Array.isArray(memberDetail.expenses) ? memberDetail.expenses : [];
        const rowHtml = rows.map((row, i) =>
            `<tr><td>${i + 1}</td><td>${row.category || '-'}</td><td>${formatCurrency(row.amount)}</td><td>${row.spent_on || '-'}</td><td>${row.status || '-'}</td><td>${row.notes || '-'}</td></tr>`
        ).join('');
        const html = `<html><head><title>${profile.employee_name || 'Member'}</title><style>body{font-family:Arial;margin:18px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ccc;padding:6px}th{background:#f2f2f2}</style></head><body><h1>${profile.employee_name || 'Member'} Expenses</h1><p>Dept: ${profile.department || '-'}</p><table><thead><tr><th>#</th><th>Category</th><th>Amount</th><th>Date</th><th>Status</th><th>Notes</th></tr></thead><tbody>${rowHtml}</tbody></table></body></html>`;
        const popup = window.open('', '_blank', 'width=980,height=700');
        if (!popup) return;
        popup.document.open(); popup.document.write(html); popup.document.close(); popup.focus(); popup.print();
    };

    const renderOverview = () => (
        <Stack spacing={2} sx={{ p: { xs: 1.5, md: 2 } }}>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Box sx={{ overflowX: 'auto', pt: 1.5, pb: 0.5 }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 1340, flexWrap: 'nowrap' }}>
                        <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={() => loadOverview(true, false)}>
                            Refresh
                        </Button>
                        <Button variant="outlined" size="small" startIcon={<DownloadIcon />} onClick={exportOverviewPdf}>
                            Export PDF
                        </Button>

                        <FormControl size="small" sx={{ minWidth: 220 }}>
                            <InputLabel>Department</InputLabel>
                            <Select label="Department" value={department} onChange={(e) => setDepartment(e.target.value)}>
                                {(overview.departments || [{ value: 'all', label: 'All Departments' }]).map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <FormControl size="small" sx={{ minWidth: 210 }}>
                            <InputLabel>Status</InputLabel>
                            <Select label="Status" value={overviewStatusFilter} onChange={(e) => setOverviewStatusFilter(String(e.target.value || 'all'))}>
                                <MenuItem value="all">All Statuses</MenuItem>
                                <MenuItem value="Draft">Draft</MenuItem>
                                <MenuItem value="Submitted">Submitted</MenuItem>
                                <MenuItem value="Dept Head Approved">Dept Head Approved</MenuItem>
                                <MenuItem value="Partially Approved">Partially Approved</MenuItem>
                                <MenuItem value="Finance Reviewed">Finance Reviewed</MenuItem>
                                <MenuItem value="Paid">Paid</MenuItem>
                                <MenuItem value="Rejected">Rejected</MenuItem>
                            </Select>
                        </FormControl>

                        <FormControl size="small" sx={{ minWidth: 190 }}>
                            <InputLabel>Category</InputLabel>
                            <Select label="Category" value={overviewCategoryFilter} onChange={(e) => setOverviewCategoryFilter(String(e.target.value || 'all').toLowerCase())}>
                                {overviewCategories.map((cat) => {
                                    const label = cat === 'all' ? 'All Categories' : cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
                                    return <MenuItem key={cat} value={cat}>{label}</MenuItem>;
                                })}
                            </Select>
                        </FormControl>

                        <FormControl size="small" sx={{ minWidth: 170 }}>
                            <InputLabel>Timeline</InputLabel>
                            <Select label="Timeline" value={overviewTimelineFilter} onChange={(e) => setOverviewTimelineFilter(String(e.target.value || 'all'))}>
                                <MenuItem value="all">All Time</MenuItem>
                                <MenuItem value="7d">Last 7 Days</MenuItem>
                                <MenuItem value="30d">Last 30 Days</MenuItem>
                                <MenuItem value="90d">Last 90 Days</MenuItem>
                                <MenuItem value="180d">Last 180 Days</MenuItem>
                            </Select>
                        </FormControl>

                        <FormControl size="small" sx={{ minWidth: 180 }}>
                            <InputLabel>Sort By</InputLabel>
                            <Select label="Sort By" value={overviewSortBy} onChange={(e) => setOverviewSortBy(String(e.target.value || 'date_desc'))}>
                                <MenuItem value="date_desc">Date: Newest</MenuItem>
                                <MenuItem value="date_asc">Date: Oldest</MenuItem>
                                <MenuItem value="amount_desc">Amount: High to Low</MenuItem>
                                <MenuItem value="amount_asc">Amount: Low to High</MenuItem>
                                <MenuItem value="member_asc">Member: A to Z</MenuItem>
                                <MenuItem value="status_asc">Status: A to Z</MenuItem>
                            </Select>
                        </FormControl>
                    </Stack>
                </Box>
            </Paper>

            <Grid container spacing={1.5}>
                {[
                    { title: 'Total Submitted', amount: summary.total_submitted_amount, subtitle: `${summary.total_entries || 0} total entries`, color: '#3949ab' },
                    { title: 'Pending Approval', amount: summary.pending_approval_amount, subtitle: `${summary.pending_entries || 0} entries awaiting`, color: '#ef6c00' },
                    { title: 'Dept Approved', amount: summary.approved_amount, subtitle: `${summary.approved_entries || 0} entries approved`, color: '#1565c0' },
                    { title: 'Total Paid', amount: summary.paid_amount, subtitle: `${summary.paid_entries || 0} entries paid`, color: '#2e7d32' },
                    { title: 'Rejected', amount: summary.rejected_amount, subtitle: `${summary.rejected_entries || 0} entries declined`, color: '#c62828' },
                ].map((card) => (
                    <Grid item xs={12} sm={6} md={2.4} key={card.title}>
                        <StatCard {...card} />
                    </Grid>
                ))}
            </Grid>

            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1.25, color: 'text.secondary' }}>Team Members</Typography>
                <Grid container spacing={1.5}>
                    {(overview.members || []).map((member) => (
                        <Grid item xs={12} sm={6} md={4} lg={3} key={member.user_id}>
                            <Paper
                                variant="outlined"
                                sx={{ p: 1.25, borderRadius: 2, height: '100%', cursor: 'pointer', '&:hover': { borderColor: 'primary.main', boxShadow: 2 } }}
                                onClick={() => handleOpenMember(member.user_id)}
                            >
                                <Stack spacing={1}>
                                    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{member.member_name || 'Unknown Member'}</Typography>
                                        {Number(member.pending_count || 0) > 0 && (
                                            <Chip size="small" color="warning" label={`${member.pending_count} pending`} />
                                        )}
                                    </Stack>
                                    <Typography variant="caption" color="text.secondary">{member.department || 'No department'}</Typography>
                                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                                        <Stack spacing={0.25} flex={1}>
                                            <Typography variant="h6" sx={{ fontWeight: 700, color: '#ef6c00' }}>{formatCurrency(member.pending_approval_amount)}</Typography>
                                            <Typography variant="caption" color="text.secondary">pending approval</Typography>
                                        </Stack>
                                        <Stack spacing={0.25} flex={1} alignItems="flex-end">
                                            <Typography variant="h6" sx={{ fontWeight: 700, color: '#6a1b9a' }}>{formatCurrency(member.unpaid_amount)}</Typography>
                                            <Typography variant="caption" color="text.secondary">unpaid</Typography>
                                        </Stack>
                                    </Stack>
                                    <Stack direction="row" spacing={0.75}>
                                        <Chip size="small" label={`Approved ${member.approved_count || 0}`} color="info" variant="outlined" />
                                        <Chip size="small" label={`Paid ${member.paid_count || 0}`} color="success" variant="outlined" />
                                        <Chip size="small" label={`Entries ${member.entries_count || 0}`} variant="outlined" />
                                    </Stack>
                                </Stack>
                            </Paper>
                        </Grid>
                    ))}
                    {!overview.members?.length && (
                        <Grid item xs={12}>
                            <Typography variant="body2" color="text.secondary">No members found for this filter.</Typography>
                        </Grid>
                    )}
                </Grid>
            </Paper>

            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }} sx={{ px: 2, py: 1.5 }} spacing={1}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Submissions</Typography>
                    <Typography variant="caption" color="text.secondary">{filteredOverviewRows.length} rows</Typography>
                </Stack>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Member</TableCell>
                                <TableCell>Category</TableCell>
                                <TableCell>Amount</TableCell>
                                <TableCell>Date</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell>Actions</TableCell>
                                <TableCell>Receipt</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filteredOverviewRows.map((row) => (
                                <TableRow key={row.id} hover>
                                    <TableCell>
                                        <Stack>
                                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{row.member_name || '-'}</Typography>
                                            <Typography variant="caption" color="text.secondary">{row.department || 'No department'}</Typography>
                                        </Stack>
                                    </TableCell>
                                    <TableCell>{String(row.category || '').replace(/_/g, ' ')}</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>
                                        {row.approved_amount !== null && row.approved_amount !== undefined && String(row.status || '').toLowerCase() === 'partially approved' ? (
                                            <Stack spacing={0.25}>
                                                <Typography variant="body2" sx={{ fontWeight: 700 }}>{formatCurrency(row.approved_amount)}</Typography>
                                                <Typography variant="caption" sx={{ textDecoration: 'line-through', color: 'text.secondary' }}>{formatCurrency(row.amount)}</Typography>
                                            </Stack>
                                        ) : formatCurrency(row.amount)}
                                    </TableCell>
                                    <TableCell>{formatDate(row.spent_on)}</TableCell>
                                    <TableCell>
                                        <Stack spacing={0.25}>
                                            <Chip size="small" label={row.status || 'Draft'} color={statusColor(row.status)} variant="outlined" />
                                            {String(row.status || '').toLowerCase() === 'paid' && row.payment_method && (
                                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                                                    {row.payment_method.replace(/_/g, ' ')}{row.payment_date ? ` · ${formatDate(row.payment_date)}` : ''}
                                                </Typography>
                                            )}
                                            {row.finance_entry_id && (
                                                <Chip
                                                    size="small"
                                                    label={`GL #${row.finance_entry_id}`}
                                                    color="primary"
                                                    variant="outlined"
                                                    clickable
                                                    onClick={() => window.open('/finance', '_blank', 'noopener,noreferrer')}
                                                />
                                            )}
                                        </Stack>
                                    </TableCell>
                                    <TableCell>{renderActionButtons(row)}</TableCell>
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
                            {!filteredOverviewRows.length && (
                                <TableRow>
                                    <TableCell colSpan={7}>
                                        <Typography variant="body2" color="text.secondary">No expenses match selected filters.</Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Stack>
    );

    const renderMemberDetail = () => {
        const profile = memberDetail.profile || EMPTY_MEMBER_DETAIL.profile;
        const quickStats = memberDetail.quick_stats || EMPTY_MEMBER_DETAIL.quick_stats;

        const memberStatCards = [
            { title: 'TOTAL SUBMITTED', amount: quickStats.total_amount, subtitle: `${quickStats.entries || 0} total entries`, color: '#3949ab' },
            { title: 'PENDING APPROVAL', amount: quickStats.pending_amount, subtitle: `${quickStats.pending || 0} entries awaiting`, color: '#ef6c00' },
            { title: 'DEPT APPROVED', amount: quickStats.dept_approved_amount, subtitle: `${quickStats.approved || 0} entries approved`, color: '#1565c0' },
            { title: 'TOTAL PAID', amount: quickStats.paid_amount, subtitle: `${quickStats.paid || 0} entries paid`, color: '#2e7d32' },
            { title: 'TOTAL UNPAID', amount: quickStats.total_unpaid_amount, subtitle: 'submitted − paid', color: '#6a1b9a' },
            { title: 'REJECTED', amount: quickStats.rejected_amount ?? null, subtitle: `${quickStats.rejected || 0} entries declined`, color: '#c62828' },
        ];

        return (
            <Box sx={{ width: '100%', boxSizing: 'border-box', p: { xs: 1.5, md: 2 } }}>
                <Stack spacing={2} sx={{ width: '100%' }}>
                    {/* Top nav */}
                    <Stack direction="row" alignItems="center" justifyContent="space-between">
                        <Button variant="text" startIcon={<ArrowBackIcon />} onClick={handleBackToOverview}>
                            Back to Overview
                        </Button>
                        <Typography variant="subtitle2" color="text.secondary">Member Expense Tracker</Typography>
                    </Stack>

                    {/* Header card: name + stat cards */}
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, width: '100%', boxSizing: 'border-box' }}>
                        <Stack spacing={2}>
                            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }} justifyContent="space-between">
                                <Box>
                                    <Typography variant="h6" sx={{ fontWeight: 700 }}>{profile.employee_name || 'Member'}</Typography>
                                    <Typography variant="body2" color="text.secondary">{profile.designation || 'Team Member'}</Typography>
                                </Box>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    disabled={requestApprovalLoading}
                                    onClick={handleRequestApproval}
                                    sx={{ flexShrink: 0 }}
                                >
                                    {requestApprovalLoading ? 'Submitting...' : 'Submit Drafts for Approval'}
                                </Button>
                            </Stack>

                            <Grid container spacing={1.5}>
                                {memberStatCards.map((card) => (
                                    <Grid item xs={6} sm={4} md={2} key={card.title}>
                                        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, borderTop: `3px solid ${card.color}`, height: '100%' }}>
                                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: 0.5, display: 'block' }}>
                                                {card.title}
                                            </Typography>
                                            <Typography variant="h6" sx={{ fontWeight: 700, color: card.color, mt: 0.25 }}>
                                                {formatCurrency(card.amount ?? 0)}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">{card.subtitle}</Typography>
                                        </Paper>
                                    </Grid>
                                ))}
                            </Grid>
                        </Stack>
                    </Paper>

                    {/* Expense entries table — full width */}
                    <Paper variant="outlined" sx={{ borderRadius: 2, width: '100%', boxSizing: 'border-box' }}>
                        <Stack
                            direction={{ xs: 'column', md: 'row' }}
                            justifyContent="space-between"
                            alignItems={{ xs: 'flex-start', md: 'center' }}
                            sx={{ px: 2, py: 1.5 }}
                            spacing={1}
                        >
                            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Expense Entries</Typography>
                            <Stack direction="row" spacing={1} alignItems="center">
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

                        {showMemberFilters && (
                            <Box sx={{ px: 2, pb: 2, pt: 0.5 }}>
                                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center" useFlexGap flexWrap="wrap">
                                    <FormControl size="small" sx={{ minWidth: 150, flexGrow: { xs: 1, sm: 0 } }}>
                                        <InputLabel>Status</InputLabel>
                                        <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                                            {(memberDetail.status_options || ['all']).map((option) => {
                                                const val = String(option || 'all');
                                                return <MenuItem key={val} value={val}>{val === 'all' ? 'All Statuses' : val}</MenuItem>;
                                            })}
                                        </Select>
                                    </FormControl>

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
                            </Box>
                        )}

                        <Box sx={{ px: 2, pb: 1 }}>
                            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                                {(memberDetail.available_categories || ['all']).map((category) => {
                                    const value = String(category || 'all').toLowerCase();
                                    const isActive = value === categoryFilter;
                                    const label = value === 'all' ? 'All Categories' : value.replace(/_/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());
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

                        <TableContainer sx={{ width: '100%' }}>
                            <Table size="small" sx={{ tableLayout: 'auto', width: '100%' }}>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Category / Dept</TableCell>
                                        <TableCell>Amount</TableCell>
                                        <TableCell>Status &amp; Trail</TableCell>
                                        <TableCell>Notes / GL</TableCell>
                                        <TableCell>Receipt</TableCell>
                                        <TableCell>Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {(memberDetail.expenses || []).map((row) => (
                                        <TableRow key={row.id} hover>
                                            <TableCell>
                                                <Stack>
                                                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{formatDate(row.spent_on)}</Typography>
                                                    {row.bill_date && row.bill_date !== row.spent_on && (
                                                        <Typography variant="caption" color="text.secondary">Bill: {formatDate(row.bill_date)}</Typography>
                                                    )}
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                <Stack>
                                                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{String(row.category || '').replace(/_/g, ' ')}</Typography>
                                                    <Typography variant="caption" color="text.secondary">{row.department || '-'}</Typography>
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                {row.approved_amount !== null && row.approved_amount !== undefined && String(row.status || '').toLowerCase() === 'partially approved' ? (
                                                    <Stack spacing={0.25}>
                                                        <Typography variant="body2" sx={{ fontWeight: 700 }}>{formatCurrency(row.approved_amount)}</Typography>
                                                        <Typography variant="caption" sx={{ textDecoration: 'line-through', color: 'text.secondary' }}>{formatCurrency(row.amount)}</Typography>
                                                    </Stack>
                                                ) : (
                                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{formatCurrency(row.amount)}</Typography>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Stack spacing={0.5}>
                                                    <Chip size="small" color={statusColor(row.status)} variant="outlined" label={row.status || 'Draft'} />
                                                    {row.rejection_reason && (
                                                        <Typography variant="caption" color="error.main" sx={{ fontSize: 10 }}>
                                                            Reason: {row.rejection_reason}
                                                        </Typography>
                                                    )}
                                                    {Array.isArray(row.workflow_steps) && row.workflow_steps.length > 0 && (
                                                        <WorkflowTrail steps={row.workflow_steps} />
                                                    )}
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                <Stack spacing={0.25}>
                                                    <Typography variant="caption">{row.notes || 'No notes'}</Typography>
                                                    {row.finance_entry_id && (
                                                        <Chip
                                                            size="small"
                                                            label={`GL #${row.finance_entry_id}`}
                                                            color="primary"
                                                            variant="outlined"
                                                            clickable
                                                            onClick={() => window.open('/finance', '_blank')}
                                                        />
                                                    )}
                                                    {row.payment_method && (
                                                        <Typography variant="caption" color="text.secondary">
                                                            {row.payment_method.replace(/_/g, ' ')} · {formatDate(row.payment_date)}
                                                        </Typography>
                                                    )}
                                                </Stack>
                                            </TableCell>
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
                                            <TableCell>{renderActionButtons(row)}</TableCell>
                                        </TableRow>
                                    ))}
                                    {!memberDetail.expenses?.length && (
                                        <TableRow>
                                            <TableCell colSpan={7}>
                                                <Typography variant="body2" color="text.secondary">No entries match selected filters.</Typography>
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </Stack>
            </Box>
        );
    };

    if (overviewLoading && !activeMemberId) {
        return (
            <Stack sx={{ p: 3, alignItems: 'center', justifyContent: 'center' }} spacing={1}>
                <CircularProgress size={26} />
                <Typography variant="body2" color="text.secondary">Loading HR expenses...</Typography>
            </Stack>
        );
    }

    return (
        <Box sx={{ minHeight: '100%', width: '100%', boxSizing: 'border-box', bgcolor: 'background.default' }}>
            <Box sx={{ px: { xs: 1.5, md: 2 }, pt: 1.5 }}>
                {message.text && (
                    <Alert severity={message.type} onClose={() => setMessage({ type: 'success', text: '' })}>
                        {message.text}
                    </Alert>
                )}
            </Box>

            {/* memberLoading spinner only shown on first navigation to a member, never during background refresh */}
            {memberLoading && activeMemberId ? (
                <Stack sx={{ p: 3, alignItems: 'center', justifyContent: 'center' }} spacing={1}>
                    <CircularProgress size={24} />
                    <Typography variant="body2" color="text.secondary">Loading member details...</Typography>
                </Stack>
            ) : activeMemberId ? (
                renderMemberDetail()
            ) : (
                renderOverview()
            )}

            {/* Reject Dialog */}
            <Dialog open={rejectDialog.open} onClose={() => setRejectDialog((p) => ({ ...p, open: false }))} maxWidth="sm" fullWidth>
                <DialogTitle>Reject Expense</DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ mb: 2 }}>Provide a reason for rejection (optional but recommended).</DialogContentText>
                    <TextField
                        fullWidth multiline rows={3} label="Rejection Reason"
                        value={rejectDialog.reason}
                        onChange={(e) => setRejectDialog((p) => ({ ...p, reason: e.target.value }))}
                        placeholder="e.g. Missing receipt, amount mismatch..."
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRejectDialog((p) => ({ ...p, open: false }))}>Cancel</Button>
                    <Button color="error" variant="contained" onClick={handleRejectConfirm}>Reject</Button>
                </DialogActions>
            </Dialog>

            {/* Partial Approval Dialog */}
            <Dialog
                open={partialApproveDialog.open}
                onClose={() => setPartialApproveDialog((p) => ({ ...p, open: false }))}
                maxWidth="xs"
                fullWidth
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ThumbsUpDownIcon sx={{ color: 'warning.main' }} />
                    Partially Approve Expense
                </DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ mb: 2 }}>
                        Enter the amount to approve. The requested amount was{' '}
                        <strong>{formatCurrency(partialApproveDialog.maxAmount)}</strong>.
                    </DialogContentText>
                    <TextField
                        fullWidth autoFocus type="number" label="Approved Amount"
                        inputProps={{ min: 1, max: partialApproveDialog.maxAmount, step: 1 }}
                        value={partialApproveDialog.amount}
                        onChange={(e) => setPartialApproveDialog((p) => ({ ...p, amount: e.target.value }))}
                        helperText={`Enter a value between ₹1 and ${formatCurrency(partialApproveDialog.maxAmount)}`}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPartialApproveDialog((p) => ({ ...p, open: false }))}>Cancel</Button>
                    <Button
                        color="warning" variant="contained" startIcon={<ThumbsUpDownIcon />}
                        onClick={handlePartialApproveConfirm}
                        disabled={!partialApproveDialog.amount || Number(partialApproveDialog.amount) <= 0}
                    >
                        Partially Approve
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}