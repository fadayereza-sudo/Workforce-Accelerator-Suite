-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - INITIAL DATABASE SCHEMA
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- USERS TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username TEXT,
    full_name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- ORGANIZATIONS TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    settings JSONB DEFAULT '{}',
    invite_code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_organizations_invite_code ON organizations(invite_code);
CREATE INDEX idx_organizations_created_by ON organizations(created_by);

-- ─────────────────────────────────────────────────────────────────────────────
-- MEMBERSHIPS TABLE (users <-> organizations, many-to-many)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, org_id)
);

CREATE INDEX idx_memberships_user_id ON memberships(user_id);
CREATE INDEX idx_memberships_org_id ON memberships(org_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- MEMBERSHIP REQUESTS TABLE (pending join requests)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE membership_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    telegram_username TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_membership_requests_user_id ON membership_requests(user_id);
CREATE INDEX idx_membership_requests_org_id ON membership_requests(org_id);
CREATE INDEX idx_membership_requests_status ON membership_requests(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- BOT REGISTRY TABLE (available bots/agents)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE bot_registry (
    id TEXT PRIMARY KEY, -- e.g., 'crm-assistant', 'calendar-bot'
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT, -- emoji or URL
    price_monthly INTEGER DEFAULT 0, -- cents, 0 = free
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ORGANIZATION BOT LICENSES TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE org_bot_licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL REFERENCES bot_registry(id),
    active BOOLEAN DEFAULT true,
    trial_ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, bot_id)
);

CREATE INDEX idx_org_bot_licenses_org_id ON org_bot_licenses(org_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- BOT MEMBER ACCESS TABLE (which team members can use which bots)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE bot_member_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    bot_id TEXT NOT NULL REFERENCES bot_registry(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by UUID REFERENCES users(id),
    UNIQUE(membership_id, bot_id)
);

CREATE INDEX idx_bot_member_access_membership_id ON bot_member_access(membership_id);
CREATE INDEX idx_bot_member_access_bot_id ON bot_member_access(bot_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- NOTIFICATIONS TABLE
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    bot_id TEXT REFERENCES bot_registry(id),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    read_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_read_at ON notifications(read_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- UPDATED_AT TRIGGER FUNCTION
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memberships_updated_at BEFORE UPDATE ON memberships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_membership_requests_updated_at BEFORE UPDATE ON membership_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_registry_updated_at BEFORE UPDATE ON bot_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_org_bot_licenses_updated_at BEFORE UPDATE ON org_bot_licenses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────────────────────
-- SEED DATA: EXAMPLE BOTS
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO bot_registry (id, name, description, icon) VALUES
    ('crm-assistant', 'CRM Assistant', 'Manage leads and deals from Telegram', '💼'),
    ('calendar-sync', 'Calendar Sync', 'Sync your calendar and get reminders', '📅'),
    ('task-manager', 'Task Manager', 'Organize tasks and projects', '✅'),
    ('knowledge-base', 'Knowledge Base', 'AI-powered company knowledge search', '🧠');
