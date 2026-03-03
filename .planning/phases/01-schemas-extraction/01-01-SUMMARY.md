---
phase: 01-schemas-extraction
plan: 01
subsystem: api
tags: [pydantic, fastapi, refactoring, telemetry, schemas]

# Dependency graph
requires: []
provides:
  - "src/feedops/api/schemas.py — 17 Pydantic models + 4 schema helpers, importable without main.py"
  - "src/feedops/api/telemetry.py — run_async_in_thread + 4 telemetry helpers, importable without main.py"
affects:
  - "02-persistence-extraction — imports from schemas.py for job/content models"
  - "Any module importing from feedops.api.main for schemas or telemetry"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module extraction: move cohesive code chunks to purpose-built modules with zero circular imports"
    - "Named re-imports: main.py imports from schemas/telemetry, making names available in both namespaces"

key-files:
  created:
    - src/feedops/api/schemas.py
    - src/feedops/api/telemetry.py
    - tests/api/test_schemas_smoke.py
    - tests/api/test_telemetry_smoke.py
  modified:
    - src/feedops/api/main.py
    - tests/api/test_regenerate_response_contract.py
    - tests/api/test_main_master_sku_alias_runtime.py

key-decisions:
  - "Pure move: zero changes to function signatures, parameters, return types, or defaults"
  - "No re-exports from main.py: imports make symbols accessible in main's namespace as a side effect (not explicit re-export)"
  - "ScoreIntent models (ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse) moved from end-of-file location (line 3662) to schemas.py alongside the other 14 models"

patterns-established:
  - "Extraction pattern: copy code to new module → verify imports → remove from main.py → run tests"
  - "Test monkeypatch updates: when extracting code, update monkeypatches to target the new module's namespace"

requirements-completed:
  - DECOMP-01
  - DECOMP-04

# Metrics
duration: 6min
completed: 2026-03-03
---

# Phase 01 Plan 01: Schemas Extraction Summary

**Extracted 17 Pydantic models + 9 helper functions from main.py into two zero-dependency modules: schemas.py and telemetry.py**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-03T05:52:27Z
- **Completed:** 2026-03-03T05:58:08Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Created `schemas.py` with all 17 Pydantic request/response models and 4 schema helpers — importable standalone without main.py
- Created `telemetry.py` with `run_async_in_thread` and 4 telemetry helpers — importable standalone without main.py
- Updated main.py to import from both new modules; `python -c "import feedops.api.main"` exits 0
- Added 10 smoke tests (5 per module) and updated 2 existing test files
- All 97 API tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract schemas.py from main.py** - `9324413c` (refactor)
2. **Task 2: Extract telemetry.py from main.py** - `4e55bef0` (refactor)

## Files Created/Modified

- `src/feedops/api/schemas.py` - 17 Pydantic models + 4 helpers (OptimizeRequest through ScoreIntentResponse)
- `src/feedops/api/telemetry.py` - run_async_in_thread + _emit_generation_summary + _telemetry_scope_for_content + _generate_with_metrics + _should_persist_finish_sentences
- `src/feedops/api/main.py` - Removed model/helper definitions, added imports from schemas.py and telemetry.py
- `tests/api/test_schemas_smoke.py` - 5 smoke tests for schemas.py standalone importability
- `tests/api/test_telemetry_smoke.py` - 5 smoke tests for telemetry.py standalone importability
- `tests/api/test_regenerate_response_contract.py` - Updated import from main to schemas
- `tests/api/test_main_master_sku_alias_runtime.py` - Fixed monkeypatch to target telemetry module

## Decisions Made

- Pure move: zero changes to function signatures, parameters, return types, or defaults
- No explicit re-exports from main.py — Python's import mechanism makes imported names accessible in main's namespace as a side effect, so external lazy imports from `feedops.api.main` still resolve (Plan 02 will clean these up)
- ScoreIntent models extracted from their end-of-file location alongside the other 14 models, keeping schemas.py as the single Pydantic model authority

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test monkeypatch targeting after telemetry extraction**

- **Found during:** Task 2 (Extract telemetry.py from main.py)
- **Issue:** `test_generation_summary_event_contract` used `monkeypatch.setattr(api_main, "log_event", ...)` but after extraction, `_emit_generation_summary` uses `log_event` from `feedops.api.telemetry`'s namespace, not `api_main`'s
- **Fix:** Changed monkeypatch to `monkeypatch.setattr(api_telemetry, "log_event", _fake_log_event)` where `api_telemetry = feedops.api.telemetry`
- **Files modified:** `tests/api/test_main_master_sku_alias_runtime.py`
- **Verification:** Test now passes; 97/97 tests green
- **Committed in:** `4e55bef0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug caused by module extraction)
**Impact on plan:** Necessary correctness fix. The monkeypatch update is a direct consequence of the extraction — the test was correct before, extraction changed the namespace, fix was required.

## Issues Encountered

None — plan executed cleanly. Both modules import standalone without main.py, no circular imports, all 97 tests pass.

## Next Phase Readiness

- `schemas.py` is ready for Phase 02 consumption — `persistence.py` and `job_management.py` can now import from `feedops.api.schemas`
- `telemetry.py` is ready for Plan 02 Task 2 — external callers (search_insights.py, gmc_sync.py, backfill.py) can be updated to import directly from `feedops.api.telemetry`
- No blockers

## Self-Check: PASSED

- FOUND: src/feedops/api/schemas.py
- FOUND: src/feedops/api/telemetry.py
- FOUND: tests/api/test_schemas_smoke.py
- FOUND: tests/api/test_telemetry_smoke.py
- FOUND: commit 9324413c (Task 1)
- FOUND: commit 4e55bef0 (Task 2)

---
*Phase: 01-schemas-extraction*
*Completed: 2026-03-03*
