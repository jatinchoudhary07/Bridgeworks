import React, { useEffect, useState } from 'react';
import { Avatar, Box, Button, Divider, Paper, Stack, TextField, Typography } from '@mui/material';
import { AutoAwesome as AutoAwesomeIcon, Edit as EditIcon } from '@mui/icons-material';
import { apiClient } from '../../../apiClient';
import { BACKEND_URL } from '../../../config/api';

export default function ProfileSection() {
    const [profile, setProfile] = useState(null);
    const [editing, setEditing] = useState(false);

    useEffect(() => {
        let mounted = true;
        apiClient(`${BACKEND_URL}/api/current-user/`, { credentials: 'include' })
            .then(async (response) => {
                if (!response.ok) return null;
                return response.json();
            })
            .then((data) => {
                if (!mounted) return;
                if (data) {
                    setProfile({
                        name: data.name || data.username || 'User',
                        email: data.email || '',
                        role: data.role || 'Team Member',
                        team: data.team || 'Operations',
                        manager: data.manager || 'Not Assigned',
                        joiningDate: data.joiningDate || '2025-01-10',
                        profilePicture: data.profilePicture || '',
                    });
                }
            })
            .catch(() => { });

        return () => {
            mounted = false;
        };
    }, []);

    if (!profile) {
        return <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}><Typography variant="body2">Loading profile…</Typography></Paper>;
    }

    return (
        <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'flex-start', md: 'center' }}>
                <Avatar src={profile.profilePicture} sx={{ width: 64, height: 64 }}>{profile.name?.charAt(0)}</Avatar>
                <Box sx={{ flex: 1 }}>
                    {editing ? (
                        <Stack spacing={1}>
                            <TextField size="small" label="Name" value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} />
                            <TextField size="small" label="Role" value={profile.role} onChange={(event) => setProfile({ ...profile, role: event.target.value })} />
                        </Stack>
                    ) : (
                        <>
                            <Typography variant="h6" sx={{ fontWeight: 700 }}>{profile.name}</Typography>
                            <Typography variant="body2" color="text.secondary">{profile.email}</Typography>
                        </>
                    )}
                </Box>
                <Stack direction="row" spacing={1}>            
                    <Button variant="contained" startIcon={<EditIcon />} onClick={() => setEditing((prev) => !prev)}>
                        {editing ? 'Done' : 'Quick Edit'}
                    </Button>
                </Stack>
            </Stack>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(4, 1fr)' }, gap: 1 }}>
                <Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="caption" color="text.secondary">Role</Typography><Typography variant="body2">{profile.role}</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="caption" color="text.secondary">Team</Typography><Typography variant="body2">{profile.team}</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="caption" color="text.secondary">Manager</Typography><Typography variant="body2">{profile.manager}</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="caption" color="text.secondary">Joining Date</Typography><Typography variant="body2">{profile.joiningDate}</Typography></Paper>
            </Box>
        </Paper>
    );
}
