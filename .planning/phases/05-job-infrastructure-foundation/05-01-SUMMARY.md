---
phase: 05-job-infrastructure-foundation
plan: 01
subsystem: backfill-infrastructure
tags: [database, models, job-management, crud, v1.0]
dependency_graph:
  requires: []
  provides:
    - backfill_jobs table schema
    - backfill_job_errors table schema
    - Python job models (JobStatus, JobType, BackfillJob, JobError)
    - Job manager CRUD layer (9 functions)
  affects:
    - All future job processing plans (05-02, 05-03, 05-04)
    - Database schema documentation
tech_stack:
  added:
    - Pydantic models for job data
    - PostgreSQL JSONB for checkpoint/config storage
    - RPC function for atomic counter updates
  patterns:
    - Supabase client pattern (get_client at call time)
    - Enum-based status and type validation
    - Checkpoint/resume architecture for long-running jobs
key_files:
  created:
    - supabase/migrations/026_backfill_jobs.sql
    - src/feedops/jobs/__init__.py
    - src/feedops/jobs/models.py
    - src/feedops/jobs/manager.py
  modified:
    - docs/database/SCHEMA.md
decisions:
  - title: "JSONB for SKU lists and checkpoint data"
    rationale: "Flexible storage for variable-length SKU arrays and arbitrary checkpoint state without schema changes"
    alternatives: ["Separate backfill_job_items table", "TEXT array columns"]
    impact: "Simplifies schema, enables complex checkpoint state, requires JSONB parsing in queries"
  
  - title: "RPC function for atomic failure increment"
    rationale: "Prevents race conditions when multiple concurrent errors are logged"
    alternatives: ["Application-level locking", "Accept eventual consistency"]
    impact: "Guarantees accurate failed_items count under concurrent writes"
  
  - title: "ETA calculation in manager.py"
    rationale: "Centralize rate-based ETA logic in Python rather than SQL triggers"
    alternatives: ["Database trigger on update", "Client-side calculation"]
    impact: "Easier to test and modify, requires passing started_at_epoch from caller"
  
  - title: "Status enum with 5 states"
    rationale: "Matches batch_generation_jobs pattern, supports partial success tracking"
    alternatives: ["Boolean is_complete flag", "Separate failed/partial states"]
    impact: "Clear lifecycle: creating → running → [complete|failed|partial]"
metrics:
  duration_minutes: 3.2
  tasks_completed: 2
  commits: 2
  files_modified: 5
  lines_added: 628
  completed_date: 2026-02-13
---

# Phase 05 Plan 01: Job Infrastructure & Foundation Summary

## One-Liner

Database schema and Python CRUD layer for backfill job lifecycle management with checkpoint/resume support.

## Objective

Establish the persistent storage and CRUD layer that all subsequent job processing depends on. Without this, no job can be created, tracked, or resumed after Cloud Run container restarts.

## What Was Built

### Database Schema (Migration 026)

**Table: `backfill_jobs`**
- Full lifecycle tracking: creating → running → complete/failed/partial
- Progress metrics: total_items, completed_items, failed_items, eta_seconds
- Checkpoint/resume: JSONB checkpoint_data field for arbitrary state
- Job config: JSONB config field for batch_size, days_lookback, etc.
- Status and job_type enums enforced via CHECK constraints

**Table: `backfill_job_errors`**
- Per-item error logging with item_id, error_type, error_message
- Retry tracking via retry_count field
- CASCADE DELETE when parent job is deleted

**RPC: `increment_backfill_failures(p_job_id UUID)`**
- Atomically increments failed_items counter
- Prevents race conditions during concurrent error logging

### Python Models (`src/feedops/jobs/models.py`)

**Enums:**
- `JobStatus`: creating, running, complete, failed, partial
- `JobType`: search_terms, performance_metrics, keyword_planner, custom_labels, full_backfill

**Models:**
- `BackfillJob`: Full job data with Pydantic validation, `from_attributes=True` for ORM
- `JobError`: Error log entry with retry tracking

### Job Manager (`src/feedops/jobs/manager.py`)

**9 CRUD functions following existing Supabase client patterns:**

1. **create_job** - Create job with SKU list, return UUID
2. **get_job** - Retrieve job by ID as BackfillJob model
3. **get_active_jobs** - Get all creating/running jobs
4. **get_active_job_count** - Count active jobs
5. **update_job_status** - Update status, auto-set started_at/completed_at
6. **update_job_progress** - Update completed_items, calculate ETA
7. **save_checkpoint** - Save checkpoint_data for resume
8. **log_job_error** - Insert error + atomic increment failed_items
9. **get_job_errors** - Retrieve error logs for debugging

**Pattern compliance:**
- `get_client()` imported at function call time (not module level)
- Follows existing retry and error handling patterns
- Uses Pydantic models for type safety

### Documentation

Updated `docs/database/SCHEMA.md`:
- Added "Backfill Infrastructure Tables" section (10)
- Full column documentation for both tables
- Common query patterns and JSONB structure examples
- Foreign key relationship to Key Relationships section
- Updated table count: 32 → 34

## Deviations from Plan

**None** - Plan executed exactly as written. All tasks completed successfully:
- ✅ Migration file with both tables, constraints, indexes, RPC function
- ✅ Python models with enums and Pydantic models
- ✅ Manager module with all 9 CRUD functions
- ✅ SCHEMA.md updated with comprehensive documentation

## Verification Results

**Migration file verification:**
- Contains backfill_jobs CREATE TABLE
- Contains backfill_job_errors CREATE TABLE
- Contains increment_backfill_failures RPC function
- All constraints and indexes present

**Python verification:**
```bash
$ python -c "from feedops.jobs import JobStatus, JobType, BackfillJob, create_job, get_job"
SUCCESS: All imports work
```

**SCHEMA.md verification:**
- ✅ Contains "backfill_jobs" section
- ✅ Contains "backfill_job_errors" section
- ✅ Foreign key relationship documented
- ✅ Table count updated to 34

## Success Criteria

- [x] backfill_jobs table supports full job lifecycle: creating → running → complete/failed/partial
- [x] backfill_job_errors table captures per-item errors with retry tracking
- [x] Python models provide type-safe job data access
- [x] Manager module provides complete CRUD for job lifecycle
- [x] All functions use existing Supabase client patterns (get_client, @_with_retry)

## Commits

| Commit | Task | Message |
|--------|------|---------|
| 98b11637 | 1 | feat(05-01): create backfill jobs database schema |
| 651666dc | 2 | feat(05-01): create job models and manager module |

## Next Steps

**Immediate dependencies (Phase 05):**
- Plan 02: Collection workers (search terms, performance, keyword planner)
- Plan 03: Queue processing engine with batch execution
- Plan 04: API endpoints for job creation and monitoring

**Integration points:**
- Collection workers will call `create_job()` to initialize jobs
- Queue processor will call `update_job_status()`, `update_job_progress()`, `save_checkpoint()`
- Error handlers will call `log_job_error()` for item failures
- Monitoring UI will call `get_active_jobs()` and `get_job_errors()`

## Self-Check: PASSED

All claimed artifacts verified:

**Files created:**
```bash
$ ls -1 supabase/migrations/026_backfill_jobs.sql
$ ls -1 src/feedops/jobs/__init__.py src/feedops/jobs/models.py src/feedops/jobs/manager.py
```
✅ All files exist

**Commits:**
```bash
$ git log --oneline --all | grep -E "98b11637|651666dc"
651666dc feat(05-01): create job models and manager module
98b11637 feat(05-01): create backfill jobs database schema
```
✅ Both commits found

**SCHEMA.md:**
```bash
$ grep -c "backfill_jobs" docs/database/SCHEMA.md
$ grep -c "backfill_job_errors" docs/database/SCHEMA.md
```
✅ Tables documented

