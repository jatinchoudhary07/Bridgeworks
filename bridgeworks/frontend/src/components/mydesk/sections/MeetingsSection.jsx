import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    Collapse,
    IconButton,
    Paper,
    Snackbar,
    Stack,
    Tab,
    Tabs,
    TextField,
    Typography,
} from '@mui/material';
import {
    Add as AddIcon,
    DeleteOutline as DeleteOutlineIcon,
    VideoCall as VideoCallIcon,
} from '@mui/icons-material';
import { keyframes } from '@mui/system';
import {
    deleteCalendarEvent,
    fetchCalendarEvents,
    fetchCalendarStatus,
    redirectToGoogleAuth,
    scheduleCalendarMeeting,
} from '../calendarService';
import { useLocation } from 'react-router-dom';
import { usePresence } from '../../../contexts/PresenceContext';

const FILTER_TABS = [
    { key: 'all', label: 'All' },
    { key: 'upcoming', label: 'Upcoming' },
    { key: 'live', label: 'Live Now' },
    { key: 'done', label: 'Past Meetings' },
];

const livePulse = keyframes`
  0% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.38); }
  70% { box-shadow: 0 0 0 8px rgba(46, 125, 50, 0); }
  100% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0); }
`;

function toDateKey(dateObj) {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    const day = String(dateObj.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getMeetingStatus(meeting, nowTs = Date.now()) {
    const startTs = new Date(meeting.start).getTime();
    const endTs = new Date(meeting.end).getTime();
    if (Number.isNaN(startTs)) return 'upcoming';
    const effectiveEnd = Number.isNaN(endTs) ? (startTs + 60 * 60 * 1000) : endTs;

    if (nowTs >= startTs && nowTs <= effectiveEnd) return 'live';
    if (nowTs < startTs) return 'upcoming';
    return 'done';
}

export default function MeetingsSection({ members = [] }) {
    const location = useLocation();
    const { setMeetingStatus } = usePresence();
    const meetingCardRefs = useRef({});
    const handledDeepLinkRef = useRef('');
    // Tracks whether this session triggered in_meeting so we can auto-revert
    const inMeetingActiveRef = useRef(false);
    const [calendarConnected, setCalendarConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isCreating, setIsCreating] = useState(false);
    const [activeFilter, setActiveFilter] = useState('all');
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [meetings, setMeetings] = useState([]);
    const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });
    const [highlightMeetingId, setHighlightMeetingId] = useState('');

    const [form, setForm] = useState(() => {
        const now = new Date();
        return {
            title: '',
            date: toDateKey(now),
            time: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
            duration: 60,
            taggedUserIds: [],
            description: '',
            notificationBefore: '10m',
            customNotificationMinutes: '',
            reminderChannels: ['push'],
        };
    });

    const loadMeetings = async ({ silent = false } = {}) => {
        if (!silent) setIsLoading(true);
        try {
            const status = await fetchCalendarStatus({ forceRefresh: true });
            const connected = Boolean(status?.connected);
            setCalendarConnected(connected);
            if (!connected) {
                setMeetings([]);
                return;
            }

            const startDate = toDateKey(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000));
            const endDate = toDateKey(new Date(Date.now() + 60 * 24 * 60 * 60 * 1000));
            const events = await Promise.race([
                fetchCalendarEvents({ start: startDate, end: endDate, forceRefresh: true }),
                new Promise((_, reject) => {
                    window.setTimeout(() => reject(new Error('Meeting sync timeout. Please retry.')), 12000);
                }),
            ]);
            const onlyMeetings = (Array.isArray(events) ? events : []).filter((eventItem) => {
                const eventType = (eventItem?.event_type || '').toLowerCase();
                return eventType === 'meeting' || Boolean(eventItem?.meet_link);
            });
            setMeetings(onlyMeetings);
        } catch (error) {
            if (error?.status === 403) setCalendarConnected(false);
            if (!silent) setMeetings([]);
            setToast({ open: true, message: error.message || 'Unable to load meetings.', severity: 'error' });
        } finally {
            if (!silent) setIsLoading(false);
        }
    };

    useEffect(() => {
        loadMeetings();

        try {
            const cached = window.localStorage.getItem('bridgeworks:last-scheduled-meeting');
            if (cached) {
                const parsed = JSON.parse(cached);
                if (parsed?.start && parsed?.title) {
                    setMeetings((previous) => {
                        if (previous.some((meeting) => String(meeting.id) === String(parsed.id))) return previous;
                        return [parsed, ...previous];
                    });
                }
            }
        } catch {
        }

        const handleScheduled = (event) => {
            const incoming = event?.detail;
            if (incoming?.start && incoming?.title) {
                setMeetings((previous) => {
                    if (previous.some((meeting) => String(meeting.id) === String(incoming.id))) return previous;
                    return [incoming, ...previous];
                });
            }
            loadMeetings({ silent: true });
        };
        const handleFocus = () => {
            loadMeetings({ silent: true });
        };

        window.addEventListener('bridgeworks:meeting-scheduled', handleScheduled);
        window.addEventListener('focus', handleFocus);
        const intervalId = window.setInterval(() => {
            loadMeetings({ silent: true });
        }, 30000);

        return () => {
            window.removeEventListener('bridgeworks:meeting-scheduled', handleScheduled);
            window.removeEventListener('focus', handleFocus);
            window.clearInterval(intervalId);
        };
    }, []);

    const nowTs = Date.now();

    const filteredMeetings = useMemo(() => {
        const withStatus = meetings.map((meeting) => ({
            ...meeting,
            status: getMeetingStatus(meeting, nowTs),
        }));

        const filtered = withStatus.filter((meeting) => {
            if (activeFilter === 'all') return true;
            return meeting.status === activeFilter;
        });

        return filtered.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
    }, [meetings, activeFilter, nowTs]);

    // ── Auto-revert meeting status when all live meetings have ended ──────────
    useEffect(() => {
        const liveMeetings = filteredMeetings.filter((m) => m.status === 'live');
        if (liveMeetings.length === 0 && inMeetingActiveRef.current) {
            inMeetingActiveRef.current = false;
            setMeetingStatus(false);
        }
    }, [filteredMeetings, setMeetingStatus]);

    const pendingStatus = useMemo(() => {
        if (!form.date || !form.time) return 'upcoming';
        const start = `${form.date}T${form.time}:00`;
        const startTs = new Date(start).getTime();
        if (Number.isNaN(startTs)) return 'upcoming';
        const endDt = new Date(startTs + Number(form.duration || 60) * 60000);
        if (Number.isNaN(endDt.getTime())) return 'upcoming';
        return getMeetingStatus({ start, end: endDt.toISOString() }, nowTs);
    }, [form.date, form.time, form.duration, nowTs]);

    const statusChip = (status) => {
        if (status === 'live') return <Chip size="small" color="success" label="LIVE" />;
        if (status === 'upcoming') return <Chip size="small" color="info" label="UPCOMING" variant="outlined" />;
        return <Chip size="small" color="default" label="DONE" variant="outlined" />;
    };

    const toggleMember = (memberId) => {
        setForm((previous) => ({
            ...previous,
            taggedUserIds: previous.taggedUserIds.includes(memberId)
                ? previous.taggedUserIds.filter((id) => id !== memberId)
                : [...previous.taggedUserIds, memberId],
        }));
    };

    const toggleReminderChannel = (channel) => {
        setForm((previous) => ({
            ...previous,
            reminderChannels: previous.reminderChannels.includes(channel)
                ? previous.reminderChannels.filter((value) => value !== channel)
                : [...previous.reminderChannels, channel],
        }));
    };

    const scheduleMeeting = async () => {
        if (!form.title.trim()) {
            setToast({ open: true, message: 'Meeting title is required.', severity: 'error' });
            return;
        }

        const startIso = `${form.date}T${form.time}:00`;
        const startDate = new Date(startIso);
        if (Number.isNaN(startDate.getTime())) {
            setToast({ open: true, message: 'Valid date and time are required.', severity: 'error' });
            return;
        }

        const endDate = new Date(startDate.getTime() + Number(form.duration || 60) * 60000);
        const pad = (value) => String(value).padStart(2, '0');
        const endIso = `${endDate.getFullYear()}-${pad(endDate.getMonth() + 1)}-${pad(endDate.getDate())}T${pad(endDate.getHours())}:${pad(endDate.getMinutes())}:${pad(endDate.getSeconds())}`;

        setIsCreating(true);
        try {
            const scheduled = await scheduleCalendarMeeting({
                title: form.title.trim(),
                start: startIso,
                end: endIso,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
                tagged_user_ids: form.taggedUserIds,
                description: form.description.trim(),
                notification_before: form.notificationBefore,
                custom_notification_minutes: form.notificationBefore === 'custom' ? Number(form.customNotificationMinutes || 0) : null,
                reminder_channels: form.reminderChannels,
            });

            setToast({ open: true, message: 'Meeting scheduled and synced.', severity: 'success' });
            setIsCreateOpen(false);
            setActiveFilter('all');

            setMeetings((previous) => {
                const eventId = scheduled?.event_id;
                if (eventId && previous.some((meeting) => meeting.id === eventId)) return previous;
                const optimisticMeeting = {
                    id: eventId || `local-${Date.now()}`,
                    title: form.title.trim(),
                    description: form.description.trim(),
                    start: scheduled?.start || startIso,
                    end: scheduled?.end || endIso,
                    event_type: 'meeting',
                    meet_link: scheduled?.meet_link || '',
                    html_link: scheduled?.event_link || '',
                };
                return [optimisticMeeting, ...previous];
            });

            setForm((previous) => ({
                ...previous,
                title: '',
                description: '',
                taggedUserIds: [],
                customNotificationMinutes: '',
            }));

            loadMeetings();
        } catch (error) {
            if (error?.payload?.needs_auth) {
                setToast({ open: true, message: 'Connect Google Calendar to schedule meetings.', severity: 'warning' });
            } else {
                setToast({ open: true, message: error.message || 'Unable to schedule meeting.', severity: 'error' });
            }
        } finally {
            setIsCreating(false);
        }
    };

    const removeMeeting = async (meetingId) => {
        try {
            await deleteCalendarEvent(meetingId);
            setMeetings((previous) => previous.filter((meeting) => meeting.id !== meetingId));
            setToast({ open: true, message: 'Meeting deleted.', severity: 'success' });
        } catch (error) {
            setToast({ open: true, message: error.message || 'Unable to delete meeting.', severity: 'error' });
        }
    };

    const formatMeetingTime = (start, end) => {
        const startDate = new Date(start);
        const endDate = new Date(end);
        if (Number.isNaN(startDate.getTime())) return 'Invalid date';

        const datePart = startDate.toLocaleDateString([], {
            month: 'short',
            day: '2-digit',
            year: 'numeric',
        });
        const startPart = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const endPart = Number.isNaN(endDate.getTime())
            ? ''
            : endDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return endPart ? `${datePart}, ${startPart} - ${endPart}` : `${datePart}, ${startPart}`;
    };

    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const eventId = (params.get('eventId') || '').trim();
        if (!eventId) return;

        if (activeFilter !== 'all') {
            setActiveFilter('all');
            return;
        }

        if (handledDeepLinkRef.current === eventId) return;
        const target = meetings.find((meeting) => String(meeting.id) === String(eventId));
        if (!target) return;

        handledDeepLinkRef.current = eventId;
        setHighlightMeetingId(String(target.id));

        window.setTimeout(() => {
            meetingCardRefs.current[target.id]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 120);
        window.setTimeout(() => setHighlightMeetingId(''), 5000);
    }, [location.search, meetings, activeFilter]);

    return (
        <Stack spacing={2}>
            {!calendarConnected && !isLoading && (
                <Alert
                    severity="warning"
                    action={<Button color="inherit" size="small" onClick={redirectToGoogleAuth}>Connect Google</Button>}
                >
                    Google Calendar is not connected. Connect to enable synced meetings and Google Meet links.
                </Alert>
            )}

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" spacing={1.25}>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                        My Meetings
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => setIsCreateOpen((previous) => !previous)}
                        disabled={!calendarConnected}
                    >
                        Schedule Meeting
                    </Button>
                </Stack>

                <Tabs
                    value={activeFilter}
                    onChange={(_, nextValue) => setActiveFilter(nextValue)}
                    sx={{ mt: 1.25 }}
                    variant="scrollable"
                    allowScrollButtonsMobile
                >
                    {FILTER_TABS.map((tab) => (
                        <Tab key={tab.key} value={tab.key} label={tab.label} />
                    ))}
                </Tabs>

                <Collapse in={isCreateOpen} timeout={220}>
                    <Paper variant="outlined" sx={{ mt: 1.5, p: 1.5, borderRadius: 2 }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                            Schedule a Meeting
                        </Typography>
                        <Stack spacing={1.25}>
                            <TextField
                                size="small"
                                label="Meeting Title"
                                value={form.title}
                                onChange={(event) => setForm({ ...form, title: event.target.value })}
                            />
                            <TextField
                                size="small"
                                label="Description"
                                multiline
                                minRows={2}
                                value={form.description}
                                onChange={(event) => setForm({ ...form, description: event.target.value })}
                            />

                            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25}>
                                <TextField
                                    size="small"
                                    type="date"
                                    label="Date"
                                    InputLabelProps={{ shrink: true }}
                                    value={form.date}
                                    onChange={(event) => setForm({ ...form, date: event.target.value })}
                                    fullWidth
                                />
                                <TextField
                                    size="small"
                                    type="time"
                                    label="Time"
                                    InputLabelProps={{ shrink: true }}
                                    value={form.time}
                                    onChange={(event) => setForm({ ...form, time: event.target.value })}
                                    fullWidth
                                />
                            </Stack>



                            {Array.isArray(members) && members.length > 0 && (
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Tag Members</Typography>
                                    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                                        {members.map((member) => {
                                            const label = member.full_name || member.username;
                                            const selected = form.taggedUserIds.includes(member.id);
                                            return (
                                                <Chip
                                                    key={member.id}
                                                    clickable
                                                    label={label}
                                                    color={selected ? 'primary' : 'default'}
                                                    variant={selected ? 'filled' : 'outlined'}
                                                    onClick={() => toggleMember(member.id)}
                                                />
                                            );
                                        })}
                                    </Stack>
                                </Box>
                            )}



                            <Box>
                                <Typography variant="caption" color="text.secondary">Notification Before</Typography>
                                <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 0.5 }}>
                                    {['10m', '1h', 'custom'].map((option) => (
                                        <Chip
                                            key={option}
                                            clickable
                                            label={option === '10m' ? '10 min' : option === '1h' ? '1 hr' : 'Custom'}
                                            color={form.notificationBefore === option ? 'primary' : 'default'}
                                            variant={form.notificationBefore === option ? 'filled' : 'outlined'}
                                            onClick={() => setForm({ ...form, notificationBefore: option })}
                                        />
                                    ))}
                                    {form.notificationBefore === 'custom' && (
                                        <TextField
                                            size="small"
                                            type="number"
                                            label="Minutes"
                                            sx={{ width: 120 }}
                                            value={form.customNotificationMinutes}
                                            onChange={(event) => setForm({ ...form, customNotificationMinutes: event.target.value })}
                                        />
                                    )}
                                </Stack>
                            </Box>

                            <Box>
                                <Typography variant="caption" color="text.secondary">Reminder Channels</Typography>
                                <Stack direction="row" spacing={0.75} sx={{ mt: 0.5 }}>
                                    {['email', 'push'].map((channel) => {
                                        const selected = form.reminderChannels.includes(channel);
                                        return (
                                            <Chip
                                                key={channel}
                                                clickable
                                                label={channel === 'email' ? 'Email' : 'Push'}
                                                color={selected ? 'primary' : 'default'}
                                                variant={selected ? 'filled' : 'outlined'}
                                                onClick={() => toggleReminderChannel(channel)}
                                            />
                                        );
                                    })}
                                </Stack>
                            </Box>

                            {/* ── Submit row ── */}
                            <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ pt: 0.5 }}>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => {
                                        setIsCreateOpen(false);
                                        setForm((prev) => ({
                                            ...prev,
                                            title: '',
                                            description: '',
                                            taggedUserIds: [],
                                            customNotificationMinutes: '',
                                        }));
                                    }}
                                    disabled={isCreating}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    id="schedule-meeting-submit-btn"
                                    variant="contained"
                                    size="small"
                                    startIcon={<VideoCallIcon />}
                                    onClick={scheduleMeeting}
                                    disabled={isCreating || !form.title.trim()}
                                >
                                    {isCreating ? 'Scheduling…' : 'Schedule Meeting'}
                                </Button>
                            </Stack>

                        </Stack>
                    </Paper>
                </Collapse>
            </Paper>

            <Stack spacing={1.25}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>
                    All Meetings
                </Typography>

                {isLoading ? (
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                        <Typography variant="body2" color="text.secondary">Loading meetings...</Typography>
                    </Paper>
                ) : filteredMeetings.length === 0 ? (
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                        <Typography variant="body2" color="text.secondary">No meetings in this filter.</Typography>
                    </Paper>
                ) : (
                    filteredMeetings.map((meeting) => {
                        const disabledJoin = meeting.status === 'done';
                        return (
                            <Paper
                                key={meeting.id}
                                ref={(element) => {
                                    if (element) meetingCardRefs.current[meeting.id] = element;
                                    else delete meetingCardRefs.current[meeting.id];
                                }}
                                variant="outlined"
                                sx={{
                                    p: 1.5,
                                    borderRadius: 2,
                                    borderLeft: '4px solid',
                                    borderLeftColor: meeting.status === 'live' ? 'success.main' : 'divider',
                                    animation: meeting.status === 'live' ? `${livePulse} 1.6s infinite` : 'none',
                                    boxShadow: String(highlightMeetingId) === String(meeting.id)
                                        ? '0 0 0 2px rgba(25,118,210,0.16)'
                                        : 'none',
                                    transition: 'box-shadow 0.2s ease',
                                }}
                            >
                                <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={1.25}>
                                    <Box sx={{ minWidth: 0, flex: 1 }}>
                                        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.35 }}>
                                            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                                                {meeting.title}
                                            </Typography>
                                            {statusChip(meeting.status)}
                                        </Stack>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                                            {meeting.description || 'No description provided.'}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {formatMeetingTime(meeting.start, meeting.end)}
                                        </Typography>
                                    </Box>

                                    <Stack direction="row" spacing={0.5} alignItems="center" justifyContent={{ xs: 'flex-start', md: 'flex-end' }}>
                                        <Button
                                            variant="contained"
                                            size="small"
                                            startIcon={<VideoCallIcon />}
                                            component={disabledJoin ? 'button' : 'a'}
                                            href={disabledJoin ? undefined : (meeting.meet_link || meeting.html_link || 'https://meet.google.com/new')}
                                            target={disabledJoin ? undefined : '_blank'}
                                            rel={disabledJoin ? undefined : 'noreferrer'}
                                            disabled={disabledJoin}
                                            onClick={disabledJoin ? undefined : () => {
                                                inMeetingActiveRef.current = true;
                                                setMeetingStatus(true);
                                            }}
                                            sx={disabledJoin ? { bgcolor: 'action.disabledBackground', color: 'text.disabled' } : { bgcolor: 'success.main', '&:hover': { bgcolor: 'success.dark' } }}
                                        >
                                            {disabledJoin ? 'Ended' : 'Join Meet'}
                                        </Button>

                                        <IconButton size="small" color="error" onClick={() => removeMeeting(meeting.id)}>
                                            <DeleteOutlineIcon fontSize="small" />
                                        </IconButton>
                                    </Stack>
                                </Stack>
                            </Paper>
                        );
                    })
                )}
            </Stack>

            <Snackbar
                open={toast.open}
                autoHideDuration={2600}
                onClose={() => setToast((previous) => ({ ...previous, open: false }))}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
                <Alert
                    severity={toast.severity}
                    variant="filled"
                    onClose={() => setToast((previous) => ({ ...previous, open: false }))}
                >
                    {toast.message}
                </Alert>
            </Snackbar>
        </Stack>
    );
}
