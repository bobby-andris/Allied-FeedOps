# Task: Investigate & Implement Performance Data Lifecycle

## Mode & Skills

**Recommended Mode:** Plan Mode (`/plan`)

**Required Skills (invoke in order):**
1. `superpowers:brainstorming` - Before designing the implementation approach
2. `superpowers:systematic-debugging` - When investigating existing data flow issues
3. `superpowers:test-driven-development` - Before implementing each phase
4. `superpowers:verification-before-completion` - Before claiming any phase complete

**MCP Servers to Use:**
- `mcp__supabase__execute_sql` - Query/inspect Supabase tables directly
- `mcp__supabase__list_tables` - Verify schema exists
- `mcp__google-ads-mcp__search` - Test Google Ads API queries
- `mcp__vercel__get_runtime_logs` - Debug API issues in production
- `mcp__plugin_playwright_playwright__*` - Visual verification of dashboard pages

**Agents to Consider:**
- `Explore` agent - For thorough codebase investigation
- `Plan` agent - For architectural decisions

---

## Objective

Fully investigate how performance data flows through Allied-FeedOps, document the current state, identify gaps, and implement a complete performance monitoring lifecycle for published content.

---

## Phase 0: Investigation (Plan Mode)

**Before writing ANY code, complete this investigation using the tools above.**

### Investigation Checklist

Use these MCP commands to gather evidence:

```bash
# 1. Check if performance tables have data
mcp__supabase__execute_sql: "SELECT COUNT(*) FROM performance_baselines"
mcp__supabase__execute_sql: "SELECT COUNT(*) FROM performance_snapshots"
mcp__supabase__execute_sql: "SELECT COUNT(*) FROM publish_events WHERE status = 'success'"

# 2. Check variant_index coverage
mcp__supabase__execute_sql: "SELECT COUNT(DISTINCT master_sku) FROM variant_index WHERE shopify_product_id IS NOT NULL"

# 3. Sample publish events to understand current state
mcp__supabase__execute_sql: "SELECT master_sku, platform, published_at FROM publish_events WHERE status = 'success' ORDER BY published_at DESC LIMIT 10"
```

### 1. Current Performance Data Sources

**Google Ads API (Primary Source)**
- Endpoint: `shopping_performance_view`
- Data fetched: impressions, clicks, CTR, conversions, conversion_value, cost_micros
- Offer ID format: `shopify_US_{shopify_product_id}_{shopify_variant_id}`
- Customer ID: `6253381786`
- Login Customer ID: `7338022535`

**Investigation Tasks:**
- [ ] Run `/api/sku-selection` and check `using_sample_data` flag
- [ ] Check Vercel logs for Google Ads API errors
- [ ] Verify Google Ads credentials are configured in Vercel env vars
- [ ] Test date range queries (7d, 30d, 90d)

### 2. Current Supabase Storage

**Tables involved:**

| Table | Purpose | Population Status |
|-------|---------|-------------------|
| `performance_baselines` | Pre-optimization baseline metrics | **VERIFY with MCP** |
| `performance_snapshots` | Daily/periodic performance snapshots | **VERIFY with MCP** |
| `publish_events` | Tracks when content was published | Populated on publish |
| `variant_index` | Maps master_sku to shopify_product_id | Populated (72,023 rows) |

**Investigation Tasks:**
- [ ] Query each table's row count using `mcp__supabase__execute_sql`
- [ ] Check if any SKU has baseline data
- [ ] Check if any SKU has snapshot data
- [ ] Identify the gap between publish_events and performance data

### 3. SKU Selection Data Flow

**Current implementation** (`/api/sku-selection`):
1. Fetches all SKUs from `variant_index`
2. Queries Google Ads `shopping_performance_view` for last 30 days
3. Filters to Shopify products (`shopify_%`) in memory
4. Scores SKUs using tier algorithm (Tier 1/2/3/Fill)
5. Returns scored recommendations with `using_sample_data` flag

**Investigation Tasks:**
- [ ] Hit the API and verify real data vs sample data
- [ ] Check response time (should be <5s)
- [ ] Verify tier distribution in response

### 4. Post-Publishing Performance Tracking

**Current state:**
- `publish_events` records: master_sku, platform, environment, published_at
- Content snapshots stored: published_title, published_description, variant_count, content_version

**Known Gaps:**
- [ ] No automatic baseline capture before publishing
- [ ] No scheduled snapshot collection post-publishing
- [ ] No A/B comparison infrastructure
- [ ] No statistical significance calculation

---

## Implementation Plan

**IMPORTANT:** Use `superpowers:test-driven-development` for each phase. Write failing tests first, then implement.

### Phase 1: Baseline Capture

**Skill:** `superpowers:test-driven-development`

**Before publishing content:**
1. Capture 30-day pre-publish performance baseline
2. Store in `performance_baselines` with:
   - master_sku, platform
   - period_start, period_end
   - impressions, clicks, ctr, conversions, cvr, cost, cpc, roas

**Implementation Steps:**
1. Write test: "baseline is captured when SKU is added to publish batch"
2. Modify `dashboard/src/lib/publishing/batch-publish.ts`
3. Add `captureBaseline(masterSku, platform)` function to `dashboard/src/lib/google-ads.ts`
4. Verify with Supabase MCP that data is stored

**Verification:**
```bash
mcp__supabase__execute_sql: "SELECT * FROM performance_baselines WHERE master_sku = '{test_sku}'"
```

### Phase 2: Post-Publish Snapshots

**Skill:** `superpowers:brainstorming` (to decide scheduler approach)

**Create a scheduled job to:**
1. Query all SKUs with `publish_events.status = 'success'`
2. Fetch current performance from Google Ads API
3. Store in `performance_snapshots` with snapshot_date

**Scheduler Decision Matrix:**

| Option | Pros | Cons |
|--------|------|------|
| Vercel Cron | Native, easy setup | Requires Pro plan |
| GitHub Actions | Free, git-tracked | Separate from app |
| GCP Cloud Scheduler | Already have GCP | Additional config |
| Manual API endpoint | Simple, controllable | Requires remembering to run |

**Recommended:** Start with manual API endpoint (`/api/performance/capture-snapshot`), add cron later.

### Phase 3: Performance Dashboard Enhancement

**Skill:** `superpowers:test-driven-development`

**Enhance `/api/performance` to:**
1. Compare baseline vs post-publish performance
2. Calculate lift metrics (CTR change, CVR change, ROAS change)
3. Flag statistically significant improvements/declines
4. Support A/B period comparisons

**UI Verification:**
```bash
mcp__plugin_playwright_playwright__browser_navigate: "https://allied-feed-ops.vercel.app/performance"
mcp__plugin_playwright_playwright__browser_take_screenshot
```

### Phase 4: Alerting & Reporting

**Skill:** `superpowers:brainstorming` (to design alert thresholds)

**Implement:**
1. Performance degradation alerts (>10% decline in CTR/CVR)
2. Success celebration (>20% improvement)
3. Weekly performance summary email/report

**Consider:** Slack webhook, email via SendGrid, or dashboard notifications

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

---

## Plan Mode Execution Checklist

When executing this prompt in plan mode, follow this order:

### Before Starting
- [ ] Enter plan mode: `/plan`
- [ ] Invoke `superpowers:brainstorming` to clarify requirements
- [ ] Read all files in "Files to Examine" section

### Investigation Phase (Phase 0)
- [ ] Run all MCP queries in Investigation Checklist
- [ ] Document current state findings
- [ ] Identify which tables need population
- [ ] Ask clarifying questions about scheduler preference

### Implementation Phases (1-4)
For EACH phase:
- [ ] Invoke `superpowers:test-driven-development`
- [ ] Write failing test
- [ ] Implement minimum code to pass
- [ ] Verify with MCP tools
- [ ] Invoke `superpowers:verification-before-completion`
- [ ] Commit with descriptive message

### Final Verification
- [ ] Use Playwright MCP to screenshot all affected pages
- [ ] Verify no regressions in existing functionality
- [ ] Update CLAUDE.md if new patterns established
- [ ] Create follow-up prompt if Phase 4 (alerting) deferred

---

## Quick Start Commands

```bash
# Start plan mode
/plan

# Investigation queries (copy-paste ready)
SELECT COUNT(*) as baseline_count FROM performance_baselines;
SELECT COUNT(*) as snapshot_count FROM performance_snapshots;
SELECT COUNT(*) as published_count FROM publish_events WHERE status = 'success';
SELECT master_sku, platform, published_at FROM publish_events WHERE status = 'success' ORDER BY published_at DESC LIMIT 5;
```
