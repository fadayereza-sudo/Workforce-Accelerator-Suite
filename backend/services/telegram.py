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
    print(f"\n{'='*80}")
    print(f"[VERIFY_INIT_DATA] Starting validation")
    print(f"[VERIFY_INIT_DATA] Bot token (first 20 chars): {token[:20]}...")
    print(f"[VERIFY_INIT_DATA] Bot token (full length): {len(token)} chars")
    print(f"[VERIFY_INIT_DATA] InitData length: {len(init_data)} chars")
    print(f"[VERIFY_INIT_DATA] InitData (first 200 chars): {init_data[:200]}...")

    # Parse the query string
    parsed = dict(parse_qs(init_data, keep_blank_values=True))
    # parse_qs returns lists, flatten single values
    parsed = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

    # Extract and remove hash
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        print(f"[VERIFY_INIT_DATA] ERROR: Missing hash in initData")
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    print(f"[VERIFY_INIT_DATA] Parsed fields: {list(parsed.keys())}")
    if "user" in parsed:
        print(f"[VERIFY_INIT_DATA] User data (first 100 chars): {parsed['user'][:100]}...")

    # Build data-check-string (sorted key=value pairs joined by newline)
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    print(f"[VERIFY_INIT_DATA] Data check string (first 200 chars):")
    print(f"  {data_check_string[:200]}...")

    # Calculate secret key: HMAC-SHA256 of bot token with "WebAppData" as key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=token.encode(),
        digestmod=hashlib.sha256
    ).digest()

    print(f"[VERIFY_INIT_DATA] Secret key (first 20 bytes hex): {secret_key[:20].hex()}...")

    # Calculate expected hash
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    # Debug logging
    print(f"[VERIFY_INIT_DATA] Received hash: {received_hash}")
    print(f"[VERIFY_INIT_DATA] Expected hash: {expected_hash}")
    print(f"[VERIFY_INIT_DATA] Hashes match: {received_hash == expected_hash}")

    # Constant-time comparison
    if not hmac.compare_digest(received_hash, expected_hash):
        print(f"[VERIFY_INIT_DATA] ❌ VALIDATION FAILED - Invalid signature")
        print(f"{'='*80}\n")
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    print(f"[VERIFY_INIT_DATA] ✅ VALIDATION SUCCESSFUL")
    print(f"{'='*80}\n")

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
