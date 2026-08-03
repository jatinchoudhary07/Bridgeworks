(function() {
    const CONFIG = {
        API_URL: 'https://bridgeworks-8ba1.onrender.com/api/v1/pixel/track/', // Backend Server
        PARAM_KEYS: ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid', 'gclid', 'ttclid', 'epik', 'sclid'],
        STORAGE_KEY: 'shori_tracking_data'  // renamed from bridgeworks_tracking_data
    };

    function getQueryParams() {
        const params = new URLSearchParams(window.location.search);
        const data = {};
        CONFIG.PARAM_KEYS.forEach(key => {
            const val = params.get(key);
            if (val) data[key] = val;
        });
        return data;
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function generateSessionId() {
        return 'sess_' + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
    }

    function getOrCreateSessionId(stored) {
        return (stored && stored.sessionId) || generateSessionId();
    }

    function getOrgId() {
        try {
            // 1. Try document.currentScript
            const currentScript = document.currentScript;
            if (currentScript) {
                const dataOrg = currentScript.getAttribute('data-org');
                if (dataOrg) return dataOrg;
                const src = currentScript.getAttribute('src');
                if (src) {
                    const url = new URL(src, window.location.href);
                    const org = url.searchParams.get('org') || url.searchParams.get('org_id');
                    if (org) return org;
                }
            }
            
            // 2. Try selector for data-org
            const dataScript = document.querySelector('script[data-org]');
            if (dataScript) {
                return dataScript.getAttribute('data-org');
            }
            
            // 3. Scan all script tags for bridgeworks-pixel
            const scripts = document.getElementsByTagName('script');
            for (let i = 0; i < scripts.length; i++) {
                const src = scripts[i].getAttribute('src');
                if (src && (src.includes('bridgeworks-pixel') || src.includes('bridgeworks-pixel.js'))) {
                    const dataOrg = scripts[i].getAttribute('data-org');
                    if (dataOrg) return dataOrg;
                    
                    const url = new URL(src, window.location.href);
                    const org = url.searchParams.get('org') || url.searchParams.get('org_id');
                    if (org) return org;
                }
            }
        } catch (e) {
            console.debug('Shori Pixel: error getting org_id dynamically:', e);
        }
        return null;
    }

    function track() {
        // 1. Get Org ID dynamically
        const orgId = getOrgId();
        if (!orgId) {
            console.debug('Shori Pixel: org_id not found in script tag, relying on backend resolution.');
        }

        // 2. Get incoming URL params
        const newParams = getQueryParams();

        // 3. Load persistent session from localStorage
        let stored = {};
        try {
            stored = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEY) || '{}');
        } catch (e) {}

        // 4. Merge new params into stored (new params on this page win)
        const mergedParams = { ...stored.params, ...newParams };

        // 5. Get or create session ID
        const sessionId = getOrCreateSessionId(stored);

        // 6. Check if a cart token just appeared (user added to cart on a previous page
        //    and this is a new page load after that event)
        const currentCartToken = getCookie('cart') || null;
        const lastCartToken = stored.lastCartToken || null;
        const cartTokenIsNew = currentCartToken && currentCartToken !== lastCartToken;

        const trackingPayload = {
            org_id: orgId,
            session_id: sessionId,
            cart_token: currentCartToken,
            url: window.location.href,
            referrer: document.referrer,
            ...mergedParams
        };

        // 7. Persist session to localStorage (always — so next page sees it)
        localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify({
            sessionId: sessionId,
            params: mergedParams,
            lastCartToken: currentCartToken || lastCartToken,
            lastUpdate: Date.now()
        }));

        // 8. Decide whether to fire a pixel POST:
        //    - First visit (no stored sessionId)
        //    - New UTM params on this page (user arrived via a new ad click)
        //    - Cart token just appeared (user added to cart on prev page, now on next page)
        const shouldFire = Object.keys(newParams).length > 0 || !stored.sessionId || cartTokenIsNew;

        if (shouldFire) {
            fetch(CONFIG.API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(trackingPayload),
                keepalive: true
            }).catch(err => console.debug('Shori Pixel Error:', err));
        }

        // 9. If a cart token just appeared on this page load, ALSO patch existing
        //    session rows to backfill the cart_token onto them. This ensures the
        //    webhook's cart_token fallback lookup works even for the initial page-load
        //    pixel events that were created before the cart existed.
        if (cartTokenIsNew) {
            fetch(CONFIG.API_URL, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    org_id: orgId,
                    session_id: sessionId,
                    cart_token: currentCartToken
                }),
                keepalive: true
            }).catch(err => console.debug('Shori Cart Patch Error:', err));
        }

        // 10. Inject session into Shopify cart + forms (for Buy Now / Express Checkout)
        injectSessionIntoShopify(orgId, sessionId);
    }

    function injectSessionIntoShopify(orgId, sessionId) {
        // 10A. Write shori_session_id into Shopify cart attributes (silent background call).
        //      This is what flows into order.note_attributes and is read by the webhook.
        fetch('/cart/update.js', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ attributes: { 'shori_session_id': sessionId } })
        }).catch(e => console.debug('Cart inject error:', e));

        // 10B. Inject hidden input into "Buy Now" / "Add to Cart" forms
        //      so the session travels with direct form submissions too.
        const forms = document.querySelectorAll('form[action^="/cart/add"], form[action^="/checkout"]');
        forms.forEach(form => {
            if (!form.querySelector('input[name="attributes[shori_session_id]"]')) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'attributes[shori_session_id]';
                input.value = sessionId;
                form.appendChild(input);
            }
        });

        // 10C. Intercept AJAX fetch calls to /cart/add.js (themes that use fetch-based ATC).
        //      When a product is added to cart, re-inject the session and trigger a PATCH
        //      to link the newly-created cart token back to all prior pixel events.
        if (!window._shoriCartIntercepted) {
            window._shoriCartIntercepted = true;
            const _origFetch = window.fetch;
            window.fetch = function(url, opts) {
                const result = _origFetch.apply(this, arguments);
                if (typeof url === 'string' && url.includes('/cart/add')) {
                    result.then(() => {
                        // Wait briefly for the cart cookie to be set, then fire
                        setTimeout(() => {
                            const newToken = getCookie('cart');
                            if (!newToken) return;

                            // Re-inject session into cart attributes
                            injectSessionIntoShopify(orgId, sessionId);

                            // If this is the first time we see this cart token, PATCH
                            // to backfill it onto all prior session pixel events
                            let stored = {};
                            try { stored = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEY) || '{}'); } catch (e) {}
                            if (newToken !== stored.lastCartToken) {
                                fetch(CONFIG.API_URL, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        org_id: orgId,
                                        session_id: sessionId,
                                        cart_token: newToken
                                    }),
                                    keepalive: true
                                }).catch(() => {});

                                // Update localStorage with the new cart token
                                stored.lastCartToken = newToken;
                                localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(stored));
                            }
                        }, 600);
                    }).catch(() => {});
                }
                return result;
            };
        }
    }

    // Run on load
    if (document.readyState === 'complete') {
        track();
    } else {
        window.addEventListener('load', track);
    }
})();
