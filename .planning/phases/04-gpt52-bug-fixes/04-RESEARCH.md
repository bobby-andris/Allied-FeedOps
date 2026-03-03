# Phase 4: GPT-5.2 Bug Fixes - Research

**Researched:** 2026-03-03
**Domain:** OpenAI provider regression testing, Python integration script authoring
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **GPT-01** (temperature/reasoning conflict): Already fixed at `openai_provider.py:370-374` — write regression test only
- **GPT-02** (reasoning_effort default): Keep `"high"` as default (not `"medium"` per original spec). The 98% approval rate was achieved with `"high"`. Update the requirement spec to match.
- **GPT-03** (json_schema strict mode): Already fixed via `_build_strict_schema()` — write regression test only
- **GPT-04** (prompt_cache_retention): Already fixed with `extra_body={"prompt_cache_retention": "24h"}` on both API call paths — write regression test only
- **GPT-05** (XML tags in system prompt): Already fixed — SYSTEM_PROMPT uses XML tags (`<creative_direction>`, `<brand_voice>`, etc.), no `===` headers remain. Write regression test only.
- **Additional improvement**: Add `prompt_cache_key` parameter to API calls (OpenAI docs: "Use prompt_cache_key instead [of user field] to maintain caching optimizations"). Groups batch requests under same cache key. One-line addition per API call path.
- **Dedicated regression file**: `tests/test_gpt52_regression.py` — all 5 bug checks in one place
- **Three verification SKUs**: `920D-6` (canonical), random SKU (from DB at runtime), `AP-41/18` (hybrid/multi-SKU)
- **Verification checks**: Description length > 500 chars per platform (Google, Bing, Shopify)
- **PR strategy**: One PR for regression test file, one PR for `prompt_cache_key` addition, one PR for verification script

### Claude's Discretion

- Exact test assertions and mock setup within the regression file
- Verification script output format and error reporting
- Whether `prompt_cache_key` value is a static string or derived from batch_id/job context
- Random SKU selection strategy in verification script (query criteria)

### Deferred Ideas (OUT OF SCOPE)

- `output_verbosity` parameter — evaluate in Phase 6 (Model Evaluation) with controlled comparisons
- `prompt_cache_key` granularity optimization — evaluate after seeing cache hit rate data from basic implementation
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GPT-01 | Remove `temperature=0.7` when `reasoning_effort` is set (mutually exclusive) | Code already correct at lines 366-374; regression test pattern confirmed via `test_openai_provider_max_tokens.py` monkeypatch pattern |
| GPT-02 | Default `reasoning_effort` to `"high"` when env var is unset (locked to "high" per CONTEXT.md) | Code correct at line 334 (`os.environ.get("FEEDOPS_REASONING_EFFORT", "high")`); existing test in `test_prompt_sanitization_contract.py:116` asserts `"medium"` — that test must be updated |
| GPT-03 | Switch from `json_object` to `json_schema` strict mode | `_build_strict_schema()` confirmed present and correct (lines 112-154); returns `type: "json_schema"` with `strict: True` |
| GPT-04 | Add `prompt_cache_retention: "24h"` for batch runs | Already present at lines 407 and 419 in `extra_body`; regression test will verify both code paths |
| GPT-05 | Restructure system prompt with XML tags | SYSTEM_PROMPT at `prompts.py:271-332` confirmed uses XML tags (`<creative_direction>`, `<objective_hierarchy>`, `<brand_voice>`, `<accuracy_guardrail>`, `<output_contract>`); no `=== ===` patterns found |
| GPT-06 | Each bug fix is a separate PR with curl verification against live endpoint | Verification script architecture researched; existing `scripts/smoke_regenerate_lineage.py` provides reference pattern |
</phase_requirements>

## Summary

All five GPT-5.2 bugs are already fixed in code. Phase 4 work is 100% regression testing + one small code addition (`prompt_cache_key`) + a reusable verification script. The bugs were fixed during prior phases — what's missing is the test coverage that would catch regressions if someone edited those code paths again.

The key risk in this phase is NOT implementing new logic incorrectly — it's writing tests that are too fragile (break on unrelated changes) or too permissive (don't actually catch the bugs they claim to cover). Each test should directly inspect the call arguments passed to `AsyncOpenAI.chat.completions.create` via mock capture, not just verify side effects.

**Primary recommendation:** Write `tests/test_gpt52_regression.py` using the monkeypatch pattern from `test_openai_provider_max_tokens.py` — capture `kwargs` from `client.chat.completions.create` and assert directly on them. This is the tightest possible regression test.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=7.0 (from pyproject.toml) | Test framework | Project standard, already configured |
| pytest-asyncio | >=0.21 (from pyproject.toml) | Async test support | Required for `async def` tests; `asyncio_mode = "auto"` in pytest.ini |
| unittest.mock | stdlib | Mocking AsyncOpenAI client | Used in every existing provider test |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | installed | HTTP client for verification script | Live endpoint calls |
| argparse | stdlib | CLI arg parsing for verification script | `--pipeline-url`, `--master-sku` flags |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| monkeypatch (attr override) | `patch.object` | Both work; monkeypatch is used in `test_openai_provider_max_tokens.py`, `patch.object` in `test_providers.py` — use monkeypatch for consistency with existing provider tests |
| argparse | click | argparse is zero-dependency; already used in `smoke_regenerate_lineage.py` |

## Architecture Patterns

### Recommended Project Structure

```
tests/
└── test_gpt52_regression.py     # All 5 bug regression tests (new)

scripts/
└── verify_content_quality.py    # Multi-SKU verification script (new)
```

### Pattern 1: Monkeypatch + kwargs capture (PRIMARY TEST PATTERN)

**What:** Replace `client.chat.completions.create` with a fake that captures kwargs, then assert on captured values.
**When to use:** All 5 regression tests — it directly verifies what gets sent to OpenAI API.

**Example (from `test_openai_provider_max_tokens.py`):**
```python
async def test_openai_provider_sets_max_completion_tokens_for_gpt5(monkeypatch):
    from feedops.providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(api_key="test", model="gpt-5.2")

    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)

    result = await provider.generate(prompt="{}", schema={})
    assert "max_completion_tokens" in captured
    assert "max_tokens" not in captured
```

**Apply this pattern to each bug:**
- GPT-01: Assert `"temperature" not in captured` when `reasoning_effort` is set
- GPT-02: Assert `captured["reasoning_effort"] == "high"` when env var is unset
- GPT-03: Assert `captured["response_format"]["type"] == "json_schema"` and `captured["response_format"]["json_schema"]["strict"] is True`
- GPT-04: Assert `captured["extra_body"]["prompt_cache_retention"] == "24h"`
- GPT-05: Pure string inspection (no mock needed) — `assert "<creative_direction>" in SYSTEM_PROMPT`

### Pattern 2: Pure string inspection (GPT-05 test)

**What:** Import SYSTEM_PROMPT and assert on its content directly — no mock needed.
**When to use:** GPT-05 only (testing static string content, not runtime behavior).

```python
from feedops.pipeline.prompts import SYSTEM_PROMPT

def test_system_prompt_uses_xml_tags_not_equals_headers():
    assert "===" not in SYSTEM_PROMPT
    assert "<creative_direction>" in SYSTEM_PROMPT
    assert "<brand_voice>" in SYSTEM_PROMPT
    assert "<accuracy_guardrail>" in SYSTEM_PROMPT
    assert "<output_contract>" in SYSTEM_PROMPT
    assert "<objective_hierarchy>" in SYSTEM_PROMPT
```

### Pattern 3: Env var isolation for default reasoning_effort (GPT-02 test)

**What:** Use monkeypatch to unset env var, then verify captured kwargs.
**When to use:** GPT-02 — must test behavior with env var absent.

```python
@pytest.mark.asyncio
async def test_reasoning_effort_defaults_to_high_when_env_unset(monkeypatch):
    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(...)

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
    await provider.generate(prompt="{}", schema={})
    assert captured.get("reasoning_effort") == "high"
```

### Pattern 4: Dual-path coverage (GPT-04 test)

**What:** Test both the image path and the regular path to verify `prompt_cache_retention` is present on both.
**When to use:** GPT-04 — the code has two separate `client.chat.completions.create` calls (lines 403-411 for image, 415-423 for text).

```python
# Test regular path:
await provider.generate(prompt="{}", schema={})
assert captured["extra_body"]["prompt_cache_retention"] == "24h"

# Test image path: (pass an ImageInput)
await provider.generate(prompt="{}", schema={}, image=ImageInput(...))
assert image_captured["extra_body"]["prompt_cache_retention"] == "24h"
```

### Pattern 5: Verification script structure

**What:** Python script that POSTs to `/optimize-sku` for each test SKU, inspects response JSON.
**When to use:** Post-merge curl verification per GPT-06.

Reference: `scripts/smoke_regenerate_lineage.py` (uses urllib, argparse, prints structured output).

```
scripts/verify_content_quality.py
  --pipeline-url   (required, or reads FEEDOPS_PIPELINE_URL from env)
  --skus           (optional override; defaults to 920D-6, AP-41/18 + random)
  --platforms      (optional; defaults to google,bing,shopify)
  Output: PASS/FAIL per SKU per platform, description char count
```

### Anti-Patterns to Avoid

- **Testing mock setup instead of behavior:** Don't just assert `mock_create.called` — assert on the specific kwargs that matter for each bug.
- **Missing env var cleanup:** Always use `monkeypatch.delenv` in tests that depend on env var absence — don't rely on CI environment not having the var.
- **Testing both paths with one mock:** The image path and text path have separate `create` calls. Dual-path tests need separate captures.
- **Hardcoding pipeline URL in verification script:** Always read from env var or `--pipeline-url` arg, with clear error if missing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async mock for create() | Custom coroutine class | `async def _fake_create(**kwargs): ...` inline | Already established pattern in the codebase; simpler |
| HTTP timeout handling | Custom retry logic | `timeout=` kwarg in `requests.post()` | Verification script is single-shot, not production code |
| JSON response parsing | Custom parser | `response.json()` | Standard |

**Key insight:** The hardest part of Phase 4 is determining what NOT to test — don't test OpenAI SDK internals, don't test that Python passes kwargs correctly, test ONLY that `OpenAIProvider.generate()` constructs the right argument set.

## Common Pitfalls

### Pitfall 1: FEEDOPS_REASONING_EFFORT already set in test environment
**What goes wrong:** GPT-02 test passes env var check with wrong value, or the test passes only because CI doesn't have the var set.
**Why it happens:** Env leakage between test processes; developer's shell may have `FEEDOPS_REASONING_EFFORT=low` set.
**How to avoid:** Always use `monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)` before asserting on the default. Also add a companion test that sets the var to a specific value and verifies it's respected.
**Warning signs:** Test passes locally but fails in CI (or vice versa).

### Pitfall 2: Conflicting existing test for GPT-02 default
**What goes wrong:** `test_prompt_sanitization_contract.py:116` already asserts `reasoning_effort` default is `"medium"` — this is now wrong per the locked decision to keep `"high"`.
**Why it happens:** CONTEXT.md locked "high" as correct; the existing test was written before that decision.
**How to avoid:** The existing test at `test_prompt_sanitization_contract.py:116` tests `generate_per_platform`'s default (a different function), not `OpenAIProvider`'s env var behavior. Verify carefully: the `generate_per_platform` function default may genuinely be `"medium"` while `openai_provider.py` fallback is `"high"`. Confirm by reading `feedops/pipeline/generator.py`.
**Warning signs:** Two tests in the suite asserting different defaults — understand which function/layer each is testing.

### Pitfall 3: extra_body vs. first-class SDK parameter for prompt_cache_key
**What goes wrong:** Adding `prompt_cache_key` to `extra_body` dict when the installed SDK already has it as a first-class parameter.
**Why it happens:** OpenAI docs discuss `extra_body` as a fallback; some examples show it there.
**How to avoid:** CONFIRMED: the installed SDK (checked via introspection) exposes `prompt_cache_key` as a first-class `create()` parameter alongside `prompt_cache_retention`. Pass it directly as a keyword argument, NOT inside `extra_body`. Example: `client.chat.completions.create(..., prompt_cache_key="feedops-batch-v1")`.
**Warning signs:** Checking older docs or examples written before the SDK added the parameter.

### Pitfall 4: prompt_cache_key value strategy
**What goes wrong:** Using a per-SKU unique value as cache key defeats the purpose — cache key should be shared across requests with the same system prompt so they can share the cached prefix.
**Why it happens:** The name sounds like an identifier for a single request.
**How to avoid:** Use a static string like `"feedops-production"` or a version-stamped string. The point is that all batch requests share the same key → same cache bucket → higher hit rate. Per CONTEXT.md, exact value is Claude's discretion — recommend `"feedops-pipeline-v1"` as a static string for simplicity (evaluate granularity later).

### Pitfall 5: Verification script against wrong endpoint
**What goes wrong:** Script calls `/regenerate` instead of `/optimize-sku` for description length check.
**Why it happens:** `/regenerate` is the dashboard-facing endpoint; `/optimize-sku` is the batch-facing endpoint.
**How to avoid:** Phase 4 verifies the core generation path — use `/optimize-sku` (matches the Cloud Run endpoint that batch and single-SKU generation use). The success criterion says "`curl /optimize-sku` with SKU `920D-6`".

## Code Examples

### GPT-01: Temperature never coexists with reasoning_effort

```python
@pytest.mark.asyncio
async def test_temperature_not_passed_with_reasoning_effort(monkeypatch):
    """GPT-01: temperature and reasoning_effort are mutually exclusive."""
    from feedops.providers.openai_provider import OpenAIProvider
    import types

    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)

    await provider.generate(prompt="{}", schema={})

    # reasoning_effort is set (defaults to "high") — temperature must NOT be present
    assert "reasoning_effort" in captured
    assert "temperature" not in captured, (
        "temperature must not be passed alongside reasoning_effort on GPT-5.2"
    )
```

### GPT-02: reasoning_effort defaults to "high" when env var unset

```python
@pytest.mark.asyncio
async def test_reasoning_effort_defaults_to_high_when_env_unset(monkeypatch):
    """GPT-02: FEEDOPS_REASONING_EFFORT unset → defaults to 'high'."""
    from feedops.providers.openai_provider import OpenAIProvider
    import types

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
    await provider.generate(prompt="{}", schema={})

    assert captured.get("reasoning_effort") == "high", (
        f"Expected 'high' default but got: {captured.get('reasoning_effort')}"
    )
```

### GPT-03: json_schema strict mode active

```python
@pytest.mark.asyncio
async def test_response_format_uses_json_schema_strict_mode(monkeypatch):
    """GPT-03: response_format uses json_schema type with strict=True, not json_object."""
    from feedops.providers.openai_provider import OpenAIProvider
    import types

    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"a": 1}'))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
    await provider.generate(prompt="{}", schema={"type": "object", "properties": {"a": {"type": "integer"}}})

    fmt = captured.get("response_format", {})
    assert fmt.get("type") == "json_schema", f"Expected 'json_schema', got: {fmt.get('type')}"
    assert fmt["json_schema"]["strict"] is True
```

### GPT-04: prompt_cache_retention on both paths

```python
@pytest.mark.asyncio
async def test_prompt_cache_retention_set_on_text_path(monkeypatch):
    """GPT-04: prompt_cache_retention: '24h' is in extra_body for text generation."""
    from feedops.providers.openai_provider import OpenAIProvider
    import types

    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)
    await provider.generate(prompt="{}", schema={})

    assert captured.get("extra_body", {}).get("prompt_cache_retention") == "24h"
```

### GPT-05: SYSTEM_PROMPT uses XML tags

```python
def test_system_prompt_uses_xml_not_equals_headers():
    """GPT-05: SYSTEM_PROMPT uses XML section tags, not === headers."""
    from feedops.pipeline.prompts import SYSTEM_PROMPT

    assert "===" not in SYSTEM_PROMPT, "Found === header in SYSTEM_PROMPT — must use XML tags"
    for tag in ("<creative_direction>", "<objective_hierarchy>", "<brand_voice>",
                "<accuracy_guardrail>", "<output_contract>"):
        assert tag in SYSTEM_PROMPT, f"Missing XML tag: {tag}"
```

### prompt_cache_key addition (the one actual code change)

```python
# In openai_provider.py — add prompt_cache_key as first-class kwarg (not inside extra_body)
# Text path (around line 415-423):
response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    response_format=response_format,
    extra_body={"prompt_cache_retention": "24h"},
    prompt_cache_key="feedops-pipeline-v1",   # <-- add this
    **token_params,
    **sampling_params,
    **reasoning_params,
)

# Image path (around line 403-411): same addition
response = await self.client.chat.completions.create(
    model=self.model,
    messages=image_messages,
    response_format=response_format,
    extra_body={"prompt_cache_retention": "24h"},
    prompt_cache_key="feedops-pipeline-v1",   # <-- add this
    **token_params,
    **sampling_params,
    **reasoning_params,
)
```

### Verification script skeleton

```python
#!/usr/bin/env python3
"""Post-deploy content quality verification script.

Calls /optimize-sku for each test SKU and verifies description length > 500 chars
per platform. Reusable for Phase 5 (Claude provider) and Phase 7 (Bing fix).

Usage:
    python scripts/verify_content_quality.py \
        --pipeline-url https://feedops-pipeline-xxx.run.app \
        --master-sku 920D-6
"""
import argparse, json, os, sys
from urllib import request, error

PASS = "PASS"
FAIL = "FAIL"
MIN_DESC_LEN = 500

def _check_sku(pipeline_url: str, master_sku: str) -> dict:
    """POST /optimize-sku and check description lengths per platform."""
    ...

def main():
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--pipeline-url", default=os.environ.get("FEEDOPS_PIPELINE_URL"))
    parser.add_argument("--master-sku", action="append", dest="skus")
    args = parser.parse_args()

    if not args.pipeline_url:
        sys.exit("ERROR: --pipeline-url or FEEDOPS_PIPELINE_URL required")
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `temperature=0.7` always passed | Temperature omitted when `reasoning_effort` set | Prior phase | No more OpenAI API error on GPT-5.2 |
| `json_object` mode | `json_schema` with `strict: True` | Prior phase | Zero retry loops from schema violations |
| No prompt cache | `prompt_cache_retention: "24h"` in `extra_body` | Prior phase | Longer cache windows during batch runs |
| `=== section ===` headers | XML tags in SYSTEM_PROMPT | Prior phase | Better GPT-5.2 prompt parsing |
| No `prompt_cache_key` | First-class `prompt_cache_key` kwarg | Phase 4 (pending) | Better cache bucketing for batch runs |

**Note on `prompt_cache_key`:** The installed OpenAI Python SDK exposes `prompt_cache_key` as a first-class parameter to `chat.completions.create()` — confirmed via SDK introspection. It is NOT an `extra_body` field. It can coexist with `extra_body={"prompt_cache_retention": "24h"}`.

## Open Questions

1. **Does `generate_per_platform` in `pipeline/generator.py` have a different `reasoning_effort` default than `openai_provider.py`?**
   - What we know: `test_prompt_sanitization_contract.py:116` asserts `generate_per_platform`'s default is `"medium"`. The `openai_provider.py` env var fallback is `"high"`. These are two different layers.
   - What's unclear: Whether the CONTEXT.md "keep high as default" applies to the provider layer, the generator layer, or both.
   - Recommendation: During plan creation, verify which function the CONTEXT.md decision targets. The locked decision says "Keep `"high"` as default" for GPT-02 (the provider-level env var fallback). The `generate_per_platform` default of `"medium"` is a separate parameter at the generator layer and is likely intentional (caller-level control). Do NOT change `generate_per_platform`'s default.

2. **Should the verification script query Supabase for a random SKU, or use a hardcoded list?**
   - What we know: CONTEXT.md says "a random SKU — selected at runtime from the database to catch edge cases." Supabase credentials are available via `.env.vercel`.
   - What's unclear: The verification script's environment — does it run with Supabase access, or just pipeline API access?
   - Recommendation: Support both modes — if Supabase credentials available, query for random SKU; if not, use a second hardcoded SKU (e.g., `FT-16` or `920D-6-FALLBACK`). This makes the script robust as a standalone tool.

## Sources

### Primary (HIGH confidence)

- **Codebase inspection** — `src/feedops/providers/openai_provider.py` lines 112-154, 332-337, 366-374, 403-423. All five bugs confirmed fixed.
- **SDK introspection** — `OPENAI_API_KEY=dummy python -c "import inspect, openai; ..."` — confirmed `prompt_cache_key` is a first-class parameter in the installed SDK version.
- **Existing test patterns** — `tests/test_openai_provider_max_tokens.py` and `tests/test_providers.py` — confirmed monkeypatch + kwargs capture is the established pattern.
- **pyproject.toml** — confirmed `pytest>=7.0`, `pytest-asyncio>=0.21`, `asyncio_mode = "auto"`.

### Secondary (MEDIUM confidence)

- **`test_prompt_sanitization_contract.py:116`** — existing assertion that `generate_per_platform` defaults to `"medium"` reasoning_effort. This is a different layer than the `openai_provider.py` env var fallback, but needs validation during planning to avoid test conflicts.
- **CONTEXT.md integration points** — line numbers (333-337, 370-374, 407, 419) provided by user; verified against actual code during research.

### Tertiary (LOW confidence)

- **OpenAI docs on `prompt_cache_key`** — cited in CONTEXT.md as "Use prompt_cache_key instead [of user field] to maintain caching optimizations." Not independently verified via docs fetch, but SDK introspection confirms the parameter exists. HIGH confidence on existence, MEDIUM on semantics.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uses existing project test stack with no new dependencies
- Architecture: HIGH — patterns directly lifted from existing provider tests in the codebase
- Pitfalls: HIGH — GPT-02/reasoning_effort layer conflict is a verified real risk from reading both `openai_provider.py` and `test_prompt_sanitization_contract.py`
- prompt_cache_key API: HIGH (SDK confirmed) / MEDIUM (semantics from docs not independently verified)

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable; OpenAI SDK parameter set unlikely to change rapidly)
