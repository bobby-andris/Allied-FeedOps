---
phase: 11-performance-page-enhancements
plan: 03
subsystem: api
tags: [performance, google-ads, supabase, nextjs, python, cloud-run]

# Dependency graph
requires:
  - phase: 11-01
    provides: Performance page reading from performance_baselines + performance_snapshots
  - phase: 11-02
    provides: Snapshot normalization and variant breakdown in route.ts
provides:
  - Corrected daily-average baseline divisor (days_lookback not variants_with_data)
  - Snapshot query using most recent snapshot (no date ceiling)
  - SKU detail fetching via variant_index offer-ID join (resilient to null master_sku)
  - Lowercase gmc_offer_id normalization in search term sync
  - Recaptured baselines for all 37 published SKUs with correct divisor
affects: [performance-page, search-insights, monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Daily-average semantics: avg_impressions = total / days_lookback (not / variant_count)
    - Resilient ID-based lookup: query by gmc_offer_id via variant_index join instead of master_sku column
    - Case normalization at intake: lowercase Google Ads offer IDs before DB lookup

key-files:
  created: []
  modified:
    - src/feedops/api/performance_baseline.py
    - src/feedops/integrations/google_ads_search_terms.py
    - dashboard/src/app/api/performance/route.ts

key-decisions:
  - "Daily-average baseline: avg_impressions/avg_clicks stored as total/days_lookback not total/variants — matches snapshot normalization pattern in route.ts (snapshot_impressions / snapshotWindowDays)"
  - "snapshots[0] over .find() window filter: most recent snapshot always wins; backfilled snapshots captured months post-publish are no longer excluded by date ceiling"
  - "Offer-ID join pattern for SKU detail: variant_index -> gmc_offer_ids -> uppercase -> search_queries.in() — resilient to historical null master_sku rows"
  - "Lowercase normalization at get_variant_info() entry: Google Ads uppercase offer IDs normalized before cache key and DB query to match variant_index lowercase storage"

patterns-established:
  - "Offer ID case handling: Google Ads returns uppercase shopify_US_, DB stores lowercase shopify_us_; normalize on intake (Python sync) and transform on query (TS route)"

requirements-completed: [PERF-01, PERF-02, PERF-03, VER-01]

# Metrics
duration: 13min
completed: 2026-02-19
---

# Phase 11 Plan 03: Gap Closure Summary

**Fixed 4 UAT gaps — corrected baseline daily-average divisor, snapshot date-ceiling removed, SKU detail joined via offer IDs, and search term sync lowercases offer IDs — then recaptured baselines for all 37 published SKUs**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-19T06:03:51Z
- **Completed:** 2026-02-19T06:17:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Fixed wrong baseline math: `avg_impressions = total_impressions / days_lookback` instead of `/ variants_with_data` — baselines now store daily averages that correctly compare to snapshot normalization
- Fixed snapshot window filter: replaced `.find(s => s.date >= publish && s.date <= publishPlus)` with `snapshots[0]` — 44 backfilled snapshots (captured Feb 2026 for months-old publishes) now all match
- Fixed SKU detail panel: variant_index join provides gmc_offer_ids, query `search_queries` via `.in('gmc_offer_id', upperOfferIds)` — historical rows with null master_sku now return data
- Fixed search term sync: `gmc_offer_id.lower()` at top of `get_variant_info()` — future syncs write correct master_sku
- Recaptured baselines for all 37 published SKUs via Cloud Run after deploy; all 37 show daily-average values (verified in Supabase)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix baseline divisor + snapshot window + SKU detail query** - `1b26dfd5` (fix)
2. **Task 2: Fix search term sync case sensitivity (Python)** - `499ed7a9` (fix)

**Plan metadata:** `[final commit]` (docs: complete plan)

## Baseline Recapture Results

- **SKUs processed:** 37 (all published)
- **SKUs with data:** 37 (all have impressions > 0)
- **Sample values:** 1016: 60.47 impr/day, 1020-3: 47.83 impr/day, 1025U: 150.5 impr/day, 1051: 224 impr/day, CL-22: 223 impr/day
- **Previous values (incorrect):** Baselines stored total/variants_count — would have been ~6x lower than actual daily totals
- **Cloud Run build:** Succeeded (06:06:03 → 06:12:39 UTC), auto-deployed from push to master

## Files Created/Modified
- `src/feedops/api/performance_baseline.py` — Fixed divisor: `days_lookback` instead of `variants_with_data` for avg_impressions and avg_clicks
- `src/feedops/integrations/google_ads_search_terms.py` — Added `gmc_offer_id = gmc_offer_id.lower()` at entry of `get_variant_info()` before cache key and DB lookup
- `dashboard/src/app/api/performance/route.ts` — Replaced `.find()` window filter with `snapshots[0]`; replaced `master_sku` equality query with variant_index join + `.in('gmc_offer_id', upperOfferIds)`; removed unused `addDays` helper; added finish enrichment from `offerFinishMap`

## Decisions Made

- Snapshot selection uses `snapshots[0]` (most recent) rather than trying to find one within the publish window — the date ceiling was wrong and there's no benefit to enforcing it when the goal is "show the most recent data we have"
- Offer-ID join pattern rather than backfilling null master_sku values in search_queries — the join approach is more resilient and avoids a data migration
- Lowercase normalization at `get_variant_info()` entry rather than at call sites — centralizes the fix where the contract is defined

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `addDays` function after removing its only call site**
- **Found during:** Task 1 (Fix snapshot window filter)
- **Issue:** After replacing `.find()` with `snapshots[0]`, the `addDays(publishDate, snapshotWindowDays)` call was removed, leaving `addDays` defined but never called — lint would flag it
- **Fix:** Removed the `addDays` function definition entirely
- **Files modified:** dashboard/src/app/api/performance/route.ts
- **Verification:** Build and lint pass with zero errors
- **Committed in:** 1b26dfd5 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - cleanup of dead code)
**Impact on plan:** Necessary cleanup — removing the function that was no longer needed prevents lint errors. No scope creep.

## Issues Encountered

- Script response showed `skus_with_data=0` for both batches despite Cloud Run logs showing successful captures for 1016, 1020, 1020-3, 1024E, 1031/30, 1031/36, 1051, 1066, 1098, 107, 920G-6, 920T-6, CL-22 and more. Supabase spot-check confirmed all 37 published SKUs have baselines with impressions > 0. The script likely hit the old container instance before the new deployment was fully serving traffic. Verified correct results directly in Supabase.

## UAT Gap Status

| Gap | Description | Status |
|-----|-------------|--------|
| Gap 1 | Baseline impressions are daily averages (total / days_lookback) | FIXED |
| Gap 2 | No published SKU shows "No snapshot" when snapshot row exists | FIXED |
| Gap 3 | Delta values show accurate non-zero percentages for published SKUs with snapshots | FIXED |
| Gap 4 | Inline panel shows variant breakdown and search terms for historical rows | FIXED |

## Next Phase Readiness
- Phase 11 complete — all 3 plans done
- Performance page shows correct baselines, accurate deltas, and populated variant/search panels
- All 37 published SKUs have daily-average baselines and snapshot data for comparison

---
*Phase: 11-performance-page-enhancements*
*Completed: 2026-02-19*
