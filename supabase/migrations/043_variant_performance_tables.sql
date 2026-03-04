-- Migration 043: Variant-level performance tables
-- Phase 8.1 — Data Model Gap Audit
--
-- Creates two new tables for storing per-offer-ID (variant-level) performance data:
--   1. performance_snapshots_variant  — daily snapshots per gmc_offer_id
--   2. performance_baselines_variant  — 30-day aggregates per gmc_offer_id
--
-- Design rationale:
-- - NEW tables (not extending performance_snapshots) to avoid 28x row bloat
--   and keep existing master_sku-level queries unchanged.
-- - gmc_offer_id stored in canonical lowercase (matches variant_index convention).
-- - Unique constraint on performance_snapshots_variant matches the on_conflict
--   columns that dual-write upserts in performance_impact.py will use.
-- - performance_baselines_variant uses composite PK (gmc_offer_id, platform)
--   mirroring the existing performance_baselines PK on (master_sku, platform).
--
-- Applied to: production (qezuszwufortkiutlhym)
-- Depends on: 042_schema_hardening.sql

-- ============================================================
-- Table 1: performance_snapshots_variant
-- Per-offer-ID daily snapshots. Only rows with impressions > 0
-- are written (enforced in Python, not DB constraint).
-- ============================================================

CREATE TABLE IF NOT EXISTS performance_snapshots_variant (
    id                  bigserial PRIMARY KEY,
    gmc_offer_id        text NOT NULL,
    master_sku          text NOT NULL,
    platform            text NOT NULL,
    environment         text NOT NULL DEFAULT 'production',
    snapshot_date       date NOT NULL,
    impressions         integer NOT NULL DEFAULT 0,
    clicks              integer NOT NULL DEFAULT 0,
    ctr                 real NOT NULL DEFAULT 0.0,
    conversions         integer NOT NULL DEFAULT 0,
    conversion_value    numeric(18,6) NOT NULL DEFAULT 0.0,
    cost                numeric(18,6) NOT NULL DEFAULT 0.0,
    roas                real NOT NULL DEFAULT 0.0,
    fetched_at          timestamptz NOT NULL DEFAULT now(),

    -- Unique constraint matching on_conflict columns for dual-write upserts.
    -- CRITICAL: Column order here must match on_conflict= parameter in Python upserts.
    CONSTRAINT uq_variant_snapshots_daily
        UNIQUE (gmc_offer_id, platform, environment, snapshot_date),

    CONSTRAINT chk_variant_snapshots_platform
        CHECK (platform IN ('google', 'bing', 'shopify')),

    CONSTRAINT chk_variant_snapshots_environment
        CHECK (environment IN ('staging', 'production'))
);

-- Index for lookups by master_sku (most common query pattern: "all variants for this SKU")
CREATE INDEX IF NOT EXISTS idx_variant_snapshots_master_sku
    ON performance_snapshots_variant (master_sku, platform, snapshot_date);

-- Index for lookups by offer ID, newest first (used in variant baseline computation)
CREATE INDEX IF NOT EXISTS idx_variant_snapshots_offer_date
    ON performance_snapshots_variant (gmc_offer_id, snapshot_date DESC);

-- ============================================================
-- Table 2: performance_baselines_variant
-- Per-offer-ID 30-day aggregates. Composite PK mirrors the
-- existing performance_baselines PK on (master_sku, platform).
-- ============================================================

CREATE TABLE IF NOT EXISTS performance_baselines_variant (
    gmc_offer_id            text NOT NULL,
    master_sku              text NOT NULL,
    platform                text NOT NULL,
    baseline_start_date     date NOT NULL,
    baseline_end_date       date NOT NULL,
    avg_impressions         real,
    avg_clicks              real,
    avg_ctr                 real,
    avg_conversions         real,
    avg_conversion_value    numeric(18,6),
    avg_cvr                 real,
    avg_cost                numeric(18,6),
    avg_roas                real,
    created_at              timestamptz NOT NULL DEFAULT now(),

    -- Composite PK mirrors performance_baselines PK on (master_sku, platform)
    CONSTRAINT pk_baselines_variant PRIMARY KEY (gmc_offer_id, platform),

    CONSTRAINT chk_baselines_variant_platform
        CHECK (platform IN ('google', 'bing', 'shopify'))
);

-- Index for lookups by master_sku (join from master-level baseline to variant baselines)
CREATE INDEX IF NOT EXISTS idx_baselines_variant_master_sku
    ON performance_baselines_variant (master_sku, platform);
