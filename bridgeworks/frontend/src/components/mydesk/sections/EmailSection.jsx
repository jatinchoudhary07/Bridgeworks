// EmailSection.jsx — Gmail-like three-panel view integrated into My Desk
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box, List, ListItem, ListItemButton, ListItemIcon, ListItemText,
    Typography, IconButton, InputBase, Divider, Avatar, Chip,
    Tooltip, CircularProgress, Snackbar, Alert, Badge, Menu, MenuItem,
    Button,
} from '@mui/material';
import {
    Inbox as InboxIcon, Send as SendIcon, Star as StarIcon,
    StarBorder as StarBorderIcon, Drafts as DraftsIcon, Delete as DeleteIcon,
    Search as SearchIcon, Refresh as RefreshIcon, FilterList as FilterIcon,
    Reply as ReplyIcon, Forward as ForwardIcon, Archive as ArchiveIcon,
    MoreVert as MoreVertIcon, AttachFile as AttachFileIcon, Label as LabelIcon,
    Close as CloseIcon, ExpandMore as ExpandMoreIcon, Mail as MailIcon,
    LinkOff as LinkOffIcon,
} from '@mui/icons-material';
import { useGmail } from './useGmail';
import ComposeModal from './ComposeModal';

// ── Constants ─────────────────────────────────────────────────────────────────

const SIDEBAR_W = 200;
const LIST_W    = 300;

const NAV = [
    { key: 'INBOX',   label: 'Inbox',   icon: <InboxIcon   fontSize="small" /> },
    { key: 'SENT',    label: 'Sent',    icon: <SendIcon    fontSize="small" /> },
    { key: 'STARRED', label: 'Starred', icon: <StarIcon    fontSize="small" /> },
    { key: 'DRAFT',   label: 'Drafts',  icon: <DraftsIcon  fontSize="small" /> },
    { key: 'TRASH',   label: 'Trash',   icon: <DeleteIcon  fontSize="small" /> },
];

const LABEL_COLORS = {
    Suppliers: '#3B82F6', Orders: '#10B981',
    Logistics: '#F59E0B', HR: '#8B5CF6', Finance: '#EF4444',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(d) {
    if (!d) return '';
    const dt = new Date(d), now = new Date();
    const diff = Math.floor((now - dt) / 86400000);
    if (diff === 0) return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff === 1) return 'Yesterday';
    if (diff < 7)  return dt.toLocaleDateString([], { weekday: 'short' });
    return dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function initials(name = '') {
    return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?';
}

function avatarBg(name = '') {
    const colors = ['#3B82F6','#10B981','#F59E0B','#8B5CF6','#EF4444','#EC4899'];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return colors[Math.abs(h) % colors.length];
}

// ── EmailRow ──────────────────────────────────────────────────────────────────

function EmailRow({ email, selected, onClick }) {
    const unread = !email.isRead;
    const from   = email.from?.name || email.from?.email || '';
    const bg     = avatarBg(from);

    return (
        <ListItemButton onClick={onClick} selected={selected} sx={{
            px: 1.5, py: 1,
            borderBottom: '1px solid', borderColor: 'divider',
            borderLeft: '3px solid',
            borderLeftColor: selected ? 'primary.main' : 'transparent',
            alignItems: 'flex-start', gap: 1,
            bgcolor: selected ? 'action.selected' : unread ? 'background.paper' : 'background.default',
            '&:hover': { bgcolor: 'action.hover' },
            transition: 'background 0.1s',
        }}>
            <Avatar sx={{ width: 32, height: 32, fontSize: 12, bgcolor: bg, mt: 0.25, flexShrink: 0 }}>
                {initials(from)}
            </Avatar>
            <Box sx={{ flex: 1, overflow: 'hidden' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography variant="body2" fontWeight={unread ? 700 : 400} noWrap sx={{ maxWidth: 160 }}>
                        {unread && <Box component="span" sx={{ display: 'inline-block', width: 6, height: 6, bgcolor: 'primary.main', borderRadius: '50%', mr: 0.75, mb: 0.25 }} />}
                        {from}
                    </Typography>
                    <Typography variant="caption" color="text.disabled" sx={{ flexShrink: 0, ml: 1 }}>
                        {fmtDate(email.date)}
                    </Typography>
                </Box>
                <Typography variant="body2" fontWeight={unread ? 600 : 400} noWrap>{email.subject}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap>{email.snippet}</Typography>
                {email.labels?.filter(l => LABEL_COLORS[l]).length > 0 && (
                    <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5 }}>
                        {email.labels.filter(l => LABEL_COLORS[l]).map(l => (
                            <Chip key={l} label={l} size="small" sx={{
                                height: 16, fontSize: 10, fontWeight: 600,
                                bgcolor: LABEL_COLORS[l] + '22', color: LABEL_COLORS[l],
                                '& .MuiChip-label': { px: 0.75 }
                            }} />
                        ))}
                    </Box>
                )}
            </Box>
        </ListItemButton>
    );
}

// ── EmailView ─────────────────────────────────────────────────────────────────

function EmailView({ email, onReply, onForward, onArchive, onDelete, onStar, onMarkUnread }) {
    const [replyText,   setReplyText]  = useState('');
    const [moreAnchor,  setMoreAnchor] = useState(null);

    if (!email) return (
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 1, color: 'text.disabled' }}>
            <MailIcon sx={{ fontSize: 56, opacity: 0.2 }} />
            <Typography variant="body2" color="text.disabled">Select an email to read</Typography>
        </Box>
    );

    const from = email.from?.name || email.from?.email || '';
    const bg   = avatarBg(from);

    return (
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Toolbar */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1, borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
                <Tooltip title="Reply"><IconButton size="small" onClick={() => onReply(email)}><ReplyIcon fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Forward"><IconButton size="small" onClick={() => onForward(email)}><ForwardIcon fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Archive"><IconButton size="small" onClick={() => onArchive(email.id)}><ArchiveIcon fontSize="small" /></IconButton></Tooltip>
                <Tooltip title="Delete"><IconButton size="small" onClick={() => onDelete(email.id)}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
                <Tooltip title={email.isStarred ? 'Unstar' : 'Star'}>
                    <IconButton size="small" onClick={() => onStar(email.id, email.isStarred)}>
                        {email.isStarred
                            ? <StarIcon fontSize="small" sx={{ color: '#F59E0B' }} />
                            : <StarBorderIcon fontSize="small" />}
                    </IconButton>
                </Tooltip>
                <Box sx={{ flex: 1 }} />
                <IconButton size="small" onClick={e => setMoreAnchor(e.currentTarget)}><MoreVertIcon fontSize="small" /></IconButton>
                <Menu anchorEl={moreAnchor} open={Boolean(moreAnchor)} onClose={() => setMoreAnchor(null)}>
                    <MenuItem onClick={() => { setMoreAnchor(null); onMarkUnread(email.id); }}>Mark as unread</MenuItem>
                    <MenuItem onClick={() => { setMoreAnchor(null); onDelete(email.id); }}>Move to trash</MenuItem>
                </Menu>
            </Box>

            {/* Body */}
            <Box sx={{ flex: 1, overflowY: 'auto', px: 3, py: 2.5 }}>
                <Typography variant="h6" fontWeight={600} gutterBottom>{email.subject}</Typography>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, mb: 2, pb: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Avatar sx={{ bgcolor: bg, width: 40, height: 40 }}>{initials(from)}</Avatar>
                    <Box sx={{ flex: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                            <Typography variant="body2" fontWeight={600}>{from}</Typography>
                            <Typography variant="caption" color="text.secondary">&lt;{email.from?.email}&gt;</Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            To: {email.to?.join(', ')}<ExpandMoreIcon sx={{ fontSize: 14 }} />
                        </Typography>
                    </Box>
                    <Typography variant="caption" color="text.disabled">
                        {email.date ? new Date(email.date).toLocaleString() : ''}
                    </Typography>
                </Box>

                {email.bodyHtml ? (
                    <Box sx={{ fontSize: 14, lineHeight: 1.7, color: 'text.primary', '& a': { color: 'primary.main' } }}
                        dangerouslySetInnerHTML={{ __html: email.bodyHtml }} />
                ) : (
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{email.bodyText}</Typography>
                )}

                {email.attachments?.length > 0 && (
                    <Box sx={{ mt: 3 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 1, display: 'block' }}>
                            {email.attachments.length} attachment{email.attachments.length > 1 ? 's' : ''}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            {email.attachments.map((att, i) => (
                                <Chip key={i} icon={<AttachFileIcon />}
                                    label={`${att.filename} · ${(att.size / 1024).toFixed(0)} KB`}
                                    variant="outlined" size="small" sx={{ cursor: 'pointer', fontSize: 11 }}
                                    onClick={() => downloadAttachment(email.id, att.attachmentId, att.filename)}
                                />
                            ))}
                        </Box>
                    </Box>
                )}
            </Box>

            {/* Quick reply */}
            <Box sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 1, alignItems: 'center', flexShrink: 0 }}>
                <InputBase fullWidth
                    placeholder={`Reply to ${from}…`}
                    value={replyText} onChange={e => setReplyText(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (replyText.trim()) { onReply(email, replyText); setReplyText(''); } } }}
                    sx={{ flex: 1, px: 1.5, py: 0.75, bgcolor: 'action.hover', borderRadius: 2, fontSize: 13 }}
                />
                <Tooltip title="Open full compose">
                    <IconButton size="small" onClick={() => onReply(email)}><ReplyIcon fontSize="small" /></IconButton>
                </Tooltip>
            </Box>
        </Box>
    );
}

// ── Connect Screen ─────────────────────────────────────────────────────────────

function ConnectScreen({ onConnect, errorReason }) {
    return (
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, p: 4 }}>
            <Box sx={{
                width: 72, height: 72, borderRadius: '50%',
                background: 'linear-gradient(135deg, #EA4335 0%, #4285F4 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
                <MailIcon sx={{ fontSize: 36, color: '#fff' }} />
            </Box>
            <Typography variant="h6" fontWeight={600}>Connect Gmail</Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ maxWidth: 340 }}>
                Connect your Google account to read and send emails directly from My Desk.
                Your OAuth tokens are stored securely on the server — never in the browser.
            </Typography>

            {errorReason && (
                <Box sx={{ bgcolor: 'error.main', color: '#fff', borderRadius: 2, px: 2, py: 1.5, maxWidth: 420, width: '100%' }}>
                    <Typography variant="caption" fontWeight={700} sx={{ display: 'block', mb: 0.5 }}>
                        Connection failed — reason:
                    </Typography>
                    <Typography variant="caption" sx={{ wordBreak: 'break-word', fontFamily: 'monospace' }}>
                        {decodeURIComponent(errorReason)}
                    </Typography>
                    <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.85 }}>
                        Common fixes: (1) Enable the Gmail API in Google Cloud Console → APIs &amp; Services → Library.
                        (2) Add gmail.readonly / gmail.send / gmail.modify scopes to your OAuth consent screen.
                    </Typography>
                </Box>
            )}

            <Button variant="contained" size="large" onClick={onConnect}
                sx={{ mt: 1, borderRadius: 2, textTransform: 'none', fontWeight: 600, px: 4 }}>
                {errorReason ? 'Try Again' : 'Connect Gmail'}
            </Button>
        </Box>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function EmailSection() {
    const {
        emails, loading, error,
        selectedFolder, setSelectedFolder,
        selectedEmail, setSelectedEmail,
        unreadCount,
        connected, gmailEmail,
        checkConnection, connectGmail, disconnectGmail,
        fetchEmails, searchEmails, openEmail,
        markAsRead, markAsUnread,
        starEmail, unstarEmail,
        archiveEmail, trashEmail,
        sendEmail,
        downloadAttachment,
    } = useGmail();

    const [searchQuery,     setSearchQuery]     = useState('');
    const [composeOpen,     setComposeOpen]     = useState(false);
    const [composeMode,     setComposeMode]     = useState('new');
    const [composeDefaults, setComposeDefaults] = useState({});
    const [snackbar,        setSnackbar]        = useState({ open: false, msg: '', severity: 'success' });
    const [errorReason,     setErrorReason]     = useState('');
    const searchTimer = useRef(null);

    // Check auth on mount
    useEffect(() => { checkConnection(); }, []);

    // Auto-fetch when folder changes
    useEffect(() => {
        if (connected) { setSearchQuery(''); fetchEmails(selectedFolder); }
    }, [selectedFolder, connected]);

    // Handle ?gmail_auth= query param after OAuth redirect
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const result = params.get('gmail_auth');
        const reason = params.get('reason') || '';
        if (result === 'success') {
            setErrorReason('');
            toast('Gmail connected successfully!');
            checkConnection().then(ok => { if (ok) fetchEmails('INBOX'); });
            window.history.replaceState({}, '', window.location.pathname);
        } else if (result === 'error') {
            setErrorReason(reason);
            toast('Gmail connection failed. See the error below.', 'error');
            window.history.replaceState({}, '', window.location.pathname);
        }
    }, []);

    // Debounced search
    useEffect(() => {
        clearTimeout(searchTimer.current);
        if (!connected) return;
        if (searchQuery.trim()) {
            searchTimer.current = setTimeout(() => searchEmails(searchQuery), 400);
        } else {
            fetchEmails(selectedFolder);
        }
        return () => clearTimeout(searchTimer.current);
    }, [searchQuery, connected]);

    const toast = useCallback((msg, severity = 'success') => {
        setSnackbar({ open: true, msg, severity });
    }, []);

    const handleReply = useCallback((email, quickText) => {
        if (quickText) {
            sendEmail({ to: [email.from.email], subject: `Re: ${email.subject}`, body: quickText, threadId: email.threadId })
                .then(() => toast('Reply sent'));
            return;
        }
        setComposeMode('reply');
        setComposeDefaults({ to: [email.from.email], subject: `Re: ${email.subject}`, threadId: email.threadId, quotedBody: email.bodyText || '' });
        setComposeOpen(true);
    }, [sendEmail, toast]);

    const handleForward = useCallback((email) => {
        setComposeMode('forward');
        setComposeDefaults({ subject: `Fwd: ${email.subject}`, quotedBody: email.bodyText || '' });
        setComposeOpen(true);
    }, []);

    const handleArchive = useCallback(async (id) => {
        await archiveEmail(id); toast('Archived');
    }, [archiveEmail, toast]);

    const handleDelete = useCallback(async (id) => {
        await trashEmail(id); toast('Moved to trash');
    }, [trashEmail, toast]);

    const handleStar = useCallback(async (id, isStarred) => {
        isStarred ? await unstarEmail(id) : await starEmail(id);
    }, [starEmail, unstarEmail]);

    // Not yet checked → spinner
    if (connected === null) return (
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CircularProgress size={32} />
        </Box>
    );

    // Not connected → connect screen
    if (!connected) return <ConnectScreen onConnect={connectGmail} errorReason={errorReason} />;

    return (
        <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>

            {/* ── Sidebar ── */}
            <Box sx={{ width: SIDEBAR_W, flexShrink: 0, borderRight: '1px solid', borderColor: 'divider', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}>
                <Box sx={{ px: 1.5, py: 1.5 }}>
                    <Box component="button"
                        onClick={() => { setComposeMode('new'); setComposeDefaults({}); setComposeOpen(true); }}
                        sx={{ width: '100%', py: 1, px: 2, bgcolor: 'primary.main', color: 'primary.contrastText', border: 'none', borderRadius: 2, cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, '&:hover': { bgcolor: 'primary.dark' }, transition: 'background 0.15s' }}>
                        ✉ Compose
                    </Box>
                </Box>

                <List dense disablePadding sx={{ flex: 1 }}>
                    {NAV.map(item => (
                        <ListItem key={item.key} disablePadding>
                            <ListItemButton selected={selectedFolder === item.key} onClick={() => setSelectedFolder(item.key)} sx={{ borderRadius: 1, mx: 0.5, mb: 0.25 }}>
                                <ListItemIcon sx={{ minWidth: 32 }}>
                                    <Badge badgeContent={item.key === 'INBOX' ? unreadCount : 0} color="primary" max={99}>
                                        {item.icon}
                                    </Badge>
                                </ListItemIcon>
                                <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 13, fontWeight: selectedFolder === item.key ? 600 : 400 }} />
                            </ListItemButton>
                        </ListItem>
                    ))}

                    <Divider sx={{ my: 1 }} />

                    <ListItem>
                        <Typography variant="caption" color="text.disabled" fontWeight={600} sx={{ letterSpacing: '0.06em', textTransform: 'uppercase' }}>Labels</Typography>
                    </ListItem>
                    {Object.entries(LABEL_COLORS).map(([label, color]) => (
                        <ListItem key={label} disablePadding>
                            <ListItemButton onClick={() => searchEmails(`label:${label.toLowerCase()}`)} sx={{ borderRadius: 1, mx: 0.5, mb: 0.25 }}>
                                <ListItemIcon sx={{ minWidth: 32 }}><LabelIcon sx={{ fontSize: 16, color }} /></ListItemIcon>
                                <ListItemText primary={label} primaryTypographyProps={{ fontSize: 13 }} />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>

                {/* Footer: connected account */}
                <Box sx={{ px: 1.5, py: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.disabled" noWrap sx={{ display: 'block', mb: 0.5 }}>
                        {gmailEmail || 'Connected via Google'}
                    </Typography>
                    <Tooltip title="Disconnect Gmail">
                        <IconButton size="small" onClick={disconnectGmail}><LinkOffIcon sx={{ fontSize: 14 }} /></IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* ── Email List ── */}
            <Box sx={{ width: LIST_W, flexShrink: 0, borderRight: '1px solid', borderColor: 'divider', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}>
                <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
                        {NAV.find(n => n.key === selectedFolder)?.label || 'Inbox'}
                    </Typography>
                    <Tooltip title="Refresh">
                        <IconButton size="small" onClick={() => fetchEmails(selectedFolder)} disabled={loading}>
                            <RefreshIcon fontSize="small" sx={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
                        </IconButton>
                    </Tooltip>
                </Box>

                <Box sx={{ px: 1, py: 0.75, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, bgcolor: 'action.hover', borderRadius: 2, px: 1.25, py: 0.5 }}>
                        <SearchIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
                        <InputBase fullWidth placeholder="Search emails…" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} sx={{ fontSize: 13 }}
                            endAdornment={searchQuery ? <IconButton size="small" onClick={() => setSearchQuery('')}><CloseIcon sx={{ fontSize: 14 }} /></IconButton> : null} />
                    </Box>
                </Box>

                <List disablePadding sx={{ flex: 1, overflowY: 'auto' }}>
                    {loading && emails.length === 0 && (
                        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress size={24} /></Box>
                    )}
                    {error && (
                        <Box sx={{ p: 2, m: 1.5, bgcolor: '#FDEDEC', color: '#C0392B', borderRadius: 2, border: '1px solid #F5B7B1' }}>
                            <Typography variant="subtitle2" fontWeight={700} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                ⚠️ Fetch Error
                            </Typography>
                            <Typography variant="caption" sx={{ wordBreak: 'break-word', fontFamily: 'monospace', display: 'block', mb: 1.5 }}>
                                {error}
                            </Typography>
                            <Typography variant="caption" sx={{ display: 'block', opacity: 0.9 }}>
                                <strong>How to fix:</strong> Visit <a href="https://console.developers.google.com/apis/api/gmail.googleapis.com/overview" target="_blank" rel="noopener noreferrer" style={{ color: '#922B21', textDecoration: 'underline', fontWeight: 600 }}>Google API Console</a> and make sure the <strong>Gmail API</strong> is enabled for your Google Cloud project, then try again.
                            </Typography>
                        </Box>
                    )}
                    {!loading && emails.length === 0 && !error && (
                        <Box sx={{ textAlign: 'center', pt: 6, color: 'text.disabled' }}>
                            <InboxIcon sx={{ fontSize: 40, opacity: 0.3 }} />
                            <Typography variant="body2" sx={{ mt: 1 }}>No emails here</Typography>
                        </Box>
                    )}
                    {emails.map(email => (
                        <EmailRow key={email.id} email={email} selected={selectedEmail?.id === email.id}
                            onClick={() => openEmail(email)} />
                    ))}
                </List>
            </Box>

            {/* ── Reading Pane ── */}
            <EmailView
                email={selectedEmail}
                onReply={handleReply}
                onForward={handleForward}
                onArchive={handleArchive}
                onDelete={handleDelete}
                onStar={handleStar}
                onMarkUnread={markAsUnread}
            />

            {/* ── Compose ── */}
            <ComposeModal
                open={composeOpen}
                onClose={() => setComposeOpen(false)}
                mode={composeMode}
                defaults={composeDefaults}
                onSend={async (payload) => {
                    await sendEmail(payload);
                    setComposeOpen(false);
                    toast('Email sent');
                }}
            />

            {/* ── Toast ── */}
            <Snackbar open={snackbar.open} autoHideDuration={3000}
                onClose={() => setSnackbar(s => ({ ...s, open: false }))}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
                <Alert severity={snackbar.severity} variant="filled" sx={{ fontSize: 13 }}>{snackbar.msg}</Alert>
            </Snackbar>
        </Box>
    );
}
