-- Migration 035: Measurement Infrastructure Schema
-- Phase 19 - Measurement Infrastructure
-- Adds schema for flag capture, cost tracking, prompt aliases, bottleneck
-- classifications, and GMC product status.

-- ============================================================
-- 1. Extend regeneration_history for MEAS-01
--    Capture feature flags, token usage, and latency per generation
-- ============================================================

ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS feature_flags_active JSONB,
  ADD COLUMN IF NOT EXISTS tokens_used INTEGER,
  ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
  ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6);

CREATE INDEX IF NOT EXISTS idx_regen_history_flags
  ON regeneration_history USING GIN (feature_flags_active);

-- ============================================================
-- 2. Create prompt_version_aliases for MEAS-03
--    Maps prompt hashes to human-readable version names
-- ============================================================

CREATE TABLE IF NOT EXISTS prompt_version_aliases (
  id          BIGSERIAL PRIMARY KEY,
  prompt_hash TEXT NOT NULL UNIQUE,
  alias       TEXT,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by  TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompt_version_aliases_hash
  ON prompt_version_aliases (prompt_hash);

-- ============================================================
-- 3. Create sku_bottleneck_classifications for MEAS-04
--    Stores per-SKU bottleneck classification results
-- ============================================================

CREATE TABLE IF NOT EXISTS sku_bottleneck_classifications (
  id                BIGSERIAL PRIMARY KEY,
  master_sku        TEXT NOT NULL,
  classification    TEXT NOT NULL,
  confidence        NUMERIC(4,2),
  evidence          JSONB,
  override_by       TEXT,
  override_note     TEXT,
  is_override       BOOLEAN DEFAULT false,
  classified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  publish_event_id  BIGINT
);

-- Partial unique index: only one non-override classification per master_sku
CREATE UNIQUE INDEX IF NOT EXISTS idx_sku_bottleneck_master_sku
  ON sku_bottleneck_classifications (master_sku)
  WHERE is_override = false;

CREATE INDEX IF NOT EXISTS idx_sku_bottleneck_classification
  ON sku_bottleneck_classifications (classification);

CREATE INDEX IF NOT EXISTS idx_sku_bottleneck_classified_at
  ON sku_bottleneck_classifications (classified_at DESC);

-- ============================================================
-- 4. Create gmc_product_status for MEAS-02
--    Stores GMC product approval status and item issues
-- ============================================================

CREATE TABLE IF NOT EXISTS gmc_product_status (
  id                BIGSERIAL PRIMARY KEY,
  gmc_offer_id      TEXT NOT NULL,
  master_sku        TEXT,
  offer_title       TEXT,
  status            TEXT NOT NULL,
  item_issues       JSONB,
  issue_count       INTEGER DEFAULT 0,
  disapproval_count INTEGER DEFAULT 0,
  synced_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  sync_job_id       UUID
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gmc_product_status_offer_id
  ON gmc_product_status (gmc_offer_id);

CREATE INDEX IF NOT EXISTS idx_gmc_product_status_master_sku
  ON gmc_product_status (master_sku);

CREATE INDEX IF NOT EXISTS idx_gmc_product_status_status
  ON gmc_product_status (status);

CREATE INDEX IF NOT EXISTS idx_gmc_product_status_synced_at
  ON gmc_product_status (synced_at DESC);
