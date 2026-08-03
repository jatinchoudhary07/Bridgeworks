import React, { useState, useRef } from 'react';
import Draggable from 'react-draggable';
import {
    Paper, IconButton, InputBase, Box,
    Tooltip, Menu, MenuItem, ListItemIcon, ListItemText,
    Typography, Checkbox, Button, Divider, Badge, Popover,
    List, ListItem, ListItemAvatar, Avatar, TextField
} from '@mui/material';
import {
    Close as CloseIcon,
    Check as CheckIcon,
    Share as ShareIcon,
    DragIndicator as DragIcon,
    AttachFile as AttachFileIcon,
    ChatBubbleOutline as CommentIcon,
    Send as SendIcon,
    Unarchive as UnarchiveIcon,
    DeleteForever as DeleteForeverIcon
} from '@mui/icons-material';
import { apiClient } from '../../apiClient';

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function StickyNote({
    note,
    noteView,
    onUpdate,
    onMove,
    onComplete,
    onDelete,
    onUnarchive,
    onPermanentDelete,
    onPass,
    users,
    currentUserId,
    selectMode = false,
    isSelected = false,
    onToggleSelect
}) {
    const [content, setContent] = useState(note.content);
    const [anchorEl, setAnchorEl] = useState(null);
    const [selectedUsers, setSelectedUsers] = useState([]);
    const [selectedFile, setSelectedFile] = useState(null);
    const nodeRef = useRef(null);
    const fileInputRef = useRef(null);

    // ========== COMMENT STATE ==========
    const [commentAnchor, setCommentAnchor] = useState(null);
    const [comments, setComments] = useState([]);
    const [commentText, setCommentText] = useState('');
    const [loadingComments, setLoadingComments] = useState(false);

    // @mention autocomplete
    const [mentionAnchor, setMentionAnchor] = useState(null);
    const [mentionFilter, setMentionFilter] = useState('');
    const [mentionCursorPos, setMentionCursorPos] = useState(0);
    const commentInputRef = useRef(null);
    const isCreator = note.created_by === currentUserId;
    const canEdit = isCreator && !note.is_completed && !note.is_deleted;
    const canComplete = !note.is_completed && !note.is_deleted;
    const canMove = true;
    const isArchivedView = noteView === 'archived';
    const isDeletedView = noteView === 'deleted';
    const isSharedNote = Boolean(note.parent_note)
        || (note.shared_with_user_ids || []).length > 0
        || note.created_by !== note.assigned_to;
    const canComment = isSharedNote && !note.is_deleted;
    const actionIconSx = {
        color: 'rgba(61,47,8,0.75)',
        '&.Mui-disabled': {
            color: 'rgba(61,47,8,0.45)',
            opacity: 1
        }
    };

    // Fetch comments when popover opens
    const fetchComments = async () => {
        setLoadingComments(true);
        try {
            const res = await apiClient(`${BACKEND_URL}/api/postits/${note.id}/comments/`, {
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                setComments(data);
            }
        } catch (err) {
            console.error('Failed to fetch comments', err);
        }
        setLoadingComments(false);
    };

    const handleCommentOpen = (e) => {
        if (!canComment) return;
        setCommentAnchor(e.currentTarget);
        fetchComments();
    };

    const handleCommentClose = () => {
        setCommentAnchor(null);
        setMentionAnchor(null);
    };

    const handleCommentSubmit = async () => {
        if (!commentText.trim()) return;
        try {
            const res = await apiClient(`${BACKEND_URL}/api/postits/${note.id}/add_comment/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ text: commentText.trim() })
            });
            if (res.ok) {
                const newComment = await res.json();
                setComments(prev => [...prev, newComment]);
                setCommentText('');
            }
        } catch (err) {
            console.error('Failed to add comment', err);
        }
    };

    // @mention: detect '@' in input
    const handleCommentChange = (e) => {
        const value = e.target.value;
        setCommentText(value);

        const cursorPos = e.target.selectionStart;
        setMentionCursorPos(cursorPos);

        // Check if we're in an @mention context
        const textBeforeCursor = value.substring(0, cursorPos);
        const atMatch = textBeforeCursor.match(/@(\w*)$/);

        if (atMatch) {
            setMentionFilter(atMatch[1].toLowerCase());
            setMentionAnchor(commentInputRef.current);
        } else {
            setMentionAnchor(null);
            setMentionFilter('');
        }
    };

    const handleMentionSelect = (user) => {
        const name = user.full_name?.split(' ')[0] || user.username;
        const textBeforeCursor = commentText.substring(0, mentionCursorPos);
        const textAfterCursor = commentText.substring(mentionCursorPos);
        // Replace the partial @text with @Name
        const beforeAt = textBeforeCursor.replace(/@\w*$/, '');
        setCommentText(`${beforeAt}@${name} ${textAfterCursor}`);
        setMentionAnchor(null);
        setMentionFilter('');
        // Refocus input
        setTimeout(() => commentInputRef.current?.focus(), 50);
    };

    const filteredMentionUsers = users.filter(u =>
        u.id !== currentUserId &&
        ((u.full_name || u.username || '').toLowerCase().includes(mentionFilter))
    );

    // Render comment text with highlighted @mentions
    const renderCommentText = (text) => {
        const parts = text.split(/(@\w+)/g);
        return parts.map((part, i) => {
            if (part.startsWith('@')) {
                return (
                    <Typography
                        key={i}
                        component="span"
                        sx={{
                            color: '#1565c0',
                            fontWeight: 600,
                            fontSize: 11,
                            lineHeight: 1.2,
                            bgcolor: 'rgba(21,101,192,0.08)',
                            borderRadius: 0.5,
                            px: 0.2
                        }}
                    >
                        {part}
                    </Typography>
                );
            }
            return <span key={i}>{part}</span>;
        });
    };

    // ========== EXISTING HANDLERS ==========

    const handleBlur = () => {
        if (!canEdit) return;
        if (content !== note.content) {
            onUpdate(note.id, { content });
        }
    };

    const handleStop = (e, data) => {
        if (data.x !== note.x_position || data.y !== note.y_position) {
            onMove(note.id, data.x, data.y);
        }
    };

    const handleShareClick = (event) => {
        if (!canEdit) return;
        setAnchorEl(event.currentTarget);
        setSelectedUsers([]);
    };

    const sharedWithEveryone = (note.shared_with_names || '').split(',').map(name => name.trim()).includes('Everyone');

    const toggleUserSelection = (userId) => {
        setSelectedUsers(prev =>
            prev.includes(userId)
                ? prev.filter(id => id !== userId)
                : [...prev, userId]
        );
    };

    const handleShareConfirm = () => {
        if (selectedUsers.length > 0) {
            onPass(note.id, selectedUsers);
        }
        setAnchorEl(null);
        setSelectedUsers([]);
    };

    const handleShareCancel = () => {
        setAnchorEl(null);
        setSelectedUsers([]);
    };

    const handleFileSelect = (event) => {
        if (!canEdit) return;
        const file = event.target.files[0];
        if (file) {
            setSelectedFile(file);
            if (content !== note.content) {
                onUpdate(note.id, { content });
            }
            setTimeout(() => {
                onUpdate(note.id, { content }, file);
            }, 100);
        }
    };

    const handleAttachClick = () => {
        if (!canEdit) return;
        fileInputRef.current?.click();
    };

    const handleRemoveAttachment = () => {
        if (!canEdit) return;
        setSelectedFile(null);
        onUpdate(note.id, { content, attachment: null });
    };

    return (
        <Draggable
            nodeRef={nodeRef}
            defaultPosition={{ x: note.x_position, y: note.y_position }}
            onStop={handleStop}
            disabled={!canMove || selectMode}
            bounds=".postit-canvas"
            cancel=".MuiIconButton-root, .MuiInputBase-root, .MuiInputBase-input, .MuiButton-root, .MuiMenu-root, .MuiPopover-root, .MuiListItem-root, .MuiChip-root, input, textarea, button, a, [role='button'], [contenteditable='true'], .MuiCheckbox-root"
        >
            <Paper
                ref={nodeRef}
                elevation={3}
                sx={{
                    position: 'absolute',
                    width: 200,
                    height: 200,
                    bgcolor: note.color || '#ffeb3b',
                    color: '#3d2f08',
                    display: 'flex',
                    flexDirection: 'column',
                    zIndex: 1300,
                    transform: 'rotate(-1deg)',
                    transition: 'box-shadow 0.2s',
                    overflow: 'visible',
                    '&:hover': {
                        boxShadow: 6,
                        zIndex: 1301
                    },
                    '&::before': {
                        content: '""',
                        position: 'absolute',
                        top: 0,
                        right: 0,
                        width: 0,
                        height: 0,
                        borderStyle: 'solid',
                        borderWidth: '0 20px 20px 0',
                        borderColor: 'transparent rgba(0,0,0,0.15) transparent transparent',
                        zIndex: 1
                    }
                }}
            >
                {/* HEADER */}
                <Box
                    className="drag-handle"
                    sx={{
                        p: 0.5,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: canMove ? 'move' : 'default',
                        borderBottom: '1px solid rgba(0,0,0,0.1)'
                    }}
                >
                    {selectMode ? (
                        <Checkbox
                            checked={isSelected}
                            onChange={onToggleSelect}
                            size="small"
                            sx={{
                                color: 'rgba(61,47,8,0.75)',
                                '&.Mui-checked': {
                                    color: 'rgba(61,47,8,0.95)'
                                }
                            }}
                        />
                    ) : (
                        <DragIcon sx={{ fontSize: 16, color: 'rgba(61,47,8,0.65)' }} />
                    )}
                    {!note.is_completed && !note.is_deleted && !isArchivedView && !isDeletedView && (
                        <Box>
                            <Tooltip title={isCreator ? "Attach File" : "Only creator can edit"}>
                                <IconButton size="small" onClick={handleAttachClick} disabled={!canEdit} sx={actionIconSx}>
                                    <AttachFileIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title={canComment ? "Comments" : "Comments are disabled for private notes"}>
                                <IconButton size="small" onClick={handleCommentOpen} disabled={!canComment} sx={actionIconSx}>
                                    <Badge
                                        badgeContent={note.comment_count || 0}
                                        color="primary"
                                        max={99}
                                        sx={{
                                            '& .MuiBadge-badge': {
                                                fontSize: 9,
                                                minWidth: 14,
                                                height: 14,
                                                p: 0
                                            }
                                        }}
                                    >
                                        <CommentIcon fontSize="small" />
                                    </Badge>
                                </IconButton>
                            </Tooltip>
                            <Tooltip title={isCreator ? "Share with Team" : "Only creator can edit"}>
                                <IconButton size="small" onClick={handleShareClick} disabled={!canEdit} sx={actionIconSx}>
                                    <ShareIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Mark as Completed">
                                <IconButton
                                    size="small"
                                    onClick={() => onComplete(note.id)}
                                    disabled={!canComplete}
                                    sx={actionIconSx}
                                >
                                    <CheckIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title={isCreator ? "Delete" : "Only creator can delete"}>
                                <IconButton
                                    size="small"
                                    onClick={() => onDelete(note.id)}
                                    disabled={!canEdit}
                                    sx={actionIconSx}
                                >
                                    <CloseIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    )}
                    {isArchivedView && (
                        <Box>
                            <Tooltip title="Unarchive">
                                <IconButton
                                    size="small"
                                    onClick={() => onUnarchive(note.id)}
                                    sx={actionIconSx}
                                >
                                    <UnarchiveIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    )}
                    {isDeletedView && (
                        <Box>
                            <Tooltip title={isCreator ? "Permanently Delete" : "Only creator can permanently delete"}>
                                <IconButton
                                    size="small"
                                    onClick={() => onPermanentDelete(note.id)}
                                    disabled={!isCreator}
                                    sx={actionIconSx}
                                >
                                    <DeleteForeverIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        </Box>
                    )}
                </Box>

                {/* CONTENT */}
                <Box sx={{ flexGrow: 1, p: 1, overflow: 'auto' }}>
                    <InputBase
                        multiline
                        fullWidth
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onBlur={handleBlur}
                        placeholder="Type a note..."
                        readOnly={!canEdit}
                        sx={{
                            height: '100%',
                            alignItems: 'flex-start',
                            color: '#3d2f08',
                            fontFamily: '"Comic Sans MS", "Cursive", "sans-serif"',
                            fontSize: '0.95rem',
                            '& textarea::placeholder': {
                                color: 'rgba(61,47,8,0.62)',
                                opacity: 1
                            },
                            ...(!canEdit && { opacity: 0.8 })
                        }}
                    />
                </Box>

                {/* ATTACHMENT DISPLAY */}
                {(note.attachment_url || selectedFile) && (
                    <Box sx={{ px: 1, pb: 0.5 }}>
                        <Box sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5,
                            bgcolor: 'rgba(0,0,0,0.05)',
                            p: 0.5,
                            borderRadius: 1
                        }}>
                            <AttachFileIcon sx={{ fontSize: 14 }} />
                            <Typography variant="caption" sx={{ flex: 1, fontSize: 11, color: '#3d2f08', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {selectedFile ? selectedFile.name : note.attachment_filename}
                            </Typography>
                            {note.attachment_url && (
                                <IconButton
                                    size="small"
                                    component="a"
                                    href={note.attachment_url}
                                    target="_blank"
                                    sx={{ p: 0.25 }}
                                >
                                    <Typography variant="caption" sx={{ fontSize: 10 }}>↓</Typography>
                                </IconButton>
                            )}
                            <IconButton size="small" onClick={handleRemoveAttachment} disabled={!canEdit} sx={{ p: 0.25 }}>
                                <CloseIcon sx={{ fontSize: 12 }} />
                            </IconButton>
                        </Box>
                    </Box>
                )}

                {/* HIDDEN FILE INPUT */}
                <input
                    ref={fileInputRef}
                    type="file"
                    hidden
                    onChange={handleFileSelect}
                    accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"
                />

                {/* FOOTER Info */}
                <Box sx={{ p: 0.5, textAlign: 'right' }}>
                    {note.shared_with_names && (
                        <Typography variant="caption" sx={{ fontSize: 10, display: 'block', color: 'rgba(61,47,8,0.72)' }}>
                            Shared with: {note.shared_with_names}
                        </Typography>
                    )}
                    <Typography variant="caption" sx={{ fontSize: 10, color: 'rgba(61,47,8,0.72)' }}>
                        {note.is_completed && note.completed_by_name ? (
                            `Completed by: ${note.completed_by === currentUserId ? 'You' : note.completed_by_name}`
                        ) : note.created_by !== note.assigned_to ? (
                            `From: ${note.created_by_name || 'teammate'}`
                        ) : !note.shared_with_names ? (
                            `By: Me`
                        ) : null}
                    </Typography>
                </Box>

                {/* =============== COMMENT POPOVER =============== */}
                <Popover
                    open={Boolean(commentAnchor)}
                    anchorEl={commentAnchor}
                    onClose={handleCommentClose}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                    transformOrigin={{ vertical: 'top', horizontal: 'center' }}
                    sx={{ zIndex: 100001 }}
                    slotProps={{
                        paper: {
                            sx: {
                                width: 280,
                                maxHeight: 350,
                                display: 'flex',
                                flexDirection: 'column',
                                borderRadius: 2,
                                boxShadow: 6
                            }
                        }
                    }}
                >
                    {/* Comment Header */}
                    <Box sx={{ p: 1.5, borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <Typography variant="subtitle2" fontWeight={700}>
                            💬 Comments ({comments.length})
                        </Typography>
                        <IconButton size="small" onClick={handleCommentClose}>
                            <CloseIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                    </Box>

                    {/* Comment List */}
                    <Box sx={{ flex: 1, overflowY: 'auto', px: 1 }}>
                        {loadingComments ? (
                            <Typography variant="caption" sx={{ p: 2, display: 'block', textAlign: 'center', color: 'text.secondary' }}>
                                Loading...
                            </Typography>
                        ) : comments.length === 0 ? (
                            <Typography variant="caption" sx={{ p: 2, display: 'block', textAlign: 'center', color: 'text.secondary' }}>
                                No comments yet. Start the conversation!
                            </Typography>
                        ) : (
                            <List dense disablePadding>
                                {comments.map(c => (
                                    <ListItem key={c.id} alignItems="flex-start" disablePadding sx={{ py: 0.5 }}>
                                        <ListItemAvatar sx={{ minWidth: 32 }}>
                                            <Avatar sx={{ width: 24, height: 24, fontSize: 12, bgcolor: '#1976d2' }}>
                                                {(c.user_name || '?')[0].toUpperCase()}
                                            </Avatar>
                                        </ListItemAvatar>
                                        <Box sx={{ flex: 1, minWidth: 0 }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                <Typography variant="caption" fontWeight={700} sx={{ fontSize: 11 }}>
                                                    {c.user_name}
                                                </Typography>
                                                <Typography variant="caption" sx={{ fontSize: 9, color: 'text.disabled' }}>
                                                    {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                </Typography>
                                            </Box>
                                            <Typography variant="body2" sx={{ fontSize: 12, wordBreak: 'break-word' }}>
                                                {renderCommentText(c.text)}
                                            </Typography>
                                        </Box>
                                    </ListItem>
                                ))}
                            </List>
                        )}
                    </Box>

                    {/* Comment Input */}
                    <Box sx={{ p: 1, borderTop: '1px solid #eee', display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        <TextField
                            inputRef={commentInputRef}
                            size="small"
                            fullWidth
                            placeholder="Type @ to mention..."
                            value={commentText}
                            onChange={handleCommentChange}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleCommentSubmit();
                                }
                            }}
                            sx={{
                                '& .MuiInputBase-root': { fontSize: 12, borderRadius: 2 }
                            }}
                        />
                        <IconButton
                            size="small"
                            color="primary"
                            onClick={handleCommentSubmit}
                            disabled={!commentText.trim()}
                        >
                            <SendIcon sx={{ fontSize: 18 }} />
                        </IconButton>
                    </Box>

                    {/* @Mention Autocomplete Dropdown */}
                    <Popover
                        open={Boolean(mentionAnchor) && filteredMentionUsers.length > 0}
                        anchorEl={mentionAnchor}
                        onClose={() => setMentionAnchor(null)}
                        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
                        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                        disableAutoFocus
                        disableEnforceFocus
                        sx={{ zIndex: 100002 }}
                        slotProps={{
                            paper: {
                                sx: { maxHeight: 150, minWidth: 180, boxShadow: 4, borderRadius: 1.5 }
                            }
                        }}
                    >
                        <List dense disablePadding>
                            {filteredMentionUsers.map(user => (
                                <ListItem
                                    key={user.id}
                                    onClick={() => handleMentionSelect(user)}
                                    sx={{
                                        cursor: 'pointer',
                                        '&:hover': { bgcolor: 'action.hover' },
                                        py: 0.35,
                                        px: 1
                                    }}
                                >
                                    <Avatar sx={{ width: 18, height: 18, fontSize: 9, mr: 0.75, bgcolor: '#1976d2' }}>
                                        {(user.full_name || user.username || '?')[0].toUpperCase()}
                                    </Avatar>
                                    <Typography variant="body2" sx={{ fontSize: 11 }}>
                                        {user.full_name || user.username}
                                    </Typography>
                                </ListItem>
                            ))}
                        </List>
                    </Popover>
                </Popover>

                {/* SHARE MENU */}
                <Menu
                    anchorEl={anchorEl}
                    open={Boolean(anchorEl)}
                    onClose={handleShareCancel}
                    PaperProps={{ sx: { minWidth: 220 } }}
                    sx={{ zIndex: 100000 }}
                >
                    <MenuItem disabled>
                        <Typography variant="caption" fontWeight="bold">
                            Share with... (Select {selectedUsers.length > 0 ? selectedUsers.length : 'teammates'})
                        </Typography>
                    </MenuItem>
                    <Divider />
                    <MenuItem
                        onClick={() => !sharedWithEveryone && toggleUserSelection('everyone')}
                        dense
                        disabled={sharedWithEveryone}
                        sx={sharedWithEveryone ? { opacity: 0.5 } : {}}
                    >
                        <Checkbox
                            checked={sharedWithEveryone || selectedUsers.includes('everyone')}
                            size="small"
                            disabled={sharedWithEveryone}
                        />
                        <ListItemText
                            primary="Everyone"
                        />
                    </MenuItem>
                    <Divider />
                    {users.filter(user => user.id !== currentUserId).map(user => {
                        const alreadyShared = (note.shared_with_user_ids || []).includes(user.id);
                        return (
                            <MenuItem
                                key={user.id}
                                onClick={() => !alreadyShared && toggleUserSelection(user.id)}
                                dense
                                disabled={alreadyShared}
                                sx={alreadyShared ? { opacity: 0.5 } : {}}
                            >
                                <Checkbox
                                    checked={alreadyShared || selectedUsers.includes(user.id)}
                                    size="small"
                                    disabled={alreadyShared}
                                />
                                <ListItemText
                                    primary={user.full_name || user.username || user.email}
                                    secondary={alreadyShared ? '✓ Shared' : null}
                                    secondaryTypographyProps={{ sx: { fontSize: 10, color: 'success.main' } }}
                                />
                            </MenuItem>
                        );
                    })}
                    {users.filter(user => user.id !== currentUserId).length === 0 && (
                        <MenuItem disabled>No teammates found</MenuItem>
                    )}
                    <Divider />
                    <Box sx={{ display: 'flex', gap: 1, p: 1, justifyContent: 'flex-end' }}>
                        <Button size="small" onClick={handleShareCancel}>Cancel</Button>
                        <Button
                            size="small"
                            variant="contained"
                            onClick={handleShareConfirm}
                            disabled={selectedUsers.length === 0}
                        >
                            Share ({selectedUsers.length})
                        </Button>
                    </Box>
                </Menu>
            </Paper>
        </Draggable>
    );
}