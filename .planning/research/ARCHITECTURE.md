# Architecture Research

**Domain:** FastAPI pipeline decomposition + LLM provider abstraction
**Researched:** 2026-03-03
**Confidence:** HIGH (codebase directly inspected; patterns verified against official FastAPI docs and community consensus)

---

## Standard Architecture

### System Overview

The current system is a FastAPI monolith where a single 3,737-line `main.py` owns everything:
routes, Pydantic schemas, business logic, batch job processors, helper functions, and telemetry.
The target architecture separates concerns into layers that can be developed, tested, and replaced
independently.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API Entry Layer                              │
│  main.py (<500 lines) — CORSMiddleware, lifespan, router mounts,    │
│  run_async_in_thread(), http middleware                              │
├────────────┬──────────────┬──────────────┬──────────────────────────┤
│  Route     │  Route       │  Route       │  Route                   │
│  Modules   │  Modules     │  Modules     │  Modules                 │
│ (generation│ (regenerate) │ (batch /     │ (backfill, score-intent, │
│  /health)  │              │  hybrid)     │  perf, images)           │
├────────────┴──────────────┴──────────────┴──────────────────────────┤
│                       Service / Logic Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  JobRunner   │  │FinishService │  │  GenerationService       │   │
│  │ (unified     │  │(placeholder  │  │ (wraps generate_per_     │   │
│  │  batch +     │  │ contract,    │  │  platform; metrics       │   │
│  │  hybrid)     │  │ parity)      │  │  wrapper; prompt build)  │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │
├─────────┴─────────────────┴──────────────────────┴───────────────────┤
│                       Provider Abstraction Layer                      │
│  providers/base.py (LLMProvider ABC, LLMError, close_provider)       │
│  providers/factory.py (get_provider, FallbackProvider)               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ OpenAIProvider   │  │  ClaudeProvider  │  │  GeminiProvider  │   │
│  │ (GPT-5.2, bugs   │  │  (NEW — Anthropic │  │  (image gen)     │   │
│  │  to fix here)    │  │  Messages API)   │  │                  │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
├──────────────────────────────────────────────────────────────────────┤
│                       Infrastructure Layer                            │
│  schemas/          persistence/      telemetry/       db/            │
│  (Pydantic models  (supabase write   (metrics,        (supabase_    │
│  extracted from     helpers, upsert   log_event,       client,      │
│  main.py)           patterns)         cost estimator)  queries)     │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Lives In |
|-----------|---------------|----------|
| `main.py` | App factory, CORS, lifespan, middleware, `run_async_in_thread`, router mounts | `api/main.py` |
| Route modules | Request parsing, response serialization, call into service layer | `api/routers/` (new) |
| `schemas/` | All Pydantic `BaseModel` classes moved out of `main.py` | `api/schemas/` (new) |
| `JobRunner` | Unified `process_batch_job` + `process_hybrid_batch_job` | `api/job_runner.py` or `jobs/runner.py` |
| `FinishService` | Finish placeholder contract, parity enforcement, fallback sentences | `pipeline/finish_service.py` |
| `GenerationService` | `_generate_with_metrics` wrapper, prompt assembly, generate-then-persist flow | `api/generation_service.py` |
| `LLMProvider` ABC | Common interface: `generate()`, `health_check()`, `aclose()`, `name` | `providers/base.py` (already exists) |
| `OpenAIProvider` | GPT-5.2 calls with bug fixes | `providers/openai_provider.py` (exists, to be fixed) |
| `ClaudeProvider` | Anthropic Messages API, `json_schema` strict mode | `providers/claude_provider.py` (new) |
| `GeminiProvider` | Imagen calls for lifestyle images | `providers/gemini_provider.py` (exists) |
| `factory.py` | Provider selection, `FallbackProvider` | `providers/factory.py` (exists) |
| `generation_telemetry.py` | Cost estimator, token extraction, provider label | `api/generation_telemetry.py` (exists) |
| `persistence.py` | Supabase upsert helpers, content ID lookups | `generation/persistence.py` (exists) |

---

## Recommended Project Structure

After decomposition, `src/feedops/api/` becomes:

```
src/feedops/
├── api/
│   ├── main.py                    # <500 lines: app factory only
│   ├── routers/                   # New: one file per endpoint group
│   │   ├── __init__.py
│   │   ├── generation.py          # /optimize-sku, /regenerate, /regenerate/{job_id}
│   │   ├── batch.py               # /batch-optimize, /batch-status/{job_id}
│   │   ├── hybrid.py              # /hybrid-generate
│   │   ├── images.py              # /generate-images
│   │   └── admin.py               # /health, /backfill/*, /score-intent
│   ├── schemas/                   # New: extracted Pydantic models
│   │   ├── __init__.py
│   │   ├── generation.py          # OptimizeRequest/Response, RegenerateRequest/Response
│   │   ├── batch.py               # BatchOptimizeRequest, BatchJobResponse, BatchStatusResponse
│   │   ├── hybrid.py              # HybridGenerateRequest, HybridJobResponse
│   │   └── intent.py              # ScoreIntentRequest/Response
│   ├── job_runner.py              # New: unified JobRunner replacing process_batch_job + process_hybrid_batch_job
│   ├── generation_service.py      # Extract: _generate_with_metrics, prompt assembly helpers
│   ├── generation_telemetry.py    # Already exists — no change needed
│   ├── prompt_builder.py          # Already exists — no change needed
│   ├── prompt_loader.py           # Already exists — no change needed
│   ├── hybrid_generation.py       # Already exists — no change needed
│   ├── multi_sku_detection.py     # Already exists — no change needed
│   ├── sku_alias.py               # Already exists — no change needed
│   ├── runtime_controls.py        # Already exists — no change needed
│   ├── env_contract.py            # Already exists — no change needed
│   ├── supabase_loader.py         # Already exists — no change needed
│   ├── backfill.py                # Already exists — no change needed
│   ├── search_insights.py         # Already exists — no change needed
│   ├── monitoring.py              # Already exists — no change needed
│   ├── gmc_sync.py                # Already exists — no change needed
│   └── performance_baseline.py    # Already exists — no change needed
├── providers/
│   ├── base.py                    # Already exists — LLMProvider ABC (solid)
│   ├── factory.py                 # Already exists — get_provider, FallbackProvider
│   ├── openai_provider.py         # Exists — fix 5 GPT-5.2 bugs here
│   ├── claude_provider.py         # New: Anthropic Messages API implementation
│   ├── gemini_provider.py         # Already exists — image gen
│   └── reliability.py             # Already exists — circuit breaker, backoff
├── pipeline/
│   ├── finish_service.py          # Extract: _enforce_finish_sentence_parity + helpers
│   │                              # Currently: _enforce_finish_sentence_parity in main.py (lines 1496-1600)
│   └── ...                        # Everything else already extracted
└── generation/
    ├── persistence.py             # Already exists — task result helpers
    └── ...
```

### Structure Rationale

- **`api/routers/`**: FastAPI's native `APIRouter` pattern. Each router is included in `main.py` with `app.include_router()`. This is the standard pattern documented by FastAPI for larger applications — already used by `search_insights`, `monitoring`, `gmc_sync`, `performance_baseline`. Extend to the remaining routes in `main.py`.
- **`api/schemas/`**: Pydantic models have zero business logic. Extracting them removes ~150 lines from `main.py` and makes them importable for unit tests without spinning up the full app.
- **`api/job_runner.py`**: `process_batch_job()` (lines 2792–3072) and `process_hybrid_batch_job()` (lines 3072–3615) share the same structure: set job to processing, iterate SKUs, generate, persist, update status, handle failures. ~60% identical code. A single `JobRunner` class with a `run()` method parameterized by job type eliminates the duplication.
- **`pipeline/finish_service.py`**: `_enforce_finish_sentence_parity()` (lines 1496–1600) is a self-contained operation with well-defined inputs/outputs. It touches finish placeholder logic, LLM call, and validation — belongs in the pipeline layer, not the route handler.
- **`providers/claude_provider.py`**: The `LLMProvider` ABC already defines the correct interface. A Claude provider is an additive change: new file, new factory entry, no existing code modified.

---

## Architectural Patterns

### Pattern 1: APIRouter Extraction

**What:** Move route handler functions from `main.py` into dedicated `APIRouter` modules. Each router is imported and mounted in `main.py` with `app.include_router(router)`.

**When to use:** Any time a group of routes shares a common prefix, tag, or concern. Already proven in this codebase: `search_insights_router`, `monitoring_router`, `gmc_sync_router`, `performance_baseline_router` are all already extracted.

**Trade-offs:** Routes that depend on module-level state (e.g., the `run_async_in_thread` helper defined in `main.py`) need that helper passed explicitly or moved to a shared location (`api/thread_runner.py`).

**Example:**
```python
# api/routers/generation.py
from fastapi import APIRouter
from feedops.api.schemas.generation import OptimizeRequest, OptimizeResponse
from feedops.api.generation_service import GenerationService

router = APIRouter(tags=["Generation"])

@router.post("/optimize-sku", response_model=OptimizeResponse)
async def optimize_single_sku(request: OptimizeRequest):
    ...

# api/main.py
from feedops.api.routers.generation import router as generation_router
app.include_router(generation_router)
```

### Pattern 2: Unified JobRunner (Template Method)

**What:** Replace `process_batch_job()` and `process_hybrid_batch_job()` with a single `JobRunner` that owns the shared lifecycle (DB status transitions, error handling, thread safety) and delegates per-item work to a callable.

**When to use:** Two or more background job functions with identical lifecycle code but different per-item logic. This codebase has exactly that.

**Trade-offs:** Adds one abstraction layer. The payoff is that lifecycle bugs (stuck "processing" status, failed job recovery) get fixed in one place instead of two. The `run_async_in_thread()` pattern must be preserved — `JobRunner.run()` is still called from within a `run_async_in_thread` wrapper, not via `BackgroundTasks`.

**Example:**
```python
# api/job_runner.py
class JobRunner:
    def __init__(self, job_id: str, supabase, options: dict):
        self.job_id = job_id
        self.supabase = supabase
        self.options = options

    async def run(self, skus: list[str], process_sku_fn: Callable) -> JobResult:
        self._mark_processing()
        completed, failed = 0, 0
        for sku in skus:
            try:
                await process_sku_fn(sku)
                completed += 1
            except Exception as exc:
                failed += 1
                self._record_failure(sku, exc)
            self._update_progress(completed, failed)
        self._mark_complete(completed, failed)
        return JobResult(completed=completed, failed=failed)
```

### Pattern 3: LLM Provider ABC with Named Constructor

**What:** The `LLMProvider` ABC already exists and is the right pattern. The missing piece is a `ClaudeProvider` implementation. The factory (`get_provider`) selects providers based on environment variables — adding Claude requires only: new file, new factory branch for `ANTHROPIC_API_KEY`, new `claude` option in `preferred` parameter.

**When to use:** Any new LLM provider. The ABC enforces the contract: `generate()`, `health_check()`, `aclose()`, `name`.

**Trade-offs:** The ABC's `generate()` signature uses `reasoning_effort` and `max_completion_tokens` — these are OpenAI-centric parameter names. For Claude (which uses `thinking` budget tokens), the implementation maps internally. The interface stays stable.

**Example:**
```python
# providers/claude_provider.py
import anthropic
from feedops.providers.base import LLMProvider, LLMError, ImageInput

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"claude/{self._model}"

    async def generate(
        self,
        prompt: str,
        schema: dict,
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict:
        # Map reasoning_effort to Claude's thinking budget
        thinking = None
        if reasoning_effort:
            budget = {"low": 1024, "medium": 4096, "high": 16000}.get(reasoning_effort)
            if budget:
                thinking = {"type": "enabled", "budget_tokens": budget}

        response = await self._client.messages.create(
            model=self._model,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "output",
                "description": "Return structured output",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": "output"},
            thinking=thinking,
            max_tokens=max_completion_tokens or 4096,
        )
        # Extract tool_use block
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        raise LLMError("No tool_use block in response", provider=self.name)

    async def health_check(self) -> bool:
        return bool(self._client.api_key)

    async def aclose(self) -> None:
        await self._client.close()
```

### Pattern 4: Schema Module Extraction

**What:** Move all Pydantic `BaseModel` classes from `main.py` into `api/schemas/` submodules grouped by concern.

**When to use:** When schemas are needed in tests or multiple route modules. Extraction allows `from feedops.api.schemas.generation import OptimizeRequest` without importing the full FastAPI app.

**Trade-offs:** Import paths change. Since schemas are currently private to `main.py` (callers go through HTTP), no external Python callers are affected. Test files may need updated imports.

---

## Data Flow

### Single-SKU Generation Request

```
POST /optimize-sku
    ↓
api/routers/generation.py::optimize_single_sku()
    ↓ deserialize OptimizeRequest
api/generation_service.py::GenerationService.generate()
    ↓ load product data
api/supabase_loader.py::load_parent_sku_from_supabase()
    ↓ build prompts
api/prompt_builder.py::build_core_prompt()
    ↓ call LLM
providers/factory.py::get_provider()
providers/openai_provider.py::OpenAIProvider.generate()
    ↓ validate finish sentences
pipeline/finish_service.py::FinishService.enforce_parity()
    ↓ persist result
generation/persistence.py::persist_finish_sentences()
    ↓ return
api/schemas/generation.py::OptimizeResponse
```

### Batch Job Flow

```
POST /batch-optimize
    ↓
api/routers/batch.py::batch_optimize()
    ↓ create DB job record
    ↓ launch thread
api/main.py::run_async_in_thread(job_runner.run, job_id=..., skus=...)
                                     [non-daemon thread, new event loop]
    ↓ (returns job_id immediately to caller)

[background thread]:
api/job_runner.py::JobRunner.run()
    ↓ for each SKU: call GenerationService
    ↓ update batch_generation_jobs progress
    ↓ on completion: mark complete
```

### Provider Selection

```
get_provider(preferred=None)
    ↓
  ANTHROPIC_API_KEY set? → ClaudeProvider (new)
  OPENAI_API_KEY set?    → OpenAIProvider (default)
  GEMINI_API_KEY set?    → GeminiProvider
  FEEDOPS_FORCE_PROVIDER_FALLBACK? → FallbackProvider(primary, secondary)
```

### Key Data Flows

1. **Finish sentence contract:** Base description → `strip_hardcoded_finish_names()` → `normalize_base_description_with_finish_placeholder()` → LLM finish call → `normalize_and_validate_finish_sentences()` → persisted with `{FINISH_NAME}` placeholder intact.

2. **Prompt authority chain:** `prompt_builder.py` (orchestrator) → `prompts.py` (SYSTEM_PROMPT) → `prompt_loader.py` (DB gold examples) → `shopping_intelligence.py` (YAML config). This chain must not be disturbed during extraction — only route-to-service boundaries move.

3. **Job recovery:** On startup (`lifespan`), stale `processing` jobs older than 2 hours are set to `failed`. After extraction, this recovery sweep stays in `main.py` lifespan or moves to `job_runner.py` as a class method `JobRunner.recover_stale()`.

---

## Build Order

The dependency graph determines what must be extracted before what else can be tested.

```
Phase 1: Schemas (no dependencies — standalone Pydantic models)
    ↓
Phase 2: FinishService (depends on pipeline imports already extracted)
    ↓
Phase 3: GenerationService (depends on providers, prompt_builder — all exist)
    ↓
Phase 4: JobRunner (depends on GenerationService + FinishService)
    ↓
Phase 5: Route routers (depend on schemas + service layer)
    ↓
Phase 6: main.py slim-down (mounts all routers, <500 lines)
```

Provider work (Claude) is independent and can happen in parallel with phases 1–4:
```
Parallel track: OpenAI bug fixes → ClaudeProvider → factory update → evaluation harness
```

---

## Scaling Considerations

This is a single Cloud Run service with a bounded SKU catalog. Scaling concerns are operational, not architectural.

| Scale Concern | Current State | After Decomposition |
|--------------|--------------|---------------------|
| Unit testability | Zero (3,737-line file) | Each module independently testable |
| Prompt sensitivity | Changes require full deploy+test | Unchanged — prompt files not touched |
| Background job reliability | Duplicate bug fix surface (2 functions) | Single `JobRunner`, bugs fixed once |
| Provider switching | Manual code change | `ANTHROPIC_API_KEY` env var toggles Claude |
| Batch throughput | Limited by per-SKU LLM latency | Unchanged — parallel SKU processing not in scope |

---

## Anti-Patterns

### Anti-Pattern 1: Touching Prompt Files During Extraction

**What people do:** Move/rename `SYSTEM_PROMPT` or prompt builder functions as "cleanup" during extraction.

**Why it's wrong:** Phase 27 confirmed GPT-5.2 strict JSON mode fails silently on ANY system prompt text change. Even cosmetic renames of variables that are string-interpolated into prompts can shift content.

**Do this instead:** Extract every module EXCEPT prompt content. `prompts.py`, `prompt_builder.py`, and `prompt_loader.py` are moved by reference (import) not by content change. Zero text changes to prompt strings during extraction.

### Anti-Pattern 2: Replacing run_async_in_thread with BackgroundTasks

**What people do:** When moving batch routes to a router module, switch to `BackgroundTasks` because it's the "FastAPI way" for async work.

**Why it's wrong:** Cloud Run containers scale to zero. `BackgroundTasks` are killed when the container shuts down after the HTTP response. `run_async_in_thread()` uses a non-daemon thread with a dedicated event loop that outlives the request.

**Do this instead:** Keep `run_async_in_thread()` in `main.py` (or extract to `api/thread_runner.py`). Inject it into route handlers via dependency injection or import. Never call `background_tasks.add_task()` for long-running generation jobs.

### Anti-Pattern 3: Monolithic JobRunner with Provider as Instance Variable

**What people do:** Store the LLM provider as a `JobRunner.__init__` attribute so it's shared across all SKUs in a batch.

**Why it's wrong:** `get_provider()` returns a fresh client instance. Provider lifecycle (create → generate → `close_provider()`) must be scoped per-SKU, not per-job. The current `process_batch_job` already calls `get_provider()` inside the SKU loop and `close_provider()` in a `finally`. Hoisting the provider to job level causes connection state leaks across SKUs.

**Do this instead:** `JobRunner.run()` calls `get_provider()` and `close_provider()` per SKU iteration, matching the existing pattern.

### Anti-Pattern 4: Claude Provider Using chat/completions Endpoint

**What people do:** Implement `ClaudeProvider.generate()` using the OpenAI-compatible endpoint (`/v1/chat/completions`) that Anthropic exposes, to reuse existing JSON parsing code.

**Why it's wrong:** The OpenAI-compatible endpoint does not support `thinking` (extended reasoning), tool use with strict input schema, or prompt cache retention. Using the native Anthropic SDK (`anthropic.AsyncAnthropic`) is required for full feature parity.

**Do this instead:** Use `anthropic.AsyncAnthropic.messages.create()` with `tool_choice={"type": "tool", "name": "output"}` for structured JSON output. Map `reasoning_effort` to Claude's `thinking.budget_tokens` internally.

### Anti-Pattern 5: Extracting Schemas Without Updating Test Imports

**What people do:** Move `OptimizeRequest` to `api/schemas/generation.py` but leave test files importing from `feedops.api.main`.

**Why it's wrong:** Tests that `from feedops.api.main import OptimizeRequest` still work because Python will resolve the name if it's re-exported — but they're fragile and import the entire application.

**Do this instead:** Update test imports to point at the schema module directly. Add `__all__` to each schema module for explicit public surface.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI (GPT-5.2) | `providers/openai_provider.py` via `AsyncOpenAI` | 5 bugs to fix in this file |
| Anthropic (Claude) | `providers/claude_provider.py` via `AsyncAnthropic` | New file — ABC interface already defined |
| Supabase | `db/supabase_client.py::get_client()` | Called per-request, not a persistent connection |
| Google Ads | `integrations/google_ads_*` | Not in decomposition scope |
| Cloud Run | `run_async_in_thread()` — non-daemon threads | Must be preserved exactly |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Route module ↔ GenerationService | Direct function/class call | No HTTP, no queue |
| GenerationService ↔ providers | `LLMProvider.generate()` ABC | Stable interface — never call provider internals |
| JobRunner ↔ GenerationService | Callback / direct call | JobRunner owns lifecycle; GenerationService owns LLM call |
| JobRunner ↔ Supabase | `get_client()` direct | Job status updates every SKU iteration |
| FinishService ↔ providers | `LLMProvider.generate()` | Finish sentences are a second LLM call per SKU |
| prompt_builder ↔ prompt_loader | Direct function call | No change during extraction |

---

## Sources

- [FastAPI Bigger Applications — Official Docs](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — HIGH confidence
- [FastAPI Best Practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices) — MEDIUM confidence (community, widely cited)
- [Building Production-Ready FastAPI Applications with Service Layer Architecture in 2025](https://medium.com/@abhinav.dobhal/building-production-ready-fastapi-applications-with-service-layer-architecture-in-2025-f3af8a6ac563) — MEDIUM confidence
- [Multi-LLM Systems with Abstract Classes in Python (2025)](https://medium.com/algomart/multi-llm-systems-with-abstract-classes-in-python-038cd6ce78d5) — MEDIUM confidence
- [Interoperability Patterns to Abstract Large Language Model Providers](https://brics-econ.org/interoperability-patterns-to-abstract-large-language-model-providers) — MEDIUM confidence
- Codebase direct inspection: `src/feedops/api/main.py` (3,737 lines), `src/feedops/providers/` — HIGH confidence

---

*Architecture research for: FastAPI pipeline decomposition + LLM provider abstraction (Allied-FeedOps)*
*Researched: 2026-03-03*
