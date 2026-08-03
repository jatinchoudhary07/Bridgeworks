import React, { useState, useEffect } from 'react';
import {
    Box, Paper, Typography, Button, Table, TableBody, TableCell,
    TableContainer, TableHead, TableRow, Chip, TextField, Dialog,
    DialogTitle, DialogContent, DialogActions, FormControl, InputLabel,
    Select, MenuItem, Stack, Alert, CircularProgress, IconButton, Tooltip
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import GavelIcon from '@mui/icons-material/Gavel';
import CancelIcon from '@mui/icons-material/Cancel';
import RefreshIcon from '@mui/icons-material/Refresh';
import EditIcon from '@mui/icons-material/Edit';

import { listHrAttendanceAnomalies, resolveHrAttendanceAnomaly } from '../mydesk/mydeskService';

const RESOLUTION_COLORS = {
    unresolved: 'error',
    ok: 'success',
    suspicious: 'warning',
    dismissed: 'default'
};

const RESOLUTION_LABELS = {
    unresolved: 'Unresolved',
    ok: 'Marked OK',
    suspicious: 'Suspicious',
    dismissed: 'Dismissed'
};

export default function AttendanceAnomalyPanel() {
    const [anomalies, setAnomalies] = useState([]);
    const [totalUnresolved, setTotalUnresolved] = useState(0);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState('unresolved');
    const [days, setDays] = useState(30);
    const [error, setError] = useState('');

    // Resolution dialog states
    const [resolveDialog, setResolveDialog] = useState(null); // session payload
    const [resolutionState, setResolutionState] = useState('ok');
    const [resolutionNote, setResolutionNote] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        loadAnomalies();
    }, [filter, days]);

    const loadAnomalies = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await listHrAttendanceAnomalies(filter, days);
            setAnomalies(Array.isArray(data?.anomalies) ? data.anomalies : []);
            setTotalUnresolved(data?.total_unresolved || 0);
        } catch (err) {
            setError(err?.message || 'Failed to fetch anomalies.');
        } finally {
            setLoading(false);
        }
    };

    const handleOpenResolveDialog = (session) => {
        setResolveDialog(session);
        setResolutionState(session.anomaly_resolution === 'unresolved' ? 'ok' : session.anomaly_resolution);
        setResolutionNote(session.anomaly_resolution_note || '');
    };

    const handleSaveResolution = async () => {
        if (!resolveDialog) return;
        setSaving(true);
        try {
            await resolveHrAttendanceAnomaly(resolveDialog.id, {
                resolution: resolutionState,
                note: resolutionNote.trim()
            });
            setResolveDialog(null);
            await loadAnomalies();
        } catch (err) {
            alert(err?.message || 'Failed to save resolution.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error && <Alert severity="error">{error}</Alert>}

            {/* Overview / Filter bar */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems="center">
                    <Stack direction="row" spacing={1.5} alignItems="center">
                        <WarningIcon color="error" />
                        <Typography variant="subtitle1" fontWeight={700}>
                            Geofencing Anomalies & Spoof Audit
                        </Typography>
                        {totalUnresolved > 0 && (
                            <Chip label={`${totalUnresolved} Unresolved`} color="error" size="small" />
                        )}
                    </Stack>

                    <Stack direction="row" spacing={1.5} alignItems="center">
                        <FormControl size="small" sx={{ minWidth: 140 }}>
                            <InputLabel>Status</InputLabel>
                            <Select label="Status" value={filter} onChange={(e) => setFilter(e.target.value)}>
                                <MenuItem value="all">All Anomalies</MenuItem>
                                <MenuItem value="unresolved">Unresolved</MenuItem>
                                <MenuItem value="ok">Resolved OK</MenuItem>
                                <MenuItem value="suspicious">Confirmed Suspicious</MenuItem>
                                <MenuItem value="dismissed">Dismissed</MenuItem>
                            </Select>
                        </FormControl>

                        <FormControl size="small" sx={{ minWidth: 110 }}>
                            <InputLabel>Timeframe</InputLabel>
                            <Select label="Timeframe" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                                <MenuItem value={7}>Last 7 days</MenuItem>
                                <MenuItem value={30}>Last 30 days</MenuItem>
                                <MenuItem value={90}>Last 90 days</MenuItem>
                            </Select>
                        </FormControl>

                        <IconButton onClick={loadAnomalies} disabled={loading} color="primary">
                            <RefreshIcon />
                        </IconButton>
                    </Stack>
                </Stack>
            </Paper>

            {/* List Table */}
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                {loading && <CircularProgress size={24} sx={{ m: 3, display: 'block', mx: 'auto' }} />}
                
                {!loading && (
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Employee</TableCell>
                                <TableCell>Date / Time</TableCell>
                                <TableCell>IP Signal</TableCell>
                                <TableCell>GPS Signal</TableCell>
                                <TableCell>Reason for Flag</TableCell>
                                <TableCell>Resolution</TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {anomalies.map((row) => (
                                <TableRow key={row.id} hover>
                                    <TableCell>
                                        <Stack spacing={0.25}>
                                            <Typography variant="body2" fontWeight={600}>{row.user_name}</Typography>
                                            <Typography variant="caption" color="text.secondary">{row.user_email}</Typography>
                                        </Stack>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2">
                                            {new Date(row.login_at).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            {new Date(row.login_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2" component="code" sx={{ bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5 }}>
                                            {row.login_ip || 'No IP'}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            {row.ip_matched_office ? `Matches ${row.ip_matched_office}` : 'Unregistered IP'}
                                        </Typography>
                                    </TableCell>
                                    <TableCell>
                                        {row.login_latitude ? (
                                            <>
                                                <Typography variant="body2">
                                                    {parseFloat(row.login_latitude).toFixed(4)}, {parseFloat(row.login_longitude).toFixed(4)}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary" display="block">
                                                    {row.gps_distance_meters ? `${parseInt(row.gps_distance_meters)}m from ${row.gps_nearest_office || 'office'}` : 'Distance unknown'}
                                                </Typography>
                                            </>
                                        ) : (
                                            <Chip label={row.gps_status} color="default" size="small" variant="outlined" />
                                        )}
                                    </TableCell>
                                    <TableCell sx={{ maxWidth: 220 }}>
                                        <Stack spacing={0.5}>
                                            {row.anomaly_reasons?.map((reason, idx) => (
                                                <Typography key={idx} variant="caption" color="error.main" display="block" sx={{ fontWeight: 500 }}>
                                                    • {reason}
                                                </Typography>
                                            ))}
                                        </Stack>
                                    </TableCell>
                                    <TableCell>
                                        <Stack direction="row" spacing={1} alignItems="center">
                                            <Chip
                                                size="small"
                                                label={RESOLUTION_LABELS[row.anomaly_resolution]}
                                                color={RESOLUTION_COLORS[row.anomaly_resolution]}
                                                variant="outlined"
                                            />
                                            {row.anomaly_resolution !== 'unresolved' && (
                                                <Tooltip title={`By: ${row.anomaly_resolved_by || 'Admin'}\nNotes: ${row.anomaly_resolution_note || 'None'}`}>
                                                    <IconButton size="small">
                                                        <CheckCircleIcon fontSize="inherit" color="action" />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                        </Stack>
                                    </TableCell>
                                    <TableCell align="right">
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            onClick={() => handleOpenResolveDialog(row)}
                                            startIcon={<EditIcon />}
                                        >
                                            Audit
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {anomalies.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={7} sx={{ p: 4, textAlign: 'center' }}>
                                        <Typography variant="body2" color="text.secondary">No anomalies flagged in this period.</Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                )}
            </TableContainer>

            {/* Resolve Dialog */}
            <Dialog open={Boolean(resolveDialog)} onClose={() => setResolveDialog(null)} maxWidth="sm" fullWidth>
                <DialogTitle>Audit Geofence Flag: {resolveDialog?.user_name}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2.5} mt={1.5}>
                        <Alert severity="error">
                            <strong>Anomaly Reasons:</strong>
                            <Box sx={{ mt: 1 }}>
                                {resolveDialog?.anomaly_reasons?.map((reason, idx) => (
                                    <div key={idx}>• {reason}</div>
                                ))}
                            </Box>
                        </Alert>

                        <FormControl size="small" fullWidth>
                            <InputLabel>Audit Determination</InputLabel>
                            <Select
                                label="Audit Determination"
                                value={resolutionState}
                                onChange={(e) => setResolutionState(e.target.value)}
                            >
                                <MenuItem value="ok">Marked OK (Legitimate Override / False Positive)</MenuItem>
                                <MenuItem value="suspicious">Confirmed Suspicious (Spoofing / Location Jump)</MenuItem>
                                <MenuItem value="dismissed">Dismissed (No Action Required)</MenuItem>
                            </Select>
                        </FormControl>

                        <TextField
                            label="Resolution / Audit Note"
                            placeholder="Add reason for override, VPN explanation, or client visit confirmation..."
                            multiline
                            rows={3}
                            value={resolutionNote}
                            onChange={(e) => setResolutionNote(e.target.value)}
                            fullWidth
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 3 }}>
                    <Button onClick={() => setResolveDialog(null)} color="inherit">Cancel</Button>
                    <Button variant="contained" onClick={handleSaveResolution} disabled={saving} startIcon={<GavelIcon />}>
                        {saving ? 'Saving...' : 'Resolve Flag'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
