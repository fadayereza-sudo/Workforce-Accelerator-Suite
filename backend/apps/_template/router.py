"""
App-level routes — endpoints shared across all agents in this app.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
