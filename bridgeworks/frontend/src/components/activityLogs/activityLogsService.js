import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';

/**
 * Fetch the current user's own activity logs.
 * Maps to GET /api/logs/me
 */
export async function fetchMyLogs({ from, to, action, source = 'frontend', page = 1, limit = 25 } = {}) {
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (action) params.set('action', action);
    if (source) params.set('source', source);
    params.set('page', String(page));
    params.set('limit', String(limit));

    const res = await apiClient(`/api/logs/me?${params.toString()}`, {
        credentials: 'include',
    });
    if (!res.ok) throw new Error(`Failed to fetch logs (${res.status})`);
    return res.json(); // { count, next, previous, results }
}

/**
 * Fetch all users' logs (HR view).
 * Maps to GET /api/logs/hr/logs
 */
export async function fetchHRLogs({ userId, from, to, action, component, search, page = 1, limit = 25 } = {}) {
    const params = new URLSearchParams();
    if (userId) params.set('userId', userId);
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (action) params.set('action', action);
    if (component) params.set('component', component);
    if (search) params.set('search', search);
    params.set('page', String(page));
    params.set('limit', String(limit));

    const res = await apiClient(`/api/logs/hr/logs?${params.toString()}`, {
        credentials: 'include',
    });
    if (!res.ok) throw new Error(`Failed to fetch HR logs (${res.status})`);
    return res.json();
}

/**
 * Trigger a streamed CSV export download for HR logs.
 * Opens the URL directly so the browser handles the file download.
 */
export function exportHRLogs({ userId, from, to, action, component, search } = {}) {
    const params = new URLSearchParams();
    if (userId) params.set('userId', userId);
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (action) params.set('action', action);
    if (component) params.set('component', component);
    if (search) params.set('search', search);

    // We need the auth token in the request. Use apiClient to fetch the stream
    // then trigger a blob download — works for streamed responses too.
    return apiClient(`/api/logs/hr/export?${params.toString()}`, {
        credentials: 'include',
    }).then(async (res) => {
        if (!res.ok) throw new Error(`Export failed (${res.status})`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `activity_logs_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    });
}
