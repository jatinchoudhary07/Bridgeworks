import React, { useState } from 'react';
import {
    Menu, MenuItem, Box, Typography, ListItemIcon, ListItemText, Tooltip,
    Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import BrightnessAutoIcon from '@mui/icons-material/BrightnessAuto';
import { usePresence } from '../../contexts/PresenceContext';
import PresenceBadge from './PresenceBadge';
import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';

// All 5 statuses the user can manually set.
const STATUS_OPTIONS = [
    { value: 'online',           label: 'Online',            hint: 'Available' },
    { value: 'offline',          label: 'Offline',            hint: 'Appear unavailable' },
    { value: 'in_meeting',       label: 'In a Meeting',       hint: 'Do not disturb' },
    { value: 'on_leave',         label: 'On Leave',           hint: 'Out of office' },
    { value: 'working_remotely', label: 'Working Remotely',   hint: 'Working from home / remote' },
];

const STATUS_LABELS = {
    online:           'Online',
    offline:          'Offline',
    in_meeting:       'In a Meeting',
    on_leave:         'On Leave',
    working_remotely: 'Working Remotely',
};

export default function StatusSelector({ compact = false }) {
    const { myPresence, setManualStatus } = usePresence();
    const [anchorEl, setAnchorEl] = useState(null);
    const [showLeaveWarning, setShowLeaveWarning] = useState(false);
    const open = Boolean(anchorEl);

    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleSelectStatus = async (status) => {
        if (status === 'on_leave') {
            try {
                const res = await apiClient(`${BACKEND_URL}/api/mydesk/leaves/`);
                if (res.ok) {
                    const leaves = await res.json();
                    const todayStr = new Date().toISOString().split('T')[0];
                    const hasApprovedLeave = leaves.some(leave =>
                        leave.status === 'approved' &&
                        leave.start_date <= todayStr &&
                        todayStr <= leave.end_date
                    );
                    if (!hasApprovedLeave) {
                        setShowLeaveWarning(true);
                        handleClose();
                        return;
                    }
                }
            } catch (err) {
                console.error('Failed to check leave requests:', err);
            }
        }
        await setManualStatus(status);
        handleClose();
    };

    const handleConfirmLeave = async () => {
        setShowLeaveWarning(false);
        await setManualStatus('on_leave');
    };

    const currentStatus = myPresence?.resolved_status || 'offline';
    const manualStatus = myPresence?.manual_status;

    const displayLabel = manualStatus
        ? `${STATUS_LABELS[manualStatus] || manualStatus}`
        : STATUS_LABELS[currentStatus] || 'Offline';

    const triggerButton = (
        <Tooltip title="Set your status" placement="bottom" arrow>
            <Box
                onClick={handleClick}
                sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.75,
                    px: 1.25,
                    py: 0.5,
                    borderRadius: '8px',
                    border: '1px solid',
                    borderColor: 'divider',
                    cursor: 'pointer',
                    userSelect: 'none',
                    transition: 'all 0.15s ease',
                    '&:hover': {
                        borderColor: 'primary.main',
                        bgcolor: 'action.hover',
                    },
                }}
            >
                <PresenceBadge status={currentStatus} size="small" />
                {!compact && (
                    <Typography variant="body2" sx={{ fontSize: '0.82rem', fontWeight: 500, color: 'text.primary' }}>
                        {displayLabel}
                    </Typography>
                )}
                {/* Chevron */}
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                    style={{ color: '#94A3B8', flexShrink: 0 }}
                >
                    <polyline points="6 9 12 15 18 9" />
                </svg>
            </Box>
        </Tooltip>
    );

    return (
        <>
            {triggerButton}

            <Menu
                anchorEl={anchorEl}
                open={open}
                onClose={handleClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                sx={{
                    '& .MuiPaper-root': {
                        borderRadius: '12px',
                        boxShadow: '0px 8px 32px rgba(0, 0, 0, 0.14)',
                        border: '1px solid',
                        borderColor: 'divider',
                        minWidth: '210px',
                        mt: 0.5,
                        overflow: 'hidden',
                    },
                }}
            >
                {/* Header */}
                <Box sx={{ px: 2, py: 1.25, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                        Set your status
                    </Typography>
                </Box>

                {STATUS_OPTIONS.map((opt) => (
                    <MenuItem
                        key={opt.value}
                        onClick={() => handleSelectStatus(opt.value)}
                        selected={manualStatus === opt.value}
                        sx={{
                            py: 1.25,
                            px: 2,
                            gap: 1.25,
                            '&.Mui-selected': {
                                bgcolor: 'action.selected',
                            },
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: 'auto' }}>
                            <PresenceBadge status={opt.value} size="small" />
                        </ListItemIcon>
                        <ListItemText
                            primary={opt.label}
                            secondary={opt.hint}
                            primaryTypographyProps={{ variant: 'body2', fontWeight: 500 }}
                            secondaryTypographyProps={{ variant: 'caption', color: 'text.disabled' }}
                        />
                        {manualStatus === opt.value && (
                            <CheckIcon sx={{ fontSize: 16, color: 'primary.main', ml: 'auto', flexShrink: 0 }} />
                        )}
                    </MenuItem>
                ))}

                {/* Divider + Reset option */}
                <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
                    <MenuItem
                        onClick={() => handleSelectStatus('')}
                        sx={{ py: 1.25, px: 2, gap: 1.25 }}
                    >
                        <ListItemIcon sx={{ minWidth: 'auto', display: 'flex', alignItems: 'center' }}>
                            <BrightnessAutoIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                        </ListItemIcon>
                        <ListItemText
                            primary="Automatic"
                            secondary="Let the system decide"
                            primaryTypographyProps={{ variant: 'body2', fontWeight: 500 }}
                            secondaryTypographyProps={{ variant: 'caption', color: 'text.disabled' }}
                        />
                        {!manualStatus && (
                            <CheckIcon sx={{ fontSize: 16, color: 'primary.main', ml: 'auto', flexShrink: 0 }} />
                        )}
                    </MenuItem>
                </Box>
            </Menu>

            <Dialog
                open={showLeaveWarning}
                onClose={() => setShowLeaveWarning(false)}
                PaperProps={{
                    sx: {
                        borderRadius: '16px',
                        padding: 1.5,
                        boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
                    }
                }}
            >
                <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>
                    ⚠️ No Approved Leave Request Found
                </DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ color: 'text.secondary', fontSize: '0.95rem' }}>
                        You do not have an approved leave request scheduled for today. Manually setting your status to <strong>On Leave</strong> may conflict with attendance tracking.
                        <br /><br />
                        Are you sure you want to proceed?
                    </DialogContentText>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button
                        onClick={() => setShowLeaveWarning(false)}
                        sx={{ textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirmLeave}
                        variant="contained"
                        color="warning"
                        sx={{ textTransform: 'none', fontWeight: 600, borderRadius: '8px' }}
                    >
                        Yes, Set Status
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}
