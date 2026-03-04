# Feature Research

**Domain:** E-commerce data infrastructure — lifecycle management for performance data, dead code cleanup, and cross-platform entity mapping
**Researched:** 2026-03-03
**Confidence:** HIGH (all findings from live codebase inspection and pre-existing `/tmp/` research reports)

---

## Context: What Already Exists

This is a subsequent milestone. The features below address gaps in an existing, production system — not a greenfield build.

**Already implemented and working:**
- Performance baseline capture (on-demand, 274/~2,500 SKUs covered)
- Search term sync (on-demand, 189K rows)
- Keyword planner enrichment (cached 30-day TTL)
- Funnel tier daily snapshots (working — correct unique constraint)
- Daily performance snapshot capture (scheduled, but broken — see bug below)
- Slack webhook notifications for job status
- `run_async_in_thread()` background task pattern
- Google Ads integration: `shopping_performance_view` batch queries (chunked 25 IDs, 5 parallel threads)
- `variant_index` as the central entity mapping hub (72K rows)

**The actual gaps targeted by this milestone:**
- `performance_snapshots` missing unique constraint (daily job fails silently since launch)
- ~200+ lines of dead code across generator.py and extracted API modules
- ~130 lines of backward-compat re-exports in main.py (only exist for test compatibility)
- Offer ID case mismatch inconsistently handled in performance query paths
- Image support wired in legacy path but not in the modern per-platform generation path
- Only 274/~2,500 master SKUs have performance baselines (on-demand only, no bulk coverage)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the system must have for the data layer to be considered production-ready. Missing any of these means daily scheduled jobs failing silently, or metrics that cannot be trusted.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **performance_snapshots upsert constraint** | Daily snapshot job (2:45 AM ET) fails with PostgreSQL 42P10 every run — the table has no unique constraint on `(master_sku, platform, environment, snapshot_date)` yet the upsert code specifies exactly those columns | LOW | Single `ALTER TABLE` migration. Root cause confirmed: `performance_impact.py:461`. All other 6 data tables already have correct constraints. |
| **Impact scores population** | `performance_impact_scores` has 0 rows because it depends on snapshots — the upsert bug cascades. Without impact scores, post-publish ROI measurement is invisible | LOW | Unblocked entirely by the constraint fix above; no code change needed in `compute_and_store_impact_scores()`. |
| **Consistent offer ID normalization** | Google Ads returns `shopify_US_` (uppercase); `variant_index` stores `shopify_us_` (lowercase). Search term code normalizes correctly. Performance baseline code does not — it passes `variant_index.gmc_offer_id` values directly | MEDIUM | Audit all Google Ads query paths; apply normalization at the integration boundary in `google_ads_performance.py`, not at every call site. |
| **Dead function removal (trivially safe)** | 8 functions confirmed as completely orphaned — no callers at runtime or in tests: `_payload_value_lengths`, `_schema_hash`, `_prompt_hash`, `_generate_with_provider_compat` in generator.py; `_provider_label` re-export in finish_processing.py; finish processing re-exports in generation.py (lines 26-30); `build_variant_adaptation_prompt` in tasks.py; `serialize_task_result` in generation/persistence.py | LOW | Mechanical deletion. No callers anywhere. Reduces ~200 lines of noise with zero risk. |
| **main.py backward-compat re-export cleanup** | ~130 lines of re-exports in main.py (lines 174-304) exist only because 5+ test files import from `feedops.api.main` rather than the actual extracted modules. This is maintenance debt from DECOMP-09 | MEDIUM | Update 5 test files to import from real module locations, then delete the re-export block. Listed test files: `test_phase7_observability_reliability.py`, `test_generation_runtime_scope_contract.py`, `test_query_intent_lineage.py`, `test_finish_prompt_source_contract.py`, `test_main_master_sku_alias_runtime.py`. |
| **Image support wiring in executor.py** | The modern per-platform generation path (`/regenerate`, `/optimize-sku`, `/batch-optimize`, `/hybrid-generate`) does NOT send product images to the LLM. Only the legacy `optimize.py` CLI path sends images. Provider infrastructure already supports it (Claude + OpenAI both accept `ImageInput`). Gap is ~15 lines of wiring | LOW | Additive — no refactor required. Fetch image once before task loop in `execute_generation_bundle()`, pass through `_generate_with_provider_compat()`. Skip image for finish sentence tasks (they don't need it). |

### Differentiators (Competitive Advantage)

Features that go beyond fixing bugs and improve data quality and coverage scale.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Full catalog baseline backfill** | Only 274/~2,500 master SKUs have performance baselines (captured on-demand only). Backfilling all active SKUs provides a data-driven benchmark for every content optimization decision | MEDIUM | Use existing `fetch_batch_product_performance()` (chunked 25 IDs, 5 parallel threads). Validate whether the existing `feedops-daily-incremental-refresh` scheduler already handles this incrementally — if not, extend the `/backfill/start` endpoint to support a full-catalog sweep. |
| **Scheduled search term sync** | 189K search term rows exist but sync only triggers on SKU selection/regeneration. If no regeneration happens for 7+ days, search intelligence goes stale. A weekly scheduled sync keeps data fresh independently | LOW | The endpoint `/search-insights/sync` already exists and works. Add a `feedops-weekly-search-sync` Cloud Scheduler job pointing to it. Near-zero implementation cost. |
| **Generator.py duplicate consolidation** | 3 functions are duplicated between generator.py and executor.py: `_platform_reasoning_effort`, `_platform_completion_cap`, `_resolve_requested_platforms`. After test imports are updated, consolidating to executor.py as the single source eliminates divergence risk | MEDIUM | Blocked on test import updates first. After that, mechanical — redirect calls to executor.py version and delete generator.py copies. |
| **Circular import resolution** | `_require_request_id()` is duplicated in `persistence.py` and `job_management.py` because a direct import would create a circular dependency. Extracting to a shared `feedops.api.utils` module eliminates the duplication cleanly | LOW | Low risk. Requires import graph analysis to confirm the extracted location does not introduce new cycles. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like natural next steps but should be explicitly deferred.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time performance data** | Daily data feels stale — "why can't I see today's metrics?" | Google Ads data has inherent 24-48 hour processing lag (conversion data up to 3 days). Real-time polling hits API rate limits and returns incomplete data that changes retroactively. | Keep daily snapshots with rolling D-1/D-2/D-3 lag correction (already implemented in `collect_daily_performance_snapshots()`). Educate via UI on Google Ads data freshness. |
| **Product-level search term attribution** | "Which specific variant triggered this search?" seems like valuable precision | Google Ads API explicitly prevents joint queries of `search_term` and `product_item_id`. The campaign-level join (up to 10 products per campaign) is an API constraint, not a code limitation. No workaround exists within the standard API. | Accept and document campaign-level attribution. The 189K existing rows are still valuable for keyword optimization even with approximate attribution. |
| **PMax campaign search term inclusion** | Performance Max campaigns exist and are excluded from search term sync | PMax search term data requires asset group reporting, a different API surface than `search_term_view`. Requires feasibility research against the actual account campaign structure before any implementation attempt. | Flag as P3 pending account audit. Performance metrics (baselines/snapshots) already include PMax data since `shopping_performance_view` has no campaign type filter. |
| **Bing/Microsoft Ads data integration** | Schema has `platform` column; feels like natural extension | `bing_ads_performance.py` exists in integrations but is likely incomplete. Bing Shopping has a different API structure, campaign types, and attribution model. Adding Bing before Google data is fully operational creates two broken pipelines. | Defer until Google pipeline is validated end-to-end. The `platform` column in `performance_baselines` and `performance_snapshots` already supports it when ready. |
| **GA4 attribution tables** | Connecting content changes to revenue via GA4 sessions would close the loop | Migration `034b` (4 tables: GA4 attribution) is explicitly deferred per project constraints. 32 TypeScript files already reference tables from migration `035b` that don't exist — adding more deferred tables expands the scope of the problem. | Evaluate as its own milestone after v1.1 is stable. |
| **Removing optimize.py and the legacy generation path** | Dead code cleanup seems like it should include the full legacy path (~450 lines in generator.py) | `optimize.py` might still be used in the production Dockerfile CMD or as a debugging tool. Removing it without confirming zero production callers could break the CLI pipeline silently. | Audit the Dockerfile CMD and any scripts invoking `optimize.py` FIRST. Only remove after confirming no production callers. Mark as P3 pending that audit. |

---

## Feature Dependencies

```
[Snapshot upsert constraint fix (migration)]
    └──unblocks──> [Impact scores population]
                       └──enables──> [Post-publish ROI visibility in dashboard]

[Dead function removal — 8 trivially-safe items]
    └──no dependencies──> [Ship independently, zero risk]

[Test import updates (5 test files)]
    └──unblocks──> [main.py re-export removal (~130 lines)]
    └──unblocks──> [generator.py duplicate consolidation]
                       └──completes──> [executor.py as single source of truth]

[Offer ID normalization audit + fix]
    └──required before──> [Full catalog baseline backfill]
                              └──enables──> [Data-driven optimization for all 2,500 SKUs]

[Image wiring in executor.py]
    └──enhances──> [All modern generation endpoints (/regenerate, /optimize-sku, /batch-optimize)]
    └──independent of──> [Data infrastructure work — can ship in any phase]

[Generator.py legacy path audit]
    └──must precede──> [Legacy path removal]
    └──outcome determines──> [~450 lines removable or preserved]
```

### Dependency Notes

- **Snapshot constraint is the unlocker**: `compute_and_store_impact_scores()` already works correctly. The function exists, the logic is correct, it just has nothing to compute because snapshots cannot be inserted. Zero code changes needed after the schema fix.
- **Offer ID normalization before backfill**: A full catalog baseline backfill silently fails to match SKUs if the case mismatch is present in the performance query path. Fix normalization first to ensure backfill data is correctly attributed.
- **Test updates must precede import cleanup**: The main.py re-export block exists specifically for test monkeypatching compatibility. Remove the tests' dependency first, then the re-exports. Never delete re-exports before updating the tests.
- **Image wiring is fully independent**: Additive (~15 lines), touches no data infrastructure code, has no schema dependencies. Can slot into any phase without ordering constraints.
- **Legacy path removal requires an audit gate**: Do not remove `generate_candidates` / `build_split_prompt` / `build_prompt` from generator.py until the Dockerfile CMD and any scheduled scripts are inspected. This is not a dependency — it is a required pre-check.

---

## MVP Definition

This is a subsequent milestone for an existing production system. "MVP" means: fix the broken daily jobs and reduce codebase noise without introducing regression risk.

### Phase 1 — Bug Fixes and Trivial Cleanup (Zero Risk)

- [ ] `performance_snapshots` unique constraint migration — the single thing blocking all daily snapshot data
- [ ] Remove 8 trivially-dead orphaned functions — mechanical deletion, no callers anywhere in runtime or tests
- [ ] Remove `_provider_label` re-export from finish_processing.py (1 line)
- [ ] Remove finish processing re-exports from generation.py (4 lines)

### Phase 2 — Test Cleanup and Import Hygiene (Low Risk)

- [ ] Update `test_prompt_sanitization_contract.py` to import `_platform_reasoning_effort` and `_platform_completion_cap` from executor.py instead of generator.py
- [ ] Update `tests/api/test_generation.py` to call `build_core_prompt()` directly instead of deprecated `_build_generation_user_prompt()` wrapper
- [ ] Update 5 test files to import from extracted modules (not main.py), then delete main.py re-export block
- [ ] After test updates: remove duplicated `_platform_reasoning_effort`, `_platform_completion_cap`, `_generate_with_provider_compat` from generator.py

### Phase 3 — Entity Mapping and Coverage (Medium Risk)

- [ ] Offer ID normalization — audit `google_ads_performance.py` and any callers; normalize at integration boundary (not call sites)
- [ ] Wire image support in executor.py (~15 lines, additive, no refactor)
- [ ] Full catalog baseline backfill — audit `feedops-daily-incremental-refresh` scheduler job; extend or create a one-time sweep if needed

### Decisions Required Before Proceeding

- [ ] Audit Dockerfile CMD and scripts for `optimize.py` invocations — determines whether ~450 lines of legacy generation path in generator.py can be removed
- [ ] Confirm or deny PMax campaign presence in the Allied Brass Google Ads account — determines whether the search term coverage gap is real

### Future Consideration (v1.2+)

- [ ] Scheduled search term sync (weekly Cloud Scheduler job) — simple, but not blocking anything right now
- [ ] Generator.py legacy path removal — gated on the optimize.py audit
- [ ] Circular import resolution via shared utils module — technical elegance, not a bug
- [ ] PMax search term inclusion — requires feasibility research

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Snapshot upsert constraint fix | HIGH — daily job failing since launch; impact scores empty | LOW — single SQL migration | P1 |
| Remove 8 trivially-dead functions | MEDIUM — codebase clarity | LOW — mechanical deletion | P1 |
| main.py re-export removal | MEDIUM — 130 lines of maintenance burden | MEDIUM — 5 test files to update | P1 |
| Generator.py duplicate consolidation | MEDIUM — removes divergence risk | LOW — after test updates | P1 |
| Offer ID normalization | HIGH — data correctness at scale | MEDIUM — audit + fix 1-2 files | P1 |
| Image wiring in executor.py | HIGH — all modern generation endpoints gain multimodal input | LOW — 15 lines, additive | P1 |
| Full catalog baseline backfill | HIGH — 2,226 SKUs currently have no benchmark | MEDIUM — validate/extend scheduler | P2 |
| Scheduled search term sync | MEDIUM — data freshness without user action | LOW — new scheduler job only | P2 |
| optimize.py audit + legacy path removal | LOW — risk of silent CLI breakage if rushed | MEDIUM — audit gate required | P3 |
| PMax search term inclusion | MEDIUM — coverage gap if PMax campaigns active | HIGH — API feasibility unknown | P3 |
| Circular import shared utils | LOW — technical elegance | LOW — low-risk refactor | P3 |
| Bing/Microsoft Ads integration | LOW — premature without stable Google pipeline | HIGH — different API surface | DEFER |
| GA4 attribution tables | MEDIUM — future value for closed-loop optimization | HIGH — scope explosion risk | DEFER |

**Priority key:**
- P1: Must have for milestone — fixes broken production behavior or is near-zero-risk cleanup
- P2: High value; add once P1 items are stable and verified
- P3: Nice to have; depends on audit gate or external research
- DEFER: Explicitly out of scope for this milestone

---

## Data Lifecycle Domain Patterns (Research)

How e-commerce performance data systems typically work — and how Allied-FeedOps aligns or deviates:

### Daily metric collection at scale

Standard pattern: batch API calls with chunking/pagination, parallel threads capped to avoid rate limits, idempotent upserts keyed on natural composite key (not surrogate PK), rolling lookback windows (D-1/D-2/D-3) to account for Google's 24-48 hour data processing lag.

Allied-FeedOps alignment: `fetch_batch_product_performance()` chunks 25 IDs per GAQL query with 5 parallel threads — correct. Rolling D-1/D-2/D-3 lag correction is already implemented and correct in `collect_daily_performance_snapshots()`. The only missing piece is the database constraint that makes idempotent upserts work.

### Schema constraint patterns for upsert-heavy workloads

Standard pattern: composite UNIQUE constraints on the natural key (not just the surrogate PK). For time-series data: `UNIQUE(entity_id, date, partition_key)`. PostgreSQL `ON CONFLICT (cols) DO UPDATE` requires a matching unique constraint or index — not just column names in the upsert call.

Allied-FeedOps alignment: 6 of 7 upsert-heavy tables have correct constraints. `performance_snapshots` is the sole exception — a bug, not a design choice. The fix is one DDL statement.

### Cross-platform entity mapping

Standard pattern: a central hub table with normalized IDs for each platform's native entity references. Case normalization at the integration boundary (not scattered across query sites). The hub table is the single lookup path — APIs never queried with a non-normalized ID.

Allied-FeedOps alignment: `variant_index` (72K rows) is this hub — correct design. The case normalization gap (`shopify_US_` vs `shopify_us_`) is the one violation. Normalization should happen when writing to variant_index, or consistently applied at the integration layer in `google_ads_performance.py`.

### Data quality validation

Standard pattern: row counts and freshness checks surfaced in health endpoints; alerts when scheduled jobs produce zero rows (not just when they error); explicit distinction between "no data" and "zero value"; staleness TTLs enforced at the application layer.

Allied-FeedOps alignment: Slack alerts on job failure (implemented). Zero-row funnel snapshot alerts (implemented). Performance baseline staleness check with 60-day TTL (implemented in ensure-data.ts). Gap: no alert when daily snapshot capture succeeds (no Python error) but produces zero new rows — which is exactly what happens silently due to the constraint bug. The error is PostgreSQL-level, swallowed by the exception handler.

---

## Sources

- `/tmp/dead-code-research.md` — Full dead code audit conducted 2026-03-03 (HIGH confidence — live codebase inspection with function-level call graph analysis)
- `/tmp/google-ads-import-research.md` — Google Ads data import pipeline research conducted 2026-03-03 (HIGH confidence — live DB constraint query + source code inspection)
- `.planning/PROJECT.md` — Milestone definition and confirmed out-of-scope items
- `src/feedops/monitoring/performance_impact.py` line 461 — Snapshot upsert bug confirmed at exact location
- `src/feedops/integrations/google_ads_performance.py` — Batch performance fetch implementation (chunked 25 IDs, 5 parallel threads confirmed)
- `src/feedops/generation/executor.py` — Image wiring gap confirmed in `execute_generation_bundle()` — no `image` parameter passed
- Live Supabase constraint query (from research report) — confirmed 7 tables, only `performance_snapshots` missing natural key unique constraint

---

*Feature research for: Allied-FeedOps v1.1 — Data Infrastructure Hardening + Dead Code Cleanup*
*Researched: 2026-03-03*
