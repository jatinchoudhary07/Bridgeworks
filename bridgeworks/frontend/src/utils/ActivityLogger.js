/**
 * ActivityLogger — Frontend event batcher
 * ========================================
 * Queues UI events in memory and flushes them to POST /api/logs/batch:
 *   • every 5 seconds, OR
 *   • when 50 events have accumulated (whichever comes first)
 *
 * Retries once on network failure, then silently drops (never blocks UI).
 *
 * Usage:
 *   import ActivityLogger from '@/utils/ActivityLogger';
 *   ActivityLogger.track('BUTTON_CLICK', 'SubmitLeaveRequest', '/leaves/apply', { formId: 123 });
 */

const FLUSH_INTERVAL_MS = 5_000;
const MAX_QUEUE_SIZE = 50;

// Resolve the Django backend URL the same way apiClient.js does.
// Use VITE_API_URL if set, otherwise '' so the request is sent as a relative
// URL — Vite dev-server proxies /api in local dev, nginx in deployed.
function getBackendUrl() {
    if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
    }
    return '';
}

// Read the JWT access token written by apiClient.js setToken()
function getAccessToken() {
    try {
        return localStorage.getItem('access_token') || null;
    } catch {
        return null;
    }
}

class _ActivityLogger {
    constructor() {
        this._queue = [];
        this._timer = null;
        this._sessionId = this._generateSessionId();
        this._startTimer();
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    /**
     * Queue a single event for async delivery.
     *
     * @param {string} action     - Event name, e.g. 'BUTTON_CLICK'
     * @param {string} component  - Component that fired the event, e.g. 'SubmitLeaveRequest'
     * @param {string} page       - Current page/route, e.g. '/leaves/apply'
     * @param {Object} [metadata] - Optional arbitrary key-value context
     */
    track(action, component, page, metadata = {}) {
        if (!action) return;

        this._queue.push({
            action: String(action).slice(0, 128),
            component: String(component || '').slice(0, 256),
            page: String(page || '').slice(0, 512),
            sessionId: this._sessionId,
            metadata: this._sanitiseMetadata(metadata),
            timestamp: new Date().toISOString(),
        });

        if (this._queue.length >= MAX_QUEUE_SIZE) {
            this._flushImmediate();
        }
    }

    // ── Internal ───────────────────────────────────────────────────────────────

    _startTimer() {
        this._timer = setInterval(() => this._flushImmediate(), FLUSH_INTERVAL_MS);
        // Don't prevent the process from exiting in Node/SSR environments
        if (this._timer?.unref) this._timer.unref();
    }

    _flushImmediate() {
        if (this._queue.length === 0) return;

        const batch = this._queue.splice(0, this._queue.length);
        this._sendWithRetry(batch, 1);
    }

    async _sendWithRetry(events, retriesLeft) {
        try {
            const token = getAccessToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`${getBackendUrl()}/api/logs/batch`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ events }),
                credentials: 'include',
            });

            if (!res.ok && retriesLeft > 0) {
                // Single retry after a short delay
                await this._delay(1_000);
                return this._sendWithRetry(events, retriesLeft - 1);
            }
            // On second failure — silently drop. Never throw.
        } catch (_err) {
            if (retriesLeft > 0) {
                await this._delay(1_000).catch(() => { });
                this._sendWithRetry(events, retriesLeft - 1).catch(() => { });
            }
            // Drop after retry — never surface errors to the user
        }
    }

    _delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    _generateSessionId() {
        try {
            return crypto.randomUUID();
        } catch {
            // Fallback for older environments
            return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        }
    }

    /** Keep metadata a flat/shallow dict and cap total JSON size at 4 KB. */
    _sanitiseMetadata(raw) {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
        const out = {};
        for (const [k, v] of Object.entries(raw)) {
            if (typeof v === 'object' && v !== null) {
                out[k] = JSON.stringify(v).slice(0, 256);
            } else {
                out[k] = v;
            }
        }
        return out;
    }
}

// Singleton — one shared instance across the app
const ActivityLogger = new _ActivityLogger();

export default ActivityLogger;
