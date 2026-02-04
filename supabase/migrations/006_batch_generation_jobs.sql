-- 006_batch_generation_jobs.sql
-- Tables for tracking batch SKU generation jobs (multi-SKU per job)
-- Separate from single-SKU generation_jobs table used by regenerate endpoint

-- ============================================================================
-- Batch Generation Jobs Table
-- ============================================================================
-- Tracks a batch generation request containing multiple SKUs

CREATE TABLE IF NOT EXISTS batch_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),

    -- SKU tracking
    total_skus INTEGER NOT NULL,
    completed_skus INTEGER DEFAULT 0,
    failed_skus INTEGER DEFAULT 0,

    -- Generation configuration
    options JSONB NOT NULL DEFAULT '{}',
    -- Expected options structure:
    -- {
    --   "titles": boolean,
    --   "descriptions": boolean,
    --   "images": boolean,
    --   "platforms": ["google", "bing", "shopify"],
    --   "num_candidates": number (optional, default 1)
    -- }

    -- Error tracking
    error_message TEXT,

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Requestor
    created_by TEXT
);

-- ============================================================================
-- Batch Generation Job SKUs Table
-- ============================================================================
-- Individual SKUs within a batch job

CREATE TABLE IF NOT EXISTS batch_generation_job_skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES batch_generation_jobs(id) ON DELETE CASCADE,
    master_sku TEXT NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,

    -- Results - references to generated content
    generated_content_ids UUID[],

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Ensure unique SKU per job
    UNIQUE(job_id, master_sku)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- For querying jobs by status (processing queue)
CREATE INDEX IF NOT EXISTS idx_batch_gen_jobs_status ON batch_generation_jobs(status, created_at);

-- For querying job progress
CREATE INDEX IF NOT EXISTS idx_batch_gen_job_skus_job ON batch_generation_job_skus(job_id);
CREATE INDEX IF NOT EXISTS idx_batch_gen_job_skus_status ON batch_generation_job_skus(job_id, status);

-- For finding jobs by user
CREATE INDEX IF NOT EXISTS idx_batch_gen_jobs_user ON batch_generation_jobs(created_by, created_at DESC);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE batch_generation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_generation_job_skus ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Allow all access" ON batch_generation_jobs;
DROP POLICY IF EXISTS "Allow all access" ON batch_generation_job_skus;

-- Create policies (app-level auth, allow all authenticated access)
CREATE POLICY "Allow all access" ON batch_generation_jobs FOR ALL USING (true);
CREATE POLICY "Allow all access" ON batch_generation_job_skus FOR ALL USING (true);
