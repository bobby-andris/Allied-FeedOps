---
phase: 05-job-infrastructure-foundation
plan: "03"
subsystem: job-infrastructure
tags: [api, fastapi, endpoints, job-management, rate-limiting, v1.0]
dependency_graph:
  requires:
    - backfill_jobs table schema (05-01)
    - Python job models and manager (05-01)
    - Token bucket rate limiter (05-02)
    - Batch processor (05-02)
  provides:
    - POST /backfill/start endpoint
    - GET /backfill/status/{job_id} endpoint
    - POST /backfill/resume/{job_id} endpoint
    - GET /backfill/jobs endpoint
    - Backfill API module (feedops.api.backfill)
  affects:
    - Dashboard data collection UI (Phase 2)
    - External monitoring tools
tech_stack:
  added:
    - FastAPI endpoint handlers for backfill jobs
    - Pydantic request/response models
    - Background task orchestration via run_async_in_thread
  patterns:
    - Concurrent job limiting (max 3 per JOB-10)
    - Checkpoint/resume support through manager layer
    - Rate-limited batch processing via BatchProcessor
key_files:
  created:
    - src/feedops/api/backfill.py
  modified:
    - src/feedops/api/main.py
    - src/feedops/jobs/__init__.py
decisions:
  - title: "Placeholder _noop_process for Phase 1"
    rationale: "Allows testing full job infrastructure without Google Ads API dependencies"
    alternatives: ["Wait for Phase 2 collection workers", "Mock Google Ads responses"]
    impact: "Can validate job lifecycle, rate limiting, checkpointing before real data collection"

  - title: "Import run_async_in_thread from main.py"
    rationale: "Centralized background task pattern already proven in Cloud Run"
    alternatives: ["Duplicate pattern in backfill.py", "Use FastAPI BackgroundTasks"]
    impact: "Ensures backfill jobs survive HTTP response completion on Cloud Run"

  - title: "Job validation in resume endpoint"
    rationale: "Prevents resuming jobs in wrong state (only failed/partial can resume)"
    alternatives: ["Reset job status automatically", "Allow resuming any job"]
    impact: "Clear contract for callers, prevents accidental duplicate processing"
metrics:
  duration_minutes: 2.4
  tasks_completed: 2
  commits: 2
  files_modified: 3
  lines_added: 468
  completed_date: 2026-02-13
---

# Phase 05 Plan 03: Backfill API Endpoints Summary

## One-Liner

FastAPI HTTP endpoints for backfill job lifecycle management with concurrent job limiting, checkpoint/resume support, and Cloud Run-compatible background processing.

## Objective

Wire the job infrastructure (database schema, models, manager, processor) into HTTP endpoints so the dashboard and external callers can create, monitor, and resume backfill jobs. Enforces the concurrent job limit (max 3) to prevent database connection exhaustion.

## What Was Built

### Backfill API Module (`src/feedops/api/backfill.py`)

**Request/Response Models:**
- `StartBackfillRequest`: Job creation with type, SKU list, config
- `BackfillJobResponse`: Single job state with progress_pct
- `BackfillJobListResponse`: Job list with active count and max_concurrent

**Helper Functions:**
- `compute_date_range(days_lookback)`: Explicit YYYY-MM-DD dates for GAQL queries (DATA-07)
- `normalize_offer_id(offer_id)`: Lowercase 'us' format for API queries (DATA-08)
- `_noop_process(batch)`: Placeholder for Phase 1 testing without Google Ads API
- `_job_to_response(job)`: Convert BackfillJob model to API response with computed progress
- `_start_background_processing()`: Background worker that creates BatchProcessor and runs job

**Endpoint Handlers (4 functions):**

1. **`start_backfill(request)`**
   - Enforces max 3 concurrent jobs (returns 429 if exceeded)
   - Creates job via `create_job()`
   - Starts background processing via `run_async_in_thread()`
   - Returns initial job state

2. **`get_backfill_status(job_id)`**
   - Retrieves job by ID
   - Computes progress percentage
   - Returns current state

3. **`resume_backfill(job_id)`**
   - Validates job status (must be 'failed' or 'partial')
   - Enforces concurrent job limit
   - Restarts background processing from checkpoint
   - Returns updated state

4. **`list_backfill_jobs(status, limit)`**
   - Queries jobs with optional status filter
   - Returns list with active count and max_concurrent

**Background Processing Architecture:**
- Uses `run_async_in_thread()` from main.py (not BackgroundTasks)
- Creates BatchProcessor with appropriate rate limiter
- For Phase 1: processes batches with `_noop_process` placeholder
- For Phase 2: will route to real collection functions based on job_type

### FastAPI Integration

**Updated `src/feedops/api/main.py`:**
- Added 4 backfill endpoints with proper tags and docstrings
- Updated module docstring to document new endpoints
- Imported request/response models and handler functions

**Updated `src/feedops/jobs/__init__.py`:**
- Exported `BatchProcessor` from processor module
- Enables external code to use batch processing primitives

## Deviations from Plan

**None** - Plan executed exactly as written. All tasks completed successfully:
- ✅ Backfill API module with 4 endpoint handlers
- ✅ Request/response models with progress calculation
- ✅ Concurrent job limiting (max 3 per JOB-10)
- ✅ Placeholder process function for Phase 1 testing
- ✅ DATA-07/DATA-08 utility helpers
- ✅ Endpoints registered in FastAPI app
- ✅ BatchProcessor exported from jobs module

## Verification Results

**Endpoint Registration:**
```bash
$ python -c "from feedops.api.main import app; routes = [r.path for r in app.routes]; \
  assert '/backfill/start' in routes; assert '/backfill/status/{job_id}' in routes; \
  assert '/backfill/resume/{job_id}' in routes; assert '/backfill/jobs' in routes"
✅ All 4 endpoints registered
```

**Import Verification:**
```bash
$ python -c "from feedops.api.backfill import start_backfill, get_backfill_status, \
  resume_backfill, list_backfill_jobs; print('OK')"
OK
```

**Utility Functions:**
```bash
$ python -c "from feedops.api.backfill import compute_date_range, normalize_offer_id; \
  start, end = compute_date_range(180); print(f'{start} to {end}'); \
  print(normalize_offer_id('shopify_US_123_456'))"
2025-08-17 to 2026-02-13
shopify_us_123_456
```

**BatchProcessor Export:**
```bash
$ python -c "from feedops.jobs import BatchProcessor; print('OK')"
OK
```

## Success Criteria

- [x] POST /backfill/start creates job, starts background processing, returns job_id
- [x] GET /backfill/status/{job_id} returns progress with ETA and percentage
- [x] POST /backfill/resume/{job_id} resumes from checkpoint
- [x] GET /backfill/jobs lists all jobs with active count
- [x] Max 3 concurrent jobs enforced (JOB-10) with 429 response
- [x] Background tasks use run_async_in_thread for Cloud Run compatibility
- [x] Date range helper produces YYYY-MM-DD format (DATA-07)
- [x] Offer ID normalizer handles case conversion (DATA-08)

## Requirements Coverage

**From 05-03-PLAN.md must_haves:**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| POST /backfill/start creates job and returns job_id | ✅ Complete | `start_backfill()` calls `create_job()` and returns BackfillJobResponse |
| GET /backfill/status/{job_id} returns progress with ETA | ✅ Complete | `get_backfill_status()` returns job with progress_pct and eta_seconds |
| POST /backfill/resume/{job_id} resumes from checkpoint | ✅ Complete | `resume_backfill()` validates status and restarts background processing |
| System rejects new jobs when 3 active (JOB-10) | ✅ Complete | `get_active_job_count() >= 3` → HTTPException(429) |
| Background processing uses run_async_in_thread | ✅ Complete | `run_async_in_thread(_start_background_processing, ...)` |

**Key Links from must_haves:**
- ✅ `src/feedops/api/backfill.py` → `src/feedops/jobs/manager.py`: via `create_job`, `get_job`, `update_job_status`
- ✅ `src/feedops/api/backfill.py` → `src/feedops/jobs/processor.py`: via `BatchProcessor` import
- ✅ `src/feedops/api/main.py` → `src/feedops/api/backfill.py`: via endpoint registration

## Commits

| Commit | Task | Message |
|--------|------|---------|
| ad9814e8 | 1 | feat(05-03): create backfill API module with endpoints |
| 312650a8 | 2 | feat(05-03): register backfill endpoints in FastAPI app |

## Next Steps

**Immediate dependencies (Phase 05):**
- Plan 04: Integration tests validating rate limiter accuracy, checkpoint/resume, concurrent job limiting

**Phase 2 Integration:**
- Replace `_noop_process` with real collection functions:
  - `job_type="search_terms"` → Google Ads search term sync
  - `job_type="performance_metrics"` → Shopping performance data
  - `job_type="keyword_planner"` → Keyword Planner data collection
  - `job_type="custom_labels"` → Category labeling
  - `job_type="full_backfill"` → All collection types

**Dashboard Integration:**
- Create UI for `/backfill/start` (job creation form)
- Progress monitoring page using `/backfill/status/{job_id}`
- Retry functionality via `/backfill/resume/{job_id}`
- Job list/history via `/backfill/jobs`

## Architecture Notes

**Background Task Pattern:**
The `run_async_in_thread()` pattern is critical for Cloud Run compatibility:
- FastAPI `BackgroundTasks` are killed when containers scale to zero
- Non-daemon threads with dedicated event loops survive HTTP response
- Pattern already proven by existing endpoints (hybrid-generate, search-insights/sync)

**Concurrent Job Limiting:**
The max 3 concurrent jobs limit prevents database connection exhaustion:
- Each job spawns a BatchProcessor with Supabase client
- Each batch makes queries via manager functions
- Testing will validate this limit is sufficient for 10 QPS rate limiting

**Checkpoint/Resume:**
Jobs can be resumed from last checkpoint after failures:
- `checkpoint_data.batch_index` tracks processing position
- BatchProcessor resumes from checkpoint on startup
- Idempotent upserts prevent duplicate data during resume
- Resume endpoint validates job status before allowing restart

## Self-Check: PASSED

All claimed artifacts verified:

**Files created:**
```bash
$ ls -1 src/feedops/api/backfill.py
src/feedops/api/backfill.py
```
✅ File exists

**Files modified:**
```bash
$ git log --oneline --all -- src/feedops/api/main.py | head -1
312650a8 feat(05-03): register backfill endpoints in FastAPI app

$ git log --oneline --all -- src/feedops/jobs/__init__.py | head -1
312650a8 feat(05-03): register backfill endpoints in FastAPI app
```
✅ Both files modified in Task 2 commit

**Commits:**
```bash
$ git log --oneline --all | grep -E "ad9814e8|312650a8"
312650a8 feat(05-03): register backfill endpoints in FastAPI app
ad9814e8 feat(05-03): create backfill API module with endpoints
```
✅ Both commits found

**Endpoints:**
```bash
$ python -c "from feedops.api.main import app; \
  routes = [r.path for r in app.routes if 'backfill' in r.path]; \
  print('\n'.join(routes))"
/backfill/start
/backfill/status/{job_id}
/backfill/resume/{job_id}
/backfill/jobs
```
✅ All 4 endpoints registered
