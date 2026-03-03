# Phase 8: Schema Hardening - Research

**Researched:** 2026-03-03
**Domain:** PostgreSQL schema migrations, Supabase constraint management, data deduplication
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Dedup Strategy (SCHM-01):** Keep the newest row (latest `fetched_at` or `created_at`) when duplicates exist on `(master_sku, platform, environment, snapshot_date)`. Delete older duplicates in the same migration transaction, before adding the unique constraint. The code already does `.upsert(on_conflict="master_sku,platform,environment,snapshot_date")` at `performance_impact.py:461` — adding the constraint makes this work instead of 42P10.
- **Migration Approach:** Single numbered migration file: `supabase/migrations/042_schema_hardening.sql`. Follows existing numbering convention (last applied is 041). Apply via Supabase MCP `apply_migration` tool. All four SCHM requirements in one migration, ordered: dedup → unique constraint → CHECK constraints → FK cleanup → FK constraint. Wrap in a transaction so it's all-or-nothing.
- **Orphaned Data Cleanup (SCHM-04):** NULL out `publish_event_id` on any `performance_snapshots` rows where the referenced `publish_events` row doesn't exist. Do NOT delete orphaned rows — the metrics data is still valuable even without a publish event link.
- **CHECK Constraint Values (SCHM-03):** Allowed platform values: `google`, `bing`, `shopify` (lowercase only). Apply CHECK constraints to platform columns on: `performance_snapshots`, `performance_baselines`, `performance_impact_scores`, `generated_content`. Audit `search_queries`, `keyword_metrics`, `funnel_snapshots_daily` for platform columns too.
- **Constraint Audit Scope (SCHM-02):** Audit all data import tables: `performance_baselines`, `search_queries`, `keyword_metrics`, `funnel_snapshots_daily`, `performance_impact_scores`. Check for: missing unique constraints, missing NOT NULL on required fields, missing CHECK constraints. Only add constraints that the existing data already satisfies (no data loss).

### Claude's Discretion
- Exact dedup SQL approach (DELETE with CTE vs temp table)
- Whether to add indexes alongside constraints for query performance
- Order of CHECK constraint application across tables
- Whether `funnel_snapshots_daily` needs the same platform CHECK (may have different valid values)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCHM-01 | Add missing unique constraint on `performance_snapshots(master_sku, platform, environment, snapshot_date)` with dedup of existing 179 rows in same migration | CTE-based dedup pattern verified from migration 032; DO block idempotency pattern verified |
| SCHM-02 | Audit all data import tables for missing or incorrect constraints | Table schemas fully documented in SCHEMA.md; audit findings below |
| SCHM-03 | Add CHECK constraints on platform columns across data tables to enforce valid values | Pattern verified in migrations 032, 041; DO block guard pattern for idempotency |
| SCHM-04 | Add FK constraint on `performance_snapshots.publish_event_id` referencing `publish_events` | FK pattern verified in migrations 032, 20260225083710; NULL-out orphan pattern documented |
</phase_requirements>

## Summary

Phase 8 is a pure database migration that adds four categories of constraints to enforce correctness at the schema level. The primary pain point is PostgreSQL error 42P10 ("there is no unique constraint matching given keys for referenced table") thrown when the Supabase Python client's `.upsert(on_conflict="master_sku,platform,environment,snapshot_date")` runs without a backing unique constraint. The constraint was previously added in migration 032 via an idempotent DO block — but the CONTEXT confirms 179 duplicate rows still exist, meaning the constraint either never landed in production or was subsequently dropped.

The fix is a single transactional migration (042) that: deduplicates `performance_snapshots` rows using a CTE/window-function pattern (keep newest by `fetched_at DESC`), adds the unique constraint, adds platform CHECK constraints across data tables, nulls out orphaned `publish_event_id` values, and adds the FK. This unblocks the daily 6:00 AM UTC Cloud Scheduler job, which will then start populating `performance_impact_scores` correctly.

The established pattern in this codebase for idempotent constraint additions uses `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '...') THEN ... END IF; END $$;` guards. All four constraints follow this pattern.

**Primary recommendation:** Write migration 042 as a single `BEGIN/COMMIT` transaction using the CTE dedup pattern from migration 032, idempotent DO block guards for all constraints, and NULL-out for orphaned FK values — applied via `mcp__supabase__apply_migration`.

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| PostgreSQL (via Supabase) | 15+ | Constraint enforcement | Project database |
| Supabase MCP `apply_migration` | Current | Apply migration to production | Established project tool pattern |

### SQL Patterns Used in This Project
| Pattern | Purpose | First Used In |
|---------|---------|---------------|
| `DO $$ BEGIN IF NOT EXISTS (...) THEN ... END IF; END $$;` | Idempotent constraint add | Migrations 032, 20260225083710 |
| `WITH ranked AS (SELECT ..., ROW_NUMBER() OVER (...) AS rn FROM ...) DELETE ... WHERE rn > 1` | CTE-based dedup, keep newest | Migration 032 |
| `ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS` | Not used here — project uses DO block guards instead | — |
| `CREATE UNIQUE INDEX IF NOT EXISTS` | Idempotent unique index (alternative to UNIQUE constraint) | Migration 038 |
| `BEGIN; ... COMMIT;` | Transaction wrapping for multi-step migrations | Migrations 032, 041 |

## Architecture Patterns

### Recommended Migration Structure
```sql
-- 042_schema_hardening.sql
BEGIN;

-- Step 1: SCHM-01 — Dedup performance_snapshots (prerequisite for unique constraint)
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY master_sku, platform, environment, snapshot_date
      ORDER BY fetched_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM performance_snapshots
)
DELETE FROM performance_snapshots p
USING ranked r
WHERE p.id = r.id
  AND r.rn > 1;

-- Step 2: SCHM-01 — Add unique constraint (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_performance_snapshots_daily'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT uq_performance_snapshots_daily
    UNIQUE (master_sku, platform, environment, snapshot_date);
  END IF;
END $$;

-- Step 3: SCHM-03 — Platform CHECK constraints
-- (one DO block per table, per constraint name)

-- Step 4: SCHM-04 — Null out orphaned publish_event_id
UPDATE performance_snapshots ps
SET publish_event_id = NULL
WHERE ps.publish_event_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM publish_events pe WHERE pe.id = ps.publish_event_id
  );

-- Step 5: SCHM-04 — Add FK constraint (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_performance_snapshots_publish_event'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT fk_performance_snapshots_publish_event
    FOREIGN KEY (publish_event_id) REFERENCES publish_events(id);
  END IF;
END $$;

COMMIT;
```

### Pattern 1: CTE Dedup (Keep Newest Row)
**What:** Window function partitions by the target unique key, assigns row numbers ordered by recency. All rows with rn > 1 are deleted.
**When to use:** Pre-constraint dedup where "newest wins" semantics apply.
**Example:**
```sql
-- Source: supabase/migrations/032_performance_impact_pipeline.sql (lines 58-70)
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY master_sku, platform, environment, snapshot_date
      ORDER BY fetched_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM performance_snapshots
)
DELETE FROM performance_snapshots p
USING ranked r
WHERE p.id = r.id
  AND r.rn > 1;
```

### Pattern 2: Idempotent Constraint Addition (DO Block)
**What:** Checks `pg_constraint` system catalog before attempting to add a constraint. Safe to re-run without error.
**When to use:** All constraint additions in this project follow this pattern.
**Example:**
```sql
-- Source: supabase/migrations/032_performance_impact_pipeline.sql (lines 72-84)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_performance_snapshots_daily'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT uq_performance_snapshots_daily
    UNIQUE (master_sku, platform, environment, snapshot_date);
  END IF;
END $$;
```

### Pattern 3: Orphaned FK Cleanup
**What:** UPDATE to NULL before adding FK — preserves data rows while eliminating dangling references.
**When to use:** When FK target rows may have been deleted but referencing rows have useful non-key data.
**Example:**
```sql
-- Null out orphaned publish_event_id before adding FK
UPDATE performance_snapshots ps
SET publish_event_id = NULL
WHERE ps.publish_event_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM publish_events pe WHERE pe.id = ps.publish_event_id
  );
```

### Anti-Patterns to Avoid
- **ADD CONSTRAINT without dedup:** Adding a UNIQUE constraint when duplicates exist will fail with `ERROR: could not create unique index`. Always dedup first in the same transaction.
- **Separate transactions for dedup and constraint:** If dedup succeeds but constraint fails, duplicates are deleted but constraint is missing. Use a single `BEGIN/COMMIT` block.
- **`ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS`:** PostgreSQL supports this syntax for UNIQUE/CHECK/FK in PG15+, but this project uses DO block guards for consistency — match existing pattern.
- **Checking `information_schema.table_constraints` instead of `pg_constraint`:** The codebase uses `pg_constraint` — keep consistent.
- **Adding FK before nulling orphans:** Will fail with `ERROR: insert or update on table violates foreign key constraint`. Always clean orphans first.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dedup logic | Python script to deduplicate via API calls | SQL CTE with ROW_NUMBER() | Atomic with constraint addition; faster; pattern already in migration 032 |
| Constraint existence check | Hardcoded constraint creation without guard | DO block + pg_constraint check | Migration may be re-run; guards prevent `already exists` errors |
| FK orphan discovery | Python JOIN query | SQL UPDATE with NOT EXISTS subquery | Single operation; atomic in transaction |

**Key insight:** All data cleanup in this phase must happen inside the SQL migration transaction. Running cleanup in Python before the migration means cleanup and constraint addition are not atomic — a failure between steps leaves the DB in an inconsistent state.

## Common Pitfalls

### Pitfall 1: Migration 032 Pattern Already Attempted — Verify Before Writing New SQL
**What goes wrong:** Migration 032 already contains SQL to add `uq_performance_snapshots_daily`. If the constraint WAS applied but then duplicates were inserted after (due to a bug), re-running just the dedup is needed, not re-writing the constraint add. If the constraint was NEVER applied, the full pattern is needed.
**Why it happens:** Migration 032 ran against a production DB state where the table may have had zero rows, OR the constraint was added but a schema rebuild (e.g., from timestamped migration) recreated the table without it.
**How to avoid:** Before writing 042, use `SELECT 1 FROM pg_constraint WHERE conname = 'uq_performance_snapshots_daily'` to verify current production state. The DO block guard handles both cases safely.
**Warning signs:** 42P10 errors in production logs confirm the constraint is missing NOW, regardless of migration 032's history.

### Pitfall 2: `funnel_snapshots_daily` Has No Platform Column
**What goes wrong:** SCHM-03 requires auditing `funnel_snapshots_daily` for platform CHECK. This table has NO platform column — it segments by `tier` (HIGH/MEDIUM/LOW) and `custom_label_0`. Adding a platform CHECK here would be wrong.
**Why it happens:** The audit scope was defined generically across "data import tables" but `funnel_snapshots_daily` serves a different purpose (funnel tier aggregation, not per-platform metrics).
**How to avoid:** `funnel_snapshots_daily` already has `tier CHECK (tier IN ('HIGH', 'MEDIUM', 'LOW'))` from its creation migration. No platform column exists — skip this table for SCHM-03.

### Pitfall 3: `keyword_metrics` and `search_queries` Have No Platform Column
**What goes wrong:** `keyword_metrics` table uses `keyword` as primary key with no platform column. `search_queries` has no platform column either (it's Google Ads only, implicit). Adding platform CHECK to these tables would require adding a column first, which is out of scope.
**Why it happens:** These tables are Google Ads-specific by design; platform is implicit.
**How to avoid:** For SCHM-02 audit, note these tables as "no platform column — not applicable for SCHM-03." Only `performance_snapshots`, `performance_baselines`, `performance_impact_scores`, and `generated_content` have explicit platform columns.

### Pitfall 4: `performance_baselines` Already Has a Composite PK Covering the Unique Case
**What goes wrong:** Auditor might try to add a UNIQUE constraint to `performance_baselines` even though its PRIMARY KEY `(master_sku, platform)` already enforces uniqueness.
**Why it happens:** SCHM-02 says "audit for missing unique constraints" — but a PK is a unique constraint.
**How to avoid:** `performance_baselines` PK is `(master_sku, platform)` — already unique. The platform CHECK is the only constraint to add here.

### Pitfall 5: 42P10 vs Constraint Actually Present
**What goes wrong:** 42P10 specifically means "no unique constraint matching given keys" — this is a runtime error from the Supabase Python client's `.upsert()` call, not from a `CREATE CONSTRAINT` call. It fires when PostgreSQL can't find a unique constraint or index with exactly `(master_sku, platform, environment, snapshot_date)` to resolve the `ON CONFLICT`.
**Why it happens:** The constraint must be a named `UNIQUE` constraint or a `UNIQUE INDEX`. A partial index or different column order will not work.
**How to avoid:** The constraint name `uq_performance_snapshots_daily` on columns `(master_sku, platform, environment, snapshot_date)` exactly matches what `performance_impact.py:461` needs. Do not change column order.

## Code Examples

### Current Failing Upsert (performance_impact.py:461)
```python
# Source: src/feedops/monitoring/performance_impact.py
supabase.table("performance_snapshots").upsert(
    payload,
    on_conflict="master_sku,platform,environment,snapshot_date",
).execute()
```
This raises 42P10 because `uq_performance_snapshots_daily` is missing from production. After migration 042, this will work correctly.

### Verify Constraint Exists (pre-migration check)
```sql
-- Run against production Supabase to confirm current state
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'performance_snapshots'::regclass
ORDER BY conname;
```

### Complete Platform CHECK Pattern (for each table)
```sql
-- Source: pattern from supabase/migrations/032_performance_impact_pipeline.sql
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_performance_snapshots_platform'
      AND conrelid = 'performance_snapshots'::regclass
  ) THEN
    ALTER TABLE performance_snapshots
    ADD CONSTRAINT chk_performance_snapshots_platform
    CHECK (platform IN ('google', 'bing', 'shopify'));
  END IF;
END $$;
```

### Verify Dedup Result Before Committing
```sql
-- Include this SELECT in the migration as a sanity check comment or run before:
SELECT master_sku, platform, environment, snapshot_date, COUNT(*) AS cnt
FROM performance_snapshots
GROUP BY master_sku, platform, environment, snapshot_date
HAVING COUNT(*) > 1;
-- Expected: 0 rows after dedup DELETE and before UNIQUE constraint add
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Text-type snapshot_date | DATE type | Migration 032 | Enables date filtering; migration 042 depends on this already being DATE |
| BIGSERIAL PRIMARY KEY for impact scores | GENERATED ALWAYS AS IDENTITY | Migration 20260225083710 | 042 creates no new tables — existing tables use their current PK type |
| No FK on publish_event_id in performance_snapshots | FK added in 042 | Phase 8 | Orphaned rows rejected at DB layer |

**Deprecated/outdated:**
- The SCHEMA.md documents `uq_performance_snapshots_daily` as existing — this reflects the intended state, not production state. The 42P10 error is the ground truth that the constraint is missing.

## Constraint Audit Findings (SCHM-02)

Based on full SCHEMA.md review:

### Tables With Platform Columns — CHECK Constraint Status

| Table | Platform Column? | Current Platform CHECK? | Action |
|-------|-----------------|------------------------|--------|
| `performance_snapshots` | YES (`google`, `bing`) | NO | Add `chk_performance_snapshots_platform` |
| `performance_baselines` | YES (`google`, `bing`) | NO | Add `chk_performance_baselines_platform` |
| `performance_impact_scores` | YES (`google`) | NO | Add `chk_performance_impact_scores_platform` |
| `generated_content` | YES (`google`, `bing`, `shopify`) | NO | Add `chk_generated_content_platform` |
| `search_queries` | NO | N/A | Skip |
| `keyword_metrics` | NO | N/A | Skip |
| `funnel_snapshots_daily` | NO (uses `tier`) | Already has `tier CHECK` | Skip for platform; already correct |

### Tables — Unique Constraint Status

| Table | Required Unique | Current Status | Action |
|-------|-----------------|---------------|--------|
| `performance_snapshots` | `(master_sku, platform, environment, snapshot_date)` | MISSING (root cause of 42P10) | Add via 042 |
| `performance_baselines` | `(master_sku, platform)` — via PK | Already enforced | None |
| `performance_impact_scores` | `(publish_event_id, metric_name, platform, environment)` | Present (via `uq_impact_scores_event_metric` index) | None |
| `generated_content` | `(master_sku, platform, content_type)` | Present | None |
| `search_queries` | `(query_text, gmc_offer_id, period_start, period_end)` | Present | None |
| `keyword_metrics` | `keyword` (PK) | Present | None |
| `funnel_snapshots_daily` | `(snapshot_date, custom_label_0, tier)` | Present | None |

### FK Constraint Status

| Table.Column | References | Current FK? | Action |
|--------------|-----------|-------------|--------|
| `performance_snapshots.publish_event_id` | `publish_events(id)` | NO | Add after orphan cleanup |
| `performance_impact_scores.publish_event_id` | `publish_events(id)` | YES (in migration 032, 20260225083710) | None |

## Open Questions

1. **Are there duplicate rows in other tables?**
   - What we know: CONTEXT confirms 179 duplicate rows in `performance_snapshots`
   - What's unclear: Whether other audit tables have duplicates that would block new constraints
   - Recommendation: Run COUNT + GROUP BY checks in Wave 0 before adding constraints to each table

2. **`performance_baselines` platform values — are any non-lowercase?**
   - What we know: DB convention is lowercase; code writes lowercase
   - What's unclear: Whether any rows have uppercase or mixed-case values from early data loads
   - Recommendation: Run `SELECT DISTINCT platform FROM performance_baselines` before adding CHECK constraint

3. **`generated_content` platform — does it contain values beyond `google`/`bing`/`shopify`?**
   - What we know: Schema says `google`, `bing`, `shopify`; SCHM-03 decision confirms these three
   - What's unclear: Whether legacy rows use different values
   - Recommendation: Run `SELECT DISTINCT platform FROM generated_content` before adding CHECK

## Sources

### Primary (HIGH confidence)
- `supabase/migrations/032_performance_impact_pipeline.sql` — dedup CTE pattern, DO block constraint guard pattern, existing uq_performance_snapshots_daily definition
- `supabase/migrations/20260225083710_create_performance_impact_scores.sql` — FK reference pattern, DO block for CHECK constraints
- `supabase/migrations/041_search_buildout_recommendations.sql` — current migration naming convention, CHECK constraint in CREATE TABLE style
- `supabase/migrations/20260225105102_create_funnel_snapshots_daily.sql` — confirms funnel_snapshots_daily has no platform column
- `docs/database/SCHEMA.md` — full table schema for all tables in scope
- `src/feedops/monitoring/performance_impact.py:461` — exact upsert call causing 42P10

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions — user-locked choices for dedup strategy, migration naming, orphan handling

## Metadata

**Confidence breakdown:**
- Dedup SQL pattern: HIGH — exact pattern verified in migration 032 for this exact table
- Idempotent constraint guards: HIGH — DO block pg_constraint pattern used consistently across migrations
- Platform CHECK values: HIGH — `google`, `bing`, `shopify` confirmed in CONTEXT and schema docs
- FK orphan cleanup: HIGH — NULL-update-before-FK pattern is standard PostgreSQL; confirmed by CONTEXT decision
- Table audit findings: HIGH — based on direct SCHEMA.md read for all tables in scope
- funnel_snapshots_daily exclusion from SCHM-03: HIGH — confirmed no platform column exists

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable domain — SQL constraints don't change)
