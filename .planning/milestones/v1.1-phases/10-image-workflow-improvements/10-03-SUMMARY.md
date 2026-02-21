---
phase: 10-image-workflow-improvements
plan: "03"
subsystem: ui
tags: [react, nextjs, typescript, lifestyle-images, coverage, variant-data]

# Dependency graph
requires:
  - phase: 10-image-workflow-improvements plan 10-01
    provides: /api/images/variant-data API route with finish/impression/image data
  - phase: 10-image-workflow-improvements plan 10-02
    provides: VariantSelectorModal, EmptyImageState finish selector UI, VariantDataEntry type

provides:
  - Coverage tab in LifestyleImageReview showing per-finish image status with thumbnail, date generated, and badge
  - CoverageSection component shared by Coverage tab and EmptyImageState collapsible toggle
  - gmc_offer_id → finish_code reverse lookup in variant-data API (fixes null finish_code impressions)
  - GenerateForNewFinish panel in VariantImageSection for SKUs that already have images

affects:
  - phase-11-performance-page (variant image coverage data accessible for all SKUs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Lift shared state to parent (variant data fetch at LifestyleImageReview level, passed as prop to EmptyImageState — eliminates double-fetch)
    - Shared function component (CoverageSection reused by Coverage tab and EmptyImageState toggle — single source of truth)
    - gmc_offer_id fallback for null finish_code rows in search_queries (reverse map via variant_index)

key-files:
  created: []
  modified:
    - dashboard/src/components/review/LifestyleImageReview.tsx
    - dashboard/src/components/review/VariantSelectorModal.tsx
    - dashboard/src/app/api/images/variant-data/route.ts

key-decisions:
  - "Coverage tab shows 'N missing' count badge — derived from variantData.filter(v => !v.has_lifestyle_image).length so badge is always current"
  - "gmc_offer_id reverse-map built from variant_index at query time — resolves search_queries rows where finish_code is null, ensuring all finishes get correct impression totals"
  - "GenerateForNewFinish added to VariantImageSection — users can generate for additional finishes without navigating away or needing to have zero images"

patterns-established:
  - "Lift-and-pass pattern: fetch variant data once at parent, pass down as prop — avoid duplicate fetches in child components"
  - "Shared internal components: CoverageSection used in both Coverage tab and EmptyImageState collapsible — single render path for consistency"

requirements-completed:
  - IMG-03
  - VER-01

# Metrics
duration: ~20min
completed: 2026-02-18
---

# Phase 10 Plan 03: Coverage Tab and End-to-End Browser Verification Summary

**Coverage tab with per-finish image status (thumbnail, date generated, badge) added to LifestyleImageReview; API impression aggregation fixed via gmc_offer_id reverse lookup; browser-verified end-to-end in live dashboard**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-02-18T19:48Z
- **Completed:** 2026-02-19T01:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Coverage tab (3rd tab) added to LifestyleImageReview showing all variants with finish name, thumbnail (if exists), "Generated MMM D, YYYY" date label, and has/no-image badge — sorted by impression count descending
- CoverageSection component shared by Coverage tab (images exist) and EmptyImageState collapsible "View coverage" toggle (zero images) — single implementation
- API fix: gmc_offer_id → finish_code reverse lookup via variant_index resolves search_queries rows where finish_code is null, so all finishes receive correct impression totals instead of being merged to zero
- GenerateForNewFinish collapsible panel added to VariantImageSection — users can generate lifestyle images for additional finishes even when images already exist for the current finish
- Browser verification confirmed all 5 Phase 10 success criteria in live dashboard: manual finish selection, auto-select highest-impressions variant, Coverage tab, correct finish passed to Cloud Run, end-to-end workflow

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Coverage tab to LifestyleImageReview** - `77058b2a` (feat)
2. **Task 2: Browser verification + two auto-fixes** - `b416e5b6` (fix)

## Files Created/Modified
- `dashboard/src/components/review/LifestyleImageReview.tsx` - Coverage tab, CoverageSection component, GenerateForNewFinish panel, lifted variant data fetch to parent
- `dashboard/src/components/review/VariantSelectorModal.tsx` - Extended VariantDataEntry interface with total_clicks, lifestyle_image_url, lifestyle_image_created_at
- `dashboard/src/app/api/images/variant-data/route.ts` - gmc_offer_id reverse lookup via variant_index to resolve null finish_code impression rows

## Decisions Made
- Coverage tab badge shows missing count (not total), because the actionable signal is how many finishes need attention
- gmc_offer_id reverse map built at query time from variant_index (not cached separately) — simple join pattern consistent with existing API patterns
- GenerateForNewFinish placed in VariantImageSection (not a new modal) — keeps the generate workflow in context of the finish currently displayed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Impression aggregation showing zero for many finishes**
- **Found during:** Task 2 (browser verification)
- **Issue:** search_queries rows have null finish_code when the row's gmc_offer_id is known; JS-side aggregation grouped by finish_code and dropped nulls, leaving many finishes at 0 impressions
- **Fix:** API route queries variant_index with gmc_offer_id to build a reverse map (gmc_offer_id → finish_code); rows with null finish_code are resolved via this map before returning to client
- **Files modified:** dashboard/src/app/api/images/variant-data/route.ts
- **Verification:** Coverage tab in live dashboard showed correct impression totals per finish after fix
- **Committed in:** b416e5b6

**2. [Rule 2 - Missing Critical] GenerateForNewFinish panel missing when images already exist**
- **Found during:** Task 2 (browser verification)
- **Issue:** Plan specified generate button only in EmptyImageState; once a finish had an image, there was no way to generate images for other finishes from the same page
- **Fix:** Added GenerateForNewFinish collapsible component to VariantImageSection, reusing the variant selector modal and auto-select label pattern from EmptyImageState
- **Files modified:** dashboard/src/components/review/LifestyleImageReview.tsx
- **Verification:** Collapsible "Generate images for another finish" panel visible and functional in live dashboard for SKUs with existing images
- **Committed in:** b416e5b6

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical functionality)
**Impact on plan:** Both fixes discovered during browser verification and required for the workflow to be genuinely usable. No scope creep — both directly address image workflow coverage.

## Issues Encountered
- None beyond the two auto-fixed deviations above

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 10 is complete. All 3 plans (10-01, 10-02, 10-03) executed and verified.
- Phase 11 (Performance Page) can proceed — lifestyle image coverage data is accessible for all SKUs via the Coverage tab, providing a natural entry point for per-SKU performance comparison views.
- No blockers.

---
*Phase: 10-image-workflow-improvements*
*Completed: 2026-02-18*
