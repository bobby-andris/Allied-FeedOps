-- Migration 027: Add synced_at to search_queries
-- Distinguishes corrected/re-synced data from old data after the Phase 13 fix.
-- Populated by save_search_terms_to_db() on every write post-fix.
--
-- NULL synced_at = pre-Phase-13-fix data (wrong variant attribution: item_ids[0])
-- Non-NULL synced_at = data written with corrected fan-out logic (one row per variant)

ALTER TABLE search_queries
  ADD COLUMN IF NOT EXISTS synced_at timestamp with time zone;

-- Index for filtering by sync recency (e.g., find rows that still need re-sync)
CREATE INDEX IF NOT EXISTS idx_search_queries_synced_at
  ON search_queries (synced_at);

COMMENT ON COLUMN search_queries.synced_at IS
  'Timestamp when this row was last synced with corrected Phase 13 logic. NULL = pre-fix data.';
