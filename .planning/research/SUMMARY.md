# Project Research Summary

**Project:** Pipeline Reliability Rewrite + Model Evaluation
**Domain:** FastAPI monolith decomposition + LLM provider abstraction + model evaluation
**Researched:** 2026-03-03
**Confidence:** HIGH

## Executive Summary

This is a subsequent-milestone engineering project, not a greenfield build. The core stack (FastAPI, Pydantic v2, OpenAI SDK, Supabase, Cloud Run) is already in production. The central challenge is safely decomposing a 3,737-line `main.py` monolith into testable modules while preserving a fragile, proven production system — then adding a Claude provider and running a data-driven head-to-head model evaluation. The recommended approach is strictly incremental: extract one concern group at a time, run the full test suite after each step, and never modify prompt content during structural refactoring.

The highest-leverage work in this milestone is GPT-5.2 bug remediation. Five known bugs exist in `openai_provider.py` (temperature/reasoning_effort conflict, zero reasoning default, legacy `json_object` mode, no prompt cache retention, `=== ===` headers). Each must be fixed as a separate PR with curl verification against `920D-6` before proceeding to the next. Phase 27 proved that even cosmetic prompt changes silently break GPT-5.2 structured output — this risk pervades every phase that touches `prompts.py`. The Bing `{FINISH_NAME}` bug (85/98 titles broken) is a parallel-track fix that does not depend on decomposition and should be addressed alongside or after the GPT-5.2 fixes.

The evaluation is the capstone. Claude (`anthropic>=0.84.0`) must be implemented as a drop-in `LLMProvider` implementation, the GPT-5.2 bugs must be fixed to establish a clean baseline, and then 10 diverse SKUs should be run through both providers with blind human scoring by Bobby/Robert. The risk of LLM-as-judge bias is real and documented — human judgment is the required ground truth. The evaluation must produce concrete cost/latency/quality data, not speculation, before any provider switch decision is made.

---

## Key Findings

### Recommended Stack

The only new dependency is `anthropic>=0.84.0`. Everything else already exists in `pyproject.toml`. The `AsyncAnthropic` client mirrors the `OpenAIProvider` pattern closely, with three key differences: `output_config` (not `response_format`), `max_tokens` (not `max_completion_tokens`), and `system=` as a separate kwarg. Native structured output via `output_config.format.json_schema` eliminates retry loops.

For module decomposition and evaluation, the existing `pytest + pytest-asyncio + unittest.mock.AsyncMock` toolchain handles everything. No new testing frameworks needed. The evaluation harness should be a custom `pytest.mark.parametrize` test that writes to CSV — `deepeval` and similar frameworks add heavyweight dependencies with no benefit for a 10-SKU human-scored comparison.

**Core technologies:**
- `anthropic>=0.84.0`: Claude SDK — mirrors `OpenAIProvider` pattern, native JSON schema structured output, `AsyncAnthropic` client
- `claude-sonnet-4-5`: Evaluation model — same tier as GPT-5.2 (capable reasoning at moderate cost), most production-relevant comparison
- `pytest` + `csv` stdlib: Evaluation harness — zero new dependencies, human scoring in spreadsheet is the ground truth
- Existing `ruff` + `mypy`: Extraction safety — run after every module extraction to catch circular imports and type contract violations

### Expected Features

Research identified a clear two-tier feature set. The P1 items are blockers — the milestone fails without them. The P2 items should complete within the milestone if capacity allows.

**Must have (table stakes / P1):**
- Backward-compatible decomposition — all existing API endpoints work identically post-extraction
- `run_async_in_thread()` preserved — background jobs die on Cloud Run without `daemon=False` threads
- Unit tests for each extracted module — the reason for decomposition is testability
- Finish placeholder contract unchanged — `{FINISH_NAME}` and `{FINISH_SENTENCE}` must survive extraction intact
- GPT-5.2 temperature/reasoning_effort conflict fixed — mutually exclusive parameters, currently always broken
- GPT-5.2 reasoning_effort default fixed — unset env var means zero reasoning; default to `"medium"`
- Claude provider implementing `LLMProvider` ABC — needed for evaluation
- Bing `{FINISH_NAME}` bug fixed — 85/98 Bing titles have hardcoded finish names
- Regenerate 85 broken Bing titles — fix without regeneration leaves broken content in production
- Head-to-head model evaluation — produces evidence for the provider switch decision

**Should have (competitive / P2):**
- Unified `JobRunner` replacing duplicated batch processors — eliminates 500+ lines of near-identical code
- GPT-5.2 `json_schema` strict mode (replaces `json_object`) — eliminates retry loops at batch scale
- GPT-5.2 prompt cache retention (`24h`) — meaningful cost reduction for 120+ SKU batches
- GPT-5.2 XML tag prompt structure (replaces `=== ===`) — documented quality improvement, highest risk
- `main.py` reduced to <500 lines — route definitions only
- Cost/quality/latency comparison documented — makes future provider decisions data-driven

**Defer (future milestone / P3):**
- Provider performance dashboard UI — out of scope; store eval results as JSON/Supabase rows
- LLM-as-judge automated scoring — supplement human scoring only after calibration against human ground truth
- Primary provider switch to Claude — requires evaluation data first; switch decision belongs in a future milestone

### Architecture Approach

The target architecture separates a 3,737-line monolith into four layers: API entry (`main.py` at <500 lines), route modules (`api/routers/`), service/logic layer (extracted `JobRunner`, `FinishService`, `GenerationService`), and the existing provider abstraction layer (add `ClaudeProvider`). The extraction order is determined by the import dependency graph: `schemas` first (no dependencies), then `FinishService`, then `GenerationService`, then `JobRunner`, then route routers, then `main.py` slim-down. Provider work (Claude) runs in parallel with extraction phases 1-4 because it touches only `providers/claude_provider.py` and `providers/factory.py`.

**Major components:**
1. `api/schemas/` — extracted Pydantic models; enables isolated unit testing without importing the full app
2. `api/job_runner.py` — unified `JobRunner` replacing `process_batch_job` and `process_hybrid_batch_job`; owns lifecycle (status transitions, error handling, thread safety); ~60% shared logic between current functions
3. `providers/claude_provider.py` — `LLMProvider` ABC implementation using `anthropic.AsyncAnthropic.messages.create()` with `tool_choice` for structured JSON; maps `reasoning_effort` to Claude's `thinking.budget_tokens`
4. `api/routers/` — `generation.py`, `batch.py`, `hybrid.py`, `images.py`, `admin.py`; existing pattern already used by `search_insights`, `monitoring`, `gmc_sync`, `performance_baseline` routers

### Critical Pitfalls

1. **GPT-5.2 prompt sensitivity** — Even cosmetic changes to `prompts.py` cause empty/placeholder-only output in strict JSON mode. Prevention: one change per PR, deploy, curl `920D-6`, verify description >500 chars before proceeding. `self_score` and `scoring_rubric` are load-bearing; never remove them without isolated testing.

2. **Breaking `run_async_in_thread` during decomposition** — If `daemon=False` is changed to `daemon=True` (or replaced with `BackgroundTasks`), batch jobs die silently on Cloud Run. Prevention: extract `run_async_in_thread` to a shared module first, write a unit test asserting `thread.daemon == False`, never change the threading pattern.

3. **Shared provider state across SKUs** — If `OpenAIProvider` is instantiated at module level and shared across concurrent SKUs, `_last_usage` and `_last_retry_counts` instance variables produce race conditions. Prevention: call `get_provider()` inside the SKU loop and `close_provider()` in `finally`, exactly as current code does.

4. **Circular imports during decomposition** — Moving 30+ models and 50+ functions creates cross-module import cycles. Prevention: define the import DAG before writing code (`types → schemas → utilities → persistence → processors → routes`); use `TYPE_CHECKING` guards for type-hint-only imports; run `python -c "import feedops.api.main"` after every extraction step.

5. **Evaluation bias** — If Claude scores Claude outputs or GPT-5.2 scores GPT-5.2 outputs, results are invalid. Prevention: human blind review by Robert is the required ground truth; labels removed, output order randomized; objective rule-violation counting (not holistic scoring) as primary metric alongside cost and latency.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Schemas Extraction
**Rationale:** Schemas have zero dependencies (pure Pydantic models). Extracting them first eliminates the most common circular import source and unblocks all subsequent extractions. Tests written here verify the extraction pattern before it's repeated for more complex modules.
**Delivers:** `api/schemas/` subpackage with all ~20 Pydantic models; unit tests importable without spinning up the full app; proven extraction pattern for subsequent phases
**Addresses:** Backward compatibility, unit testability (table stakes features)
**Avoids:** Circular imports (Pitfall 4) — DAG established before any business logic moves

### Phase 2: FinishService and GenerationService Extraction
**Rationale:** Both services have clean, well-defined interfaces and limited dependencies. `FinishService` owns the finish placeholder contract which must not be broken. Extracting these before `JobRunner` means the job processor can delegate to tested, isolated services.
**Delivers:** `pipeline/finish_service.py` with placeholder contract; `api/generation_service.py` with metrics wrapper; unit tests for each; prompt authority chain verified intact
**Addresses:** Finish placeholder contract preserved (table stakes)
**Avoids:** Prompt content contamination (Pitfall 1) — extract by import path only, zero text changes to `SYSTEM_PROMPT`

### Phase 3: JobRunner and Route Extraction
**Rationale:** Depends on clean service layer from Phase 2. Route extraction uses the existing `APIRouter` pattern (4 routers already extracted). `JobRunner` unification consolidates the ~60% shared logic between `process_batch_job` and `process_hybrid_batch_job`.
**Delivers:** Unified `api/job_runner.py`; all remaining routes in `api/routers/`; `main.py` at <500 lines; `run_async_in_thread` extracted to shared location with `daemon=False` test
**Addresses:** Unified JobRunner (P2 differentiator), `main.py` <500 lines target
**Avoids:** `run_async_in_thread` breakage (Pitfall 2) — extracted first within this phase with unit test

### Phase 4: GPT-5.2 Bug Fixes (5 separate PRs)
**Rationale:** Must happen after decomposition so fixes are made in isolated, testable files. Must happen before evaluation to establish a clean baseline for comparison. Each fix is a separate PR with curl verification. Order: (1) temperature/reasoning_effort conflict, (2) reasoning_effort default, (3) `json_schema` strict mode, (4) prompt cache retention, (5) XML tag prompt structure (highest risk, last).
**Delivers:** All 5 GPT-5.2 bugs fixed; clean production baseline; reduced retry waste; improved content quality
**Addresses:** Both P1 provider bugs; `json_schema` and prompt cache (P2); XML structure (P2, highest risk)
**Avoids:** Batching prompt changes (anti-feature), silent quality regressions (Pitfall 1)

### Phase 5: Claude Provider and Factory
**Rationale:** Can run in parallel with Phases 1-3. Placed here to ensure GPT-5.2 baseline is clean before evaluation. Uses the existing `LLMProvider` ABC — additive change only, no existing code modified.
**Delivers:** `providers/claude_provider.py` with `tool_choice` structured output; `factory.py` updated for `ANTHROPIC_API_KEY`; unit tests; `get_provider(preferred="claude")` functional; tested against all three platforms (google, bing, shopify)
**Addresses:** Claude provider (table stakes for evaluation)
**Avoids:** Schema incompatibility (Pitfall 5) — test with production schema on 3 diverse SKUs before declaring complete

### Phase 6: Model Evaluation
**Rationale:** Requires both providers functional and GPT-5.2 baseline clean. Human blind scoring is the ground truth. 10 diverse SKUs selected to cover different categories, collection types, and content complexity.
**Delivers:** `tests/eval/test_model_comparison.py` with CSV output; 10 SKUs evaluated on both providers; blind human scoring by Bobby/Robert; cost/latency/quality comparison table; documented provider recommendation
**Addresses:** Head-to-head evaluation (P1), cost/quality/latency documentation (P2)
**Avoids:** Evaluation bias (Pitfall 6) — evaluation protocol designed before running comparisons; blind review mandatory

### Phase 7: Bing Fix and Regeneration
**Rationale:** Independent of decomposition and provider work. Can technically run in parallel with Phases 1-3 but scheduled after Phase 4 to ensure it uses the corrected incremental prompt change protocol.
**Delivers:** Root cause of `{FINISH_NAME}` absence diagnosed and fixed in `prompts.py`; 85 broken Bing titles regenerated; variant expansion verified correct; SQL check confirming 0 hardcoded finish names in Bing content
**Addresses:** Bing fix and regeneration (both P1)
**Avoids:** Batching prompt changes (anti-feature) — fix is a single isolated change with deploy-and-test

### Phase Ordering Rationale

- **Decompose before fixing bugs:** Modular isolation means bug fixes happen in a focused, testable file rather than a 3,737-line monolith. This is a risk reduction dependency, not a hard technical one — but Phase 27 showed that context matters when touching GPT-5.2 prompt behavior.
- **Fix GPT-5.2 before evaluation:** The evaluation needs a clean GPT-5.2 baseline. Comparing Claude against a buggy GPT-5.2 produces misleading results and potentially defers a valid provider switch.
- **Provider parallel with decomposition:** `ClaudeProvider` only touches `providers/claude_provider.py` and `providers/factory.py` — no overlap with extraction work. Parallelizing saves wall-clock time.
- **Bing fix last (or parallel):** Independent of decomposition and provider. Scheduled after Phase 4 to ensure the incremental prompt-change protocol is established and practiced before applying it to the Bing fix.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (GPT-5.2 bugs):** XML tag migration (bug #5) is the highest risk change. Research the exact diff against current `prompts.py` `=== ===` structure before planning the PR. Requires baseline capture of current output lengths before any change.
- **Phase 6 (Evaluation):** SKU selection criteria and scoring rubric design need deliberate planning. Which 10 SKUs represent the catalog diversity? What are the objective rule-violation checks vs. subjective quality dimensions?
- **Phase 5 (Claude provider):** The `tool_choice` structured output approach in ARCHITECTURE.md differs from the `output_config.format` approach in STACK.md. These need to be reconciled — verify which path supports Claude's extended thinking alongside structured output before implementation.

Phases with standard patterns (skip research during planning):
- **Phase 1 (Schemas):** Pydantic model extraction is a textbook refactoring. Existing extraction pattern already proven with 4 existing routers.
- **Phase 3 (Route extraction):** `APIRouter` pattern is well-documented and already used in this codebase for 4 routers.
- **Phase 7 (Bing fix):** Root cause is known (prompt instruction missing). Protocol is established. No new research needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `anthropic>=0.84.0` verified against official docs; codebase directly inspected for existing patterns; version compatibility confirmed |
| Features | HIGH | Direct codebase analysis of `main.py` and `providers/`; feature gaps verified against existing code; priorities based on proven production constraints |
| Architecture | HIGH | Codebase directly inspected; FastAPI `APIRouter` pattern verified against official docs and existing usage in this codebase |
| Pitfalls | HIGH (project-specific) / MEDIUM (ecosystem) | Project-specific pitfalls backed by Phase 27 post-mortem and audit docs; ecosystem pitfalls (circular imports, LLM bias) from multiple community sources |

**Overall confidence:** HIGH

### Gaps to Address

- **Claude structured output API path:** STACK.md recommends `output_config.format.json_schema`; ARCHITECTURE.md recommends `tool_choice={"type": "tool", "name": "output"}`. These are different implementation approaches. Reconcile before Phase 5 planning — `tool_choice` approach is more reliable for enforcing schema but adds one more API surface area to understand.
- **Extended thinking compatibility with structured output:** Whether Claude's `thinking` mode can be used simultaneously with `tool_choice` structured output is not confirmed. If not compatible, the `reasoning_effort` mapping in `ClaudeProvider` may need to be disabled by default.
- **10 SKU evaluation set:** Not defined in research. Should span different categories (grab bars, shower doors, accessories), collection types (named vs unnamed), and content complexity levels (simple vs multi-attribute). Bobby/Robert should confirm the selection before Phase 6.
- **Bing `{FINISH_NAME}` root cause:** Research identifies the symptom (85/98 titles hardcoded) and likely location (`prompts.py` Bing section) but the exact prompt instruction gap needs a targeted `prompts.py` review at planning time.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `src/feedops/api/main.py` (3,737 lines) — function groupings, line number references
- Codebase: `src/feedops/providers/` — base, openai, gemini, factory, reliability
- Codebase: `src/feedops/quality/eval_framework.py` + `tests/test_eval_framework.py`
- [Anthropic Structured Outputs Official Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — `output_config.format.json_schema` pattern
- [FastAPI Bigger Applications Official Docs](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — `APIRouter` pattern
- [FastAPI Background Tasks Official Docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) — lifecycle limitations

### Secondary (MEDIUM confidence)
- [anthropics/anthropic-sdk-python GitHub](https://github.com/anthropics/anthropic-sdk-python) — version 0.84.0 current
- [FastAPI Best Practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices) — community consensus
- [LLM evaluation bias 2025](https://www.mdpi.com/2078-2489/16/8/652) — positional bias in pairwise comparisons
- [LLM-as-judge self-preference bias](https://cameronrwolfe.substack.com/p/llm-as-a-judge) — self-preference documentation

### Project Documentation
- `CLAUDE.md` — GPT-5.2 Known Issues, Phase 27 learnings, prompt sensitivity
- `memory/MEMORY.md` — Phase 27 critical discovery, Bing bug details
- `docs/setup/pipeline-rewrite-brief.md` — Milestone brief and `main.py` analysis
- `docs/audit/background-task-fix-2026-02-08.md` — `run_async_in_thread` rationale

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*
