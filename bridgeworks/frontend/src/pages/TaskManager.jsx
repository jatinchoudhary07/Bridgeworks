import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Paper,
    Snackbar,
    Stack,
    Typography,
} from '@mui/material';
import Sidebar from '../components/mydesk/Sidebar';
import CalendarPopover from '../components/mydesk/CalendarPopover';
import ScheduleModal from '../components/mydesk/ScheduleModal';
import { apiClient } from '../apiClient';
import { BACKEND_URL } from '../config/api';
import { MYDESK_NAV_ITEMS, MYDESK_PATH_TO_ID } from '../components/mydesk/config';
import {
    formatEventTime,
    groupEventsByDate,
    monthRangeKeys,
    sortEventsForDay,
    toDateKey,
} from '../components/mydesk/calendarUtils';
import {
    createCalendarEvent,
    fetchCalendarEvents,
    fetchCalendarStatus,
    fetchTeamMembers,
    redirectToGoogleAuth,
    syncCalendarRange,
} from '../components/mydesk/calendarService';
import FeatureSections from '../components/mydesk/FeatureSections';
import { MYDESK_NOTIFY_EVENT } from '../components/mydesk/mydeskNotifications';
import { useNavigate, useParams } from 'react-router-dom';

function buildEventPayload(formData) {
    const start = new Date(`${formData.date}T${formData.time}:00`);
    const end = new Date(start.getTime() + 60 * 60 * 1000);

    const attendees = formData.actionType === 'meeting'
        ? formData.participants
            .filter((member) => member?.email)
            .map((member) => ({ email: member.email }))
        : [];

    const detailLines = [];
    if (formData.actionType === 'meeting') {
        detailLines.push(`Platform: ${formData.platform === 'in_person' ? 'In-person' : 'Google Meet'}`);
    }
    if (formData.notes) {
        detailLines.push(`Notes: ${formData.notes}`);
    }

    const description = detailLines.join('\n');

    const eventType = formData.actionType === 'task'
        ? 'task'
        : formData.platform === 'in_person'
            ? 'personal'
            : 'meeting';

    return {
        title: formData.title,
        start: start.toISOString(),
        end: end.toISOString(),
        description,
        attendees,
        event_type: eventType,
        timezone: 'Asia/Kolkata',
    };
}

function resolveSectionFromPath(pathSegment) {
    if (!pathSegment) return 'my-notes';
    const id = MYDESK_PATH_TO_ID[pathSegment];
    return id || 'my-notes';
}

export default function TaskManager() {
    const { section: sectionParam } = useParams();
    const navigate = useNavigate();
    const [selectedSection, setSelectedSection] = useState(() => resolveSectionFromPath(sectionParam));

    const [calendarConnected, setCalendarConnected] = useState(false);
    const [calendarMonth, setCalendarMonth] = useState(() => {
        const today = new Date();
        return new Date(today.getFullYear(), today.getMonth(), 1);
    });
    const [calendarEvents, setCalendarEvents] = useState([]);
    const [calendarLoading, setCalendarLoading] = useState(false);
    const [calendarError, setCalendarError] = useState('');

    const [selectedDate, setSelectedDate] = useState(() => toDateKey(new Date()));
    const [popoverAnchorEl, setPopoverAnchorEl] = useState(null);

    const [scheduleOpen, setScheduleOpen] = useState(false);
    const [scheduleType, setScheduleType] = useState('meeting');
    const [scheduleSubmitting, setScheduleSubmitting] = useState(false);
    const [scheduleError, setScheduleError] = useState('');

    const [members, setMembers] = useState([]);
    const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });
    const [chatUnreadCount, setChatUnreadCount] = useState(0);

    const loadChatUnreadCount = useCallback(async () => {
        try {
            const res = await apiClient(`${BACKEND_URL}/api/chat/unread-count/`, { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                setChatUnreadCount(Number(data.count || 0));
            }
        } catch {
            // Ignore
        }
    }, []);

    useEffect(() => {
        loadChatUnreadCount();
        const interval = setInterval(loadChatUnreadCount, 5000);
        window.addEventListener('bridgeworks:chat-unread-updated', loadChatUnreadCount);
        return () => {
            clearInterval(interval);
            window.removeEventListener('bridgeworks:chat-unread-updated', loadChatUnreadCount);
        };
    }, [loadChatUnreadCount]);

    const navigationItems = useMemo(() => {
        return MYDESK_NAV_ITEMS.map((item) => {
            if (item.id === 'my-chats') {
                return { ...item, badgeCount: chatUnreadCount };
            }
            return item;
        });
    }, [chatUnreadCount]);

    const eventsByDate = useMemo(() => groupEventsByDate(calendarEvents), [calendarEvents]);
    const selectedDayEvents = useMemo(() => {
        return sortEventsForDay(eventsByDate[selectedDate] || []);
    }, [eventsByDate, selectedDate]);

    const loadMonthEvents = useCallback(async (monthDate) => {
        if (!calendarConnected) {
            setCalendarEvents([]);
            return;
        }

        setCalendarLoading(true);
        setCalendarError('');
        try {
            const { start, end } = monthRangeKeys(monthDate);
            const events = await fetchCalendarEvents({ start, end });
            setCalendarEvents(events);
        } catch (error) {
            if (error?.status === 403) {
                setCalendarConnected(false);
            }
            setCalendarEvents([]);
            setCalendarError(error.message || 'Unable to load calendar events.');
        } finally {
            setCalendarLoading(false);
        }
    }, [calendarConnected]);

    const loadCalendarStatus = useCallback(async () => {
        try {
            const status = await fetchCalendarStatus();
            setCalendarConnected(Boolean(status.connected));
        } catch {
            setCalendarConnected(false);
        }
    }, []);

    useEffect(() => {
        loadCalendarStatus();
        fetchTeamMembers().then(setMembers).catch(() => setMembers([]));
    }, [loadCalendarStatus]);

    useEffect(() => {
        const resolvedSection = resolveSectionFromPath(sectionParam);
        setSelectedSection((previous) => (previous === resolvedSection ? previous : resolvedSection));
    }, [sectionParam]);

    useEffect(() => {
        loadMonthEvents(calendarMonth);
    }, [calendarMonth, loadMonthEvents]);

    useEffect(() => {
        const onNotify = (event) => {
            const message = event?.detail?.message;
            if (!message) return;
            const severity = event?.detail?.severity === 'error' ? 'error' : 'success';
            setToast({ open: true, message, severity });

            const shouldRefreshCalendar = severity === 'success' && /(task|meeting|calendar|reminder)/i.test(message);
            if (shouldRefreshCalendar && calendarConnected) {
                loadMonthEvents(calendarMonth);
            }
        };

        window.addEventListener(MYDESK_NOTIFY_EVENT, onNotify);
        return () => window.removeEventListener(MYDESK_NOTIFY_EVENT, onNotify);
    }, [calendarConnected, calendarMonth, loadMonthEvents]);

    const handleDayClick = (dateKey, anchorNode) => {
        setSelectedDate(dateKey);
        setPopoverAnchorEl(anchorNode);
    };

    const handleOpenSchedule = (type) => {
        setScheduleType(type);
        setScheduleError('');
        setScheduleOpen(true);
    };

    const handleScheduleSubmit = async (formData) => {
        setScheduleSubmitting(true);
        setScheduleError('');

        try {
            const payload = buildEventPayload(formData);
            await createCalendarEvent(payload);
            setScheduleOpen(false);
            await loadMonthEvents(calendarMonth);
        } catch (error) {
            setScheduleError(error.message || 'Unable to schedule event.');
        } finally {
            setScheduleSubmitting(false);
        }
    };

    const handleSync = async () => {
        if (!calendarConnected) return;

        setCalendarLoading(true);
        setCalendarError('');

        try {
            const { start, end } = monthRangeKeys(calendarMonth);
            await syncCalendarRange({ start, end });
            await loadMonthEvents(calendarMonth);
        } catch (error) {
            setCalendarError(error.message || 'Unable to sync calendar.');
        } finally {
            setCalendarLoading(false);
        }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, height: '100%', minHeight: 0 }}>
            <Box
                sx={{
                    flex: 1,
                    minHeight: 0,
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    overflow: 'hidden',
                }}
            >
                <Sidebar
                    items={navigationItems}
                    selectedItem={selectedSection}
                    onSelectItem={(id) => {
                        const item = navigationItems.find((n) => n.id === id);
                        if (item) navigate(`/mydesk/${item.path}`);
                    }}
                    monthDate={calendarMonth}
                    eventsByDate={eventsByDate}
                    selectedDate={selectedDate}
                    calendarLoading={calendarLoading}
                    onPrevMonth={() => {
                        setCalendarMonth((previous) => new Date(previous.getFullYear(), previous.getMonth() - 1, 1));
                    }}
                    onNextMonth={() => {
                        setCalendarMonth((previous) => new Date(previous.getFullYear(), previous.getMonth() + 1, 1));
                    }}
                    onSyncCalendar={handleSync}
                    onDayClick={handleDayClick}
                />

                <Box
                    sx={{
                        flex: 1,
                        minWidth: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        p: ['my-chats', 'gallery', 'my-notes', 'my-email'].includes(selectedSection) ? 0 : { xs: 2, sm: 3 },
                        overflowY: ['my-chats', 'my-notes', 'my-email'].includes(selectedSection) ? 'hidden' : 'auto',
                        bgcolor: 'background.default',
                    }}
                >
                    {selectedSection !== 'my-chats' && !calendarConnected && (
                        <Alert
                            severity="warning"
                            sx={{ mb: 2 }}
                            action={(
                                <Button color="inherit" size="small" onClick={redirectToGoogleAuth}>
                                    Connect Google
                                </Button>
                            )}
                        >
                            Calendar sync is inactive. Connect Google Workspace to load meetings and event indicators.
                        </Alert>
                    )}

                    {selectedSection !== 'my-chats' && calendarError && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {calendarError}
                        </Alert>
                    )}

                    {selectedSection !== 'my-chats' && calendarLoading ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 2 }}>
                            <CircularProgress size={18} />
                            <Typography variant="body2" color="text.secondary">
                                Loading calendar...
                            </Typography>
                        </Box>
                    ) : null}

                    <FeatureSections sectionId={selectedSection} members={members} />


                </Box>
            </Box>

            <CalendarPopover
                anchorEl={popoverAnchorEl}
                open={Boolean(popoverAnchorEl)}
                selectedDate={selectedDate}
                events={selectedDayEvents}
                onClose={() => setPopoverAnchorEl(null)}
            />

            <ScheduleModal
                open={scheduleOpen}
                actionType={scheduleType}
                selectedDate={selectedDate}
                members={members}
                submitting={scheduleSubmitting}
                connected={calendarConnected}
                error={scheduleError}
                onClose={() => setScheduleOpen(false)}
                onSubmit={handleScheduleSubmit}
                onConnectGoogle={redirectToGoogleAuth}
            />

            <Snackbar
                open={toast.open}
                autoHideDuration={3500}
                onClose={() => setToast((previous) => ({ ...previous, open: false }))}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <Alert
                    onClose={() => setToast((previous) => ({ ...previous, open: false }))}
                    severity={toast.severity}
                    variant="filled"
                    sx={{ width: '100%' }}
                >
                    {toast.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}
