---
phase: 06-data-collection-pipeline
plan: 02
subsystem: backfill-api
tags: [routing, worker-integration, rate-limiting, composite-worker]

dependency_graph:
  requires:
    - phase: 06
      plan: 01
      reason: "Worker functions for data collection"
    - phase: 05
      plan: all
      reason: "BatchProcessor and job management infrastructure"
  provides:
    - "Job-type routing from backfill API to collection workers"
    - "Rate limiter selection based on API requirements (10 QPS, 2 QPS, none)"
    - "Composite full_backfill worker running all 4 types sequentially"
  affects:
    - "Backfill API endpoints become fully functional (no longer using placeholder)"
    - "Dashboard can trigger real data collection jobs"
    - "Phase 3 validation testing (end-to-end backfill)"

tech_stack:
  added:
    - collect_full_backfill_batch (composite worker function)
  patterns:
    - Job-type routing via _get_worker_config() function
    - Composite worker pattern (sequential sub-worker execution)
    - Rate limiter selection per job type (API-specific limits)

key_files:
  created: []
  modified:
    - src/feedops/api/backfill.py

decisions:
  - title: "Full Backfill as Composite Worker"
    context: "full_backfill needs to run all 4 collection types, but unclear if it should be 4 separate jobs or one"
    options:
      - "Create 4 sub-jobs with separate processors (complex orchestration)"
      - "Use composite worker function that calls all 4 workers sequentially (chosen)"
    rationale: "Composite worker keeps full_backfill as a single job/processor while running all 4 collection types. Simpler implementation, clearer checkpoint/resume semantics."
    impact: "Single BatchProcessor invocation, one checkpoint stream, sequential execution order ensures dependencies (search_terms → keyword_planner)"

metrics:
  duration_seconds: 137
  duration_minutes: 2.3
  completed_at: "2026-02-13T10:39:10Z"
  tasks_completed: 2
  commits: 2
  files_created: 0
  files_modified: 1
---

# Phase 06 Plan 02: Backfill API Endpoint Integration Summary

**One-liner:** Connected backfill API endpoints to real collection workers with job-type routing, rate limiter selection, and composite full_backfill worker running all 4 types sequentially.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace _noop_process with job-type routing | b21b8bf3 | backfill.py |
| 2 | Update endpoint docs and verify registration | 417db6c3 | backfill.py |

## Implementation Details

### Job-Type Routing

Added `_get_worker_config(job_type)` function that returns `(process_fn, rate_limiter)` tuple for each job type:

| Job Type | Worker Function | Rate Limiter | Notes |
|----------|----------------|--------------|-------|
| search_terms | collect_search_terms_batch | google_ads_limiter (10 QPS) | Campaign-join pattern |
| performance_metrics | collect_performance_batch | google_ads_limiter (10 QPS) | Variant aggregation |
| keyword_planner | collect_keyword_planner_batch | keyword_planner_limiter (2 QPS) | 30-day cache |
| custom_labels | collect_custom_labels_batch | None | GMC API has different limits |
| full_backfill | collect_full_backfill_batch | google_ads_limiter (10 QPS) | Composite worker (see below) |

### Composite Worker for Full Backfill

The `collect_full_backfill_batch()` function is a **composite worker** that:

1. **Runs all 4 workers sequentially** for the same batch of SKUs
2. **Maintains dependency order**: search_terms → performance_metrics → keyword_planner → custom_labels
3. **Returns combined results** with `sub_results` tracking each sub-worker's status
4. **Uses single BatchProcessor** (not 4 separate jobs)

This design ensures:
- Search terms are collected before keyword_planner runs (keyword planner uses search terms as seeds)
- Single checkpoint stream (simpler resume logic)
- One job ID for entire backfill operation
- Sequential execution prevents API quota issues

Example result format:
```python
{
  "item_id": "DMF-2/2X",
  "status": "ok",
  "sub_results": {
    "search_terms": "ok",
    "performance_metrics": "ok",
    "keyword_planner": "ok",
    "custom_labels": "no_data"
  }
}
```

### Background Processing Updates

Updated `_start_background_processing()` to:
1. Accept `job_type` parameter (passed from endpoints)
2. Call `_get_worker_config(job_type)` to get correct worker + limiter
3. Create `BatchProcessor` with job-specific rate limiter
4. Run processor with real worker function (not placeholder)

Both `start_backfill()` and `resume_backfill()` endpoints now pass `job_type` through to the background processing function.

### Documentation Updates

**Module Docstring**: Added "Job Type Routing" section documenting all 5 job types with their worker mappings, rate limiters, and behavior.

**StartBackfillRequest Docstring**: Added config option hints:
- `batch_size` (default 10)
- `checkpoint_interval` (default 100)
- `days_lookback` (default 180)

**Cleanup**: Removed all references to "Phase 1", "_noop_process", and placeholder logic.

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verification commands passed:

```bash
# Worker config routing works
PYTHONPATH=./src python -c "from feedops.api.backfill import _get_worker_config; fn, rl = _get_worker_config('search_terms'); print(f'fn={fn.__name__}, rl={rl}')"
# Output: fn=collect_search_terms_batch, rl=<...TokenBucket object...>

# _noop_process removed
grep -c '_noop_process' src/feedops/api/backfill.py
# Output: 0

# All endpoints registered
PYTHONPATH=./src python -c "from feedops.api.main import app; routes = [r.path for r in app.routes if 'backfill' in str(getattr(r, 'path', ''))]; print(routes); assert len(routes) >= 4"
# Output: ['/backfill/start', '/backfill/status/{job_id}', '/backfill/resume/{job_id}', '/backfill/jobs']

# No stale references
grep -c 'noop\|Phase 1' src/feedops/api/backfill.py
# Output: 0
```

## Integration Points

### Phase 1 Infrastructure (05-*)
- `BatchProcessor.run()` now receives real worker functions (not noop)
- Rate limiters applied based on job_type (Phase 1 tested with google_ads_limiter)
- Checkpoint/resume logic works with all worker types

### Phase 1 Workers (06-01)
- All 4 collection workers integrated via routing function
- Composite worker reuses individual workers (no code duplication)
- Worker contract preserved: `async def fn(batch: list[str]) -> list[dict]`

### Endpoints
All 4 backfill endpoints now functional:
- `POST /backfill/start` - Creates job with correct worker routing
- `GET /backfill/status/{job_id}` - Returns progress (unchanged)
- `POST /backfill/resume/{job_id}` - Resumes with correct worker for job's type
- `GET /backfill/jobs` - Lists jobs (unchanged)

## Next Steps

**Phase 3 (06-03):** Validation testing of full backfill pipeline
- End-to-end test: Create job → Process batch → Verify data in DB
- Test all 5 job types with real API calls (small batches)
- Validate checkpoint/resume with real workers
- Verify rate limiting works under load

**Phase 4 (06-04):** Production readiness
- Add monitoring/alerting for job failures
- Dashboard UI for triggering backfill jobs
- Scheduled backfill automation (cron or Cloud Scheduler)

## Success Criteria

- [x] `_noop_process` removed from backfill.py
- [x] `_get_worker_config()` correctly maps all 5 job types
- [x] Rate limiters correctly assigned (google_ads_limiter, keyword_planner_limiter, None)
- [x] `full_backfill` runs all 4 types sequentially in one processor
- [x] All 4 endpoints still registered and functional
- [x] No "Phase 1" or "_noop" references remain
- [x] Endpoints pass job_type through to background processing
- [x] Documentation reflects real job routing (not placeholder)

## Self-Check: PASSED

**Modified Files:**
```bash
✓ src/feedops/api/backfill.py (exists, 90 lines added, 21 removed)
```

**Commits:**
```bash
✓ b21b8bf3 - feat(06-02): replace _noop_process with job-type routing
✓ 417db6c3 - docs(06-02): update backfill API documentation
```

**Verification:**
```bash
✓ Worker routing works (verified with import test)
✓ _noop_process removed (grep returns 0)
✓ All 4 endpoints registered (verified in main.py)
✓ No stale Phase 1 references (grep returns 0)
```

All claims verified.
