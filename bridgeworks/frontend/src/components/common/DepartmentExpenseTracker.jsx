import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Button, Chip, CircularProgress, Dialog, DialogActions,
    DialogContent, DialogTitle, Divider, IconButton, InputAdornment,
    MenuItem, Paper, Select, Snackbar, Alert, Stack, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
    Typography, FormControl, InputLabel, useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterListIcon from '@mui/icons-material/FilterList';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import { apiClient } from '../../apiClient';
import { useUser } from '../../contexts/UserContext';

// ─── constants ────────────────────────────────────────────────────────────────

const EXPENSE_CATEGORIES = [
    'Travel & Transport',
    'Meals & Entertainment',
    'Office Supplies',
    'Software & Subscriptions',
    'Equipment & Hardware',
    'Marketing & Advertising',
    'Training & Development',
    'Courier & Shipping',
    'Utilities',
    'Repairs & Maintenance',
    'Vendor Payments',
    'Miscellaneous',
];

const getStatusConfig = (status, isDark) => {
    const configs = {
        pending: {
            label: 'Pending',
            bgcolor: isDark ? 'rgba(234, 179, 8, 0.15)' : '#fef9c3',
            color: isDark ? '#facc15' : '#854d0e',
            border: isDark ? '#facc1566' : '#fde68a'
        },
        approved: {
            label: 'Approved',
            bgcolor: isDark ? 'rgba(34, 197, 94, 0.15)' : '#dcfce7',
            color: isDark ? '#4ade80' : '#166534',
            border: isDark ? '#4ade8066' : '#bbf7d0'
        },
        rejected: {
            label: 'Rejected',
            bgcolor: isDark ? 'rgba(239, 68, 68, 0.15)' : '#fee2e2',
            color: isDark ? '#f87171' : '#991b1b',
            border: isDark ? '#f8717166' : '#fecaca'
        },
    };
    return configs[status] || configs.pending;
};

const thSx = (theme) => ({
    fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.06em', color: 'text.secondary',
    bgcolor: theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc',
    borderBottom: '1px solid', borderColor: 'divider', py: 1.5, px: 1.5,
    whiteSpace: 'nowrap',
});
const tdSx = { py: 1.25, px: 1.5, fontSize: '0.82rem' };

const fmt = (n) =>
    Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const today = () => new Date().toISOString().slice(0, 10);

// ─── component ────────────────────────────────────────────────────────────────

export default function DepartmentExpenseTracker({ department }) {
    const { user } = useUser();
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const [expenses, setExpenses] = useState([]);
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filterStatus, setFilterStatus] = useState('all');

    // dialog
    const [open, setOpen] = useState(false);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({
        date: today(), amount: '', category: '', description: '', account: '', receipt: null,
    });

    // toast
    const [toast, setToast] = useState({ open: false, type: 'success', msg: '' });
    const showToast = (type, msg) => setToast({ open: true, type, msg });

    // ── fetch ──────────────────────────────────────────────────────────────────

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({ department });
            const res = await apiClient(`/api/accounting/expenses/?${params}`);
            const data = await res.json();
            const rows = Array.isArray(data?.data) ? data.data : Array.isArray(data) ? data : [];
            setExpenses(rows);
        } catch {
            setExpenses([]);
        } finally {
            setLoading(false);
        }
    }, [department]);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        apiClient('/api/accounting/accounts/')
            .then(r => r.json())
            .then(d => setAccounts(Array.isArray(d?.data) ? d.data : Array.isArray(d) ? d : []))
            .catch(() => setAccounts([]));
    }, []);

    // ── submit ─────────────────────────────────────────────────────────────────

    const handleSubmit = async () => {
        if (!form.amount || Number(form.amount) <= 0) { showToast('error', 'Amount must be positive'); return; }
        if (!form.date) { showToast('error', 'Date is required'); return; }
        if (!form.category) { showToast('error', 'Category is required'); return; }

        setSaving(true);
        try {
            const body = new FormData();
            body.append('amount', form.amount);
            body.append('date', form.date);
            body.append('description', form.description || form.category);
            body.append('department', department);
            // account: use first available or send category name as account fallback
            body.append('account', form.account || (accounts[0]?.id || form.category));
            if (form.receipt) body.append('receipt', form.receipt);

            const res = await apiClient('/api/accounting/expenses/create/', {
                method: 'POST',
                body,
            });
            const data = await res.json();
            if (!res.ok || data?.success === false) throw new Error(data?.message || 'Failed');

            showToast('success', 'Expense submitted to Finance for approval.');
            setOpen(false);
            setForm({ date: today(), amount: '', category: '', description: '', account: '', receipt: null });
            load();
        } catch (e) {
            showToast('error', e.message || 'Could not submit expense.');
        } finally {
            setSaving(false);
        }
    };

    // ── derived ────────────────────────────────────────────────────────────────

    const filtered = filterStatus === 'all'
        ? expenses
        : expenses.filter(e => (e.status || 'pending') === filterStatus);

    const totalAll = expenses.reduce((s, e) => s + Number(e.amount || 0), 0);
    const totalApproved = expenses.filter(e => e.status === 'approved')
        .reduce((s, e) => s + Number(e.amount || 0), 0);
    const totalPending = expenses.filter(e => !e.status || e.status === 'pending')
        .reduce((s, e) => s + Number(e.amount || 0), 0);

    const summaryCards = [
        { label: 'Total Submitted', amount: totalAll, color: isDark ? '#60a5fa' : '#3b82f6', bg: isDark ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff' },
        { label: 'Pending Approval', amount: totalPending, color: isDark ? '#fbbf24' : '#d97706', bg: isDark ? 'rgba(245, 158, 11, 0.15)' : '#fffbeb' },
        { label: 'Approved', amount: totalApproved, color: isDark ? '#4ade80' : '#16a34a', bg: isDark ? 'rgba(22, 163, 74, 0.15)' : '#f0fdf4' },
    ];

    // ── render ─────────────────────────────────────────────────────────────────

    return (
        <Box sx={{ p: { xs: 1.5, md: 2.5 }, display: 'flex', flexDirection: 'column', gap: 2, height: '100%' }}>

            {/* Header */}
            <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                <Stack direction="row" alignItems="center" gap={1.5}>
                    <AccountBalanceWalletIcon sx={{ color: 'primary.main', fontSize: 28 }} />
                    <Box>
                        <Typography variant="h6" fontWeight={700} lineHeight={1.2}>{department}</Typography>
                        <Typography variant="caption" color="text.secondary">Department Expenses</Typography>
                    </Box>
                </Stack>
                <Stack direction="row" gap={1}>
                    <Tooltip title="Refresh">
                        <IconButton size="small" onClick={load} disabled={loading}>
                            <RefreshIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Button
                        variant="contained"
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={() => setOpen(true)}
                        sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
                    >
                        Add Expense
                    </Button>
                </Stack>
            </Stack>

            {/* Summary cards */}
            <Stack direction="row" gap={1.5} flexWrap="wrap">
                {summaryCards.map(card => (
                    <Paper
                        key={card.label}
                        variant="outlined"
                        sx={{
                            flex: '1 1 140px', p: 1.5, borderRadius: 2, borderColor: card.color + '40',
                            bgcolor: card.bg, minWidth: 120
                        }}
                    >
                        <Typography variant="caption" color="text.secondary" display="block">{card.label}</Typography>
                        <Typography variant="subtitle1" fontWeight={800} sx={{ color: card.color }}>
                            ₹{fmt(card.amount)}
                        </Typography>
                    </Paper>
                ))}
            </Stack>

            {/* Filter + table */}
            <Paper variant="outlined" sx={{ flex: 1, borderRadius: 2, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {/* filter bar */}
                <Stack direction="row" alignItems="center" gap={1.5} sx={{ px: 2, py: 1.25, borderBottom: 1, borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc' }}>
                    <FilterListIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                    <Typography variant="caption" fontWeight={600} color="text.secondary">STATUS:</Typography>
                    {['all', 'pending', 'approved', 'rejected'].map(s => (
                        <Chip
                            key={s}
                            label={s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                            size="small"
                            onClick={() => setFilterStatus(s)}
                            variant={filterStatus === s ? 'filled' : 'outlined'}
                            color={filterStatus === s ? 'primary' : 'default'}
                            sx={{ cursor: 'pointer', textTransform: 'capitalize', fontWeight: 600, fontSize: '0.72rem' }}
                        />
                    ))}
                    <Box sx={{ ml: 'auto' }}>
                        <Typography variant="caption" color="text.secondary">{filtered.length} record{filtered.length !== 1 ? 's' : ''}</Typography>
                    </Box>
                </Stack>

                {/* table */}
                {loading ? (
                    <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={20} />
                        <Typography variant="body2" color="text.secondary">Loading expenses…</Typography>
                    </Box>
                ) : filtered.length === 0 ? (
                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 1.5, color: 'text.secondary' }}>
                        <ReceiptLongIcon sx={{ fontSize: 48, opacity: 0.3 }} />
                        <Typography variant="body2">No expenses found.</Typography>
                        <Button size="small" variant="outlined" startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ textTransform: 'none', borderRadius: 2 }}>
                            Add First Expense
                        </Button>
                    </Box>
                ) : (
                    <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    {['Date', 'Category / Description', 'Amount', 'Account', 'Submitted By', 'Status', 'Receipt'].map(h => (
                                        <TableCell key={h} sx={thSx}>{h}</TableCell>
                                    ))}
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {filtered.map((row, idx) => {
                                    const status = row.status || 'pending';
                                    const cfg = getStatusConfig(status, isDark);
                                    return (
                                        <TableRow key={row.id || idx} hover sx={{ '&:last-child td': { border: 0 } }}>
                                            <TableCell sx={tdSx}>
                                                {row.date
                                                    ? new Date(row.date).toLocaleDateString('en-GB')
                                                    : '—'}
                                            </TableCell>
                                            <TableCell sx={tdSx}>
                                                <Typography variant="body2" fontWeight={600} noWrap>
                                                    {row.category?.name || row.category || '—'}
                                                </Typography>
                                                {row.description && (
                                                    <Typography variant="caption" color="text.secondary" noWrap>
                                                        {row.description}
                                                    </Typography>
                                                )}
                                            </TableCell>
                                            <TableCell sx={{ ...tdSx, fontWeight: 700, color: 'error.main', whiteSpace: 'nowrap' }}>
                                                ₹{fmt(row.amount)}
                                            </TableCell>
                                            <TableCell sx={tdSx}>{row.account?.name || '—'}</TableCell>
                                            <TableCell sx={tdSx}>{row.created_by?.name || row.submitted_by || user?.name || '—'}</TableCell>
                                            <TableCell sx={tdSx}>
                                                <Chip
                                                    label={cfg.label}
                                                    size="small"
                                                    sx={{
                                                        bgcolor: cfg.bgcolor, color: cfg.color,
                                                        border: `1px solid ${cfg.border}`,
                                                        fontWeight: 700, fontSize: '0.7rem',
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell sx={tdSx}>
                                                {row.receipt ? (
                                                    <Tooltip title="View receipt">
                                                        <IconButton size="small" component="a" href={row.receipt} target="_blank" rel="noreferrer">
                                                            <AttachFileIcon fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                ) : '—'}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </Paper>

            {/* ── Add Expense Dialog ── */}
            <Dialog open={open} onClose={() => !saving && setOpen(false)} maxWidth="sm" fullWidth
                PaperProps={{ sx: { borderRadius: 3 } }}>
                <DialogTitle sx={{ fontWeight: 700, pb: 0 }}>
                    <Stack direction="row" alignItems="center" gap={1}>
                        <ReceiptLongIcon sx={{ color: 'primary.main' }} />
                        New Department Expense
                    </Stack>
                    <Typography variant="caption" color="text.secondary">{department}</Typography>
                </DialogTitle>
                <Divider sx={{ mt: 1 }} />

                <DialogContent sx={{ pt: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Stack direction="row" gap={2}>
                        <TextField
                            label="Date"
                            type="date"
                            size="small"
                            fullWidth
                            value={form.date}
                            onChange={e => setForm(p => ({ ...p, date: e.target.value }))}
                            InputLabelProps={{ shrink: true }}
                        />
                        <TextField
                            label="Amount (₹)"
                            type="number"
                            size="small"
                            fullWidth
                            value={form.amount}
                            onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                            InputProps={{ startAdornment: <InputAdornment position="start">₹</InputAdornment> }}
                            inputProps={{ min: 0, step: '0.01' }}
                        />
                    </Stack>

                    <FormControl size="small" fullWidth>
                        <InputLabel>Category *</InputLabel>
                        <Select
                            value={form.category}
                            label="Category *"
                            onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                        >
                            {EXPENSE_CATEGORIES.map(c => (
                                <MenuItem key={c} value={c}>{c}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <TextField
                        label="Description"
                        size="small"
                        fullWidth
                        multiline
                        rows={2}
                        value={form.description}
                        onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                        placeholder="Brief description of the expense..."
                    />

                    {accounts.length > 0 && (
                        <FormControl size="small" fullWidth>
                            <InputLabel>Payment Account</InputLabel>
                            <Select
                                value={form.account}
                                label="Payment Account"
                                onChange={e => setForm(p => ({ ...p, account: e.target.value }))}
                            >
                                {accounts.map(a => (
                                    <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    )}

                    <Box>
                        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                            Receipt / Supporting Document (optional)
                        </Typography>
                        <Button
                            variant="outlined"
                            component="label"
                            size="small"
                            startIcon={<AttachFileIcon />}
                            sx={{ textTransform: 'none', borderRadius: 2 }}
                        >
                            {form.receipt ? form.receipt.name : 'Attach File'}
                            <input
                                hidden
                                type="file"
                                accept="image/*,application/pdf"
                                onChange={e => setForm(p => ({ ...p, receipt: e.target.files[0] || null }))}
                            />
                        </Button>
                    </Box>

                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(245, 158, 11, 0.15)' : '#fffbeb', borderColor: (theme) => theme.palette.mode === 'dark' ? '#f59e0b' : '#fde68a' }}>
                        <Typography variant="caption" sx={{ color: (theme) => theme.palette.mode === 'dark' ? '#fbbf24' : '#92400e' }}>
                            This expense will be submitted to Finance for approval. It will appear in your department's expense register once reviewed.
                        </Typography>
                    </Paper>
                </DialogContent>

                <Divider />
                <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
                    <Button onClick={() => setOpen(false)} disabled={saving} sx={{ textTransform: 'none' }}>
                        Cancel
                    </Button>
                    <Button
                        variant="contained"
                        onClick={handleSubmit}
                        disabled={saving}
                        startIcon={saving ? <CircularProgress size={16} /> : <ReceiptLongIcon />}
                        sx={{ textTransform: 'none', fontWeight: 600, borderRadius: 2 }}
                    >
                        {saving ? 'Submitting…' : 'Submit to Finance'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Toast */}
            <Snackbar open={toast.open} autoHideDuration={4000} onClose={() => setToast(p => ({ ...p, open: false }))}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
                <Alert severity={toast.type} variant="filled" onClose={() => setToast(p => ({ ...p, open: false }))}>
                    {toast.msg}
                </Alert>
            </Snackbar>
        </Box>
    );
}
