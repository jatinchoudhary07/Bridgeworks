import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Chip,
    CircularProgress,
    Divider,
    FormControl,
    FormControlLabel,
    InputAdornment,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TablePagination,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import EventNoteIcon from '@mui/icons-material/EventNote';
import { fetchMyLogs } from './activityLogsService';

// ── Helpers ───────────────────────────────────────────────────────────────────

function getLocalDate(offsetDays = 0) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.toISOString().slice(0, 10);
}

function formatTime(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}

/** Group a flat list of log rows by calendar date (user's local timezone). */
function groupByDate(rows) {
    const groups = {};
    rows.forEach((row) => {
        const day = row.timestamp ? new Date(row.timestamp).toLocaleDateString(undefined, {
            weekday: 'long', day: '2-digit', month: 'long', year: 'numeric',
        }) : 'Unknown Date';
        if (!groups[day]) groups[day] = [];
        groups[day].push(row);
    });
    return groups;
}

/** Derive a user-agent device string from user_agent header. */
function parseDevice(userAgent) {
    if (!userAgent) return '—';
    if (/mobile|android|iphone|ipad/i.test(userAgent)) return '📱 Mobile';
    if (/tablet/i.test(userAgent)) return '📋 Tablet';
    return '🖥️ Desktop';
}

// ── Action badge colour config ─────────────────────────────────────────────────

const ACTION_COLOUR = {
    API_CALL: 'default',
    BUTTON_CLICK: 'primary',
    PAGE_VIEW: 'success',
    FORM_SUBMIT: 'secondary',
    LOGIN: 'info',
    LOGOUT: 'warning',
    ERROR: 'error',
    TASK_CREATE: 'success',
    TASK_UPDATE: 'primary',
    TASK_DELETE: 'error',
    MESSAGE_SENT: 'info',
    TAB_SWITCH: 'secondary',
    DROPDOWN_CHANGE: 'default',
    MODAL_OPEN: 'info',
    MODAL_CLOSE: 'default',
    ACCORDION_EXPAND: 'secondary',
    ACCORDION_COLLAPSE: 'default',
    SEARCH: 'info',
    FILTER_CHANGE: 'secondary',
    SCROLL_DEPTH: 'default',
    EXTERNAL_LINK_CLICK: 'warning',
    COPY: 'default',
    FILE_DOWNLOAD: 'success',
    SORT: 'default',
    PAGINATION: 'default',
    NAV_CLICK: 'primary',
    TAB_HIDDEN: 'warning',
    TAB_VISIBLE: 'success',
};

function ActionBadge({ action }) {
    const color = ACTION_COLOUR[action] || 'default';
    return (
        <Chip
            label={action}
            color={color}
            size="small"
            variant={color === 'default' ? 'outlined' : 'filled'}
            sx={{
                fontWeight: 600,
                fontSize: '0.65rem',
                letterSpacing: '0.03em',
                height: 18,
                '& .MuiChip-label': { px: 0.75 },
            }}
        />
    );
}

// ── Known action options for the filter dropdown ──────────────────────────────
// API_CALL is intentionally excluded — server-side middleware events are shown
// only when the user explicitly enables "Include server logs".
const ACTION_OPTIONS = [
    'BUTTON_CLICK',
    'PAGE_VIEW',
    'FORM_SUBMIT',
    'LOGIN',
    'LOGOUT',
    'ERROR',
    'TASK_CREATE',
    'TASK_UPDATE',
    'TASK_DELETE',
    'MESSAGE_SENT',
    'TAB_SWITCH',
    'DROPDOWN_CHANGE',
    'MODAL_OPEN',
    'MODAL_CLOSE',
    'ACCORDION_EXPAND',
    'ACCORDION_COLLAPSE',
    'SEARCH',
    'FILTER_CHANGE',
    'SCROLL_DEPTH',
    'EXTERNAL_LINK_CLICK',
    'COPY',
    'FILE_DOWNLOAD',
    'SORT',
    'PAGINATION',
    'NAV_CLICK',
    'TAB_HIDDEN',
    'TAB_VISIBLE',
];

// ── Module options — maps label → page-path prefix ────────────────────────────
const MODULE_OPTIONS = [
    { label: 'Home', prefix: '/' },
    { label: 'My Desk', prefix: '/mydesk' },
    { label: 'Operations & Fulfilment', prefix: '/operations' },
    { label: 'Logistics', prefix: '/tracking' },
    { label: 'Reverse Shipment', prefix: '/rto' },
    { label: 'Customer Experience', prefix: '/customer-care' },
    { label: 'Marketing & Growth', prefix: '/marketing' },
    { label: 'Finance & Accounting', prefix: '/finance' },
    { label: 'Product & Merchandising', prefix: '/product' },
    { label: 'Intelligence', prefix: '/intelligence' },
    { label: 'Sales & Business Dev', prefix: '/sales' },
    { label: 'Human Resources', prefix: '/team' },
    { label: 'Webhooks', prefix: '/webhooks' },
];

function matchesModule(page, prefix) {
    if (!page) return false;
    if (prefix === '/') return page === '/';
    return page === prefix || page.startsWith(prefix + '/');
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function PersonalActivityLogs() {
    // ── Filter state ──────────────────────────────────────────────────────────
    const [date, setDate] = useState(getLocalDate(0));
    const [action, setAction] = useState('');
    const [moduleFilter, setModuleFilter] = useState('');
    const [componentSearch, setComponentSearch] = useState('');
    const [componentDraft, setComponentDraft] = useState('');
    // false = frontend events only; true = include backend API_CALL logs too
    const [showServer, setShowServer] = useState(false);

    // ── Pagination ────────────────────────────────────────────────────────────
    const [page, setPage] = useState(0);          // MUI 0-based
    const [rowsPerPage, setRowsPerPage] = useState(25);

    // ── Data state ────────────────────────────────────────────────────────────
    const [rows, setRows] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // ── Fetch ─────────────────────────────────────────────────────────────────
    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const data = await fetchMyLogs({
                from: date ? `${date}T00:00:00` : undefined,
                to: date ? `${date}T23:59:59` : undefined,
                action: action || undefined,
                source: showServer ? '' : 'frontend',
                page: page + 1,
                limit: rowsPerPage,
            });
            setRows(data.results || []);
            setTotalCount(data.count || 0);
        } catch (err) {
            setError(err.message || 'Failed to load activity logs.');
        } finally {
            setLoading(false);
        }
    }, [date, action, showServer, page, rowsPerPage]);

    useEffect(() => { load(); }, [load]);

    // ── Component search (client-side filter on current page) ─────────────────
    const displayRows = useMemo(() => {
        let filtered = rows;
        if (moduleFilter) {
            const mod = MODULE_OPTIONS.find((m) => m.label === moduleFilter);
            if (mod) filtered = filtered.filter((r) => matchesModule(r.page, mod.prefix));
        }
        if (componentSearch.trim()) {
            const q = componentSearch.toLowerCase();
            filtered = filtered.filter(
                (r) =>
                    (r.component || '').toLowerCase().includes(q) ||
                    (r.page || '').toLowerCase().includes(q),
            );
        }
        return filtered;
    }, [rows, moduleFilter, componentSearch]);

    // Group displayed rows by date for the daily timeline view
    const grouped = useMemo(() => groupByDate(displayRows), [displayRows]);

    // ── Handlers ──────────────────────────────────────────────────────────────
    const handlePageChange = (_, newPage) => {
        setPage(newPage);
    };

    const handleRowsPerPageChange = (e) => {
        setRowsPerPage(parseInt(e.target.value, 10));
        setPage(0);
    };

    const handleActionChange = (e) => {
        setAction(e.target.value);
        setPage(0);
    };

    const handleShowServerToggle = (e) => {
        setShowServer(e.target.checked);
        // When enabling server logs, clear action filter since API_CALL won't be in the dropdown
        if (e.target.checked) setAction('');
        setPage(0);
    };

    const handleDateChange = (e) => { setDate(e.target.value); setPage(0); };
    const handleModuleFilterChange = (e) => { setModuleFilter(e.target.value); setPage(0); };

    // Debounce component search locally
    const handleComponentDraft = (e) => {
        setComponentDraft(e.target.value);
    };
    useEffect(() => {
        const t = setTimeout(() => setComponentSearch(componentDraft), 300);
        return () => clearTimeout(t);
    }, [componentDraft]);

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <Box sx={{ p: 1, height: '100%', display: 'flex', flexDirection: 'column', gap: 1 }}>

            {/* ── Filters ────────────────────────────────────────────────── */}
            <Paper variant="outlined" sx={{ p: 1, borderRadius: 2 }}>
                <Stack direction="row" flexWrap="wrap" gap={1} alignItems="center">

                    <TextField
                        label="Date"
                        type="date"
                        size="small"
                        value={date}
                        onChange={handleDateChange}
                        InputLabelProps={{ shrink: true }}
                        sx={{ minWidth: 150 }}
                    />

                    <FormControl size="small" sx={{ minWidth: 170 }}>
                        <InputLabel>Action</InputLabel>
                        <Select
                            value={action}
                            label="Action"
                            onChange={handleActionChange}
                        >
                            <MenuItem value=""><em>All actions</em></MenuItem>
                            {ACTION_OPTIONS.map((a) => (
                                <MenuItem key={a} value={a}>{a}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ minWidth: 180 }}>
                        <InputLabel>Module</InputLabel>
                        <Select
                            value={moduleFilter}
                            label="Module"
                            onChange={handleModuleFilterChange}
                        >
                            <MenuItem value=""><em>All modules</em></MenuItem>
                            {MODULE_OPTIONS.map((m) => (
                                <MenuItem key={m.label} value={m.label}>{m.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <TextField
                        label="Search component / page"
                        size="small"
                        value={componentDraft}
                        onChange={handleComponentDraft}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon fontSize="small" />
                                </InputAdornment>
                            ),
                        }}
                        sx={{ minWidth: 240 }}
                    />

                    <FormControlLabel
                        control={
                            <Switch
                                size="small"
                                checked={showServer}
                                onChange={handleShowServerToggle}
                            />
                        }
                        label={
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                                Include server logs
                            </Typography>
                        }
                        sx={{ ml: 0.5, whiteSpace: 'nowrap' }}
                    />
                </Stack>
            </Paper>

            {/* ── Body ───────────────────────────────────────────────────── */}
            {error && (
                <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
            )}

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                    <CircularProgress />
                </Box>
            ) : displayRows.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                    <Typography color="text.secondary">No activity found for the selected filters.</Typography>
                </Box>
            ) : (
                <Box sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {Object.entries(grouped).map(([dateLabel, dayRows]) => (
                        <Box key={dateLabel}>
                            {/* Day header */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                <Typography
                                    variant="subtitle2"
                                    fontWeight={700}
                                    sx={{
                                        color: (theme) => theme.palette.mode === 'dark' ? '#90caf9' : 'primary.main',
                                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(144, 202, 249, 0.15)' : 'primary.50',
                                        px: 1,
                                        py: 0.2,
                                        borderRadius: 999,
                                        fontSize: '0.68rem',
                                        letterSpacing: '0.04em',
                                        textTransform: 'uppercase',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {dateLabel}
                                </Typography>
                                <Divider sx={{ flex: 1 }} />
                                <Typography variant="caption" color="text.disabled">
                                    {dayRows.length} event{dayRows.length !== 1 ? 's' : ''}
                                </Typography>
                            </Box>

                            {/* Day table */}
                            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                                <Table size="small" stickyHeader>
                                    <TableHead>
                                        <TableRow sx={{
                                            '& th': {
                                                fontWeight: 700,
                                                fontSize: '0.68rem',
                                                textTransform: 'uppercase',
                                                letterSpacing: '0.05em',
                                                bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : 'grey.50',
                                                color: (theme) => theme.palette.mode === 'dark' ? 'text.secondary' : 'text.primary',
                                                py: 0.4,
                                                px: 1
                                            }
                                        }}>
                                            <TableCell sx={{ width: 100 }}>Time</TableCell>
                                            <TableCell sx={{ width: 160 }}>Action</TableCell>
                                            <TableCell>Component</TableCell>
                                            <TableCell>Page Path</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {dayRows.map((row) => (
                                            <TableRow
                                                key={row.id}
                                                hover
                                                sx={{
                                                    '&:last-child td': { borderBottom: 0 },
                                                    '& td': { fontSize: '0.75rem', py: 0.25, px: 1 },
                                                }}
                                            >
                                                <TableCell>
                                                    <Typography
                                                        variant="caption"
                                                        sx={{
                                                            fontFamily: 'monospace',
                                                            color: 'text.secondary',
                                                            fontWeight: 600,
                                                        }}
                                                    >
                                                        {formatTime(row.timestamp)}
                                                    </Typography>
                                                </TableCell>

                                                <TableCell>
                                                    <ActionBadge action={row.action} />
                                                </TableCell>

                                                <TableCell>
                                                    <Tooltip title={row.component || '—'} arrow>
                                                        <Typography
                                                            variant="body2"
                                                            sx={{
                                                                maxWidth: 200,
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'nowrap',
                                                                fontSize: '0.8rem',
                                                            }}
                                                        >
                                                            {row.component || '—'}
                                                        </Typography>
                                                    </Tooltip>
                                                </TableCell>

                                                <TableCell>
                                                    <Tooltip title={row.page || '—'} arrow>
                                                        <Typography
                                                            variant="body2"
                                                            sx={{
                                                                maxWidth: 240,
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'nowrap',
                                                                fontFamily: 'monospace',
                                                                fontSize: '0.76rem',
                                                                color: 'text.secondary',
                                                            }}
                                                        >
                                                            {row.page || '—'}
                                                        </Typography>
                                                    </Tooltip>
                                                </TableCell>


                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Box>
                    ))}
                </Box>
            )}

            {/* ── Pagination ──────────────────────────────────────────────── */}
            {!loading && totalCount > 0 && (
                <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                    <TablePagination
                        component="div"
                        count={totalCount}
                        page={page}
                        rowsPerPage={rowsPerPage}
                        onPageChange={handlePageChange}
                        onRowsPerPageChange={handleRowsPerPageChange}
                        rowsPerPageOptions={[10, 25, 50, 100]}
                        labelRowsPerPage="Rows:"
                        sx={{ '& .MuiTablePagination-toolbar': { minHeight: 44 } }}
                    />
                </Paper>
            )}
        </Box>
    );
}
