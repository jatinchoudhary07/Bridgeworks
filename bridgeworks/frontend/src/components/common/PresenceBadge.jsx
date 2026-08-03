import React from 'react';
import { Badge, Box, Typography, Tooltip } from '@mui/material';
import { styled } from '@mui/material/styles';
import { usePresence } from '../../contexts/PresenceContext';

const StyledBadge = styled(Badge)(({ theme, statuscolor }) => ({
    '& .MuiBadge-badge': {
        backgroundColor: statuscolor,
        color: statuscolor,
        boxShadow: `0 0 0 2px ${theme.palette.background.paper}`,
        '&::after': {
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            borderRadius: '50%',
            animation: statuscolor !== '#94A3B8' ? 'ripple 1.2s infinite ease-in-out' : 'none',
            border: '1px solid currentColor',
            content: '""',
        },
    },
    '@keyframes ripple': {
        '0%': {
            transform: 'scale(.8)',
            opacity: 1,
        },
        '100%': {
            transform: 'scale(2.4)',
            opacity: 0,
        },
    },
}));

// P1: on_leave        → Amber  (always wins)
// P2: in_meeting      → Blue
// P3: manual          → user-chosen
// P4: activity        → Green/Gray
const STATUS_CONFIG = {
    online:           { color: '#10B981', label: 'Online' },
    offline:          { color: '#94A3B8', label: 'Offline' },
    in_meeting:       { color: '#1976D2', label: 'In a Meeting' },
    on_leave:         { color: '#F59E0B', label: 'On Leave' },
    working_remotely: { color: '#06B6D4', label: 'Working Remotely' },
};

export default function PresenceBadge({ userId, status, size = 'medium', showLabel = false, children }) {
    const { userStatuses } = usePresence();
    const resolvedStatus = status || userStatuses[userId] || 'offline';
    const config = STATUS_CONFIG[resolvedStatus] || STATUS_CONFIG.offline;

    const dotSize = size === 'small' ? 8 : size === 'large' ? 14 : 10;

    const dot = (
        <Tooltip title={config.label} placement="top" arrow>
            <Box
                sx={{
                    width: dotSize,
                    height: dotSize,
                    borderRadius: '50%',
                    backgroundColor: config.color,
                    boxShadow: (theme) => `0 0 0 2px ${theme.palette.background.paper}`,
                    display: 'inline-block',
                    position: 'relative',
                    cursor: 'default',
                    flexShrink: 0,
                    animation: resolvedStatus !== 'offline' ? 'presence-ripple 1.8s infinite ease-in-out' : 'none',
                    '@keyframes presence-ripple': {
                        '0%': { boxShadow: `0 0 0 0 ${config.color}66` },
                        '70%': { boxShadow: `0 0 0 4px ${config.color}00` },
                        '100%': { boxShadow: `0 0 0 0 ${config.color}00` },
                    },
                }}
            />
        </Tooltip>
    );

    if (children) {
        return (
            <Tooltip title={config.label} placement="top" arrow>
                <span style={{ display: 'inline-flex' }}>
                    <StyledBadge
                        statuscolor={config.color}
                        overlap="circular"
                        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                        variant="dot"
                        sx={{
                            '& .MuiBadge-badge': {
                                width: dotSize,
                                height: dotSize,
                                minWidth: dotSize,
                                borderRadius: '50%',
                            }
                        }}
                    >
                        {children}
                    </StyledBadge>
                </span>
            </Tooltip>
        );
    }

    if (showLabel) {
        return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {dot}
                <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                    {config.label}
                </Typography>
            </Box>
        );
    }

    return dot;
}
