import React, { useState, useEffect, useCallback } from 'react';
import {
    Box, Card, CardContent, Typography, TextField, Button, Switch,
    FormControlLabel, Alert, Snackbar, CircularProgress, Chip,
    Select, MenuItem, FormControl, InputLabel
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';

export default function AnalyticsIntelligence() {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [draft, setDraft] = useState({ system_prompt: '', is_active: true, model_name: 'gemini-2.5-flash-lite' });
    const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
    const [hasChanges, setHasChanges] = useState(false);

    const fetchConfig = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiClient(`${BACKEND_URL}/api/analytics/config/`, { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                setConfig(data);
                setDraft({
                    system_prompt: data.system_prompt || '',
                    is_active: data.is_active ?? true,
                    model_name: data.model_name || 'gemini-2.5-flash-lite',
                });
                setHasChanges(false);
            }
        } catch (err) {
            console.error('Failed to fetch config:', err);
            setSnackbar({ open: true, message: 'Failed to load configuration', severity: 'error' });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchConfig(); }, [fetchConfig]);

    const handleSave = async () => {
        setSaving(true);
        try {
            const res = await apiClient(`${BACKEND_URL}/api/analytics/config/`, {
                method: 'PUT',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(draft),
            });
            if (res.ok) {
                const data = await res.json();
                setConfig(data);
                setHasChanges(false);
                setSnackbar({ open: true, message: 'Configuration saved successfully!', severity: 'success' });
            } else {
                setSnackbar({ open: true, message: 'Failed to save configuration', severity: 'error' });
            }
        } catch (err) {
            setSnackbar({ open: true, message: 'Network error while saving', severity: 'error' });
        } finally {
            setSaving(false);
        }
    };

    const handlePromptChange = (e) => {
        setDraft(prev => ({ ...prev, system_prompt: e.target.value }));
        setHasChanges(true);
    };

    const handleActiveToggle = (e) => {
        setDraft(prev => ({ ...prev, is_active: e.target.checked }));
        setHasChanges(true);
    };

    const handleModelChange = (e) => {
        setDraft(prev => ({ ...prev, model_name: e.target.value }));
        setHasChanges(true);
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ maxWidth: '100%', mx: 'auto', p: 3, display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3, flexShrink: 0 }}>
                <AutoAwesomeIcon sx={{ fontSize: 32, color: 'primary.main' }} />
                <Box>
                    <Typography variant="h5" fontWeight={700}>Conversational Analytics Configuration</Typography>
                    <Typography variant="body2" color="text.secondary">
                        Configure the behavior, prompt, and model for Thorfinn (Langchain SQL Agent)
                    </Typography>
                </Box>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <Box>
                    <Card variant="outlined">
                        {/* Status & Model Box */}
                        <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : 'grey.50' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                    <FormControlLabel
                                        control={<Switch checked={draft.is_active} onChange={handleActiveToggle} color="primary" />}
                                        label={<Typography fontWeight={600}>Agent {draft.is_active ? 'Active' : 'Inactive'}</Typography>}
                                    />
                                    <Chip
                                        label={draft.is_active ? 'LIVE' : 'OFF'}
                                        size="small"
                                        color={draft.is_active ? 'success' : 'default'}
                                        variant={draft.is_active ? 'filled' : 'outlined'}
                                    />
                                </Box>
                                <FormControl size="small" sx={{ minWidth: 200, bgcolor: 'background.paper' }}>
                                    <InputLabel>Gemini Model</InputLabel>
                                    <Select value={draft.model_name} onChange={handleModelChange} label="Gemini Model">
                                        <MenuItem value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</MenuItem>
                                        <MenuItem value="gemini-2.5-flash">Gemini 2.5 Flash</MenuItem>
                                        <MenuItem value="gemini-2.0-flash">Gemini 2.0 Flash</MenuItem>
                                        <MenuItem value="gemini-2.5-pro">Gemini 2.5 Pro</MenuItem>
                                        <MenuItem value="gemini-3-flash">Gemini 3 Flash</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box>
                        </Box>

                        {/* System Prompt Editor Box */}
                        <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 0 }}>
                            <Box sx={{ p: 2, pb: 1 }}>
                                <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                                    System Prompt
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Edit the master logic instructions for the Conversational AI agent below:
                                </Typography>
                            </Box>

                            <Box sx={{ px: 2, flexGrow: 1, overflow: 'auto' }}>
                                <TextField
                                    fullWidth
                                    multiline
                                    minRows={10}
                                    value={draft.system_prompt}
                                    onChange={handlePromptChange}
                                    placeholder="Enter the AI agent's system prompt here..."
                                    variant="outlined"
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                            fontSize: '0.85rem',
                                            lineHeight: 1.6,
                                            alignItems: 'flex-start'
                                        }
                                    }}
                                />
                            </Box>

                            <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : 'grey.50', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    {config?.updated_at && (
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            Last saved: {new Date(config.updated_at).toLocaleString('en-IN', {
                                                day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                            })}
                                        </Typography>
                                    )}
                                    <Typography variant="caption" color="text.secondary">
                                        {draft.system_prompt.length} characters
                                    </Typography>
                                </Box>
                                <Button
                                    variant="contained"
                                    disableElevation
                                    startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveIcon />}
                                    onClick={handleSave}
                                    disabled={saving || !hasChanges}
                                >
                                    {saving ? 'Saving...' : 'Save Configuration'}
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            </Box>

            <Snackbar
                open={snackbar.open}
                autoHideDuration={4000}
                onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
            >
                <Alert
                    onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
                    severity={snackbar.severity}
                    variant="filled"
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}
