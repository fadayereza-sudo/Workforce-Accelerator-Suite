-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - B2B LEAD AGENT TABLES
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- LEAD AGENT PRODUCTS TABLE (organization's products/services)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE lead_agent_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    price DECIMAL(12, 2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lead_agent_products_org_id ON lead_agent_products(org_id);
CREATE INDEX idx_lead_agent_products_is_active ON lead_agent_products(is_active);

-- Apply updated_at trigger
CREATE TRIGGER update_lead_agent_products_updated_at BEFORE UPDATE ON lead_agent_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- LEAD AGENT PROSPECTS TABLE (scraped business leads)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE lead_agent_prospects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Business Information (from Gemini search)
    business_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    website TEXT,
    google_maps_url TEXT,

    -- Deduplication (hash of business_name + phone/address)
    dedup_hash TEXT NOT NULL,

    -- Search context
    search_query TEXT NOT NULL,
    source TEXT DEFAULT 'gemini_search',

    -- AI-Generated Content (from OpenAI)
    business_summary TEXT,
    pain_points JSONB DEFAULT '[]',
    ai_generated_at TIMESTAMPTZ,

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'not_contacted'
        CHECK (status IN ('not_contacted', 'contacted', 'ongoing_conversations', 'closed')),

    -- Metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicates per org
    UNIQUE(org_id, dedup_hash)
);

CREATE INDEX idx_lead_agent_prospects_org_id ON lead_agent_prospects(org_id);
CREATE INDEX idx_lead_agent_prospects_status ON lead_agent_prospects(status);
CREATE INDEX idx_lead_agent_prospects_search_query ON lead_agent_prospects(search_query);
CREATE INDEX idx_lead_agent_prospects_dedup_hash ON lead_agent_prospects(dedup_hash);
CREATE INDEX idx_lead_agent_prospects_created_at ON lead_agent_prospects(created_at DESC);

-- Apply updated_at trigger
CREATE TRIGGER update_lead_agent_prospects_updated_at BEFORE UPDATE ON lead_agent_prospects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- LEAD AGENT SEARCHES TABLE (search history tracking)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE lead_agent_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    new_prospects_count INTEGER DEFAULT 0,
    skipped_duplicates_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lead_agent_searches_org_id ON lead_agent_searches(org_id);
CREATE INDEX idx_lead_agent_searches_user_id ON lead_agent_searches(user_id);
CREATE INDEX idx_lead_agent_searches_created_at ON lead_agent_searches(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE lead_agent_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_agent_prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_agent_searches ENABLE ROW LEVEL SECURITY;

-- Deny all access for anon role (service role bypasses RLS)
CREATE POLICY "Deny all for anon on lead_agent_products"
    ON lead_agent_products TO anon USING (false);

CREATE POLICY "Deny all for anon on lead_agent_prospects"
    ON lead_agent_prospects TO anon USING (false);

CREATE POLICY "Deny all for anon on lead_agent_searches"
    ON lead_agent_searches TO anon USING (false);

-- ─────────────────────────────────────────────────────────────────────────────
-- REGISTER LEAD AGENT BOT
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO bot_registry (id, name, description, icon, is_active) VALUES
    ('lead-agent', 'B2B Lead Agent', 'Find and manage business leads with AI-powered insights', '🎯', true);
