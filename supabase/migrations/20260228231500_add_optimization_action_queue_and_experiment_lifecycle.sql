-- R5: Prioritization queue + experiment lifecycle control plane

CREATE TABLE IF NOT EXISTS optimization_action_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_key TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL DEFAULT 'lineage_outcome',
  source_ref TEXT,
  change_package_id UUID REFERENCES change_packages(id) ON DELETE SET NULL,
  generation_effect_window_id BIGINT REFERENCES generation_effect_windows(id) ON DELETE SET NULL,
  experiment_key TEXT REFERENCES experiment_registry(experiment_key) ON DELETE SET NULL,
  master_sku TEXT,
  platform TEXT,
  action_type TEXT NOT NULL,
  title TEXT NOT NULL,
  rationale TEXT,
  recommended_payload JSONB,
  current_state TEXT NOT NULL DEFAULT 'proposed',
  priority_score DOUBLE PRECISION,
  expected_revenue_impact DOUBLE PRECISION,
  confidence_score DOUBLE PRECISION,
  effort_score DOUBLE PRECISION,
  policy_risk_score DOUBLE PRECISION,
  approved_by TEXT,
  approved_at TIMESTAMPTZ,
  executed_at TIMESTAMPTZ,
  validated_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'optimization_action_queue_state_check'
  ) THEN
    ALTER TABLE optimization_action_queue
      ADD CONSTRAINT optimization_action_queue_state_check
      CHECK (current_state IN ('proposed', 'approved', 'executing', 'validated', 'rejected'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_optimization_action_queue_state_created
  ON optimization_action_queue (current_state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_action_queue_master_platform
  ON optimization_action_queue (master_sku, platform, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_action_queue_priority
  ON optimization_action_queue (priority_score DESC NULLS LAST, created_at DESC);

CREATE TABLE IF NOT EXISTS optimization_action_scores (
  id BIGSERIAL PRIMARY KEY,
  action_id UUID NOT NULL REFERENCES optimization_action_queue(id) ON DELETE CASCADE,
  score_version TEXT NOT NULL DEFAULT 'r5.v1',
  expected_revenue_impact DOUBLE PRECISION NOT NULL DEFAULT 0,
  confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  effort_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  policy_risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  composite_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  inputs JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (action_id, score_version)
);

CREATE INDEX IF NOT EXISTS idx_optimization_action_scores_action_created
  ON optimization_action_scores (action_id, created_at DESC);

CREATE TABLE IF NOT EXISTS experiment_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_key TEXT NOT NULL UNIQUE,
  experiment_key TEXT NOT NULL REFERENCES experiment_registry(experiment_key) ON DELETE RESTRICT,
  action_id UUID REFERENCES optimization_action_queue(id) ON DELETE SET NULL,
  change_package_id UUID REFERENCES change_packages(id) ON DELETE SET NULL,
  generation_effect_window_id BIGINT REFERENCES generation_effect_windows(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  gate_status TEXT,
  gate_results JSONB,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  owner TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'experiment_runs_status_check'
  ) THEN
    ALTER TABLE experiment_runs
      ADD CONSTRAINT experiment_runs_status_check
      CHECK (status IN ('proposed', 'approved', 'executing', 'validated', 'rejected'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_experiment_runs_status_created
  ON experiment_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_experiment_key
  ON experiment_runs (experiment_key, created_at DESC);

CREATE TABLE IF NOT EXISTS experiment_candidates (
  id BIGSERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES experiment_runs(id) ON DELETE CASCADE,
  candidate_key TEXT NOT NULL,
  generated_content_id UUID REFERENCES generated_content(id) ON DELETE SET NULL,
  regeneration_history_id UUID REFERENCES regeneration_history(id) ON DELETE SET NULL,
  request_id TEXT,
  master_sku TEXT,
  platform TEXT,
  content_type TEXT,
  cohort TEXT,
  status TEXT NOT NULL DEFAULT 'proposed',
  observed_lift DOUBLE PRECISION,
  sample_size INTEGER,
  metrics JSONB,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, candidate_key)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'experiment_candidates_cohort_check'
  ) THEN
    ALTER TABLE experiment_candidates
      ADD CONSTRAINT experiment_candidates_cohort_check
      CHECK (cohort IS NULL OR cohort IN ('control', 'treatment', 'holdout'));
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'experiment_candidates_status_check'
  ) THEN
    ALTER TABLE experiment_candidates
      ADD CONSTRAINT experiment_candidates_status_check
      CHECK (status IN ('proposed', 'approved', 'executing', 'validated', 'rejected'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_experiment_candidates_run_status
  ON experiment_candidates (run_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiment_candidates_request_id
  ON experiment_candidates (request_id)
  WHERE request_id IS NOT NULL;

DROP TRIGGER IF EXISTS update_optimization_action_queue_updated_at ON optimization_action_queue;
CREATE TRIGGER update_optimization_action_queue_updated_at
  BEFORE UPDATE ON optimization_action_queue
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_runs_updated_at ON experiment_runs;
CREATE TRIGGER update_experiment_runs_updated_at
  BEFORE UPDATE ON experiment_runs
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_candidates_updated_at ON experiment_candidates;
CREATE TRIGGER update_experiment_candidates_updated_at
  BEFORE UPDATE ON experiment_candidates
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE optimization_action_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_action_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_candidates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access" ON optimization_action_queue;
DROP POLICY IF EXISTS "Allow all access" ON optimization_action_scores;
DROP POLICY IF EXISTS "Allow all access" ON experiment_runs;
DROP POLICY IF EXISTS "Allow all access" ON experiment_candidates;

CREATE POLICY "Allow all access" ON optimization_action_queue FOR ALL USING (true);
CREATE POLICY "Allow all access" ON optimization_action_scores FOR ALL USING (true);
CREATE POLICY "Allow all access" ON experiment_runs FOR ALL USING (true);
CREATE POLICY "Allow all access" ON experiment_candidates FOR ALL USING (true);

COMMENT ON TABLE optimization_action_queue IS
  'Prioritized optimization queue used to move actions through proposed->approved->executing->validated/rejected states.';

COMMENT ON TABLE optimization_action_scores IS
  'Versioned scoring snapshots for queue actions (impact, confidence, effort, and policy risk).';

COMMENT ON TABLE experiment_runs IS
  'Execution lifecycle for optimization experiments linked to queue actions, change packages, and effect windows.';

COMMENT ON TABLE experiment_candidates IS
  'Candidate variants and observed metrics tracked inside an experiment run lifecycle.';
