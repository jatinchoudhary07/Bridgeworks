import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Box, Badge, IconButton, Popover, List, ListItem,
    ListItemText, Typography, Button, Tooltip, Stack, Chip
} from '@mui/material';
import { 
    Notifications as NotifIcon,
    CheckCircle as CheckIcon,
    Archive as ArchiveIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { BACKEND_URL } from '../../config/api';
import { apiClient, getToken } from '../../apiClient';
import { useUser } from '../../contexts/UserContext';
import { playNotificationSoundForNotification, primeNotificationAudio } from '../../utils/notificationSound';
import { MYDESK_ID_TO_PATH } from '../mydesk/config';


const NOTIFICATION_POLL_INTERVAL_MS = 7000;
const UNREAD_COUNT_POLL_INTERVAL_MS = 30000;
const WEBSOCKET_RETRY_MS = 3000;


const FILTER_CATEGORIES = [
    { id: 'All', label: 'All', type: 'all' },
    { id: 'critical', label: 'Critical', type: 'priority' },
    { id: 'high', label: 'High', type: 'priority' },
    { id: 'medium', label: 'Medium', type: 'priority' },
    { id: 'low', label: 'Low', type: 'priority' },
    { id: 'leadership', label: 'Leadership & Strategy', type: 'module' },
    { id: 'product', label: 'Product & Merchandising', type: 'module' },
    { id: 'branding', label: 'Branding & Creative', type: 'module' },
    { id: 'marketing', label: 'Marketing & Growth', type: 'module' },
    { id: 'ecommerce', label: 'E-Commerce & Website', type: 'module' },
    { id: 'operations', label: 'Operations & Fulfilment', type: 'module' },
    { id: 'tracking', label: 'Logistics', type: 'module' },
    { id: 'rto_management', label: 'Reverse Shipment', type: 'module' },
    { id: 'taskmanager', label: 'My Desk', type: 'module' },
    { id: 'customerExperience', label: 'Customer Experience', type: 'module' },
    { id: 'intelligence', label: 'Intelligence', type: 'module' },
    { id: 'webhooks', label: 'Webhooks', type: 'module' },
    { id: 'finance', label: 'Finance & Accounting', type: 'module' },
    { id: 'hr', label: 'Human Resources', type: 'module' },
    { id: 'it', label: 'IT & Data', type: 'module' },
    { id: 'production', label: 'Production / Manufacturing', type: 'module' },
    { id: 'sales', label: 'Sales & Business Dev', type: 'module' },
];

const MODULE_DISPLAY_LABELS = {
    leadership: 'Leadership & Strategy',
    product: 'Product & Merchandising',
    branding: 'Branding & Creative',
    marketing: 'Marketing & Growth',
    ecommerce: 'E-Commerce & Website',
    operations: 'Operations & Fulfilment',
    tracking: 'Logistics',
    rto_management: 'Reverse Shipment',
    taskmanager: 'My Desk',
    customerExperience: 'Customer Experience',
    intelligence: 'Intelligence',
    webhooks: 'Webhooks',
    finance: 'Finance & Accounting',
    hr: 'Human Resources',
    it: 'IT & Data',
    production: 'Production / Manufacturing',
    sales: 'Sales & Business Dev',
};

function parseNotificationList(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && typeof payload === 'object' && Array.isArray(payload.results)) {
        return payload.results;
    }
    return [];
}

export default function NotificationBell() {
    const navigate = useNavigate();
    const [unreadCount, setUnreadCount] = useState(0);
    const [notifications, setNotifications] = useState([]);
    const [anchor, setAnchor] = useState(null);
    const { user, loadingUser } = useUser();
    const seenNotificationIdsRef = useRef(new Set());
    const notificationsHydratedRef = useRef(false);

    const [localNotifications, setLocalNotifications] = useState(() => {
        try {
            const readLocalIds = JSON.parse(localStorage.getItem('read_local_notification_ids') || '[]');
            const archivedLocalIds = JSON.parse(localStorage.getItem('archived_local_notification_ids') || '[]');
            return [
                { id: 'notif_1', message: 'GST filing due in 12 days', category: 'Compliance', priority: 'Critical', is_read: readLocalIds.includes('notif_1'), is_archived: archivedLocalIds.includes('notif_1'), created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString() },
                { id: 'notif_2', message: 'Receivables crossed threshold', category: 'Finance', priority: 'High', is_read: readLocalIds.includes('notif_2'), is_archived: archivedLocalIds.includes('notif_2'), created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString() },
                { id: 'notif_3', message: 'Payroll approved', category: 'Operations', priority: 'Medium', is_read: true, is_archived: archivedLocalIds.includes('notif_3'), created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString() },
                { id: 'notif_4', message: 'Bank reconciliation completed', category: 'Banking', priority: 'Low', is_read: true, is_archived: archivedLocalIds.includes('notif_4'), created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString() },
                { id: 'notif_5', message: 'Asset replacement recommended', category: 'Operations', priority: 'Medium', is_read: readLocalIds.includes('notif_5'), is_archived: archivedLocalIds.includes('notif_5'), created_at: new Date(Date.now() - 1000 * 60 * 60 * 30).toISOString() },
            ];
        } catch (e) {
            return [
                { id: 'notif_1', message: 'GST filing due in 12 days', category: 'Compliance', priority: 'Critical', is_read: false, is_archived: false, created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString() },
                { id: 'notif_2', message: 'Receivables crossed threshold', category: 'Finance', priority: 'High', is_read: false, is_archived: false, created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString() },
                { id: 'notif_3', message: 'Payroll approved', category: 'Operations', priority: 'Medium', is_read: true, is_archived: false, created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString() },
                { id: 'notif_4', message: 'Bank reconciliation completed', category: 'Banking', priority: 'Low', is_read: true, is_archived: false, created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString() },
                { id: 'notif_5', message: 'Asset replacement recommended', category: 'Operations', priority: 'Medium', is_read: false, is_archived: false, created_at: new Date(Date.now() - 1000 * 60 * 60 * 30).toISOString() },
            ];
        }
    });
    const [currentTab, setCurrentTab] = useState('all'); // 'all', 'module', 'priority'
    const [selectedModule, setSelectedModule] = useState('');
    const [selectedPriority, setSelectedPriority] = useState('critical');
    const [preferences, setPreferences] = useState([]);

    const fetchPreferences = useCallback(async () => {
        try {
            const res = await apiClient(`${BACKEND_URL}/api/notification-preferences/bulk-settings/`, {
                credentials: 'include',
                cache: 'no-store'
            });
            if (res.ok) {
                const data = await res.json();
                setPreferences(data);
                
                // Set initial active module if not set
                const enabled = data.filter(p => p.in_app_delivery);
                if (enabled.length > 0) {
                    setSelectedModule(prev => prev || enabled[0].category);
                }
            }
        } catch (err) {
            console.error('Failed to load preferences:', err);
        }
    }, []);

    const markNotificationSeen = useCallback((notificationId) => {
        if (notificationId == null) return;
        seenNotificationIdsRef.current.add(String(notificationId));
    }, []);

    const fetchUnreadCount = useCallback(async () => {
        try {
            const res = await apiClient(`${BACKEND_URL}/api/notifications/unread_count/`, {
                credentials: 'include',
                cache: 'no-store',
            });
            if (res.ok) {
                const data = await res.json();
                setUnreadCount(data.count);
            }
        } catch {
            // Silent failure: websocket and fallback polling continue to work.
        }
    }, []);

    const upsertIncomingNotification = useCallback((incomingNotification, { playSound = false } = {}) => {
        if (!incomingNotification || incomingNotification.id == null) return;

        const notificationId = String(incomingNotification.id);
        if (seenNotificationIdsRef.current.has(notificationId)) {
            return;
        }

        seenNotificationIdsRef.current.add(notificationId);

        setNotifications((previous) => [incomingNotification, ...previous].slice(0, 100));
        if (!incomingNotification.is_read) {
            setUnreadCount((previous) => previous + 1);
        }

        if (playSound && !incomingNotification.is_read) {
            playNotificationSoundForNotification(incomingNotification).catch(() => {
                // Sound playback is best-effort and can be blocked by browser policies.
            });
        }
    }, []);

    const fetchNotifications = useCallback(async ({ playSoundForNew = false } = {}) => {
        try {
            const res = await apiClient(`${BACKEND_URL}/api/notifications/?limit=100`, {
                credentials: 'include',
                cache: 'no-store',
            });
            if (!res.ok) {
                return false;
            }

            const payload = await res.json();
            const nextNotifications = parseNotificationList(payload);

            if (playSoundForNew && notificationsHydratedRef.current) {
                const unseen = nextNotifications.filter((entry) => {
                    if (!entry || entry.id == null) return false;
                    return !seenNotificationIdsRef.current.has(String(entry.id));
                });

                unseen
                    .slice()
                    .sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))
                    .forEach((entry) => {
                        if (!entry.is_read) {
                            playNotificationSoundForNotification(entry).catch(() => {
                                // Sound playback is best-effort.
                            });
                        }
                    });
            }

            nextNotifications.forEach((entry) => markNotificationSeen(entry?.id));
            notificationsHydratedRef.current = true;
            setNotifications(nextNotifications.slice(0, 100));
            return true;
        } catch (error) {
            console.error('Fetch notifications failed', error);
            return false;
        }
    }, [markNotificationSeen]);

    useEffect(() => {
        try {
            const readIds = localNotifications.filter(n => n.is_read).map(n => n.id);
            localStorage.setItem('read_local_notification_ids', JSON.stringify(readIds));
            
            const archivedIds = localNotifications.filter(n => n.is_archived).map(n => n.id);
            localStorage.setItem('archived_local_notification_ids', JSON.stringify(archivedIds));
        } catch (e) {
            // ignore
        }
    }, [localNotifications]);

    useEffect(() => {
        if (!user) {
            setUnreadCount(0);
            setNotifications([]);
            seenNotificationIdsRef.current = new Set();
            notificationsHydratedRef.current = false;
        }
    }, [user]);

    useEffect(() => {
        if (loadingUser) return;
        if (!user) return;

        fetchUnreadCount();
        const interval = setInterval(fetchUnreadCount, UNREAD_COUNT_POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [user, loadingUser, fetchUnreadCount]);

    useEffect(() => {
        if (loadingUser || !user) return undefined;

        let unmounted = false;

        const unlockSoundPlayback = () => {
            if (unmounted) return;
            primeNotificationAudio()
                .finally(() => {
                    window.removeEventListener('pointerdown', unlockSoundPlayback);
                    window.removeEventListener('keydown', unlockSoundPlayback);
                    window.removeEventListener('touchstart', unlockSoundPlayback);
                });
        };

        window.addEventListener('pointerdown', unlockSoundPlayback, { passive: true });
        window.addEventListener('keydown', unlockSoundPlayback);
        window.addEventListener('touchstart', unlockSoundPlayback, { passive: true });

        fetchNotifications({ playSoundForNew: false });
        fetchPreferences();
        const pollTimer = setInterval(() => {
            fetchNotifications({ playSoundForNew: true });
        }, NOTIFICATION_POLL_INTERVAL_MS);

        return () => {
            unmounted = true;
            clearInterval(pollTimer);
            window.removeEventListener('pointerdown', unlockSoundPlayback);
            window.removeEventListener('keydown', unlockSoundPlayback);
            window.removeEventListener('touchstart', unlockSoundPlayback);
        };
    }, [user, loadingUser, fetchNotifications]);

    useEffect(() => {
        if (loadingUser || !user) return undefined;

        let socket;
        let shouldCloseAfterConnect = false;
        let reconnectTimer = null;
        let stopped = false;

        const scheduleReconnect = () => {
            if (stopped || reconnectTimer) return;
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connect();
            }, WEBSOCKET_RETRY_MS);
        };

        const connect = () => {
            if (stopped) return;

            const accessToken = getToken();
            const wsBaseUrl = `${BACKEND_URL.replace(/^http/, 'ws')}/ws/notifications/`;
            const wsUrl = accessToken
                ? `${wsBaseUrl}?token=${encodeURIComponent(accessToken)}`
                : wsBaseUrl;

            try {
                socket = new WebSocket(wsUrl);
            } catch {
                scheduleReconnect();
                return;
            }

            socket.onopen = () => {
                if (shouldCloseAfterConnect && socket?.readyState === WebSocket.OPEN) {
                    socket.close(1000, 'NotificationBell unmounted');
                }
            };

            socket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data || '{}');
                    if (payload.type === 'notification.created' && payload.notification) {
                        upsertIncomingNotification(payload.notification, { playSound: true });
                        if (payload.notification.module === 'my_chats') {
                            window.dispatchEvent(new CustomEvent('bridgeworks:chat-unread-updated'));
                        }
                        return;
                    }

                    if (payload.type === 'notification.read' && payload.notification_id != null) {
                        const targetId = String(payload.notification_id);
                        const targetNotif = notifications.find(n => String(n.id) === targetId);
                        setNotifications((previous) => previous.map((entry) => (
                            String(entry.id) === targetId ? { ...entry, is_read: true } : entry
                        )));
                        fetchUnreadCount();
                        if (targetNotif && targetNotif.module === 'my_chats') {
                            window.dispatchEvent(new CustomEvent('bridgeworks:chat-unread-updated'));
                        }
                        return;
                    }

                    if (payload.type === 'notification.all_read') {
                        const ids = Array.isArray(payload.notification_ids)
                            ? new Set(payload.notification_ids.map((value) => String(value)))
                            : null;
                        setNotifications((previous) => previous.map((entry) => {
                            if (!ids || ids.size === 0) return { ...entry, is_read: true };
                            return ids.has(String(entry.id)) ? { ...entry, is_read: true } : entry;
                        }));
                        fetchUnreadCount();
                        window.dispatchEvent(new CustomEvent('bridgeworks:chat-unread-updated'));
                    }
                } catch {
                    // Ignore malformed websocket payloads
                }
            };

            socket.onerror = () => {
                if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) {
                    socket.close();
                }
            };

            socket.onclose = () => {
                if (stopped) return;
                fetchNotifications({ playSoundForNew: true });
                scheduleReconnect();
            };
        };

        connect();

        return () => {
            stopped = true;
            shouldCloseAfterConnect = true;

            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
            }

            if (!socket) return;

            socket.onmessage = null;
            socket.onclose = null;
            socket.onerror = null;

            if (socket.readyState === WebSocket.OPEN) {
                socket.close(1000, 'NotificationBell unmounted');
            }
        };
    }, [user, loadingUser, fetchNotifications, fetchUnreadCount, upsertIncomingNotification]);

    const handleOpen = (e) => {
        setAnchor(e.currentTarget);
        primeNotificationAudio().catch(() => {
            // Browser can still reject audio priming without a trusted user gesture.
        });
        fetchNotifications({ playSoundForNew: false });
        fetchPreferences();
    };

    const handleClose = () => setAnchor(null);

    const handleMarkAllRead = async () => {
        try {
            await apiClient(`${BACKEND_URL}/api/notifications/mark_all_read/`, {
                method: 'POST',
                headers: {},
                credentials: 'include'
            });
            setUnreadCount(0);
            setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
        } catch (e) { console.error('Mark all read failed', e); }
    };

    const handleMarkRead = async (notifId) => {
        try {
            await apiClient(`${BACKEND_URL}/api/notifications/${notifId}/mark_read/`, {
                method: 'POST',
                headers: {},
                credentials: 'include'
            });
            const targetId = String(notifId);
            setNotifications(prev => prev.map(n => String(n.id) === targetId ? { ...n, is_read: true } : n));
            setUnreadCount(prev => Math.max(0, prev - 1));
        } catch (e) { /* silent */ }
    };

    const openNotification = async (notification) => {
        const link = notification.deep_link && typeof notification.deep_link === 'object'
            ? notification.deep_link
            : {};

        const params = new URLSearchParams();
        if (link.section) params.set('section', String(link.section));
        if (link.noteId) params.set('noteId', String(link.noteId));
        if (link.commentId) params.set('commentId', String(link.commentId));
        if (link.taskId) params.set('taskId', String(link.taskId));
        if (link.messageId) params.set('messageId', String(link.messageId));
        if (link.withUserId) params.set('withUserId', String(link.withUserId));
        if (link.roomId) params.set('roomId', String(link.roomId));
        if (link.channelId) params.set('channelId', String(link.channelId));
        if (link.isBroadcast) params.set('isBroadcast', String(link.isBroadcast));
        if (Array.isArray(link.groupUserIds) && link.groupUserIds.length > 0) {
            params.set('groupUserIds', link.groupUserIds.join(','));
        }
        if (link.expenseId) params.set('expenseId', String(link.expenseId));
        if (link.leaveId) params.set('leaveId', String(link.leaveId));
        if (link.itemId) params.set('itemId', String(link.itemId));
        if (link.albumId) params.set('albumId', String(link.albumId));
        if (link.eventId) params.set('eventId', String(link.eventId));

        let basePath = typeof link.page === 'string' && link.page.trim() ? link.page : '';
        if (!basePath && typeof link.pathname === 'string' && link.pathname.trim()) {
            basePath = link.pathname;
        }
        if (!basePath) {
            basePath = '/mydesk/notes';
        }

        // Map legacy/incorrect paths to the correct /mydesk/:section path using MYDESK_ID_TO_PATH
        if (basePath === '/task-manager' || basePath.startsWith('/task-manager/') || basePath === '/mydesk' || basePath.startsWith('/mydesk/')) {
            if (link.section && MYDESK_ID_TO_PATH && MYDESK_ID_TO_PATH[link.section]) {
                basePath = `/mydesk/${MYDESK_ID_TO_PATH[link.section]}`;
            }
        }

        navigate(params.toString() ? `${basePath}?${params.toString()}` : basePath);
        await handleMarkRead(notification.id);
        if (notification.module === 'my_chats') {
            window.dispatchEvent(new CustomEvent('bridgeworks:chat-unread-updated'));
        }
        setAnchor(null);
    };

    const normalizedLocal = localNotifications.map(n => {
        let cat = String(n.category).toLowerCase().replace(/ & /g, '_').replace(/ /g, '_');
        if (cat === 'compliance' || cat === 'banking' || cat === 'finance') cat = 'finance_accounting';
        return {
            ...n,
            isLocal: true,
            category: cat,
            priority: String(n.priority).toLowerCase(),
        };
    });

    const normalizedBackend = notifications.map(n => ({
        ...n,
        isLocal: false,
        priority: String(n.priority || 'medium').toLowerCase(),
        category: String(n.category || 'sales_overview').toLowerCase()
    }));

    const allCombined = [...normalizedLocal, ...normalizedBackend];

    // Filter out notifications from disabled categories
    const enabledCategoryKeys = new Set(
        preferences
            .filter(p => p.in_app_delivery)
            .map(p => String(p.category).toLowerCase())
    );

    const isCategoryEnabled = (cat) => {
        if (preferences.length === 0) return true;
        return enabledCategoryKeys.has(String(cat).toLowerCase());
    };

    const filteredByPreferences = allCombined.filter(n => isCategoryEnabled(n.category));

    const activeUnreadCount = filteredByPreferences.filter(n => !n.is_read && !n.is_archived).length;

    // List of enabled modules for sub-tabs
    const enabledModules = preferences.length > 0
        ? preferences.filter(p => p.in_app_delivery)
        : Object.keys(MODULE_DISPLAY_LABELS).map(key => ({
            category: key,
            category_display: MODULE_DISPLAY_LABELS[key]
        }));

    return (
        <>
            <Tooltip title="Notifications">
                <IconButton onClick={handleOpen} size="small">
                    <Badge badgeContent={activeUnreadCount} color="error" max={99}>
                        <NotifIcon fontSize="small" />
                    </Badge>
                </IconButton>
            </Tooltip>

            <Popover
                open={Boolean(anchor)}
                anchorEl={anchor}
                onClose={handleClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                sx={{ zIndex: 100000 }}
                slotProps={{
                    paper: {
                        sx: { width: 420, maxHeight: 540, borderRadius: '12px', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)', border: '1px solid #E2E8F0' }
                    }
                }}
            >
                {/* Header */}
                <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9' }}>
                    <Typography sx={{ fontSize: '14px', fontWeight: 800, color: '#0F172A' }}>
                        🔔 Notification Center
                    </Typography>
                    <Stack direction="row" spacing={1}>
                        <Button 
                            size="small" 
                            onClick={() => {
                                setAnchor(null);
                                navigate('/notifications');
                            }}
                            sx={{ textTransform: 'none', fontSize: 11, fontWeight: 700, color: '#6366F1' }}
                        >
                            Board View
                        </Button>
                        <Button 
                            size="small" 
                            onClick={async () => {
                                await handleMarkAllRead();
                                setLocalNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
                            }} 
                            sx={{ textTransform: 'none', fontSize: 11, fontWeight: 700, color: '#6366F1' }}
                        >
                            Mark all read
                        </Button>
                    </Stack>
                </Box>

                {/* Main Selector Tabs */}
                <Box sx={{ px: 2, pt: 1, pb: 1, borderBottom: '1px solid #F1F5F9', display: 'flex', gap: 1 }}>
                    {[
                        { id: 'all', label: 'All' },
                        { id: 'module', label: 'By Module' },
                        { id: 'priority', label: 'By Priority' }
                    ].map((tab) => (
                        <Button
                            key={tab.id}
                            size="small"
                            onClick={() => {
                                setCurrentTab(tab.id);
                                if (tab.id === 'module' && !selectedModule && enabledModules.length > 0) {
                                    setSelectedModule(enabledModules[0].category);
                                }
                            }}
                            sx={{
                                flex: 1,
                                textTransform: 'none',
                                fontSize: '11px',
                                fontWeight: 700,
                                borderRadius: '8px',
                                py: 0.5,
                                bgcolor: currentTab === tab.id ? '#6366F1' : 'transparent',
                                color: currentTab === tab.id ? '#fff' : '#64748B',
                                '&:hover': {
                                    bgcolor: currentTab === tab.id ? '#4F46E5' : 'rgba(99,102,241,0.05)',
                                    color: currentTab === tab.id ? '#fff' : '#4F46E5'
                                }
                            }}
                        >
                            {tab.label}
                        </Button>
                    ))}
                </Box>

                {/* Sub-tabs / Chips Container */}
                {currentTab === 'module' && (
                    <Box sx={{ px: 2, py: 1.5, display: 'flex', gap: 0.75, overflowX: 'auto', borderBottom: '1px solid #F1F5F9', '&::-webkit-scrollbar': { display: 'none' } }}>
                        {enabledModules.map((m) => {
                            const count = filteredByPreferences.filter(n => !n.is_archived && n.category === m.category).length;
                            const isSelected = selectedModule === m.category;
                            return (
                                <Chip
                                    key={m.category}
                                    label={`${m.category_display || MODULE_DISPLAY_LABELS[m.category] || m.category} (${count})`}
                                    size="small"
                                    onClick={() => setSelectedModule(m.category)}
                                    sx={{
                                        fontSize: '10.5px',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        bgcolor: isSelected ? '#6366F1' : '#F1F5F9',
                                        color: isSelected ? '#fff' : '#64748B',
                                        '&:hover': { bgcolor: isSelected ? '#4F46E5' : '#E2E8F0' }
                                    }}
                                />
                            );
                        })}
                    </Box>
                )}

                {currentTab === 'priority' && (
                    <Box sx={{ px: 2, py: 1.5, display: 'flex', gap: 0.75, overflowX: 'auto', borderBottom: '1px solid #F1F5F9', '&::-webkit-scrollbar': { display: 'none' } }}>
                        {['critical', 'high', 'medium', 'low'].map((p) => {
                            const count = filteredByPreferences.filter(n => !n.is_archived && n.priority === p).length;
                            const isSelected = selectedPriority === p;
                            
                            let chipBg = '#F1F5F9';
                            let chipColor = '#64748B';
                            let hoverBg = '#E2E8F0';
                            
                            if (isSelected) {
                                if (p === 'critical') { chipBg = '#EF4444'; chipColor = '#fff'; hoverBg = '#DC2626'; }
                                else if (p === 'high') { chipBg = '#F59E0B'; chipColor = '#fff'; hoverBg = '#D97706'; }
                                else if (p === 'medium') { chipBg = '#3B82F6'; chipColor = '#fff'; hoverBg = '#2563EB'; }
                                else { chipBg = '#10B981'; chipColor = '#fff'; hoverBg = '#059669'; }
                            }
                            
                            return (
                                <Chip
                                    key={p}
                                    label={`${p.charAt(0).toUpperCase() + p.slice(1)} (${count})`}
                                    size="small"
                                    onClick={() => setSelectedPriority(p)}
                                    sx={{
                                        fontSize: '10.5px',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        bgcolor: chipBg,
                                        color: chipColor,
                                        '&:hover': { bgcolor: hoverBg }
                                    }}
                                />
                            );
                        })}
                    </Box>
                )}

                {/* List Container */}
                <Box sx={{ overflowY: 'auto', maxHeight: 340 }}>
                    {(() => {
                        const filtered = filteredByPreferences.filter(n => {
                            if (n.is_archived) return false;
                            if (currentTab === 'all') return true;
                            if (currentTab === 'module') return n.category === selectedModule;
                            if (currentTab === 'priority') return n.priority === selectedPriority;
                            return true;
                        });

                        if (filtered.length === 0) {
                            return (
                                <Box sx={{ p: 4, textAlign: 'center' }}>
                                    <Typography sx={{ fontSize: '12px', color: '#64748B' }}>
                                        No notifications in this category
                                    </Typography>
                                </Box>
                            );
                        }

                        return (
                            <List dense disablePadding>
                                {filtered.map(n => {
                                    const priorityColors = n.priority === 'critical' 
                                        ? { color: '#EF4444', bg: '#FEE2E2' }
                                        : n.priority === 'high'
                                            ? { color: '#F59E0B', bg: '#FEF9F0' }
                                            : n.priority === 'medium'
                                                ? { color: '#3B82F6', bg: '#DBEAFE' }
                                                : { color: '#10B981', bg: '#E6F4EA' };
                                                
                                    const categoryLabel = MODULE_DISPLAY_LABELS[n.category] || n.category;

                                    return (
                                        <ListItem
                                            key={n.id}
                                            sx={{
                                                borderBottom: '1px solid #F1F5F9',
                                                bgcolor: n.is_read ? 'transparent' : 'rgba(99,102,241,0.03)',
                                                px: 2.5,
                                                py: 1.5,
                                                display: 'flex',
                                                flexDirection: 'column',
                                                alignItems: 'stretch',
                                                gap: 0.5,
                                                '&:hover': { bgcolor: 'action.hover' }
                                            }}
                                        >
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                                <Typography 
                                                    onClick={() => openNotification(n)}
                                                    sx={{ fontSize: '12px', fontWeight: n.is_read ? 500 : 700, color: '#0F172A', lineHeight: 1.3, flex: 1, pr: 2, cursor: 'pointer', '&:hover': { color: '#6366F1' } }}
                                                >
                                                    {n.title ? <strong>{n.title}: </strong> : null}
                                                    {n.message}
                                                </Typography>
                                                <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
                                                    {!n.is_read && (
                                                        <Tooltip title="Mark read">
                                                            <IconButton 
                                                                size="small" 
                                                                onClick={async () => {
                                                                    if (n.isLocal) {
                                                                        setLocalNotifications(prev => prev.map(item => item.id === n.id ? { ...item, is_read: true } : item));
                                                                    } else {
                                                                        await handleMarkRead(n.id);
                                                                    }
                                                                }}
                                                                sx={{ p: 0.25, color: '#10B981' }}
                                                            >
                                                                <CheckIcon sx={{ fontSize: 14 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                    )}
                                                    <Tooltip title="Archive">
                                                        <IconButton 
                                                            size="small" 
                                                            onClick={() => {
                                                                if (n.isLocal) {
                                                                    setLocalNotifications(prev => prev.map(item => item.id === n.id ? { ...item, is_archived: true } : item));
                                                                } else {
                                                                    setNotifications(prev => prev.filter(item => item.id !== n.id));
                                                                }
                                                            }}
                                                            sx={{ p: 0.25, color: '#64748B' }}
                                                        >
                                                            <ArchiveIcon sx={{ fontSize: 14 }} />
                                                        </IconButton>
                                                    </Tooltip>
                                                </Box>
                                            </Box>
                                            
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
                                                <Stack direction="row" spacing={0.75}>
                                                    <Box sx={{ px: 0.7, py: 0.2, borderRadius: '4px', bgcolor: priorityColors.bg, color: priorityColors.color, fontSize: '8.5px', fontWeight: 800, textTransform: 'uppercase' }}>
                                                        {n.priority}
                                                    </Box>
                                                    <Box sx={{ px: 0.7, py: 0.2, borderRadius: '4px', bgcolor: '#F1F5F9', color: '#64748B', fontSize: '8.5px', fontWeight: 800 }}>
                                                        {categoryLabel}
                                                    </Box>
                                                </Stack>
                                                <Typography sx={{ fontSize: '9px', color: '#94A3B8', fontWeight: 500 }}>
                                                    {new Date(n.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })}
                                                </Typography>
                                            </Box>
                                        </ListItem>
                                    );
                                })}
                            </List>
                        );
                    })()}
                </Box>
            </Popover>
        </>
    );
}
