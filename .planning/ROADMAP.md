# Roadmap: Pipeline Reliability Rewrite + Model Evaluation

## Overview

A safety-first decomposition of the 3,737-line `main.py` monolith into testable modules, followed by GPT-5.2 bug remediation, Claude provider implementation, a head-to-head model evaluation, and a Bing placeholder fix. Every phase preserves the 98% human approval rate and backward compatibility of all existing API endpoints. Phases run in strict dependency order: schemas first (no dependencies), services second, then JobRunner unification, then GPT-5.2 fixes (clean baseline), then Claude provider, then evaluation, then Bing fix using the proven protocol.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Schemas Extraction** - Extract all Pydantic models into `schemas.py` — no dependencies, unblocks all subsequent extraction
- [ ] **Phase 2: Services Extraction** - Extract finish processing, intent scoring, telemetry, generation, and persistence into isolated service modules
- [ ] **Phase 3: JobRunner and Route Extraction** - Unify batch/hybrid job processing into `JobRunner`; slim `main.py` to <500 lines
- [ ] **Phase 4: GPT-5.2 Bug Fixes** - Fix all 5 known GPT-5.2 bugs as separate PRs with curl verification
- [ ] **Phase 5: Claude Provider** - Implement `ClaudeProvider` with structured output and factory support
- [ ] **Phase 6: Model Evaluation** - Run head-to-head Claude vs GPT-5.2 on 10 diverse SKUs with blind human scoring
- [ ] **Phase 7: Bing Fix** - Diagnose and fix `{FINISH_NAME}` bug; regenerate 85 broken Bing titles

## Phase Details

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
  - [ ] 01-01-PLAN.md — Extract schemas.py and telemetry.py (zero inter-module deps)
  - [ ] 01-02-PLAN.md — Extract persistence.py and job_management.py + update external callers

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
**Plans**: TBD

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
**Plans**: TBD

### Phase 4: GPT-5.2 Bug Fixes
**Goal**: All 5 known GPT-5.2 bugs fixed with clean curl verification — production baseline is correct and measurable
**Depends on**: Phase 3
**Requirements**: GPT-01, GPT-02, GPT-03, GPT-04, GPT-05, GPT-06
**Success Criteria** (what must be TRUE):
  1. `curl /optimize-sku` with SKU `920D-6` returns a description longer than 500 characters after each individual PR merge
  2. `openai_provider.py` never passes `temperature` alongside `reasoning_effort` — verified by code inspection and test
  3. `reasoning_effort` defaults to `"medium"` when `FEEDOPS_REASONING_EFFORT` env var is unset — verified by unit test
  4. `json_schema` strict mode is active; no retry-on-invalid-JSON loops in production logs after a batch run
  5. System prompt uses XML section tags instead of `=== ===` headers — and curl verification confirms descriptions unchanged in length and quality
**Plans**: TBD

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
**Plans**: TBD

### Phase 6: Model Evaluation
**Goal**: Concrete cost/quality/latency data exists to make a data-driven provider decision — blind human scores are the ground truth
**Depends on**: Phase 5
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Success Criteria** (what must be TRUE):
  1. 10 diverse SKUs (mix of categories, collection types, single vs multi-SKU) are selected and documented before any generation runs
  2. Both providers generate content for all 10 SKUs using identical prompts — results stored in CSV with provider labels hidden
  3. Bobby and Robert complete blind scoring on all 20 outputs (title quality, description quality, brand voice, accuracy) before labels are revealed
  4. A comparison table exists with cost-per-SKU, p50/p95 latency, and average blind score for each provider
  5. A written recommendation exists stating which provider to use for which scenarios, backed by the evaluation data
**Plans**: TBD

### Phase 7: Bing Fix
**Goal**: All Bing titles use `{FINISH_NAME}` placeholder — broken content is replaced, variant expansion produces correct per-finish titles
**Depends on**: Phase 4
**Requirements**: BING-01, BING-02, BING-03, BING-04
**Success Criteria** (what must be TRUE):
  1. Root cause of hardcoded finish names is documented (exact missing prompt instruction identified in `prompts.py`)
  2. A single isolated prompt fix is deployed and curl-verified against one Bing title before mass regeneration
  3. All 85 broken Bing titles are regenerated — SQL query confirms 0 Bing titles in `generated_content` contain hardcoded finish names from the 28-finish list
  4. Variant expansion for a regenerated SKU produces 28 distinct finish-specific titles, each beginning with the correct finish name
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in dependency order. Phase 7 depends on Phase 4 (prompt-change protocol established) but is independent of Phases 5-6 and can run after Phase 4 completes.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schemas Extraction | 1/2 | In Progress|  |
| 2. Services Extraction | 0/TBD | Not started | - |
| 3. JobRunner and Route Extraction | 0/TBD | Not started | - |
| 4. GPT-5.2 Bug Fixes | 0/TBD | Not started | - |
| 5. Claude Provider | 0/TBD | Not started | - |
| 6. Model Evaluation | 0/TBD | Not started | - |
| 7. Bing Fix | 0/TBD | Not started | - |
