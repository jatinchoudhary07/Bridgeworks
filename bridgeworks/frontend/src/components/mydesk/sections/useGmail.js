// useGmail.js — hook that wires gmailService to local state
import { useState, useCallback, useRef } from 'react';
import * as svc from './gmailService';

export function useGmail() {
    const [emails,          setEmails]          = useState([]);
    const [loading,         setLoading]         = useState(false);
    const [error,           setError]           = useState(null);
    const [selectedFolder,  setSelectedFolder]  = useState('INBOX');
    const [selectedEmail,   setSelectedEmail]   = useState(null);
    const [unreadCount,     setUnreadCount]      = useState(0);
    const [connected,       setConnected]        = useState(null); // null = unknown
    const [gmailEmail,      setGmailEmail]       = useState('');

    const abortRef = useRef(null);

    // ── Auth ────────────────────────────────────────────────────────────────

    const checkConnection = useCallback(async () => {
        try {
            const data = await svc.getGmailStatus();
            setConnected(data.connected);
            setGmailEmail(data.email || '');
            return data.connected;
        } catch {
            setConnected(false);
            return false;
        }
    }, []);

    const connectGmail = useCallback(async () => {
        const data = await svc.initiateGmailOAuth();
        window.location.href = data.auth_url;
    }, []);

    const disconnectGmail = useCallback(async () => {
        await svc.disconnectGmail();
        setConnected(false);
        setGmailEmail('');
        setEmails([]);
    }, []);

    // ── Fetch ────────────────────────────────────────────────────────────────

    const fetchEmails = useCallback(async (folder = selectedFolder) => {
        setLoading(true);
        setError(null);
        try {
            const data = await svc.fetchEmailList(folder);
            setEmails(data.emails || []);
            if (folder === 'INBOX') setUnreadCount(data.totalUnread || 0);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [selectedFolder]);

    const searchEmails = useCallback(async (query) => {
        setLoading(true);
        setError(null);
        try {
            const data = await svc.searchEmails(query);
            setEmails(data.emails || []);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    // ── Open full detail ─────────────────────────────────────────────────────

    const openEmail = useCallback(async (summary) => {
        setSelectedEmail(summary); // Show summary immediately
        try {
            const detail = await svc.fetchEmailDetail(summary.id);
            setSelectedEmail(detail);
            // Optimistically mark as read in list
            if (!detail.isRead) {
                setEmails(prev => prev.map(e => e.id === summary.id ? { ...e, isRead: true } : e));
            }
        } catch { /* keep summary */ }
    }, []);

    // ── Mutations ────────────────────────────────────────────────────────────

    const markAsRead = useCallback(async (id) => {
        await svc.markAsRead([id]);
        setEmails(prev => prev.map(e => e.id === id ? { ...e, isRead: true } : e));
        if (selectedEmail?.id === id) setSelectedEmail(s => s ? { ...s, isRead: true } : s);
    }, [selectedEmail]);

    const markAsUnread = useCallback(async (id) => {
        await svc.markAsUnread([id]);
        setEmails(prev => prev.map(e => e.id === id ? { ...e, isRead: false } : e));
    }, []);

    const starEmail = useCallback(async (id) => {
        await svc.starEmail(id);
        setEmails(prev => prev.map(e => e.id === id ? { ...e, isStarred: true } : e));
        if (selectedEmail?.id === id) setSelectedEmail(s => s ? { ...s, isStarred: true } : s);
    }, [selectedEmail]);

    const unstarEmail = useCallback(async (id) => {
        await svc.unstarEmail(id);
        setEmails(prev => prev.map(e => e.id === id ? { ...e, isStarred: false } : e));
        if (selectedEmail?.id === id) setSelectedEmail(s => s ? { ...s, isStarred: false } : s);
    }, [selectedEmail]);

    const archiveEmail = useCallback(async (id) => {
        await svc.archiveEmail(id);
        setEmails(prev => prev.filter(e => e.id !== id));
        if (selectedEmail?.id === id) setSelectedEmail(null);
    }, [selectedEmail]);

    const trashEmail = useCallback(async (id) => {
        await svc.trashEmail(id);
        setEmails(prev => prev.filter(e => e.id !== id));
        if (selectedEmail?.id === id) setSelectedEmail(null);
    }, [selectedEmail]);

    const sendEmail = useCallback(async (payload) => {
        return svc.sendEmail(payload);
    }, []);

    const downloadAttachment = useCallback(async (messageId, attachmentId, filename) => {
        return svc.downloadAttachment(messageId, attachmentId, filename);
    }, []);

    return {
        emails, loading, error,
        selectedFolder, setSelectedFolder,
        selectedEmail,  setSelectedEmail,
        unreadCount,
        connected, gmailEmail,
        checkConnection, connectGmail, disconnectGmail,
        fetchEmails, searchEmails, openEmail,
        markAsRead, markAsUnread,
        starEmail, unstarEmail,
        archiveEmail, trashEmail,
        sendEmail,
        downloadAttachment,
    };
}
