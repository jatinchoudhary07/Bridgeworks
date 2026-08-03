import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';
import { emitMyDeskNotification } from './mydeskNotifications';

let lastCalendarStatus = { connected: false };
const eventsCacheByRange = new Map();

export async function fetchCalendarStatus(options = {}) {
    const { forceRefresh = false } = options;
    const query = forceRefresh ? `?_=${Date.now()}` : '';
    const response = await apiClient(`${BACKEND_URL}/api/calendar/status/${query}`, {
        credentials: 'include',
    });

    if (response.status === 304) {
        return lastCalendarStatus;
    }

    if (!response.ok) {
        return lastCalendarStatus;
    }

    const data = await response.json().catch(() => ({ connected: false }));
    lastCalendarStatus = data && typeof data === 'object' ? data : { connected: false };
    return lastCalendarStatus;
}

export async function fetchCalendarEvents({ start, end, forceRefresh = false }) {
    const cacheKey = `${start || ''}|${end || ''}`;
    const refreshSuffix = forceRefresh ? `&_=${Date.now()}` : '';
    const response = await apiClient(`${BACKEND_URL}/api/calendar/events/?start=${start}&end=${end}${refreshSuffix}`, {
        credentials: 'include',
    });

    if (response.status === 304) {
        return eventsCacheByRange.get(cacheKey) || [];
    }

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const error = new Error(payload?.error || 'Unable to fetch calendar events.');
        error.status = response.status;
        throw error;
    }

    const payload = await response.json();
    const normalized = Array.isArray(payload) ? payload : [];
    eventsCacheByRange.set(cacheKey, normalized);
    return normalized;
}

export async function createCalendarEvent(payload) {
    try {
        const response = await apiClient(`${BACKEND_URL}/api/calendar/events/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(data?.error || 'Unable to create calendar event.');
            error.status = response.status;
            throw error;
        }

        emitMyDeskNotification('Calendar event created.', 'success');
        return data;
    } catch (error) {
        emitMyDeskNotification(error?.message || 'Unable to create calendar event.', 'error');
        throw error;
    }
}

export async function scheduleCalendarMeeting(payload) {
    try {
        const response = await apiClient(`${BACKEND_URL}/api/calendar/schedule/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(data?.error || 'Unable to schedule meeting.');
            error.status = response.status;
            error.payload = data;
            throw error;
        }

        emitMyDeskNotification('Meeting scheduled.', 'success');
        return data;
    } catch (error) {
        emitMyDeskNotification(error?.message || 'Unable to schedule meeting.', 'error');
        throw error;
    }
}

export async function deleteCalendarEvent(eventId) {
    try {
        const response = await apiClient(`${BACKEND_URL}/api/calendar/events/${eventId}/`, {
            method: 'DELETE',
            credentials: 'include',
        });

        if (!response.ok && response.status !== 204) {
            const data = await response.json().catch(() => ({}));
            const error = new Error(data?.error || 'Unable to delete event.');
            error.status = response.status;
            throw error;
        }

        emitMyDeskNotification('Calendar event deleted.', 'success');
        return true;
    } catch (error) {
        emitMyDeskNotification(error?.message || 'Unable to delete event.', 'error');
        throw error;
    }
}

export async function syncCalendarRange({ start, end }) {
    try {
        const response = await apiClient(`${BACKEND_URL}/api/calendar/sync/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end }),
        });

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const error = new Error(payload?.error || 'Unable to sync calendar.');
            error.status = response.status;
            throw error;
        }

        emitMyDeskNotification('Calendar synced.', 'success');
        return response.json().catch(() => ({}));
    } catch (error) {
        emitMyDeskNotification(error?.message || 'Unable to sync calendar.', 'error');
        throw error;
    }
}

export async function fetchTeamMembers() {
    const response = await apiClient(`${BACKEND_URL}/api/team/members/`, { credentials: 'include' });
    if (!response.ok) {
        return [];
    }
    const data = await response.json();
    return Array.isArray(data) ? data : [];
}

export async function redirectToGoogleAuth() {
    try {
        const response = await apiClient(`${BACKEND_URL}/api/calendar/auth/`, { credentials: 'include' });
        const data = await response.json().catch(() => ({}));
        if (response.ok && data?.auth_url) {
            window.location.href = data.auth_url;
            return;
        }
    } catch (error) {
        emitMyDeskNotification(error?.message || 'Unable to connect Google Calendar.', 'error');
    }

    window.location.href = `${BACKEND_URL}/accounts/google/login/`;
}