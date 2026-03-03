---
phase: 03-jobrunner-and-route-extraction
plan: 02
subsystem: api
tags: [decomposition, route-extraction, fastapi, decomp-09]
dependency_graph:
  requires: [03-01-SUMMARY.md]
  provides: [routes.py with all 14 route handlers, slimmed main.py under 500 lines, line-count guard test]
  affects: [src/feedops/api/main.py, src/feedops/api/routes.py]
tech_stack:
  added: [FastAPI APIRouter pattern for main routes]
  patterns: [dual-namespace re-export backward-compat, dual-namespace monkeypatching in tests]
key_files:
  created:
    - src/feedops/api/routes.py
    - tests/api/test_main_line_count.py
  modified:
    - src/feedops/api/main.py
    - tests/api/test_main_master_sku_alias_runtime.py
    - tests/test_phase7_observability_reliability.py
    - tests/test_v1_path_regression.py
decisions:
  - "Dual-namespace backward-compat re-exports added to main.py so tests patching api_main.* continue to work without modification (same pattern as Phase 02-02)"
  - "Test files updated to also patch api_routes.* for route handler functions that moved out of main.py — same dual-namespace monkeypatching protocol established in Phase 02"
  - "test_v1_path_regression updated to check routes.py instead of main.py for prompt_version='v2' (route logic moved, test was checking wrong file)"
  - "_patch_generation_deps helper in test_phase7 updated to also patch api_routes module — shared helper pattern for route-level test isolation"
metrics:
  duration: 22 min
  completed: "2026-03-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  tests_added: 1
  test_suite: "737 passing, 1 pre-existing failure (test_cli), 1 skipped"
---

# Phase 03 Plan 02: Route Extraction to routes.py Summary

All 14 route handlers extracted from main.py to routes.py via FastAPI APIRouter; main.py reduced from 1,258 to 304 lines with a permanent guard test preventing regression.

## What Was Built

### Task 1: Extract all route handlers to routes.py and slim main.py

Created `src/feedops/api/routes.py` with a single `APIRouter` containing all 14 route handlers previously inline in `main.py`:

- `GET /` (root info)
- `GET /health` (health check)
- `POST /optimize-sku` (single SKU generation)
- `async process_regenerate_job` (background worker — co-located with route)
- `POST /regenerate` (content regeneration sync/async)
- `GET /regenerate/status/{job_id}` (async job status)
- `POST /generate-images` (lifestyle image generation)
- `POST /batch-optimize` (batch job creation)
- `GET /batch-status/{job_id}` (batch job status)
- `POST /hybrid-generate` (hybrid multi-SKU generation)
- `POST /backfill/start`
- `GET /backfill/validation-report`
- `GET /backfill/status/{job_id}`
- `POST /backfill/resume/{job_id}`
- `GET /backfill/jobs`

`main.py` now contains only: lifespan context manager, `app = FastAPI(...)` creation, CORS middleware, Prometheus metrics mount, router includes, `attach_request_context` middleware, and backward-compat re-exports.

**Key design decisions:**
- `process_regenerate_job` moved to routes.py alongside `regenerate_content` (its only caller) — not left in main.py
- Backward-compat re-exports added to main.py using `from feedops.api.routes import ...` (same dual-namespace pattern from Phase 02-02) so existing tests patching `api_main.*` work without modification
- Tests in 3 files updated to add `api_routes` dual-namespace patches for the functions that actually execute inside route handlers

### Task 2: Add main.py line-count assertion test

Created `tests/api/test_main_line_count.py` with `test_main_py_under_500_lines()` — a permanent regression guard. Any future code added directly to main.py will cause this test to fail, directing developers to routes.py or an appropriate service module instead.

## Verification Results

```
wc -l src/feedops/api/main.py      → 304 (< 500 ✓)
wc -l src/feedops/api/routes.py    → 1057 (> 600 ✓)
router.routes count                → 14 routes ✓
import feedops.api.routes; import feedops.api.main → No circular imports ✓
grep process_regenerate_job main.py  → 1 (re-export only) ✓
grep process_regenerate_job routes.py → 6 (actual definition) ✓
pytest tests/                      → 737 passed, 1 pre-existing failure ✓
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test monkeypatching broken after function relocation**
- **Found during:** Task 1 — post-extraction test run
- **Issue:** 13 tests failed because they patched `api_main.get_request_id`, `api_main.ensure_generation_enabled`, `api_main.get_client`, `api_main.run_async_in_thread`, `api_main._emit_generation_summary`, `api_main._execute_regeneration_request`, `api_main.detect_multi_sku_families`, and similar names — but route handlers now execute from `routes.py` namespace, not `main.py` namespace. Monkeypatches on `api_main.*` had no effect on route execution.
- **Fix:** Added `import feedops.api.routes as api_routes` to 3 test files and added matching `api_routes.*` patches alongside each `api_main.*` patch in 13 test cases. Also updated `_patch_generation_deps` shared helper to patch both `api_main` and `api_routes`. This is the dual-namespace monkeypatching protocol established in Phase 02-02.
- **Files modified:** `tests/api/test_main_master_sku_alias_runtime.py`, `tests/test_phase7_observability_reliability.py`
- **Commits:** 082d0ade

**2. [Rule 1 - Bug] test_v1_path_regression checking wrong source file**
- **Found during:** Task 1
- **Issue:** `test_main_generation_paths_call_v2_per_platform_generation_only` asserted `prompt_version="v2"` exists in `main.py` source. After extraction, this code lives in `routes.py`. The test was checking the wrong file.
- **Fix:** Updated test to check `routes.py` instead of `main.py` with an explanatory comment.
- **Files modified:** `tests/test_v1_path_regression.py`
- **Commits:** 082d0ade

## Self-Check: PASSED

- FOUND: src/feedops/api/routes.py (1057 lines, 14 routes)
- FOUND: tests/api/test_main_line_count.py
- FOUND: commit 082d0ade (feat(03-02): extract all route handlers)
- FOUND: commit 669d3188 (test(03-02): guard test)
- Test suite: 737 passed, 1 pre-existing failure
