---
phase: quick-1
plan: 1
subsystem: dashboard-navigation, monitoring-automation
tags: [sidebar, navigation, performance-snapshots, cloud-scheduler, automation]
dependency_graph:
  requires: []
  provides: [sidebar-backfill-link, daily-snapshot-job]
  affects: [dashboard-nav, performance-tracking-automation]
tech_stack:
  added: []
  patterns: [cloud-scheduler-http-job, supabase-rest-api]
key_files:
  created: []
  modified:
    - dashboard/src/components/shared/Sidebar.tsx
decisions:
  - "Use Activity icon for Backfill Monitoring (consistent with monitoring-style icons)"
  - "Schedule snapshot capture at 3am PT (1hr after incremental refresh at 2am)"
  - "Target Vercel endpoint directly — no OIDC needed for public dashboard endpoint"
metrics:
  duration: "10 minutes"
  completed: "2026-02-18"
---

# Quick Task 1: Add Backfill Monitoring to Sidebar + Data Check

**One-liner:** Backfill Monitoring added to sidebar nav with Activity icon; performance_snapshots has 1 test row (181 baselines captured); Cloud Scheduler automates daily captures at 3am PT.

## Tasks Completed

| Task | Name | Commit | Result |
|------|------|--------|--------|
| 1 | Add Backfill Monitoring to sidebar | `7bbb1e26` | Sidebar updated, build passes |
| 2 | Check performance_snapshots data | n/a (data check) | 1 snapshot, 181 baselines |
| 3 | Create Cloud Scheduler job | n/a (infrastructure) | Job ENABLED at 3am PT |

## Task 1: Sidebar Change

**File modified:** `dashboard/src/components/shared/Sidebar.tsx`

**Changes:**
1. Added `Activity` to the `lucide-react` import block
2. Inserted `{ name: 'Backfill Monitoring', href: '/backfill', icon: Activity }` between `Search Insights` and `Settings`

**Final navigation order:** Overview, Generate, Review Queue, Competitors, Batches, Performance, Search Insights, Backfill Monitoring, Settings

**Build verification:** `cd dashboard && npm run build` — passed with zero TypeScript errors. `/backfill` route confirmed to exist (shown in route list during build).

## Task 2: Performance Snapshots Data State

### Query Results

**Query 1 — Row count and date range:**

| Metric | Value |
|--------|-------|
| total_snapshots | 1 |
| distinct_skus | 1 |
| earliest_snapshot | 2026-02-03 08:24:18 UTC |
| latest_snapshot | 2026-02-03 08:24:18 UTC |

**Query 2 — Platform breakdown:**

| platform | snapshot_count |
|----------|---------------|
| google | 1 |

**Query 3 — Days since publish distribution:**

| days_since_publish | count |
|--------------------|-------|
| (no rows — `days_since_publish` is NULL for the 1 existing row) | — |

**Additional — Single snapshot detail:**

| master_sku | platform | snapshot_date | days_since_publish | impressions | clicks | ctr |
|------------|----------|--------------|-------------------|-------------|--------|-----|
| 1051 | google | 2025-12-31 | NULL | 320 | 2 | 0.00625 |

**Additional — performance_baselines:**

| total_baselines | distinct_skus |
|-----------------|---------------|
| 181 | 89 |

### Interpretation

- **Snapshots are sparse:** Only 1 snapshot exists, captured during initial testing on 2026-02-03. This is a single test row for master_sku `1051`.
- **`days_since_publish` is NULL:** The snapshot was captured before the publish event tracking was wired up, so days_since_publish couldn't be calculated.
- **Baselines are much richer:** 181 baseline records across 89 distinct SKUs — these are the pre-publish 30-day metrics captured during the content generation pipeline.
- **Automated collection needed:** The Cloud Scheduler job (Task 3) will begin populating real snapshot data starting 2026-02-19 at 3am PT.

### Column Name Note (Deviation — Rule 1 Auto-fix)

The plan referenced `captured_at` as the timestamp column. The actual column is `fetched_at` (per live schema introspection). Queries were corrected inline. No code change was needed since this was a data-check-only task.

## Task 3: Cloud Scheduler Job

**Command run:**
```bash
gcloud scheduler jobs create http feedops-daily-snapshot-capture \
  --project=bobbys-project-346400 \
  --location=us-east1 \
  --schedule="0 3 * * *" \
  --time-zone="America/Los_Angeles" \
  --uri="https://allied-feed-ops.vercel.app/api/performance/capture-snapshot" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{}' \
  --description="Daily performance snapshot capture for all published SKUs" \
  --attempt-deadline=30m
```

**Job created successfully:**
```
name: projects/bobbys-project-346400/locations/us-east1/jobs/feedops-daily-snapshot-capture
schedule: 0 3 * * *
timeZone: America/Los_Angeles
state: ENABLED
attemptDeadline: 1800s
scheduleTime: 2026-02-19T11:00:00Z (next run = 3am PT Feb 19)
```

**All scheduler jobs (verified):**

| ID | Schedule | State |
|----|---------|-------|
| feedops-daily-incremental-refresh | 0 2 * * * (America/Los_Angeles) | ENABLED |
| feedops-daily-snapshot-capture | 0 3 * * * (America/Los_Angeles) | ENABLED |

**Timing:** Snapshot capture runs 1 hour after the incremental refresh (2am PT), ensuring fresh search/performance data is available before snapshots are taken.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected column name `captured_at` → `fetched_at`**
- **Found during:** Task 2
- **Issue:** Plan specified `captured_at` for timestamp queries on `performance_snapshots`. Actual column is `fetched_at` (confirmed via schema introspection).
- **Fix:** Corrected SQL query inline. Data-check-only task — no code changes needed.
- **Files modified:** None (no code change)
- **Commit:** None required

## Success Criteria Verification

- [x] Backfill Monitoring is accessible from sidebar navigation at /backfill
- [x] Performance snapshots data state is known (1 snapshot, 1 SKU, google platform only, captured 2026-02-03)
- [x] Cloud Scheduler job automates daily snapshot capture at 3am PT
- [x] Dashboard build passes with zero TypeScript/lint errors

## Self-Check: PASSED

- FOUND: dashboard/src/components/shared/Sidebar.tsx
- FOUND: 1-SUMMARY.md
- FOUND: commit 7bbb1e26 (feat(quick-1): add Backfill Monitoring to sidebar navigation)
- FOUND: Activity import in Sidebar.tsx
- FOUND: Backfill Monitoring nav entry in Sidebar.tsx
- FOUND: href: '/backfill' in Sidebar.tsx
- FOUND: feedops-daily-snapshot-capture Cloud Scheduler job (ENABLED)
