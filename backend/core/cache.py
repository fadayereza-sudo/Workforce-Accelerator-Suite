"""
In-memory TTL cache service for reducing redundant Supabase queries.

Uses cachetools.TTLCache with separate pools for different data types,
each with an appropriate TTL based on how frequently the data changes.

Apps can register their own pools via register_cache_pool().
"""
import threading
from cachetools import TTLCache


# Thread-safe lock for cache operations
_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# CACHE POOLS
# Core pools are created at import time. Apps register additional pools
# via register_cache_pool() during app discovery.
# ─────────────────────────────────────────────────────────────────────────────

_pools: dict[str, TTLCache] = {}

# Core pool definitions
_CORE_POOLS = {
    "auth":      {"maxsize": 512, "ttl": 60},      # User lookups, membership checks
    "org":       {"maxsize": 256, "ttl": 120},      # Org details, invite codes, member lists
    "catalog":   {"maxsize": 256, "ttl": 120},      # Products, bots registry
    "plans":     {"maxsize": 32,  "ttl": 600},      # Subscription plans (rarely change)
    "analytics": {"maxsize": 256, "ttl": 30},       # Team/agent analytics, dashboards
    "reports":   {"maxsize": 128, "ttl": 60},       # Activity reports
}

# Initialize core pools
for _name, _config in _CORE_POOLS.items():
    _pools[_name] = TTLCache(**_config)


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC POOL REGISTRATION (for apps)
# ─────────────────────────────────────────────────────────────────────────────

def register_cache_pool(name: str, maxsize: int = 128, ttl: int = 60):
    """
    Register a new cache pool. Called by apps during manifest loading.
    No-op if pool already exists.
    """
    with _lock:
        if name not in _pools:
            _pools[name] = TTLCache(maxsize=maxsize, ttl=ttl)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def cache_get(pool: str, key: str):
    """
    Get a value from a cache pool.
    Returns None if pool doesn't exist, key not found, or expired.
    """
    cache = _pools.get(pool)
    if cache is None:
        return None
    with _lock:
        return cache.get(key)


def cache_set(pool: str, key: str, value):
    """Store a value in a cache pool."""
    cache = _pools.get(pool)
    if cache is None:
        return
    with _lock:
        cache[key] = value


def cache_delete(pool: str, key: str):
    """Delete a specific key from a cache pool."""
    cache = _pools.get(pool)
    if cache is None:
        return
    with _lock:
        cache.pop(key, None)


def cache_invalidate(pool: str, prefix: str = ""):
    """
    Invalidate cache entries in a pool.
    If prefix is given, only keys starting with that prefix are removed.
    If no prefix, the entire pool is cleared.
    """
    cache = _pools.get(pool)
    if cache is None:
        return
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
