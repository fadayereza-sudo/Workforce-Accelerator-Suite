"""
Telegram authentication and authorization - consolidated from hub.py, lead_agent.py, reports.py.

Provides:
- verify_init_data(): HMAC signature verification
- get_telegram_user(): Extract TelegramUser from initData
- cached_get_user_id(): Telegram ID -> DB user UUID (cached)
- verify_org_member(): Verify membership, return (user_id, role) (cached)
- verify_org_admin(): Verify admin role, return user_id (cached)
"""
import hashlib
import hmac
import json
from urllib.parse import parse_qs
from typing import Optional
from fastapi import HTTPException

from config import settings
from core.cache import cache_get, cache_set
from core.database import get_supabase_admin
from core.models.user import TelegramUser


def verify_init_data(init_data: str, bot_token: Optional[str] = None) -> dict:
    """
    Verify Telegram Mini App initData signature.
    Returns the parsed data if valid.

    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    token = bot_token or settings.bot_hub_token
    if not token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    # Parse the query string
    parsed = dict(parse_qs(init_data, keep_blank_values=True))
    parsed = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

    # Extract and remove hash
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    # Build data-check-string (sorted key=value pairs joined by newline)
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # Calculate secret key: HMAC-SHA256 of bot token with "WebAppData" as key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    # Calculate expected hash
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(received_hash, expected_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    return parsed


def get_telegram_user(init_data: str) -> TelegramUser:
    """
    Verify initData and extract user information.
    """
    parsed = verify_init_data(init_data)

    user_json = parsed.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="No user data in initData")

    try:
        user_data = json.loads(user_json)
        return TelegramUser(**user_data)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=401, detail=f"Invalid user data: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CACHED AUTH HELPERS (consolidated from hub.py, lead_agent.py, reports.py)
# ─────────────────────────────────────────────────────────────────────────────

def cached_get_user_id(telegram_id: int) -> str:
    """Get user ID from telegram_id, with caching."""
    cache_key = f"user:{telegram_id}"
    cached = cache_get("auth", cache_key)
    if cached is not None:
        return cached

    db = get_supabase_admin()
    result = db.table("users").select("id").eq("telegram_id", telegram_id).single().execute()
    if not result.data:
        raise HTTPException(404, "User not found")

    user_id = result.data["id"]
    cache_set("auth", cache_key, user_id)
    return user_id


def verify_org_member(telegram_id: int, org_id: str) -> tuple[str, str]:
    """
    Verify user is a member of the organization.
    Returns (user_id, role). Uses auth cache.
    """
    user_id = cached_get_user_id(telegram_id)

    membership_cache_key = f"membership:{user_id}:{org_id}"
    cached_membership = cache_get("auth", membership_cache_key)

    if cached_membership is not None:
        return user_id, cached_membership.get("role", "member")

    db = get_supabase_admin()
    membership = db.table("memberships").select("role").eq(
        "user_id", user_id
    ).eq("org_id", org_id).execute()

    if not membership.data:
        raise HTTPException(403, "Not a member of this organization")

    cache_set("auth", membership_cache_key, membership.data[0])
    return user_id, membership.data[0]["role"]


def verify_org_admin(telegram_id: int, org_id: str) -> str:
    """
    Verify user is an admin of the organization.
    Returns user_id.
    """
    user_id, role = verify_org_member(telegram_id, org_id)
    if role != "admin":
        raise HTTPException(403, "Admin access required")
    return user_id
