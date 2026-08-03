import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert, alpha, Box, Button, Chip, CircularProgress, Collapse,
    Divider, FormControl, Grid, IconButton, InputLabel,
    LinearProgress, MenuItem, Paper, Select, Stack, Table,
    TableBody, TableCell, TableContainer, TableHead, TableRow,
    TextField, Tooltip, Typography, useTheme,
    Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ScheduleIcon from '@mui/icons-material/Schedule';
import RefreshIcon from '@mui/icons-material/Refresh';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AddIcon from '@mui/icons-material/Add';
import {
    createMyAttendanceEntry,
    listMyAttendanceOverview,
    getMyAttendanceRulebook,
    getMyAttendanceScore,
} from '../mydeskService';

const STATUS_COLOR = {
    present: 'success',
    absent: 'error',
    half_day: 'warning',
    wfh: 'info',
    on_duty: 'secondary',
    leave: 'default',
};

const STATUS_ICON = {
    present: '🏢',
    absent: '❌',
    half_day: '⚠️',
    wfh: '🏠',
    on_duty: '🚗',
    leave: '🏖️',
};

function formatStatus(value, workMode) {
    if (value === 'present') return 'WFO';
    if (value === 'half_day') {
        if (workMode === 'wfh') return 'Half Day (WFH)';
        if (workMode === 'wfo') return 'Half Day (WFO)';
        return 'Half Day';
    }
    if (value === 'on_duty') return 'On Duty';
    if (value === 'wfh') return 'WFH';
    return String(value || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function getStatusIcon(status, workMode) {
    if (status === 'half_day' && workMode === 'wfh') return '⚠️ 🏠';
    return STATUS_ICON[status] || '📋';
}

function monthName(index) {
    return new Date(2000, index, 1).toLocaleString(undefined, { month: 'short' });
}

function getLocalDateInputValue(date = new Date()) {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
}

function asDateLabel(value) {
    if (!value) return '-';
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function ScoreMeter({ score }) {
    const theme = useTheme();
    const color = score >= 90
        ? theme.palette.success.main
        : score >= 75
            ? theme.palette.warning.main
            : theme.palette.error.main;
    const label = score >= 90 ? 'Excellent' : score >= 75 ? 'Good' : score >= 50 ? 'Average' : 'Poor';
    return (
        <Box sx={{ minWidth: 160 }}>
            <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                    Attendance Score
                </Typography>
                <Tooltip title="Monthly attendance health: 100 = perfect, deducted for lates/absences/half-days">
                    <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                </Tooltip>
            </Stack>
            <Stack direction="row" alignItems="center" spacing={1.5}>
                <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                    <CircularProgress
                        variant="determinate"
                        value={score}
                        size={56}
                        thickness={5}
                        sx={{ color }}
                    />
                    <Box sx={{
                        top: 0, left: 0, bottom: 0, right: 0, position: 'absolute',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Typography variant="caption" fontWeight={700} sx={{ color }}>
                            {Math.round(score)}
                        </Typography>
                    </Box>
                </Box>
                <Typography variant="body2" fontWeight={600} sx={{ color }}>{label}</Typography>
            </Stack>
        </Box>
    );
}

function RulebookCard({ rulebook }) {
    if (!rulebook) return null;
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                borderRadius: 2,
                bgcolor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.15 : 0.04),
                borderColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.3 : 0.2),
            }}
        >
            <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                <ScheduleIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                <Typography variant="subtitle2" fontWeight={700} color="primary.main">
                    My Shift Rulebook
                </Typography>
                {rulebook.is_default && (
                    <Chip label="Default Rules" size="small" variant="outlined" sx={{ fontSize: 10 }} />
                )}
            </Stack>
            <Grid container spacing={1.5}>
                {[
                    { label: 'Shift Start', value: rulebook.shift_start },
                    { label: 'Shift End', value: rulebook.shift_end },
                    { label: 'Grace Period', value: `${rulebook.grace_period_minutes} min` },
                    { label: '1hr Deduct Threshold', value: `${rulebook.late_deduction_threshold_minutes} min late` },
                    { label: 'Half Day (late)', value: `≥ ${rulebook.half_day_late_threshold_minutes} min late` },
                    { label: 'Half Day (early leave)', value: `≥ ${rulebook.half_day_early_leave_minutes} min early` },
                    { label: 'Regularizations/month', value: rulebook.regularization_limit_per_month },
                    { label: 'Weekly Off', value: rulebook.weekly_off },
                ].map(({ label, value }) => (
                    <Grid key={label} item xs={6} sm={4} md={3}>
                        <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                        <Typography variant="body2" fontWeight={600}>{value}</Typography>
                    </Grid>
                ))}
            </Grid>
            {rulebook.last_edited_by && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    Last updated by {rulebook.last_edited_by}
                </Typography>
            )}
        </Paper>
    );
}

export default function MyAttendanceSection() {
    const now = useMemo(() => new Date(), []);
    const [month, setMonth] = useState(now.getMonth() + 1);
    const [year, setYear] = useState(now.getFullYear());

    const [overview, setOverview] = useState({
        summary: {}, calendar: [], recent_entries: [], today_entry: null, server_today: '',
    });
    const [rulebook, setRulebook] = useState(null);
    const [score, setScore] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showRulebook, setShowRulebook] = useState(false);

    const [form, setForm] = useState({
        entryDate: getLocalDateInputValue(),
        inTime: '09:30',
        outTime: '18:30',
        // status only for WFH/Leave explicit marking
        status: '',
        note: '',
        onDutyDetail: '',
        regularizationReason: '',
    });
    const [submitting, setSubmitting] = useState(false);
    const [submitSuccess, setSubmitSuccess] = useState('');
    const [regularizeDialogOpen, setRegularizeDialogOpen] = useState(false);

    const monthToken = `${year}-${String(month).padStart(2, '0')}`;
    const localTodayKey = useMemo(() => getLocalDateInputValue(), []);
    const effectiveTodayKey = overview.server_today || localTodayKey;
    const requiresRegularization = form.entryDate < effectiveTodayKey;

    const loadAll = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const [data, rb, sc] = await Promise.all([
                listMyAttendanceOverview({ month: monthToken }),
                getMyAttendanceRulebook().catch(() => null),
                getMyAttendanceScore({ month: monthToken }).catch(() => null),
            ]);
            setOverview({
                summary: data?.summary || {},
                calendar: Array.isArray(data?.calendar) ? data.calendar : [],
                recent_entries: Array.isArray(data?.recent_entries) ? data.recent_entries : [],
                today_entry: data?.today_entry || null,
                server_today: data?.server_today || '',
            });
            setRulebook(rb);
            setScore(sc?.score ?? null);
            if (rb) {
                setForm((prev) => ({
                    ...prev,
                    inTime: rb.shift_start || '09:30',
                    outTime: rb.shift_end || '18:30',
                }));
            }
        } catch (err) {
            setError(err?.message || 'Unable to load attendance data.');
        } finally {
            setLoading(false);
        }
    }, [monthToken]);

    useEffect(() => { loadAll(); }, [loadAll]);

    const summaryCards = [
        { key: 'present', label: 'WFO', color: 'success.main' },
        { key: 'absent', label: 'Absent', color: 'error.main' },
        { key: 'half_day', label: 'Half Day', color: 'warning.main' },
        { key: 'wfh', label: 'WFH', color: 'info.main' },
        { key: 'leave', label: 'Leave', color: 'text.secondary' },
    ];

    const yearOptions = useMemo(() => {
        const cur = new Date().getFullYear();
        return [cur - 1, cur, cur + 1];
    }, []);

    const payableDays = useMemo(() => {
        const s = overview.summary || {};
        return (
            Number(s.present || 0) + Number(s.wfh || 0) + Number(s.on_duty || 0) +
            Number(s.leave || 0) + Number(s.half_day || 0) * 0.5
        );
    }, [overview.summary]);

    const handleSubmit = async () => {
        setError('');
        setSubmitSuccess('');

        if (form.inTime && form.outTime && form.outTime <= form.inTime) {
            setError('Out time must be later than in time.');
            return;
        }
        if (!form.regularizationReason.trim()) {
            setError('Regularization reason is required.');
            return;
        }

        const payload = {
            entry_date: form.entryDate,
            in_time: form.inTime || null,
            out_time: form.outTime || null,
            note: form.note,
            on_duty_detail: form.onDutyDetail,
            is_regularization: true,
            regularization_reason: form.regularizationReason,
        };
        // Only send explicit status for WFH/Leave
        if (form.status === 'wfh' || form.status === 'leave') {
            payload.status = form.status;
        }

        setSubmitting(true);
        try {
            await createMyAttendanceEntry(payload);
            await loadAll();
            setForm((prev) => ({ ...prev, note: '', regularizationReason: '', onDutyDetail: '', status: '' }));
            setRegularizeDialogOpen(false);
            setSubmitSuccess('Regularization request submitted — pending HR approval.');
        } catch (err) {
            setError(err?.message || 'Unable to submit regularization.');
        } finally {
            setSubmitting(false);
        }
    };

    const todayEntry = overview.today_entry;
    const isHrOverridden = todayEntry?.hr_override_status;

    return (
        <Stack spacing={2}>
            {/* Header row */}
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between">
                    <Stack direction="row" spacing={1}>
                        <FormControl size="small" sx={{ minWidth: 110 }}>
                            <InputLabel>Month</InputLabel>
                            <Select label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                                {Array.from({ length: 12 }).map((_, i) => (
                                    <MenuItem key={i + 1} value={i + 1}>{monthName(i)}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 100 }}>
                            <InputLabel>Year</InputLabel>
                            <Select label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))}>
                                {yearOptions.map((y) => <MenuItem key={y} value={y}>{y}</MenuItem>)}
                            </Select>
                        </FormControl>
                    </Stack>
                    <Stack direction="row" spacing={1} alignItems="center">
                        {score !== null && <ScoreMeter score={score} />}
                        <Button
                            size="small"
                            variant="contained"
                            color="primary"
                            startIcon={<AddIcon />}
                            onClick={() => {
                                setForm({
                                    entryDate: getLocalDateInputValue(),
                                    inTime: rulebook?.shift_start || '09:30',
                                    outTime: rulebook?.shift_end || '18:30',
                                    status: '',
                                    note: '',
                                    onDutyDetail: '',
                                    regularizationReason: '',
                                });
                                setSubmitSuccess('');
                                setError('');
                                setRegularizeDialogOpen(true);
                            }}
                            sx={{ fontSize: 12, fontWeight: 700, borderRadius: '8px', textTransform: 'none' }}
                        >
                            Request Regularization
                        </Button>
                        <Button
                            size="small"
                            variant={showRulebook ? 'contained' : 'outlined'}
                            startIcon={<InfoOutlinedIcon />}
                            onClick={() => {
                                const next = !showRulebook;
                                setShowRulebook(next);
                                // Re-fetch rulebook every time the panel is expanded
                                if (next) {
                                    getMyAttendanceRulebook()
                                        .then((rb) => setRulebook(rb))
                                        .catch(() => {});
                                }
                            }}
                            sx={{ fontSize: 12, textTransform: 'none' }}
                        >
                            My Rulebook
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            startIcon={loading ? <CircularProgress size={14} /> : <RefreshIcon />}
                            onClick={loadAll}
                            disabled={loading}
                            sx={{ fontSize: 12, textTransform: 'none' }}
                        >
                            Refresh
                        </Button>
                    </Stack>
                </Stack>
            </Paper>

            {/* Rulebook card (collapsible) */}
            <Collapse in={showRulebook}>
                <RulebookCard rulebook={rulebook} />
            </Collapse>

            {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
            {submitSuccess && <Alert severity="success" icon={<CheckCircleOutlineIcon />} onClose={() => setSubmitSuccess('')}>{submitSuccess}</Alert>}

            {/* Today's status banner */}
            {todayEntry && (
                <Alert
                    severity={todayEntry.status === 'absent' ? 'error' : todayEntry.status === 'half_day' ? 'warning' : 'success'}
                    icon={<span style={{ fontSize: 18 }}>{getStatusIcon(todayEntry.status, todayEntry.work_mode)}</span>}
                >
                    <strong>Today:</strong> {formatStatus(todayEntry.status, todayEntry.work_mode)}
                    {todayEntry.in_time && ` · In ${todayEntry.in_time}`}
                    {todayEntry.out_time && ` · Out ${todayEntry.out_time}`}
                    {todayEntry.late_minutes > 0 && ` · Late ${todayEntry.late_minutes} min`}
                    {isHrOverridden && (
                        <Chip label={`HR Override: ${formatStatus(todayEntry.hr_override_status, todayEntry.work_mode)}`}
                            size="small" color="warning" sx={{ ml: 1, fontSize: 10 }} />
                    )}
                    {todayEntry.approval_status === 'pending' && (
                        <Chip label="Pending HR Approval" size="small" color="info" sx={{ ml: 1, fontSize: 10 }} />
                    )}
                </Alert>
            )}

            {/* Summary cards */}
            <Grid container spacing={1.25}>
                {summaryCards.map((card) => (
                    <Grid key={card.key} item xs={6} sm={4} md={2.4}>
                        <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                            <Typography variant="caption" color="text.secondary">{card.label}</Typography>
                            <Typography variant="h6" sx={{ fontWeight: 700, color: card.color }}>
                                {overview.summary?.[card.key] ?? 0}
                            </Typography>
                        </Paper>
                    </Grid>
                ))}
                <Grid item xs={6} sm={4} md={2.4}>
                    <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">Payable Days</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 700, color: 'primary.main' }}>
                            {payableDays.toFixed(1)}
                        </Typography>
                    </Paper>
                </Grid>
            </Grid>


            {/* Recent Entries */}
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Entries</Typography>
                </Box>
                {loading && <LinearProgress />}
                <TableContainer sx={{ maxHeight: 420 }}>
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow>
                                <TableCell>Date</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell>Auto Status</TableCell>
                                <TableCell>In</TableCell>
                                <TableCell>Out</TableCell>
                                <TableCell align="right">Late (min)</TableCell>
                                <TableCell align="right">Hours</TableCell>
                                <TableCell>Approval</TableCell>
                                <TableCell>Note</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {(overview.recent_entries || []).map((row) => (
                                <TableRow key={row.id} hover>
                                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{asDateLabel(row.entry_date)}</TableCell>
                                    <TableCell>
                                        <Chip
                                            size="small"
                                            label={formatStatus(row.status, row.work_mode)}
                                            color={STATUS_COLOR[row.status] || 'default'}
                                            variant="outlined"
                                            icon={row.hr_override_status ? <WarningAmberIcon style={{ fontSize: 12 }} /> : undefined}
                                        />
                                        {row.hr_override_status && (
                                            <Tooltip title={`HR Override: ${row.hr_override_reason || ''}`}>
                                                <Chip label="Overridden" size="small" color="warning" sx={{ ml: 0.5, fontSize: 10, height: 18 }} />
                                            </Tooltip>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {row.auto_status ? (
                                            <Typography variant="caption" color="text.secondary">
                                                {formatStatus(row.auto_status, row.work_mode)}
                                            </Typography>
                                        ) : '—'}
                                    </TableCell>
                                    <TableCell>{row.in_time || '—'}</TableCell>
                                    <TableCell>{row.out_time || '—'}</TableCell>
                                    <TableCell align="right">
                                        {row.late_minutes > 0 ? (
                                            <Typography variant="caption" color="warning.main" fontWeight={600}>
                                                {row.late_minutes}
                                            </Typography>
                                        ) : '0'}
                                    </TableCell>
                                    <TableCell align="right">{Number(row.hours_worked || 0).toFixed(2)}</TableCell>
                                    <TableCell>
                                        {row.approval_status === 'rejected' ? (
                                            <Tooltip title={`Rejection Reason: ${row.rejection_reason || 'Rejected by HR'}`} arrow>
                                                <Chip
                                                    size="small"
                                                    label="Rejected"
                                                    color="error"
                                                    variant="outlined"
                                                    sx={{ fontSize: 10, height: 20, cursor: 'help' }}
                                                />
                                            </Tooltip>
                                        ) : (
                                            <Chip
                                                size="small"
                                                label={row.approval_status === 'approved' ? 'Approved' : 'Pending'}
                                                color={row.approval_status === 'approved' ? 'success' : 'info'}
                                                variant="outlined"
                                                sx={{ fontSize: 10, height: 20 }}
                                            />
                                        )}
                                    </TableCell>
                                    <TableCell sx={{ maxWidth: 220 }}>
                                        <Stack spacing={0.5}>
                                            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'normal' }}>
                                                {row.note || row.regularization_reason || '—'}
                                            </Typography>
                                            {row.approval_status === 'rejected' && row.rejection_reason && (
                                                <Typography variant="caption" color="error.main" sx={{ whiteSpace: 'normal', fontWeight: 600 }}>
                                                    Reason: {row.rejection_reason}
                                                </Typography>
                                            )}
                                        </Stack>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {(!overview.recent_entries || overview.recent_entries.length === 0) && !loading && (
                                <TableRow>
                                    <TableCell colSpan={9}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 1.5 }}>
                                            No attendance entries for this month yet.
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>

            {/* Request Regularization Dialog */}
            <Dialog 
                open={regularizeDialogOpen} 
                onClose={() => setRegularizeDialogOpen(false)}
                maxWidth="sm"
                fullWidth
                PaperProps={{ sx: { borderRadius: '12px' } }}
            >
                <DialogTitle sx={{ fontWeight: 800 }}>Request Attendance Regularization</DialogTitle>
                <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, pt: 2 }}>
                    <Alert severity="info" sx={{ py: 0.5, fontSize: 12 }}>
                        Request HR to correct or mark backdated attendance. Requires a justification reason.
                    </Alert>
                    
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                        <TextField
                            type="date"
                            size="small"
                            label="Date to Regularize"
                            InputLabelProps={{ shrink: true }}
                            value={form.entryDate}
                            onChange={(e) => setForm((prev) => ({ ...prev, entryDate: e.target.value }))}
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                        <FormControl size="small" fullWidth sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}>
                            <InputLabel>Type (optional)</InputLabel>
                            <Select
                                label="Type (optional)"
                                value={form.status}
                                onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
                            >
                                <MenuItem value=""><em>Auto (from In/Out)</em></MenuItem>
                                <MenuItem value="wfh">🏠 WFH</MenuItem>
                                <MenuItem value="leave">🏖️ Leave</MenuItem>
                            </Select>
                        </FormControl>
                    </Stack>

                    <Stack direction="row" spacing={2}>
                        <TextField
                            type="time"
                            size="small"
                            label="In Time"
                            InputLabelProps={{ shrink: true }}
                            value={form.inTime}
                            onChange={(e) => setForm((prev) => ({ ...prev, inTime: e.target.value }))}
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                        <TextField
                            type="time"
                            size="small"
                            label="Out Time"
                            InputLabelProps={{ shrink: true }}
                            value={form.outTime}
                            onChange={(e) => setForm((prev) => ({ ...prev, outTime: e.target.value }))}
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                    </Stack>

                    <TextField
                        size="small"
                        label="Note (optional)"
                        placeholder="e.g. Forgot to punch out"
                        value={form.note}
                        onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))}
                        fullWidth
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                    />

                    <TextField
                        size="small"
                        label="Regularization Reason *"
                        placeholder="Provide detailed justification for HR approval..."
                        multiline
                        rows={2}
                        value={form.regularizationReason}
                        onChange={(e) => setForm((prev) => ({ ...prev, regularizationReason: e.target.value }))}
                        fullWidth
                        required
                        error={!form.regularizationReason.trim()}
                        helperText={!form.regularizationReason.trim() ? "Reason is required to submit a request." : ""}
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                    />
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setRegularizeDialogOpen(false)} sx={{ textTransform: 'none', fontWeight: 600 }}>
                        Cancel
                    </Button>
                    <Button 
                        onClick={handleSubmit} 
                        variant="contained" 
                        disabled={submitting || !form.regularizationReason.trim()}
                        startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px', px: 3 }}
                    >
                        {submitting ? 'Submitting...' : 'Submit Request'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}
