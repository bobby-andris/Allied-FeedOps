---
phase: 12-shared-utils-extraction
plan: 01
subsystem: api
tags: [python, refactoring, dead-code, utils, imports]

# Dependency graph
requires:
  - phase: 11-test-import-cleanup-re-export-removal
    provides: update-then-delete pattern for symbol extraction
provides:
  - src/feedops/api/utils.py with _require_request_id and GenerationBudgetExceededError
  - Single canonical location for both shared API primitives
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [update-then-delete symbol extraction, shared utils module pattern]

key-files:
  created:
    - src/feedops/api/utils.py
  modified:
    - src/feedops/api/persistence.py
    - src/feedops/api/job_management.py
    - src/feedops/api/routes.py
    - src/feedops/pipeline/generator.py
    - tests/api/test_main_master_sku_alias_runtime.py
    - tests/api/test_job_management_smoke.py

key-decisions:
  - "No re-export from generator.py: generator.py imports GenerationBudgetExceededError from utils (linear import chain, not circular); gen.GenerationBudgetExceededError works via module attribute access"
  - "job_management.py does not re-export _require_request_id: callers updated to import from utils directly"
  - "test_job_management_smoke.py updated: _require_request_id import moved to feedops.api.utils"
  - "test_main_master_sku_alias_runtime.py updated: both imports (_require_request_id, GenerationBudgetExceededError) now from feedops.api.utils"

patterns-established:
  - "Phase 11 update-then-delete pattern: all callers updated before old definitions removed"
  - "utils.py zero-dependency rule: no feedops.* imports in utils.py to prevent circular imports"

requirements-completed: [DEAD-06]

# Metrics
duration: 7min
completed: 2026-03-04
---

# Phase 12 Plan 01: Shared Utils Extraction Summary

**Duplicate _require_request_id eliminated from persistence.py and job_management.py; GenerationBudgetExceededError moved from generator.py — both now in single feedops/api/utils.py module (DEAD-06 complete)**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-04T08:15:33Z
- **Completed:** 2026-03-04T08:22:48Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Created `src/feedops/api/utils.py` with exactly 2 symbols: `_require_request_id` and `GenerationBudgetExceededError`
- Removed identical duplicate `_require_request_id` definitions from `persistence.py` (bottom of file, with duplication comment) and `job_management.py` (lines 72-77)
- Moved `GenerationBudgetExceededError` class from `generator.py` (pipeline layer) to `utils.py` (API layer) — import in generator.py re-exports it for callers; no circular import (utils.py has zero feedops.* imports)
- Updated all 6 import sites: routes.py, generator.py, 2 test files
- 790 tests pass; only pre-existing flaky test (unclosed sockets ResourceWarning in test_optimize_pipeline_integration) fails when run after 188 other tests, passes in isolation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create utils.py and update all import sites** - `0dda93e2` (feat)
2. **Task 2: Final validation** - no code changes, validation-only

**Plan metadata:** (created after state updates)

## Files Created/Modified

- `src/feedops/api/utils.py` - New shared primitives module: _require_request_id() and GenerationBudgetExceededError
- `src/feedops/api/persistence.py` - Added import from utils; removed local _require_request_id definition (lines 472-483, including duplication comment)
- `src/feedops/api/job_management.py` - Removed local _require_request_id definition (lines 72-77); no re-export needed (callers updated)
- `src/feedops/api/routes.py` - Removed _require_request_id from job_management import block; added from feedops.api.utils import; removed GenerationBudgetExceededError from generator import
- `src/feedops/pipeline/generator.py` - Removed GenerationBudgetExceededError class definition; added import from feedops.api.utils (re-exported for gen.GenerationBudgetExceededError access pattern)
- `tests/api/test_main_master_sku_alias_runtime.py` - Updated GenerationBudgetExceededError and _require_request_id imports to feedops.api.utils
- `tests/api/test_job_management_smoke.py` - Updated _require_request_id import to feedops.api.utils

## Decisions Made

- **generator.py circular import is safe:** feedops.pipeline.generator imports feedops.api.utils — this creates a linear chain (api.main → api.routes → pipeline.generator → api.utils), NOT a cycle. utils.py imports nothing from feedops.*. Confirmed with `python -c "import feedops.api.main"`.
- **No re-export in job_management.py:** Rather than keeping _require_request_id as a re-export in job_management.py, all callers (routes.py, test files) were updated to import from utils directly. Cleaner than phantom re-exports.
- **Pre-existing flaky tests documented:** test_optimize_pipeline_integration and test_optimize_parent_sku_reports_product_not_found fail only when run after other tests (unclosed socket ResourceWarning from async test teardown). Both pass in isolation. Not caused by this plan's changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_job_management_smoke.py import**
- **Found during:** Task 1 (running tests after extraction)
- **Issue:** test_job_management_smoke.py imported _require_request_id from feedops.api.job_management which no longer exports it after cleanup
- **Fix:** Updated test to import _require_request_id from feedops.api.utils directly
- **Files modified:** tests/api/test_job_management_smoke.py
- **Verification:** 4/4 smoke tests pass
- **Committed in:** 0dda93e2 (Task 1 commit)

**2. [Rule 1 - Bug] Removed unused import from job_management.py**
- **Found during:** Task 1 (ruff check)
- **Issue:** Added `from feedops.api.utils import _require_request_id` to job_management.py for potential re-export, but it was unused (no internal callers after local def removed)
- **Fix:** Removed the unused import; updated test_main_master_sku_alias_runtime.py to import _require_request_id from utils directly
- **Files modified:** src/feedops/api/job_management.py, tests/api/test_main_master_sku_alias_runtime.py
- **Verification:** ruff check passes on all modified files
- **Committed in:** 0dda93e2 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs discovered during verification)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- ruff flagged _require_request_id as unused in job_management.py after adding the import — resolved by removing the import entirely and updating the test that relied on the re-export
- Pre-existing flaky tests (ResourceWarning, order-dependent) confirmed not caused by this plan

## Next Phase Readiness

- Phase 12 complete — DEAD-06 satisfied
- utils.py establishes the shared API primitives module for future shared helpers
- All tests green (790 passing); pre-existing flakiness documented and out of scope

## Self-Check: PASSED

- src/feedops/api/utils.py: FOUND
- Commit 0dda93e2: FOUND

---
*Phase: 12-shared-utils-extraction*
*Completed: 2026-03-04*
