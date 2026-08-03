import React, { useState, useEffect, useRef } from 'react';
import {
    Box, Typography, Avatar, Chip, CircularProgress, TextField,
    Button, IconButton, Tooltip, Dialog, DialogTitle, DialogContent,
    DialogActions, Grid, Divider, Link, Tabs, Tab, Badge,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import LinkedInIcon from '@mui/icons-material/LinkedIn';
import GitHubIcon from '@mui/icons-material/GitHub';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import AddIcon from '@mui/icons-material/Add';
import NoteAddIcon from '@mui/icons-material/NoteAdd';
import {
    fetchCandidates, fetchCandidate, createCandidate, updateCandidate,
    fetchCandidateNotes, addCandidateNote, fetchApplications,
} from './hiringApi';

const SOURCE_COLORS = { manual: 'default', google_form: 'primary', linkedin: 'info', referral: 'success', portal: 'warning' };

export default function HiringCandidates({ onSelectCandidate }) {
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState(null);
    const [detailOpen, setDetailOpen] = useState(false);
    const [notes, setNotes] = useState([]);
    const [applications, setApplications] = useState([]);
    const [noteText, setNoteText] = useState('');
    const [addingNote, setAddingNote] = useState(false);
    const [activeTab, setActiveTab] = useState(0);
    const [createOpen, setCreateOpen] = useState(false);
    const [form, setForm] = useState({ name: '', email: '', phone: '', resume_url: '', linkedin_url: '', github_url: '', skills: [], current_company: '', total_experience_years: '' });
    const [skillInput, setSkillInput] = useState('');

    const load = async () => {
        setLoading(true);
        try {
            const params = search ? { search } : {};
            const data = await fetchCandidates(params);
            setCandidates(Array.isArray(data) ? data : []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const openDetail = async (candidate) => {
        setSelected(candidate);
        setDetailOpen(true);
        setActiveTab(0);
        const [n, a] = await Promise.all([
            fetchCandidateNotes(candidate.id),
            fetchApplications({ candidate_id: candidate.id }),
        ]);
        setNotes(Array.isArray(n) ? n : []);
        setApplications(Array.isArray(a) ? a : []);
    };

    const handleAddNote = async () => {
        if (!noteText.trim()) return;
        setAddingNote(true);
        try {
            const note = await addCandidateNote(selected.id, { content: noteText });
            setNotes(prev => [note, ...prev]);
            setNoteText('');
        } catch (e) { console.error(e); }
        finally { setAddingNote(false); }
    };

    const handleCreate = async () => {
        try {
            const c = await createCandidate(form);
            setCandidates(prev => [c, ...prev]);
            setCreateOpen(false);
            setForm({ name: '', email: '', phone: '', resume_url: '', linkedin_url: '', github_url: '', skills: [], current_company: '', total_experience_years: '' });
        } catch (e) { console.error(e); }
    };

    const addSkill = () => {
        if (skillInput.trim()) {
            setForm(f => ({ ...f, skills: [...(f.skills || []), skillInput.trim()] }));
            setSkillInput('');
        }
    };

    const getInitials = (name) => name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) || '?';

    return (
        <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Box>
                    <Typography variant="h5" fontWeight={700}>Candidates</Typography>
                    <Typography variant="body2" color="text.secondary">{candidates.length} total candidates</Typography>
                </Box>
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)} sx={{ borderRadius: 2 }}>
                    Add Candidate
                </Button>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                <TextField
                    size="small" placeholder="Search by name, email, company…"
                    value={search} onChange={e => setSearch(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && load()}
                    sx={{ width: 340 }}
                />
                <Button variant="outlined" size="small" onClick={load}>Search</Button>
            </Box>

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
            ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {candidates.map(c => (
                        <Box
                            key={c.id}
                            onClick={() => openDetail(c)}
                            sx={{
                                display: 'flex', alignItems: 'center', gap: 2, p: 2,
                                bgcolor: 'background.paper', borderRadius: 2, border: '1px solid',
                                borderColor: 'divider', cursor: 'pointer',
                                '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' },
                            }}
                        >
                            <Avatar sx={{ bgcolor: 'primary.main', width: 44, height: 44 }}>{getInitials(c.name)}</Avatar>
                            <Box sx={{ flex: 1 }}>
                                <Typography fontWeight={600}>{c.name}</Typography>
                                <Typography variant="body2" color="text.secondary">{c.email}</Typography>
                                {c.current_company && (
                                    <Typography variant="caption" color="text.secondary">{c.current_company}</Typography>
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5 }}>
                                <Chip label={c.source} size="small" color={SOURCE_COLORS[c.source] || 'default'} />
                                {c.total_experience_years && (
                                    <Typography variant="caption" color="text.secondary">{c.total_experience_years} yrs exp</Typography>
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', gap: 0.5 }}>
                                {(c.skills || []).slice(0, 3).map(skill => (
                                    <Chip key={skill} label={skill} size="small" variant="outlined" />
                                ))}
                                {(c.skills || []).length > 3 && (
                                    <Chip label={`+${c.skills.length - 3}`} size="small" variant="outlined" />
                                )}
                            </Box>
                            <Badge badgeContent={c.applications_count} color="primary">
                                <Chip label="apps" size="small" />
                            </Badge>
                        </Box>
                    ))}
                    {candidates.length === 0 && (
                        <Box sx={{ textAlign: 'center', py: 8 }}>
                            <PersonIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography color="text.secondary">No candidates found.</Typography>
                        </Box>
                    )}
                </Box>
            )}

            {/* Candidate Detail Dialog */}
            <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="md" fullWidth>
                {selected && (
                    <>
                        <DialogTitle>
                            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                <Avatar sx={{ bgcolor: 'primary.main', width: 52, height: 52 }}>{getInitials(selected.name)}</Avatar>
                                <Box>
                                    <Typography variant="h6" fontWeight={700}>{selected.name}</Typography>
                                    <Typography variant="body2" color="text.secondary">{selected.email}</Typography>
                                </Box>
                                <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
                                    {selected.linkedin_url && (
                                        <IconButton component="a" href={selected.linkedin_url} target="_blank" size="small">
                                            <LinkedInIcon color="primary" />
                                        </IconButton>
                                    )}
                                    {selected.github_url && (
                                        <IconButton component="a" href={selected.github_url} target="_blank" size="small">
                                            <GitHubIcon />
                                        </IconButton>
                                    )}
                                    {selected.resume_url && (
                                        <Button
                                            size="small" variant="outlined" endIcon={<OpenInNewIcon />}
                                            component="a" href={selected.resume_url} target="_blank"
                                        >
                                            Resume
                                        </Button>
                                    )}
                                </Box>
                            </Box>
                        </DialogTitle>
                        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ px: 2 }}>
                            <Tab label="Profile" />
                            <Tab label={`Applications (${applications.length})`} />
                            <Tab label={`Notes (${notes.length})`} />
                        </Tabs>
                        <DialogContent dividers>
                            {activeTab === 0 && (
                                <Grid container spacing={2}>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Phone</Typography><Typography>{selected.phone || '—'}</Typography></Grid>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Current Company</Typography><Typography>{selected.current_company || '—'}</Typography></Grid>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Experience</Typography><Typography>{selected.total_experience_years ? `${selected.total_experience_years} years` : '—'}</Typography></Grid>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Expected Salary</Typography><Typography>{selected.expected_salary ? `₹${Number(selected.expected_salary).toLocaleString()}` : '—'}</Typography></Grid>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Notice Period</Typography><Typography>{selected.notice_period_days ? `${selected.notice_period_days} days` : '—'}</Typography></Grid>
                                    <Grid item xs={6}><Typography variant="caption" color="text.secondary">Source</Typography><Typography><Chip label={selected.source} size="small" /></Typography></Grid>
                                    <Grid item xs={12}>
                                        <Typography variant="caption" color="text.secondary">Skills</Typography>
                                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                                            {(selected.skills || []).map(s => <Chip key={s} label={s} size="small" variant="outlined" />)}
                                        </Box>
                                    </Grid>
                                </Grid>
                            )}
                            {activeTab === 1 && (
                                <Box>
                                    {applications.length === 0
                                        ? <Typography color="text.secondary">No applications yet.</Typography>
                                        : applications.map(app => (
                                            <Box key={app.id} sx={{ py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                                                <Typography fontWeight={600}>{app.job_detail?.title || `Job #${app.job}`}</Typography>
                                                <Typography variant="body2" color="text.secondary">{app.job_detail?.department}</Typography>
                                                {app.current_stage_detail && (
                                                    <Chip label={app.current_stage_detail.name} size="small" sx={{ mt: 0.5, bgcolor: app.current_stage_detail.color, color: '#fff' }} />
                                                )}
                                            </Box>
                                        ))
                                    }
                                </Box>
                            )}
                            {activeTab === 2 && (
                                <Box>
                                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                                        <TextField
                                            fullWidth multiline rows={2} size="small"
                                            placeholder="Add a note…" value={noteText}
                                            onChange={e => setNoteText(e.target.value)}
                                        />
                                        <Button variant="contained" size="small" onClick={handleAddNote} disabled={addingNote}>
                                            Add
                                        </Button>
                                    </Box>
                                    {notes.map(note => (
                                        <Box key={note.id} sx={{ mb: 1.5, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                                            <Typography variant="body2">{note.content}</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {note.author_detail?.first_name} {note.author_detail?.last_name} · {new Date(note.created_at).toLocaleDateString()}
                                            </Typography>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </DialogContent>
                        <DialogActions>
                            <Button onClick={() => setDetailOpen(false)}>Close</Button>
                        </DialogActions>
                    </>
                )}
            </Dialog>

            {/* Create Candidate Dialog */}
            <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Add New Candidate</DialogTitle>
                <DialogContent dividers>
                    <Grid container spacing={2}>
                        <Grid item xs={12}><TextField fullWidth label="Full Name *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></Grid>
                        <Grid item xs={12}><TextField fullWidth label="Email *" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="Phone" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="Current Company" value={form.current_company} onChange={e => setForm(f => ({ ...f, current_company: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="Experience (years)" type="number" value={form.total_experience_years} onChange={e => setForm(f => ({ ...f, total_experience_years: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="Resume URL" value={form.resume_url} onChange={e => setForm(f => ({ ...f, resume_url: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="LinkedIn URL" value={form.linkedin_url} onChange={e => setForm(f => ({ ...f, linkedin_url: e.target.value }))} /></Grid>
                        <Grid item xs={6}><TextField fullWidth label="GitHub URL" value={form.github_url} onChange={e => setForm(f => ({ ...f, github_url: e.target.value }))} /></Grid>
                        <Grid item xs={12}>
                            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <TextField size="small" label="Add Skill" value={skillInput} onChange={e => setSkillInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && addSkill()} />
                                <Button variant="outlined" size="small" onClick={addSkill}>Add</Button>
                            </Box>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {(form.skills || []).map(s => <Chip key={s} label={s} size="small" onDelete={() => setForm(f => ({ ...f, skills: f.skills.filter(x => x !== s) }))} />)}
                            </Box>
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleCreate} disabled={!form.name || !form.email}>Create</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
