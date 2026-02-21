# Backfill Pipeline Debug Document — 2026-02-20

## STATUS: ALL RUNNING JOBS KILLED. PIPELINE IS BROKEN.

**Purpose**: This document captures everything known about the recurring backfill pipeline failures so a Codex session can diagnose and fix the root cause.

---

## The Core Problem

The performance metrics backfill job (`/backfill/start`) cannot complete processing 2,784 SKUs. Every attempt dies silently after processing only ~100 SKUs (~10 batches), leaving the job status as "running" in the database with no further progress.

**This has happened 3 times now:**
1. Job `2c738140` (Phase 16-01 era): Killed at 90/2784 by Cloud Run redeployment
2. Job `bd3665f0`: Failed at 0/2784
3. Job `3da77cd6` (Phase 16-02 era): Stuck at 100/2784 for 4+ hours — background thread died silently

## Current State (as of 2026-02-20 04:20 UTC)

- **All running jobs: KILLED** (marked `failed` in database)
- **performance_baselines: 189 distinct SKUs** (out of 2,784 target)
- **search_queries: ~179,526 rows** (this part works — 8 date windows completed successfully)
- **No active processes on Cloud Run** related to backfill

## Architecture Overview

```
Dashboard or curl → POST /backfill/start → Cloud Run (main.py)
  → Creates job record in backfill_jobs table (status: 'creating')
  → Calls run_async_in_thread(_start_background_processing, ...)
    → Non-daemon thread with new asyncio event loop
    → BatchProcessor.run() processes items in batches of 10
      → Each batch: collect_performance_batch(batch_skus)
        → Looks up offer IDs from variant_index for each SKU
        → Detects multi-SKU families
        → Calls fetch_batch_product_performance(offer_ids, ...)
          → Chunks offer IDs into groups of 25
          → Runs GAQL query per chunk via ThreadPoolExecutor(5 workers)
          → Aggregates results by product_id → master_sku
        → Validates and upserts to performance_baselines
```

## Key Files

| File | What it does |
|------|-------------|
| `src/feedops/api/main.py:175-201` | `run_async_in_thread()` — spawns non-daemon thread with asyncio loop |
| `src/feedops/api/backfill.py:424-510` | `start_backfill()` — creates job, calls `run_async_in_thread` |
| `src/feedops/api/backfill.py:272-340` | `_start_background_processing()` — routes to worker, creates BatchProcessor |
| `src/feedops/jobs/processor.py:81-249` | `BatchProcessor.run()` — batch loop with checkpointing, retry, progress |
| `src/feedops/jobs/workers.py:195+` | `collect_performance_batch()` — the actual per-batch worker |
| `src/feedops/integrations/google_ads_performance.py:370-440` | `fetch_batch_product_performance()` — parallel GAQL chunk queries |
| `src/feedops/jobs/manager.py` | Job CRUD operations (get_job, update_status, save_checkpoint, etc.) |

## Known Failure Mode: Cloud Run Redeployment Kills Background Threads

**Documented in CLAUDE.md and confirmed for job `3da77cd6`.**

Timeline for job `3da77cd6`:
- `00:00:40` — Job created and background thread started
- `00:12:25` — Cloud Build deployment triggered (by code push from Phase 16-02)
- `00:17:54` — New Cloud Run revision deployed, old container receives SIGTERM
- `00:17:55` — New container processes batch 11 (items 100-109) — ONE batch on new container
- `00:18:02` — Batch 11 completes. **No further processing logs ever appear.**
- `04:17+` — Job still shows status "running" with 100/2784 completed

**The thread was killed by the container shutdown/replacement.** The new container doesn't know about the old thread's job. The job record stays "running" forever.

### Why `run_async_in_thread` Doesn't Survive Deployments

```python
def run_async_in_thread(async_func, request_id=None, **kwargs):
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(async_func(**kwargs))
        finally:
            loop.close()

    thread = threading.Thread(target=wrapper, daemon=False)
    thread.start()
    return thread
```

The `daemon=False` flag means the thread won't be killed when the main thread exits — but **Cloud Run SIGTERM kills the entire process**, including non-daemon threads. The thread has no signal handler and no graceful shutdown hook.

## Suspected Additional Issue: Thread Silently Dies Even Without Deployment?

**The one-batch-then-silence pattern needs investigation.** After the new container processed batch 11 at 00:18:02, there should have been batch 12, 13, etc. But nothing happened. Possible causes:

1. **The new container didn't resume the thread** — because `run_async_in_thread` is called in the HTTP handler. When the old container died, the thread died with it. The new container only knows about the job because the DB record exists, but nobody called `run_async_in_thread` again.

2. **The batch 11 log at 00:18:02 was actually from the OLD container's last gasp** — old containers get a grace period before SIGTERM. This would mean the new container never ran any batch at all.

3. **There's a thread crash we're not seeing** — unhandled exceptions in `run_async_in_thread` threads are silently swallowed because they run in a separate thread with no exception propagation.

## Questions for Codex to Investigate

### Q1: What happens to `run_async_in_thread` when Cloud Run replaces a container?

The thread runs in the OLD container's process space. When the old container receives SIGTERM:
- Does the process get killed immediately?
- Does the non-daemon thread get any chance to finish?
- Is there a `SIGTERM` handler that could set a shutdown flag?

**Look at**: `src/feedops/api/main.py` for any `signal` handling or shutdown hooks.

### Q2: Why did batch 11 log appear at 00:18:02 (4 seconds AFTER the new revision deployed at 00:17:54)?

This suggests the old container was still alive briefly. Investigate Cloud Run's request draining / container shutdown lifecycle.

### Q3: Is the BatchProcessor properly handling thread death?

**Look at** `src/feedops/jobs/processor.py:81-249` — the `BatchProcessor.run()` method. If the thread dies mid-batch:
- The job status stays "running" forever
- The checkpoint data shows `batch_index: 100` (last successful save)
- There's no watchdog or timeout to detect stale "running" jobs

### Q4: Could we use Cloud Run Jobs instead of background threads?

Cloud Run **Jobs** (not Services) are designed for long-running batch work. They don't get killed by redeployments. This might be the right architecture.

### Q5: Could we add a `/backfill/resume/{job_id}` self-healing mechanism?

The resume endpoint already exists (`src/feedops/api/backfill.py:560+`). A Cloud Scheduler cron could:
1. Check for "running" jobs older than 30 minutes with no progress
2. Call `/backfill/resume/{job_id}` to restart from checkpoint
3. This would auto-heal after deployments

### Q6: What about the search_query_sync_jobs running fine?

The search terms sync (`/search-insights/sync`) completed 8 date windows successfully (179,526 rows). Why does this work but backfill doesn't?

**Key difference**: Search term sync windows are smaller, independent operations. Each window takes ~2-3 minutes. A deployment between windows just stops; you can restart the next window. The performance backfill is ONE GIANT JOB running 2,784 SKUs sequentially in a single thread — if the thread dies, everything dies.

## Data State

```
performance_baselines: 189 distinct master_skus (target: ~2,000+ with Google Ads activity)
search_queries: ~179,526 rows across 8 date windows (Aug 2025 - Feb 2026)
backfill_jobs: All in terminal status (failed/complete). No running jobs.
search_query_sync_jobs: All in terminal status.
```

## Potential Solutions (for Codex to evaluate)

### Option A: Cloud Run Jobs (Best long-term)
Move backfill processing to Cloud Run Jobs, which are designed for batch work and don't get killed by service redeployments.

### Option B: Self-healing resume cron
Add Cloud Scheduler that detects stale "running" jobs and calls `/backfill/resume/{job_id}`. The checkpoint system already works (batch_index=100 was saved). This is the quickest fix.

### Option C: Smaller, independent jobs
Instead of one 2,784-SKU job, split into many smaller jobs (50-100 SKUs each). Each completes fast enough to survive between deployments. Similar to how search terms windows work.

### Option D: Add SIGTERM handler
Register a signal handler in `main.py` that catches SIGTERM, sets a shutdown flag, and lets the current batch complete + save checkpoint + update job status to "partial". Then resume picks up where it left off.

### Option E: External orchestration
Use Cloud Scheduler or Cloud Tasks to enqueue individual batches as separate HTTP requests. Each request processes 10 SKUs and returns. No long-running background threads needed.

## Reproduction Steps

```bash
# Start a performance backfill
curl -X POST https://feedops-pipeline-623866089882.us-east1.run.app/backfill/start \
  -H "Content-Type: application/json" \
  -d '{"job_type": "performance_metrics", "skus": ["101","1016","101A"], "config": {"batch_size": 10, "force_backfill": true, "days_lookback": 180}}'

# Watch logs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="feedops-pipeline" AND textPayload=~"batch|Batch|Processing|Job"' --project=bobbys-project-346400 --limit=20 --format="value(timestamp,textPayload)"

# Check job status
curl https://feedops-pipeline-623866089882.us-east1.run.app/backfill/jobs | python3 -m json.tool

# The job will process a few batches then silently stop (especially if a deploy happens)
```

## Environment

- **Cloud Run service**: `feedops-pipeline` in `bobbys-project-346400`
- **Region**: `us-east1`
- **Container**: Python 3.11 + FastAPI + uvicorn
- **Supabase project**: `qezuszwufortkiutlhym`
- **Google Ads customer ID**: `6253381786`
- **Code repo**: `/Users/bobby/Documents/GitHub/Allied-FeedOps`
- **Python pipeline**: `src/feedops/`
