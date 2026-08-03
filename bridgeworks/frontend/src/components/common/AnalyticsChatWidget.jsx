import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box, IconButton, Paper, Typography, Fab, Tooltip,
    TextField, InputAdornment, Avatar, CircularProgress,
    Fade, Chip
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import ChatBubbleIcon from '@mui/icons-material/ChatBubble';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

// ─── Default welcome message ───
const WELCOME_MESSAGE = {
    text: "Hi! I'm **Thorfinn**, your BridgeWorks Data Analyst. Ask me anything about your orders, revenue, fulfillment status, or tickets!",
    sender: "Thorfinn",
    direction: "incoming"
};

// ─── Simple Markdown-ish renderer ───
// Handles **bold**, *italic*, `code`, line breaks, and bullet points
const FormattedMessage = ({ text }) => {
    if (!text) return null;

    // Split by lines first, then process inline formatting
    const lines = text.split('\n');
    
    return (
        <Box component="span" sx={{ display: 'block' }}>
            {lines.map((line, lineIdx) => {
                const trimmed = line.trim();
                
                // Handle bullet points
                const isBullet = /^[-•*]\s/.test(trimmed);
                const isNumbered = /^\d+[.)]\s/.test(trimmed);
                const content = isBullet ? trimmed.slice(2) : isNumbered ? trimmed.replace(/^\d+[.)]\s/, '') : trimmed;

                // Process inline formatting
                const processInline = (str) => {
                    const parts = [];
                    let remaining = str;
                    let key = 0;

                    while (remaining.length > 0) {
                        // Bold
                        const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
                        // Inline code
                        const codeMatch = remaining.match(/`([^`]+)`/);

                        let firstMatch = null;
                        let firstIdx = remaining.length;

                        if (boldMatch && boldMatch.index < firstIdx) {
                            firstMatch = { type: 'bold', match: boldMatch };
                            firstIdx = boldMatch.index;
                        }
                        if (codeMatch && codeMatch.index < firstIdx) {
                            firstMatch = { type: 'code', match: codeMatch };
                            firstIdx = codeMatch.index;
                        }

                        if (!firstMatch) {
                            parts.push(<span key={key++}>{remaining}</span>);
                            break;
                        }

                        // Text before match
                        if (firstIdx > 0) {
                            parts.push(<span key={key++}>{remaining.slice(0, firstIdx)}</span>);
                        }

                        if (firstMatch.type === 'bold') {
                            parts.push(<strong key={key++}>{firstMatch.match[1]}</strong>);
                            remaining = remaining.slice(firstIdx + firstMatch.match[0].length);
                        } else if (firstMatch.type === 'code') {
                            parts.push(
                                <Box key={key++} component="code" sx={{
                                    bgcolor: 'action.hover',
                                    px: 0.5,
                                    py: 0.25,
                                    borderRadius: 0.5,
                                    fontFamily: 'monospace',
                                    fontSize: '0.8em'
                                }}>
                                    {firstMatch.match[1]}
                                </Box>
                            );
                            remaining = remaining.slice(firstIdx + firstMatch.match[0].length);
                        }
                    }
                    return parts;
                };

                if (trimmed === '') {
                    return <Box key={lineIdx} sx={{ height: 8 }} />;
                }

                if (isBullet || isNumbered) {
                    return (
                        <Box key={lineIdx} sx={{ display: 'flex', gap: 0.75, pl: 0.5, py: 0.15 }}>
                            <Typography variant="body2" component="span" sx={{ fontSize: '0.85rem', lineHeight: 1.6, flexShrink: 0 }}>
                                {isBullet ? '•' : trimmed.match(/^\d+[.)]/)[0]}
                            </Typography>
                            <Typography variant="body2" component="span" sx={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
                                {processInline(content)}
                            </Typography>
                        </Box>
                    );
                }

                return (
                    <Typography key={lineIdx} variant="body2" component="div" sx={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
                        {processInline(trimmed)}
                    </Typography>
                );
            })}
        </Box>
    );
};


const AnalyticsChatWidget = ({ isOpen: controlledIsOpen, onClose } = {}) => {
    const navigate = useNavigate();
    const [internalOpen, setInternalOpen] = useState(false);
    const isControlled = controlledIsOpen !== undefined;
    const isOpen = isControlled ? controlledIsOpen : internalOpen;

    const [messages, setMessages] = useState([WELCOME_MESSAGE]);
    const [inputValue, setInputValue] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [isLoadingSessions, setIsLoadingSessions] = useState(false);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);

    // ─── Fetch all sessions for sidebar ───
    const fetchSessions = useCallback(async () => {
        setIsLoadingSessions(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/analytics/chat/sessions/`);
            if (response.ok) {
                const data = await response.json();
                setSessions(Array.isArray(data) ? data : []);
            } else {
                console.error("[Thorfinn] fetchSessions failed:", response.status, response.statusText);
                try {
                    const errBody = await response.text();
                    console.error("[Thorfinn] Error body:", errBody);
                } catch {}
            }
        } catch (error) {
            console.error("[Thorfinn] fetchSessions network error:", error);
        } finally {
            setIsLoadingSessions(false);
        }
    }, []);

    // ─── Select a session and load its messages ───
    const handleSelectSession = useCallback(async (sessionId) => {
        if (sessionId === currentSessionId) return;
        setCurrentSessionId(sessionId);
        setIsLoadingMessages(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/analytics/chat/sessions/${sessionId}/messages/`);
            if (response.ok) {
                const data = await response.json();
                const formatted = (Array.isArray(data) ? data : []).map(m => ({
                    text: m.content,
                    sender: m.role === 'user' ? 'user' : 'Thorfinn',
                    direction: m.role === 'user' ? 'outgoing' : 'incoming',
                    actions: m.actions
                }));
                setMessages(formatted.length > 0 ? formatted : [WELCOME_MESSAGE]);
            } else {
                console.error("[Thorfinn] fetchMessages failed:", response.status);
            }
        } catch (error) {
            console.error("[Thorfinn] fetchMessages error:", error);
        } finally {
            setIsLoadingMessages(false);
        }
    }, [currentSessionId]);

    // ─── Delete a session ───
    const handleDeleteSession = useCallback(async (e, sessionId) => {
        e.stopPropagation();
        if (!window.confirm("Delete this conversation?")) return;
        try {
            const response = await apiClient(`${BACKEND_URL}/api/analytics/chat/sessions/${sessionId}/`, {
                method: 'DELETE'
            });
            if (response.ok) {
                if (currentSessionId === sessionId) {
                    setCurrentSessionId(null);
                    setMessages([WELCOME_MESSAGE]);
                }
                fetchSessions();
            }
        } catch (error) {
            console.error("[Thorfinn] deleteSession error:", error);
        }
    }, [currentSessionId, fetchSessions]);

    // ─── Start a new chat ───
    const handleNewChat = useCallback(() => {
        setCurrentSessionId(null);
        setMessages([WELCOME_MESSAGE]);
        // Focus the input
        setTimeout(() => inputRef.current?.focus(), 100);
    }, []);

    // ─── Fetch sessions when widget opens ───
    useEffect(() => {
        if (isOpen) {
            fetchSessions();
        }
    }, [isOpen, fetchSessions]);

    // ─── Auto-scroll to bottom ───
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isTyping]);

    // ─── Send a message ───
    const handleSend = async () => {
        const text = inputValue.trim();
        if (!text || isTyping) return;

        // Build conversation history from existing messages (skip welcome)
        const history = messages
            .filter(m => m !== WELCOME_MESSAGE)
            .map(m => ({
                role: m.sender === 'user' ? 'user' : 'model',
                content: m.text
            }));

        setInputValue('');
        setMessages(prev => [...prev, { text, sender: 'user', direction: 'outgoing' }]);
        setIsTyping(true);

        try {
            const response = await apiClient(`${BACKEND_URL}/api/analytics/chat/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: text,
                    history,
                    session_id: currentSessionId
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returned ${response.status}`);
            }

            const data = await response.json();

            // Auto-create session tracking
            if (!currentSessionId && data.session_id) {
                setCurrentSessionId(data.session_id);
            }
            // Always refresh sessions list to update timestamps/titles
            fetchSessions();

            // Add bot reply
            setMessages(prev => [...prev, {
                text: data.answer || "I have processed your request.",
                sender: "Thorfinn",
                direction: "incoming"
            }]);

            // Execute interactive actions from the agent
            if (data.actions && Array.isArray(data.actions)) {
                data.actions.forEach(action => {
                    if (action.type === 'navigate' && action.route) {
                        navigate(action.route);
                    }
                });
            }
        } catch (error) {
            console.error("[Thorfinn] Chat Error:", error);
            setMessages(prev => [...prev, {
                text: "I'm having trouble processing your request right now. Please try again.",
                sender: 'Thorfinn',
                direction: 'incoming'
            }]);
        } finally {
            setIsTyping(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleClose = () => {
        if (isControlled) {
            onClose?.();
        } else {
            setInternalOpen(false);
        }
    };

    return (
        <>
            {/* ─── Floating Action Button ─── */}
            {!isControlled && !isOpen && (
                <Tooltip title="Ask Thorfinn" placement="left">
                    <Fab
                        aria-label="chat"
                        onClick={() => setInternalOpen(true)}
                        sx={{
                            position: 'fixed',
                            bottom: 24,
                            right: 24,
                            zIndex: 9999,
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            color: '#fff',
                            boxShadow: '0 8px 32px rgba(102, 126, 234, 0.4)',
                            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                            '&:hover': {
                                transform: 'scale(1.1)',
                                boxShadow: '0 12px 40px rgba(102, 126, 234, 0.5)',
                                background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
                            },
                        }}
                    >
                        <ChatBubbleIcon />
                    </Fab>
                </Tooltip>
            )}

            {/* ─── Chat Window ─── */}
            {isOpen && (
                <Fade in={isOpen} timeout={250}>
                    <Paper
                        elevation={12}
                        sx={{
                            position: 'fixed',
                            bottom: 24,
                            right: 24,
                            width: { xs: '95vw', sm: 850 },
                            maxWidth: 900,
                            height: { xs: '80vh', sm: 600 },
                            zIndex: 9999,
                            display: 'flex',
                            flexDirection: 'row',
                            overflow: 'hidden',
                            borderRadius: 3,
                            boxShadow: '0px 12px 48px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(255,255,255,0.05)',
                            border: '1px solid',
                            borderColor: 'divider',
                        }}
                    >
                        {/* ─── Left Sidebar ─── */}
                        <Box
                            sx={{
                                width: 260,
                                borderRight: '1px solid',
                                borderColor: 'divider',
                                display: { xs: 'none', sm: 'flex' },
                                flexDirection: 'column',
                                bgcolor: (theme) => theme.palette.mode === 'dark'
                                    ? 'rgba(18,18,24,0.95)'
                                    : 'rgba(248,249,252,1)',
                                flexShrink: 0,
                            }}
                        >
                            {/* Sidebar Header */}
                            <Box
                                sx={{
                                    px: 2,
                                    py: 1.75,
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    borderBottom: '1px solid',
                                    borderColor: 'divider',
                                    flexShrink: 0,
                                }}
                            >
                                <Typography variant="subtitle2" fontWeight={700} color="text.primary" letterSpacing={0.3}>
                                    Conversations
                                </Typography>
                                <Tooltip title="New Chat" arrow>
                                    <IconButton
                                        size="small"
                                        onClick={handleNewChat}
                                        sx={{
                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                            color: '#fff',
                                            width: 26,
                                            height: 26,
                                            transition: 'all 0.2s ease',
                                            '&:hover': {
                                                transform: 'scale(1.1)',
                                                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                                            },
                                        }}
                                    >
                                        <AddIcon sx={{ fontSize: 15 }} />
                                    </IconButton>
                                </Tooltip>
                            </Box>

                            {/* Sessions List */}
                            <Box
                                sx={{
                                    flexGrow: 1,
                                    overflowY: 'auto',
                                    px: 0.75,
                                    py: 1,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 0.25,
                                    '&::-webkit-scrollbar': { width: 4 },
                                    '&::-webkit-scrollbar-thumb': {
                                        bgcolor: 'divider',
                                        borderRadius: 2,
                                    },
                                }}
                            >
                                {isLoadingSessions ? (
                                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
                                        <CircularProgress size={22} thickness={3} />
                                    </Box>
                                ) : sessions.length === 0 ? (
                                    <Box sx={{ px: 2, py: 5, textAlign: 'center' }}>
                                        <ChatOutlinedIcon sx={{ fontSize: 36, color: 'text.disabled', mb: 1 }} />
                                        <Typography variant="body2" color="text.secondary" fontSize="0.8rem">
                                            No conversations yet
                                        </Typography>
                                        <Typography variant="caption" color="text.disabled" fontSize="0.7rem">
                                            Start chatting to create one
                                        </Typography>
                                    </Box>
                                ) : (
                                    sessions.map((session) => {
                                        const isActive = session.id === currentSessionId;
                                        return (
                                            <Box
                                                key={session.id}
                                                onClick={() => handleSelectSession(session.id)}
                                                sx={{
                                                    px: 1.5,
                                                    py: 1,
                                                    borderRadius: 1.5,
                                                    cursor: 'pointer',
                                                    transition: 'all 0.15s ease',
                                                    bgcolor: isActive
                                                        ? (theme) => theme.palette.mode === 'dark'
                                                            ? 'rgba(102, 126, 234, 0.15)'
                                                            : 'rgba(102, 126, 234, 0.08)'
                                                        : 'transparent',
                                                    borderLeft: '3px solid',
                                                    borderLeftColor: isActive ? '#667eea' : 'transparent',
                                                    '&:hover': {
                                                        bgcolor: isActive
                                                            ? undefined
                                                            : 'action.hover',
                                                        '& .session-delete-btn': { opacity: 1 },
                                                    },
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'space-between',
                                                    gap: 0.75,
                                                }}
                                            >
                                                <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                                                    <Typography
                                                        variant="body2"
                                                        fontWeight={isActive ? 600 : 400}
                                                        color={isActive ? '#667eea' : 'text.primary'}
                                                        sx={{
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                            fontSize: '0.8rem',
                                                        }}
                                                    >
                                                        {session.title || "Untitled Chat"}
                                                    </Typography>
                                                    <Typography variant="caption" color="text.disabled" fontSize="0.65rem">
                                                        {new Date(session.updated_at).toLocaleDateString([], {
                                                            month: 'short',
                                                            day: 'numeric',
                                                            hour: '2-digit',
                                                            minute: '2-digit',
                                                        })}
                                                    </Typography>
                                                </Box>
                                                <IconButton
                                                    className="session-delete-btn"
                                                    size="small"
                                                    onClick={(e) => handleDeleteSession(e, session.id)}
                                                    sx={{
                                                        opacity: 0,
                                                        transition: 'opacity 0.2s ease',
                                                        color: 'text.disabled',
                                                        p: 0.4,
                                                        '&:hover': { color: 'error.main' },
                                                    }}
                                                >
                                                    <DeleteOutlineIcon sx={{ fontSize: 15 }} />
                                                </IconButton>
                                            </Box>
                                        );
                                    })
                                )}
                            </Box>
                        </Box>

                        {/* ─── Right Chat Area ─── */}
                        <Box
                            sx={{
                                flexGrow: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                overflow: 'hidden',
                                minWidth: 0,
                            }}
                        >
                            {/* Chat Header */}
                            <Box sx={{
                                px: 2, py: 1.25,
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                color: '#fff',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                flexShrink: 0,
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                                    <Avatar sx={{
                                        width: 30,
                                        height: 30,
                                        bgcolor: 'rgba(255,255,255,0.2)',
                                        backdropFilter: 'blur(10px)',
                                    }}>
                                        <SmartToyIcon sx={{ fontSize: 17 }} />
                                    </Avatar>
                                    <Box>
                                        <Typography variant="subtitle2" fontWeight={700} lineHeight={1.2} letterSpacing={0.2}>
                                            Thorfinn
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                            <Box sx={{
                                                width: 6,
                                                height: 6,
                                                borderRadius: '50%',
                                                bgcolor: '#4ade80',
                                                boxShadow: '0 0 6px #4ade80',
                                            }} />
                                            <Typography variant="caption" sx={{ opacity: 0.85, fontSize: '0.65rem' }}>
                                                Online
                                            </Typography>
                                        </Box>
                                    </Box>
                                </Box>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                                    <Tooltip title="New Chat" arrow>
                                        <IconButton size="small" onClick={handleNewChat} sx={{
                                            color: 'rgba(255,255,255,0.8)',
                                            '&:hover': { color: '#fff', bgcolor: 'rgba(255,255,255,0.1)' },
                                        }}>
                                            <RefreshIcon sx={{ fontSize: 18 }} />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Close" arrow>
                                        <IconButton size="small" onClick={handleClose} sx={{
                                            color: 'rgba(255,255,255,0.8)',
                                            '&:hover': { color: '#fff', bgcolor: 'rgba(255,255,255,0.1)' },
                                        }}>
                                            <CloseIcon sx={{ fontSize: 18 }} />
                                        </IconButton>
                                    </Tooltip>
                                </Box>
                            </Box>

                            {/* Messages Area */}
                            <Box sx={{
                                flexGrow: 1,
                                overflowY: 'auto',
                                px: 2,
                                py: 2,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 1.5,
                                bgcolor: 'background.default',
                                '&::-webkit-scrollbar': { width: 5 },
                                '&::-webkit-scrollbar-thumb': {
                                    bgcolor: 'divider',
                                    borderRadius: 2,
                                },
                            }}>
                                {isLoadingMessages ? (
                                    <Box sx={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                        height: '100%',
                                        gap: 1.5
                                    }}>
                                        <CircularProgress size={28} thickness={3} sx={{ color: '#667eea' }} />
                                        <Typography variant="body2" color="text.secondary" fontSize="0.8rem">
                                            Loading conversation...
                                        </Typography>
                                    </Box>
                                ) : (
                                    <>
                                        {messages.map((m, i) => {
                                            const isUser = m.sender === 'user';
                                            return (
                                                <Box
                                                    key={i}
                                                    sx={{
                                                        display: 'flex',
                                                        justifyContent: isUser ? 'flex-end' : 'flex-start',
                                                        alignItems: 'flex-end',
                                                        gap: 1,
                                                        animation: 'fadeSlideUp 0.25s ease-out',
                                                        '@keyframes fadeSlideUp': {
                                                            from: { opacity: 0, transform: 'translateY(8px)' },
                                                            to: { opacity: 1, transform: 'translateY(0)' },
                                                        },
                                                    }}
                                                >
                                                    {!isUser && (
                                                        <Avatar sx={{
                                                            width: 28,
                                                            height: 28,
                                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                            flexShrink: 0,
                                                        }}>
                                                            <SmartToyIcon sx={{ fontSize: 15 }} />
                                                        </Avatar>
                                                    )}
                                                    <Box
                                                        sx={{
                                                            maxWidth: '80%',
                                                            px: 1.75,
                                                            py: 1,
                                                            borderRadius: isUser
                                                                ? '16px 16px 4px 16px'
                                                                : '16px 16px 16px 4px',
                                                            bgcolor: isUser
                                                                ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                                                                : 'background.paper',
                                                            background: isUser
                                                                ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                                                                : undefined,
                                                            color: isUser ? '#fff' : 'text.primary',
                                                            boxShadow: isUser
                                                                ? '0 2px 12px rgba(102, 126, 234, 0.25)'
                                                                : '0 1px 4px rgba(0, 0, 0, 0.06)',
                                                            border: isUser ? 'none' : '1px solid',
                                                            borderColor: isUser ? 'transparent' : 'divider',
                                                        }}
                                                    >
                                                        <FormattedMessage text={m.text} />
                                                    </Box>
                                                    {isUser && (
                                                        <Avatar sx={{
                                                            width: 28,
                                                            height: 28,
                                                            bgcolor: 'grey.300',
                                                            flexShrink: 0,
                                                        }}>
                                                            <PersonIcon sx={{ fontSize: 15, color: 'grey.600' }} />
                                                        </Avatar>
                                                    )}
                                                </Box>
                                            );
                                        })}

                                        {/* Typing Indicator */}
                                        {isTyping && (
                                            <Box sx={{
                                                display: 'flex',
                                                alignItems: 'flex-end',
                                                gap: 1,
                                                animation: 'fadeSlideUp 0.25s ease-out',
                                                '@keyframes fadeSlideUp': {
                                                    from: { opacity: 0, transform: 'translateY(8px)' },
                                                    to: { opacity: 1, transform: 'translateY(0)' },
                                                },
                                            }}>
                                                <Avatar sx={{
                                                    width: 28,
                                                    height: 28,
                                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                    flexShrink: 0,
                                                }}>
                                                    <SmartToyIcon sx={{ fontSize: 15 }} />
                                                </Avatar>
                                                <Box sx={{
                                                    px: 2,
                                                    py: 1.25,
                                                    borderRadius: '16px 16px 16px 4px',
                                                    bgcolor: 'background.paper',
                                                    border: '1px solid',
                                                    borderColor: 'divider',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: 1,
                                                }}>
                                                    <Box sx={{ display: 'flex', gap: 0.4 }}>
                                                        {[0, 1, 2].map(i => (
                                                            <Box key={i} sx={{
                                                                width: 6, height: 6,
                                                                borderRadius: '50%',
                                                                bgcolor: '#667eea',
                                                                animation: `typingDot 1.4s ease-in-out infinite`,
                                                                animationDelay: `${i * 0.2}s`,
                                                                '@keyframes typingDot': {
                                                                    '0%, 60%, 100%': { opacity: 0.3, transform: 'scale(0.8)' },
                                                                    '30%': { opacity: 1, transform: 'scale(1)' },
                                                                },
                                                            }} />
                                                        ))}
                                                    </Box>
                                                    <Typography variant="caption" color="text.secondary" fontSize="0.7rem">
                                                        Analyzing...
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        )}
                                        <div ref={messagesEndRef} />
                                    </>
                                )}
                            </Box>

                            {/* Input Area */}
                            <Box sx={{
                                px: 2, py: 1.5,
                                borderTop: '1px solid',
                                borderColor: 'divider',
                                bgcolor: 'background.paper',
                                flexShrink: 0,
                            }}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    inputRef={inputRef}
                                    placeholder="Ask about orders, revenue, RTO..."
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    disabled={isTyping}
                                    multiline
                                    maxRows={3}
                                    InputProps={{
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton
                                                    size="small"
                                                    onClick={handleSend}
                                                    disabled={!inputValue.trim() || isTyping || isLoadingMessages}
                                                    sx={{
                                                        background: inputValue.trim() && !isTyping
                                                            ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                                                            : 'transparent',
                                                        color: inputValue.trim() && !isTyping ? '#fff' : 'text.disabled',
                                                        transition: 'all 0.2s ease',
                                                        width: 30,
                                                        height: 30,
                                                        '&:hover': {
                                                            background: inputValue.trim() && !isTyping
                                                                ? 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)'
                                                                : 'transparent',
                                                        },
                                                        '&.Mui-disabled': {
                                                            color: 'text.disabled',
                                                        }
                                                    }}
                                                >
                                                    <SendIcon sx={{ fontSize: 16 }} />
                                                </IconButton>
                                            </InputAdornment>
                                        )
                                    }}
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            borderRadius: 2.5,
                                            bgcolor: 'action.hover',
                                            '& fieldset': { borderColor: 'transparent' },
                                            '&:hover fieldset': { borderColor: 'divider' },
                                            '&.Mui-focused fieldset': { borderColor: '#667eea', borderWidth: 1.5 },
                                        },
                                    }}
                                />
                            </Box>
                        </Box>
                    </Paper>
                </Fade>
            )}
        </>
    );
};

export default AnalyticsChatWidget;
