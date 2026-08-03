import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  Avatar,
  List,
  ListItem,
  ListItemButton,
  ListItemAvatar,
  ListItemText,
  Divider,
  Chip,
  Badge,
  InputAdornment,
  Button,
} from '@mui/material';
import {
  Send as SendIcon,
  Close as CloseIcon,
  Search as SearchIcon,
  Tag as TagIcon,
  Person as PersonIcon,
} from '@mui/icons-material';

const MOCK_CHANNELS = [
  { id: 'c1', name: 'general', type: 'channel', unread: 2 },
  { id: 'c2', name: 'finance-compliance', type: 'channel', unread: 0 },
  { id: 'c3', name: 'engineering-sync', type: 'channel', unread: 1 },
];

const MOCK_USERS = [
  { id: 'u1', name: 'Jatin Choudhary', role: 'Head of Engineering', status: 'online' },
  { id: 'u2', name: 'Priya Nair', role: 'Lead Accountant', status: 'online' },
  { id: 'u3', name: 'Rahul Verma', role: 'HR Partner', status: 'offline' },
  { id: 'u4', name: 'Ananya Deshmukh', role: 'Senior Engineer', status: 'online' },
];

const MOCK_MESSAGES = {
  c1: [
    { id: 'm1', sender: 'Jatin Choudhary', text: 'Welcome to BridgeWorks Team Chat! Workspace channels are live.', time: '10:00 AM' },
    { id: 'm2', sender: 'Priya Nair', text: 'GST returns for July 2026 have been generated and reviewed.', time: '10:15 AM' },
    { id: 'm3', sender: 'Ananya Deshmukh', text: 'Local SQLite database migration completed with 0ms query latency.', time: '10:30 AM' },
  ],
  c2: [
    { id: 'm4', sender: 'Priya Nair', text: 'All Input Tax Credit claims for Q3 are reconciled.', time: '09:45 AM' },
  ],
  c3: [
    { id: 'm5', sender: 'Jatin Choudhary', text: 'Sprint planning meeting at 2 PM today.', time: '11:00 AM' },
  ],
  u1: [
    { id: 'm6', sender: 'Jatin Choudhary', text: 'Hey! The 3-module SPA navbar is fully functional.', time: '09:00 AM' },
  ],
};

export default function TeamChat({
  isOpen = true,
  onClose,
  embedded = false,
  title = 'Team Chat & Channels',
  showCloseButton = true,
  focusRoomId,
  focusChannelId,
  focusWithUserId,
}) {
  const [activeId, setActiveId] = useState(focusChannelId || focusRoomId || 'c1');
  const [activeType, setActiveType] = useState('channel');
  const [activeName, setActiveName] = useState('general');
  const [messages, setMessages] = useState(MOCK_MESSAGES);
  const [inputText, setInputText] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeId]);

  if (!isOpen && !embedded) return null;

  const handleSelectChannel = (chan) => {
    setActiveId(chan.id);
    setActiveType('channel');
    setActiveName(chan.name);
  };

  const handleSelectUser = (u) => {
    setActiveId(u.id);
    setActiveType('user');
    setActiveName(u.name);
  };

  const handleSend = () => {
    if (!inputText.trim()) return;
    const newMsg = {
      id: `m_${Date.now()}`,
      sender: 'You',
      text: inputText.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => ({
      ...prev,
      [activeId]: [...(prev[activeId] || []), newMsg],
    }));

    setInputText('');
  };

  const currentMessages = messages[activeId] || [];

  return (
    <Box
      sx={{
        display: 'flex',
        flex: 1,
        height: '100%',
        minHeight: '520px',
        width: '100%',
        bgcolor: 'background.paper',
        borderRadius: embedded ? 0 : 2,
        overflow: 'hidden',
        border: embedded ? 0 : 1,
        borderColor: 'divider',
      }}
    >
      {/* Sidebar: Channels & Users */}
      <Box
        sx={{
          width: { xs: 180, sm: 240 },
          borderRight: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'grey.50',
          flexShrink: 0,
        }}
      >
        <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search chat..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
        </Box>

        <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 1 }}>
          <Typography variant="caption" sx={{ px: 1, fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>
            Channels
          </Typography>
          <List dense disablePadding sx={{ mb: 2 }}>
            {MOCK_CHANNELS.filter((c) => c.name.toLowerCase().includes(searchQuery.toLowerCase())).map((chan) => (
              <ListItem key={chan.id} disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  selected={activeId === chan.id}
                  onClick={() => handleSelectChannel(chan)}
                  sx={{ borderRadius: 1.5 }}
                >
                  <ListItemAvatar sx={{ minWidth: 32 }}>
                    <TagIcon fontSize="small" color={activeId === chan.id ? 'primary' : 'action'} />
                  </ListItemAvatar>
                  <ListItemText
                    primary={`# ${chan.name}`}
                    primaryTypographyProps={{ fontSize: '0.85rem', fontWeight: activeId === chan.id ? 700 : 500 }}
                  />
                  {chan.unread > 0 && (
                    <Chip label={chan.unread} size="small" color="primary" sx={{ height: 18, fontSize: '0.7rem' }} />
                  )}
                </ListItemButton>
              </ListItem>
            ))}
          </List>

          <Typography variant="caption" sx={{ px: 1, fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>
            Direct Messages
          </Typography>
          <List dense disablePadding>
            {MOCK_USERS.filter((u) => u.name.toLowerCase().includes(searchQuery.toLowerCase())).map((u) => (
              <ListItem key={u.id} disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  selected={activeId === u.id}
                  onClick={() => handleSelectUser(u)}
                  sx={{ borderRadius: 1.5 }}
                >
                  <ListItemAvatar sx={{ minWidth: 32 }}>
                    <Badge
                      overlap="circular"
                      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                      variant="dot"
                      color={u.status === 'online' ? 'success' : 'default'}
                    >
                      <Avatar sx={{ width: 24, height: 24, fontSize: '0.75rem', bgcolor: 'primary.main' }}>
                        {u.name[0]}
                      </Avatar>
                    </Badge>
                  </ListItemAvatar>
                  <ListItemText
                    primary={u.name}
                    secondary={u.role}
                    primaryTypographyProps={{ fontSize: '0.825rem', fontWeight: activeId === u.id ? 700 : 500 }}
                    secondaryTypographyProps={{ fontSize: '0.7rem', noWrap: true }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Box>

      {/* Main Conversation Area */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Chat Header */}
        <Box
          sx={{
            p: 1.5,
            px: 2,
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {activeType === 'channel' ? <TagIcon color="primary" /> : <PersonIcon color="primary" />}
            <Typography variant="subtitle1" fontWeight={700}>
              {activeType === 'channel' ? `# ${activeName}` : activeName}
            </Typography>
          </Box>
          {showCloseButton && onClose && (
            <IconButton size="small" onClick={onClose}>
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
        </Box>

        {/* Message Feed */}
        <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {currentMessages.length === 0 ? (
            <Box sx={{ my: 'auto', textAlign: 'center', color: 'text.secondary' }}>
              <Typography variant="body2">No messages yet. Start the conversation!</Typography>
            </Box>
          ) : (
            currentMessages.map((msg) => {
              const isMe = msg.sender === 'You';
              return (
                <Box
                  key={msg.id}
                  sx={{
                    alignSelf: isMe ? 'flex-end' : 'flex-start',
                    maxWidth: '75%',
                  }}
                >
                  <Typography variant="caption" sx={{ color: 'text.secondary', px: 0.5, display: 'block', textAlign: isMe ? 'right' : 'left' }}>
                    {msg.sender} • {msg.time}
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.25,
                      px: 2,
                      borderRadius: 2,
                      bgcolor: isMe ? 'primary.main' : 'grey.100',
                      color: isMe ? 'primary.contrastText' : 'text.primary',
                    }}
                  >
                    <Typography variant="body2" sx={{ whitespace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {msg.text}
                    </Typography>
                  </Paper>
                </Box>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </Box>

        {/* Message Input Bar */}
        <Box sx={{ p: 1.5, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper', display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            size="small"
            placeholder={`Message ${activeType === 'channel' ? `#${activeName}` : activeName}...`}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <Button variant="contained" color="primary" onClick={handleSend} endIcon={<SendIcon />}>
            Send
          </Button>
        </Box>
      </Box>
    </Box>
  );
}
