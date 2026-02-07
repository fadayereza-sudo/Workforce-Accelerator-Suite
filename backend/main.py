"""
Apex Solutions — App Ecosystem Platform

Entry point for the FastAPI backend. Auto-discovers apps from backend/apps/,
registers their routers, and starts the unified task scheduler.

URL scheme:
  /api/hub/*                                    Platform (org, membership, billing)
  /api/apps/{app_id}/*                          App-level routes
  /api/apps/{app_id}/{agent_id}/*               Agent routes
  /app/launcher                                 Ecosystem home screen
  /app/{app_name}/{sub_app}                     Per-app mini-apps
"""
import asyncio
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from config import settings
from apps import discover_apps
from core.scheduler import scheduler, ScheduledTask
from core.cache import register_cache_pool


def _register_apps(app: FastAPI):
    """Discover apps and register their routers + scheduled tasks."""
    manifests = discover_apps()

    for manifest in manifests:
        # Register app-specific cache pools
        for pool in manifest.cache_pools:
            register_cache_pool(pool["name"], pool.get("maxsize", 128), pool.get("ttl", 60))

        # Register app-level router
        if manifest.router_module:
            try:
                mod = importlib.import_module(manifest.router_module)
                app.include_router(
                    mod.router,
                    prefix=f"/api/apps/{manifest.app_id}",
                    tags=[manifest.name]
                )
                print(f"[Router] {manifest.name}: /api/apps/{manifest.app_id}/*")
            except Exception as e:
                print(f"[Router] Error loading {manifest.router_module}: {e}")

        # Register agent routers + scheduled tasks
        for agent in manifest.agents:
            if agent.router_module:
                try:
                    mod = importlib.import_module(agent.router_module)
                    app.include_router(
                        mod.router,
                        prefix=f"/api/apps/{manifest.app_id}/{agent.agent_id}",
                        tags=[f"{manifest.name} — {agent.name}"]
                    )
                    print(f"[Router]   {agent.name}: /api/apps/{manifest.app_id}/{agent.agent_id}/*")
                except Exception as e:
                    print(f"[Router] Error loading {agent.router_module}: {e}")

            # Register scheduled tasks
            for task_def in agent.scheduled_tasks:
                scheduler.register(ScheduledTask(
                    name=task_def["name"],
                    func_path=task_def["func_path"],
                    interval_seconds=task_def["interval_seconds"],
                    condition_path=task_def.get("condition_path"),
                    app_id=manifest.app_id,
                    agent_id=agent.agent_id,
                ))


def _register_core_routes(app: FastAPI):
    """Register platform-level routes (hub, billing)."""
    from core.hub.router import router as hub_router
    from core.hub.billing import router as billing_router

    app.include_router(hub_router, prefix="/api/hub", tags=["Platform — Hub"])
    app.include_router(billing_router, prefix="/api/hub", tags=["Platform — Billing"])
    print("[Router] Platform hub: /api/hub/*")


def _register_compat_routes(app: FastAPI):
    """
    Backward-compatible routes so the existing frontend keeps working
    until it's updated to use the new /api/apps/... paths.
    """
    try:
        from apps.workforce_accelerator.router import router as wa_router
        from apps.workforce_accelerator.agents.lead_agent.router import router as la_router
        from apps.workforce_accelerator.agents.report_agent.router import router as ra_router

        # Old /api/hub also served WA-specific routes (products, analytics)
        app.include_router(wa_router, prefix="/api/hub", tags=["Compat — Hub+WA"])
        # Old /api/lead-agent
        app.include_router(la_router, prefix="/api/lead-agent", tags=["Compat — Lead Agent"])
        # Old /api/hub for reports
        app.include_router(ra_router, prefix="/api/hub", tags=["Compat — Reports"])
        print("[Router] Backward-compatible routes registered")
    except Exception as e:
        print(f"[Router] Warning: Could not register compat routes: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    scheduler_task = asyncio.create_task(scheduler.start())
    print(f"[Startup] Unified scheduler started with {len(scheduler.tasks)} tasks")
    yield
    await scheduler.stop()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        print("[Shutdown] Scheduler stopped")


# Create app
app = FastAPI(
    title="Apex Solutions Platform API",
    description="App ecosystem platform — Telegram Mini Apps",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

_register_core_routes(app)
_register_apps(app)
_register_compat_routes(app)


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FILES & MINI APPS
# ─────────────────────────────────────────────────────────────────────────────

static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/app/launcher")
async def serve_launcher():
    """Serve the ecosystem launcher mini-app."""
    file_path = static_path / "mini-apps" / "launcher" / "index.html"
    if not file_path.exists():
        return {"error": "Launcher not found"}
    return FileResponse(file_path, media_type="text/html")


@app.get("/app/{app_name}/{sub_app}")
async def serve_app_mini_app(app_name: str, sub_app: str):
    """Serve a per-app mini-app (e.g. /app/workforce-accelerator/hub)."""
    file_path = static_path / "mini-apps" / app_name / f"{sub_app}.html"
    if not file_path.exists():
        return {"error": f"Mini App '{app_name}/{sub_app}' not found"}
    return FileResponse(file_path, media_type="text/html")


@app.get("/app/{bot_name}")
async def serve_mini_app(bot_name: str):
    """Backward-compatible: serve old-style mini-app (e.g. /app/hub)."""
    file_path = static_path / "mini-apps" / bot_name / "index.html"
    if not file_path.exists():
        return {"error": f"Mini App '{bot_name}' not found"}
    return FileResponse(file_path, media_type="text/html")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK & ROOT
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "debug": settings.debug}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Apex Solutions Platform",
        "version": "2.0.0",
        "docs": "/docs",
        "apps": {
            "launcher": "/app/launcher",
            "workforce-accelerator": {
                "hub": "/app/workforce-accelerator/hub",
                "lead-agent": "/app/workforce-accelerator/lead-agent"
            }
        }
    }
