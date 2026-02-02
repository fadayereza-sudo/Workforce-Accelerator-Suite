-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - ORGANIZATION ENHANCEMENTS
-- ═══════════════════════════════════════════════════════════════════════════
--
-- This migration adds:
-- 1. Organization description field
-- 2. Member activity tracking (last_active_at)
-- ═══════════════════════════════════════════════════════════════════════════

-- Add organization description
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS description TEXT;

-- Add member activity tracking
ALTER TABLE memberships ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;

-- Index for efficient activity queries
CREATE INDEX IF NOT EXISTS idx_memberships_last_active ON memberships(last_active_at);
