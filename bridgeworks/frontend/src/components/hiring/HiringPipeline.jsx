import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
    Box, Typography, Chip, CircularProgress, Avatar, Button,
    Dialog, DialogTitle, DialogContent, DialogActions,
    FormControl, InputLabel, Select, MenuItem, TextField,
    Paper, Tooltip, IconButton, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import WorkIcon from '@mui/icons-material/Work';
import PeopleIcon from '@mui/icons-material/People';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import {
    fetchJobs,
    fetchApplications,
    fetchJobPipelineStages,
    initJobPipeline,
    createJobPipelineStage,
    updateJobPipelineStage,
    deleteJobPipelineStage,
    setApplicationPipelineStage,
    convertToEmployee,
    reorderJobPipelineStages,
} from './hiringApi';

const COLORS = [
    '#6366f1', '#3b82f6', '#f59e0b', '#10b981',
    '#22c55e', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316',
];

const getInitials = (name) =>
    (name || '?').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

export default function HiringPipeline() {
    const location = useLocation();
    const navigate = useNavigate();
    const [jobs, setJobs] = useState([]);
    const [selectedJob, setSelectedJob] = useState('');
    const [stages, setStages] = useState([]);
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(false);
    const [jobsLoading, setJobsLoading] = useState(true);

    const [dragApp, setDragApp] = useState(null);
    const [dragOverStage, setDragOverStage] = useState(null);
    const [draggedColumnIndex, setDraggedColumnIndex] = useState(null);

    const [addColOpen, setAddColOpen] = useState(false);
    const [newColName, setNewColName] = useState('');
    const [newColColor, setNewColColor] = useState(COLORS[0]);
    const [addColSaving, setAddColSaving] = useState(false);

    const [editCol, setEditCol] = useState(null);
    const [editColSaving, setEditColSaving] = useState(false);

    const [deleteColId, setDeleteColId] = useState(null);
    const [deleteColSaving, setDeleteColSaving] = useState(false);

    const [initOpen, setInitOpen] = useState(false);
    const [initSaving, setInitSaving] = useState(false);

    const [converting, setConverting] = useState(null);
    const [moveDialog, setMoveDialog] = useState(null);

    useEffect(() => {
        fetchJobs().then(d => { setJobs(Array.isArray(d) ? d : []); setJobsLoading(false); });
    }, []);

    useEffect(() => {
        if (!jobsLoading && jobs.length > 0) {
            const stateJobId = location.state?.jobId;
            const params = new URLSearchParams(location.search);
            const queryJobId = params.get('jobId');
            const targetJobId = stateJobId || queryJobId;
            
            if (targetJobId) {
                const found = jobs.some(j => String(j.id) === String(targetJobId));
                if (found) {
                    setSelectedJob(String(targetJobId));
                } else if (jobs.length > 0) {
                    setSelectedJob(String(jobs[0].id));
                }
            } else if (jobs.length > 0) {
                setSelectedJob(String(jobs[0].id));
            }
        }
    }, [location, jobs, jobsLoading]);

    const loadPipeline = useCallback(async (jobId) => {
        setLoading(true);
        try {
            const [s, a] = await Promise.all([
                fetchJobPipelineStages(jobId),
                fetchApplications({ job_id: jobId }),
            ]);
            setStages(Array.isArray(s) ? s : []);
            setApplications(Array.isArray(a) ? a.filter(app => app.current_stage !== null) : []);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => {
        if (selectedJob) loadPipeline(selectedJob);
        else { setStages([]); setApplications([]); }
    }, [selectedJob, loadPipeline]);

    const getAppsForStage = (stageId) =>
        applications.filter(a =>
            a.pipeline_stage === stageId || a.pipeline_stage_detail?.id === stageId
        );
    const getUnplacedApps = () =>
        applications.filter(a => !a.pipeline_stage && !a.pipeline_stage_detail);

    const handleColDragStart = (e, index) => {
        e.stopPropagation();
        setDraggedColumnIndex(index);
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleColDragOver = (e, index) => {
        if (draggedColumnIndex === null) return;
        e.preventDefault();
    };

    const handleColDrop = async (e, targetIndex) => {
        if (draggedColumnIndex === null || draggedColumnIndex === targetIndex) return;
        e.preventDefault();
        const newStages = [...stages];
        const [draggedStage] = newStages.splice(draggedColumnIndex, 1);
        newStages.splice(targetIndex, 0, draggedStage);

        const updatedStages = newStages.map((s, idx) => ({ ...s, order: idx }));
        setStages(updatedStages);
        setDraggedColumnIndex(null);

        try {
            await reorderJobPipelineStages(selectedJob, updatedStages.map(s => ({ id: s.id, order: s.order })));
        } catch (err) {
            console.error("Failed to reorder columns:", err);
        }
    };

    const handleColDragEnd = () => {
        setDraggedColumnIndex(null);
    };

    const handleDragStart = (e, app) => { setDragApp(app); e.dataTransfer.effectAllowed = 'move'; };
    const handleDragOver = (e, stageId) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setDragOverStage(stageId); };
    const handleDrop = (e, stage) => {
        e.preventDefault(); setDragOverStage(null);
        if (!dragApp) return;
        const cur = dragApp.pipeline_stage_detail?.id ?? dragApp.pipeline_stage;
        if (cur === stage.id) return;
        setMoveDialog({ app: dragApp, toStage: stage });
        setDragApp(null);
    };
    const confirmMove = async () => {
        const { app, toStage } = moveDialog;
        try {
            const updated = await setApplicationPipelineStage(app.id, toStage.id);
            setApplications(prev => prev.map(a => a.id === app.id ? { ...a, ...updated } : a));
        } catch (e) { console.error(e); }
        setMoveDialog(null);
    };

    const handleAddColumn = async () => {
        if (!newColName.trim()) return;
        setAddColSaving(true);
        try {
            const stage = await createJobPipelineStage(selectedJob, { name: newColName.trim(), color: newColColor });
            setStages(prev => [...prev, stage]);
            setAddColOpen(false); setNewColName(''); setNewColColor(COLORS[0]);
        } catch (e) { console.error(e); } finally { setAddColSaving(false); }
    };
    const handleEditColumn = async () => {
        setEditColSaving(true);
        try {
            const updated = await updateJobPipelineStage(selectedJob, editCol.id, { name: editCol.name, color: editCol.color });
            setStages(prev => prev.map(s => s.id === editCol.id ? updated : s));
            setEditCol(null);
        } catch (e) { console.error(e); } finally { setEditColSaving(false); }
    };
    const handleDeleteColumn = async () => {
        const stageApps = getAppsForStage(deleteColId);
        if (stageApps.length > 0) {
            alert("Cannot delete column because it contains candidates.");
            setDeleteColId(null);
            return;
        }
        setDeleteColSaving(true);
        try {
            await deleteJobPipelineStage(selectedJob, deleteColId);
            setStages(prev => prev.filter(s => s.id !== deleteColId));
            setApplications(prev => prev.map(a =>
                (a.pipeline_stage === deleteColId || a.pipeline_stage_detail?.id === deleteColId)
                    ? { ...a, pipeline_stage: null, pipeline_stage_detail: null } : a
            ));
            setDeleteColId(null);
        } catch (e) { console.error(e); } finally { setDeleteColSaving(false); }
    };
    const handleInitPipeline = async () => {
        setInitSaving(true);
        try {
            const created = await initJobPipeline(selectedJob);
            setStages(Array.isArray(created) ? created : []);
            setInitOpen(false);
        } catch (e) { console.error(e); } finally { setInitSaving(false); }
    };
    const handleConvert = async (appId) => {
        setConverting(appId);
        try { const r = await convertToEmployee(appId); alert(r.message || 'Converted!'); }
        catch (e) { alert('Conversion failed'); } finally { setConverting(null); }
    };

    const renderCard = (app) => (
        <Paper key={app.id} draggable onDragStart={e => handleDragStart(e, app)} elevation={0}
            sx={{
                p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider', cursor: 'grab',
                '&:hover': { borderColor: 'primary.main', boxShadow: 2 }, '&:active': { cursor: 'grabbing' }, bgcolor: 'background.paper'
            }}>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <Avatar sx={{ bgcolor: 'primary.light', width: 32, height: 32, fontSize: 12, flexShrink: 0 }}>
                    {getInitials(app.candidate_detail?.name)}
                </Avatar>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" fontWeight={600} noWrap>{app.candidate_detail?.name || 'Unknown'}</Typography>
                    <Typography variant="caption" color="text.secondary" noWrap display="block">{app.candidate_detail?.email || '\u2014'}</Typography>
                    {app.candidate_detail?.current_company && (
                        <Typography variant="caption" color="text.secondary" noWrap display="block">{app.candidate_detail.current_company}</Typography>
                    )}
                    {app.candidate_detail?.total_experience_years != null && (
                        <Chip label={`${app.candidate_detail.total_experience_years} yrs`} size="small" variant="outlined" sx={{ height: 16, fontSize: 10, mt: 0.5 }} />
                    )}
                </Box>
                <DragIndicatorIcon sx={{ color: 'text.disabled', fontSize: 16, mt: 0.3, flexShrink: 0 }} />
            </Box>
            {app.pipeline_stage_detail?.name === 'Hired' && (
                <Button size="small" variant="outlined" color="success" fullWidth sx={{ mt: 1, fontSize: 11 }}
                    onClick={() => handleConvert(app.id)} disabled={converting === app.id}>
                    {converting === app.id ? <CircularProgress size={12} /> : 'Convert to Employee'}
                </Button>
            )}
        </Paper>
    );

    const selectedJobObj = jobs.find(j => j.id === Number(selectedJob));
    const unplaced = getUnplacedApps();

    return (
        <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, gap: 1.5 }}>
                <IconButton onClick={() => navigate('/team/hiring', { state: { jobId: selectedJob } })} size="small">
                    <ArrowBackIcon />
                </IconButton>
                <Typography variant="h6" fontWeight={700}>
                    {selectedJobObj ? selectedJobObj.title : 'Loading…'}
                </Typography>
                {selectedJob && stages.length > 0 && (
                    <Button variant="outlined" startIcon={<AddIcon />} size="small" onClick={() => setAddColOpen(true)} sx={{ borderRadius: 2, ml: 'auto' }}>
                        Add Column
                    </Button>
                )}
            </Box>

            {!selectedJob && !jobsLoading && (
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
                    <WorkIcon sx={{ fontSize: 64, color: 'text.disabled' }} />
                    <Typography color="text.secondary" variant="h6">Select a job to view its pipeline</Typography>
                    <Typography variant="body2" color="text.disabled">Each job has its own customizable Kanban pipeline.</Typography>
                </Box>
            )}

            {loading && <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><CircularProgress /></Box>}

            {!loading && selectedJob && stages.length === 0 && (
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
                    <PeopleIcon sx={{ fontSize: 64, color: 'text.disabled' }} />
                    <Typography variant="h6" color="text.secondary">No pipeline columns for this job yet</Typography>
                    <Typography variant="body2" color="text.disabled" sx={{ textAlign: 'center', maxWidth: 380 }}>
                        Initialize with default columns or build your own from scratch.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1.5 }}>
                        <Button variant="contained" onClick={() => setInitOpen(true)}>Initialize with Defaults</Button>
                        <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setAddColOpen(true)}>Add First Column</Button>
                    </Box>
                </Box>
            )}

            {!loading && selectedJob && stages.length > 0 && (
                <>
                    <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', flex: 1, pb: 2, alignItems: 'flex-start' }}>
                        {stages.map((stage, idx) => {
                            const stageApps = getAppsForStage(stage.id);
                            const isOver = dragOverStage === stage.id;
                            const isScreening = stage.name.toLowerCase() === 'screening';
                            return (
                                <Box key={stage.id}
                                    onDragOver={e => {
                                        if (draggedColumnIndex !== null) {
                                            handleColDragOver(e, idx);
                                        } else {
                                            handleDragOver(e, stage.id);
                                        }
                                    }}
                                    onDrop={e => {
                                        if (draggedColumnIndex !== null) {
                                            handleColDrop(e, idx);
                                        } else {
                                            handleDrop(e, stage);
                                        }
                                    }}
                                    onDragLeave={() => {
                                        if (draggedColumnIndex === null) {
                                            setDragOverStage(null);
                                        }
                                    }}
                                    sx={{
                                        minWidth: 260, maxWidth: 280, flex: '0 0 260px', display: 'flex', flexDirection: 'column',
                                        bgcolor: isOver ? 'action.selected' : 'background.default',
                                        borderRadius: 2, border: '2px solid',
                                        borderColor: isOver ? 'primary.main' : 'divider', transition: 'all 0.15s'
                                    }}>
                                    <Box
                                        draggable
                                        onDragStart={e => handleColDragStart(e, idx)}
                                        onDragEnd={handleColDragEnd}
                                        sx={{
                                            px: 2,
                                            py: 1.5,
                                            borderBottom: '1px solid',
                                            borderColor: 'divider',
                                            cursor: 'grab',
                                            '&:active': { cursor: 'grabbing' },
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 1
                                        }}
                                    >
                                        <DragIndicatorIcon sx={{ fontSize: 16, color: 'text.disabled', flexShrink: 0 }} />
                                        <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: stage.color, flexShrink: 0 }} />
                                        <Typography variant="subtitle2" fontWeight={700} noWrap sx={{ flex: 1 }}>{stage.name}</Typography>
                                        <Chip label={stageApps.length} size="small" sx={{ height: 20, fontSize: 11, flexShrink: 0 }} />
                                        <Tooltip title={isScreening ? "Screening column cannot be edited" : "Edit"}>
                                            <span>
                                                <IconButton size="small" disabled={isScreening} onClick={e => { e.stopPropagation(); setEditCol({ id: stage.id, name: stage.name, color: stage.color }); }} sx={{ p: 0.3 }}>
                                                    <EditIcon sx={{ fontSize: 14 }} />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                        <Tooltip title={isScreening ? "Screening column cannot be deleted" : (stageApps.length > 0 ? "Cannot delete column with candidates" : "Delete column")}>
                                            <span>
                                                <IconButton
                                                    size="small"
                                                    color="error"
                                                    onClick={e => { e.stopPropagation(); setDeleteColId(stage.id); }}
                                                    disabled={stageApps.length > 0 || isScreening}
                                                    sx={{ p: 0.3 }}
                                                >
                                                    <DeleteIcon sx={{ fontSize: 14 }} />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                    </Box>
                                    <Box sx={{ flex: 1, overflowY: 'auto', p: 1, display: 'flex', flexDirection: 'column', gap: 1, minHeight: 120 }}>
                                        {stageApps.map(renderCard)}
                                        {stageApps.length === 0 && (
                                            <Box sx={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', py: 3 }}>
                                                <Typography variant="caption" color="text.disabled">Drop candidates here</Typography>
                                            </Box>
                                        )}
                                    </Box>
                                </Box>
                            );
                        })}
                    </Box>
                </>
            )}

            {/* Add Column Dialog */}
            <Dialog open={addColOpen} onClose={() => setAddColOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Add Pipeline Column</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
                    <TextField autoFocus label="Column Name" fullWidth size="small"
                        value={newColName} onChange={e => setNewColName(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleAddColumn()} />
                    <Box>
                        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>Color</Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {COLORS.map(c => (
                                <Box key={c} onClick={() => setNewColColor(c)} sx={{
                                    width: 28, height: 28, borderRadius: '50%',
                                    bgcolor: c, cursor: 'pointer',
                                    outline: newColColor === c ? '3px solid #1976d2' : 'none', outlineOffset: 2
                                }} />
                            ))}
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddColOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleAddColumn} disabled={addColSaving || !newColName.trim()}>
                        {addColSaving ? <CircularProgress size={16} /> : 'Add'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Edit Column Dialog */}
            <Dialog open={!!editCol} onClose={() => setEditCol(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Edit Column</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '12px !important' }}>
                    {editCol && (<>
                        <TextField autoFocus label="Column Name" fullWidth size="small"
                            value={editCol.name} onChange={e => setEditCol(c => ({ ...c, name: e.target.value }))} />
                        <Box>
                            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>Color</Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                                {COLORS.map(c => (
                                    <Box key={c} onClick={() => setEditCol(col => ({ ...col, color: c }))} sx={{
                                        width: 28, height: 28,
                                        borderRadius: '50%', bgcolor: c, cursor: 'pointer',
                                        outline: editCol.color === c ? '3px solid #1976d2' : 'none', outlineOffset: 2
                                    }} />
                                ))}
                            </Box>
                        </Box>
                    </>)}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditCol(null)}>Cancel</Button>
                    <Button variant="contained" onClick={handleEditColumn} disabled={editColSaving || !editCol?.name?.trim()}>
                        {editColSaving ? <CircularProgress size={16} /> : 'Save'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete Column Confirm */}
            <Dialog open={!!deleteColId} onClose={() => setDeleteColId(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Delete Column?</DialogTitle>
                <DialogContent>
                    <Typography>Candidates in this column will become unplaced. This cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteColId(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={handleDeleteColumn} disabled={deleteColSaving}>
                        {deleteColSaving ? <CircularProgress size={16} /> : 'Delete'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Init Pipeline Dialog */}
            <Dialog open={initOpen} onClose={() => setInitOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle>Initialize Pipeline</DialogTitle>
                <DialogContent>
                    <Typography gutterBottom>Create default columns for <b>{selectedJobObj?.title}</b>:</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                        {['Applied', 'Screening', 'Interview', 'Offer', 'Hired', 'Rejected'].map(n => (
                            <Chip key={n} label={n} size="small" />
                        ))}
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                        You can rename, add, or delete columns afterwards.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setInitOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleInitPipeline} disabled={initSaving}>
                        {initSaving ? <CircularProgress size={16} /> : 'Initialize'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Move Confirm Dialog */}
            <Dialog open={!!moveDialog} onClose={() => setMoveDialog(null)} maxWidth="xs" fullWidth>
                <DialogTitle>Move Candidate</DialogTitle>
                <DialogContent>
                    {moveDialog && (
                        <Typography>Move <b>{moveDialog.app.candidate_detail?.name}</b> to <b>{moveDialog.toStage.name}</b>?</Typography>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setMoveDialog(null)}>Cancel</Button>
                    <Button variant="contained" onClick={confirmMove}>Move</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
