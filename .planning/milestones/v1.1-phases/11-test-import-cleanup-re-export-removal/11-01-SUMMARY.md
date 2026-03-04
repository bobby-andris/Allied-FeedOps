---
phase: 11-test-import-cleanup-re-export-removal
plan: "01"
subsystem: python-pipeline
tags: [dead-code, test-refactoring, imports, main-py, re-exports]
dependency_graph:
  requires: []
  provides: [DEAD-02, DEAD-03]
  affects: [src/feedops/api/main.py, tests/api/test_finish_prompt_source_contract.py, tests/test_generation_runtime_scope_contract.py, tests/test_phase7_observability_reliability.py, tests/api/test_main_master_sku_alias_runtime.py]
tech_stack:
  added: []
  patterns: [canonical-import-migration, monkeypatch-at-resolution-site]
key_files:
  created: []
  modified:
    - src/feedops/api/main.py
    - tests/api/test_finish_prompt_source_contract.py
    - tests/test_generation_runtime_scope_contract.py
    - tests/test_phase7_observability_reliability.py
    - tests/api/test_main_master_sku_alias_runtime.py
    - tests/test_query_intent_lineage.py
decisions:
  - "get_request_id monkeypatches for job_runner tests: patch at feedops.api.job_management (where _resolve_execution_request_id resolves the name), not api_job_runner directly"
  - "Pre-existing E402 violations on router mounting imports: suppressed with noqa annotations (were masked by the now-deleted re-export block)"
  - "test_query_intent_lineage.py migrated as Rule 1 auto-fix: not in DEAD-02 list but broke when re-export block removed"
metrics:
  duration: 13 min
  completed: "2026-03-04"
  tasks_completed: 2
  files_modified: 6
---

# Phase 11 Plan 01: Test-Import Cleanup and Re-export Removal Summary

Migrated 4 test files from `feedops.api.main` re-export imports to canonical module imports (DEAD-02), then deleted the 131-line backward-compat re-export block from main.py (DEAD-03), shrinking main.py from 304 to 172 lines with zero test regressions.

## What Was Built

### Task 1: Migrate 4 Test Files to Canonical Imports (DEAD-02)

Four test files were migrated one at a time in complexity order:

**File 1: test_finish_prompt_source_contract.py (4 refs)**
- `api_main.get_finish_list` → direct import from `feedops.api.prompt_loader`
- `api_main._assembled_prompt_hash` → direct import from `feedops.api.persistence`
- `api_main._enforce_finish_sentence_parity` → direct import from `feedops.api.finish_processing`
- Removed `import feedops.api.main as api_main` entirely

**File 2: test_generation_runtime_scope_contract.py (8 refs)**
- `api_main.get_finish_list()` → direct import from `feedops.api.prompt_loader`
- `api_main.get_request_id` patches (for job_runner tests) → `api_job_management.get_request_id` (resolved via `_resolve_execution_request_id`)
- `api_main.regenerate_content` calls → `api_routes.regenerate_content`
- `api_main.RegenerateRequest` → `api_schemas.RegenerateRequest`
- `api_main.generate_per_platform` patches → `api_generation.generate_per_platform`

**File 3: test_phase7_observability_reliability.py (21 refs)**
- `api_main.get_finish_list()` in `_FakeProvider`/`_RecordingProvider` → direct import
- All `api_main.*` patches in `_patch_generation_deps` removed (were redundant — `api_routes`/`api_generation`/`api_job_runner` patches already present)
- Route handler calls (`optimize_single_sku`, `regenerate_content`, `batch_optimize`, `hybrid_generate`) → `api_routes.*`
- Schema refs → `api_schemas.*`
- `api_main.get_request_id` patches → `api_routes.get_request_id` or `api_job_management.get_request_id`
- `api_main._emit_generation_summary` patches → `api_job_runner._emit_generation_summary`

**File 4: test_main_master_sku_alias_runtime.py (42 refs)**
- All schema types (`RegenerateRequest`, `HybridGenerateRequest`, `OptimizeRequest`, `BatchOptimizeRequest`, `RegenerateJobResponse`) → `api_schemas.*`
- Route handler calls → `api_routes.*`
- Job management helpers (`_regeneration_idempotency_key`, `_hybrid_generation_idempotency_key`, `_require_request_id`) → direct imports from `feedops.api.job_management`
- Persistence helpers (`_assembled_prompt_hash`, `_enforce_write_time_finish_placeholder_contract`) → direct imports from `feedops.api.persistence`
- `api_main._emit_generation_summary` → direct import from `feedops.api.telemetry`
- `api_main.HTTPException` → `from fastapi import HTTPException`
- `api_main.GenerationBudgetExceededError` → direct import from `feedops.pipeline.generator`
- All monkeypatches → `api_routes.*` or `api_job_management.*`

### Task 2: Delete Re-export Block and Verify Importability (DEAD-03)

- Deleted entire backward-compat re-export block (lines 174-304 of original main.py, 131 lines)
- Removed `HTTPException` from line 39 import (no longer used in main.py functional code)
- Added `# noqa: E402` to 7 pre-existing router mounting imports (previously masked by re-export block's noqa annotations)
- main.py: 304 → 172 lines

## Commits

| Hash | Message |
|------|---------|
| `3f1b983f` | refactor(tests): migrate test_finish_prompt_source_contract.py to canonical imports |
| `017d5771` | refactor(tests): migrate test_generation_runtime_scope_contract.py to canonical imports |
| `639266bd` | refactor(tests): migrate test_phase7_observability_reliability.py to canonical imports |
| `c7ebc5f8` | refactor(tests): migrate test_main_master_sku_alias_runtime.py to canonical imports |
| `67e99ee0` | refactor(dead-code): remove 131-line backward-compat re-export block from main.py (DEAD-03) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_query_intent_lineage.py broke after re-export removal**
- **Found during:** Task 2 (after re-export block deletion)
- **Issue:** `test_query_intent_lineage.py` was not in the DEAD-02 migration list but accessed `api_main._extract_query_intent_generation_diagnostics`, `api_main._persist_regeneration_result`, `api_main.get_request_id`, and `api_main.get_platform_system_prompt_hash` via the re-export block
- **Fix:** Migrated to canonical imports — `_extract_query_intent_generation_diagnostics` from `feedops.api.intent_scoring`, `_persist_regeneration_result` from `feedops.api.persistence`; monkeypatches moved to `api_persistence` module
- **Files modified:** `tests/test_query_intent_lineage.py`
- **Commit:** `67e99ee0` (included in Task 2 commit)

**2. [Rule 2 - Missing] E402 noqa annotations on pre-existing router mounting imports**
- **Found during:** Task 2 (ruff check after re-export removal)
- **Issue:** 7 router mounting imports (prometheus, search_insights, monitoring, gmc_sync, performance_baseline, intent_scoring, routes) had pre-existing E402 violations that were masked by the now-deleted re-export block's noqa annotations
- **Fix:** Added `# noqa: E402` to each of the 7 lines
- **Files modified:** `src/feedops/api/main.py`
- **Commit:** `67e99ee0`

**3. [Rule 1 - Bug] Monkeypatch target for get_request_id in job_runner tests**
- **Found during:** Task 1, File 2 migration (test failures)
- **Issue:** `api_job_runner` module does not import `get_request_id` directly; it resolves through `feedops.api.job_management._resolve_execution_request_id`. Patching `api_job_runner.get_request_id` raised `AttributeError`
- **Fix:** Patch at `feedops.api.job_management.get_request_id` (where the name is actually resolved)
- **Files modified:** `tests/test_generation_runtime_scope_contract.py`, `tests/test_phase7_observability_reliability.py`, `tests/api/test_main_master_sku_alias_runtime.py`

## Verification Results

```
Zero api_main.* refs in 4 migrated files: 0
main.py line count: 172 (down from 304)
main.py importable: OK
ruff check src/feedops/api/main.py: All checks passed!
Full test suite: 790 passed, 1 failed (pre-existing test_cli.py), 1 skipped
5 smoke tests: 31 passed
```

## Self-Check: PASSED

- SUMMARY.md exists: FOUND
- All 5 task commits: FOUND (3f1b983f, 017d5771, 639266bd, c7ebc5f8, 67e99ee0)
- Zero api_main.* refs in 4 migrated files: VERIFIED (0 results)
- main.py line count 172: VERIFIED
- main.py importable: VERIFIED (OK)
- ruff clean on main.py: VERIFIED
- Full suite 790 passed: VERIFIED
