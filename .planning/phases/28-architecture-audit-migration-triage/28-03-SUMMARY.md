---
phase: 28-architecture-audit-migration-triage
plan: 03
subsystem: database
tags: [supabase, google-ads, null-audit, api-quota, caching, performance-snapshots]

# Dependency graph
requires:
  - phase: 28-architecture-audit-migration-triage
    provides: "RESEARCH.md with join chain mapping and GAQL query inventory"
provides:
  - "NULL rate audit for all publish-performance join chain columns"
  - "Go/no-go decision for feedback view (GO with backfill strategy)"
  - "API quota sustainability verdict (SUSTAINABLE at 1.2% utilization)"
  - "Complete Google Ads API call site catalog (16 GAQL query sites)"
  - "Caching strategy recommendations for TS/Python redundancy"
  - "Phase 29 backfill priorities and NOT NULL enforcement list"
affects: [29-feedback-loop-data-contracts, 30-historical-persistence-daily-snapshots]

# Tech tracking
tech-stack:
  added: []
  patterns: ["write-behind caching for ephemeral API data", "backfill-before-constraint pattern"]

key-files:
  created:
    - ".planning/phases/28-architecture-audit-migration-triage/28-null-audit-and-quota.md"
  modified: []

key-decisions:
  - "Feedback view GO: 99.4% snapshot-to-publish_event linkage justifies building view"
  - "prompt_hash backfillable from generated_content (82.9% coverage)"
  - "performance_impact_scores table does not exist in production -- schema drift"
  - "Daily snapshot capture SUSTAINABLE: ~187 req/day vs 15,000 limit (1.2%)"
  - "service.ts is most wasteful API consumer: 7 queries/2min, no persistence"
  - "Recommend write-behind caching for service.ts in Phase 30 HIST-01"

patterns-established:
  - "Schema audit pattern: query information_schema.columns to verify production vs documentation"
  - "Join chain audit pattern: NULL rate tables with assessment column for each FK"

requirements-completed: [AUDIT-02, AUDIT-04]

# Metrics
duration: 7min
completed: 2026-02-25
---

# Phase 28 Plan 03: NULL Audit & Quota Analysis Summary

**NULL rate audit reveals 99.4% join chain integrity with 2.7% prompt_hash coverage (backfillable to ~95%); API quota analysis confirms daily snapshots at 1.2% of Standard Access limits**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-25T07:35:09Z
- **Completed:** 2026-02-25T07:42:02Z
- **Tasks:** 2/2
- **Files modified:** 1

## Accomplishments

- Audited all join chain columns across `publish_events` (10 columns) and `performance_snapshots` (7 columns) with production SQL data
- Discovered schema drift: `cohort_type` and `product_category` columns missing from production `performance_snapshots`; `performance_impact_scores` table does not exist
- Made GO decision for Phase 29 feedback view with clear backfill roadmap
- Cataloged all 16 Google Ads API call sites across TypeScript and Python layers
- Confirmed daily snapshot capture is sustainable at 1.2% of quota with massive headroom
- Identified service.ts as the most wasteful API consumer and recommended write-behind caching

## Task Commits

Each task was committed atomically:

1. **Task 1: NULL rate audit on publish-performance join chain** - `d752a4f4` (docs)
2. **Task 2: API quota analysis and caching strategy** - `fc5cd648` (docs)

## Files Created/Modified

- `.planning/phases/28-architecture-audit-migration-triage/28-null-audit-and-quota.md` - Combined NULL audit results, go/no-go decision, API quota analysis, and caching strategy recommendations

## Decisions Made

1. **Feedback view: GO** -- 99.4% of performance_snapshots link to publish_events via `publish_event_id`. Even with only 2.7% prompt_hash coverage, the view produces useful content-performance correlation via `master_sku + platform` join.

2. **Backfill strategy for prompt_hash** -- 82.9% of generated_content has `generation_prompt_hash`. A backfill script matching on `(master_sku, platform)` can retroactively populate ~67/69 success publish_events.

3. **Schema drift documented, not fixed** -- `cohort_type`, `product_category` columns and `performance_impact_scores` table are in SCHEMA.md but not in production. Flagged for Phase 29-31 to address.

4. **API quota: no concerns** -- Even with 10x growth, usage stays under 13% of Standard Access limits. Caching recommendations are for latency/efficiency, not quota survival.

5. **service.ts is the priority caching target** -- 7 GAQL queries per context build with 2-minute ephemeral cache, no persistence. Write-behind pattern recommended for Phase 30 HIST-01.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected SQL queries for missing production columns**
- **Found during:** Task 1 (NULL rate audit)
- **Issue:** Plan's Query 2 referenced `cohort_type` and `product_category` columns that do not exist in production `performance_snapshots`
- **Fix:** Removed missing columns from query, documented schema drift as a finding
- **Files modified:** None (queries adjusted in-flight, finding documented in deliverable)
- **Verification:** Queries succeeded after column removal; drift documented in section 1.2

**2. [Rule 1 - Bug] Corrected for non-existent performance_impact_scores table**
- **Found during:** Task 1 (NULL rate audit)
- **Issue:** Plan's Query 4 referenced `performance_impact_scores` which does not exist in production
- **Fix:** Documented as finding; added to schema drift section
- **Files modified:** None (documented in deliverable section 1.3)

---

**Total deviations:** 2 auto-fixed (2 bugs -- schema documentation vs production mismatch)
**Impact on plan:** Both discoveries are valuable audit findings. They strengthen the deliverable by revealing previously unknown schema drift.

## Issues Encountered

- Initial SQL query approach via `exec_sql` RPC failed (function named `execute_sql` in production). Corrected function name and all queries succeeded.
- Join chain Query 3 returned inflated counts due to `generated_content` having multiple rows per (master_sku, platform) -- one for title, one for description. Corrected with DISTINCT counting.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 29 (FEED-01) has clear GO decision with minimum viable join defined
- Backfill priorities documented (P1: prompt_hash, content_version; P2: final_payload_hash; P3: segment_key)
- Phase 30 (HIST-01) has caching strategy ready for service.ts write-behind implementation
- Schema drift findings feed into Phase 31 for cleanup

---
*Phase: 28-architecture-audit-migration-triage*
*Completed: 2026-02-25*
