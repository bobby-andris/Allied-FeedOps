-- Migration: 034_add_publish_lineage_hashes.sql
-- Purpose: Persist deterministic lineage hashes for publish observability.

ALTER TABLE publish_events
  ADD COLUMN IF NOT EXISTS final_payload_hash TEXT,
  ADD COLUMN IF NOT EXISTS prompt_hash TEXT,
  ADD COLUMN IF NOT EXISTS evidence_hash TEXT,
  ADD COLUMN IF NOT EXISTS segment_key TEXT;

COMMENT ON COLUMN publish_events.final_payload_hash IS
  'SHA-256 hash of canonicalized final_payload_snapshot JSON (post-expansion payload truth).';
COMMENT ON COLUMN publish_events.prompt_hash IS
  'Prompt identity hash used for generation lineage.';
COMMENT ON COLUMN publish_events.evidence_hash IS
  'SHA-256 hash of canonicalized evidence input object used at publish logging time.';
COMMENT ON COLUMN publish_events.segment_key IS
  'Normalized custom_label_0 segment key (lowercased, collapsed whitespace).';

CREATE INDEX IF NOT EXISTS idx_publish_events_final_payload_hash
  ON publish_events(final_payload_hash);
CREATE INDEX IF NOT EXISTS idx_publish_events_prompt_hash
  ON publish_events(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_publish_events_segment_key
  ON publish_events(segment_key);
