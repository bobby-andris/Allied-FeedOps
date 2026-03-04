---
phase: 02-services-extraction
plan: 02
subsystem: feedops-api
tags: [refactoring, services-extraction, generation, decomposition]
dependency_graph:
  requires:
    - 02-01-SUMMARY.md  # intent_scoring.py, finish_processing.py
  provides:
    - src/feedops/api/generation.py
  affects:
    - src/feedops/api/main.py
tech_stack:
  added: []
  patterns:
    - Pure function extraction (no APIRouter needed — generation.py has no route handlers)
    - Dual-namespace monkeypatching (tests patching both api_main and api_generation after extraction)
key_files:
  created:
    - src/feedops/api/generation.py
    - tests/api/test_generation.py
  modified:
    - src/feedops/api/main.py
    - tests/api/test_main_master_sku_alias_runtime.py
    - tests/test_generation_runtime_scope_contract.py
    - tests/test_phase7_observability_reliability.py
decisions:
  - "Pure function extraction for generation.py — no APIRouter needed since _execute_regeneration_request and _build_generation_user_prompt are not route handlers"
  - "Dual-namespace monkeypatching pattern: tests that previously patched api_main.load_parent_sku_from_supabase etc. must now also patch api_generation.* after extraction"
  - "_patch_generation_deps helper updated to patch both api_main and api_generation namespaces for correct dependency injection"
metrics:
  duration: "~11 min"
  completed: "2026-03-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
---

# Phase 02 Plan 02: Services Extraction (Generation) Summary

**One-liner:** Extracted generation.py with _execute_regeneration_request (324-line core orchestrator) and _build_generation_user_prompt from main.py (DECOMP-07), completing Phase 2 services extraction — main.py reduced by 579 lines total from Phase 2.

## What Was Built

### generation.py (DECOMP-07)

New module `src/feedops/api/generation.py` containing:

- `_build_generation_user_prompt(...)` — DEPRECATED thin wrapper around build_core_prompt() + apply_feedback_layer(), moved verbatim
- `_execute_regeneration_request(...)` — 324-line core generation orchestrator: loads corrections, builds feedback, calls generate_per_platform, persists results, emits telemetry, returns RegenerateResponse

**Key design:** Pure function extraction (no APIRouter needed). All 15+ dependency imports correctly resolved in generation.py using same aliases as main.py (e.g., `from feedops.api.generation_telemetry import provider_label as _provider_label`).

### Tests (DECOMP-11 completion)

New module `tests/api/test_generation.py` with 7 unit tests:
- `test_generation_importable_without_main` — import isolation
- `test_build_generation_user_prompt_returns_string` — wrapper delegation
- `test_build_generation_user_prompt_no_feedback` — None feedback handling
- `test_build_generation_user_prompt_passes_finish_code` — kwargs forwarding
- `test_execute_regeneration_request_missing_sku_raises_404` — error path
- `test_execute_regeneration_request_missing_content_field_raises_502` — error path
- `test_execute_regeneration_request_calls_persist_and_returns_response` — happy path

### main.py Reduction

- Removed ~349 lines: `_build_generation_user_prompt` (25 lines) + `_execute_regeneration_request` (324 lines)
- Added 6 import lines referencing generation module
- Net: main.py went from 2,424 to 2,075 lines
- Total Phase 2 reduction: 2,654 → 2,075 = **579 lines removed**

### Endpoint Verification (DECOMP-10)

All 7 required routes verified registered:
- `/optimize-sku`, `/regenerate`, `/batch-optimize`, `/hybrid-generate`, `/generate-images`, `/score-intent`, `/health`
- Total: 39 routes registered in the FastAPI app

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken tests after extraction — dual-namespace monkeypatching**

- **Found during:** Task 1 (full suite run after extraction)
- **Issue:** 6 tests in 3 files patched `api_main.load_parent_sku_from_supabase`, `api_main.get_provider`, `api_main.get_client`, and `api_main.generate_per_platform` — but these calls now happen inside `generation.py`, which has its own references. Monkeypatching `api_main.*` no longer intercepts the calls in `_execute_regeneration_request`.
- **Fix:**
  - Added `import feedops.api.generation as api_generation` to 3 test files
  - Updated `_patch_generation_deps()` helper to also patch at `api_generation` namespace (`load_parent_sku_from_supabase`, `get_provider`, `get_client`, `resolve_canonical_master_sku`)
  - Updated 4 tests in `test_main_master_sku_alias_runtime.py` to patch `api_generation.resolve_canonical_master_sku`, `get_client`, `get_provider`, `load_parent_sku_from_supabase`, `generate_per_platform`
  - Updated 3 tests in `test_generation_runtime_scope_contract.py` to also patch `api_generation.generate_per_platform`
  - Updated 2 standalone tests in `test_phase7_observability_reliability.py` to patch `api_generation.*`
- **Files modified:** `tests/api/test_main_master_sku_alias_runtime.py`, `tests/test_generation_runtime_scope_contract.py`, `tests/test_phase7_observability_reliability.py`
- **Commit:** b7b2e587

## Results

- 725 tests passed, 1 skipped — zero regressions
- All must-have truths verified:
  - `generation.py` importable standalone (exit 0)
  - `feedops.api.main` importable with no circular imports (exit 0)
  - All 7 required endpoints registered and functional
  - Full test suite passes with zero regressions
  - main.py reduced by 349 lines in this plan (579 total in Phase 2)

## Phase 2 Complete: DECOMP Requirements Satisfied

| Requirement | Status |
|-------------|--------|
| DECOMP-05 (intent_scoring.py) | Complete — Plan 01 |
| DECOMP-06 (finish_processing.py) | Complete — Plan 01 |
| DECOMP-07 (generation.py) | Complete — Plan 02 |
| DECOMP-08 (daemon=False assertion) | Complete — Plan 01 |
| DECOMP-10 (endpoint verification) | Complete — Plan 02 |
| DECOMP-11 (unit tests for all modules) | Complete — Plans 01+02 |

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits verified in git log.

| Item | Status |
|------|--------|
| src/feedops/api/generation.py | FOUND |
| tests/api/test_generation.py | FOUND |
| Commit b7b2e587 (Task 1) | FOUND |
| Commit 56422920 (Task 2) | FOUND |
