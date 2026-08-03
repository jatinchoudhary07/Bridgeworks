import React, { useEffect, useMemo, useState } from 'react';
import {
    Box,
    Button,
    Chip,
    Dialog,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    InputLabel,
    List,
    ListItem,
    ListItemText,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AutoAwesome as AutoAwesomeIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    FileUpload as FileUploadIcon,
} from '@mui/icons-material';
import {
    createMyDeskDiaryEntry,
    deleteMyDeskDiaryEntry,
    listMyDeskDiaryEntries,
    updateMyDeskDiaryEntry,
} from '../mydeskService';

function toLocalDateValue(value) {
    if (!value) return new Date().toISOString().slice(0, 10);
    return String(value).slice(0, 10);
}

function toDateInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDateTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatDayLabel(dateKey) {
    if (!dateKey) return '';
    const date = new Date(`${dateKey}T00:00:00`);
    if (Number.isNaN(date.getTime())) return dateKey;

    const today = new Date();
    const todayKey = today.toISOString().slice(0, 10);
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const yesterdayKey = yesterday.toISOString().slice(0, 10);

    if (dateKey === todayKey) return 'Today';
    if (dateKey === yesterdayKey) return 'Yesterday';

    return date.toLocaleDateString('en-GB', {
        weekday: 'long',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
    });
}

export default function DiarySection() {
    const [entries, setEntries] = useState([]);
    const [form, setForm] = useState({
        title: '',
        note: '',
        hours: '',
        entryDate: new Date().toISOString().slice(0, 10),
        files: [],
    });
    const [search, setSearch] = useState('');
    const [order, setOrder] = useState('newest');
    const [timeline, setTimeline] = useState('all');
    const [filterDate, setFilterDate] = useState(new Date().toISOString().slice(0, 10));
    const [rangeStart, setRangeStart] = useState('');
    const [rangeEnd, setRangeEnd] = useState('');
    const [saving, setSaving] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [activeEntry, setActiveEntry] = useState(null);

    const queryFilters = useMemo(() => {
        const filters = { q: search, order };
        const today = new Date();
        const todayValue = toDateInputValue(today);

        if (timeline === 'today') {
            filters.start_date = todayValue;
            filters.end_date = todayValue;
        } else if (timeline === 'yesterday') {
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            const yesterdayValue = toDateInputValue(yesterday);
            filters.start_date = yesterdayValue;
            filters.end_date = yesterdayValue;
        } else if (timeline === 'last7') {
            const start = new Date(today);
            start.setDate(start.getDate() - 6);
            filters.start_date = toDateInputValue(start);
            filters.end_date = todayValue;
        } else if (timeline === 'last30') {
            const start = new Date(today);
            start.setDate(start.getDate() - 29);
            filters.start_date = toDateInputValue(start);
            filters.end_date = todayValue;
        } else if (timeline === 'thisMonth') {
            const first = new Date(today.getFullYear(), today.getMonth(), 1);
            const last = new Date(today.getFullYear(), today.getMonth() + 1, 0);
            filters.start_date = toDateInputValue(first);
            filters.end_date = toDateInputValue(last);
        } else if (timeline === 'date' && filterDate) {
            filters.start_date = filterDate;
            filters.end_date = filterDate;
        } else if (timeline === 'custom') {
            if (rangeStart) filters.start_date = rangeStart;
            if (rangeEnd) filters.end_date = rangeEnd;
        }

        return filters;
    }, [search, order, timeline, filterDate, rangeStart, rangeEnd]);

    useEffect(() => {
        let mounted = true;

        listMyDeskDiaryEntries(queryFilters)
            .then((data) => {
                if (!mounted) return;
                const list = Array.isArray(data) ? data : [];
                setEntries(list);
            })
            .catch(() => { });

        return () => {
            mounted = false;
        };
    }, [queryFilters]);

    const canSave = useMemo(() => {
        return form.title.trim() && form.note.trim() && form.entryDate && !saving;
    }, [form, saving]);

    const groupedEntries = useMemo(() => {
        const grouped = [];
        const map = new Map();

        entries.forEach((entry) => {
            const key = entry.entry_date || toLocalDateValue(entry.created_at);
            if (!map.has(key)) {
                const block = { key, entries: [], totalHours: 0 };
                map.set(key, block);
                grouped.push(block);
            }
            const block = map.get(key);
            block.entries.push(entry);
            block.totalHours += Number(entry.hours || 0);
        });

        return grouped;
    }, [entries]);

    const handleCreate = async () => {
        if (!canSave) return;

        const formData = new FormData();
        formData.append('title', form.title.trim());
        formData.append('note', form.note.trim());
        formData.append('entry_date', form.entryDate);
        formData.append('hours', form.hours || '0');
        form.files.forEach((file) => formData.append('attachments', file));

        setSaving(true);
        try {
            if (editingId) {
                await updateMyDeskDiaryEntry(editingId, formData);
            } else {
                await createMyDeskDiaryEntry(formData);
            }

            const latest = await listMyDeskDiaryEntries(queryFilters);
            setEntries(Array.isArray(latest) ? latest : []);
            setForm({
                title: '',
                note: '',
                hours: '',
                entryDate: new Date().toISOString().slice(0, 10),
                files: [],
            });
            setEditingId(null);
        } catch {
            return;
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        try {
            await deleteMyDeskDiaryEntry(id);
            setEntries((previous) => previous.filter((entry) => entry.id !== id));
            if (activeEntry?.id === id) setActiveEntry(null);
        } catch {
            return;
        }
    };

    const handleEdit = (entry) => {
        setEditingId(entry.id);
        setForm({
            title: entry.title || '',
            note: entry.note || '',
            hours: entry.hours ? String(entry.hours) : '',
            entryDate: toLocalDateValue(entry.entry_date || entry.created_at),
            files: [],
        });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setForm({
            title: '',
            note: '',
            hours: '',
            entryDate: new Date().toISOString().slice(0, 10),
            files: [],
        });
    };

    return (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack spacing={1.5}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>My Diary</Typography>
                    <TextField
                        size="small"
                        label="Title"
                        value={form.title}
                        onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))}
                        placeholder="What did you work on today?"
                    />
                    <TextField
                        multiline
                        minRows={3}
                        label="Log"
                        value={form.note}
                        onChange={(event) => setForm((previous) => ({ ...previous, note: event.target.value }))}
                        placeholder="Describe what you did, blockers, and outcomes..."
                    />
                    <Stack sx={{ overflowX: 'auto' }}>
                        <Stack direction="row" spacing={1.5} sx={{ minWidth: 'max-content', width: '100%', overflowX: 'auto', pt: 0.75, pb: 0.5 }}>
                            <TextField
                                size="small"
                                type="number"
                                label="Hours"
                                value={form.hours}
                                inputProps={{ min: 0, step: 0.5 }}
                                onChange={(event) => setForm((previous) => ({ ...previous, hours: event.target.value }))}
                                sx={{ width: 110 }}
                            />
                            <TextField
                                size="small"
                                type="date"
                                label="Date"
                                InputLabelProps={{ shrink: true }}
                                value={form.entryDate}
                                onChange={(event) => setForm((previous) => ({ ...previous, entryDate: event.target.value }))}
                                sx={{ minWidth: 150 }}
                            />
                            <Button component="label" variant="outlined" startIcon={<FileUploadIcon />}>
                                Add Attachments
                                <input
                                    hidden
                                    type="file"
                                    multiple
                                    onChange={(event) => setForm((previous) => ({ ...previous, files: Array.from(event.target.files || []) }))}
                                />
                            </Button>
                            {form.files.map((file, index) => (
                                <Chip
                                    key={`${file.name}-${index}`}
                                    label={file.name}
                                    onDelete={() => setForm((previous) => ({
                                        ...previous,
                                        files: previous.files.filter((_, currentIndex) => currentIndex !== index),
                                    }))}
                                />
                            ))}
                            <Box sx={{ flexGrow: 1 }} />
                            <Tooltip title="Coming Soon">
                                <span>
                                    <Button
                                        variant="outlined"
                                        startIcon={<AutoAwesomeIcon />}
                                        disabled
                                        sx={{ minWidth: 170 }}
                                    >
                                        Generate with AI
                                    </Button>
                                </span>
                            </Tooltip>
                            <Button variant="contained" onClick={handleCreate} disabled={!canSave}>
                                {editingId ? 'Update Logbook' : 'Add to Logbook'}
                            </Button>
                            {editingId && (
                                <Button variant="text" onClick={cancelEdit}>Cancel</Button>
                            )}
                        </Stack>
                    </Stack>
                </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Stack sx={{ overflowX: 'auto', overflowY: 'visible', pt: 0.75 }}>
                    <Stack direction="row" spacing={1} sx={{ minWidth: 'max-content' }}>
                        <TextField
                            size="small"
                            fullWidth
                            placeholder="Search entries..."
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            sx={{ minWidth: 420 }}
                        />
                        <FormControl size="small" sx={{ minWidth: 170 }}>
                            <InputLabel>Timeline</InputLabel>
                            <Select label="Timeline" value={timeline} onChange={(event) => setTimeline(event.target.value)}>
                                <MenuItem value="all">All</MenuItem>
                                <MenuItem value="today">Today</MenuItem>
                                <MenuItem value="yesterday">Yesterday</MenuItem>
                                <MenuItem value="last7">Last 7 Days</MenuItem>
                                <MenuItem value="last30">Last 30 Days</MenuItem>
                                <MenuItem value="thisMonth">This Month</MenuItem>
                                <MenuItem value="date">By Date</MenuItem>
                                <MenuItem value="custom">Custom Range</MenuItem>
                            </Select>
                        </FormControl>
                        {timeline === 'date' && (
                            <TextField
                                size="small"
                                type="date"
                                label="Date"
                                InputLabelProps={{ shrink: true }}
                                value={filterDate}
                                onChange={(event) => setFilterDate(event.target.value)}
                                sx={{ minWidth: 150 }}
                            />
                        )}
                        {timeline === 'custom' && (
                            <>
                                <TextField
                                    size="small"
                                    type="date"
                                    label="From"
                                    InputLabelProps={{ shrink: true }}
                                    value={rangeStart}
                                    onChange={(event) => setRangeStart(event.target.value)}
                                    sx={{ minWidth: 150 }}
                                />
                                <TextField
                                    size="small"
                                    type="date"
                                    label="To"
                                    InputLabelProps={{ shrink: true }}
                                    value={rangeEnd}
                                    onChange={(event) => setRangeEnd(event.target.value)}
                                    sx={{ minWidth: 150 }}
                                />
                            </>
                        )}
                        <FormControl size="small" sx={{ minWidth: 160 }}>
                            <InputLabel>Sort</InputLabel>
                            <Select label="Sort" value={order} onChange={(event) => setOrder(event.target.value)}>
                                <MenuItem value="newest">Newest First</MenuItem>
                                <MenuItem value="oldest">Oldest First</MenuItem>
                            </Select>
                        </FormControl>
                    </Stack>
                </Stack>
            </Paper>

            {groupedEntries.map((group) => (
                <Paper key={group.key} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 0.5, pb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{formatDayLabel(group.key)}</Typography>
                        <Chip size="small" label={`${group.totalHours}h logged`} variant="outlined" />
                    </Stack>

                    <List sx={{ pt: 0 }}>
                        {group.entries.map((entry) => (
                            <ListItem
                                key={entry.id}
                                divider
                                alignItems="flex-start"
                                secondaryAction={(
                                    <Stack direction="row" spacing={0.5}>
                                        <IconButton size="small" onClick={(event) => {
                                            event.stopPropagation();
                                            handleEdit(entry);
                                        }}>
                                            <EditIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton size="small" onClick={(event) => {
                                            event.stopPropagation();
                                            handleDelete(entry.id);
                                        }}>
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                    </Stack>
                                )}
                                sx={{ cursor: 'pointer' }}
                                onClick={() => setActiveEntry(entry)}
                            >
                                <ListItemText
                                    primary={(
                                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems={{ xs: 'flex-start', md: 'center' }} flexWrap="wrap" useFlexGap>
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{entry.title}</Typography>
                                            <Chip size="small" label={`${entry.hours || 0}h`} variant="outlined" />
                                            <Typography variant="caption" color="text.secondary">{formatDateTime(entry.created_at)}</Typography>
                                        </Stack>
                                    )}
                                    secondary={(
                                        <Stack spacing={0.75} sx={{ mt: 0.5 }}>
                                            <Typography
                                                variant="body2"
                                                color="text.primary"
                                                sx={{
                                                    display: '-webkit-box',
                                                    WebkitLineClamp: 2,
                                                    WebkitBoxOrient: 'vertical',
                                                    overflow: 'hidden',
                                                }}
                                            >
                                                {entry.note}
                                            </Typography>
                                        </Stack>
                                    )}
                                    secondaryTypographyProps={{ component: 'div' }}
                                />
                            </ListItem>
                        ))}
                    </List>
                </Paper>
            ))}

            {entries.length === 0 && (
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        No diary logs yet. Add your first log for today.
                    </Typography>
                </Paper>
            )}

            <Dialog open={Boolean(activeEntry)} onClose={() => setActiveEntry(null)} fullWidth maxWidth="md">
                <DialogTitle>{activeEntry?.title || 'Diary Entry'}</DialogTitle>
                <DialogContent>
                    {activeEntry && (
                        <Stack spacing={1}>
                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                <Chip size="small" label={`${activeEntry.hours || 0}h`} variant="outlined" />
                                <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                                    {formatDateTime(activeEntry.created_at)}
                                </Typography>
                            </Stack>

                            <Typography variant="body2" color="text.primary" sx={{ whiteSpace: 'pre-wrap' }}>
                                {activeEntry.note}
                            </Typography>

                            {Array.isArray(activeEntry.attachments) && activeEntry.attachments.length > 0 && (
                                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                                    {activeEntry.attachments.map((attachment) => (
                                        <Chip
                                            key={attachment.id}
                                            component="a"
                                            clickable
                                            href={attachment.file_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            size="small"
                                            label={attachment.original_name || 'Attachment'}
                                        />
                                    ))}
                                </Stack>
                            )}
                        </Stack>
                    )}
                </DialogContent>
            </Dialog>
        </Stack>
    );
}
