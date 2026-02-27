-- R2: normalized lineage and idempotency fields for regeneration writes

ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS result_state TEXT,
  ADD COLUMN IF NOT EXISTS result_version INTEGER,
  ADD COLUMN IF NOT EXISTS result_idempotent BOOLEAN,
  ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
  ADD COLUMN IF NOT EXISTS canonical_platform_hash TEXT,
  ADD COLUMN IF NOT EXISTS assembled_prompt_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_regen_history_result_state
  ON regeneration_history (result_state);

CREATE INDEX IF NOT EXISTS idx_regen_history_idempotency_key
  ON regeneration_history (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_regen_history_canonical_platform_hash
  ON regeneration_history (canonical_platform_hash);

CREATE INDEX IF NOT EXISTS idx_regen_history_assembled_prompt_hash
  ON regeneration_history (assembled_prompt_hash);

-- Expression indexes for active dedupe lookups.
CREATE INDEX IF NOT EXISTS idx_generation_jobs_regen_idempotency_active
  ON generation_jobs ((input_params->>'idempotency_key'))
  WHERE job_type = 'regenerate' AND status IN ('pending', 'running');

CREATE INDEX IF NOT EXISTS idx_batch_generation_jobs_idempotency_active
  ON batch_generation_jobs ((options->>'idempotency_key'))
  WHERE status IN ('queued', 'processing');
