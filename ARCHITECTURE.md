# Apex Solutions — App Ecosystem Architecture

A multi-app business platform delivered through one Telegram bot with a shared database. Apps are logically isolated within a single Python process — new apps plug in without touching existing code.

## Ecosystem Overview

```
One Telegram Bot → One Backend → One Database → Multiple Apps → Multiple AI Agents

Currently:
  Workforce Accelerator (App #1)
    ├── B2B Lead Agent      — AI-powered prospect scraping, insights, call scripts
    ├── Timekeeping Agent   — Smart follow-up scheduling from journal entries
    └── Report Agent        — LLM-generated activity and performance reports

Future:
  6 more apps, each with ~7 AI agents
```

## Core Philosophy

| Principle | Implementation |
|-----------|----------------|
| Zero Build Step | Vanilla JS + CSS in single HTML files — edit, refresh, done |
| Thin Client | JS handles UI state + Telegram SDK only |
| Thick Backend | Python/FastAPI handles all logic, AI, DB, APIs |
| App Isolation | Each app in its own directory; one failure doesn't break others |
| Convention over Config | Apps auto-discovered by directory structure |
| LLM Context Density | Entire app UI in one file for full-picture AI prompts |

## Technology Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Database | Supabase PostgreSQL | Managed, RLS, realtime |
| Backend | FastAPI (Python) | Fast, async, type hints, auto-docs |
| Frontend | Vanilla JS + CSS | Zero tooling, instant reload |
| AI | OpenAI GPT-4o / GPT-4o-mini | Two-tier: cheap extraction → strategic insights |
| Caching | cachetools.TTLCache (in-memory) | No Redis dependency |
| Scheduling | Custom unified scheduler | Condition-checked polling, zero idle cost |

## Directory Structure

```
apex-solutions/
├── backend/
│   ├── main.py                          # Entry point — auto-discovers apps, starts scheduler
│   ├── config.py                        # Environment variables
│   │
│   ├── core/                            # Platform-level shared code
│   │   ├── __init__.py
│   │   ├── auth.py                      # Telegram initData HMAC verification + cached helpers
│   │   ├── database.py                  # Supabase client factory
│   │   ├── cache.py                     # TTLCache pools + dynamic pool registration
│   │   ├── notifications.py             # Telegram notification dispatch
│   │   ├── task_logger.py               # Generic bot task logging
│   │   ├── scheduler.py                 # Unified task scheduler with condition checks
│   │   │
│   │   ├── models/                      # Core Pydantic models (shared across apps)
│   │   │   ├── user.py                  # TelegramUser, User, UserCreate
│   │   │   ├── org.py                   # Organization, OrgCreate, InviteCode, OrgDetails
│   │   │   ├── membership.py            # MembershipRequest, Member, BotAccess
│   │   │   ├── billing.py              # SubscriptionPlan, OrgSubscription, Invoice
│   │   │   └── reports.py              # ActivityReport, BotTaskLogEntry
│   │   │
│   │   └── hub/                         # Platform-level API routes
│   │       ├── router.py               # /me, /orgs, /members, /bots, invite flow
│   │       └── billing.py              # /plans, /billing
│   │
│   ├── apps/                            # App ecosystem
│   │   ├── __init__.py                  # AppManifest, AgentManifest, discover_apps()
│   │   ├── _template/                   # Copy to create a new app
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── models.py
│   │   │   ├── services.py
│   │   │   └── agents/
│   │   │       └── _template/
│   │   │
│   │   └── workforce_accelerator/       # APP #1
│   │       ├── __init__.py              # APP_ID, get_manifest()
│   │       ├── config.py               # App-specific constants
│   │       ├── router.py               # Products, analytics, activity tracking
│   │       ├── models.py               # Product, Prospect, Journal, Customer, Analytics
│   │       ├── services.py             # Shared app helpers (get_org_currency)
│   │       └── agents/
│   │           ├── __init__.py          # Auto-discovers agents via pkgutil
│   │           ├── lead_agent/
│   │           │   ├── __init__.py      # AGENT_ID, get_agent_manifest()
│   │           │   ├── router.py        # Prospect CRUD, scraping, journal, dashboard
│   │           │   ├── service.py       # LeadAgentAI (GPT-4o insights, call scripts)
│   │           │   ├── scraper.py       # URLScraperService
│   │           │   └── tasks.py         # Scheduled notification processing
│   │           ├── timekeeping/
│   │           │   ├── __init__.py
│   │           │   └── service.py       # Follow-up analysis from journal entries
│   │           └── report_agent/
│   │               ├── __init__.py
│   │               ├── router.py        # Report listing, on-demand generation
│   │               ├── service.py       # ReportGenerator (GPT-4o-mini summaries)
│   │               └── tasks.py         # Scheduled report generation
│   │
│   ├── api/bots/                        # Legacy routes (backward compat — will be removed)
│   │   ├── hub.py
│   │   ├── lead_agent.py
│   │   └── reports.py
│   │
│   ├── services/                        # Legacy shim — re-exports from core.*
│   │   └── __init__.py
│   │
│   └── models/                          # Legacy shim — re-exports from core.models.*
│       └── __init__.py
│
├── static/
│   ├── shared/
│   │   ├── design-system.css            # Common CSS variables, components
│   │   └── core.js                      # Shared JS: Telegram SDK, API client, cache
│   │
│   └── mini-apps/
│       ├── launcher/
│       │   └── index.html               # Ecosystem home — shows all apps
│       ├── hub/
│       │   └── index.html               # Legacy Hub admin dashboard
│       ├── lead-agent/
│       │   └── index.html               # Legacy Lead Agent UI
│       └── workforce-accelerator/
│           ├── hub.html                 # WA admin dashboard (new path)
│           └── lead-agent.html          # WA lead agent (new path)
│
└── supabase/
    └── migrations/
        ├── 001-014_*.sql                # Existing migrations
        └── 015_ecosystem_tables.sql     # App registry, org app subscriptions
```

## URL Scheme

### API Routes

```
/api/hub/*                                          Platform (org, membership, billing)
/api/apps/workforce-accelerator/*                   WA app-level (products, analytics)
/api/apps/workforce-accelerator/lead-agent/*         Lead agent routes
/api/apps/workforce-accelerator/report-agent/*       Report routes

# Backward-compatible (same routes, old prefixes — still work):
/api/hub/orgs/{org_id}/products                     → same as /api/apps/workforce-accelerator/orgs/{org_id}/products
/api/lead-agent/prospects                            → same as /api/apps/workforce-accelerator/lead-agent/prospects
```

### Mini App Routes

```
/app/launcher                                        Ecosystem home screen
/app/workforce-accelerator/hub                       WA admin dashboard
/app/workforce-accelerator/lead-agent                WA lead agent

# Backward-compatible (still work):
/app/hub                                             Old hub path
/app/lead-agent                                      Old lead agent path
```

## Auto-Discovery System

Apps are discovered at startup by scanning `backend/apps/` for packages with a `get_manifest()` function.

### App Manifest

```python
# backend/apps/workforce_accelerator/__init__.py

from apps import AppManifest

APP_ID = "workforce-accelerator"

def get_manifest() -> AppManifest:
    from apps.workforce_accelerator.agents import get_agent_manifests
    return AppManifest(
        app_id=APP_ID,
        name="Workforce Accelerator",
        router_module="apps.workforce_accelerator.router",
        agents=get_agent_manifests(),
    )
```

### Agent Manifest

```python
# backend/apps/workforce_accelerator/agents/lead_agent/__init__.py

from apps import AgentManifest

def get_agent_manifest() -> AgentManifest:
    return AgentManifest(
        agent_id="lead-agent",
        name="B2B Lead Agent",
        router_module="apps.workforce_accelerator.agents.lead_agent.router",
        scheduled_tasks=[{
            "name": "wa:lead-agent:notifications",
            "func_path": "apps.workforce_accelerator.agents.lead_agent.tasks:process_due_notifications",
            "interval_seconds": 60,
            "condition_path": "apps.workforce_accelerator.agents.lead_agent.tasks:has_pending_notifications",
        }],
    )
```

### Startup Flow

```
main.py starts
  → _register_core_routes()          Register /api/hub/* (platform routes)
  → _register_apps()
      → discover_apps()              Scan backend/apps/ for packages
      → For each app:
          → Register app router       at /api/apps/{app_id}/*
          → For each agent:
              → Register agent router  at /api/apps/{app_id}/{agent_id}/*
              → Register scheduled tasks in unified scheduler
  → _register_compat_routes()        Legacy /api/hub/*, /api/lead-agent/* routes
  → Start unified scheduler          10s tick, condition-checked tasks
```

## How to Add a New App

1. Copy `backend/apps/_template/` to `backend/apps/my_new_app/`
2. Edit `__init__.py` — set `APP_ID`, `APP_NAME`, implement `get_manifest()`
3. Add app-specific models in `models.py`
4. Add routes in `router.py`
5. Add agents under `agents/` following the same pattern
6. Create a database migration if needed
7. Create a mini-app HTML at `static/mini-apps/my-new-app/`
8. Restart the server — auto-discovery registers everything

No changes needed to `main.py`, `core/`, or any existing app.

## How to Add a New Agent

1. Copy `backend/apps/my_app/agents/_template/` to `agents/my_agent/`
2. Edit `__init__.py` — set `AGENT_ID`, implement `get_agent_manifest()`
3. Add routes in `router.py`
4. Add AI logic in `service.py`
5. Add scheduled tasks in `tasks.py` (with condition checks)
6. Restart — the parent app's auto-discovery picks it up

## Authentication

Every API request includes `X-Telegram-Init-Data` header containing Telegram's HMAC-signed `initData`. Verification flow:

```
Request → X-Telegram-Init-Data header
  → get_telegram_user()         HMAC verify, extract TelegramUser
  → verify_org_member()         Cached user lookup + membership check
  → verify_org_admin()          Same + role == 'admin' check
```

Auth helpers in `core/auth.py` use the `auth` cache pool (60s TTL) so the user lookup + membership check (2 DB queries) are cached across requests.

## Caching Architecture

Two-layer in-memory caching — no Redis needed.

### Backend (Server-Side)

`core/cache.py` provides named cache pools with TTLs:

| Pool | TTL | What's Cached |
|------|-----|---------------|
| `auth` | 60s | User ID lookups, membership/role checks |
| `org` | 120s | Org details, invite codes, member lists, billing |
| `catalog` | 120s | Products, bots registry |
| `plans` | 600s | Subscription plans (rarely change) |
| `analytics` | 30s | Team/agent analytics, dashboards |
| `reports` | 60s | Activity reports |

Apps can register additional pools via `register_cache_pool()`.

**Pattern for endpoints:**
- **GET** — Check cache → return if valid → else fetch from DB → cache result
- **POST/PUT/PATCH/DELETE** — Perform mutation → `cache_delete()` affected keys

### Frontend (Client-Side)

Each mini-app has a JS cache with per-key TTLs. The shared `core.js` provides `createCacheManager(ttls)`.

## Background Task Strategy

The unified scheduler (`core/scheduler.py`) replaces individual polling loops:

- **10-second tick** — checks all registered tasks against their intervals
- **Condition checks** — optional async function checked before running (e.g., `has_pending_notifications()` does a quick DB query to avoid unnecessary work)
- **Fault tolerance** — failed tasks don't retry immediately, errors are logged
- **Zero idle cost** — polling itself is near-free; AI generation only runs on-demand

Current scheduled tasks:
| Task | Interval | Condition |
|------|----------|-----------|
| `wa:lead-agent:notifications` | 60s | `has_pending_notifications()` |
| `wa:report-agent:reports` | 3600s | None (hourly check, skips if no activity) |

## Billing Model

One monthly recurring fee per organization, based on subscribed apps:

- Each app has a `monthly_price` and `annual_price` in `app_registry`
- Orgs subscribe to individual apps via `org_app_subscriptions`
- Platform subscription (`org_subscriptions` / `subscription_plans`) covers base access
- Monthly/annual toggle per org

## Database Organization

Single Supabase PostgreSQL database. Tables are prefixed by domain:

| Prefix | Domain |
|--------|--------|
| (none) | Core: `users`, `organizations`, `memberships`, `bot_registry` |
| `org_*` | Platform: `org_subscriptions`, `org_app_subscriptions` |
| `lead_agent_*` | WA Lead Agent: `prospects`, `products`, `journal_entries`, `search_history` |
| `bot_task_log` | Cross-app agent task logging |
| `activity_reports` | Cross-app activity reports |
| `member_activity_log` | Cross-app activity tracking |
| `app_registry` | App catalog |

Existing table names stay as-is. New apps use their own prefix convention.

### Migration Numbering

- `0xx` — Core/platform migrations
- `1xx` — Workforce Accelerator
- `2xx`–`7xx` — Future apps

## Development Workflow

### Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Edit Mini App

1. Open any HTML file in `static/mini-apps/`
2. Edit HTML/CSS/JS
3. Refresh browser — see changes instantly

### Edit Backend

1. Edit files in `backend/`
2. FastAPI auto-reloads
3. Test at `/docs`

### Local Tunnel for Telegram

```bash
ngrok http 8000
# Set mini app URL in BotFather to: https://your-tunnel.ngrok.io/app/hub
```

## Shared Design System

`static/shared/design-system.css` provides:
- CSS custom properties (colors, spacing, shadows, gradients)
- Base reset and typography
- Card, button, form, badge, skeleton, modal components
- Utility classes

`static/shared/core.js` provides:
- `initTelegram()` — SDK init with theme application
- `createApiClient(baseUrl, tg)` — Fetch wrapper with auth and error handling
- `createCacheManager(ttls)` — Client-side cache with per-key TTLs
- `createNavigator(config)` — Page navigation with back button support
- `haptic(type)` — Haptic feedback wrapper
- `openModal(id)` / `closeModal(id)` — Modal toggles
- `formatCurrency()`, `timeAgo()` — Formatting helpers

New apps import these instead of duplicating.
