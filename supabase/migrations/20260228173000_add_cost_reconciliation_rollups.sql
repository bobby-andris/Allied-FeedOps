-- R3: Cost reconciliation + retry attribution persistence

ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS provider_attempt_count INTEGER,
  ADD COLUMN IF NOT EXISTS parse_retry_count INTEGER;

CREATE INDEX IF NOT EXISTS idx_regen_history_created_at
  ON regeneration_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_regen_history_provider_attempt_count
  ON regeneration_history (provider_attempt_count)
  WHERE provider_attempt_count IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_regen_history_parse_retry_count
  ON regeneration_history (parse_retry_count)
  WHERE parse_retry_count IS NOT NULL;

CREATE TABLE IF NOT EXISTS openai_usage_window_rollups (
  id BIGSERIAL PRIMARY KEY,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  bucket_width TEXT NOT NULL DEFAULT '1d',
  openai_request_count INTEGER NOT NULL DEFAULT 0,
  input_tokens BIGINT NOT NULL DEFAULT 0,
  output_tokens BIGINT NOT NULL DEFAULT 0,
  cached_input_tokens BIGINT NOT NULL DEFAULT 0,
  total_cost_usd NUMERIC(14,6),
  currency TEXT NOT NULL DEFAULT 'usd',
  source TEXT NOT NULL DEFAULT 'openai_organization_api',
  metadata JSONB,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(window_start, window_end, bucket_width)
);

CREATE INDEX IF NOT EXISTS idx_openai_usage_window_rollups_window
  ON openai_usage_window_rollups (window_start DESC, window_end DESC);

CREATE TABLE IF NOT EXISTS generation_cost_window_rollups (
  id BIGSERIAL PRIMARY KEY,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  bucket_width TEXT NOT NULL DEFAULT '1d',
  internal_request_count INTEGER NOT NULL DEFAULT 0,
  with_cost_request_count INTEGER NOT NULL DEFAULT 0,
  missing_cost_request_count INTEGER NOT NULL DEFAULT 0,
  total_tokens BIGINT NOT NULL DEFAULT 0,
  total_cost_usd NUMERIC(14,6) NOT NULL DEFAULT 0,
  avg_latency_ms NUMERIC(12,3),
  p95_latency_ms NUMERIC(12,3),
  provider_attempt_count_sum INTEGER NOT NULL DEFAULT 0,
  parse_retry_count_sum INTEGER NOT NULL DEFAULT 0,
  mode_breakdown JSONB,
  metadata JSONB,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(window_start, window_end, bucket_width)
);

CREATE INDEX IF NOT EXISTS idx_generation_cost_window_rollups_window
  ON generation_cost_window_rollups (window_start DESC, window_end DESC);

CREATE TABLE IF NOT EXISTS cost_reconciliation_deltas (
  id BIGSERIAL PRIMARY KEY,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  bucket_width TEXT NOT NULL DEFAULT '1d',
  openai_total_cost_usd NUMERIC(14,6),
  internal_total_cost_usd NUMERIC(14,6) NOT NULL DEFAULT 0,
  delta_cost_usd NUMERIC(14,6),
  delta_ratio NUMERIC(14,6),
  openai_total_requests INTEGER,
  internal_total_requests INTEGER NOT NULL DEFAULT 0,
  internal_with_cost_requests INTEGER NOT NULL DEFAULT 0,
  internal_missing_cost_requests INTEGER NOT NULL DEFAULT 0,
  provider_attempt_count_sum INTEGER NOT NULL DEFAULT 0,
  parse_retry_count_sum INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'unknown',
  mismatch_categories JSONB,
  metadata JSONB,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(window_start, window_end, bucket_width)
);

CREATE INDEX IF NOT EXISTS idx_cost_reconciliation_deltas_window
  ON cost_reconciliation_deltas (window_start DESC, window_end DESC);

CREATE INDEX IF NOT EXISTS idx_cost_reconciliation_deltas_status
  ON cost_reconciliation_deltas (status);

-- Reuse shared update_updated_at_column function from earlier migrations.
DROP TRIGGER IF EXISTS update_openai_usage_window_rollups_updated_at ON openai_usage_window_rollups;
CREATE TRIGGER update_openai_usage_window_rollups_updated_at
  BEFORE UPDATE ON openai_usage_window_rollups
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_generation_cost_window_rollups_updated_at ON generation_cost_window_rollups;
CREATE TRIGGER update_generation_cost_window_rollups_updated_at
  BEFORE UPDATE ON generation_cost_window_rollups
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_cost_reconciliation_deltas_updated_at ON cost_reconciliation_deltas;
CREATE TRIGGER update_cost_reconciliation_deltas_updated_at
  BEFORE UPDATE ON cost_reconciliation_deltas
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE openai_usage_window_rollups ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_cost_window_rollups ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_reconciliation_deltas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access" ON openai_usage_window_rollups;
DROP POLICY IF EXISTS "Allow all access" ON generation_cost_window_rollups;
DROP POLICY IF EXISTS "Allow all access" ON cost_reconciliation_deltas;

CREATE POLICY "Allow all access" ON openai_usage_window_rollups FOR ALL USING (true);
CREATE POLICY "Allow all access" ON generation_cost_window_rollups FOR ALL USING (true);
CREATE POLICY "Allow all access" ON cost_reconciliation_deltas FOR ALL USING (true);
