import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Avatar,
    Box,
    Button,
    Chip,
    CircularProgress,
    Divider,
    FormControl,
    IconButton,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import MiniCalendar from '../mydesk/MiniCalendar';
import { formatEventTime, monthRangeKeys, sortEventsForDay, toDateKey } from '../mydesk/calendarUtils';
import {
    createHrMeetingManagerCompanyEvent,
    deleteHrMeetingManagerCompanyEvent,
    listHrMeetingManagerOverview,
} from '../mydesk/mydeskService';

const EVENT_TYPE_META = {
    birthday: { label: 'Birthday', color: 'secondary', calendarType: 'birthday' },
    high_pressure: { label: 'High Pressure Day', color: 'error', calendarType: 'high_pressure' },
    holiday: { label: 'Holiday', color: 'success', calendarType: 'holiday' },
    event: { label: 'Event', color: 'info', calendarType: 'company_event' },
    big_sale: { label: 'Big Sale', color: 'warning', calendarType: 'big_sale' },
    annual_event: { label: 'Annual Event', color: 'primary', calendarType: 'annual_event' },
};

const EMPTY_OVERVIEW = {
    generated_at: '',
    range: { start: '', end: '' },
    default_selected_date: '',
    summary: {
        team_members: 0,
        calendar_connected_members: 0,
        total_meetings: 0,
        meeting_days: 0,
        company_events: 0,
    },
    event_type_options: [],
    members: [],
    meetings: [],
    company_events: [],
};

function formatDateHeading(dateKey) {
    if (!dateKey) return 'Selected day';
    const parsed = new Date(`${dateKey}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return dateKey;
    return parsed.toLocaleDateString(undefined, {
        weekday: 'long', day: '2-digit', month: 'short', year: 'numeric',
    });
}

function formatDateRange(startDate, endDate) {
    if (!startDate) return '-';
    if (!endDate || endDate === startDate) return formatDateHeading(startDate);
    return `${formatDateHeading(startDate)} – ${formatDateHeading(endDate)}`;
}

function eventOccursOnDate(eventItem, targetDateKey) {
    if (!eventItem || !targetDateKey) return false;
    const start = String(eventItem.start_date || '').trim();
    const end = String(eventItem.end_date || start || '').trim();
    if (!start) return false;
    return start <= targetDateKey && targetDateKey <= end;
}

function companyEventColor(eventType) {
    return EVENT_TYPE_META[String(eventType || '').trim().toLowerCase()]?.color || 'default';
}

function companyEventCalendarType(eventType) {
    return EVENT_TYPE_META[String(eventType || '').trim().toLowerCase()]?.calendarType || 'company_event';
}

export default function HRMeetingManager() {
    const initialDate = useMemo(() => new Date(), []);
    const [monthDate, setMonthDate] = useState(() => new Date(initialDate.getFullYear(), initialDate.getMonth(), 1));
    const [selectedDate, setSelectedDate] = useState(() => toDateKey(initialDate));
    const [overview, setOverview] = useState(EMPTY_OVERVIEW);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [formError, setFormError] = useState('');
    const [savingEvent, setSavingEvent] = useState(false);
    const [deletingEventId, setDeletingEventId] = useState(null);

    const [eventForm, setEventForm] = useState({
        title: '', event_type: 'event',
        start_date: toDateKey(initialDate), end_date: '', description: '',
    });

    const [searchText, setSearchText] = useState('');
    const [departmentFilter, setDepartmentFilter] = useState('all');
    const [hostFilter, setHostFilter] = useState('all');
    const [eventTypeFilter, setEventTypeFilter] = useState('all');

    const loadOverview = useCallback(async (targetMonthDate = monthDate) => {
        const { start, end } = monthRangeKeys(targetMonthDate);
        setLoading(true);
        setError('');
        try {
            const response = await listHrMeetingManagerOverview({ start, end });
            const normalized = {
                ...EMPTY_OVERVIEW, ...(response || {}),
                summary: { ...EMPTY_OVERVIEW.summary, ...(response?.summary || {}) },
                event_type_options: Array.isArray(response?.event_type_options) ? response.event_type_options : [],
                members: Array.isArray(response?.members) ? response.members : [],
                meetings: Array.isArray(response?.meetings) ? response.meetings : [],
                company_events: Array.isArray(response?.company_events) ? response.company_events : [],
            };
            setOverview(normalized);
            setSelectedDate((prev) => (prev && prev >= start && prev <= end) ? prev : start);
            setEventForm((prev) => ({
                ...prev,
                start_date: selectedDate >= start && selectedDate <= end ? selectedDate : start,
            }));
        } catch (err) {
            setOverview(EMPTY_OVERVIEW);
            setError(err?.message || 'Unable to load meeting manager data.');
        } finally {
            setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [monthDate]);

    useEffect(() => { loadOverview(monthDate); }, [monthDate, loadOverview]);

    const eventTypeOptions = useMemo(() => {
        if (overview.event_type_options.length > 0) return overview.event_type_options;
        return Object.entries(EVENT_TYPE_META).map(([value, item]) => ({ value, label: item.label }));
    }, [overview.event_type_options]);

    const departmentsList = useMemo(() => {
        const deps = new Set((overview.members || []).map((m) => m.department).filter(Boolean));
        return Array.from(deps).sort();
    }, [overview.members]);

    const filteredMeetings = useMemo(() => {
        let arr = overview.meetings || [];
        if (departmentFilter !== 'all') {
            arr = arr.filter((m) => m.created_by?.department === departmentFilter);
        }
        if (hostFilter !== 'all') {
            arr = arr.filter((m) => String(m.created_by?.id) === hostFilter);
        }
        if (searchText) {
            const lower = searchText.toLowerCase();
            arr = arr.filter((m) => 
                (m.title || '').toLowerCase().includes(lower) || 
                (m.agenda || '').toLowerCase().includes(lower) ||
                (m.created_by?.name || '').toLowerCase().includes(lower) ||
                (m.created_by?.email || '').toLowerCase().includes(lower)
            );
        }
        return arr;
    }, [overview.meetings, departmentFilter, hostFilter, searchText]);

    const filteredCompanyEvents = useMemo(() => {
        let arr = overview.company_events || [];
        if (eventTypeFilter !== 'all') {
            arr = arr.filter((ev) => ev.event_type === eventTypeFilter);
        }
        if (searchText) {
            const lower = searchText.toLowerCase();
            arr = arr.filter((ev) => 
                (ev.title || '').toLowerCase().includes(lower) || 
                (ev.description || '').toLowerCase().includes(lower)
            );
        }
        return arr;
    }, [overview.company_events, eventTypeFilter, searchText]);

    const calendarEventsByDate = useMemo(() => {
        const map = {};
        filteredMeetings.forEach((m) => {
            const dk = String(m.day_key || '').trim();
            if (!dk) return;
            if (!map[dk]) map[dk] = [];
            map[dk].push({ calendarType: 'meeting', id: m.id });
        });
        filteredCompanyEvents.forEach((ev) => {
            const s = String(ev.start_date || '').trim();
            const e = String(ev.end_date || s || '').trim();
            if (!s) return;
            const sd = new Date(`${s}T00:00:00`);
            const ed = new Date(`${e}T00:00:00`);
            if (isNaN(sd) || isNaN(ed)) return;
            const cur = new Date(sd);
            let g = 0;
            while (cur <= ed && g < 366) {
                const dk = toDateKey(cur);
                if (dk) {
                    if (!map[dk]) map[dk] = [];
                    map[dk].push({ calendarType: companyEventCalendarType(ev.event_type), id: ev.id });
                }
                cur.setDate(cur.getDate() + 1);
                g++;
            }
        });
        return map;
    }, [filteredCompanyEvents, filteredMeetings]);

    const selectedDayMeetings = useMemo(() =>
        sortEventsForDay(filteredMeetings.filter((m) => String(m.day_key || '').trim() === selectedDate)),
        [filteredMeetings, selectedDate]
    );

    const selectedDayCompanyEvents = useMemo(() =>
        filteredCompanyEvents.filter((ev) => eventOccursOnDate(ev, selectedDate)),
        [filteredCompanyEvents, selectedDate]
    );

    const handleResetFilters = () => {
        setSearchText('');
        setDepartmentFilter('all');
        setHostFilter('all');
        setEventTypeFilter('all');
    };

    const handleRefresh = () => loadOverview(monthDate);
    const patchForm = (key) => (e) => setEventForm((prev) => ({ ...prev, [key]: e.target.value }));

    const handleCreateCompanyEvent = async () => {
        if (!eventForm.start_date) { setFormError('Please select a start date.'); return; }
        if (eventForm.end_date && eventForm.end_date < eventForm.start_date) {
            setFormError('End date should be on or after start date.');
            return;
        }
        setFormError('');
        setSavingEvent(true);
        try {
            await createHrMeetingManagerCompanyEvent({
                title: String(eventForm.title || '').trim(),
                event_type: eventForm.event_type,
                start_date: eventForm.start_date,
                end_date: eventForm.end_date || undefined,
                description: String(eventForm.description || '').trim(),
            });
            setEventForm((prev) => ({ ...prev, title: '', description: '', end_date: '' }));
            await loadOverview(monthDate);
        } catch (err) {
            setFormError(err?.message || 'Unable to create company calendar event.');
        } finally {
            setSavingEvent(false);
        }
    };

    const handleDeleteCompanyEvent = async (id) => {
        setDeletingEventId(id);
        try { await deleteHrMeetingManagerCompanyEvent(id); await loadOverview(monthDate); }
        catch { /* handled in service */ }
        finally { setDeletingEventId(null); }
    };

    return (
        <Box sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 2.25 }}>

            {/* ── Summary bar ── */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
                    <Chip label={`Team Members: ${overview.summary.team_members || 0}`} size="small" />
                    <Chip label={`Connected Calendars: ${overview.summary.calendar_connected_members || 0}`} color="info" size="small" />
                    <Chip label={`Meetings: ${overview.summary.total_meetings || 0}`} color="primary" size="small" />
                    <IconButton size="small" onClick={handleRefresh} disabled={loading}>
                        <RefreshIcon fontSize="small" />
                    </IconButton>
                </Stack>
            </Paper>

            {error && <Alert severity="error">{error}</Alert>}

            {/* ── Filter bar ── */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} flexWrap="wrap" alignItems="center">
                    <TextField
                        label="Search Meetings"
                        size="small"
                        value={searchText}
                        onChange={(event) => setSearchText(event.target.value)}
                        sx={{ minWidth: 220, flexGrow: 1 }}
                        placeholder="Title, description, host, members"
                    />

                    <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Department</InputLabel>
                        <Select
                            label="Department"
                            value={departmentFilter}
                            onChange={(event) => setDepartmentFilter(event.target.value)}
                        >
                            <MenuItem value="all">All Departments</MenuItem>
                            {departmentsList.map((dept) => (
                                <MenuItem key={dept} value={dept}>{dept}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Host / Creator</InputLabel>
                        <Select
                            label="Host / Creator"
                            value={hostFilter}
                            onChange={(event) => setHostFilter(event.target.value)}
                        >
                            <MenuItem value="all">All Hosts</MenuItem>
                            {(overview.members || []).map((item) => (
                                <MenuItem key={item.id} value={item.id}>
                                    {item.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Event Type</InputLabel>
                        <Select
                            label="Event Type"
                            value={eventTypeFilter}
                            onChange={(event) => setEventTypeFilter(event.target.value)}
                        >
                            <MenuItem value="all">All Events</MenuItem>
                            {eventTypeOptions.map((item) => (
                                <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <Button variant="text" onClick={handleResetFilters}>
                        Reset
                    </Button>
                </Stack>
            </Paper>


            <Box
                sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    alignItems: 'flex-start',
                    gap: 2.25,
                    width: '100%',
                }}
            >
                {/* ── LEFT ── */}
                <Box sx={{ flexShrink: 0, width: { xs: '100%', md: 280 }, display: 'flex', flexDirection: 'column', gap: 2.25 }}>
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <MiniCalendar
                            monthDate={monthDate}
                            eventsByDate={calendarEventsByDate}
                            selectedDate={selectedDate}
                            loading={loading}
                            onPrevMonth={() => setMonthDate((p) => new Date(p.getFullYear(), p.getMonth() - 1, 1))}
                            onNextMonth={() => setMonthDate((p) => new Date(p.getFullYear(), p.getMonth() + 1, 1))}
                            onSync={handleRefresh}
                            onDayClick={(dk) => {
                                setSelectedDate(dk);
                                setEventForm((p) => ({ ...p, start_date: dk }));
                            }}
                        />
                    </Paper>

                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
                            Add Company Event
                        </Typography>
                        <Stack spacing={1.25}>
                            <TextField label="Event Title" size="small" value={eventForm.title} onChange={patchForm('title')} placeholder="Optional title" />

                            <FormControl size="small">
                                <InputLabel>Event Type</InputLabel>
                                <Select label="Event Type" value={eventForm.event_type} onChange={patchForm('event_type')}>
                                    {eventTypeOptions.map((o) => (
                                        <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <Stack direction="row" spacing={1}>
                                <TextField label="Start Date" type="date" size="small" InputLabelProps={{ shrink: true }} value={eventForm.start_date} onChange={patchForm('start_date')} fullWidth />
                                <TextField label="End Date" type="date" size="small" InputLabelProps={{ shrink: true }} value={eventForm.end_date} onChange={patchForm('end_date')} fullWidth />
                            </Stack>

                            <TextField
                                label="Description / Agenda" size="small" multiline minRows={2}
                                value={eventForm.description} onChange={patchForm('description')}
                                placeholder="Reason, context, or notes for HR team"
                            />

                            {formError && <Alert severity="error">{formError}</Alert>}

                            <Button variant="contained" onClick={handleCreateCompanyEvent} disabled={savingEvent}>
                                {savingEvent ? 'Saving…' : 'Add To Company Calendar'}
                            </Button>
                        </Stack>
                    </Paper>
                </Box>

                {/* ── RIGHT — flex:1 fills all remaining horizontal space ── */}
                <Box
                    sx={{
                        flex: '1 1 0%',   /* grow to fill, base of 0 so it never starts oversized */
                        minWidth: 0,      /* allow shrinking below intrinsic content width */
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2.25,
                    }}
                >
                    {/* ── Meetings card ── */}
                    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                        <Stack
                            direction={{ xs: 'column', sm: 'row' }}
                            spacing={1}
                            alignItems={{ xs: 'flex-start', sm: 'center' }}
                            justifyContent="space-between"
                            sx={{ px: 2, pt: 1.75, pb: 1.25 }}
                        >
                            <Typography variant="h6" sx={{ fontWeight: 700 }}>
                                Meetings On {formatDateHeading(selectedDate)}
                            </Typography>
                            <Chip color="primary" size="small"
                                label={`${selectedDayMeetings.length} meeting${selectedDayMeetings.length === 1 ? '' : 's'}`} />
                        </Stack>

                        <Divider />

                        {loading ? (
                            <Box sx={{ py: 5, textAlign: 'center' }}><CircularProgress size={28} /></Box>
                        ) : selectedDayMeetings.length === 0 ? (
                            <Typography variant="body2" sx={{ color: 'text.secondary', px: 2, py: 1.5 }}>
                                No meetings found for this day.
                            </Typography>
                        ) : (
                            <Box sx={{ width: '100%', overflowX: 'auto' }}>
                                {/* Column header */}
                                <Box sx={{
                                    display: 'grid',
                                    gridTemplateColumns: '14% 24% 16% 22% 24%',
                                    minWidth: 560,
                                    px: 1.5, py: 0.75,
                                    bgcolor: 'action.hover',
                                    borderBottom: '1px solid',
                                    borderColor: 'divider',
                                }}>
                                    {['Meeting Title', 'Description', 'Time', 'Host', 'Members'].map((col) => (
                                        <Typography key={col} variant="caption" sx={{
                                            fontWeight: 700, color: 'text.secondary',
                                            textTransform: 'uppercase', letterSpacing: 0.5, fontSize: '0.65rem',
                                        }}>
                                            {col}
                                        </Typography>
                                    ))}
                                </Box>

                                {/* Data rows */}
                                {selectedDayMeetings.map((meeting, idx) => {
                                    const createdBy = meeting.created_by || {};
                                    const attendees = meeting.attendees || [];
                                    const timeStr = formatEventTime(meeting.start);
                                    const endTimeStr = meeting.end ? formatEventTime(meeting.end) : '';
                                    const timeDisplay = timeStr
                                        ? (endTimeStr && endTimeStr !== timeStr ? `${timeStr} – ${endTimeStr}` : timeStr)
                                        : 'All day';

                                    return (
                                        <Box
                                            key={meeting.dedupe_key || meeting.id}
                                            sx={{
                                                display: 'grid',
                                                gridTemplateColumns: '14% 24% 16% 22% 24%',
                                                minWidth: 560,
                                                alignItems: 'stretch',
                                                borderBottom: idx < selectedDayMeetings.length - 1 ? '1px solid' : 'none',
                                                borderColor: 'divider',
                                                borderLeft: '4px solid',
                                                borderLeftColor: 'primary.main',
                                                bgcolor: idx % 2 === 0 ? 'background.paper' : 'grey.50',
                                                '&:hover': { bgcolor: 'primary.50' },
                                                transition: 'background-color 0.15s',
                                            }}
                                        >
                                            {/* Title */}
                                            <Box sx={{ px: 1, py: 1, borderRight: '1px solid', borderColor: 'divider', minWidth: 0 }}>
                                                <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.78rem', lineHeight: 1.3, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                                    {meeting.title || '(No title)'}
                                                </Typography>
                                                {meeting.company && (
                                                    <Chip size="small" color="info" variant="outlined" label={meeting.company}
                                                        sx={{ mt: 0.5, height: 16, fontSize: '0.6rem', '& .MuiChip-label': { px: 0.6 } }} />
                                                )}
                                            </Box>

                                            {/* Description */}
                                            <Box sx={{ px: 1, py: 1, borderRight: '1px solid', borderColor: 'divider', minWidth: 0 }}>
                                                {meeting.agenda ? (
                                                    <Typography variant="body2" sx={{ fontSize: '0.72rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.4 }}>
                                                        {meeting.agenda}
                                                    </Typography>
                                                ) : (
                                                    <Typography variant="caption" color="text.disabled" fontStyle="italic" sx={{ fontSize: '0.68rem' }}>
                                                        No agenda shared.
                                                    </Typography>
                                                )}
                                            </Box>

                                            {/* Time */}
                                            <Box sx={{ px: 1, py: 1, borderRight: '1px solid', borderColor: 'divider', minWidth: 0 }}>
                                                <Typography variant="caption" sx={{ fontWeight: 700, color: 'primary.main', fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                                                    {timeDisplay}
                                                </Typography>
                                            </Box>

                                            {/* Host */}
                                            <Box sx={{ px: 1, py: 1, borderRight: '1px solid', borderColor: 'divider', minWidth: 0 }}>
                                                {createdBy?.name ? (
                                                    <Stack spacing={0.15}>
                                                        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem', wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                                            {createdBy.name}
                                                        </Typography>
                                                        {createdBy.email && (
                                                            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.62rem', wordBreak: 'break-all', display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                                                {createdBy.email}
                                                            </Typography>
                                                        )}
                                                    </Stack>
                                                ) : (
                                                    <Typography variant="caption" color="text.disabled" fontStyle="italic">—</Typography>
                                                )}
                                            </Box>

                                            {/* Members */}
                                            <Box sx={{ px: 1, py: 1, minWidth: 0 }}>
                                                <Stack direction="row" spacing={0.4} alignItems="center" sx={{ mb: 0.3 }}>
                                                    <GroupsOutlinedIcon sx={{ fontSize: 11, color: 'text.secondary', flexShrink: 0 }} />
                                                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, fontSize: '0.62rem' }}>
                                                        Members ({attendees.length})
                                                    </Typography>
                                                </Stack>
                                                {attendees.length === 0 ? (
                                                    <Typography variant="caption" color="text.disabled" fontStyle="italic" sx={{ fontSize: '0.68rem' }}>No attendees.</Typography>
                                                ) : (
                                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.35 }}>
                                                        {attendees.slice(0, 8).map((att, i) => {
                                                            const initials = (att.name || att.email || '?').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
                                                            const tip = [att.name, att.email ? `<${att.email}>` : '', att.company ? `· ${att.company}` : ''].filter(Boolean).join(' ');
                                                            return (
                                                                <Tooltip key={`${meeting.id}-${att.email || i}`} title={tip} arrow placement="top">
                                                                    <Chip size="small"
                                                                        avatar={<Avatar sx={{ width: 14, height: 14, fontSize: '0.45rem' }}>{initials}</Avatar>}
                                                                        label={att.name || att.email || 'Participant'}
                                                                        variant="outlined"
                                                                        sx={{ height: 18, fontSize: '0.62rem', '& .MuiChip-label': { px: 0.5 } }}
                                                                    />
                                                                </Tooltip>
                                                            );
                                                        })}
                                                        {attendees.length > 8 && (
                                                            <Chip size="small" variant="outlined" label={`+${attendees.length - 8}`}
                                                                sx={{ height: 18, fontSize: '0.62rem', '& .MuiChip-label': { px: 0.5 } }} />
                                                        )}
                                                    </Box>
                                                )}
                                            </Box>
                                        </Box>
                                    );
                                })}
                            </Box>
                        )}
                    </Paper>

                    {/* ── Company events card ── */}
                    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                        <Stack
                            direction={{ xs: 'column', sm: 'row' }}
                            spacing={1}
                            alignItems={{ xs: 'flex-start', sm: 'center' }}
                            justifyContent="space-between"
                        >
                            <Typography variant="h6" sx={{ fontWeight: 700 }}>
                                Events On {formatDateHeading(selectedDate)}
                            </Typography>
                            <Chip size="small" color="secondary"
                                label={`${selectedDayCompanyEvents.length} event${selectedDayCompanyEvents.length === 1 ? '' : 's'}`} />
                        </Stack>

                        <Divider sx={{ my: 1.5 }} />

                        {selectedDayCompanyEvents.length === 0 ? (
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                No company-level events for this day.
                            </Typography>
                        ) : (
                            <Stack spacing={1.25}>
                                {selectedDayCompanyEvents.map((ev) => (
                                    <Paper key={ev.id} variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
                                        <Stack direction="row" justifyContent="space-between" spacing={1}>
                                            <Box sx={{ minWidth: 0 }}>
                                                <Stack direction="row" spacing={0.75} flexWrap="wrap" alignItems="center">
                                                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{ev.title || 'Event'}</Typography>
                                                    <Chip size="small" color={companyEventColor(ev.event_type)}
                                                        label={ev.event_type_label || EVENT_TYPE_META[ev.event_type]?.label || 'Event'} />
                                                </Stack>
                                                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.35 }}>
                                                    {formatDateRange(ev.start_date, ev.end_date)}
                                                </Typography>
                                                {ev.description && (
                                                    <Typography variant="body2" sx={{ mt: 0.8 }}>{ev.description}</Typography>
                                                )}
                                            </Box>
                                            <IconButton size="small" color="error"
                                                onClick={() => handleDeleteCompanyEvent(ev.id)}
                                                disabled={deletingEventId === ev.id}
                                            >
                                                <DeleteOutlineIcon fontSize="small" />
                                            </IconButton>
                                        </Stack>
                                    </Paper>
                                ))}
                            </Stack>
                        )}
                    </Paper>
                </Box>
            </Box>
        </Box>
    );
}