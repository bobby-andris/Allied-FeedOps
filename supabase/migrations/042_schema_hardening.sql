-- Migration 042: Schema Hardening
--
-- Purpose: Add missing constraints to data tables — fixing the 42P10 upsert failure that
-- blocks the daily performance snapshot job.
--
-- Requirements: SCHM-01, SCHM-02, SCHM-03, SCHM-04
--
-- SCHM-02 Audit Findings (informational — no action needed for these tables):
--   - performance_baselines: PK (master_sku, platform) already enforces uniqueness — no additional unique constraint needed
--   - search_queries: unique constraint on (query_text, gmc_offer_id, period_start, period_end) already present
--   - keyword_metrics: PK on keyword already present; no platform column (Google Ads only)
--   - funnel_snapshots_daily: unique on (snapshot_date, custom_label_0, tier) already present;
--     tier CHECK already present; no platform column — skip for SCHM-03
--   - performance_impact_scores: unique index uq_impact_scores_event_metric already present;
--     FK to publish_events already present
--   - performance_snapshots: FK performance_snapshots_publish_event_id_fkey already exists
--     (SCHM-04 Step 5 guards against duplicate FK creation)
--   - search_queries: no platform column (implicit Google Ads only) — skip for SCHM-03
--   - keyword_metrics: no platform column — skip for SCHM-03

BEGIN;

-- ============================================================
-- SCHM-01 Step 1: Dedup performance_snapshots
-- Keep newest row (latest fetched_at, then latest id) per
-- (master_sku, platform, environment, snapshot_date).
-- This is a prerequisite — must run before unique constraint add.
-- ============================================================
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

-- ============================================================
-- SCHM-01 Step 2: Add unique constraint on performance_snapshots
-- Matches the on_conflict= parameter in performance_impact.py:461
-- Fixes 42P10 error: "there is no unique constraint matching given keys"
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_performance_snapshots_daily'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT uq_performance_snapshots_daily
    UNIQUE (master_sku, platform, environment, snapshot_date);
  END IF;
END $$;

-- ============================================================
-- SCHM-03 Step 3: Platform CHECK constraints on 4 tables
-- Allowed values: google, bing, shopify (lowercase — DB convention)
-- Tables WITHOUT platform column (skip): search_queries, keyword_metrics, funnel_snapshots_daily
-- ============================================================

-- 3a: performance_snapshots
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_performance_snapshots_platform'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT chk_performance_snapshots_platform
    CHECK (platform IN ('google', 'bing', 'shopify'));
  END IF;
END $$;

-- 3b: performance_baselines
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_performance_baselines_platform'
      AND conrelid = 'performance_baselines'::regclass
  ) THEN
    ALTER TABLE performance_baselines
    ADD CONSTRAINT chk_performance_baselines_platform
    CHECK (platform IN ('google', 'bing', 'shopify'));
  END IF;
END $$;

-- 3c: performance_impact_scores
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_performance_impact_scores_platform'
      AND conrelid = 'performance_impact_scores'::regclass
  ) THEN
    ALTER TABLE performance_impact_scores
    ADD CONSTRAINT chk_performance_impact_scores_platform
    CHECK (platform IN ('google', 'bing', 'shopify'));
  END IF;
END $$;

-- 3d: generated_content
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_generated_content_platform'
      AND conrelid = 'generated_content'::regclass
  ) THEN
    ALTER TABLE generated_content
    ADD CONSTRAINT chk_generated_content_platform
    CHECK (platform IN ('google', 'bing', 'shopify'));
  END IF;
END $$;

-- ============================================================
-- SCHM-04 Step 4: Null out orphaned publish_event_id
-- Preserves snapshot metric data while enabling FK constraint.
-- Per decision: do NOT delete orphaned rows — metrics are valuable.
-- ============================================================
UPDATE performance_snapshots ps
SET publish_event_id = NULL
WHERE ps.publish_event_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM publish_events pe WHERE pe.id = ps.publish_event_id
  );

-- ============================================================
-- SCHM-04 Step 5: Add FK constraint on publish_event_id
-- Must run after orphan cleanup (Step 4) or will fail with FK violation.
-- Note: Pre-migration audit found performance_snapshots_publish_event_id_fkey
-- already exists (added by a prior migration). The guard below checks for ANY
-- FK from this table referencing publish_events to avoid adding a duplicate.
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_class r ON r.oid = c.confrelid
    WHERE c.contype = 'f'
      AND t.relname = 'performance_snapshots'
      AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
      AND r.relname = 'publish_events'
      AND EXISTS (
        SELECT 1
        FROM pg_attribute a
        JOIN unnest(c.conkey) AS k(col) ON a.attnum = k.col
        WHERE a.attrelid = t.oid AND a.attname = 'publish_event_id'
      )
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT fk_performance_snapshots_publish_event
    FOREIGN KEY (publish_event_id) REFERENCES publish_events(id);
  END IF;
END $$;

COMMIT;
