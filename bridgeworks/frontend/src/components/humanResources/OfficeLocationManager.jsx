import React, { useState, useEffect, useRef } from 'react';
import {
    Box, Grid, Paper, Typography, Button, TextField, List, ListItem,
    ListItemButton, ListItemText, ListItemSecondaryAction, IconButton,
    Dialog, DialogTitle, DialogContent, DialogActions, Stack, Chip,
    Alert, CircularProgress, Divider, InputAdornment, Tooltip, FormControlLabel, Switch
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import MapIcon from '@mui/icons-material/Map';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import BusinessIcon from '@mui/icons-material/Business';
import GpsFixedIcon from '@mui/icons-material/GpsFixed';
import SecurityIcon from '@mui/icons-material/Security';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import {
    listHrOffices, createHrOffice, updateHrOffice, deleteHrOffice,
    geocodeHrOffice, createHrOfficeIp, deleteHrOfficeIp, detectMyIp
} from '../mydesk/mydeskService';
import { apiClient } from '../../apiClient';

// Fix default leaflet marker icon issue in production bundles
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

export default function OfficeLocationManager() {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';

    const [offices, setOffices] = useState([]);
    const [selectedOffice, setSelectedOffice] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Global Org Settings States
    const [globalIdleEnabled, setGlobalIdleEnabled] = useState(true);
    const [globalIdleMinutes, setGlobalIdleMinutes] = useState(15);
    const [savingGlobal, setSavingGlobal] = useState(false);

    // Form states
    const [officeDialogOpen, setOfficeDialogOpen] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [formData, setFormData] = useState({
        name: '', address: '', latitude: '', longitude: '', geofence_radius_meters: 200, idle_timeout_enabled: true, idle_timeout_minutes: 15
    });
    const [formLoading, setFormLoading] = useState(false);

    // Whitelist IP Form state
    const [newIpAddress, setNewIpAddress] = useState('');
    const [newIpLabel, setNewIpLabel] = useState('');
    const [detectedIp, setDetectedIp] = useState('');
    const [detectingIp, setDetectingIp] = useState(false);
    const [ipLoading, setIpLoading] = useState(false);

    // Leaflet map refs
    const mapContainerRef = useRef(null);
    const mapInstanceRef = useRef(null);
    const markerRef = useRef(null);
    const circleRef = useRef(null);

    useEffect(() => {
        loadOffices();
        fetchClientIp();
        fetchGlobalSettings();
    }, []);

    const fetchGlobalSettings = async () => {
        try {
            const response = await apiClient('/api/shop-profile/', { credentials: 'include' });
            if (response.ok) {
                const data = await response.json();
                setGlobalIdleEnabled(data.global_idle_timeout_enabled !== false);
                setGlobalIdleMinutes(data.global_idle_timeout_minutes || 15);
            }
        } catch (err) {
            console.error("Failed to fetch global settings:", err);
        }
    };

    const handleSaveGlobalSettings = async () => {
        setSavingGlobal(true);
        try {
            const response = await apiClient('/api/shop-profile/', {
                method: 'PUT',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    global_idle_timeout_enabled: globalIdleEnabled,
                    global_idle_timeout_minutes: globalIdleMinutes
                })
            });
            if (response.ok) {
                alert('Organization-Wide Defaults saved successfully!');
            } else {
                const errData = await response.json();
                alert(errData.error || 'Failed to save global defaults.');
            }
        } catch (err) {
            alert('Connection error. Failed to save global defaults.');
        } finally {
            setSavingGlobal(false);
        }
    };

    // Re-initialize map on selecting an office or latitude/longitude update
    useEffect(() => {
        if (!selectedOffice || !mapContainerRef.current) {
            // Clean up map if no office is selected
            if (mapInstanceRef.current) {
                mapInstanceRef.current.remove();
                mapInstanceRef.current = null;
                markerRef.current = null;
                circleRef.current = null;
            }
            return;
        }

        const lat = parseFloat(selectedOffice.latitude);
        const lng = parseFloat(selectedOffice.longitude);
        const radius = selectedOffice.geofence_radius_meters || 200;

        if (Number.isNaN(lat) || Number.isNaN(lng)) {
            // No valid coordinates to map
            if (mapInstanceRef.current) {
                mapInstanceRef.current.remove();
                mapInstanceRef.current = null;
            }
            return;
        }

        // Initialize leaflet map
        if (!mapInstanceRef.current) {
            mapInstanceRef.current = L.map(mapContainerRef.current).setView([lat, lng], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(mapInstanceRef.current);
        } else {
            mapInstanceRef.current.setView([lat, lng], 15);
        }

        // Update marker position
        if (markerRef.current) {
            markerRef.current.setLatLng([lat, lng]);
        } else {
            markerRef.current = L.marker([lat, lng]).addTo(mapInstanceRef.current);
        }

        // Update geofence circle
        if (circleRef.current) {
            circleRef.current.setLatLng([lat, lng]);
            circleRef.current.setRadius(radius);
        } else {
            circleRef.current = L.circle([lat, lng], {
                radius: radius,
                color: '#3b82f6',
                fillColor: '#60a5fa',
                fillOpacity: 0.35,
                weight: 2
            }).addTo(mapInstanceRef.current);
        }

        // Force relayout after initialization
        setTimeout(() => {
            if (mapInstanceRef.current) {
                mapInstanceRef.current.invalidateSize();
            }
        }, 100);

    }, [selectedOffice]);

    const loadOffices = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await listHrOffices();
            const list = Array.isArray(data?.offices) ? data.offices : [];
            setOffices(list);
            if (list.length > 0) {
                setSelectedOffice(list[0]);
            } else {
                setSelectedOffice(null);
            }
        } catch (err) {
            setError(err?.message || 'Failed to fetch office locations.');
        } finally {
            setLoading(false);
        }
    };

    const fetchClientIp = async () => {
        setDetectingIp(true);
        try {
            const res = await detectMyIp();
            if (res?.ip) setDetectedIp(res.ip);
        } catch (e) {
            console.error('Failed to auto-detect client IP', e);
        } finally {
            setDetectingIp(false);
        }
    };

    const handleOpenAddDialog = () => {
        setIsEditing(false);
        setFormData({
            name: '', address: '', latitude: '', longitude: '', geofence_radius_meters: 200, idle_timeout_enabled: true, idle_timeout_minutes: 15, require_dual_signal: false
        });
        setOfficeDialogOpen(true);
    };

    const handleOpenEditDialog = (office) => {
        setIsEditing(true);
        setFormData({
            id: office.id,
            name: office.name,
            address: office.address || '',
            latitude: office.latitude || '',
            longitude: office.longitude || '',
            geofence_radius_meters: office.geofence_radius_meters || 200,
            idle_timeout_enabled: office.idle_timeout_enabled !== false,
            idle_timeout_minutes: office.idle_timeout_minutes || 15,
            require_dual_signal: !!office.require_dual_signal
        });
        setOfficeDialogOpen(true);
    };

    const handleSaveOffice = async () => {
        if (!formData.name.trim()) return;
        setFormLoading(true);
        try {
            const payload = {
                name: formData.name,
                address: formData.address,
                geofence_radius_meters: parseInt(formData.geofence_radius_meters) || 200,
                latitude: formData.latitude !== '' ? parseFloat(formData.latitude) : null,
                longitude: formData.longitude !== '' ? parseFloat(formData.longitude) : null,
                idle_timeout_enabled: !!formData.idle_timeout_enabled,
                idle_timeout_minutes: parseInt(formData.idle_timeout_minutes) || 15,
                require_dual_signal: !!formData.require_dual_signal
            };

            let updatedOffice = null;
            if (isEditing) {
                updatedOffice = await updateHrOffice(formData.id, payload);
            } else {
                updatedOffice = await createHrOffice(payload);
            }

            setOfficeDialogOpen(false);
            await loadOffices();

            // Auto-select saved office
            if (updatedOffice) {
                const found = offices.find(o => o.id === updatedOffice.id) || updatedOffice;
                setSelectedOffice(found);
            }
        } catch (err) {
            setError(err?.message || 'Failed to save office location.');
        } finally {
            setFormLoading(false);
        }
    };

    const handleDeleteOffice = async (officeId) => {
        if (!window.confirm('Are you sure you want to delete this office location? All whitelisted IPs for this office will be removed.')) return;
        try {
            await deleteHrOffice(officeId);
            await loadOffices();
        } catch (err) {
            setError(err?.message || 'Failed to delete office.');
        }
    };

    const handleGeocode = async () => {
        if (!formData.address.trim()) return;
        setFormLoading(true);
        try {
            const query = encodeURIComponent(formData.address.trim());
            const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${query}&format=json&limit=1`, {
                headers: { 'User-Agent': 'BridgeWorksAttendance/1.0' }
            });
            const data = await res.json();
            if (data && data.length > 0) {
                setFormData(prev => ({
                    ...prev,
                    latitude: parseFloat(data[0].lat).toFixed(7),
                    longitude: parseFloat(data[0].lon).toFixed(7)
                }));
            } else {
                alert('Geocoding failed. Address not found. Please enter coordinates manually.');
            }
        } catch (e) {
            alert('Geocoding request failed. Please configure lat/lng coordinates manually.');
        } finally {
            setFormLoading(false);
        }
    };

    const handleAddIp = async () => {
        if (!selectedOffice || !newIpAddress.trim()) return;
        setIpLoading(true);
        try {
            const ipPayload = {};
            if (newIpAddress.trim().includes('/')) {
                ipPayload.ip_cidr = newIpAddress.trim();
            } else {
                ipPayload.ip_address = newIpAddress.trim();
            }
            ipPayload.label = newIpLabel.trim();

            const updated = await createHrOfficeIp(selectedOffice.id, ipPayload);
            setNewIpAddress('');
            setNewIpLabel('');
            
            // Refresh selection payload details
            if (updated) {
                setOffices(prev => prev.map(o => o.id === updated.id ? updated : o));
                setSelectedOffice(updated);
            }
        } catch (err) {
            alert(err?.message || 'Failed to register IP address.');
        } finally {
            setIpLoading(false);
        }
    };

    const handleDeleteIp = async (ipId) => {
        if (!selectedOffice) return;
        try {
            await deleteHrOfficeIp(selectedOffice.id, ipId);
            // Reload office to refresh whitelisted IPs
            const data = await listHrOffices();
            const list = Array.isArray(data?.offices) ? data.offices : [];
            setOffices(list);
            const found = list.find(o => o.id === selectedOffice.id);
            if (found) setSelectedOffice(found);
        } catch (err) {
            alert(err?.message || 'Failed to delete whitelisted IP.');
        }
    };

    return (
        <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 3 }}>
            {error && (
                <Alert severity="error" sx={{ borderRadius: '12px', boxShadow: '0 4px 12px rgba(239, 68, 68, 0.08)' }}>
                    {error}
                </Alert>
            )}

            {/* Explanatory Header */}
            <Paper 
                variant="outlined"
                sx={{ 
                    p: 2.5, 
                    borderRadius: '16px',
                    bgcolor: isDarkMode ? 'rgba(30, 41, 59, 0.4)' : 'rgba(248, 250, 252, 0.8)',
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
                    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.01)'
                }}
            >
                <Stack direction="row" spacing={2} alignItems="center">
                    <Box sx={{ 
                        p: 1.5, 
                        borderRadius: '12px', 
                        bgcolor: 'primary.main', 
                        color: 'white',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <BusinessIcon />
                    </Box>
                    <Box>
                        <Typography variant="h6" fontWeight={800} sx={{ color: isDarkMode ? '#f8fafc' : '#0f172a' }}>
                            Office Locations &amp; Network Configuration
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            Configure physical coordinates with radial safety geofencing or whitelist specific corporate network gateways (IPs) to enable automated employee check-ins and check-outs.
                        </Typography>
                    </Box>
                </Stack>
            </Paper>

            {/* Organization-Wide Defaults */}
            <Paper 
                variant="outlined"
                sx={{ 
                    p: 2.5, 
                    borderRadius: '16px',
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
                    boxShadow: '0 4px 24px rgba(15, 23, 42, 0.01)',
                    bgcolor: isDarkMode ? 'rgba(30, 41, 59, 0.2)' : 'rgba(255, 255, 255, 0.5)',
                }}
            >
                <Typography variant="subtitle2" fontWeight={800} sx={{ letterSpacing: '0.02em', textTransform: 'uppercase', fontSize: '0.75rem', color: 'text.secondary', mb: 2 }}>
                    Organization-Wide Defaults
                </Typography>
                <Grid container spacing={3} alignItems="center">
                    <Grid item xs={12} md={4}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={globalIdleEnabled}
                                    onChange={(e) => setGlobalIdleEnabled(e.target.checked)}
                                    color="primary"
                                />
                            }
                            label={
                                <Box sx={{ ml: 1 }}>
                                    <Typography variant="body2" fontWeight={700}>
                                        Enable Global Inactivity Alarm
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Default alarm setting for all locations/teammates
                                    </Typography>
                                </Box>
                            }
                        />
                    </Grid>
                    <Grid item xs={12} sm={6} md={4}>
                        <TextField
                            size="small"
                            type="number"
                            label="Default Idle Timeout (Minutes)"
                            value={globalIdleMinutes}
                            onChange={(e) => setGlobalIdleMinutes(Math.max(1, parseInt(e.target.value) || 0))}
                            disabled={!globalIdleEnabled}
                            fullWidth
                            InputProps={{ inputProps: { min: 1 } }}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                    </Grid>
                    <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex', justifyContent: { xs: 'flex-start', sm: 'flex-end' } }}>
                        <Button
                            variant="contained"
                            onClick={handleSaveGlobalSettings}
                            disabled={savingGlobal}
                            sx={{ 
                                borderRadius: '8px', 
                                textTransform: 'none', 
                                fontWeight: 700,
                                px: 3,
                                py: 1,
                                boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)' 
                            }}
                        >
                            {savingGlobal ? 'Saving...' : 'Save Global Defaults'}
                        </Button>
                    </Grid>
                </Grid>
            </Paper>

            <Grid container spacing={3}>
                {/* Left side list */}
                <Grid item xs={12} md={4}>
                    <Paper 
                        variant="outlined" 
                        sx={{ 
                            borderRadius: '16px', 
                            height: 520, 
                            display: 'flex', 
                            flexDirection: 'column',
                            boxShadow: '0 4px 24px rgba(15, 23, 42, 0.02)',
                            borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
                            overflow: 'hidden'
                        }}
                    >
                        <Box sx={{ 
                            p: 2, 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center', 
                            borderBottom: '1px solid', 
                            borderColor: 'divider', 
                            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.01)'
                        }}>
                            <Typography variant="subtitle2" fontWeight={800} sx={{ color: 'text.primary', letterSpacing: '0.02em', textTransform: 'uppercase', fontSize: '0.75rem' }}>
                                Offices
                            </Typography>
                            <Button 
                                variant="contained" 
                                size="small" 
                                startIcon={<AddIcon />} 
                                onClick={handleOpenAddDialog}
                                sx={{ 
                                    borderRadius: '8px', 
                                    textTransform: 'none', 
                                    fontWeight: 700,
                                    boxShadow: '0 2px 8px rgba(37, 99, 235, 0.25)' 
                                }}
                            >
                                Add Office
                            </Button>
                        </Box>
                        {loading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
                                <CircularProgress size={30} />
                            </Box>
                        ) : (
                            <List sx={{ overflowY: 'auto', flex: 1, p: 1.5 }}>
                                {offices.map((office) => (
                                    <ListItem
                                        key={office.id}
                                        disablePadding
                                        secondaryAction={
                                            <Stack 
                                                className="action-buttons" 
                                                direction="row" 
                                                spacing={0.5} 
                                                sx={{ 
                                                    mr: 1,
                                                    opacity: 0,
                                                    transition: 'opacity 0.2s ease-in-out',
                                                    bgcolor: isDarkMode ? 'rgba(15, 23, 42, 0.85)' : 'rgba(255, 255, 255, 0.85)',
                                                    borderRadius: '8px',
                                                    p: '2px',
                                                    border: '1px solid',
                                                    borderColor: 'divider',
                                                    backdropFilter: 'blur(4px)'
                                                }}
                                            >
                                                <IconButton size="small" color="primary" onClick={() => handleOpenEditDialog(office)}>
                                                    <EditIcon sx={{ fontSize: '1.05rem' }} />
                                                </IconButton>
                                                <IconButton size="small" color="error" onClick={() => handleDeleteOffice(office.id)}>
                                                    <DeleteIcon sx={{ fontSize: '1.05rem' }} />
                                                </IconButton>
                                            </Stack>
                                        }
                                        sx={{ 
                                            mb: 1.25, 
                                            borderRadius: '10px', 
                                            overflow: 'hidden',
                                            '&:hover .action-buttons': { opacity: 1 }
                                        }}
                                    >
                                        <ListItemButton
                                            selected={selectedOffice?.id === office.id}
                                            onClick={() => setSelectedOffice(office)}
                                            sx={{ 
                                                pr: 9,
                                                borderRadius: '10px',
                                                borderLeft: selectedOffice?.id === office.id ? '4px solid #2563eb' : '4px solid transparent',
                                                transition: 'all 0.2s',
                                                bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.01)' : 'rgba(0, 0, 0, 0.005)',
                                                border: '1px solid',
                                                borderColor: selectedOffice?.id === office.id ? 'primary.main' : 'divider',
                                                '&.Mui-selected': {
                                                    bgcolor: isDarkMode ? 'rgba(37, 99, 235, 0.08)' : 'rgba(37, 99, 235, 0.04)',
                                                    '&:hover': {
                                                        bgcolor: isDarkMode ? 'rgba(37, 99, 235, 0.12)' : 'rgba(37, 99, 235, 0.06)',
                                                    }
                                                }
                                            }}
                                        >
                                            <ListItemText
                                                primary={office.name}
                                                primaryTypographyProps={{ fontWeight: 700, fontSize: '0.88rem', color: selectedOffice?.id === office.id ? 'primary.main' : 'text.primary' }}
                                                secondary={
                                                    <Typography variant="caption" color="text.secondary" noWrap display="block" sx={{ maxWidth: 170, mt: 0.5 }}>
                                                        {office.address || 'No address configured'}
                                                    </Typography>
                                                }
                                            />
                                        </ListItemButton>
                                    </ListItem>
                                ))}
                                {offices.length === 0 && (
                                    <Box sx={{ p: 4, textAlign: 'center' }}>
                                        <Typography variant="body2" color="text.secondary">No offices configured yet.</Typography>
                                    </Box>
                                )}
                            </List>
                        )}
                    </Paper>
                </Grid>

                {/* Right side geofence and whitelisting */}
                <Grid item xs={12} md={8}>
                    {selectedOffice ? (
                        <Grid container spacing={3}>
                            {/* Map Geofence Preview */}
                            <Grid item xs={12} lg={6}>
                                <Paper 
                                    variant="outlined" 
                                    sx={{ 
                                        p: 2.5, 
                                        borderRadius: '16px', 
                                        height: 520, 
                                        display: 'flex', 
                                        flexDirection: 'column',
                                        boxShadow: '0 4px 24px rgba(15, 23, 42, 0.02)',
                                        borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'
                                    }}
                                >
                                    <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
                                        <GpsFixedIcon color="primary" sx={{ fontSize: '1.25rem' }} />
                                        <Typography variant="subtitle2" fontWeight={800} sx={{ letterSpacing: '0.02em', textTransform: 'uppercase', fontSize: '0.75rem', color: 'text.secondary' }}>
                                            Geofence Circle ({selectedOffice.name})
                                        </Typography>
                                    </Stack>
                                    
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                                        Verification radius constraints mapping for check-ins. If configured, users must be inside this zone.
                                    </Typography>

                                    {/* Parameter Metric Grid */}
                                    <Grid container spacing={1} mb={2}>
                                        <Grid item xs={3}>
                                            <Box sx={{ p: 1, borderRadius: '8px', bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.02)', textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
                                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }} display="block">Radius</Typography>
                                                <Typography variant="body2" fontWeight={700} color="primary.main">{selectedOffice.geofence_radius_meters}m</Typography>
                                            </Box>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Box sx={{ p: 1, borderRadius: '8px', bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.02)', textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
                                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }} display="block">Idle Alarm</Typography>
                                                <Typography variant="body2" fontWeight={700} color="primary.main" noWrap>
                                                    {selectedOffice.idle_timeout_enabled ? `${selectedOffice.idle_timeout_minutes} min` : 'Disabled'}
                                                </Typography>
                                            </Box>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Box sx={{ p: 1, borderRadius: '8px', bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.02)', textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
                                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }} display="block">Coordinates</Typography>
                                                <Typography variant="body2" fontWeight={700} color="primary.main" noWrap sx={{ textOverflow: 'ellipsis' }}>
                                                    {selectedOffice.latitude ? `${parseFloat(selectedOffice.latitude).toFixed(3)}, ${parseFloat(selectedOffice.longitude).toFixed(3)}` : '—'}
                                                </Typography>
                                            </Box>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Box sx={{ p: 1, borderRadius: '8px', bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.02)', textAlign: 'center', border: '1px solid', borderColor: 'divider' }}>
                                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }} display="block">Verification</Typography>
                                                <Typography variant="body2" fontWeight={700} color="primary.main" noWrap>
                                                    {selectedOffice.require_dual_signal ? 'IP + GPS' : 'IP or GPS'}
                                                </Typography>
                                            </Box>
                                        </Grid>
                                    </Grid>

                                    {selectedOffice.latitude && selectedOffice.longitude ? (
                                        <Box
                                            ref={mapContainerRef}
                                            sx={{
                                                flex: 1,
                                                minHeight: 250,
                                                width: '100%',
                                                borderRadius: '12px',
                                                overflow: 'hidden',
                                                border: '1px solid',
                                                borderColor: 'divider',
                                                zIndex: 1
                                            }}
                                        />
                                    ) : (
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, bgcolor: 'action.hover', borderRadius: '12px', border: '1px dashed', borderColor: 'divider', p: 3 }}>
                                            <Typography variant="caption" align="center" color="text.secondary">
                                                No GPS coordinates configured. Click Edit Office to configure coordinates or address geocoding.
                                            </Typography>
                                        </Box>
                                    )}
                                </Paper>
                            </Grid>

                            {/* Whitelisting IPs */}
                            <Grid item xs={12} lg={6}>
                                <Paper 
                                    variant="outlined" 
                                    sx={{ 
                                        p: 2.5, 
                                        borderRadius: '16px', 
                                        height: 520, 
                                        display: 'flex', 
                                        flexDirection: 'column',
                                        boxShadow: '0 4px 24px rgba(15, 23, 42, 0.02)',
                                        borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'
                                    }}
                                >
                                    <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
                                        <SecurityIcon color="primary" sx={{ fontSize: '1.25rem' }} />
                                        <Typography variant="subtitle2" fontWeight={800} sx={{ letterSpacing: '0.02em', textTransform: 'uppercase', fontSize: '0.75rem', color: 'text.secondary' }}>
                                            Whitelisted Network Gateways
                                        </Typography>
                                    </Stack>
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                                        Requests originating from these public WAN IPs bypass GPS checks and default to WFO status.
                                    </Typography>

                                    {/* Add whitelist IP form */}
                                    <Stack spacing={1.5} mb={2}>
                                        <TextField
                                            size="small"
                                            label="Public IP / Subnet CIDR"
                                            value={newIpAddress}
                                            onChange={(e) => setNewIpAddress(e.target.value)}
                                            placeholder="e.g. 103.45.18.2 or 103.45.18.0/24"
                                            fullWidth
                                            helperText="Enter single IP or subnet (e.g. 103.45.0.0/24) for dynamic ranges."
                                            InputLabelProps={{ shrink: true }}
                                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                                        />
                                        <Stack direction="row" spacing={1}>
                                            <TextField
                                                size="small"
                                                label="Label"
                                                value={newIpLabel}
                                                onChange={(e) => setNewIpLabel(e.target.value)}
                                                placeholder="e.g. Main Office Wi-Fi"
                                                sx={{ flex: 1, '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                                                InputLabelProps={{ shrink: true }}
                                            />
                                            <Button
                                                variant="contained"
                                                onClick={handleAddIp}
                                                disabled={ipLoading || !newIpAddress}
                                                sx={{ px: 3, borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}
                                            >
                                                {ipLoading ? 'Adding...' : 'Add'}
                                            </Button>
                                        </Stack>
                                    </Stack>

                                    {/* Detect Current IP utility */}
                                    {detectedIp && (
                                        <Box 
                                            sx={{ 
                                                mb: 2, 
                                                p: 1.5, 
                                                borderRadius: '12px', 
                                                bgcolor: isDarkMode ? 'rgba(37, 99, 235, 0.08)' : 'rgba(37, 99, 235, 0.04)', 
                                                border: '1px solid',
                                                borderColor: isDarkMode ? 'rgba(37, 99, 235, 0.2)' : 'rgba(37, 99, 235, 0.15)', 
                                                display: 'flex', 
                                                justifyContent: 'space-between', 
                                                alignItems: 'center',
                                                position: 'relative',
                                                overflow: 'hidden',
                                                '&::before': {
                                                    content: '""',
                                                    position: 'absolute',
                                                    left: 0,
                                                    top: 0,
                                                    height: '100%',
                                                    width: '4px',
                                                    bgcolor: '#3b82f6'
                                                }
                                            }}
                                        >
                                            <Stack direction="row" spacing={1.5} alignItems="center">
                                                <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                                    <Box sx={{ 
                                                        width: 8, height: 8, borderRadius: '50%', bgcolor: '#10b981',
                                                        animation: 'pulse 2s infinite'
                                                     }} />
                                                    <style>{`
                                                        @keyframes pulse {
                                                            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
                                                            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
                                                            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
                                                        }
                                                    `}</style>
                                                </Box>
                                                <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                                                    Detected WAN: <code style={{ fontSize: '0.85rem', color: '#3b82f6', fontWeight: 'bold' }}>{detectedIp}</code>
                                                </Typography>
                                            </Stack>
                                            <Stack direction="row" spacing={1}>
                                                <Button
                                                    size="small"
                                                    variant="outlined"
                                                    onClick={() => {
                                                        setNewIpAddress(detectedIp);
                                                        setNewIpLabel('My Current IP');
                                                    }}
                                                    sx={{ textTransform: 'none', py: 0.25, px: 1, fontSize: '0.65rem', fontWeight: 700, borderRadius: '6px' }}
                                                >
                                                    Use IP
                                                </Button>
                                                <Button
                                                    size="small"
                                                    variant="outlined"
                                                    onClick={() => {
                                                        const parts = detectedIp.split('.');
                                                        if (parts.length === 4) {
                                                            setNewIpAddress(`${parts[0]}.${parts[1]}.${parts[2]}.0/24`);
                                                            setNewIpLabel('My Network Subnet');
                                                        } else {
                                                            setNewIpAddress(detectedIp);
                                                            setNewIpLabel('My Current IP');
                                                        }
                                                    }}
                                                    sx={{ textTransform: 'none', py: 0.25, px: 1, fontSize: '0.65rem', fontWeight: 700, borderRadius: '6px' }}
                                                >
                                                    Use Subnet (/24)
                                                </Button>
                                            </Stack>
                                        </Box>
                                    )}

                                    <Divider sx={{ my: 1.5 }} />

                                    {/* List registered IPs */}
                                    <Stack direction="row" spacing={1} alignItems="center" mb={1}>
                                        <Typography variant="caption" fontWeight={800} sx={{ color: 'text.secondary', textTransform: 'uppercase', fontSize: '0.7rem' }}>
                                            Registered Whitelist Gateways
                                        </Typography>
                                        {selectedOffice.registered_ips && selectedOffice.registered_ips.length > 0 && (
                                            <Chip label={selectedOffice.registered_ips.length} size="small" variant="filled" sx={{ height: 16, fontSize: '0.65rem', fontWeight: 700 }} />
                                        )}
                                    </Stack>

                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.25, overflowY: 'auto', flex: 1, maxHeight: 160, alignContent: 'flex-start' }}>
                                        {selectedOffice.registered_ips?.map((ip) => (
                                            <Chip
                                                key={ip.id}
                                                label={
                                                    <Stack direction="row" spacing={0.5} alignItems="center">
                                                        <span style={{ fontWeight: 700, color: isDarkMode ? '#f8fafc' : '#0f172a' }}>
                                                            {ip.ip_cidr || ip.ip_address}
                                                        </span>
                                                        <span style={{ opacity: 0.8, fontSize: '0.68rem' }}>({ip.label || 'no label'})</span>
                                                    </Stack>
                                                }
                                                onDelete={() => handleDeleteIp(ip.id)}
                                                color="primary"
                                                variant="outlined"
                                                size="medium"
                                                sx={{ 
                                                    borderRadius: '8px',
                                                    p: '4px 6px',
                                                    borderColor: isDarkMode ? 'rgba(37, 99, 235, 0.3)' : 'rgba(37, 99, 235, 0.2)',
                                                    bgcolor: isDarkMode ? 'rgba(37, 99, 235, 0.05)' : 'rgba(37, 99, 235, 0.02)',
                                                    transition: 'all 0.2s ease',
                                                    '&:hover': {
                                                        bgcolor: isDarkMode ? 'rgba(37, 99, 235, 0.1)' : 'rgba(37, 99, 235, 0.05)',
                                                        borderColor: 'primary.main',
                                                        transform: 'translateY(-1px)'
                                                    }
                                                }}
                                            />
                                        ))}
                                        {(!selectedOffice.registered_ips || selectedOffice.registered_ips.length === 0) && (
                                            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', display: 'block', mt: 0.5 }}>
                                                No corporate network IP gateways whitelisted yet. Users will undergo standard GPS verification.
                                            </Typography>
                                        )}
                                    </Box>
                                </Paper>
                            </Grid>
                        </Grid>
                    ) : (
                        <Paper variant="outlined" sx={{ p: 4, borderRadius: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 520, boxShadow: '0 4px 24px rgba(15, 23, 42, 0.02)', borderColor: 'divider' }}>
                            <MapIcon sx={{ fontSize: 56, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="subtitle1" fontWeight={700} color="text.primary" align="center">
                                No Office Location Selected
                            </Typography>
                            <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 320, mt: 0.5 }}>
                                Select an office location from the directory list on the left to configure geofencing and whitelisting.
                            </Typography>
                        </Paper>
                    )}
                </Grid>
            </Grid>

            {/* Office Add/Edit Dialog */}
            <Dialog open={officeDialogOpen} onClose={() => setOfficeDialogOpen(false)} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: '16px' } }}>
                <DialogTitle sx={{ fontWeight: 800, pb: 1 }}>{isEditing ? 'Modify Office Settings' : 'Register New Office Location'}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2.5} sx={{ mt: 1.5 }}>
                        <TextField
                            label="Office Name"
                            value={formData.name}
                            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="e.g. Headquarters / Production Unit"
                            fullWidth
                            required
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                        <TextField
                            label="Address"
                            value={formData.address}
                            onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                            placeholder="Full physical address"
                            multiline
                            rows={2}
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <Tooltip title="Auto-detect coordinates from physical address using OSM geocoding">
                                            <IconButton onClick={handleGeocode} color="primary" disabled={!formData.address.trim()}>
                                                <TravelExploreIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </InputAdornment>
                                )
                            }}
                        />

                        <Grid container spacing={2}>
                            <Grid item xs={6}>
                                <TextField
                                    label="Latitude"
                                    type="number"
                                    value={formData.latitude}
                                    onChange={(e) => setFormData(prev => ({ ...prev, latitude: e.target.value }))}
                                    placeholder="e.g. 19.07600"
                                    fullWidth
                                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                                />
                            </Grid>
                            <Grid item xs={6}>
                                <TextField
                                    label="Longitude"
                                    type="number"
                                    value={formData.longitude}
                                    onChange={(e) => setFormData(prev => ({ ...prev, longitude: e.target.value }))}
                                    placeholder="e.g. 72.87770"
                                    fullWidth
                                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                                />
                            </Grid>
                        </Grid>

                        <TextField
                            label="Geofence Radius (meters)"
                            type="number"
                            value={formData.geofence_radius_meters}
                            onChange={(e) => setFormData(prev => ({ ...prev, geofence_radius_meters: e.target.value }))}
                            placeholder="Radius in meters"
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />

                        <Box sx={{ p: 2, borderRadius: '8px', border: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={!!formData.require_dual_signal}
                                        onChange={(e) => setFormData(prev => ({ ...prev, require_dual_signal: e.target.checked }))}
                                        color="primary"
                                    />
                                }
                                label={
                                    <Box>
                                        <Typography variant="body2" fontWeight={700}>Require Both IP + GPS (Anti-Spoofing)</Typography>
                                        <Typography variant="caption" color="text.secondary">Enforce BOTH whitelisted IP gateway and GPS validation for WFO status</Typography>
                                    </Box>
                                }
                            />
                        </Box>

                        <Box sx={{ p: 2, borderRadius: '8px', border: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={!!formData.idle_timeout_enabled}
                                        onChange={(e) => setFormData(prev => ({ ...prev, idle_timeout_enabled: e.target.checked }))}
                                        color="primary"
                                    />
                                }
                                label={
                                    <Box>
                                        <Typography variant="body2" fontWeight={700}>Enable Inactivity Alarm</Typography>
                                        <Typography variant="caption" color="text.secondary">Trigger desktop alarm alert if user is idle during work hours</Typography>
                                    </Box>
                                }
                            />
                        </Box>

                        <TextField
                            label="Inactivity Alarm Timeout (minutes)"
                            type="number"
                            value={formData.idle_timeout_minutes}
                            onChange={(e) => setFormData(prev => ({ ...prev, idle_timeout_minutes: e.target.value }))}
                            placeholder="Inactivity threshold in minutes (default 15)"
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            disabled={!formData.idle_timeout_enabled}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 3, gap: 1 }}>
                    <Button onClick={() => setOfficeDialogOpen(false)} color="inherit" sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>Cancel</Button>
                    <Button variant="contained" onClick={handleSaveOffice} disabled={formLoading || !formData.name.trim()} sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 700 }}>
                        {formLoading ? 'Saving...' : 'Save Office'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
