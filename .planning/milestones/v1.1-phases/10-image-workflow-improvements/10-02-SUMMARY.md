---
phase: 10-image-workflow-improvements
plan: "02"
subsystem: ui
tags: [next.js, shadcn, modal, image-generation, python, cloud-run]

# Dependency graph
requires:
  - phase: 10-image-workflow-improvements
    plan: "01"
    provides: GET /api/images/variant-data with per-finish impression + coverage data
provides:
  - VariantSelectorModal component for finish selection before image generation
  - EmptyImageState with auto-select label and manual override via modal
  - selected_finish_code passed to Cloud Run /generate-images
  - Python GenerateImagesRequest.selected_finish_code field
  - generate_lifestyle_images_for_sku force_finish_code parameter
affects:
  - 10-03-coverage-view-tab

# Tech tracking
tech-stack:
  added: []
  patterns:
    - useEffect fetch on mount for non-blocking variant data load
    - Derived state pattern: auto = variants[0], manual overrides, computed activeFinishCode/Name
    - Optional spread pattern for conditional body field: ...(activeFinishCode ? { selected_finish_code: activeFinishCode } : {})
    - Post-generation state reset: clear manualFinishCode after success so next run uses auto

key-files:
  created:
    - dashboard/src/components/review/VariantSelectorModal.tsx
  modified:
    - dashboard/src/components/review/LifestyleImageReview.tsx
    - src/feedops/api/main.py
    - src/feedops/pipeline/lifestyle_images.py

key-decisions:
  - "VariantDataEntry interface exported from VariantSelectorModal (not duplicated in LifestyleImageReview) — single source of truth for the type"
  - "Post-generation reset of manualFinishCode/Name to null — one-time choice, next generation returns to auto-select"
  - "force_finish_code fallback to auto-selection when provided code not found in variant_index — graceful degradation"
  - "No duplicate VariantDataEntry type in LifestyleImageReview — import from VariantSelectorModal instead"

patterns-established:
  - "Import type from modal component rather than defining duplicate interface in parent"
  - "Derived active finish: manualFinishCode ?? autoSelectedFinish?.finish_code ?? null"

requirements-completed:
  - IMG-01
  - IMG-02
  - IMG-04

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 10 Plan 02: Variant Selector Modal Summary

**Finish selection UI for lifestyle image generation: auto-select badge showing highest-impressions finish, modal for manual override, and selected_finish_code wired through to Cloud Run and Python pipeline**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T00:39:17Z
- **Completed:** 2026-02-19T00:43:24Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created `VariantSelectorModal.tsx` — shadcn Dialog + Select modal showing each finish with impression count and "has image" indicator
- Updated `EmptyImageState` in `LifestyleImageReview.tsx`:
  - Fetches `/api/images/variant-data` on mount (non-blocking)
  - Shows `"Highest impressions: [Finish]"` badge when using auto-select
  - Shows `"Manual: [Finish]"` badge after user picks via modal
  - "Change" button opens modal; manual choice resets after successful generation
  - Passes `selected_finish_code` in Cloud Run POST body
- Updated `src/feedops/api/main.py` — `GenerateImagesRequest` now has `selected_finish_code: str | None`
- Updated `src/feedops/pipeline/lifestyle_images.py` — `generate_lifestyle_images_for_sku` accepts `force_finish_code: str | None = None`; when set, looks up finish in `variant_index` and skips auto-selection; falls back gracefully if code not found

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VariantSelectorModal component** - `fc8e4f45` (feat)
2. **Task 2: Update EmptyImageState with selector UI and generate integration** - `819c33ad` (feat)
3. **Task 3: Update Python Cloud Run to accept and honor selected_finish_code** - `ec0c43f0` (feat)

## Files Created/Modified

- `dashboard/src/components/review/VariantSelectorModal.tsx` — New modal component for finish selection (exports `VariantDataEntry` interface and `VariantSelectorModal`)
- `dashboard/src/components/review/LifestyleImageReview.tsx` — Updated `EmptyImageState` with variant fetch, selection label, modal trigger, and `selected_finish_code` in generate call
- `src/feedops/api/main.py` — Added `selected_finish_code: str | None` to `GenerateImagesRequest`; passes as `force_finish_code` to pipeline function
- `src/feedops/pipeline/lifestyle_images.py` — Added `force_finish_code: str | None = None` to `generate_lifestyle_images_for_sku`; Step 2 honors forced finish with graceful fallback

## Decisions Made

- `VariantDataEntry` exported from `VariantSelectorModal.tsx` and imported into `LifestyleImageReview.tsx` — no type duplication
- After successful generation, `manualFinishCode` and `manualFinishName` reset to null — one-time choice, next run uses auto-select again
- `force_finish_code` gracefully falls back to auto-selection if the provided finish_code is not found in `variant_index`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 10-02 complete. Frontend and Python pipeline both support finish selection.
- Plan 10-03 can now build the coverage view tab using the same `/api/images/variant-data` endpoint.

## Self-Check

Checking created files and commits:

- [x] `dashboard/src/components/review/VariantSelectorModal.tsx` — created
- [x] `dashboard/src/components/review/LifestyleImageReview.tsx` — modified
- [x] `src/feedops/api/main.py` — modified
- [x] `src/feedops/pipeline/lifestyle_images.py` — modified
- [x] Commit `fc8e4f45` — feat(10-02): create VariantSelectorModal component
- [x] Commit `819c33ad` — feat(10-02): update EmptyImageState with variant selector UI
- [x] Commit `ec0c43f0` — feat(10-02): add selected_finish_code support to Python Cloud Run pipeline

## Self-Check: PASSED

---
*Phase: 10-image-workflow-improvements*
*Completed: 2026-02-19*
