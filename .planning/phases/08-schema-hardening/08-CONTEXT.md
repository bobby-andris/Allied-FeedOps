# Phase 8: Schema Hardening - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add missing database constraints to data tables so the daily performance snapshot job succeeds instead of failing with 42P10 upsert errors. Enforce correctness at the DB level: unique constraints, CHECK constraints on platform columns, and FK on publish_event_id. No application code changes — schema only (plus data cleanup to enable constraints).

</domain>

<decisions>
## Implementation Decisions

### Dedup Strategy (SCHM-01)
- Keep the newest row (latest `fetched_at` or `created_at`) when duplicates exist on `(master_sku, platform, environment, snapshot_date)`
- Delete older duplicates in the same migration transaction, before adding the unique constraint
- The code already does `.upsert(on_conflict="master_sku,platform,environment,snapshot_date")` at `performance_impact.py:461` — adding the constraint makes this work instead of 42P10

### Migration Approach
- Single numbered migration file: `supabase/migrations/042_schema_hardening.sql`
- Follows existing numbering convention (last applied is 041)
- Apply via Supabase MCP `apply_migration` tool
- All four SCHM requirements in one migration, ordered: dedup → unique constraint → CHECK constraints → FK cleanup → FK constraint
- Wrap in a transaction so it's all-or-nothing

### Orphaned Data Cleanup (SCHM-04)
- NULL out `publish_event_id` on any `performance_snapshots` rows where the referenced `publish_events` row doesn't exist
- This preserves snapshot data while enabling the FK constraint
- Do NOT delete orphaned rows — the metrics data is still valuable even without a publish event link

### CHECK Constraint Values (SCHM-03)
- Allowed platform values: `google`, `bing`, `shopify` (lowercase only — matches DB convention)
- Apply CHECK constraints to platform columns on: `performance_snapshots`, `performance_baselines`, `performance_impact_scores`, `generated_content`
- Audit `search_queries`, `keyword_metrics`, `funnel_snapshots_daily` for platform columns too

### Constraint Audit Scope (SCHM-02)
- Audit all data import tables listed in requirements: `performance_baselines`, `search_queries`, `keyword_metrics`, `funnel_snapshots_daily`, `performance_impact_scores`
- Check for: missing unique constraints, missing NOT NULL on required fields, missing CHECK constraints
- Only add constraints that the existing data already satisfies (no data loss)

### Claude's Discretion
- Exact dedup SQL approach (DELETE with CTE vs temp table)
- Whether to add indexes alongside constraints for query performance
- Order of CHECK constraint application across tables
- Whether `funnel_snapshots_daily` needs the same platform CHECK (may have different valid values)

</decisions>

<specifics>
## Specific Ideas

- The 42P10 error is the primary pain point — fixing SCHM-01 alone unblocks the daily snapshot job
- `performance_impact_scores` table is currently empty because it depends on snapshots collecting correctly
- Success criterion #1 (Slack alert reports success) implies the Cloud Scheduler job already exists and runs at 6:00 AM UTC — this phase fixes why it fails, not the job itself
- The upsert at `performance_impact.py:461` specifies `on_conflict="master_sku,platform,environment,snapshot_date"` — the unique constraint must match this exact column set

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/feedops/monitoring/performance_impact.py` — `collect_daily_performance_snapshots()` is the function that fails on upsert
- `src/feedops/db/supabase_client.py:926` — `insert()` for snapshots (separate from upsert path)
- `docs/database/SCHEMA.md` — Full schema reference for audit

### Established Patterns
- Migration files in `supabase/migrations/` with sequential numbering (001-041 + timestamped)
- Platform values are always lowercase strings in DB ("google", "bing", "shopify")
- `on_conflict` upsert pattern used throughout `performance_impact.py`

### Integration Points
- Daily Cloud Scheduler job calls snapshot collection endpoint
- `performance_impact_scores` computation depends on `performance_snapshots` collecting correctly
- `publish_events` table is the FK target for `publish_event_id`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-schema-hardening*
*Context gathered: 2026-03-03*
