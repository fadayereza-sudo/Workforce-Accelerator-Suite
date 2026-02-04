-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - CUSTOMER DATABASE (CRM Core)
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- CUSTOMERS TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Contact Information
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,

    -- Address
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'US',

    -- Status & Type
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'lead', 'churned')),
    customer_type TEXT DEFAULT 'individual' CHECK (customer_type IN ('individual', 'business')),

    -- Financial
    lifetime_value DECIMAL(12, 2) DEFAULT 0,
    currency TEXT DEFAULT 'USD',

    -- Metadata
    tags JSONB DEFAULT '[]',
    custom_fields JSONB DEFAULT '{}',
    notes TEXT,

    -- Source tracking
    source TEXT,  -- 'import', 'manual', 'lead-agent', etc.
    source_id TEXT,  -- Reference ID from source (e.g., prospect_id)

    -- Timestamps
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_org ON customers(org_id);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
CREATE INDEX IF NOT EXISTS idx_customers_org_status ON customers(org_id, status);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_customers_search ON customers
    USING gin(to_tsvector('english', coalesce(name, '') || ' ' || coalesce(email, '') || ' ' || coalesce(company, '')));

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_customers_updated_at ON customers;
CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- CUSTOMER IMPORT JOBS TABLE (track CSV imports)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customer_import_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Import details
    file_name TEXT NOT NULL,
    total_rows INTEGER DEFAULT 0,
    imported_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,

    -- Status
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_details JSONB DEFAULT '[]',

    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_import_jobs_org ON customer_import_jobs(org_id);
CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON customer_import_jobs(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_import_jobs ENABLE ROW LEVEL SECURITY;

-- Deny all access for anon role (service role bypasses RLS)
DROP POLICY IF EXISTS "Deny all for anon on customers" ON customers;
CREATE POLICY "Deny all for anon on customers"
    ON customers TO anon USING (false);

DROP POLICY IF EXISTS "Deny all for anon on customer_import_jobs" ON customer_import_jobs;
CREATE POLICY "Deny all for anon on customer_import_jobs"
    ON customer_import_jobs TO anon USING (false);
