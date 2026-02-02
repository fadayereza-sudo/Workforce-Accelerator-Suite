# Workforce Accelerator - Architecture Blueprint

A Telegram Mini App platform using **Thin-Client, Thick-Backend** architecture. Zero build step. Zero Node.js. Maximum simplicity.

## Core Philosophy

| Principle | Implementation |
|-----------|----------------|
| Zero Build Step | Edit a file, refresh browser, see changes |
| Thin Client | Vanilla JS handles UI state + Telegram SDK only |
| Thick Backend | Python/FastAPI handles all logic, AI, DB, APIs |
| LLM Context Density | Entire UI in ~3 files for full-picture prompts |
| Rich Aesthetics | Premium CSS that rivals React apps |

## Technology Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Database | Supabase (PostgreSQL + Auth + Storage) | Managed, RLS, realtime |
| Backend | **FastAPI (Python)** | Fast, async, type hints, auto-docs |
| Telegram Framework | **python-telegram-bot** or **aiogram** | Native Python, mature |
| Mini App UI | **Vanilla JS (ES6+) + Vanilla CSS** | Zero tooling, instant reload |
| Hosting | Railway / Render / Fly.io | Simple Python deployment |
| Background Jobs | Celery + Redis or APScheduler | Python-native |

## The Golden Rule

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM MINI APP                        │
│                                                              │
│   index.html ──► Contains ALL UI code                       │
│   ├── <style>    Premium CSS (gradients, blur, typography)  │
│   ├── <script>   Vanilla JS (UI state, fetch, Telegram SDK) │
│   └── <body>     Semantic HTML structure                    │
│                                                              │
│   The JS does THREE things only:                            │
│   1. Render UI based on state                               │
│   2. Call backend APIs (fetch)                              │
│   3. Integrate Telegram WebApp SDK                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ fetch('/api/...')
┌─────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                          │
│                                                              │
│   ALL business logic lives here:                            │
│   • User authentication (Telegram initData verification)    │
│   • Database queries (Supabase client)                      │
│   • AI/LLM calls (OpenAI, Anthropic, etc.)                 │
│   • External API integrations                               │
│   • File processing                                         │
│   • Scheduled tasks                                         │
│   • Webhook handlers                                        │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
workforce-accelerator/
│
├── backend/                      # FastAPI application
│   ├── main.py                   # App entry point, mounts routers
│   ├── config.py                 # Environment variables, settings
│   │
│   ├── api/                      # API routes
│   │   ├── __init__.py
│   │   ├── auth.py               # Telegram auth verification
│   │   ├── users.py              # User endpoints
│   │   ├── orgs.py               # Organization endpoints
│   │   └── bots/                 # Bot-specific endpoints
│   │       ├── __init__.py
│   │       ├── hub.py            # Hub bot API
│   │       └── crm.py            # CRM bot API (example)
│   │
│   ├── services/                 # Business logic layer
│   │   ├── __init__.py
│   │   ├── telegram.py           # Telegram bot logic
│   │   ├── ai.py                 # LLM integration
│   │   ├── database.py           # Supabase client wrapper
│   │   └── notifications.py      # Push notifications
│   │
│   ├── models/                   # Pydantic models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── org.py
│   │   └── responses.py          # API response schemas
│   │
│   ├── jobs/                     # Background tasks
│   │   ├── __init__.py
│   │   └── scheduler.py          # APScheduler or Celery tasks
│   │
│   └── requirements.txt          # Python dependencies
│
├── static/                       # Served by FastAPI at /static
│   │
│   ├── mini-apps/                # Each bot's Mini App
│   │   │
│   │   ├── hub/                  # Hub bot Mini App
│   │   │   └── index.html        # ENTIRE app in one file
│   │   │
│   │   ├── crm/                  # CRM bot Mini App
│   │   │   └── index.html        # ENTIRE app in one file
│   │   │
│   │   └── [bot-name]/           # Pattern for new bots
│   │       └── index.html
│   │
│   └── shared/                   # Shared assets (optional)
│       ├── design-system.css     # If you want shared styles
│       └── utils.js              # If you want shared utilities
│
├── supabase/                     # Database configuration
│   ├── migrations/               # SQL migration files
│   └── seed.sql                  # Test data
│
├── .env.example                  # Environment template
├── .env                          # Local environment (gitignored)
└── README.md
```

## Mini App File Structure

Each Mini App is a **single index.html** file containing everything:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>App Name</title>

    <!-- Telegram Web App SDK -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>

    <style>
        /* ═══════════════════════════════════════════════════════════
           DESIGN SYSTEM - Premium aesthetics without React
           ═══════════════════════════════════════════════════════════ */

        :root {
            /* Colors - pulled from Telegram theme when available */
            --tg-theme-bg-color: #ffffff;
            --tg-theme-text-color: #000000;
            --tg-theme-hint-color: #999999;
            --tg-theme-link-color: #2481cc;
            --tg-theme-button-color: #2481cc;
            --tg-theme-button-text-color: #ffffff;

            /* Custom premium colors */
            --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-success: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.08);
            --shadow-elevated: 0 8px 40px rgba(0, 0, 0, 0.12);
            --blur-glass: blur(20px);

            /* Typography */
            --font-primary: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-mono: 'SF Mono', 'Fira Code', monospace;

            /* Spacing */
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;

            /* Transitions */
            --transition-fast: 150ms ease;
            --transition-smooth: 300ms cubic-bezier(0.4, 0, 0.2, 1);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: var(--font-primary);
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Glass morphism card */
        .card {
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: var(--blur-glass);
            border-radius: 16px;
            padding: var(--space-lg);
            box-shadow: var(--shadow-soft);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        /* Premium button */
        .btn-primary {
            background: var(--gradient-primary);
            color: white;
            border: none;
            padding: var(--space-md) var(--space-lg);
            border-radius: 12px;
            font-weight: 600;
            font-size: 16px;
            cursor: pointer;
            transition: transform var(--transition-fast), box-shadow var(--transition-fast);
        }

        .btn-primary:active {
            transform: scale(0.98);
        }

        /* Loading skeleton */
        .skeleton {
            background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
            background-size: 200% 100%;
            animation: skeleton-loading 1.5s infinite;
            border-radius: 8px;
        }

        @keyframes skeleton-loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* Page sections */
        .page { display: none; padding: var(--space-lg); }
        .page.active { display: block; }

        /* ... more styles ... */
    </style>
</head>
<body>
    <!-- ═══════════════════════════════════════════════════════════
         HTML STRUCTURE - Semantic, accessible
         ═══════════════════════════════════════════════════════════ -->

    <div id="app">
        <!-- Loading State -->
        <div id="page-loading" class="page active">
            <div class="skeleton" style="height: 200px; margin-bottom: 16px;"></div>
            <div class="skeleton" style="height: 48px; width: 60%;"></div>
        </div>

        <!-- Main Content -->
        <div id="page-main" class="page">
            <!-- Content rendered by JS -->
        </div>

        <!-- Error State -->
        <div id="page-error" class="page">
            <p>Something went wrong. Please try again.</p>
        </div>
    </div>

    <script>
        /* ═══════════════════════════════════════════════════════════
           APPLICATION LOGIC - Thin client, fetch-driven
           ═══════════════════════════════════════════════════════════ */

        // ─────────────────────────────────────────────────────────────
        // TELEGRAM INTEGRATION
        // ─────────────────────────────────────────────────────────────

        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        // Apply Telegram theme colors to CSS variables
        const applyTelegramTheme = () => {
            const root = document.documentElement;
            if (tg.themeParams) {
                Object.entries(tg.themeParams).forEach(([key, value]) => {
                    root.style.setProperty(`--tg-theme-${key.replace(/_/g, '-')}`, value);
                });
            }
        };
        applyTelegramTheme();
        tg.onEvent('themeChanged', applyTelegramTheme);

        // ─────────────────────────────────────────────────────────────
        // STATE MANAGEMENT (simple reactive pattern)
        // ─────────────────────────────────────────────────────────────

        const state = {
            user: null,
            data: [],
            loading: true,
            error: null,
            currentPage: 'loading'
        };

        const setState = (updates) => {
            Object.assign(state, updates);
            render();
        };

        // ─────────────────────────────────────────────────────────────
        // API LAYER (all calls go through here)
        // ─────────────────────────────────────────────────────────────

        const API_BASE = '/api';

        const api = {
            async fetch(endpoint, options = {}) {
                const response = await fetch(`${API_BASE}${endpoint}`, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': tg.initData,  // Auth header
                        ...options.headers
                    }
                });

                if (!response.ok) {
                    throw new Error(`API Error: ${response.status}`);
                }

                return response.json();
            },

            // Specific endpoints
            getUser: () => api.fetch('/user'),
            getData: () => api.fetch('/data'),
            createItem: (data) => api.fetch('/items', {
                method: 'POST',
                body: JSON.stringify(data)
            }),
        };

        // ─────────────────────────────────────────────────────────────
        // RENDER FUNCTIONS (declarative UI updates)
        // ─────────────────────────────────────────────────────────────

        const showPage = (pageName) => {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${pageName}`)?.classList.add('active');
        };

        const render = () => {
            if (state.loading) {
                showPage('loading');
                return;
            }

            if (state.error) {
                showPage('error');
                return;
            }

            showPage('main');
            renderMainContent();
        };

        const renderMainContent = () => {
            const container = document.getElementById('page-main');
            container.innerHTML = `
                <div class="card">
                    <h1>Welcome, ${state.user?.name || 'User'}</h1>
                    <p>${state.data.length} items loaded</p>
                </div>
            `;
        };

        // ─────────────────────────────────────────────────────────────
        // INITIALIZATION
        // ─────────────────────────────────────────────────────────────

        const init = async () => {
            try {
                const [user, data] = await Promise.all([
                    api.getUser(),
                    api.getData()
                ]);

                setState({ user, data, loading: false });
            } catch (error) {
                console.error('Init failed:', error);
                setState({ error: error.message, loading: false });
            }
        };

        // Start the app
        init();
    </script>
</body>
</html>
```

## Backend Structure

### main.py - Application Entry

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api import auth, users, orgs
from api.bots import hub, crm
from config import settings

app = FastAPI(title="Workforce Accelerator API")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(orgs.router, prefix="/api/orgs", tags=["orgs"])
app.include_router(hub.router, prefix="/api/bots/hub", tags=["hub-bot"])
app.include_router(crm.router, prefix="/api/bots/crm", tags=["crm-bot"])

# Serve Mini Apps (static files)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mini App routes (serve index.html for each bot)
@app.get("/app/{bot_name}")
async def serve_mini_app(bot_name: str):
    return FileResponse(f"static/mini-apps/{bot_name}/index.html")
```

### auth.py - Telegram Authentication

```python
import hashlib
import hmac
from urllib.parse import parse_qs
from fastapi import Header, HTTPException

def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Verify Telegram Mini App initData signature.
    Returns parsed user data if valid.
    """
    parsed = parse_qs(init_data)

    # Extract and remove hash
    received_hash = parsed.pop('hash', [None])[0]
    if not received_hash:
        raise HTTPException(401, "Missing hash")

    # Build data-check-string
    data_check_string = '\n'.join(
        f"{k}={v[0]}" for k, v in sorted(parsed.items())
    )

    # Calculate expected hash
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_hash, expected_hash):
        raise HTTPException(401, "Invalid signature")

    # Parse user JSON
    import json
    user_data = json.loads(parsed.get('user', ['{}'])[0])
    return user_data
```

## Database Schema

Same Supabase PostgreSQL schema as before - organizations, users, memberships, bot licenses. RLS policies enforce data isolation.

```sql
-- Core tables remain the same
-- See original schema for: users, organizations, memberships,
-- bot_registry, org_bot_licenses, bot_member_access, notifications
```

## Development Workflow

### 1. Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Edit Mini App

1. Open `static/mini-apps/[bot]/index.html`
2. Edit HTML/CSS/JS
3. Refresh browser
4. See changes instantly

**No build step. No waiting. No node_modules.**

### 3. Local Tunnel for Telegram

```bash
# Use ngrok, localtunnel, or cloudflared
ngrok http 8000

# Set webhook to: https://your-tunnel.ngrok.io/webhook/[bot-name]
```

## Environment Configuration

```bash
# .env

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Telegram Bots
BOT_HUB_TOKEN=123456:ABC...
BOT_CRM_TOKEN=789012:DEF...

# AI (if using)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Redis (for background jobs)
REDIS_URL=redis://localhost:6379
```

## Adding a New Bot

1. **Create Mini App**: `static/mini-apps/[bot-name]/index.html`
2. **Create API routes**: `backend/api/bots/[bot_name].py`
3. **Add to main.py**: Mount the router
4. **Create DB migration**: If bot needs custom tables
5. **Add bot token**: To `.env`
6. **Done** - no build, no deploy config

## Why This Architecture?

### For Development Speed
- Change CSS → refresh → see it
- Change JS → refresh → see it
- No waiting for webpack/vite/esbuild
- No "module not found" errors
- No dependency hell

### For LLM Collaboration
- Entire UI fits in one prompt
- No jumping between component files
- No import chains to trace
- Claude sees the full picture, every time

### For Production Quality
- FastAPI is battle-tested and fast
- Supabase handles scaling
- Static files are cached efficiently
- No JS bundle size concerns

### For Aesthetics
- CSS can do everything React CSS-in-JS can
- Gradients, animations, blur effects
- Responsive design
- Dark mode via CSS variables
- No runtime style calculation overhead

## What This Architecture Avoids

| Avoided | Why |
|---------|-----|
| Node.js | Python-only backend simplifies deployment |
| npm/pnpm | No package manager for frontend |
| Webpack/Vite/etc | Zero build configuration |
| React/Vue/Svelte | Vanilla JS is enough for Mini Apps |
| TypeScript (frontend) | JSDoc comments if types needed |
| Monorepo tooling | Simple folder structure |
| CSS-in-JS | Native CSS is powerful enough |

## Constraints & Tradeoffs

1. **No component reuse across Mini Apps** - Copy-paste shared styles/utilities (or use shared/*.css)
2. **No static type checking in JS** - Use JSDoc + VS Code for intellisense
3. **Large HTML files** - Acceptable for Mini Apps (typically <500 lines)
4. **No hot module replacement** - Full page refresh (fast enough for Mini Apps)

These tradeoffs are worth it for the simplicity gained.
