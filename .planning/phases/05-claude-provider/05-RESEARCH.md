# Phase 5: Claude Provider - Research

**Researched:** 2026-03-03
**Domain:** Anthropic Python SDK — structured outputs, prompt caching, extended thinking, provider abstraction
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Model**: Claude Sonnet 4.6 (`claude-sonnet-4-6`) by default; configurable via `FEEDOPS_CLAUDE_MODEL`
- **Prompt compatibility**: Same prompt verbatim as GPT-5.2 — no Claude-specific optimization in Phase 5
- **No fallback chains**: Claude is standalone; `FallbackProvider` stays OpenAI/Gemini only
- **API key**: `ANTHROPIC_API_KEY` (standard SDK convention); GCP secret `feedops-anthropic-api-key` already created and bound
- **Extended thinking**: Research findings should inform the decision — may or may not be needed
- **Metrics parity**: `last_usage`, `last_parse_details`, `last_retry_counts` must be exposed identically to `OpenAIProvider`
- **Full image support**: `ImageInput` from day one — Claude supports vision natively
- **Retry-on-bad-JSON**: Mirror OpenAI provider's repair loop

### Claude's Discretion
- Structured output mechanism selection (tool_use vs JSON mode vs constrained output)
- Extended thinking token budgets (pending research findings)
- Prompt caching implementation (cache_control breakpoints for batch cost savings)
- SDK version pinning strategy for `anthropic` package
- Factory integration pattern (extend existing `get_provider()`)
- Retry logic configuration (retry counts, backoff strategy)
- Circuit breaker integration (existing `reliability.py` patterns)
- Schema validation test depth for PROV-05

### Deferred Ideas (OUT OF SCOPE)
- Claude-optimized prompt variant — evaluate after Phase 6 baseline comparison
- Claude fallback chains — evaluate after Phase 6 proves provider strengths
- Extended thinking fine-tuning for content quality — evaluate in Phase 6
- `output_verbosity` parameter exploration
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROV-01 | Provider abstraction layer (`providers/base.py`) with common `generate()` interface | Already exists — `LLMProvider` ABC is complete; no changes needed |
| PROV-02 | OpenAI/GPT-5.2 provider refactored to use abstraction | Already done in Phases 1-4; `OpenAIProvider` implements `LLMProvider` correctly |
| PROV-03 | Anthropic/Claude provider implementation with structured JSON output | Core deliverable — use `output_config.format` with `json_schema` type (GA, no beta header needed) |
| PROV-04 | Provider factory supports selection via environment variable | Extend `get_provider()` in `factory.py` with `FEEDOPS_PROVIDER=claude` branch |
| PROV-05 | Claude provider tested against all 3 content platforms (Google, Bing, Shopify) | New test file `tests/test_claude_provider.py` with mocked `AsyncAnthropic` client |
</phase_requirements>

---

## Summary

Phase 5 is straightforward: implement `ClaudeProvider` as a drop-in `LLMProvider` implementation, then extend `get_provider()` to recognize `FEEDOPS_PROVIDER=claude`. The Anthropic Python SDK (v0.84.x) provides native structured output support via `output_config.format` with `json_schema` type, which is now generally available for `claude-sonnet-4-6` — no beta headers required. The SDK is async-capable via `AsyncAnthropic`, mirroring how `AsyncOpenAI` is used.

The key design question from CONTEXT.md — "which structured output mechanism?" — is resolved: use `output_config.format` with `json_schema`. This is equivalent to OpenAI's `response_format: json_schema` (strict mode), gives constrained decoding guarantees, and means the retry-on-bad-JSON loop is a safety net rather than a primary mechanism. Prompt caching for the static system prompt uses `cache_control={"type": "ephemeral"}` at the request level (automatic mode) — simpler than explicit breakpoints and sufficient for single-request batches.

Extended thinking on `claude-sonnet-4-6` is supported with `thinking={"type": "enabled", "budget_tokens": N}`, but the research finding is: **do not enable it by default in Phase 5**. The CONTEXT.md decision deferred extended thinking evaluation to Phase 6. Phase 5 should map `reasoning_effort` to a disabled thinking block or simply omit it, accepting the interface parameter without acting on it. This keeps Phase 5 clean and Phase 6 comparison uncontaminated.

**Primary recommendation:** Use `output_config.format` (GA, no beta header), `AsyncAnthropic`, automatic prompt caching via `cache_control`, and defer extended thinking activation to Phase 6. Extract text from `response.content[0].text`, parse with the shared `_parse_json_payload()` from `openai_provider.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.84.0` | Anthropic SDK with structured outputs GA | Required for `output_config.format` (not beta) and `AsyncAnthropic` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio` | stdlib | Retry sleep, backoff | Same as OpenAI/Gemini providers |
| `base64` | stdlib | Image encoding for vision | Same as OpenAI provider multimodal path |
| `json` | stdlib | JSON parse fallback if structured output fails | Safety net in retry loop |
| `logging` | stdlib | `log_event()` + structured logging | All providers use this |
| `time` | stdlib | Latency measurement, circuit breaker | All providers use this |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `output_config.format` (native structured output) | Tool-use forced JSON extraction | Tool-use requires schema wrapping in tool definition; more complex; structured output is cleaner and now GA |
| `output_config.format` (native structured output) | Prompt-only JSON instruction + parse | Zero schema guarantees; relies on retry loop exclusively; already proven problematic in Phase 27 with GPT-5.2 |
| `AsyncAnthropic` | `Anthropic` + `asyncio.run_in_executor` | Sync-in-executor is an anti-pattern; AsyncAnthropic is the native async path |

**Installation:**
```bash
# Add to pyproject.toml dependencies
anthropic>=0.84.0
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/feedops/providers/
├── base.py              # LLMProvider ABC (no changes needed)
├── factory.py           # get_provider() — add claude branch
├── openai_provider.py   # Reference implementation (no changes)
├── gemini_provider.py   # Second reference (no changes)
├── reliability.py       # Shared circuit breakers (no changes)
└── claude_provider.py   # NEW: ClaudeProvider implementation
tests/
└── test_claude_provider.py  # NEW: mocked Anthropic client tests
```

### Pattern 1: output_config.format for Structured JSON (GA)
**What:** Pass schema directly to the Anthropic API via `output_config.format` — constrained decoding guarantees valid JSON.
**When to use:** All calls in `ClaudeProvider.generate()`.
**Example:**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
response = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    system="You are a product content expert...",
    messages=[{"role": "user", "content": prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": schema,  # same dict passed to generate()
        }
    },
    cache_control={"type": "ephemeral"},  # automatic prompt caching
)
content = response.content[0].text  # always valid JSON per schema
```

**Important notes:**
- `response.content` is a list; text is at `response.content[0].text` (NOT `response.choices[0].message.content` like OpenAI)
- `output_config` is a dict (not a separate class in Python SDK)
- No beta header required — GA for `claude-sonnet-4-6`

### Pattern 2: AsyncAnthropic Client Lifecycle
**What:** Create `AsyncAnthropic` at `__init__` time, close in `aclose()`.
**When to use:** All async providers follow this pattern.
```python
# Source: Anthropic SDK docs + OpenAI provider pattern
from anthropic import AsyncAnthropic

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", ...):
        self.client = AsyncAnthropic(api_key=api_key)
        ...

    async def aclose(self) -> None:
        await self.client.close()
```

### Pattern 3: Prompt Caching (Automatic Mode)
**What:** Add `cache_control={"type": "ephemeral"}` at the request level. System automatically caches the static prefix (system prompt).
**When to use:** All `generate()` calls when `system_prompt` is provided.
**Cost:** Cache write = 1.25x input token cost; cache hits = 0.10x. For our 18K-token system prompt on Sonnet 4.6 ($3/MTok base), cache writes = $0.067/call, hits = $0.0054/call. Break-even at 2 calls per session window.
**Cache lifetime:** 5 minutes by default (refreshed on every hit). For batch runs, the 5-min window is ample.
```python
# Source: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching
response = await client.messages.create(
    model=self.model,
    max_tokens=max_tokens,
    system=system_prompt,  # static; gets cached
    messages=[{"role": "user", "content": prompt}],
    output_config={"format": {"type": "json_schema", "schema": schema}},
    cache_control={"type": "ephemeral"},  # auto-cache the system prefix
)
```

### Pattern 4: Usage Extraction (Different Field Names than OpenAI)
**What:** Anthropic usage fields differ from OpenAI — `input_tokens`/`output_tokens` vs `prompt_tokens`/`completion_tokens`.
**When to use:** `_extract_usage()` must map to the standard `{"prompt_tokens", "completion_tokens", "cached_tokens"}` dict.
```python
# Source: Anthropic SDK response structure
usage = response.usage
# Fields: input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens
cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
prompt_tokens = getattr(usage, "input_tokens", 0) or 0
completion_tokens = getattr(usage, "output_tokens", 0) or 0
# Return standard dict matching OpenAIProvider.last_usage structure
{"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cached_tokens": cached_tokens}
```

### Pattern 5: Image Encoding for Vision
**What:** Claude accepts base64 images as content blocks with `type: "image"`.
**When to use:** When `image: ImageInput` is passed to `generate()`.
```python
# Source: Anthropic vision docs
import base64
encoded = base64.b64encode(image.data).decode("utf-8")
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.mime_type,
                    "data": encoded,
                },
            },
        ],
    }
]
```
Note: Anthropic image format differs from OpenAI (`"source"` dict vs `"image_url"` dict). The media_type field replaces OpenAI's `data:mime/type;base64,` prefix.

### Pattern 6: Factory Extension
**What:** Add `FEEDOPS_PROVIDER=claude` handling to `get_provider()` in `factory.py`.
**When to use:** When environment variable is set.
```python
# In factory.py get_provider():
claude_key = os.environ.get("ANTHROPIC_API_KEY")
claude_model = os.environ.get("FEEDOPS_CLAUDE_MODEL", "claude-sonnet-4-6")

preferred_env = os.environ.get("FEEDOPS_PROVIDER")  # new env var
effective_preferred = preferred or preferred_env

if effective_preferred == "claude" and claude_key:
    return _build_claude_provider(api_key=claude_key, model=claude_model)
# ... existing openai/gemini logic unchanged
```

### Anti-Patterns to Avoid
- **Response access via `.choices[0].message.content`**: Anthropic uses `response.content[0].text` — conflating the two will raise `AttributeError`.
- **Passing `temperature` with extended thinking**: When `thinking` is enabled, `temperature` must be `1.0` or omitted. Since we're NOT enabling thinking by default, this is moot — but document for Phase 6.
- **Beta headers in production**: `structured-outputs-2025-11-13` header is no longer required for `output_config.format`. Using the old `output_format` parameter in beta still works for a transition period but points to the deprecated path.
- **Expecting `.parse()` return type**: `client.messages.parse()` returns a typed Pydantic wrapper. We want `client.messages.create()` with `output_config` — raw dict, no Pydantic required.
- **Using `tool_use` forced JSON**: More complex than `output_config.format`, requires wrapping schema inside a tool definition, and adds model overhead for calling a fake tool.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON output | Custom prompt like "respond in JSON only" | `output_config.format` with `json_schema` | Constrained decoding eliminates parse failures; retry loop becomes a pure safety net |
| Prompt caching | Manual cache key management | `cache_control={"type": "ephemeral"}` automatic mode | SDK handles breakpoint placement; no state to maintain per-call |
| JSON parse fallback | New parse utility | Re-use `_parse_json_payload()` from `openai_provider.py` | Already handles fence recovery, substring fallback, key validation |
| Backoff logic | New sleep/retry loop | Re-use `compute_backoff_seconds()` from `reliability.py` | Already tested, consistent across providers |
| Circuit breaker | New failure state | Re-use `circuit_breakers` from `reliability.py` | Keyed by `provider.name` — works for any string key |
| Retryable error detection | New string matching | Re-use `is_retryable_provider_error()` from `reliability.py` | Covers 429, rate limit, timeout, connection reset |
| Metrics emission | New metrics calls | Re-use `metrics_registry` and `log_event()` patterns from `openai_provider.py` | Identical telemetry surface required for Phase 6 comparison |

**Key insight:** The entire reliability, caching, and metrics infrastructure from `openai_provider.py` is directly reusable. `ClaudeProvider` is primarily a translation layer between the `LLMProvider` interface and the Anthropic SDK's different method signatures and response shapes.

---

## Common Pitfalls

### Pitfall 1: Response Content Path
**What goes wrong:** `response.content[0].text` not `response.choices[0].message.content` — `AttributeError: 'Message' object has no attribute 'choices'`.
**Why it happens:** OpenAI's chat completions model; Anthropic's messages model have completely different response shapes.
**How to avoid:** Always use `response.content[0].text` for Anthropic. Extract to `_extract_claude_text(response)` helper.
**Warning signs:** `AttributeError` on `choices` in production logs.

### Pitfall 2: Schema Compatibility with output_config
**What goes wrong:** Schemas with features unsupported by Anthropic's JSON schema subset (e.g., `anyOf`, `oneOf`, `$ref`, recursive schemas) cause API errors.
**Why it happens:** Anthropic's constrained decoding supports a subset of JSON Schema. The feedops schemas are flat objects with string fields — likely fine — but verify.
**How to avoid:** Test with actual schemas from `prompt_builder.py`. If issues arise, strip unsupported keywords (`anyOf`, `$ref`) from schema before passing to `output_config`.
**Warning signs:** 400 error from Anthropic API mentioning schema validation.

### Pitfall 3: Extended Thinking Response Shape
**What goes wrong:** If extended thinking is ever enabled, `response.content` becomes a list of `[thinking_block, text_block]` — extracting `[0].text` returns the thinking block, not the JSON.
**Why it happens:** Thinking blocks appear before text blocks in the content array.
**How to avoid:** If thinking is ever activated (Phase 6+), filter for `block.type == "text"` before extracting `.text`. In Phase 5, thinking is disabled — this is a Phase 6 risk to document.
**Warning signs:** Parsed JSON contains thinking content (long, reasoning-style text) instead of product fields.

### Pitfall 4: Usage Field Names
**What goes wrong:** `response.usage.prompt_tokens` raises `AttributeError` — Anthropic uses `input_tokens`.
**Why it happens:** Different naming convention from OpenAI SDK.
**How to avoid:** Use `getattr(usage, "input_tokens", 0)` and map to standard dict keys in `_extract_claude_usage()`.
**Warning signs:** `last_usage` always returns zeros in telemetry.

### Pitfall 5: `cache_creation_input_tokens` vs `cached_tokens`
**What goes wrong:** Logging "0 cached tokens" on every call even when caching is working.
**Why it happens:** Cache hits report in `cache_read_input_tokens`, not `cached_tokens` (OpenAI field name). Cache writes report in `cache_creation_input_tokens`.
**How to avoid:** Map `cache_read_input_tokens` → `cached_tokens` in usage extraction.
**Warning signs:** Cache hit rate logged as 0% even after repeated calls.

### Pitfall 6: Missing asyncio_mode in Test
**What goes wrong:** `pytest.mark.asyncio` tests hang or error without proper config.
**Why it happens:** `pytest-asyncio` version compatibility.
**How to avoid:** `pyproject.toml` already has `asyncio_mode = "auto"` — async tests work automatically. No decorator needed.
**Warning signs:** `SyntaxWarning: coroutine was never awaited`.

---

## Code Examples

Verified patterns from official sources:

### Minimal ClaudeProvider.generate() Skeleton
```python
# Source: Anthropic structured outputs docs + openai_provider.py patterns
import asyncio
import base64
import json
import logging
import time
from typing import Any

from anthropic import AsyncAnthropic

from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.providers.base import ImageInput, LLMError, LLMProvider
from feedops.providers.reliability import (
    circuit_breakers,
    compute_backoff_seconds,
    is_retryable_provider_error,
)
# Import shared parse utility from openai_provider
from feedops.providers.openai_provider import _parse_json_payload

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 3,
        *,
        sdk_timeout_seconds: float | None = None,
        max_total_seconds: float | None = None,
        json_retry_max: int | None = None,
    ):
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if sdk_timeout_seconds is not None:
            client_kwargs["timeout"] = max(sdk_timeout_seconds, 1.0)
        self.client = AsyncAnthropic(**client_kwargs)
        self.model = model
        self.max_retries = max(1, max_retries)
        self.max_total_seconds = max_total_seconds if max_total_seconds is not None else 300.0
        self.json_retry_max = max(0, int(json_retry_max)) if json_retry_max is not None else 1
        self._last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
        self._last_parse_details: dict[str, Any] = {
            "parse_mode": "none", "parsed_key_count": 0,
            "expected_key_count": 0, "missing_keys": [],
        }
        self._last_retry_counts: dict[str, int] = {
            "attempt_count": 0, "json_decode_retries": 0,
            "api_retries": 0, "budget_retries": 0,
        }

    @property
    def name(self) -> str:
        return f"claude/{self.model}"

    async def aclose(self) -> None:
        await self.client.close()

    async def generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,  # Accepted but not used in Phase 5
        max_completion_tokens: int | None = None,
    ) -> dict[str, Any]:
        circuit_ok, cooldown_remaining = circuit_breakers.allow_request(self.name)
        if not circuit_ok:
            raise LLMError(
                f"Circuit breaker open ({cooldown_remaining:.2f}s remaining)", self.name, 0
            )

        start_time = time.perf_counter()
        max_tokens = max_completion_tokens or 8000

        # Build messages
        if image:
            encoded = base64.b64encode(image.data).decode("utf-8")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": image.mime_type,
                        "data": encoded,
                    }},
                ],
            }]
        else:
            messages = [{"role": "user", "content": prompt}]

        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
            "cache_control": {"type": "ephemeral"},
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        last_error = None
        content = ""
        self._last_retry_counts = {
            "attempt_count": 0, "json_decode_retries": 0,
            "api_retries": 0, "budget_retries": 0,
        }

        for attempt in range(self.max_retries):
            self._last_retry_counts["attempt_count"] = attempt + 1
            if (time.perf_counter() - start_time) >= self.max_total_seconds:
                last_error = f"provider_max_total_seconds_exceeded: {self.max_total_seconds:.2f}s"
                break
            parse_details: dict[str, Any] = {}
            try:
                response = await self.client.messages.create(**create_kwargs)
                self._last_usage = _extract_claude_usage(response)
                content = response.content[0].text  # Anthropic path
                expected_keys = set(schema.get("properties", {}).keys())
                result = _parse_json_payload(
                    content, expected_keys=expected_keys, parse_details=parse_details
                )
                self._last_parse_details = parse_details
                circuit_breakers.record_success(self.name)
                metrics_registry.observe(
                    "provider_latency_seconds",
                    time.perf_counter() - start_time,
                    provider=self.name,
                )
                return result

            except json.JSONDecodeError as e:
                # ... retry logic mirroring openai_provider.py
                ...

            except Exception as e:
                # ... retryable API error handling
                ...

        circuit_breakers.record_failure(self.name)
        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)
```

### Usage Extraction Helper
```python
# Source: Anthropic SDK response shape observation
def _extract_claude_usage(response: Any) -> dict[str, int]:
    """Normalize Anthropic usage fields to standard provider dict.

    Anthropic field names differ from OpenAI:
      input_tokens -> prompt_tokens
      output_tokens -> completion_tokens
      cache_read_input_tokens -> cached_tokens
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cached_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }
```

### Factory Extension Pattern
```python
# Source: factory.py existing pattern, extended
def _build_claude_provider(*, api_key: str, model: str) -> "ClaudeProvider":
    from feedops.providers.claude_provider import ClaudeProvider
    return ClaudeProvider(
        api_key=api_key,
        model=model,
        max_retries=_int_env("FEEDOPS_PROVIDER_MAX_RETRIES", 1),
        sdk_timeout_seconds=_float_env("FEEDOPS_CLAUDE_SDK_TIMEOUT_SECONDS", 60.0),
        max_total_seconds=_float_env("FEEDOPS_PROVIDER_MAX_TOTAL_SECONDS", 120.0),
        json_retry_max=_int_env("FEEDOPS_CLAUDE_JSON_RETRY_MAX", 1),
    )

# In get_provider(), add before existing openai check:
preferred_env = os.environ.get("FEEDOPS_PROVIDER")
effective_preferred = preferred or preferred_env
claude_key = os.environ.get("ANTHROPIC_API_KEY")
claude_model = os.environ.get("FEEDOPS_CLAUDE_MODEL", "claude-sonnet-4-6")

if effective_preferred == "claude" and claude_key:
    logger.info("Using Claude provider (FEEDOPS_PROVIDER=claude)")
    return _build_claude_provider(api_key=claude_key, model=claude_model)
```

### Test Mock Pattern (mirrors test_providers.py style)
```python
# Source: tests/test_providers.py existing mock pattern
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from feedops.providers.claude_provider import ClaudeProvider

@pytest.mark.asyncio
async def test_claude_provider_generate_returns_json():
    provider = ClaudeProvider(api_key="test-key")

    # Anthropic response shape: response.content[0].text (not .choices[0].message.content)
    mock_content_block = MagicMock()
    mock_content_block.text = '{"google_title": "Test", "google_description": "Desc"}'
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.usage.cache_read_input_tokens = 0

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await provider.generate(
            "Test prompt",
            {"type": "object", "properties": {"google_title": {}, "google_description": {}}}
        )
        assert result["google_title"] == "Test"

        # Verify output_config.format was passed
        _, kwargs = mock_create.call_args
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `betas=["structured-outputs-2025-11-13"]` with `output_format` | `output_config.format` (no beta header) | GA Nov 2025, migrated early 2026 | Old header still works for transition period; new `output_config` is canonical |
| Manual `tool_use` extraction for JSON | `output_config.format` with `json_schema` | Nov 2025 | Native constrained decoding; no tool overhead |
| Explicit `cache_control` on individual content blocks | `cache_control={"type": "ephemeral"}` at request level (auto) | 2026 | Simpler; system moves breakpoint as conversation grows |
| `budget_tokens` manual thinking on Opus 4.6 | `type: "adaptive"` for Opus | Feb 2026 | Manual mode deprecated on Opus 4.6; still valid on Sonnet 4.6 |

**Deprecated/outdated:**
- Beta header `anthropic-beta: structured-outputs-2025-11-13`: Still works for transition; new code should omit it
- `output_format` parameter (old beta shape): `output_config.format` is the canonical form
- `type: "enabled"` thinking on `claude-opus-4-6`: Deprecated; use `type: "adaptive"` on Opus 4.6

---

## Open Questions

1. **`_parse_json_payload()` importability**
   - What we know: `_parse_json_payload` is a module-level function in `openai_provider.py` (not private by convention, just prefixed with `_`)
   - What's unclear: Should it be moved to a shared `providers/utils.py` to avoid cross-provider import coupling, or is direct import from `openai_provider` acceptable?
   - Recommendation: Import directly from `openai_provider` for Phase 5 (low risk, no circular imports). Consider `providers/utils.py` extraction as a Phase 6 cleanup if desired.

2. **Schema compatibility with Anthropic's JSON Schema subset**
   - What we know: Anthropic supports most JSON Schema Draft 2020-12; docs list `anyOf`, `oneOf`, `$ref` as unsupported. Feedops schemas are flat `{"type": "object", "properties": {...}}` structures — likely fully compatible.
   - What's unclear: Exact schema from `prompt_builder.py` not examined in this research
   - Recommendation: Test with the actual schema on the first manual verification call; `400` from Anthropic signals schema incompatibility.

3. **reasoning_effort mapping for Phase 6**
   - What we know: In Phase 5, `reasoning_effort` is accepted but not acted on. Sonnet 4.6 supports `thinking={"type": "enabled", "budget_tokens": N}` for extended thinking.
   - What's unclear: The mapping between `reasoning_effort` levels ("low"/"medium"/"high") and `budget_tokens` values
   - Recommendation: Phase 5 plan should document the mapping proposal for Phase 6: `low=2000`, `medium=8000`, `high=20000` — but do NOT implement. Log a warning if `reasoning_effort` is passed to `ClaudeProvider` (signals misconfiguration in Phase 5).

---

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/build-with-claude/structured-outputs` — `output_config.format` API shape, GA status, supported models including claude-sonnet-4-6
- `platform.claude.com/docs/en/build-with-claude/extended-thinking` — Thinking parameter syntax for Sonnet 4.6, budget_tokens, content block shapes
- `platform.claude.com/docs/en/docs/build-with-claude/prompt-caching` — `cache_control` automatic mode, pricing table for Sonnet 4.6, usage field names
- `src/feedops/providers/openai_provider.py` — Reference implementation for retry loop, metrics, `_parse_json_payload()`, circuit breaker integration
- `src/feedops/providers/base.py` — `LLMProvider` ABC interface, `ImageInput` dataclass
- `src/feedops/providers/factory.py` — `get_provider()` extension point, `_build_openai_provider()` builder pattern
- `src/feedops/providers/reliability.py` — `circuit_breakers`, `compute_backoff_seconds()`, `is_retryable_provider_error()`
- `tests/test_providers.py` — Existing mock patterns for async provider tests

### Secondary (MEDIUM confidence)
- PyPI search results: `anthropic>=0.84.0` is latest version (Feb 2026)
- WebSearch: Claude Sonnet 4.6 released Feb 17, 2026; supports structured outputs GA, prompt caching, extended thinking

### Tertiary (LOW confidence)
- None — all key claims verified against official Anthropic docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Anthropic SDK version and structured output API verified against official docs
- Architecture patterns: HIGH — Response shapes, caching, usage fields all verified in official docs; code patterns derived from existing `openai_provider.py` reference
- Pitfalls: HIGH — Response shape, usage field names verified; extended thinking content array structure verified
- Extended thinking: MEDIUM — Confirmed it works with Sonnet 4.6; Phase 5 does NOT enable it (so this is Phase 6 risk documentation only)

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (30 days — Anthropic SDK is fast-moving but structured outputs are now GA)
