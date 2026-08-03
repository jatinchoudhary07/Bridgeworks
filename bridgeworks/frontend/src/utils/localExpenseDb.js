const DB_NAME = 'bridgeworks_expenses_db';
const DB_VERSION = 2;          // bumped: adds mydesk_expenses store
const OVERVIEW_STORE = 'expense_overview';
const MEMBER_DETAIL_STORE = 'member_details';
const MYDESK_EXPENSE_STORE = 'mydesk_expenses'; // personal expense list cache

function openDB() {
    return new Promise((resolve, reject) => {
        if (typeof window === 'undefined' || !window.indexedDB) {
            reject(new Error('IndexedDB is not supported in this environment.'));
            return;
        }

        const request = window.indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(OVERVIEW_STORE)) {
                db.createObjectStore(OVERVIEW_STORE);
            }
            if (!db.objectStoreNames.contains(MEMBER_DETAIL_STORE)) {
                db.createObjectStore(MEMBER_DETAIL_STORE);
            }
            // v2: personal expense list cache
            if (!db.objectStoreNames.contains(MYDESK_EXPENSE_STORE)) {
                db.createObjectStore(MYDESK_EXPENSE_STORE);
            }
        };

        request.onsuccess = (event) => {
            resolve(event.target.result);
        };

        request.onerror = (event) => {
            reject(event.target.error);
        };
    });
}

export async function getCachedOverview(department) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(OVERVIEW_STORE, 'readonly');
            const store = transaction.objectStore(OVERVIEW_STORE);
            const request = store.get(department);
            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to get cached overview:', e);
        return null;
    }
}

export async function setCachedOverview(department, data) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(OVERVIEW_STORE, 'readwrite');
            const store = transaction.objectStore(OVERVIEW_STORE);
            const request = store.put(data, department);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to set cached overview:', e);
    }
}

export async function getCachedMemberDetail(userId, filters) {
    const key = `${userId}_${JSON.stringify(filters || {})}`;
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(MEMBER_DETAIL_STORE, 'readonly');
            const store = transaction.objectStore(MEMBER_DETAIL_STORE);
            const request = store.get(key);
            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to get cached member details:', e);
        return null;
    }
}

export async function setCachedMemberDetail(userId, filters, data) {
    const key = `${userId}_${JSON.stringify(filters || {})}`;
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(MEMBER_DETAIL_STORE, 'readwrite');
            const store = transaction.objectStore(MEMBER_DETAIL_STORE);
            const request = store.put(data, key);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to set cached member details:', e);
    }
}

export async function clearCachedOverview(department) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(OVERVIEW_STORE, 'readwrite');
            const store = transaction.objectStore(OVERVIEW_STORE);
            const request = store.delete(department);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to clear cached overview:', e);
    }
}

export async function clearAllMemberDetailCache() {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(MEMBER_DETAIL_STORE, 'readwrite');
            const store = transaction.objectStore(MEMBER_DETAIL_STORE);
            const request = store.clear();
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (e) {
        console.error('Failed to clear member detail cache:', e);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MyDesk personal expense list cache  (DB v2)
// Key = JSON.stringify(filters) so each timeline/sort combo has its own slot.
// Each record: { results, count, has_more, saved_at }
// ─────────────────────────────────────────────────────────────────────────────

export async function getMyDeskExpenses(key) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(MYDESK_EXPENSE_STORE, 'readonly');
            const store = tx.objectStore(MYDESK_EXPENSE_STORE);
            const req = store.get(key);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => reject(req.error);
        });
    } catch {
        return null;
    }
}

export async function setMyDeskExpenses(key, data) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(MYDESK_EXPENSE_STORE, 'readwrite');
            const store = tx.objectStore(MYDESK_EXPENSE_STORE);
            const req = store.put({ ...data, saved_at: Date.now() }, key);
            req.onsuccess = () => resolve();
            req.onerror = () => reject(req.error);
        });
    } catch {
        // silently ignore — IndexedDB write failure should not break the UI
    }
}

export async function clearMyDeskExpenses(key) {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(MYDESK_EXPENSE_STORE, 'readwrite');
            const store = tx.objectStore(MYDESK_EXPENSE_STORE);
            const req = store.delete(key);
            req.onsuccess = () => resolve();
            req.onerror = () => reject(req.error);
        });
    } catch {
        // ignore
    }
}

export async function clearAllMyDeskExpenses() {
    try {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(MYDESK_EXPENSE_STORE, 'readwrite');
            const store = tx.objectStore(MYDESK_EXPENSE_STORE);
            const req = store.clear();
            req.onsuccess = () => resolve();
            req.onerror = () => reject(req.error);
        });
    } catch {
        // ignore
    }
}

