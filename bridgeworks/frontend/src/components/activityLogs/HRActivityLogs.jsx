import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    FormControl,
    InputAdornment,
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
    TablePagination,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import { fetchHRLogs, exportHRLogs } from './activityLogsService';

// ── Helpers ───────────────────────────────────────────────────────────────────

function getLocalDate(offsetDays = 0) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.toISOString().slice(0, 10);
}

function formatDateTime(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}

function parseDevice(userAgent) {
    if (!userAgent) return '—';
    if (/mobile|android|iphone|ipad/i.test(userAgent)) return '📱 Mobile';
    if (/tablet/i.test(userAgent)) return '📋 Tablet';
    return '🖥️ Desktop';
}

// ── Action badge ──────────────────────────────────────────────────────────────

const ACTION_COLOUR = {
    API_CALL: 'default',
    BUTTON_CLICK: 'primary',
    PAGE_VIEW: 'success',
    FORM_SUBMIT: 'secondary',
    LOGIN: 'info',
    LOGOUT: 'warning',
    ERROR: 'error',
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
                fontSize: '0.68rem',
                letterSpacing: '0.03em',
                height: 22,
                '& .MuiChip-label': { px: 1 },
            }}
        />
    );
}

const ACTION_OPTIONS = [
    'API_CALL',
    'BUTTON_CLICK',
    'PAGE_VIEW',
    'FORM_SUBMIT',
    'LOGIN',
    'LOGOUT',
    'ERROR',
];

// ── Metadata cell — render safe preview ──────────────────────────────────────

function MetadataCell({ value, isSensitive }) {
    if (isSensitive || value === '[REDACTED]') {
        return (
            <Chip
                label="REDACTED"
                size="small"
                color="error"
                variant="outlined"
                sx={{ fontSize: '0.65rem', height: 20 }}
            />
        );
    }
    if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) {
        return <Typography variant="caption" color="text.disabled">—</Typography>;
    }
    const preview = typeof value === 'object'
        ? JSON.stringify(value).slice(0, 60) + (JSON.stringify(value).length > 60 ? '…' : '')
        : String(value).slice(0, 60);
    return (
        <Tooltip title={<pre style={{ margin: 0, fontSize: 11 }}>{JSON.stringify(value, null, 2)}</pre>} arrow>
            <Typography
                variant="caption"
                sx={{ fontFamily: 'monospace', cursor: 'help', color: 'text.secondary' }}
            >
                {preview}
            </Typography>
        </Tooltip>
    );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function HRActivityLogs() {
    // ── Filter state ──────────────────────────────────────────────────────────
    const [userId, setUserId] = useState('');
    const [from, setFrom] = useState(getLocalDate(-29));
    const [to, setTo] = useState(getLocalDate(0));
    const [action, setAction] = useState('');
    const [component, setComponent] = useState('');
    const [componentDraft, setComponentDraft] = useState('');
    const [search, setSearch] = useState('');
    const [searchDraft, setSearchDraft] = useState('');

    // ── Pagination ────────────────────────────────────────────────────────────
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);

    // ── Data state ────────────────────────────────────────────────────────────
    const [rows, setRows] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [exporting, setExporting] = useState(false);

    // ── Fetch ─────────────────────────────────────────────────────────────────
    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const data = await fetchHRLogs({
                userId: userId || undefined,
                from: from ? `${from}T00:00:00` : undefined,
                to: to ? `${to}T23:59:59` : undefined,
                action: action || undefined,
                component: component || undefined,
                search: search || undefined,
                page: page + 1,
                limit: rowsPerPage,
            });
            setRows(data.results || []);
            setTotalCount(data.count || 0);
        } catch (err) {
            setError(err.message || 'Failed to fetch HR logs.');
        } finally {
            setLoading(false);
        }
    }, [userId, from, to, action, component, search, page, rowsPerPage]);

    useEffect(() => { load(); }, [load]);

    // Debounce component + search text fields
    useEffect(() => {
        const t = setTimeout(() => { setComponent(componentDraft); setPage(0); }, 400);
        return () => clearTimeout(t);
    }, [componentDraft]);

    useEffect(() => {
        const t = setTimeout(() => { setSearch(searchDraft); setPage(0); }, 400);
        return () => clearTimeout(t);
    }, [searchDraft]);

    // ── Export ────────────────────────────────────────────────────────────────
    const handleExport = async () => {
        setExporting(true);
        try {
            await exportHRLogs({
                userId: userId || undefined,
                from: from ? `${from}T00:00:00` : undefined,
                to: to ? `${to}T23:59:59` : undefined,
                action: action || undefined,
                component: component || undefined,
                search: search || undefined,
            });
        } catch (err) {
            setError('Export failed: ' + (err.message || 'Unknown error'));
        } finally {
            setExporting(false);
        }
    };

    // ── Handlers ──────────────────────────────────────────────────────────────
    const handlePageChange = (_, newPage) => setPage(newPage);
    const handleRowsPerPageChange = (e) => {
        setRowsPerPage(parseInt(e.target.value, 10));
        setPage(0);
    };

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>

            {/* ── Header ─────────────────────────────────────────────────── */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                <ManageSearchIcon sx={{ color: 'primary.main', fontSize: 26 }} />
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" fontWeight={700} lineHeight={1.2}>
                        HR Activity Logs
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Monitor and audit all user activity across the platform
                    </Typography>
                </Box>

                <Stack direction="row" gap={1} alignItems="center">
                    {totalCount > 0 && (
                        <Chip
                            label={`${totalCount.toLocaleString()} records`}
                            size="small"
                            color="primary"
                            variant="outlined"
                            sx={{ fontWeight: 600 }}
                        />
                    )}
                    <Button
                        variant="outlined"
                        size="small"
                        startIcon={exporting ? <CircularProgress size={14} /> : <DownloadIcon />}
                        onClick={handleExport}
                        disabled={exporting || loading || totalCount === 0}
                        sx={{ textTransform: 'none', fontWeight: 600 }}
                    >
                        {exporting ? 'Exporting…' : 'Export CSV'}
                    </Button>
                </Stack>
            </Box>

            {/* ── Filters ────────────────────────────────────────────────── */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction="row" flexWrap="wrap" gap={2} alignItems="center">

                    <TextField
                        label="User ID"
                        size="small"
                        value={userId}
                        onChange={(e) => { setUserId(e.target.value); setPage(0); }}
                        placeholder="e.g. 42"
                        sx={{ width: 110 }}
                    />

                    <TextField
                        label="From"
                        type="date"
                        size="small"
                        value={from}
                        onChange={(e) => { setFrom(e.target.value); setPage(0); }}
                        InputLabelProps={{ shrink: true }}
                        sx={{ minWidth: 150 }}
                    />

                    <TextField
                        label="To"
                        type="date"
                        size="small"
                        value={to}
                        onChange={(e) => { setTo(e.target.value); setPage(0); }}
                        InputLabelProps={{ shrink: true }}
                        sx={{ minWidth: 150 }}
                    />

                    <FormControl size="small" sx={{ minWidth: 170 }}>
                        <InputLabel>Action</InputLabel>
                        <Select
                            value={action}
                            label="Action"
                            onChange={(e) => { setAction(e.target.value); setPage(0); }}
                        >
                            <MenuItem value=""><em>All actions</em></MenuItem>
                            {ACTION_OPTIONS.map((a) => (
                                <MenuItem key={a} value={a}>{a}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <TextField
                        label="Component"
                        size="small"
                        value={componentDraft}
                        onChange={(e) => setComponentDraft(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon fontSize="small" />
                                </InputAdornment>
                            ),
                        }}
                        sx={{ minWidth: 190 }}
                    />

                    <TextField
                        label="Search users / actions"
                        size="small"
                        value={searchDraft}
                        onChange={(e) => setSearchDraft(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon fontSize="small" />
                                </InputAdornment>
                            ),
                        }}
                        sx={{ minWidth: 220 }}
                    />
                </Stack>
            </Paper>

            {/* ── Error ──────────────────────────────────────────────────── */}
            {error && (
                <Alert severity="error" onClose={() => setError('')}>{error}</Alert>
            )}

            {/* ── Table ──────────────────────────────────────────────────── */}
            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                    <CircularProgress />
                </Box>
            ) : rows.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                    <Typography color="text.secondary">No logs found for the selected filters.</Typography>
                </Box>
            ) : (
                <TableContainer
                    component={Paper}
                    variant="outlined"
                    sx={{ borderRadius: 2, flex: 1, overflow: 'auto' }}
                >
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow
                                sx={{
                                    '& th': {
                                        fontWeight: 700,
                                        fontSize: '0.72rem',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : 'grey.50',
                                        color: (theme) => theme.palette.mode === 'dark' ? 'text.secondary' : 'text.primary',
                                        whiteSpace: 'nowrap',
                                    },
                                }}
                            >
                                <TableCell sx={{ width: 165 }}>Timestamp</TableCell>
                                <TableCell sx={{ width: 160 }}>User</TableCell>
                                <TableCell sx={{ width: 155 }}>Action</TableCell>
                                <TableCell>Component</TableCell>
                                <TableCell>Page Path</TableCell>
                                <TableCell sx={{ width: 70 }}>Method</TableCell>
                                <TableCell sx={{ width: 70 }}>Status</TableCell>
                                <TableCell sx={{ width: 80 }}>Duration</TableCell>
                                <TableCell sx={{ width: 110 }}>Device</TableCell>
                                <TableCell>Metadata</TableCell>
                            </TableRow>
                        </TableHead>

                        <TableBody>
                            {rows.map((row) => (
                                <TableRow
                                    key={row.id}
                                    hover
                                    sx={{
                                        '&:last-child td': { borderBottom: 0 },
                                        '& td': { fontSize: '0.79rem', py: 0.9 },
                                    }}
                                >
                                    {/* Timestamp */}
                                    <TableCell>
                                        <Typography
                                            variant="caption"
                                            sx={{ fontFamily: 'monospace', color: 'text.secondary', fontWeight: 500 }}
                                        >
                                            {formatDateTime(row.timestamp)}
                                        </Typography>
                                    </TableCell>

                                    {/* User */}
                                    <TableCell>
                                        <Box>
                                            <Typography variant="body2" fontWeight={600} fontSize="0.78rem">
                                                {row.username || <span style={{ color: '#999' }}>Anonymous</span>}
                                            </Typography>
                                            {row.email && (
                                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.3 }}>
                                                    {row.email}
                                                </Typography>
                                            )}
                                        </Box>
                                    </TableCell>

                                    {/* Action badge */}
                                    <TableCell>
                                        <ActionBadge action={row.action} />
                                    </TableCell>

                                    {/* Component */}
                                    <TableCell>
                                        <Tooltip title={row.component || '—'} arrow>
                                            <Typography
                                                variant="body2"
                                                sx={{
                                                    maxWidth: 180,
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap',
                                                    fontSize: '0.79rem',
                                                }}
                                            >
                                                {row.component || '—'}
                                            </Typography>
                                        </Tooltip>
                                    </TableCell>

                                    {/* Page path */}
                                    <TableCell>
                                        <Tooltip title={row.page || '—'} arrow>
                                            <Typography
                                                variant="body2"
                                                sx={{
                                                    maxWidth: 200,
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap',
                                                    fontFamily: 'monospace',
                                                    fontSize: '0.74rem',
                                                    color: 'text.secondary',
                                                }}
                                            >
                                                {row.page || '—'}
                                            </Typography>
                                        </Tooltip>
                                    </TableCell>

                                    {/* HTTP method */}
                                    <TableCell>
                                        {row.method ? (
                                            <Chip
                                                label={row.method}
                                                size="small"
                                                variant="outlined"
                                                sx={{ fontSize: '0.65rem', height: 20, fontWeight: 700 }}
                                            />
                                        ) : (
                                            <Typography variant="caption" color="text.disabled">—</Typography>
                                        )}
                                    </TableCell>

                                    {/* Status code */}
                                    <TableCell>
                                        {row.status_code != null ? (
                                            <Chip
                                                label={row.status_code}
                                                size="small"
                                                color={
                                                    row.status_code >= 500 ? 'error'
                                                        : row.status_code >= 400 ? 'warning'
                                                            : row.status_code >= 300 ? 'info'
                                                                : 'success'
                                                }
                                                variant="filled"
                                                sx={{ fontSize: '0.65rem', height: 20, fontWeight: 700 }}
                                            />
                                        ) : (
                                            <Typography variant="caption" color="text.disabled">—</Typography>
                                        )}
                                    </TableCell>

                                    {/* Duration */}
                                    <TableCell>
                                        {row.duration_ms != null ? (
                                            <Typography
                                                variant="caption"
                                                sx={{
                                                    fontFamily: 'monospace',
                                                    color: row.duration_ms > 2000 ? 'error.main'
                                                        : row.duration_ms > 500 ? 'warning.main'
                                                            : 'success.main',
                                                    fontWeight: 600,
                                                }}
                                            >
                                                {row.duration_ms}ms
                                            </Typography>
                                        ) : (
                                            <Typography variant="caption" color="text.disabled">—</Typography>
                                        )}
                                    </TableCell>

                                    {/* Device */}
                                    <TableCell>
                                        <Typography variant="caption" color="text.secondary">
                                            {parseDevice(row.user_agent || '')}
                                        </Typography>
                                    </TableCell>

                                    {/* Metadata */}
                                    <TableCell>
                                        <MetadataCell value={row.metadata} isSensitive={row.is_sensitive} />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
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
