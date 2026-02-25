# Phase 29: Content-Performance Feedback Linkage - Research

**Researched:** 2026-02-25
**Domain:** Dashboard UI + API routes + SQL joins + schema enforcement
**Confidence:** HIGH

## Summary

Phase 29 builds a new dashboard page that connects published content to measurable performance outcomes. The core data infrastructure is largely in place: `publish_events`, `performance_baselines`, `performance_snapshots`, and `search_query_snapshots` tables all exist in production with good linkage (99.4% snapshot-to-publish_event join rate). The Python pipeline already has working `collect-daily` and `compute-impact` endpoints that implement the diff-in-diff methodology. The primary gaps are: (1) `performance_impact_scores` table does not exist in production despite being documented in SCHEMA.md, (2) `performance_snapshots` is missing `cohort_type` and `product_category` columns in production, and (3) the `prompt_hash` NOT NULL enforcement is only at 2.7% population in existing data.

The implementation is predominantly TypeScript (Next.js dashboard page + API routes) reading from existing Supabase tables, with a small amount of SQL migration work to create the missing `performance_impact_scores` table and add missing columns to `performance_snapshots`. The existing `/api/performance/route.ts` already implements a simpler version of the feedback view pattern -- this phase replaces it with the richer CONTEXT.md-specified design.

**Primary recommendation:** Create the `performance_impact_scores` table and missing `performance_snapshots` columns via Supabase migration, build a new `/content-impact` dashboard page with API routes that join the existing data, and enforce `prompt_hash` NOT NULL at the application layer in both publish code paths.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Dedicated page at a new top-level route (e.g., `/feedback` or `/content-impact`)
- Landing view: SKU list table with impact summary -- columns include SKU, publish date, baseline CTR, current CTR, delta, impact score
- Click a row to drill into detailed view (search terms, control cohort, history)
- CTR/CVR deltas displayed as color-coded percentages: green for positive, red for negative, gray for insufficient data
- All three time windows shown by default: 7-day, 14-day, 30-day columns
- Scores presented as labeled tiers: "Strong Improvement", "Moderate Improvement", "No Significant Change", "Decline" -- color-coded
- Low-data SKUs show gray "Insufficient Data" badge instead of a score, with tooltip explaining minimum thresholds
- Control cohort: auto-select similar unpublished SKUs from same product category for diff-in-diff comparison
- Control methodology transparency: expandable detail row shows which control SKUs were used, raw numbers, methodology note
- Gained/Lost split view for search terms: "Terms Gained" on left, "Terms Lost" on right, color-coded
- Each term row shows: search term text, impression delta (+/-), click delta (+/-)
- New terms (zero pre-publish impressions) get a "New" badge
- Top 10 terms per side by default, "Show all" to expand
- Recently published SKUs: show available windows with data, gray out unavailable windows with "Pending (X days)" countdown
- Re-published SKUs: show latest publish event's impact by default, expandable "History" section for prior publishes
- Missing baselines: show post-publish metrics with "No baseline" warning badge -- don't hide the SKU
- Existing NULL prompt_hashes: leave as-is, enforce NOT NULL going forward only. Legacy rows display as "Legacy publish (no version tracking)" in UI

### Claude's Discretion
- Exact threshold values for impact score tiers (what numeric ranges map to "Strong", "Moderate", etc.)
- Algorithm for selecting control cohort SKUs (category matching, similarity criteria)
- Minimum impression threshold for "Insufficient Data" badge
- Page routing path and navigation placement
- Drill-down detail layout and component structure
- Error state handling and loading states

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FEED-01 | Content-performance feedback view/table joins publish_events + performance_snapshots + generated_content, keyed on (master_sku, platform), showing baseline vs post-publish CTR/CVR deltas at 7/14/30-day windows | Existing `/api/performance/route.ts` proves the join pattern works. Phase 28 NULL audit confirms 99.4% join rate on `publish_event_id`. performance_baselines has avg_ctr/avg_cvr for baseline. performance_snapshots has daily ctr/cvr. Need to aggregate snapshots into 7/14/30-day windows. |
| FEED-02 | Performance impact scores computed and written to existing performance_impact_scores table using diff-in-diff methodology (treated vs control cohort lift) | Python `compute_and_store_impact_scores()` in `performance_impact.py` ALREADY implements the full algorithm. But `performance_impact_scores` table does NOT exist in production -- must CREATE TABLE first. Once table exists, the capture-snapshot proxy already calls both collect-daily and compute-impact. |
| FEED-03 | Search query snapshots populated after publish events, capturing which search terms gained/lost impressions after content changes | `search_query_snapshots` table exists in production. `/api/monitoring/snapshot-capture/route.ts` captures snapshots. `/api/monitoring/search-delta/route.ts` computes gained/lost deltas. The infrastructure works -- need to wire it into the new page UI. |
| FEED-04 | prompt_hash NOT NULL constraint enforced for new publish events to ensure content versioning linkage integrity | Two code paths insert into publish_events: `publish/sku/route.ts` (line 786) and `publish/batch/route.ts` (line 1091). Both use `PublishEventInsert` type. `expand-variants.ts` already fetches `generation_prompt_hash` from `generated_content`. Enforcement = validate before insert, reject if null. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 14.x (existing) | Dashboard framework | Already in use, App Router pages |
| React | 18.x (existing) | UI components | Already in use |
| Supabase JS | 2.x (existing) | Database queries | Already in use via `@/lib/supabase/server` |
| shadcn/ui | latest (existing) | UI components | Already in use (Table, Card, Badge, Tabs, Tooltip, Collapsible) |
| Tailwind CSS | 3.x (existing) | Styling | Already in use |
| lucide-react | latest (existing) | Icons | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @supabase/supabase-js | 2.x (existing) | Server-side Supabase client | API route queries |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Client-side data fetching | Server Components | Server Components would avoid loading states but this page needs interactivity (row expansion, tab switching). Use client component with `fetch()` to API routes, consistent with existing pages like `/performance`. |
| Supabase View (SQL) | Application-layer joins | SQL view would be faster but harder to maintain. Application-layer joins in API route are consistent with existing codebase pattern. |

**Installation:** No new packages needed. All dependencies already in `dashboard/package.json`.

## Architecture Patterns

### Recommended Project Structure
```
dashboard/src/
├── app/(dashboard)/content-impact/
│   └── page.tsx                           # New page (client component)
├── app/api/content-impact/
│   ├── route.ts                           # GET: SKU list with impact summary
│   └── [sku]/
│       ├── route.ts                       # GET: Drill-down detail for one SKU
│       └── search-terms/
│           └── route.ts                   # GET: Search term deltas for one SKU
├── components/content-impact/
│   ├── ContentImpactTable.tsx             # Landing table with expandable rows
│   ├── ImpactScoreBadge.tsx               # Tier label badge component
│   ├── TimeWindowColumns.tsx              # 7/14/30-day delta display
│   ├── SearchTermDelta.tsx                # Gained/lost split view
│   └── ControlCohortDetail.tsx            # Expandable control methodology
└── components/shared/Sidebar.tsx           # Add navigation entry
```

### Pattern 1: Feedback View API Route (FEED-01)
**What:** Single API route that joins publish_events + performance_baselines + performance_snapshots + performance_impact_scores
**When to use:** Landing page data fetch
**Example:**
```typescript
// API route: /api/content-impact/route.ts
// Joins the 4 tables and aggregates snapshots into 7/14/30-day windows

// Step 1: Get successful publish events
const { data: events } = await supabase
  .from('publish_events')
  .select('id, master_sku, platform, published_at, prompt_hash, content_version, product_category')
  .eq('status', 'success')
  .eq('action', 'publish')
  .order('published_at', { ascending: false })

// Step 2: Get baselines for those SKUs
const { data: baselines } = await supabase
  .from('performance_baselines')
  .select('master_sku, platform, avg_ctr, avg_cvr, avg_impressions, avg_clicks')
  .in('master_sku', uniqueSkus)

// Step 3: Get snapshots with days_since_publish for window aggregation
const { data: snapshots } = await supabase
  .from('performance_snapshots')
  .select('master_sku, platform, snapshot_date, ctr, cvr, impressions, clicks, days_since_publish, publish_event_id')
  .in('master_sku', uniqueSkus)

// Step 4: Get impact scores (if table exists)
const { data: scores } = await supabase
  .from('performance_impact_scores')
  .select('publish_event_id, metric_name, did_lift_pct, label, confidence, sample_size_treated, sample_size_control')
  .in('publish_event_id', eventIds)

// Step 5: Aggregate snapshots into 7/14/30-day windows
// Filter by days_since_publish: 0-7, 0-14, 0-30
// Calculate mean CTR/CVR for each window
```

### Pattern 2: Window Aggregation (7/14/30 days)
**What:** Aggregate performance_snapshots by days_since_publish into time windows
**When to use:** Computing post-publish metrics at each window
**Example:**
```typescript
function aggregateWindow(snapshots: Snapshot[], maxDays: number): WindowMetrics | null {
  const windowSnapshots = snapshots.filter(s =>
    s.days_since_publish !== null &&
    s.days_since_publish >= 0 &&
    s.days_since_publish <= maxDays
  )
  if (windowSnapshots.length === 0) return null

  const avgCtr = windowSnapshots.reduce((sum, s) => sum + s.ctr, 0) / windowSnapshots.length
  const avgCvr = windowSnapshots.reduce((sum, s) => sum + s.cvr, 0) / windowSnapshots.length
  return { avgCtr, avgCvr, dataPoints: windowSnapshots.length, available: true }
}
```

### Pattern 3: Impact Score Tier Classification
**What:** Map numeric impact scores to labeled tiers
**When to use:** Display in ImpactScoreBadge component
**Example:**
```typescript
// Recommended thresholds (Claude's discretion per CONTEXT.md)
function classifyImpactTier(
  didLiftPct: number | null,
  confidence: number,
  sampleSizeTreated: number,
  sampleSizeControl: number
): { label: string; color: string } {
  // Minimum data threshold: at least 7 days of data for both treated and control
  if (sampleSizeTreated < 7 || sampleSizeControl < 7) {
    return { label: 'Insufficient Data', color: 'gray' }
  }
  if (didLiftPct === null) {
    return { label: 'Insufficient Data', color: 'gray' }
  }
  if (didLiftPct >= 10) return { label: 'Strong Improvement', color: 'green' }
  if (didLiftPct >= 3) return { label: 'Moderate Improvement', color: 'emerald' }
  if (didLiftPct <= -10) return { label: 'Decline', color: 'red' }
  if (didLiftPct <= -3) return { label: 'Moderate Decline', color: 'orange' }
  return { label: 'No Significant Change', color: 'gray' }
}

// Minimum impression threshold for "Insufficient Data":
// Recommend 50 total impressions across the window (aligns with Google Ads minimum reporting)
```

### Pattern 4: prompt_hash NOT NULL Enforcement (FEED-04)
**What:** Application-layer validation before insert into publish_events
**When to use:** Both publish code paths (sku/route.ts and batch/route.ts)
**Example:**
```typescript
// In logPublishEvent() — both sku/route.ts and batch/route.ts
async function logPublishEvent(
  supabase: ...,
  event: PublishEventInsert
): Promise<void> {
  // FEED-04: Enforce prompt_hash for new events
  if (!event.prompt_hash || !event.prompt_hash.trim()) {
    console.error(`FEED-04 violation: prompt_hash is null for ${event.master_sku}/${event.platform}`)
    throw new Error(`Cannot publish without prompt_hash for ${event.master_sku}. Content versioning linkage required.`)
  }
  // ... existing insert logic
}
```

### Anti-Patterns to Avoid
- **ALTER TABLE ADD NOT NULL on existing columns:** Would fail because 71/73 publish_events have NULL prompt_hash. Enforce at application layer only.
- **Building custom diff-in-diff in TypeScript:** The Python pipeline already implements this correctly in `performance_impact.py`. Read the results from `performance_impact_scores` table instead.
- **Querying Google Ads API from the dashboard page:** All performance data should come from pre-collected database tables. The capture-snapshot proxy triggers collection; the feedback page only reads.
- **Using SQL materialized views in Supabase:** Supabase has limited support for materialized views (no automatic refresh). Use application-layer aggregation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Diff-in-diff computation | TypeScript DID calculator | `performance_impact_scores` table (populated by Python pipeline) | Already implemented and tested in `performance_impact.py` with confidence scoring, guardrail metrics |
| Search term delta detection | New search delta logic | Existing `/api/monitoring/search-delta/route.ts` | Already computes new/lost/volume_increase/volume_decrease status |
| Search query snapshot capture | New snapshot capture logic | Existing `/api/monitoring/snapshot-capture/route.ts` | Already captures from search_queries to search_query_snapshots |
| Control cohort selection | New matching algorithm | Python `collect_daily_performance_snapshots()` | Already implements category-based control matching with `max_controls` parameter |

**Key insight:** The core data collection and computation infrastructure is ALREADY BUILT. Phase 29 is primarily a UI + API read layer on top of existing data. The main coding work is the new dashboard page and its API routes, plus the schema gaps (create table, add columns, enforce prompt_hash).

## Common Pitfalls

### Pitfall 1: performance_impact_scores Table Doesn't Exist
**What goes wrong:** The compute-impact Python endpoint tries to upsert into `performance_impact_scores`, which doesn't exist in production. API calls return 500 errors.
**Why it happens:** Phase 28 audit discovered this schema drift. The table is documented in SCHEMA.md and referenced in code, but the migration was never applied.
**How to avoid:** CREATE TABLE `performance_impact_scores` as the FIRST task before any API or UI work. Use the schema from SCHEMA.md as the source of truth.
**Warning signs:** `compute-impact` endpoint returns PostgreSQL "relation does not exist" errors.

### Pitfall 2: Missing cohort_type and product_category Columns
**What goes wrong:** The Python collector writes `cohort_type` and `product_category` to `performance_snapshots`, but these columns don't exist in production (only documented in SCHEMA.md).
**Why it happens:** Schema drift discovered in Phase 28 NULL audit.
**How to avoid:** ALTER TABLE ADD COLUMN for both before running the collector. These are nullable so no data migration needed.
**Warning signs:** Upsert errors or silently dropped columns in Python collector output.

### Pitfall 3: Publish Code Fallback Strips prompt_hash
**What goes wrong:** Both publish routes have a legacy fallback that deletes `prompt_hash` (lines 800-803 in sku/route.ts, lines 1104-1107 in batch/route.ts) when the insert fails. If the table schema rejects the column, the fallback strips it and inserts without.
**Why it happens:** Defensive coding for backward compatibility when migration 034 columns weren't yet in production.
**How to avoid:** For FEED-04, the enforcement must happen BEFORE the insert attempt, not after. The fallback path should be updated to still reject null prompt_hash even when stripping other columns.
**Warning signs:** Events inserted successfully but with NULL prompt_hash despite "enforcement."

### Pitfall 4: Time Window Aggregation Off-by-One
**What goes wrong:** A 7-day window includes 8 days of data (day 0 through day 7).
**Why it happens:** `days_since_publish = 0` is the publish date itself.
**How to avoid:** Use `days_since_publish >= 1 && days_since_publish <= 7` for 7-day post-publish window (exclude publish date).
**Warning signs:** Inconsistent window sizes between different calculations.

### Pitfall 5: Re-Published SKUs Have Multiple Events
**What goes wrong:** A SKU published twice has two publish_events. Snapshots may link to either event. Impact scores computed for the earlier event include post-re-publish data.
**Why it happens:** The `publish_event_id` in snapshots is set at collection time based on the most recent publish event before the snapshot date.
**How to avoid:** Group snapshots by `publish_event_id`, not just `master_sku`. For the landing table, show the latest publish event by default. For drill-down, show all publish events in the "History" section.
**Warning signs:** Anomalous CTR jumps in middle of a time series.

### Pitfall 6: Existing Performance Page Overlap
**What goes wrong:** The new `/content-impact` page duplicates functionality of the existing `/performance` page, causing user confusion.
**Why it happens:** Both pages show post-publish performance data.
**How to avoid:** The new page focuses on FEEDBACK LINKAGE (impact scores, control cohorts, search term deltas). The existing page focuses on raw performance monitoring. Consider adding a cross-link between them. Do NOT replace `/performance` -- it serves a different purpose.
**Warning signs:** Users asking "which page do I use?"

## Code Examples

### SQL Migration: Create performance_impact_scores Table
```sql
-- Must be applied BEFORE any compute-impact calls succeed
CREATE TABLE IF NOT EXISTS performance_impact_scores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  publish_event_id bigint NOT NULL REFERENCES publish_events(id),
  master_sku text NOT NULL,
  platform text NOT NULL,
  environment text NOT NULL,
  metric_name text NOT NULL,
  pre_value numeric(18,8),
  post_value numeric(18,8),
  control_pre numeric(18,8),
  control_post numeric(18,8),
  did_lift_pct numeric(18,8),
  label text NOT NULL CHECK (label IN ('positive', 'negative', 'neutral')),
  confidence numeric(6,4) NOT NULL DEFAULT 0,
  sample_size_treated integer NOT NULL DEFAULT 0,
  sample_size_control integer NOT NULL DEFAULT 0,
  window_pre_days integer NOT NULL DEFAULT 30,
  window_post_days integer NOT NULL DEFAULT 30,
  run_date date NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now()
);

-- Unique constraint matching Python upsert on_conflict
CREATE UNIQUE INDEX uq_impact_scores_event_metric
  ON performance_impact_scores (publish_event_id, metric_name, platform, environment);

-- Supporting indexes
CREATE INDEX idx_performance_impact_scores_publish_event ON performance_impact_scores (publish_event_id);
CREATE INDEX idx_performance_impact_scores_master_sku ON performance_impact_scores (master_sku);
CREATE INDEX idx_performance_impact_scores_run_date ON performance_impact_scores (run_date DESC);
CREATE INDEX idx_performance_impact_scores_metric ON performance_impact_scores (metric_name);
CREATE INDEX idx_performance_impact_scores_label ON performance_impact_scores (label);
```

### SQL Migration: Add Missing Columns to performance_snapshots
```sql
-- These columns are written by Python collector but missing from production
ALTER TABLE performance_snapshots ADD COLUMN IF NOT EXISTS cohort_type text;
ALTER TABLE performance_snapshots ADD COLUMN IF NOT EXISTS product_category text;

-- Add check constraint matching SCHEMA.md
ALTER TABLE performance_snapshots ADD CONSTRAINT chk_performance_snapshots_cohort_type
  CHECK (cohort_type IS NULL OR cohort_type IN ('treated', 'control'));

-- Add index for cohort-based queries
CREATE INDEX IF NOT EXISTS idx_performance_snapshots_cohort_date
  ON performance_snapshots (cohort_type, snapshot_date DESC);
```

### Existing Join Pattern (Proven in /api/performance/route.ts)
```typescript
// This pattern WORKS TODAY with 178/179 rows matching (from Phase 28 audit)
// Source: /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/performance/route.ts

// 1. Get publish events
const { data: publishEvents } = await supabase
  .from('publish_events')
  .select('id, master_sku, platform, published_at, prompt_hash, content_version')
  .eq('status', 'success')
  .eq('action', 'publish')

// 2. Get snapshots linked by publish_event_id
const { data: snapshots } = await supabase
  .from('performance_snapshots')
  .select('master_sku, platform, snapshot_date, ctr, cvr, days_since_publish, publish_event_id')
  .in('master_sku', uniqueSkus)

// 3. Get impact scores by publish_event_id
const { data: scores } = await supabase
  .from('performance_impact_scores')
  .select('publish_event_id, metric_name, did_lift_pct, label, confidence, sample_size_treated, sample_size_control')
  .in('publish_event_id', eventIds)
  .in('metric_name', ['ctr', 'cvr', 'roas'])
```

### Sidebar Navigation Entry
```typescript
// Source: /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/components/shared/Sidebar.tsx
// Add after Performance entry (line 34)
{ name: 'Content Impact', href: '/content-impact', icon: TrendingUp },
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/performance` page with simple before/after | Phase 29: Dedicated feedback page with impact scores, control cohorts, search term deltas | This phase | Users get actionable feedback on content changes |
| No diff-in-diff scoring | Python pipeline computes DID with confidence | Already implemented in `performance_impact.py` | Just needs the table to write to |
| Manual search term comparison | `search-delta/route.ts` computes gained/lost terms | Already exists | Just needs UI wiring |
| No prompt_hash on publish events | prompt_hash populated since 2026-02-16 | Migration 034 | FEED-04 enforces going forward |

## Open Questions

1. **Impact score time windows vs CONTEXT.md windows**
   - What we know: The Python pipeline computes impact with configurable `pre_window_days` and `post_window_days` (default 30 each). CONTEXT.md requires 7/14/30-day columns.
   - What's unclear: Should impact scores be computed separately for 7/14/30-day windows, or compute once with 30-day window and show simple CTR/CVR averages for 7/14 windows?
   - Recommendation: Show simple CTR/CVR averages for all three windows from `performance_snapshots`. Show DID impact score only for the 30-day window (most statistically meaningful). The 7-day and 14-day windows would show "Pending" if insufficient data.

2. **Backfill prompt_hash for existing events**
   - What we know: 82.9% of `generated_content` rows have `generation_prompt_hash`. A backfill script could populate ~67 of 69 success events.
   - What's unclear: Should backfill be part of Phase 29 scope or left for later?
   - Recommendation: Include a one-time backfill script as a low-priority task. It improves the feedback view for historical SKUs. The user's CONTEXT.md says "leave as-is" for existing NULLs, so this is optional but beneficial.

3. **Control cohort size and quality**
   - What we know: Python collector selects controls by product_category match with `max_controls=500`. Current variant_index has multiple product categories.
   - What's unclear: Whether the category-level matching produces good controls for Allied Brass's specific product catalog.
   - Recommendation: Use existing Python logic as-is. The expandable detail row (per CONTEXT.md) will show which controls were used, letting users evaluate quality manually.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pyproject.toml config |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_performance_impact.py -x` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x --timeout=30` |
| Estimated runtime | ~15 seconds for performance_impact tests |

### Dashboard Build Verification
| Property | Value |
|----------|-------|
| Framework | Next.js + TypeScript |
| Build command | `cd dashboard && npm run build` |
| Lint command | `cd dashboard && npm run lint` |
| Type check | `cd dashboard && npx tsc --noEmit` |
| Estimated runtime | ~30-60 seconds for full build |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEED-01 | Feedback view joins tables correctly | integration (dashboard build) | `cd dashboard && npm run build` | Page doesn't exist yet -- Wave 0 |
| FEED-01 | Window aggregation logic | unit | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_performance_impact.py -x` | Partial -- existing tests cover DID but not window aggregation in TS |
| FEED-02 | Impact scores written to table | integration | `curl -X POST pipeline/performance/compute-impact` | Manual -- requires production table to exist |
| FEED-02 | DID computation correctness | unit | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_performance_impact.py -x` | Yes -- existing tests |
| FEED-03 | Search query snapshots populated | integration | `curl -X POST dashboard/api/monitoring/snapshot-capture` | Manual -- requires production data |
| FEED-03 | Search delta detection | integration (dashboard build) | `cd dashboard && npm run build` | Route exists but no unit tests |
| FEED-04 | prompt_hash NOT NULL enforcement | unit | `cd dashboard && npm run build` (type safety) | No -- Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After every committed task -> run: `cd dashboard && npm run build`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** `cd dashboard && npm run build && npm run lint` + `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_performance_impact.py -x`
- **Estimated feedback latency per task:** ~45 seconds

### Wave 0 Gaps (must be created before implementation)
- [ ] `tests/test_window_aggregation.py` -- covers FEED-01 window logic (if implementing in Python)
- [ ] Dashboard build must pass after each UI task -- existing `npm run build` serves as integration test
- [ ] No new test framework needed -- existing pytest and Next.js build cover requirements

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** -- All findings verified by reading actual source files
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/monitoring/performance_impact.py` -- Full DID implementation
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/performance/route.ts` -- Existing join pattern
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/monitoring/search-delta/route.ts` -- Search term delta logic
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/monitoring/snapshot-capture/route.ts` -- Snapshot capture
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/publish/sku/route.ts` -- Publish event insert with prompt_hash
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/phases/28-architecture-audit-migration-triage/28-null-audit-and-quota.md` -- Production data state

### Secondary (MEDIUM confidence)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` -- Table schemas (documented state, may differ from production per Phase 28 findings)

### Tertiary (LOW confidence)
- Impact score tier thresholds (recommended values based on general causal inference practice, not project-specific validation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already in use, no new dependencies
- Architecture: HIGH -- Follows existing codebase patterns exactly (API routes, client pages, Supabase queries)
- Pitfalls: HIGH -- All identified from Phase 28 audit findings and actual code inspection
- Schema gaps: HIGH -- Verified by Phase 28 production queries (performance_impact_scores missing, cohort_type/product_category columns missing)

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable -- no external dependency changes expected)
