---
phase: 09-trivial-dead-code-removal
plan: 02
subsystem: pipeline
tags: [python, dead-code, feature-flag, generator, reporter, finish_injection]

# Dependency graph
requires:
  - phase: 09-01
    provides: "DEAD-01 through DEAD-04 removed; test imports updated, re-exports cleaned"
provides:
  - "FEEDOPS_VARIANT_AT_LLM_TIME feature flag block fully removed from codebase"
  - "generator.py shrunk by ~200 lines (851 -> 651)"
  - "reporter.py generate_variant_patch_preview uses finish_injection directly (no if/else branch)"
  - "finish_injection.py has no deprecation notices referencing the flag"
  - "2 dead-code tests removed from test_pipeline.py"
affects: [pipeline, testing, content-generation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dead flag removal: collapse if/else to direct else-body when flag was never enabled"

key-files:
  created: []
  modified:
    - src/feedops/pipeline/generator.py
    - src/feedops/pipeline/reporter.py
    - src/feedops/pipeline/finish_injection.py
    - tests/test_pipeline.py

key-decisions:
  - "Removed orphaned logging and warnings imports from finish_injection.py (auto-fix: Rule 1 - orphaned by debug log removal)"

patterns-established:
  - "Single atomic commit for all files in a dead-code removal that spans multiple files"

requirements-completed: [DEAD-05]

# Metrics
duration: 15min
completed: 2026-03-04
---

# Phase 09 Plan 02: Trivial Dead Code Removal — FEEDOPS_VARIANT_AT_LLM_TIME Summary

**Deleted 5-function FEEDOPS_VARIANT_AT_LLM_TIME variant-generation block from generator.py (851 -> 651 lines), collapsed reporter.py conditional to direct finish_injection path, and stripped deprecation notices from finish_injection.py and test_pipeline.py**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-04T04:50:00Z
- **Completed:** 2026-03-04T05:05:00Z
- **Tasks:** 2 (committed as 1 atomic commit)
- **Files modified:** 4

## Accomplishments
- Removed 5 dead functions from generator.py: `_variant_generation_enabled`, `build_variant_prompt`, `generate_variant_candidate`, `generate_variant_candidates_batch`, and the section header comment block
- Removed `FINISH_CONTEXT_TEMPLATE` and `VARIANT_USER_PROMPT_TEMPLATE` orphaned imports from generator.py
- Deleted `_variant_at_llm_time_enabled()` from reporter.py
- Collapsed the `if use_llm_variant / else` branch in `generate_variant_patch_preview()` to the direct finish_injection path
- Removed `variant_candidate: Candidate | None = None` parameter from `generate_variant_patch_preview()` signature
- Stripped DEPRECATION NOTICE and DEPRECATED FUNCTIONS list from finish_injection.py module docstring
- Removed `.. deprecated::` directives from `generate_finish_snippet()` and `generate_variant_description()` docstrings
- Removed `logging.debug()` deprecation warning call from `generate_variant_description()`
- Removed orphaned `logging` and `warnings` imports from finish_injection.py
- Deleted 2 dead tests (`test_build_variant_prompt_uses_canonical_prompt_loader`, `test_build_variant_prompt_includes_gold_examples_when_available`) and removed `build_variant_prompt` import from test_pipeline.py
- Zero references to FEEDOPS_VARIANT_AT_LLM_TIME remain anywhere in src/ or tests/
- 785 tests pass, ruff clean on all modified files

## Task Commits

1. **Tasks 1 & 2: FEEDOPS_VARIANT_AT_LLM_TIME removal (all files, atomic)** - `62346b10` (refactor)

## Files Created/Modified
- `src/feedops/pipeline/generator.py` - Removed 5 variant-generation functions + 2 orphaned imports; 851 -> 651 lines
- `src/feedops/pipeline/reporter.py` - Deleted _variant_at_llm_time_enabled(), removed variant_candidate param, collapsed if/else to direct path
- `src/feedops/pipeline/finish_injection.py` - Removed deprecation notices from module docstring and 2 function docstrings, removed debug log, removed orphaned logging/warnings imports
- `tests/test_pipeline.py` - Removed build_variant_prompt import and 2 dead test functions

## Decisions Made
- Removed orphaned `logging` and `warnings` imports discovered by ruff after removing the debug log call — these were directly caused by our changes (Rule 1 auto-fix)
- Single atomic commit for all 4 files per plan's explicit instruction

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed orphaned logging and warnings imports from finish_injection.py**
- **Found during:** Task 2 (ruff check after all changes)
- **Issue:** Removing `logging.debug()` call left `logging` and `warnings` as unused imports; ruff flagged both as F401
- **Fix:** Removed both import lines from finish_injection.py
- **Files modified:** src/feedops/pipeline/finish_injection.py
- **Verification:** ruff check passes on all modified files
- **Committed in:** 62346b10 (part of atomic task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - orphaned imports)
**Impact on plan:** Necessary correctness fix; no scope creep.

## Issues Encountered
- None beyond the orphaned imports found by ruff.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DEAD-05 complete. Phase 09 (both plans) is fully done.
- generator.py is now ~53% smaller (fewer lines than 936 due to earlier decomposition; the variant block removed was lines 655-851 of the 851-line file).
- Codebase is ready for next milestone work.

---
*Phase: 09-trivial-dead-code-removal*
*Completed: 2026-03-04*
