# Task: Investigate & Implement Performance Data Lifecycle

## Objective

Fully investigate how performance data flows through Allied-FeedOps, document the current state, identify gaps, and implement a complete performance monitoring lifecycle for published content.

## Investigation Areas

### 1. Current Performance Data Sources

**Google Ads API (Primary Source)**
- Endpoint: `shopping_performance_view`
- Data fetched: impressions, clicks, CTR, conversions, conversion_value, cost_micros
- Offer ID format: `shopify_US_{shopify_product_id}_{shopify_variant_id}`
- Customer ID: `6253381786`
- Login Customer ID: `7338022535`

**Investigate:**
- [ ] How often is Google Ads data queried? (On-demand vs scheduled)
- [ ] What date ranges are supported? (7d, 30d, 90d implemented)
- [ ] Are there rate limits affecting data freshness?
- [ ] Does the SKU selection algorithm rely on cached or live data?

### 2. Current Supabase Storage

**Tables involved:**

| Table | Purpose | Population Status |
|-------|---------|-------------------|
| `performance_baselines` | Pre-optimization baseline metrics | Schema exists, data TBD |
| `performance_snapshots` | Daily/periodic performance snapshots | Schema exists, data TBD |
| `publish_events` | Tracks when content was published | Populated on publish |
| `variant_index` | Maps master_sku to shopify_product_id | Populated (72,023 rows) |

**Investigate:**
- [ ] Are `performance_baselines` being populated? When?
- [ ] Are `performance_snapshots` being populated? By what mechanism?
- [ ] How is baseline defined? (30 days pre-publish? Custom period?)
- [ ] Is there a scheduled job to capture snapshots?

### 3. SKU Selection Data Flow

**Current implementation** (`/api/sku-selection`):
1. Fetches all SKUs from `variant_index`
2. Queries Google Ads `shopping_performance_view` for last 30 days
3. Filters to Shopify products (`shopify_%`)
4. Scores SKUs using tier algorithm (Tier 1/2/3/Fill)
5. Returns scored recommendations

**Investigate:**
- [ ] Is this data cached anywhere for dashboard displays?
- [ ] Should historical scoring be stored for trend analysis?
- [ ] Are there performance issues with querying all products?

### 4. Post-Publishing Performance Tracking

**Current state:**
- `publish_events` records: master_sku, platform, environment, published_at
- Content snapshots stored: published_title, published_description, variant_count, content_version

**Missing pieces:**
- [ ] No automatic baseline capture before publishing
- [ ] No scheduled snapshot collection post-publishing
- [ ] No A/B comparison infrastructure
- [ ] No statistical significance calculation

## Implementation Plan

### Phase 1: Baseline Capture

**Before publishing content:**
1. Capture 30-day pre-publish performance baseline
2. Store in `performance_baselines` with:
   - master_sku
   - platform
   - period_start, period_end
   - impressions, clicks, ctr, conversions, cvr, cost, cpc, roas

**Implementation location:** `dashboard/src/lib/publishing/batch-publish.ts`

### Phase 2: Post-Publish Snapshots

**Create a scheduled job to:**
1. Query all SKUs with `publish_events.status = 'success'`
2. Fetch current performance from Google Ads API
3. Store in `performance_snapshots` with snapshot_date

**Options:**
- Vercel Cron Jobs (if using Vercel Pro)
- External scheduler (GitHub Actions, Cloud Scheduler)
- Manual trigger via dashboard API

### Phase 3: Performance Dashboard Enhancement

**Enhance `/api/performance` to:**
1. Compare baseline vs post-publish performance
2. Calculate lift metrics (CTR change, CVR change, ROAS change)
3. Flag statistically significant improvements/declines
4. Support A/B period comparisons

### Phase 4: Alerting & Reporting

**Implement:**
1. Performance degradation alerts (>10% decline in CTR/CVR)
2. Success celebration (>20% improvement)
3. Weekly performance summary email/report

## Files to Examine

### API Routes
- `dashboard/src/app/api/performance/route.ts` - Current performance API
- `dashboard/src/app/api/sku-selection/route.ts` - SKU selection with Google Ads data

### Libraries
- `dashboard/src/lib/google-ads.ts` - Google Ads API client
- `dashboard/src/lib/supabase/queries.ts` - Database query functions
- `dashboard/src/lib/supabase/types.ts` - Type definitions

### Publishing Flow
- `dashboard/src/lib/publishing/batch-publish.ts` - Batch publishing logic
- `dashboard/src/lib/publishing/expand-variants.ts` - Variant expansion

### Pages
- `dashboard/src/app/(dashboard)/performance/page.tsx` - Performance dashboard UI

## Database Schema Reference

```sql
-- Performance Baselines
CREATE TABLE performance_baselines (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL, -- 'google', 'bing', 'shopify'
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  ctr DECIMAL(10,6) DEFAULT 0,
  conversions DECIMAL(10,2) DEFAULT 0,
  cvr DECIMAL(10,6) DEFAULT 0,
  cost DECIMAL(10,2) DEFAULT 0,
  cpc DECIMAL(10,4) DEFAULT 0,
  roas DECIMAL(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(master_sku, platform, period_start, period_end)
);

-- Performance Snapshots
CREATE TABLE performance_snapshots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  environment TEXT NOT NULL, -- 'staging', 'production'
  snapshot_date DATE NOT NULL,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  ctr DECIMAL(10,6) DEFAULT 0,
  conversions DECIMAL(10,2) DEFAULT 0,
  cvr DECIMAL(10,6) DEFAULT 0,
  cost DECIMAL(10,2) DEFAULT 0,
  cpc DECIMAL(10,4) DEFAULT 0,
  roas DECIMAL(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(master_sku, platform, environment, snapshot_date)
);
```

## Success Criteria

1. **Baseline capture works**: Before any content is published, 30-day baseline is automatically stored
2. **Snapshots are scheduled**: Daily/weekly snapshots captured for published SKUs
3. **Dashboard shows lift**: Performance page displays baseline vs current with % change
4. **Data integrity**: No gaps in time series data for published SKUs
5. **Alerts configured**: Team notified of significant performance changes

## Questions to Answer

1. Should we use Vercel Cron, GitHub Actions, or GCP Cloud Scheduler for snapshots?
2. What's the retention policy for performance_snapshots? (90 days? 1 year?)
3. Should we store variant-level performance or master-SKU aggregated?
4. How do we handle products that get unpublished/rolled back?
5. Should performance data influence the SKU scoring algorithm?

## Related Documentation

- `docs/prompts/01-performance-dashboard.md` - Original performance dashboard implementation
- `docs/prompts/08-sku-selection-generation.md` - SKU selection algorithm
- `docs/prompts/12-ab-testing-dashboard.md` - A/B testing infrastructure (future)
- `CLAUDE.md` - Project configuration and conventions
