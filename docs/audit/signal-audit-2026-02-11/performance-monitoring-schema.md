# Long-Term Performance Monitoring Schema Design

## 1. Current State Assessment

### Existing Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `performance_baselines` | 168 | Pre-publish 30-day averages (one row per master_sku + platform) |
| `performance_snapshots` | 1 | Post-publish point-in-time metrics |
| `search_query_snapshots` | 0 | Search query performance over time |
| `publish_events` | 29 | Audit log of publish actions (3 distinct SKUs published) |
| `variant_index` | 72,023 | All variants (2,784 master SKUs) |

### Database Size
- Current: 209 MB
- Supabase Pro plan: 8 GB database included, then $0.125/GB/month

### Available Extensions (NOT installed yet)
- `pg_cron` 1.6.4 - Scheduled jobs within Postgres
- `pg_partman` 5.3.1 - Partition management
- `timescaledb` - NOT available on this Supabase instance

### Current Schema Issues

1. **`snapshot_date` is `text` not `date`** in `performance_snapshots` - prevents efficient date-range queries and partitioning
2. **No unique constraint** on `performance_snapshots` (master_sku, platform, snapshot_date) - allows duplicate snapshots
3. **No deduplication** in capture code - running capture twice on same day creates duplicate rows
4. **`real` type for financial metrics** - floating point imprecision; should be `numeric` for cost/value fields
5. **Single composite index** `(master_sku, platform, snapshot_date DESC)` covers the primary query but won't help aggregate queries across all SKUs by date
6. **No FK constraint** from `performance_snapshots.publish_event_id` to `publish_events.id`

---

## 2. Growth Projections

### Scale Parameters
- **Published SKUs today**: 3 (of 2,784 master SKUs)
- **Target scale**: 500-2,000 master SKUs published within 12 months
- **Platforms**: 2 (Google, Bing)
- **Variants per master SKU**: ~26 average (72,023 / 2,784)

### Snapshot Granularity Analysis

Snapshots are captured at the **master_sku + platform** level (not per-variant), because:
- Google Ads reports at product_id level, which maps to master_sku
- Baselines are stored at master_sku + platform granularity
- Dashboard queries compare baseline vs snapshot at master_sku level

| Scenario | Frequency | Rows/Year | Storage Est. |
|----------|-----------|-----------|-------------|
| 500 SKUs x 2 platforms, weekly | 52/yr | 52,000 | ~5 MB |
| 1,000 SKUs x 2 platforms, weekly | 52/yr | 104,000 | ~10 MB |
| 2,000 SKUs x 2 platforms, weekly | 52/yr | 208,000 | ~20 MB |
| 2,000 SKUs x 2 platforms, daily | 365/yr | 1,460,000 | ~140 MB |

**Recommendation: Weekly snapshots** for the first year. At 2,000 published SKUs with weekly collection, that is only ~208K rows/year — well within Supabase Pro limits. Daily collection can be reserved for the first 30 days post-publish when changes are most meaningful.

### Search Query Snapshots

Search query snapshots are much larger because each SKU can have 50-200+ search terms:
- 1,000 SKUs x 100 queries x 2 platforms x 12 monthly = ~2.4M rows/year
- 2,000 SKUs x 100 queries x 2 platforms x 12 monthly = ~4.8M rows/year

**Recommendation: Monthly snapshots** for search queries, with the unique constraint already in place `(query_text, master_sku, snapshot_date)`.

---

## 3. Proposed Schema Changes

### 3.1 Fix `performance_snapshots` (Migration)

```sql
-- Migration: fix_performance_snapshots_schema.sql

-- 1. Convert snapshot_date from text to date
ALTER TABLE performance_snapshots
  ALTER COLUMN snapshot_date TYPE date USING snapshot_date::date;

-- 2. Add unique constraint to prevent duplicate snapshots
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique
  ON performance_snapshots (master_sku, platform, snapshot_date);

-- 3. Add FK to publish_events
ALTER TABLE performance_snapshots
  ADD CONSTRAINT fk_snapshots_publish_event
  FOREIGN KEY (publish_event_id) REFERENCES publish_events(id);

-- 4. Add index for aggregate-by-date queries (dashboard overview)
CREATE INDEX IF NOT EXISTS idx_snapshots_date
  ON performance_snapshots (snapshot_date DESC);

-- 5. Add index for days_since_publish range queries
CREATE INDEX IF NOT EXISTS idx_snapshots_days_since_publish
  ON performance_snapshots (days_since_publish);
```

### 3.2 New Table: `performance_rollups` (Weekly/Monthly Aggregates)

For long-term trend analysis, pre-compute aggregated metrics rather than querying raw snapshots.

```sql
CREATE TABLE performance_rollups (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  master_sku text NOT NULL,
  platform text NOT NULL,
  rollup_period text NOT NULL,          -- 'weekly' or 'monthly'
  period_start date NOT NULL,           -- Monday of week or 1st of month
  period_end date NOT NULL,             -- Sunday of week or last day of month

  -- Aggregated metrics (averages over the period)
  avg_impressions numeric,
  avg_clicks numeric,
  avg_ctr numeric,
  avg_conversions numeric,
  avg_conversion_value numeric,
  avg_cvr numeric,
  avg_cost numeric,
  avg_roas numeric,

  -- Min/Max for sparklines
  min_ctr numeric,
  max_ctr numeric,
  min_impressions integer,
  max_impressions integer,

  -- Delta from baseline (pre-computed)
  baseline_ctr_delta numeric,           -- (avg_ctr - baseline_avg_ctr) / baseline_avg_ctr * 100
  baseline_impressions_delta numeric,
  baseline_roas_delta numeric,

  -- Metadata
  snapshot_count integer NOT NULL DEFAULT 0,  -- How many raw snapshots contributed
  publish_event_id bigint REFERENCES publish_events(id),
  days_since_publish_start integer,     -- days_since_publish at period_start
  days_since_publish_end integer,       -- days_since_publish at period_end

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE (master_sku, platform, rollup_period, period_start)
);

CREATE INDEX idx_rollups_sku_platform
  ON performance_rollups (master_sku, platform, period_start DESC);
CREATE INDEX idx_rollups_period
  ON performance_rollups (rollup_period, period_start DESC);
```

### 3.3 New Table: `monitoring_alerts` (Threshold-Based Notifications)

```sql
CREATE TABLE monitoring_alerts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  master_sku text NOT NULL,
  platform text NOT NULL,
  alert_type text NOT NULL,             -- 'ctr_drop', 'impressions_drop', 'roas_drop', 'ctr_improvement'
  severity text NOT NULL DEFAULT 'info', -- 'critical', 'warning', 'info'

  -- Alert details
  metric_name text NOT NULL,            -- 'ctr', 'impressions', 'roas', etc.
  baseline_value numeric,
  current_value numeric,
  delta_percent numeric,
  threshold_percent numeric,            -- What threshold triggered this

  -- State
  acknowledged boolean NOT NULL DEFAULT false,
  acknowledged_by text,
  acknowledged_at timestamptz,
  resolved boolean NOT NULL DEFAULT false,
  resolved_at timestamptz,

  -- Context
  publish_event_id bigint REFERENCES publish_events(id),
  days_since_publish integer,
  snapshot_date date,

  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_unresolved
  ON monitoring_alerts (resolved, severity, created_at DESC)
  WHERE resolved = false;
CREATE INDEX idx_alerts_sku
  ON monitoring_alerts (master_sku, platform, created_at DESC);
```

### 3.4 New Table: `search_query_rollups` (Monthly Search Aggregates)

```sql
CREATE TABLE search_query_rollups (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  master_sku text NOT NULL,
  platform text NOT NULL DEFAULT 'google',
  rollup_month date NOT NULL,           -- First day of month

  -- Aggregate search metrics
  total_unique_queries integer,
  total_impressions bigint,
  total_clicks bigint,
  total_conversions numeric,
  total_cost_micros bigint,
  avg_ctr numeric,

  -- Top queries (JSONB array, top 20 by impressions)
  top_queries jsonb,                    -- [{query_text, impressions, clicks, ctr}, ...]

  -- New/lost query counts
  new_queries_count integer DEFAULT 0,
  lost_queries_count integer DEFAULT 0,

  -- Delta from previous month
  query_count_delta integer,
  impressions_delta_percent numeric,

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE (master_sku, platform, rollup_month)
);

CREATE INDEX idx_search_rollups_month
  ON search_query_rollups (rollup_month DESC);
```

---

## 4. Partitioning Strategy

### Should We Partition?

**Not yet.** Here is the reasoning:

| Factor | Assessment |
|--------|-----------|
| Current rows | 1 (performance_snapshots), 0 (search_query_snapshots) |
| Year-1 projected | ~208K snapshots, ~2.4M search query snapshots |
| Partition benefit threshold | Typically 10M+ rows for meaningful benefit |
| Supabase pg_partman | Available but adds operational complexity |

**When to introduce partitioning:**
- When `performance_snapshots` exceeds **5M rows** (~Year 3-4 at full scale)
- When `search_query_snapshots` exceeds **10M rows** (~Year 2 at full scale)
- Strategy: Range partition by `snapshot_date` in monthly chunks

**Prepare for future partitioning now** by:
1. Using `date` type for `snapshot_date` (not text) -- enables range partitioning later
2. Always including `snapshot_date` in queries (future partition key)
3. Keeping the rollup tables as the primary query target for dashboards (reduces need to scan raw data)

### Retention Policy

| Data Tier | Retention | Action |
|-----------|-----------|--------|
| Raw daily snapshots | 90 days | DELETE rows older than 90 days (pg_cron weekly) |
| Raw weekly snapshots | 2 years | DELETE rows older than 2 years |
| Weekly rollups | 2 years | DELETE rollups older than 2 years |
| Monthly rollups | Forever | Never delete |
| Search query snapshots (raw) | 6 months | DELETE; rely on monthly rollups after |
| Search query rollups | Forever | Never delete |
| Baselines | Forever | One row per SKU/platform, updated on re-publish |
| Alerts | 1 year | DELETE resolved alerts older than 1 year |

---

## 5. Collection Schedule Design

### Recommended Collection Cadence

```
Phase 1: Post-Publish (Days 0-30)
  - Daily performance snapshots for newly published SKUs
  - Captures the critical "settling period" after content changes
  - Trigger: Scheduled job checks publish_events for recent publishes

Phase 2: Steady State (Days 31+)
  - Weekly performance snapshots (every Monday)
  - Monthly search query snapshots (1st of month)
  - Weekly rollup computation (every Monday for prior week)
  - Monthly rollup computation (1st of month for prior month)

Phase 3: Cleanup
  - Weekly: Delete raw daily snapshots older than 90 days
  - Monthly: Delete raw weekly snapshots older than 2 years
  - Monthly: Delete raw search query snapshots older than 6 months
```

### pg_cron Implementation

```sql
-- Enable pg_cron
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 1. Weekly performance snapshot capture (Mondays at 6 AM UTC)
-- This calls a Supabase Edge Function that runs the capture logic
SELECT cron.schedule(
  'weekly-performance-snapshots',
  '0 6 * * 1',  -- Every Monday at 06:00 UTC
  $$SELECT net.http_post(
    url := 'https://allied-feed-ops.vercel.app/api/performance/capture-snapshot',
    headers := '{"Content-Type": "application/json"}'::jsonb
  )$$
);

-- 2. Weekly rollup computation (Mondays at 8 AM UTC, after snapshot capture)
SELECT cron.schedule(
  'weekly-rollup-computation',
  '0 8 * * 1',
  $$SELECT compute_weekly_rollups()$$
);

-- 3. Monthly search query snapshot (1st of month at 6 AM UTC)
SELECT cron.schedule(
  'monthly-search-snapshots',
  '0 6 1 * *',
  $$SELECT net.http_post(
    url := 'https://feedops-pipeline-623866089882.us-east1.run.app/search-insights/sync',
    headers := '{"Content-Type": "application/json"}'::jsonb,
    body := '{"snapshot_mode": true}'::jsonb
  )$$
);

-- 4. Monthly rollup + cleanup (2nd of month at 6 AM UTC)
SELECT cron.schedule(
  'monthly-rollup-and-cleanup',
  '0 6 2 * *',
  $$
    SELECT compute_monthly_rollups();
    SELECT cleanup_old_snapshots();
  $$
);
```

### Helper Functions

```sql
-- Compute weekly rollups from raw snapshots
CREATE OR REPLACE FUNCTION compute_weekly_rollups()
RETURNS void AS $$
BEGIN
  INSERT INTO performance_rollups (
    master_sku, platform, rollup_period, period_start, period_end,
    avg_impressions, avg_clicks, avg_ctr, avg_conversions,
    avg_conversion_value, avg_cvr, avg_cost, avg_roas,
    min_ctr, max_ctr, min_impressions, max_impressions,
    baseline_ctr_delta, baseline_impressions_delta, baseline_roas_delta,
    snapshot_count, publish_event_id, days_since_publish_start, days_since_publish_end
  )
  SELECT
    s.master_sku, s.platform, 'weekly',
    date_trunc('week', s.snapshot_date)::date AS period_start,
    (date_trunc('week', s.snapshot_date) + interval '6 days')::date AS period_end,
    AVG(s.impressions), AVG(s.clicks), AVG(s.ctr), AVG(s.conversions),
    AVG(s.conversion_value), AVG(s.cvr), AVG(s.cost), AVG(s.roas),
    MIN(s.ctr), MAX(s.ctr), MIN(s.impressions), MAX(s.impressions),
    -- Baseline deltas
    CASE WHEN b.avg_ctr > 0
      THEN ((AVG(s.ctr) - b.avg_ctr) / b.avg_ctr * 100)
      ELSE NULL END,
    CASE WHEN b.avg_impressions > 0
      THEN ((AVG(s.impressions) - b.avg_impressions) / b.avg_impressions * 100)
      ELSE NULL END,
    CASE WHEN b.avg_roas > 0
      THEN ((AVG(s.roas) - b.avg_roas) / b.avg_roas * 100)
      ELSE NULL END,
    COUNT(*),
    MAX(s.publish_event_id),
    MIN(s.days_since_publish), MAX(s.days_since_publish)
  FROM performance_snapshots s
  LEFT JOIN performance_baselines b
    ON s.master_sku = b.master_sku AND s.platform = b.platform
  WHERE s.snapshot_date >= date_trunc('week', CURRENT_DATE - interval '1 week')::date
    AND s.snapshot_date < date_trunc('week', CURRENT_DATE)::date
  GROUP BY s.master_sku, s.platform,
    date_trunc('week', s.snapshot_date), b.avg_ctr, b.avg_impressions, b.avg_roas
  ON CONFLICT (master_sku, platform, rollup_period, period_start)
  DO UPDATE SET
    avg_impressions = EXCLUDED.avg_impressions,
    avg_clicks = EXCLUDED.avg_clicks,
    avg_ctr = EXCLUDED.avg_ctr,
    avg_conversions = EXCLUDED.avg_conversions,
    avg_conversion_value = EXCLUDED.avg_conversion_value,
    avg_cvr = EXCLUDED.avg_cvr,
    avg_cost = EXCLUDED.avg_cost,
    avg_roas = EXCLUDED.avg_roas,
    snapshot_count = EXCLUDED.snapshot_count,
    created_at = now();
END;
$$ LANGUAGE plpgsql;

-- Cleanup old raw snapshots
CREATE OR REPLACE FUNCTION cleanup_old_snapshots()
RETURNS void AS $$
BEGIN
  -- Delete raw daily snapshots older than 90 days
  DELETE FROM performance_snapshots
  WHERE snapshot_date < CURRENT_DATE - interval '90 days'
    AND snapshot_date NOT IN (
      -- Keep one snapshot per week (the most recent per week)
      SELECT DISTINCT ON (master_sku, platform, date_trunc('week', snapshot_date))
        snapshot_date
      FROM performance_snapshots
      WHERE snapshot_date < CURRENT_DATE - interval '90 days'
      ORDER BY master_sku, platform, date_trunc('week', snapshot_date), snapshot_date DESC
    );

  -- Delete raw search query snapshots older than 6 months
  DELETE FROM search_query_snapshots
  WHERE snapshot_date < CURRENT_DATE - interval '6 months';

  -- Delete resolved alerts older than 1 year
  DELETE FROM monitoring_alerts
  WHERE resolved = true AND created_at < now() - interval '1 year';
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Dashboard Query Optimization

### Current Query Patterns (from monitoring API routes)

1. **"Show performance for SKU X over time"**
   - Current: `SELECT * FROM performance_snapshots WHERE master_sku = X ORDER BY snapshot_date DESC`
   - Optimized: Query `performance_rollups` for long-term view, raw snapshots for last 90 days
   - Index: `idx_rollups_sku_platform` covers this

2. **"Which SKUs improved most after publish?"**
   - Current: App-side delta calculation (fetch all snapshots + all baselines, compute in TS)
   - Optimized: Query `performance_rollups` where `baseline_ctr_delta > 0 ORDER BY baseline_ctr_delta DESC`
   - Pre-computed deltas eliminate app-side computation

3. **"Aggregate CTR trend across all published SKUs"**
   - Current: Not efficiently supported
   - Optimized: `SELECT period_start, AVG(avg_ctr) FROM performance_rollups WHERE rollup_period = 'weekly' GROUP BY period_start ORDER BY period_start`
   - Index: `idx_rollups_period` covers this

4. **"Alert me when CTR drops >20% from baseline"**
   - Current: Not supported
   - Optimized: `monitoring_alerts` table populated by rollup computation function

### Materialized View: Portfolio Performance Summary

```sql
CREATE MATERIALIZED VIEW mv_portfolio_performance AS
SELECT
  COUNT(DISTINCT r.master_sku) AS total_monitored_skus,
  r.platform,
  r.rollup_period,
  r.period_start,

  -- Averages across all SKUs
  AVG(r.avg_ctr) AS portfolio_avg_ctr,
  AVG(r.avg_roas) AS portfolio_avg_roas,
  SUM(r.avg_impressions) AS portfolio_total_impressions,
  SUM(r.avg_clicks) AS portfolio_total_clicks,
  SUM(r.avg_conversions) AS portfolio_total_conversions,
  SUM(r.avg_conversion_value) AS portfolio_total_value,

  -- Improvement rates
  AVG(r.baseline_ctr_delta) AS avg_ctr_improvement,
  COUNT(*) FILTER (WHERE r.baseline_ctr_delta > 0) AS improving_count,
  COUNT(*) FILTER (WHERE r.baseline_ctr_delta < 0) AS declining_count,
  COUNT(*) FILTER (WHERE r.baseline_ctr_delta BETWEEN -5 AND 5) AS stable_count
FROM performance_rollups r
WHERE r.rollup_period = 'weekly'
GROUP BY r.platform, r.rollup_period, r.period_start
ORDER BY r.period_start DESC;

CREATE UNIQUE INDEX idx_mv_portfolio
  ON mv_portfolio_performance (platform, rollup_period, period_start);

-- Refresh weekly after rollup computation
-- (Add to pg_cron schedule)
```

---

## 7. Days-Since-Publish Dimension

### Current Approach
- Computed at snapshot capture time: `Math.floor((now - publishDate) / (1000*60*60*24))`
- Stored as integer in `days_since_publish` column

### Issues
1. If a SKU is re-published, `days_since_publish` resets — historical trend breaks
2. No way to compare "performance at day 14" across different SKUs published at different times

### Proposed Solution: Publish Cohort Analysis

The `publish_event_id` FK already ties each snapshot to a specific publish event. This enables cohort analysis:

```sql
-- "How did all SKUs perform at day 14 after their respective publishes?"
SELECT
  r.master_sku,
  r.days_since_publish_start,
  r.baseline_ctr_delta
FROM performance_rollups r
WHERE r.days_since_publish_start BETWEEN 12 AND 16  -- ~2 weeks post-publish
ORDER BY r.baseline_ctr_delta DESC;

-- "Performance trajectory for a specific publish cohort"
SELECT
  r.period_start,
  r.days_since_publish_start,
  r.avg_ctr,
  r.baseline_ctr_delta
FROM performance_rollups r
WHERE r.publish_event_id = 123
ORDER BY r.period_start;
```

For re-published SKUs:
- Each publish creates a new `publish_events` row
- Snapshots after re-publish reference the new `publish_event_id`
- Old snapshots retain their original `publish_event_id`
- Rollups inherit `publish_event_id` from their constituent snapshots

---

## 8. Migration Plan

### Phase 1: Schema Fixes (Immediate)

1. Convert `snapshot_date` to `date` type
2. Add unique constraint on `(master_sku, platform, snapshot_date)`
3. Add FK constraint to `publish_events`
4. Add `idx_snapshots_date` and `idx_snapshots_days_since_publish` indexes

### Phase 2: New Tables (Week 1)

1. Create `performance_rollups` table
2. Create `monitoring_alerts` table
3. Create `search_query_rollups` table
4. Create helper functions (`compute_weekly_rollups`, `compute_monthly_rollups`, `cleanup_old_snapshots`)

### Phase 3: Automation (Week 2)

1. Enable `pg_cron` extension
2. Schedule weekly snapshot capture
3. Schedule weekly/monthly rollup computation
4. Schedule monthly cleanup
5. Update capture-snapshot API to handle daily collection for recently-published SKUs

### Phase 4: Dashboard Updates (Week 3)

1. Create `mv_portfolio_performance` materialized view
2. Update `/api/monitoring/performance-delta` to read from rollups
3. Add portfolio-level trend charts to monitoring page
4. Add alert display to monitoring page

### Phase 5: Partitioning (When Needed — est. Year 2-3)

1. Enable `pg_partman` extension
2. Convert `performance_snapshots` to range-partitioned table (by month)
3. Convert `search_query_snapshots` to range-partitioned table (by month)

---

## 9. Storage Budget

| Component | Year 1 | Year 2 | Year 3 |
|-----------|--------|--------|--------|
| Raw performance snapshots | ~20 MB | ~40 MB (after cleanup) | ~40 MB (steady state) |
| Performance rollups | ~5 MB | ~15 MB | ~25 MB |
| Search query snapshots | ~200 MB | ~200 MB (after cleanup) | ~200 MB (steady state) |
| Search query rollups | ~10 MB | ~30 MB | ~50 MB |
| Monitoring alerts | ~1 MB | ~2 MB | ~3 MB |
| Materialized views | ~1 MB | ~2 MB | ~3 MB |
| **Total new storage** | **~237 MB** | **~289 MB** | **~321 MB** |

Current database is 209 MB. Total projected: ~530 MB by Year 3, well within Supabase Pro's 8 GB limit.

---

## 10. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Snapshot granularity | Weekly (daily for first 30 days post-publish) | Sufficient for trend analysis; daily for settling period |
| Snapshot level | master_sku + platform (not variant) | Matches Google Ads reporting grain and baseline grain |
| Rollup strategy | Pre-computed weekly + monthly tables | Avoids scanning raw data for dashboard queries |
| Partitioning | Deferred (prepare schema now) | Current/projected scale doesn't justify complexity |
| Retention | 90d raw daily, 2yr raw weekly, forever for rollups | Balances detail with storage |
| Delta computation | Pre-computed in rollups | Eliminates app-side computation in delta API |
| Search query aggregation | Monthly rollups with top-20 JSONB | Manages the N(queries) x N(SKUs) explosion |
| Scheduling | pg_cron (Supabase-native) | No external scheduler needed; runs in-database |
| Alerts | Database table + threshold checks in rollup function | Simple, queryable, no external service needed |
