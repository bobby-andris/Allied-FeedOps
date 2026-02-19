# Phase 12: Dashboard Audit

**Audited:** 2026-02-19
**Method:** Code inspection — page files, API routes, and component logic

---

## Status Summary

| Page | Route | Status | Issue Summary | Action |
|------|-------|--------|---------------|--------|
| Overview | / | STALE | "Pending Review" count reads from `sku_approvals.approval_status = 'pending'` but the actual workflow uses the review queue (generated_content), not a pending approval status. Also shows no "pending" guidance if count is 0, and platform breakdown falls back to overall counts when variant_approvals is empty, showing duplicate data | FIX |
| Generate | /generate | WORKING | Multi-step wizard with tier-based SKU selection, progress polling, past jobs tab. Error handling is inline. No issues. | KEEP |
| Review Queue | /review | WORKING | Server component fetches enriched SKU data with platform progress, lifestyle image lifecycle. ReviewListClient renders compact expandable rows with filtering. Well-structured. | KEEP |
| Review [SKU] | /review/[sku] | WORKING | Full SKU detail view with platform tabs, content cards, variant accordions, lifestyle image review. Well-implemented. | KEEP |
| Competitors | /competitors | DEAD-END | Page loads and shows empty state correctly when no data. Scraping requires Apify API key configured. If no recent scrape has run, all tabs show empty. Category-based workflow doesn't connect to current SKU-specific optimization flow. No guidance on when to use this vs search insights. | SIMPLIFY |
| Batches | /batches | WORKING | Server component with reconciliation logic. Batch creation, publish, status tracking all functional. `draft` status issue was fixed (migration 025). | KEEP |
| Performance | /performance | WORKING | Snapshot-based comparison, sortable table, inline SKU detail panel, delta badges. Recently updated in Phase 11. | KEEP |
| Search Insights | /search-insights | WORKING | SKU-level search query analysis with variant breakdown, gap analysis, keyword planner metrics. Requires manual SKU entry — no browse/list mode. Sync status banner present. | KEEP |
| Backfill Monitoring | /backfill | WORKING | Shows active Cloud Run backfill jobs, coverage KPIs, freshness heatmap, API health panel. Depends on `@tremor/react` for `Metric` + `ProgressBar` components. Coverage panel requires `/api/monitoring/backfill-health` working. No action to start a backfill from the UI (informational only). | KEEP |
| Settings | /settings | STALE | Notification switches (`Switch defaultChecked`) have no persistence — they reset on page reload. Danger Zone "Clear" buttons are wired up but have no confirmation dialog. Supabase URL is hardcoded in the UI (not a runtime env var display). | FIX |
| Post-Publish Monitoring | /monitoring | BROKEN | Uses `alert()` for snapshot capture feedback (line 107). Empty state says "wait 7+ days" with no link to take action. Search delta empty state says "Run search insights sync first" with no link. Snapshot capture calls `/api/monitoring/snapshot-capture` which queries `search_query_snapshots` table — but performance snapshot capture (the one that's actually automated via Cloud Scheduler) lives at `/api/performance/capture-snapshot`. The monitoring page's snapshot button captures SEARCH query snapshots, not performance snapshots — this is likely confusing and may be why the monitoring page shows no data even when the Performance page has data. | FIX |

---

## Issues Requiring Fix (Plan 12-02)

### Overview (/)

- **Status:** STALE
- **Root cause 1:** `overview.pendingReview` is `sku_approvals.approval_status = 'pending'` (line 36 in `/api/stats/route.ts`). This count represents SKUs that have been explicitly created in `sku_approvals` with pending status — not SKUs that have generated content awaiting first review. A SKU with content in `generated_content` but no row in `sku_approvals` won't appear as "pending". This could show 0 pending even when SKUs need review.
- **Root cause 2:** Platform breakdown falls back to overall `sku_approvals` counts when `variant_approvals` is empty for a platform (lines 59–66 in `/api/stats/route.ts`), causing triplicate display of the same numbers across Google/Bing/Shopify.
- **Root cause 3:** Quality Distribution chart shows `No scores yet` when `qualityScores.average === 0`, but 0 is a valid average. Condition should check `scores.length === 0`.
- **File(s):**
  - `dashboard/src/app/api/stats/route.ts` (lines 34–45, 51–66, 82–83)
  - `dashboard/src/app/(dashboard)/page.tsx` (line 178)
- **Fix:** (1) For pendingReview, use `generated_content` SKU count minus `sku_approvals` approved count, OR add guidance that "pending" means no approval row yet. (2) For platform breakdown, return empty arrays rather than fallback totals when no variant approvals exist — makes the "0 approved" state explicit rather than misleading. (3) Fix quality check to use `scores.length === 0`.

---

### Settings (/settings)

- **Status:** STALE
- **Root cause 1:** Notification switches (lines 216, 224, 232 in `settings/page.tsx`) use `defaultChecked` with no state or persistence. They reset on page reload. If these switches don't do anything yet, they're misleading UI.
- **Root cause 2:** Danger Zone "Clear" buttons (lines 254, 261) have no confirmation dialog. They call no visible action handler — but appear dangerous. Without a click handler, they're non-functional buttons that look functional.
- **Root cause 3:** Supabase URL hardcoded as display value: `value="https://qezuszwufortkiutlhym.supabase.co"` (line 127). Should use `process.env.NEXT_PUBLIC_SUPABASE_URL` or remove entirely.
- **File(s):**
  - `dashboard/src/app/(dashboard)/settings/page.tsx` (lines 127, 216–234, 249–263)
- **Fix:** (1) Remove notification switches (not wired up, misleading) or replace with static info about current notification config. (2) Add confirmation dialog or remove Danger Zone buttons entirely if they have no handler. (3) Replace hardcoded URL with env var or remove the display field.

---

### Post-Publish Monitoring (/monitoring)

- **Status:** BROKEN
- **Root cause 1:** `alert()` on line 107 in `monitoring/page.tsx` — browser `alert()` used for snapshot capture feedback. Blocks the UI thread and looks unpolished.
- **Root cause 2:** Performance delta empty state (line 228) says "Publish some content and wait 7+ days" with no link or action. Users have no path forward.
- **Root cause 3:** Search delta empty state (line 321) says "Run search insights sync first" with no link to `/search-insights`.
- **Root cause 4 (deeper):** The "Capture Snapshots" button calls `/api/monitoring/snapshot-capture` (line 100) which captures **search query snapshots** into `search_query_snapshots` table. The performance snapshot capture (used by the Performance page) is at `/api/performance/capture-snapshot` and writes to `performance_snapshots`. These are two different tables for two different purposes. The monitoring page's performance delta tab reads from `performance_snapshots` (via `/api/monitoring/performance-delta`), but the Capture Snapshots button only captures search query snapshots — **there's no button to capture performance snapshots from this page**. Users expecting "Capture Snapshots" to refresh both tabs will see only search data update.
- **Root cause 5:** `/api/monitoring/performance-delta` queries `performance_snapshots` table. This data *does* exist (44 snapshots backfilled). The empty state on the performance delta tab appears because the query needs `days_since_publish >= 7` (min_days default). SKUs published recently may not appear. The empty state message doesn't explain the 7-day threshold.
- **File(s):**
  - `dashboard/src/app/(dashboard)/monitoring/page.tsx` (lines 100, 107, 228–231, 321–323)
  - `dashboard/src/app/api/monitoring/performance-delta/route.ts`
  - `dashboard/src/app/api/monitoring/snapshot-capture/route.ts`
- **Fix:**
  1. Replace `alert()` with inline toast/status message in the existing card.
  2. Add links in empty states: performance delta → `/performance`, search delta → `/search-insights`.
  3. Rename "Capture Snapshots" button to "Capture Search Snapshots" to clarify what it does. Add a second "Capture Performance Snapshots" button that calls `/api/performance/capture-snapshot`.
  4. Add 7-day threshold explanation to performance delta empty state.

---

## Pages to Simplify (Plan 12-03)

### Competitors (/competitors)

- **Status:** DEAD-END
- **Rationale:** The competitors page is category-based (hardcoded categories like "towel bars", "grab bars") and not connected to the SKU-specific workflow that the rest of the dashboard uses. Content optimization is now driven by search query data from Google Ads (Search Insights) rather than competitive SERP scraping. The Apify-powered scraping is functional but requires separate scheduling and adds cost without clear integration into the optimize-review-publish workflow. No recent scrape jobs means the page shows entirely empty state.
- **Action: SIMPLIFY** — Reduce to a single tab, remove marketplace scraping buttons (they're not used), and add a prominent empty state with guidance: "Run a SERP scrape to see competitor titles for your categories."
- **Alternative: REMOVE** — If the competitive intelligence workflow is not planned for re-use in the near term, the page could be removed entirely. The data it surfaces (competitor titles, patterns) is interesting but not actionable in the current workflow.
- **Files:**
  - `dashboard/src/app/(dashboard)/competitors/page.tsx`
  - `dashboard/src/app/api/competitors/route.ts`
  - `dashboard/src/app/api/competitors/scrape/route.ts`

---

## Out-of-Scope Observations (Deferred)

The following were noticed during inspection but are NOT blocking and will not be fixed in Phase 12:

1. `search-insights/page.tsx` line 209: uses deprecated `onKeyPress` event (should be `onKeyDown`). Non-breaking.
2. `monitoring/page.tsx` line 121: `eslint-disable-next-line react-hooks/exhaustive-deps` suppresses a legitimate warning on the `useEffect` with `skuFilter`. Not broken but could cause stale closure bugs if other state is added.
3. Overview quick-links section only shows Review Queue, Batch Management, Performance — not Search Insights or Backfill Monitoring. Minor navigation gap, not broken.
