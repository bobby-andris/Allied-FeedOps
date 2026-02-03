-- 001_initial_schema.sql
-- Canonical Supabase schema for FeedOps workflow state management.
-- Apply to a fresh Supabase project.

-- SKU Approvals (element-level approval tracking)
CREATE TABLE IF NOT EXISTS sku_approvals (
    id BIGSERIAL PRIMARY KEY,
    master_sku TEXT NOT NULL UNIQUE,
    title_approved BOOLEAN,
    description_approved BOOLEAN,
    image_approved BOOLEAN,
    selected_finish TEXT,
    selected_image_index INTEGER,
    approval_status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON sku_approvals(approval_status, updated_at DESC);

-- Variant Approvals (per-finish approval tracking)
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

-- Publish Batches
CREATE TABLE IF NOT EXISTS publish_batches (
    id BIGSERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,
    name TEXT,
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_at TIMESTAMPTZ,
    sku_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_batches_status ON publish_batches(status, created_at DESC);

-- Batch SKU Assignments
CREATE TABLE IF NOT EXISTS batch_sku_assignments (
    id BIGSERIAL PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES publish_batches(batch_id),
    master_sku TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(batch_id, master_sku)
);

CREATE INDEX IF NOT EXISTS idx_batch_assignments ON batch_sku_assignments(batch_id, master_sku);

-- Publish Events
CREATE TABLE IF NOT EXISTS publish_events (
    id BIGSERIAL PRIMARY KEY,
    master_sku TEXT NOT NULL,
    platform TEXT NOT NULL,
    environment TEXT NOT NULL,
    action TEXT NOT NULL,
    patch_file TEXT NOT NULL DEFAULT '',
    quality_score REAL,
    approval_status TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_by TEXT,
    rollback_id BIGINT REFERENCES publish_events(id),
    batch_id TEXT,
    product_category TEXT,
    product_collection TEXT
);

CREATE INDEX IF NOT EXISTS idx_publish_sku_platform ON publish_events(master_sku, platform, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_batch ON publish_events(batch_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_category ON publish_events(product_category, published_at DESC);

-- Performance Baselines
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

-- Performance Snapshots
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

-- Enable Row Level Security (RLS)
ALTER TABLE sku_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE variant_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE publish_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_sku_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE publish_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_snapshots ENABLE ROW LEVEL SECURITY;

-- Allow anon key full access (dashboard auth is handled at app level)
CREATE POLICY "Allow all access" ON sku_approvals FOR ALL USING (true);
CREATE POLICY "Allow all access" ON variant_approvals FOR ALL USING (true);
CREATE POLICY "Allow all access" ON publish_batches FOR ALL USING (true);
CREATE POLICY "Allow all access" ON batch_sku_assignments FOR ALL USING (true);
CREATE POLICY "Allow all access" ON publish_events FOR ALL USING (true);
CREATE POLICY "Allow all access" ON performance_baselines FOR ALL USING (true);
CREATE POLICY "Allow all access" ON performance_snapshots FOR ALL USING (true);
