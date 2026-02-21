# Phase 21: Apply Database Migrations & Update Schema Docs - Research

**Researched:** 2026-02-21
**Domain:** Supabase database migrations, schema documentation, prompt lineage infrastructure
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Migration execution**
- Apply migrations via Supabase MCP `execute_sql` tool — stay in Claude context, no manual copy-paste
- Apply anytime — these are additive (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS), no downtime risk
- Check live Supabase first to see what's already applied before running anything

**Migration file selection**
- 4 migration files exist with duplicate numbers (two 034s, two 035s)
- Phase success criteria only reference `034_add_publish_lineage_hashes.sql` and `035_measurement_infrastructure_schema.sql`
- Before applying: audit all 4 files against codebase usage and milestone scope
- Check if any tables from the extra files (`034_ga4_attribution_forensics.sql`, `035_unified_intent_execution_system.sql`) already exist in live DB
- Deferred migrations: rename to avoid number conflicts, document reasoning for deferral
- Ensure all applied migrations align with what's actually implemented in code for this milestone

**Verification approach**
- Two-layer verification: schema queries AND API endpoint testing
- Query `information_schema.columns` and `information_schema.tables` to confirm new columns/tables exist
- Test `/api/prompt-lineage` endpoint — must return non-empty lineage for published SKUs with prompt hashes
- If no published SKUs have prompt_hash yet, backfill at least one publish_event to prove end-to-end
- Write a VERIFICATION.md report with query results proving migrations applied correctly

**Schema docs update**
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

### Deferred Ideas (OUT OF SCOPE)
- `034_ga4_attribution_forensics.sql` — GA4 diagnostics tables (4 tables: ga4_source_medium_daily, ga4_landing_page_quality_daily, ga4_attribution_root_cause_daily, ga4_shopify_reconciliation_daily). Pending audit against codebase and milestone scope.
- `035_unified_intent_execution_system.sql` — Intent intelligence + experiment tracking (14 tables). Pending audit against codebase and milestone scope.
- Both will be evaluated during execution: if code references them and they're in-milestone, apply; otherwise rename and defer with documented reasoning.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MEAS-01 | Each content generation records which feature flags were active at generation time (`feature_flags_active` field in `regeneration_history`) | Migration 035 adds `feature_flags_active JSONB` + GIN index to `regeneration_history`. Python code in `main.py` already writes `capture_flag_snapshot()` to this field — it just needs the column to exist |
| MEAS-03 | Prompt hash lineage tracking connects generated content to the exact prompt version that produced it | Migration 034 adds `prompt_hash` column to `publish_events`. Migration 035 creates `prompt_version_aliases` table. TypeScript API route `dashboard/src/app/api/prompt-lineage/route.ts` is fully implemented and reads both. Publishing code in `route.ts` already writes `prompt_hash` to publish_events (with legacy fallback when column missing) |
| MEAS-04 | Bottleneck classifier categorizes impact issues as code-path, auction/bid, query relevance, coverage gap, or propagation failure | Migration 035 creates `sku_bottleneck_classifications` table with partial unique index for one non-override classification per SKU |
</phase_requirements>

---

## Summary

This is an operations phase with no new code. The goal is to apply two pending SQL migrations to the live Supabase instance and update documentation. All the TypeScript and Python code to USE these new columns/tables is already written and deployed — the code is blocked only by missing schema.

**Critical discovery**: The codebase already has backward-compatible fallback logic for when the migration 034 columns don't exist yet. Both `dashboard/src/app/api/publish/sku/route.ts` and `dashboard/src/app/api/publish/batch/route.ts` catch the column-not-found error and retry without the lineage fields. Once migration 034 is applied, these fallbacks become unnecessary dead code — but are harmless. Similarly, `dashboard/src/app/(dashboard)/review/page.tsx` has a fallback for reading `publish_events` without lineage columns.

**Deferred migration decision is clear from audit**: Both `034_ga4_attribution_forensics.sql` and `035_unified_intent_execution_system.sql` have EXTENSIVE active codebase usage — multiple API routes, lib files, and tests reference their tables. However, the CONTEXT.md explicitly defers them pending scope audit. The research below provides the full codebase reference count to inform that audit decision.

**Primary recommendation**: Apply migrations one at a time (034 then 035) with schema verification between each. The SCHEMA.md already contains partial documentation for the new tables — it needs the `publish_events` lineage columns added and a cross-check pass against actual schema for altered tables.

---

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Supabase MCP `execute_sql` | Current | Apply DDL to live DB | Stays in Claude context, avoids copy-paste errors, gives immediate result feedback |
| `information_schema.columns` | PostgreSQL standard | Schema verification | Standard PostgreSQL system catalog, always accurate |
| `information_schema.tables` | PostgreSQL standard | Table existence check | Same — no ORM abstraction needed |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `pg_indexes` | PostgreSQL system catalog | Verify indexes applied | After each migration to confirm indexes exist |
| `/api/prompt-lineage` endpoint | Deployed | End-to-end verification | After both migrations applied, to confirm API works with real data |

---

## Architecture Patterns

### Migration File Inventory

Four migration files with duplicate sequence numbers exist:

**Apply (in-scope for this phase):**
```
supabase/migrations/034_add_publish_lineage_hashes.sql
supabase/migrations/035_measurement_infrastructure_schema.sql
```

**Defer (pending scope audit — codebase references exist):**
```
supabase/migrations/034_ga4_attribution_forensics.sql
supabase/migrations/035_unified_intent_execution_system.sql
```

### What Migration 034 Does

Adds 4 columns to `publish_events` and 3 indexes:

```sql
ALTER TABLE publish_events
  ADD COLUMN IF NOT EXISTS final_payload_hash TEXT,
  ADD COLUMN IF NOT EXISTS prompt_hash TEXT,
  ADD COLUMN IF NOT EXISTS evidence_hash TEXT,
  ADD COLUMN IF NOT EXISTS segment_key TEXT;

-- Comments and 3 indexes (final_payload_hash, prompt_hash, segment_key)
```

**Key facts:**
- ALL IF NOT EXISTS — completely safe to re-run
- `prompt_hash` is the critical column for MEAS-03 (`/api/prompt-lineage` queries it)
- `final_payload_hash` and `evidence_hash` are computed SHA-256 hashes by `dashboard/src/lib/publishing/final-payload.ts`
- `segment_key` is the normalized `custom_label_0` value

### What Migration 035 Does

4 distinct DDL operations for 4 requirements:

**1. Extend `regeneration_history` (MEAS-01):**
```sql
ALTER TABLE regeneration_history
  ADD COLUMN IF NOT EXISTS feature_flags_active JSONB,
  ADD COLUMN IF NOT EXISTS tokens_used INTEGER,
  ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
  ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6);

CREATE INDEX IF NOT EXISTS idx_regen_history_flags
  ON regeneration_history USING GIN (feature_flags_active);
```

**2. Create `prompt_version_aliases` (MEAS-03):**
```sql
CREATE TABLE IF NOT EXISTS prompt_version_aliases (
  id BIGSERIAL PRIMARY KEY,
  prompt_hash TEXT NOT NULL UNIQUE,
  alias TEXT, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT
);
```

**3. Create `sku_bottleneck_classifications` (MEAS-04):**
```sql
CREATE TABLE IF NOT EXISTS sku_bottleneck_classifications (
  id BIGSERIAL PRIMARY KEY,
  master_sku TEXT NOT NULL,
  classification TEXT NOT NULL,
  confidence NUMERIC(4,2), evidence JSONB,
  override_by TEXT, override_note TEXT,
  is_override BOOLEAN DEFAULT false,
  classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  publish_event_id BIGINT
);
-- PARTIAL UNIQUE INDEX: only one non-override per master_sku
CREATE UNIQUE INDEX IF NOT EXISTS idx_sku_bottleneck_master_sku
  ON sku_bottleneck_classifications (master_sku) WHERE is_override = false;
```

**4. Create `gmc_product_status` (MEAS-02, not primary for this phase):**
```sql
CREATE TABLE IF NOT EXISTS gmc_product_status (
  id BIGSERIAL PRIMARY KEY, gmc_offer_id TEXT NOT NULL,
  master_sku TEXT, offer_title TEXT,
  status TEXT NOT NULL, item_issues JSONB,
  issue_count INTEGER DEFAULT 0, disapproval_count INTEGER DEFAULT 0,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(), sync_job_id UUID
);
```

### Python Code Already Writes to New Columns

The Python pipeline in `src/feedops/api/main.py` already captures `feature_flags_active` and `latency_ms` for `regeneration_history`. Lines 605-607 and 1097-1098:

```python
"feature_flags_active": capture_flag_snapshot(),  # returns dict of active flags
"latency_ms": _regen_latency_ms,
```

Once migration 035 is applied, these will persist successfully. Until then, the insert will fail silently (or Supabase may reject unknown columns — needs verification).

### TypeScript Code Has Fallbacks That Will Auto-Resolve

The publishing routes have exception handling for column-not-found errors:

```typescript
// From dashboard/src/app/api/publish/sku/route.ts (lines 789-804)
if (error && (event.final_payload_hash || event.prompt_hash || event.evidence_hash || event.segment_key)
    && /final_payload_snapshot|final_payload_hash|prompt_hash|evidence_hash|segment_key/i.test(error.message)) {
  // Retry without lineage fields
  const legacyPayload = { ...payload }
  delete legacyPayload.final_payload_hash
  delete legacyPayload.prompt_hash
  // ...
}
```

Once migration 034 is applied, the primary insert will succeed, and these fallback paths will never trigger.

### The `/api/prompt-lineage` Route

Location: `dashboard/src/app/api/prompt-lineage/route.ts`

The route is fully implemented and queries:
1. `publish_events` for `prompt_hash` (needs migration 034)
2. `prompt_version_aliases` for human-readable alias (needs migration 035)
3. `regeneration_history` for `feature_flags_active`, `tokens_used`, `latency_ms` (needs migration 035)

It also has a `compare` mode for side-by-side prompt hash comparison.

**Note on backfill for testing**: The `/api/prompt-lineage` route handles the case where no `prompt_hash` exists (returns `lineage: null` with a note). To verify end-to-end post-migration, a publish event needs `prompt_hash` set. Since the publishing code already computes and writes `prompt_hash` (with fallback), the NEXT publish after migration 034 will have lineage data. For immediate verification without triggering a real publish, a test row can be INSERTed directly into `publish_events` and `regeneration_history` using `execute_sql`.

### SCHEMA.md Current State

**Already documented (but not yet applied to live DB):**
- `regeneration_history` — section at line 1268 ALREADY includes `feature_flags_active`, `tokens_used`, `latency_ms`, `cost_usd` columns and the GIN index
- `prompt_version_aliases` — section at line 1340 ALREADY documented
- `sku_bottleneck_classifications` — section at line 1382 ALREADY documented
- `gmc_product_status` — section at line 1411 ALREADY documented

**Missing from SCHEMA.md (need to add):**
- `publish_events` section at line 329 does NOT include the 4 new lineage columns: `final_payload_hash`, `prompt_hash`, `evidence_hash`, `segment_key`
- Also note: the `final_payload_snapshot` column from migration 033 may also be missing (it was added separately)

**Cross-check needed:**
- Verify `publish_events` docs match actual live schema (migration 033 added `final_payload_snapshot`, migration 034 adds the 4 lineage columns)
- Verify the listed indexes for all altered tables match what's actually applied

### Deferred Migration Codebase Usage (Full Audit)

**`034_ga4_attribution_forensics.sql` (4 tables):**

Tables: `ga4_source_medium_daily`, `ga4_landing_page_quality_daily`, `ga4_attribution_root_cause_daily`, `ga4_shopify_reconciliation_daily`

Active codebase references:
- `dashboard/src/lib/ga4/forensics.ts` — lib file
- `dashboard/src/app/api/ga4/snapshot-capture/route.ts` — API route
- `dashboard/src/lib/ga4/__tests__/attribution-thresholds.test.ts` — tests
- `dashboard/src/app/api/ga4/__tests__/snapshot-capture.route.test.ts` — tests

**`035_unified_intent_execution_system.sql` (14 tables):**

Tables: `intent_taxonomy_versions`, `term_intent_state`, `policy_decision_log`, `policy_action_execution_log`, `policy_snapshots`, `sku_margin_daily`, `order_line_returns_daily`, `attribution_confidence_daily`, `experiment_registry`, `experiment_assignments`, `experiment_outcomes`, `negative_registry`, `search_buildout_recommendations`, `operator_review_audit`

Active codebase references (10+ API routes + test files):
- `dashboard/src/lib/intent/tier-movement.ts`, `value-signal.ts`, `profit-forecast.ts`
- `dashboard/src/app/api/search/governance/*` (5 routes)
- `dashboard/src/app/api/intent/*` (7 routes)
- `dashboard/src/app/api/experiments/*` (3 routes)
- Multiple `__tests__/` files

**Recommendation**: Since both deferred migration files have extensive code references, they are likely needed for future phases. However, the CONTEXT.md decision is to defer them. Rename with a non-conflicting prefix (e.g., `034b_` and `035b_`) and document reasons in a migration audit note.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Applying SQL | Manual psql or copying SQL | Supabase MCP `execute_sql` | Stays in Claude context, immediate feedback, no paste errors |
| Schema verification | Manual table inspection | `information_schema.columns` queries | Deterministic, returns exact column types and nullability |
| API testing | curl or browser | `execute_sql` to verify data + `information_schema` | Controlled, documents what was verified |

**Key insight**: All the hard work (TypeScript routes, Python writing, SCHEMA.md table sections) is already done. The phase is purely DDL execution + documentation completion. The risk is NOT in the SQL itself (all IF NOT EXISTS) but in verifying the right state before and after.

---

## Common Pitfalls

### Pitfall 1: Assuming SCHEMA.md Is Complete When It Has Gaps

**What goes wrong**: SCHEMA.md already has sections for `regeneration_history`, `prompt_version_aliases`, `sku_bottleneck_classifications`, and `gmc_product_status` — so it looks complete. But `publish_events` is missing the 4 new lineage columns from migration 034, and `final_payload_snapshot` from migration 033 may also be absent.

**Why it happens**: Documentation was written ahead of migration application (speculative docs), but `publish_events` was updated later.

**How to avoid**: Query `information_schema.columns WHERE table_name = 'publish_events'` on live DB after applying migration, then compare against SCHEMA.md docs.

**Warning signs**: The `publish_events` section in SCHEMA.md (line 329) shows only ~16 columns and doesn't include `final_payload_hash`, `prompt_hash`, `evidence_hash`, `segment_key`, or `final_payload_snapshot`.

### Pitfall 2: Applying Migrations Without Pre-Check

**What goes wrong**: Running migration 034 when some columns already exist (e.g., if someone ran it manually before).

**Why it happens**: Skipping the pre-check step.

**How to avoid**: Before applying each migration, run:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'publish_events'
  AND column_name IN ('final_payload_hash', 'prompt_hash', 'evidence_hash', 'segment_key');
```
All IF NOT EXISTS means re-running is safe, but a pre-check confirms current state.

**Warning signs**: Migration runs without error but shows 0 columns added — means they already existed.

### Pitfall 3: Verifying Migrations Without End-to-End Test

**What goes wrong**: Schema checks pass (columns exist) but `/api/prompt-lineage` returns `lineage: null` for all SKUs because no publish event has `prompt_hash` set yet.

**Why it happens**: The migration unlocks the code path, but data must be written by a real publish or manual INSERT before the API can return non-null lineage.

**How to avoid**: After migration 034, either:
- (A) Trigger a real SKU publish through the UI to generate a `prompt_hash`-populated publish event
- (B) INSERT a synthetic test row directly using `execute_sql`:
```sql
INSERT INTO publish_events (master_sku, platform, environment, action, status, prompt_hash, published_at)
VALUES ('WP-2/16-GAL', 'google', 'production', 'publish', 'success', 'test-hash-abc123', now())
RETURNING id;
```

**Warning signs**: `/api/prompt-lineage?master_sku=X` returns `{"lineage": null, "note": "No successful publish events..."}`

### Pitfall 4: Duplicate Migration Number Confusion

**What goes wrong**: The file renaming for deferred migrations is done inconsistently, leaving the directory in an ambiguous state (two files both starting with `034_`).

**Why it happens**: Renaming files without a clear convention.

**How to avoid**: Rename deferred files to a clearly distinguished prefix before closing the phase. Example pattern:
- `034_ga4_attribution_forensics.sql` → `034b_ga4_attribution_forensics.sql` (or `034_DEFERRED_ga4_attribution_forensics.sql`)
- `035_unified_intent_execution_system.sql` → `035b_unified_intent_execution_system.sql`

Document the reason in a `MIGRATION_AUDIT.md` or in the CONTEXT.md deferred section.

### Pitfall 5: Python Code Not Persisting Measurement Data

**What goes wrong**: Migration 035 applied, columns exist, but `regeneration_history` rows don't have `feature_flags_active` populated.

**Why it happens**: `capture_flag_snapshot()` in `main.py` may return None or empty if env vars aren't set, or the code path that writes it isn't triggered.

**How to avoid**: After migration 035, trigger a real regeneration via the UI and query:
```sql
SELECT feature_flags_active, tokens_used, latency_ms, cost_usd, created_at
FROM regeneration_history
ORDER BY created_at DESC LIMIT 5;
```
If columns are NULL, check `capture_flag_snapshot()` implementation in `main.py`.

---

## Code Examples

### Pre-Migration State Check

```sql
-- Check which migration 034 columns exist
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'publish_events'
  AND column_name IN ('final_payload_hash', 'prompt_hash', 'evidence_hash', 'segment_key', 'final_payload_snapshot');

-- Check which migration 035 tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('prompt_version_aliases', 'sku_bottleneck_classifications', 'gmc_product_status');

-- Check which migration 035 columns exist on regeneration_history
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'regeneration_history'
  AND column_name IN ('feature_flags_active', 'tokens_used', 'latency_ms', 'cost_usd');
```

### Post-Migration Verification

```sql
-- Verify migration 034 applied: publish_events columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'publish_events'
ORDER BY ordinal_position;

-- Verify migration 034 applied: new indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'publish_events'
  AND indexname IN ('idx_publish_events_final_payload_hash', 'idx_publish_events_prompt_hash', 'idx_publish_events_segment_key');

-- Verify migration 035 applied: new tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('prompt_version_aliases', 'sku_bottleneck_classifications', 'gmc_product_status');

-- Verify regeneration_history columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'regeneration_history'
  AND column_name IN ('feature_flags_active', 'tokens_used', 'latency_ms', 'cost_usd');

-- Verify GIN index on feature_flags_active
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'regeneration_history'
  AND indexname = 'idx_regen_history_flags';
```

### SCHEMA.md Gap: publish_events Columns to Add

The current `publish_events` documentation (line 329) needs these columns added to the Columns table:

```markdown
| final_payload_snapshot | jsonb | YES | - | Post-expansion channel-ready payload snapshot for audit/debug (migration 033) |
| final_payload_hash | text | YES | - | SHA-256 of canonicalized final_payload_snapshot JSON (migration 034) |
| prompt_hash | text | YES | - | Prompt identity hash used for generation lineage (migration 034) |
| evidence_hash | text | YES | - | SHA-256 of canonicalized evidence input at publish time (migration 034) |
| segment_key | text | YES | - | Normalized custom_label_0 segment key (lowercased, collapsed whitespace) (migration 034) |
```

And these indexes:
```markdown
- `idx_publish_events_final_payload_hash` on `final_payload_hash`
- `idx_publish_events_prompt_hash` on `prompt_hash`
- `idx_publish_events_segment_key` on `segment_key`
```

And an example query:
```sql
-- Get lineage for a published SKU
SELECT id, published_at, prompt_hash, evidence_hash, segment_key
FROM publish_events
WHERE master_sku = 'WP-2/16-GAL'
  AND platform = 'google'
  AND prompt_hash IS NOT NULL
ORDER BY published_at DESC LIMIT 5;
```

### Synthetic Test Row for End-to-End Verification

```sql
-- Insert test publish event with prompt_hash to verify /api/prompt-lineage
INSERT INTO publish_events (
  master_sku, platform, environment, action, status,
  prompt_hash, final_payload_hash, evidence_hash, segment_key,
  published_at
) VALUES (
  'WP-2/16-GAL', 'google', 'production', 'publish', 'success',
  'test-prompt-hash-abc123',
  'test-payload-hash-def456',
  'test-evidence-hash-ghi789',
  'towel-bars',
  now()
) RETURNING id;

-- Then test /api/prompt-lineage?master_sku=WP-2/16-GAL&platform=google
-- Expected: returns lineage object with prompt_hash, not null
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual SQL copy-paste to Supabase dashboard | Supabase MCP `execute_sql` in Claude | This phase | Reduces human error, keeps audit trail in conversation |
| Speculative SCHEMA.md docs | Verified-against-live SCHEMA.md | This phase | Docs become authoritative reference |
| Publishing without lineage tracking | Publishing writes `prompt_hash` to `publish_events` | After migration 034 applied | Enables `/api/prompt-lineage` to function |

---

## Open Questions

1. **Is `final_payload_snapshot` (migration 033) already applied to live DB?**
   - What we know: The file `033_add_publish_event_final_payload_snapshot.sql` exists. The `supabase/types.ts` includes `final_payload_snapshot` in `PublishEvent` interface (line 64).
   - What's unclear: Whether migration 033 was previously applied to live Supabase.
   - Recommendation: Run the pre-check query before applying anything. If `final_payload_snapshot` exists, 033 was applied. If not, apply it before 034.

2. **Will deferred migrations cause errors for existing API routes that reference their tables?**
   - What we know: Many API routes (`/api/intent/*`, `/api/experiments/*`, `/api/ga4/*`, `/api/search/governance/*`) query these tables. If the tables don't exist in live DB, those routes will fail.
   - What's unclear: Whether these routes are currently returning 500 errors or whether the tables were applied previously through another mechanism.
   - Recommendation: Run a pre-check for the deferred tables too:
     ```sql
     SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public'
       AND table_name IN ('intent_taxonomy_versions', 'term_intent_state', 'experiment_registry', 'ga4_source_medium_daily');
     ```
     If they already exist, the deferred migrations were applied out-of-band and renaming the files is sufficient. If they don't exist, those API routes are currently broken — which would be out of scope for this phase but important to note.

3. **What is the current `prompt_hash` field state in `regeneration_history`?**
   - What we know: `regeneration_history.prompt_hash` column exists (it's in the base schema, not migration 035). Python writes `prompt_hash` to it already.
   - What's unclear: Whether existing rows have `prompt_hash` populated.
   - Recommendation: After migration 035, check `SELECT COUNT(*) FROM regeneration_history WHERE prompt_hash IS NOT NULL` to understand whether immediate backfill of `publish_events.prompt_hash` is feasible via a join.

---

## Sources

### Primary (HIGH confidence)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/034_add_publish_lineage_hashes.sql` — Full DDL, verified exact column names and index names
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/035_measurement_infrastructure_schema.sql` — Full DDL, verified all 4 schema operations
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/034_ga4_attribution_forensics.sql` — Deferred migration content
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/supabase/migrations/035_unified_intent_execution_system.sql` — Deferred migration content (14 tables)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/prompt-lineage/route.ts` — Full implementation of the lineage API
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/publishing/final-payload.ts` — How hashes are computed and written
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/api/main.py` lines 571-607 — Python measurement data capture
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` — Lines 329 (publish_events), 1268 (regeneration_history), 1340 (prompt_version_aliases), 1382 (sku_bottleneck_classifications), 1411 (gmc_product_status)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/publish/sku/route.ts` lines 789-804 — Fallback logic (confirms migration not yet applied)
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/api/publish/batch/route.ts` lines 1093-1110 — Same fallback in batch publish

### Secondary (MEDIUM confidence)
- Grep of all files referencing deferred table names — confirms 10+ API routes reference intent/experiment/ga4 tables from the deferred migrations

---

## Metadata

**Confidence breakdown:**
- Migration content: HIGH — files read directly, exact DDL verified
- SCHEMA.md gaps: HIGH — confirmed by reading both the schema and migration files
- Codebase fallback logic: HIGH — verified in publish routes
- Deferred migration codebase usage: HIGH — grep confirmed 10+ active references
- Open questions: MEDIUM — identified from codebase evidence, not yet confirmed against live DB

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (stable — DDL is static, no fast-moving library concerns)
