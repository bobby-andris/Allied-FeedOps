# Pre-flight Setup: Performance & Search Insights Infrastructure

## Objective

Set up comprehensive performance and search insights data collection infrastructure BEFORE regenerating all SKU content. This ensures:
1. All existing SKUs have baseline performance data and search insights
2. All future SKUs automatically collect this data before content generation
3. Post-publish monitoring tracks changes in performance and search terms over time

## CRITICAL: Use Agent Teams

You MUST use agent teams for this work via the `TeamCreate` and `Task` tools.

**Team name:** `setup-team`

**Team structure (5 agents):**
1. **Team Lead** - Orchestrates work, coordinates agents, makes decisions, handles escalations
2. **Audit Agent** - Query databases, generate gap analysis, identify missing data
3. **Data Collection Agent** - Trigger API calls for performance baselines and search insights sync, monitor job completion
4. **Automation Agent** - Implement data collection helpers, integrate into existing APIs
5. **Monitoring Agent** - Create monitoring infrastructure (tables, API endpoints, dashboard pages)

## Phase 1: Current State Audit

**Owner: Audit Agent**

### Tasks

1. **Query current coverage:**
   - Use Supabase MCP (`mcp__supabase__execute_sql`) to check:
     ```sql
     -- All active SKUs in the system
     SELECT DISTINCT master_sku FROM variant_index WHERE master_sku IS NOT NULL;

     -- SKUs with performance baselines
     SELECT DISTINCT master_sku FROM performance_baselines;

     -- SKUs with search insights
     SELECT DISTINCT master_sku FROM search_queries_by_master_sku;

     -- SKUs with generated content
     SELECT DISTINCT master_sku FROM generated_content;
     ```

2. **Generate gap analysis report:**
   - Identify SKUs missing performance baselines
   - Identify SKUs missing search insights
   - Identify SKUs with stale data (>30 days old)
   - Create a prioritized list for backfill

3. **Check Cloud Run pipeline health:**
   - Test endpoint: `"$FEEDOPS_PIPELINE_URL/health"`
   - Verify Supabase connection
   - Verify Google Ads API credentials

4. **Deliverable:**
   - Write report to `docs/audit/preflight-audit-YYYY-MM-DD.md`
   - Include total SKU count, coverage percentages, gaps list
   - Share with Team Lead

## Phase 2: Backfill Missing Data

**Owner: Data Collection Agent**

### Prerequisites
- Audit Agent must complete Phase 1
- Gap analysis report available

### Tasks

1. **Backfill performance baselines:**
   - For each SKU missing baseline data:
     - Use Google Ads MCP (`mcp__google-ads-mcp__search`) to fetch 30-day historical metrics
     - Query: `shopping_performance_view` filtered by `product_item_id` (master SKU)
     - Metrics needed: impressions, clicks, CTR, conversions, cost, ROAS
     - Calculate `baseline_start_date` (30 days ago), `baseline_end_date` (today)
   - Use Supabase MCP to insert into `performance_baselines`:
     ```sql
     INSERT INTO performance_baselines (
       master_sku, platform, avg_impressions, avg_clicks, avg_ctr,
       avg_conversions, avg_cost, avg_roas, baseline_start_date, baseline_end_date
     ) VALUES (?, 'google', ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT (master_sku, platform) DO UPDATE SET ...
     ```
   - Track progress: Report every 100 SKUs to Team Lead

2. **Backfill search insights:**
   - Trigger search insights sync via Cloud Run API:
     ```bash
     curl -X POST "$FEEDOPS_PIPELINE_URL/search-insights/sync" \
       -H "Content-Type: application/json" \
       -d '{"date_range_days": 30}'
     ```
   - Poll job status: `GET /search-insights/sync/{job_id}`
   - Wait for completion (may take 10-20 minutes for all SKUs)
   - Verify `search_queries` table populated with recent data

3. **Enrich with Keyword Planner data:**
   - Trigger enrichment via Cloud Run API:
     ```bash
     curl -X POST "$FEEDOPS_PIPELINE_URL/search-insights/enrich"
     ```
   - This fetches search volume, competition index, CPC estimates for all keywords
   - Populates `keyword_metrics` table with 30-day TTL

4. **Verification:**
   - Re-run coverage queries from Phase 1
   - Confirm 100% coverage for active SKUs
   - Report to Team Lead

## Phase 3: Automate Data Collection for Future SKUs

**Owner: Automation Agent**

### Tasks

1. **Create data collection helpers:**
   - Create file: `dashboard/src/lib/data-collection/ensure-data.ts`
   - Implement:
     ```typescript
     /**
      * Ensures performance baseline data exists for a master SKU
      * Fetches from Google Ads API if missing or stale (>30 days)
      */
     export async function ensurePerformanceData(masterSku: string): Promise<boolean>

     /**
      * Ensures search insights data exists for a master SKU
      * Triggers sync job if missing or stale (>30 days)
      */
     export async function ensureSearchInsights(masterSku: string): Promise<boolean>

     /**
      * Combined check - ensures both performance and search data exist
      * Use this before content generation
      */
     export async function ensureAllData(masterSku: string): Promise<{
       performance: boolean;
       searchInsights: boolean;
     }>
     ```

2. **Integrate into SKU selection API:**
   - Read: `dashboard/src/app/api/sku-selection/route.ts`
   - Before returning scored recommendations, call `ensureAllData()` for each SKU
   - If data is missing/stale, trigger collection and wait (or mark SKU as "data pending")

3. **Integrate into regeneration API:**
   - Read: `dashboard/src/app/api/regenerate/route.ts`
   - Before generating content, call `ensureAllData()` for the master SKU
   - Fail fast if data collection fails (don't generate without context)

4. **Integrate into batch generation:**
   - Read: `dashboard/src/app/api/sku-selection/generate/route.ts`
   - Before starting batch job, ensure ALL SKUs in batch have data
   - Add data collection status to `batch_generation_job_skus` table

5. **Update evidence table builder:**
   - Read: `dashboard/src/lib/evidence/builder.ts`
   - Ensure performance and search insights are ALWAYS included in evidence table
   - If data is missing, the evidence builder should trigger collection

6. **Update CLAUDE.md:**
   - Document the automation in the "Common Workflows" section
   - Add note: "Performance + search insights data is automatically collected before content generation"

## Phase 4: Post-Publish Monitoring Infrastructure

**Owner: Monitoring Agent**

### Tasks

1. **Create search query snapshots table:**
   - Create migration: `dashboard/supabase/migrations/YYYYMMDDHHMMSS_create_search_query_snapshots.sql`
   - Schema:
     ```sql
     CREATE TABLE search_query_snapshots (
       id BIGSERIAL PRIMARY KEY,
       master_sku TEXT NOT NULL,
       gmc_offer_id TEXT,
       publish_event_id BIGINT REFERENCES publish_events(id),
       snapshot_date DATE NOT NULL,
       days_since_publish INTEGER,
       search_term TEXT NOT NULL,
       impressions INTEGER DEFAULT 0,
       clicks INTEGER DEFAULT 0,
       ctr NUMERIC(5,4),
       avg_cpc_micros BIGINT,
       cost_micros BIGINT,
       conversions NUMERIC(10,2),
       created_at TIMESTAMPTZ DEFAULT NOW(),
       UNIQUE(master_sku, snapshot_date, search_term)
     );

     CREATE INDEX idx_search_snapshots_sku ON search_query_snapshots(master_sku);
     CREATE INDEX idx_search_snapshots_publish ON search_query_snapshots(publish_event_id);
     CREATE INDEX idx_search_snapshots_days ON search_query_snapshots(days_since_publish);
     ```
   - Apply migration using Supabase MCP: `mcp__supabase__apply_migration`

2. **Create monitoring API endpoints:**
   - Create: `dashboard/src/app/api/monitoring/performance-delta/route.ts`
     - Compares baseline vs current performance for a master SKU
     - Returns: CTR change %, impression change %, cost change %, ROAS change %
   - Create: `dashboard/src/app/api/monitoring/search-delta/route.ts`
     - Compares pre-publish vs post-publish search terms
     - Returns: new keywords, lost keywords, impression shifts, CTR changes
   - Create: `dashboard/src/app/api/monitoring/snapshot-capture/route.ts`
     - Triggers snapshot capture for published SKUs at intervals (7, 14, 30, 60, 90 days)
     - Called by cron job or manually

3. **Create monitoring dashboard page:**
   - Create: `dashboard/src/app/(dashboard)/monitoring/page.tsx`
   - Features:
     - Table of published SKUs with days since publish
     - CTR trend chart (baseline → 7d → 14d → 30d)
     - Impression trend chart
     - Search term evolution (new keywords, lost keywords)
     - Alerts for significant drops (CTR down >20%, impressions down >50%)
   - Use existing components from `/components/dashboard/*` where possible

4. **Document monitoring workflow:**
   - Update CLAUDE.md "Publishing Workflow" section
   - Add subsection: "Post-Publish Monitoring"
   - Document snapshot capture schedule
   - Document how to read performance delta reports

## Phase 5: End-to-End Verification

**Owner: Team Lead (coordinates all agents)**

### Tasks

1. **Verify data collection automation:**
   - Pick 3 test SKUs (one with data, one without, one with stale data)
   - Call `/api/sku-selection?limit=3` and verify `ensureAllData()` is called
   - Verify data exists in `performance_baselines` and `search_queries_by_master_sku`

2. **Verify monitoring infrastructure:**
   - Use Playwright MCP to test monitoring dashboard:
     ```typescript
     mcp__plugin_playwright_playwright__browser_navigate({
       url: "http://localhost:3000/monitoring"
     })
     mcp__plugin_playwright_playwright__browser_take_screenshot({
       path: "docs/screenshots/monitoring-dashboard.png"
     })
     ```
   - Manually trigger snapshot capture for one test SKU
   - Verify `search_query_snapshots` table has new entry

3. **Generate completion report:**
   - Write to: `docs/audit/preflight-completion-YYYY-MM-DD.md`
   - Include:
     - Total SKUs with data (before vs after)
     - Automation integration points completed
     - Monitoring infrastructure status
     - Next steps (ready for main regeneration prompt)

4. **Commit and push:**
   - Commit all changes with message: `feat: Add performance and search insights infrastructure`
   - Push to master (triggers auto-deploy for Vercel dashboard)
   - Verify no build errors

## Success Criteria

- [ ] 100% of active SKUs have performance baselines (<30 days old)
- [ ] 100% of active SKUs have search insights data (<30 days old)
- [ ] `ensureAllData()` helper implemented and integrated into 3 API routes
- [ ] `search_query_snapshots` table created
- [ ] Monitoring API endpoints created (`/api/monitoring/*`)
- [ ] Monitoring dashboard page created (`/monitoring`)
- [ ] End-to-end verification completed
- [ ] Documentation updated in CLAUDE.md
- [ ] All changes committed and pushed to master
- [ ] No build errors, dashboard accessible

## Important Constraints

- **Use Supabase MCP** for all database operations - don't write custom SQL scripts
- **Use Google Ads MCP** for fetching performance data - don't use Python client directly
- **Rate limits:** Google Ads API is rate limited - batch requests and add delays between calls
- **Data freshness:** 30-day TTL for cached data (performance baselines, keyword metrics)
- **Cloud Run health:** Monitor `/health` endpoint during data collection - retry if unhealthy

## Deployment Notes

- Dashboard changes auto-deploy on push to master (Vercel)
- No Cloud Run changes needed (Python pipeline already has search insights endpoints)
- No GCP secrets needed (all already configured)
- Database migrations applied via Supabase MCP (no manual Supabase dashboard work)

## Team Communication

- **Use SendMessage tool** to communicate between agents (not just text output)
- **Use TaskCreate/TaskUpdate** for tracking progress
- **Team Lead should broadcast** major milestones (Phase X complete, moving to Phase Y)
- **Agents should report blockers** immediately to Team Lead (don't wait)

## Handoff to Main Regeneration Prompt

Once this pre-flight setup is complete:
- All SKUs have performance + search insights data
- Future SKUs automatically collect data before generation
- Monitoring infrastructure is ready to track post-publish changes
- Ready to run the main regeneration prompt (clears approved content, regenerates all SKUs)
