---
phase: 10-image-workflow-improvements
plan: "01"
subsystem: api
tags: [supabase, next.js, search-queries, variant-lifestyle-images, variant-index]

# Dependency graph
requires:
  - phase: 09-sku-review-revamp
    provides: lifestyle image approval/selection workflow context
provides:
  - GET /api/images/variant-data returning per-finish impression totals and lifestyle image coverage
  - VariantDataEntry and VariantDataResponse TypeScript interfaces
affects:
  - 10-02-variant-selector-modal
  - 10-03-coverage-view-tab

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Three-table merge pattern: variant_index (source of truth) + search_queries (aggregated JS-side) + variant_lifestyle_images (most-recent-per-finish)
    - Server route using createClient from @/lib/supabase/server

key-files:
  created:
    - dashboard/src/app/api/images/variant-data/route.ts
  modified: []

key-decisions:
  - "JS-side aggregation for search_queries impression/click totals (Supabase client does not support GROUP BY directly)"
  - "variant_index as source of truth for finish list — ensures finishes with no search data still appear in results"
  - "Most-recent-per-finish image using ordered query + first-seen dedup in JS (avoids subquery complexity)"
  - "thumbnail_url preferred over image_url for lifestyle_image_url field (falls back to image_url if null)"

patterns-established:
  - "Three-way merge pattern: fetch all three tables independently, merge in JS, sort client-side"
  - "Finish deduplication using Map keyed by finish_code"

requirements-completed:
  - IMG-01
  - IMG-02
  - IMG-03

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 10 Plan 01: Variant Data API Summary

**GET /api/images/variant-data endpoint merging variant_index + search_queries + variant_lifestyle_images into per-finish impression and coverage data sorted highest-impressions first**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T00:31:03Z
- **Completed:** 2026-02-19T00:37:09Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `GET /api/images/variant-data?master_sku=X` endpoint
- Merges three Supabase tables: `variant_index` (finish list), `search_queries` (impression/click aggregation), `variant_lifestyle_images` (image coverage)
- Returns `{ variants: VariantDataEntry[] }` sorted by `total_impressions` descending — highest-impression finish first
- Returns 400 if `master_sku` missing, 500 on any DB error
- Build passes with zero TypeScript errors; route correctly listed as `ƒ /api/images/variant-data`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create GET /api/images/variant-data route** - `4669b1bf` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `dashboard/src/app/api/images/variant-data/route.ts` - GET endpoint returning per-finish impression + image coverage data for a master SKU

## Decisions Made
- JS-side aggregation for `search_queries` impression/click totals — Supabase client does not support GROUP BY directly, so raw rows are fetched and summed in a Map keyed by finish_code
- `variant_index` used as the canonical finish list so finishes with zero search impressions still appear (not silently dropped)
- Most-recent lifestyle image per finish determined by ordering the query `desc` and taking first-seen in JS — avoids subquery complexity
- `thumbnail_url` preferred over `image_url` in the `lifestyle_image_url` response field, falling back to `image_url` if thumbnail is null

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 10-01 complete. `GET /api/images/variant-data` is ready for consumption by:
  - Plan 10-02: Variant selector modal (uses impression data to auto-select highest-impressions finish)
  - Plan 10-03: Coverage view tab (uses `has_lifestyle_image` to show which finishes are missing images)
- No blockers.

## Self-Check

Checking created files and commits:

- [x] `dashboard/src/app/api/images/variant-data/route.ts` — created
- [x] Commit `4669b1bf` — feat(10-01): create GET /api/images/variant-data route

## Self-Check: PASSED

---
*Phase: 10-image-workflow-improvements*
*Completed: 2026-02-19*
