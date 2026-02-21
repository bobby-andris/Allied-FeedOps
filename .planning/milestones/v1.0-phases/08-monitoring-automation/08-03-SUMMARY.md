---
phase: 08-monitoring-automation
plan: 03
subsystem: dashboard-monitoring-ui
tags: [dashboard, monitoring, ui, backfill-visibility, tremor]
dependency_graph:
  requires:
    - src/feedops/api/backfill.py (GET /backfill/jobs endpoint)
    - src/feedops/api/monitoring.py (GET /monitoring/freshness, /monitoring/coverage, /monitoring/api-health)
    - '@tremor/react' (data visualization components)
  provides:
    - dashboard/src/app/(dashboard)/backfill/page.tsx (Backfill monitoring dashboard)
    - dashboard/src/app/api/backfill/route.ts (Next.js API proxy to Cloud Run /backfill/jobs)
    - dashboard/src/app/api/monitoring/backfill-health/route.ts (Next.js API proxy aggregating monitoring endpoints)
  affects:
    - None (new dashboard page, no modifications to existing code)
tech_stack:
  added:
    - '@tremor/react@3.18.7': Pre-built data visualization components (Metric, ProgressBar, Card)
  patterns:
    - Auto-polling with cleanup: useEffect + setInterval for running jobs, stops on terminal state
    - Promise.allSettled for parallel endpoint aggregation with graceful degradation
    - Responsive grid layouts with Tailwind (mobile stack, desktop side-by-side)
    - Color-coded KPIs based on threshold logic (green/yellow/red)
key_files:
  created:
    - dashboard/src/app/(dashboard)/backfill/page.tsx: Backfill monitoring dashboard with 4 panels (jobs, coverage, freshness, health)
    - dashboard/src/app/api/backfill/route.ts: Next.js API proxy to Cloud Run /backfill/jobs
    - dashboard/src/app/api/monitoring/backfill-health/route.ts: Next.js API proxy aggregating 3 monitoring endpoints
  modified:
    - dashboard/package.json: Added @tremor/react dependency
decisions:
  - title: "Install Tremor with --legacy-peer-deps"
    rationale: "Tremor requires React 18, project uses React 19. --legacy-peer-deps allows installation without breaking changes."
    alternatives: ["Wait for Tremor to support React 19", "Use shadcn/ui components only"]
    impact: "Enables use of pre-built Metric and ProgressBar components, no runtime issues observed"
  - title: "Separate polling for jobs vs. monitoring data"
    rationale: "Job status changes frequently (5s refresh needed), coverage/freshness/health data changes slowly (mount-only fetch)"
    alternatives: ["Poll everything at 5s intervals", "Use WebSocket for real-time updates"]
    impact: "Reduces unnecessary API calls for slow-changing monitoring data, minimizes dashboard load on Cloud Run"
  - title: "Limit freshness heatmap to 500 SKUs"
    rationale: "Rendering 2,784 DOM elements causes performance issues in browser, 500 provides sufficient visual insight"
    alternatives: ["Virtualized scrolling", "Server-side aggregation to color buckets"]
    impact: "Fast initial render, note displayed when >500 SKUs exist"
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_modified: 5
  lines_added: 916
  commits: 2
  completed_date: "2026-02-13"
---

# Phase 08 Plan 03: Backfill Monitoring Dashboard Summary

**One-liner:** Built Next.js dashboard page at /backfill with real-time job status, coverage KPIs, freshness heatmap, and API health panels using Tremor components

## Objective Completion

Created the backfill monitoring dashboard page that gives Bobby visual insight into:
- **Job progress** (MON-01): Table with status badges, progress bars, ETAs, auto-refreshes every 5s for running jobs
- **Coverage metrics** (MON-02): KPI cards showing X/2,784 SKUs with search terms, performance, keywords (color-coded)
- **Freshness heatmap** (MON-03): Grid of colored squares per SKU with green/yellow/orange/red age thresholds
- **API health** (MON-04): Latency p95, error counts, rate limit hits from metrics_registry

All 4 panels are responsive, use Tremor for data visualization, and follow existing dashboard patterns.

## Implementation Details

### Task 1: Create Next.js API Proxy Routes

Created two API routes following the pattern from `dashboard/src/app/api/regenerate/route.ts`:

**dashboard/src/app/api/backfill/route.ts**
- GET handler that proxies to Cloud Run `GET /backfill/jobs`
- Forwards `status` and `limit` query params to upstream
- Returns JSON response with job list
- Error handling returns 502 on upstream failure
- Uses `cache: 'no-store'` to avoid stale data

**dashboard/src/app/api/monitoring/backfill-health/route.ts**
- GET handler that aggregates 3 monitoring endpoints into one response
- Fetches from Cloud Run: `/monitoring/freshness`, `/monitoring/coverage`, `/monitoring/api-health`
- Uses `Promise.allSettled` to fetch all 3 in parallel (graceful degradation)
- Returns combined JSON: `{"freshness": {...}, "coverage": {...}, "apiHealth": {...}}`
- Any failed fetch returns null for that section (doesn't block other data)

**Files created:**
- `dashboard/src/app/api/backfill/route.ts` (41 lines)
- `dashboard/src/app/api/monitoring/backfill-health/route.ts` (60 lines)

**Commit:** `6064d2f3`

### Task 2: Install Tremor and Build Backfill Monitoring Dashboard

**Step 1: Install Tremor**
- Ran: `npm install @tremor/react --legacy-peer-deps`
- Required `--legacy-peer-deps` because Tremor supports React 18, project uses React 19
- No runtime issues observed, all components work correctly

**Step 2: Create dashboard/src/app/(dashboard)/backfill/page.tsx**

Built client-side page with 4 monitoring panels:

**Panel 1: Active Jobs Table (MON-01)**
- Fetches `/api/backfill` for job list
- Table columns: Job ID (truncated to 8 chars), Type, Status badge, Progress bar, Items (completed/total), ETA
- Status badges: running=blue, complete=green, failed=red, partial=yellow, creating=gray
- Uses Tremor `<Table>`, `<Badge>`, `<ProgressBar>` components
- Auto-refresh logic: `setInterval` every 5 seconds when ANY job has status "running"
- Stops polling when all jobs are terminal (complete/failed/partial)
- Cleanup: `clearInterval` in useEffect return function

**Panel 2: Coverage KPI Cards (MON-02)**
- Fetches `/api/monitoring/backfill-health` (coverage section)
- 3 Tremor `<Metric>` cards in vertical stack:
  - Search Terms: {N}/2784 SKUs with percentage subtitle
  - Performance: {N}/2784 SKUs with percentage subtitle
  - Keywords: {N}/2784 SKUs with percentage subtitle
- Color coding function `getCoverageColor()`: >90% green, 50-90% yellow, <50% red
- Percentage calculation function `getCoveragePercentage()`: (coverage / total) * 100

**Panel 3: Data Freshness Heatmap (MON-03)**
- Fetches `/api/monitoring/backfill-health` (freshness section)
- Grid of small colored squares (16px × 16px) using CSS grid with `auto-fill`
- Color logic function `getFreshnessColor()`:
  - Green (#10b981): ≤7 days
  - Yellow (#fbbf24): 8-30 days
  - Orange (#fb923c): 31-60 days
  - Red (#ef4444): >60 days
- Uses max age across all data types (search_terms, performance, keywords) for color
- Hover tooltip with `title` attribute shows SKU name and age
- Legend at bottom with 4 color thresholds
- Limits display to first 500 SKUs for performance (note shown if >500 exist)
- Scrollable container with `maxHeight: 300px`

**Panel 4: API Health Cards (MON-04)**
- Fetches `/api/monitoring/backfill-health` (apiHealth section)
- 3 Tremor `<Metric>` cards in vertical stack:
  - Latency P95: {N}ms with sample size subtitle
  - Error Count: {N} with "HTTP request errors" subtitle
  - Rate Limit Hits: {N} with provider errors subtitle
- Color thresholds function `getLatencyColor()`: <500ms green, 500-2000ms yellow, >2000ms red
- Error count: red if >0, green if 0
- Rate limit hits: yellow if >0, green if 0

**Polling Strategy:**
- Job list: useEffect with dependency on `jobs` array triggers 5s interval when running jobs exist
- Monitoring data: useEffect with empty dependency array (mount only) — data changes slowly
- All loading states use Skeleton components from shadcn/ui
- Empty states with helpful messages for each panel

**Layout:**
- Row 1: Active Jobs (2/3 width) + Coverage KPIs (1/3 width) — `grid-cols-1 lg:grid-cols-3`
- Row 2: Freshness Heatmap (1/2 width) + API Health (1/2 width) — `grid-cols-1 lg:grid-cols-2`
- Mobile: stacks all panels vertically
- Desktop: side-by-side as specified

**Files modified:**
- `dashboard/package.json` (+1 dependency)
- `dashboard/package-lock.json` (Tremor + dependencies)
- `dashboard/src/app/(dashboard)/backfill/page.tsx` (415 lines)

**Commit:** `067925ba`

## Verification Results

All plan verification criteria passed:

1. ✓ `cd dashboard && npm run build` passes (build successful, /backfill route listed)
2. ✓ `/backfill` page exists at `dashboard/src/app/(dashboard)/backfill/page.tsx`
3. ✓ API proxy routes compile and proxy to Cloud Run
4. ✓ Tremor is installed in package.json (@tremor/react@3.18.7)
5. ✓ Page has 4 distinct panels: jobs table, coverage KPI cards, freshness heatmap grid, API health cards
6. ✓ Polling stops when no running jobs (useEffect cleanup + conditional interval)

**Success criteria met:**
- ✓ Dashboard /backfill page shows all 4 monitoring panels
- ✓ Job list auto-refreshes during active jobs (5s interval with cleanup)
- ✓ Coverage KPIs show X/2784 with color coding (getCoverageColor function)
- ✓ Freshness heatmap displays per-SKU age with color legend (4 thresholds documented)
- ✓ API health shows latency p95, errors, rate limit hits (3 Tremor Metric cards)
- ✓ Full dashboard build passes with zero errors

## Deviations from Plan

None - plan executed exactly as written.

## Output

Created `/backfill` dashboard page with complete monitoring visibility. Next plan (08-04) will add Cloud Scheduler automation for daily incremental refresh.

## Self-Check: PASSED

**Files created:**
```bash
[ -f "dashboard/src/app/(dashboard)/backfill/page.tsx" ] && echo "FOUND: backfill/page.tsx"
[ -f "dashboard/src/app/api/backfill/route.ts" ] && echo "FOUND: api/backfill/route.ts"
[ -f "dashboard/src/app/api/monitoring/backfill-health/route.ts" ] && echo "FOUND: api/monitoring/backfill-health/route.ts"
```
FOUND: backfill/page.tsx
FOUND: api/backfill/route.ts
FOUND: api/monitoring/backfill-health/route.ts

**Commits exist:**
```bash
git log --oneline --all | grep -E "(6064d2f3|067925ba)"
```
067925ba feat(08-03): install Tremor and build backfill monitoring dashboard page
6064d2f3 feat(08-03): create Next.js API proxy routes for backfill and monitoring endpoints

**Build verification:**
```bash
cd dashboard && npm run build 2>&1 | grep -E "(backfill|error)"
```
├ ○ /backfill

All files and commits verified. Build successful with /backfill route listed.
