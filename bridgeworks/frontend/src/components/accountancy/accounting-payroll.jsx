import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Divider,
    FormControl,
    Grid,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Paper,
    Select,
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
    useTheme,
} from '@mui/material';
import {
    AccountBalance as AccountBalanceIcon,
    CheckCircle as CheckCircleIcon,
    Close as CloseIcon,
    Download as DownloadIcon,
    ExpandLess as ExpandLessIcon,
    ExpandMore as ExpandMoreIcon,
    History as HistoryIcon,
    Lock as LockIcon,
    MonetizationOn as MoneyIcon,
    Payment as PaymentIcon,
    Print as PrintIcon,
    Refresh as RefreshIcon,
    TaskAlt as TaskAltIcon,
    VerifiedUser as VerifiedUserIcon,
} from '@mui/icons-material';
import {
    executeHrPayrollRunAction,
    getFinancePayrollLedger,
    getHrPayrollRunStatus,
    listHrPayrollDashboard,
    verifyFinancePayrollRecord,
} from '../mydesk/mydeskService';
import { usePagePermissions } from '../../utils/rbac';

const MONTHS = [
    { value: 1, label: 'January' },
    { value: 2, label: 'February' },
    { value: 3, label: 'March' },
    { value: 4, label: 'April' },
    { value: 5, label: 'May' },
    { value: 6, label: 'June' },
    { value: 7, label: 'July' },
    { value: 8, label: 'August' },
    { value: 9, label: 'September' },
    { value: 10, label: 'October' },
    { value: 11, label: 'November' },
    { value: 12, label: 'December' },
];

function fmt(val) {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(val || 0));
}

function fmtDate(val) {
    if (!val) return '-';
    const d = new Date(val.includes('T') ? val : val + 'T00:00:00');
    return isNaN(d) ? val : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function stageChip(stage) {
    const map = {
        draft: { label: 'Draft', color: 'default' },
        attendance_locked: { label: 'Attendance Locked', color: 'info' },
        calculated: { label: 'Calculated', color: 'warning' },
        hr_approved: { label: 'HR Approved', color: 'warning' },
        finance_approved: { label: 'Finance Approved', color: 'secondary' },
        locked: { label: 'Locked', color: 'success' },
    };
    const m = map[stage] || { label: stage, color: 'default' };
    return <Chip size="small" label={m.label} color={m.color} variant="outlined" />;
}

function StatCard({ icon, title, value, color = '#3949ab' }) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const resolvedColor = useMemo(() => {
        if (color === '#1565c0' || color === '#3949ab') return isDark ? '#90caf9' : '#1565c0';
        if (color === '#6a1b9a') return isDark ? '#ce93d8' : '#6a1b9a';
        if (color === '#c62828') return isDark ? '#ef9a9a' : '#c62828';
        if (color === '#2e7d32') return isDark ? '#a5d6a7' : '#2e7d32';
        return color;
    }, [color, isDark]);

    return (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: '3px solid', borderTopColor: resolvedColor }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.75 }}>
                <Box sx={{ color: resolvedColor, display: 'flex' }}>{icon}</Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}>{title}</Typography>
            </Stack>
            <Typography variant="h5" sx={{ fontWeight: 700, color: resolvedColor }}>{value}</Typography>
        </Paper>
    );
}

function DeductionDetail({ rows }) {
    if (!Array.isArray(rows) || rows.length === 0) return <Typography variant="caption" color="text.secondary">—</Typography>;
    return (
        <Stack spacing={0.25}>
            {rows.map((r, i) => (
                <Stack key={i} direction="row" justifyContent="space-between" spacing={2}>
                    <Typography variant="caption" color="text.secondary">{r.component}</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{fmt(r.amount)}</Typography>
                </Stack>
            ))}
        </Stack>
    );
}

export default function AccountingPayroll() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const { canCreate, canEdit, canViewAmounts } = usePagePermissions();

    const fmt = (val) => {
        if (!canViewAmounts) return '₹ ****';
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(val || 0));
    };

    const getVal = (v) => canViewAmounts ? v : '****';

    const now = new Date();
    const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
    const [selectedYear, setSelectedYear] = useState(now.getFullYear());
    const [activeTab, setActiveTab] = useState(0);
    const [showLedger, setShowLedger] = useState(false);

    const [loading, setLoading] = useState(false);
    const [runState, setRunState] = useState(null);
    const [rows, setRows] = useState([]);
    const [totals, setTotals] = useState({ gross: 0, deductions: 0, net: 0 });
    const [verifiedCount, setVerifiedCount] = useState(0);
    const [ledger, setLedger] = useState([]);
    const [ledgerLoading, setLedgerLoading] = useState(false);

    const [message, setMessage] = useState({ type: 'success', text: '' });
    const [busy, setBusy] = useState(false);
    const [expandedRow, setExpandedRow] = useState(null);

    // Approve dialog
    const [approveDialog, setApproveDialog] = useState(false);
    // GL Post dialog
    const [postGLDialog, setPostGLDialog] = useState(false);
    // Lock dialog
    const [lockDialog, setLockDialog] = useState(false);

    const monthStr = useMemo(() => {
        const m = String(selectedMonth).padStart(2, '0');
        return `${selectedYear}-${m}`;
    }, [selectedMonth, selectedYear]);

    const monthLabel = useMemo(() => {
        const m = MONTHS.find((x) => x.value === selectedMonth);
        return `${m ? m.label : selectedMonth} ${selectedYear}`;
    }, [selectedMonth, selectedYear]);

    const setErr = (e, fallback) => setMessage({ type: 'error', text: typeof e === 'string' ? e : e?.detail || e?.message || fallback });

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [runRes, dashRes] = await Promise.all([
                getHrPayrollRunStatus({ month: monthStr }),
                listHrPayrollDashboard({ month: monthStr }),
            ]);
            setRunState(runRes?.run || null);
            setRows(dashRes?.rows || []);
            setTotals(dashRes?.totals || { gross: 0, deductions: 0, net: 0 });
            setVerifiedCount(dashRes?.verified_count || 0);
        } catch (e) {
            setErr(e, 'Failed to load payroll data.');
        } finally {
            setLoading(false);
        }
    }, [monthStr]);

    const loadLedger = useCallback(async () => {
        setLedgerLoading(true);
        try {
            const res = await getFinancePayrollLedger();
            setLedger(res?.runs || []);
        } catch (e) {
            setErr(e, 'Failed to load payroll ledger.');
        } finally {
            setLedgerLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        if (showLedger) loadLedger();
    }, [showLedger, loadLedger]);

    const doAction = async (action, extraPayload = {}, successMsg = '') => {
        setBusy(true);
        try {
            const res = await executeHrPayrollRunAction({ action, month: monthStr, ...extraPayload });
            if (successMsg) setMessage({ type: 'success', text: successMsg });
            else if (res?.detail) setMessage({ type: 'success', text: res.detail });
            await load();
        } catch (e) {
            setErr(e, `Action '${action}' failed.`);
        } finally {
            setBusy(false);
        }
    };

    const handleVerify = async (userId) => {
        setBusy(true);
        try {
            const res = await verifyFinancePayrollRecord(monthStr, userId);
            if (res?.detail) setMessage({ type: 'success', text: res.detail });
            setVerifiedCount(res?.verified_record?.verified_count || verifiedCount);
            setRows((prev) => prev.map((r) =>
                r.user_id === userId
                    ? { ...r, finance_verified: !r.finance_verified }
                    : r
            ));
        } catch (e) {
            setErr(e, 'Failed to update verification.');
        } finally {
            setBusy(false);
        }
    };

    const totalEmployees = rows.filter((r) => r.has_record).length;
    const allVerified = totalEmployees > 0 && verifiedCount >= totalEmployees;

    const canApproveFinance = runState?.hr_approved && allVerified && !runState?.finance_approved;
    const canPostGL = runState?.finance_approved && !runState?.gl_posted;
    const canLock = runState?.finance_approved && !runState?.is_locked;

    // Export CSV
    const exportCSV = () => {
        const headers = ['Employee', 'Dept', 'Working Days', 'Present Days', 'LOP', 'Gross', 'Deductions', 'Net Pay', 'Status', 'Verified'];
        const csvRows = rows.map((r) => [
            r.employee_name || '',
            r.department || '',
            r.working_days || 0,
            r.present_days || 0,
            r.lop_days || 0,
            getVal(r.gross || 0),
            getVal(r.deductions || 0),
            getVal(r.net || 0),
            r.status || '',
            r.finance_verified ? 'Yes' : 'No',
        ]);
        const content = [headers, ...csvRows].map((row) => row.join(',')).join('\n');
        const blob = new Blob([content], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `payroll_${monthStr}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // Print
    const printTable = () => {
        const rowsHtml = rows.map((r, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${r.employee_name || ''}</td>
                <td>${r.department || ''}</td>
                <td>${r.working_days || '-'}</td>
                <td>${r.present_days || '-'}</td>
                <td>${getVal(r.gross || 0)}</td>
                <td>${getVal(r.deductions || 0)}</td>
                <td>${getVal(r.net || 0)}</td>
                <td>${r.status || '-'}</td>
                <td>${r.finance_verified ? '✓' : ''}</td>
            </tr>
        `).join('');
        const html = `<html><head><title>Payroll ${monthLabel}</title><style>body{font-family:Arial;margin:16px}h1{font-size:16px}table{width:100%;border-collapse:collapse;font-size:11px}th,td{border:1px solid #ccc;padding:5px}th{background:#f0f0f0}tfoot td{font-weight:bold}</style></head><body><h1>Payroll — ${monthLabel}</h1><p>Total Gross: ${fmt(totals.gross)} | Total Deductions: ${fmt(totals.deductions)} | Net Payout: ${fmt(totals.net)}</p><table><thead><tr><th>#</th><th>Employee</th><th>Dept</th><th>Work Days</th><th>Present</th><th>Gross</th><th>Deductions</th><th>Net Pay</th><th>Status</th><th>Verified</th></tr></thead><tbody>${rowsHtml}</tbody><tfoot><tr><td colspan="5">TOTALS</td><td>${fmt(totals.gross)}</td><td>${fmt(totals.deductions)}</td><td>${fmt(totals.net)}</td><td colspan="2"></td></tr></tfoot></table></body></html>`;
        const popup = window.open('', '_blank', 'width=1050,height=700');
        if (!popup) return;
        popup.document.open(); popup.document.write(html); popup.document.close(); popup.focus(); popup.print();
    };

    const renderHeader = () => (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 2 }}>
            <Stack direction={{ xs: 'column', md: 'row' }} alignItems={{ xs: 'flex-start', md: 'center' }} justifyContent="space-between" spacing={2}>
                <Stack>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>Payroll</Typography>
                    <Typography variant="caption" color="text.secondary">Finance Approval &amp; Accounting</Typography>
                </Stack>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
                    <FormControl size="small" sx={{ minWidth: 130 }}>
                        <InputLabel>Month</InputLabel>
                        <Select label="Month" value={selectedMonth} onChange={(e) => setSelectedMonth(Number(e.target.value))}>
                            {MONTHS.map((m) => <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 90 }}>
                        <InputLabel>Year</InputLabel>
                        <Select label="Year" value={selectedYear} onChange={(e) => setSelectedYear(Number(e.target.value))}>
                            {[2023, 2024, 2025, 2026, 2027].map((y) => <MenuItem key={y} value={y}>{y}</MenuItem>)}
                        </Select>
                    </FormControl>
                    {runState && stageChip(runState.stage)}
                    <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>Refresh</Button>
                    <Button size="small" variant="outlined" startIcon={<HistoryIcon />} onClick={() => setShowLedger((v) => !v)}>
                        {showLedger ? 'Hide' : 'Ledger'}
                    </Button>
                </Stack>
            </Stack>
        </Paper>
    );

    const renderStats = () => (
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
            <Grid item xs={12} sm={6} md={3}>
                <StatCard icon={<VerifiedUserIcon />} title="Employees" value={`${verifiedCount}/${totalEmployees} verified`} color="#1565c0" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
                <StatCard icon={<MoneyIcon />} title="Total Gross" value={fmt(totals.gross)} color="#6a1b9a" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
                <StatCard icon={<CloseIcon />} title="Deductions" value={fmt(totals.deductions)} color="#c62828" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
                <StatCard icon={<PaymentIcon />} title="Net Payout" value={fmt(totals.net)} color="#2e7d32" />
            </Grid>
        </Grid>
    );

    const renderVerifyTab = () => (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1.5 }}>
                    <Stack>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                            Payroll Verification — {monthLabel}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            Verify individually or in bulk. All must be verified to proceed.
                        </Typography>
                    </Stack>
                    <Stack direction="row" spacing={1}>
                        <Button size="small" variant="outlined" startIcon={<PrintIcon />} onClick={printTable}>Print All</Button>
                        <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={exportCSV}>Export CSV</Button>
                    </Stack>
                </Stack>

                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell padding="checkbox" />
                                <TableCell>Employee</TableCell>
                                <TableCell>Dept</TableCell>
                                <TableCell align="right">Gross</TableCell>
                                <TableCell align="right" sx={{ color: isDark ? 'info.main' : '#1d4ed8' }}>Exp. Reimb.</TableCell>
                                <TableCell align="right">Deductions</TableCell>
                                <TableCell align="right">Net Pay</TableCell>
                                <TableCell>Info</TableCell>
                                <TableCell>Verify</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rows.map((row) => (
                                <React.Fragment key={row.user_id}>
                                    <TableRow hover sx={{ opacity: row.has_record ? 1 : 0.5 }}>
                                        <TableCell padding="checkbox">
                                            <IconButton size="small" onClick={() => setExpandedRow(expandedRow === row.user_id ? null : row.user_id)}>
                                                {expandedRow === row.user_id ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                            </IconButton>
                                        </TableCell>
                                        <TableCell>
                                            <Stack>
                                                <Stack direction="row" spacing={0.75} alignItems="center">
                                                    <Box sx={{ width: 30, height: 30, borderRadius: '50%', bgcolor: 'primary.main', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>
                                                        {String(row.employee_name || '?')[0].toUpperCase()}
                                                    </Box>
                                                    <Stack>
                                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{row.employee_name || '-'}</Typography>
                                                        <Typography variant="caption" color="text.secondary">{row.bank_account_display || row.pan_masked || '-'}</Typography>
                                                    </Stack>
                                                </Stack>
                                            </Stack>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2">{row.department || '-'}</Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? 'primary.light' : '#1565c0' }}>{fmt(row.gross)}</Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? 'info.main' : '#1d4ed8' }}>
                                                {Number(row.expense_total || 0) > 0 ? fmt(row.expense_total) : '—'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 600, color: isDark ? 'error.light' : '#c62828' }}>{fmt(row.deductions)}</Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 700, color: isDark ? 'success.light' : '#2e7d32' }}>{fmt(row.net)}</Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Stack spacing={0.5}>
                                                <Typography variant="caption">{row.working_days}d work / {row.present_days}d present</Typography>
                                                {row.lop_days > 0 && <Chip size="small" label={`LOP: ${row.lop_days}d`} color="warning" variant="outlined" />}
                                            </Stack>
                                        </TableCell>
                                        <TableCell>
                                            {row.has_record ? (
                                                <Button
                                                    size="small"
                                                    variant={row.finance_verified ? 'contained' : 'outlined'}
                                                    color={row.finance_verified ? 'success' : 'primary'}
                                                    startIcon={row.finance_verified ? <CheckCircleIcon /> : null}
                                                    disabled={busy || !canEdit}
                                                    onClick={() => handleVerify(row.user_id)}
                                                 >
                                                    {row.finance_verified ? 'Verified' : 'Verify'}
                                                </Button>
                                            ) : (
                                                <Chip size="small" label="No Record" variant="outlined" color="default" />
                                            )}
                                        </TableCell>
                                    </TableRow>
                                    <TableRow>
                                        <TableCell colSpan={9} sx={{ py: 0, border: 0 }}>
                                            <Collapse in={expandedRow === row.user_id} timeout="auto" unmountOnExit>
                                                <Box sx={{ py: 1.5, px: 2 }}>
                                                    <Grid container spacing={2}>
                                                        <Grid item xs={12} md={5}>
                                                            <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary' }}>Earnings</Typography>
                                                            <Stack spacing={0.25} sx={{ mt: 0.5 }}>
                                                                {(row.earnings_breakup || []).map((e, i) => (
                                                                    <Stack key={i} direction="row" justifyContent="space-between">
                                                                        <Typography variant="caption">{e.component}</Typography>
                                                                        <Typography variant="caption" sx={{ fontWeight: 600 }}>{fmt(e.amount)}</Typography>
                                                                    </Stack>
                                                                ))}
                                                                {!row.earnings_breakup?.length && <Typography variant="caption" color="text.secondary">No breakdown available</Typography>}
                                                            </Stack>
                                                        </Grid>
                                                        <Grid item xs={12} md={4}>
                                                            <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary' }}>Deductions</Typography>
                                                            <Box sx={{ mt: 0.5 }}>
                                                                <DeductionDetail rows={row.deductions_breakup} />
                                                            </Box>
                                                        </Grid>
                                                        <Grid item xs={12} md={3}>
                                                            {Number(row.expense_total || 0) > 0 && (
                                                                <Box sx={{ p: 1, borderRadius: 1, bgcolor: isDark ? 'rgba(30, 136, 229, 0.15)' : '#eff6ff', border: `1px solid ${isDark ? 'rgba(30, 136, 229, 0.3)' : '#bfdbfe'}` }}>
                                                                    <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: isDark ? 'info.main' : '#1d4ed8', display: 'block', mb: 0.5 }}>Expense Reimb.</Typography>
                                                                    <Stack direction="row" justifyContent="space-between">
                                                                        <Typography variant="caption">Reimbursement</Typography>
                                                                        <Typography variant="caption" sx={{ fontWeight: 700, color: isDark ? 'info.main' : '#1d4ed8' }}>{fmt(row.expense_total)}</Typography>
                                                                    </Stack>
                                                                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block', fontSize: 10 }}>
                                                                        From approved expense claims
                                                                    </Typography>
                                                                </Box>
                                                            )}
                                                            {row.finance_verified_by && (
                                                                <Stack sx={{ mt: Number(row.expense_total || 0) > 0 ? 1 : 0 }}>
                                                                    <Typography variant="caption" color="text.secondary">Verified by</Typography>
                                                                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{row.finance_verified_by}</Typography>
                                                                    <Typography variant="caption" color="text.secondary">{fmtDate(row.finance_verified_at)}</Typography>
                                                                </Stack>
                                                            )}
                                                        </Grid>
                                                    </Grid>
                                                </Box>
                                            </Collapse>
                                        </TableCell>
                                    </TableRow>
                                </React.Fragment>
                            ))}
                            {rows.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={8}>
                                        <Typography variant="body2" color="text.secondary">
                                            {loading ? 'Loading...' : 'No payroll records for this period. Ask HR to run payroll calculation first.'}
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>

                {/* Totals row */}
                {rows.length > 0 && (
                    <Box sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: 'divider', bgcolor: isDark ? 'rgba(255, 255, 255, 0.02)' : 'grey.50' }}>
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Typography variant="caption" sx={{ fontWeight: 700, flex: 1 }}>TOTALS</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: isDark ? 'primary.light' : '#1565c0', minWidth: 90, textAlign: 'right' }}>{fmt(totals.gross)}</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: isDark ? 'info.main' : '#1d4ed8', minWidth: 90, textAlign: 'right' }}>
                                {fmt(rows.reduce((s, r) => s + Number(r.expense_total || 0), 0))}
                            </Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: isDark ? 'error.light' : '#c62828', minWidth: 90, textAlign: 'right' }}>{fmt(totals.deductions)}</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: isDark ? 'success.light' : '#2e7d32', minWidth: 90, textAlign: 'right' }}>{fmt(totals.net)}</Typography>
                            <Box sx={{ minWidth: 60 }} />
                            <Box sx={{ minWidth: 90 }} />
                        </Stack>
                    </Box>
                )}

                {/* Footer status */}
                <Box sx={{ px: 2, py: 1, borderTop: 1, borderColor: 'divider' }}>
                    <Stack direction="row" alignItems="center" justifyContent="space-between">
                        <Typography variant="caption" color={allVerified ? 'success.main' : 'text.secondary'} sx={{ fontWeight: allVerified ? 700 : 400 }}>
                            {verifiedCount}/{totalEmployees} verified{allVerified ? ' — ready to approve' : ' — verify all to proceed'}
                        </Typography>
                        {!allVerified && totalEmployees > 0 && (
                            <Button size="small" variant="outlined" disabled={busy || !canEdit}
                                onClick={async () => {
                                    // Verify all unverified records
                                    const unverified = rows.filter((r) => r.has_record && !r.finance_verified);
                                    for (const r of unverified) {
                                        await handleVerify(r.user_id);
                                    }
                                }}>
                                Verify All
                            </Button>
                        )}
                    </Stack>
                </Box>
            </Paper>
        </Stack>
    );

    const renderApproveTab = () => (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Finance Approval — {monthLabel}</Typography>

                <Stack spacing={1.5}>
                    <Stack direction="row" spacing={2} alignItems="center">
                        <CheckCircleIcon color={runState?.hr_approved ? 'success' : 'disabled'} />
                        <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>HR Approval</Typography>
                            <Typography variant="caption" color="text.secondary">
                                {runState?.hr_approved ? `Approved by ${runState.hr_approved_by || 'HR'} on ${fmtDate(runState.hr_approved_at)}` : 'Pending HR approval'}
                            </Typography>
                        </Box>
                    </Stack>
                    <Stack direction="row" spacing={2} alignItems="center">
                        <CheckCircleIcon color={allVerified ? 'success' : 'disabled'} />
                        <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>Finance Verification</Typography>
                            <Typography variant="caption" color="text.secondary">
                                {allVerified ? `All ${totalEmployees} records verified` : `${verifiedCount}/${totalEmployees} records verified`}
                            </Typography>
                        </Box>
                    </Stack>
                    <Stack direction="row" spacing={2} alignItems="center">
                        <CheckCircleIcon color={runState?.finance_approved ? 'success' : 'disabled'} />
                        <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>Finance Approval</Typography>
                            <Typography variant="caption" color="text.secondary">
                                {runState?.finance_approved ? `Approved by ${runState.finance_approved_by || 'Finance'} on ${fmtDate(runState.finance_approved_at)}` : 'Pending'}
                            </Typography>
                        </Box>
                    </Stack>
                </Stack>

                <Divider sx={{ my: 2 }} />

                <Stack spacing={1} sx={{ mb: 2 }}>
                    {['gross', 'deductions', 'net'].map((key) => (
                        <Stack key={key} direction="row" justifyContent="space-between">
                            <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>{key === 'net' ? 'Net Payout' : key === 'gross' ? 'Total Gross' : 'Total Deductions'}</Typography>
                            <Typography variant="body2" sx={{ fontWeight: 700 }}>{fmt(totals[key])}</Typography>
                        </Stack>
                    ))}
                </Stack>

                <Button
                    variant="contained" color="primary" fullWidth size="large"
                    disabled={!canApproveFinance || busy || !canEdit}
                    onClick={() => setApproveDialog(true)}
                    startIcon={<TaskAltIcon />}
                >
                    {runState?.finance_approved ? 'Already Approved' : 'Approve Finance'}
                </Button>
                {!runState?.hr_approved && (
                    <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
                        Waiting for HR approval before Finance can approve.
                    </Typography>
                )}
                {!allVerified && runState?.hr_approved && (
                    <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
                        All records must be verified on the Verify tab first.
                    </Typography>
                )}
            </Paper>
        </Stack>
    );

    const renderPaymentTab = () => (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Payment — {monthLabel}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                    Download the bank transfer file and upload to your bank portal. Mark as paid once transfers are complete.
                </Typography>

                {!runState?.finance_approved && (
                    <Alert severity="info" sx={{ mb: 2 }}>Finance approval is required before generating payment files.</Alert>
                )}

                <Stack spacing={1.5}>
                    <Button
                        variant="outlined" fullWidth size="large" startIcon={<DownloadIcon />}
                        disabled={!runState?.finance_approved || busy || !canViewAmounts}
                        onClick={() => doAction('export_bank_file', {}, 'Bank transfer file ready.')}
                    >
                        {runState?.bank_file_generated ? 'Re-download Bank File' : 'Download Bank Transfer File'}
                    </Button>
                    {runState?.bank_file_generated && (
                        <Typography variant="caption" color="success.main">
                            Bank file last generated on {fmtDate(runState.bank_file_generated_at)}
                        </Typography>
                    )}
                    <Button
                        variant="outlined" fullWidth size="large" startIcon={<PrintIcon />}
                        disabled={!runState?.finance_approved || busy || !canEdit}
                        onClick={() => doAction('generate_payslips', {}, 'Payslips generated and sent to employees.')}
                    >
                        {runState?.payslips_generated ? 'Regenerate Payslips' : 'Generate &amp; Send Payslips'}
                    </Button>
                    {runState?.payslips_generated && (
                        <Typography variant="caption" color="success.main">
                            Payslips last generated on {fmtDate(runState.payslips_generated_at)}
                        </Typography>
                    )}
                </Stack>

                <Divider sx={{ my: 2 }} />

                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>Employees</Typography>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Employee</TableCell>
                                <TableCell>Bank</TableCell>
                                <TableCell align="right">Net Pay</TableCell>
                                <TableCell>Mode</TableCell>
                                <TableCell>Status</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rows.filter((r) => r.has_record).map((row) => (
                                <TableRow key={row.user_id} hover>
                                    <TableCell>
                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{row.employee_name}</Typography>
                                        <Typography variant="caption" color="text.secondary">{row.department}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{row.bank_account_display || '-'}</Typography>
                                    </TableCell>
                                    <TableCell align="right">
                                        <Typography variant="body2" sx={{ fontWeight: 700, color: isDark ? 'success.light' : '#2e7d32' }}>{fmt(row.net)}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{row.payment_mode || 'NEFT'}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Chip size="small" label={row.status || 'Processed'} color={row.status === 'Paid' ? 'success' : 'default'} variant="outlined" />
                                    </TableCell>
                                </TableRow>
                            ))}
                            {!rows.filter((r) => r.has_record).length && (
                                <TableRow>
                                    <TableCell colSpan={5}>
                                        <Typography variant="body2" color="text.secondary">No payroll records.</Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Stack>
    );

    const renderPostGLTab = () => (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Post to Accounting — {monthLabel}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                    This creates a journal entry: Debit Salary Expense (by department) / Credit Salary Payable. Once posted, the payroll run is locked.
                </Typography>

                <Stack spacing={2} sx={{ mb: 2 }}>
                    {/* GL Summary */}
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1 }}>
                        <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary', display: 'block', mb: 1 }}>Proposed Journal Entry</Typography>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Account</TableCell>
                                        <TableCell>Description</TableCell>
                                        <TableCell align="right">Debit</TableCell>
                                        <TableCell align="right">Credit</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    <TableRow>
                                        <TableCell>Salary Expense</TableCell>
                                        <TableCell>Gross payroll — {monthLabel}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700 }}>{fmt(totals.gross)}</TableCell>
                                        <TableCell align="right">—</TableCell>
                                    </TableRow>
                                    <TableRow>
                                        <TableCell>PF/TDS Payable</TableCell>
                                        <TableCell>Statutory deductions — {monthLabel}</TableCell>
                                        <TableCell align="right">—</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700 }}>{fmt(totals.deductions)}</TableCell>
                                    </TableRow>
                                    <TableRow>
                                        <TableCell>Salary Payable</TableCell>
                                        <TableCell>Net payout — {monthLabel}</TableCell>
                                        <TableCell align="right">—</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700 }}>{fmt(totals.net)}</TableCell>
                                    </TableRow>
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>

                    {runState?.gl_posted && (
                        <Alert severity="success" icon={<CheckCircleIcon />}>
                            GL posted — Reference: <strong>{runState.gl_reference}</strong> on {fmtDate(runState.gl_posted_at)} by {runState.gl_posted_by || 'Finance'}.
                        </Alert>
                    )}
                </Stack>

                <Stack spacing={1.5}>
                    <Button
                        variant="contained" color="primary" fullWidth size="large" startIcon={<AccountBalanceIcon />}
                        disabled={!canPostGL || busy || !canCreate}
                        onClick={() => setPostGLDialog(true)}
                    >
                        {runState?.gl_posted ? 'GL Already Posted' : 'Post to General Ledger'}
                    </Button>
                    <Button
                        variant="outlined" color="error" fullWidth size="large" startIcon={<LockIcon />}
                        disabled={!canLock || busy || !canEdit}
                        onClick={() => setLockDialog(true)}
                    >
                        {runState?.is_locked ? 'Payroll Locked' : 'Lock Payroll Month'}
                    </Button>
                </Stack>

                {!runState?.finance_approved && (
                    <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
                        Finance approval is required before GL posting.
                    </Typography>
                )}
            </Paper>
        </Stack>
    );

    const renderLedger = () => (
        <Collapse in={showLedger}>
            <Paper variant="outlined" sx={{ borderRadius: 2, mb: 2 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, py: 1.5 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Payroll Ledger</Typography>
                    {ledgerLoading && <CircularProgress size={18} />}
                </Stack>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Period</TableCell>
                                <TableCell>Stage</TableCell>
                                <TableCell align="right">Employees</TableCell>
                                <TableCell align="right">Total Gross</TableCell>
                                <TableCell align="right">Deductions</TableCell>
                                <TableCell align="right">Net Pay</TableCell>
                                <TableCell>GL Ref</TableCell>
                                <TableCell>Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {ledger.map((run) => (
                                <TableRow key={run.month} hover>
                                    <TableCell sx={{ fontWeight: 600 }}>{run.month_label}</TableCell>
                                    <TableCell>{stageChip(run.stage)}</TableCell>
                                    <TableCell align="right">{run.employee_count}</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 600 }}>{fmt(run.total_gross)}</TableCell>
                                    <TableCell align="right" sx={{ color: isDark ? 'error.light' : '#c62828' }}>{fmt(run.total_deductions)}</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, color: isDark ? 'success.light' : '#2e7d32' }}>{fmt(run.total_net)}</TableCell>
                                    <TableCell>
                                        <Typography variant="caption">{run.gl_reference || '-'}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Button size="small" variant="text"
                                            onClick={() => {
                                                const [yr, mo] = run.month.split('-');
                                                setSelectedYear(Number(yr));
                                                setSelectedMonth(Number(mo));
                                                setShowLedger(false);
                                            }}>
                                            View
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {!ledger.length && !ledgerLoading && (
                                <TableRow>
                                    <TableCell colSpan={8}>
                                        <Typography variant="body2" color="text.secondary">No payroll runs recorded yet.</Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Collapse>
    );

    return (
        <Box sx={{ minHeight: '100%' }}>
            {message.text && (
                <Alert severity={message.type} onClose={() => setMessage({ type: 'success', text: '' })} sx={{ mb: 2 }}>
                    {message.text}
                </Alert>
            )}

            {renderHeader()}
            {renderLedger()}
            {renderStats()}

            {loading ? (
                <Stack alignItems="center" justifyContent="center" sx={{ py: 6 }} spacing={1}>
                    <CircularProgress size={28} />
                    <Typography variant="body2" color="text.secondary">Loading payroll data...</Typography>
                </Stack>
            ) : (
                <>
                    <Paper variant="outlined" sx={{ borderRadius: 2, mb: 2 }}>
                        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 1 }}>
                            <Tab label="1. Verify" />
                            <Tab label="2. Approve" disabled={!runState?.hr_approved} />
                            <Tab label="3. Payment" disabled={!runState?.finance_approved} />
                            <Tab label="4. Post to Accounting" disabled={!runState?.finance_approved} />
                        </Tabs>
                    </Paper>

                    <Box>
                        {activeTab === 0 && renderVerifyTab()}
                        {activeTab === 1 && renderApproveTab()}
                        {activeTab === 2 && renderPaymentTab()}
                        {activeTab === 3 && renderPostGLTab()}
                    </Box>
                </>
            )}

            {/* Approve Finance Dialog */}
            <Dialog open={approveDialog} onClose={() => setApproveDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Approve Finance — {monthLabel}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        This will mark Finance approval for {monthLabel} payroll.
                        Total Net Payout: <strong>{fmt(totals.net)}</strong> for <strong>{totalEmployees} employees</strong>.
                        This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setApproveDialog(false)}>Cancel</Button>
                    <Button variant="contained" color="primary" onClick={() => { setApproveDialog(false); doAction('approve_finance', {}, 'Finance approval recorded.'); }}>
                        Confirm Approval
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Post GL Dialog */}
            <Dialog open={postGLDialog} onClose={() => setPostGLDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Post to General Ledger — {monthLabel}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        This will create a journal entry for {monthLabel} payroll:<br />
                        <strong>Debit</strong> Salary Expense {fmt(totals.gross)}<br />
                        <strong>Credit</strong> PF/TDS Payable {fmt(totals.deductions)} + Salary Payable {fmt(totals.net)}<br /><br />
                        Once posted, a GL reference number will be assigned.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPostGLDialog(false)}>Cancel</Button>
                    <Button variant="contained" color="primary" onClick={() => { setPostGLDialog(false); doAction('post_gl', {}, 'Payroll posted to General Ledger.'); }}>
                        Post to GL
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Lock Payroll Dialog */}
            <Dialog open={lockDialog} onClose={() => setLockDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Lock Payroll — {monthLabel}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Locking the payroll for {monthLabel} will <strong>permanently prevent</strong> any further edits.
                        This is usually done after all bank transfers are confirmed.
                        Are you sure you want to lock?
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setLockDialog(false)}>Cancel</Button>
                    <Button variant="contained" color="error" startIcon={<LockIcon />} onClick={() => { setLockDialog(false); doAction('lock_payroll', {}, 'Payroll month locked.'); }}>
                        Lock Payroll
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
