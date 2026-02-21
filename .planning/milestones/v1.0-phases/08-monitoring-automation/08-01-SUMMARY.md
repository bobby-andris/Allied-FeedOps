---
phase: 08-monitoring-automation
plan: 01
subsystem: monitoring-api
tags: [monitoring, observability, prometheus, api-health]
dependency_graph:
  requires:
    - feedops.observability.metrics (MetricsRegistry)
    - feedops.db.supabase_client (get_client)
    - prometheus_client (REGISTRY, make_asgi_app)
  provides:
    - GET /monitoring/freshness (per-SKU data age)
    - GET /monitoring/coverage (SKU coverage counts)
    - GET /monitoring/api-health (latency p95, error counts)
    - GET /metrics (Prometheus-format metrics)
  affects:
    - feedops.api.main (router inclusion, /metrics mount)
    - feedops.api.backfill (structured logging enhancement)
tech_stack:
  added:
    - prometheus-client: Prometheus metrics export library
  patterns:
    - Efficient SQL aggregation (not per-SKU loops) for freshness queries
    - Structured logging with log_event for job lifecycle events
    - Prometheus ASGI app mounting for external scraping
key_files:
  created:
    - src/feedops/api/monitoring.py: Monitoring API router with 3 endpoints
  modified:
    - src/feedops/api/main.py: Added Prometheus /metrics mount and monitoring router inclusion
    - src/feedops/api/backfill.py: Enhanced with structured log_event calls for job lifecycle
    - pyproject.toml: Added prometheus-client>=0.20 dependency
decisions:
  - title: "RPC execute_sql for freshness queries"
    rationale: "Needed to run custom SQL aggregation for efficient multi-SKU freshness calculation"
    alternatives: ["Build complex Supabase client query chain", "Create RPC function in database"]
    impact: "Enables single-query freshness check for all SKUs instead of N queries"
  - title: "Separate coverage and freshness endpoints"
    rationale: "Freshness is per-SKU (large payload), coverage is aggregate (small payload)"
    alternatives: ["Combined endpoint returning both", "Single /monitoring endpoint with query params"]
    impact: "Dashboard can fetch coverage frequently without transferring large freshness arrays"
  - title: "P95 calculation in Python (not database)"
    rationale: "metrics_registry snapshot already in-memory, no DB query needed"
    alternatives: ["Store metrics in database and calculate via SQL percentile_cont"]
    impact: "Faster response, no additional database load for health checks"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_modified: 4
  lines_added: 345
  commits: 2
  completed_date: "2026-02-13"
---

# Phase 08 Plan 01: Monitoring API & Prometheus Metrics Summary

**One-liner:** Created Python monitoring API endpoints (freshness, coverage, api-health) and mounted Prometheus /metrics endpoint for production observability

## Objective Completion

Created the data layer for dashboard monitoring UI (Plan 02) by implementing:
- **GET /monitoring/freshness**: Per-SKU data age for search_terms, performance, keywords (efficient SQL aggregation)
- **GET /monitoring/coverage**: SKU coverage counts per collection type (total vs. covered)
- **GET /monitoring/api-health**: API latency p95, error counts, rate limit hits from metrics_registry
- **GET /metrics**: Prometheus-format metrics endpoint for external scraping

Enhanced backfill job lifecycle with structured logging (log_event) for Cloud Logging JSON parsing.

## Implementation Details

### Task 1: Monitoring API Router (src/feedops/api/monitoring.py)

Created FastAPI router with 3 monitoring endpoints:

**1. GET /monitoring/freshness**
- Efficient SQL aggregation query (not per-SKU loops)
- Returns age in days for search_terms, performance, keywords per SKU
- Defaults to 999 days for missing data
- Uses LEFT JOIN with variant_index for all SKUs

**2. GET /monitoring/coverage**
- Total distinct master_skus from variant_index
- Count of SKUs with search_queries, performance_baselines, keyword metrics
- 4 separate COUNT DISTINCT queries for each coverage type

**3. GET /monitoring/api-health**
- Extracts metrics from `metrics_registry.snapshot()`
- Calculates p95 latency from sorted timings array (95th percentile index)
- Counts http_request_error_total, provider_error_total, rate_limit errors
- Returns sample_size for context

**Files created:**
- `src/feedops/api/monitoring.py` (238 lines)

**Commit:** `17df2c28`

### Task 2: Prometheus Metrics & Monitoring Router Integration

Modified main.py to:
1. **Mount Prometheus /metrics endpoint**:
   - Added `prometheus-client>=0.20` to pyproject.toml
   - Mounted `make_asgi_app(registry=REGISTRY)` at `/metrics` path
   - Placed after CORSMiddleware but before route definitions
   - Exports default Python process metrics (foundation for future custom metrics)

2. **Include monitoring router**:
   - Imported and included monitoring_router alongside search_insights_router
   - All 3 monitoring endpoints now accessible via FastAPI app

3. **Enhanced backfill job lifecycle logging**:
   - Added structured `log_event` calls to backfill.py:
     - `backfill.job.created`: When job is created with config details
     - `backfill.job.started`: When background processing begins
     - `backfill.job.completed`: When job finishes (includes final status, completed/failed counts)
     - `backfill.job.failed`: When exception occurs during processing
   - All events include `job_id`, `job_type`, `total_items` for Cloud Logging structured parsing

**Files modified:**
- `src/feedops/api/main.py` (+13 lines)
- `src/feedops/api/backfill.py` (+49 lines)
- `pyproject.toml` (+1 dependency)

**Commit:** `9361d0ef`

## Verification Results

All plan verification criteria passed:

1. ✓ `from feedops.api.monitoring import router` succeeds
2. ✓ `from feedops.api.main import app` succeeds (no import errors)
3. ✓ monitoring.py has 3 GET endpoints (freshness, coverage, api-health)
4. ✓ main.py mounts /metrics via make_asgi_app
5. ✓ main.py includes monitoring_router

**Success criteria met:**
- ✓ All 3 monitoring endpoints return structured JSON responses
- ✓ Prometheus /metrics endpoint is mounted and returns metrics in Prometheus text format
- ✓ Structured logging with request_id context is used for key job lifecycle events
- ✓ No per-SKU loops in freshness/coverage queries (SQL aggregation instead)

## Deviations from Plan

None - plan executed exactly as written.

## Output

Created monitoring API foundation for Phase 08 Plan 02 (Dashboard UI integration). Next plan will consume these endpoints to build monitoring dashboard components.

## Self-Check: PASSED

**Files created:**
```bash
[ -f "src/feedops/api/monitoring.py" ] && echo "FOUND: src/feedops/api/monitoring.py"
```
FOUND: src/feedops/api/monitoring.py

**Files modified:**
```bash
git show 17df2c28 --stat | grep monitoring.py
git show 9361d0ef --stat | grep -E "(main.py|backfill.py|pyproject.toml)"
```
src/feedops/api/monitoring.py
src/feedops/api/main.py
src/feedops/api/backfill.py
pyproject.toml

**Commits exist:**
```bash
git log --oneline --all | grep -E "(17df2c28|9361d0ef)"
```
9361d0ef feat(08-01): mount Prometheus /metrics endpoint and include monitoring router in main.py
17df2c28 feat(08-01): create monitoring API router with freshness, coverage, and api-health endpoints

All files and commits verified.
