/**
 * Apex Solutions — Shared Core JS
 *
 * Common utilities for all Telegram Mini Apps:
 * - Telegram SDK initialization
 * - API client with auth headers
 * - Client-side cache manager
 * - Page navigation
 * - Haptic feedback helpers
 */

// ─────────────────────────────────────────────────────────────────────────
// TELEGRAM SDK
// ─────────────────────────────────────────────────────────────────────────

/**
 * Initialize the Telegram WebApp SDK and apply theme.
 * @returns {object} The Telegram WebApp instance
 */
function initTelegram() {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    // Apply Telegram theme variables to CSS
    const applyTheme = () => {
        const root = document.documentElement;
        if (tg.themeParams) {
            Object.entries(tg.themeParams).forEach(([key, value]) => {
                const cssVar = `--tg-theme-${key.replace(/_/g, '-')}`;
                root.style.setProperty(cssVar, value);
            });
        }
    };
    applyTheme();
    tg.onEvent('themeChanged', applyTheme);

    return tg;
}


// ─────────────────────────────────────────────────────────────────────────
// API CLIENT
// ─────────────────────────────────────────────────────────────────────────

/**
 * Create an API client with Telegram auth.
 * @param {string} baseUrl - API base URL (e.g. '/api/apps/workforce-accelerator')
 * @param {object} tg - Telegram WebApp instance
 * @returns {object} API client with fetch method
 */
function createApiClient(baseUrl, tg) {
    return {
        async fetch(endpoint, options = {}) {
            const url = `${baseUrl}${endpoint}`;

            const res = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': tg.initData,
                    ...options.headers
                }
            });

            if (!res.ok) {
                const errorText = await res.text();
                let error;
                try {
                    error = JSON.parse(errorText);
                } catch {
                    error = { detail: errorText || 'Request failed' };
                }

                // Handle FastAPI validation errors (422)
                if (Array.isArray(error.detail)) {
                    const messages = error.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
                    throw new Error(messages);
                }

                throw new Error(error.detail || `Error ${res.status}`);
            }

            return res.json();
        },

        async get(endpoint) {
            return this.fetch(endpoint);
        },

        async post(endpoint, body) {
            return this.fetch(endpoint, {
                method: 'POST',
                body: JSON.stringify(body)
            });
        },

        async patch(endpoint, body) {
            return this.fetch(endpoint, {
                method: 'PATCH',
                body: JSON.stringify(body)
            });
        },

        async put(endpoint, body) {
            return this.fetch(endpoint, {
                method: 'PUT',
                body: JSON.stringify(body)
            });
        },

        async del(endpoint) {
            return this.fetch(endpoint, { method: 'DELETE' });
        }
    };
}


// ─────────────────────────────────────────────────────────────────────────
// CACHE MANAGER
// ─────────────────────────────────────────────────────────────────────────

/**
 * Create a client-side cache manager with per-key TTLs.
 * @param {object} ttls - Map of key prefix to TTL in ms (e.g. { products: 120000 })
 * @param {number} defaultTtl - Default TTL if key prefix not found (ms)
 * @returns {object} Cache manager
 */
function createCacheManager(ttls = {}, defaultTtl = 60000) {
    return {
        _data: {},
        _timestamps: {},
        _ttls: ttls,

        _getTtl(key) {
            const prefix = key.split('_')[0].split(':')[0];
            return this._ttls[prefix] || defaultTtl;
        },

        get(key) {
            const ts = this._timestamps[key];
            if (ts && (Date.now() - ts) < this._getTtl(key)) {
                return this._data[key];
            }
            return null;
        },

        isValid(key) {
            const ts = this._timestamps[key];
            return ts && (Date.now() - ts) < this._getTtl(key);
        },

        set(key, value) {
            this._data[key] = value;
            this._timestamps[key] = Date.now();
        },

        invalidate(key) {
            delete this._data[key];
            delete this._timestamps[key];
        },

        invalidatePrefix(prefix) {
            Object.keys(this._timestamps).forEach(k => {
                if (k.startsWith(prefix)) {
                    delete this._data[k];
                    delete this._timestamps[k];
                }
            });
        },

        invalidateAll() {
            this._data = {};
            this._timestamps = {};
        }
    };
}


// ─────────────────────────────────────────────────────────────────────────
// PAGE NAVIGATION
// ─────────────────────────────────────────────────────────────────────────

/**
 * Create a page navigator with back button support.
 * @param {object} config
 * @param {object} config.tg - Telegram WebApp instance
 * @param {string[]} config.rootPages - Pages that reset nav history
 * @param {Function} [config.onNavigate] - Callback after navigation
 * @returns {object} Navigator with showPage(), goBack()
 */
function createNavigator(config) {
    const { tg, rootPages = [], onNavigate } = config;
    const history = [];

    function showPage(pageName, { pushHistory = true } = {}) {
        const currentPage = document.querySelector('.page.active')?.id?.replace('page-', '');

        if (rootPages.includes(pageName)) {
            history.length = 0;
        } else if (pushHistory && currentPage && currentPage !== pageName) {
            history.push(currentPage);
        }

        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(`page-${pageName}`);
        if (target) target.classList.add('active');

        if (history.length > 0) {
            tg.BackButton.show();
        } else {
            tg.BackButton.hide();
        }

        if (onNavigate) onNavigate(pageName);
    }

    tg.BackButton.onClick(() => {
        if (history.length > 0) {
            const prev = history.pop();
            showPage(prev, { pushHistory: false });
        }
    });

    return { showPage, history };
}


// ─────────────────────────────────────────────────────────────────────────
// HAPTIC FEEDBACK
// ─────────────────────────────────────────────────────────────────────────

/**
 * Trigger haptic feedback if available.
 * @param {'success'|'warning'|'error'|'selection'} type
 */
function haptic(type) {
    const hf = window.Telegram?.WebApp?.HapticFeedback;
    if (!hf) return;

    if (type === 'selection') {
        hf.selectionChanged();
    } else {
        hf.notificationOccurred(type);
    }
}


// ─────────────────────────────────────────────────────────────────────────
// MODAL HELPERS
// ─────────────────────────────────────────────────────────────────────────

/**
 * Open a modal overlay.
 * @param {string} id - Modal element ID
 */
function openModal(id) {
    document.getElementById(id)?.classList.add('active');
}

/**
 * Close a modal overlay.
 * @param {string} id - Modal element ID
 */
function closeModal(id) {
    document.getElementById(id)?.classList.remove('active');
}


// ─────────────────────────────────────────────────────────────────────────
// FORMATTING HELPERS
// ─────────────────────────────────────────────────────────────────────────

/**
 * Format a number as currency.
 * @param {number} amount
 * @param {string} currency - 3-letter currency code
 * @returns {string}
 */
function formatCurrency(amount, currency = 'USD') {
    try {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(amount);
    } catch {
        return `${currency} ${amount}`;
    }
}

/**
 * Format a date relative to now (e.g. "2 hours ago").
 * @param {string|Date} dateStr
 * @returns {string}
 */
function timeAgo(dateStr) {
    const now = new Date();
    const date = new Date(dateStr);
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}
