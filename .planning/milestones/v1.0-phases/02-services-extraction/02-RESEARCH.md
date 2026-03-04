# Phase 2: Services Extraction - Research

**Researched:** 2026-03-03
**Domain:** Python module refactoring — mechanical function extraction into service modules
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module boundaries:**
- `finish_processing.py`: `_validate_finish_sentences_payload()`, `_enforce_finish_sentence_parity()`, `_build_finish_sentences_user_prompt()` — all finish-related logic in one module
- `intent_scoring.py`: `_get_intent_scorer()`, `_extract_query_intent_generation_diagnostics()`, `api_score_intent()` route handler (self-contained enough to own its route)
- `generation.py`: `_build_generation_user_prompt()`, `_execute_regeneration_request()` — core generation orchestration and prompt assembly
- Route handlers for all other endpoints stay in main.py — only intent scoring moves its route (it's fully self-contained)

**run_async_in_thread (DECOMP-08):**
- Keep in `telemetry.py` where Phase 1 placed it — callers already updated, import graph is clean
- Add unit test asserting `thread.daemon == False` to satisfy DECOMP-08
- No need for a separate utils.py

**Test approach (DECOMP-11):**
- One test file per extracted module: `test_finish_processing.py`, `test_intent_scoring.py`, `test_generation.py`
- Real unit tests with mocked dependencies (Supabase, OpenAI) — not just smoke tests
- Test actual business logic: finish parity catches missing finishes, intent scoring returns expected structure, generation handles error paths
- Add daemon=False assertion for run_async_in_thread in existing telemetry tests

**Import and commit strategy (carried from Phase 1):**
- All modules flat in `src/feedops/api/` — established pattern
- Clean break imports, no re-exports from main.py
- Preserve exact function signatures — zero changes during move
- One commit per module extraction
- Pytest verification after each extraction

**generation_telemetry.py:**
- Claude's discretion on whether to merge into telemetry.py or leave as-is — check for overlap and decide

### Claude's Discretion
- Exact function grouping for edge cases (helpers that could go in multiple modules)
- Internal module organization and ordering
- Test case selection and mock depth
- Whether generation_telemetry.py merges into telemetry.py

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DECOMP-05 | Extract query intent and content scoring into `intent_scoring.py` | `_get_intent_scorer()` and `_extract_query_intent_generation_diagnostics()` at lines 2601–2654 in main.py. Route handler `api_score_intent` moves with them. Module singleton pattern with threading.Lock already in place. |
| DECOMP-06 | Extract finish sentence validation and parity enforcement into `finish_processing.py` | Three functions at lines 320–543: `_build_finish_sentences_user_prompt()`, `_validate_finish_sentences_payload()`, `_enforce_finish_sentence_parity()`. All depend on `get_finish_list()` from prompt_loader.py. |
| DECOMP-07 | Extract core generation orchestration into `generation.py` | `_build_generation_user_prompt()` (lines 292–317, marked DEPRECATED thin wrapper) and `_execute_regeneration_request()` (lines 789–1112, the 324-line core generation function). |
| DECOMP-08 | Extract `run_async_in_thread()` into shared utility module with daemon=False test | Already extracted to `telemetry.py` in Phase 1 (line 26–70). Only gap: unit test asserting `thread.daemon == False` at runtime (current test inspects source code, not runtime behavior). |
| DECOMP-10 | All existing API endpoints work identically after extraction | No behavioral changes — pure move. Verified by running existing test suite after each extraction. Five endpoints under test: `/optimize-sku`, `/regenerate`, `/batch-optimize`, `/hybrid-generate`, `/generate-images`. |
| DECOMP-11 | pytest covers each extracted module independently | Three new test files, one per module. Pattern: import module without main.py, mock Supabase/OpenAI, assert business logic (not just callable). See existing `test_*_smoke.py` files for structural precedent. |
</phase_requirements>

## Summary

Phase 2 extracts three service modules from `main.py` (currently 2,654 lines after Phase 1). The extraction targets are well-defined in CONTEXT.md: `finish_processing.py` (finish sentence building, validation, and parity enforcement), `intent_scoring.py` (singleton scorer setup and the `/score-intent` route), and `generation.py` (`_build_generation_user_prompt` thin wrapper and the large `_execute_regeneration_request` orchestration function).

This is a mechanical refactoring — no behavioral changes, no signature changes. The pattern is identical to Phase 1: copy functions verbatim, update imports in main.py, delete dead code, verify with pytest. The key risk is import graph — each new module needs its own imports, and the functions being moved carry substantial dependency trees (especially `_execute_regeneration_request` which calls into persistence, telemetry, job_management, providers, and supabase).

The test requirement (DECOMP-11) is what differentiates Phase 2 from Phase 1. Phase 1 wrote smoke tests (callable assertions, no-circular-import checks). Phase 2 needs real unit tests: finish parity logic must catch actual missing finishes; intent scoring must return expected score structure; generation must handle error paths. The existing `tests/test_finish_sentence_validation.py` and `tests/test_intent_scorer.py` show the mock data patterns to follow.

**Primary recommendation:** Extract modules in order of isolation: `intent_scoring.py` first (most self-contained), then `finish_processing.py` (medium coupling), then `generation.py` (highest coupling, most risk). Write tests alongside each extraction before moving to the next.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | project-installed | Test runner | Used throughout the test suite; `asyncio_mode = "auto"` in pyproject.toml |
| unittest.mock | stdlib | Mocking Supabase/OpenAI dependencies | No external mock library used anywhere in the test suite |
| pytest-asyncio | project-installed | async test support | `asyncio_mode = "auto"` already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| threading | stdlib | daemon=False verification | In `test_finish_processing.py` and telemetry test for DECOMP-08 |
| inspect | stdlib | Source-level assertions | Already used in `test_telemetry_smoke.py`; for runtime assertions prefer actual thread creation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `unittest.mock.patch` | `pytest-mock` | Project doesn't use pytest-mock; stick with stdlib mocking |
| Runtime daemon assertion | Source inspection | Runtime assertion is stronger — actually calls `run_async_in_thread` and checks `thread.daemon` attribute |

**Installation:** No new packages needed — all test dependencies already installed.

## Architecture Patterns

### Recommended Project Structure
```
src/feedops/api/
├── main.py              # Route definitions only (~500 lines after Phase 3)
├── schemas.py           # Pydantic models (Phase 1 complete)
├── persistence.py       # DB read/write (Phase 1 complete)
├── job_management.py    # Job lifecycle (Phase 1 complete)
├── telemetry.py         # Metrics + run_async_in_thread (Phase 1 complete)
├── finish_processing.py # NEW: finish building, validation, parity
├── intent_scoring.py    # NEW: scorer singleton + /score-intent route
└── generation.py        # NEW: _build_generation_user_prompt + _execute_regeneration_request
```

### Pattern 1: Module Extraction Template (established in Phase 1)
**What:** Copy functions verbatim. Add module docstring. Add imports. Delete from main.py. Update main.py imports. Verify pytest passes.
**When to use:** Every module in this phase.

```python
# Source: src/feedops/api/persistence.py (Phase 1 model)
"""[Module description]."""

from __future__ import annotations

import logging
# ... other stdlib

# ... project imports (copy from main.py headers, scoped to what this module needs)

logger = logging.getLogger(__name__)

# [Functions verbatim from main.py]
```

### Pattern 2: Singleton with Threading Lock (intent_scoring.py)
**What:** `_intent_scorer` global + `_intent_scorer_lock` must move together with the getter function.
**When to use:** When extracting `_get_intent_scorer()`.

```python
# Source: main.py lines 2601-2616
import threading

_intent_scorer = None
_intent_scorer_lock = threading.Lock()

def _get_intent_scorer():
    """Get or lazily initialize the IntentScorer singleton."""
    global _intent_scorer
    if _intent_scorer is not None:
        return _intent_scorer
    with _intent_scorer_lock:
        if _intent_scorer is not None:
            return _intent_scorer
        from feedops.scoring.intent_scorer import IntentScorer
        logger.info("Initializing IntentScorer (first request)...")
        _intent_scorer = IntentScorer.from_supabase()
        logger.info("IntentScorer ready")
        return _intent_scorer
```

### Pattern 3: Route Handler in Service Module
**What:** `api_score_intent` stays attached to `app` (FastAPI instance) via import + `@app.post` decorator. Route must be registered via `app.include_router()` or direct decorator reference.
**When to use:** intent_scoring.py owns its route.
**Critical:** The `app` object lives in `main.py`. Two options: (A) pass `app` as parameter and register in main.py after import, or (B) use `APIRouter` and `include_router`. Option B is cleaner.

```python
# intent_scoring.py
from fastapi import APIRouter, HTTPException
from feedops.api.schemas import ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse

router = APIRouter()

@router.post("/score-intent", response_model=ScoreIntentResponse)
async def api_score_intent(request: ScoreIntentRequest):
    ...
```

```python
# main.py — add after existing router includes
from feedops.api.intent_scoring import router as intent_scoring_router
app.include_router(intent_scoring_router)
```

### Pattern 4: Unit Test with Mocked Dependencies
**What:** Import the new module without `main.py`. Mock the DB client and provider. Assert business logic.
**When to use:** DECOMP-11 test files.

```python
# Source: tests/test_finish_sentence_validation.py (existing pattern to follow)
from unittest.mock import patch, MagicMock

def test_validate_finish_sentences_payload_rejects_incomplete():
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list") as mock_list:
        mock_list.return_value = ["Antique Brass", "Matte Black", "Polished Chrome"]
        result = _validate_finish_sentences_payload(
            {"Antique Brass": "Antique Brass adds warmth to this grab bar."},
            base_description="This grab bar provides secure support.",
            master_sku="920D-6",
            platform="google",
        )
    # Should accept valid entry, log warning about incomplete set
    assert "Antique Brass" in result
```

### Anti-Patterns to Avoid
- **Re-exporting from main.py:** Do NOT add `from feedops.api.finish_processing import *` in main.py. Use direct imports in callers (Phase 1 established this pattern).
- **Changing function signatures during move:** Any signature change is out of scope — pure move only.
- **Moving `process_regenerate_job` or `process_batch_job`:** These are Phase 3 scope (`JOBS-01`/`JOBS-02`). Leave in main.py.
- **Moving route handlers except intent scoring:** Only `api_score_intent` moves with its service module.
- **Using `@app.post` decorator in service module:** Use `APIRouter` instead — `app` lives in main.py.
- **Monolithic test:** Don't write one test file covering all three modules. One file per module as decided.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async test support | Manual event loop in tests | `asyncio_mode = "auto"` in pyproject.toml | Already configured — `async def test_*` just works |
| Mock patch paths | Guessing module paths | Match the import path used inside the module | `finish_processing.py` imports `get_finish_list` from `feedops.api.prompt_loader` — patch that path |
| daemon=False verification | Source inspection (current approach is weak) | `run_async_in_thread` creates a thread — inspect `thread.daemon` attribute directly | Runtime assertion is stronger than text search |

**Key insight:** The existing test suite has 100+ tests demonstrating all needed patterns. Read `tests/test_intent_scorer.py` for scorer mocking, `tests/test_finish_sentence_validation.py` for finish logic, `tests/api/test_telemetry_smoke.py` for the import-isolation pattern.

## Common Pitfalls

### Pitfall 1: generation.py Dependency Chain
**What goes wrong:** `_execute_regeneration_request` calls 15+ functions from across the codebase. Missing one import causes `NameError` at runtime (not import time).
**Why it happens:** The function body references module-level aliases like `_provider_label`, `_safe_int`, `_estimate_openai_cost_usd_from_usage` that were aliased at import time in main.py (e.g., `from feedops.api.generation_telemetry import provider_label as _provider_label`).
**How to avoid:** Before deleting from main.py, grep for every symbol used in `_execute_regeneration_request` body and confirm each is imported in generation.py.
**Warning signs:** Tests pass but endpoint returns 500 with NameError.

### Pitfall 2: FastAPI App Reference in intent_scoring.py
**What goes wrong:** If `api_score_intent` keeps the `@app.post` decorator, `intent_scoring.py` must import `app` from main.py, creating a circular import.
**Why it happens:** `app = FastAPI(...)` is in main.py; if the decorator references it, you need that module.
**How to avoid:** Use `APIRouter` (Pattern 3 above). Register with `app.include_router()` in main.py.
**Warning signs:** `ImportError: cannot import name 'app' from partially initialized module 'feedops.api.main'`

### Pitfall 3: Global State Migration (intent scorer singleton)
**What goes wrong:** `_intent_scorer` and `_intent_scorer_lock` are module-level globals. If they stay in main.py and `_get_intent_scorer()` moves to intent_scoring.py, the singleton is broken.
**Why it happens:** Python module globals are per-module. A function in intent_scoring.py that references `global _intent_scorer` will look in intent_scoring's namespace, not main.py's.
**How to avoid:** Move `_intent_scorer = None` and `_intent_scorer_lock = threading.Lock()` to intent_scoring.py alongside `_get_intent_scorer()`.
**Warning signs:** IntentScorer re-initialized on every request (logs show repeated "Initializing IntentScorer" messages).

### Pitfall 4: finish_processing.py Calls persistence.py Function
**What goes wrong:** `_enforce_finish_sentence_parity()` calls `_assembled_prompt_hash()` from persistence.py (line 490 in main.py). If finish_processing.py doesn't import from persistence.py, NameError at runtime.
**Why it happens:** `_assembled_prompt_hash` was extracted to persistence.py in Phase 1. The body of `_enforce_finish_sentence_parity` uses it.
**How to avoid:** Add `from feedops.api.persistence import _assembled_prompt_hash` in finish_processing.py.
**Warning signs:** `NameError: name '_assembled_prompt_hash' is not defined` in test or at runtime.

### Pitfall 5: Test Isolation — Mocking the Right Path
**What goes wrong:** Tests mock `feedops.api.prompt_loader.get_finish_list` but the function was imported at module level (`from feedops.api.prompt_loader import get_finish_list`). The mock doesn't intercept calls.
**Why it happens:** `unittest.mock.patch` must patch where the name is *used*, not where it's *defined*.
**How to avoid:** Patch `feedops.api.finish_processing.get_finish_list` (the name in the module under test), not `feedops.api.prompt_loader.get_finish_list`.
**Warning signs:** Test passes unconditionally regardless of mock return value.

### Pitfall 6: generation_telemetry.py Merge Decision
**What goes wrong:** Merging generation_telemetry.py into telemetry.py changes the import path. All callers importing from `feedops.api.generation_telemetry` break.
**Why it happens:** main.py imports from both: `from feedops.api.generation_telemetry import ...` and `from feedops.api.telemetry import ...`.
**How to avoid:** Check overlap. `generation_telemetry.py` contains pure data normalization helpers (safe_int, estimate_openai_cost_usd_from_usage, provider_label, extract_platform_telemetry, extract_scoped_telemetry). `telemetry.py` imports from generation_telemetry already (it re-uses `provider_label`). They are already well-separated — recommend leaving as-is to avoid churn. If merging, add a compatibility shim: `from feedops.api.telemetry import safe_int, ...` in generation_telemetry.py.
**Warning signs:** `ImportError` in generation_telemetry importers after merge.

## Code Examples

### daemon=False Runtime Test (stronger than current source inspection)
```python
# Source: tests/api/test_telemetry_smoke.py (enhancement)
import asyncio

def test_run_async_in_thread_daemon_false_at_runtime():
    """DECOMP-08: thread.daemon must be False at runtime, not just in source."""
    from feedops.api.telemetry import run_async_in_thread

    async def noop():
        pass

    thread = run_async_in_thread(noop)
    assert thread.daemon == False, "run_async_in_thread must use non-daemon threads"
    thread.join(timeout=2.0)  # Wait for quick noop to finish
```

### finish_processing.py Structure
```python
"""Finish sentence building, validation, and parity enforcement."""

from __future__ import annotations

import logging

from feedops.api.generation_telemetry import provider_label as _provider_label
from feedops.api.persistence import _assembled_prompt_hash
from feedops.api.prompt_loader import get_finish_list, get_platform_system_prompt
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.pipeline.finish_sentence_placeholder import (
    build_fallback_finish_sentences,
    normalize_base_description_with_finish_placeholder,
    strip_hardcoded_finish_names,
    strip_generic_finish_count_claims,
)
from feedops.pipeline.finish_sentence_validation import normalize_and_validate_finish_sentences

logger = logging.getLogger(__name__)


def _build_finish_sentences_user_prompt(...) -> str: ...
def _validate_finish_sentences_payload(...) -> dict[str, str]: ...
async def _enforce_finish_sentence_parity(...) -> tuple[str, dict[str, str] | None]: ...
```

### intent_scoring.py Structure with APIRouter
```python
"""Query intent scoring service and /score-intent route handler."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from feedops.api.schemas import ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_intent_scorer = None
_intent_scorer_lock = threading.Lock()


def _extract_query_intent_generation_diagnostics(generated: dict | None) -> dict: ...
def _get_intent_scorer(): ...


@router.post("/score-intent", response_model=ScoreIntentResponse)
async def api_score_intent(request: ScoreIntentRequest): ...
```

### generation.py Structure
```python
"""Core generation orchestration: prompt assembly and regeneration execution."""

from __future__ import annotations

import logging

from fastapi import HTTPException
# ... imports for all symbols used in _execute_regeneration_request body

logger = logging.getLogger(__name__)


def _build_generation_user_prompt(...) -> str: ...
async def _execute_regeneration_request(...) -> RegenerateResponse: ...
```

### Test for finish parity logic
```python
# tests/api/test_finish_processing.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

FINISH_NAMES = ["Antique Brass", "Matte Black", "Polished Chrome"]


def test_validate_finish_sentences_payload_accepts_valid():
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.normalize_and_validate_finish_sentences") as mock_nv:
        mock_nv.return_value = ({"Antique Brass": "AB sentence."}, [])
        result = _validate_finish_sentences_payload(
            {"Antique Brass": "AB sentence."},
            base_description="A grab bar.", master_sku="920D-6", platform="google",
        )
    assert "Antique Brass" in result


def test_validate_finish_sentences_payload_increments_metric_on_rejection():
    from feedops.api.finish_processing import _validate_finish_sentences_payload
    with patch("feedops.api.finish_processing.get_finish_list", return_value=FINISH_NAMES), \
         patch("feedops.api.finish_processing.normalize_and_validate_finish_sentences") as mock_nv, \
         patch("feedops.api.finish_processing.metrics_registry") as mock_metrics:
        mock_nv.return_value = ({}, ["Antique Brass", "Matte Black", "Polished Chrome"])
        _validate_finish_sentences_payload(
            {}, base_description="A grab bar.", master_sku="920D-6", platform="google",
        )
    mock_metrics.increment.assert_called()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All business logic in main.py | Extracted modules (persistence, telemetry, job_management from Phase 1) | Phase 1 (2026-03-03) | Import isolation, testability per module |
| Smoke tests only (callable check) | Real unit tests with mocked dependencies | Phase 2 (this phase) | Business logic verified without live services |
| `@app.post` decorator on route in main.py | `APIRouter` for self-contained service routes | Phase 2 (this phase) | Enables route ownership by service modules |

## generation_telemetry.py Merge Analysis

**Recommendation: Leave as-is (do NOT merge into telemetry.py).**

Evidence:
- `generation_telemetry.py` contains 5 pure functions with zero side effects (no logging imports, no metrics calls). All are data normalization helpers.
- `telemetry.py` already imports from `generation_telemetry.py`: `from feedops.api.generation_telemetry import provider_label as _provider_label`. Merging would create a file that imports from itself (circular).
- `main.py` imports from both modules with different aliases. No duplication — they serve different purposes.
- Adding a compatibility shim to support merge creates more churn than value.
- File is 130 lines. No reason to merge.

**Confidence:** HIGH — the import graph makes merge impossible without breaking changes.

## Open Questions

1. **`_execute_regeneration_request` calls `_content_field_key()`**
   - What we know: `_content_field_key` is defined in `schemas.py` (extracted Phase 1) and imported in main.py: `from feedops.api.schemas import ..., _content_field_key, ...`
   - What's unclear: Is it imported at the top of main.py or used as a local alias in the function body?
   - Recommendation: Grep confirms it's in the top-level import block (line 51). generation.py needs `from feedops.api.schemas import _content_field_key`.

2. **`_execute_regeneration_request` uses `_provider_label`, `_safe_int`, `_estimate_openai_cost_usd_from_usage`**
   - What we know: These are aliased in main.py's import block from `generation_telemetry` (lines 69-74): `provider_label as _provider_label`, `safe_int as _safe_int`, `estimate_openai_cost_usd_from_usage as _estimate_openai_cost_usd_from_usage`.
   - What's unclear: The function body uses the aliased names. generation.py must re-declare the same aliases.
   - Recommendation: In generation.py, use `from feedops.api.generation_telemetry import provider_label as _provider_label, safe_int as _safe_int, estimate_openai_cost_usd_from_usage as _estimate_openai_cost_usd_from_usage`.

## Sources

### Primary (HIGH confidence)
- Direct source code read — `src/feedops/api/main.py` (2,654 lines, full function inventory)
- Direct source code read — `src/feedops/api/telemetry.py` (current state, `run_async_in_thread` already daemon=False)
- Direct source code read — `src/feedops/api/generation_telemetry.py` (merge analysis)
- Direct test read — `tests/api/test_*_smoke.py` (established test patterns for Phase 2 to follow)
- Direct test read — `tests/test_finish_sentence_validation.py` and `tests/test_intent_scorer.py` (mocking patterns)

### Secondary (MEDIUM confidence)
- FastAPI APIRouter pattern — standard FastAPI documentation pattern for modular route registration; consistent with how `search_insights_router`, `monitoring_router`, `gmc_sync_router`, `performance_baseline_router` are already registered in main.py

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, all patterns from existing codebase
- Architecture: HIGH — direct source read, patterns established in Phase 1
- Pitfalls: HIGH — derived from actual source analysis (alias symbols, circular import risk, singleton globals)
- generation_telemetry merge: HIGH — import graph makes merge circular, confirmed by reading both files

**Research date:** 2026-03-03
**Valid until:** Until main.py is modified outside this phase (stable — pure extraction)
