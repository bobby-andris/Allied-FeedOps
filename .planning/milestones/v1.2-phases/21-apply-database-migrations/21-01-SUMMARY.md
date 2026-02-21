---
phase: 21-apply-database-migrations
plan: "01"
subsystem: database-schema
tags: [database, migrations, schema, lineage, measurement]
dependency_graph:
  requires: []
  provides: [publish_events.prompt_hash, publish_events.evidence_hash, publish_events.segment_key, prompt_version_aliases, sku_bottleneck_classifications, gmc_product_status, regeneration_history.feature_flags_active]
  affects: [/api/prompt-lineage, SCHEMA.md]
tech_stack:
  added: []
  patterns: [Supabase REST API for migration verification, execute_sql RPC for pre-checks]
key_files:
  created: [.planning/phases/21-apply-database-migrations/21-01-SUMMARY.md]
  modified:
    - docs/database/SCHEMA.md
    - supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql
    - supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql
decisions:
  - "Migrations 034+035 were already applied in live Supabase (verified via information_schema queries) — no re-execution needed"
  - "Deferred migration files renamed with 034b_DEFERRED_ / 035b_DEFERRED_ prefix to eliminate number conflicts"
  - "Deferred migration tables (ga4_source_medium_daily, intent_taxonomy_versions, experiment_registry, etc.) exist in live DB — applied out-of-band previously"
  - "/api/prompt-lineage returns lineage: null gracefully (no 500) when no prompt_hash data exists — acceptable per plan"
metrics:
  duration: "6 minutes"
  completed_date: "2026-02-21"
  tasks_completed: 3
  files_modified: 3
---

# Phase 21 Plan 01: Apply Database Migrations Summary

**One-liner**: Verified migrations 034 (publish lineage hashes) and 035 (measurement infrastructure) already applied in live Supabase, renamed deferred migration files, and updated SCHEMA.md with all 5 new publish_events lineage columns.

## Tasks Completed

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Pre-check live DB state, apply migrations 034+035, verify schema | Complete | (no code change — DB already applied) | - |
| 2 | End-to-end lineage verification + rename deferred migrations | Complete | 89621ecb | supabase/migrations/034b_DEFERRED_*, 035b_DEFERRED_* |
| 3 | Update SCHEMA.md with migration 034 columns | Complete | 02ce3610 | docs/database/SCHEMA.md |

## Pre-check Results

**Pre-check findings (all ran before any migration execution):**

| Check | Item | Status |
|-------|------|--------|
| 034 columns | final_payload_hash | Already existed |
| 034 columns | prompt_hash | Already existed |
| 034 columns | evidence_hash | Already existed |
| 034 columns | segment_key | Already existed |
| 034 columns | final_payload_snapshot | Already existed (migration 033) |
| 035 tables | prompt_version_aliases | Already existed |
| 035 tables | sku_bottleneck_classifications | Already existed |
| 035 tables | gmc_product_status | Already existed |
| 035 cols | feature_flags_active | Already existed |
| 035 cols | tokens_used | Already existed |
| 035 cols | latency_ms | Already existed |
| 035 cols | cost_usd | Already existed |
| Deferred tables | ga4_source_medium_daily | Applied out-of-band |
| Deferred tables | intent_taxonomy_versions | Applied out-of-band |
| Deferred tables | term_intent_state | Applied out-of-band |
| Deferred tables | experiment_registry | Applied out-of-band |

**Conclusion**: Both migrations 034 and 035 were already applied to live Supabase in a previous session. No re-execution was required. All columns and tables match the migration DDL exactly.

## Verification Results

### Migration 034 — publish_events lineage columns
- `final_payload_hash` TEXT NULLABLE — verified
- `prompt_hash` TEXT NULLABLE — verified
- `evidence_hash` TEXT NULLABLE — verified
- `segment_key` TEXT NULLABLE — verified
- `idx_publish_events_final_payload_hash` index — verified
- `idx_publish_events_prompt_hash` index — verified
- `idx_publish_events_segment_key` index — verified

### Migration 035 — measurement infrastructure
- `regeneration_history.feature_flags_active` JSONB — verified
- `regeneration_history.tokens_used` INTEGER — verified
- `regeneration_history.latency_ms` INTEGER — verified
- `regeneration_history.cost_usd` NUMERIC — verified
- `idx_regen_history_flags` GIN index — verified
- `prompt_version_aliases` table — verified
- `sku_bottleneck_classifications` table — verified (all 3 indexes)
- `gmc_product_status` table — verified (all 4 indexes)

### End-to-end Lineage Verification
- Synthetic test row inserted (publish_events ID: 72) with prompt_hash = 'test-prompt-hash-verification-21'
- `/api/prompt-lineage?master_sku=WP-2/16-GAL&platform=google` returned:
  ```json
  {"publish_event_id":72,"published_at":"2026-02-21T11:58:46+00:00","prompt_hash":"test-prompt-hash-verification-21","prompt_alias":null,"prompt_notes":null,"generation":null}
  ```
- Test row deleted and cleanup verified (0 rows remain)
- API returns `{"lineage":null,"note":"No successful publish events found..."}` gracefully when no real data — no 500 errors

### Deferred Migration Files
- `034_ga4_attribution_forensics.sql` → `034b_DEFERRED_ga4_attribution_forensics.sql`
- `035_unified_intent_execution_system.sql` → `035b_DEFERRED_unified_intent_execution_system.sql`
- Both files annotated with deferral reasoning block

### SCHEMA.md Updates
- `publish_events` section: added all 5 new columns (final_payload_snapshot, final_payload_hash, prompt_hash, evidence_hash, segment_key)
- Added 3 new indexes to publish_events section
- Added lineage query example
- Cross-checked regeneration_history, prompt_version_aliases, sku_bottleneck_classifications, gmc_product_status — all match live schema (already documented)

## Decisions Made

1. **No migration re-execution needed** — Both 034 and 035 were already applied in a previous session. Pre-checks confirmed exact schema match against migration DDL.

2. **Deferred tables exist in live DB** — The ga4_source_medium_daily and intent_taxonomy_versions/term_intent_state/experiment_registry tables were applied out-of-band previously. The deferred migration files are now reference-only.

3. **File rename approach** — Used `git mv` to rename deferred migrations, preserving git history while eliminating number conflicts with the applied migrations.

4. **Graceful null is acceptable** — The `/api/prompt-lineage` endpoint returning `lineage: null` when no real prompt_hash data exists is valid behavior (pre-Phase 19 historical publishes don't have lineage data).

## Deviations from Plan

None — plan executed exactly as written. The only difference from the plan's anticipated flow was that the migrations were already applied (which is expected and the plan accounted for with "IF NOT EXISTS" SQL). The pre-check step correctly detected this and no re-execution was needed.

## Self-Check

- [x] `docs/database/SCHEMA.md` modified and committed (02ce3610)
- [x] `supabase/migrations/034b_DEFERRED_ga4_attribution_forensics.sql` renamed and committed (89621ecb)
- [x] `supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` renamed and committed (89621ecb)
- [x] No test artifacts in database
- [x] No duplicate migration numbers (verified with `ls` check)
- [x] `/api/prompt-lineage` returns valid response
