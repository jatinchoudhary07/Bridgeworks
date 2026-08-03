import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
    Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
    DialogContent, DialogTitle, Divider, FormControl, IconButton, InputLabel,
    LinearProgress, MenuItem, Paper, Select, Stack, TextField, Tooltip, Typography,
} from '@mui/material';
import {
    Delete as DeleteIcon,
    Edit as EditIcon,
    AttachFile as AttachFileIcon,
    CheckCircleOutline as CheckCircleOutlineIcon,
    HourglassEmpty as HourglassEmptyIcon,
    Cancel as CancelIcon,
    NotificationsActive as NotificationsActiveIcon,
    OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import { createMyDeskLeave, deleteMyDeskLeave, listMyDeskLeaves, remindMyDeskLeave, updateMyDeskLeave } from '../mydeskService';

const LEAVE_TYPES = [
    { value: 'casual', label: 'Casual Leave' },
    { value: 'sick', label: 'Sick Leave' },
    { value: 'earned', label: 'Earned Leave' },
    { value: 'parents_birthday', label: "Parent's Birthday" },
    { value: 'comp_off', label: 'Comp-Off' },
    { value: 'unpaid', label: 'Unpaid Leave' },
    { value: 'wfh', label: 'WFH' },
];

const LEAVE_LABEL = Object.fromEntries(LEAVE_TYPES.map((t) => [t.value, t.label]));

const STATUS_ICON = {
    approved: <CheckCircleOutlineIcon fontSize="small" sx={{ color: 'success.main' }} />,
    pending: <HourglassEmptyIcon fontSize="small" sx={{ color: 'warning.main' }} />,
    rejected: <CancelIcon fontSize="small" sx={{ color: 'error.main' }} />,
};

const STATUS_COLOR = { approved: 'success', pending: 'warning', rejected: 'error' };

function localDate(d) {
    if (!d) return '—';
    const dt = new Date(`${d}T00:00:00`);
    return dt.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function dayCount(start, end) {
    if (!start || !end) return 0;
    const s = new Date(`${start}T00:00:00`);
    const e = new Date(`${end}T00:00:00`);
    return Math.max(1, Math.round((e - s) / 86400000) + 1);
}

const EMPTY_FORM = { type: 'casual', from: '', to: '', reason: '', document: null };

export default function LeaveSection() {
    const [form, setForm] = useState(EMPTY_FORM);
    const [editingId, setEditingId] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState('');
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [remindingId, setRemindingId] = useState(null);
    const [rejectDialog, setRejectDialog] = useState(null); // entry to view reject reason
    const docInputRef = useRef(null);

    const loadLeaves = useCallback(async () => {
        setLoading(true);
        try {
            const data = await listMyDeskLeaves();
            setHistory(Array.isArray(data) ? data : []);
        } catch { /* ignore */ } finally { setLoading(false); }
    }, []);

    useEffect(() => {
        loadLeaves();
        const id = setInterval(loadLeaves, 30000);
        const onFocus = () => loadLeaves();
        window.addEventListener('focus', onFocus);
        return () => { clearInterval(id); window.removeEventListener('focus', onFocus); };
    }, [loadLeaves]);

    const handleSubmit = async () => {
        setFormError('');
        if (!form.from || !form.to) { setFormError('Please select a date range.'); return; }
        if (form.to < form.from) { setFormError('End date cannot be before start date.'); return; }
        if (!form.reason.trim()) { setFormError('Please provide a reason.'); return; }

        const fd = new FormData();
        fd.append('leave_type', form.type);
        fd.append('start_date', form.from);
        fd.append('end_date', form.to);
        fd.append('reason', form.reason);
        if (form.document) fd.append('document', form.document);

        setSubmitting(true);
        try {
            if (editingId) {
                await updateMyDeskLeave(editingId, fd);
            } else {
                await createMyDeskLeave(fd);
            }
            await loadLeaves();
            setForm(EMPTY_FORM);
            setEditingId(null);
        } catch { /* notification handled by service */ } finally { setSubmitting(false); }
    };

    const startEdit = (entry) => {
        if (entry.status !== 'pending') return;
        setEditingId(entry.id);
        setForm({ type: entry.leave_type || 'casual', from: entry.start_date || '', to: entry.end_date || '', reason: entry.reason || '', document: null });
        setFormError('');
    };

    const cancelEdit = () => { setEditingId(null); setForm(EMPTY_FORM); setFormError(''); };

    const handleDelete = async (id) => {
        try { await deleteMyDeskLeave(id); await loadLeaves(); if (editingId === id) cancelEdit(); } catch { /* handled */ }
    };

    const handleRemind = async (entry) => {
        if (remindingId) return;
        setRemindingId(entry.id);
        try { await remindMyDeskLeave(entry.id); await loadLeaves(); } catch { /* handled */ } finally { setRemindingId(null); }
    };

    const docs = form.type === 'sick' || form.type === 'comp_off';

    return (
        <Stack spacing={2}>
            {/* ── Application Form ── */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                    <Typography variant="subtitle1" fontWeight={700}>
                        {editingId ? 'Edit Leave Request' : 'Apply for Leave'}
                    </Typography>
                    <Chip label="Goes to HR" size="small" color="primary" sx={{ fontSize: 10, height: 20 }} />
                </Stack>

                {formError && <Alert severity="error" sx={{ mb: 1.5, py: 0.5 }}>{formError}</Alert>}

                <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
                    <FormControl size="small" sx={{ minWidth: 170 }}>
                        <InputLabel>Leave Type</InputLabel>
                        <Select label="Leave Type" value={form.type} onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}>
                            {LEAVE_TYPES.map((t) => <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>)}
                        </Select>
                    </FormControl>
                    <TextField type="date" size="small" label="From" InputLabelProps={{ shrink: true }}
                        value={form.from} onChange={(e) => setForm((p) => ({ ...p, from: e.target.value }))} sx={{ minWidth: 155 }} />
                    <TextField type="date" size="small" label="To" InputLabelProps={{ shrink: true }}
                        value={form.to} onChange={(e) => setForm((p) => ({ ...p, to: e.target.value }))} sx={{ minWidth: 155 }} />
                    {form.from && form.to && form.to >= form.from && (
                        <Chip label={`${dayCount(form.from, form.to)} day${dayCount(form.from, form.to) !== 1 ? 's' : ''}`}
                            size="small" color="info" variant="outlined" />
                    )}
                    <TextField size="small" label="Reason *" value={form.reason}
                        onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
                        sx={{ minWidth: 220, flex: 1 }} />
                    {/* Document upload — shown for sick/comp-off */}
                    {docs && (
                        <>
                            <input ref={docInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" hidden
                                onChange={(e) => setForm((p) => ({ ...p, document: e.target.files[0] || null }))} />
                            <Tooltip title="Attach document (optional for sick/comp-off)">
                                <Button size="small" variant="outlined" startIcon={<AttachFileIcon />}
                                    onClick={() => docInputRef.current?.click()}
                                    color={form.document ? 'success' : 'inherit'}
                                    sx={{ flexShrink: 0 }}>
                                    {form.document ? form.document.name.slice(0, 16) + '…' : 'Attach Doc'}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                    <Button variant="contained" onClick={handleSubmit} disabled={submitting}
                        startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
                        sx={{ flexShrink: 0 }}>
                        {submitting ? 'Submitting…' : editingId ? 'Update' : 'Submit to HR'}
                    </Button>
                    {editingId && (
                        <Button variant="text" onClick={cancelEdit} sx={{ flexShrink: 0 }}>Cancel</Button>
                    )}
                </Stack>

                <Alert severity="info" sx={{ mt: 1.5, py: 0.5, fontSize: 12 }}>
                    Your leave request goes directly to <strong>HR</strong> for review. Once approved, your attendance will be updated automatically.
                </Alert>
            </Paper>

            {/* ── My Applied Requests ── */}
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight={700}>My Leave History</Typography>
                </Box>
                {loading && <LinearProgress />}
                <Stack spacing={0} divider={<Divider />}>
                    {history.filter((e) => e.is_requester).map((entry) => (
                        <Box key={entry.id} sx={{ px: 2, py: 1.5,
                            bgcolor: entry.status === 'approved' ? 'rgba(34,197,94,0.04)' :
                                entry.status === 'rejected' ? 'rgba(239,68,68,0.04)' : 'transparent' }}>
                            <Stack direction="row" spacing={1.5} alignItems="flex-start" flexWrap="wrap">
                                <Box sx={{ flex: 1, minWidth: 200 }}>
                                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                                        <Typography variant="body2" fontWeight={700}>
                                            {LEAVE_LABEL[entry.leave_type] || entry.leave_type?.toUpperCase()}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {localDate(entry.start_date)} → {localDate(entry.end_date)}
                                            {' '}({dayCount(entry.start_date, entry.end_date)} day{dayCount(entry.start_date, entry.end_date) !== 1 ? 's' : ''})
                                        </Typography>
                                        <Chip
                                            icon={STATUS_ICON[entry.status]}
                                            label={entry.status.charAt(0).toUpperCase() + entry.status.slice(1)}
                                            size="small"
                                            color={STATUS_COLOR[entry.status] || 'default'}
                                            variant="outlined"
                                        />
                                    </Stack>
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                                        {entry.reason || '—'}
                                    </Typography>
                                    {entry.status === 'rejected' && entry.decline_reason && (
                                        <Alert severity="error" sx={{ mt: 0.5, py: 0.25, fontSize: 11 }}>
                                            HR Rejection Reason: {entry.decline_reason}
                                        </Alert>
                                    )}
                                    {entry.status === 'approved' && entry.approved_by_name && (
                                        <Typography variant="caption" color="success.main">
                                            ✓ Approved by {entry.approved_by_name}
                                        </Typography>
                                    )}
                                    {entry.document_url && (
                                        <Button size="small" href={entry.document_url} target="_blank"
                                            startIcon={<OpenInNewIcon fontSize="small" />} sx={{ mt: 0.5, fontSize: 11 }}>
                                            View Document
                                        </Button>
                                    )}
                                </Box>
                                {entry.status === 'pending' && (
                                    <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
                                        <Tooltip title="Remind HR">
                                            <span>
                                                <IconButton size="small" color="primary" disabled={remindingId === entry.id}
                                                    onClick={() => handleRemind(entry)}>
                                                    <NotificationsActiveIcon fontSize="small" />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                        <Tooltip title="Edit">
                                            <IconButton size="small" color="primary" onClick={() => startEdit(entry)}>
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Delete">
                                            <IconButton size="small" color="error" onClick={() => handleDelete(entry.id)}>
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Stack>
                                )}
                            </Stack>
                        </Box>
                    ))}
                    {!loading && history.filter((e) => e.is_requester).length === 0 && (
                        <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
                            <Typography variant="body2" color="text.secondary">No leave requests yet. Apply above.</Typography>
                        </Box>
                    )}
                </Stack>
            </Paper>

            {/* Reject reason dialog */}
            <Dialog open={Boolean(rejectDialog)} onClose={() => setRejectDialog(null)} maxWidth="sm" fullWidth>
                <DialogTitle>Rejection Reason</DialogTitle>
                <DialogContent>
                    <Typography variant="body2">{rejectDialog?.decline_reason || 'No reason provided.'}</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRejectDialog(null)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}
