-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - BILLING SYSTEM
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- SUBSCRIPTION PLANS TABLE (available plans)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS subscription_plans (
    id TEXT PRIMARY KEY,  -- e.g., 'free', 'starter', 'professional', 'enterprise'
    name TEXT NOT NULL,
    description TEXT,

    -- Pricing (in cents)
    price_monthly INTEGER NOT NULL DEFAULT 0,
    price_yearly INTEGER,  -- optional annual discount
    currency TEXT DEFAULT 'USD',

    -- Limits
    max_members INTEGER,  -- NULL = unlimited
    max_customers INTEGER,  -- NULL = unlimited
    included_bots TEXT[] DEFAULT '{}',  -- Array of bot_ids included

    -- Features
    features JSONB DEFAULT '[]',  -- ["Feature 1", "Feature 2", etc.]

    -- Status
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_subscription_plans_updated_at ON subscription_plans;
CREATE TRIGGER update_subscription_plans_updated_at BEFORE UPDATE ON subscription_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed default plans
INSERT INTO subscription_plans (id, name, description, price_monthly, max_members, max_customers, features, sort_order) VALUES
    ('free', 'Free', 'Get started with basic features', 0, 3, 100, '["Up to 3 team members", "100 customers", "1 agent", "Community support"]', 1),
    ('starter', 'Starter', 'For small teams getting productive', 2900, 10, 1000, '["Up to 10 team members", "1,000 customers", "All agents", "Email support", "Basic analytics"]', 2),
    ('professional', 'Professional', 'For growing businesses', 7900, 50, 10000, '["Up to 50 team members", "10,000 customers", "All agents", "Priority support", "Advanced analytics", "API access"]', 3),
    ('enterprise', 'Enterprise', 'For large organizations', 0, NULL, NULL, '["Unlimited team members", "Unlimited customers", "All agents", "Dedicated support", "Custom integrations", "SLA guarantee"]', 4)
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- ORGANIZATION SUBSCRIPTIONS TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS org_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES subscription_plans(id),

    -- Billing cycle
    billing_cycle TEXT DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly', 'yearly')),

    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'trialing')),

    -- Trial
    trial_ends_at TIMESTAMPTZ,

    -- Billing dates
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end TIMESTAMPTZ NOT NULL,

    canceled_at TIMESTAMPTZ,

    -- External payment provider (for future Stripe integration)
    stripe_subscription_id TEXT,
    stripe_customer_id TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(org_id)  -- One active subscription per org
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_org ON org_subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON org_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON org_subscriptions(plan_id);

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_org_subscriptions_updated_at ON org_subscriptions;
CREATE TRIGGER update_org_subscriptions_updated_at BEFORE UPDATE ON org_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- INVOICES TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES org_subscriptions(id),

    -- Invoice details
    invoice_number TEXT NOT NULL,

    -- Amounts (in cents)
    subtotal INTEGER NOT NULL DEFAULT 0,
    tax INTEGER DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    currency TEXT DEFAULT 'USD',

    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'paid', 'void', 'uncollectible')),

    -- Dates
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    paid_at TIMESTAMPTZ,

    -- Line items
    line_items JSONB DEFAULT '[]',  -- [{description, quantity, unit_price, amount}]

    -- External (for future Stripe integration)
    stripe_invoice_id TEXT,
    pdf_url TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_org ON invoices(org_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_invoices_updated_at ON invoices;
CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Generate invoice numbers sequence
CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1000;

-- ─────────────────────────────────────────────────────────────────────────────
-- ENABLE ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

-- Subscription plans are publicly readable (for plan selection UI)
DROP POLICY IF EXISTS "Allow read for anon on subscription_plans" ON subscription_plans;
CREATE POLICY "Allow read for anon on subscription_plans"
    ON subscription_plans FOR SELECT TO anon USING (is_active = true);

-- Deny all access for anon on subscription and invoice data
DROP POLICY IF EXISTS "Deny all for anon on org_subscriptions" ON org_subscriptions;
CREATE POLICY "Deny all for anon on org_subscriptions"
    ON org_subscriptions TO anon USING (false);

DROP POLICY IF EXISTS "Deny all for anon on invoices" ON invoices;
CREATE POLICY "Deny all for anon on invoices"
    ON invoices TO anon USING (false);

-- ─────────────────────────────────────────────────────────────────────────────
-- AUTO-CREATE FREE SUBSCRIPTION FOR NEW ORGS (function + trigger)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION create_default_subscription()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO org_subscriptions (org_id, plan_id, current_period_end)
    VALUES (NEW.id, 'free', NOW() + INTERVAL '100 years')
    ON CONFLICT (org_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS create_org_subscription ON organizations;
CREATE TRIGGER create_org_subscription
    AFTER INSERT ON organizations
    FOR EACH ROW EXECUTE FUNCTION create_default_subscription();
