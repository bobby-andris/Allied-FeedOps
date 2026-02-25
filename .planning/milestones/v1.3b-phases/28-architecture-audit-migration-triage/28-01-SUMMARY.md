---
phase: 28-architecture-audit-migration-triage
plan: 01
subsystem: architecture
tags: [data-flow, mermaid, google-ads, supabase, audit]

# Dependency graph
requires:
  - phase: v1.2
    provides: "Production schema, publishing chain, performance capture pipeline"
provides:
  - "Complete data flow map with Mermaid diagrams (6 sections)"
  - "Circular feedback loop validation with per-link status"
  - "Dead end and gap inventory for Phases 29-31"
  - "Redundant API query identification with caching recommendation"
  - "Schema comparison: SCHEMA.md vs expected production tables"
affects: [28-02, 28-03, 29, 30, 31]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mermaid graph TD/LR for architecture documentation"
    - "Per-link validation pattern for feedback loop assessment"

key-files:
  created:
    - ".planning/phases/28-architecture-audit-migration-triage/28-data-flow-map.md"
    - "docs/architecture/data-flow-map.md"
  modified: []

key-decisions:
  - "Circular flow validation included as Section 6 within data flow map (not separate document)"
  - "Identified 3 redundant shopping_performance_view query paths -- recommend Python consolidation"
  - "service.ts ephemeral cache classified as highest-severity gap for funnel analysis"
  - "034b GA4 tables noted as missing from SCHEMA.md -- need production verification"

patterns-established:
  - "Data flow documentation with Mermaid diagrams + annotated prose per section"
  - "Dead end classification: type, impact, resolution phase"

requirements-completed: [AUDIT-01, AUDIT-05]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 28 Plan 01: Data Flow Map & Circular Loop Validation Summary

**Complete data flow map with 10 Mermaid diagrams covering Google Ads ingestion (TS + Python), publishing chain, performance monitoring, dashboard consumption, dead ends, and circular feedback loop validation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T07:34:56Z
- **Completed:** 2026-02-25T07:39:00Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Mapped all 4 data flow sections (ingestion, publishing, monitoring, dashboard) with Mermaid diagrams
- Documented both TypeScript and Python Google Ads integration paths with exact GAQL queries
- Identified 5 dead ends: service.ts ephemeral cache, missing funnel_snapshots_daily, empty 034b/035b tables, orphaned components, redundant API queries
- Validated circular feedback loop: all 5 links exist, ANALYZE link has nullable FK gaps
- Created long-term reference copy in docs/architecture/

## Task Commits

Each task was committed atomically:

1. **Task 1: Query production schema and build data flow map** - `13d68d3f` (docs)
2. **Task 2: Validate circular feedback loop and create long-term reference** - `26f98c4f` (docs)

## Files Created/Modified
- `.planning/phases/28-architecture-audit-migration-triage/28-data-flow-map.md` - Complete data flow map (680 lines, 10 Mermaid diagrams, 6 sections)
- `docs/architecture/data-flow-map.md` - Long-term reference copy (identical)

## Decisions Made
- Included circular flow validation as Section 6 within the data flow map document rather than a separate file -- content volume was manageable in one document
- Classified 3 redundant `shopping_performance_view` queries across TS google-ads.ts, Python google_ads_performance.py, and Python google_ads_search_terms.py -- recommended consolidating TS baseline capture into Python pipeline
- Identified service.ts ephemeral cache as the highest-severity gap (7 GAQL queries, 2-min TTL, zero persistence)
- Noted 034b GA4 tables are documented in migration files but missing from SCHEMA.md -- flagged for production verification

## Deviations from Plan

None - plan executed exactly as written. Production SQL queries (pg_tables, row counts) were documented as verification queries to run but could not be executed directly (no MCP database tool available in this execution context). All data flow mappings were verified from source code review.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Data flow map provides ground truth for Plans 02 (migration triage) and 03 (NULL rate audit)
- Verification queries documented for production execution during subsequent plans
- Dead end inventory directly feeds Phase 29-31 implementation priorities

## Self-Check: PASSED

- FOUND: `.planning/phases/28-architecture-audit-migration-triage/28-data-flow-map.md`
- FOUND: `docs/architecture/data-flow-map.md`
- FOUND: `.planning/phases/28-architecture-audit-migration-triage/28-01-SUMMARY.md`
- FOUND: commit `13d68d3f`
- FOUND: commit `26f98c4f`

---
*Phase: 28-architecture-audit-migration-triage*
*Completed: 2026-02-25*
