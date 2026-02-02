"""
Supabase database client.
"""
from functools import lru_cache
from supabase import create_client, Client
from config import settings


@lru_cache()
def get_supabase() -> Client:
    """Get Supabase client with anon key (respects RLS)."""
    return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache()
def get_supabase_admin() -> Client:
    """Get Supabase client with service key (bypasses RLS)."""
    return create_client(settings.supabase_url, settings.supabase_service_key)
