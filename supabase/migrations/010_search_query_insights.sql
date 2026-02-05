-- 010_search_query_insights.sql
-- Tables for Search Query Insights dashboard
-- Tracks Google Ads search terms at variant level with Keyword Planner enrichment

-- ============================================================================
-- Search Query Sync Jobs Table
-- ============================================================================
-- Tracks sync operations from Google Ads

CREATE TABLE IF NOT EXISTS search_query_sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    job_type TEXT NOT NULL DEFAULT 'search_terms'
        CHECK (job_type IN ('search_terms', 'keyword_planner', 'full_sync')),

    -- Config
    days_lookback INTEGER DEFAULT 30,
    limit_results INTEGER DEFAULT 1000,
    enrich_with_keyword_planner BOOLEAN DEFAULT false,

    -- Results
    queries_fetched INTEGER DEFAULT 0,
    queries_enriched INTEGER DEFAULT 0,
    error_message TEXT,

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- Search Queries Table (Variant Level)
-- ============================================================================
-- Stores search query data from Google Ads at VARIANT level

CREATE TABLE IF NOT EXISTS search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    campaign_id TEXT,

    -- Variant-level identification (links to variant_index)
    gmc_offer_id TEXT,          -- e.g., 'shopify_us_4545063682180_32128479625348'
    master_sku TEXT,
    finish TEXT,                -- e.g., 'Polished Chrome'
    finish_code TEXT,           -- e.g., 'PC'
    shopify_variant_id TEXT,

    -- Google Ads Metrics (actual performance)
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    conversions NUMERIC DEFAULT 0,
    conversion_value NUMERIC DEFAULT 0,
    cost_micros BIGINT DEFAULT 0,

    -- Computed metrics
    ctr NUMERIC GENERATED ALWAYS AS (
        CASE WHEN impressions > 0 THEN clicks::NUMERIC / impressions ELSE 0 END
    ) STORED,
    cvr NUMERIC GENERATED ALWAYS AS (
        CASE WHEN clicks > 0 THEN conversions / clicks ELSE 0 END
    ) STORED,

    -- Keyword Planner Metrics (market context)
    avg_monthly_searches INTEGER,
    competition TEXT CHECK (competition IN ('LOW', 'MEDIUM', 'HIGH', 'UNSPECIFIED', NULL)),
    competition_index INTEGER CHECK (competition_index IS NULL OR competition_index BETWEEN 0 AND 100),
    low_cpc_micros BIGINT,
    high_cpc_micros BIGINT,
    keyword_metrics_updated_at TIMESTAMPTZ,

    -- Time tracking
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    sync_job_id UUID REFERENCES search_query_sync_jobs(id) ON DELETE SET NULL,

    -- Prevent duplicates per period
    UNIQUE(query_text, gmc_offer_id, period_start, period_end)
);

-- ============================================================================
-- Search Queries by Master SKU (Aggregated View)
-- ============================================================================
-- Pre-aggregated queries per master SKU (across all variants)

CREATE TABLE IF NOT EXISTS search_queries_by_master_sku (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    query_text TEXT NOT NULL,

    -- Aggregated metrics across all variants
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_conversions NUMERIC DEFAULT 0,
    total_conversion_value NUMERIC DEFAULT 0,
    variant_count INTEGER DEFAULT 1,        -- how many variants triggered this query
    top_variant_finish TEXT,                -- finish with most impressions for this query
    top_variant_finish_code TEXT,

    -- Keyword Planner metrics (same across variants)
    avg_monthly_searches INTEGER,
    competition TEXT,
    competition_index INTEGER,

    -- Time tracking
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(master_sku, query_text, period_start, period_end)
);

-- ============================================================================
-- Keyword Metrics Cache
-- ============================================================================
-- Cached Keyword Planner data (rate-limited API, refresh monthly)

CREATE TABLE IF NOT EXISTS keyword_metrics (
    keyword TEXT PRIMARY KEY,
    avg_monthly_searches INTEGER,
    competition TEXT CHECK (competition IN ('LOW', 'MEDIUM', 'HIGH', 'UNSPECIFIED')),
    competition_index INTEGER CHECK (competition_index IS NULL OR competition_index BETWEEN 0 AND 100),
    low_cpc_micros BIGINT,
    high_cpc_micros BIGINT,

    -- Monthly search volume breakdown (last 12 months)
    monthly_searches JSONB,  -- [{year: 2026, month: 1, searches: 1200}, ...]

    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- Keyword Coverage Tables
-- ============================================================================
-- Track which keywords appear in content at variant and master level

-- Variant level (for Google/Bing)
CREATE TABLE IF NOT EXISTS keyword_coverage_variant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    finish TEXT NOT NULL,
    finish_code TEXT,
    gmc_offer_id TEXT,
    keyword TEXT NOT NULL,
    in_title BOOLEAN DEFAULT false,
    in_description BOOLEAN DEFAULT false,
    query_volume INTEGER DEFAULT 0,          -- impressions for this keyword
    avg_monthly_searches INTEGER,            -- from Keyword Planner
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(master_sku, finish, keyword)
);

-- Master level (for Shopify)
CREATE TABLE IF NOT EXISTS keyword_coverage_master (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    master_sku TEXT NOT NULL,
    keyword TEXT NOT NULL,
    in_title BOOLEAN DEFAULT false,
    in_description BOOLEAN DEFAULT false,
    query_volume INTEGER DEFAULT 0,
    avg_monthly_searches INTEGER,
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(master_sku, keyword)
);

-- ============================================================================
-- Finish Search Patterns
-- ============================================================================
-- Aggregated finish-specific search behavior

CREATE TABLE IF NOT EXISTS finish_search_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finish TEXT NOT NULL,
    finish_code TEXT NOT NULL,
    pattern_keyword TEXT NOT NULL,          -- e.g., 'antique brass', 'chrome', 'gold'
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    query_count INTEGER DEFAULT 1,          -- how many unique queries contain this keyword
    category TEXT,                          -- e.g., 'towel bars', 'grab bars'
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(finish_code, pattern_keyword, category)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Sync jobs indexes
CREATE INDEX IF NOT EXISTS idx_search_query_sync_jobs_status
    ON search_query_sync_jobs(status, created_at DESC);

-- Search queries indexes
CREATE INDEX IF NOT EXISTS idx_search_queries_gmc
    ON search_queries(gmc_offer_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_master_sku
    ON search_queries(master_sku);
CREATE INDEX IF NOT EXISTS idx_search_queries_finish
    ON search_queries(finish_code);
CREATE INDEX IF NOT EXISTS idx_search_queries_impressions
    ON search_queries(impressions DESC);
CREATE INDEX IF NOT EXISTS idx_search_queries_period
    ON search_queries(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_search_queries_sync_job
    ON search_queries(sync_job_id);

-- Aggregated queries indexes
CREATE INDEX IF NOT EXISTS idx_search_queries_by_master_sku
    ON search_queries_by_master_sku(master_sku);
CREATE INDEX IF NOT EXISTS idx_search_queries_by_master_sku_impressions
    ON search_queries_by_master_sku(total_impressions DESC);

-- Keyword coverage indexes
CREATE INDEX IF NOT EXISTS idx_keyword_coverage_variant_sku
    ON keyword_coverage_variant(master_sku, finish);
CREATE INDEX IF NOT EXISTS idx_keyword_coverage_variant_gaps
    ON keyword_coverage_variant(master_sku)
    WHERE in_title = false AND query_volume > 0;

CREATE INDEX IF NOT EXISTS idx_keyword_coverage_master_sku
    ON keyword_coverage_master(master_sku);
CREATE INDEX IF NOT EXISTS idx_keyword_coverage_master_gaps
    ON keyword_coverage_master(master_sku)
    WHERE in_title = false AND query_volume > 0;

-- Finish patterns indexes
CREATE INDEX IF NOT EXISTS idx_finish_search_patterns_finish
    ON finish_search_patterns(finish_code);
CREATE INDEX IF NOT EXISTS idx_finish_search_patterns_category
    ON finish_search_patterns(category, total_impressions DESC);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE search_query_sync_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries_by_master_sku ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_coverage_variant ENABLE ROW LEVEL SECURITY;
ALTER TABLE keyword_coverage_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE finish_search_patterns ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Allow all access" ON search_query_sync_jobs;
DROP POLICY IF EXISTS "Allow all access" ON search_queries;
DROP POLICY IF EXISTS "Allow all access" ON search_queries_by_master_sku;
DROP POLICY IF EXISTS "Allow all access" ON keyword_metrics;
DROP POLICY IF EXISTS "Allow all access" ON keyword_coverage_variant;
DROP POLICY IF EXISTS "Allow all access" ON keyword_coverage_master;
DROP POLICY IF EXISTS "Allow all access" ON finish_search_patterns;

-- Create policies (app-level auth, allow all authenticated access)
CREATE POLICY "Allow all access" ON search_query_sync_jobs FOR ALL USING (true);
CREATE POLICY "Allow all access" ON search_queries FOR ALL USING (true);
CREATE POLICY "Allow all access" ON search_queries_by_master_sku FOR ALL USING (true);
CREATE POLICY "Allow all access" ON keyword_metrics FOR ALL USING (true);
CREATE POLICY "Allow all access" ON keyword_coverage_variant FOR ALL USING (true);
CREATE POLICY "Allow all access" ON keyword_coverage_master FOR ALL USING (true);
CREATE POLICY "Allow all access" ON finish_search_patterns FOR ALL USING (true);
