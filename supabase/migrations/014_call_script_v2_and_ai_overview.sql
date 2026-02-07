-- Migration: Add AI Overview column for lead management
--
-- Add ai_overview column for AI-generated management summaries

-- Add AI overview column (populated by timekeeping agent after journal entries)
ALTER TABLE lead_agent_prospects
ADD COLUMN IF NOT EXISTS ai_overview TEXT;
