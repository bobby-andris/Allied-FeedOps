# Phase 21: Apply Database Migrations & Update Schema Docs - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Unblock all measurement infrastructure by applying pending database migrations (034, 035) to live Supabase and updating SCHEMA.md documentation. This is an operations phase — run SQL, verify results, update docs. No new features or UI work.

</domain>

<decisions>
## Implementation Decisions

### Migration execution
- Apply migrations via Supabase MCP `execute_sql` tool — stay in Claude context, no manual copy-paste
- Apply anytime — these are additive (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS), no downtime risk
- Check live Supabase first to see what's already applied before running anything

### Migration file selection
- 4 migration files exist with duplicate numbers (two 034s, two 035s)
- Phase success criteria only reference `034_add_publish_lineage_hashes.sql` and `035_measurement_infrastructure_schema.sql`
- Before applying: audit all 4 files against codebase usage and milestone scope
- Check if any tables from the extra files (`034_ga4_attribution_forensics.sql`, `035_unified_intent_execution_system.sql`) already exist in live DB
- Deferred migrations: rename to avoid number conflicts, document reasoning for deferral
- Ensure all applied migrations align with what's actually implemented in code for this milestone

### Verification approach
- Two-layer verification: schema queries AND API endpoint testing
- Query `information_schema.columns` and `information_schema.tables` to confirm new columns/tables exist
- Test `/api/prompt-lineage` endpoint — must return non-empty lineage for published SKUs with prompt hashes
- If no published SKUs have prompt_hash yet, backfill at least one publish_event to prove end-to-end
- Write a VERIFICATION.md report with query results proving migrations applied correctly

### Schema docs update
- Full update with query patterns — match existing SCHEMA.md documentation depth
- Add all new tables (prompt_version_aliases, sku_bottleneck_classifications, gmc_product_status) with complete column definitions
- Add new columns on existing tables (publish_events lineage columns, regeneration_history measurement columns)
- Include common query patterns, JSONB parsing examples, and relationship notes for new schema
- Verify and fix existing docs for altered tables (publish_events, regeneration_history) — cross-check against actual schema, fix any drift

### Claude's Discretion
- Whether to apply migrations one at a time with verification between, or all at once
- Rollback strategy (IF NOT EXISTS safety vs. prepared DROP statements)
- Commit strategy for SCHEMA.md update (separate from migration execution or bundled)
- Where to document deferred migration reasoning (CONTEXT.md section vs. separate migration audit doc)

</decisions>

<specifics>
## Specific Ideas

- "Deeply understand what each migration does" before deciding to apply or defer
- Rename deferred migration files to avoid number conflicts with applied ones
- "Make sure all migrations align with what we have implemented in our code as well as implemented in this milestone"
- Information about deferred migrations must be documented somewhere with reasons

</specifics>

<deferred>
## Deferred Ideas

- `034_ga4_attribution_forensics.sql` — GA4 diagnostics tables (4 tables: ga4_source_medium_daily, ga4_landing_page_quality_daily, ga4_attribution_root_cause_daily, ga4_shopify_reconciliation_daily). Pending audit against codebase and milestone scope.
- `035_unified_intent_execution_system.sql` — Intent intelligence + experiment tracking (14 tables). Pending audit against codebase and milestone scope.
- Both will be evaluated during execution: if code references them and they're in-milestone, apply; otherwise rename and defer with documented reasoning.

</deferred>

---

*Phase: 21-apply-database-migrations*
*Context gathered: 2026-02-21*
