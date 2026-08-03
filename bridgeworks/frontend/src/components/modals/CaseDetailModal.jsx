import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Paper, Grid, Divider, Chip, CircularProgress, Alert,
    TextField, MenuItem, Button, Dialog, DialogTitle, DialogContent, DialogActions,
    List, ListItem, ListItemText, Avatar
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import HistoryIcon from '@mui/icons-material/History';
import PersonIcon from '@mui/icons-material/Person';

// --- CONFIGURATION ---
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

// --- Helpers ---
const formatDate = (iso) => {
    if (!iso) return "-";
    return new Date(iso).toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
};

const getStatusColor = (status) => {
    switch (status) {
        case 'NEW_FIR': return 'error';
        case 'INVESTIGATING': return 'info';
        case 'PENDING_CUST': case 'PENDING_OP': return 'warning';
        case 'RESOLVED': return 'success';
        case 'CLOSED': return 'default';
        default: return 'default';
    }
};

const STATUS_CHOICES = [
    { value: 'NEW_FIR', label: 'New FIR Filed' },
    { value: 'INVESTIGATING', label: 'Investigating' },
    { value: 'PENDING_CUST', label: 'Pending Customer Reply' },
    { value: 'PENDING_OP', label: 'Pending Operations' },
    { value: 'RESOLVED', label: 'Resolved' },
    { value: 'CLOSED', label: 'Closed' },
];

const getStatusLabel = (value) => {
    const choice = STATUS_CHOICES.find(c => c.value === value);
    return choice ? choice.label : value;
};

export default function CaseDetailModal({ open, caseFile, onClose, onSaveSuccess }) {
    const [data, setData] = useState(caseFile);
    const [history, setHistory] = useState([]);

    const [updateForm, setUpdateForm] = useState({
        status: '',
        solution_provided_text: '',
        reshipment_order_number: '',
        remark: ''
    });

    const [loading, setLoading] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (open && caseFile) {
            setData(caseFile);
            setUpdateForm({
                status: caseFile.status,
                solution_provided_text: caseFile.solution_provided_text || '',
                reshipment_order_number: caseFile.reshipment_order_number || '',
                remark: ''
            });
            fetchHistory(caseFile.case_number);
        }
    }, [open, caseFile]);

    const fetchHistory = async (caseNumber) => {
        setHistoryLoading(true);
        try {
            // ✅ FIX 1: Added credentials: 'include' and BACKEND_URL
            const res = await apiClient(`${BACKEND_URL}/api/cases/${caseNumber}/comments/`, {
                credentials: "include"
            });

            if (res.ok) {
                const comments = await res.json();
                setHistory(comments);
            } else {
                console.error("Failed to load history:", res.status);
            }
        } catch (e) {
            console.error("Failed to load history", e);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleFormChange = (e) => {
        setUpdateForm({ ...updateForm, [e.target.name]: e.target.value });
    };

    const handleSaveUpdate = async () => {
        setLoading(true);
        setError(null);

        const oldStatusLabel = getStatusLabel(data.status);
        const newStatusLabel = getStatusLabel(updateForm.status);

        let changes = [];
        if (data.status !== updateForm.status) changes.push(`Status: ${oldStatusLabel} ➝ ${newStatusLabel}`);
        if (updateForm.solution_provided_text !== data.solution_provided_text) changes.push(`Solution updated`);
        if (updateForm.reshipment_order_number !== data.reshipment_order_number) changes.push(`Reshipment Order set to ${updateForm.reshipment_order_number}`);

        if (!updateForm.remark.trim() && changes.length === 0) {
            setError("Please enter a remark or change a field to log an update.");
            setLoading(false);
            return;
        }

        try {
            // ✅ FIX 2: Fetch a fresh CSRF token first
            
            if (!csrfRes.ok) throw new Error("Failed to authenticate session.");
            const csrfData = await csrfRes.json();
            const token = csrfData.csrftoken;

            const patchPayload = {
                status: updateForm.status,
                solution_provided_text: updateForm.solution_provided_text,
                reshipment_order_number: updateForm.reshipment_order_number,
                latest_remark: updateForm.remark
            };

            const patchRes = await apiClient(`${BACKEND_URL}/api/cases/${data.case_number}/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': token // Use fetched token
                },
                body: JSON.stringify(patchPayload),
                credentials: 'include'
            });

            if (!patchRes.ok) {
                const errData = await patchRes.json();
                throw new Error(errData.detail || 'Failed to update case details.');
            }

            const updatedCase = await patchRes.json();

            onSaveSuccess(updatedCase);
            onClose();

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // --- Helper to render message content ---
    const renderMessageContent = (message) => {
        const systemMarker = "(System:";
        let remarkText = message;
        let systemParts = [];

        if (message && message.includes(systemMarker)) {
            const parts = message.split(systemMarker);
            remarkText = parts[0].trim();
            const rawSystemText = parts[1].replace(/\)$/, '').trim();

            systemParts = rawSystemText.split(', ');
        }

        return (
            <Box>
                {remarkText && (
                    <Typography variant="body2" color="text.primary" sx={{ whiteSpace: 'pre-wrap', mb: systemParts.length ? 0.5 : 0 }}>
                        {remarkText}
                    </Typography>
                )}

                {systemParts.length > 0 && (
                    <Box sx={{ bgcolor: 'background.default', p: 1, borderRadius: 1, borderLeft: 3, borderColor: 'primary.main', mt: 0.5 }}>
                        <Typography variant="caption" display="block" sx={{ fontWeight: 'bold', color: 'primary.main', mb: 0.5, fontSize: '0.7rem', textTransform: 'uppercase' }}>
                            System Updates
                        </Typography>
                        {systemParts.map((part, index) => {
                            const splitIndex = part.indexOf(':');
                            let label = part;
                            let value = "";
                            if (splitIndex !== -1) {
                                label = part.substring(0, splitIndex);
                                value = part.substring(splitIndex + 1);
                            }

                            return (
                                <Typography key={index} variant="caption" display="block" sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}>
                                    {splitIndex !== -1 ? (
                                        <span>
                                            <strong>{label}:</strong>{value}
                                        </span>
                                    ) : (
                                        part
                                    )}
                                </Typography>
                            );
                        })}
                    </Box>
                )}
            </Box>
        );
    };

    if (!data) return null;

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg" scroll="paper">
            {/* HEADER */}
            <DialogTitle sx={{ bgcolor: 'background.default', borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                    <Typography variant="h6" component="span" fontWeight="bold">
                        Case #{data.case_number}
                    </Typography>
                    <Typography variant="caption" sx={{ ml: 2, color: 'text.secondary' }}>
                        Filed on {formatDate(data.created_at)}
                    </Typography>
                </Box>
                <Chip label={data.status_display} color={getStatusColor(data.status)} />
            </DialogTitle>

            <DialogContent dividers sx={{ p: 0, height: '70vh' }}>
                <Grid container sx={{ height: '100%' }}>

                    {/* --- LEFT COLUMN: CONTEXT & HISTORY --- */}
                    <Grid item xs={12} md={7} sx={{ height: '100%', overflowY: 'auto', borderRight: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
                        <Box sx={{ p: 3 }}>
                            {/* Order Summary */}
                            <Paper variant="outlined" sx={{ p: 1, mb: 3, bgcolor: 'background.default' }}>
                                <Grid container spacing={2}>
                                    <Grid item xs={6}>
                                        <Typography variant="caption" color="text.secondary">Order</Typography>
                                        <Typography variant="body2" fontWeight="bold">#{data.order_details?.order_number}</Typography>
                                    </Grid>
                                    <Grid item xs={6}>
                                        <Typography variant="caption" color="text.secondary">Customer</Typography>
                                        <Typography variant="body2" fontWeight="bold">{data.order_details?.customer_first_name}</Typography>
                                    </Grid>
                                    <Grid item xs={6}>
                                        <Typography variant="caption" color="text.secondary">Issue</Typography>
                                        <Typography variant="body2">{data.type_display}</Typography>
                                    </Grid>
                                    <Grid item xs={6}>
                                        <Typography variant="caption" color="text.secondary">Agent</Typography>
                                        <Typography variant="body2">{data.registered_by_name}</Typography>
                                    </Grid>
                                </Grid>
                            </Paper>

                            {/* Problem Description */}
                            <Typography variant="subtitle2" color="primary" gutterBottom>PROBLEM DESCRIPTION</Typography>
                            <Typography variant="body2" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
                                {data.description}
                            </Typography>

                            {data.images?.length > 0 && (
                                <Box sx={{ mb: 3 }}>
                                    <Typography variant="caption" fontWeight="bold">Evidence:</Typography>
                                    <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                                        {data.images.map((img) => (
                                            <Box component="img" key={img.id} src={img.image} alt="Evidence" sx={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 0.5, border: 1, borderColor: 'divider' }} />
                                        ))}
                                    </Box>
                                </Box>
                            )}

                            <Divider sx={{ my: 3 }} />

                            {/* Current Solution Status (Read Only) */}
                            <Box sx={{ mb: 3 }}>
                                <Typography variant="subtitle2" color="primary" gutterBottom>CURRENT SOLUTION DATA</Typography>
                                <Grid container spacing={2}>
                                    <Grid item xs={12}>
                                        <Typography variant="caption" color="text.secondary">Solution Provided Text:</Typography>
                                        <Typography variant="body2">{data.solution_provided_text || "No solution text recorded yet."}</Typography>
                                    </Grid>
                                    <Grid item xs={12}>
                                        <Typography variant="caption" color="text.secondary">Reshipment Order #:</Typography>
                                        <Typography variant="body2">{data.reshipment_order_number || "N/A"}</Typography>
                                    </Grid>
                                </Grid>
                            </Box>

                            <Divider sx={{ my: 3 }} />

                            {/* UPDATE HISTORY / AUDIT TRAIL */}
                            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <HistoryIcon color="action" /> Update History
                            </Typography>

                            {historyLoading ? <CircularProgress size={20} /> : (
                                <List dense sx={{ bgcolor: 'background.default', borderRadius: 2 }}>
                                    {history.length === 0 ? (
                                        <ListItem><ListItemText primary="No updates recorded." /></ListItem>
                                    ) : (
                                        history.map((item) => (
                                            <React.Fragment key={item.id}>
                                                <ListItem alignItems="flex-start">
                                                    <Box sx={{ mr: 2, mt: 0.5 }}>
                                                        <Avatar sx={{ width: 24, height: 24, fontSize: '0.7rem' }}>
                                                            <PersonIcon fontSize="inherit" />
                                                        </Avatar>
                                                    </Box>
                                                    <ListItemText
                                                        primary={
                                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                                                <Typography variant="subtitle2" fontWeight="bold">{item.user_name}</Typography>
                                                                <Typography variant="caption" color="text.secondary">{formatDate(item.created_at)}</Typography>
                                                            </Box>
                                                        }
                                                        secondary={renderMessageContent(item.message)}
                                                        disableTypography
                                                    />
                                                </ListItem>
                                                <Divider variant="inset" component="li" />
                                            </React.Fragment>
                                        ))
                                    )}
                                </List>
                            )}
                        </Box>
                    </Grid>

                    {/* --- RIGHT COLUMN: ACTION FORM --- */}
                    <Grid item xs={12} md={5} sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
                        <Box sx={{ p: 3, flex: 1, overflowY: 'auto' }}>
                            <Typography variant="h6" gutterBottom color="primary">
                                Log New Update
                            </Typography>
                            <Typography variant="caption" color="text.secondary" paragraph>
                                Talked to the customer? Changing the status? Enter details here to update the case and save to history.
                            </Typography>

                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                                <TextField
                                    select
                                    label="Update Status"
                                    name="status"
                                    value={updateForm.status}
                                    onChange={handleFormChange}
                                    fullWidth
                                    size="small"
                                    helperText="Current Status of the case"
                                >
                                    {STATUS_CHOICES.map(opt => (
                                        <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                    ))}
                                </TextField>

                                <TextField
                                    label="Solution Provided"
                                    name="solution_provided_text"
                                    value={updateForm.solution_provided_text}
                                    onChange={handleFormChange}
                                    fullWidth
                                    size="small"
                                    multiline
                                    rows={2}
                                    placeholder="e.g. Refund processed..."
                                    helperText="Update the official solution text"
                                />

                                <TextField
                                    label="Reshipment Order #"
                                    name="reshipment_order_number"
                                    value={updateForm.reshipment_order_number}
                                    onChange={handleFormChange}
                                    fullWidth
                                    size="small"
                                    placeholder="If applicable"
                                />

                                <Divider sx={{ my: 1 }} />

                                <TextField
                                    label="Add Remark / Note"
                                    name="remark"
                                    value={updateForm.remark}
                                    onChange={handleFormChange}
                                    fullWidth
                                    multiline
                                    rows={4}
                                    placeholder="Describe your interaction or action taken..."
                                    required
                                />
                            </Box>
                        </Box>

                        {/* Footer Action */}
                        <Box sx={{ p: 3, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
                            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                            <Button
                                variant="contained"
                                color="primary"
                                fullWidth
                                size="large"
                                onClick={handleSaveUpdate}
                                disabled={loading}
                                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
                            >
                                {loading ? "Saving..." : "Save & Log Update"}
                            </Button>
                        </Box>
                    </Grid>

                </Grid>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}