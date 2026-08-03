import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
    DialogContent, DialogTitle, FormControl, Grid, IconButton, InputLabel, LinearProgress,
    MenuItem, Paper, Select, Stack, Tab, Tabs, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, TextField, Tooltip, Typography,
    Avatar,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import SettingsIcon from '@mui/icons-material/Settings';
import {
    listHrAttendanceEmployeeSummary,
    listHrAttendanceMonthlyRegister,
    listHrAttendanceToday,
    saveHrAttendanceToday,
    listHrRegularizationQueue,
    actionHrRegularization,
    hrOverrideAttendance,
    getHrAttendanceRulebook,
    updateHrAttendanceRulebook,
    listHrAttendanceScores,
    hrListLeaveRequests,
    hrActionLeaveRequest,
} from '../mydesk/mydeskService';

import OfficeLocationManager from './OfficeLocationManager';
import AttendanceAnomalyPanel from './AttendanceAnomalyPanel';
import AttendanceReportsDashboard from './AttendanceReportsDashboard';

// Helper to generate initials and soft background colors for employee avatars
const stringToColor = (name) => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const colors = [
        '#6366f1', // Indigo
        '#06b6d4', // Cyan
        '#0d9488', // Teal
        '#10b981', // Emerald
        '#d97706', // Amber
        '#ef4444', // Red
        '#ec4899', // Pink
        '#8b5cf6'  // Purple
    ];
    const index = Math.abs(hash) % colors.length;
    return colors[index];
};

const getAvatarProps = (name) => {
    if (!name) return { sx: { bgcolor: '#9ca3af' }, children: '?' };
    const parts = name.trim().split(/\s+/);
    const initials = parts.length > 1 
        ? `${parts[0][0]}${parts[parts.length - 1][0]}` 
        : parts[0][0];
    return {
        sx: {
            bgcolor: stringToColor(name),
            width: 34,
            height: 34,
            fontSize: '0.8rem',
            fontWeight: 700,
            color: '#ffffff',
            boxShadow: '0 2px 5px rgba(0,0,0,0.08)'
        },
        children: initials.toUpperCase()
    };
};

const getStatusBadgeDetails = (status) => {
    switch (status) {
        case 'present':
        case 'wfo':
            return { color: '#10b981', text: 'WFO' };
        case 'wfh':
            return { color: '#3b82f6', text: 'WFH' };
        case 'absent':
            return { color: '#ef4444', text: 'Absent' };
        case 'half_day_wfo':
            return { color: '#f59e0b', text: 'Half Day (WFO)' };
        case 'half_day_wfh':
            return { color: '#f59e0b', text: 'Half Day (WFH)' };
        case 'half_day':
            return { color: '#f59e0b', text: 'Half Day' };
        case 'leave':
            return { color: '#6b7280', text: 'Leave' };
        default:
            return { color: '#9ca3af', text: status || 'Present' };
    }
};


const STATUS_OPTIONS = [
    { value: 'present', label: '🏢 WFO' },
    { value: 'wfh', label: '🏠 WFH' },
    { value: 'absent', label: 'Absent' },
    { value: 'half_day_wfo', label: '⏳ Half Day (WFO)' },
    { value: 'half_day_wfh', label: '⏳ Half Day (WFH)' },
    { value: 'half_day', label: '⏳ Half Day' },
    { value: 'leave', label: 'Leave' },
];

const STATUS_SHORT = {
    present: 'P',
    absent: 'A',
    half_day: 'H',
    half_day_wfo: 'H(O)',
    half_day_wfh: 'H(H)',
    wfh: 'W',
    on_duty: 'OD',
    leave: 'L',
};

const STATUS_COLOR = {
    present: 'success',
    absent: 'error',
    half_day: 'warning',
    half_day_wfo: 'warning',
    half_day_wfh: 'warning',
    wfh: 'info',
    on_duty: 'secondary',
    leave: 'default',
};

function monthName(index) {
    return new Date(2000, index, 1).toLocaleString(undefined, { month: 'short' });
}

function dateLabel(value) {
    if (!value) return '-';
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function getLocalDateInputValue(date = new Date()) {
    const local = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
    return local.toISOString().slice(0, 10);
}

function getStatusLabelAndTooltip(dayData) {
    if (!dayData) return { label: '-', tooltip: '' };
    const status = dayData.status;
    const workMode = dayData.work_mode;
    
    let label = '';
    let tooltip = '';
    
    if (status === 'half_day') {
        if (workMode === 'wfh') {
            label = 'H(H)';
            tooltip = 'Half Day (Work From Home)';
        } else if (workMode === 'wfo') {
            label = 'H(O)';
            tooltip = 'Half Day (Work From Office)';
        } else {
            label = 'H';
            tooltip = 'Half Day';
        }
    } else if (status === 'present') {
        label = 'P';
        tooltip = 'WFO (Present)';
    } else if (status === 'wfh') {
        label = 'W';
        tooltip = 'WFH (Present)';
    } else {
        label = STATUS_SHORT[status] || '-';
        tooltip = String(status || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }
    
    if (dayData.late_minutes > 0) {
        tooltip += ` (Late by ${dayData.late_minutes} min)`;
    }
    
    return { label, tooltip };
}

export default function HRAttendanceDashboard() {
    const [tab, setTab] = useState(0);

    const now = useMemo(() => new Date(), []);
    const [selectedDate, setSelectedDate] = useState(getLocalDateInputValue());
    const [month, setMonth] = useState(now.getMonth() + 1);
    const [year, setYear] = useState(now.getFullYear());
    const monthToken = `${year}-${String(month).padStart(2, '0')}`;

    const [todayData, setTodayData] = useState({ rows: [] });
    const [todayDrafts, setTodayDrafts] = useState({});
    const [todayLoading, setTodayLoading] = useState(false);
    const [todaySaving, setTodaySaving] = useState(false);

    const [registerData, setRegisterData] = useState({ days: [], rows: [] });
    const [registerLoading, setRegisterLoading] = useState(false);

    const [summaryRows, setSummaryRows] = useState([]);
    const [summaryLoading, setSummaryLoading] = useState(false);

    // Regularization queue
    const [regsRows, setRegsRows] = useState([]);
    const [regsLoading, setRegsLoading] = useState(false);
    const [regsFilter, setRegsFilter] = useState('pending');
    const [regsActing, setRegsActing] = useState(null); // entry id

    // Attendance scores
    const [scoresRows, setScoresRows] = useState([]);
    const [scoresLoading, setScoresLoading] = useState(false);

    // Override dialog
    const [overrideDialog, setOverrideDialog] = useState(null); // { entryId, currentStatus, employeeName }
    const [overrideStatus, setOverrideStatus] = useState('');
    const [overrideWorkMode, setOverrideWorkMode] = useState('unknown');
    const [overrideReason, setOverrideReason] = useState('');
    const [overrideSaving, setOverrideSaving] = useState(false);

    // Rulebook dialog
    const [rulebookDialog, setRulebookDialog] = useState(null); // { userId, employeeName }
    const [rulebookData, setRulebookData] = useState({});
    const [rulebookSaving, setRulebookSaving] = useState(false);

    // Leave requests
    const [leavesRows, setLeavesRows] = useState([]);
    const [leavesLoading, setLeavesLoading] = useState(false);
    const [leavesFilter, setLeavesFilter] = useState('');
    const [leavesActing, setLeavesActing] = useState(null);
    const [rejectLeaveDialog, setRejectLeaveDialog] = useState(null);
    const [rejectLeaveReason, setRejectLeaveReason] = useState('');

    const [error, setError] = useState('');

    const yearOptions = useMemo(() => {
        const current = new Date().getFullYear();
        return [current - 1, current, current + 1];
    }, []);

    const loadToday = useCallback(async () => {
        setTodayLoading(true);
        setError('');
        try {
            const data = await listHrAttendanceToday({ date: selectedDate });
            const rows = Array.isArray(data?.rows) ? data.rows : [];
            const seeded = {};
            rows.forEach((row) => {
                // Combine status + work_mode into a virtual "half_day_wfo" / "half_day_wfh" for the UI dropdown
                let draftStatus = row.status || 'present';
                if (draftStatus === 'half_day') {
                    if (row.work_mode === 'wfh') draftStatus = 'half_day_wfh';
                    else if (row.work_mode === 'wfo') draftStatus = 'half_day_wfo';
                }
                seeded[row.user_id] = {
                    status: draftStatus,
                    in_time: row.in_time || '',
                    out_time: row.out_time || '',   // leave blank if not yet recorded
                    note: row.note || '',
                    on_duty_detail: row.on_duty_detail || '',
                };
            });
            setTodayData({ rows });
            setTodayDrafts(seeded);
        } catch (err) {
            setError(err?.message || 'Unable to load today attendance list.');
        } finally {
            setTodayLoading(false);
        }
    }, [selectedDate]);

    const loadRegister = useCallback(async () => {
        setRegisterLoading(true);
        setError('');
        try {
            const data = await listHrAttendanceMonthlyRegister({ month: monthToken });
            setRegisterData({
                days: Array.isArray(data?.days) ? data.days : [],
                rows: Array.isArray(data?.rows) ? data.rows : [],
            });
        } catch (err) {
            setError(err?.message || 'Unable to load monthly register.');
        } finally {
            setRegisterLoading(false);
        }
    }, [monthToken]);

    const loadSummary = useCallback(async () => {
        setSummaryLoading(true);
        setError('');
        try {
            const data = await listHrAttendanceEmployeeSummary({ month: monthToken });
            setSummaryRows(Array.isArray(data?.rows) ? data.rows : []);
        } catch (err) {
            setError(err?.message || 'Unable to load employee summary.');
        } finally {
            setSummaryLoading(false);
        }
    }, [monthToken]);

    useEffect(() => {
        if (tab === 0) loadToday();
    }, [tab, loadToday]);

    useEffect(() => {
        if (tab === 1) loadRegister();
    }, [tab, loadRegister]);

    useEffect(() => {
        if (tab === 2) loadSummary();
    }, [tab, loadSummary]);

    const loadRegularizations = useCallback(async () => {
        setRegsLoading(true);
        try {
            const data = await listHrRegularizationQueue({ approval_status: regsFilter, month: monthToken });
            setRegsRows(Array.isArray(data?.rows) ? data.rows : []);
        } catch { /* handled */ } finally { setRegsLoading(false); }
    }, [regsFilter, monthToken]);

    const loadScores = useCallback(async () => {
        setScoresLoading(true);
        try {
            const data = await listHrAttendanceScores({ month: monthToken });
            setScoresRows(Array.isArray(data?.rows) ? data.rows : []);
        } catch { /* handled */ } finally { setScoresLoading(false); }
    }, [monthToken]);

    useEffect(() => {
        if (tab === 3) loadRegularizations();
    }, [tab, loadRegularizations]);

    useEffect(() => {
        if (tab === 4) loadScores();
    }, [tab, loadScores]);

    const loadLeaves = useCallback(async () => {
        setLeavesLoading(true);
        try {
            const filters = { month: monthToken };
            if (leavesFilter) filters.status = leavesFilter;
            const data = await hrListLeaveRequests(filters);
            setLeavesRows(Array.isArray(data?.rows) ? data.rows : []);
        } catch { /* handled */ } finally { setLeavesLoading(false); }
    }, [monthToken, leavesFilter]);

    useEffect(() => {
        if (tab === 5) loadLeaves();
    }, [tab, loadLeaves]);

    const updateDraft = (userId, key, value) => {
        setTodayDrafts((previous) => ({
            ...previous,
            [userId]: {
                ...(previous[userId] || {}),
                [key]: value,
            },
        }));
    };

    const saveToday = async () => {
        const rows = (todayData.rows || [])
            .filter((row) => {
                const draft = todayDrafts[row.user_id];
                if (!draft) return false;
                
                // Compare status, in_time, out_time, note, on_duty_detail
                const originalStatus = row.status || 'present';
                let draftStatus = draft.status || 'present';
                
                const statusChanged = draftStatus !== originalStatus;
                const inTimeChanged = (draft.in_time || '') !== (row.in_time ? row.in_time.substring(0, 5) : '');
                const outTimeChanged = (draft.out_time || '') !== (row.out_time ? row.out_time.substring(0, 5) : '');
                const noteChanged = (draft.note || '') !== (row.note || '');
                const onDutyChanged = (draft.on_duty_detail || '') !== (row.on_duty_detail || '');
                
                return statusChanged || inTimeChanged || outTimeChanged || noteChanged || onDutyChanged;
            })
            .map((row) => ({
                user_id: row.user_id,
                ...(todayDrafts[row.user_id] || {}),
            }));

        if (rows.length === 0) {
            return;
        }

        setTodaySaving(true);
        try {
            await saveHrAttendanceToday({ date: selectedDate, rows });
            await loadToday();
        } catch {
            // notification handled in service layer
        } finally {
            setTodaySaving(false);
        }
    };

    return (
        <Box sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            {/* ── Filters Toolbar ── */}
            <Paper 
                variant="outlined" 
                sx={{ 
                    p: 2, 
                    borderRadius: '16px', 
                    bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(30, 41, 59, 0.4)' : 'rgba(248, 250, 252, 0.8)',
                    borderColor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
                    boxShadow: '0 2px 12px rgba(0, 0, 0, 0.02)'
                }}
            >
                <Stack
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={2}
                    justifyContent="space-between"
                    alignItems={{ xs: 'stretch', md: 'center' }}
                >
                    <Stack direction="row" spacing={1.5} alignItems="center">
                        <Box sx={{ p: 1, borderRadius: '10px', bgcolor: 'rgba(94, 106, 210, 0.1)', color: '#5E6AD2', display: 'flex' }}>
                            <CalendarTodayIcon fontSize="small" />
                        </Box>
                        <Box>
                            <Typography variant="subtitle2" fontWeight={800} sx={{ color: 'text.primary' }}>
                                Attendance Register Toolbar
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                Filter by specific date, month, or year
                            </Typography>
                        </Box>
                    </Stack>

                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                        <TextField
                            type="date"
                            size="small"
                            label="Date"
                            InputLabelProps={{ shrink: true }}
                            value={selectedDate}
                            onChange={(event) => setSelectedDate(event.target.value)}
                            sx={{ 
                                minWidth: 165,
                                '& .MuiOutlinedInput-root': { borderRadius: '8px' }
                            }}
                        />
                        <FormControl size="small" sx={{ minWidth: 120 }}>
                            <InputLabel>Month</InputLabel>
                            <Select 
                                label="Month" 
                                value={month} 
                                onChange={(event) => setMonth(Number(event.target.value))}
                                sx={{ borderRadius: '8px' }}
                            >
                                {Array.from({ length: 12 }).map((_, index) => (
                                    <MenuItem key={index + 1} value={index + 1}>{monthName(index)}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 110 }}>
                            <InputLabel>Year</InputLabel>
                            <Select 
                                label="Year" 
                                value={year} 
                                onChange={(event) => setYear(Number(event.target.value))}
                                sx={{ borderRadius: '8px' }}
                            >
                                {yearOptions.map((option) => (
                                    <MenuItem key={option} value={option}>{option}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Stack>
                </Stack>
            </Paper>

            {/* ── Tabs Navigation ── */}
            <Paper 
                variant="outlined" 
                sx={{ 
                    borderRadius: '12px', 
                    p: 0.5, 
                    bgcolor: 'background.paper',
                    borderColor: 'divider',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.02)'
                }}
            >
                <Tabs 
                    value={tab} 
                    onChange={(_, v) => setTab(v)} 
                    variant="scrollable" 
                    scrollButtons="auto"
                    sx={{
                        minHeight: 40,
                        '& .MuiTabs-indicator': {
                            display: 'none', // Hide standard line indicator
                        },
                        '& .MuiTabs-flexContainer': {
                            gap: '4px',
                        }
                    }}
                >
                    {["Today's Marking", "Monthly Register", "Employee Summary", "Regularizations", "Attendance Scores", "Leave Requests", "Office Locations", "Anomaly Flags", "Detailed Analytics"].map((label, idx) => (
                        <Tab 
                            key={idx}
                            label={label} 
                            sx={{
                                minHeight: 36,
                                py: 1,
                                px: 2.25,
                                borderRadius: '8px',
                                fontSize: '0.8125rem',
                                fontWeight: tab === idx ? 700 : 500,
                                textTransform: 'none',
                                color: tab === idx ? '#ffffff !important' : 'text.secondary',
                                bgcolor: tab === idx ? '#5E6AD2' : 'transparent',
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    bgcolor: tab === idx ? '#5E6AD2' : 'action.hover',
                                    color: tab === idx ? '#ffffff' : 'text.primary',
                                }
                            }}
                        />
                    ))}
                </Tabs>
            </Paper>

            {error && <Alert severity="error" sx={{ borderRadius: '8px' }}>{error}</Alert>}

            {/* ── Today's Marking Tab ── */}
            {tab === 0 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                                Today's Attendance ({dateLabel(selectedDate)})
                            </Typography>
                            <Button 
                                variant="contained" 
                                onClick={saveToday} 
                                disabled={todayLoading || todaySaving}
                                sx={{
                                    textTransform: 'none',
                                    fontWeight: 700,
                                    borderRadius: '8px',
                                    px: 3.5,
                                    py: 1,
                                    background: 'linear-gradient(135deg, #5E6AD2 0%, #4D58C2 100%)',
                                    boxShadow: '0 4px 12px rgba(94, 106, 210, 0.25)',
                                    '&:hover': {
                                        background: 'linear-gradient(135deg, #6E7BE2 0%, #5E6AD2 100%)',
                                        boxShadow: '0 6px 16px rgba(94, 106, 210, 0.35)',
                                        transform: 'translateY(-1px)'
                                    },
                                    '&:active': {
                                        transform: 'translateY(0)'
                                    },
                                    transition: 'all 0.2s ease'
                                }}
                            >
                                {todaySaving ? 'Saving...' : 'Save Today'}
                            </Button>
                        </Stack>
                    </Box>
                    <TableContainer sx={{ maxHeight: 500 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{ fontWeight: 700, pl: 3 }}>Employee</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>In</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Out</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Duty Note</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Override Reason</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 3 }}>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {(todayData.rows || []).map((employee) => {
                                    const draft = todayDrafts[employee.user_id] || {};
                                    return (
                                        <TableRow key={employee.user_id} hover>
                                            <TableCell sx={{ pl: 3 }}>
                                                <Stack direction="row" spacing={1.5} alignItems="center">
                                                    <Avatar {...getAvatarProps(employee.employee_name)} />
                                                    <Stack spacing={0.1}>
                                                        <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                                                            {employee.employee_name || 'Employee'}
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {employee.email || '-'}
                                                        </Typography>
                                                    </Stack>
                                                </Stack>
                                            </TableCell>
                                            <TableCell>
                                                <FormControl size="small" sx={{ minWidth: 175 }}>
                                                    <Select
                                                        value={draft.status || 'present'}
                                                        onChange={(event) => updateDraft(employee.user_id, 'status', event.target.value)}
                                                        sx={{ borderRadius: '8px' }}
                                                        renderValue={(selected) => {
                                                            const details = getStatusBadgeDetails(selected);
                                                            return (
                                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                    <Box sx={{ width: 8, height: 8, borderRadius: '55%', bgcolor: details.color }} />
                                                                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{details.text}</Typography>
                                                                </Box>
                                                            );
                                                        }}
                                                    >
                                                        {STATUS_OPTIONS.map((option) => {
                                                            const details = getStatusBadgeDetails(option.value);
                                                            return (
                                                                <MenuItem key={option.value} value={option.value} sx={{ py: 1 }}>
                                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                                                                        <Box sx={{ width: 8, height: 8, borderRadius: '55%', bgcolor: details.color }} />
                                                                        <Typography variant="body2">{option.label}</Typography>
                                                                    </Box>
                                                                </MenuItem>
                                                            );
                                                        })}
                                                    </Select>
                                                </FormControl>
                                            </TableCell>
                                            <TableCell>
                                                <TextField
                                                    type="time"
                                                    size="small"
                                                    value={draft.in_time || ''}
                                                    onChange={(event) => updateDraft(employee.user_id, 'in_time', event.target.value)}
                                                    sx={{ 
                                                        width: 150,
                                                        '& .MuiOutlinedInput-root': { borderRadius: '8px' } 
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <TextField
                                                    type="time"
                                                    size="small"
                                                    value={draft.out_time || ''}
                                                    onChange={(event) => updateDraft(employee.user_id, 'out_time', event.target.value)}
                                                    sx={{ 
                                                        width: 150,
                                                        '& .MuiOutlinedInput-root': { borderRadius: '8px' } 
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <TextField
                                                    size="small"
                                                    value={draft.on_duty_detail || ''}
                                                    onChange={(event) => updateDraft(employee.user_id, 'on_duty_detail', event.target.value)}
                                                    placeholder="Client visit / duty note"
                                                    sx={{ 
                                                        minWidth: 180,
                                                        '& .MuiOutlinedInput-root': { borderRadius: '8px' } 
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <TextField
                                                    size="small"
                                                    value={draft.note || ''}
                                                    onChange={(event) => updateDraft(employee.user_id, 'note', event.target.value)}
                                                    placeholder="Optional note"
                                                    sx={{ 
                                                        minWidth: 160,
                                                        '& .MuiOutlinedInput-root': { borderRadius: '8px' } 
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell align="right" sx={{ pr: 3 }}>
                                                {employee.record_id && (
                                                    <Tooltip title="Override attendance with audit log">
                                                        <Button size="small" color="warning" variant="outlined"
                                                            startIcon={<EditIcon sx={{ fontSize: '0.9rem' }} />}
                                                            onClick={() => {
                                                                setOverrideStatus(employee.status || '');
                                                                setOverrideWorkMode(employee.work_mode || 'unknown');
                                                                setOverrideReason('');
                                                                setOverrideDialog({
                                                                    entryId: employee.record_id,
                                                                    employeeName: employee.employee_name,
                                                                    currentStatus: employee.status,
                                                                });
                                                            }}
                                                            sx={{ 
                                                                borderRadius: '8px', 
                                                                textTransform: 'none', 
                                                                fontWeight: 700,
                                                                borderColor: 'rgba(245, 158, 11, 0.4)',
                                                                color: '#d97706',
                                                                '&:hover': {
                                                                    borderColor: '#d97706',
                                                                    bgcolor: 'rgba(245, 158, 11, 0.05)'
                                                                }
                                                            }}
                                                        >
                                                            Override
                                                        </Button>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                                {todayData.rows.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={7}>
                                            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                                                {todayLoading ? 'Loading team attendance list...' : 'No users found for attendance marking.'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {tab === 1 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                            Monthly Attendance Register ({monthName(month - 1)} {year})
                        </Typography>
                    </Box>
                    <TableContainer sx={{ maxHeight: 520 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{
                                        position: 'sticky',
                                        left: 0,
                                        zIndex: 4,
                                        bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : '#f8fafc',
                                        borderRight: '1px solid',
                                        borderColor: 'divider',
                                        minWidth: 160,
                                        fontWeight: 800,
                                        textTransform: 'uppercase',
                                        fontSize: '0.75rem',
                                        letterSpacing: '0.05em'
                                    }}>Employee</TableCell>
                                    {registerData.days.map((day) => (
                                        <TableCell key={`day-${day}`} align="center" sx={{ minWidth: 36, px: 0.5, py: 1, fontWeight: 700 }}>
                                            {new Date(`${day}T00:00:00`).getDate()}
                                        </TableCell>
                                    ))}
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>P</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>H</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>W</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>OD</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>L</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>A</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 2 }}>Payable</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {registerData.rows.map((row) => (
                                    <TableRow key={row.user_id} hover>
                                        <TableCell sx={{
                                            position: 'sticky',
                                            left: 0,
                                            zIndex: 2,
                                            bgcolor: 'background.paper',
                                            borderRight: '1px solid',
                                            borderColor: 'divider',
                                            fontWeight: 600,
                                            whiteSpace: 'nowrap',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 1.25,
                                            py: 1.5
                                        }}>
                                            <Avatar {...getAvatarProps(row.employee_name)} sx={{ ...getAvatarProps(row.employee_name).sx, width: 26, height: 26, fontSize: '0.7rem' }} />
                                            <Typography variant="body2" fontWeight={600}>{row.employee_name || `User #${row.user_id}`}</Typography>
                                        </TableCell>
                                        {(row.cells || []).map((dayData) => {
                                            const { label, tooltip } = getStatusLabelAndTooltip(dayData);
                                            return (
                                                <TableCell key={`${row.user_id}-${dayData.date}`} align="center" sx={{ px: 0.25, py: 0.75 }}>
                                                    <Tooltip title={tooltip}>
                                                        <Chip
                                                            size="small"
                                                            label={label}
                                                            color={STATUS_COLOR[dayData.status] || 'default'}
                                                            variant="outlined"
                                                            sx={{ 
                                                                minWidth: 26, 
                                                                height: 20, 
                                                                fontSize: '0.58rem', 
                                                                fontWeight: 700,
                                                                borderRadius: '4px',
                                                                '& .MuiChip-label': { px: 0.25 } 
                                                            }}
                                                        />
                                                    </Tooltip>
                                                </TableCell>
                                            );
                                        })}
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.present || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.half_day || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.wfh || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.on_duty || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.leave || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 500 }}>{row.totals?.absent || 0}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700, pr: 2, color: 'primary.main' }}>{row.totals?.payable_days || 0}</TableCell>
                                    </TableRow>
                                ))}
                                {registerData.rows.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={registerData.days.length + 8}>
                                            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                                                {registerLoading ? 'Loading monthly register...' : 'No register data available for this month.'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {tab === 2 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                            Payroll Summary ({monthName(month - 1)} {year})
                        </Typography>
                    </Box>
                    <TableContainer sx={{ maxHeight: 520 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{ fontWeight: 700 }}>Employee</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Payable Days</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>WFO</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Half Day</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>WFH</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>OD</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Leave</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Absent</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Late Marks</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Deduction Days</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 2 }}>Total Hours</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {summaryRows.map((row) => (
                                    <TableRow key={row.user_id} hover>
                                        <TableCell sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1.25, py: 1.5 }}>
                                            <Avatar {...getAvatarProps(row.employee_name)} sx={{ ...getAvatarProps(row.employee_name).sx, width: 26, height: 26, fontSize: '0.7rem' }} />
                                            <Typography variant="body2" fontWeight={600}>{row.employee_name || `User #${row.user_id}`}</Typography>
                                        </TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700, color: 'primary.main' }}>{row.payable_days || 0}</TableCell>
                                        <TableCell align="right">{row.present_days || 0}</TableCell>
                                        <TableCell align="right">{row.half_days || 0}</TableCell>
                                        <TableCell align="right">{row.wfh_days || 0}</TableCell>
                                        <TableCell align="right">{row.on_duty_days || 0}</TableCell>
                                        <TableCell align="right">{row.leave_days || 0}</TableCell>
                                        <TableCell align="right">{row.absent_days || 0}</TableCell>
                                        <TableCell align="right" sx={{ color: row.late_marks > 0 ? 'warning.main' : 'inherit', fontWeight: row.late_marks > 0 ? 600 : 500 }}>{row.late_marks || 0}</TableCell>
                                        <TableCell align="right" sx={{ color: row.deduction_days > 0 ? 'error.main' : 'inherit', fontWeight: row.deduction_days > 0 ? 600 : 500 }}>{row.deduction_days || 0}</TableCell>
                                        <TableCell align="right" sx={{ pr: 2, fontWeight: 500 }}>{Number(row.total_hours || 0).toFixed(2)} hrs</TableCell>
                                    </TableRow>
                                ))}
                                {summaryRows.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={11}>
                                            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                                                {summaryLoading ? 'Loading employee summary...' : 'No summary data available for this month.'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}
            {tab === 3 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1.5}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                                Regularization Queue
                            </Typography>
                            <Stack direction="row" spacing={1}>
                                {['pending', 'approved', 'rejected'].map((f) => (
                                    <Button 
                                        key={f} 
                                        size="small"
                                        variant={regsFilter === f ? 'contained' : 'outlined'}
                                        onClick={() => setRegsFilter(f)}
                                        sx={{ 
                                            textTransform: 'none', 
                                            fontWeight: 700,
                                            borderRadius: '8px',
                                            px: 2,
                                            bgcolor: regsFilter === f ? '#5E6AD2' : 'transparent',
                                            '&:hover': {
                                                bgcolor: regsFilter === f ? '#4D58C2' : 'action.hover'
                                            }
                                        }}
                                    >
                                        {f.charAt(0).toUpperCase() + f.slice(1)}
                                    </Button>
                                ))}
                            </Stack>
                        </Stack>
                    </Box>
                    {regsLoading && <LinearProgress />}
                    <TableContainer sx={{ maxHeight: 500 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{ fontWeight: 700, pl: 3 }}>Employee</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Date</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>In / Out Time</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Auto Status</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Reason</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Approval Status</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 3 }}>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {regsRows.map((row) => (
                                    <TableRow key={row.id} hover>
                                        <TableCell sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1.25, py: 1.5, pl: 3 }}>
                                            <Avatar {...getAvatarProps(row.employee_name)} sx={{ ...getAvatarProps(row.employee_name).sx, width: 28, height: 28, fontSize: '0.75rem' }} />
                                            <Typography variant="body2" fontWeight={600}>{row.employee_name}</Typography>
                                        </TableCell>
                                        <TableCell sx={{ whiteSpace: 'nowrap' }}>{row.entry_date}</TableCell>
                                        <TableCell>{row.in_time || '—'} → {row.out_time || '—'}</TableCell>
                                        <TableCell>
                                            <Chip size="small" label={row.auto_status || '—'}
                                                color={STATUS_COLOR[row.auto_status] || 'default'} variant="outlined" sx={{ borderRadius: '6px', fontWeight: 600 }} />
                                        </TableCell>
                                        <TableCell sx={{ maxWidth: 220 }}>
                                            <Typography variant="caption" sx={{ whiteSpace: 'normal', color: 'text.secondary' }}>
                                                {row.regularization_reason || '—'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip size="small"
                                                label={row.approval_status}
                                                color={row.approval_status === 'approved' ? 'success' : row.approval_status === 'pending' ? 'info' : 'error'}
                                                variant="filled" sx={{ borderRadius: '6px', fontWeight: 700, textTransform: 'capitalize' }} />
                                        </TableCell>
                                        <TableCell align="right" sx={{ pr: 3 }}>
                                            {row.approval_status === 'pending' && (
                                                <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                                    <Tooltip title="Approve">
                                                        <IconButton size="small" color="success"
                                                            disabled={regsActing === row.id}
                                                            onClick={async () => {
                                                                setRegsActing(row.id);
                                                                try {
                                                                    await actionHrRegularization(row.id, { action: 'approve' });
                                                                    await loadRegularizations();
                                                                } finally { setRegsActing(null); }
                                                            }}
                                                            sx={{ bgcolor: 'rgba(34, 197, 94, 0.08)', '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.15)' } }}
                                                        >
                                                            <CheckIcon fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                    <Tooltip title="Reject">
                                                        <IconButton size="small" color="error"
                                                            disabled={regsActing === row.id}
                                                            onClick={async () => {
                                                                setRegsActing(row.id);
                                                                try {
                                                                    await actionHrRegularization(row.id, { action: 'reject', reason: 'Rejected by HR' });
                                                                    await loadRegularizations();
                                                                } finally { setRegsActing(null); }
                                                            }}
                                                            sx={{ bgcolor: 'rgba(239, 68, 68, 0.08)', '&:hover': { bgcolor: 'rgba(239, 68, 68, 0.15)' } }}
                                                        >
                                                            <CloseIcon fontSize="small" />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Stack>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {regsRows.length === 0 && !regsLoading && (
                                    <TableRow><TableCell colSpan={7}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>No {regsFilter} regularizations found.</Typography>
                                    </TableCell></TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {tab === 4 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                            Attendance Scores — {monthName(month - 1)} {year}
                        </Typography>
                    </Box>
                    {scoresLoading && <LinearProgress />}
                    <TableContainer sx={{ maxHeight: 500 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{ fontWeight: 700, pl: 3 }}>Employee</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Performance Score</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Absent Days</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>Late Marks</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 3 }}>Rulebook Configuration</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {scoresRows.map((row) => {
                                    const color = row.score >= 90 ? '#22c55e' : row.score >= 75 ? '#f59e0b' : '#ef4444';
                                    return (
                                        <TableRow key={row.user_id} hover>
                                            <TableCell sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1.25, py: 1.5, pl: 3 }}>
                                                <Avatar {...getAvatarProps(row.employee_name)} sx={{ ...getAvatarProps(row.employee_name).sx, width: 28, height: 28, fontSize: '0.75rem' }} />
                                                <Typography variant="body2" fontWeight={600}>{row.employee_name}</Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Stack direction="row" spacing={2} alignItems="center">
                                                    <Box sx={{ width: 120 }}>
                                                        <LinearProgress variant="determinate" value={row.score}
                                                            sx={{
                                                                height: 8, borderRadius: 4, bgcolor: 'action.hover',
                                                                '& .MuiLinearProgress-bar': { bgcolor: color }
                                                            }} />
                                                    </Box>
                                                    <Typography variant="body2" fontWeight={800} sx={{ color }}>
                                                        {row.score}%
                                                    </Typography>
                                                </Stack>
                                            </TableCell>
                                            <TableCell align="right">{row.absent_count}</TableCell>
                                            <TableCell align="right">{row.late_count}</TableCell>
                                            <TableCell align="right" sx={{ pr: 3 }}>
                                                <Button
                                                    size="small"
                                                    variant="outlined"
                                                    startIcon={<EditIcon sx={{ fontSize: '0.9rem' }} />}
                                                    onClick={async () => {
                                                        try {
                                                            const rb = await getHrAttendanceRulebook(row.user_id);
                                                            setRulebookData(rb || {});
                                                            setRulebookDialog({ userId: row.user_id, employeeName: row.employee_name });
                                                        } catch {
                                                            // fallback: open with empty
                                                            setRulebookData({});
                                                            setRulebookDialog({ userId: row.user_id, employeeName: row.employee_name });
                                                        }
                                                    }}
                                                    sx={{ 
                                                        textTransform: 'none', 
                                                        fontWeight: 700,
                                                        borderRadius: '8px',
                                                        borderColor: 'divider',
                                                        '&:hover': {
                                                            borderColor: '#5E6AD2',
                                                            bgcolor: 'rgba(94, 106, 210, 0.04)'
                                                        }
                                                    }}
                                                >
                                                    Edit Rulebook
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                                {scoresRows.length === 0 && !scoresLoading && (
                                    <TableRow><TableCell colSpan={5}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>No score data available.</Typography>
                                    </TableCell></TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {/* ── Leave Requests Tab ── */}
            {tab === 5 && (
                <Paper 
                    variant="outlined" 
                    sx={{ 
                        borderRadius: '16px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)',
                        borderColor: 'divider'
                    }}
                >
                    <Box 
                        sx={{ 
                            px: 3, 
                            py: 2.25, 
                            borderBottom: '1px solid', 
                            borderColor: 'divider',
                            bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.01)' : 'rgba(94, 106, 210, 0.02)'
                        }}
                    >
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 800, color: 'text.primary' }}>
                                Leave Request Applications
                            </Typography>
                            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" gap={1}>
                                <FormControl size="small" sx={{ minWidth: 140 }}>
                                    <InputLabel>Status</InputLabel>
                                    <Select label="Status" value={leavesFilter} onChange={(e) => setLeavesFilter(e.target.value)} sx={{ borderRadius: '8px' }}>
                                        <MenuItem value="">All Statuses</MenuItem>
                                        <MenuItem value="pending">Pending</MenuItem>
                                        <MenuItem value="approved">Approved</MenuItem>
                                        <MenuItem value="rejected">Rejected</MenuItem>
                                    </Select>
                                </FormControl>
                                <Button size="small" variant="outlined" onClick={loadLeaves} disabled={leavesLoading} sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px' }}>Refresh</Button>
                            </Stack>
                        </Stack>
                    </Box>
                    {leavesLoading && <LinearProgress />}
                    <TableContainer sx={{ maxHeight: 520 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow sx={{ bgcolor: (theme) => theme.palette.mode === 'dark' ? '#0f172a' : 'rgba(94, 106, 210, 0.03)' }}>
                                    <TableCell sx={{ fontWeight: 700, pl: 3 }}>Employee</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Leave Type</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>From Date</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>To Date</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700 }}>Days</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Reason</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                                    <TableCell sx={{ fontWeight: 700 }}>Submitted</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, pr: 3, minWidth: 180 }}>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {leavesRows.map((row) => {
                                    const isPending = row.status === 'pending';
                                    const acting = leavesActing === row.id;
                                    const days = (() => {
                                        try {
                                            const s = new Date(`${row.start_date}T00:00:00`);
                                            const e = new Date(`${row.end_date}T00:00:00`);
                                            return Math.max(1, Math.round((e - s) / 86400000) + 1);
                                        } catch { return 1; }
                                    })();
                                    return (
                                        <TableRow key={row.id} hover
                                            sx={{ bgcolor: row.status === 'approved' ? 'rgba(34,197,94,0.02)' : row.status === 'rejected' ? 'rgba(239,68,68,0.02)' : 'transparent' }}>
                                            <TableCell sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1.25, py: 1.5, pl: 3 }}>
                                                <Avatar {...getAvatarProps(row.requested_by_name)} sx={{ ...getAvatarProps(row.requested_by_name).sx, width: 28, height: 28, fontSize: '0.75rem' }} />
                                                <Typography variant="body2" fontWeight={600}>{row.requested_by_name || `User #${row.id}`}</Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip size="small" label={(row.leave_type || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} variant="outlined" sx={{ borderRadius: '6px', fontWeight: 600 }} />
                                            </TableCell>
                                            <TableCell>{dateLabel(row.start_date)}</TableCell>
                                            <TableCell>{dateLabel(row.end_date)}</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 600 }}>{days}</TableCell>
                                            <TableCell sx={{ maxWidth: 200 }}>
                                                <Typography variant="caption" noWrap title={row.reason} sx={{ display: 'block', textOverflow: 'ellipsis', overflow: 'hidden' }}>{row.reason || '—'}</Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip size="small"
                                                    label={row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                                                    color={row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'error' : 'warning'}
                                                    variant="filled" sx={{ borderRadius: '6px', fontWeight: 700 }}
                                                />
                                                {row.status === 'rejected' && row.decline_reason && (
                                                    <Tooltip title={`Reason: ${row.decline_reason}`}><span> ℹ️</span></Tooltip>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption" color="text.secondary">
                                                    {row.created_at ? new Date(row.created_at).toLocaleDateString('en-GB') : '—'}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right" sx={{ pr: 3 }}>
                                                {isPending ? (
                                                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                                                        <Button size="small" variant="contained" color="success"
                                                            disabled={acting}
                                                            startIcon={<CheckIcon fontSize="small" />}
                                                            onClick={async () => {
                                                                setLeavesActing(row.id);
                                                                try {
                                                                    await hrActionLeaveRequest(row.id, { action: 'approve' });
                                                                    await loadLeaves();
                                                                } catch { /* handled */ } finally { setLeavesActing(null); }
                                                            }}
                                                            sx={{ textTransform: 'none', fontSize: 11, fontWeight: 700, borderRadius: '6px' }}>
                                                            Approve
                                                        </Button>
                                                        <Button size="small" variant="outlined" color="error"
                                                            disabled={acting}
                                                            startIcon={<CloseIcon fontSize="small" />}
                                                            onClick={() => { setRejectLeaveDialog(row); setRejectLeaveReason(''); }}
                                                            sx={{ textTransform: 'none', fontSize: 11, fontWeight: 700, borderRadius: '6px' }}>
                                                            Reject
                                                        </Button>
                                                    </Stack>
                                                ) : (
                                                    <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                                        {row.approved_by_name ? `By ${row.approved_by_name}` : 'Processed'}
                                                    </Typography>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                                {leavesRows.length === 0 && !leavesLoading && (
                                    <TableRow><TableCell colSpan={9}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>No leave requests found.</Typography>
                                    </TableCell></TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}

            {tab === 6 && <OfficeLocationManager />}
            {tab === 7 && <AttendanceAnomalyPanel />}
            {tab === 8 && <AttendanceReportsDashboard />}

            {/* Reject Leave Dialog */}
            <Dialog 
                open={!!rejectLeaveDialog} 
                onClose={() => setRejectLeaveDialog(null)} 
                maxWidth="sm" 
                fullWidth
                PaperProps={{ sx: { borderRadius: '16px' } }}
            >
                <DialogTitle sx={{ fontWeight: 800 }}>Reject Leave Request</DialogTitle>
                <DialogContent>
                    <Alert severity="warning" sx={{ mb: 2.5, borderRadius: '8px', fontSize: 12 }}>
                        Employee will be notified with your rejection reason. Their attendance dates will remain as <strong>Absent</strong> unless they regularize.
                    </Alert>
                    <TextField 
                        autoFocus 
                        fullWidth 
                        multiline 
                        rows={3} 
                        size="small"
                        label="Rejection Reason *"
                        value={rejectLeaveReason}
                        onChange={(e) => setRejectLeaveReason(e.target.value)}
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                    />
                </DialogContent>
                <DialogActions sx={{ p: 2.5, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Button onClick={() => setRejectLeaveDialog(null)} sx={{ textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}>Cancel</Button>
                    <Button variant="contained" color="error"
                        disabled={!rejectLeaveReason.trim() || leavesActing === rejectLeaveDialog?.id}
                        onClick={async () => {
                            if (!rejectLeaveDialog) return;
                            setLeavesActing(rejectLeaveDialog.id);
                            try {
                                await hrActionLeaveRequest(rejectLeaveDialog.id, { action: 'reject', decline_reason: rejectLeaveReason.trim() });
                                setRejectLeaveDialog(null);
                                await loadLeaves();
                            } catch { /* handled */ } finally { setLeavesActing(null); }
                        }}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px', px: 3 }}>
                        Confirm Rejection
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Override Dialog */}
            <Dialog 
                open={!!overrideDialog} 
                onClose={() => setOverrideDialog(null)} 
                maxWidth="sm" 
                fullWidth
                PaperProps={{ sx: { borderRadius: '16px' } }}
            >
                <DialogTitle sx={{ fontWeight: 800 }}>Override Attendance — {overrideDialog?.employeeName}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2.5} sx={{ mt: 1.5 }}>
                        <Alert severity="warning" sx={{ borderRadius: '8px', fontSize: 12 }}>
                            Override is logged with your name and timestamp. Employee will see this change.
                        </Alert>
                        <FormControl size="small" fullWidth>
                            <InputLabel>New Status</InputLabel>
                            <Select 
                                label="New Status" 
                                value={overrideStatus} 
                                onChange={(e) => {
                                    setOverrideStatus(e.target.value);
                                    if (e.target.value === 'half_day_wfo') setOverrideWorkMode('wfo');
                                    else if (e.target.value === 'half_day_wfh') setOverrideWorkMode('wfh');
                                }}
                                sx={{ borderRadius: '8px' }}
                            >
                                {STATUS_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
                            </Select>
                        </FormControl>
                        {!['half_day_wfo', 'half_day_wfh'].includes(overrideStatus) && (
                            <FormControl size="small" fullWidth>
                                <InputLabel>Work Mode</InputLabel>
                                <Select label="Work Mode" value={overrideWorkMode} onChange={(e) => setOverrideWorkMode(e.target.value)} sx={{ borderRadius: '8px' }}>
                                    <MenuItem value="wfo">🏢 Work From Office</MenuItem>
                                    <MenuItem value="wfh">🏠 Work From Home</MenuItem>
                                    <MenuItem value="unknown">❓ Unknown</MenuItem>
                                </Select>
                            </FormControl>
                        )}
                        <TextField 
                            label="Override Reason *" 
                            size="small" 
                            fullWidth 
                            multiline 
                            rows={2}
                            value={overrideReason} 
                            onChange={(e) => setOverrideReason(e.target.value)}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ p: 2.5, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Button onClick={() => setOverrideDialog(null)} sx={{ textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}>Cancel</Button>
                    <Button variant="contained" color="warning" disabled={overrideSaving || !overrideStatus || !overrideReason}
                        onClick={async () => {
                            setOverrideSaving(true);
                            try {
                                let submitStatus = overrideStatus;
                                let submitWorkMode = overrideWorkMode;
                                if (overrideStatus === 'half_day_wfo') { submitStatus = 'half_day'; submitWorkMode = 'wfo'; }
                                else if (overrideStatus === 'half_day_wfh') { submitStatus = 'half_day'; submitWorkMode = 'wfh'; }
                                await hrOverrideAttendance(overrideDialog.entryId, { 
                                    status: submitStatus, 
                                    work_mode: submitWorkMode,
                                    reason: overrideReason 
                                });
                                setOverrideDialog(null); setOverrideStatus(''); setOverrideWorkMode('unknown'); setOverrideReason('');
                                await loadToday();
                            } finally { setOverrideSaving(false); }
                        }}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px', px: 3 }}>
                        {overrideSaving ? 'Saving…' : 'Apply Override'}
                    </Button>
                </DialogActions>
            </Dialog>


            {/* Rulebook Edit Dialog */}
            <Dialog 
                open={!!rulebookDialog} 
                onClose={() => setRulebookDialog(null)} 
                maxWidth="lg" 
                fullWidth
                PaperProps={{
                    sx: {
                        borderRadius: 3,
                        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.08)',
                    }
                }}
            >
                <DialogTitle sx={{ 
                    p: 2.5, 
                    background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)', 
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                }}>
                    <Stack>
                        <Typography variant="h6" fontWeight={700}>Edit Attendance Rulebook</Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                            Customize work hours, penalties, and schedule rules for <strong>{rulebookDialog?.employeeName}</strong>
                        </Typography>
                    </Stack>
                    <IconButton onClick={() => setRulebookDialog(null)} sx={{ color: 'white' }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent sx={{ p: 3, bgcolor: '#f8fafc' }}>
                    <Grid container spacing={3} sx={{ mt: 0.25 }}>
                        {/* Section 1: Shift & Grace */}
                        <Grid item xs={12} md={4}>
                            <Paper variant="outlined" sx={{ p: 2.5, height: '100%', borderRadius: 3, bgcolor: 'background.paper', display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                                <Stack direction="row" alignItems="center" spacing={1.25} sx={{ pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                                    <Box sx={{ p: 0.75, borderRadius: 1.5, bgcolor: 'primary.light', color: 'primary.main', display: 'flex' }}>
                                        <AccessTimeIcon fontSize="small" />
                                    </Box>
                                    <Stack>
                                        <Typography variant="subtitle2" fontWeight={700}>Shift Timings & Grace</Typography>
                                        <Typography variant="caption" color="text.secondary">Specify work hours and buffer period</Typography>
                                    </Stack>
                                </Stack>

                                <TextField 
                                    label="Shift Start" 
                                    size="small" 
                                    fullWidth 
                                    type="time"
                                    InputLabelProps={{ shrink: true }}
                                    value={rulebookData.shift_start ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, shift_start: e.target.value }))} 
                                />
                                <TextField 
                                    label="Shift End" 
                                    size="small" 
                                    fullWidth 
                                    type="time"
                                    InputLabelProps={{ shrink: true }}
                                    value={rulebookData.shift_end ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, shift_end: e.target.value }))} 
                                />
                                <TextField 
                                    label="Grace Period (minutes)" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.grace_period_minutes ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, grace_period_minutes: e.target.value }))} 
                                />
                                <TextField 
                                    label="Max Regularizations / Month" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.regularization_limit_per_month ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, regularization_limit_per_month: e.target.value }))} 
                                />
                            </Paper>
                        </Grid>

                        {/* Section 2: Penalty Thresholds */}
                        <Grid item xs={12} md={4}>
                            <Paper variant="outlined" sx={{ p: 2.5, height: '100%', borderRadius: 3, bgcolor: 'background.paper', display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                                <Stack direction="row" alignItems="center" spacing={1.25} sx={{ pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                                    <Box sx={{ p: 0.75, borderRadius: 1.5, bgcolor: 'warning.light', color: 'warning.main', display: 'flex' }}>
                                        <WarningAmberIcon fontSize="small" />
                                    </Box>
                                    <Stack>
                                        <Typography variant="subtitle2" fontWeight={700}>Attendance Penalties</Typography>
                                        <Typography variant="caption" color="text.secondary">Set limits for late arrivals and early leaves</Typography>
                                    </Stack>
                                </Stack>

                                <TextField 
                                    label="Late 1hr Deduct Threshold (min)" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.late_deduction_threshold_minutes ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, late_deduction_threshold_minutes: e.target.value }))} 
                                />
                                <TextField 
                                    label="Late Half Day Threshold (min)" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.half_day_late_threshold_minutes ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, half_day_late_threshold_minutes: e.target.value }))} 
                                />
                                <TextField 
                                    label="Early Leave Deduct (min)" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.early_leave_deduction_minutes ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, early_leave_deduction_minutes: e.target.value }))} 
                                />
                                <TextField 
                                    label="Half Day Early Leave (min)" 
                                    size="small" 
                                    fullWidth 
                                    type="number"
                                    value={rulebookData.half_day_early_leave_minutes ?? ''}
                                    onChange={(e) => setRulebookData((prev) => ({ ...prev, half_day_early_leave_minutes: e.target.value }))} 
                                />
                            </Paper>
                        </Grid>

                        {/* Section 3: Schedule & Shift Type */}
                        <Grid item xs={12} md={4}>
                            <Paper variant="outlined" sx={{ p: 2.5, height: '100%', borderRadius: 3, bgcolor: 'background.paper', display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                                <Stack direction="row" alignItems="center" spacing={1.25} sx={{ pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                                    <Box sx={{ p: 0.75, borderRadius: 1.5, bgcolor: 'info.light', color: 'info.main', display: 'flex' }}>
                                        <CalendarTodayIcon fontSize="small" />
                                    </Box>
                                    <Stack>
                                        <Typography variant="subtitle2" fontWeight={700}>Work Schedule</Typography>
                                        <Typography variant="caption" color="text.secondary">Define weekly offs and Saturday policies</Typography>
                                    </Stack>
                                </Stack>

                                <FormControl size="small" fullWidth>
                                    <InputLabel>Employee Type</InputLabel>
                                    <Select 
                                        label="Employee Type" 
                                        value={rulebookData.employee_type || ''}
                                        onChange={(e) => setRulebookData((prev) => ({ ...prev, employee_type: e.target.value }))}
                                    >
                                        <MenuItem value="office">🏢 Office</MenuItem>
                                        <MenuItem value="labour">👷 Labour</MenuItem>
                                        <MenuItem value="field">🚗 Field</MenuItem>
                                    </Select>
                                </FormControl>

                                <FormControl size="small" fullWidth>
                                    <InputLabel>Weekly Off</InputLabel>
                                    <Select 
                                        label="Weekly Off" 
                                        value={rulebookData.weekly_off || ''}
                                        onChange={(e) => setRulebookData((prev) => ({ ...prev, weekly_off: e.target.value }))}
                                    >
                                        <MenuItem value="sunday">Sunday</MenuItem>
                                        <MenuItem value="saturday">Saturday</MenuItem>
                                        <MenuItem value="none">None</MenuItem>
                                    </Select>
                                </FormControl>

                                <FormControl size="small" fullWidth>
                                    <InputLabel>Saturday Working</InputLabel>
                                    <Select 
                                        label="Saturday Working" 
                                        value={rulebookData.saturday_working || ''}
                                        onChange={(e) => setRulebookData((prev) => ({ ...prev, saturday_working: e.target.value }))}
                                    >
                                        <MenuItem value="yes">Yes</MenuItem>
                                        <MenuItem value="no">No</MenuItem>
                                        <MenuItem value="alternate">Alternate</MenuItem>
                                    </Select>
                                </FormControl>
                            </Paper>
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions sx={{ p: 2.5, bgcolor: '#f1f5f9', borderTop: '1px solid', borderColor: 'divider' }}>
                    <Button onClick={() => setRulebookDialog(null)} sx={{ textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}>
                        Cancel
                    </Button>
                    <Button 
                        variant="contained" 
                        disabled={rulebookSaving}
                        onClick={async () => {
                            setRulebookSaving(true);
                            try {
                                await updateHrAttendanceRulebook(rulebookDialog.userId, rulebookData);
                                setRulebookDialog(null);
                                await loadScores();
                            } finally { setRulebookSaving(false); }
                        }}
                        sx={{ 
                            textTransform: 'none', 
                            fontWeight: 600,
                            borderRadius: 2,
                            px: 3,
                            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                            boxShadow: '0 4px 12px 0 rgba(15, 23, 42, 0.15)',
                            '&:hover': {
                                background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)',
                            }
                        }}
                    >
                        {rulebookSaving ? 'Saving…' : 'Save Rulebook'}
                    </Button>
                </DialogActions>
            </Dialog>

        </Box>
    );
}
