# Workforce Accelerator - Architecture Blueprint

A unified Telegram Mini App with multiple AI agents using **Thin-Client, Thick-Backend** architecture. One app. Many agents. Zero build step. Zero Node.js. Maximum simplicity.

## Core Philosophy

| Principle | Implementation |
|-----------|----------------|
| Zero Build Step | Edit a file, refresh browser, see changes |
| Thin Client | Vanilla JS handles UI state + Telegram SDK only |
| Thick Backend | Python/FastAPI handles all logic, AI, DB, APIs |
| Agent Isolation | Agents in separate folders; one failure doesn't break others |
| Single Entry Point | One bot, one mini app - agents shown based on user access |
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
│                  ONE TELEGRAM MINI APP                       │
│                                                              │
│   index.html ──► Contains ALL UI code                       │
│   ├── <style>    Premium CSS (gradients, blur, typography)  │
│   ├── <script>   Vanilla JS (UI state, fetch, Telegram SDK) │
│   └── <body>     Semantic HTML structure                    │
│                                                              │
│   User identified by Telegram ID                            │
│   ├── Fetches accessible agents from backend               │
│   ├── Renders agent cards based on permissions             │
│   └── Routes interactions to appropriate agent              │
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
│   • Agent routing and access control                        │
│   • Database queries (Supabase - single database)          │
│   • AI/LLM calls per agent (OpenAI, Anthropic, etc.)       │
│   • External API integrations (social media, CRM, etc.)    │
│   • Scheduled tasks per agent                               │
│   • Webhook handlers                                        │
│   • Notification dispatch to main chat                      │
│                                                              │
│   Agents organized by function:                             │
│   ├── agents/social_media/   (Instagram, Twitter, etc.)    │
│   ├── agents/sales/           (Lead gen, CRM, outreach)    │
│   └── agents/customer_service/ (Support, ticketing)        │
│                                                              │
│   Each agent is isolated - failures don't cascade          │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
workforce-accelerator/
│
├── backend/                      # FastAPI application
│   ├── main.py                   # App entry point, mounts all routers
│   ├── config.py                 # Environment variables, settings
│   │
│   ├── api/                      # API routes
│   │   ├── __init__.py
│   │   ├── auth.py               # Telegram auth verification
│   │   ├── users.py              # User endpoints
│   │   ├── orgs.py               # Organization endpoints
│   │   └── bots/                 # Main bot endpoints
│   │       ├── __init__.py
│   │       └── hub.py            # Main org bot API
│   │
│   ├── agents/                   # Agent modules (isolated)
│   │   ├── __init__.py
│   │   │
│   │   ├── social_media/         # Social media agents
│   │   │   ├── __init__.py
│   │   │   ├── api.py            # API endpoints
│   │   │   ├── service.py        # Business logic
│   │   │   ├── models.py         # Pydantic models
│   │   │   └── tasks.py          # Background jobs
│   │   │
│   │   ├── sales/                # Sales agents
│   │   │   ├── __init__.py
│   │   │   ├── api.py            # API endpoints
│   │   │   ├── service.py        # Business logic
│   │   │   ├── models.py         # Pydantic models
│   │   │   └── tasks.py          # Background jobs
│   │   │
│   │   └── customer_service/     # Customer service agents
│   │       ├── __init__.py
│   │       ├── api.py            # API endpoints
│   │       ├── service.py        # Business logic
│   │       ├── models.py         # Pydantic models
│   │       └── tasks.py          # Background jobs
│   │
│   ├── services/                 # Shared services layer
│   │   ├── __init__.py
│   │   ├── telegram.py           # Telegram bot logic (main bot)
│   │   ├── ai.py                 # LLM integration (shared)
│   │   ├── database.py           # Supabase client wrapper
│   │   └── notifications.py      # Notifications to main chat
│   │
│   ├── models/                   # Shared Pydantic models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── org.py
│   │   ├── membership.py
│   │   └── responses.py          # API response schemas
│   │
│   ├── jobs/                     # Shared background tasks
│   │   ├── __init__.py
│   │   └── scheduler.py          # APScheduler or Celery tasks
│   │
│   └── requirements.txt          # Python dependencies
│
├── static/                       # Served by FastAPI at /static
│   │
│   ├── mini-app/                 # Single Mini App
│   │   └── index.html            # ENTIRE app in one file
│   │                             # Shows agents based on user access
│   │
│   └── shared/                   # Shared assets (optional)
│       ├── design-system.css     # If you want shared styles
│       └── utils.js              # If you want shared utilities
│
├── supabase/                     # Single database configuration
│   ├── migrations/               # SQL migration files
│   └── seed.sql                  # Test data
│
├── .env.example                  # Environment template
├── .env                          # Local environment (gitignored)
└── README.md
```

## Mini App File Structure

The **single Mini App** is one `index.html` file containing everything. It identifies users by their Telegram ID and displays only the agents they have access to:

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
            agents: [],        // Agents user has access to
            currentAgent: null,
            agentData: {},
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
            getAccessibleAgents: () => api.fetch('/agents/accessible'),  // Agents user can access
            getAgentData: (agentId) => api.fetch(`/agents/${agentId}/data`),
            sendAgentAction: (agentId, action, data) => api.fetch(`/agents/${agentId}/actions`, {
                method: 'POST',
                body: JSON.stringify({ action, data })
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

            // Render agent cards based on user access
            const agentCards = state.agents.map(agent => `
                <div class="card agent-card" onclick="openAgent('${agent.id}')">
                    <h3>${agent.name}</h3>
                    <p>${agent.description}</p>
                    <span class="badge">${agent.category}</span>
                </div>
            `).join('');

            container.innerHTML = `
                <div class="header">
                    <h1>Welcome, ${state.user?.first_name || 'User'}</h1>
                    <p>Your Workforce Accelerator Agents</p>
                </div>
                <div class="agent-grid">
                    ${agentCards || '<p>No agents available</p>'}
                </div>
            `;
        };

        // ─────────────────────────────────────────────────────────────
        // INITIALIZATION
        // ─────────────────────────────────────────────────────────────

        const init = async () => {
            try {
                // Fetch user info and accessible agents
                // User identified by Telegram ID from initData
                const [user, agents] = await Promise.all([
                    api.getUser(),
                    api.getAccessibleAgents()  // Returns only agents user has access to
                ]);

                setState({ user, agents, loading: false });
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
from fastapi.responses import FileResponse

from api import auth, users, orgs
from api.bots import hub
from agents.social_media import api as social_media_api
from agents.sales import api as sales_api
from agents.customer_service import api as customer_service_api
from config import settings

app = FastAPI(title="Workforce Accelerator API")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core API routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(orgs.router, prefix="/api/orgs", tags=["orgs"])
app.include_router(hub.router, prefix="/api/bots/hub", tags=["main-bot"])

# Agent API routes (isolated by category)
app.include_router(social_media_api.router, prefix="/api/agents/social-media", tags=["social-media"])
app.include_router(sales_api.router, prefix="/api/agents/sales", tags=["sales"])
app.include_router(customer_service_api.router, prefix="/api/agents/customer-service", tags=["customer-service"])

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Single Mini App entry point
@app.get("/app")
async def serve_mini_app():
    """Serves the single Mini App that displays agents based on user access"""
    return FileResponse("static/mini-app/index.html")

# Agent access endpoint
@app.get("/api/agents/accessible")
async def get_accessible_agents(current_user: User = Depends(get_current_user)):
    """Returns agents the current user has access to based on their org membership"""
    # Business logic to determine which agents user can access
    # Based on Telegram ID, org membership, and permissions
    pass
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

Single Supabase PostgreSQL database shared by all agents. Core tables: organizations, users, memberships, agent access. RLS policies enforce data isolation between organizations.

```sql
-- Core tables:
-- • users - User profiles (linked to Telegram ID)
-- • organizations - Organization details
-- • memberships - User-org relationships with roles
-- • agents - Agent registry (social_media, sales, customer_service)
-- • org_agent_access - Which orgs have which agents enabled
-- • agent_member_permissions - User-level agent access within orgs
-- • notifications - Notification queue for main chat
-- • [agent-specific tables] - Each agent can have its own tables
```

**Key principles:**
- One database for all agents
- Agent-specific data in separate tables with agent_id foreign key
- RLS policies ensure org-level data isolation
- Agent failures isolated at application layer, not database layer

## Development Workflow

### 1. Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Edit Mini App

1. Open `static/mini-app/index.html`
2. Edit HTML/CSS/JS
3. Refresh browser
4. See changes instantly

**No build step. No waiting. No node_modules.**

### 3. Edit Agent Logic

1. Navigate to `backend/agents/[category]/`
2. Edit `api.py`, `service.py`, or `models.py`
3. FastAPI auto-reloads
4. Test agent endpoint

**Agent isolation means bugs stay contained.**

### 4. Local Tunnel for Telegram

```bash
# Use ngrok, localtunnel, or cloudflared
ngrok http 8000

# Set webhook to: https://your-tunnel.ngrok.io/webhook/hub
# Only ONE webhook needed for main bot
```

## Environment Configuration

```bash
# .env

# Supabase (single database for all agents)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Telegram (single main bot)
BOT_TOKEN=123456:ABC...
BOT_USERNAME=workforce_accelerator_bot

# AI (shared by all agents)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# External APIs (per agent needs)
INSTAGRAM_API_KEY=...
TWITTER_API_KEY=...
SALESFORCE_API_KEY=...

# Redis (for background jobs)
REDIS_URL=redis://localhost:6379
```

## Adding a New Agent

1. **Create agent folder**: `backend/agents/[agent_name]/`
2. **Create agent modules**:
   - `api.py` - FastAPI router with endpoints
   - `service.py` - Business logic (isolated)
   - `models.py` - Pydantic models
   - `tasks.py` - Background jobs (if needed)
3. **Add to main.py**: Import and mount the agent router
4. **Create DB migration**: If agent needs custom tables
5. **Update Mini App**: Add agent card/UI in `static/mini-app/index.html` (optional, if needs custom UI)
6. **Configure access**: Set up agent permissions in database
7. **Done** - Agent is isolated, failure won't break other agents

**No separate bot needed. No separate mini app. No cluttered UX.**

## Why This Architecture?

### For Development Speed
- Change CSS → refresh → see it
- Change JS → refresh → see it
- No waiting for webpack/vite/esbuild
- No "module not found" errors
- No dependency hell

### For Agent Isolation
- Each agent in its own folder
- Agent failures don't cascade
- Deploy/update agents independently
- Easy to add/remove agents
- Clear separation of concerns

### For User Experience
- Single bot = no clutter
- Single mini app = consistent interface
- Agents shown based on permissions
- Notifications all go to one chat
- No context switching between bots

### For LLM Collaboration
- Entire UI fits in one prompt
- No jumping between component files
- No import chains to trace
- Agent code is self-contained
- Claude sees the full picture, every time

### For Production Quality
- FastAPI is battle-tested and fast
- Supabase handles scaling
- Static files are cached efficiently
- No JS bundle size concerns
- Agent isolation = better reliability

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
| React/Vue/Svelte | Vanilla JS is enough for Mini App |
| TypeScript (frontend) | JSDoc comments if types needed |
| Multiple bots | Single bot = cleaner UX, no fragmentation |
| Multiple mini apps | Single app shows agents contextually |
| Microservices | Monolithic Python app with isolated agents |
| Monorepo tooling | Simple folder structure |
| CSS-in-JS | Native CSS is powerful enough |

## Constraints & Tradeoffs

1. **Single Mini App grows over time** - As agents are added, the HTML file grows. Mitigate with lazy loading or conditional rendering
2. **No static type checking in JS** - Use JSDoc + VS Code for intellisense
3. **Agents share Python process** - One agent's memory leak could affect others. Mitigate with monitoring and resource limits
4. **No hot module replacement** - Full page refresh (fast enough for Mini App)
5. **Agent UI all in one file** - Different agent UIs are conditionally rendered in the same HTML. Keep organized with clear sections

These tradeoffs are worth it for the simplicity, consistency, and user experience gained.

## Agent Isolation Strategy

While agents share the same Python process and database, isolation is achieved through:

1. **Folder structure** - Clear boundaries in codebase
2. **Error handling** - Try-except blocks prevent cascading failures
3. **Separate routers** - Each agent has its own FastAPI router
4. **Permission checks** - Access control at API level
5. **Database naming** - Agent-specific tables clearly prefixed/namespaced
6. **Monitoring** - Per-agent metrics and logging
7. **Background jobs** - Isolated task queues per agent (optional)

This provides **logical isolation** without the overhead of microservices.

## Caching Architecture

Two-layer in-memory caching eliminates redundant database queries and makes the app feel instant. No Redis — just Python `cachetools.TTLCache` on the backend and a simple JS cache object on the frontend.

### Layer 1: Backend (Server-Side)

All caching goes through `backend/services/cache.py`. It provides named **cache pools**, each with a max size and TTL appropriate for how frequently that data changes.

#### Cache Pools

| Pool | TTL | Max Size | What's Cached |
|------|-----|----------|---------------|
| `auth` | 60s | 512 | User ID lookups by `telegram_id`, membership/role checks |
| `org` | 120s | 256 | Org details, invite codes, member lists, membership requests, billing |
| `catalog` | 120s | 256 | Products, bots registry |
| `plans` | 600s | 32 | Subscription plans (rarely change) |
| `analytics` | 30s | 256 | Team/agent analytics, dashboards (changes frequently) |
| `reports` | 60s | 128 | Activity reports |

#### API: `cache_get`, `cache_set`, `cache_delete`, `cache_invalidate`

```python
from services.cache import cache_get, cache_set, cache_delete, cache_invalidate

# Read from cache
cached = cache_get("org", f"org_details:{org_id}")
if cached is not None:
    return cached

# Fetch from DB, then cache
result = db.table("organizations").select("*").eq("id", org_id).single().execute()
cache_set("org", f"org_details:{org_id}", result.data)

# Invalidate after mutation
cache_delete("org", f"org_details:{org_id}")

# Invalidate by prefix (e.g., all keys starting with "requests:abc")
cache_invalidate("org", f"requests:{org_id}")
```

#### Auth Caching Pattern

Every request requires two DB queries for auth: user lookup + membership check. These are cached via helper functions so endpoints don't repeat this work.

**Hub** (`hub.py`) uses sync helpers:
```python
def _cached_get_user_id(telegram_id: int) -> str:
    """Cache user ID lookup. Used by all auth helpers."""

def _cached_verify_admin(telegram_id: int, org_id: str) -> str:
    """Verify admin role, return user_id. Cached."""

def _cached_verify_member(telegram_id: int, org_id: str) -> tuple:
    """Verify membership, return (user_id, role). Cached."""
```

**Lead Agent** and **Reports** (`lead_agent.py`, `reports.py`) use async helpers:
```python
async def verify_org_member(user_telegram_id: int, org_id: str) -> tuple[str, str]:
    """Verify membership, return (user_id, role). Cached."""

async def verify_org_admin(user_telegram_id: int, org_id: str) -> str:
    """Verify admin role, return user_id. Cached."""
```

All helpers use the `auth` cache pool with key patterns `user:{telegram_id}` and `membership:{user_id}:{org_id}`.

#### Cache Key Convention

Keys are scoped by entity and org/user ID to avoid cross-org leakage:

```
user:{telegram_id}              → user UUID
membership:{user_id}:{org_id}   → {role: "admin"|"member"}
org_details:{org_id}            → OrgDetails object
invite:{org_id}                 → InviteCode object
members:{org_id}                → List[Member]
requests:{org_id}:{status}      → List[MembershipRequest]
products:{org_id}               → List[Product]
team_analytics:{org_id}:{period} → TeamAnalytics
agent_analytics:{org_id}:{period} → AgentAnalytics
billing:{org_id}                → BillingOverview
la_dashboard:{org_id}           → LeadAgentDashboard
latest_reports:{org_id}:{period} → ReportSummaryResponse
active_plans                    → List[SubscriptionPlan]
bots:active                     → List[dict]
```

#### When Adding a New Endpoint

1. **GET endpoints** — Check cache before querying DB. Cache the result after fetching.
2. **POST/PUT/PATCH/DELETE endpoints** — Call `cache_delete()` or `cache_invalidate()` for any keys affected by the mutation.
3. **Auth** — Use the cached auth helpers (`_cached_verify_admin`, `verify_org_member`, etc.) instead of inline user+membership queries.

```python
# Template for a new cached GET endpoint
@router.get("/orgs/{org_id}/things")
async def list_things(org_id: str, x_telegram_init_data: str = Header(...)):
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)        # Step 1: cached auth

    cache_key = f"things:{org_id}"                   # Step 2: check cache
    cached = cache_get("org", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()                        # Step 3: fetch from DB
    result = db.table("things").select("*").eq("org_id", org_id).execute()

    cache_set("org", cache_key, result.data)         # Step 4: store in cache
    return result.data


# Template for a mutation endpoint
@router.post("/orgs/{org_id}/things")
async def create_thing(org_id: str, data: ThingCreate, x_telegram_init_data: str = Header(...)):
    tg_user = get_telegram_user(x_telegram_init_data)
    _cached_verify_admin(tg_user.id, org_id)

    db = get_supabase_admin()
    result = db.table("things").insert({...}).execute()

    cache_delete("org", f"things:{org_id}")          # Invalidate the list cache
    return result.data[0]
```

#### What NOT to Cache

- **Telegram initData verification** — HMAC check must run every request (security)
- **Mutation responses** — POST/PUT/PATCH/DELETE results are not cached
- **File exports** — CSV exports, one-off downloads
- **AI-generated content** — Call scripts, insights (already stored in DB)
- **Background task results** — Scheduler outputs

### Layer 2: Frontend (Client-Side)

Both mini-apps maintain a JS cache object that stores API responses with per-key TTLs. This eliminates re-fetching when users navigate between sections.

#### Hub Cache (`static/mini-apps/hub/index.html`)

```javascript
const cache = {
    data: {},
    timestamps: {},
    ttls: {
        orgDetails: 120000,     // 2 min
        inviteCode: 120000,
        members: 60000,         // 1 min
        requests: 30000,        // 30s
        bots: 300000,           // 5 min
        teamAnalytics: 30000,
        agentAnalytics: 30000,
        reports: 60000,
        billing: 60000,
        products: 120000,
        plans: 600000           // 10 min
    },
    get(key) { /* returns data if within TTL, else null */ },
    set(key, value) { /* stores data + timestamp */ },
    invalidate(key) { /* deletes single key */ },
    invalidatePrefix(prefix) { /* deletes keys matching prefix */ },
    invalidateAll() { /* clears everything */ }
};
```

#### Lead Agent Cache (`static/mini-apps/lead-agent/index.html`)

```javascript
const cache = {
    timestamps: {},
    ttls: {
        products: 120000,       // 2 min - rarely changes
        prospects: 30000,       // 30s - changes frequently
        dashboard: 30000,
        searches: 60000,
        journal: 30000,
        prospect: 30000
    },
    isValid(key) { /* checks if key is within its TTL */ },
    invalidate(key) { /* deletes key timestamp + data */ },
    invalidatePrefix(prefix) { /* batch invalidation */ }
};
```

#### Frontend Cache Rules

1. **Before every API GET call** — check `cache.get(key)`. If valid, use cached data and skip the fetch.
2. **After every successful fetch** — call `cache.set(key, data)`.
3. **After every mutation** (create, update, delete) — call `cache.invalidate(key)` for affected data so the next navigation triggers a fresh fetch.
4. **Smart parallel fetching** — When loading a dashboard section that needs multiple data sources, only fetch what's missing from cache:
   ```javascript
   const cachedMembers = cache.get('members');
   const cachedBots = cache.get('bots');
   const fetches = [];
   if (!cachedMembers) fetches.push(api.getMembers(orgId));
   if (!cachedBots) fetches.push(api.getBots());
   const results = await Promise.all(fetches);
   // Merge cached + fresh data
   ```
