import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Box, Typography, Button, Chip, TextField, Select, MenuItem,
    FormControl, InputLabel, Grid, Card, CardContent,
    CircularProgress, IconButton, Tooltip, Divider, Alert,
    Table, TableHead, TableRow, TableCell, TableBody, TableContainer,
    Paper, Avatar, Dialog, DialogTitle, DialogContent, DialogActions,
    InputAdornment, OutlinedInput, Stack, LinearProgress, ListSubheader,
    Popover, Checkbox, useTheme
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PublishIcon from '@mui/icons-material/Publish';
import CloseIcon from '@mui/icons-material/Close';
import WorkIcon from '@mui/icons-material/Work';
import PeopleIcon from '@mui/icons-material/People';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import LinkIcon from '@mui/icons-material/Link';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import BusinessCenterIcon from '@mui/icons-material/BusinessCenter';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import SearchIcon from '@mui/icons-material/Search';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import FilterListIcon from '@mui/icons-material/FilterList';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import {
    fetchJobs, createJob, updateJob, deleteJob,
    publishJob, closeJob, fetchJobApplications,
    syncJobGoogleForm, acceptApplication, rejectApplication, toggleSaveApplication,
    fetchDepartments, createDepartment, deleteDepartment,
} from './hiringApi';

// ─── Constants ───────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
    draft: { label: 'Draft', color: '#b45309', bg: '#fef3c7' },
    published: { label: 'Published', color: '#15803d', bg: '#dcfce7' },
    paused: { label: 'Paused', color: '#1d4ed8', bg: '#dbeafe' },
    closed: { label: 'Closed', color: '#6b7280', bg: '#f3f4f6' },
};

const EMPTY_FORM = {
    title: '', department: '', employment_type: 'full_time',
    experience_min: 0, experience_max: '', salary_min: '', salary_max: '',
    currency: 'INR', location: '', location_type: 'onsite',
    description: '', requirements: '', openings_count: 1,
    status: 'draft', posting_type: 'external',
    skills_required: [],
    google_form_url: '',
};

// ─── Small reusable pieces ───────────────────────────────────────────────────

function StatusChip({ status }) {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.draft;
    return (
        <Chip
            label={cfg.label}
            size="small"
            sx={{ fontWeight: 700, fontSize: '0.7rem', height: 24, bgcolor: cfg.bg, color: cfg.color, border: 'none' }}
        />
    );
}

function SectionLabel({ children }) {
    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.25 }}>
            <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: 1, color: 'text.disabled', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                {children}
            </Typography>
            <Divider sx={{ flex: 1 }} />
        </Box>
    );
}

function FieldLabel({ children, htmlFor, required }) {
    return (
        <Typography component="label" htmlFor={htmlFor} sx={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary', mb: 0.4 }}>
            {children}{required && <Box component="span" sx={{ color: 'error.main', ml: 0.3 }}>*</Box>}
        </Typography>
    );
}

// Reusable single-row flex grid
function SingleRowGrid({ children, spacing = 1.5 }) {
    return (
        <Box sx={{
            display: 'flex',
            gap: spacing,
            width: '100%',
            '& > *': { minWidth: 0, flex: 1 },
        }}>
            {children}
        </Box>
    );
}

// ─── Job Form Dialog ─────────────────────────────────────────────────────────

function JobFormDialog({ open, onClose, editJob, onSaved }) {
    const [form, setForm] = useState(EMPTY_FORM);
    const [saving, setSaving] = useState(false);
    const [skillInput, setSkillInput] = useState('');
    const [errors, setErrors] = useState({});
    const [attempted, setAttempted] = useState(false);
    const [departments, setDepartments] = useState([]);
    const [departmentsLoading, setDepartmentsLoading] = useState(false);
    const [departmentActionLoading, setDepartmentActionLoading] = useState(false);
    const [departmentInput, setDepartmentInput] = useState('');
    const [departmentError, setDepartmentError] = useState('');

    useEffect(() => {
        if (open) {
            setForm(editJob ? { ...EMPTY_FORM, ...editJob } : EMPTY_FORM);
            setErrors({});
            setAttempted(false);
            setSkillInput('');
            setDepartmentInput('');
            setDepartmentError('');
        }
    }, [open, editJob]);

    useEffect(() => {
        if (!open) return;

        let mounted = true;
        setDepartmentsLoading(true);
        fetchDepartments()
            .then((data) => {
                if (mounted) setDepartments(Array.isArray(data) ? data : []);
            })
            .catch((e) => {
                console.error(e);
                if (mounted) setDepartmentError('Unable to load departments.');
            })
            .finally(() => {
                if (mounted) setDepartmentsLoading(false);
            });

        return () => { mounted = false; };
    }, [open]);

    const departmentOptions = useMemo(() => {
        const selectedDepartment = (form.department || '').trim();
        const hasSelected = departments.some((dept) => dept.name === selectedDepartment);
        if (!selectedDepartment || hasSelected) return departments;
        return [{ id: `current-${selectedDepartment}`, name: selectedDepartment, isCurrentOnly: true }, ...departments];
    }, [departments, form.department]);

    const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

    const validate = () => {
        const errs = {};
        if (!form.title?.trim()) errs.title = 'Job title is required';
        return errs;
    };

    const save = async (overrides = {}) => {
        const payload = { ...form, ...overrides };
        setSaving(true);
        try {
            const result = editJob
                ? await updateJob(editJob.id, payload)
                : await createJob(payload);
            onSaved(result, !!editJob);
            onClose();
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    const handleSubmit = async () => {
        setAttempted(true);
        const errs = validate();
        setErrors(errs);
        if (Object.keys(errs).length) return;
        await save();
    };

    const handleSaveDraft = async () => {
        setAttempted(true);
        const errs = validate();
        setErrors(errs);
        if (Object.keys(errs).length) return;
        await save({ status: 'draft' });
    };

    const addSkill = () => {
        const s = skillInput.trim();
        if (s && !form.skills_required.includes(s)) {
            setForm(f => ({ ...f, skills_required: [...f.skills_required, s] }));
        }
        setSkillInput('');
    };

    const removeSkill = (skill) =>
        setForm(f => ({ ...f, skills_required: f.skills_required.filter(s => s !== skill) }));

    const handleCreateDepartment = async () => {
        const name = departmentInput.trim();
        if (!name) return;

        setDepartmentActionLoading(true);
        setDepartmentError('');
        try {
            const created = await createDepartment(name);
            setDepartments((prev) => {
                const next = prev.some((dept) => dept.id === created.id)
                    ? prev.map((dept) => dept.id === created.id ? created : dept)
                    : [...prev, created];
                return next.sort((a, b) => a.name.localeCompare(b.name));
            });
            setForm((prev) => ({ ...prev, department: created.name }));
            setDepartmentInput('');
        } catch (e) {
            console.error(e);
            setDepartmentError('Unable to add department.');
        } finally {
            setDepartmentActionLoading(false);
        }
    };

    const handleDeleteDepartment = async (department) => {
        if (!department?.id || department.isCurrentOnly) return;
        if (!window.confirm(`Delete ${department.name} department?`)) return;

        setDepartmentActionLoading(true);
        setDepartmentError('');
        try {
            const response = await deleteDepartment(department.id);
            if (!response.ok) throw new Error('Delete failed');
            setDepartments((prev) => prev.filter((dept) => dept.id !== department.id));
            setForm((prev) => prev.department === department.name ? { ...prev, department: '' } : prev);
        } catch (e) {
            console.error(e);
            setDepartmentError('Unable to delete department.');
        } finally {
            setDepartmentActionLoading(false);
        }
    };

    const inputSx = (field) => ({
        '& .MuiOutlinedInput-root': {
            fontSize: '0.875rem',
            ...(attempted && errors[field] ? { '& fieldset': { borderColor: 'error.main' } } : {}),
        },
    });

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="lg"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: 3,
                    maxHeight: '92vh',
                    overflowX: 'hidden',
                }
            }}
        >
            {/* Header */}
            <DialogTitle sx={{ pb: 1.25, pt: 1.75, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
                    <Typography variant="h6" fontWeight={700} sx={{ fontSize: '0.95rem', lineHeight: 1.3 }}>
                        {editJob ? 'Edit Job Posting' : 'Create New Job Posting'}
                    </Typography>
                    <IconButton size="small" onClick={onClose}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </Box>
            </DialogTitle>

            {/* Scrollable body */}
            <DialogContent sx={{ py: 2, px: 2.5, overflowX: 'hidden' }}>

                {/* Error summary */}
                {attempted && Object.keys(errors).length > 0 && (
                    <Alert severity="error" icon={<ErrorOutlineIcon />} sx={{ mb: 2, borderRadius: 2 }}>
                        <Typography variant="body2" fontWeight={600}>Please fix the following:</Typography>
                        {Object.values(errors).map((e, i) => (
                            <Typography key={i} variant="caption" display="block">· {e}</Typography>
                        ))}
                    </Alert>
                )}

                <Stack spacing={2}>

                    {/* ── Section 1: Basic Information ── */}
                    <Box>
                        <SectionLabel>Basic Information</SectionLabel>
                        <SingleRowGrid>
                            <Box sx={{ flex: '1.6 1 0', minWidth: 0 }}>
                                <FieldLabel htmlFor="jf-title" required>Job Title</FieldLabel>
                                <TextField
                                    id="jf-title"
                                    fullWidth size="small"
                                    value={form.title}
                                    onChange={set('title')}
                                    onBlur={() => {
                                        if (!form.title?.trim()) setErrors(p => ({ ...p, title: 'Job title is required' }));
                                        else setErrors(p => { const n = { ...p }; delete n.title; return n; });
                                    }}
                                    placeholder="e.g. Senior Software Engineer"
                                    error={attempted && !!errors.title}
                                    helperText={attempted && errors.title}
                                    autoFocus
                                    sx={inputSx('title')}
                                />
                            </Box>
                            <Box sx={{ flex: '1.2 1 0', minWidth: 0 }}>
                                <FieldLabel htmlFor="jf-dept">Department</FieldLabel>
                                <FormControl fullWidth size="small">
                                    <Select
                                        id="jf-dept"
                                        value={form.department || ''}
                                        onChange={set('department')}
                                        displayEmpty
                                        disabled={departmentsLoading}
                                        renderValue={(value) => value || (
                                            <Typography component="span" sx={{ color: 'text.disabled' }}>
                                                Select department
                                            </Typography>
                                        )}
                                        MenuProps={{ PaperProps: { sx: { maxHeight: 360 } } }}
                                    >
                                        {departmentsLoading && (
                                            <MenuItem disabled>
                                                <CircularProgress size={16} sx={{ mr: 1 }} /> Loading departments
                                            </MenuItem>
                                        )}
                                        {!departmentsLoading && departmentOptions.length === 0 && (
                                            <MenuItem disabled>No departments yet</MenuItem>
                                        )}
                                        {departmentOptions.map((department) => (
                                            <MenuItem key={department.id} value={department.name} sx={{ pr: 0.5 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', minWidth: 0, gap: 1 }}>
                                                    <Typography noWrap sx={{ flex: 1, fontSize: '0.875rem' }}>
                                                        {department.name}
                                                    </Typography>
                                                    {!department.isCurrentOnly && (
                                                        <Tooltip title="Delete department">
                                                            <IconButton
                                                                size="small"
                                                                disabled={departmentActionLoading}
                                                                onMouseDown={(e) => {
                                                                    e.preventDefault();
                                                                    e.stopPropagation();
                                                                }}
                                                                onClick={(e) => {
                                                                    e.preventDefault();
                                                                    e.stopPropagation();
                                                                    handleDeleteDepartment(department);
                                                                }}
                                                            >
                                                                <DeleteIcon sx={{ fontSize: 16 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                    )}
                                                </Box>
                                            </MenuItem>
                                        ))}
                                        <ListSubheader disableSticky sx={{ bgcolor: 'background.paper', pt: 1 }}>
                                            <Box
                                                sx={{ display: 'flex', gap: 1, alignItems: 'center', py: 0.5 }}
                                                onMouseDown={(e) => e.stopPropagation()}
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <TextField
                                                    size="small"
                                                    fullWidth
                                                    value={departmentInput}
                                                    onChange={(e) => setDepartmentInput(e.target.value)}
                                                    onKeyDown={(e) => {
                                                        e.stopPropagation();
                                                        if (e.key === 'Enter') {
                                                            e.preventDefault();
                                                            handleCreateDepartment();
                                                        }
                                                    }}
                                                    placeholder="Add department"
                                                    inputProps={{ style: { fontSize: '0.8rem' } }}
                                                />
                                                <Button
                                                    size="small"
                                                    variant="outlined"
                                                    onClick={handleCreateDepartment}
                                                    disabled={departmentActionLoading || !departmentInput.trim()}
                                                    startIcon={departmentActionLoading ? <CircularProgress size={13} /> : <AddIcon />}
                                                    sx={{ whiteSpace: 'nowrap' }}
                                                >
                                                    Add
                                                </Button>
                                            </Box>
                                        </ListSubheader>
                                    </Select>
                                </FormControl>
                                {departmentError && (
                                    <Typography variant="caption" color="error" sx={{ mt: 0.4, display: 'block' }}>
                                        {departmentError}
                                    </Typography>
                                )}
                            </Box>
                            <Box sx={{ flex: '1 1 0', minWidth: 0 }}>
                                <FieldLabel htmlFor="jf-emp-type">Employment Type</FieldLabel>
                                <Select id="jf-emp-type" fullWidth size="small" value={form.employment_type} onChange={set('employment_type')}>
                                    <MenuItem value="full_time">Full Time</MenuItem>
                                    <MenuItem value="part_time">Part Time</MenuItem>
                                    <MenuItem value="contract">Contract</MenuItem>
                                    <MenuItem value="internship">Internship</MenuItem>
                                    <MenuItem value="freelance">Freelance</MenuItem>
                                </Select>
                            </Box>
                            <Box sx={{ flex: '0.9 1 0', minWidth: 0 }}>
                                <FieldLabel htmlFor="jf-loc-type">Location Type</FieldLabel>
                                <Select id="jf-loc-type" fullWidth size="small" value={form.location_type} onChange={set('location_type')}>
                                    <MenuItem value="onsite">On-site</MenuItem>
                                    <MenuItem value="remote">Remote</MenuItem>
                                    <MenuItem value="hybrid">Hybrid</MenuItem>
                                </Select>
                            </Box>
                            <Box sx={{ flex: '0.9 1 0', minWidth: 0 }}>
                                <FieldLabel htmlFor="jf-location">Location</FieldLabel>
                                <TextField
                                    id="jf-location"
                                    fullWidth size="small"
                                    value={form.location}
                                    onChange={set('location')}
                                    placeholder="e.g. Jaipur"
                                />
                            </Box>
                        </SingleRowGrid>
                    </Box>

                    {/* ── Section 2: Experience, Compensation & Settings (merged) ── */}
                    <Box>
                        <SectionLabel>Experience, Compensation &amp; Settings</SectionLabel>
                        <SingleRowGrid>
                            <Box>
                                <FieldLabel htmlFor="jf-exp-min">Min Exp (yrs)</FieldLabel>
                                <TextField
                                    id="jf-exp-min"
                                    fullWidth size="small" type="number"
                                    inputProps={{ min: 0 }}
                                    value={form.experience_min}
                                    onChange={set('experience_min')}
                                    placeholder="0"
                                />
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-exp-max">Max Exp (yrs)</FieldLabel>
                                <TextField
                                    id="jf-exp-max"
                                    fullWidth size="small" type="number"
                                    inputProps={{ min: 0 }}
                                    value={form.experience_max}
                                    onChange={set('experience_max')}
                                    placeholder="e.g. 5"
                                />
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-sal-min">Salary Min</FieldLabel>
                                <TextField
                                    id="jf-sal-min"
                                    fullWidth size="small" type="number"
                                    inputProps={{ min: 0 }}
                                    InputProps={{ startAdornment: <InputAdornment position="start">₹</InputAdornment> }}
                                    value={form.salary_min}
                                    onChange={set('salary_min')}
                                    placeholder="500000"
                                />
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-sal-max">Salary Max</FieldLabel>
                                <TextField
                                    id="jf-sal-max"
                                    fullWidth size="small" type="number"
                                    inputProps={{ min: 0 }}
                                    InputProps={{ startAdornment: <InputAdornment position="start">₹</InputAdornment> }}
                                    value={form.salary_max}
                                    onChange={set('salary_max')}
                                    placeholder="800000"
                                />
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-openings">Openings</FieldLabel>
                                <TextField
                                    id="jf-openings"
                                    fullWidth size="small" type="number"
                                    inputProps={{ min: 1 }}
                                    value={form.openings_count}
                                    onChange={set('openings_count')}
                                />
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-post-type">Posting Type</FieldLabel>
                                <Select id="jf-post-type" fullWidth size="small" value={form.posting_type} onChange={set('posting_type')}>
                                    <MenuItem value="external">External</MenuItem>
                                    <MenuItem value="internal">Internal</MenuItem>
                                    <MenuItem value="both">Both</MenuItem>
                                </Select>
                            </Box>
                            <Box>
                                <FieldLabel htmlFor="jf-status">Status</FieldLabel>
                                <Select
                                    id="jf-status"
                                    fullWidth size="small"
                                    value={form.status}
                                    onChange={set('status')}
                                    renderValue={(val) => (
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: STATUS_CONFIG[val]?.color || 'text.secondary' }} />
                                            {STATUS_CONFIG[val]?.label || val}
                                        </Box>
                                    )}
                                >
                                    {Object.entries(STATUS_CONFIG).map(([val, cfg]) => (
                                        <MenuItem key={val} value={val}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: cfg.color }} />
                                                {cfg.label}
                                            </Box>
                                        </MenuItem>
                                    ))}
                                </Select>
                            </Box>
                        </SingleRowGrid>
                    </Box>

                    {/* ── Section 3: Job Details (side by side) ── */}
                    <Box>
                        <SectionLabel>Job Details</SectionLabel>
                        <SingleRowGrid spacing={1.5}>
                            <Box>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
                                    <FieldLabel htmlFor="jf-desc">Job Description</FieldLabel>
                                    <Typography variant="caption" color="text.disabled">{(form.description || '').length} chars</Typography>
                                </Box>
                                <TextField
                                    id="jf-desc"
                                    fullWidth multiline rows={3}
                                    value={form.description}
                                    onChange={set('description')}
                                    placeholder="Role scope, daily responsibilities, team structure, growth opportunities…"
                                    inputProps={{ style: { fontSize: '0.875rem' } }}
                                />
                            </Box>
                            <Box>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
                                    <FieldLabel htmlFor="jf-req">Requirements</FieldLabel>
                                    <Typography variant="caption" color="text.disabled">{(form.requirements || '').length} chars</Typography>
                                </Box>
                                <TextField
                                    id="jf-req"
                                    fullWidth multiline rows={3}
                                    value={form.requirements}
                                    onChange={set('requirements')}
                                    placeholder="Must-have skills, qualifications, tools, experience levels…"
                                    inputProps={{ style: { fontSize: '0.875rem' } }}
                                />
                            </Box>
                        </SingleRowGrid>
                    </Box>

                    {/* ── Section 4: Skills ── */}
                    <Box>
                        <SectionLabel>Skills Required</SectionLabel>
                        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                            <TextField
                                fullWidth size="small"
                                value={skillInput}
                                onChange={e => setSkillInput(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                                placeholder="e.g. React, Node.js, SQL — press Enter to add"
                                inputProps={{ style: { fontSize: '0.875rem' } }}
                            />
                            <Button
                                variant="outlined" size="small"
                                startIcon={<AddCircleOutlineIcon />}
                                onClick={addSkill}
                                sx={{ whiteSpace: 'nowrap', px: 2 }}
                            >
                                Add
                            </Button>
                        </Box>
                        <Box sx={{
                            minHeight: 36, p: 1, display: 'flex', flexWrap: 'wrap', gap: 0.75,
                            bgcolor: 'action.hover', borderRadius: 2,
                            border: '1px solid', borderColor: 'divider',
                        }}>
                            {form.skills_required.length === 0 ? (
                                <Typography variant="caption" color="text.disabled" sx={{ alignSelf: 'center' }}>
                                    No skills added yet
                                </Typography>
                            ) : form.skills_required.map(skill => (
                                <Chip
                                    key={skill}
                                    label={skill}
                                    size="small"
                                    onDelete={() => removeSkill(skill)}
                                    sx={{ fontSize: '0.75rem', bgcolor: 'primary.50', color: 'primary.dark' }}
                                />
                            ))}
                        </Box>
                    </Box>

                    {/* ── Section 5: Application Source ── */}
                    <Box>
                        <FieldLabel htmlFor="jf-form-url">Google Sheets URL</FieldLabel>
                        <TextField
                            id="jf-form-url"
                            fullWidth size="small" type="url"
                            value={form.google_form_url}
                            onChange={set('google_form_url')}
                            placeholder="https://docs.google.com/spreadsheets/d/…/edit"
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <LinkIcon sx={{ fontSize: 16 }} />
                                    </InputAdornment>
                                ),
                            }}
                            helperText="Link the Google Form response spreadsheet (shared as Viewer)"
                        />
                    </Box>

                </Stack>
            </DialogContent>

            {/* Footer */}
            <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: '1px solid', borderColor: 'divider', gap: 1 }}>
                <Button onClick={onClose} color="inherit" sx={{ mr: 'auto' }}>Cancel</Button>
                <Button
                    onClick={handleSaveDraft}
                    disabled={saving}
                    color="inherit"
                    sx={{ textDecoration: 'underline', color: 'text.secondary' }}
                >
                    Save as Draft
                </Button>
                <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={saving}
                    startIcon={saving ? <CircularProgress size={15} color="inherit" /> : null}
                    sx={{ borderRadius: 2, fontWeight: 700, px: 3 }}
                >
                    {saving ? 'Saving…' : editJob ? 'Save Changes' : 'Create Job'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

// ─── Main Board ───────────────────────────────────────────────────────────────

export default function HiringJobsBoard() {
    const navigate = useNavigate();
    const location = useLocation();
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ status: '', search: '' });
    const [sortBy, setSortBy] = useState('newest');
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editJob, setEditJob] = useState(null);

    const [selectedJob, setSelectedJob] = useState(null);
    const [applications, setApplications] = useState([]);
    const [appsLoading, setAppsLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState(null);

    const loadJobs = async (params = {}) => {
        setLoading(true);
        try {
            const data = await fetchJobs(params);
            setJobs(Array.isArray(data) ? data : []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadJobs(filter.status ? { status: filter.status } : {});
    }, [filter.status]);

    const displayJobs = useMemo(() => {
        const q = filter.search.trim().toLowerCase();
        let filtered = jobs;
        if (q) {
            filtered = jobs.filter(j =>
                j.title?.toLowerCase().includes(q) ||
                j.department?.toLowerCase().includes(q) ||
                j.location?.toLowerCase().includes(q)
            );
        }
        return [...filtered].sort((a, b) => {
            if (sortBy === 'newest') {
                return new Date(b.published_at || b.created_at || 0) - new Date(a.published_at || a.created_at || 0);
            }
            if (sortBy === 'oldest') {
                return new Date(a.published_at || a.created_at || 0) - new Date(b.published_at || b.created_at || 0);
            }
            if (sortBy === 'title_asc') {
                return (a.title || '').localeCompare(b.title || '');
            }
            if (sortBy === 'title_desc') {
                return (b.title || '').localeCompare(a.title || '');
            }
            if (sortBy === 'applications_desc') {
                return (b.applications_count || 0) - (a.applications_count || 0);
            }
            if (sortBy === 'openings_desc') {
                return (b.openings_count || 0) - (a.openings_count || 0);
            }
            return 0;
        });
    }, [jobs, filter.search, sortBy]);

    const stats = useMemo(() => ({
        total: jobs.length,
        published: jobs.filter(j => j.status === 'published').length,
        draft: jobs.filter(j => j.status === 'draft').length,
        closed: jobs.filter(j => j.status === 'closed').length,
    }), [jobs]);

    const openCreate = () => { setEditJob(null); setDialogOpen(true); };
    const openEdit = (job) => { setEditJob(job); setDialogOpen(true); };

    const handleSaved = (result, isEdit) => {
        if (isEdit) {
            setJobs(prev => prev.map(j => j.id === result.id ? result : j));
        } else {
            setJobs(prev => [result, ...prev]);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this job posting? This cannot be undone.')) return;
        try {
            await deleteJob(id);
            setJobs(prev => prev.filter(j => j.id !== id));
        } catch (e) {
            console.error(e);
        }
    };

    const handlePublish = async (id) => {
        try {
            const updated = await publishJob(id);
            setJobs(prev => prev.map(j => j.id === id ? { ...j, ...updated } : j));
        } catch (e) {
            console.error(e);
        }
    };

    const handleCloseJob = async (id) => {
        try {
            const updated = await closeJob(id);
            setJobs(prev => prev.map(j => j.id === id ? { ...j, ...updated } : j));
        } catch (e) {
            console.error(e);
        }
    };

    const openCandidates = async (job) => {
        setSelectedJob(job);
        setSyncResult(null);
        setApplications([]);
        setAppsLoading(true);
        try {
            const data = await fetchJobApplications(job.id);
            setApplications(Array.isArray(data) ? data : []);
            setJobs(prev => prev.map(j =>
                j.id === job.id ? { ...j, applications_count: data.length } : j
            ));
        } catch (e) {
            console.error(e);
        } finally {
            setAppsLoading(false);
        }
    };

    useEffect(() => {
        if (!loading && jobs.length > 0) {
            const stateJobId = location.state?.jobId;
            if (stateJobId) {
                const found = jobs.find(j => String(j.id) === String(stateJobId));
                if (found) {
                    openCandidates(found);
                    navigate('/team/hiring', { replace: true, state: {} });
                }
            }
        }
    }, [loading, jobs, location.state, navigate]);

    const handleSyncForm = async () => {
        if (!selectedJob) return;
        setSyncing(true);
        setSyncResult(null);
        try {
            const result = await syncJobGoogleForm(selectedJob.id);
            setSyncResult(result);
            const data = await fetchJobApplications(selectedJob.id);
            setApplications(Array.isArray(data) ? data : []);
            setJobs(prev => prev.map(j =>
                j.id === selectedJob.id ? { ...j, applications_count: data.length } : j
            ));
        } catch (e) {
            setSyncResult({ error: e.is_form_url ? 'FORM_URL' : (e.message || 'Sync failed'), is_form_url: !!e.is_form_url });
        } finally {
            setSyncing(false);
        }
    };

    const handleAccept = async (appId) => {
        try {
            const updated = await acceptApplication(appId);
            setApplications(prev => prev.map(a => a.id === appId ? { ...a, ...updated } : a));
        } catch (e) { console.error(e); }
    };

    const handleReject = async (appId) => {
        try {
            const existing = applications.find(a => a.id === appId);
            const wasRejected = existing?.current_stage_detail?.slug === 'rejected';
            const updated = await rejectApplication(appId);
            setApplications(prev => prev.map(a => a.id === appId ? { ...a, ...updated } : a));
            if (!wasRejected && selectedJob) {
                setJobs(prev => prev.map(j =>
                    j.id === selectedJob.id ? { ...j, rejected_count: (j.rejected_count || 0) + 1 } : j
                ));
            }
        } catch (e) { console.error(e); }
    };

    const handleSaveToggle = async (appId) => {
        try {
            const { is_saved } = await toggleSaveApplication(appId);
            setApplications(prev => prev.map(a => a.id === appId ? { ...a, is_saved } : a));
        } catch (e) { console.error(e); }
    };

    const extraColumns = useMemo(() => {
        const keys = new Set();
        applications.forEach(app =>
            Object.keys(app.extra_data || {}).forEach(k => { if (!k.startsWith('_')) keys.add(k); })
        );
        return [...keys];
    }, [applications]);

    // ── Excel-like table state ────────────────────────────────────────────────
    const [xlPage, setXlPage] = useState(0);
    const [xlRpp, setXlRpp] = useState(25);
    const [colWidths, setColWidths] = useState({});
    const resizingRef = React.useRef(null);

    // Filter and Sort states
    const [colFilters, setColFilters] = useState({});
    const [colSort, setColSort] = useState(null);
    const [filterAnchorEl, setFilterAnchorEl] = useState(null);
    const [activeFilterCol, setActiveFilterCol] = useState(null);
    const [tempSelectedValues, setTempSelectedValues] = useState(new Set());
    const [valSearchQuery, setValSearchQuery] = useState('');

    const getColValueString = (app, colKey) => {
        if (colKey === '__name__') return app.candidate_detail?.name || '—';
        if (colKey === '__email__') return app.candidate_detail?.email || '—';
        if (colKey === '__phone__') return app.candidate_detail?.phone || '—';
        if (colKey === '__stage__') return app.current_stage?.name || '—';
        if (colKey === '__source__') return app.candidate_detail?.source || 'manual';
        if (colKey === '__applied__') {
            if (!app.applied_at) return '—';
            return new Date(app.applied_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' });
        }
        return String((app.extra_data || {})[colKey] ?? '').trim() || '—';
    };

    const uniqueValues = useMemo(() => {
        if (!activeFilterCol) return [];
        const valuesSet = new Set();
        applications.forEach(app => {
            valuesSet.add(getColValueString(app, activeFilterCol));
        });
        return [...valuesSet].sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
    }, [applications, activeFilterCol]);

    const filteredUniqueValues = useMemo(() => {
        const q = valSearchQuery.toLowerCase().trim();
        if (!q) return uniqueValues;
        return uniqueValues.filter(val => val.toLowerCase().includes(q));
    }, [uniqueValues, valSearchQuery]);

    const handleOpenFilter = (e, colKey) => {
        e.stopPropagation();
        setFilterAnchorEl(e.currentTarget);
        setActiveFilterCol(colKey);
        setValSearchQuery('');
        
        const valuesSet = new Set();
        applications.forEach(app => {
            valuesSet.add(getColValueString(app, colKey));
        });
        const allVals = [...valuesSet];

        if (colFilters[colKey]) {
            setTempSelectedValues(new Set(colFilters[colKey]));
        } else {
            setTempSelectedValues(new Set(allVals));
        }
    };

    const handleToggleValue = (val) => {
        setTempSelectedValues(prev => {
            const next = new Set(prev);
            if (next.has(val)) {
                next.delete(val);
            } else {
                next.add(val);
            }
            return next;
        });
    };

    const handleSelectAllValues = () => {
        setTempSelectedValues(new Set(uniqueValues));
    };

    const handleClearAllValues = () => {
        setTempSelectedValues(new Set());
    };

    const handleApplyFilter = () => {
        setColFilters(prev => {
            const next = { ...prev };
            if (tempSelectedValues.size === uniqueValues.length) {
                delete next[activeFilterCol];
            } else {
                next[activeFilterCol] = new Set(tempSelectedValues);
            }
            return next;
        });
        setFilterAnchorEl(null);
    };

    const handleSortClick = (direction) => {
        setColSort({ key: activeFilterCol, direction });
        setFilterAnchorEl(null);
    };

    const handleClearAllFilters = () => {
        setColFilters({});
        setColSort(null);
    };

    useEffect(() => {
        setXlPage(0);
    }, [colFilters, colSort]);

    const filteredApplications = useMemo(() => {
        let res = [...applications];
        Object.entries(colFilters).forEach(([colKey, selectedSet]) => {
            res = res.filter(app => {
                const val = getColValueString(app, colKey);
                return selectedSet.has(val);
            });
        });
        if (colSort) {
            const { key, direction } = colSort;
            res.sort((a, b) => {
                const valA = getColValueString(a, key);
                const valB = getColValueString(b, key);
                if (valA === '—' && valB !== '—') return 1;
                if (valB === '—' && valA !== '—') return -1;
                const cmp = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' });
                return direction === 'asc' ? cmp : -cmp;
            });
        }
        return res;
    }, [applications, colFilters, colSort]);

    const ALL_COLS = useMemo(() => [
        { key: '__num__',     label: '#',       w: 44,  frozen: true },
        { key: '__name__',    label: 'Name',    w: 180, frozen: true },
        { key: '__email__',   label: 'Email',   w: 210 },
        { key: '__phone__',   label: 'Phone',   w: 145 },
        { key: '__stage__',   label: 'Stage',   w: 120 },
        { key: '__source__',  label: 'Source',  w: 100 },
        ...extraColumns.map(k => ({ key: k, label: k, w: 160 })),
        { key: '__applied__', label: 'Applied', w: 110 },
        { key: '__actions__', label: 'Actions', w: 140 },
    ], [extraColumns]);

    const getW = (key) => colWidths[key] ?? (ALL_COLS.find(c => c.key === key)?.w ?? 120);

    const frozenLeft = useMemo(() => {
        const m = {}; let acc = 0;
        ALL_COLS.forEach(c => { m[c.key] = acc; if (c.frozen) acc += getW(c.key); });
        return m;
    }, [ALL_COLS, colWidths]);

    const startResize = (e, key) => {
        e.preventDefault();
        const x0 = e.clientX, w0 = getW(key);
        resizingRef.current = { key, x0, w0 };
        const move = ev => {
            const currentX = ev.clientX;
            setColWidths(p => ({ ...p, [key]: Math.max(50, w0 + currentX - x0) }));
        };
        const up = () => {
            resizingRef.current = null;
            window.removeEventListener('mousemove', move);
            window.removeEventListener('mouseup', up);
        };
        window.addEventListener('mousemove', move);
        window.addEventListener('mouseup', up);
    };

    const xlPaged = useMemo(() => filteredApplications.slice(xlPage * xlRpp, xlPage * xlRpp + xlRpp), [filteredApplications, xlPage, xlRpp]);
    const xlTotal = Math.ceil(filteredApplications.length / xlRpp);

    const thSx = (col) => ({
        position: 'sticky', top: 0, zIndex: col.frozen ? 5 : 2,
        ...(col.frozen ? { left: frozenLeft[col.key] } : {}),
        width: getW(col.key), minWidth: getW(col.key), maxWidth: getW(col.key),
        background: isDark ? '#1e293b' : '#eef0f4',
        borderRight: isDark ? '1px solid #334155' : '1px solid #c8cdd6',
        borderBottom: isDark ? '2px solid #475569' : '2px solid #bcc1cb',
        fontWeight: 700, fontSize: '0.7rem',
        color: isDark ? '#cbd5e1' : '#4b5563',
        letterSpacing: '0.04em',
        textTransform: 'uppercase', padding: '0 8px', height: 34,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        userSelect: 'none', boxSizing: 'border-box', verticalAlign: 'middle',
    });

    const tdSx = (col, ri) => ({
        ...(col.frozen ? { position: 'sticky', left: frozenLeft[col.key], zIndex: 1 } : {}),
        width: getW(col.key), minWidth: getW(col.key), maxWidth: getW(col.key),
        background: isDark
            ? (ri % 2 === 0 ? '#1e293b' : '#0f172a')
            : (ri % 2 === 0 ? (col.frozen ? '#f9fafb' : '#fff') : (col.frozen ? '#f3f5f7' : '#f8f9fa')),
        borderRight: isDark ? '1px solid #334155' : '1px solid #e8ecf0',
        borderBottom: isDark ? '1px solid #334155' : '1px solid #edf0f5',
        fontSize: '0.78rem', padding: '0 8px', height: 32,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        boxSizing: 'border-box',
        color: isDark ? '#f1f5f9' : '#1f2937',
        verticalAlign: 'middle',
    });

    return (
        <Box sx={{
            p: 3,
            ...(selectedJob ? {
                height: 'calc(100vh - 84px)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxSizing: 'border-box'
            } : {})
        }}>

            {selectedJob ? (
                <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                        <IconButton onClick={() => setSelectedJob(null)} size="small">
                            <ArrowBackIcon />
                        </IconButton>
                        <Box sx={{ flex: 1 }}>
                            <Typography variant="h6" fontWeight={700}>{selectedJob.title}</Typography>
                            <Typography variant="body2" color="text.secondary">
                                {filteredApplications.length === applications.length
                                    ? `${applications.length} applicant${applications.length !== 1 ? 's' : ''}`
                                    : `${filteredApplications.length} of ${applications.length} applicant${applications.length !== 1 ? 's' : ''} filtered`}
                            </Typography>
                        </Box>
                        {(Object.keys(colFilters).length > 0 || colSort !== null) && (
                            <Button
                                variant="outlined" size="small"
                                color="error"
                                onClick={handleClearAllFilters}
                                sx={{ textTransform: 'none' }}
                            >
                                Clear Filters
                            </Button>
                        )}
                        <Button
                            size="small" variant="outlined" color="inherit"
                            startIcon={<PeopleIcon />}
                            onClick={() => navigate('/team/hiring/pipeline', { state: { jobId: selectedJob.id } })}
                        >
                            Pipeline
                        </Button>
                        {selectedJob.google_form_url && (
                            <Button
                                variant="outlined" size="small"
                                startIcon={syncing ? <CircularProgress size={14} /> : <CloudSyncIcon />}
                                onClick={handleSyncForm}
                                disabled={syncing}
                            >
                                {syncing ? 'Syncing…' : 'Sync Form'}
                            </Button>
                        )}
                        <Button
                            size="small" variant="outlined" color="inherit"
                            startIcon={<EditIcon />}
                            onClick={() => openEdit(selectedJob)}
                        >
                            Edit Job
                        </Button>
                    </Box>

                    {syncResult && (
                        syncResult.is_form_url ? (
                            <Alert
                                severity="warning"
                                onClose={() => setSyncResult(null)}
                                sx={{ mb: 2, borderRadius: 2 }}
                                action={
                                    <Button
                                        size="small" color="inherit"
                                        startIcon={<EditIcon />}
                                        onClick={() => { setSyncResult(null); openEdit(selectedJob); }}
                                    >
                                        Edit Job
                                    </Button>
                                }
                            >
                                <Typography fontWeight={700} variant="body2" sx={{ mb: 1 }}>
                                    You saved a Google Form URL — please update it with the Sheets URL
                                </Typography>
                                {[
                                    'Open your Google Form → click the Responses tab',
                                    'Click the green Sheets icon "Link to Sheets" → a spreadsheet opens',
                                    'Spreadsheet → Share → "Anyone with the link" → Viewer → Done',
                                    'Copy the spreadsheet URL → Edit this job → paste it → save',
                                ].map((step, i) => (
                                    <Box key={i} sx={{ display: 'flex', gap: 1, mb: 0.5 }}>
                                        <Box sx={{
                                            width: 20, height: 20, borderRadius: '50%',
                                            bgcolor: 'warning.main', color: '#fff',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            fontSize: '0.65rem', fontWeight: 700, flexShrink: 0,
                                        }}>
                                            {i + 1}
                                        </Box>
                                        <Typography variant="body2">{step}</Typography>
                                    </Box>
                                ))}
                            </Alert>
                        ) : (
                            <Alert
                                severity={syncResult.error ? 'error' : 'success'}
                                onClose={() => setSyncResult(null)}
                                sx={{ mb: 2, borderRadius: 2 }}
                            >
                                {syncResult.error
                                    ? syncResult.error
                                    : `Synced ${syncResult.imported} candidate(s) (${syncResult.new_count ?? 0} new).${syncResult.skipped ? ` ${syncResult.skipped} skipped (no email).` : ''}`}
                            </Alert>
                        )
                    )}

                    {appsLoading ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 10, gap: 2 }}>
                            <CircularProgress />
                            <Typography variant="body2" color="text.secondary">
                                Loading candidates…
                            </Typography>
                        </Box>
                    ) : applications.length === 0 ? (
                        <Box sx={{ textAlign: 'center', py: 10 }}>
                            <PeopleIcon sx={{ fontSize: 56, color: 'text.disabled', mb: 1.5 }} />
                            <Typography color="text.secondary" fontWeight={600}>No candidates yet</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                {selectedJob.google_form_url
                                    ? 'Click "Sync Form" to import responses from your Google Form.'
                                    : 'Edit the job to add a Google Form URL and sync responses.'}
                            </Typography>
                        </Box>
                    ) : (
                        <Box sx={{
                            border: '1px solid',
                            borderColor: isDark ? '#334155' : '#d0d5dd',
                            borderRadius: 2,
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column',
                            flex: 1,
                            minHeight: 0
                        }}>
                            <Box sx={{ overflowX: 'auto', overflowY: 'auto', flex: 1, minHeight: 0 }}>
                                <table style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: 'max-content', minWidth: '100%' }}>
                                    <thead>
                                        <tr>
                                            {ALL_COLS.map(col => {
                                                const isFilterable = col.key !== '__num__' && col.key !== '__actions__';
                                                const isFilterActive = colFilters[col.key] !== undefined;
                                                const isSortActive = colSort?.key === col.key;
                                                return (
                                                    <Box component="th" key={col.key} sx={{ ...thSx(col), position: 'relative', pr: isFilterable ? '26px' : '8px' }}>
                                                        <Tooltip title={col.label} placement="top">
                                                            <Box component="span" sx={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                                {col.label}
                                                            </Box>
                                                        </Tooltip>
                                                        {isFilterable && (
                                                            <IconButton
                                                                size="small"
                                                                onClick={(e) => handleOpenFilter(e, col.key)}
                                                                sx={{
                                                                    position: 'absolute',
                                                                    right: 6,
                                                                    top: '50%',
                                                                    transform: 'translateY(-50%)',
                                                                    p: 0.2,
                                                                    color: (isFilterActive || isSortActive) ? '#6366f1' : 'text.disabled',
                                                                    '&:hover': { color: '#6366f1' }
                                                                }}
                                                            >
                                                                <FilterListIcon sx={{ fontSize: 13 }} />
                                                            </IconButton>
                                                        )}
                                                        <Box onMouseDown={e => startResize(e, col.key)}
                                                            sx={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 4, cursor: 'col-resize', '&:hover': { bgcolor: '#6366f1' } }} />
                                                    </Box>
                                                );
                                            })}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {xlPaged.map((app, ri) => {
                                            const gRow = xlPage * xlRpp + ri + 1;
                                            return (
                                                <tr key={app.id}>
                                                    {ALL_COLS.map(col => {
                                                        const cs = tdSx(col, ri);
                                                        if (col.key === '__num__') return <Box component="td" key={col.key} sx={{ ...cs, color: '#9ca3af', textAlign: 'center', fontWeight: 600 }}>{gRow}</Box>;
                                                        if (col.key === '__name__') return (
                                                            <Box component="td" key={col.key} sx={cs}>
                                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                                    <Avatar sx={{ width: 20, height: 20, fontSize: '0.58rem', bgcolor: '#6366f1', flexShrink: 0 }}>
                                                                        {(app.candidate_detail?.name || '?')[0].toUpperCase()}
                                                                    </Avatar>
                                                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>{app.candidate_detail?.name || '—'}</span>
                                                                </Box>
                                                            </Box>
                                                        );
                                                        if (col.key === '__email__') return (
                                                            <Box component="td" key={col.key} sx={cs}>
                                                                {app.candidate_detail?.email?.endsWith('@noemail.form')
                                                                    ? <span style={{ color: '#f59e0b', fontStyle: 'italic', fontSize: '0.72rem' }}>no email</span>
                                                                    : (app.candidate_detail?.email || '—')}
                                                            </Box>
                                                        );
                                                        if (col.key === '__phone__') return <Box component="td" key={col.key} sx={cs}>{app.candidate_detail?.phone || '—'}</Box>;
                                                        if (col.key === '__stage__') return (
                                                            <Box component="td" key={col.key} sx={cs}>
                                                                {app.current_stage_detail
                                                                    ? <Chip label={app.current_stage_detail.name} size="small" sx={{ bgcolor: (app.current_stage_detail.color || '#6366f1') + '22', color: app.current_stage_detail.color || '#6366f1', fontWeight: 600, fontSize: '0.65rem', height: 18 }} />
                                                                    : '—'}
                                                            </Box>
                                                        );
                                                        if (col.key === '__source__') return (
                                                            <Box component="td" key={col.key} sx={cs}>
                                                                <Chip label={app.candidate_detail?.source || 'manual'} size="small" variant="outlined" sx={{ fontSize: '0.62rem', height: 17 }} />
                                                            </Box>
                                                        );
                                                        if (col.key === '__applied__') return <Box component="td" key={col.key} sx={{ ...cs, color: '#6b7280', fontSize: '0.71rem' }}>{new Date(app.applied_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })}</Box>;
                                                        if (col.key === '__actions__') return (
                                                            <Box component="td" key={col.key} sx={{ ...cs, overflow: 'visible' }}>
                                                                <Box sx={{ display: 'flex' }}>
                                                                    <Tooltip title="Resume"><span><IconButton size="small" color="primary" disabled={!app.candidate_detail?.resume_url} onClick={() => window.open(app.candidate_detail.resume_url, '_blank')} sx={{ p: 0.4 }}><OpenInNewIcon sx={{ fontSize: 13 }} /></IconButton></span></Tooltip>
                                                                    <Tooltip title={app.is_saved ? 'Saved' : 'Save'}><IconButton size="small" color={app.is_saved ? 'warning' : 'default'} onClick={() => handleSaveToggle(app.id)} sx={{ p: 0.4 }}>{app.is_saved ? <BookmarkIcon sx={{ fontSize: 13 }} /> : <BookmarkBorderIcon sx={{ fontSize: 13 }} />}</IconButton></Tooltip>
                                                                    <Tooltip title="Accept"><span><IconButton size="small" color="success" disabled={app.pipeline_stage !== null || app.current_stage_detail?.slug === 'rejected'} onClick={() => handleAccept(app.id)} sx={{ p: 0.4 }}><CheckCircleIcon sx={{ fontSize: 13 }} /></IconButton></span></Tooltip>
                                                                    <Tooltip title="Reject"><span><IconButton size="small" color="error" disabled={app.current_stage_detail?.slug === 'rejected'} onClick={() => handleReject(app.id)} sx={{ p: 0.4 }}><CancelIcon sx={{ fontSize: 13 }} /></IconButton></span></Tooltip>
                                                                </Box>
                                                            </Box>
                                                        );
                                                        const v = String((app.extra_data || {})[col.key] ?? '');
                                                        return <Box component="td" key={col.key} sx={cs}><Tooltip title={v} placement="top" disableHoverListener={v.length < 24}><span>{v || '—'}</span></Tooltip></Box>;
                                                    })}
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 0.75, borderTop: '1px solid', borderColor: isDark ? '#334155' : '#e5e9f0', background: isDark ? '#0f172a' : '#f0f2f5', flexWrap: 'wrap', gap: 1 }}>
                                <Typography sx={{ fontSize: '0.74rem', color: '#6b7280' }}>
                                    {`${Math.min(xlPage * xlRpp + 1, filteredApplications.length)}–${Math.min((xlPage + 1) * xlRpp, filteredApplications.length)} of ${filteredApplications.length}`}
                                </Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                    <Typography sx={{ fontSize: '0.71rem', color: '#6b7280' }}>Rows:</Typography>
                                    <Select size="small" value={xlRpp} onChange={e => { setXlRpp(Number(e.target.value)); setXlPage(0); }}
                                        sx={{ fontSize: '0.72rem', height: 26, '.MuiSelect-select': { py: 0.2, px: 1 } }}>
                                        {[10, 25, 50, 100].map(n => <MenuItem key={n} value={n} sx={{ fontSize: '0.72rem' }}>{n}</MenuItem>)}
                                    </Select>
                                    {[{l:'«',a:()=>setXlPage(0),d:xlPage===0},{l:'‹',a:()=>setXlPage(p=>p-1),d:xlPage===0}].map(b=><IconButton key={b.l} size="small" disabled={b.d} onClick={b.a} sx={{p:0.4,minWidth:26,height:26,fontSize:'0.72rem',fontWeight:700,borderRadius:1,color: isDark ? '#cbd5e1' : 'inherit'}}>{b.l}</IconButton>)}
                                    {Array.from({length:Math.min(5,xlTotal)},(_,i)=>{
                                        const s=Math.max(0,Math.min(xlPage-2,xlTotal-5)); const pg=s+i;
                                        if(pg>=xlTotal) return null;
                                        return <IconButton key={pg} size="small" onClick={()=>setXlPage(pg)} sx={{p:0.4,minWidth:26,height:26,borderRadius:1,fontSize:'0.72rem',bgcolor:pg===xlPage?'#6366f1':'transparent',color:pg===xlPage?'#fff':(isDark?'#cbd5e1':'#374151'),fontWeight:pg===xlPage?700:400}}>{pg+1}</IconButton>;
                                    })}
                                    {[{l:'›',a:()=>setXlPage(p=>p+1),d:xlPage>=xlTotal-1},{l:'»',a:()=>setXlPage(xlTotal-1),d:xlPage>=xlTotal-1}].map(b=><IconButton key={b.l} size="small" disabled={b.d} onClick={b.a} sx={{p:0.4,minWidth:26,height:26,fontSize:'0.72rem',fontWeight:700,borderRadius:1,color: isDark ? '#cbd5e1' : 'inherit'}}>{b.l}</IconButton>)}
                                </Box>
                            </Box>
                        </Box>

                    )}
                </>

            ) : (
                <>
                    {/* Toolbar */}
                    <Box sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 3,
                        flexWrap: 'wrap',
                        gap: 2,
                    }}>
                        {/* Filters (Search, Status, Sort) */}
                        <Box sx={{
                            display: 'flex',
                            gap: 1.5,
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            width: { xs: '100%', lg: 'auto' },
                        }}>
                            <TextField
                                size="small"
                                placeholder="Search jobs…"
                                value={filter.search}
                                onChange={e => setFilter(f => ({ ...f, search: e.target.value }))}
                                InputProps={{
                                    startAdornment: (
                                        <InputAdornment position="start">
                                            <SearchIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
                                        </InputAdornment>
                                    ),
                                }}
                                sx={{ width: { xs: '100%', sm: 260 }, '& .MuiOutlinedInput-root': { height: 40 } }}
                            />
                            <FormControl size="small" sx={{ width: { xs: '100%', sm: 150 }, '& .MuiOutlinedInput-root': { height: 40 } }}>
                                <InputLabel>Status</InputLabel>
                                <Select
                                    label="Status"
                                    value={filter.status}
                                    onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
                                >
                                    <MenuItem value="">All</MenuItem>
                                    {Object.entries(STATUS_CONFIG).map(([val, cfg]) => (
                                        <MenuItem key={val} value={val}>{cfg.label}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                            <FormControl size="small" sx={{ width: { xs: '100%', sm: 150 }, '& .MuiOutlinedInput-root': { height: 40 } }}>
                                <InputLabel>Sort By</InputLabel>
                                <Select
                                    label="Sort By"
                                    value={sortBy}
                                    onChange={e => setSortBy(e.target.value)}
                                >
                                    <MenuItem value="newest">Newest First</MenuItem>
                                    <MenuItem value="oldest">Oldest First</MenuItem>
                                    <MenuItem value="title_asc">Title (A-Z)</MenuItem>
                                    <MenuItem value="title_desc">Title (Z-A)</MenuItem>
                                    <MenuItem value="applications_desc">Applications</MenuItem>
                                    <MenuItem value="openings_desc">Openings</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* Dashboard Stats Cards in Middle */}
                        <Box sx={{
                            display: 'flex',
                            gap: 1,
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            justifyContent: { xs: 'flex-start', md: 'center' },
                            width: { xs: '100%', md: 'auto' },
                        }}>
                            {[
                                { label: 'Total Jobs', value: stats.total, color: '#6366f1' },
                                { label: 'Published', value: stats.published, color: '#16a34a' },
                                { label: 'Draft', value: stats.draft, color: '#d97706' },
                                { label: 'Closed', value: stats.closed, color: '#6b7280' },
                            ].map(stat => (
                                <Card
                                    key={stat.label}
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        height: 40,
                                        px: 1.5,
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        borderLeft: `4px solid ${stat.color}`,
                                        borderRadius: 2,
                                        boxShadow: 'none',
                                        bgcolor: 'background.paper',
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Typography
                                            variant="h6"
                                            fontWeight={800}
                                            sx={{ color: stat.color, fontSize: '1.05rem', lineHeight: 1 }}
                                        >
                                            {stat.value}
                                        </Typography>
                                        <Typography
                                            variant="caption"
                                            color="text.secondary"
                                            sx={{ fontWeight: 600, fontSize: '0.72rem', whiteSpace: 'nowrap' }}
                                        >
                                            {stat.label}
                                        </Typography>
                                    </Box>
                                </Card>
                            ))}
                        </Box>

                        {/* Actions */}
                        <Button
                            variant="contained"
                            startIcon={<AddIcon />}
                            onClick={openCreate}
                            sx={{
                                borderRadius: 2,
                                fontWeight: 700,
                                height: 40,
                                width: { xs: '100%', sm: 'auto' },
                            }}
                        >
                            New Job
                        </Button>
                    </Box>

                    {/* Job cards */}
                    {loading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}><CircularProgress /></Box>
                    ) : displayJobs.length === 0 ? (
                        <Box sx={{ textAlign: 'center', py: 10 }}>
                            <WorkIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography color="text.secondary" fontWeight={600}>
                                {filter.search || filter.status ? 'No jobs match your filters' : 'No job openings yet'}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                {filter.search || filter.status
                                    ? 'Try adjusting the search or status filter.'
                                    : 'Create your first job posting to get started.'}
                            </Typography>
                        </Box>
                    ) : (
                        <Box sx={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(3, 1fr)',
                            gap: 3,
                        }}>
                            {displayJobs.map(job => (
                                <Card key={job.id} sx={{
                                    borderRadius: 3, height: '100%',
                                    display: 'flex', flexDirection: 'column',
                                    border: '1px solid', borderColor: 'divider',
                                    boxShadow: 'none',
                                    transition: 'box-shadow 0.2s, transform 0.15s',
                                    '&:hover': { boxShadow: '0 4px 20px rgba(0,0,0,0.1)', transform: 'translateY(-2px)' },
                                }}>
                                    <CardContent sx={{ flex: 1, p: 2.5, pb: 1.5 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5, flexWrap: 'wrap' }}>
                                            <StatusChip status={job.status} />
                                            <Chip
                                                label={job.employment_type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                                variant="outlined" size="small"
                                                sx={{ fontWeight: 500, fontSize: '0.7rem', height: 24 }}
                                            />
                                            <Chip
                                                icon={<WorkIcon sx={{ fontSize: '0.9rem' }} />}
                                                label={`${job.openings_count || 0} ${job.openings_count === 1 ? 'Opening' : 'Openings'}`}
                                                variant="outlined" size="small"
                                                sx={{ fontWeight: 600, fontSize: '0.7rem', height: 24 }}
                                            />
                                            {job.posting_type && job.posting_type !== 'external' && (
                                                <Chip
                                                    label={job.posting_type.charAt(0).toUpperCase() + job.posting_type.slice(1)}
                                                    size="small" variant="outlined" color="secondary"
                                                    sx={{ fontSize: '0.7rem', height: 24, ml: 'auto' }}
                                                />
                                            )}
                                        </Box>

                                        <Typography variant="h6" fontWeight={700} sx={{ fontSize: '1rem', lineHeight: 1.3, mb: 0.3 }}>
                                            {job.title}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem', mb: 2 }}>
                                            {[job.department, job.location_type?.replace(/_/g, '-')].filter(Boolean).join(' · ')}
                                        </Typography>

                                        <Box sx={{
                                            display: 'flex', border: '1px solid', borderColor: 'divider',
                                            borderRadius: 2, overflow: 'hidden', mb: 2,
                                        }}>
                                            {[
                                                { value: job.applications_count || 0, label: 'Applications' },
                                                { value: job.shortlisted_count || 0, label: 'Shortlisted' },
                                                { value: job.rejected_count || 0, label: 'Rejected' },
                                            ].map((s, i) => (
                                                <Box key={s.label} sx={{
                                                    flex: 1, textAlign: 'center', py: 1.25,
                                                    borderLeft: i > 0 ? '1px solid' : 'none',
                                                    borderColor: 'divider',
                                                }}>
                                                    <Typography fontWeight={800} sx={{ fontSize: '1.4rem', lineHeight: 1 }}>{s.value}</Typography>
                                                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem' }}>{s.label}</Typography>
                                                </Box>
                                            ))}
                                        </Box>

                                        <Stack spacing={0.75}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                <LocationOnIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
                                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.82rem' }}>
                                                    {job.location || 'Remote'} · {job.location_type?.replace('_', '-').replace(/\b\w/g, c => c.toUpperCase())}
                                                </Typography>
                                            </Box>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                <BusinessCenterIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
                                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.82rem' }}>
                                                    {job.experience_min}{job.experience_max ? `–${job.experience_max}` : '+'} yrs experience
                                                </Typography>
                                            </Box>
                                            {job.salary_min && (
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                    <Typography sx={{ fontSize: 13, color: 'text.secondary', fontWeight: 600 }}>₹</Typography>
                                                    <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.82rem' }}>
                                                        {Number(job.salary_min).toLocaleString('en-IN')}
                                                        {job.salary_max ? ` – ₹ ${Number(job.salary_max).toLocaleString('en-IN')}` : '+'}
                                                    </Typography>
                                                </Box>
                                            )}
                                            {job.published_at && (
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                    <AccessTimeIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
                                                    <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.82rem' }}>
                                                        Posted {new Date(job.published_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                                                    </Typography>
                                                </Box>
                                            )}
                                            {job.google_form_url && (
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                    <LinkIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
                                                    <Typography variant="body2" color="text.disabled" sx={{ fontSize: '0.78rem' }}>
                                                        Google Form linked
                                                    </Typography>
                                                </Box>
                                            )}
                                        </Stack>

                                        {job.skills_required?.length > 0 && (
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1.5 }}>
                                                {job.skills_required.slice(0, 5).map(skill => (
                                                    <Chip key={skill} label={skill} size="small" sx={{ fontSize: '0.68rem', height: 22 }} />
                                                ))}
                                                {job.skills_required.length > 5 && (
                                                    <Chip label={`+${job.skills_required.length - 5}`} size="small" variant="outlined" sx={{ fontSize: '0.68rem', height: 22 }} />
                                                )}
                                            </Box>
                                        )}
                                    </CardContent>

                                    <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
                                        <Button
                                            variant="contained" disableElevation size="small"
                                            startIcon={<PeopleIcon />}
                                            onClick={() => openCandidates(job)}
                                            sx={{ mr: 'auto', borderRadius: 2, fontSize: '0.75rem', fontWeight: 700 }}
                                        >
                                            Candidates
                                        </Button>
                                        {job.status === 'draft' && (
                                            <Tooltip title="Publish">
                                                <IconButton size="small" color="success" onClick={() => handlePublish(job.id)}>
                                                    <PublishIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                        {job.status === 'published' && (
                                            <Tooltip title="Close Job">
                                                <IconButton size="small" onClick={() => handleCloseJob(job.id)} sx={{ color: 'text.secondary' }}>
                                                    <CloseIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                        <Tooltip title="Edit">
                                            <IconButton size="small" onClick={() => openEdit(job)} sx={{ color: 'text.secondary' }}>
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Delete">
                                            <IconButton size="small" color="error" onClick={() => handleDelete(job.id)}>
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                </Card>
                            ))}
                        </Box>
                    )}
                </>
            )}

            <Popover
                open={Boolean(filterAnchorEl)}
                anchorEl={filterAnchorEl}
                onClose={() => setFilterAnchorEl(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                PaperProps={{
                    sx: {
                        width: 240,
                        maxHeight: 400,
                        display: 'flex',
                        flexDirection: 'column',
                        p: 1.5,
                        borderRadius: 2,
                        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                        border: '1px solid',
                        borderColor: 'divider',
                    }
                }}
            >
                {activeFilterCol && (
                    <>
                        {/* Sort Options */}
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 1 }}>
                            <Button
                                size="small"
                                color="inherit"
                                startIcon={<ArrowUpwardIcon sx={{ fontSize: 14 }} />}
                                onClick={() => handleSortClick('asc')}
                                sx={{ justifyContent: 'flex-start', textTransform: 'none', py: 0.5, px: 1, fontSize: '0.75rem' }}
                            >
                                Sort A to Z
                            </Button>
                            <Button
                                size="small"
                                color="inherit"
                                startIcon={<ArrowDownwardIcon sx={{ fontSize: 14 }} />}
                                onClick={() => handleSortClick('desc')}
                                sx={{ justifyContent: 'flex-start', textTransform: 'none', py: 0.5, px: 1, fontSize: '0.75rem' }}
                            >
                                Sort Z to A
                            </Button>
                        </Box>
                        <Divider sx={{ my: 0.5 }} />

                        {/* Search and Checkboxes */}
                        <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ mt: 0.5, mb: 0.5 }}>
                            FILTER BY VALUES
                        </Typography>
                        <TextField
                            size="small"
                            placeholder="Search values..."
                            value={valSearchQuery}
                            onChange={e => setValSearchQuery(e.target.value)}
                            fullWidth
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                                    </InputAdornment>
                                ),
                                style: { fontSize: '0.75rem', height: 28 }
                            }}
                            sx={{ mb: 1 }}
                        />

                        {/* Quick Select Buttons */}
                        <Box sx={{ display: 'flex', gap: 1, mb: 0.5 }}>
                            <Button
                                size="small"
                                onClick={handleSelectAllValues}
                                sx={{ textTransform: 'none', fontSize: '0.68rem', py: 0, px: 0.5, minWidth: 0 }}
                            >
                                Select All
                            </Button>
                            <Button
                                size="small"
                                onClick={handleClearAllValues}
                                sx={{ textTransform: 'none', fontSize: '0.68rem', py: 0, px: 0.5, minWidth: 0, color: 'error.main' }}
                            >
                                Clear
                            </Button>
                        </Box>

                        {/* Checkbox list */}
                        <Box sx={{ flex: 1, overflowY: 'auto', maxHeight: 180, display: 'flex', flexDirection: 'column', pr: 0.5 }}>
                            {filteredUniqueValues.length === 0 ? (
                                <Typography variant="caption" color="text.disabled" sx={{ p: 1, textAlign: 'center' }}>
                                    No values found
                                </Typography>
                            ) : (
                                filteredUniqueValues.map(val => (
                                    <Box key={val} sx={{ display: 'flex', alignItems: 'center', py: 0.25 }}>
                                        <Checkbox
                                            size="small"
                                            checked={tempSelectedValues.has(val)}
                                            onChange={() => handleToggleValue(val)}
                                            sx={{ p: 0.5 }}
                                        />
                                        <Typography variant="body2" sx={{ fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {val}
                                        </Typography>
                                    </Box>
                                ))
                            )}
                        </Box>

                        <Divider sx={{ my: 1 }} />

                        {/* Footer actions */}
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                            <Button
                                size="small"
                                color="inherit"
                                onClick={() => setFilterAnchorEl(null)}
                                sx={{ textTransform: 'none', fontSize: '0.7rem' }}
                            >
                                Cancel
                            </Button>
                            <Button
                                size="small"
                                variant="contained"
                                onClick={handleApplyFilter}
                                sx={{ textTransform: 'none', fontSize: '0.7rem', px: 1.5 }}
                            >
                                Apply
                            </Button>
                        </Box>
                    </>
                )}
            </Popover>

            <JobFormDialog
                open={dialogOpen}
                onClose={() => setDialogOpen(false)}
                editJob={editJob}
                onSaved={handleSaved}
            />
        </Box>
    );
}
