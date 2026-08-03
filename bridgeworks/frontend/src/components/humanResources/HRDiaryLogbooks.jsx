import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    FormControl,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    CalendarToday as CalendarIcon,
    Download as DownloadIcon,
    Refresh as RefreshIcon,
    Schedule as ScheduleIcon,
    StickyNote2 as NoteIcon,
} from '@mui/icons-material';
import { listHrDiaryLogbooks } from '../mydesk/mydeskService';

// ─── helpers ────────────────────────────────────────────────────────────────

function getLocalDate(date = new Date()) {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
}

function formatDate(value) {
    if (!value) return '-';
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}



const TYPE_COLOR = {
    work: 'primary',
    meeting: 'secondary',
    learning: 'info',
    review: 'warning',
    issue: 'error',
};

// ─── StatCard ───────────────────────────────────────────────────────────────

function StatCard({ title, value, subtitle, color }) {
    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                borderRadius: 2,
                borderTop: '3px solid',
                borderTopColor: color,
                minHeight: 110,
            }}
        >
            <Typography
                variant="caption"
                sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5 }}
            >
                {title}
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color, mt: 0.75 }}>
                {value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
                {subtitle}
            </Typography>
        </Paper>
    );
}

// ─── MemberCard ─────────────────────────────────────────────────────────────

function MemberCard({ member, onClick }) {
    const entries = member.entry_count ?? 0;
    const hours = Number(member.total_hours ?? 0).toFixed(1);
    const name = member.name || 'Unknown';
    const initials = name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase();

    return (
        <Paper
            variant="outlined"
            sx={{
                p: 1.5,
                borderRadius: 2,
                cursor: 'pointer',
                transition: 'box-shadow 0.15s, border-color 0.15s',
                '&:hover': { borderColor: 'primary.main', boxShadow: 3 },
            }}
            onClick={() => onClick(member)}
        >
            <Stack spacing={0.75}>
                <Stack direction="row" alignItems="center" spacing={1}>
                    <Box
                        sx={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            bgcolor: 'primary.main',
                            color: 'primary.contrastText',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            flexShrink: 0,
                        }}
                    >
                        {initials}
                    </Box>
                    <Box sx={{ minWidth: 0 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }} noWrap>
                            {name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                            {member.email || '—'}
                        </Typography>
                    </Box>
                </Stack>

                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {hours}h
                </Typography>

                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                    <Chip size="small" label={`Entries ${entries}`} variant="outlined" />
                </Stack>
            </Stack>
        </Paper>
    );
}

// ─── Overview ───────────────────────────────────────────────────────────────

function Overview({ onMemberClick }) {
    const defaultStart = getLocalDate(new Date(Date.now() - 7 * 86400000));
    const defaultEnd = getLocalDate();

    const [startDate, setStartDate] = useState(defaultStart);
    const [endDate, setEndDate] = useState(defaultEnd);
    const [memberFilter, setMemberFilter] = useState('all');
    const [entryTypeFilter, setEntryTypeFilter] = useState('all');
    const [sortBy, setSortBy] = useState('newest');

    const [data, setData] = useState({ summary: {}, members: [], entries: [] });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const res = await listHrDiaryLogbooks({
                start_date: startDate,
                end_date: endDate,
                user_id: memberFilter === 'all' ? '' : memberFilter,
                entry_type: entryTypeFilter === 'all' ? '' : entryTypeFilter,
                order: sortBy,
            });
            setData(res || { summary: {}, members: [], entries: [] });
        } catch (err) {
            setError(err?.message || 'Unable to load diary logbooks.');
        } finally {
            setLoading(false);
        }
    }, [startDate, endDate, memberFilter, entryTypeFilter, sortBy]);

    useEffect(() => { load(); }, [load]);

    const summary = data.summary || {};
    const members = data.members || [];
    const entries = data.entries || [];

    // Build per-member stats from entries for the cards
    const memberStats = useMemo(() => {
        const map = {};
        entries.forEach((e) => {
            if (!map[e.user_id]) {
                map[e.user_id] = {
                    id: e.user_id,
                    name: e.user_name || '—',
                    email: e.user_email || '',
                    entry_count: 0,
                    total_hours: 0,
                };
            }
            map[e.user_id].entry_count += 1;
            map[e.user_id].total_hours += Number(e.hours || 0);
        });

        // Merge with the members list (includes members with 0 entries too)
        members.forEach((m) => {
            if (!map[m.id]) {
                map[m.id] = { id: m.id, name: m.name, email: m.email, entry_count: 0, total_hours: 0 };
            }
        });

        return Object.values(map);
    }, [entries, members]);

    const filteredEntries = useMemo(() => {
        let rows = [...entries];
        if (sortBy === 'oldest') rows.sort((a, b) => a.entry_date?.localeCompare(b.entry_date));
        else rows.sort((a, b) => b.entry_date?.localeCompare(a.entry_date));
        return rows;
    }, [entries, sortBy]);

    return (
        <Stack spacing={2} sx={{ p: { xs: 1.5, md: 4 } }}>
            {/* ── toolbar ── */}
            <Paper variant="outlined" sx={{ p: 1, borderRadius: 2 }}>
                <Box sx={{ overflowX: 'auto', pt: 1.5, pb: 1 }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 900 }}>
                        <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
                            Refresh
                        </Button>
                        <TextField
                            type="date" size="small" label="Start Date"
                            InputLabelProps={{ shrink: true }} value={startDate}
                            onChange={(e) => setStartDate(e.target.value)} sx={{ width: 145 }}
                        />
                        <TextField
                            type="date" size="small" label="End Date"
                            InputLabelProps={{ shrink: true }} value={endDate}
                            onChange={(e) => setEndDate(e.target.value)} sx={{ width: 145 }}
                        />
                        <FormControl size="small" sx={{ minWidth: 160 }}>
                            <InputLabel>Member</InputLabel>
                            <Select label="Member" value={memberFilter} onChange={(e) => setMemberFilter(e.target.value)}>
                                <MenuItem value="all">All Members</MenuItem>
                                {members.map((m) => (
                                    <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 150 }}>
                            <InputLabel>Entry Type</InputLabel>
                            <Select label="Entry Type" value={entryTypeFilter} onChange={(e) => setEntryTypeFilter(e.target.value)}>
                                <MenuItem value="all">All Types</MenuItem>
                                <MenuItem value="work">Work</MenuItem>
                                <MenuItem value="meeting">Meeting</MenuItem>
                                <MenuItem value="learning">Learning</MenuItem>
                                <MenuItem value="review">Review</MenuItem>
                                <MenuItem value="issue">Issue</MenuItem>
                            </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 160 }}>
                            <InputLabel>Sort By</InputLabel>
                            <Select label="Sort By" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                                <MenuItem value="newest">Date: Newest</MenuItem>
                                <MenuItem value="oldest">Date: Oldest</MenuItem>
                            </Select>
                        </FormControl>
                    </Stack>
                </Box>
            </Paper>

            {error && <Alert severity="error">{error}</Alert>}

            {/* ── stat cards ── */}
            <Grid container spacing={1.5}>
                {[
                    { title: 'Total Logged Hours', value: `${Number(summary.total_hours || 0).toFixed(1)}h`, subtitle: `${summary.total_entries || 0} total entries`, color: '#3949ab' },
                    { title: 'Active Members', value: summary.member_count || 0, subtitle: 'with log entries', color: '#2e7d32' },
                    { title: 'Total Entries', value: summary.total_entries || 0, subtitle: 'across all members', color: '#ef6c00' },
                    { title: 'Avg Hours / Entry', value: summary.total_entries ? `${(summary.total_hours / summary.total_entries).toFixed(1)}h` : '—', subtitle: 'per log entry', color: '#6a1b9a' },
                ].map((card) => (
                    <Grid item xs={12} sm={6} md={3} key={card.title}>
                        <StatCard {...card} />
                    </Grid>
                ))}
            </Grid>

            {/* ── team member cards ── */}
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1.25, color: 'text.secondary' }}>
                    Team Members
                </Typography>
                {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                        <CircularProgress size={28} />
                    </Box>
                ) : (
                    <Grid container spacing={1.5}>
                        {memberStats.length === 0 && (
                            <Grid item xs={12}>
                                <Typography variant="body2" color="text.secondary">No members found.</Typography>
                            </Grid>
                        )}
                        {memberStats.map((m) => (
                            <Grid item xs={12} sm={6} md={4} lg={3} key={m.id}>
                                <MemberCard member={m} onClick={onMemberClick} />
                            </Grid>
                        ))}
                    </Grid>
                )}
            </Paper>

            {/* ── recent log entries table ── */}
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="center"
                    sx={{ px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}
                >
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Log Entries</Typography>
                    <Typography variant="caption" color="text.secondary">{filteredEntries.length} rows</Typography>
                </Stack>
                <TableContainer sx={{ maxHeight: 420 }}>
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow>
                                <TableCell>Member</TableCell>
                                <TableCell>Title</TableCell>
                                <TableCell align="right">Hours</TableCell>
                                <TableCell>Date</TableCell>
                                <TableCell>Type</TableCell>

                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filteredEntries.map((entry) => (
                                <TableRow
                                    key={entry.id}
                                    hover
                                    sx={{ cursor: 'pointer' }}
                                    onClick={() => {
                                        const member = memberStats.find((m) => m.id === entry.user_id);
                                        if (member) onMemberClick(member);
                                    }}
                                >
                                    <TableCell>
                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{entry.user_name}</Typography>
                                        <Typography variant="caption" color="text.secondary">{entry.user_email}</Typography>
                                    </TableCell>
                                    <TableCell>
                                        <Typography variant="body2" color="primary.main" sx={{ fontWeight: 500 }}>
                                            {entry.title}
                                        </Typography>
                                    </TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700 }}>{entry.hours}h</TableCell>
                                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(entry.entry_date)}</TableCell>
                                    <TableCell>
                                        <Chip size="small" label={entry.entry_type} color={TYPE_COLOR[entry.entry_type] || 'default'} />
                                    </TableCell>

                                </TableRow>
                            ))}
                            {!loading && filteredEntries.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={6}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                                            No diary entries found for the selected filters.
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Stack>
    );
}

// ─── MemberDetail ────────────────────────────────────────────────────────────

function MemberDetail({ member, onBack }) {
    const [startDate, setStartDate] = useState(getLocalDate(new Date(Date.now() - 30 * 86400000)));
    const [endDate, setEndDate] = useState(getLocalDate());
    const [entryTypeFilter, setEntryTypeFilter] = useState('all');

    const [data, setData] = useState({ summary: {}, members: [], entries: [] });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const res = await listHrDiaryLogbooks({
                user_id: member.id,
                start_date: startDate,
                end_date: endDate,
                entry_type: entryTypeFilter === 'all' ? '' : entryTypeFilter,
                order: 'newest',
            });
            setData(res || { summary: {}, members: [], entries: [] });
        } catch (err) {
            setError(err?.message || 'Unable to load member diary.');
        } finally {
            setLoading(false);
        }
    }, [member.id, startDate, endDate, entryTypeFilter]);

    useEffect(() => { load(); }, [load]);

    const entries = data.entries || [];
    const summary = data.summary || {};

    // Group entries by date for day-wise view
    const dayGroups = useMemo(() => {
        const map = {};
        entries.forEach((e) => {
            const d = e.entry_date || 'unknown';
            if (!map[d]) map[d] = [];
            map[d].push(e);
        });
        return Object.entries(map).sort(([a], [b]) => b.localeCompare(a));
    }, [entries]);

    const totalHours = entries.reduce((sum, e) => sum + Number(e.hours || 0), 0);

    return (
        <Stack spacing={2} sx={{ p: { xs: 1.5, md: 2 } }}>
            {/* ── header ── */}
            <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Button variant="text" startIcon={<ArrowBackIcon />} onClick={onBack}>
                    Back to Overview
                </Button>
                <Typography variant="caption" color="text.secondary">Day-wise Diary</Typography>
            </Stack>

            {/* ── member banner ── */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'flex-start', sm: 'center' }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                        <Box
                            sx={{
                                width: 44, height: 44, borderRadius: '50%',
                                bgcolor: 'primary.main', color: 'primary.contrastText',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '1rem', fontWeight: 700, flexShrink: 0,
                            }}
                        >
                            {(member.name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()}
                        </Box>
                        <Box>
                            <Typography variant="h6" sx={{ fontWeight: 700 }}>{member.name}</Typography>
                            <Typography variant="body2" color="text.secondary">{member.email}</Typography>
                        </Box>
                    </Stack>
                    <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Box sx={{ textAlign: 'center' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: 'primary.main' }}>{totalHours.toFixed(1)}h</Typography>
                            <Typography variant="caption" color="text.secondary">Total Hours</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'center' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800 }}>{entries.length}</Typography>
                            <Typography variant="caption" color="text.secondary">Entries</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'center' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800 }}>{dayGroups.length}</Typography>
                            <Typography variant="caption" color="text.secondary">Days</Typography>
                        </Box>
                    </Stack>
                </Stack>
            </Paper>

            {/* ── filters ── */}
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} flexWrap="wrap" useFlexGap>
                <TextField
                    type="date" size="small" label="Start Date"
                    InputLabelProps={{ shrink: true }} value={startDate}
                    onChange={(e) => setStartDate(e.target.value)} sx={{ width: 145 }}
                />
                <TextField
                    type="date" size="small" label="End Date"
                    InputLabelProps={{ shrink: true }} value={endDate}
                    onChange={(e) => setEndDate(e.target.value)} sx={{ width: 145 }}
                />
                <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Entry Type</InputLabel>
                    <Select label="Entry Type" value={entryTypeFilter} onChange={(e) => setEntryTypeFilter(e.target.value)}>
                        <MenuItem value="all">All Types</MenuItem>
                        <MenuItem value="work">Work</MenuItem>
                        <MenuItem value="meeting">Meeting</MenuItem>
                        <MenuItem value="learning">Learning</MenuItem>
                        <MenuItem value="review">Review</MenuItem>
                        <MenuItem value="issue">Issue</MenuItem>
                    </Select>
                </FormControl>
                <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
                    Apply
                </Button>
            </Stack>

            {error && <Alert severity="error">{error}</Alert>}

            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress />
                </Box>
            )}

            {/* ── day-wise timeline ── */}
            {!loading && dayGroups.length === 0 && (
                <Paper variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">No diary entries found for this period.</Typography>
                </Paper>
            )}

            {!loading && dayGroups.map(([date, dayEntries]) => {
                const dayHours = dayEntries.reduce((s, e) => s + Number(e.hours || 0), 0);
                return (
                    <Paper key={date} variant="outlined" sx={{ borderRadius: 2 }}>
                        {/* day header */}
                        <Box
                            sx={{
                                px: 2, py: 1.25,
                                borderBottom: '1px solid', borderColor: 'divider',
                                bgcolor: 'action.hover',
                                borderTopLeftRadius: 8, borderTopRightRadius: 8,
                            }}
                        >
                            <Stack direction="row" alignItems="center" justifyContent="space-between">
                                <Stack direction="row" alignItems="center" spacing={1}>
                                    <CalendarIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                                        {formatDate(date)}
                                    </Typography>
                                    <Chip size="small" label={`${dayEntries.length} ${dayEntries.length === 1 ? 'entry' : 'entries'}`} variant="outlined" />
                                </Stack>
                                <Stack direction="row" alignItems="center" spacing={0.5}>
                                    <ScheduleIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'primary.main' }}>
                                        {dayHours.toFixed(1)}h
                                    </Typography>
                                </Stack>
                            </Stack>
                        </Box>

                        {/* entries for this day */}
                        <Stack divider={<Box sx={{ borderBottom: '1px solid', borderColor: 'divider' }} />}>
                            {dayEntries.map((entry) => (
                                <Box key={entry.id} sx={{ px: 2, py: 1.5 }}>
                                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between">
                                        <Box sx={{ flex: 1 }}>
                                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                                                <NoteIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
                                                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                                                    {entry.title}
                                                </Typography>
                                            </Stack>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{
                                                    display: '-webkit-box',
                                                    WebkitLineClamp: 3,
                                                    WebkitBoxOrient: 'vertical',
                                                    overflow: 'hidden',
                                                    mb: 1,
                                                }}
                                            >
                                                {entry.note}
                                            </Typography>
                                            {entry.tags?.length > 0 && (
                                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                                                    {entry.tags.map((tag, idx) => (
                                                        <Chip key={idx} label={tag} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />
                                                    ))}
                                                </Stack>
                                            )}
                                        </Box>
                                        <Stack direction="row" spacing={1} alignItems="flex-start" flexShrink={0}>
                                            <Chip size="small" label={entry.entry_type} color={TYPE_COLOR[entry.entry_type] || 'default'} />
                                            <Chip size="small" label={`${entry.hours}h`} color="primary" variant="outlined" />
                                        </Stack>
                                    </Stack>
                                </Box>
                            ))}
                        </Stack>
                    </Paper>
                );
            })}
        </Stack>
    );
}

// ─── Main export ─────────────────────────────────────────────────────────────

export default function HRDiaryLogbooks() {
    const [activeMember, setActiveMember] = useState(null);

    if (activeMember) {
        return <MemberDetail member={activeMember} onBack={() => setActiveMember(null)} />;
    }

    return <Overview onMemberClick={setActiveMember} />;
}
