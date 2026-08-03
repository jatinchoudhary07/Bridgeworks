// gmailService.js
// Proxies all Gmail API calls through the Django backend.

import { apiClient } from '../../../apiClient';

async function apiFetch(path, options = {}) {
    const res = await apiClient(path, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        }
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `HTTP ${res.status}`);
    }
    return res.status === 204 ? null : res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const getGmailStatus    = ()  => apiFetch('/api/emails/auth/status/');
export const initiateGmailOAuth= ()  => apiFetch('/api/emails/auth/initiate/');
export const disconnectGmail   = ()  => apiFetch('/api/emails/auth/disconnect/', { method: 'POST' });

// ── Email list & search ───────────────────────────────────────────────────────

export function fetchEmailList(folder = 'INBOX', maxResults = 50, pageToken = null) {
    const p = new URLSearchParams({ folder, max_results: maxResults });
    if (pageToken) p.set('page_token', pageToken);
    return apiFetch(`/api/emails/?${p}`);
}

export function searchEmails(query, maxResults = 50) {
    const p = new URLSearchParams({ q: query, max_results: maxResults });
    return apiFetch(`/api/emails/search/?${p}`);
}

// ── Single email ──────────────────────────────────────────────────────────────

export const fetchEmailDetail = (id) => apiFetch(`/api/emails/${id}/`);

// ── Mutations ─────────────────────────────────────────────────────────────────

export async function sendEmail(payload) {
    if (payload.attachments?.some(a => a instanceof File)) {
        const form = new FormData();
        form.append('to',      JSON.stringify(payload.to));
        form.append('cc',      JSON.stringify(payload.cc  || []));
        form.append('bcc',     JSON.stringify(payload.bcc || []));
        form.append('subject', payload.subject || '');
        form.append('body',    payload.body    || '');
        if (payload.thread_id) form.append('thread_id', payload.thread_id);
        payload.attachments.filter(a => a instanceof File).forEach(f => form.append('attachments', f));
        const res   = await apiClient('/api/emails/send/', {
            method: 'POST',
            body: form,
        });
        if (!res.ok) throw new Error(`Send failed: HTTP ${res.status}`);
        return res.json();
    }
    return apiFetch('/api/emails/send/', {
        method: 'POST',
        body: JSON.stringify({
            to:        payload.to,
            cc:        payload.cc  || [],
            bcc:       payload.bcc || [],
            subject:   payload.subject   || '',
            body:      payload.body      || '',
            thread_id: payload.threadId,
        }),
    });
}

export const markAsRead   = (ids) => apiFetch('/api/emails/modify/', { method: 'POST', body: JSON.stringify({ ids, add_labels: [], remove_labels: ['UNREAD']    }) });
export const markAsUnread = (ids) => apiFetch('/api/emails/modify/', { method: 'POST', body: JSON.stringify({ ids, add_labels: ['UNREAD'], remove_labels: []     }) });
export const starEmail    = (id)  => apiFetch('/api/emails/modify/', { method: 'POST', body: JSON.stringify({ ids: [id], add_labels: ['STARRED'], remove_labels: [] }) });
export const unstarEmail  = (id)  => apiFetch('/api/emails/modify/', { method: 'POST', body: JSON.stringify({ ids: [id], add_labels: [], remove_labels: ['STARRED'] }) });
export const archiveEmail = (id)  => apiFetch('/api/emails/modify/', { method: 'POST', body: JSON.stringify({ ids: [id], add_labels: [], remove_labels: ['INBOX']   }) });
export const trashEmail   = (id)  => apiFetch(`/api/emails/${id}/trash/`, { method: 'POST' });

// ── Attachments ───────────────────────────────────────────────────────────────

export async function downloadAttachment(messageId, attachmentId, filename) {
    const res   = await apiClient(
        `/api/emails/${messageId}/attachments/${attachmentId}/?filename=${encodeURIComponent(filename)}`
    );
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

