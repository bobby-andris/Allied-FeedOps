-- Phase 29 Plan 01: Create performance_impact_scores table and add missing performance_snapshots columns
-- This resolves schema drift discovered in Phase 28 audit (28-03-SUMMARY.md)

-- Step 1: Create performance_impact_scores table
CREATE TABLE IF NOT EXISTS performance_impact_scores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  publish_event_id bigint NOT NULL REFERENCES publish_events(id),
  master_sku text NOT NULL,
  platform text NOT NULL,
  environment text NOT NULL,
  metric_name text NOT NULL,
  pre_value numeric(18,8),
  post_value numeric(18,8),
  control_pre numeric(18,8),
  control_post numeric(18,8),
  did_lift_pct numeric(18,8),
  label text NOT NULL CHECK (label IN ('positive', 'negative', 'neutral')),
  confidence numeric(6,4) NOT NULL DEFAULT 0,
  sample_size_treated integer NOT NULL DEFAULT 0,
  sample_size_control integer NOT NULL DEFAULT 0,
  window_pre_days integer NOT NULL DEFAULT 30,
  window_post_days integer NOT NULL DEFAULT 30,
  run_date date NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_impact_scores_event_metric
  ON performance_impact_scores (publish_event_id, metric_name, platform, environment);
CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_publish_event ON performance_impact_scores (publish_event_id);
CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_master_sku ON performance_impact_scores (master_sku);
CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_run_date ON performance_impact_scores (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_metric ON performance_impact_scores (metric_name);
CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_label ON performance_impact_scores (label);

-- Step 2: Add missing columns to performance_snapshots
ALTER TABLE performance_snapshots ADD COLUMN IF NOT EXISTS cohort_type text;
ALTER TABLE performance_snapshots ADD COLUMN IF NOT EXISTS product_category text;

-- Add check constraint (only if not exists - use DO block to handle idempotency)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_performance_snapshots_cohort_type'
  ) THEN
    ALTER TABLE performance_snapshots ADD CONSTRAINT chk_performance_snapshots_cohort_type
      CHECK (cohort_type IS NULL OR cohort_type IN ('treated', 'control'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_cohort_date
  ON performance_snapshots (cohort_type, snapshot_date DESC);
