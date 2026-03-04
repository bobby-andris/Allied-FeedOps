# Project Research Summary

**Project:** Allied-FeedOps v1.1 — Data Infrastructure Hardening + Dead Code Cleanup
**Domain:** E-commerce data lifecycle management — schema constraint design, entity relationship hardening, dead code elimination for a Python/FastAPI content generation pipeline
**Researched:** 2026-03-03
**Confidence:** HIGH

## Executive Summary

This is a stabilization milestone for an existing, production-validated system — not a greenfield build. The core architecture (FastAPI on Cloud Run, Supabase PostgreSQL, Google Ads API integration, Claude Sonnet 4.6) is working correctly. The problems being addressed are precision defects: one missing database unique constraint that causes the daily performance snapshot job to silently fail every night, approximately 330+ lines of dead code left behind by the DECOMP-09 decomposition, and an offer ID case mismatch that will corrupt data at bulk operation scale. These are well-understood problems with well-understood fixes. No new technologies are required; all dependencies are already installed.

The recommended approach is to tackle work in strict dependency order: schema migration first (highest value, zero code risk), then trivially-dead function removal (no test entanglement), then image wiring in executor.py (additive feature), then test-import updates followed by re-export block removal (the most coordination-intensive piece), and finally shared utils extraction (optional cleanup). The snapshot constraint fix is the single highest-leverage change in this milestone — it unblocks the impact scores pipeline entirely without touching a line of Python code.

The key risks are all execution-related, not design-related: removing dead code before updating test imports causes CI failures; adding a unique constraint without deduplicating existing rows fails the migration; scaling bulk baseline fetch to 2,500 SKUs without throttling exhausts the Google Ads API daily quota. Every pitfall has a documented prevention step. The research provides a function-level inventory of all dead code, confirmed constraint audit results, and exact SQL for safe migration sequencing.

## Key Findings

### Recommended Stack

No new packages are required for this milestone. The full stack — FastAPI 0.109+, Pydantic v2, `supabase>=2.0`, `google-ads>=28.4.1`, `anthropic>=0.84.0` — is already production-validated and installed. The work is pure schema DDL, Python function deletion, and a 15-line additive wiring change.

The only new artifact is migration 036 (`ALTER TABLE performance_snapshots ADD CONSTRAINT uq_snapshots_sku_platform_env_date UNIQUE (master_sku, platform, environment, snapshot_date)`) plus a dedup DELETE that must precede it in the same migration file. Migration 032 was previously written and contains the correct constraint definition — 036 is the version that actually gets applied to production.

**Core technologies:**
- PostgreSQL UNIQUE constraints (native DDL): enforce upsert deduplication — the fix that unblocks the entire daily snapshot pipeline
- PostgreSQL CHECK constraints (native DDL): extend to `platform` column for domain enforcement, following the pattern already applied to `cohort_type` and `label`
- `supabase>=2.0` (already installed): execute upserts with `on_conflict=` once constraints are in place
- `ruff + pytest + mypy` (already configured): safety net for every dead code removal — run after each individual deletion, not in batches
- `google-ads>=28.4.1` (already installed): no SDK changes needed; PMax is already included in `shopping_performance_view` without filter changes

### Expected Features

The milestone targets two distinct categories: production bug fixes and codebase cleanup. All P1 items fix broken or misleading behavior; P2 items improve coverage and quality; P3 items require an explicit audit gate before proceeding.

**Must have (table stakes):**
- `performance_snapshots` unique constraint migration — daily job has been failing silently since launch; impact scores empty as a result; single SQL statement fix
- Dead function removal (8 trivially orphaned items) — `_payload_value_lengths`, `_schema_hash`, `_prompt_hash`, legacy `_generate_with_provider_compat` copy in generator.py, `_provider_label` re-export in finish_processing.py, finish processing re-exports in generation.py (lines 26-30), `build_variant_adaptation_prompt` in tasks.py, `serialize_task_result` in generation/persistence.py — mechanical deletion, zero callers anywhere in runtime or tests
- main.py backward-compat re-export removal — ~130 lines of maintenance debt from DECOMP-09; gated on updating 5 specific test files first
- Generator.py duplicate consolidation — `_platform_reasoning_effort`, `_platform_completion_cap`, `_resolve_requested_platforms` duplicated between generator.py and executor.py; executor.py becomes single source of truth
- Offer ID normalization audit — `shopify_US_` (Google Ads) vs `shopify_us_` (database); mismatch causes silent data loss in performance queries; fix at integration boundary in `google_ads_performance.py`
- Image wiring in executor.py — ~15 lines additive; modern API path (`/regenerate`, `/optimize-sku`, `/batch-optimize`) does not currently send product images to Claude; provider layer already accepts `ImageInput`

**Should have (differentiators):**
- Full catalog baseline backfill — only 274 of ~2,500 master SKUs have performance baselines; backfill infrastructure (`/backfill/start` with `job_type: "performance_metrics"`) already exists; needs throttling at scale
- Shared utils extraction — `_require_request_id()` duplicated in persistence.py and job_management.py due to circular import; extract to new `feedops/api/utils.py`

**Defer (v2+):**
- Scheduled weekly search term sync — endpoint exists and works; adding Cloud Scheduler job is trivial but not blocking anything currently
- optimize.py legacy path removal — ~450 lines; requires explicit audit of Dockerfile CMD and scripts before removal is safe
- PMax search term inclusion — requires feasibility research against actual account campaign structure
- Bing/Microsoft Ads integration — schema supports it; defer until Google pipeline is validated end-to-end
- GA4 attribution tables — migrations 034b/035b explicitly deferred; 32 TypeScript files already reference missing tables

### Architecture Approach

The system is a dual-layer architecture: Python/FastAPI on Cloud Run handles content generation and data collection; Next.js on Vercel handles review and publishing. This milestone operates exclusively on the Python layer and database schema. The central entity hub is `variant_index` (72K rows), which maps `gmc_offer_id` (lowercase) to `master_sku`, `shopify_product_id`, `shopify_variant_id`, and `finish_code`. Three Cloud Scheduler jobs drive daily automated data collection at 2:15 AM, 2:45 AM, and 6:00 AM UTC. The only new file created in v1.1 is `feedops/api/utils.py` to resolve a circular import.

**Major components:**
1. `performance_impact.py` — daily snapshot collection and diff-in-diff scoring; broken by missing constraint at line 461; zero code changes needed after migration 036 is applied
2. `generation/executor.py` — modern per-platform LLM generation path; needs 15-line image wiring addition
3. `pipeline/generator.py` — legacy path (still active via optimize.py CLI); partial dead code removal only — the `generate_candidates` / `build_split_prompt` / `build_prompt` generation chain must be preserved until an explicit audit confirms optimize.py is retired
4. `supabase/migrations/` — schema evolution via SQL files; migration 036 must run dedup DELETE before ALTER TABLE in the same migration file
5. `feedops/api/main.py` — backward-compat re-export block (lines 174-304); removal requires updating 5 test files first, in sequence

### Critical Pitfalls

1. **Removing dead code before updating test imports** — 5 groups of functions appear dead in production but are imported by tests through the backward-compat re-export chain. Fix sequence: update test import, run pytest, remove dead code, run pytest again. Never batch across multiple functions. Confirmed affected test files: `test_prompt_sanitization_contract.py`, `test_pipeline.py`, `test_generation.py`, `test_phase7_observability_reliability.py`, `test_generation_runtime_scope_contract.py`, `test_query_intent_lineage.py`, `test_finish_prompt_source_contract.py`, `test_main_master_sku_alias_runtime.py`.

2. **Adding unique constraint to a table with existing duplicate rows** — `performance_snapshots` has 179 rows from early inserts; any duplicates will fail the ALTER TABLE statement with `could not create unique index`. Run the dedup check first; include the dedup DELETE in the same migration file as the ALTER TABLE so they execute atomically.

3. **Upsert semantics after constraint fix — last-write-wins corrupts historical snapshots** — after the constraint is added, the existing ON CONFLICT DO UPDATE logic overwrites all columns on re-run. For time-series snapshot data, `ignore_duplicates=True` is the safer semantic: first write wins, re-runs do not corrupt historical data. This is an explicit decision, not a default.

4. **Offer ID case mismatch corrupts bulk data operations** — `variant_index` uses lowercase `shopify_us_`; Google Ads API returns uppercase `shopify_US_`. Joins fail silently: matching SKUs appear to have zero impressions. Create a `normalize_offer_id()` utility and apply it at every integration boundary before any bulk fetch code is written.

5. **Google Ads quota exhaustion during bulk baseline fetch** — 2,500 master SKUs x ~29 offer IDs each = ~72K IDs. At 25 per GAQL query the bulk fetch issues ~2,880 requests, consuming 19% of the 15,000/day quota in one shot. Cap concurrent threads at 3 (not 5), add 200ms inter-batch delays for operations over 100 SKUs, catch `RESOURCE_EXHAUSTED` with exponential backoff.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Schema Migration — Snapshot Constraint Fix
**Rationale:** Single highest-leverage change in the milestone. Zero Python code risk. Unblocks the entire daily snapshot collection and impact scores pipeline that has been failing silently since launch. Must come first because impact scores depend on snapshot rows existing.
**Delivers:** Daily snapshot job succeeds; `performance_impact_scores` starts populating; Slack reports success instead of FAILED. Post-publish ROI visibility in the dashboard becomes operational.
**Addresses:** P1 — `performance_snapshots` upsert constraint; cascading P1 — impact scores population
**Avoids:** Pitfall 2 (run dedup query against production first, include DELETE and ALTER TABLE in same migration file); Pitfall 3 (decide `ignore_duplicates=True` semantics explicitly before writing the upsert call); Pitfall 6 (verify Slack webhook binding before declaring complete)
**Research flag:** Standard pattern — well-documented PostgreSQL DDL + Supabase CLI migration tooling. No additional research needed.

### Phase 2: Trivial Dead Code Removal
**Rationale:** No test dependencies, no ordering constraints relative to other phases. These 8 items are confirmed orphans with zero callers in production or tests. Fast, zero-risk wins that reduce codebase noise before the more complex test-dependent cleanup in Phase 4.
**Delivers:** ~200 lines of dead code removed from generator.py, tasks.py, generation/persistence.py, generation.py, finish_processing.py.
**Addresses:** P1 — 8 trivially orphaned functions
**Avoids:** Pitfall 7 — do NOT remove the `generate_candidates` / `build_split_prompt` / `build_prompt` chain from generator.py; those functions are called by optimize.py and are explicitly out of scope for this phase
**Research flag:** Standard pattern — mechanical deletion with ruff + pytest verification after each removal.

### Phase 3: Image Wiring in executor.py
**Rationale:** Additive feature with no dependencies on Phase 2 or Phase 4. Independent of all data infrastructure work. Placing it as a standalone phase keeps it isolated from the test-import coordination work in Phase 4.
**Delivers:** All modern generation endpoints (`/regenerate`, `/optimize-sku`, `/batch-optimize`, `/hybrid-generate`) send product images to Claude during generation. Content quality improvement for all SKUs with a `main_image_url` in `variant_index`.
**Addresses:** P1 — image wiring in executor.py (~15 lines additive)
**Avoids:** Skip image fetch for finish sentence tasks; handle `image=None` gracefully so SKUs without a product image continue to work unchanged
**Research flag:** Standard pattern — 15-line addition following the existing `fetch_image()` + `ImageInput` pattern. No additional research needed.

### Phase 4: Test-Import Cleanup and Re-export Block Removal
**Rationale:** The most coordination-intensive work. Must be executed in sub-steps: update one test import, run pytest, remove the dead code, run pytest again. Never remove code before updating the test. The main.py re-export block (130 lines) can only be fully removed after all 5 test files are updated.
**Delivers:** generator.py reduced by 3 duplicated functions; main.py reduced by ~130 lines of re-export debt; executor.py becomes the single source of truth for per-platform generation utilities.
**Addresses:** P1 — main.py re-export removal; P1 — generator.py duplicate consolidation
**Avoids:** Pitfall 1 (critical — never remove a symbol from its source location before updating all test imports pointing to it; run full pytest between each removal)
**Research flag:** Standard pattern — known test files catalogued with exact import citations in dead-code-research.md. No additional research needed, but requires careful sequential execution.

### Phase 5: Entity Mapping and Bulk Coverage
**Rationale:** Offer ID normalization must precede bulk baseline backfill — a case mismatch in a 2,500-SKU fetch silently creates thousands of zero-impression baseline records. Fix normalization at the integration boundary first, then extend coverage.
**Delivers:** Offer ID normalization utility in `google_ads_performance.py`; full catalog baseline backfill for all ~2,500 master SKUs (up from 274 currently). All content optimization decisions become data-driven.
**Addresses:** P1 — offer ID normalization; P2 — full catalog baseline backfill
**Avoids:** Pitfall 4 (normalization utility before any bulk fetch code is written); Pitfall 5 (3-thread cap, 200ms inter-batch delay, `RESOURCE_EXHAUSTED` catch with exponential backoff; test against 50-SKU sample before running full catalog sweep)
**Research flag:** Bulk backfill scale needs pre-run validation. Test against 50 SKUs with throttling before running full 2,500-SKU sweep. Monitor Google Ads API Center for quota consumption before and after the test run.

### Phase 6: Shared Utils Extraction (Optional)
**Rationale:** Not a bug — a code elegance improvement. `_require_request_id()` is duplicated in persistence.py and job_management.py only because a direct import creates a circular dependency. Extracting to a shared `utils.py` eliminates the duplication cleanly with low risk. Can be deferred to a follow-up PR if schedule is tight.
**Delivers:** New `feedops/api/utils.py`; circular import resolved; duplication eliminated with a comment explaining why.
**Addresses:** P3 — circular import resolution
**Avoids:** Confirm the import graph before extraction — `utils.py` must not itself import from either `persistence.py` or `job_management.py` or new cycles are created
**Research flag:** Standard refactoring pattern. Low urgency.

### Phase Ordering Rationale

- **Schema first:** Zero code risk, highest cascade value (unblocks impact scores, validates Slack alerting, establishes a verification baseline before code changes begin)
- **Trivial dead code second:** Establishes the "run ruff + pytest after each deletion" discipline before the more complex test-dependent removals in Phase 4
- **Image wiring third:** Additive and independent — isolating it before Phase 4 prevents additive changes from mixing with subtractive changes in the same PR
- **Test-import cleanup fourth:** Highest coordination cost — doing it after simple successes builds confidence in the deletion pattern and keeps failures attributable
- **Entity mapping fifth:** Offer ID normalization must precede bulk baseline fetch; bulk fetch is the largest operational risk item in the milestone and should run last among P1/P2 work
- **Shared utils last:** Only item with no urgency — duplication is documented, not broken

### Research Flags

Phases with standard patterns (no additional research needed):
- **Phase 1:** PostgreSQL DDL + Supabase CLI migration workflow is well-documented; constraint DDL already written in migration 032
- **Phase 2:** Mechanical deletion with ruff/pytest; dead-code-research.md provides the complete function-level inventory
- **Phase 3:** Provider layer image support already implemented; 15-line addition following an established pattern
- **Phase 4:** Test files and canonical import paths fully catalogued in dead-code-research.md

Phases needing validation during execution:
- **Phase 5 (bulk backfill):** Test against a 50-SKU sample with throttling before running the full 2,500-SKU sweep. Verify the `RESOURCE_EXHAUSTED` error path in `google_ads_performance.py` is handled before scale-out. Check Google Ads API Center quota before and after the test run.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All dependencies confirmed present in pyproject.toml; no new installations required; constraint fix verified against live migration SQL and production DB row counts |
| Features | HIGH | Feature list derived from live codebase inspection with file/line citations; dead code inventory function-level with call graph confirmation; row counts from production DB |
| Architecture | HIGH | Component responsibilities verified against actual source files; build order derived from confirmed dependency graph (no inference required); scheduler job times confirmed from live GCP config |
| Pitfalls | HIGH | All pitfalls grounded in actual codebase state; specific test file names and line numbers confirmed; `performance_impact.py:461` confirmed as exact upsert bug location; Google Ads quota limits from official documentation |

**Overall confidence:** HIGH

### Gaps to Address

- **optimize.py retirement decision:** The research explicitly flags this as requiring a team decision before the legacy generation chain in generator.py can be removed (~450 lines). Recommend making this call explicit in the Phase 2 plan — the trivially-dead items in Phase 2 do NOT include the optimize.py generation chain, so Phase 2 is safe regardless of this decision.

- **Upsert semantics choice:** The research flags a decision between `DO UPDATE SET` (last-write-wins) and `ignore_duplicates=True` (first-write-wins) for the `performance_snapshots` upsert. For time-series data where historical snapshots should not be overwritten by re-runs, `ignore_duplicates=True` is recommended — but this must be a conscious decision made during Phase 1 planning, not a default.

- **Google Ads quota headroom:** The 15,000 requests/day limit is from official documentation; actual quota can vary by account and API version. Verify the actual limit in Google Ads API Center for customer ID `6253381786` before Phase 5.

- **Slack webhook binding verification:** The research identifies the possibility that `SLACK_WEBHOOK_URL` may not be bound to the current Cloud Run revision. Verify this as part of Phase 1 verification: `gcloud run services describe feedops-pipeline --project=bobbys-project-346400 --format='value(spec.template.spec.containers[0].env)'`.

## Sources

### Primary (HIGH confidence)
- `/tmp/dead-code-research.md` (2026-03-03) — function-level dead code inventory with call graph analysis; exact test import file/line citations
- `/tmp/google-ads-import-research.md` (2026-03-03) — live DB row counts and constraint audit; ON CONFLICT bug root cause confirmed at `performance_impact.py:461`; scheduled job architecture
- `supabase/migrations/032_performance_impact_pipeline.sql` — confirmed correct constraint DDL and dedup pattern
- `pyproject.toml` — confirmed all dependencies present; no new pip installs required
- `docs/database/SCHEMA.md` — 56 tables documented; constraint patterns verified
- `src/feedops/monitoring/performance_impact.py:461` — confirmed upsert with missing unique constraint
- `src/feedops/integrations/google_ads_performance.py` — confirmed 25-per-chunk, 5-thread batch architecture
- `src/feedops/generation/executor.py` — confirmed image wiring gap in `execute_generation_bundle()`

### Secondary (MEDIUM confidence)
- Official Google Ads API quotas documentation — 15,000 requests/day limit (may vary by account/API version)
- Official PostgreSQL ON CONFLICT documentation — confirms constraint requirement for `ON CONFLICT (columns)` syntax

### Tertiary (LOW confidence — needs validation during execution)
- Google Ads quota headroom for Allied Brass account — verify in API Center before Phase 5 bulk backfill
- optimize.py production usage status — git log shows file exists and is maintained; exact production usage pattern not confirmed during research

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*
