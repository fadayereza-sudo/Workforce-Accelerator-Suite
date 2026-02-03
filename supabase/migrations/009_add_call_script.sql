-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - ADD CALL SCRIPT COLUMN
-- ═══════════════════════════════════════════════════════════════════════════

-- Add call_script column to lead_agent_prospects table
-- This column stores AI-generated conversational call scripts as JSONB
-- Format: [{"question": "...", "answer": "..."}, ...]

ALTER TABLE lead_agent_prospects
ADD COLUMN IF NOT EXISTS call_script JSONB DEFAULT '[]';
