# Phase 10: Image Wiring - Research

**Researched:** 2026-03-04
**Domain:** Python pipeline — multimodal image forwarding through `executor.py`
**Confidence:** HIGH

## Summary

The image wiring capability is already deeply implemented in the codebase — just not yet
wired into the modern `execute_generation_bundle` / `execute_generation_legacy_payload`
code path. All three required pieces already exist: `ImageInput` dataclass in `base.py`,
`fetch_image()` in `pipeline/images.py`, and `ClaudeProvider.generate(image=...)` in
`claude_provider.py`. The gap is exclusively in `generation/executor.py`, which calls
`_generate_with_provider_compat()` without ever passing `image=`.

The legacy `generate_candidates()` path in `pipeline/generator.py` (lines 543-547) already
does the right thing: it fetches `parent_sku.variants[0].main_image_url` before the call.
Phase 10 simply ports that same pattern into `execute_generation_bundle()` in the modern
path, with one important constraint: finish sentence tasks (`platform == "finish"`) must
NOT receive image input (per success criterion 3).

**Primary recommendation:** Add a single `await fetch_image(...)` call in
`execute_generation_bundle()` before the per-task loop, then thread the fetched
`ImageInput | None` through `_generate_with_provider_compat()` to the provider. Skip
passing image for tasks whose `spec.platform == "finish"`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IMG-01 | Wire image input through executor.py modern generation path so all per-platform generation endpoints receive product images | All infrastructure exists. Gap is exclusively in `execute_generation_bundle()` not forwarding image to `_generate_with_provider_compat()`. Implementation is additive — no existing interfaces change. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | already in requirements | Async HTTP client for fetching images | Already used by `fetch_image()` |
| `anthropic` SDK | already in requirements | Accepts base64 image input in messages | Already used by `ClaudeProvider` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | already installed | Async test support | For testing the async fetch + executor path |
| `unittest.mock` | stdlib | Patching `fetch_image` in unit tests | Prevents HTTP calls during pytest |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fetch once before per-task loop | Fetch inside each task iteration | Fetching once is correct — image is product-level, same for all platforms. Fetching per-task wastes bandwidth and adds latency. |
| Pass image to finish task | Skip image for finish task | Finish tasks generate per-finish sentences, not product descriptions. Success criterion 3 explicitly requires no image for finish tasks. |

## Architecture Patterns

### Recommended Project Structure

No new files needed. Changes are confined to:

```
src/feedops/generation/executor.py    # add fetch_image call + thread image through
tests/test_image_wiring.py            # new test file — Wave 0 gap
```

### Pattern 1: Fetch-Once Before Task Loop

**What:** Image is product-level data (not per-platform). Fetch once before the task
loop, reuse the same `ImageInput | None` for every non-finish task.

**When to use:** Always — matches what `generate_candidates()` already does in generator.py.

**Example (from `generator.py` lines 543-547 — already working):**
```python
# Source: src/feedops/pipeline/generator.py:543
image = None
if parent_sku.variants:
    main_image_url = parent_sku.variants[0].main_image_url
    if main_image_url:
        image = await fetch_image(main_image_url)
```

Then pass `image=image` (or `image=None` for finish tasks) into the provider call.

### Pattern 2: Finish-Task Image Guard

**What:** Explicitly skip image for `platform == "finish"` tasks.

**When to use:** Inside the per-task loop before calling `_generate_with_provider_compat`.

**Example:**
```python
# Source: success criterion 3 + executor.py task loop pattern
task_image = None if spec.platform == "finish" else image
payload = await asyncio.wait_for(
    _generate_with_provider_compat(
        provider=provider,
        prompt=user_prompt,
        schema=schema,
        system_prompt=system_prompt,
        reasoning_effort=platform_reasoning,
        max_completion_tokens=platform_cap,
        image=task_image,
    ),
    timeout=120.0,
)
```

### Pattern 3: `_generate_with_provider_compat` Image Threading

**What:** The compat function already uses `inspect.signature` to decide which kwargs to
forward. The `image` parameter must be explicitly added to its kwargs dict and only
forwarded when the provider signature accepts it (or uses `**kwargs`).

**Current signature of `ClaudeProvider.generate`:**
```python
async def generate(
    self,
    prompt: str,
    schema: dict[str, Any],
    image: ImageInput | None = None,    # already present
    system_prompt: str | None = None,
    reasoning_effort: str | None = None,
    max_completion_tokens: int | None = None,
) -> dict[str, Any]:
```
`ClaudeProvider` already accepts `image`. `_generate_with_provider_compat` must also check
for `image` in the provider's signature and forward it.

### Pattern 4: Log Confirmation Line (Success Criterion 1)

**What:** After fetching image, emit a log line that confirms the image was sent.

**When to use:** Inside the fetch block, before the task loop.

**Example:**
```python
if image:
    logger.info(
        "image_wired: master_sku=%s source_url=%s bytes=%d",
        parent_sku.master_sku,
        image.source_url,
        len(image.data),
    )
```

Cloud Run logs can then be searched for `image_wired` to satisfy success criterion 1.

### Anti-Patterns to Avoid

- **Fetching image inside the per-task loop:** Causes N redundant HTTP fetches (N = number of platforms). Image is product-level, fetch once.
- **Passing image to finish tasks:** Explicitly banned by success criterion 3.
- **Raising on fetch failure:** `fetch_image()` already returns `None` on any error (HTTP 4xx, timeout, non-image content-type, oversized body). Callers must tolerate `None` gracefully — this is already the contract.
- **Hardcoding `variants[0]`:** Correct — all variants share the same product image (`main_image_url` in `product_catalog` is product-level, same value across all variant rows for a master_sku).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP image fetch with size/type guards | Custom httpx wrapper | `fetch_image()` in `pipeline/images.py` | Already handles content-type check, 5MB size limit, streaming, redirects, timeout, error logging |
| Base64 encoding for Anthropic | Manual base64 | `ClaudeProvider.generate(image=...)` | Already handles encoding in the provider |
| Image cache/dedup across tasks | Custom dict | Fetch-once pattern (single variable) | Image is per-SKU, not per-task; single fetch suffices |

**Key insight:** All image infrastructure was built during Phase 5 (Claude Provider).
Phase 10 is purely a wiring change — threading the already-built pieces together in the
modern executor path.

## Common Pitfalls

### Pitfall 1: `_generate_with_provider_compat` not forwarding `image`
**What goes wrong:** Function uses `inspect.signature` to decide which kwargs to forward.
If `image` is not added to the forwarding logic, the provider never receives it even if
`image=task_image` is passed to `_generate_with_provider_compat`.
**Why it happens:** The compat function was written before image support was wired.
**How to avoid:** Add `image` to the kwargs dict in `_generate_with_provider_compat` with
the same pattern used for `reasoning_effort` and `max_completion_tokens`.
**Warning signs:** Test confirms image fetch happened but provider mock was called with
`image=None` instead of the fetched `ImageInput`.

### Pitfall 2: Finish task receives image
**What goes wrong:** Success criterion 3 fails — finish sentence generation is slower and
uses image tokens unnecessarily.
**Why it happens:** Applying a single `image=image` variable to all tasks without the
finish-platform guard.
**How to avoid:** `task_image = None if spec.platform == "finish" else image` before each
provider call.
**Warning signs:** Test asserting finish task called with `image=None` fails.

### Pitfall 3: Image fetch failure causes generation failure
**What goes wrong:** Network timeout or 404 on image URL silently breaks all content
generation.
**Why it happens:** Treating the `fetch_image()` result as required rather than optional.
**How to avoid:** `fetch_image()` returns `None` on any error — always treat as optional.
Generation MUST proceed with `image=None` when fetch fails (success criterion 2 requires
a SKU without `main_image_url` to complete normally).
**Warning signs:** Test for SKU-without-image fails or raises.

### Pitfall 4: `main_image_url` lookup — which variant?
**What goes wrong:** Trying to pick a "best" variant or using a variant with a null URL
when `variants[0]` has one.
**Why it happens:** Over-engineering the variant selection.
**How to avoid:** Use `variants[0].main_image_url` — consistent with what `generator.py`
already does. All variants for a product share the same master product image in
`product_catalog`.
**Warning signs:** Logic to select the "best" variant with a non-null URL when it's not
needed.

### Pitfall 5: `ParentSKU` has no variants
**What goes wrong:** `parent_sku.variants[0]` raises `IndexError`.
**Why it happens:** Edge case where a SKU has no variant rows.
**How to avoid:** Guard with `if parent_sku.variants:` before accessing `variants[0]` —
same guard already in `generator.py:544`.
**Warning signs:** No guard present before variants list access.

## Code Examples

### Where to Add Image Fetch (executor.py)

```python
# Source: src/feedops/generation/executor.py — execute_generation_bundle()
# Add after building task_specs, before the for loop at line ~472

from feedops.pipeline.images import fetch_image  # add to imports at top of file

# Fetch product image once (product-level, shared across all platform tasks)
image = None
if parent_sku.variants:
    main_image_url = parent_sku.variants[0].main_image_url
    if main_image_url:
        image = await fetch_image(main_image_url)
        if image:
            logger.info(
                "image_wired: master_sku=%s source_url=%s bytes=%d",
                parent_sku.master_sku,
                image.source_url,
                len(image.data),
            )
        else:
            logger.debug(
                "image_fetch_skipped: master_sku=%s url=%s (fetch returned None)",
                parent_sku.master_sku,
                main_image_url,
            )
```

### Per-Task Image Guard (executor.py)

```python
# Source: src/feedops/generation/executor.py — inside the for spec in task_specs loop
# Add before the _generate_with_provider_compat call

task_image = None if spec.platform == "finish" else image

payload = await asyncio.wait_for(
    _generate_with_provider_compat(
        provider=provider,
        prompt=user_prompt,
        schema=schema,
        system_prompt=system_prompt,
        reasoning_effort=platform_reasoning,
        max_completion_tokens=platform_cap,
        image=task_image,     # NEW: pass image (None for finish tasks)
    ),
    timeout=120.0,
)
```

### `_generate_with_provider_compat` Update

```python
# Source: src/feedops/generation/executor.py — _generate_with_provider_compat()
# Must accept image parameter and forward it if provider supports it

async def _generate_with_provider_compat(
    *,
    provider: LLMProvider,
    prompt: str,
    schema: dict[str, object],
    system_prompt: str,
    reasoning_effort: str,
    max_completion_tokens: int,
    image: ImageInput | None = None,   # NEW parameter
) -> dict[str, object]:
    generate_fn = provider.generate
    signature = inspect.signature(generate_fn)
    accepts_varkw = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    kwargs: dict[str, object] = {
        "prompt": prompt,
        "schema": schema,
        "system_prompt": system_prompt,
    }
    if accepts_varkw or "reasoning_effort" in signature.parameters:
        kwargs["reasoning_effort"] = reasoning_effort
    if accepts_varkw or "max_completion_tokens" in signature.parameters:
        kwargs["max_completion_tokens"] = max_completion_tokens
    if image is not None and (accepts_varkw or "image" in signature.parameters):
        kwargs["image"] = image        # NEW: forward image only if provider supports it
    return await generate_fn(**kwargs)
```

### Test Skeleton (new file)

```python
# tests/test_image_wiring.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from feedops.providers.base import ImageInput

FAKE_IMAGE = ImageInput(
    data=b"fake-image-bytes",
    mime_type="image/jpeg",
    source_url="https://example.com/product.jpg",
)

def _make_parent_sku(main_image_url=None):
    """Minimal ParentSKU with one variant."""
    # Use project's existing pattern from test_claude_provider.py / test_images.py
    ...

@pytest.mark.asyncio
async def test_image_is_fetched_and_forwarded_to_provider():
    """Provider receives ImageInput when main_image_url is present."""
    ...

@pytest.mark.asyncio
async def test_no_image_url_completes_normally():
    """image=None handled gracefully when variant has no main_image_url."""
    ...

@pytest.mark.asyncio
async def test_finish_task_does_not_receive_image():
    """Finish sentence tasks are called with image=None regardless of SKU image."""
    ...

@pytest.mark.asyncio
async def test_fetch_failure_does_not_break_generation():
    """If fetch_image returns None (network error), generation proceeds."""
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Legacy `generate_candidates()` — has image wiring | Modern `execute_generation_bundle()` — image wiring missing | Phase 5 (Claude provider) added `fetch_image` + `ImageInput` | Phase 10 closes the gap in the modern path |
| All platforms called via `generate_candidates()` | Per-platform task graph via `execute_generation_bundle()` | Phase 3 (route extraction) | Modern path is what all production endpoints now use |

**Deprecated/outdated:**
- `generate_candidates()`: Still exists in `generator.py` but is only called by `generate_candidate()` which is used in CLI/quality pipelines, not the production API. The production API uses `generate_per_platform()` → `execute_generation_legacy_payload()` → `execute_generation_bundle()`. Image wiring in `generate_candidates()` (lines 543-547) is the reference implementation to replicate in the modern path.

## Open Questions

1. **Does OpenAI provider need image support?**
   - What we know: `ClaudeProvider.generate(image=...)` is fully implemented. `OpenAIProvider.generate()` does not accept `image` (not in its signature).
   - What's unclear: Whether to add image support to OpenAI provider in this phase.
   - Recommendation: No. The compat function's guard (`if image is not None and (accepts_varkw or "image" in signature.parameters)`) already handles this — if OpenAI provider doesn't declare `image`, it won't receive it. Only Claude benefits, which is the active provider in production (`FEEDOPS_PROVIDER=claude`). No change needed to OpenAI provider.

2. **Should image fetch timeout be configurable?**
   - What we know: `fetch_image()` defaults to 5s timeout, 5MB max.
   - What's unclear: Whether these defaults are appropriate for product images.
   - Recommendation: Use defaults. They're already validated in `test_images.py`. Allied Brass product images are typically small JPEG/PNG files well under 5MB.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already configured) |
| Config file | `pyproject.toml` (project root) |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_image_wiring.py -x -v` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IMG-01 | Provider receives `ImageInput` for SKU with `main_image_url` | unit | `pytest tests/test_image_wiring.py::test_image_is_fetched_and_forwarded_to_provider -x` | Wave 0 |
| IMG-01 | `image=None` handled gracefully (no error) for SKU without URL | unit | `pytest tests/test_image_wiring.py::test_no_image_url_completes_normally -x` | Wave 0 |
| IMG-01 | Finish tasks never receive image | unit | `pytest tests/test_image_wiring.py::test_finish_task_does_not_receive_image -x` | Wave 0 |
| IMG-01 | fetch_image failure does not break generation | unit | `pytest tests/test_image_wiring.py::test_fetch_failure_does_not_break_generation -x` | Wave 0 |
| IMG-01 | Full test suite stays green after change | regression | `pytest tests/ -x` | ✅ (788 tests) |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_image_wiring.py -x -v`
- **Per wave merge:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x`
- **Phase gate:** Full suite green (788 tests + new) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_image_wiring.py` — covers IMG-01 (4 test functions listed above)

*(Framework, conftest, and all supporting infrastructure already exist. Only the new test file is missing.)*

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/feedops/generation/executor.py` — full module read, confirmed no `image` parameter anywhere
- Direct code inspection: `src/feedops/pipeline/generator.py:543-553` — reference implementation of fetch-once + pass-to-provider pattern
- Direct code inspection: `src/feedops/providers/claude_provider.py:114-145` — `generate()` already accepts `image: ImageInput | None = None`
- Direct code inspection: `src/feedops/providers/base.py` — `ImageInput` dataclass definition
- Direct code inspection: `src/feedops/pipeline/images.py` — `fetch_image()` fully implemented with error handling
- Direct code inspection: `src/feedops/models/variant.py:62` — `main_image_url: str | None = None` confirmed on Variant model
- Direct code inspection: `src/feedops/api/supabase_loader.py:127` — `main_image_url` loaded from `product_catalog.main_image_url`
- Direct code inspection: `tests/test_images.py` — existing test patterns for `fetch_image` mocking
- Direct code inspection: `tests/test_claude_provider.py` — existing test patterns for `ClaudeProvider` with image

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — IMG-01 definition and scope
- `.planning/ROADMAP.md` — Phase 10 success criteria (4 criteria)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all code directly read, no assumptions
- Architecture: HIGH — the exact change location identified (executor.py `_generate_with_provider_compat` + `execute_generation_bundle`), reference implementation in generator.py confirmed working
- Pitfalls: HIGH — all pitfalls derived from direct code inspection of the gap and the existing working implementation

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable — no external dependencies, all internal code)
