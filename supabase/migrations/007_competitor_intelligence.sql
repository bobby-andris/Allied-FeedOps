-- 007_competitor_intelligence.sql
-- Tables for competitor intelligence panel
-- Supports Google SERP analysis and marketplace scraping

-- ============================================================================
-- Competitor Scrape Jobs Table
-- ============================================================================
-- Tracks Apify scrape jobs for both SERP and marketplace sources

CREATE TABLE IF NOT EXISTS competitor_scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    job_type TEXT NOT NULL CHECK (job_type IN ('serp', 'marketplace')),
    category TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'google', 'amazon', 'wayfair', 'homedepot'
    search_query TEXT,     -- For SERP jobs, the search query used

    -- Apify tracking
    apify_run_id TEXT,
    apify_dataset_id TEXT,

    -- Results
    listings_count INTEGER DEFAULT 0,
    error_message TEXT,

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- Competitor Listings Table
-- ============================================================================
-- Stores scraped competitor data from both SERP and marketplace sources

CREATE TABLE IF NOT EXISTS competitor_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source info
    source TEXT NOT NULL,          -- 'google', 'amazon', 'wayfair', 'homedepot'
    source_type TEXT NOT NULL,     -- 'serp' or 'marketplace'
    source_url TEXT,
    domain TEXT,                   -- Extracted domain (for SERP grouping)

    -- Product info
    product_category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price NUMERIC,
    rating NUMERIC,
    review_count INTEGER,
    brand TEXT,
    position INTEGER,              -- Rank in search results
    image_url TEXT,

    -- Metadata
    scraped_at TIMESTAMPTZ DEFAULT now(),
    scrape_job_id UUID REFERENCES competitor_scrape_jobs(id) ON DELETE SET NULL,
    keywords_extracted TEXT[],

    -- Prevent duplicates
    UNIQUE(source, source_url)
);

-- ============================================================================
-- Competitor Patterns Table
-- ============================================================================
-- Extracted patterns from competitor content

CREATE TABLE IF NOT EXISTS competitor_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT NOT NULL,
    pattern_type TEXT NOT NULL,  -- 'title_structure', 'keyword', 'benefit', 'trust_signal', 'competitor_brand'
    pattern_value TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    avg_position NUMERIC,        -- Average search position of listings with this pattern
    sources TEXT[],              -- Which sources use this pattern
    example_titles TEXT[],       -- Representative examples
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- One pattern per category/type/value
    UNIQUE(category, pattern_type, pattern_value)
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Jobs indexes
CREATE INDEX IF NOT EXISTS idx_competitor_scrape_jobs_status
    ON competitor_scrape_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_competitor_scrape_jobs_category
    ON competitor_scrape_jobs(category, source);

-- Listings indexes
CREATE INDEX IF NOT EXISTS idx_competitor_listings_category
    ON competitor_listings(product_category);
CREATE INDEX IF NOT EXISTS idx_competitor_listings_source_type
    ON competitor_listings(source_type, product_category);
CREATE INDEX IF NOT EXISTS idx_competitor_listings_domain
    ON competitor_listings(domain);
CREATE INDEX IF NOT EXISTS idx_competitor_listings_job
    ON competitor_listings(scrape_job_id);

-- Patterns indexes
CREATE INDEX IF NOT EXISTS idx_competitor_patterns_category
    ON competitor_patterns(category, pattern_type);
CREATE INDEX IF NOT EXISTS idx_competitor_patterns_frequency
    ON competitor_patterns(category, frequency DESC);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE competitor_scrape_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_patterns ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Allow all access" ON competitor_scrape_jobs;
DROP POLICY IF EXISTS "Allow all access" ON competitor_listings;
DROP POLICY IF EXISTS "Allow all access" ON competitor_patterns;

-- Create policies (app-level auth, allow all authenticated access)
CREATE POLICY "Allow all access" ON competitor_scrape_jobs FOR ALL USING (true);
CREATE POLICY "Allow all access" ON competitor_listings FOR ALL USING (true);
CREATE POLICY "Allow all access" ON competitor_patterns FOR ALL USING (true);
