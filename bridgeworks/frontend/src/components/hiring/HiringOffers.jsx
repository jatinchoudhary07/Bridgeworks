import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Button, CircularProgress, Chip,
    Dialog, DialogTitle, DialogContent, DialogActions,
    Grid, TextField, FormControl, InputLabel, Select, MenuItem, Divider,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { fetchOffers, createOffer, updateOffer, fetchApplications } from './hiringApi';

const STATUS_CONFIG = {
    pending: { color: 'warning', label: 'Pending' },
    sent: { color: 'info', label: 'Sent' },
    accepted: { color: 'success', label: 'Accepted' },
    rejected: { color: 'error', label: 'Rejected' },
    expired: { color: 'default', label: 'Expired' },
    revoked: { color: 'default', label: 'Revoked' },
};

export default function HiringOffers() {
    const [offers, setOffers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [createOpen, setCreateOpen] = useState(false);
    const [applications, setApplications] = useState([]);
    const [filterStatus, setFilterStatus] = useState('');
    const [form, setForm] = useState({
        application_id: '', offered_salary: '', currency: 'INR',
        joining_date: '', offer_letter_url: '', valid_until: '', notes: '',
    });

    const load = async () => {
        setLoading(true);
        try {
            const params = filterStatus ? { status: filterStatus } : {};
            const [offerData, appData] = await Promise.all([fetchOffers(params), fetchApplications()]);
            setOffers(Array.isArray(offerData) ? offerData : []);
            setApplications(Array.isArray(appData) ? appData : []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [filterStatus]);

    const handleCreate = async () => {
        try {
            const offer = await createOffer(form);
            setOffers(prev => [offer, ...prev]);
            setCreateOpen(false);
            setForm({ application_id: '', offered_salary: '', currency: 'INR', joining_date: '', offer_letter_url: '', valid_until: '', notes: '' });
        } catch (e) { console.error(e); }
    };

    const handleStatusUpdate = async (offerId, newStatus) => {
        try {
            const updated = await updateOffer(offerId, { status: newStatus });
            setOffers(prev => prev.map(o => o.id === offerId ? updated : o));
        } catch (e) { console.error(e); }
    };

    const stats = {
        total: offers.length,
        pending: offers.filter(o => o.status === 'pending').length,
        accepted: offers.filter(o => o.status === 'accepted').length,
        rejected: offers.filter(o => o.status === 'rejected').length,
    };

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>

                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)} sx={{ borderRadius: 2 }}>
                    Create Offer
                </Button>
            </Box>

            {/* Stats */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                {[
                    { label: 'Total Offers', value: stats.total, color: '#6366f1' },
                    { label: 'Pending', value: stats.pending, color: '#f59e0b' },
                    { label: 'Accepted', value: stats.accepted, color: '#22c55e' },
                    { label: 'Rejected', value: stats.rejected, color: '#ef4444' },
                ].map(s => (
                    <Grid item xs={6} md={3} key={s.label}>
                        <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 2, borderLeft: `4px solid ${s.color}`, border: '1px solid', borderColor: 'divider' }}>
                            <Typography variant="h4" fontWeight={700} color={s.color}>{s.value}</Typography>
                            <Typography variant="body2" color="text.secondary">{s.label}</Typography>
                        </Box>
                    </Grid>
                ))}
            </Grid>

            <FormControl size="small" sx={{ width: 200, mb: 3 }}>
                <InputLabel>Status Filter</InputLabel>
                <Select label="Status Filter" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                    <MenuItem value="">All</MenuItem>
                    {Object.keys(STATUS_CONFIG).map(s => <MenuItem key={s} value={s}>{STATUS_CONFIG[s].label}</MenuItem>)}
                </Select>
            </FormControl>

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
            ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {offers.map(offer => {
                        const cfg = STATUS_CONFIG[offer.status] || { color: 'default', label: offer.status };
                        return (
                            <Box key={offer.id} sx={{ p: 2.5, bgcolor: 'background.paper', borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <Box>
                                        <Typography fontWeight={700} variant="h6">{offer.candidate_name}</Typography>
                                        <Typography variant="body2" color="text.secondary">{offer.job_title}</Typography>
                                    </Box>
                                    <Chip label={cfg.label} color={cfg.color} />
                                </Box>
                                <Divider sx={{ my: 1.5 }} />
                                <Grid container spacing={2}>
                                    <Grid item xs={6} md={3}>
                                        <Typography variant="caption" color="text.secondary">Offered Salary</Typography>
                                        <Typography fontWeight={600}>{offer.currency} {Number(offer.offered_salary).toLocaleString()}</Typography>
                                    </Grid>
                                    <Grid item xs={6} md={3}>
                                        <Typography variant="caption" color="text.secondary">Joining Date</Typography>
                                        <Typography>{offer.joining_date ? new Date(offer.joining_date).toLocaleDateString() : '—'}</Typography>
                                    </Grid>
                                    <Grid item xs={6} md={3}>
                                        <Typography variant="caption" color="text.secondary">Valid Until</Typography>
                                        <Typography>{offer.valid_until ? new Date(offer.valid_until).toLocaleDateString() : '—'}</Typography>
                                    </Grid>
                                    <Grid item xs={6} md={3}>
                                        <Typography variant="caption" color="text.secondary">Created</Typography>
                                        <Typography>{new Date(offer.created_at).toLocaleDateString()}</Typography>
                                    </Grid>
                                </Grid>
                                {offer.offer_letter_url && (
                                    <Box sx={{ mt: 1 }}>
                                        <Button size="small" variant="outlined" component="a" href={offer.offer_letter_url} target="_blank">
                                            View Offer Letter
                                        </Button>
                                    </Box>
                                )}
                                {offer.status === 'pending' && (
                                    <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                                        <Button
                                            size="small" variant="contained" color="success" startIcon={<CheckCircleIcon />}
                                            onClick={() => handleStatusUpdate(offer.id, 'accepted')}
                                        >
                                            Mark Accepted
                                        </Button>
                                        <Button
                                            size="small" variant="outlined" color="error" startIcon={<CancelIcon />}
                                            onClick={() => handleStatusUpdate(offer.id, 'rejected')}
                                        >
                                            Mark Rejected
                                        </Button>
                                        <Button
                                            size="small" variant="outlined"
                                            onClick={() => handleStatusUpdate(offer.id, 'sent')}
                                        >
                                            Mark Sent
                                        </Button>
                                    </Box>
                                )}
                            </Box>
                        );
                    })}
                    {offers.length === 0 && (
                        <Box sx={{ textAlign: 'center', py: 8 }}>
                            <LocalOfferIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography color="text.secondary">No offers created yet.</Typography>
                        </Box>
                    )}
                </Box>
            )}

            {/* Create Offer Dialog */}
            <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Create Job Offer</DialogTitle>
                <DialogContent dividers>
                    <Grid container spacing={2}>
                        <Grid item xs={12}>
                            <FormControl fullWidth>
                                <InputLabel>Application *</InputLabel>
                                <Select label="Application *" value={form.application_id} onChange={e => setForm(f => ({ ...f, application_id: e.target.value }))}>
                                    {applications.map(a => (
                                        <MenuItem key={a.id} value={a.id}>
                                            {a.candidate_detail?.name} — {a.job_detail?.title || `Job #${a.job}`}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={8}><TextField fullWidth type="number" label="Offered Salary *" value={form.offered_salary} onChange={e => setForm(f => ({ ...f, offered_salary: e.target.value }))} /></Grid>
                        <Grid item xs={4}><TextField fullWidth label="Currency" value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth type="date" label="Joining Date" InputLabelProps={{ shrink: true }} value={form.joining_date} onChange={e => setForm(f => ({ ...f, joining_date: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth type="date" label="Valid Until" InputLabelProps={{ shrink: true }} value={form.valid_until} onChange={e => setForm(f => ({ ...f, valid_until: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth label="Offer Letter URL" value={form.offer_letter_url} onChange={e => setForm(f => ({ ...f, offer_letter_url: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Notes" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleCreate} disabled={!form.application_id || !form.offered_salary}>Create Offer</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
