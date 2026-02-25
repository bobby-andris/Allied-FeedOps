---
phase: 30-historical-funnel-persistence
plan: 01
subsystem: api
tags: [supabase, google-ads, cloud-scheduler, funnel-snapshots, cron]

# Dependency graph
requires:
  - phase: 30-00
    provides: "Failing test scaffolds for capture endpoint (auth, upsert, retention)"
provides:
  - "funnel_snapshots_daily table in production Supabase with unique constraint and index"
  - "POST /api/funnel-snapshots/capture endpoint with Bearer auth, upsert, 90-day retention"
  - "Cloud Scheduler setup script for daily 5 AM ET capture"
affects: [30-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bearer CRON_SECRET auth pattern for scheduled API endpoints"
    - "Supabase upsert with onConflict for idempotent daily captures"
    - "Retention cleanup via .delete().lt().select('id') for accurate count"

key-files:
  created:
    - "dashboard/src/app/api/funnel-snapshots/capture/route.ts"
    - "scripts/setup-funnel-scheduler.sh"
    - "supabase/migrations/20260225105102_create_funnel_snapshots_daily.sql"
  modified: []

key-decisions:
  - "Renamed 5 duplicate migration files to DEFERRED pattern to unblock supabase db push"
  - "Used createAdminClient() for Supabase writes (service role, no RLS dependency)"

patterns-established:
  - "CRON_SECRET Bearer auth for Cloud Scheduler endpoints"
  - "90-day retention cleanup with select('id') for accurate deleted count"

requirements-completed: [HIST-01, HIST-02]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 30 Plan 01: Capture Endpoint Summary

**funnel_snapshots_daily table with Bearer-auth capture endpoint persisting daily Google Ads tier data via upsert, 90-day retention cleanup, and Cloud Scheduler setup script**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T10:49:53Z
- **Completed:** 2026-02-25T10:55:19Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments
- funnel_snapshots_daily table created in production Supabase with CHECK constraint, unique constraint, and descending date index
- Capture endpoint passes all 7 test cases: auth rejection, upsert, retention cleanup with accurate rows_deleted, error handling
- Cloud Scheduler setup script with 5 AM ET schedule, retry config, and data settlement advisory

## Task Commits

Each task was committed atomically:

1. **Task 1: Create funnel_snapshots_daily table and capture endpoint** - `b03e480c` (feat)
2. **Task 2: Create Cloud Scheduler setup script** - `103fedba` (chore)

## Files Created/Modified
- `dashboard/src/app/api/funnel-snapshots/capture/route.ts` - POST endpoint: auth check, getLabelTierPerformance call, Supabase upsert, 90-day retention cleanup
- `supabase/migrations/20260225105102_create_funnel_snapshots_daily.sql` - Table DDL with unique constraint and index
- `scripts/setup-funnel-scheduler.sh` - Cloud Scheduler job setup with --delete option

## Decisions Made
- Renamed 5 duplicate local migration files (004, 026x2, 032, 033) to DEFERRED pattern -- they were blocking `supabase db push` because the CLI saw them as "to be inserted before last migration" despite their content already being applied
- Used createAdminClient() (service role) consistent with existing capture-snapshot pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Renamed duplicate migration files to DEFERRED pattern**
- **Found during:** Task 1 (table creation via supabase db push)
- **Issue:** 5 local migration files with non-timestamped names (004, 026x2, 032, 033) blocked `supabase db push` -- CLI required `--include-all` which failed on duplicate version keys
- **Fix:** Renamed to `*b_DEFERRED_*` / `*c_DEFERRED_*` pattern (same as existing 034b/035b) so CLI skips them
- **Files modified:** 5 migration files renamed
- **Verification:** `supabase db push` succeeded, migration applied to production
- **Committed in:** b03e480c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to unblock table creation. No scope creep. Renamed files were pre-existing duplicates already applied under different names.

## Issues Encountered
None beyond the migration rename deviation.

## User Setup Required

**Cloud Scheduler requires manual configuration:**
1. Generate a random UUID for CRON_SECRET
2. Add CRON_SECRET to Vercel environment variables (Dashboard > Settings > Environment Variables)
3. Run: `bash scripts/setup-funnel-scheduler.sh <CRON_SECRET>`
4. Verify: `gcloud scheduler jobs describe feedops-funnel-snapshot-daily --project=bobbys-project-346400 --location=us-east1`

## Next Phase Readiness
- Capture endpoint ready for Plan 02 (trends API and FunnelTrendCards UI)
- Table will accumulate daily data once Cloud Scheduler is configured
- Zero modifications to existing shopping-funnel files (verified via git diff)

## Self-Check: PASSED

- FOUND: capture/route.ts (106 lines, min 40)
- FOUND: setup-funnel-scheduler.sh (66 lines, min 15)
- FOUND: 20260225105102_create_funnel_snapshots_daily.sql
- FOUND: commit b03e480c
- FOUND: commit 103fedba
- funnel_snapshots_daily table verified in production Supabase (via dump)
- All 7 capture.test.ts tests pass

---
*Phase: 30-historical-funnel-persistence*
*Completed: 2026-02-25*
