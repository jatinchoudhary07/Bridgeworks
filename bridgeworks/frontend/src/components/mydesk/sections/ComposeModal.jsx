// ComposeModal.jsx — Full compose / reply / forward dialog
import React, { useState, useEffect, useRef } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Box, TextField, IconButton, Button, Chip, Tooltip,
    Typography, Divider, CircularProgress,
} from '@mui/material';
import {
    Close as CloseIcon,
    AttachFile as AttachIcon,
    Send as SendIcon,
    ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';

export default function ComposeModal({ open, onClose, mode = 'new', defaults = {}, onSend }) {
    const [to,       setTo]       = useState('');
    const [cc,       setCc]       = useState('');
    const [bcc,      setBcc]      = useState('');
    const [subject,  setSubject]  = useState('');
    const [body,     setBody]     = useState('');
    const [files,    setFiles]    = useState([]);
    const [showCc,   setShowCc]   = useState(false);
    const [sending,  setSending]  = useState(false);
    const [error,    setError]    = useState('');
    const fileRef = useRef(null);

    // Populate fields when defaults change (reply / forward)
    useEffect(() => {
        if (!open) return;
        setTo(     (defaults.to    || []).join(', '));
        setCc(     (defaults.cc    || []).join(', '));
        setBcc(    (defaults.bcc   || []).join(', '));
        setSubject(defaults.subject  || '');
        setFiles(  defaults.attachments?.filter(a => a instanceof File) || []);

        // For reply/forward — add quoted body below a separator
        if (mode === 'reply' || mode === 'forward') {
            setBody(`\n\n------- ${mode === 'reply' ? 'Original message' : 'Forwarded message'} -------\n${defaults.quotedBody || ''}`);
        } else {
            setBody('');
        }
        setError('');
        setSending(false);
    }, [open, defaults, mode]);

    const handleSend = async () => {
        if (!to.trim()) { setError('Recipient (To) is required.'); return; }
        setSending(true);
        setError('');
        try {
            await onSend({
                to:       to.split(',').map(s => s.trim()).filter(Boolean),
                cc:       cc.split(',').map(s => s.trim()).filter(Boolean),
                bcc:      bcc.split(',').map(s => s.trim()).filter(Boolean),
                subject,
                body,
                threadId: defaults.threadId,
                attachments: files,
            });
        } catch (e) {
            setError(e.message || 'Failed to send.');
            setSending(false);
        }
    };

    const modeTitle = { new: 'New Message', reply: 'Reply', forward: 'Forward' }[mode] || 'Compose';

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="md"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: 3,
                    boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
                    overflow: 'hidden',
                }
            }}
        >
            {/* Header */}
            <DialogTitle component="div" sx={{ display: 'flex', alignItems: 'center', py: 1.5, px: 2.5, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
                <Typography variant="subtitle1" component="span" fontWeight={600} sx={{ flex: 1 }}>{modeTitle}</Typography>
                <IconButton size="small" onClick={onClose} sx={{ color: 'primary.contrastText' }}>
                    <CloseIcon fontSize="small" />
                </IconButton>
            </DialogTitle>

            <DialogContent sx={{ p: 0 }}>
                {/* Recipients */}
                <Box sx={{ px: 2.5, pt: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ width: 40, flexShrink: 0 }}>To</Typography>
                        <TextField
                            fullWidth variant="standard" size="small"
                            placeholder="recipient@example.com, another@example.com"
                            value={to} onChange={e => setTo(e.target.value)}
                            InputProps={{ disableUnderline: false }}
                            sx={{ '& .MuiInput-root': { fontSize: 13 } }}
                        />
                        <Tooltip title="Add Cc / Bcc">
                            <IconButton size="small" onClick={() => setShowCc(v => !v)}>
                                <ExpandMoreIcon sx={{ fontSize: 18, transform: showCc ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
                            </IconButton>
                        </Tooltip>
                    </Box>

                    {showCc && (
                        <>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                                <Typography variant="caption" color="text.secondary" sx={{ width: 40, flexShrink: 0 }}>Cc</Typography>
                                <TextField fullWidth variant="standard" size="small" placeholder="cc@example.com"
                                    value={cc} onChange={e => setCc(e.target.value)}
                                    sx={{ '& .MuiInput-root': { fontSize: 13 } }} />
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                                <Typography variant="caption" color="text.secondary" sx={{ width: 40, flexShrink: 0 }}>Bcc</Typography>
                                <TextField fullWidth variant="standard" size="small" placeholder="bcc@example.com"
                                    value={bcc} onChange={e => setBcc(e.target.value)}
                                    sx={{ '& .MuiInput-root': { fontSize: 13 } }} />
                            </Box>
                        </>
                    )}

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ width: 40, flexShrink: 0 }}>Subj</Typography>
                        <TextField fullWidth variant="standard" size="small" placeholder="Subject"
                            value={subject} onChange={e => setSubject(e.target.value)}
                            sx={{ '& .MuiInput-root': { fontSize: 13 } }} />
                    </Box>
                </Box>

                <Divider />

                {/* Body */}
                <TextField
                    fullWidth multiline minRows={10} maxRows={20}
                    placeholder="Write your message…"
                    value={body} onChange={e => setBody(e.target.value)}
                    variant="standard"
                    sx={{
                        px: 2.5, pt: 1.5, pb: 1,
                        '& .MuiInput-root': { fontSize: 13, lineHeight: 1.7 },
                        '& textarea': { resize: 'none' },
                    }}
                    InputProps={{ disableUnderline: true }}
                />

                {/* Attachments */}
                {files.length > 0 && (
                    <Box sx={{ px: 2.5, pb: 1, display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                        {files.map((f, i) => (
                            <Chip key={i} label={`${f.name} (${(f.size / 1024).toFixed(0)} KB)`} size="small"
                                onDelete={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                                sx={{ fontSize: 11 }} />
                        ))}
                    </Box>
                )}

                {error && (
                    <Typography variant="caption" color="error" sx={{ px: 2.5, pb: 1, display: 'block' }}>
                        {error}
                    </Typography>
                )}
            </DialogContent>

            <Divider />

            {/* Footer actions */}
            <DialogActions sx={{ px: 2.5, py: 1.25, justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    <Tooltip title="Attach files">
                        <IconButton size="small" onClick={() => fileRef.current?.click()}>
                            <AttachIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <input ref={fileRef} type="file" multiple hidden
                        onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files)])} />
                </Box>

                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button size="small" onClick={onClose} disabled={sending}>Cancel</Button>
                    <Button
                        size="small" variant="contained" startIcon={sending ? <CircularProgress size={14} color="inherit" /> : <SendIcon fontSize="small" />}
                        onClick={handleSend} disabled={sending || !to.trim()}
                        sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
                    >
                        {sending ? 'Sending…' : 'Send'}
                    </Button>
                </Box>
            </DialogActions>
        </Dialog>
    );
}
