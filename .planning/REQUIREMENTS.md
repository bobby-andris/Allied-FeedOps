# Requirements: Pipeline Reliability Rewrite + Model Evaluation

**Defined:** 2026-03-03
**Core Value:** The pipeline produces high-quality product content reliably at scale — decomposition and bug fixes must not regress the 98% human approval rate or break any existing API endpoints.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Decomposition

- [x] **DECOMP-01**: Extract all Pydantic request/response models (~17 classes) into `schemas.py`
- [x] **DECOMP-02**: Extract all Supabase read/write functions into `persistence.py`
- [x] **DECOMP-03**: Extract job lifecycle functions into `job_management.py`
- [x] **DECOMP-04**: Extract metrics emission and diagnostics into `telemetry.py`
- [x] **DECOMP-05**: Extract query intent and content scoring into `intent_scoring.py`
- [x] **DECOMP-06**: Extract finish sentence validation and parity enforcement into `finish_processing.py`
- [x] **DECOMP-07**: Extract core generation orchestration into `generation.py`
- [x] **DECOMP-08**: Extract `run_async_in_thread()` into a shared utility module with daemon=False test
- [ ] **DECOMP-09**: Reduce `main.py` to <500 lines (route definitions and request handling only)
- [x] **DECOMP-10**: All existing API endpoints work identically after extraction
- [x] **DECOMP-11**: pytest covers each extracted module independently

### Job Unification

- [ ] **JOBS-01**: Replace duplicated `process_batch_job()` and `process_hybrid_batch_job()` with unified `JobRunner` class
- [ ] **JOBS-02**: Single job processing loop with batch/hybrid mode flag
- [ ] **JOBS-03**: Shared retry logic, error handling, and status updates
- [ ] **JOBS-04**: Configurable SKU processing strategy (full generation vs variant adaptation)
- [ ] **JOBS-05**: Proper cancellation support and graceful shutdown
- [ ] **JOBS-06**: Batch and hybrid generation produce identical results to current implementation

### GPT-5.2 Fixes

- [ ] **GPT-01**: Remove `temperature=0.7` when `reasoning_effort` is set (mutually exclusive)
- [ ] **GPT-02**: Default `reasoning_effort` to `"medium"` when env var is unset
- [ ] **GPT-03**: Switch from `json_object` to `json_schema` strict mode
- [ ] **GPT-04**: Add `prompt_cache_retention: "24h"` for batch runs
- [ ] **GPT-05**: Restructure system prompt with XML tags (incremental, deploy-and-test per change)
- [ ] **GPT-06**: Each bug fix is a separate PR with curl verification against live endpoint

### Provider Abstraction

- [ ] **PROV-01**: Provider abstraction layer (`providers/base.py`) with common `generate(system_prompt, user_prompt, schema) -> structured_output` interface
- [ ] **PROV-02**: OpenAI/GPT-5.2 provider refactored to use abstraction
- [ ] **PROV-03**: Anthropic/Claude provider implementation with structured JSON output
- [ ] **PROV-04**: Provider factory supports selection via environment variable
- [ ] **PROV-05**: Claude provider tested against all 3 content platforms (Google, Bing, Shopify)

### Model Evaluation

- [ ] **EVAL-01**: Select 10 diverse SKUs (mix of categories, single vs multi-SKU products)
- [ ] **EVAL-02**: Generate content with both providers using identical prompts
- [ ] **EVAL-03**: Blind human scoring by Bobby/Robert on title quality, description quality, brand voice, accuracy
- [ ] **EVAL-04**: Compare cost per SKU, latency, and consistency across runs
- [ ] **EVAL-05**: Clear data on which provider produces better content for which scenarios
- [ ] **EVAL-06**: Cost/quality tradeoff documented

### Bing Fix

- [ ] **BING-01**: Diagnose why Bing titles don't use `{FINISH_NAME}` placeholder
- [ ] **BING-02**: Fix the prompt to enforce `{FINISH_NAME}` in Bing titles
- [ ] **BING-03**: Regenerate the 85 broken Bing titles
- [ ] **BING-04**: Verify variant expansion works correctly with placeholders

## v2 Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Optimization Loop

- **OPT-01**: Performance-informed regeneration (use post-publish metrics to trigger content updates)
- **OPT-02**: A/B testing framework for generated content
- **OPT-03**: Automated quality scoring pipeline (currently manual approval)

### Dashboard Intelligence

- **DASH-01**: Tier intelligence redesign (distribution scoring, revenue leakage)
- **DASH-02**: Intent execution tracking (035b migration tables)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dashboard UI changes | Pipeline-only milestone — dashboard is stable |
| Database migrations (034b, 035b) | Not yet evaluated for production readiness |
| Prompt content rewriting | Phase 27 proved GPT-5.2 is hyper-sensitive; only incremental XML tag changes |
| Multi-provider fallback chains | Complexity not justified until evaluation data proves value |
| Automated LLM-as-judge scoring | Evaluation bias risk; human scoring is ground truth for this milestone |
| New content generation modes | Focus on reliability of existing modes first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DECOMP-01 | Phase 1 | Complete |
| DECOMP-02 | Phase 1 | Complete |
| DECOMP-03 | Phase 1 | Complete |
| DECOMP-04 | Phase 1 | Complete |
| DECOMP-05 | Phase 2 | Complete |
| DECOMP-06 | Phase 2 | Complete |
| DECOMP-07 | Phase 2 | Complete |
| DECOMP-08 | Phase 2 | Complete |
| DECOMP-09 | Phase 3 | Pending |
| DECOMP-10 | Phase 2 | Complete |
| DECOMP-11 | Phase 2 | Partial (intent+finish done, generation pending 02-02) |
| JOBS-01 | Phase 3 | Pending |
| JOBS-02 | Phase 3 | Pending |
| JOBS-03 | Phase 3 | Pending |
| JOBS-04 | Phase 3 | Pending |
| JOBS-05 | Phase 3 | Pending |
| JOBS-06 | Phase 3 | Pending |
| GPT-01 | Phase 4 | Pending |
| GPT-02 | Phase 4 | Pending |
| GPT-03 | Phase 4 | Pending |
| GPT-04 | Phase 4 | Pending |
| GPT-05 | Phase 4 | Pending |
| GPT-06 | Phase 4 | Pending |
| PROV-01 | Phase 5 | Pending |
| PROV-02 | Phase 5 | Pending |
| PROV-03 | Phase 5 | Pending |
| PROV-04 | Phase 5 | Pending |
| PROV-05 | Phase 5 | Pending |
| EVAL-01 | Phase 6 | Pending |
| EVAL-02 | Phase 6 | Pending |
| EVAL-03 | Phase 6 | Pending |
| EVAL-04 | Phase 6 | Pending |
| EVAL-05 | Phase 6 | Pending |
| EVAL-06 | Phase 6 | Pending |
| BING-01 | Phase 7 | Pending |
| BING-02 | Phase 7 | Pending |
| BING-03 | Phase 7 | Pending |
| BING-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability populated by roadmap creation*
