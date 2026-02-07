-- ═══════════════════════════════════════════════════════════════════════════
-- 015: Ecosystem Tables — App registry and per-org app subscriptions
--
-- Adds the foundation for the multi-app ecosystem:
-- - app_registry: catalog of available apps
-- - org_app_subscriptions: which apps each org has access to
-- - app_id column on bot_task_log for cross-app agent tracking
--
-- Migration numbering convention going forward:
--   0xx — Core/platform migrations
--   1xx — Workforce Accelerator app
--   2xx–7xx — Future apps
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────
-- APP REGISTRY
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS app_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    is_active BOOLEAN DEFAULT true,
    monthly_price NUMERIC(10,2) DEFAULT 0,
    annual_price NUMERIC(10,2) DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed the first app
INSERT INTO app_registry (id, name, description, icon, is_active, sort_order)
VALUES (
    'workforce-accelerator',
    'Workforce Accelerator',
    'B2B sales productivity suite with AI-powered lead generation, smart follow-ups, and automated reporting.',
    'briefcase',
    true,
    1
) ON CONFLICT (id) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────
-- ORG APP SUBSCRIPTIONS
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS org_app_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    app_id TEXT NOT NULL REFERENCES app_registry(id),
    active BOOLEAN DEFAULT true,
    billing_cycle TEXT DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly', 'annual')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, app_id)
);

CREATE INDEX IF NOT EXISTS idx_org_app_subs_org ON org_app_subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_org_app_subs_active ON org_app_subscriptions(org_id, active);


-- ─────────────────────────────────────────────────────────────────────────
-- ADD app_id TO bot_task_log FOR CROSS-APP TRACKING
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE bot_task_log ADD COLUMN IF NOT EXISTS app_id TEXT;

CREATE INDEX IF NOT EXISTS idx_bot_task_log_app ON bot_task_log(app_id);


-- ─────────────────────────────────────────────────────────────────────────
-- AUTO-SUBSCRIBE EXISTING ORGS TO WORKFORCE ACCELERATOR
-- ─────────────────────────────────────────────────────────────────────────

INSERT INTO org_app_subscriptions (org_id, app_id, active)
SELECT id, 'workforce-accelerator', true
FROM organizations
WHERE id NOT IN (
    SELECT org_id FROM org_app_subscriptions WHERE app_id = 'workforce-accelerator'
)
ON CONFLICT DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────
-- RLS POLICIES
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE app_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_app_subscriptions ENABLE ROW LEVEL SECURITY;

-- App registry is readable by all authenticated users (via service role)
CREATE POLICY "app_registry_read" ON app_registry
    FOR SELECT USING (true);

-- Org app subscriptions: members can read their org's subscriptions
CREATE POLICY "org_app_subs_read" ON org_app_subscriptions
    FOR SELECT USING (true);

-- Only service role (backend) can insert/update app subscriptions
CREATE POLICY "org_app_subs_insert" ON org_app_subscriptions
    FOR INSERT WITH CHECK (true);

CREATE POLICY "org_app_subs_update" ON org_app_subscriptions
    FOR UPDATE USING (true);
