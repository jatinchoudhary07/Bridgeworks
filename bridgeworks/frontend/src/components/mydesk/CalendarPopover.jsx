import React, { useMemo, useState } from 'react';
import {
    Box,
    Button,
    Chip,
    Divider,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Popover,
    Stack,
    Typography,
} from '@mui/material';
import {
    TaskAlt as TaskIcon,
    Videocam as MeetingIcon,
    EventBusy as LeaveIcon,
} from '@mui/icons-material';
import { formatEventTime } from './calendarUtils';

const EVENT_TYPE_META = {
    task: { label: 'Task', icon: TaskIcon },
    meeting: { label: 'Meeting', icon: MeetingIcon },
    leave: { label: 'Leave', icon: LeaveIcon },
};

export default function CalendarPopover({
    anchorEl,
    open,
    selectedDate,
    events,
    onClose,
}) {
    const [activeFilter, setActiveFilter] = useState('all');

    const visibleEvents = useMemo(() => {
        if (activeFilter === 'all') return events;
        return events.filter((eventItem) => eventItem.calendarType === activeFilter);
    }, [events, activeFilter]);

    return (
        <Popover
            open={open}
            anchorEl={anchorEl}
            onClose={onClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
            <Box sx={{ p: 2, width: 340, maxWidth: '90vw' }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    {selectedDate ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString([], {
                        weekday: 'long',
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                    }) : 'Day events'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    Tasks, Meetings, and Leaves
                </Typography>

                <Stack direction="row" spacing={1} sx={{ mt: 1.5, mb: 1 }}>
                    <Button size="small" variant={activeFilter === 'all' ? 'contained' : 'outlined'} onClick={() => setActiveFilter('all')}>
                        All
                    </Button>
                    <Button size="small" variant={activeFilter === 'meeting' ? 'contained' : 'outlined'} onClick={() => setActiveFilter('meeting')}>
                        Meeting
                    </Button>
                    <Button size="small" variant={activeFilter === 'task' ? 'contained' : 'outlined'} onClick={() => setActiveFilter('task')}>
                        Task
                    </Button>
                </Stack>

                <Divider sx={{ mb: 1 }} />

                {visibleEvents.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                        No events scheduled for this day.
                    </Typography>
                ) : (
                    <List dense disablePadding>
                        {visibleEvents.map((eventItem) => {
                            const meta = EVENT_TYPE_META[eventItem.calendarType] || EVENT_TYPE_META.meeting;
                            const IconComponent = meta.icon;

                            return (
                                <ListItem key={eventItem.id} disableGutters sx={{ py: 0.75 }}>
                                    <ListItemIcon sx={{ minWidth: 34 }}>
                                        <IconComponent fontSize="small" color="action" />
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={eventItem.title || 'Untitled'}
                                        secondary={formatEventTime(eventItem.start)}
                                        primaryTypographyProps={{ variant: 'body2', fontWeight: 600 }}
                                        secondaryTypographyProps={{ variant: 'caption' }}
                                    />
                                    <Stack direction="row" spacing={0.5} alignItems="center">
                                        <Chip size="small" label={meta.label} variant="outlined" />
                                        {eventItem.meet_link ? (
                                            <Button
                                                size="small"
                                                variant="contained"
                                                color="success"
                                                href={eventItem.meet_link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                sx={{ textTransform: 'none', py: 0.25, px: 1, minWidth: 'auto', fontSize: '11px', borderRadius: '12px' }}
                                            >
                                                Join
                                            </Button>
                                        ) : eventItem.html_link ? (
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                href={eventItem.html_link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                sx={{ textTransform: 'none', py: 0.25, px: 1, minWidth: 'auto', fontSize: '11px', borderRadius: '12px' }}
                                            >
                                                View
                                            </Button>
                                        ) : null}
                                    </Stack>
                                </ListItem>
                            );
                        })}
                    </List>
                )}
            </Box>
        </Popover>
    );
}