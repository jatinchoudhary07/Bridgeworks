/**
 * PresenceContext
 * ===============
 * Tracks which org members are currently online and exposes that state
 * to the entire app — not just the chat panel.
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { BACKEND_URL } from '../config/api';
import { apiClient, getToken } from '../apiClient';
import { useUser } from './UserContext';

const PresenceContext = createContext({
    onlineUserIds: new Set(),
    userStatuses: {},
    myPresence: null,
    setManualStatus: async () => {},
    setMeetingStatus: async () => {},
});

export function PresenceProvider({ children }) {
    const { user } = useUser();
    const [userStatuses, setUserStatuses] = useState({});
    const [myPresence, setMyPresence] = useState(null);

    const wsRef = useRef(null);
    const wsRetryRef = useRef(0);
    const wsRetryTimerRef = useRef(null);
    const heartbeatTimerRef = useRef(null);
    const manuallyClosedRef = useRef(false);
    const meetingTimerRef = useRef(null);

    // Derive onlineUserIds for backwards compatibility
    const onlineUserIds = React.useMemo(() => {
        const online = new Set();
        Object.entries(userStatuses).forEach(([userId, status]) => {
            if (status === 'online' || status === 'in_meeting') {
                online.add(Number(userId));
            }
        });
        return online;
    }, [userStatuses]);

    // ── Heartbeat via WebSocket ────────────────────────────────────────────
    const sendWsHeartbeat = useCallback(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            try {
                wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
            } catch (err) {
                // ignore
            }
        }
    }, []);

    // ── Update manual status override ──────────────────────────────────────
    // status: 'online' | 'offline' | 'in_meeting' | 'on_leave' | '' (clears override)
    const setManualStatus = useCallback(async (status) => {
        if (!user) return;
        try {
            const res = await apiClient(`${BACKEND_URL}/api/presence/me/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ manual_status: status }),
                credentials: 'include',
            });
            if (res.ok) {
                const data = await res.json();
                setMyPresence(data);
                setUserStatuses((prev) => ({
                    ...prev,
                    [data.user_id]: data.resolved_status,
                }));
            }
        } catch (err) {
            console.error('Failed to set manual status:', err);
        }
    }, [user]);

    // ── Set meeting_active flag (called when user clicks "Join Meet") ──────
    // active: true = joining a meeting, false = leaving / meeting ended
    const setMeetingStatus = useCallback(async (active, durationMs = 3600000) => {
        if (!user) return;
        if (meetingTimerRef.current) {
            clearTimeout(meetingTimerRef.current);
            meetingTimerRef.current = null;
        }

        try {
            const res = await apiClient(`${BACKEND_URL}/api/presence/me/meeting/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active }),
                credentials: 'include',
            });
            if (res.ok) {
                const data = await res.json();
                setMyPresence(data);
                setUserStatuses((prev) => ({
                    ...prev,
                    [data.user_id]: data.resolved_status,
                }));

                if (active && durationMs > 0) {
                    meetingTimerRef.current = setTimeout(() => {
                        setMeetingStatus(false);
                    }, durationMs);
                }
            }
        } catch (err) {
            console.error('Failed to set meeting status:', err);
        }
    }, [user]);

    // ── Initial presence snapshot (REST fallback) ──────────────────────────
    const fetchPresenceSnapshot = useCallback(async () => {
        if (!user) return;
        try {
            const res = await apiClient(`${BACKEND_URL}/api/presence/`, {
                credentials: 'include',
            });
            if (res.ok) {
                const data = await res.json();
                const statuses = {};
                let currentPresence = null;
                data.forEach((p) => {
                    statuses[p.user_id] = p.resolved_status;
                    if (p.user_id === user.id) {
                        currentPresence = p;
                    }
                });
                setUserStatuses(statuses);
                if (currentPresence) {
                    setMyPresence(currentPresence);
                }
            }
        } catch (err) {
            console.error('Failed to fetch presence snapshot:', err);
        }
    }, [user]);

    // ── WebSocket (presence_update listener) ──────────────────────────────
    useEffect(() => {
        if (!user) return;

        manuallyClosedRef.current = false;
        const wsBase =
            BACKEND_URL.replace(/^https?/, (m) => (m === 'https' ? 'wss' : 'ws')) + '/ws/presence/';

        const connect = () => {
            const token = getToken();
            const wsUrl = token ? `${wsBase}?token=${token}` : wsBase;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                wsRetryRef.current = 0;
                // Grab an up-to-date snapshot immediately after connecting
                fetchPresenceSnapshot();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'presence_update') {
                        const { user_id, status } = data;
                        setUserStatuses((prev) => ({
                            ...prev,
                            [user_id]: status,
                        }));
                        if (user_id === user.id) {
                            setMyPresence((prev) => prev ? { ...prev, resolved_status: status } : null);
                        }
                    }
                } catch (err) {
                    // ignore malformed frames
                }
            };

            ws.onclose = (event) => {
                wsRef.current = null;
                if (manuallyClosedRef.current || event.code === 1000) return;
                const delay = Math.min(500 * 2 ** wsRetryRef.current, 30_000);
                wsRetryRef.current += 1;
                if (wsRetryTimerRef.current) clearTimeout(wsRetryTimerRef.current);
                wsRetryTimerRef.current = setTimeout(connect, delay);
            };

            ws.onerror = () => {
                try { ws.close(); } catch { /* ignore */ }
            };
        };

        connect();

        return () => {
            manuallyClosedRef.current = true;
            if (wsRetryTimerRef.current) clearTimeout(wsRetryTimerRef.current);
            if (wsRef.current && wsRef.current.readyState < 2) {
                wsRef.current.close(1000);
            }
            wsRef.current = null;
        };
    }, [user, fetchPresenceSnapshot]);

    // ── Heartbeat loop (fires as long as the user is logged in) ───────────
    useEffect(() => {
        if (!user) return;

        // Send heartbeat initially
        sendWsHeartbeat();

        heartbeatTimerRef.current = setInterval(() => {
            if (!document.hidden) sendWsHeartbeat();
        }, 30_000);

        const handleVisibility = () => {
            if (!document.hidden) sendWsHeartbeat();
        };
        document.addEventListener('visibilitychange', handleVisibility);

        return () => {
            clearInterval(heartbeatTimerRef.current);
            if (meetingTimerRef.current) {
                clearTimeout(meetingTimerRef.current);
            }
            document.removeEventListener('visibilitychange', handleVisibility);
        };
    }, [user, sendWsHeartbeat]);

    return (
        <PresenceContext.Provider value={{ onlineUserIds, userStatuses, myPresence, setManualStatus, setMeetingStatus }}>
            {children}
        </PresenceContext.Provider>
    );
}

export function usePresence() {
    return useContext(PresenceContext);
}
