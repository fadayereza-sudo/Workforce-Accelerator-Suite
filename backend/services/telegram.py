"""
Telegram authentication and utilities.
"""
import hashlib
import hmac
import json
from urllib.parse import parse_qs
from typing import Optional
from fastapi import HTTPException

from config import settings
from models import TelegramUser


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

    # Debug logging
    print(f"[DEBUG] Verifying initData with token: {token[:20]}...")
    print(f"[DEBUG] initData (first 100 chars): {init_data[:100]}...")

    # Parse the query string
    parsed = dict(parse_qs(init_data, keep_blank_values=True))
    # parse_qs returns lists, flatten single values
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

    # Debug logging
    print(f"[DEBUG] Received hash: {received_hash}")
    print(f"[DEBUG] Expected hash: {expected_hash}")

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
