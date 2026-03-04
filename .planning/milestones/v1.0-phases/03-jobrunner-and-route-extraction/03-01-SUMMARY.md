---
phase: 03-jobrunner-and-route-extraction
plan: 01
subsystem: api-decomposition
tags: [refactoring, job-runner, extraction, tdd]
requirements: [JOBS-01, JOBS-02, JOBS-03, JOBS-04, JOBS-05, JOBS-06]

dependency_graph:
  requires:
    - 02-02-SUMMARY.md  # generation.py extraction (generate_per_platform)
    - persistence.py    # _persist_generated_content_and_history, _upsert_batch_job_sku_status
    - telemetry.py      # _emit_generation_summary, run_async_in_thread
    - hybrid_generation.py  # adapt_variant_content
  provides:
    - src/feedops/api/job_runner.py  # JobRunner class (batch + hybrid modes)
  affects:
    - src/feedops/api/main.py        # removed 817 lines; uses JobRunner
    - tests/test_generation_runtime_scope_contract.py  # updated patches
    - tests/test_phase7_observability_reliability.py   # updated patches
    - tests/api/test_main_master_sku_alias_runtime.py  # updated patches

tech_stack:
  added: []
  patterns:
    - "JobRunner class with mode enum dispatch (batch/hybrid)"
    - "threading.Event cancellation checked at SKU boundary"
    - "Cancellation registry: register_runner/unregister_runner/cancel_runner"
    - "_generate_full_sku() extracted from generate_full_content_v2 inner closure"
    - "TDD: RED commit (tests) then GREEN commit (implementation)"
    - "Dual-namespace monkeypatching: tests patch api_job_runner instead of api_main"

key_files:
  created:
    - path: src/feedops/api/job_runner.py
      purpose: "Unified JobRunner class replacing process_batch_job and process_hybrid_batch_job"
      lines: 580
    - path: tests/api/test_job_runner_smoke.py
      purpose: "Smoke and parity tests for JobRunner (JOBS-01 through JOBS-06)"
      lines: 439
  modified:
    - path: src/feedops/api/main.py
      change: "Removed 817 lines (process_batch_job, process_hybrid_batch_job); wired JobRunner"
      lines_before: 2075
      lines_after: 1258
    - path: tests/test_generation_runtime_scope_contract.py
      change: "Updated 8 tests to use api_job_runner for patching and calling"
    - path: tests/test_phase7_observability_reliability.py
      change: "Updated _patch_generation_deps + 5 test calls to use api_job_runner"
    - path: tests/api/test_main_master_sku_alias_runtime.py
      change: "Updated 2 test calls to use api_job_runner"

decisions:
  - "extract_spec_difference imported from multi_sku_detection (not hybrid_generation) — research doc had wrong module"
  - "Dual-namespace monkeypatching: tests that call job processing must patch at api_job_runner, not api_main"
  - "func_name assertion updated: 'process_batch_job' -> 'run' (bound method __name__)"
  - "process_regenerate_job left in main.py — JOBS-01 specifies batch+hybrid only"

metrics:
  duration_minutes: 13
  completed_date: "2026-03-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  tests_added: 12
  tests_updated: 15
  lines_removed_from_main: 817
---

# Phase 3 Plan 01: JobRunner Extraction Summary

**One-liner:** Unified JobRunner class in job_runner.py replaces two 817-line duplicate job processors from main.py, with threading.Event cancellation support and TDD verification.

## What Was Built

### job_runner.py — Unified Background Job Processor

New file providing `JobRunner` class that replaces both `process_batch_job()` and `process_hybrid_batch_job()` top-level functions from `main.py`:

```python
from feedops.api.job_runner import JobRunner

# Batch mode (replaces process_batch_job)
runner = JobRunner(mode="batch")
await runner.run(job_id=job_id, skus=skus, num_candidates=1, dry_run=False, options=options)

# Hybrid mode (replaces process_hybrid_batch_job)
runner = JobRunner(mode="hybrid")
await runner.run(job_id=job_id, families=families, single_skus=single_skus, options=options)

# Cancellation
event = threading.Event()
runner = JobRunner(mode="batch", cancel_event=event)
event.set()  # Stops at next SKU boundary
```

Key design choices:
- **Mode dispatch** (JOBS-02): `run()` dispatches to `_run_batch()` or `_run_hybrid()`
- **Separate methods** (JOBS-04, Pitfall 5): Progress tracking stays mode-specific; only `_generate_full_sku()` is shared
- **cancellation registry** (JOBS-05): `register_runner/cancel_runner` for per-job cancellation via `cancel_runner(job_id)`
- **`_generate_full_sku()`** (Pitfall 2): `generate_full_content_v2` inner closure extracted as explicit-parameter method

### main.py — Reduced to Route Handlers

- `from feedops.api.job_runner import JobRunner` added
- `run_async_in_thread(process_batch_job, ...)` → `run_async_in_thread(JobRunner(mode="batch").run, ...)`
- `run_async_in_thread(process_hybrid_batch_job, ...)` → `run_async_in_thread(JobRunner(mode="hybrid").run, ...)`
- `extract_spec_difference` import removed (now only in job_runner.py)
- 817 lines removed (279 for batch, 538 for hybrid)

## Tasks Completed

| Task | Description | Commit | Key Changes |
|------|-------------|--------|-------------|
| 1 (RED) | Write failing smoke/parity tests | 49c05b5e | tests/api/test_job_runner_smoke.py (12 tests) |
| 1 (GREEN) | Implement JobRunner class | 4fd14345 | src/feedops/api/job_runner.py (~580 lines) |
| 2 | Wire main.py + delete old functions | 3c25bf4f | main.py -817 lines; 3 test files updated |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] extract_spec_difference was in wrong import module**
- **Found during:** Task 1 (GREEN phase - first import attempt)
- **Issue:** Research document stated `from feedops.api.hybrid_generation import adapt_variant_content, extract_spec_difference` but `extract_spec_difference` is actually in `feedops.api.multi_sku_detection`
- **Fix:** `from feedops.api.multi_sku_detection import extract_spec_difference` (separate import)
- **Files modified:** src/feedops/api/job_runner.py
- **Commit:** 4fd14345

**2. [Rule 1 - Bug] Test func_name assertion was 'process_batch_job', must be 'run'**
- **Found during:** Task 2 (test suite update)
- **Issue:** `test_batch_optimize_passes_generation_options_to_background_job` asserted `captured["func_name"] == "process_batch_job"`. After extraction, `JobRunner(mode="batch").run` is passed — bound method `__name__` is `"run"`.
- **Fix:** Updated assertion to `captured["func_name"] == "run"`
- **Files modified:** tests/test_phase7_observability_reliability.py
- **Commit:** 3c25bf4f

**3. [Rule 3 - Blocking] Existing tests patch api_main for job processing code**
- **Found during:** Task 2 (run full test suite step)
- **Issue:** 15 tests in 3 files called `await api_main.process_batch_job(...)` or `await api_main.process_hybrid_batch_job(...)` and used `monkeypatch.setattr(api_main, "generate_per_platform", ...)`. After extraction, these patches no longer reach the job processing code.
- **Fix:** Updated all 15 tests to call `api_job_runner.JobRunner(mode=X)._run_batch/hybrid(...)` and patch at `api_job_runner`. Updated `_patch_generation_deps` to also patch `api_job_runner` module.
- **Files modified:** tests/test_generation_runtime_scope_contract.py, tests/test_phase7_observability_reliability.py, tests/api/test_main_master_sku_alias_runtime.py
- **Commit:** 3c25bf4f

## Verification Results

All plan verification checks pass:

```
python -c "from feedops.api.job_runner import JobRunner; print('OK')"  → OK
python -c "import feedops.api.main"  → OK (no circular imports)
grep -c "process_batch_job|process_hybrid_batch_job" main.py  → 1 (comment only)
grep -n "JobRunner" main.py  → lines 125, 966, 1171 (import + 2 usages)
wc -l main.py  → 1258 (down from 2075, -817 lines)
pytest tests/api/test_job_runner_smoke.py  → 12 passed
pytest tests/ (full suite)  → 726+ passed, 0 new failures
```

## Self-Check: PASSED

All files exist and all commits are present in git history:

- FOUND: src/feedops/api/job_runner.py
- FOUND: tests/api/test_job_runner_smoke.py
- FOUND commit 49c05b5e (RED phase tests)
- FOUND commit 4fd14345 (GREEN phase implementation)
- FOUND commit 3c25bf4f (main.py wiring + test updates)
