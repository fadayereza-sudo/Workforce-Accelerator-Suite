-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - ROW LEVEL SECURITY POLICIES
-- ═══════════════════════════════════════════════════════════════════════════
--
-- This migration enables RLS on all tables and sets up policies.
-- Since we authenticate via Telegram (not Supabase Auth), we use service_role
-- for all backend operations. The anon key has NO direct access.
--
-- Security Model:
-- - All data access goes through our FastAPI backend
-- - Backend uses service_role key (bypasses RLS)
-- - Anon key cannot read/write any data directly
-- - This prevents malicious clients from accessing data even with the anon key
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE RLS ON ALL TABLES
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_bot_licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_member_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────────────────
-- POLICIES: DENY ALL FOR ANON
-- ─────────────────────────────────────────────────────────────────────────────
-- With RLS enabled and no policies granting access to anon,
-- the anon role cannot read or write any data.
-- The service_role key bypasses RLS entirely.

-- bot_registry is the only table we might want public read access to
-- (so the Mini App can show available bots without authentication)
CREATE POLICY "Allow public read access to bot_registry"
    ON bot_registry
    FOR SELECT
    TO anon
    USING (is_active = true);

-- ─────────────────────────────────────────────────────────────────────────────
-- OPTIONAL: Authenticated user policies (if using Supabase Auth later)
-- ─────────────────────────────────────────────────────────────────────────────
-- These are commented out since we use Telegram auth via backend.
-- Uncomment and modify if you add Supabase Auth in the future.

-- CREATE POLICY "Users can view own profile"
--     ON users FOR SELECT
--     TO authenticated
--     USING (auth.uid()::text = id::text);

-- CREATE POLICY "Users can view their memberships"
--     ON memberships FOR SELECT
--     TO authenticated
--     USING (user_id::text = auth.uid()::text);

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════════════════════════════════
-- After running this migration, verify RLS is enabled:
--
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public';
--
-- All tables should show rowsecurity = true
-- ═══════════════════════════════════════════════════════════════════════════
