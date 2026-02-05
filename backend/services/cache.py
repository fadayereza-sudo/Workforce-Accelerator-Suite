"""
In-memory TTL cache service for reducing redundant Supabase queries.

Uses cachetools.TTLCache with separate pools for different data types,
each with an appropriate TTL based on how frequently the data changes.
"""
import threading
from cachetools import TTLCache


# Thread-safe lock for cache operations
_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# CACHE POOLS
# Each pool has a max size and TTL appropriate for its data type.
# ─────────────────────────────────────────────────────────────────────────────

# Auth: user lookups by telegram_id, membership checks (every request)
_auth_cache = TTLCache(maxsize=512, ttl=60)

# Org: org details, invite codes, member lists
_org_cache = TTLCache(maxsize=256, ttl=120)

# Catalog: products, bots registry
_catalog_cache = TTLCache(maxsize=256, ttl=120)

# Plans: subscription plans (rarely change)
_plans_cache = TTLCache(maxsize=32, ttl=600)

# Analytics: team/agent analytics, dashboards (changes frequently)
_analytics_cache = TTLCache(maxsize=256, ttl=30)

# Reports: activity reports
_reports_cache = TTLCache(maxsize=128, ttl=60)

# Pool registry for easy access
_pools = {
    "auth": _auth_cache,
    "org": _org_cache,
    "catalog": _catalog_cache,
    "plans": _plans_cache,
    "analytics": _analytics_cache,
    "reports": _reports_cache,
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def cache_get(pool: str, key: str):
    """
    Get a value from a cache pool.
    Returns None if not found or expired.
    """
    cache = _pools[pool]
    with _lock:
        return cache.get(key)


def cache_set(pool: str, key: str, value):
    """Store a value in a cache pool."""
    cache = _pools[pool]
    with _lock:
        cache[key] = value


def cache_delete(pool: str, key: str):
    """Delete a specific key from a cache pool."""
    cache = _pools[pool]
    with _lock:
        cache.pop(key, None)


def cache_invalidate(pool: str, prefix: str = ""):
    """
    Invalidate cache entries in a pool.
    If prefix is given, only keys starting with that prefix are removed.
    If no prefix, the entire pool is cleared.
    """
    cache = _pools[pool]
    with _lock:
        if not prefix:
            cache.clear()
        else:
            keys_to_remove = [k for k in cache if k.startswith(prefix)]
            for k in keys_to_remove:
                cache.pop(k, None)


def cache_invalidate_multi(pools: list[str], prefix: str = ""):
    """Invalidate entries across multiple pools at once."""
    for pool in pools:
        cache_invalidate(pool, prefix)
