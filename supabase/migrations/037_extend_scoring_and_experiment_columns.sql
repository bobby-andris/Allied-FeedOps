-- Migration: 037_extend_scoring_and_experiment_columns.sql
-- Phase 32: OPS-03 (query_value_scores) and OPS-04 (experiment_outcomes)
-- Applied: 2026-02-25

-- =============================================================================
-- Safety: Ensure base tables exist (from DEFERRED migrations 033b and 035b)
-- Both were reportedly applied out-of-band, but CREATE IF NOT EXISTS is safe.
-- =============================================================================

-- From 033b: query_value_scores
CREATE TABLE IF NOT EXISTS query_value_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  search_term text NOT NULL,
  custom_label_0 text NOT NULL,
  score_version text NOT NULL DEFAULT 'v1',
  expected_clicks numeric(12,4) NOT NULL DEFAULT 0,
  expected_cvr numeric(10,6) NOT NULL DEFAULT 0,
  expected_conversion_value numeric(14,4) NOT NULL DEFAULT 0,
  expected_profit_proxy numeric(14,4) NOT NULL DEFAULT 0,
  uncertainty numeric(10,6) NOT NULL DEFAULT 1,
  impact_score numeric(14,4) NOT NULL DEFAULT 0,
  model_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_query_value_scores_term_label_created
  ON query_value_scores (search_term, custom_label_0, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_value_scores_impact_created
  ON query_value_scores (impact_score DESC, created_at DESC);

-- From 035b: experiment_outcomes (requires experiment_registry)
CREATE TABLE IF NOT EXISTS experiment_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_key text NOT NULL UNIQUE,
  name text NOT NULL,
  initiative text NOT NULL,
  hypothesis text NOT NULL,
  decision_rule text,
  success_threshold numeric(14,4),
  failure_threshold numeric(14,4),
  status text NOT NULL DEFAULT 'active',
  start_date date NOT NULL,
  end_date date,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_key text NOT NULL,
  metric_name text NOT NULL,
  observed_lift numeric(14,6) NOT NULL DEFAULT 0,
  sample_size bigint NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'observing',
  measured_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT experiment_outcomes_experiment_key_fkey
    FOREIGN KEY (experiment_key)
    REFERENCES experiment_registry (experiment_key)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiment_outcomes_experiment_measured
  ON experiment_outcomes (experiment_key, measured_at DESC);

-- RLS for safety-created tables (idempotent)
ALTER TABLE query_value_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access" ON query_value_scores;
DROP POLICY IF EXISTS "Allow all access" ON experiment_registry;
DROP POLICY IF EXISTS "Allow all access" ON experiment_outcomes;

CREATE POLICY "Allow all access" ON query_value_scores FOR ALL USING (true);
CREATE POLICY "Allow all access" ON experiment_registry FOR ALL USING (true);
CREATE POLICY "Allow all access" ON experiment_outcomes FOR ALL USING (true);

-- =============================================================================
-- OPS-03: Extend query_value_scores for Phase 33 tier scoring
-- Adds: tier_fit_scores (JSONB), recommended_tier (TEXT),
--       net_monthly_impact (NUMERIC), scored_at (TIMESTAMPTZ)
-- NULL = "not yet scored" -- no defaults. Phase 33 populates on first run.
-- =============================================================================

ALTER TABLE query_value_scores
  ADD COLUMN IF NOT EXISTS tier_fit_scores JSONB,
  ADD COLUMN IF NOT EXISTS recommended_tier TEXT,
  ADD COLUMN IF NOT EXISTS net_monthly_impact NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;

-- Constraint: recommended_tier must be HIGH, MEDIUM, LOW, or NULL (not yet scored)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'query_value_scores_recommended_tier_check'
  ) THEN
    ALTER TABLE query_value_scores
      ADD CONSTRAINT query_value_scores_recommended_tier_check
      CHECK (recommended_tier IS NULL OR recommended_tier IN ('HIGH', 'MEDIUM', 'LOW'));
  END IF;
END $$;

-- Index for Phase 33 queries that filter by recently scored rows
CREATE INDEX IF NOT EXISTS idx_query_value_scores_scored_at
  ON query_value_scores (scored_at DESC NULLS LAST);

-- =============================================================================
-- OPS-04: Extend experiment_outcomes for Phase 36 A/B testing
-- Adds: p_value (NUMERIC), confidence_interval (JSONB),
--       minimum_sample_size (BIGINT)
-- NULL = "not yet computed" -- no defaults.
-- =============================================================================

ALTER TABLE experiment_outcomes
  ADD COLUMN IF NOT EXISTS p_value NUMERIC(10,8),
  ADD COLUMN IF NOT EXISTS confidence_interval JSONB,
  ADD COLUMN IF NOT EXISTS minimum_sample_size BIGINT;

-- p_value must be between 0 and 1 inclusive when present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'experiment_outcomes_p_value_check'
  ) THEN
    ALTER TABLE experiment_outcomes
      ADD CONSTRAINT experiment_outcomes_p_value_check
      CHECK (p_value IS NULL OR (p_value >= 0 AND p_value <= 1));
  END IF;
END $$;
