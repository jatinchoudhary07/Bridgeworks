import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Button, CircularProgress, Chip, Avatar,
    Dialog, DialogTitle, DialogContent, DialogActions, Grid, TextField,
    FormControl, InputLabel, Select, MenuItem, Divider, Rating, IconButton,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VideocamIcon from '@mui/icons-material/Videocam';
import EventIcon from '@mui/icons-material/Event';
import FeedbackIcon from '@mui/icons-material/Feedback';
import EditIcon from '@mui/icons-material/Edit';
import {
    fetchInterviews, createInterview, rescheduleInterview,
    fetchInterviewFeedback, submitInterviewFeedback, fetchApplications,
} from './hiringApi';

const STATUS_COLORS = { scheduled: 'primary', completed: 'success', cancelled: 'error', rescheduled: 'warning', no_show: 'default' };
const MODE_ICONS = { google_meet: '🎥', zoom: '📹', phone: '📞', in_person: '🏢', other: '📋' };

export default function HiringInterviews() {
    const [interviews, setInterviews] = useState([]);
    const [loading, setLoading] = useState(true);
    const [scheduleOpen, setScheduleOpen] = useState(false);
    const [feedbackOpen, setFeedbackOpen] = useState(null);
    const [rescheduleOpen, setRescheduleOpen] = useState(null);
    const [applications, setApplications] = useState([]);
    const [feedbackData, setFeedbackData] = useState([]);
    const [form, setForm] = useState({
        application_id: '', title: 'Interview', scheduled_at: '',
        duration_minutes: 60, mode: 'google_meet', meeting_link: '', notes: '',
    });
    const [feedbackForm, setFeedbackForm] = useState({
        overall_rating: 3, strengths: '', weaknesses: '', notes: '', recommendation: 'neutral',
    });
    const [rescheduleForm, setRescheduleForm] = useState({ scheduled_at: '', notes: '' });
    const [filterStatus, setFilterStatus] = useState('');

    const load = async () => {
        setLoading(true);
        try {
            const params = filterStatus ? { status: filterStatus } : {};
            const [data, apps] = await Promise.all([fetchInterviews(params), fetchApplications()]);
            setInterviews(Array.isArray(data) ? data : []);
            setApplications(Array.isArray(apps) ? apps : []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [filterStatus]);

    const handleCreate = async () => {
        try {
            const interview = await createInterview(form);
            setInterviews(prev => [interview, ...prev]);
            setScheduleOpen(false);
            setForm({ application_id: '', title: 'Interview', scheduled_at: '', duration_minutes: 60, mode: 'google_meet', meeting_link: '', notes: '' });
        } catch (e) { console.error(e); }
    };

    const openFeedback = async (interview) => {
        setFeedbackOpen(interview);
        const data = await fetchInterviewFeedback(interview.id);
        setFeedbackData(Array.isArray(data) ? data : []);
    };

    const handleSubmitFeedback = async () => {
        try {
            await submitInterviewFeedback(feedbackOpen.id, feedbackForm);
            setFeedbackOpen(null);
            setFeedbackForm({ overall_rating: 3, strengths: '', weaknesses: '', notes: '', recommendation: 'neutral' });
        } catch (e) { console.error(e); }
    };

    const handleReschedule = async () => {
        try {
            const updated = await rescheduleInterview(rescheduleOpen.id, rescheduleForm);
            setInterviews(prev => prev.map(i => i.id === rescheduleOpen.id ? updated : i));
            setRescheduleOpen(null);
        } catch (e) { console.error(e); }
    };

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setScheduleOpen(true)} sx={{ borderRadius: 2 }}>
                    Schedule Interview
                </Button>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                <FormControl size="small" sx={{ width: 200 }}>
                    <InputLabel>Status Filter</InputLabel>
                    <Select label="Status Filter" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="scheduled">Scheduled</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="cancelled">Cancelled</MenuItem>
                        <MenuItem value="rescheduled">Rescheduled</MenuItem>
                    </Select>
                </FormControl>
            </Box>

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
            ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {interviews.map(interview => (
                        <Box
                            key={interview.id}
                            sx={{
                                p: 2.5, bgcolor: 'background.paper', borderRadius: 2,
                                border: '1px solid', borderColor: 'divider',
                            }}
                        >
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                    <Box sx={{ fontSize: 28 }}>{MODE_ICONS[interview.mode] || '📋'}</Box>
                                    <Box>
                                        <Typography fontWeight={600}>{interview.title}</Typography>
                                        <Typography variant="body2" color="primary">{interview.candidate_name}</Typography>
                                        <Typography variant="caption" color="text.secondary">{interview.job_title}</Typography>
                                    </Box>
                                </Box>
                                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                    <Chip label={interview.status} color={STATUS_COLORS[interview.status] || 'default'} size="small" />
                                    <IconButton size="small" onClick={() => setRescheduleOpen(interview)}>
                                        <EditIcon fontSize="small" />
                                    </IconButton>
                                    <Button
                                        size="small" startIcon={<FeedbackIcon />} variant="outlined"
                                        onClick={() => openFeedback(interview)}
                                    >
                                        Feedback
                                    </Button>
                                </Box>
                            </Box>
                            <Divider sx={{ my: 1.5 }} />
                            <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <EventIcon fontSize="small" color="action" />
                                    <Typography variant="body2">
                                        {new Date(interview.scheduled_at).toLocaleString()} · {interview.duration_minutes} min
                                    </Typography>
                                </Box>
                                {interview.meeting_link && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <VideocamIcon fontSize="small" color="action" />
                                        <Typography
                                            variant="body2" component="a" href={interview.meeting_link} target="_blank"
                                            sx={{ color: 'primary.main', textDecoration: 'none' }}
                                        >
                                            Join Meeting
                                        </Typography>
                                    </Box>
                                )}
                                {(interview.interviewers_detail || []).length > 0 && (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <Typography variant="caption" color="text.secondary">Interviewers:</Typography>
                                        {interview.interviewers_detail.map(i => (
                                            <Chip key={i.id} label={`${i.first_name} ${i.last_name}`} size="small" variant="outlined" />
                                        ))}
                                    </Box>
                                )}
                            </Box>
                        </Box>
                    ))}
                    {interviews.length === 0 && (
                        <Box sx={{ textAlign: 'center', py: 8 }}>
                            <EventIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography color="text.secondary">No interviews scheduled yet.</Typography>
                        </Box>
                    )}
                </Box>
            )}

            {/* Schedule Interview Dialog */}
            <Dialog open={scheduleOpen} onClose={() => setScheduleOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Schedule Interview</DialogTitle>
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
                        <Grid item xs={12}><TextField fullWidth label="Interview Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} /></Grid>
                        <Grid item xs={8}><TextField fullWidth type="datetime-local" label="Date & Time" InputLabelProps={{ shrink: true }} value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} /></Grid>
                        <Grid item xs={4}><TextField fullWidth type="number" label="Duration (min)" value={form.duration_minutes} onChange={e => setForm(f => ({ ...f, duration_minutes: e.target.value }))} /></Grid>
                        <Grid item xs={6}>
                            <FormControl fullWidth>
                                <InputLabel>Mode</InputLabel>
                                <Select label="Mode" value={form.mode} onChange={e => setForm(f => ({ ...f, mode: e.target.value }))}>
                                    <MenuItem value="google_meet">Google Meet</MenuItem>
                                    <MenuItem value="zoom">Zoom</MenuItem>
                                    <MenuItem value="phone">Phone</MenuItem>
                                    <MenuItem value="in_person">In Person</MenuItem>
                                    <MenuItem value="other">Other</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={6}><TextField fullWidth label="Meeting Link" value={form.meeting_link} onChange={e => setForm(f => ({ ...f, meeting_link: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Notes" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setScheduleOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleCreate} disabled={!form.application_id || !form.scheduled_at}>Schedule</Button>
                </DialogActions>
            </Dialog>

            {/* Feedback Dialog */}
            <Dialog open={!!feedbackOpen} onClose={() => setFeedbackOpen(null)} maxWidth="sm" fullWidth>
                <DialogTitle>Interview Feedback</DialogTitle>
                <DialogContent dividers>
                    {feedbackData.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>Existing Feedback</Typography>
                            {feedbackData.map(fb => (
                                <Box key={fb.id} sx={{ p: 1.5, mb: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="body2" fontWeight={600}>{fb.interviewer_detail?.first_name} {fb.interviewer_detail?.last_name}</Typography>
                                        <Chip label={fb.recommendation} size="small" color={fb.recommendation === 'strong_hire' || fb.recommendation === 'hire' ? 'success' : fb.recommendation === 'reject' ? 'error' : 'default'} />
                                    </Box>
                                    <Rating value={fb.overall_rating} readOnly size="small" />
                                    {fb.strengths && <Typography variant="caption" display="block">✅ {fb.strengths}</Typography>}
                                    {fb.weaknesses && <Typography variant="caption" display="block">⚠️ {fb.weaknesses}</Typography>}
                                </Box>
                            ))}
                            <Divider sx={{ my: 2 }} />
                        </Box>
                    )}
                    <Typography variant="subtitle2" gutterBottom>Submit Your Feedback</Typography>
                    <Grid container spacing={2}>
                        <Grid item xs={12}>
                            <Typography variant="body2" gutterBottom>Overall Rating</Typography>
                            <Rating value={feedbackForm.overall_rating} onChange={(_, v) => setFeedbackForm(f => ({ ...f, overall_rating: v }))} />
                        </Grid>
                        <Grid item xs={12}>
                            <FormControl fullWidth size="small">
                                <InputLabel>Recommendation</InputLabel>
                                <Select label="Recommendation" value={feedbackForm.recommendation} onChange={e => setFeedbackForm(f => ({ ...f, recommendation: e.target.value }))}>
                                    <MenuItem value="strong_hire">Strong Hire</MenuItem>
                                    <MenuItem value="hire">Hire</MenuItem>
                                    <MenuItem value="neutral">Neutral</MenuItem>
                                    <MenuItem value="reject">Reject</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Strengths" value={feedbackForm.strengths} onChange={e => setFeedbackForm(f => ({ ...f, strengths: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Weaknesses" value={feedbackForm.weaknesses} onChange={e => setFeedbackForm(f => ({ ...f, weaknesses: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Additional Notes" value={feedbackForm.notes} onChange={e => setFeedbackForm(f => ({ ...f, notes: e.target.value }))} /></Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setFeedbackOpen(null)}>Close</Button>
                    <Button variant="contained" onClick={handleSubmitFeedback}>Submit Feedback</Button>
                </DialogActions>
            </Dialog>

            {/* Reschedule Dialog */}
            <Dialog open={!!rescheduleOpen} onClose={() => setRescheduleOpen(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Reschedule Interview</DialogTitle>
                <DialogContent dividers>
                    <Grid container spacing={2}>
                        <Grid item xs={12}><TextField fullWidth type="datetime-local" label="New Date & Time" InputLabelProps={{ shrink: true }} value={rescheduleForm.scheduled_at} onChange={e => setRescheduleForm(f => ({ ...f, scheduled_at: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth multiline rows={2} label="Notes" value={rescheduleForm.notes} onChange={e => setRescheduleForm(f => ({ ...f, notes: e.target.value }))} /></Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRescheduleOpen(null)}>Cancel</Button>
                    <Button variant="contained" onClick={handleReschedule} disabled={!rescheduleForm.scheduled_at}>Reschedule</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
