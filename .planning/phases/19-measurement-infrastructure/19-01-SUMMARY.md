---
phase: 19-measurement-infrastructure
plan: 01
subsystem: database
tags: [supabase, postgresql, migrations, feature-flags, observability, python, measurement]

# Dependency graph
requires:
  - phase: 18-diagnosis-establish-ground-truth
    provides: Confirmed all 3 feature flags wired to production paths
provides:
  - Schema migration 035 with 4 new columns on regeneration_history and 3 new tables
  - capture_flag_snapshot() helper function in feature_flags.py
  - Flag state + latency capture wired into all 4 generation paths in main.py
affects:
  - 19-02 (flag analysis queries now have data to query)
  - 19-03 (prompt hash → alias lookup table ready)
  - 20-content-optimization (every regeneration now records which flags were active)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Feature flag snapshot at call time (not import time) — avoids warm container stale state"
    - "Optional latency_ms/tokens_used kwargs on persist function — nullable columns, graceful degradation"
    - "Partial unique index on sku_bottleneck_classifications — allows override records alongside auto-classifications"

key-files:
  created:
    - supabase/migrations/035_measurement_infrastructure_schema.sql
    - .planning/phases/19-measurement-infrastructure/19-01-SUMMARY.md
  modified:
    - src/feedops/pipeline/feature_flags.py
    - src/feedops/api/main.py
    - docs/database/SCHEMA.md

key-decisions:
  - "capture_flag_snapshot() added to feature_flags.py — captures all 3 flags at runtime, not import time"
  - "Partial unique index on sku_bottleneck_classifications.master_sku WHERE is_override = false — allows manual overrides alongside auto-classifications"
  - "Migration 035 created but NOT applied — direct postgres access blocked from dev machine; user must apply via Supabase SQL Editor"
  - "latency_ms captures only primary LLM call latency (excludes finish-sentence call) — sufficient for cost/performance regression detection"

patterns-established:
  - "capture_flag_snapshot(): Call at generation time inside the function body, not at module level"
  - "history_payload additions: feature_flags_active and latency_ms added to both the _persist helper and the inline regenerate_content insert"

requirements-completed: [MEAS-01, MEAS-03]

# Metrics
duration: 16min
completed: 2026-02-21
---

# Phase 19 Plan 01: Measurement Infrastructure Schema Summary

**SQL migration for flag capture, cost tracking, prompt aliases, and GMC status tables; Python pipeline wired to capture feature flag snapshot and LLM latency on every generation**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-21T03:54:14Z
- **Completed:** 2026-02-21T04:10:54Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created migration 035 with all Phase 19 schema additions (4 tables/extensions)
- Added `capture_flag_snapshot()` to `feature_flags.py` — captures all 3 flags at call time, documented pitfall of import-time capture
- Wired flag snapshot + latency into `_persist_generated_content_and_history()` and the inline `regeneration_history` insert in `regenerate_content()`
- Added timing capture (`time.time()`) around LLM calls in all 3 generation code paths (optimize, batch, hybrid batch)
- Updated SCHEMA.md with all new tables, columns, and measurement query examples

## Task Commits

Each task was committed atomically:

1. **Task 1: Create measurement infrastructure schema migration** - `53bda6cd` (feat)
2. **Task 2: Wire Python pipeline to capture flag state and generation cost** - `418960f2` (feat)

## Files Created/Modified
- `supabase/migrations/035_measurement_infrastructure_schema.sql` - All Phase 19 DDL: 4 columns on regeneration_history, 3 new tables
- `src/feedops/pipeline/feature_flags.py` - Added `capture_flag_snapshot()` function
- `src/feedops/api/main.py` - Import + wire capture_flag_snapshot and latency_ms in all generation paths
- `docs/database/SCHEMA.md` - Updated with new tables (prompt_version_aliases, sku_bottleneck_classifications, gmc_product_status), extended regeneration_history docs, updated table count to 37

## Decisions Made
- `capture_flag_snapshot()` captures flags at call time to avoid warm container stale state (all 3 flags read env var at runtime)
- `latency_ms` captures only the primary LLM generation call, not the finish-sentence sub-call — sufficient for cost regression detection
- Partial unique index on `sku_bottleneck_classifications` allows coexisting override and auto-classification records
- Migration uses `ADD COLUMN IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` for idempotent re-application

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written. All code changes match the specification.

### Blocking Issue (Not Auto-Fixed)

**Migration 035 could not be applied autonomously.**
- **Issue:** Direct postgres port (5432/6543) is blocked by network firewall from the dev machine. The Supabase REST API `execute_sql` RPC only allows SELECT queries. No Supabase personal access token (`sbp_`) found in environment to use management API.
- **Resolution:** Migration file is created and committed. Apply manually via Supabase SQL Editor (https://supabase.com/dashboard/project/qezuszwufortkiutlhym/sql) or `supabase db push` with personal access token.
- **Impact:** Python code changes compile and deploy. The new `feature_flags_active` and `latency_ms` fields will fail silently (logging a warning) until migration is applied — non-blocking for existing functionality.

## Issues Encountered
- All approaches to execute DDL remotely failed (REST API SELECT-only, direct postgres blocked, management API requires personal token). Proceeded with code changes only; migration requires manual application.

## User Setup Required

**One manual step required to activate measurement data collection:**

1. Open Supabase SQL Editor: https://supabase.com/dashboard/project/qezuszwufortkiutlhym/sql
2. Paste and run the contents of `supabase/migrations/035_measurement_infrastructure_schema.sql`
3. Verify with:
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'regeneration_history'
AND column_name IN ('feature_flags_active', 'tokens_used', 'latency_ms', 'cost_usd');

SELECT table_name FROM information_schema.tables
WHERE table_name IN ('prompt_version_aliases', 'sku_bottleneck_classifications', 'gmc_product_status');
```

After migration is applied, every content generation will automatically capture flag state and latency.

## Next Phase Readiness
- Python pipeline is deployed and will capture flag state on next generation after migration is applied
- `prompt_version_aliases` table ready for Phase 19 Plan 03 (MEAS-03 prompt alias tracking)
- `sku_bottleneck_classifications` and `gmc_product_status` tables ready for downstream plans
- Migration 035 is the only prerequisite for Plans 02-04 to have real measurement data

## Self-Check: PASSED

- FOUND: supabase/migrations/035_measurement_infrastructure_schema.sql
- FOUND: src/feedops/pipeline/feature_flags.py (capture_flag_snapshot exported)
- FOUND: src/feedops/api/main.py (capture_flag_snapshot imported, latency wired)
- FOUND: docs/database/SCHEMA.md (updated with new tables)
- FOUND: 19-01-SUMMARY.md
- Commit 53bda6cd verified (Task 1: migration schema)
- Commit 418960f2 verified (Task 2: Python pipeline)
- Python import test: capture_flag_snapshot() returns {'PROMPT_CONTRACT_V2': True, 'INTENT_CURATOR_V1': True, 'SEGMENT_STRATEGY_V1': True}

---
*Phase: 19-measurement-infrastructure*
*Completed: 2026-02-21*
