-- Migration 026: Backfill Job Infrastructure Tables
--
-- Purpose: Create persistent storage for v1.0 data backfill infrastructure.
--
-- This migration establishes the foundational tables for managing historical
-- data backfill jobs (search terms, performance metrics, keyword planner, etc.)
-- with full checkpoint/resume capability for long-running batch operations.
--
-- Created: 2026-02-13

-- ============================================================================
-- Table: backfill_jobs
-- ============================================================================
-- Stores metadata and state for backfill jobs that process historical data
-- in batches. Supports checkpoint/resume for Cloud Run container restarts.

CREATE TABLE backfill_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'creating',
  total_items INTEGER NOT NULL,
  completed_items INTEGER DEFAULT 0,
  failed_items INTEGER DEFAULT 0,
  skus JSONB,                    -- Array of SKU strings to process
  checkpoint_data JSONB,         -- { "batch_index": 50, "last_sku": "920D-6" }
  config JSONB DEFAULT '{}',     -- Job config: { "batch_size": 10, "days_lookback": 180 }
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  eta_seconds INTEGER,
  created_by TEXT,

  -- Constraints
  CONSTRAINT valid_status CHECK (status IN ('creating', 'running', 'complete', 'failed', 'partial')),
  CONSTRAINT valid_job_type CHECK (job_type IN ('search_terms', 'performance_metrics', 'keyword_planner', 'custom_labels', 'full_backfill'))
);

-- Indexes for job queries and monitoring
CREATE INDEX idx_backfill_jobs_status ON backfill_jobs (status, created_at DESC);
CREATE INDEX idx_backfill_jobs_type ON backfill_jobs (job_type, created_at DESC);

-- ============================================================================
-- Table: backfill_job_errors
-- ============================================================================
-- Stores per-item error logs for backfill jobs to support debugging and
-- selective retry operations.

CREATE TABLE backfill_job_errors (
  id BIGSERIAL PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES backfill_jobs(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL,
  error_type TEXT NOT NULL,
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for job error lookups
CREATE INDEX idx_backfill_job_errors_job ON backfill_job_errors (job_id, created_at DESC);

-- ============================================================================
-- RPC Function: increment_backfill_failures
-- ============================================================================
-- Atomically increments the failed_items counter for a job. Used during
-- concurrent error logging to prevent race conditions.

CREATE OR REPLACE FUNCTION increment_backfill_failures(p_job_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE backfill_jobs
  SET failed_items = COALESCE(failed_items, 0) + 1
  WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;
