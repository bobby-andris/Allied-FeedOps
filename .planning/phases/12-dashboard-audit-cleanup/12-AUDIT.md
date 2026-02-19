# Phase 12: Dashboard Audit

**Audited:** 2026-02-19
**Method:** Code inspection — page files, API routes, and component logic
**Verified:** 2026-02-19 — agent-browser walkthrough on live Vercel URL after all 3 plans complete

---

## Status Summary

| Page | Route | Initial Status | Action | Final Status (Verified) |
|------|-------|----------------|--------|-------------------------|
| Overview | / | STALE | FIX (plan 12-02) | VERIFIED — stats cards render, quality distribution correct, quick-action links work |
| Generate | /generate | WORKING | KEEP | VERIFIED — multi-step wizard loads, tier distribution visible, past jobs tab present |
| Review Queue | /review | WORKING | KEEP | VERIFIED — 97 SKUs listed, platform filter stats correct, expandable rows work |
| Review [SKU] | /review/[sku] | WORKING | KEEP | VERIFIED — SKU detail view loads (tested /review/1016) |
| Competitors | /competitors | DEAD-END | SIMPLIFY (plan 12-03) | VERIFIED — SERP-only layout, Marketplace tab removed, usage guidance banner present, contextual empty state for no-data |
| Batches | /batches | WORKING | KEEP | VERIFIED — batch table renders, stats (6 total, 5 published) visible |
| Performance | /performance | WORKING | KEEP | VERIFIED — sortable table with delta badges, 36 SKUs with snapshot data |
| Search Insights | /search-insights | WORKING | KEEP | VERIFIED — page loads, "Enter a Master SKU" guidance visible |
| Backfill Monitoring | /backfill | WORKING | KEEP | VERIFIED — "No backfill jobs found" empty state, freshness heatmap and API health sections visible |
| Settings | /settings | STALE | FIX (plan 12-02) | VERIFIED — notification switches removed, Danger Zone has text guidance, Supabase URL shows env var value |
| Post-Publish Monitoring | /monitoring | BROKEN | FIX (plan 12-02) | VERIFIED — no alert() dialogs, two separate snapshot buttons, performance delta data showing |

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
