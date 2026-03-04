# Stack Research

**Domain:** Google Ads data lifecycle management, schema constraint design, entity relationship optimization, dead code cleanup
**Researched:** 2026-03-03
**Confidence:** HIGH (all findings verified against existing codebase, migration SQL, and live research files in /tmp)

---

## Context: Subsequent Milestone — What Already Exists

This is v1.1 of Allied-FeedOps. The full stack (FastAPI, Pydantic v2, Supabase Python client, Google Ads SDK, Cloud Run, pytest-asyncio, anthropic SDK) is production-validated. This research covers ONLY what the v1.1 feature set requires that is not already in place.

**Core stack (do not change):** FastAPI 0.109+, Pydantic v2, `supabase>=2.0`, `google-ads>=28.4.1`, `anthropic>=0.84.0`, Cloud Run, `run_async_in_thread()` pattern.

---

## Recommended Stack

### Core Technologies (New for v1.1)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Supabase migration SQL (native) | N/A — DDL only | Fix `performance_snapshots` unique constraint and audit all data table schemas | Migration 032 already written (`supabase/migrations/032_performance_impact_pipeline.sql`) — it contains the exact `ADD CONSTRAINT uq_performance_snapshots_daily UNIQUE (master_sku, platform, environment, snapshot_date)` fix. Apply it; do not rewrite. |
| PostgreSQL `UNIQUE` constraints | Native PostgreSQL — no library | Enforce upsert deduplication across `performance_snapshots`, `performance_impact_scores`, entity mapping tables | Supabase's `.upsert(on_conflict=...)` requires a matching UNIQUE constraint or composite PK. Missing constraint causes PostgreSQL error 42P10. Pattern already used correctly on 6/7 tables — `performance_snapshots` is the lone exception. |
| PostgreSQL `CHECK` constraints | Native PostgreSQL — no library | Enforce domain values on `cohort_type`, `platform`, `label` columns | Migration 032 already adds `CHECK (cohort_type IN ('treated', 'control'))` and `CHECK (label IN ('positive', 'negative', 'neutral'))`. Extend this pattern to `platform` column (currently unconstrained text). |
| PostgreSQL `FOREIGN KEY` constraints | Native PostgreSQL — no library | Enforce `ON DELETE CASCADE` from `publish_events` → `performance_impact_scores` | Already in 032: `publish_event_id BIGINT NOT NULL REFERENCES publish_events(id) ON DELETE CASCADE`. Audit remaining tables (`performance_snapshots.publish_event_id`) for missing FK enforcement. |

### Supporting Libraries (Already Present — No New Installations)

| Library | Version (installed) | Role in v1.1 | Notes |
|---------|---------------------|-------------|-------|
| `supabase>=2.0` | 2.x | Execute upserts with `on_conflict=` after constraints are in place | Already in pyproject.toml. No version change. |
| `google-ads>=28.4.1` | 28.4.1+ | `shopping_performance_view` queries for baseline + snapshot backfill | Already installed. PMax inclusion requires no SDK change — remove the `advertising_channel_type = 'SHOPPING'` filter from `search_term_view` queries only (performance view already includes PMax). |
| `pandas>=2.0` | 2.x | Batch aggregation during full-catalog baseline backfill | Already installed. Used in existing batch performance fetching path. |
| `pytest>=7.0` + `pytest-asyncio>=0.21` | existing | Regression tests for dead code removals (verify imports from new locations) | Already configured with `asyncio_mode = auto`. No changes. |
| `ruff>=0.1` | existing | Catch unused imports and circular imports after dead code cleanup | Run after EVERY file edit during cleanup. Already in dev dependencies. |

### Development Tools (Existing — No Changes)

| Tool | Purpose | Notes |
|------|---------|-------|
| `supabase db push` (Supabase CLI) | Apply migrations to production | Test locally with `supabase start` before pushing. Migration 032 has a dedup step (`DELETE FROM performance_snapshots WHERE rn > 1`) that must run before the UNIQUE constraint is added — already written correctly. |
| `ruff check src/feedops/` | Catch dead import artifacts during cleanup | Run after removing each dead code block. Use `ruff check --select F401` to find unused imports specifically. |
| `mypy --strict src/feedops/` | Verify type contracts hold after dead code removal | Particularly important for executor.py image wiring — `ImageInput | None` must flow correctly through `_generate_with_provider_compat()`. |
| `pytest -x tests/` | Fail-fast after each dead code removal | The test files that import from generator.py (test_prompt_sanitization_contract.py, test_pipeline.py) will break on import until those imports are updated to point at executor.py. |

---

## Installation

No new packages required. All dependencies already in `pyproject.toml`.

```bash
# Verify current install is complete
uv pip install -e ".[dev]"

# Apply migration 032 (the core fix)
# Local test first:
supabase start
supabase db push --local

# Production (after local verification):
supabase db push --project-ref qezuszwufortkiutlhym
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Apply existing migration 032 | Write a new migration for the constraint fix | Never — 032 is already correct and contains the dedup step. Writing a new migration risks applying the constraint before deduplicating rows (which would fail). |
| PostgreSQL native UNIQUE constraints | Application-level deduplication in Python (check-then-insert) | Never for this use case — check-then-insert has TOCTOU race conditions under concurrent inserts. DB constraints are the correct layer. |
| PostgreSQL native CHECK constraints | Pydantic enum validation only | Use Pydantic too, but CHECK constraints catch bad data inserted by raw SQL, migrations, or future code paths that bypass the Python layer. Both layers are appropriate. |
| `ruff` for dead code detection | `vulture` (finds dead Python code) | Use `vulture` as an additive scan if `ruff` misses orphaned functions. `ruff` finds unused imports (F401); `vulture` finds unused function definitions. Neither is a hard requirement — the dead-code-research.md already has the full inventory. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| New Python migration library (Alembic, Flyway) | Project uses Supabase migrations (raw SQL files in `supabase/migrations/`). Alembic would require schema reflection and create a competing migration history. | Supabase CLI + raw SQL migrations in existing `supabase/migrations/` directory. |
| `ON DELETE SET NULL` for `performance_snapshots.publish_event_id` | Snapshots orphaned from their publish events become uninterpretable for diff-in-diff calculation. Orphaned rows with NULL publish_event_id cannot be labeled as "treated". | `ON DELETE CASCADE` — delete the snapshot rows when the publish event is deleted. This is already the pattern in `performance_impact_scores`. |
| Partial index instead of UNIQUE constraint for `performance_snapshots` | A partial index (e.g., `WHERE cohort_type = 'treated'`) only enforces uniqueness on a subset of rows. Daily snapshot upserts happen for both treated and control cohorts. | Full UNIQUE constraint on `(master_sku, platform, environment, snapshot_date)` — already specified in the upsert's `on_conflict=` string. |
| Removing backward-compat re-exports in main.py before updating test imports | The re-exports in `main.py:174-304` are actively used by 5+ test files for monkeypatching. Removing them without updating tests breaks the test suite silently (import succeeds but attributes are missing). | Update each test file's import to point at the actual module location, run pytest, THEN remove the re-export. One module at a time. |
| Removing `_platform_reasoning_effort()` / `_platform_completion_cap()` from generator.py before updating test imports | `test_prompt_sanitization_contract.py` imports these directly from `feedops.pipeline.generator`. Removing them causes ImportError. | Update the test import to `feedops.generation.executor`, verify pytest passes, then delete from generator.py. |
| Adding a campaign_structure or negative_keywords table | The search term attribution is already approximate at campaign level (Google Ads API limitation — can't join `search_term` and `product_item_id`). A campaign structure table doesn't fix this fundamental API constraint. | Accept the approximation, document it in the schema, consider ad group-level product subdivision only if Google Ads API adds joint query support. |

---

## Schema Constraint Design Patterns

These patterns govern all new migrations in v1.1.

### Pattern 1: Upsert-Safe Unique Constraints

Every table that uses Supabase `.upsert(on_conflict="col1,col2")` MUST have a matching UNIQUE constraint. Audit checklist:

| Table | `on_conflict` columns | Has matching constraint? | Action |
|-------|----------------------|--------------------------|--------|
| `performance_baselines` | `master_sku, platform` | YES (composite PK) | None |
| `performance_snapshots` | `master_sku, platform, environment, snapshot_date` | NO — **APPLY MIGRATION 032** | Apply 032 |
| `performance_impact_scores` | `publish_event_id, metric_name, platform, environment` | YES (from 032) | None once 032 applied |
| `search_queries` | `query_text, gmc_offer_id, period_start, period_end` | YES | None |
| `search_queries_by_master_sku` | `master_sku, query_text, period_start, period_end` | YES | None |
| `keyword_metrics` | `keyword` | YES (PK) | None |
| `funnel_snapshots_daily` | `snapshot_date, custom_label_0, tier` | YES | None |

### Pattern 2: Offer ID Normalization

`variant_index.gmc_offer_id` stores lowercase (`shopify_us_`). Google Ads returns uppercase (`shopify_US_`). Always normalize to lowercase before database lookups:

```python
# Correct normalization (already in search_terms code):
offer_id.lower()

# Must also be applied in:
# - google_ads_performance.py batch performance queries
# - Any new backfill code that feeds offer_ids into variant_index lookups
```

### Pattern 3: PMax Campaign Inclusion

For performance baselines and snapshots, `shopping_performance_view` already returns PMax campaign data — no filter change needed. For search term sync, the existing `advertising_channel_type = 'SHOPPING'` filter in `search_term_view` intentionally excludes PMax (PMax search terms are not actionable via negative keywords). Do NOT add PMax to search term queries.

---

## Entity Relationship Map (Reference for New Code)

```
variant_index (72K rows) — THE HUB
  ├── gmc_offer_id (lowercase) ← Google Ads product_item_id (uppercase — normalize on read)
  ├── master_sku → performance_baselines, performance_snapshots, search_queries_by_master_sku
  ├── shopify_product_id → Shopify product GraphQL
  ├── shopify_variant_id → Shopify variant GraphQL
  └── finish_code → 28 finishes, variant_finish_sentences

publish_events
  ├── master_sku
  ├── published_at (used for pre/post window calculation)
  └── id → performance_impact_scores.publish_event_id (FK CASCADE — in 032)
           └── performance_snapshots.publish_event_id (FK — currently unenforced, add in migration)
```

The only structural gap is `performance_snapshots.publish_event_id` lacking an FK to `publish_events`. Add this FK when applying migration 032's follow-up migration.

---

## Dead Code Removal Stack Requirements

Dead code cleanup requires no new libraries. The existing `ruff + pytest + mypy` stack is sufficient. Removal order matters:

1. **Trivially dead (no deps, remove immediately):** `_payload_value_lengths()`, `_schema_hash()`, `_prompt_hash()`, `_generate_with_provider_compat()` copy in generator.py, `_provider_label` re-export in finish_processing.py, finish processing re-exports in generation.py, `build_variant_adaptation_prompt()` in tasks.py, `serialize_task_result()` in persistence.py.

2. **Requires test import updates first:** `_platform_reasoning_effort()`, `_platform_completion_cap()` in generator.py (update `test_prompt_sanitization_contract.py` to import from `executor.py`); variant generation functions in generator.py (update `test_pipeline.py`); `_build_generation_user_prompt()` in generation.py (update `tests/api/test_generation.py`); main.py re-exports block (update 5+ test files).

3. **Additive feature (not removal):** Image wiring in executor.py — import `fetch_image` from `feedops.pipeline.images`, add `image` parameter to `_generate_with_provider_compat()`, pass `image=image` in `execute_generation_bundle()` for non-finish-sentence tasks.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `supabase>=2.0` | Python `>=3.11` | No conflict with project requirement |
| `google-ads>=28.4.1` | `grpcio>=1.49` | Already installed transitively — no change |
| PostgreSQL migration 032 | Supabase hosted PostgreSQL 15 | Uses standard DDL (no PostgreSQL 16+ features). Safe to apply. |
| `ruff>=0.1` | Python `>=3.9` | No conflict |

---

## Sources

- `/tmp/google-ads-import-research.md` — Live codebase research (2026-03-03): constraint audit, ON CONFLICT bug root cause, entity mapping gaps, scheduled job architecture — HIGH confidence (verified against live DB row counts and migration SQL)
- `/tmp/dead-code-research.md` — Live codebase research (2026-03-03): function-level dead code inventory with file/line citations — HIGH confidence (verified via grep against source files)
- `supabase/migrations/032_performance_impact_pipeline.sql` — Contains the exact fix for the performance_snapshots constraint bug (dedup step + ADD CONSTRAINT). Verified correct — HIGH confidence
- `pyproject.toml` — Verified all listed libraries already present. No new pip installs required for v1.1 — HIGH confidence
- `docs/database/SCHEMA.md` — 56 tables documented, constraint patterns verified — HIGH confidence

---

*Stack research for: v1.1 Dead Code Cleanup + Data Infrastructure (Allied-FeedOps)*
*Researched: 2026-03-03*
