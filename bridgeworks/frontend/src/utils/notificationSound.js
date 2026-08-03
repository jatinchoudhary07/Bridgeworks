const SOUND_CATEGORY_TASK_URGENT = 'task_urgent';
const SOUND_CATEGORY_TASK_NORMAL = 'task_normal';
const SOUND_CATEGORY_CHAT = 'chat';
const SOUND_CATEGORY_GENERAL = 'general';
const SOUND_CATEGORY_ASSIGN_BATCH = 'assign_batch';

const VALID_SOUND_CATEGORIES = new Set([
    SOUND_CATEGORY_TASK_URGENT,
    SOUND_CATEGORY_TASK_NORMAL,
    SOUND_CATEGORY_CHAT,
    SOUND_CATEGORY_GENERAL,
    SOUND_CATEGORY_ASSIGN_BATCH,
]);

const VALID_TASK_PRIORITIES = new Set(['low', 'medium', 'high', 'critical']);

const SOUND_FILES_BY_CATEGORY = {
    [SOUND_CATEGORY_TASK_URGENT]: [
        '/sounds/taskurgent.mp3',
        '/sounds/task_urgent.mp3',
        '/sounds/task-urgent.mp3',
        '/sounds/task urgent.mp3',
    ],
    [SOUND_CATEGORY_TASK_NORMAL]: [
        '/sounds/tasknormal.mp3',
        '/sounds/task_normal.mp3',
        '/sounds/task-normal.mp3',
        '/sounds/task normal.mp3',
    ],
    [SOUND_CATEGORY_CHAT]: ['/sounds/chat.mp3'],
    [SOUND_CATEGORY_GENERAL]: ['/sounds/general.mp3'],
};

const FALLBACK_CATEGORIES_BY_CATEGORY = {
    [SOUND_CATEGORY_TASK_URGENT]: [SOUND_CATEGORY_TASK_NORMAL],
    [SOUND_CATEGORY_TASK_NORMAL]: [SOUND_CATEGORY_TASK_URGENT],
    [SOUND_CATEGORY_CHAT]: [SOUND_CATEGORY_GENERAL, SOUND_CATEGORY_TASK_NORMAL],
    [SOUND_CATEGORY_GENERAL]: [SOUND_CATEGORY_CHAT, SOUND_CATEGORY_TASK_NORMAL],
};

const _audioTemplateCache = new Map();
const _audioAvailabilityCache = new Map();
let _audioContext = null;
let _audioPrimed = false;

function _isAutoplayBlockedError(error) {
    const errorName = String(error?.name || '').toLowerCase();
    const errorMessage = String(error?.message || '').toLowerCase();
    return (
        errorName === 'notallowederror'
        || errorMessage.includes('notallowederror')
        || errorMessage.includes('user gesture')
        || errorMessage.includes('allowed to start')
    );
}

export function normalizeTaskPriority(value) {
    const normalized = String(value || '').trim().toLowerCase();
    return VALID_TASK_PRIORITIES.has(normalized) ? normalized : '';
}

export function resolveNotificationSoundCategory(notification) {
    const payload = notification && typeof notification === 'object' ? notification : {};
    const metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {};

    const payloadCategory = String(payload.sound_category || '').trim().toLowerCase();
    if (VALID_SOUND_CATEGORIES.has(payloadCategory)) {
        return payloadCategory;
    }

    const metadataCategory = String(metadata.sound_category || '').trim().toLowerCase();
    if (VALID_SOUND_CATEGORIES.has(metadataCategory)) {
        return metadataCategory;
    }

    const moduleName = String(payload.module || '').trim().toLowerCase();
    if (moduleName === 'tasks') {
        const priority = normalizeTaskPriority(
            payload.task_priority || metadata.task_priority || metadata.priority
        ) || 'medium';
        if (priority === 'high' || priority === 'critical') {
            return SOUND_CATEGORY_TASK_URGENT;
        }
        return SOUND_CATEGORY_TASK_NORMAL;
    }

    if (moduleName === 'my_chats') {
        return SOUND_CATEGORY_CHAT;
    }

    if (moduleName === 'my_meetings') {
        return SOUND_CATEGORY_GENERAL;
    }

    return SOUND_CATEGORY_GENERAL;
}

function _getAudioContext({ createIfMissing = false } = {}) {
    if (typeof window === 'undefined') return null;
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return null;

    if (!_audioContext && createIfMissing) {
        _audioContext = new AudioContextCtor();
    }

    return _audioContext;
}

async function _ensureAudioContextRunning({ createIfMissing = false } = {}) {
    const ctx = _getAudioContext({ createIfMissing });
    if (!ctx) return null;

    if (ctx.state === 'suspended') {
        try {
            await ctx.resume();
        } catch {
            return null;
        }
    }

    if (ctx.state !== 'running') {
        return null;
    }

    return ctx;
}

function _scheduleTone(ctx, startAt, duration, frequency, gainValue) {
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(frequency, startAt);

    gainNode.gain.setValueAtTime(0.0001, startAt);
    gainNode.gain.exponentialRampToValueAtTime(gainValue, startAt + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.start(startAt);
    oscillator.stop(startAt + duration + 0.01);
}

async function _isAudioAssetAvailable(srcPath) {
    if (!srcPath) return false;

    if (_audioAvailabilityCache.get(srcPath) === true) {
        return true;
    }

    try {
        const response = await fetch(srcPath, {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'force-cache',
        });

        if (!response.ok) {
            return false;
        }

        const contentType = String(response.headers.get('content-type') || '').toLowerCase();
        const isAudioLike = contentType.includes('audio/') || contentType.includes('application/octet-stream');
        if (isAudioLike) {
            _audioAvailabilityCache.set(srcPath, true);
        }
        return isAudioLike;
    } catch {
        return false;
    }
}

async function _playSynthFallback(category) {
    const ctx = await _ensureAudioContextRunning();
    if (!ctx) return false;

    const now = ctx.currentTime + 0.02;

    if (category === SOUND_CATEGORY_ASSIGN_BATCH) {
        // Unique ascending four-note arpeggio chime (C5 -> E5 -> G5 -> C6)
        _scheduleTone(ctx, now, 0.12, 523.25, 0.2); // C5
        _scheduleTone(ctx, now + 0.15, 0.12, 659.25, 0.2); // E5
        _scheduleTone(ctx, now + 0.30, 0.12, 783.99, 0.2); // G5
        _scheduleTone(ctx, now + 0.45, 0.20, 1046.50, 0.2); // C6
        return true;
    }

    if (category === SOUND_CATEGORY_TASK_URGENT) {
        _scheduleTone(ctx, now, 0.1, 880, 0.26);
        _scheduleTone(ctx, now + 0.14, 0.1, 980, 0.26);
        _scheduleTone(ctx, now + 0.28, 0.12, 660, 0.22);
        return true;
    }

    if (category === SOUND_CATEGORY_TASK_NORMAL) {
        _scheduleTone(ctx, now, 0.11, 660, 0.2);
        return true;
    }

    if (category === SOUND_CATEGORY_CHAT) {
        _scheduleTone(ctx, now, 0.07, 740, 0.18);
        _scheduleTone(ctx, now + 0.11, 0.09, 620, 0.17);
        return true;
    }

    _scheduleTone(ctx, now, 0.08, 523, 0.15);
    _scheduleTone(ctx, now + 0.1, 0.12, 659, 0.14);
    return true;
}

async function _playAudioFile(srcPath) {
    if (typeof window === 'undefined') {
        throw new Error('Audio playback is not available outside browser context');
    }

    if (!srcPath) {
        throw new Error('Audio source unavailable');
    }

    const isAssetAvailable = await _isAudioAssetAvailable(srcPath);
    if (!isAssetAvailable) {
        throw new Error('Audio asset missing or invalid content type');
    }

    if (!_audioTemplateCache.has(srcPath)) {
        const template = new Audio(srcPath);
        template.preload = 'auto';
        _audioTemplateCache.set(srcPath, template);
    }

    const playbackAudio = _audioTemplateCache.get(srcPath).cloneNode(true);
    playbackAudio.volume = 0.95;

    try {
        await playbackAudio.play();
    } catch (error) {
        throw error;
    }
}

export async function playNotificationSoundCategory(category) {
    const normalizedCategory = VALID_SOUND_CATEGORIES.has(String(category || '').toLowerCase())
        ? String(category).toLowerCase()
        : SOUND_CATEGORY_GENERAL;

    if (normalizedCategory === SOUND_CATEGORY_ASSIGN_BATCH) {
        return _playSynthFallback(SOUND_CATEGORY_ASSIGN_BATCH);
    }

    const categoryOrder = [
        normalizedCategory,
        ...(FALLBACK_CATEGORIES_BY_CATEGORY[normalizedCategory] || []),
        SOUND_CATEGORY_GENERAL,
    ];
    const triedSrc = new Set();

    for (const categoryKey of categoryOrder) {
        const srcCandidates = SOUND_FILES_BY_CATEGORY[categoryKey] || [];
        for (const srcPath of srcCandidates) {
            if (!srcPath || triedSrc.has(srcPath)) continue;
            triedSrc.add(srcPath);

            try {
                await _playAudioFile(srcPath);
                return true;
            } catch (error) {
                // Browser autoplay policy blocks programmatic playback until a gesture.
                // Do not spam retries/fallback URLs or synth in this case.
                if (_isAutoplayBlockedError(error)) {
                    return false;
                }
                continue;
            }
        }
    }

    return _playSynthFallback(normalizedCategory);
}

export async function playNotificationSoundForNotification(notification) {
    const category = resolveNotificationSoundCategory(notification);
    return playNotificationSoundCategory(category);
}

export async function primeNotificationAudio() {
    if (_audioPrimed) {
        return true;
    }

    const ctx = await _ensureAudioContextRunning({ createIfMissing: true });
    if (!ctx) {
        return false;
    }

    try {
        const now = ctx.currentTime + 0.01;
        // Prime the graph with an effectively silent pulse so subsequent playbacks are immediate.
        _scheduleTone(ctx, now, 0.02, 440, 0.00011);
    } catch {
        // No-op; resumed context is enough for most browsers.
    }

    _audioPrimed = true;
    return true;
}

export const NOTIFICATION_SOUND_CATEGORIES = {
    TASK_URGENT: SOUND_CATEGORY_TASK_URGENT,
    TASK_NORMAL: SOUND_CATEGORY_TASK_NORMAL,
    CHAT: SOUND_CATEGORY_CHAT,
    GENERAL: SOUND_CATEGORY_GENERAL,
    ASSIGN_BATCH: SOUND_CATEGORY_ASSIGN_BATCH,
};
