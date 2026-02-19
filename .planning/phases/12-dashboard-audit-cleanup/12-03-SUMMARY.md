---
phase: 12-dashboard-audit-cleanup
plan: "03"
subsystem: ui
tags: [ux, competitors, empty-states, agent-browser, verification]
dependency_graph:
  requires:
    - phase: 12-dashboard-audit-cleanup
      provides: 12-01 audit + 12-02 fixes for broken/stale pages
  provides:
    - simplified-competitors-page with SERP-only layout and contextual empty state
    - agent-browser walkthrough confirming all 11 pages verified on live Vercel URL
    - final verified status table in 12-AUDIT.md
  affects: [dashboard/src/app/(dashboard)/competitors/page.tsx]
tech_stack:
  added: []
  patterns: [usage-guidance-banner, contextual-empty-state-inline, agent-browser-verification]
key_files:
  created:
    - .planning/phases/12-dashboard-audit-cleanup/12-03-SUMMARY.md
  modified:
    - dashboard/src/app/(dashboard)/competitors/page.tsx
    - .planning/phases/12-dashboard-audit-cleanup/12-AUDIT.md
key_decisions:
  - "Competitors page SIMPLIFIED (not removed) — SERP tab retained, marketplace tab removed; functional scraping capability preserved for future use"
  - "Usage guidance banner added pointing users to Search Insights for SKU-level keyword data — clarifies when to use each tool"
  - "No shared EmptyState component created — only 1 DEAD-END page existed (threshold is 3+), applied inline"
  - "agent-browser walkthrough run before stopping at checkpoint — VER-01 requirement fulfilled within task 1 automated execution"
patterns-established:
  - "Usage guidance banner pattern: amber-50/amber-200 border card explaining when a page is useful vs. when to use another tool"
requirements-completed: [DASH-01, DASH-03, VER-01]
duration: 8min
completed: "2026-02-19"
---

# Phase 12 Plan 03: Empty States and Verification Summary

**Simplified /competitors to SERP-only with contextual empty state and usage guidance banner; agent-browser verified all 11 dashboard pages on live Vercel URL.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-19T05:05:43Z
- **Completed:** 2026-02-19T05:13:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Simplified /competitors page — removed Marketplace tab (Amazon/Wayfair/Home Depot scraping), kept SERP analysis, added usage guidance banner linking to Search Insights
- Added contextual empty state for zero-data SERP condition explaining why data is missing and what to do (click Scrape Google SERP, takes 2-5 minutes)
- Completed agent-browser walkthrough of all 11 live dashboard pages — confirmed no blank/broken states remain
- Updated 12-AUDIT.md with final verified status for all pages

## Empty States Added

| Page | Empty State Title | Description | Action |
|------|-------------------|-------------|--------|
| Competitors (no SERP data) | "No SERP data for this category yet" | Explains scraping takes 2-5 minutes, uses Apify account | "Scrape Google SERP" button (in header) |

Note: Only 1 DEAD-END page existed in the audit (Competitors). The threshold for a shared EmptyState component is 3+ pages — no shared component was created; empty state applied inline.

## Usage Guidance Banner

Added an amber information banner to /competitors explaining the distinction between Competitor Intelligence (category-level SERP, who ranks) vs. Search Insights (SKU-level Google Ads data, what customers search). The banner includes a direct link to /search-insights.

## SIMPLIFY Changes to /competitors

| Before | After |
|--------|-------|
| Two tabs: "SERP Analysis" + "Marketplace Details" | Single SERP view (no tabs) |
| "All Sources" dropdown | Removed (only Google SERP remains) |
| Scrape buttons: Google, Amazon, Wayfair, Home Depot | Single "Scrape Google SERP" button |
| No usage context | Amber guidance banner with link to Search Insights |
| Generic empty state | Contextual empty state with category name and action |

## agent-browser Walkthrough Results (VER-01)

**All 11 pages visited on live Vercel URL (allied-feed-ops.vercel.app)**

| # | Page | Route | Result |
|---|------|-------|--------|
| 1 | Overview | / | PASS — Stats cards render (577 SKUs, 575 Pending), quality distribution chart, quick-action links work |
| 2 | Generate | /generate | PASS — Multi-step wizard loads, tier distribution description visible, Past Jobs tab present |
| 3 | Review Queue | /review | PASS — 97 SKUs listed, platform filter stats (Google: 59/1/0/37, Bing: 93/3/0/1, Shopify: 89/1/0/7) |
| 4 | Review [SKU] | /review/1016 | PASS — SKU detail view loads, Back button visible, content displayed |
| 5 | Competitors | /competitors | PASS — NEW: Scrape Google SERP button, usage guidance banner, no Marketplace tab, SERP data showing (10 results across 9 domains for "towel bars") |
| 6 | Batches | /batches | PASS — Batch table renders (6 total, 5 published), Create Batch button |
| 7 | Performance | /performance | PASS — Sortable table with delta badges, 36/37 SKUs with snapshot data, alert about snapshot-based comparison |
| 8 | Search Insights | /search-insights | PASS — Page loads, instruction "Enter a Master SKU above..." shown, Sync Data button present |
| 9 | Backfill Monitoring | /backfill | PASS — "No backfill jobs found" empty state, Data Freshness Heatmap and API Health sections visible |
| 10 | Settings | /settings | PASS — No misleading switches, Danger Zone has text guidance, Supabase URL shows env var value |
| 11 | Post-Publish Monitoring | /monitoring | PASS — No alert() dialogs, two snapshot buttons (Search/Performance separate), performance delta data showing |

**Result: All 11 pages PASS — no blank states, no broken states, no dead ends.**

## Task Commits

1. **Task 1: Simplify competitors page** - `5bb5196a` (feat)

## Files Created/Modified

- `dashboard/src/app/(dashboard)/competitors/page.tsx` — SERP-only layout, marketplace tab removed, contextual empty state, usage guidance banner
- `.planning/phases/12-dashboard-audit-cleanup/12-AUDIT.md` — Updated with final verified status column for all 11 pages

## Decisions Made

- **Simplified, not removed**: Competitors page still has functional Apify scraping. The SERP analysis data and pattern extraction is useful for category research. Removing it outright would lose that capability. Simplification reduces confusion without destroying utility.
- **Inline empty state**: Only 1 DEAD-END page — no shared EmptyState component created (threshold is 3 or more).
- **Guidance banner style**: amber-50/amber-200 border to distinguish it from error (red) or success (green) — informational, not alarming.

## Deviations from Plan

None — plan executed exactly as written. One DEAD-END page addressed (Competitors simplified). No REMOVE action taken. Build passes, deployed, agent-browser walkthrough completed.

## Phase 12 Complete — All Plans Resolved

| Plan | Name | Status |
|------|------|--------|
| 12-01 | Audit all pages | COMPLETE — 11 pages documented |
| 12-02 | Fix BROKEN and STALE pages | COMPLETE — monitoring, settings, overview all fixed |
| 12-03 | Address DEAD-END pages, verify | COMPLETE — competitors simplified, all 11 pages live-verified |

## Self-Check: PASSED

- `dashboard/src/app/(dashboard)/competitors/page.tsx` exists and no longer contains Marketplace tab
- Commit `5bb5196a` in git log
- 12-AUDIT.md updated with "Final Status (Verified)" column
- Build passes (`npm run build` — 56 pages, 0 errors)
- Live Vercel URL confirms new competitors page (Scrape Google SERP button visible, no Marketplace tab)

---
*Phase: 12-dashboard-audit-cleanup*
*Completed: 2026-02-19*
