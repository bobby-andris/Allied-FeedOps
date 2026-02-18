---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/api/performance/capture-snapshot/route.ts
  - dashboard/src/app/api/performance/route.ts
autonomous: true
must_haves:
  truths:
    - "Performance page shows real data for ~35 published Google SKUs"
    - "Snapshot capture endpoint correctly reads published_at from publish_events"
    - "Performance API returns data when platform=all (no platform param)"
  artifacts:
    - path: "dashboard/src/app/api/performance/capture-snapshot/route.ts"
      provides: "Fixed snapshot capture with correct column names"
    - path: "dashboard/src/app/api/performance/route.ts"
      provides: "Performance API with correct publish_events query"
  key_links:
    - from: "capture-snapshot/route.ts"
      to: "publish_events table"
      via: "Supabase query"
      pattern: "published_at"
    - from: "performance/route.ts"
      to: "publish_events + baselines + snapshots"
      via: "Supabase queries + Google Ads API"
      pattern: "fetchShoppingPerformance"
---

<objective>
Fix bugs in the snapshot capture and performance API endpoints, then backfill performance snapshots for ~35 published Google SKUs.

Purpose: The Performance page shows no data because (1) capture-snapshot uses wrong column name `executed_at` (should be `published_at`), (2) capture-snapshot doesn't filter on `action = 'publish'`, and (3) only 1 test row exists in performance_snapshots.
Output: Working snapshot capture, populated performance_snapshots table, Performance page showing real data.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/database/SCHEMA.md
@dashboard/src/app/api/performance/capture-snapshot/route.ts
@dashboard/src/app/api/performance/route.ts
@dashboard/src/app/(dashboard)/performance/page.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix capture-snapshot endpoint bugs</name>
  <files>dashboard/src/app/api/performance/capture-snapshot/route.ts</files>
  <action>
Fix two bugs in the capture-snapshot endpoint:

1. **Wrong column name**: Line 36 selects `executed_at` but the `publish_events` schema column is `published_at`. Change the select to use `published_at` instead of `executed_at`. Also update line 122 where it reads `publishEvent.executed_at` to use `publishEvent.published_at`.

2. **Missing action filter**: The endpoint queries publish_events with only `.eq('status', 'success')` but doesn't filter on `.eq('action', 'publish')`. This could include rollback events or other actions. Add `.eq('action', 'publish')` to the query chain (after the status filter, around line 37).

After fixing, verify the endpoint compiles:
```bash
cd dashboard && npx tsc --noEmit
```
  </action>
  <verify>
Run `cd dashboard && npx tsc --noEmit` - zero errors.
Grep the file to confirm `published_at` appears and `executed_at` does not:
`grep -n "executed_at\|published_at" dashboard/src/app/api/performance/capture-snapshot/route.ts`
  </verify>
  <done>capture-snapshot endpoint uses correct `published_at` column and filters on `action = 'publish'`</done>
</task>

<task type="auto">
  <name>Task 2: Backfill snapshots and verify Performance page data</name>
  <files>dashboard/src/app/api/performance/capture-snapshot/route.ts</files>
  <action>
After Task 1 fixes are applied:

1. **Verify build passes**: `cd dashboard && npm run build` must succeed before any deployment.

2. **Push to master** to deploy the fix: `git push origin master`

3. **Wait ~2 minutes** for Vercel deployment, then call the capture-snapshot endpoint to backfill:
```bash
curl -X POST "https://allied-feed-ops.vercel.app/api/performance/capture-snapshot"
```
Expect response with `snapshots_created > 0`. If `snapshots_created: 0`, check the `errors` array in the response for clues.

4. **Verify snapshots were created** by querying Supabase (via MCP):
```sql
SELECT COUNT(*), MIN(days_since_publish), MAX(days_since_publish)
FROM performance_snapshots
WHERE fetched_at > NOW() - INTERVAL '1 hour';
```

5. **Verify Performance page shows data**: Call the performance API:
```bash
curl "https://allied-feed-ops.vercel.app/api/performance?dateRange=30d"
```
Confirm `summary.totalPublished > 0` and `skus` array has entries with non-zero `current` values.

If the capture endpoint returns 0 snapshots, debug by checking:
- Are there publish_events with `status='success'` and `action='publish'`?
- Do those SKUs have variant_index entries with shopify_product_id?
- Does Google Ads have performance data for those product IDs?
  </action>
  <verify>
`curl "https://allied-feed-ops.vercel.app/api/performance?dateRange=30d"` returns JSON with `summary.totalPublished > 0` and non-empty `skus` array.
Supabase query: `SELECT COUNT(*) FROM performance_snapshots WHERE fetched_at > NOW() - INTERVAL '1 hour'` returns > 0.
  </verify>
  <done>performance_snapshots table has real rows with days_since_publish values, Performance page displays published SKU data with baseline vs current comparison</done>
</task>

</tasks>

<verification>
1. `cd dashboard && npm run build` passes
2. `performance_snapshots` table has rows for published SKUs (not just 1 test row)
3. `/api/performance?dateRange=30d` returns data with `totalPublished > 0`
4. Performance page at https://allied-feed-ops.vercel.app/performance shows SKU rows with metrics
</verification>

<success_criteria>
- capture-snapshot endpoint uses `published_at` (not `executed_at`) and filters `action = 'publish'`
- performance_snapshots has real data for ~35 published Google SKUs
- Performance page shows baseline vs current comparison for published SKUs
- Build passes cleanly
</success_criteria>

<output>
After completion, create `.planning/quick/2-backfill-performance-snapshots-and-impro/2-SUMMARY.md`
</output>
