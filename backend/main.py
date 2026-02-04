"""
Workforce Accelerator - FastAPI Backend

Entry point for the application.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from api.bots import hub, lead_agent, reports
from config import settings
from services.notification_scheduler import notification_scheduler_loop
from services.report_scheduler import report_scheduler_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start notification scheduler in background
    notification_task = asyncio.create_task(notification_scheduler_loop(poll_interval_seconds=60))
    print("[Startup] Notification scheduler started")

    # Start report scheduler in background (runs hourly)
    report_task = asyncio.create_task(report_scheduler_loop(poll_interval_seconds=3600))
    print("[Startup] Report scheduler started")

    yield

    # Cancel schedulers on shutdown
    notification_task.cancel()
    report_task.cancel()
    try:
        await notification_task
    except asyncio.CancelledError:
        print("[Shutdown] Notification scheduler stopped")
    try:
        await report_task
    except asyncio.CancelledError:
        print("[Shutdown] Report scheduler stopped")


# Create app
app = FastAPI(
    title="Workforce Accelerator API",
    description="Backend for Telegram Mini App platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(hub.router, prefix="/api/hub", tags=["Hub Bot"])
app.include_router(lead_agent.router, prefix="/api/lead-agent", tags=["Lead Agent"])
app.include_router(reports.router, prefix="/api/hub", tags=["Reports"])


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FILES & MINI APPS
# ─────────────────────────────────────────────────────────────────────────────

# Serve static files (CSS, JS, images)
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/app/{bot_name}")
async def serve_mini_app(bot_name: str):
    """Serve Mini App HTML for a specific bot."""
    file_path = static_path / "mini-apps" / bot_name / "index.html"

    if not file_path.exists():
        return {"error": f"Mini App '{bot_name}' not found"}

    return FileResponse(file_path, media_type="text/html")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "debug": settings.debug}


# ─────────────────────────────────────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Workforce Accelerator API",
        "version": "1.0.0",
        "docs": "/docs",
        "mini_apps": {
            "hub": "/app/hub",
            "lead-agent": "/app/lead-agent"
        }
    }
