"""
Service layer — compatibility shim.

Re-exports from backend.core.* so existing imports continue to work
during the migration to the ecosystem architecture.
"""
# Database
from core.database import get_supabase, get_supabase_admin

# Auth (was telegram.py)
from core.auth import verify_init_data, get_telegram_user

# Notifications
from core.notifications import notify_admin_new_request, notify_user_approved

# Cache
from core.cache import (
    cache_get, cache_set, cache_delete,
    cache_invalidate, cache_invalidate_multi,
    register_cache_pool
)

__all__ = [
    "get_supabase",
    "get_supabase_admin",
    "verify_init_data",
    "get_telegram_user",
    "notify_admin_new_request",
    "notify_user_approved",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_invalidate",
    "cache_invalidate_multi",
    "register_cache_pool",
]
