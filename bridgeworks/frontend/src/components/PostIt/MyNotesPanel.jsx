import React, { useEffect, useMemo, useState } from 'react';
import {
    Box,
    Button,
    Divider,
    IconButton,
    List,
    ListItemButton,
    ListItemText,
    Paper,
    Stack,
    Tab,
    Tabs,
    TextField,
    Typography
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    AttachFile as AttachFileIcon,
    Close as CloseIcon,
    Delete as DeleteIcon,
    Image as ImageIcon,
    InsertDriveFile as InsertDriveFileIcon,
    VideoFile as VideoFileIcon,
} from '@mui/icons-material';
import {
    createMyDeskNote,
    deleteMyDeskNote,
    deleteMyDeskNoteAttachment,
    listMyDeskNotes,
} from '../mydesk/mydeskService';

const formatFileSize = (size) => {
    if (!size) return '0 B';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDateTime = (value) => {
    const date = value ? new Date(value) : new Date();
    return date.toLocaleString('en-GB', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};

const htmlToPlainText = (html) => {
    if (!html) return '';
    return String(html)
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/p>/gi, '\n')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .trim();
};

const plainTextToHtml = (text) => {
    const escaped = String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    return escaped.replace(/\n/g, '<br />');
};

const normalizeEntry = (entry) => ({
    id: String(entry.id),
    title: String(entry.title || ''),
    note: htmlToPlainText(entry.content_html || ''),
    createdAt: String(entry.created_at || new Date().toISOString()),
    attachments: Array.isArray(entry.file_attachments)
        ? entry.file_attachments.map((attachment) => ({
            id: String(attachment.id),
            name: String(attachment.original_name || 'Attachment'),
            type: String(attachment.mime_type || ''),
            size: Number(attachment.file_size || 0),
            url: String(attachment.file_url || ''),
        }))
        : [],
});

export default function MyNotesPanel({ open, onClose }) {
    const [activeTab, setActiveTab] = useState('write');
    const [clock, setClock] = useState(new Date());
    const [entries, setEntries] = useState([]);
    const [title, setTitle] = useState('');
    const [note, setNote] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedEntryId, setSelectedEntryId] = useState(null);
    const [attachments, setAttachments] = useState([]);
    const [loadingEntries, setLoadingEntries] = useState(false);
    const [savingEntry, setSavingEntry] = useState(false);

    const fetchEntries = async () => {
        setLoadingEntries(true);
        try {
            const data = await listMyDeskNotes();
            setEntries(Array.isArray(data) ? data.map(normalizeEntry) : []);
        } catch (error) {
            console.error('Failed to fetch my notes', error);
        } finally {
            setLoadingEntries(false);
        }
    };

    useEffect(() => {
        if (!open) return;
        fetchEntries();
    }, [open]);

    useEffect(() => {
        const interval = setInterval(() => {
            setClock(new Date());
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const selectedEntry = useMemo(
        () => entries.find((entry) => entry.id === selectedEntryId) || null,
        [entries, selectedEntryId]
    );

    const filteredEntries = useMemo(() => {
        const query = searchQuery.trim().toLowerCase();
        if (!query) return entries;

        return entries.filter((entry) => {
            const attachmentNames = (entry.attachments || []).map((attachment) => attachment.name).join(' ');
            const text = `${entry.title} ${entry.note} ${attachmentNames}`.toLowerCase();
            return text.includes(query);
        });
    }, [entries, searchQuery]);

    const handleSave = async () => {
        const trimmedTitle = title.trim();
        const trimmedNote = note.trim();
        if (!trimmedTitle || !trimmedNote) return;

        setSavingEntry(true);
        try {
            const created = await createMyDeskNote({
                title: trimmedTitle,
                content_html: plainTextToHtml(trimmedNote),
                tags: [],
                labels: ['quick-access'],
                attachments: attachments.map((attachment) => attachment.name),
                drive_links: [],
            }, attachments.map((attachment) => attachment.file));
            setEntries((prev) => [normalizeEntry(created), ...prev]);
            window.dispatchEvent(new CustomEvent('mydesk-note-created', { detail: created }));
            setTitle('');
            setNote('');
            setAttachments([]);
            setActiveTab('entries');
        } catch (error) {
            console.error('Failed to save my note', error);
            alert(error?.message || 'Failed to save note.');
        } finally {
            setSavingEntry(false);
        }
    };

    const handleDelete = async (id) => {
        try {
            await deleteMyDeskNote(id);
            window.dispatchEvent(new CustomEvent('mydesk-note-deleted', { detail: { id: String(id) } }));

            setEntries((prev) => prev.filter((entry) => entry.id !== id));
            if (selectedEntryId === id) {
                setSelectedEntryId(null);
            }
        } catch (error) {
            console.error('Failed to delete note', error);
            alert('Failed to delete note.');
        }
    };

    const handleDeleteAttachmentFromEntry = async (entryId, attachmentId) => {
        try {
            await deleteMyDeskNoteAttachment(attachmentId);
            setEntries((prev) => prev.map((entry) => (
                entry.id === entryId
                    ? { ...entry, attachments: (entry.attachments || []).filter((attachment) => attachment.id !== String(attachmentId)) }
                    : entry
            )));
        } catch (error) {
            console.error('Failed to delete note attachment', error);
            alert('Failed to delete attachment.');
        }
    };

    const handleAttachmentSelect = (event) => {
        const files = Array.from(event.target.files || []);
        if (files.length === 0) return;

        const mapped = files.map((file) => ({
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            name: file.name,
            type: file.type,
            size: file.size,
            file,
        }));

        setAttachments((prev) => [...prev, ...mapped]);
        event.target.value = '';
    };

    const handleRemoveAttachment = (id) => {
        setAttachments((prev) => prev.filter((attachment) => attachment.id !== id));
    };

    if (!open) return null;

    return (
        <Paper
            elevation={8}
            sx={{
                position: 'fixed',
                right: 16,
                bottom: 200,
                width: { xs: 'calc(100vw - 32px)', sm: 360 },
                maxHeight: '72vh',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1405,
                overflow: 'hidden'
            }}
        >
            <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                    <Typography variant="subtitle1" fontWeight={700}>My notes</Typography>
                    <Typography variant="caption" color="text.secondary">{formatDateTime(clock)}</Typography>
                </Box>
                <IconButton onClick={onClose} size="small" aria-label="close my notes">
                    <CloseIcon fontSize="small" />
                </IconButton>
            </Box>

            <Divider />

            <Tabs
                value={activeTab}
                onChange={(_, value) => {
                    setActiveTab(value);
                    setSelectedEntryId(null);
                }}
                variant="fullWidth"
            >
                <Tab value="write" label="Write" />
                <Tab value="entries" label="My Notes" />
            </Tabs>

            <Divider />

            <Box sx={{ p: 2, overflowY: 'auto' }}>
                {activeTab === 'write' && (
                    <Stack spacing={1.5}>
                        <TextField
                            label="Title"
                            value={title}
                            onChange={(event) => setTitle(event.target.value)}
                            fullWidth
                            size="small"
                        />
                        <TextField
                            label="Note"
                            value={note}
                            onChange={(event) => setNote(event.target.value)}
                            fullWidth
                            multiline
                            minRows={6}
                        />
                        <Button
                            component="label"
                            variant="outlined"
                            startIcon={<AttachFileIcon />}
                        >
                            Add files / images
                            <input
                                type="file"
                                hidden
                                multiple
                                accept="image/*,video/*,*/*"
                                onChange={handleAttachmentSelect}
                            />
                        </Button>
                        {attachments.length > 0 && (
                            <Stack spacing={0.75} sx={{ maxHeight: 140, overflowY: 'auto' }}>
                                {attachments.map((attachment) => {
                                    const isImage = attachment.type.startsWith('image/');
                                    const isVideo = attachment.type.startsWith('video/');
                                    return (
                                        <Stack
                                            key={attachment.id}
                                            direction="row"
                                            alignItems="center"
                                            justifyContent="space-between"
                                            sx={{
                                                px: 1,
                                                py: 0.75,
                                                borderRadius: 1,
                                                border: '1px solid',
                                                borderColor: 'divider',
                                            }}
                                        >
                                            <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                                                {isImage ? <ImageIcon fontSize="small" /> : isVideo ? <VideoFileIcon fontSize="small" /> : <InsertDriveFileIcon fontSize="small" />}
                                                <Box sx={{ minWidth: 0 }}>
                                                    <Typography variant="body2" noWrap>{attachment.name}</Typography>
                                                    <Typography variant="caption" color="text.secondary">
                                                        {formatFileSize(attachment.size)}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                            <IconButton
                                                size="small"
                                                color="error"
                                                onClick={() => handleRemoveAttachment(attachment.id)}
                                            >
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Stack>
                                    );
                                })}
                            </Stack>
                        )}
                        <Button
                            variant="contained"
                            onClick={handleSave}
                            disabled={!title.trim() || !note.trim() || savingEntry}
                        >
                            {savingEntry ? 'Saving...' : 'Save entry'}
                        </Button>
                    </Stack>
                )}

                {activeTab === 'entries' && (
                    <Stack spacing={1.5}>
                        <TextField
                            label="Search entries"
                            value={searchQuery}
                            onChange={(event) => setSearchQuery(event.target.value)}
                            fullWidth
                            size="small"
                        />

                        {loadingEntries && (
                            <Typography variant="body2" color="text.secondary">
                                Loading notes...
                            </Typography>
                        )}

                        {selectedEntry ? (
                            <Stack spacing={1}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                    <Button
                                        startIcon={<ArrowBackIcon />}
                                        onClick={() => setSelectedEntryId(null)}
                                        size="small"
                                    >
                                        Back
                                    </Button>
                                    <Button
                                        color="error"
                                        startIcon={<DeleteIcon />}
                                        onClick={() => handleDelete(selectedEntry.id)}
                                        size="small"
                                    >
                                        Delete
                                    </Button>
                                </Stack>
                                <Typography variant="h6">{selectedEntry.title}</Typography>
                                <Typography variant="caption" color="text.secondary">
                                    {formatDateTime(selectedEntry.createdAt)}
                                </Typography>
                                <Divider />
                                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                                    {selectedEntry.note}
                                </Typography>
                                {selectedEntry.attachments?.length > 0 && (
                                    <Stack spacing={1.25}>
                                        <Divider />
                                        <Typography variant="subtitle2">Attachments</Typography>
                                        {selectedEntry.attachments.map((attachment) => (
                                            <Stack key={attachment.id} direction="row" spacing={1} alignItems="center">
                                                <Button
                                                    component="a"
                                                    href={attachment.url}
                                                    download={attachment.name}
                                                    size="small"
                                                    variant="outlined"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    sx={{ justifyContent: 'flex-start', flex: 1 }}
                                                >
                                                    {attachment.name}
                                                </Button>
                                                <IconButton
                                                    size="small"
                                                    color="error"
                                                    onClick={() => handleDeleteAttachmentFromEntry(selectedEntry.id, attachment.id)}
                                                    aria-label="delete attachment"
                                                >
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Stack>
                                        ))}
                                    </Stack>
                                )}
                            </Stack>
                        ) : (
                            <List disablePadding sx={{ borderRadius: 1, bgcolor: 'background.default' }}>
                                {filteredEntries.length === 0 ? (
                                    <Box sx={{ p: 2 }}>
                                        <Typography variant="body2" color="text.secondary">
                                            No notes found.
                                        </Typography>
                                    </Box>
                                ) : (
                                    filteredEntries.map((entry) => (
                                        <Stack
                                            key={entry.id}
                                            direction="row"
                                            alignItems="flex-start"
                                            spacing={0.5}
                                            sx={{ px: 0.5 }}
                                        >
                                            <ListItemButton
                                                onClick={() => setSelectedEntryId(entry.id)}
                                                sx={{ alignItems: 'flex-start', py: 1.25, flex: 1 }}
                                            >
                                                <ListItemText
                                                    primary={entry.title}
                                                    secondary={
                                                        <>
                                                            <Typography variant="caption" color="text.secondary" component="div">
                                                                {formatDateTime(entry.createdAt)}
                                                            </Typography>
                                                            <Typography
                                                                variant="body2"
                                                                color="text.secondary"
                                                                component="div"
                                                                sx={{
                                                                    overflow: 'hidden',
                                                                    textOverflow: 'ellipsis',
                                                                    display: '-webkit-box',
                                                                    WebkitLineClamp: 2,
                                                                    WebkitBoxOrient: 'vertical'
                                                                }}
                                                            >
                                                                {entry.note}
                                                            </Typography>
                                                        </>
                                                    }
                                                />
                                            </ListItemButton>
                                            <IconButton
                                                size="small"
                                                color="error"
                                                sx={{ mt: 1 }}
                                                onClick={() => handleDelete(entry.id)}
                                                aria-label="delete quick note"
                                            >
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Stack>
                                    ))
                                )}
                            </List>
                        )}
                    </Stack>
                )}
            </Box>
        </Paper>
    );
}