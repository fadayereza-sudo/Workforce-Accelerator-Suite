-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - ADMIN ANALYTICS & ACTIVITY TRACKING
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- MEMBER ACTIVITY LOG TABLE (granular activity tracking)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS member_activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Activity Details
    bot_id TEXT REFERENCES bot_registry(id),
    action_type TEXT NOT NULL,  -- 'page_view', 'task_completed', 'search', 'create', 'update', 'delete'
    action_detail JSONB DEFAULT '{}',  -- Flexible storage for action-specific data

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_activity_log_membership ON member_activity_log(membership_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_org ON member_activity_log(org_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_bot ON member_activity_log(bot_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON member_activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_org_date ON member_activity_log(org_id, created_at DESC);

-- Composite index for common queries (org + bot + time range)
CREATE INDEX IF NOT EXISTS idx_activity_log_org_bot_time ON member_activity_log(org_id, bot_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- AGENT TASK AGGREGATES TABLE (pre-computed for performance)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_task_aggregates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL REFERENCES bot_registry(id),

    -- Aggregation Period
    period_type TEXT NOT NULL CHECK (period_type IN ('daily', 'weekly', 'monthly')),
    period_start DATE NOT NULL,

    -- Metrics
    task_count INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,

    -- Last updated
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(org_id, bot_id, period_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_agent_aggregates_org ON agent_task_aggregates(org_id);
CREATE INDEX IF NOT EXISTS idx_agent_aggregates_lookup ON agent_task_aggregates(org_id, bot_id, period_type, period_start);

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_agent_task_aggregates_updated_at ON agent_task_aggregates;
CREATE TRIGGER update_agent_task_aggregates_updated_at BEFORE UPDATE ON agent_task_aggregates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- ADD last_active_at TO MEMBERSHIPS (if not exists)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE memberships ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;

-- Index for querying active members
CREATE INDEX IF NOT EXISTS idx_memberships_last_active ON memberships(org_id, last_active_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE member_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_task_aggregates ENABLE ROW LEVEL SECURITY;

-- Deny all access for anon role (service role bypasses RLS)
DROP POLICY IF EXISTS "Deny all for anon on member_activity_log" ON member_activity_log;
CREATE POLICY "Deny all for anon on member_activity_log"
    ON member_activity_log TO anon USING (false);

DROP POLICY IF EXISTS "Deny all for anon on agent_task_aggregates" ON agent_task_aggregates;
CREATE POLICY "Deny all for anon on agent_task_aggregates"
    ON agent_task_aggregates TO anon USING (false);
