-- ─────────────────────────────────────────────────────────────────────────────
-- MIGRATION: Grant Lead Agent access to all existing members
-- ─────────────────────────────────────────────────────────────────────────────

-- Grant Lead Agent access to all existing organization members who don't already have it
INSERT INTO bot_member_access (membership_id, bot_id, granted_at)
SELECT
    m.id as membership_id,
    'lead-agent' as bot_id,
    NOW() as granted_at
FROM memberships m
WHERE NOT EXISTS (
    SELECT 1
    FROM bot_member_access bma
    WHERE bma.membership_id = m.id
    AND bma.bot_id = 'lead-agent'
)
ON CONFLICT (membership_id, bot_id) DO NOTHING;
