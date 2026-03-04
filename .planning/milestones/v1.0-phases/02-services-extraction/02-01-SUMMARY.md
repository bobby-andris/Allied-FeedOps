---
phase: 02-services-extraction
plan: 01
subsystem: feedops-api
tags: [refactoring, services-extraction, intent-scoring, finish-processing, decomposition]
dependency_graph:
  requires:
    - 01-02-SUMMARY.md  # persistence.py, job_management.py, telemetry.py
  provides:
    - src/feedops/api/intent_scoring.py
    - src/feedops/api/finish_processing.py
  affects:
    - src/feedops/api/main.py
tech_stack:
  added: []
  patterns:
    - APIRouter extraction (FastAPI modular routing)
    - Deferred import indirection for testable monkeypatching (_get_generate_with_metrics)
    - Runtime daemon assertion test (stronger than source inspection)
key_files:
  created:
    - src/feedops/api/intent_scoring.py
    - src/feedops/api/finish_processing.py
    - tests/api/test_intent_scoring.py
    - tests/api/test_finish_processing.py
  modified:
    - src/feedops/api/main.py
    - tests/api/test_telemetry_smoke.py
    - tests/api/test_finish_prompt_source_contract.py
decisions:
  - "APIRouter pattern for intent_scoring: router = APIRouter() instead of @app.post to avoid circular import with main.py"
  - "_get_generate_with_metrics() indirection in finish_processing.py enables monkeypatching without module-level circular import"
  - "Contract test updated to patch at finish_processing module (not api_main) after extraction"
metrics:
  duration: "~10 min"
  completed: "2026-03-03"
  tasks_completed: 2
  files_created: 4
  files_modified: 3
---

# Phase 02 Plan 01: Services Extraction (Intent + Finish) Summary

**One-liner:** Extracted intent_scoring.py (APIRouter pattern, singleton, DECOMP-05) and finish_processing.py (3 finish functions, DECOMP-06) from main.py, with 13 new unit tests and a runtime daemon assertion for DECOMP-08.

## What Was Built

### intent_scoring.py (DECOMP-05)

New module `src/feedops/api/finish_processing.py` containing:

- `_intent_scorer` (module-level global) + `_intent_scorer_lock` (threading.Lock) — singleton state
- `_get_intent_scorer()` — double-check locking singleton initializer
- `_extract_query_intent_generation_diagnostics(generated)` — extracts intent diagnostics from generation output
- `api_score_intent(request)` — route handler, now decorated with `@router.post("/score-intent")`
- `router = APIRouter()` — registered in main.py via `app.include_router(intent_scoring_router)`

**Key design:** APIRouter avoids importing `app` from main.py (circular import prevention).

### finish_processing.py (DECOMP-06)

New module `src/feedops/api/finish_processing.py` containing:

- `_build_finish_sentences_user_prompt(...)` — builds finish-sentence LLM prompt
- `_validate_finish_sentences_payload(...)` — validates finish sentences against canonical list
- `_enforce_finish_sentence_parity(...)` — async end-to-end parity enforcement

All three functions moved verbatim with zero signature changes.

### Tests (DECOMP-11 partial)

- `tests/api/test_intent_scoring.py` — 6 unit tests: import isolation, singleton double-check, diagnostics extraction (with/without key), router route presence
- `tests/api/test_finish_processing.py` — 7 unit tests: import isolation, prompt content, payload validation (accept/reject/incomplete), parity kill-switch
- `tests/api/test_telemetry_smoke.py` — Added `test_run_async_in_thread_daemon_false_at_runtime` (DECOMP-08): runtime assertion stronger than source inspection

### main.py Reduction

- Removed ~150 lines of function definitions (intent scoring globals + 3 functions, finish processing 3 functions)
- Added import statements referencing the new modules
- Added `app.include_router(intent_scoring_router)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken contract test after extraction**

- **Found during:** Task 2
- **Issue:** `test_finish_prompt_source_contract.py` patched `api_main._generate_with_metrics` and `api_main.log_event`, but after extraction `_enforce_finish_sentence_parity` lives in `finish_processing.py` — patches at `api_main` no longer intercepted the function
- **Fix:** Added `_get_generate_with_metrics()` indirection in `finish_processing.py` to make the telemetry call patchable. Updated the contract test to patch at `feedops.api.finish_processing` instead of `feedops.api.main`
- **Files modified:** `src/feedops/api/finish_processing.py`, `tests/api/test_finish_prompt_source_contract.py`
- **Commits:** 353a2bca

## Results

- 718 tests passed, 1 skipped — zero regressions
- All must-have truths verified:
  - `intent_scoring.py` importable standalone (exit 0)
  - `finish_processing.py` importable standalone (exit 0)
  - Singleton initializes once (double-check locking pattern preserved + tested)
  - `/score-intent` endpoint responds via APIRouter registration
  - `run_async_in_thread` daemon=False assertion at runtime (DECOMP-08)
  - Full test suite passes with zero regressions

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits verified in git log.

| Item | Status |
|------|--------|
| src/feedops/api/intent_scoring.py | FOUND |
| src/feedops/api/finish_processing.py | FOUND |
| tests/api/test_intent_scoring.py | FOUND |
| tests/api/test_finish_processing.py | FOUND |
| Commit 62cbfbeb (Task 1) | FOUND |
| Commit 353a2bca (Task 2) | FOUND |
