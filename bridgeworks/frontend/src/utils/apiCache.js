/**
 * apiCache.js — Lightweight in-memory API cache with TTL.
 *
 * Features:
 *  - In-memory cache (fast, no serialisation overhead)
 *  - Per-entry TTL (default 60 s for list endpoints)
 *  - Stale-while-revalidate: returns cached data immediately,
 *    triggers a background refresh so the next render is fresh.
 *  - Manual invalidation by prefix.
 */

const cache = new Map(); // key → { data, ts, ttl }

/**
 * Set an entry in the cache.
 * @param {string} key
 * @param {*} data
 * @param {number} ttlMs  Time-to-live in milliseconds (default 60 s)
 */
export function cacheSet(key, data, ttlMs = 60_000) {
    cache.set(key, { data, ts: Date.now(), ttl: ttlMs });
}

/**
 * Get an entry. Returns { data, stale } or null.
 * stale = true when the entry is older than its TTL but not yet evicted.
 */
export function cacheGet(key) {
    const entry = cache.get(key);
    if (!entry) return null;
    const age = Date.now() - entry.ts;
    if (age > entry.ttl * 3) {
        // Hard-expire after 3× TTL
        cache.delete(key);
        return null;
    }
    return { data: entry.data, stale: age > entry.ttl };
}

/**
 * Invalidate all cache entries whose keys start with `prefix`.
 */
export function cacheInvalidate(prefix) {
    for (const key of cache.keys()) {
        if (key.startsWith(prefix)) cache.delete(key);
    }
}

/**
 * cachedFetch — wraps an async fetcher function with caching.
 *
 * Usage:
 *   const data = await cachedFetch('my-cache-key', () => apiFetch(url), { ttl: 30_000 });
 *
 * @param {string} key        Cache key (should be unique per URL + params)
 * @param {Function} fetcher  Async function that returns the data
 * @param {object} opts
 * @param {number}  opts.ttl        TTL in ms (default 60 s)
 * @param {Function} opts.onStale   Called with stale data while fetching fresh (optional)
 * @returns {Promise<*>}  Fresh or cached data
 */
export async function cachedFetch(key, fetcher, { ttl = 60_000, onStale } = {}) {
    const cached = cacheGet(key);

    if (cached && !cached.stale) {
        // Cache hit, not stale — return immediately
        return cached.data;
    }

    if (cached && cached.stale && onStale) {
        // Stale-while-revalidate: surface the stale data NOW,
        // then kick off a background refresh.
        onStale(cached.data);
        // Don't await — let it update asynchronously
        fetcher().then(fresh => {
            cacheSet(key, fresh, ttl);
        }).catch(() => { /* silent — stale data is still usable */ });
        return cached.data;
    }

    // Cache miss or stale without onStale callback — fetch fresh
    const fresh = await fetcher();
    cacheSet(key, fresh, ttl);
    return fresh;
}
