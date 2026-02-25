-- Create funnel_snapshots_daily table for historical shopping funnel data
-- Phase 30-01: Historical Funnel Persistence

CREATE TABLE IF NOT EXISTS funnel_snapshots_daily (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  custom_label_0 TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('HIGH', 'MEDIUM', 'LOW')),
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  cost_micros BIGINT NOT NULL DEFAULT 0,
  conversions DOUBLE PRECISION NOT NULL DEFAULT 0,
  conversions_value DOUBLE PRECISION NOT NULL DEFAULT 0,
  roas DOUBLE PRECISION NOT NULL DEFAULT 0,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (snapshot_date, custom_label_0, tier)
);

CREATE INDEX IF NOT EXISTS idx_funnel_snapshots_date ON funnel_snapshots_daily (snapshot_date DESC);

ALTER TABLE funnel_snapshots_daily ENABLE ROW LEVEL SECURITY;
