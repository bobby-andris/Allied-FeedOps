---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Dead Code Cleanup + Data Infrastructure
status: executing
stopped_at: Completed 12-shared-utils-extraction/12-01-PLAN.md
last_updated: "2026-03-04T08:07:43.005Z"
last_activity: "2026-03-04 — Phase 12 Plan 01 complete: _require_request_id and GenerationBudgetExceededError extracted to feedops/api/utils.py; duplicates removed from persistence.py, job_management.py, generator.py"
progress:
  total_phases: 13
  completed_phases: 11
  total_plans: 25
  completed_plans: 22
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** The pipeline produces high-quality product content reliably at scale, backed by accurate performance data that maps seamlessly across Google Ads, Shopify, and Merchant Center.
**Current focus:** Phase 8.1 — Data Model Gap Audit (INSERTED — urgent requirements audit before continuing v1.1)

## Current Position

Phase: 12 (Shared Utils Extraction) — COMPLETE
Plan: 01 complete — Phase 12 done, all dead code cleanup complete (DEAD-06 satisfied)
Status: In progress
Last activity: 2026-03-04 - Completed quick task 1: Execute comprehensive dashboard UAT test plan with agent-browser

Progress: [█████████░] 88%

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
| Phase 08.1-data-model-gap-audit P04 | 10 | 1 tasks | 1 files |
| Phase 08.1-data-model-gap-audit P04 | 45 | 2 tasks | 1 files |
| Phase 09-trivial-dead-code-removal P01 | 4 | 2 tasks | 4 files |
| Phase 09-trivial-dead-code-removal P02 | 15 | 2 tasks | 4 files |
| Phase 10-image-wiring P01 | 12 | 2 tasks | 2 files |
| Phase 11-test-import-cleanup-re-export-removal P01 | 13 | 2 tasks | 6 files |
| Phase 11 P02 | 5 | 1 tasks | 2 files |
| Phase 12-shared-utils-extraction P01 | 7 | 2 tasks | 7 files |

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
- Phase 10-01: fetch_image called once at bundle level before task loop — single network call efficiency
- Phase 10-01: Finish tasks always receive image=None — finish sentences are text-only by design
- Phase 10-01: Image forwarded via existing inspect.signature pattern in _generate_with_provider_compat — consistent with reasoning_effort/max_completion_tokens forwarding
- Phase 11-01: get_request_id monkeypatches for job_runner tests patch at feedops.api.job_management (where _resolve_execution_request_id resolves the name), not api_job_runner directly
- Phase 11-01: test_query_intent_lineage.py migrated as Rule 1 auto-fix — not in DEAD-02 list but relied on re-export block (broke when block was removed)
- Phase 11-02: executor.py is the canonical location for _platform_reasoning_effort and _platform_completion_cap — generator.py no longer re-defines them (DEAD-04 complete)
- Phase 12-01: feedops/api/utils.py is the canonical location for _require_request_id and GenerationBudgetExceededError — generator.py imports from utils (linear chain, not circular); DEAD-06 complete
- Phase 12-01: No re-export in job_management.py for _require_request_id — all callers import directly from feedops.api.utils; test_job_management_smoke.py updated accordingly

### Blockers/Concerns
- Phase 9/11 ordering critical: DEAD-02 (test imports) must precede DEAD-03 (re-export removal) and DEAD-04 (generator.py cleanup)
- (Resolved) Old Phase 12 pre-condition and quota risk no longer apply — requirements completed in Phase 8.1
- Slack webhook binding: Verify `SLACK_WEBHOOK_URL` is bound to current Cloud Run revision before declaring Phase 8 complete

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|

## Session Continuity

Last session: 2026-03-04T08:03:57.527Z
Stopped at: Completed 12-shared-utils-extraction/12-01-PLAN.md
Resume file: None
