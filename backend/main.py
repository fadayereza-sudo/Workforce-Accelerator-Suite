"""
Workforce Accelerator - FastAPI Backend

Entry point for the application.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from api.bots import hub
from config import settings

# Create app
app = FastAPI(
    title="Workforce Accelerator API",
    description="Backend for Telegram Mini App platform",
    version="1.0.0"
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
            "hub": "/app/hub"
        }
    }
