# Roadmap: Allied-FeedOps

## Milestones

- ✅ **v1.0 Pipeline Reliability Rewrite + Model Evaluation** - Phases 1-7 (shipped 2026-03-03)
- 🚧 **v1.1 Dead Code Cleanup + Data Infrastructure** - Phases 8-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 Pipeline Reliability Rewrite + Model Evaluation (Phases 1-7) - SHIPPED 2026-03-03</summary>

### Phase 1: Schemas Extraction
**Goal**: All Pydantic request/response models live in isolated `schemas.py` — importable without spinning up the full app
**Depends on**: Nothing (first phase)
**Requirements**: DECOMP-01, DECOMP-02, DECOMP-03, DECOMP-04
**Success Criteria** (what must be TRUE):
  1. `from feedops.api.schemas import OptimizeSkuRequest` works without importing `main.py`
  2. All Supabase read/write functions are in `persistence.py` and `main.py` imports them from there
  3. All metrics and diagnostics emit identically before and after extraction (curl `/health` returns same structure)
  4. No circular imports: `python -c "import feedops.api.main"` exits 0 after extraction
**Plans**: 2 plans
  - [x] 01-01-PLAN.md — Extract schemas.py and telemetry.py (zero inter-module deps)
  - [x] 01-02-PLAN.md — Extract persistence.py and job_management.py + update external callers

### Phase 2: Services Extraction
**Goal**: Business logic for finish processing, intent scoring, and core generation lives in testable, isolated service modules
**Depends on**: Phase 1
**Requirements**: DECOMP-05, DECOMP-06, DECOMP-07, DECOMP-08, DECOMP-10, DECOMP-11
**Success Criteria** (what must be TRUE):
  1. `pytest tests/test_finish_processing.py` passes — finish placeholder contract (`{FINISH_NAME}`, `{FINISH_SENTENCE}`) verified in isolation
  2. `pytest tests/test_intent_scoring.py` passes — query intent and content scoring independently testable
  3. `pytest tests/test_generation.py` passes — core generation orchestration independently testable
  4. `run_async_in_thread()` is in a shared utility module and a unit test asserts `thread.daemon == False`
  5. All existing API endpoints (`/optimize-sku`, `/regenerate`, `/batch-optimize`, `/hybrid-generate`, `/generate-images`) return identical responses before and after extraction
**Plans**: 2 plans
  - [x] 02-01-PLAN.md — Extract intent_scoring.py and finish_processing.py with unit tests + daemon test
  - [ ] 02-02-PLAN.md — Extract generation.py with unit tests + endpoint verification

### Phase 3: JobRunner and Route Extraction
**Goal**: Duplicated batch/hybrid processors unified into a single `JobRunner`; `main.py` reduced to route definitions only
**Depends on**: Phase 2
**Requirements**: DECOMP-09, JOBS-01, JOBS-02, JOBS-03, JOBS-04, JOBS-05, JOBS-06
**Success Criteria** (what must be TRUE):
  1. `main.py` is under 500 lines (route definitions and request handling only — verified with `wc -l`)
  2. A single `JobRunner` class replaces both `process_batch_job()` and `process_hybrid_batch_job()` — neither function exists in the codebase
  3. Batch generation job completes end-to-end via `JobRunner` with identical output to pre-extraction run
  4. Hybrid multi-SKU generation job completes end-to-end via `JobRunner` with identical variant adaptation output
  5. Job cancellation and graceful shutdown work without orphaned threads
**Plans**: 2 plans
  - [x] 03-01-PLAN.md — Extract JobRunner class unifying batch + hybrid job processing
  - [x] 03-02-PLAN.md — Extract route handlers to routes.py + main.py line-count guard

### Phase 4: GPT-5.2 Bug Fixes
**Goal**: All 5 known GPT-5.2 bugs fixed with clean curl verification — production baseline is correct and measurable
**Depends on**: Phase 3
**Requirements**: GPT-01, GPT-02, GPT-03, GPT-04, GPT-05, GPT-06
**Success Criteria** (what must be TRUE):
  1. `curl /optimize-sku` with SKU `920D-6` returns a description longer than 500 characters after each individual PR merge
  2. `openai_provider.py` never passes `temperature` alongside `reasoning_effort` — verified by code inspection and test
  3. `reasoning_effort` defaults to `"high"` when `FEEDOPS_REASONING_EFFORT` env var is unset — verified by unit test
  4. `json_schema` strict mode is active; no retry-on-invalid-JSON loops in production logs after a batch run
  5. System prompt uses XML section tags instead of `=== ===` headers — and curl verification confirms descriptions unchanged in length and quality
**Plans**: 3 plans
  - [x] 04-01-PLAN.md — GPT-5.2 regression tests (GPT-01 through GPT-05)
  - [x] 04-02-PLAN.md — Add prompt_cache_key to OpenAI API calls
  - [ ] 04-03-PLAN.md — Post-deploy content quality verification script

### Phase 5: Claude Provider
**Goal**: Claude can generate structured product content through the same interface as GPT-5.2 — environment variable selects the provider
**Depends on**: Phase 4
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, PROV-05
**Success Criteria** (what must be TRUE):
  1. `FEEDOPS_PROVIDER=claude` environment variable causes `/optimize-sku` to use `ClaudeProvider` — verified in Cloud Run logs
  2. `ClaudeProvider` produces a valid, structured JSON response (title, description, all platform fields) for Google, Bing, and Shopify content types
  3. `OpenAIProvider` still works identically when `FEEDOPS_PROVIDER=openai` (or unset) — no regression
  4. `pytest tests/test_claude_provider.py` passes with mocked Anthropic client
  5. `providers/base.py` defines the `LLMProvider` ABC and both providers implement it without modification to any other module
**Plans**: 2 plans
  - [x] 05-01-PLAN.md — Implement ClaudeProvider with structured output + mocked tests for all 3 platforms
  - [ ] 05-02-PLAN.md — Extend provider factory with FEEDOPS_PROVIDER=claude selection

### Phase 6: Model Evaluation
**Goal**: Concrete cost/quality/latency data exists to make a data-driven provider decision — blind human scores are the ground truth
**Depends on**: Phase 5
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Success Criteria** (what must be TRUE):
  1. 10 diverse SKUs (mix of categories, collection types, single vs multi-SKU) are selected and documented before any generation runs
  2. Both providers generate content for all 10 SKUs using identical prompts — results stored in CSV with provider labels hidden
  3. Bobby and Robert complete blind scoring on all 20 outputs before labels are revealed
  4. A comparison table exists with cost-per-SKU, p50/p95 latency, and average blind score for each provider
  5. A written recommendation exists stating which provider to use for which scenarios, backed by evaluation data
**Plans**: 3 plans
  - [x] 06-01-PLAN.md — SKU selection script + evaluation script + run full 3-way evaluation
  - [x] 06-02-PLAN.md — Create blind scoring sheet + Bobby/Robert complete scoring
  - [x] 06-03-PLAN.md — Analysis: comparison table + written recommendation

### Phase 7: Bing Fix
**Goal**: All Bing titles use `{FINISH_NAME}` placeholder — broken content is replaced, variant expansion produces correct per-finish titles
**Depends on**: Phase 4
**Requirements**: BING-01, BING-02, BING-03, BING-04
**Success Criteria** (what must be TRUE):
  1. Root cause of hardcoded finish names is documented (exact missing prompt instruction identified in `prompts.py`)
  2. A single isolated prompt fix is deployed and curl-verified against one Bing title before mass regeneration
  3. All 85 broken Bing titles are regenerated — SQL query confirms 0 Bing titles contain hardcoded finish names
  4. Variant expansion for a regenerated SKU produces 28 distinct finish-specific titles
**Plans**: TBD — deferred

</details>

### 🚧 v1.1 Dead Code Cleanup + Data Infrastructure (In Progress)

**Milestone Goal:** Remove dead code from the v1.0 pipeline decomposition, fix the broken daily performance snapshot job, harden data table schemas, normalize entity relationships, and scale baseline coverage from 274 to all ~2,500 master SKUs.

#### Phase 8: Schema Hardening
**Goal**: Data table schemas enforce correctness at the database level — the daily performance snapshot job succeeds instead of failing silently
**Depends on**: Phase 7 (v1.0 complete)
**Requirements**: SCHM-01, SCHM-02, SCHM-03, SCHM-04
**Success Criteria** (what must be TRUE):
  1. Daily Cloud Scheduler snapshot job at 6:00 AM UTC completes without error — Slack alert reports success instead of a 42P10 upsert failure
  2. `performance_impact_scores` table starts populating with real data (was empty due to snapshot job failing)
  3. `SELECT COUNT(*) FROM performance_snapshots` grows by the expected number of SKUs the morning after migration 042 is applied
  4. A CHECK constraint rejects any INSERT on platform columns that uses a value outside the allowed set (google, bing, shopify)
  5. `performance_snapshots.publish_event_id` has a FK to `publish_events` — orphaned rows are rejected at the DB layer
**Plans**: 1 plan
Plans:
- [ ] 08-01-PLAN.md — Write and apply migration 042 (dedup + unique constraint + CHECK constraints + FK)

#### Phase 9: Trivial Dead Code Removal
**Goal**: All zero-caller orphan functions are deleted from the codebase — no test changes required, ruff and pytest stay green after each deletion
**Depends on**: Phase 8
**Requirements**: DEAD-01, DEAD-05
**Success Criteria** (what must be TRUE):
  1. `_payload_value_lengths`, `_schema_hash`, `_prompt_hash`, and `_generate_with_provider_compat` no longer exist in generator.py
  2. `_provider_label` re-export no longer exists in finish_processing.py; finish processing re-exports removed from generation.py (lines 26-30)
  3. The ~500-line `FEEDOPS_VARIANT_AT_LLM_TIME` feature flag block and all code behind it is deleted from the codebase
  4. `pytest tests/` passes with zero failures after all deletions
  5. `ruff check src/` passes with zero violations after all deletions
**Plans**: TBD

#### Phase 10: Image Wiring
**Goal**: All modern generation endpoints send product images to Claude during generation — SKUs with a `main_image_url` get richer context
**Depends on**: Phase 8 (independent of Phase 9)
**Requirements**: IMG-01
**Success Criteria** (what must be TRUE):
  1. A `curl /optimize-sku` call for a SKU with a `main_image_url` in `variant_index` produces a Cloud Run log line confirming an image was sent to Claude
  2. A `curl /optimize-sku` call for a SKU without a `main_image_url` completes normally — `image=None` is handled gracefully with no error
  3. Finish sentence tasks do not receive image inputs (image wiring is skipped for finish tasks)
  4. `pytest tests/` passes with zero failures after the change
**Plans**: TBD

#### Phase 11: Test-Import Cleanup and Re-export Removal
**Goal**: Test files import from canonical module locations; main.py backward-compat re-export block is deleted; executor.py is the single source of truth for per-platform generation utilities
**Depends on**: Phase 9
**Requirements**: DEAD-02, DEAD-03, DEAD-04
**Success Criteria** (what must be TRUE):
  1. No test file imports any symbol from `feedops.api.main` — all imports point to the actual extracted module
  2. The ~130-line backward-compat re-export block (lines 174-304) no longer exists in main.py
  3. The 6 functions duplicated between generator.py and executor.py exist only in executor.py — generator.py has no copies
  4. `pytest tests/` passes with zero failures throughout the entire sequential update process
  5. `python -c "import feedops.api.main"` exits 0 (no import errors after re-exports removed)
**Plans**: TBD

#### Phase 12: Entity Mapping and Bulk Coverage
**Goal**: Offer ID normalization is applied at every data integration boundary; all ~2,500 master SKUs have performance baselines instead of the current 274
**Depends on**: Phase 8, Phase 10, Phase 11
**Requirements**: ENTM-01, ENTM-02, ENTM-03, DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. A `normalize_offer_id()` utility exists and is applied at every Google Ads integration boundary before any data query runs
  2. A test confirms that `normalize_offer_id("shopify_US_123_456")` and `normalize_offer_id("shopify_us_123_456")` both return the same canonical form
  3. A 50-SKU throttled test run completes successfully with no `RESOURCE_EXHAUSTED` errors before the full catalog sweep is attempted
  4. After the full baseline backfill, `SELECT COUNT(DISTINCT master_sku) FROM performance_baselines` returns a value greater than 2,400 (up from 274)
  5. The entity relationship map document exists at `docs/architecture/entity-relationships.md` and correctly diagrams `variant_index` as the hub
  6. Daily snapshot verification: the morning after backfill completes, snapshot count in `performance_snapshots` reflects new SKUs being captured
**Plans**: TBD

#### Phase 13: Shared Utils Extraction
**Goal**: The duplicated `_require_request_id()` and `GenerationBudgetExceededError` exist in exactly one location — circular import between persistence.py and job_management.py is resolved cleanly
**Depends on**: Phase 11
**Requirements**: DEAD-06
**Success Criteria** (what must be TRUE):
  1. `feedops/api/utils.py` exists and contains exactly one definition of `_require_request_id()` and `GenerationBudgetExceededError`
  2. Neither `persistence.py` nor `job_management.py` defines these symbols — both import from `utils.py`
  3. `python -c "import feedops.api.main"` exits 0 (no circular import introduced by utils.py)
  4. `pytest tests/` passes with zero failures after extraction
**Plans**: TBD

## Progress

**Execution Order:**
v1.0 phases 1-7 executed in dependency order. v1.1 phases execute as: 8 → 9 → 10 (parallel with 9) → 11 (after 9) → 12 (after 8, 10, 11) → 13 (after 11).

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Schemas Extraction | v1.0 | 2/2 | Complete | 2026-03-03 |
| 2. Services Extraction | v1.0 | 1/2 | Complete | 2026-03-03 |
| 3. JobRunner and Route Extraction | v1.0 | 2/2 | Complete | 2026-03-03 |
| 4. GPT-5.2 Bug Fixes | v1.0 | 2/3 | Complete | 2026-03-03 |
| 5. Claude Provider | v1.0 | 2/2 | Complete | 2026-03-03 |
| 6. Model Evaluation | v1.0 | 3/3 | Complete | 2026-03-03 |
| 7. Bing Fix | v1.0 | 0/TBD | Deferred | - |
| 8. Schema Hardening | 1/1 | Complete   | 2026-03-03 | - |
| 9. Trivial Dead Code Removal | v1.1 | 0/TBD | Not started | - |
| 10. Image Wiring | v1.1 | 0/TBD | Not started | - |
| 11. Test-Import Cleanup and Re-export Removal | v1.1 | 0/TBD | Not started | - |
| 12. Entity Mapping and Bulk Coverage | v1.1 | 0/TBD | Not started | - |
| 13. Shared Utils Extraction | v1.1 | 0/TBD | Not started | - |
