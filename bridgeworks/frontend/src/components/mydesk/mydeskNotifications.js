export const MYDESK_NOTIFY_EVENT = 'mydesk:notify';

export function emitMyDeskNotification(message, severity = 'success') {
    if (!message || typeof window === 'undefined') return;
    window.dispatchEvent(new CustomEvent(MYDESK_NOTIFY_EVENT, {
        detail: {
            message: String(message),
            severity: severity === 'error' ? 'error' : 'success',
        },
    }));
}
