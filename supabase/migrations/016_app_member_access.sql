-- ═══════════════════════════════════════════════════════════════════════════
-- 016: App Member Access — Per-member app access control
--
-- Adds app_member_access table for tracking which members have access
-- to which apps (parallel to bot_member_access but at the app level).
-- Admins have implicit access to all subscribed apps.
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────
-- APP MEMBER ACCESS TABLE
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS app_member_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    app_id TEXT NOT NULL REFERENCES app_registry(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by UUID REFERENCES users(id),
    UNIQUE(membership_id, app_id)
);

CREATE INDEX IF NOT EXISTS idx_app_member_access_membership ON app_member_access(membership_id);
CREATE INDEX IF NOT EXISTS idx_app_member_access_app ON app_member_access(app_id);


-- ─────────────────────────────────────────────────────────────────────────
-- RLS POLICIES
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE app_member_access ENABLE ROW LEVEL SECURITY;

CREATE POLICY "app_member_access_read" ON app_member_access
    FOR SELECT USING (true);

CREATE POLICY "app_member_access_insert" ON app_member_access
    FOR INSERT WITH CHECK (true);

CREATE POLICY "app_member_access_delete" ON app_member_access
    FOR DELETE USING (true);


-- ─────────────────────────────────────────────────────────────────────────
-- BACKFILL: Grant workforce-accelerator access to existing members
-- who have any bot_member_access entries
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO app_member_access (membership_id, app_id)
SELECT DISTINCT bma.membership_id, 'workforce-accelerator'
FROM bot_member_access bma
JOIN memberships m ON m.id = bma.membership_id
WHERE NOT EXISTS (
    SELECT 1 FROM app_member_access ama
    WHERE ama.membership_id = bma.membership_id
    AND ama.app_id = 'workforce-accelerator'
)
ON CONFLICT DO NOTHING;
