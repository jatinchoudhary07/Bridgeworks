export const pad2 = (value) => String(value).padStart(2, '0');

export const toDateKey = (dateObj) => {
    if (!(dateObj instanceof Date) || Number.isNaN(dateObj.getTime())) return '';
    return `${dateObj.getFullYear()}-${pad2(dateObj.getMonth() + 1)}-${pad2(dateObj.getDate())}`;
};

export const dateKeyToLocalDate = (dateKey) => {
    if (!dateKey || !/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) return null;
    const [year, month, day] = dateKey.split('-').map(Number);
    return new Date(year, month - 1, day);
};

export const monthRangeKeys = (monthDate) => {
    const start = toDateKey(new Date(monthDate.getFullYear(), monthDate.getMonth(), 1));
    const end = toDateKey(new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0));
    return { start, end };
};

const LEAVE_REGEX = /\b(leave|wfh|vacation|casual|sick|earned)\b/i;

export const inferEventType = (event) => {
    const rawType = String(event?.event_type || '').toLowerCase();
    const text = `${event?.title || ''} ${event?.description || ''}`;

    if (rawType === 'task' || rawType === 'deadline') return 'task';
    if (rawType === 'call') return 'meeting';
    if (rawType === 'meeting') return 'meeting';
    if (LEAVE_REGEX.test(text) || rawType === 'leave') return 'leave';
    if (String(event?.source || '').toLowerCase() === 'task') return 'task';
    return 'meeting';
};

export const eventToDateKey = (event) => {
    const value = event?.start;
    if (!value) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
    const date = new Date(value);
    return toDateKey(date);
};

export const groupEventsByDate = (events = []) => {
    return events.reduce((accumulator, event) => {
        const dateKey = eventToDateKey(event);
        if (!dateKey) return accumulator;

        if (!accumulator[dateKey]) {
            accumulator[dateKey] = [];
        }

        accumulator[dateKey].push({
            ...event,
            calendarType: inferEventType(event),
        });

        return accumulator;
    }, {});
};

export const sortEventsForDay = (events = []) => {
    return [...events].sort((a, b) => {
        const aTime = new Date(a.start).getTime();
        const bTime = new Date(b.start).getTime();

        if (Number.isNaN(aTime) && Number.isNaN(bTime)) return 0;
        if (Number.isNaN(aTime)) return -1;
        if (Number.isNaN(bTime)) return 1;
        return aTime - bTime;
    });
};

export const formatEventTime = (start) => {
    if (!start) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(start)) return 'All day';

    const date = new Date(start);
    if (Number.isNaN(date.getTime())) return '';

    return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
    });
};