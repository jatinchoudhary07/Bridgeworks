/**
 * useActivityTracking
 * ====================
 * Drop-in hook that automatically captures all user activity events via
 * global listeners. NO onClick or useEffect should be added to individual
 * page components — all tracking lives here.
 *
 * Covered events (17 total):
 *   1.  PAGE_VIEW            — every React Router location change
 *   2.  BUTTON_CLICK         — any button / a / role=button click
 *   3.  TAB_SWITCH           — tab pills and sub-nav tabs inside pages
 *   4.  DROPDOWN_CHANGE      — native <select> and MUI/custom listbox selections
 *   5.  MODAL_OPEN/CLOSE     — dialogs, drawers, modals via MutationObserver
 *   6.  ACCORDION_EXPAND/COLLAPSE — details, [aria-expanded] toggles
 *   7.  SEARCH               — debounced (1500ms) search input events
 *   8.  FILTER_CHANGE        — date pickers, checkboxes inside filter containers
 *   9.  SCROLL_DEPTH         — 25/50/75/100% milestones per page visit
 *   10. EXTERNAL_LINK_CLICK  — links leaving the current domain
 *   11. COPY                 — Ctrl+C / copy button events
 *   12. FILE_DOWNLOAD        — <a download> / data-download clicks
 *   13. SORT                 — sortable table column header clicks
 *   14. PAGINATION           — pagination control clicks
 *   15. NAV_CLICK            — sidebar/nav link clicks
 *   16. TAB_HIDDEN/VISIBLE   — browser tab visibility changes
 *   17. LOGIN/LOGOUT         — auth events via window custom events
 *
 * Usage (AppLayout.jsx — already wired):
 *   useActivityTracking();
 */

import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import ActivityLogger from '../utils/ActivityLogger';

// ── Helpers ───────────────────────────────────────────────────────────────────

function labelFromPath(pathname) {
    if (!pathname || pathname === '/') return 'Home';
    return pathname
        .replace(/^\//, '')
        .split('/')
        .map((seg) => seg.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()))
        .join(' › ');
}

/** Always read the live path so non-location-dependent listeners stay accurate. */
function getPage() {
    return window.location.pathname;
}

/**
 * Resolve a component label for a clicked element.
 * Priority: data-log-id → aria-label → inner text (40 chars) → id → warn + "unknown-button"
 */
function resolveButtonLabel(el) {
    if (el.dataset?.logId) return el.dataset.logId.slice(0, 40);
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim().slice(0, 40);
    const text = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
    if (text) return text;
    if (el.id) return el.id.slice(0, 40);
    console.warn('[ActivityLogger] BUTTON_CLICK fired with no component label', el);
    return 'unknown-button';
}

/** Walk up the DOM looking for a matching ancestor within maxDepth steps. */
function findAncestor(target, predicate, maxDepth = 6) {
    let el = target;
    let depth = 0;
    while (el && el !== document.body && depth < maxDepth) {
        if (predicate(el)) return el;
        el = el.parentElement;
        depth++;
    }
    return null;
}

// ── Element classifiers ───────────────────────────────────────────────────────

function isTabElement(el) {
    if (el.getAttribute?.('role') === 'tab') return true;
    if (el.classList?.contains('tab') || el.classList?.contains('nav-tab') || el.classList?.contains('tab-item')) return true;
    if ('tab' in (el.dataset || {}) || 'tabId' in (el.dataset || {})) return true;
    return false;
}

function isNavElement(el) {
    if ('navItem' in (el.dataset || {})) return true;
    if (el.tagName === 'A' && el.closest('aside, nav, [data-nav-item]')) return true;
    return false;
}

function isPaginationElement(el) {
    if ('pagination' in (el.dataset || {})) return true;
    const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
    if (/go to (next|prev|previous|first|last) page|page \d/.test(ariaLabel)) return true;
    if (el.closest('.MuiTablePagination-root, .pagination, [data-pagination]')) return true;
    return false;
}

function isSortElement(el) {
    return el.tagName === 'TH' && (
        'sort' in (el.dataset || {}) ||
        el.classList?.contains('sortable') ||
        el.hasAttribute('aria-sort')
    );
}

function isDownloadElement(el) {
    if (el.tagName === 'A' && el.hasAttribute('download')) return true;
    if ('download' in (el.dataset || {}) || el.classList?.contains('download-btn')) return true;
    return false;
}

function isExternalLink(el) {
    if (el.tagName !== 'A') return false;
    const href = el.href || '';
    if (!href.startsWith('http')) return false;
    try { return new URL(href).hostname !== window.location.hostname; } catch { return false; }
}

function isAccordionToggle(el) {
    if (el.tagName === 'SUMMARY') return true;
    if (el.hasAttribute('aria-expanded') && (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button')) return true;
    if (el.classList?.contains('accordion-item')) return true;
    return false;
}

function isClickableButton(el) {
    if (!el || el === document) return false;
    if (el.dataset?.track === 'false') return false;
    if (el.tagName === 'BUTTON' || el.tagName === 'A') return true;
    const role = el.getAttribute('role');
    if (role && ['button', 'link', 'menuitem', 'checkbox', 'radio'].includes(role)) return true;
    if ('track' in (el.dataset || {})) return true;
    return false;
}

// ── Modal helpers ─────────────────────────────────────────────────────────────

function getModalLabel(el) {
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
        const labelEl = document.getElementById(labelledBy);
        if (labelEl) return (labelEl.textContent || '').trim().slice(0, 80);
    }
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel.slice(0, 80);
    const heading = el.querySelector('h1, h2, h3, h4, [class*="title"], [class*="Title"]');
    if (heading) return (heading.textContent || '').trim().slice(0, 80);
    return el.id || 'modal';
}

function isModalEl(el) {
    const role = el.getAttribute?.('role');
    if (role === 'dialog' || role === 'alertdialog') return true;
    if (el.classList?.contains('modal') || el.classList?.contains('drawer')) return true;
    return false;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export default function useActivityTracking() {
    const location = useLocation();
    const prevPath = useRef(null);
    const pageEnteredAt = useRef(Date.now());
    const scrollMilestonesHit = useRef(new Set());
    const modalOpenTimes = useRef(new Map());

    // ── 1. PAGE_VIEW ──────────────────────────────────────────────────────────
    useEffect(() => {
        const path = location.pathname;
        if (path === prevPath.current) return;

        const now = Date.now();
        const timeOnPreviousPage_ms = prevPath.current !== null ? now - pageEnteredAt.current : undefined;

        ActivityLogger.track('PAGE_VIEW', labelFromPath(path), path, {
            previousPage: prevPath.current || undefined,
            timeOnPreviousPage_ms,
            search: location.search || undefined,
        });

        prevPath.current = path;
        pageEnteredAt.current = now;
        scrollMilestonesHit.current = new Set(); // reset milestones for new page
    }, [location]);

    // ── 2–17. All global listeners in a single persistent effect ─────────────
    useEffect(() => {

        // ── Click dispatcher (events: 2, 3, 6, 10, 12, 13, 14, 15) ───────────
        function handleClick(e) {
            try {
                const target = e.target;
                const page = getPage();

                // 3. TAB_SWITCH — checked before BUTTON_CLICK to avoid double-firing
                const tabEl = findAncestor(target, isTabElement, 5);
                if (tabEl) {
                    const toTab = tabEl.dataset?.tabId
                        || tabEl.getAttribute('aria-label')
                        || (tabEl.textContent || '').trim().slice(0, 40);
                    ActivityLogger.track('TAB_SWITCH', toTab || 'unknown-tab', page, {
                        toTab: toTab || '',
                        tabGroupId: tabEl.closest('[id]')?.id || tabEl.parentElement?.id || '',
                    });
                    return;
                }

                // 15. NAV_CLICK
                const navEl = findAncestor(target, isNavElement, 4);
                if (navEl) {
                    const label = navEl.dataset?.logId
                        || navEl.getAttribute('aria-label')
                        || (navEl.textContent || '').trim().slice(0, 40);
                    ActivityLogger.track('NAV_CLICK', label || 'nav-item', page, {
                        destination: navEl.getAttribute('href') || navEl.dataset?.href || '',
                    });
                    return;
                }

                // 12. FILE_DOWNLOAD
                const dlEl = findAncestor(target, isDownloadElement, 4);
                if (dlEl) {
                    const href = dlEl.getAttribute('href') || '';
                    const ext = href.includes('.') ? href.split('.').pop().toLowerCase().slice(0, 10) : '';
                    const label = dlEl.dataset?.logId
                        || dlEl.getAttribute('aria-label')
                        || (dlEl.textContent || '').trim().slice(0, 40)
                        || href.split('/').pop().slice(0, 40);
                    ActivityLogger.track('FILE_DOWNLOAD', label || 'download', page, {
                        fileExtension: ext,
                        triggeredBy: dlEl.tagName === 'A' ? 'link' : 'button',
                    });
                    return;
                }

                // 10. EXTERNAL_LINK_CLICK
                const extEl = findAncestor(target, isExternalLink, 3);
                if (extEl) {
                    let domain = '';
                    try { domain = new URL(extEl.href).hostname; } catch { /* ignore */ }
                    const label = extEl.dataset?.logId
                        || extEl.getAttribute('aria-label')
                        || (extEl.textContent || '').trim().slice(0, 40);
                    ActivityLogger.track('EXTERNAL_LINK_CLICK', label || 'external-link', page, { domain });
                    return;
                }

                // 13. SORT
                const sortEl = findAncestor(target, isSortElement, 3);
                if (sortEl) {
                    const col = (sortEl.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
                    ActivityLogger.track('SORT', col || 'column', page, {
                        direction: sortEl.getAttribute('aria-sort') || 'none',
                    });
                    return;
                }

                // 14. PAGINATION
                const pageEl = findAncestor(target, isPaginationElement, 5);
                if (pageEl) {
                    const al = (pageEl.getAttribute('aria-label') || '').toLowerCase();
                    const direction = /next/.test(al) ? 'next' : /prev/.test(al) ? 'prev' : 'page';
                    const pageNumber = parseInt(pageEl.textContent || '', 10) || undefined;
                    ActivityLogger.track('PAGINATION', 'PaginationControl', page, { direction, pageNumber });
                    return;
                }

                // 6. ACCORDION_EXPAND / ACCORDION_COLLAPSE
                const accordionEl = findAncestor(target, isAccordionToggle, 4);
                if (accordionEl) {
                    // aria-expanded reflects the CURRENT state before toggle
                    const currentlyExpanded = accordionEl.getAttribute('aria-expanded') === 'true'
                        || (accordionEl.tagName === 'SUMMARY' && accordionEl.closest('details')?.open);
                    const label = accordionEl.dataset?.logId
                        || accordionEl.getAttribute('aria-label')
                        || (accordionEl.textContent || '').trim().slice(0, 60);
                    ActivityLogger.track(
                        currentlyExpanded ? 'ACCORDION_COLLAPSE' : 'ACCORDION_EXPAND',
                        label || 'panel',
                        page,
                        { panelId: accordionEl.id || accordionEl.closest('[id]')?.id || '' },
                    );
                    return;
                }

                // 2. BUTTON_CLICK (catch-all for remaining clickable elements)
                const btnEl = findAncestor(target, isClickableButton, 5);
                if (btnEl) {
                    const label = resolveButtonLabel(btnEl);
                    ActivityLogger.track('BUTTON_CLICK', label, page, {
                        tagName: btnEl.tagName,
                        href: btnEl.tagName === 'A' ? (btnEl.getAttribute('href') || '') : undefined,
                        elementId: btnEl.id || undefined,
                    });
                }
            } catch (_) { /* never crash the UI */ }
        }

        // ── 4a. DROPDOWN_CHANGE — MUI/custom listbox (role="option" clicks) ───
        function handleMuiDropdown(e) {
            try {
                const optionEl = findAncestor(e.target, (el) => el.getAttribute?.('role') === 'option', 4);
                if (!optionEl) return;
                const listbox = optionEl.closest('[role="listbox"]');
                if (!listbox) return;
                const labelledBy = listbox.getAttribute('aria-labelledby');
                const ownerLabel = labelledBy ? (document.getElementById(labelledBy)?.textContent || '').trim() : '';
                const name = listbox.dataset?.logId || listbox.id || ownerLabel || 'dropdown';
                const selectedLabel = (optionEl.textContent || '').trim().slice(0, 80);
                ActivityLogger.track('DROPDOWN_CHANGE', name, getPage(), {
                    selectedValue: optionEl.getAttribute('data-value') || optionEl.getAttribute('value') || selectedLabel,
                    selectedLabel,
                });
            } catch (_) { /* never crash */ }
        }

        // ── 4b & 8. DROPDOWN_CHANGE (native select) + FILTER_CHANGE ──────────
        function handleChange(e) {
            try {
                const target = e.target;
                const page = getPage();

                if (target.tagName === 'SELECT') {
                    const name = target.dataset?.logId || target.name || target.id || target.getAttribute('aria-label') || 'select';
                    ActivityLogger.track('DROPDOWN_CHANGE', name, page, {
                        selectedValue: target.value,
                        selectedLabel: (target.options[target.selectedIndex]?.text || '').slice(0, 80),
                    });
                    return;
                }

                // FILTER_CHANGE — date / checkbox / radio inside a filter container
                if (['date', 'checkbox', 'radio'].includes(target.type)
                    && target.closest('[data-filter-group], .filter-bar, .filters, [data-filter]')) {
                    const name = target.dataset?.filter || target.name || target.id || target.getAttribute('aria-label') || 'filter';
                    ActivityLogger.track('FILTER_CHANGE', name, page, {
                        filterType: target.type,
                        hasValue: target.type === 'checkbox' ? target.checked : Boolean(target.value),
                    });
                }
            } catch (_) { /* never crash */ }
        }

        // ── 7. SEARCH — debounced 1500ms ──────────────────────────────────────
        const searchTimers = new Map();
        function handleSearchInput(e) {
            try {
                const target = e.target;
                const isSearch = target.type === 'search'
                    || target.getAttribute('role') === 'searchbox'
                    || 'search' in (target.dataset || {})
                    || /search/i.test(target.placeholder || '');
                if (!isSearch) return;
                clearTimeout(searchTimers.get(target));
                searchTimers.set(target, setTimeout(() => {
                    searchTimers.delete(target);
                    const name = target.dataset?.logId || target.id || target.name || target.getAttribute('aria-label') || 'search';
                    ActivityLogger.track('SEARCH', name, getPage(), { queryLength: target.value.length });
                }, 1500));
            } catch (_) { /* never crash */ }
        }

        // ── 9. SCROLL_DEPTH — 25/50/75/100% milestones ───────────────────────
        function handleScroll() {
            try {
                const doc = document.documentElement;
                const pct = ((doc.scrollTop + doc.clientHeight) / doc.scrollHeight) * 100;
                const hits = scrollMilestonesHit.current;
                for (const m of [25, 50, 75, 100]) {
                    if (pct >= m && !hits.has(m)) {
                        hits.add(m);
                        ActivityLogger.track('SCROLL_DEPTH', 'PageScroll', getPage(), { milestone: `${m}%` });
                    }
                }
            } catch (_) { /* never crash */ }
        }

        // ── 11. COPY ──────────────────────────────────────────────────────────
        function handleCopy(e) {
            try {
                const textLength = window.getSelection()?.toString().length ?? 0;
                const target = e.target;
                const context = target?.dataset?.logId
                    || target?.closest?.('[data-log-id]')?.dataset?.logId
                    || 'keyboard-shortcut';
                ActivityLogger.track('COPY', context, getPage(), { textLength });
            } catch (_) { /* never crash */ }
        }

        // ── 16. TAB_HIDDEN / TAB_VISIBLE ──────────────────────────────────────
        let tabHiddenAt = null;
        function handleVisibility() {
            try {
                const page = getPage();
                if (document.visibilityState === 'hidden') {
                    tabHiddenAt = Date.now();
                    ActivityLogger.track('TAB_HIDDEN', 'BrowserTab', page, {});
                } else {
                    const hiddenFor_ms = tabHiddenAt !== null ? Date.now() - tabHiddenAt : undefined;
                    tabHiddenAt = null;
                    ActivityLogger.track('TAB_VISIBLE', 'BrowserTab', page, { hiddenFor_ms });
                }
            } catch (_) { /* never crash */ }
        }

        // ── 17. LOGIN / LOGOUT ────────────────────────────────────────────────
        function handleLogin(e) {
            ActivityLogger.track('LOGIN', 'AuthSystem', getPage(), {
                method: e?.detail?.method || 'password',
            });
        }
        function handleLogout() {
            ActivityLogger.track('LOGOUT', 'AuthSystem', getPage(), { method: 'token-refresh' });
        }

        // ── 5. MODAL_OPEN / MODAL_CLOSE via MutationObserver ─────────────────
        const openTimes = modalOpenTimes.current;
        const observer = new MutationObserver((mutations) => {
            try {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType !== 1) continue;
                        const modal = isModalEl(node)
                            ? node
                            : node.querySelector?.('[role="dialog"],[role="alertdialog"],.modal,.drawer');
                        if (!modal) continue;
                        const label = getModalLabel(modal);
                        openTimes.set(label, Date.now());
                        const triggeredBy = (document.activeElement?.getAttribute('aria-label')
                            || document.activeElement?.textContent?.trim().slice(0, 40)
                            || '');
                        ActivityLogger.track('MODAL_OPEN', label, getPage(), { triggeredBy });
                    }
                    for (const node of mutation.removedNodes) {
                        if (node.nodeType !== 1) continue;
                        const modal = isModalEl(node)
                            ? node
                            : node.querySelector?.('[role="dialog"],[role="alertdialog"],.modal,.drawer');
                        if (!modal) continue;
                        const label = getModalLabel(modal);
                        const durationOpen_ms = openTimes.has(label) ? Date.now() - openTimes.get(label) : undefined;
                        openTimes.delete(label);
                        ActivityLogger.track('MODAL_CLOSE', label, getPage(), { durationOpen_ms });
                    }
                }
            } catch (_) { /* never crash */ }
        });
        observer.observe(document.body, { childList: true, subtree: true });

        // ── Register all listeners ─────────────────────────────────────────────
        document.addEventListener('click', handleClick, { passive: true });
        document.addEventListener('click', handleMuiDropdown, { passive: true });
        document.addEventListener('change', handleChange, { passive: true });
        document.addEventListener('input', handleSearchInput, { passive: true });
        document.addEventListener('copy', handleCopy, { passive: true });
        document.addEventListener('visibilitychange', handleVisibility);
        window.addEventListener('scroll', handleScroll, { passive: true });
        window.addEventListener('auth_login', handleLogin);
        window.addEventListener('auth_logout', handleLogout);

        return () => {
            document.removeEventListener('click', handleClick);
            document.removeEventListener('click', handleMuiDropdown);
            document.removeEventListener('change', handleChange);
            document.removeEventListener('input', handleSearchInput);
            document.removeEventListener('copy', handleCopy);
            document.removeEventListener('visibilitychange', handleVisibility);
            window.removeEventListener('scroll', handleScroll);
            window.removeEventListener('auth_login', handleLogin);
            window.removeEventListener('auth_logout', handleLogout);
            observer.disconnect();
            searchTimers.forEach((t) => clearTimeout(t));
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // intentionally stable — listeners read live state via getPage() / refs
}
