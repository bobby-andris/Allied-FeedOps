---
phase: 01-schemas-extraction
plan: 02
subsystem: api
tags: [python, fastapi, refactor, supabase, extraction, modularization]

requires:
  - phase: 01-schemas-extraction/01-01
    provides: schemas.py, telemetry.py, generation_telemetry.py extracted from main.py

provides:
  - persistence.py with 8 Supabase CRUD functions extracted from main.py
  - job_management.py with 9 job lifecycle helpers extracted from main.py
  - smoke tests for both new modules (4 tests each)
  - Zero lazy imports from main.py in the api/ directory

affects:
  - all future phases that modify main.py or api/ modules
  - Phase 2 (prompt extraction) which depends on clean module boundaries

tech-stack:
  added: []
  patterns:
    - "Layered extraction: persistence.py -> schemas.py, job_management.py -> schemas.py, no cross-imports between siblings"
    - "_require_request_id duplicated in persistence.py to avoid circular import — job_management.py is public home"
    - "Lazy imports eliminated from external callers (search_insights, gmc_sync, backfill) — all now use top-level imports from telemetry.py"

key-files:
  created:
    - src/feedops/api/persistence.py
    - src/feedops/api/job_management.py
    - tests/api/test_persistence_smoke.py
    - tests/api/test_job_management_smoke.py
  modified:
    - src/feedops/api/main.py
    - src/feedops/api/search_insights.py
    - src/feedops/api/gmc_sync.py
    - src/feedops/api/backfill.py

key-decisions:
  - "_require_request_id lives in job_management.py (public) and is duplicated in persistence.py (private copy) to avoid circular imports between sibling modules"
  - "All external callers (search_insights.py, gmc_sync.py, backfill.py) now import run_async_in_thread from feedops.api.telemetry at module level, eliminating all lazy imports from main.py"

patterns-established:
  - "Phase 1 extraction complete: main.py now delegates to schemas.py, telemetry.py, generation_telemetry.py, persistence.py, and job_management.py"
  - "Smoke tests verify importability without triggering application startup"

requirements-completed:
  - DECOMP-02
  - DECOMP-03

duration: 7min
completed: 2026-03-03
---

# Phase 1 Plan 02: Persistence and Job Management Extraction Summary

**8 Supabase CRUD functions moved to persistence.py and 9 job lifecycle helpers to job_management.py, eliminating all lazy imports from feedops.api.main in the api/ directory**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-03T06:01:58Z
- **Completed:** 2026-03-03T06:08:56Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Created `persistence.py` with 8 functions: `_lookup_generated_content_id`, `_load_generated_content_row`, `_assembled_prompt_hash`, `_enforce_write_time_finish_placeholder_contract`, `_persist_regeneration_result`, `_persist_generated_content_and_history`, `_persist_finish_prompt_lineage`, `_upsert_batch_job_sku_status`
- Created `job_management.py` with 9 functions: `_create_regeneration_job`, `_format_job_error`, `_require_request_id`, `_resolve_execution_request_id`, `_regeneration_idempotency_key`, `_hybrid_generation_idempotency_key`, `_find_active_regeneration_job`, `_find_active_hybrid_job`, `_normalize_regeneration_job_row`
- Updated 3 external callers (search_insights.py, gmc_sync.py, backfill.py) to import `run_async_in_thread` directly from telemetry.py
- All 704 existing tests pass, zero regressions

## Task Commits

1. **Task 1a: Extract persistence.py** - `fa156e63` (refactor)
2. **Task 1b: Extract job_management.py** - `d6e86cae` (refactor)
3. **Task 2: Update external callers** - `170b3c99` (refactor)

## Files Created/Modified

- `src/feedops/api/persistence.py` - 8 Supabase CRUD functions extracted from main.py
- `src/feedops/api/job_management.py` - 9 job lifecycle helpers extracted from main.py
- `src/feedops/api/main.py` - Replaced function bodies with imports from new modules; section comments added
- `src/feedops/api/search_insights.py` - Removed lazy import from main; added top-level import from telemetry
- `src/feedops/api/gmc_sync.py` - Removed lazy import from main; added top-level import from telemetry
- `src/feedops/api/backfill.py` - Removed 2 lazy imports from main; added single top-level import from telemetry
- `tests/api/test_persistence_smoke.py` - 4 smoke tests for persistence module (all pass)
- `tests/api/test_job_management_smoke.py` - 4 smoke tests for job_management module (all pass)

## Decisions Made

- `_require_request_id` lives in `job_management.py` (canonical home, per plan) but is also duplicated in `persistence.py` as a private copy to avoid a circular import between sibling modules — persistence functions call it internally and persistence.py cannot import from job_management.py per the layering rules
- Extraction was purely mechanical — zero changes to function signatures or behavior

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 extraction complete: `main.py` now imports from 5 clean modules (schemas, telemetry, generation_telemetry, persistence, job_management)
- Phase 2 (prompt builder extraction) can proceed — module boundaries are clean
- Full test suite green (704 passed, 1 skipped)

## Self-Check: PASSED

All files confirmed present:
- FOUND: src/feedops/api/persistence.py
- FOUND: src/feedops/api/job_management.py
- FOUND: tests/api/test_persistence_smoke.py
- FOUND: tests/api/test_job_management_smoke.py
- FOUND: .planning/phases/01-schemas-extraction/01-02-SUMMARY.md

All commits confirmed:
- FOUND: fa156e63 (persistence extraction)
- FOUND: d6e86cae (job_management extraction)
- FOUND: 170b3c99 (external callers update)

---
*Phase: 01-schemas-extraction*
*Completed: 2026-03-03*
