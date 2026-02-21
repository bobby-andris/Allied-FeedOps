---
phase: 20-targeted-fixes-intelligence-application
plan: "02"
subsystem: pipeline
tags: [image-generation, gemini, lifestyle-images, prompt-engineering, finish-lighting, collection-dna]

# Dependency graph
requires:
  - phase: 20-targeted-fixes-intelligence-application
    provides: collection_descriptions.py with get_collection_description() and CSV data loader

provides:
  - FINISH_LIGHTING dict: lighting/rendering guidance for all 28 Allied Brass finishes
  - CATEGORY_SCENE dict: scene descriptions for 30 major product categories
  - _build_enhanced_image_prompt(): three-dimensional image intelligence function
  - Enhanced generate_lifestyle_images_for_sku() using new prompt builder

affects:
  - lifestyle image generation quality
  - Google Shopping visual ranking (GOOG-05)
  - product fidelity in AI-generated images

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-dimensional image intelligence: category scene + finish lighting + collection design DNA"
    - "PRODUCT FIDELITY as first non-negotiable section in image prompts"
    - "Graceful fallback when collection/finish/category data is missing"

key-files:
  created: []
  modified:
    - src/feedops/pipeline/lifestyle_images.py

key-decisions:
  - "PRODUCT FIDELITY section is first and most prominent in all image prompts — product accuracy is non-negotiable"
  - "FINISH_LIGHTING dict covers all 28 finishes with specific lighting/material rendering guidance"
  - "CATEGORY_SCENE dict covers 30 categories with appropriate scene descriptions"
  - "Collection design DNA wired via get_collection_description() from existing collection_descriptions.py loader"
  - "Graceful fallback: prompt still generated if collection/finish/category data is missing"

patterns-established:
  - "Enhanced prompt structure: PRODUCT FIDELITY → PRODUCT VISUAL INVENTORY → SCENE ENVIRONMENT → USAGE VALIDATION → TECHNICAL SPECIFICATIONS"
  - "Import from collection_descriptions.py for collection DNA (not inline/hardcoded)"

requirements-completed: [GOOG-05]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 20 Plan 02: Image Intelligence Wiring Summary

**Three-dimensional lifestyle image intelligence (finish lighting + category scene + collection design DNA) wired into Gemini Imagen prompt with PRODUCT FIDELITY as non-negotiable first section**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T10:51:52Z
- **Completed:** 2026-02-21T10:54:17Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `FINISH_LIGHTING` dict with specific lighting and material rendering guidance for all 28 Allied Brass finishes (Oil Rubbed Bronze → warm directional amber, Polished Chrome → bright diffuse crisp reflections, Matte Black → even studio minimal reflections, etc.)
- Added `CATEGORY_SCENE` dict with scene descriptions for 30 major product categories (towel bars, grab bars, robe hooks, toilet paper holders, paper towel holders, garment rods, soap dispensers, corner shelves, glass shelves, etc.)
- Added `_build_enhanced_image_prompt()` function that assembles the three-dimensional prompt with PRODUCT FIDELITY as the first and most prominent section per user decision
- Wired collection design DNA from `collection_descriptions.py` (existing loader) into the prompt via `get_collection_description()` and `sanitize_collection_description()`
- Updated `generate_lifestyle_images_for_sku()` to use the new enhanced prompt builder instead of the generic `build_prompt()` method
- Implements GOOG-05 completely

## Task Commits

1. **Task 1: Add finish lighting and category scene lookup data** - `c590bcf9` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/feedops/pipeline/lifestyle_images.py` - Added FINISH_LIGHTING (28 entries), CATEGORY_SCENE (30 entries), _build_enhanced_image_prompt(), import from collection_descriptions.py, wired into generate_lifestyle_images_for_sku()

## Decisions Made
- PRODUCT FIDELITY is the first section in the prompt — "Never compromise the ability to focus on the product" per user decision in CONTEXT.md
- Used graceful fallback for missing collection/finish/category data so generation never fails due to lookup misses
- Collection name extracted from `product_catalog.collection` or `product_catalog.collection_name` fields (whichever exists)
- Product type derived from category field (lowercased) for natural language in prompt

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Image generation prompt now carries full three-dimensional intelligence
- GOOG-05 is complete
- Next: Plans 03+ (FIX-01 prompt parity, FIX-02 feature flags, MODEL-03 accuracy guardrail, GOOG-04 Shopping intelligence)

## Self-Check: PASSED

- lifestyle_images.py: FOUND
- 20-02-SUMMARY.md: FOUND
- Commit c590bcf9: FOUND

---
*Phase: 20-targeted-fixes-intelligence-application*
*Completed: 2026-02-21*
