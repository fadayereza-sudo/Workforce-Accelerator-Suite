-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - ACTIVITY REPORTS & BOT TASK LOGGING
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- BOT TASK LOG TABLE (granular bot/agent activity tracking)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bot_task_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL REFERENCES bot_registry(id),

    -- Task Details
    task_type TEXT NOT NULL,  -- 'prospect_scraped', 'insights_generated', 'call_script_created', etc.
    task_detail JSONB DEFAULT '{}',  -- Flexible storage for task-specific data

    -- Optional: Which user triggered this (NULL for autonomous tasks)
    triggered_by UUID REFERENCES users(id),

    -- Execution metrics
    execution_time_ms INTEGER,  -- How long the task took
    tokens_used INTEGER,        -- LLM tokens consumed (if applicable)

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_bot_task_log_org ON bot_task_log(org_id);
CREATE INDEX IF NOT EXISTS idx_bot_task_log_bot ON bot_task_log(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_task_log_created ON bot_task_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_task_log_org_bot_time ON bot_task_log(org_id, bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_task_log_task_type ON bot_task_log(task_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- ACTIVITY REPORTS TABLE (stored LLM-generated summaries)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS activity_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Report Type & Scope
    report_type TEXT NOT NULL CHECK (report_type IN ('team', 'agent', 'combined')),
    period_type TEXT NOT NULL CHECK (period_type IN ('daily', 'weekly', 'monthly')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Optional: For individual member reports
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    -- Optional: For individual bot reports
    bot_id TEXT REFERENCES bot_registry(id),

    -- Raw data snapshot (for regeneration/debugging)
    raw_metrics JSONB NOT NULL DEFAULT '{}',

    -- LLM-Generated Content
    summary_text TEXT NOT NULL,           -- The main summary paragraph(s)
    highlights JSONB DEFAULT '[]',        -- Array of key highlights/achievements
    recommendations JSONB DEFAULT '[]',   -- Optional suggestions

    -- Metadata
    generated_by TEXT DEFAULT 'gpt-4o-mini',  -- Model used
    tokens_used INTEGER,
    generation_time_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate reports for same period/scope
    UNIQUE(org_id, report_type, period_type, period_start, user_id, bot_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_reports_org ON activity_reports(org_id);
CREATE INDEX IF NOT EXISTS idx_activity_reports_lookup ON activity_reports(org_id, report_type, period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_activity_reports_user ON activity_reports(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activity_reports_bot ON activity_reports(bot_id) WHERE bot_id IS NOT NULL;

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_activity_reports_updated_at ON activity_reports;
CREATE TRIGGER update_activity_reports_updated_at BEFORE UPDATE ON activity_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bot_task_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_reports ENABLE ROW LEVEL SECURITY;

-- Deny all access for anon role (service role bypasses RLS)
DROP POLICY IF EXISTS "Deny all for anon on bot_task_log" ON bot_task_log;
CREATE POLICY "Deny all for anon on bot_task_log"
    ON bot_task_log TO anon USING (false);

DROP POLICY IF EXISTS "Deny all for anon on activity_reports" ON activity_reports;
CREATE POLICY "Deny all for anon on activity_reports"
    ON activity_reports TO anon USING (false);
