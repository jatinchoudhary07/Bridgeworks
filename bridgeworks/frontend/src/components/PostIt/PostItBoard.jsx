import React, { useState, useEffect, useMemo, useRef } from 'react';
import Draggable from 'react-draggable';
import {
    Box, Chip, Menu, MenuItem, Checkbox, Button
} from '@mui/material';
import {
    NoteAdd as NoteAddIcon,
    StickyNote2 as StickyNoteIcon,
    Close as CloseIcon,
    Menu as MenuIcon,
    Assessment as AssessmentIcon,
    Group as GroupIcon,
    MenuBook as MenuBookIcon,
} from '@mui/icons-material';
import StickyNote from './StickyNote';
import { apiClient } from '../../apiClient';
import { useUser } from '../../contexts/UserContext';
import TeamChat from '../taskmanager/TeamChat';
import AnalyticsChatWidget from '../common/AnalyticsChatWidget';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import MyNotesPanel from './MyNotesPanel';

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const NOTE_WIDTH = 200;
const NOTE_HEIGHT = 200;
const NOTE_HORIZONTAL_GAP = 12;
const NOTE_VERTICAL_GAP = 14;
const NOTE_START_X = 16;
const NOTE_START_Y = 74;

export default function PostItBoard({ quickAccessOpen, setQuickAccessOpen, anchorEl }) {
    const { user } = useUser();
    const [isOpen, setIsOpen] = useState(false);
    const [notes, setNotes] = useState([]);
    const [users, setUsers] = useState([]);
    const [noteView, setNoteView] = useState('active');
    const [currentUserId, setCurrentUserId] = useState(null);
    const [chatOpen, setChatOpen] = useState(false);
    const [analystOpen, setAnalystOpen] = useState(false);
    const [myNotesOpen, setMyNotesOpen] = useState(false);
    const [selectMode, setSelectMode] = useState(false);
    const [selectedNoteIds, setSelectedNoteIds] = useState(new Set());
    const [hiddenNoteIds, setHiddenNoteIds] = useState(new Set());
    const [showHidden, setShowHidden] = useState(false);
    const [selectedUserIds, setSelectedUserIds] = useState(new Set());
    const [userFilterAnchor, setUserFilterAnchor] = useState(null);
    const [sortAnchor, setSortAnchor] = useState(null);
    const [sortOrder, setSortOrder] = useState('newest');
    const [shareAnchor, setShareAnchor] = useState(null);
    const [selectedShareUserIds, setSelectedShareUserIds] = useState([]);
    const filterNodeRef = useRef(null);
    const skipNextAutoFetchRef = useRef(false);

    const memberOptions = useMemo(() => {
        const unique = [];
        const seenIds = new Set();
        for (const u of users) {
            if (!seenIds.has(u.id)) {
                unique.push(u);
                seenIds.add(u.id);
            }
        }
        return unique;
    }, [users]);

    // 1. Initial Setup — only after auth is ready
    useEffect(() => {
        if (!user) return;
        setCurrentUserId(user.id);

        const init = async () => {
            try {
                const userRes = await apiClient(`${BACKEND_URL}/api/team/members/`, { credentials: "include" });
                if (userRes.ok) {
                    const members = await userRes.json();
                    setUsers(members);
                }
            } catch (e) { console.error("User Fetch Error", e); }
        };

        init();
    }, [user]);

    // Fetch notes while board is open + poll every 30s
    useEffect(() => {
        if (!isOpen) return undefined;

        if (skipNextAutoFetchRef.current) {
            skipNextAutoFetchRef.current = false;
            return undefined;
        }

        fetchNotes();
        const interval = setInterval(fetchNotes, 30000);
        return () => clearInterval(interval);
    }, [isOpen, noteView]);

    useEffect(() => {
        setSelectedNoteIds(new Set());
        setSelectMode(false);
    }, [noteView]);

    useEffect(() => {
        setNotes((prev) => arrangeNotesForDisplay(prev, sortOrder));
    }, [sortOrder]);

    const fetchNotes = async () => {
        try {
            const notesUrl = noteView === 'archived'
                ? `${BACKEND_URL}/api/postits/completed/`
                : noteView === 'deleted'
                    ? `${BACKEND_URL}/api/postits/?view=deleted`
                    : `${BACKEND_URL}/api/postits/`;

            const res = await apiClient(notesUrl, { credentials: "include" });
            if (res.ok) {
                const data = await res.json();
                setNotes(arrangeNotesForDisplay(data, sortOrder));
            }
        } catch (err) {
            console.error("Failed to fetch notes", err);
        }
    };

    // --- ACTIONS ---

    const getCreatedTime = (note) => {
        const raw = note.created_at || note.createdAt;
        if (!raw) return 0;
        const time = new Date(raw).getTime();
        return Number.isNaN(time) ? 0 : time;
    };

    const arrangeNotesForDisplay = (noteItems, order = sortOrder) => {
        const sorted = [...noteItems].sort((a, b) => {
            const timeA = getCreatedTime(a);
            const timeB = getCreatedTime(b);
            if (timeA === timeB) {
                return (b.id || 0) - (a.id || 0);
            }
            return order === 'oldest' ? timeA - timeB : timeB - timeA;
        });
        return layoutNotesSequentially(sorted);
    };

    const layoutNotesSequentially = (noteItems) => {
        const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1280;
        const usableWidth = Math.max(NOTE_WIDTH, viewportWidth - (NOTE_START_X * 2));
        const columns = Math.max(1, Math.floor((usableWidth + NOTE_HORIZONTAL_GAP) / (NOTE_WIDTH + NOTE_HORIZONTAL_GAP)));

        return noteItems.map((note, index) => {
            const row = Math.floor(index / columns);
            const column = index % columns;

            return {
                ...note,
                x_position: NOTE_START_X + (column * (NOTE_WIDTH + NOTE_HORIZONTAL_GAP)),
                y_position: NOTE_START_Y + (row * (NOTE_HEIGHT + NOTE_VERTICAL_GAP))
            };
        });
    };

    const getNextNotePosition = () => {
        const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1280;
        const usableWidth = Math.max(NOTE_WIDTH, viewportWidth - (NOTE_START_X * 2));
        const maxColumns = Math.max(1, Math.floor((usableWidth + NOTE_HORIZONTAL_GAP) / (NOTE_WIDTH + NOTE_HORIZONTAL_GAP)));
        const fallbackIndex = notes.length;

        return {
            x: NOTE_START_X + ((fallbackIndex % maxColumns) * (NOTE_WIDTH + NOTE_HORIZONTAL_GAP)),
            y: NOTE_START_Y + (Math.floor(fallbackIndex / maxColumns) * (NOTE_HEIGHT + NOTE_VERTICAL_GAP))
        };
    };

    const toggleNoteSelection = (noteId) => {
        setSelectedNoteIds((prev) => {
            const updated = new Set(prev);
            if (updated.has(noteId)) {
                updated.delete(noteId);
            } else {
                updated.add(noteId);
            }
            return updated;
        });
    };

    const toggleUserFilter = (userId) => {
        setSelectedUserIds((prev) => {
            const updated = new Set(prev);
            if (updated.has(userId)) {
                updated.delete(userId);
            } else {
                updated.add(userId);
            }
            return updated;
        });
    };

    const toggleShareTargetUser = (userId) => {
        setSelectedShareUserIds((prev) => (
            prev.includes(userId)
                ? prev.filter((id) => id !== userId)
                : [...prev, userId]
        ));
    };

    const clearSelection = () => {
        setSelectedNoteIds(new Set());
    };

    const handleToggleSelectMode = () => {
        setSelectMode((prev) => {
            const next = !prev;
            if (!next) {
                clearSelection();
            }
            return next;
        });
    };

    const handleSelectAllVisible = () => {
        setSelectedNoteIds(new Set(visibleNotes.map((note) => note.id)));
    };

    const handleBulkHideSelected = () => {
        if (selectedNoteIds.size === 0) return;
        setHiddenNoteIds((prev) => {
            const updated = new Set(prev);
            selectedNoteIds.forEach((id) => updated.add(id));
            return updated;
        });
        setShowHidden(false);
        clearSelection();
    };

    const handleBulkUnhideSelected = () => {
        if (selectedNoteIds.size === 0) return;
        setHiddenNoteIds((prev) => {
            const updated = new Set(prev);
            selectedNoteIds.forEach((id) => updated.delete(id));
            return updated;
        });
        clearSelection();
    };

    const executeBulkApiAction = async (buildRequest) => {
        const ids = Array.from(selectedNoteIds);
        if (ids.length === 0) return;
        await Promise.allSettled(ids.map((id) => buildRequest(id)));
        clearSelection();
        await fetchNotes();
    };

    const handleBulkCompleteSelected = async () => {
        await executeBulkApiAction((id) => apiClient(`${BACKEND_URL}/api/postits/${id}/complete/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        }));
    };

    const handleBulkDeleteSelected = async () => {
        await executeBulkApiAction((id) => apiClient(`${BACKEND_URL}/api/postits/${id}/delete_note/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        }));
    };

    const handleBulkUnarchiveSelected = async () => {
        await executeBulkApiAction((id) => apiClient(`${BACKEND_URL}/api/postits/${id}/unarchive/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        }));
    };

    const handleBulkPermanentDeleteSelected = async () => {
        await executeBulkApiAction((id) => apiClient(`${BACKEND_URL}/api/postits/${id}/permanent_delete/`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        }));
    };

    const handleBulkShareSelected = async () => {
        const ids = Array.from(selectedNoteIds);
        if (ids.length === 0 || selectedShareUserIds.length === 0) return;

        await Promise.allSettled(
            ids.map((id) => apiClient(`${BACKEND_URL}/api/postits/${id}/pass_note/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ target_user_ids: selectedShareUserIds })
            }))
        );

        setShareAnchor(null);
        setSelectedShareUserIds([]);
        clearSelection();
        await fetchNotes();
    };

    const getFilteredNotes = () => {
        let filtered = [...notes];

        if (!showHidden) {
            filtered = filtered.filter((note) => !hiddenNoteIds.has(note.id));
        }

        if (selectedUserIds.size > 0) {
            filtered = filtered.filter((note) => selectedUserIds.has(note.created_by));
        }

        return filtered;
    };

    const handleCreate = async () => {
        if (!isOpen) {
            skipNextAutoFetchRef.current = true;
            setIsOpen(true);
        }

        const nextPosition = getNextNotePosition();

        try {
            const res = await apiClient(`${BACKEND_URL}/api/postits/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include",
                body: JSON.stringify({
                    content: '',
                    x_position: nextPosition.x,
                    y_position: nextPosition.y
                })
            });
            if (res.ok) {
                const createdNote = await res.json();
                setNotes(createdNote ? [createdNote] : []);
            }
        } catch (err) {
            console.error("Create failed", err);
        }
    };

    const handleUpdate = async (id, data) => {
        setNotes(prev => prev.map(n => n.id === id ? { ...n, ...data } : n));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include",
                body: JSON.stringify(data)
            });
        } catch (err) {
            fetchNotes();
        }
    };

    const handleMove = async (id, x, y) => {
        setNotes(prev => prev.map(n => n.id === id ? { ...n, x_position: x, y_position: y } : n));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/move/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include",
                body: JSON.stringify({ x, y })
            });
        } catch (err) {
            console.error("Move failed", err);
        }
    };

    const handleComplete = async (id) => {
        setNotes(prev => prev.filter(n => n.id !== id));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/complete/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include"
            });
        } catch (err) {
            fetchNotes();
        }
    };

    const handleDelete = async (id) => {
        setNotes(prev => prev.filter(n => n.id !== id));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/delete_note/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include"
            });
        } catch (err) {
            fetchNotes();
        }
    };

    const handleUnarchive = async (id) => {
        setNotes(prev => prev.filter(n => n.id !== id));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/unarchive/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include"
            });
        } catch (err) {
            fetchNotes();
        }
    };

    const handlePermanentDelete = async (id) => {
        setNotes(prev => prev.filter(n => n.id !== id));

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/permanent_delete/`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include"
            });
        } catch (err) {
            fetchNotes();
        }
    };

    const handlePass = async (id, userIds) => {

        const targetUserIds = Array.isArray(userIds) ? userIds : [userIds];

        try {
            await apiClient(`${BACKEND_URL}/api/postits/${id}/pass_note/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: "include",
                body: JSON.stringify({ target_user_ids: targetUserIds })
            });
            fetchNotes();
        } catch (err) {
            fetchNotes();
            alert("Failed to share note");
        }
    };

    const visibleNotes = getFilteredNotes();
    const selectedCount = selectedNoteIds.size;
    const teammatesForShare = memberOptions.filter((user) => user.id !== currentUserId);

    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1280;
    const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 800;
    const isMobile = viewportWidth <= 640;
    const pageHeight = typeof document !== 'undefined' ? document.documentElement.scrollHeight : viewportHeight;
    const estimatedChipsWidth = 980;
    const desktopMaxFilterWidth = Math.max(700, viewportWidth - 48);
    const desktopFilterWidth = Math.min(desktopMaxFilterWidth, Math.max(680, estimatedChipsWidth + 24));
    const filterWidth = isMobile ? viewportWidth - 16 : desktopFilterWidth;
    const filterLeft = isMobile ? 8 : Math.max(16, Math.floor((viewportWidth - desktopFilterWidth) / 2));
    const furthestY = visibleNotes.reduce((max, note) => Math.max(max, (note.y_position || 0) + NOTE_HEIGHT), pageHeight);
    const canvasHeight = Math.max(pageHeight, viewportHeight * 1.3, furthestY + 220);

    return (
        <>
            {isOpen && (
                <Draggable nodeRef={filterNodeRef}>
                    <Box
                        ref={filterNodeRef}
                        className="filter-drag-handle"
                        sx={{
                            position: 'fixed',
                            top: isMobile ? 10 : 16,
                            left: filterLeft,
                            zIndex: 1410,
                            bgcolor: 'rgba(235,236,240,0.96)',
                            borderRadius: 4,
                            px: isMobile ? 0.65 : 1,
                            py: isMobile ? 0.6 : 0.9,
                            boxShadow: 6,
                            border: '2px solid rgba(31,41,55,0.72)',
                            width: filterWidth,
                            cursor: 'move',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'stretch',
                            gap: isMobile ? 0.65 : 0.9
                        }}
                    >
                        <Box
                            sx={{
                                display: 'flex',
                                gap: 1,
                                overflow: 'hidden',
                                whiteSpace: 'normal',
                                flexWrap: 'wrap',
                                pb: 0.25,
                                maxWidth: '100%'
                            }}
                        >
                            {[
                                { value: 'active', label: 'Active Notes' },
                                { value: 'archived', label: 'Archived' },
                                { value: 'deleted', label: 'Deleted Notes' }
                            ].map((option) => {
                                const selected = noteView === option.value;
                                return (
                                    <Chip
                                        key={option.value}
                                        label={option.label}
                                        className="member-chip"
                                        clickable
                                        size={isMobile ? 'medium' : 'small'}
                                        color="default"
                                        variant="outlined"
                                        onClick={() => setNoteView(option.value)}
                                        sx={{
                                            borderRadius: 3,
                                            borderWidth: '2px',
                                            borderColor: selected ? 'rgba(30,64,175,0.95)' : 'rgba(31,41,55,0.6)',
                                            bgcolor: selected ? 'rgba(191,219,254,0.95)' : 'rgba(255,255,255,0.92)',
                                            color: '#111827',
                                            fontWeight: 600,
                                            px: isMobile ? 0.25 : 0.8,
                                            minHeight: isMobile ? 30 : undefined,
                                            '& .MuiChip-label': {
                                                px: isMobile ? 0.8 : 1.2,
                                                fontSize: isMobile ? 12 : 13,
                                                maxWidth: isMobile ? 140 : 'none',
                                                overflow: isMobile ? 'hidden' : 'visible',
                                                textOverflow: isMobile ? 'ellipsis' : 'clip'
                                            }
                                        }}
                                    />
                                );
                            })}

                            <Chip
                                label={selectMode ? `Selected (${selectedCount})` : 'Select Notes'}
                                className="member-chip"
                                clickable
                                size={isMobile ? 'medium' : 'small'}
                                color={selectMode ? 'primary' : 'default'}
                                variant={selectMode ? 'filled' : 'outlined'}
                                onClick={handleToggleSelectMode}
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    fontWeight: 600,
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />

                            <Chip
                                label={selectedUserIds.size > 0 ? `Users (${selectedUserIds.size})` : 'Filter Users'}
                                className="member-chip"
                                clickable
                                size={isMobile ? 'medium' : 'small'}
                                color={selectedUserIds.size > 0 ? 'primary' : 'default'}
                                variant={selectedUserIds.size > 0 ? 'filled' : 'outlined'}
                                onClick={(e) => setUserFilterAnchor(e.currentTarget)}
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    fontWeight: 600,
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />

                            <Chip
                                label={sortOrder === 'newest' ? 'Newest First' : 'Oldest First'}
                                className="member-chip"
                                clickable
                                size={isMobile ? 'medium' : 'small'}
                                color="default"
                                variant="outlined"
                                onClick={(e) => setSortAnchor(e.currentTarget)}
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    fontWeight: 600,
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />

                            <Chip
                                label={showHidden ? 'Showing Hidden' : `Hidden (${hiddenNoteIds.size})`}
                                className="member-chip"
                                clickable
                                size={isMobile ? 'medium' : 'small'}
                                color={showHidden ? 'primary' : 'default'}
                                variant={showHidden ? 'filled' : 'outlined'}
                                onClick={() => setShowHidden((prev) => !prev)}
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    fontWeight: 600,
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />

                            <Chip
                                label={`${selectedCount} selected / ${visibleNotes.length} visible`}
                                className="member-chip"
                                size={isMobile ? 'medium' : 'small'}
                                color="default"
                                variant="outlined"
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    bgcolor: 'rgba(255,255,255,0.92)',
                                    color: '#374151',
                                    fontWeight: 600,
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />

                            <Chip
                                icon={<CloseIcon sx={{ fontSize: 16 }} />}
                                className="member-chip"
                                clickable
                                size={isMobile ? 'medium' : 'small'}
                                color="default"
                                variant="outlined"
                                onClick={() => setIsOpen(false)}
                                sx={{
                                    borderRadius: 3,
                                    borderWidth: '2px',
                                    borderColor: 'rgba(220,38,38,0.6)',
                                    bgcolor: 'rgba(254,226,226,0.9)',
                                    color: '#991b1b',
                                    fontWeight: 600,
                                    '&:hover': {
                                        bgcolor: 'rgba(254,202,202,1)',
                                        borderColor: 'rgba(220,38,38,0.9)',
                                    },
                                    '& .MuiChip-label': {
                                        px: isMobile ? 0.8 : 1.2,
                                        fontSize: isMobile ? 12 : 13
                                    }
                                }}
                            />
                        </Box>

                        {selectMode && (
                            <Box
                                sx={{
                                    display: 'flex',
                                    gap: 1,
                                    overflow: 'hidden',
                                    whiteSpace: 'normal',
                                    flexWrap: 'wrap',
                                    pb: 0.1,
                                    maxWidth: '100%'
                                }}
                            >
                                <Chip
                                    label="Select All"
                                    clickable
                                    size={isMobile ? 'medium' : 'small'}
                                    onClick={handleSelectAllVisible}
                                />
                                <Chip
                                    label="Clear"
                                    clickable
                                    size={isMobile ? 'medium' : 'small'}
                                    onClick={clearSelection}
                                />

                                {noteView === 'active' && (
                                    <>
                                        <Chip
                                            label="Mark Complete"
                                            clickable
                                            size={isMobile ? 'medium' : 'small'}
                                            color="success"
                                            disabled={selectedCount === 0}
                                            onClick={handleBulkCompleteSelected}
                                        />
                                        <Chip
                                            label="Delete"
                                            clickable
                                            size={isMobile ? 'medium' : 'small'}
                                            color="error"
                                            disabled={selectedCount === 0}
                                            onClick={handleBulkDeleteSelected}
                                        />
                                        <Chip
                                            label="Hide"
                                            clickable
                                            size={isMobile ? 'medium' : 'small'}
                                            disabled={selectedCount === 0}
                                            onClick={handleBulkHideSelected}
                                        />
                                        <Chip
                                            label="Unhide"
                                            clickable
                                            size={isMobile ? 'medium' : 'small'}
                                            disabled={selectedCount === 0}
                                            onClick={handleBulkUnhideSelected}
                                        />
                                        <Chip
                                            label="Share with Team"
                                            clickable
                                            size={isMobile ? 'medium' : 'small'}
                                            color="primary"
                                            disabled={selectedCount === 0}
                                            onClick={(e) => {
                                                if (selectedCount > 0) {
                                                    setShareAnchor(e.currentTarget);
                                                }
                                            }}
                                        />
                                    </>
                                )}

                                {noteView === 'archived' && (
                                    <Chip
                                        label="Unarchive"
                                        clickable
                                        size={isMobile ? 'medium' : 'small'}
                                        color="warning"
                                        disabled={selectedCount === 0}
                                        onClick={handleBulkUnarchiveSelected}
                                    />
                                )}

                                {noteView === 'deleted' && (
                                    <Chip
                                        label="Permanent Delete"
                                        clickable
                                        size={isMobile ? 'medium' : 'small'}
                                        color="error"
                                        disabled={selectedCount === 0}
                                        onClick={handleBulkPermanentDeleteSelected}
                                    />
                                )}
                            </Box>
                        )}
                    </Box>
                </Draggable>
            )}

            {/* USER FILTER MENU */}
            <Menu
                anchorEl={userFilterAnchor}
                open={Boolean(userFilterAnchor)}
                onClose={() => setUserFilterAnchor(null)}
                PaperProps={{
                    sx: {
                        maxHeight: 300,
                        width: 280,
                        boxShadow: 6,
                        borderRadius: 2
                    }
                }}
            >
                <MenuItem disabled>
                    <strong>Filter by User</strong>
                </MenuItem>
                {memberOptions.map(user => (
                    <MenuItem
                        key={user.id}
                        onClick={() => toggleUserFilter(user.id)}
                        sx={{
                            py: 1,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1
                        }}
                    >
                        <Checkbox
                            checked={selectedUserIds.has(user.id)}
                            size="small"
                        />
                        <span>{user.full_name || user.username}</span>
                    </MenuItem>
                ))}
                {memberOptions.length === 0 && (
                    <MenuItem disabled>No users found</MenuItem>
                )}
                {selectedUserIds.size > 0 && (
                    <>
                        <MenuItem divider />
                        <MenuItem
                            onClick={() => setSelectedUserIds(new Set())}
                            sx={{ py: 1, color: 'error.main', textAlign: 'center' }}
                        >
                            Clear Filters
                        </MenuItem>
                    </>
                )}
            </Menu>

            <Menu
                anchorEl={sortAnchor}
                open={Boolean(sortAnchor)}
                onClose={() => setSortAnchor(null)}
                PaperProps={{
                    sx: {
                        width: 220,
                        boxShadow: 6,
                        borderRadius: 2
                    }
                }}
            >
                <MenuItem
                    onClick={() => {
                        setSortOrder('newest');
                        setSortAnchor(null);
                    }}
                >
                    <Checkbox checked={sortOrder === 'newest'} size="small" />
                    Newest First
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        setSortOrder('oldest');
                        setSortAnchor(null);
                    }}
                >
                    <Checkbox checked={sortOrder === 'oldest'} size="small" />
                    Oldest First
                </MenuItem>
            </Menu>

            <Menu
                anchorEl={shareAnchor}
                open={Boolean(shareAnchor)}
                onClose={() => {
                    setShareAnchor(null);
                    setSelectedShareUserIds([]);
                }}
                PaperProps={{ sx: { minWidth: 260, maxHeight: 360 } }}
            >
                <MenuItem disabled>
                    Share selected notes ({selectedCount})
                </MenuItem>
                {teammatesForShare.map((user) => (
                    <MenuItem
                        key={user.id}
                        onClick={() => toggleShareTargetUser(user.id)}
                    >
                        <Checkbox
                            checked={selectedShareUserIds.includes(user.id)}
                            size="small"
                        />
                        {user.full_name || user.username || user.email}
                    </MenuItem>
                ))}
                <MenuItem
                    onClick={() => toggleShareTargetUser('everyone')}
                >
                    <Checkbox
                        checked={selectedShareUserIds.includes('everyone')}
                        size="small"
                    />
                    Everyone
                </MenuItem>
                <MenuItem divider />
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, p: 1 }}>
                    <Button
                        size="small"
                        onClick={() => {
                            setShareAnchor(null);
                            setSelectedShareUserIds([]);
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        size="small"
                        variant="contained"
                        disabled={selectedShareUserIds.length === 0 || selectedCount === 0}
                        onClick={handleBulkShareSelected}
                    >
                        Share
                    </Button>
                </Box>
            </Menu>

            {/* OVERLAY FOR NOTES */}
            <Box
                sx={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: isOpen ? 'auto' : 'none',
                    zIndex: 1200,
                    display: isOpen ? 'block' : 'none',
                    overflowY: 'auto',
                    overflowX: 'hidden'
                }}
            >
                <Box
                    className="postit-canvas"
                    sx={{
                        position: 'relative',
                        width: '100%',
                        height: canvasHeight,
                        minWidth: '100%',
                        minHeight: '100%'
                    }}
                >
                    {visibleNotes.map((note) => {
                        const isCreator = note.created_by === currentUserId;
                        const colorizedNote = {
                            ...note,
                            color: isCreator ? '#ffeb3b' : '#ffcc80'
                        };

                        return (
                            <StickyNote
                                key={note.id}
                                note={colorizedNote}
                                noteView={noteView}
                                users={memberOptions}
                                currentUserId={currentUserId}
                                onUpdate={handleUpdate}
                                onMove={handleMove}
                                onComplete={handleComplete}
                                onDelete={handleDelete}
                                onUnarchive={handleUnarchive}
                                onPermanentDelete={handlePermanentDelete}
                                onPass={handlePass}
                                selectMode={selectMode}
                                isSelected={selectedNoteIds.has(note.id)}
                                onToggleSelect={() => toggleNoteSelection(note.id)}
                            />
                        );
                    })}
                </Box>
            </Box>

            {/* QUICK ACCESS dropdown panel */}
            {quickAccessOpen && (
                <>
                    {/* Backdrop */}
                    <Box
                        onClick={() => setQuickAccessOpen(false)}
                        sx={{ position: 'fixed', inset: 0, zIndex: 1499 }}
                    />
                    <Box
                        sx={{
                            position: 'fixed',
                            top: anchorEl ? anchorEl.getBoundingClientRect().bottom + 4 : 56,
                            left: anchorEl ? anchorEl.getBoundingClientRect().left : 110,
                            zIndex: 1500,
                            bgcolor: '#fff',
                            borderRadius: 2,
                            boxShadow: '0 8px 30px rgba(0,0,0,0.14)',
                            border: '1px solid #e2e8f0',
                            minWidth: 210,
                            py: 1,
                            overflow: 'hidden',
                        }}
                    >
                        {[
                            { label: 'My Notes', icon: <MenuBookIcon sx={{ fontSize: 17 }} />, action: () => { setMyNotesOpen(true); setQuickAccessOpen(false); } },
                            { label: 'My Chat', icon: <GroupIcon sx={{ fontSize: 17 }} />, action: () => { setChatOpen(true); setQuickAccessOpen(false); } },
                            { label: 'Ask Analyst', icon: <SmartToyIcon sx={{ fontSize: 17 }} />, action: () => { setAnalystOpen(true); setQuickAccessOpen(false); } },

                            { label: isOpen ? 'Hide Sticky Notes' : 'Show Sticky Notes', icon: <StickyNoteIcon sx={{ fontSize: 17 }} />, action: () => { if (!isOpen) fetchNotes(); setIsOpen(p => !p); setQuickAccessOpen(false); } },
                            { label: 'New Sticky Note', icon: <NoteAddIcon sx={{ fontSize: 17 }} />, action: () => { handleCreate(); setQuickAccessOpen(false); } },
                        ].map((item, i) =>
                            item === null ? (
                                <Box key={i} sx={{ my: 0.75, mx: 2, borderTop: '1px solid #e2e8f0' }} />
                            ) : (
                                <Box
                                    key={i}
                                    onClick={item.action}
                                    sx={{
                                        display: 'flex', alignItems: 'center', gap: 1.5,
                                        px: 2, py: 1,
                                        cursor: 'pointer',
                                        color: '#1e293b',
                                        fontSize: '0.875rem',
                                        fontWeight: 500,
                                        '&:hover': { bgcolor: '#f8fafc' },
                                        transition: 'background 0.1s',
                                    }}
                                >
                                    <Box sx={{ color: '#475569', display: 'flex' }}>{item.icon}</Box>
                                    {item.label}
                                </Box>
                            )
                        )}
                    </Box>
                </>
            )}

            <TeamChat
                isOpen={chatOpen}
                onClose={() => setChatOpen(false)}
            />

            <AnalyticsChatWidget
                isOpen={analystOpen}
                onClose={() => setAnalystOpen(false)}
            />

            <MyNotesPanel
                open={myNotesOpen}
                onClose={() => setMyNotesOpen(false)}
            />
        </>
    );
}