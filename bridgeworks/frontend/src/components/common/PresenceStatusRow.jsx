import React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { usePresence } from '../../contexts/PresenceContext';

const STATUS_CONFIG = {
    online:           { color: '#10B981', label: 'Online',            icon: '●' },
    offline:          { color: '#94A3B8', label: 'Offline',           icon: '●' },
    in_meeting:       { color: '#1976D2', label: 'In a Meeting',      icon: '●' },
    on_leave:         { color: '#F59E0B', label: 'On Leave',          icon: '●' },
    working_remotely: { color: '#06B6D4', label: 'Working Remotely',  icon: '●' },
};

function formatLastSeen(lastSeenIso) {
    if (!lastSeenIso) return '';
    const now = new Date();
    const then = new Date(lastSeenIso);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1)  return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24)  return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
}

/**
 * PresenceStatusRow
 * =================
 * A compact status indicator for use on profile pages, member cards, and directory rows.
 *
 * Props:
 *   userId   — ID of the user whose presence to show (reads from PresenceContext)
 *   lastSeen — Optional ISO timestamp string for the "last seen" suffix (offline only)
 *   size     — 'sm' | 'md' (default: 'md') — controls dot and font size
 *
 * Usage:
 *   <PresenceStatusRow userId={member.id} lastSeen={member.last_seen} />
 */
export default function PresenceStatusRow({ userId, lastSeen, size = 'md' }) {
    const { userStatuses } = usePresence();
    const status = userStatuses[userId] || 'offline';
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.offline;

    const dotSize  = size === 'sm' ? 7  : 9;
    const fontSize = size === 'sm' ? '0.75rem' : '0.82rem';
    const lastSeenLabel = status === 'offline' ? formatLastSeen(lastSeen) : '';

    return (
        <Tooltip
            title={config.label + (lastSeenLabel ? ` · Last seen ${lastSeenLabel}` : '')}
            placement="top"
            arrow
        >
            <Box
                sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.6,
                    cursor: 'default',
                    userSelect: 'none',
                }}
            >
                {/* Presence dot */}
                <Box
                    sx={{
                        width: dotSize,
                        height: dotSize,
                        borderRadius: '50%',
                        bgcolor: config.color,
                        flexShrink: 0,
                        transition: 'background-color 0.3s ease',
                        // Subtle pulse for active statuses
                        animation: status !== 'offline'
                            ? 'presence-row-pulse 2.5s infinite ease-in-out'
                            : 'none',
                        '@keyframes presence-row-pulse': {
                            '0%, 100%': { opacity: 1 },
                            '50%': { opacity: 0.65 },
                        },
                    }}
                />

                {/* Label */}
                <Typography
                    variant="body2"
                    component="span"
                    sx={{
                        fontSize,
                        color: 'text.secondary',
                        fontWeight: 500,
                        lineHeight: 1,
                    }}
                >
                    {config.label}
                    {lastSeenLabel && (
                        <Box
                            component="span"
                            sx={{ color: 'text.disabled', fontWeight: 400, ml: 0.4 }}
                        >
                            · {lastSeenLabel}
                        </Box>
                    )}
                </Typography>
            </Box>
        </Tooltip>
    );
}
