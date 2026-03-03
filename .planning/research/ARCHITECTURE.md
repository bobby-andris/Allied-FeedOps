# Architecture Research

**Domain:** Data infrastructure hardening + dead code cleanup for existing Python/FastAPI content generation pipeline
**Researched:** 2026-03-03
**Confidence:** HIGH (based on direct codebase inspection, live database constraint analysis, and pre-existing research files at /tmp/)

---

## Standard Architecture

### System Overview

The existing architecture is a dual-layer system: a Python/FastAPI Cloud Run pipeline for content generation and data collection, and a Next.js/Vercel dashboard for review and publishing. The v1.1 milestone operates exclusively on the Python layer and database schema — the dashboard is explicitly out of scope.

```
┌────────────────────────────────────────────────────────────────────┐
│                    Next.js Dashboard (Vercel)                      │
│  ensure-data.ts (auto-triggers baseline/search collection)         │
│  funnel-snapshots/capture/route.ts (Cloud Scheduler, 6 AM UTC)     │
└─────────────────────┬──────────────────────┬───────────────────────┘
                      │ HTTP                  │ HTTP
┌─────────────────────▼──────────────────────▼───────────────────────┐
│              Python FastAPI — Cloud Run                            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  API Entry (main.py + routes.py)                            │  │
│  │  Content: /optimize-sku /regenerate /batch-optimize         │  │
│  │  Data:    /performance/* /search-insights/* /backfill/*     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│  ┌──────────────────┐  ┌─────▼────────────┐  ┌──────────────────┐  │
│  │ generation/      │  │ backfill.py      │  │ performance_     │  │
│  │ executor.py      │  │ (4 job types:    │  │ baseline.py      │  │
│  │                  │  │  search_terms,   │  │ + performance_   │  │
│  │ [IMAGE GAP HERE] │  │  perf_metrics,   │  │ impact.py        │  │
│  │ image= not wired │  │  keyword_planner,│  │                  │  │
│  │ in modern path   │  │  custom_labels)  │  │ [SNAPSHOT BUG]   │  │
│  └──────────────────┘  └────────┬─────────┘  └──────┬───────────┘  │
│                                 │                    │             │
│  ┌──────────────────────────────▼────────────────────▼───────────┐  │
│  │              Integration Layer                                │  │
│  │  google_ads_performance.py  (shopping_performance_view)       │  │
│  │  google_ads_search_terms.py (search_term_view + KW planner)   │  │
│  │  LLM providers (Claude Sonnet 4.6)                            │  │
│  └──────────────────────────────────────┬──────────────────────┘  │
│              run_async_in_thread()       │                         │
│              (non-daemon thread pattern) │                         │
└─────────────────────────────────────────┼──────────────────────────┘
                           Cloud Scheduler │ (3 jobs)
                           2:15 AM /backfill/start
                           2:45 AM /performance/capture-snapshot
                           6:00 AM /api/funnel-snapshots/capture (Vercel)
                                          │
┌─────────────────────────────────────────▼──────────────────────────┐
│                    Supabase PostgreSQL                              │
│                                                                    │
│  variant_index (72K) ← central entity hub                         │
│  performance_baselines (274 rows — on-demand only)                │
│  performance_snapshots (179 rows — BROKEN upsert, should be 2500+)│
│  performance_impact_scores (0 rows — blocked by snapshot failure)  │
│  search_queries (189K rows — healthy)                              │
│  keyword_metrics (1.5K rows — healthy)                             │
│  funnel_snapshots_daily (5K rows — healthy)                        │
└────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `routes.py` | FastAPI route handlers (thin delegates) | `src/feedops/api/routes.py` |
| `generation.py` | Content generation orchestration | `src/feedops/api/generation.py` |
| `executor.py` | Per-platform task execution (modern path) | `src/feedops/generation/executor.py` |
| `generator.py` | Legacy generation (optimize.py CLI + tests) | `src/feedops/pipeline/generator.py` |
| `backfill.py` | Bulk data collection job management (4 types) | `src/feedops/api/backfill.py` |
| `performance_baseline.py` | API routes: capture-baseline, collect-daily, compute-impact | `src/feedops/api/performance_baseline.py` |
| `performance_impact.py` | Snapshot collector + diff-in-diff scorer | `src/feedops/monitoring/performance_impact.py` |
| `google_ads_performance.py` | shopping_performance_view client (batch + single) | `src/feedops/integrations/google_ads_performance.py` |
| `google_ads_search_terms.py` | SearchTermsClient + KeywordPlannerClient | `src/feedops/integrations/google_ads_search_terms.py` |
| `persistence.py` | Supabase write operations | `src/feedops/api/persistence.py` |
| `job_management.py` | Job state machine | `src/feedops/api/job_management.py` |
| `alerts.py` | Slack webhook + Resend email notifications | `src/feedops/observability/alerts.py` |
| `telemetry.py` | `run_async_in_thread()` background task lifecycle | `src/feedops/api/telemetry.py` |
| `variant_index` table | Central entity hub: GMC offer ID ↔ master_sku ↔ Shopify ↔ finish | Supabase |

---

## What Is New vs. What Is Modified

### New (v1.1 only creates one file)

| New Component | Type | Purpose |
|--------------|------|---------|
| `src/feedops/api/utils.py` | Python module | Shared utilities (_require_request_id) to break circular import between persistence.py and job_management.py |
| Migration `036_performance_snapshot_constraint.sql` | SQL migration | Adds unique constraint on performance_snapshots (master_sku, platform, environment, snapshot_date) |

### Modified (existing files changed in v1.1)

| File | Change Type | What Changes |
|------|------------|-------------|
| `src/feedops/api/main.py` | Dead code removal | Remove ~130-line re-export block (after updating 5 test files) |
| `src/feedops/api/routes.py` | Dead code removal | Remove ~14 unused imports |
| `src/feedops/api/generation.py` | Dead code removal | Remove re-exports of finish_processing internals; deprecate _build_generation_user_prompt |
| `src/feedops/api/finish_processing.py` | Dead code removal | Remove unused _provider_label re-export |
| `src/feedops/api/persistence.py` | Refactor | Import _require_request_id from utils.py instead of defining locally |
| `src/feedops/api/job_management.py` | Refactor | Import _require_request_id from utils.py instead of defining locally |
| `src/feedops/generation/executor.py` | Feature | Wire image parameter: fetch image from parent_sku, pass to llm.generate() (~15 lines) |
| `src/feedops/generation/tasks.py` | Dead code removal | Remove build_variant_adaptation_prompt(), VARIANT_*_TASK_SCHEMA |
| `src/feedops/generation/persistence.py` | Dead code removal | Remove serialize_task_result() |
| `src/feedops/pipeline/generator.py` | Dead code removal | Remove 5 orphaned functions, then 6 variant generation functions (after test updates) |
| `src/feedops/monitoring/performance_impact.py` | No code change | Upsert already correct — works after migration 036 is applied |
| Multiple test files (~8) | Test updates | Update import paths to point at actual modules, not main.py re-exports |

---

## Architectural Patterns

### Pattern 1: Schema Migration Before Code Fix

**What:** Add the missing unique constraint to `performance_snapshots` as a Supabase migration — no Python code change needed. The upsert code in `performance_impact.py:461` already specifies the correct ON CONFLICT columns. The database just lacks the constraint.

**When to use:** Any time an upsert silently fails with PostgreSQL error 42P10 (no matching unique constraint). The fix is always a migration, never a code rewrite.

**Trade-offs:** Migration is one-way in production. Test with a dry-run `EXPLAIN` to confirm the planner will use the constraint before deploying.

**Example:**
```sql
-- Migration: 036_performance_snapshot_constraint.sql
ALTER TABLE performance_snapshots
ADD CONSTRAINT uq_snapshots_sku_platform_env_date
UNIQUE (master_sku, platform, environment, snapshot_date);
```

### Pattern 2: Test-First Dead Code Removal

**What:** Dead code in this codebase is entangled with test imports. The correct sequence is: update the test import → verify tests pass → delete the dead code. Never delete code first.

**When to use:** Every item in the "Requires test updates first" category (5 groups, ~8 test files).

**Trade-offs:** Slightly more granular PRs, but prevents silently breaking the test suite. The test suite is the only safety net for these cleanup changes.

**Example sequence:**
```
1. Edit test_prompt_sanitization_contract.py:
   from feedops.generation.executor import _platform_reasoning_effort
   (was: from feedops.pipeline.generator import _platform_reasoning_effort)
2. Run: PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v
3. Confirm all tests pass
4. Delete _platform_reasoning_effort() from generator.py
5. Run tests again — confirm still passing
```

### Pattern 3: Additive Image Wiring (Not a Refactor)

**What:** Wire the `image` parameter through `executor.py`'s `execute_generation_bundle()` to `_generate_with_provider_compat()` to `llm.generate()`. The provider layer (Claude, OpenAI) already accepts this parameter. This is a pure addition — callers with no image get `image=None` behavior unchanged.

**When to use:** Any time the modern per-platform path needs to send multimodal input to the LLM. The legacy `generate_candidates()` path already does this correctly in generator.py.

**Trade-offs:** Adds one async network call (image fetch) per SKU during generation. Acceptable since `fetch_image()` is async and product images are used by Claude for visual context.

**Example (executor.py, ~15 lines total):**
```python
# In execute_generation_bundle(), before the task loop:
from feedops.pipeline.images import fetch_image  # existing utility

image = None
if parent_sku.variants:
    main_image_url = parent_sku.variants[0].main_image_url
    if main_image_url:
        image = await fetch_image(main_image_url)

# In _generate_with_provider_compat(), add image to signature and forward:
async def _generate_with_provider_compat(
    llm: LLMProvider, prompt, schema, ..., image=None
) -> dict:
    return await llm.generate(prompt, schema, ..., image=image)
    # Skip image for finish sentence tasks:
    # if task_kind == GenerationTaskKind.FINISH_SENTENCE: image = None
```

### Pattern 4: Circular Import Resolution via Shared Utility Module

**What:** `_require_request_id()` is duplicated in `persistence.py` and `job_management.py` because importing from each other creates a cycle. Extract to `feedops.api.utils` — a new module that neither of them imports from.

**When to use:** Any utility function needed by two modules in the same package that mutually import each other.

**Trade-offs:** Adds one new file but eliminates duplication and removes the misleading "duplicated here to avoid circular import" comment.

---

## Data Flow

### Critical Path: Daily Snapshot Collection (Currently Broken → Fixed by Migration 036)

```
Cloud Scheduler (2:45 AM ET)
    → POST /performance/capture-snapshot
        → capture_snapshot_compat()
            → collect_daily_performance_snapshots()
                1. Load all publish_events (treated SKUs, last 365 days)
                2. Load ALL variant_index rows (72K) for control SKU set
                3. For D-1, D-2, D-3 rolling dates:
                   a. fetch_batch_product_performance() [25 IDs/chunk, 5 threads]
                   b. Aggregate by master_sku
                   c. Label treated vs control cohorts
                   d. UPSERT performance_snapshots  ← NOW SUCCEEDS (after migration 036)
            → compute_and_store_impact_scores()
                1. Load snapshots (now populated)
                2. Compute diff-in-diff lift
                3. UPSERT performance_impact_scores  ← NOW REACHED
    → send_slack_notification()  ← reports SUCCESS instead of FAILED
```

**Before migration 036:** Step 3d raises PostgreSQL 42P10 every night. Result: 179 snapshot rows, 0 impact score rows, daily Slack FAILED alerts.

**After migration 036:** Step 3d upserts correctly. Rows accumulate daily. Impact scores populate. Slack reports success.

### Path: Performance Baseline Collection (On-Demand, Working — Coverage Gap)

```
User triggers regeneration or SKU selection
    → ensureSkuData() [dashboard, ensure-data.ts]
        → POST /performance/capture-baseline [Cloud Run]
            → For each master_sku in request:
                1. Query variant_index → get all gmc_offer_ids
                2. fetch_batch_product_performance() [25 IDs/chunk, 5 threads]
                3. Aggregate metrics across all variants
                4. UPSERT performance_baselines (master_sku, platform)  ← WORKS
```

**Coverage gap:** Only 274 of ~2,500 master SKUs have baselines because collection is on-demand. The backfill job type `performance_metrics` closes this gap when run via `/backfill/start`. No code change needed — the infrastructure exists.

### Path: Bulk Data Backfill (Existing Infrastructure, Available for Full Coverage)

```
POST /backfill/start { job_type: "performance_metrics" }
    → create backfill job record
    → run_async_in_thread(collect_performance_batch)
        → Load all master_skus from variant_index
        → For each SKU (with google_ads_limiter, 10 QPS):
            → fetch_batch_product_performance()
            → UPSERT performance_baselines
        → Slack notification on completion
```

Available job types: `search_terms`, `performance_metrics`, `keyword_planner`, `custom_labels`, `full_backfill` (all four sequentially).

---

## Entity Relationships

```
variant_index (72K rows) — CENTRAL HUB
    │
    ├── master_sku ──────────► performance_baselines (274 rows)
    │                    ├──── performance_snapshots (179 rows — BROKEN)
    │                    └──── search_queries_by_master_sku (7.4K rows)
    │
    ├── gmc_offer_id ────────► Google Ads shopping_performance_view
    │                          (product_item_id field)
    │
    ├── shopify_product_id ──► Shopify product API
    ├── shopify_variant_id ──► Shopify variant API
    └── finish_code ─────────► 28 finish variants

publish_events
    ├── master_sku ──────────► links content changes to SKUs
    ├── published_at ────────► timestamp for pre/post window calculation
    └── id ──────────────────► performance_impact_scores.publish_event_id (FK)
                                performance_snapshots.publish_event_id (FK)

search_queries (189K rows) — variant-level
    └── gmc_offer_id ────────► variant_index.gmc_offer_id (soft ref, no FK)
```

**Offer ID case handling:** `variant_index` stores lowercase `shopify_us_`, Google Ads returns uppercase `shopify_US_`. Search terms code normalizes correctly. Performance code uses `variant_index` values directly (already lowercase, matches Google Ads queries that use the same values).

---

## Build Order (Dependency-Aware)

### Step 1: Schema Migration — Fix Snapshot Upsert

**What:** Write and deploy migration 036 (`UNIQUE (master_sku, platform, environment, snapshot_date)` on `performance_snapshots`).

**Why first:** Single highest-value change. Unblocks daily snapshot collection and impact scores. Zero Python code changes, zero regression risk. The constraint does not break any existing reads.

**Verification:** After deploying, manually call `POST /performance/capture-snapshot`. Check Slack for success message (not FAILED). Query `SELECT COUNT(*) FROM performance_snapshots` and confirm rows increasing. Query `SELECT COUNT(*) FROM performance_impact_scores` and confirm rows appearing.

**Files changed:** One new migration SQL file only.

---

### Step 2: Trivial Dead Code Removal — No Test Dependencies

**What:** Remove 8 orphaned items with zero runtime or test callers.

| Item | File | Lines |
|------|------|-------|
| `_payload_value_lengths()` | generator.py | 138-148 |
| `_schema_hash()` | generator.py | 184-187 |
| `_prompt_hash()` | generator.py | 190-193 |
| `_generate_with_provider_compat()` | generator.py | 151-181 |
| `_provider_label` re-export | finish_processing.py | 7 |
| Finish processing re-exports | generation.py | 26-30 |
| `build_variant_adaptation_prompt()` | tasks.py | 162-236 |
| `serialize_task_result()` | generation/persistence.py | 38-58 |

**Why second:** No dependencies on any other step. Fast, risk-free wins.

**Verification:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` — must pass with zero failures.

---

### Step 3: Image Wiring in executor.py — Additive Feature

**What:** Thread `image: ImageInput | None` through `execute_generation_bundle()` → `_generate_with_provider_compat()` → `llm.generate()`. ~15 lines. Import `fetch_image` from `feedops.pipeline.images`.

**Why third:** Additive, no removals. Independent of Steps 2 and 4.

**Verification:** Trigger `/regenerate` for one SKU that has a `main_image_url` in `variant_index`. Verify generation succeeds and Cloud Run logs show image was fetched and sent to Claude.

---

### Step 4: Test-Dependent Dead Code Removal — In Sub-Steps

Execute each sub-step as update-test → run tests → remove code:

**4a.** Update `test_prompt_sanitization_contract.py` imports → remove `_platform_reasoning_effort()` and `_platform_completion_cap()` from `generator.py`.

**4b.** Update `test_pipeline.py` to remove `build_variant_prompt` import → remove 6 variant generation functions from `generator.py` (lines 423-937).

**4c.** Update `tests/api/test_generation.py` (3 functions) to call `build_core_prompt()` directly → remove `_build_generation_user_prompt()` from `generation.py`.

**Why fourth:** Requires coordination across multiple test files. Do one sub-step at a time with a full test run between each.

---

### Step 5: main.py Re-export Block Removal

**What:** Update the 5 test files that monkeypatch via `feedops.api.main.*` to import from actual module locations. Then remove the ~130-line re-export block from `main.py`.

**Why last among dead code:** Most impactful but highest coordination cost. Touching 5+ test files in one PR. Do after Steps 2-4 establish confidence in the test-update pattern.

**Files:** `tests/test_phase7_observability_reliability.py`, `tests/test_generation_runtime_scope_contract.py`, `tests/test_query_intent_lineage.py`, `tests/api/test_finish_prompt_source_contract.py`, `tests/api/test_main_master_sku_alias_runtime.py`

---

### Step 6: Shared Utils Extraction — Optional Cleanup

**What:** Create `feedops/api/utils.py`, move `_require_request_id()` from both `persistence.py` and `job_management.py`. Update import sites.

**Why optional/last:** No runtime bugs caused by this duplication. The comment in `persistence.py` documents why it's duplicated (circular import). Low urgency — can be a follow-up PR post-v1.1.

---

## Anti-Patterns

### Anti-Pattern 1: Fix the Upsert Code Instead of Adding the Constraint

**What people do:** Change `on_conflict="master_sku,platform,environment,snapshot_date"` in `performance_impact.py` to use a different conflict target, or switch to INSERT-only (no upsert).

**Why it's wrong:** The upsert logic is correct. The deduplication it provides is necessary — without it, every daily run creates new rows instead of updating existing ones, bloating the table indefinitely. The code is fine; the schema is wrong.

**Do this instead:** Add the unique constraint via migration. The Python code does not need to change.

### Anti-Pattern 2: Removing Code Before Updating Test Imports

**What people do:** Delete the dead function from `generator.py`, then discover tests fail because they import it from there.

**Why it's wrong:** Test failures block the PR and require a revert or an extra fix commit. The research already catalogued exactly which tests import each function.

**Do this instead:** Update the test import, run pytest, then delete the function. In that order, every time.

### Anti-Pattern 3: Bulk Removal of main.py Re-exports

**What people do:** Delete the entire ~130-line re-export block from `main.py` in one pass, then run tests to see what breaks.

**Why it's wrong:** Multiple test files monkeypatch via `feedops.api.main.*`. A bulk deletion creates a cascade of import errors across 5+ test files simultaneously, making it hard to attribute which removal broke which test.

**Do this instead:** Work through the 5 test files one at a time. Update each file's imports to point at the actual module, run pytest, confirm it still passes, then delete that symbol from the re-export block.

### Anti-Pattern 4: Adding a New Scheduler Job for Search Term Sync

**What people do:** Because search term sync is on-demand only, add a fourth Cloud Scheduler job calling `/search-insights/sync` directly to get automated coverage.

**Why it's wrong:** The backfill infrastructure already has a `search_terms` job type with rate limiting (10 QPS), idempotent upserts, and Slack notifications. Adding a direct Scheduler job would duplicate the mechanism and create competing sync jobs with no coordination.

**Do this instead:** If automated search term sync is needed, point a Cloud Scheduler job at `/backfill/start` with `job_type: "search_terms"`. It handles all the same logic with proper backfill controls.

### Anti-Pattern 5: Triggering Full SKU Baseline Backfill Through Dashboard ensure-data.ts

**What people do:** To close the 274/2500 baseline coverage gap, call the dashboard's `/api/sku-selection/generate` endpoint for all SKUs, which auto-triggers `ensureSkuData()` on each.

**Why it's wrong:** That path is designed for per-SKU on-demand collection triggered by user actions. Running it for 2,500 SKUs through the dashboard would create 2,500 sequential HTTP calls to Cloud Run without rate limiting.

**Do this instead:** Call `POST /backfill/start` with `job_type: "performance_metrics"`. The backfill infrastructure handles rate limiting (10 QPS), chunking (25 offer IDs per query), parallelism (5 threads), and progress tracking.

---

## Integration Points

### External Boundaries (Unchanged by v1.1)

| Service | Integration Pattern | v1.1 Impact |
|---------|---------------------|------------|
| Google Ads API | `google_ads_performance.py` + `google_ads_search_terms.py` | No changes |
| Supabase | `db/supabase_client.py::get_client()` per-request | Schema change (migration 036) only |
| Cloud Scheduler (3 jobs) | OIDC auth to Cloud Run + CRON_SECRET to Vercel | No changes — snapshot job starts succeeding |
| Claude Sonnet 4.6 | `providers/claude_provider.py` via AsyncAnthropic | executor.py now passes image= parameter |
| Slack webhook | `observability/alerts.py` via urllib | No changes — just sends success instead of failure |

### Internal Module Boundaries After v1.1

| Boundary | Communication | Change |
|----------|---------------|--------|
| `persistence.py` ↔ `job_management.py` | Both import `_require_request_id` from new `utils.py` | New file; circular import resolved |
| `executor.py` → `fetch_image()` | Direct async call | New import and call site in executor.py |
| `executor.py` → `llm.generate()` | Existing LLMProvider ABC | image= kwarg now forwarded |
| `performance_impact.py` → Supabase upsert | `on_conflict` spec already correct | Works after migration 036 |

---

## Sources

- `/tmp/dead-code-research.md` — Direct codebase inspection of all dead code items (HIGH confidence)
- `/tmp/google-ads-import-research.md` — Live database constraint analysis + source code trace to bug location (HIGH confidence)
- `src/feedops/monitoring/performance_impact.py:461` — Confirmed upsert bug location (HIGH confidence)
- `src/feedops/api/backfill.py` — Backfill job type routing and rate limiter configuration (HIGH confidence)
- `.planning/PROJECT.md` — v1.1 milestone scope and out-of-scope constraints (HIGH confidence)

---

*Architecture research for: Allied-FeedOps v1.1 data infrastructure hardening and dead code cleanup*
*Researched: 2026-03-03*
