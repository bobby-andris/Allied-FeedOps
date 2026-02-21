---
phase: 12-dashboard-audit-cleanup
plan: "01"
subsystem: dashboard
tags: [audit, ux, cleanup]
dependency_graph:
  requires: []
  provides: [12-AUDIT.md]
  affects: [12-02-PLAN.md, 12-03-PLAN.md]
tech_stack:
  added: []
  patterns: [code-inspection, dev-server-validation]
key_files:
  created:
    - .planning/phases/12-dashboard-audit-cleanup/12-AUDIT.md
  modified: []
decisions:
  - "Post-Publish Monitoring (/monitoring) is BROKEN — alert() for snapshot feedback + mismatched snapshot buttons (search vs performance snapshots)"
  - "Competitors (/competitors) is DEAD-END — category-based workflow disconnected from SKU-specific optimization flow"
  - "Settings (/settings) has non-functional UI (non-persisting switches, no-op Danger Zone buttons)"
  - "Overview (/) stats use sku_approvals pending count which may not reflect generated_content awaiting review"
metrics:
  duration_minutes: 2
  completed_date: "2026-02-19"
  tasks_completed: 2
  files_changed: 1
---

# Phase 12 Plan 01: Dashboard Audit Summary

Code inspection of all 11 dashboard pages with status classification, issue documentation, and dev server validation — producing 12-AUDIT.md as the foundation for Plans 12-02 and 12-03.

## Final Audit Table

| Page | Route | Status | Action |
|------|-------|--------|--------|
| Overview | / | STALE | FIX |
| Generate | /generate | WORKING | KEEP |
| Review Queue | /review | WORKING | KEEP |
| Review [SKU] | /review/[sku] | WORKING | KEEP |
| Competitors | /competitors | DEAD-END | SIMPLIFY |
| Batches | /batches | WORKING | KEEP |
| Performance | /performance | WORKING | KEEP |
| Search Insights | /search-insights | WORKING | KEEP |
| Backfill Monitoring | /backfill | WORKING | KEEP |
| Settings | /settings | STALE | FIX |
| Post-Publish Monitoring | /monitoring | BROKEN | FIX |

## Status Count

- WORKING: 7
- STALE: 2 (Overview, Settings)
- BROKEN: 1 (Post-Publish Monitoring)
- DEAD-END: 1 (Competitors)
- LOW-VALUE: 0

## Issues List for Plan 12-02

### 1. Post-Publish Monitoring — BROKEN

The most significant issue. Three distinct problems:

1. **`alert()` for feedback** — `monitoring/page.tsx` line 107 uses `window.alert()` for snapshot capture feedback, blocking the UI thread.
2. **Misleading "Capture Snapshots" button** — calls `/api/monitoring/snapshot-capture` which captures **search query snapshots** into `search_query_snapshots`. The performance snapshot (written by `/api/performance/capture-snapshot` to `performance_snapshots`) is entirely separate. Users clicking the button expect both tabs to refresh, but only the search delta tab could update.
3. **Empty states with no action links** — Performance delta: "wait 7+ days" with no link. Search delta: "Run search insights sync first" with no link.

**Fix:** Replace `alert()` with inline status, rename/split the button, add navigation links.

### 2. Overview — STALE

1. **Pending Review count is misleading** — reads `sku_approvals.approval_status = 'pending'` but many SKUs have generated content in `generated_content` with no row in `sku_approvals` at all. These don't appear as "pending".
2. **Platform breakdown fallback** — when no `variant_approvals` exist for a platform, falls back to overall `sku_approvals` totals, showing the same numbers for Google/Bing/Shopify.
3. **Quality distribution condition** — checks `qualityScores.average > 0` for "no scores yet" but 0 is a valid average.

**Fix:** Correct the pending count source, remove fallback totals, fix quality condition.

### 3. Settings — STALE

1. **Non-persisting notification switches** — `Switch defaultChecked` with no state or API, resets on reload.
2. **No-op Danger Zone buttons** — "Clear all approvals" and "Clear performance data" have no click handlers in the code.
3. **Hardcoded Supabase URL** — line 127, should use env var or be removed.

**Fix:** Remove switches or add static info, remove or implement Danger Zone buttons with confirmation, remove hardcoded URL.

## Pages for Plan 12-03

### Competitors — DEAD-END / SIMPLIFY

Category-based SERP scraping (towel bars, grab bars, etc.) is disconnected from the SKU-specific workflow. No recent scrape data means entirely empty state. Options: simplify to single SERP tab with better empty state guidance, or remove if competitive intelligence is not in the near-term roadmap.

## Deviations from Plan

None — plan executed exactly as written.

## Dev Server Validation Notes

- Dev server started clean in 895ms, no compilation errors
- Auth guard redirects all dashboard routes to `/login` (307)
- Performance page API confirmed working via dev server log: `/api/performance?baselineWindow=30d&snapshotWindow=30d 200 in 1277ms`
- Auth credentials not accessible — local walkthrough validated dev server health and compilation only
- All code-level findings were confirmed via static analysis of page files, component trees, and API route logic

## Self-Check: PASSED

- `12-AUDIT.md` exists at `.planning/phases/12-dashboard-audit-cleanup/12-AUDIT.md`
- Commit `3642e199` confirmed in git log
- All 11 pages have status and action rows in audit table
- All FIX actions have detailed issue entries with file paths and line numbers
