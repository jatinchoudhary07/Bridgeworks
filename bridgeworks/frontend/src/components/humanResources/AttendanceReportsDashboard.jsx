import React, { useState, useEffect } from 'react';
import {
    Box, Paper, Typography, Grid, Button, Stack, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, Chip, TextField,
    FormControl, InputLabel, Select, MenuItem, CircularProgress, Alert,
    IconButton, Card, CardContent, Collapse, Tooltip
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import BusinessIcon from '@mui/icons-material/Business';
import HomeIcon from '@mui/icons-material/Home';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PeopleIcon from '@mui/icons-material/People';
import DateRangeIcon from '@mui/icons-material/DateRange';

import { listHrAttendanceReport } from '../mydesk/mydeskService';

// Safe date default helper
function getLocalDateString(date = new Date()) {
    const local = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
    return local.toISOString().slice(0, 10);
}

export default function AttendanceReportsDashboard() {
    const [period, setPeriod] = useState('monthly');
    const [selectedDate, setSelectedDate] = useState(getLocalDateString());
    const [month, setMonth] = useState(`${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`);
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [reportData, setReportData] = useState(null);

    // Expanded row state (for detailed daily list)
    const [expandedRow, setExpandedRow] = useState(null);

    useEffect(() => {
        loadReport();
    }, [period, selectedDate, month]);

    const loadReport = async () => {
        setLoading(true);
        setError('');
        try {
            const dateVal = period === 'monthly' ? '' : selectedDate;
            const monthVal = period === 'monthly' ? month : '';
            const data = await listHrAttendanceReport(period, dateVal, monthVal);
            setReportData(data);
        } catch (err) {
            setError(err?.message || 'Failed to fetch report.');
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadCsv = () => {
        const queryParams = new URLSearchParams();
        if (period === 'monthly') {
            queryParams.set('month', month);
        } else {
            // Default to current month if daily/weekly is selected
            queryParams.set('month', month);
        }
        
        // Open download link
        window.open(`/api/hr/attendance/report/export/?${queryParams.toString()}`, '_blank');
    };

    const toggleRow = (userId) => {
        setExpandedRow(prev => (prev === userId ? null : userId));
    };

    return (
        <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
            {error && <Alert severity="error">{error}</Alert>}

            {/* Filter Panel */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems="center">
                    <Stack direction="row" spacing={1.5} alignItems="center">
                        <DateRangeIcon color="primary" />
                        <Typography variant="subtitle1" fontWeight={700}>Attendance & Geofence Analytics</Typography>
                    </Stack>

                    <Stack direction="row" spacing={2} alignItems="center">
                        <FormControl size="small" sx={{ minWidth: 120 }}>
                            <InputLabel>View By</InputLabel>
                            <Select label="View By" value={period} onChange={(e) => setPeriod(e.target.value)}>
                                <MenuItem value="daily">Daily View</MenuItem>
                                <MenuItem value="weekly">Weekly View</MenuItem>
                                <MenuItem value="monthly">Monthly Register</MenuItem>
                            </Select>
                        </FormControl>

                        {period === 'monthly' ? (
                            <TextField
                                size="small"
                                type="month"
                                label="Month"
                                InputLabelProps={{ shrink: true }}
                                value={month}
                                onChange={(e) => setMonth(e.target.value)}
                            />
                        ) : (
                            <TextField
                                size="small"
                                type="date"
                                label="Date"
                                InputLabelProps={{ shrink: true }}
                                value={selectedDate}
                                onChange={(e) => setSelectedDate(e.target.value)}
                            />
                        )}

                        <Button
                            variant="contained"
                            startIcon={<DownloadIcon />}
                            onClick={handleDownloadCsv}
                            sx={{ whiteSpace: 'nowrap' }}
                        >
                            Export CSV
                        </Button>
                    </Stack>
                </Stack>
            </Paper>

            {/* Loading Indicator */}
            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
                    <CircularProgress />
                </Box>
            )}

            {/* Metrics Cards */}
            {!loading && reportData && (
                <Grid container spacing={2.5}>
                    {/* Summary Cards */}
                    <Grid item xs={6} sm={3}>
                        <Card variant="outlined" sx={{ borderRadius: 2.5 }}>
                            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'primary.light', color: 'primary.contrastText', display: 'flex' }}>
                                    <PeopleIcon />
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary" fontWeight={500}>Total Employees</Typography>
                                    <Typography variant="h6" fontWeight={700}>{reportData.summary?.total_employees || 0}</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={6} sm={3}>
                        <Card variant="outlined" sx={{ borderRadius: 2.5 }}>
                            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'success.light', color: 'success.contrastText', display: 'flex' }}>
                                    <BusinessIcon />
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary" fontWeight={500}>WFO Days (Office)</Typography>
                                    <Typography variant="h6" fontWeight={700}>{reportData.summary?.total_wfo_days || 0}</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={6} sm={3}>
                        <Card variant="outlined" sx={{ borderRadius: 2.5 }}>
                            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'info.light', color: 'info.contrastText', display: 'flex' }}>
                                    <HomeIcon />
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary" fontWeight={500}>WFH Days (Home)</Typography>
                                    <Typography variant="h6" fontWeight={700}>{reportData.summary?.total_wfh_days || 0}</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid item xs={6} sm={3}>
                        <Card variant="outlined" sx={{ borderRadius: 2.5 }}>
                            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: 'warning.light', color: 'warning.contrastText', display: 'flex' }}>
                                    <AccessTimeIcon />
                                </Box>
                                <Box>
                                    <Typography variant="caption" color="text.secondary" fontWeight={500}>WFO / WFH Ratio</Typography>
                                    <Typography variant="h6" fontWeight={700}>{reportData.summary?.wfo_ratio || 0}% Office</Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Ratio visual indicator bar */}
                    <Grid item xs={12}>
                        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                            <Typography variant="subtitle2" fontWeight={600} mb={1}>Workplace Mode Ratio Breakdown</Typography>
                            <Box sx={{ width: '100%', height: 16, borderRadius: 8, overflow: 'hidden', display: 'flex', bgcolor: 'grey.100' }}>
                                <Tooltip title={`WFO: ${reportData.summary?.total_wfo_days} days`}>
                                    <Box sx={{ width: `${reportData.summary?.wfo_ratio || 0}%`, bgcolor: 'success.main', height: '100%' }} />
                                </Tooltip>
                                <Tooltip title={`WFH: ${reportData.summary?.total_wfh_days} days`}>
                                    <Box sx={{ flex: 1, bgcolor: 'info.main', height: '100%' }} />
                                </Tooltip>
                            </Box>
                            <Stack direction="row" spacing={3} mt={1.5}>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: 'success.main' }} />
                                    <Typography variant="caption" fontWeight={600}>WFO (Office): {reportData.summary?.total_wfo_days || 0} days ({reportData.summary?.wfo_ratio || 0}%)</Typography>
                                </Stack>
                                <Stack direction="row" spacing={1} alignItems="center">
                                    <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: 'info.main' }} />
                                    <Typography variant="caption" fontWeight={600}>WFH (Home): {reportData.summary?.total_wfh_days || 0} days ({100 - (reportData.summary?.wfo_ratio || 0)}%)</Typography>
                                </Stack>
                            </Stack>
                        </Paper>
                    </Grid>

                    {/* Breakdown Register */}
                    <Grid item xs={12}>
                        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell />
                                        <TableCell>Employee</TableCell>
                                        <TableCell align="right">Present Days</TableCell>
                                        <TableCell align="right">WFO (Office)</TableCell>
                                        <TableCell align="right">WFH (Home)</TableCell>
                                        <TableCell align="right">Leave Days</TableCell>
                                        <TableCell align="right">Absent Days</TableCell>
                                        <TableCell align="right">Hours Worked</TableCell>
                                        <TableCell align="right">Late Min</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {(reportData.employees || []).map((emp) => {
                                        const isExpanded = expandedRow === emp.user_id;
                                        return (
                                            <React.Fragment key={emp.user_id}>
                                                <TableRow hover>
                                                    <TableCell sx={{ width: 40 }}>
                                                        <IconButton size="small" onClick={() => toggleRow(emp.user_id)}>
                                                            {isExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                                                        </IconButton>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Stack spacing={0.25}>
                                                            <Typography variant="body2" fontWeight={600}>{emp.name}</Typography>
                                                            <Typography variant="caption" color="text.secondary">{emp.email}</Typography>
                                                        </Stack>
                                                    </TableCell>
                                                    <TableCell align="right" sx={{ fontWeight: 600 }}>{emp.present}</TableCell>
                                                    <TableCell align="right">
                                                        <Chip label={emp.wfo} size="small" color="success" variant="outlined" />
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Chip label={emp.wfh} size="small" color="info" variant="outlined" />
                                                    </TableCell>
                                                    <TableCell align="right">{emp.leave}</TableCell>
                                                    <TableCell align="right">{emp.absent}</TableCell>
                                                    <TableCell align="right">{parseFloat(emp.total_hours).toFixed(1)} hrs</TableCell>
                                                    <TableCell align="right" sx={{ color: emp.total_late_minutes > 0 ? 'error.main' : 'inherit' }}>
                                                        {emp.total_late_minutes} min
                                                    </TableCell>
                                                </TableRow>

                                                {/* Expanded Daily breakdown list */}
                                                <TableRow>
                                                    <TableCell colSpan={9} sx={{ py: 0, bgcolor: 'action.hover' }}>
                                                        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                                                            <Box sx={{ p: 2 }}>
                                                                <Typography variant="subtitle2" fontWeight={600} mb={1}>Daily Log Detail</Typography>
                                                                <Table size="small" sx={{ bgcolor: 'background.paper', borderRadius: 1.5, overflow: 'hidden' }}>
                                                                    <TableHead>
                                                                        <TableRow>
                                                                            <TableCell>Date</TableCell>
                                                                            <TableCell>Status</TableCell>
                                                                            <TableCell>Work Mode</TableCell>
                                                                            <TableCell>In Time</TableCell>
                                                                            <TableCell>Out Time</TableCell>
                                                                            <TableCell align="right">Hours</TableCell>
                                                                            <TableCell align="right">Late Mark</TableCell>
                                                                        </TableRow>
                                                                    </TableHead>
                                                                    <TableBody>
                                                                        {emp.days?.map((day, idx) => (
                                                                            <TableRow key={idx}>
                                                                                <TableCell>{day.date}</TableCell>
                                                                                <TableCell>
                                                                                    <Chip label={day.status} size="small" color={day.status === 'present' || day.status === 'wfh' ? 'success' : 'default'} variant="outlined" />
                                                                                </TableCell>
                                                                                <TableCell>
                                                                                    {day.work_mode !== 'unknown' ? (
                                                                                        <Chip label={day.work_mode.toUpperCase()} size="small" color={day.work_mode === 'wfo' ? 'success' : 'info'} />
                                                                                    ) : (
                                                                                        '-'
                                                                                    )}
                                                                                </TableCell>
                                                                                <TableCell>{day.in_time || '-'}</TableCell>
                                                                                <TableCell>{day.out_time || '-'}</TableCell>
                                                                                <TableCell align="right">{day.hours} hrs</TableCell>
                                                                                <TableCell align="right" sx={{ color: day.late_min > 0 ? 'error.main' : 'inherit' }}>
                                                                                    {day.late_min > 0 ? `${day.late_min} min` : '-'}
                                                                                </TableCell>
                                                                            </TableRow>
                                                                        ))}
                                                                    </TableBody>
                                                                </Table>
                                                            </Box>
                                                        </Collapse>
                                                    </TableCell>
                                                </TableRow>
                                            </React.Fragment>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Grid>
                </Grid>
            )}
        </Box>
    );
}
