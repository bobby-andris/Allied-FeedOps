-- 032_performance_impact_pipeline.sql
-- Harden daily performance fact storage and add persisted impact scorecards.

BEGIN;

-- Convert text dates to true DATE types for performant date filtering.
ALTER TABLE performance_snapshots
ALTER COLUMN snapshot_date TYPE DATE
USING (
  CASE
    WHEN snapshot_date IS NULL THEN NULL
    WHEN snapshot_date::text ~ '^\d{4}-\d{2}-\d{2}$' THEN snapshot_date::date
    ELSE to_date(left(snapshot_date::text, 10), 'YYYY-MM-DD')
  END
);

ALTER TABLE performance_baselines
ALTER COLUMN baseline_start_date TYPE DATE
USING (
  CASE
    WHEN baseline_start_date IS NULL THEN NULL
    WHEN baseline_start_date::text ~ '^\d{4}-\d{2}-\d{2}$' THEN baseline_start_date::date
    ELSE to_date(left(baseline_start_date::text, 10), 'YYYY-MM-DD')
  END
),
ALTER COLUMN baseline_end_date TYPE DATE
USING (
  CASE
    WHEN baseline_end_date IS NULL THEN NULL
    WHEN baseline_end_date::text ~ '^\d{4}-\d{2}-\d{2}$' THEN baseline_end_date::date
    ELSE to_date(left(baseline_end_date::text, 10), 'YYYY-MM-DD')
  END
);

-- Use fixed precision for money-like metrics.
ALTER TABLE performance_snapshots
ALTER COLUMN conversion_value TYPE NUMERIC(18,6) USING COALESCE(conversion_value, 0)::NUMERIC(18,6),
ALTER COLUMN cost TYPE NUMERIC(18,6) USING COALESCE(cost, 0)::NUMERIC(18,6),
ALTER COLUMN cpc TYPE NUMERIC(18,6) USING COALESCE(cpc, 0)::NUMERIC(18,6);

ALTER TABLE performance_baselines
ALTER COLUMN avg_conversion_value TYPE NUMERIC(18,6) USING COALESCE(avg_conversion_value, 0)::NUMERIC(18,6),
ALTER COLUMN avg_cost TYPE NUMERIC(18,6) USING COALESCE(avg_cost, 0)::NUMERIC(18,6);

-- Collector metadata used for treated/control diff-in-diff cohorts.
ALTER TABLE performance_snapshots
ADD COLUMN IF NOT EXISTS cohort_type TEXT,
ADD COLUMN IF NOT EXISTS product_category TEXT;

UPDATE performance_snapshots
SET cohort_type = CASE
  WHEN publish_event_id IS NULL THEN 'control'
  ELSE 'treated'
END
WHERE cohort_type IS NULL;

-- Deduplicate historical rows before enforcing a daily unique key.
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY master_sku, platform, environment, snapshot_date
      ORDER BY fetched_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM performance_snapshots
)
DELETE FROM performance_snapshots p
USING ranked r
WHERE p.id = r.id
  AND r.rn > 1;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_performance_snapshots_daily'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT uq_performance_snapshots_daily
    UNIQUE (master_sku, platform, environment, snapshot_date);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_snapshot_date
  ON performance_snapshots(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_platform_snapshot_date
  ON performance_snapshots(platform, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_publish_event
  ON performance_snapshots(publish_event_id);

CREATE INDEX IF NOT EXISTS idx_performance_snapshots_cohort_date
  ON performance_snapshots(cohort_type, snapshot_date DESC);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_performance_snapshots_cohort_type'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT chk_performance_snapshots_cohort_type
    CHECK (cohort_type IN ('treated', 'control'));
  END IF;
END $$;

-- Persisted scorecards by publish event + metric for dashboard reads.
CREATE TABLE IF NOT EXISTS performance_impact_scores (
  id BIGSERIAL PRIMARY KEY,
  publish_event_id BIGINT NOT NULL REFERENCES publish_events(id) ON DELETE CASCADE,
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  environment TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  pre_value NUMERIC(18,8),
  post_value NUMERIC(18,8),
  control_pre NUMERIC(18,8),
  control_post NUMERIC(18,8),
  did_lift_pct NUMERIC(18,8),
  label TEXT NOT NULL,
  confidence NUMERIC(6,4) NOT NULL DEFAULT 0,
  sample_size_treated INTEGER NOT NULL DEFAULT 0,
  sample_size_control INTEGER NOT NULL DEFAULT 0,
  window_pre_days INTEGER NOT NULL DEFAULT 30,
  window_post_days INTEGER NOT NULL DEFAULT 30,
  run_date DATE NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (publish_event_id, metric_name, platform, environment)
);

CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_publish_event
  ON performance_impact_scores(publish_event_id);

CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_master_sku
  ON performance_impact_scores(master_sku);

CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_run_date
  ON performance_impact_scores(run_date DESC);

CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_metric
  ON performance_impact_scores(metric_name);

CREATE INDEX IF NOT EXISTS idx_performance_impact_scores_label
  ON performance_impact_scores(label);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_performance_impact_scores_label'
      AND conrelid = 'performance_impact_scores'::regclass
  ) THEN
    ALTER TABLE performance_impact_scores
    ADD CONSTRAINT chk_performance_impact_scores_label
    CHECK (label IN ('positive', 'negative', 'neutral'));
  END IF;
END $$;

ALTER TABLE performance_impact_scores ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'performance_impact_scores'
      AND policyname = 'Allow all access'
  ) THEN
    CREATE POLICY "Allow all access"
    ON performance_impact_scores
    FOR ALL
    USING (true);
  END IF;
END $$;

COMMIT;
