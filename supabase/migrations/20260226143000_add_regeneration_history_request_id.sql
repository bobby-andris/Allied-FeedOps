-- Add request-level lineage to regeneration history for deterministic traceability.
ALTER TABLE regeneration_history
ADD COLUMN IF NOT EXISTS request_id text;

CREATE INDEX IF NOT EXISTS idx_regen_history_request_id
ON regeneration_history (request_id)
WHERE request_id IS NOT NULL;
