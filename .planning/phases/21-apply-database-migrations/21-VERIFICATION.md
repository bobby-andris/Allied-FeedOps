---
phase: 21-apply-database-migrations
verified: 2026-02-21T15:30:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 21: Apply Database Migrations Verification Report

**Phase Goal:** Unblock all measurement infrastructure by applying pending database migrations to live Supabase and updating schema documentation
**Verified:** 2026-02-21
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `publish_events` table has `prompt_hash`, `final_payload_hash`, `evidence_hash`, `segment_key` columns in live Supabase | VERIFIED | SUMMARY confirms pre-check found all 4 columns already applied. Migration 034 SQL uses `ADD COLUMN IF NOT EXISTS`. SCHEMA.md lines 357-360 document all 4 columns. End-to-end test row with `prompt_hash='test-prompt-hash-verification-21'` was inserted, queried via `/api/prompt-lineage`, then deleted. |
| 2 | `regeneration_history` table has `feature_flags_active`, `tokens_used`, `latency_ms`, `cost_usd` columns in live Supabase | VERIFIED | SCHEMA.md lines 1309-1312 document all 4 columns. Python `main.py` lines 605 and 1097 actively write `feature_flags_active: capture_flag_snapshot()`, `tokens_used`, `latency_ms` into `regeneration_history` on every generation call. Migration 035 SQL contains the DDL. |
| 3 | `prompt_version_aliases`, `sku_bottleneck_classifications`, `gmc_product_status` tables exist in live Supabase | VERIFIED | All 3 tables documented in SCHEMA.md (lines 1356, 1398, 1427). SUMMARY confirms pre-check found all tables already applied. `/api/bottleneck/classify/route.ts` and `/api/bottleneck/status/route.ts` actively query `sku_bottleneck_classifications`. `/api/prompt-lineage/route.ts` queries `prompt_version_aliases`. |
| 4 | `/api/prompt-lineage` returns non-empty lineage for a published SKU with a prompt hash | VERIFIED | SUMMARY documents actual API response with synthetic row: `{"publish_event_id":72,"published_at":"2026-02-21T11:58:46+00:00","prompt_hash":"test-prompt-hash-verification-21","prompt_alias":null,...}`. Route is 228 lines with full compare-mode and standard-mode implementations. Returns graceful `lineage: null` (not 500) when no data. |
| 5 | SCHEMA.md documents all new columns on `publish_events` including lineage columns from migration 034 | VERIFIED | `docs/database/SCHEMA.md` lines 355-396 include `final_payload_snapshot`, `final_payload_hash`, `prompt_hash`, `evidence_hash`, `segment_key` with descriptions, 3 indexes, and a lineage query example. Commit `02ce3610` added 16 lines documenting these. |
| 6 | Deferred migration files are renamed to avoid number conflicts and reasoning is documented | VERIFIED | `ls supabase/migrations/` confirms: `034b_DEFERRED_ga4_attribution_forensics.sql` and `035b_DEFERRED_unified_intent_execution_system.sql` exist alongside the applied `034_add_publish_lineage_hashes.sql` and `035_measurement_infrastructure_schema.sql`. Commit `89621ecb` used `git mv`. Deferral block at top of each file explains WHY deferred, codebase status, and when to apply. |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/database/SCHEMA.md` | Updated publish_events section with lineage columns, cross-checked against live schema, contains `prompt_hash` | VERIFIED | Contains `prompt_hash` at lines 358, 1303, 1364. All 5 new `publish_events` columns documented. `regeneration_history` measurement columns documented. All 3 new tables (`prompt_version_aliases`, `sku_bottleneck_classifications`, `gmc_product_status`) fully documented. |
| `supabase/migrations/034_add_publish_lineage_hashes.sql` | Migration DDL for publish_events lineage columns | VERIFIED | 25-line file with `ADD COLUMN IF NOT EXISTS` for all 4 columns + 3 indexes. Committed and applied to live Supabase. |
| `supabase/migrations/035_measurement_infrastructure_schema.sql` | Migration DDL for measurement infrastructure | VERIFIED | 3,524-byte file. Contains DDL for `feature_flags_active`/`tokens_used`/`latency_ms`/`cost_usd` on `regeneration_history` plus 3 new tables. |
| `supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` | Renamed deferred file with documented reasoning | VERIFIED | File exists (6,792 bytes). Renamed from `034_ga4_attribution_forensics.sql` via `git mv`. Has deferral reasoning block at top. |
| `supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` | Renamed deferred file with documented reasoning | VERIFIED | File exists (16,436 bytes). Renamed from `035_unified_intent_execution_system.sql` via `git mv`. Has deferral reasoning block at top. |
| `dashboard/src/app/api/prompt-lineage/route.ts` | Queries publish_events.prompt_hash + prompt_version_aliases | VERIFIED | 228-line substantive implementation. Queries `publish_events` for `prompt_hash`, joins `prompt_version_aliases` for alias/notes, joins `regeneration_history` for generation metadata. Handles compare mode and standard lineage mode. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `supabase/migrations/034_add_publish_lineage_hashes.sql` | Live Supabase `publish_events` table | `execute_sql` MCP | VERIFIED | SUMMARY pre-check confirmed all 4 columns (`final_payload_hash`, `prompt_hash`, `evidence_hash`, `segment_key`) already existed before execution. End-to-end synthetic row test proves columns are queryable. |
| `supabase/migrations/035_measurement_infrastructure_schema.sql` | Live Supabase (`regeneration_history` + 3 new tables) | `execute_sql` MCP | VERIFIED | SUMMARY pre-check confirmed all 4 `regeneration_history` columns and all 3 new tables already existed. Python `main.py` actively writes to `regeneration_history.feature_flags_active` on every generation. |
| `dashboard/src/app/api/prompt-lineage/route.ts` | `publish_events.prompt_hash` + `prompt_version_aliases` | Supabase query | VERIFIED | Route queries `publish_events` selecting `prompt_hash` (line 137). Queries `prompt_version_aliases` for aliases (line 81). Both column and table exist in live schema. End-to-end test returned real data. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MEAS-01 | 21-01-PLAN.md | Each content generation records which feature flags were active at generation time (`feature_flags_active` field in `regeneration_history`) | SATISFIED | Schema unblocked: `regeneration_history.feature_flags_active` JSONB column exists (migration 035). Python `main.py` writes `feature_flags_active: capture_flag_snapshot()` at lines 605 and 1097. SCHEMA.md documents usage pattern with MEAS-01 tag. |
| MEAS-03 | 21-01-PLAN.md | Prompt hash lineage tracking connects generated content to the exact prompt version that produced it | SATISFIED | Schema unblocked: `publish_events.prompt_hash`, `regeneration_history.prompt_hash`, `prompt_version_aliases` table all exist. `/api/prompt-lineage` end-to-end verified. `publish/batch/route.ts` propagates `generation_prompt_hash` into `publish_events.prompt_hash` at publish time. |
| MEAS-04 | 21-01-PLAN.md | Bottleneck classifier categorizes impact issues as code-path, auction/bid, query relevance, coverage gap, or propagation failure — with evidence for each classification | SATISFIED | Schema unblocked: `sku_bottleneck_classifications` table exists (migration 035). `/api/bottleneck/classify/route.ts` (360 lines) implements all 5 classification categories: `coverage_gap`, `code_path_gap`, `propagation_failure`, `query_relevance`, `auction_bid`. Writes to `sku_bottleneck_classifications` with confidence and evidence JSONB. |

**Orphaned requirements check:** REQUIREMENTS.md maps MEAS-01, MEAS-03, MEAS-04 to Phase 21. All 3 are claimed by plan `21-01-PLAN.md`. No orphaned requirements.

**Note on REQUIREMENTS.md "Pending" status:** The REQUIREMENTS.md `Coverage` section still lists these 3 requirements under "Pending" (line 90: `Pending (gap closure): 7 (MEAS-01, MEAS-02, MEAS-03, MEAS-04, FIX-01, MODEL-01, MODEL-02)`). However, the Traceability table (lines 77-80) correctly shows these as "Complete" for Phase 21. This is an internal REQUIREMENTS.md inconsistency — the Coverage count was not updated when the Traceability rows were updated. This is a documentation artifact, not a gap in implementation.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `supabase/migrations/` | - | Pre-existing duplicate numbers (026, 032, 033) | Info | Pre-existed before Phase 21. Out of scope for this phase — only 034/035 conflicts were in scope. |

No blockers or warnings in Phase 21 deliverables. No TODO/FIXME/placeholder comments in modified files.

---

### Human Verification Required

None required. All goal-critical checks are verifiable programmatically:
- Schema columns/tables documented in SCHEMA.md and confirmed by SUMMARY pre-check queries
- API route implementation is substantive (not a stub) — 228 lines with real Supabase queries
- End-to-end synthetic row test documented in SUMMARY with actual API response JSON
- Python pipeline actively writes measurement columns on every generation call

---

### Gaps Summary

No gaps. All 6 must-have truths are verified.

**Phase goal achieved:** The measurement infrastructure database schema is in place. Migrations 034 (publish lineage hashes) and 035 (measurement infrastructure) are applied to live Supabase. The `/api/prompt-lineage` endpoint is operational. SCHEMA.md accurately documents all new columns and tables. Deferred migration files are renamed with no duplicate numbers remaining for the applied migrations.

---

_Verified: 2026-02-21_
_Verifier: Claude (gsd-verifier)_
