# Stack Research

**Domain:** FastAPI monolith decomposition + LLM provider abstraction + model evaluation
**Researched:** 2026-03-03
**Confidence:** HIGH (existing codebase verified; Anthropic SDK and structured outputs verified via official docs)

---

## Context: What Already Exists

This is a subsequent-milestone project. The core stack (FastAPI, Pydantic v2, OpenAI SDK, Supabase, Cloud Run, pytest-asyncio) is already established and running in production. This research focuses exclusively on the three new concerns:

1. **Module decomposition tooling** — how to safely extract from a 3,737-line monolith
2. **Anthropic Claude provider** — what SDK and API shape to use for structured output
3. **Evaluation harness** — how to run a structured head-to-head model comparison

Do NOT change: FastAPI version, Pydantic version, Supabase client, Google Ads SDK, Cloud Run deployment, or the `run_async_in_thread()` background task pattern.

---

## Recommended Stack

### 1. Anthropic Provider (New Addition)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `anthropic` | `>=0.84.0` | Anthropic Claude SDK | Current stable release (0.84.0 as of 2026-02-25). AsyncAnthropic client mirrors OpenAIProvider pattern exactly. Native structured output via `output_config.format.json_schema` — no retry loops needed. |

**Installation:**
```bash
uv pip install "anthropic>=0.84.0"
```

**Add to `pyproject.toml` dependencies:**
```toml
"anthropic>=0.84.0",
```

**How the Anthropic structured output API works (HIGH confidence — verified via official docs):**

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=api_key)

response = await client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=8000,
    system=system_prompt,       # separate system message (same pattern as OpenAI)
    messages=[{"role": "user", "content": prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": schema,   # same dict the existing LLMProvider.generate() accepts
        }
    },
)
result_text = response.content[0].text
```

Key differences from OpenAI provider:
- `system=` kwarg instead of prepending a `{"role": "system"}` message
- `output_config` instead of `response_format`
- `max_tokens=` (not `max_completion_tokens=`)
- No `reasoning_effort` parameter (Claude uses extended thinking, which is separate)
- Response is always valid JSON when `output_config` is used — no parse-retry loop needed
- Prompt caching: use `cache_control={"type": "ephemeral"}` on the system message block

**Recommended models for evaluation (MEDIUM confidence — model landscape shifts fast):**
- `claude-sonnet-4-5` — best quality/cost balance for production content generation
- `claude-haiku-4-5` — fast/cheap, good for batch jobs or rapid iteration
- `claude-opus-4-6` — highest quality, highest cost; use only for gold-standard comparison

Use `claude-sonnet-4-5` as the default Claude model for head-to-head evaluation against `gpt-5.2`. It occupies the same tier (capable reasoning model at moderate cost) and gives the most useful production-relevant comparison.

---

### 2. Module Decomposition (No New Libraries Needed)

The decomposition of `main.py` requires no new libraries. The existing stack handles everything:

| Existing Tool | Use in Decomposition |
|--------------|----------------------|
| `pydantic>=2.0` | Already used for models — move to `schemas.py` with no changes |
| `pytest>=7.0` + `pytest-asyncio>=0.21` | Already configured with `asyncio_mode = auto` — module tests just need the right imports |
| `unittest.mock.AsyncMock` | Already used in `test_providers.py` — use same pattern for new module tests |
| `ruff>=0.1` | Already configured — run after each extraction to catch import errors |

**Module extraction pattern (no new tooling):**

```python
# BEFORE (in main.py):
class OptimizeRequest(BaseModel):
    master_sku: str
    ...

# AFTER (in schemas.py):
class OptimizeRequest(BaseModel):
    master_sku: str
    ...

# In main.py, replace with:
from feedops.api.schemas import OptimizeRequest
```

Each extracted module gets its own test file targeting only that module's interface. The existing `asyncio_mode = auto` in `pyproject.toml` means async test functions work without additional decoration.

**No new testing libraries needed.** The existing `pytest + pytest-asyncio + unittest.mock.AsyncMock` pattern already used in `test_providers.py` is exactly correct for testing extracted modules with mocked dependencies.

---

### 3. Evaluation Harness (Lightweight Custom — No Framework)

**Recommendation: Custom pytest-based harness, NOT deepeval or similar frameworks.**

Rationale: This is a one-time 10-SKU head-to-head comparison, not a continuous evaluation pipeline. The existing test suite is already 100+ files using pytest. Adding deepeval introduces a heavyweight dependency (it uses its own LLM to grade outputs by default) that doesn't fit the workflow: human scoring by Bobby/Robert IS the evaluation.

**Pattern: `pytest-evals` plugin OR pure `pytest.mark.parametrize` with CSV export**

Use `pytest-evals` (minimalist pytest plugin) if you want structured `--save-evals-csv` output automatically. Use raw pytest if you prefer zero dependencies.

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `pytest-evals` | `>=0.2.0` | Saves eval results to CSV automatically | Use if you want structured output without custom file writing |
| Raw `pytest` + `csv` stdlib | — | Write results to CSV manually in test fixtures | Use if zero new dependencies is the priority |

**Recommended pattern (raw pytest, zero new deps):**

```python
# tests/eval/test_model_comparison.py
import csv, time, pytest
from feedops.providers.factory import get_provider

SKU_IDS = ["920D-6", "WP-2/16-GAL", ...]  # 10 diverse SKUs

@pytest.mark.parametrize("sku_id", SKU_IDS)
@pytest.mark.parametrize("model", ["gpt-5.2", "claude-sonnet-4-5"])
async def test_generate_content(sku_id, model, eval_results):
    provider = get_provider(preferred=model)
    t0 = time.perf_counter()
    result = await provider.generate(prompt, schema)
    latency = time.perf_counter() - t0
    eval_results.append({
        "sku_id": sku_id, "model": model,
        "latency_s": round(latency, 2),
        "title": result.get("title", ""),
        "description": result.get("description", ""),
    })
```

A session-scoped `conftest.py` fixture writes the accumulated `eval_results` to `eval_output.csv` at the end. Bobby/Robert score each row manually (1-10 per dimension) in a spreadsheet.

---

## Supporting Libraries Already Present

These are already in `pyproject.toml` and confirmed working. No changes needed:

| Library | Version (installed) | Role in this milestone |
|---------|---------------------|----------------------|
| `pydantic>=2.0` | 2.x | Schemas module — move models, no API changes |
| `pytest>=7.0` | 7.x | Test runner for all module tests |
| `pytest-asyncio>=0.21` | 0.21+ | Async test support (`asyncio_mode = auto` already set) |
| `ruff>=0.1` | current | Lint after each extraction |
| `mypy>=1.0` | current | Type-check provider interface conformance |
| `prometheus-client>=0.20` | current | Telemetry module — metrics already instrumented |

---

## Development Tools (Existing, No Changes)

| Tool | Purpose | Notes |
|------|---------|-------|
| `ruff` | Lint and import checking | Run after EVERY module extraction to catch circular imports |
| `mypy` | Type checking | Verify `AnthropicProvider` satisfies `LLMProvider` ABC |
| `uv` | Package management | `uv pip install "anthropic>=0.84.0"` |
| `pytest -x` | Fail-fast testing | Run after each module extraction before proceeding |

---

## Installation (New Dependency Only)

```bash
# In project root
uv pip install "anthropic>=0.84.0"

# Add to pyproject.toml [project.dependencies]
# "anthropic>=0.84.0",

# Verify
python -c "import anthropic; print(anthropic.__version__)"
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `anthropic>=0.84.0` (native SDK) | `instructor` library | Use instructor if you need Pydantic model validation on top of Claude responses. Not needed here — `output_config.json_schema` provides native schema validation. |
| Custom pytest eval harness | `deepeval` | Use deepeval if you need automated LLM-graded metrics at scale (RAG eval, hallucination detection). For a 10-SKU human-scored comparison, deepeval adds complexity with no benefit. |
| Custom pytest eval harness | `pytest-evals` | Use pytest-evals if you want automatic CSV export without writing the fixture yourself. Fine choice if zero boilerplate matters. |
| `claude-sonnet-4-5` for eval | `claude-opus-4-6` | Use Opus only if Sonnet quality is demonstrably insufficient. Opus is ~3-5x the cost and the quality delta for product copy generation is unlikely to justify it. |
| Module extraction (no new tools) | `import-linter` | Use import-linter to enforce module boundaries after extraction if the team wants CI enforcement of the new structure. Good for long-term maintainability, not required for this milestone. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `langchain` or `llama-index` | Heavyweight abstraction over provider calls. Adds 50+ transitive dependencies. The existing `LLMProvider` ABC is a better-fit abstraction for this codebase. | Native SDKs with the existing `LLMProvider` base class |
| `openai>=2.0` for Claude | Wrong SDK entirely | `anthropic>=0.84.0` |
| `BackgroundTasks` for job extraction | Cloud Run kills these on scale-to-zero — already proven. | Preserve `run_async_in_thread()` exactly as-is when extracting `job_management.py` |
| `asyncio.create_task()` for long jobs | Tasks are tied to the event loop lifecycle; same problem as `BackgroundTasks` | Preserve `run_async_in_thread()` |
| Batch prompt changes during decomposition | Phase 27 proved GPT-5.2 crashes on multi-change prompt deploys. | One prompt change → deploy → curl verify → next change |
| `deepeval` for evaluation | Requires its own OpenAI calls to score outputs; adds cost and latency to the evaluation run itself | Custom pytest harness with human scoring |

---

## Provider Abstraction Pattern (Reference)

The existing `LLMProvider` ABC in `src/feedops/providers/base.py` is the correct interface. `AnthropicProvider` must implement:

```python
class AnthropicProvider(LLMProvider):
    async def generate(self, prompt, schema, image=None, system_prompt=None,
                       reasoning_effort=None, max_completion_tokens=None) -> dict:
        ...

    async def health_check(self) -> bool:
        ...

    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"
```

`reasoning_effort` should be ignored (Claude doesn't expose this parameter directly). `max_completion_tokens` maps to `max_tokens`. `image` can be supported via Claude's vision capability if needed in a later milestone.

The `factory.py` `get_provider()` function needs a new branch for `preferred="anthropic"` reading from `ANTHROPIC_API_KEY` env var.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `anthropic>=0.84.0` | Python `>=3.9` | Project requires `>=3.11` — no conflict |
| `anthropic>=0.84.0` | `pydantic>=2.0` | No Pydantic dependency in anthropic SDK |
| `anthropic>=0.84.0` | `fastapi>=0.109` | No conflict — purely separate concerns |
| `anthropic>=0.84.0` | existing `openai>=1.0` | Both can coexist in same environment |

---

## Sources

- [anthropics/anthropic-sdk-python GitHub](https://github.com/anthropics/anthropic-sdk-python) — version 0.84.0 confirmed current (Feb 25, 2026)
- [Anthropic Structured Outputs Official Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — `output_config.format.json_schema` pattern verified HIGH confidence
- [FastAPI Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) — `asyncio_mode = auto` pattern
- [pytest-evals PyPI](https://pypi.org/project/pytest-evals/) — lightweight eval CSV plugin
- Codebase inspection: `src/feedops/providers/base.py`, `openai_provider.py`, `factory.py`, `test_providers.py` — existing patterns verified

---

*Stack research for: Pipeline Reliability Rewrite + Model Evaluation (Allied-FeedOps)*
*Researched: 2026-03-03*
