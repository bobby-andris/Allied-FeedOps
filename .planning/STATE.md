---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Dead Code Cleanup + Data Infrastructure
status: executing
stopped_at: Completed 08.1-02-PLAN.md
last_updated: "2026-03-04T03:23:13.875Z"
last_activity: "2026-03-04 — Phase 8.1 Plan 01 complete: offer ID utility created (13 tests), migration 043 applied (variant performance tables)"
progress:
  total_phases: 14
  completed_phases: 6
  total_plans: 19
  completed_plans: 15
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.
**Current focus:** Phase 8.1 — Data Model Gap Audit (INSERTED — urgent requirements audit before continuing v1.1)

## Current Position

Phase: 8.1 (Data Model Gap Audit — inserted after Phase 8)
Plan: 02 complete — 03 next
Status: In progress
Last activity: 2026-03-04 — Phase 8.1 Plan 02 complete: offer ID normalization applied to 4 codepaths (ENTM-02), variant snapshot dual-write wired to performance_snapshots_variant

Progress: [████████░░] 79%

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
| Phase 08.1-data-model-gap-audit P02 | 8 | 2 tasks | 4 files |

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
- Phase 8.1-02: normalize_offer_id() applied at ingestion boundary in _fetch_chunk_data() and offer_to_sku construction — all downstream dict keys are normalized before any DB lookup
- Phase 8.1-02: variant snapshot upsert uses ignore_duplicates=False (standard upsert) — re-runs for same day update the row; zero-impression rows skipped per locked decision
- Phase 8.1-02 (ENTM-02 COMPLETE): All 4 Python codepaths now use normalize_offer_id() from shared utility

### Blockers/Concerns
- Phase 9/11 ordering critical: DEAD-02 (test imports) must precede DEAD-03 (re-export removal) and DEAD-04 (generator.py cleanup)
- Phase 12 pre-condition: ENTM-01 (offer ID normalization) must be applied before DATA-01 (bulk backfill) runs
- Phase 12 quota risk: 2,500 SKU backfill consumes ~19% of Google Ads daily quota in one shot — 50-SKU test gate required first
- Slack webhook binding: Verify `SLACK_WEBHOOK_URL` is bound to current Cloud Run revision before declaring Phase 8 complete

## Session Continuity

Last session: 2026-03-04T03:23:13.872Z
Stopped at: Completed 08.1-02-PLAN.md
Resume file: None
