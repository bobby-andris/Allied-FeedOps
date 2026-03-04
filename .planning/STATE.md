---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Dead Code Cleanup + Data Infrastructure
status: planning
stopped_at: Completed 08.1-01-PLAN.md
last_updated: "2026-03-04T03:12:56.220Z"
last_activity: "2026-03-04 — Phase 8 complete: migration 042 applied, daily snapshot job verified (1,866 rows, 622 SKUs)"
progress:
  total_phases: 14
  completed_phases: 6
  total_plans: 19
  completed_plans: 14
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.
**Current focus:** Phase 8.1 — Data Model Gap Audit (INSERTED — urgent requirements audit before continuing v1.1)

## Current Position

Phase: 8.1 (Data Model Gap Audit — inserted after Phase 8)
Plan: 01 complete — 02 next
Status: In progress
Last activity: 2026-03-04 — Phase 8.1 Plan 01 complete: offer ID utility created (13 tests), migration 043 applied (variant performance tables)

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 1 (v1.1)
- Average duration: 30 min
- Total execution time: 0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 08-schema-hardening | 1 | 30 min | 30 min |
| Phase 08.1-data-model-gap-audit P03 | 2 | 1 tasks | 1 files |
| Phase 08.1-data-model-gap-audit P01 | 3 | 2 tasks | 4 files |

## Accumulated Context
| Phase 08-schema-hardening P01 | 11 | 1 tasks | 1 files |
| Phase 08-schema-hardening P01 | 30 | 2 tasks | 1 files |

### Roadmap Evolution
- Phase 8.1 inserted after Phase 8: Data Model Gap Audit (URGENT) — variant-level performance data discarded during aggregation, potential other granularity mismatches across Google Ads/Merchant Center/Shopify data flows. Phase 12 requirements (ENTM-01 through DATA-03) absorbed into audit scope.

### From v1.0 (Pipeline Reliability Rewrite + Model Evaluation)
- main.py decomposed: 3,737 → ~500 lines, 9 extracted modules
- All 5 GPT-5.2 bugs fixed; Claude Sonnet 4.6 in production (84% cheaper, 2x faster)
- 98% human approval rate on generated Google content
- Deploy checklist created as mandatory pre-push workflow
- Phase 7 (Bing fix) deferred — 96 SKUs need regeneration, tracked as v2 requirement

### Key Decisions (v1.1)
- Dead code before data infra: Low-risk cleanup reduces noise before schema changes
- variant_index as entity hub: 72K rows, central to all cross-platform mapping
- Upsert semantics: Use `ignore_duplicates=True` for snapshots (first-write-wins; historical data must not be overwritten)
- Test-import update BEFORE re-export removal: Never remove a symbol before updating all test imports
- Phase 8: FK already existed as performance_snapshots_publish_event_id_fkey — SCHM-04 guard updated to check ANY FK on column to prevent duplicate creation
- Phase 8: Orphaned publish_event_id rows NULLed rather than deleted — metrics data preserved
- Phase 8: Unique constraint columns (master_sku, platform, environment, snapshot_date) match performance_impact.py:461 on_conflict parameter exactly
- Phase 8.1-01: normalize_offer_id() uses .lower() — simple, safe, idempotent; to_gmc_format() uses .replace() — targeted, idempotent at publish boundary only
- Phase 8.1-01: Unique constraint columns (gmc_offer_id, platform, environment, snapshot_date) match on_conflict parameter Plan 02 will use exactly
- Phase 8.1-01: Supabase keychain token format is go-keyring-base64:{b64} — split on colon before decoding

### Blockers/Concerns
- Phase 9/11 ordering critical: DEAD-02 (test imports) must precede DEAD-03 (re-export removal) and DEAD-04 (generator.py cleanup)
- Phase 12 pre-condition: ENTM-01 (offer ID normalization) must be applied before DATA-01 (bulk backfill) runs
- Phase 12 quota risk: 2,500 SKU backfill consumes ~19% of Google Ads daily quota in one shot — 50-SKU test gate required first
- Slack webhook binding: Verify `SLACK_WEBHOOK_URL` is bound to current Cloud Run revision before declaring Phase 8 complete

## Session Continuity

Last session: 2026-03-04T03:12:56.218Z
Stopped at: Completed 08.1-01-PLAN.md
Resume file: None
