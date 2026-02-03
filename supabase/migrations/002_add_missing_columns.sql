-- 002_add_missing_columns.sql
-- Incremental migration for existing Supabase projects.
-- Adds columns that may be missing from older schema versions.

-- sku_approvals: rename columns if they exist with old names
-- (Supabase doesn't support RENAME COLUMN IF EXISTS, so these are best-effort)
-- If your project was created before this migration, manually rename:
--   status -> approval_status
--   revision_notes -> notes
--   reviewed_by -> approved_by
--   reviewed_at -> approved_at

-- publish_events: add missing columns
ALTER TABLE publish_events ADD COLUMN IF NOT EXISTS approval_status TEXT;
ALTER TABLE publish_events ADD COLUMN IF NOT EXISTS published_by TEXT;
ALTER TABLE publish_events ADD COLUMN IF NOT EXISTS rollback_id BIGINT REFERENCES publish_events(id);
ALTER TABLE publish_events ADD COLUMN IF NOT EXISTS product_category TEXT;
ALTER TABLE publish_events ADD COLUMN IF NOT EXISTS product_collection TEXT;

-- publish_batches: add missing columns
ALTER TABLE publish_batches ADD COLUMN IF NOT EXISTS target_date TEXT;
ALTER TABLE publish_batches ADD COLUMN IF NOT EXISTS sku_count INTEGER DEFAULT 0;
ALTER TABLE publish_batches ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE publish_batches ADD COLUMN IF NOT EXISTS failed_count INTEGER DEFAULT 0;

-- Create variant_approvals table if it doesn't exist
CREATE TABLE IF NOT EXISTS variant_approvals (
    id BIGSERIAL PRIMARY KEY,
    master_sku TEXT NOT NULL,
    finish TEXT NOT NULL,
    finish_code TEXT,
    title_approved BOOLEAN,
    description_approved BOOLEAN,
    image_approved BOOLEAN,
    selected_image_index INTEGER,
    approval_status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(master_sku, finish)
);

ALTER TABLE variant_approvals ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "Allow all access" ON variant_approvals FOR ALL USING (true);

-- Create performance tables if they don't exist
CREATE TABLE IF NOT EXISTS performance_baselines (
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    baseline_start_date TEXT NOT NULL,
    baseline_end_date TEXT NOT NULL,
    avg_impressions REAL,
    avg_clicks REAL,
    avg_ctr REAL,
    avg_conversions REAL,
    avg_conversion_value REAL,
    avg_cvr REAL,
    avg_cost REAL,
    avg_roas REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (master_sku, platform)
);

ALTER TABLE performance_baselines ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "Allow all access" ON performance_baselines FOR ALL USING (true);

CREATE TABLE IF NOT EXISTS performance_snapshots (
    id BIGSERIAL PRIMARY KEY,
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    environment TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0.0,
    conversions INTEGER DEFAULT 0,
    conversion_value REAL DEFAULT 0.0,
    cvr REAL DEFAULT 0.0,
    cost REAL DEFAULT 0.0,
    cpc REAL DEFAULT 0.0,
    roas REAL DEFAULT 0.0,
    publish_event_id BIGINT REFERENCES publish_events(id),
    content_version TEXT,
    days_since_publish INTEGER,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_sku_platform_date ON performance_snapshots(master_sku, platform, snapshot_date DESC);
ALTER TABLE performance_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "Allow all access" ON performance_snapshots FOR ALL USING (true);
