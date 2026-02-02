-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFORCE ACCELERATOR - URL SCRAPING SUPPORT
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Adds support for URL-based prospect scraping:
-- - Makes search_query nullable (URL scraping has no search query)
-- - Updates source default
-- ═══════════════════════════════════════════════════════════════════════════

-- Make search_query nullable for URL-scraped prospects
ALTER TABLE lead_agent_prospects
    ALTER COLUMN search_query DROP NOT NULL;

-- Add comment explaining the sources
COMMENT ON COLUMN lead_agent_prospects.source IS
    'Source of the prospect: gemini_search (search-based) or url_scrape (URL-based)';

COMMENT ON COLUMN lead_agent_prospects.search_query IS
    'Original search query (null for URL-scraped prospects)';
