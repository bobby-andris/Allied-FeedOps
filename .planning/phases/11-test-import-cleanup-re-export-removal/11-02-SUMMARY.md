---
phase: 11-test-import-cleanup-re-export-removal
plan: "02"
subsystem: pipeline
tags: [dead-code, refactor, generator, executor, imports]

# Dependency graph
requires:
  - phase: 11-01
    provides: re-export block removed from main.py; test imports migrated to canonical locations
provides:
  - generator.py with zero duplicate functions vs executor.py
  - test_prompt_sanitization_contract.py importing from feedops.generation.executor (canonical)
affects: [phase-12, executor, generator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "executor.py is the single canonical location for _platform_reasoning_effort and _platform_completion_cap"
    - "generator.py delegates all per-platform execution utilities to executor.py"

key-files:
  created: []
  modified:
    - src/feedops/pipeline/generator.py
    - tests/test_prompt_sanitization_contract.py

key-decisions:
  - "DEAD-04: executor.py is the canonical location for _platform_reasoning_effort and _platform_completion_cap — generator.py no longer re-defines them"
  - "import os removed from generator.py after deletion rendered it orphaned"
  - "Pre-existing unused importlib.util import in test file cleaned up via ruff auto-fix (scope: ruff was already run on the file)"

patterns-established:
  - "All per-platform generation helper functions live in executor.py — do not add them to generator.py"

requirements-completed: [DEAD-04]

# Metrics
duration: 5min
completed: 2026-03-04
---

# Phase 11 Plan 02: Test-Import Cleanup and Re-export Removal Summary

**Deleted 2 duplicate helper functions from generator.py and updated test_prompt_sanitization_contract.py to import from canonical executor.py, completing DEAD-04**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-04T08:10:00Z
- **Completed:** 2026-03-04T08:15:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Removed `_platform_reasoning_effort` and `_platform_completion_cap` from generator.py (lines 75–119, ~46 lines deleted)
- Removed orphaned `import os` from generator.py (no longer needed after helper deletion)
- Updated test_prompt_sanitization_contract.py to import both helpers from `feedops.generation.executor`
- `generate_per_platform` continues to be imported from `feedops.pipeline.generator` (correct — canonical location)
- All 790 tests pass; ruff clean on both modified files

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove duplicate functions from generator.py and update test import (DEAD-04)** - `5641f8f2` (refactor)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/feedops/pipeline/generator.py` — Removed `_platform_reasoning_effort`, `_platform_completion_cap`, and orphaned `import os`
- `tests/test_prompt_sanitization_contract.py` — Import path updated from `feedops.pipeline.generator` to `feedops.generation.executor` for the two helpers; `generate_per_platform` import split to its own `from feedops.pipeline.generator import` line

## Decisions Made
- executor.py is the single canonical source of truth for per-platform generation helpers — confirmed by this cleanup
- import os removal was safe: only usage was inside the two deleted functions
- Pre-existing `importlib.util` unused import in test file cleaned up as part of ruff pass (scope: file was already being modified)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Removed orphaned `import os` from generator.py**
- **Found during:** Task 1 (after deleting the two functions)
- **Issue:** `import os` became unused after deleting `_platform_completion_cap` which was its only consumer
- **Fix:** Removed `import os` from imports block
- **Files modified:** src/feedops/pipeline/generator.py
- **Verification:** ruff check passes; no other os.* usage in file
- **Committed in:** 5641f8f2 (Task 1 commit)

**2. [Rule 2 - Pre-existing lint] Removed unused `importlib.util` from test file via ruff**
- **Found during:** Task 1 (ruff check on test file)
- **Issue:** Pre-existing unused import, flagged by ruff when checking the modified file
- **Fix:** Applied ruff --fix to remove it
- **Files modified:** tests/test_prompt_sanitization_contract.py
- **Verification:** ruff clean; test still passes
- **Committed in:** 5641f8f2 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both trivial cleanup, same commit as planned changes)
**Impact on plan:** No scope creep — both fixes are correctness/housekeeping items found while executing the planned task.

## Issues Encountered
- None — `test_cli.py::test_optimize_pipeline_integration` showed one intermittent network-related failure during full suite run (Supabase `timeout` parameter deprecation warning) — re-run confirmed it passes; pre-existing flakiness, not caused by our changes.

## Next Phase Readiness
- DEAD-04 complete — generator.py and executor.py have zero duplicate functions
- Phase 11 fully complete (both plans done): DEAD-02, DEAD-03, DEAD-04 all resolved
- Ready for Phase 12 (bulk performance backfill / data infrastructure)

## Self-Check: PASSED
- SUMMARY.md exists at `.planning/phases/11-test-import-cleanup-re-export-removal/11-02-SUMMARY.md`
- Commit 5641f8f2 exists in git log

---
*Phase: 11-test-import-cleanup-re-export-removal*
*Completed: 2026-03-04*
