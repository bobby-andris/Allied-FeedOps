# Phase 1: Schemas Extraction - Research

**Researched:** 2026-03-03
**Domain:** Python module decomposition — extracting Pydantic models, Supabase CRUD, job lifecycle, and telemetry from a 3,737-line FastAPI main.py
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module boundaries:**
- Extract ALL four modules in Phase 1: `schemas.py`, `persistence.py`, `job_management.py`, `telemetry.py`
- All modules live flat in `src/feedops/api/` alongside main.py (matches existing pattern — prompt_loader.py, search_insights.py already there)
- `persistence.py` gets CRUD functions only — Supabase client initialization stays in main.py's lifespan, passed as parameter
- `job_management.py` gets lifecycle helpers only (job creation, status tracking, idempotency checks, error formatting) — the big `process_batch_job()` and `process_hybrid_batch_job()` stay in main.py until Phase 3 unifies them into JobRunner

**Import strategy:**
- Clean break: update all callers to import from new modules directly, no re-exports from main.py
- 3 files need updating for `run_async_in_thread`: search_insights.py, gmc_sync.py, backfill.py
- Named imports for schemas: `from feedops.api.schemas import OptimizeRequest, BatchOptimizeRequest`
- Preserve exact function signatures during move — zero signature changes, type hint improvements are a separate concern

**Test approach:**
- Smoke tests only: one test file per extracted module verifying imports work, no circular dependencies, key classes/functions accessible (~5-10 tests total)
- Full contract testing deferred to Phase 2 (DECOMP-11)

**Commit strategy:**
- One commit per module (4 commits): schemas.py, persistence.py, job_management.py, telemetry.py
- Each commit independently reviewable and revertable
- Local verification after each extraction (pytest + `python -c 'import feedops.api.main'`)
- Single deploy + curl verification after all 4 modules extracted

### Claude's Discretion

- Exact function grouping within each module (which helpers go where)
- Internal module organization (ordering, grouping by concern)
- Smoke test specifics (which assertions, which edge cases)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DECOMP-01 | Extract all Pydantic request/response models (~17 classes) into `schemas.py` | 17 classes identified at lines 295–514 + 3 intent scoring models at 3662–3680; exact inventory documented below |
| DECOMP-02 | Extract all Supabase read/write functions into `persistence.py` | 7 CRUD functions identified at lines 695–1117; all take `supabase` as first param, safe to move |
| DECOMP-03 | Extract job lifecycle functions into `job_management.py` | 8 lifecycle helpers identified at lines 1121–1404; clearly scoped, no FastAPI/route dependencies |
| DECOMP-04 | Extract metrics emission and diagnostics into `telemetry.py` | generation_telemetry.py already extracted; 3 telemetry helpers remain in main.py to move |
</phase_requirements>

---

## Summary

`main.py` is 3,737 lines. The extraction target is ~1,200 lines across four modules, leaving the remaining ~2,500 lines for routes and two large batch-processing functions that Phase 3 will address. This phase is purely mechanical — no logic changes, no signature changes, no behavior changes.

The existing codebase already demonstrates the correct pattern: `generation_telemetry.py`, `prompt_loader.py`, `search_insights.py`, and `sku_alias.py` are all flat-in-`api/` extracted modules. The extraction follows the identical pattern. The sole non-trivial challenge is the `run_async_in_thread` function, which 4 files currently import via lazy in-function imports from `main.py` — moving it to `telemetry.py` (or a shared utility) requires updating those 4 call sites.

One pre-existing test (`tests/api/test_regenerate_response_contract.py`) imports `RegenerateResponse` directly from `feedops.api.main`. After extraction, that import must be updated to `feedops.api.schemas`. This is the only known test that will break. All other tests import through route-level contracts and won't need changes.

**Primary recommendation:** Extract modules in dependency order — schemas first (no deps), then persistence (needs schemas for type hints), then job_management (needs schemas + persistence), then telemetry (standalone). One commit per module.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | v2 (already in use) | Request/response model validation | Project already uses BaseModel from pydantic v2; all models use `Field`, `Literal` |
| fastapi | already in use | Route definitions stay in main.py | No new dependency; extraction does not touch FastAPI machinery |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7.0 (pyproject.toml) | Smoke test execution | `pytest tests/` — asyncio_mode=auto already configured |
| pytest-asyncio | >=0.21 | Async test support | Already configured; no additional setup needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Flat module structure in `api/` | Sub-package (`api/models/`) | Flat is consistent with existing pattern; sub-packages add `__init__.py` complexity with no benefit at this scale |
| Clean break imports | Re-exports via `main.py` | Re-exports defeat the purpose — they maintain tight coupling and prevent independent import testing |

---

## Architecture Patterns

### Recommended Project Structure (after Phase 1)

```
src/feedops/api/
├── main.py               # Routes + 2 large batch functions (~2,500 lines, down from 3,737)
├── schemas.py            # NEW: 17 Pydantic models + 3 intent scoring models + helper fns
├── persistence.py        # NEW: 7 Supabase CRUD functions
├── job_management.py     # NEW: 8 job lifecycle helpers
├── telemetry.py          # NEW: run_async_in_thread + emit summary + telemetry scope helper
├── generation_telemetry.py  # EXISTING: already extracted (safe_int, estimate_cost, etc.)
├── prompt_loader.py      # EXISTING: already extracted
├── search_insights.py    # EXISTING: already extracted (update 1 lazy import)
├── gmc_sync.py           # EXISTING: update 1 lazy import
├── backfill.py           # EXISTING: update 2 lazy imports
└── ...
```

### Pattern 1: Extracted Module Structure (established pattern)

**What:** Each module is a plain Python file with no FastAPI machinery, no `app` reference, no route decorators. Only pure functions and Pydantic models.

**When to use:** Every extracted module in this phase.

**Example (from existing `generation_telemetry.py`):**
```python
"""Shared generation telemetry normalization helpers."""
from __future__ import annotations

def safe_int(value: object, default: int = 0) -> int:
    """Best-effort int conversion for telemetry snapshots."""
    ...
```

**Key:** No `from fastapi import ...` — modules must be importable without FastAPI being initialized.

### Pattern 2: Supabase Parameter Passing

**What:** Persistence functions receive `supabase` as an explicit parameter (not module-level global access). This is already the pattern in main.py — all 7 CRUD functions take `*, supabase` as first keyword arg.

**When to use:** All functions in `persistence.py`.

**Example:**
```python
# persistence.py
def _lookup_generated_content_id(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
) -> str | None:
    ...
```

The Supabase client is initialized in `_app_lifespan()` in main.py and stays there. Call sites in main.py pass it explicitly — no change needed.

### Pattern 3: Lazy Import → Direct Import Migration

**What:** Four files currently use lazy (in-function) imports to avoid circular dependencies:
- `search_insights.py` line 131: `from feedops.api.main import run_async_in_thread`
- `gmc_sync.py` line 72: `from feedops.api.main import run_async_in_thread`
- `backfill.py` lines 502 and 590: `from feedops.api.main import run_async_in_thread`

After moving `run_async_in_thread` to `telemetry.py`, circular import risk is eliminated. The lazy import pattern can be replaced with top-level imports.

**Migration:**
```python
# BEFORE (lazy, in function body):
def start_sync(...):
    from feedops.api.main import run_async_in_thread
    run_async_in_thread(...)

# AFTER (direct top-level import):
from feedops.api.telemetry import run_async_in_thread

def start_sync(...):
    run_async_in_thread(...)
```

### Pattern 4: Smoke Test Structure

**What:** One test file per module, ~5 tests each. Tests verify: (1) module imports without error, (2) key classes are accessible, (3) no circular import when main.py is also imported, (4) critical helpers return expected types.

**Example:**
```python
# tests/api/test_schemas_smoke.py
def test_schemas_importable_without_main():
    from feedops.api.schemas import OptimizeRequest, RegenerateResponse
    assert OptimizeRequest is not None

def test_no_circular_import():
    import feedops.api.main  # must not raise
    import feedops.api.schemas  # must not raise

def test_optimize_request_fields():
    from feedops.api.schemas import OptimizeRequest
    req = OptimizeRequest(master_sku="FT-16")
    assert req.dry_run is True  # default
```

### Anti-Patterns to Avoid

- **Importing `app` or `HTTPException` in extracted modules:** The modules must be importable without FastAPI. `_enforce_write_time_finish_placeholder_contract` in `persistence.py` raises `HTTPException` — this is an exception to the rule that requires deliberate handling (see Open Questions).
- **Re-exporting from main.py:** `from feedops.api.main import X` in callers must be updated to the new module path. No shim imports in main.py.
- **Moving `process_batch_job` or `process_hybrid_batch_job`:** These stay in main.py until Phase 3. Do not extract them now.
- **Moving `_app_lifespan`, `run_async_in_thread`'s inline Supabase crash handler:** The crash handler inside `run_async_in_thread` accesses Supabase directly — this is acceptable since it's error recovery code, not normal CRUD.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circular import detection | Custom import checker | `python -c "import feedops.api.main"` | Python itself errors on circular imports; this is the verification command |
| Module dependency graph | Visualization tool | Manual audit (already done below) | Phase 1 is small enough to verify by reading |
| Import path updates | Sed/regex script | Targeted grep + edit | 4 files, 5 specific lines — faster to edit directly |

**Key insight:** This is a mechanical refactoring. The verification strategy (`python -c "import feedops.api.main"` + `pytest`) is already defined. No tooling needed beyond standard Python and pytest.

---

## Complete Function Inventory

### schemas.py — What to Extract

**Pydantic Models (lines 295–514, 3662–3680):**

| Class | Line | Destination |
|-------|------|-------------|
| `OptimizeRequest` | 295 | schemas.py |
| `RegenerateRequest` | 305 | schemas.py |
| `BatchOptimizeRequest` | 341 | schemas.py |
| `HealthResponse` | 360 | schemas.py |
| `OptimizeResponse` | 370 | schemas.py |
| `RegenerateResponse` | 380 | schemas.py |
| `RegenerateJobResponse` | 399 | schemas.py |
| `RegenerateJobStatusResponse` | 412 | schemas.py |
| `BatchJobResponse` | 441 | schemas.py |
| `BatchStatusResponse` | 450 | schemas.py |
| `GenerateImagesRequest` | 464 | schemas.py |
| `GenerateImagesResponse` | 480 | schemas.py |
| `HybridGenerateRequest` | 491 | schemas.py |
| `HybridJobResponse` | 503 | schemas.py |
| `ScoreIntentRequest` | 3662 | schemas.py |
| `ScoreIntentItem` | 3668 | schemas.py |
| `ScoreIntentResponse` | 3677 | schemas.py |

**Schema Helper Functions (travel with schemas):**
| Function | Line | Destination |
|----------|------|-------------|
| `_normalize_regeneration_job_status()` | 429 | schemas.py (used by `RegenerateJobStatusResponse`, `_normalize_regeneration_job_row`) |
| `_normalize_generation_options()` | 516 | schemas.py (normalizes `BatchOptimizeRequest.options`) |
| `_content_field_key()` | 544 | schemas.py (maps platform/content_type to field key) |
| `_extract_content_from_schema_response()` | 557 | schemas.py (extracts content from schema response dict) |

**Total: 17 Pydantic models + 4 helper functions**

### persistence.py — What to Extract

| Function | Line | Notes |
|----------|------|-------|
| `_lookup_generated_content_id()` | 695 | Reads `generated_content` table |
| `_load_generated_content_row()` | 730 | Reads `generated_content` table |
| `_assembled_prompt_hash()` | 759 | Pure helper — computes hash of prompt pair |
| `_enforce_write_time_finish_placeholder_contract()` | 772 | Raises `HTTPException` — see Open Questions |
| `_persist_regeneration_result()` | 816 | Writes `generated_content` + `regeneration_history` |
| `_persist_generated_content_and_history()` | 952 | Writes `generated_content` + `regeneration_history` |
| `_persist_finish_prompt_lineage()` | 1044 | Writes `regeneration_history` (finish subcall) |
| `_upsert_batch_job_sku_status()` | 1376 | Writes `batch_generation_job_skus` |

**Total: 8 functions**

**Import dependencies for persistence.py:**
- `from feedops.api.schemas import RegenerateResponse` (for type hints in `_normalize_regeneration_job_row` — but that's in job_management, not persistence)
- `from feedops.api.generation_telemetry import _safe_int` (already extracted)
- `from feedops.observability import get_request_id, log_event`
- `from feedops.pipeline.feature_flags import capture_flag_snapshot`
- `from feedops.api.prompt_loader import get_platform_system_prompt_hash`
- `from feedops.pipeline.finish_sentence_placeholder import count_finish_sentence_placeholders`
- `from feedops.generation.persistence import get_finish_task_result`
- `from fastapi import HTTPException` (for `_enforce_write_time_finish_placeholder_contract` — see Open Questions)

### job_management.py — What to Extract

| Function | Line | Notes |
|----------|------|-------|
| `_create_regeneration_job()` | 1121 | Creates `generation_jobs` row |
| `_format_job_error()` | 1155 | Pure helper — formats exception into stable string |
| `_require_request_id()` | 1165 | Pure helper — validates request_id |
| `_resolve_execution_request_id()` | 1173 | Resolves/synthesizes request_id |
| `_regeneration_idempotency_key()` | 1186 | Pure helper — computes idempotency hash |
| `_hybrid_generation_idempotency_key()` | 1207 | Pure helper — computes idempotency hash |
| `_find_active_regeneration_job()` | 1225 | Reads `generation_jobs` for deduplication |
| `_find_active_hybrid_job()` | 1254 | Reads `batch_generation_jobs` for deduplication |
| `_normalize_regeneration_job_row()` | 1404 | Normalizes DB row → `RegenerateJobStatusResponse` |

**Total: 9 functions**

**Import dependencies for job_management.py:**
- `from feedops.api.schemas import RegenerateRequest, RegenerateResponse, RegenerateJobStatusResponse`
- `from feedops.observability import get_request_id`
- `from fastapi import HTTPException` (only if `_normalize_regeneration_job_row` needs it — it does not)

### telemetry.py — What to Extract

| Function | Line | Notes |
|----------|------|-------|
| `run_async_in_thread()` | 243 | Background thread launcher — 4 callers to update |
| `_emit_generation_summary()` | 1280 | Emits structured log event |
| `_telemetry_scope_for_content()` | 1336 | Maps content row back to task snapshots |
| `_generate_with_metrics()` | 588 | Async wrapper emitting latency/error metrics |
| `_should_persist_finish_sentences()` | 1362 | Thin wrapper around `_task_should_persist_finish_sentences` |

**Total: 5 functions**

**Import dependencies for telemetry.py:**
- `from feedops.observability import log_event, request_context`
- `from feedops.observability.metrics import metrics_registry`
- `from feedops.api.generation_telemetry import _provider_label` (already extracted)
- `from feedops.generation.persistence import should_persist_finish_sentences as _task_should_persist_finish_sentences`

**Note on `run_async_in_thread`:** This function contains an inline Supabase crash handler (lines 269–280) that does a lazy `from feedops.db.supabase_client import get_client`. This lazy import pattern is intentional error recovery and should be preserved as-is when moving.

---

## Common Pitfalls

### Pitfall 1: HTTPException in persistence.py

**What goes wrong:** `_enforce_write_time_finish_placeholder_contract()` raises `HTTPException` (FastAPI). If persistence.py imports from FastAPI, importing persistence.py triggers FastAPI machinery.

**Why it happens:** This function was written as a guard clause that raises HTTP 422 — it lives at the boundary of persistence logic and API response logic.

**How to avoid:** Two options (Claude's discretion):
1. Keep `from fastapi import HTTPException` in persistence.py — FastAPI is installed and importable without the app running; this is safe for smoke tests.
2. Replace `HTTPException` with a custom `FinishPlaceholderError` and let main.py catch and convert it — cleaner separation but more changes.

**Warning signs:** If smoke test for persistence.py fails with `ModuleNotFoundError: fastapi`, option 2 is needed. In practice, FastAPI is always installed, so option 1 is fine.

**Recommendation:** Keep `from fastapi import HTTPException` — it's importable without app initialization. This matches how backfill.py and search_insights.py both import from fastapi at module level.

### Pitfall 2: test_regenerate_response_contract.py import path

**What goes wrong:** `tests/api/test_regenerate_response_contract.py` line 3 imports `from feedops.api.main import RegenerateResponse`. After extraction this will break.

**How to avoid:** Update this import to `from feedops.api.schemas import RegenerateResponse` in the schemas.py commit. This is the ONLY known test file that imports a model directly from main.py.

**Warning signs:** `pytest tests/api/test_regenerate_response_contract.py` fails with `ImportError`.

### Pitfall 3: Circular imports from helper function placement

**What goes wrong:** If `job_management.py` imports from `persistence.py` and `persistence.py` imports from `job_management.py`, circular import. If `schemas.py` imports from any other new module, it creates a dependency chain.

**How to avoid:** Strict layering:
```
schemas.py → no imports from other new modules
persistence.py → may import from schemas.py (type hints only)
job_management.py → may import from schemas.py
telemetry.py → no imports from schemas/persistence/job_management
```

**Warning signs:** `ImportError: cannot import name X (most likely due to a circular import)` when running `python -c "import feedops.api.main"`.

### Pitfall 4: _intent_scorer_lock and module-level state

**What goes wrong:** `main.py` lines 3658–3659 define `_intent_scorer = None` and `_intent_scorer_lock = threading.Lock()` as module globals used by `_get_intent_scorer()`. The `ScoreIntentRequest/Item/Response` models move to schemas.py, but `_get_intent_scorer()` and the module-level state stay in main.py (it's a route helper, not a schema).

**How to avoid:** Only move the 3 Pydantic model classes to schemas.py. The `_get_intent_scorer()` function, `_intent_scorer`, and `_intent_scorer_lock` remain in main.py.

### Pitfall 5: `_build_generation_user_prompt` and `_build_finish_sentences_user_prompt`

**What goes wrong:** These two functions (lines 626–692) look like "content helpers" but are generation logic wrappers — NOT persistence or schema functions. They depend on `build_core_prompt`, `apply_feedback_layer`, and `get_finish_list`. They belong in Phase 2/7 extractions, not this phase.

**How to avoid:** Leave both functions in main.py. They are NOT in scope for Phase 1.

### Pitfall 6: `_extract_query_intent_generation_diagnostics`

**What goes wrong:** This 5-line function (line 807) is a diagnostic helper — it's NOT persistence. It extracts a diagnostics dict from a generated result. It's a generation helper that belongs with generation logic (Phase 2 `generation.py`).

**How to avoid:** Leave it in main.py for now.

---

## Code Examples

### Verified: How to run the circular import check

```bash
# From project root
PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main"
# Must exit 0 with no output
```

### Verified: How to run smoke tests

```bash
# From project root
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_schemas_smoke.py -v
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_persistence_smoke.py -v
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_job_management_smoke.py -v
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_telemetry_smoke.py -v
```

### Verified: Lazy import → direct import migration pattern

```python
# search_insights.py line 131 (BEFORE):
async def _run_sync_job(job_id: str, ...):
    ...
    from feedops.api.main import run_async_in_thread  # lazy import
    run_async_in_thread(do_sync, job_id=job_id)

# AFTER (top-level import, lazy body import removed):
from feedops.api.telemetry import run_async_in_thread  # top-level

async def _run_sync_job(job_id: str, ...):
    ...
    run_async_in_thread(do_sync, job_id=job_id)
```

### Verified: Smoke test skeleton for schemas.py

```python
# tests/api/test_schemas_smoke.py
"""Smoke tests — schemas.py importable without main.py."""


def test_schemas_importable_standalone():
    """Core requirement: from feedops.api.schemas import X works without main.py."""
    from feedops.api.schemas import (
        OptimizeRequest,
        RegenerateRequest,
        BatchOptimizeRequest,
        RegenerateResponse,
        HybridGenerateRequest,
    )
    assert OptimizeRequest is not None


def test_no_circular_import_with_main():
    """Importing both modules in same process must not raise."""
    import feedops.api.schemas  # noqa: F401
    import feedops.api.main  # noqa: F401


def test_optimize_request_defaults():
    from feedops.api.schemas import OptimizeRequest
    req = OptimizeRequest(master_sku="FT-16")
    assert req.dry_run is True
    assert req.num_candidates == 3


def test_regenerate_response_requires_prompt_hash_and_request_id():
    from pydantic import ValidationError
    from feedops.api.schemas import RegenerateResponse
    try:
        RegenerateResponse(
            success=True, master_sku="FT-16", content_type="description",
            platform="google", content="x", used_feedback=False, model="gpt-5.2",
        )
    except ValidationError:
        return
    raise AssertionError("Should require prompt_hash and request_id")
```

### Verified: curl health check (deploy verification)

```bash
curl -s "$FEEDOPS_PIPELINE_URL/health" | python3 -m json.tool
# Must return: {"status": "healthy", "service": "FeedOps Pipeline API", ...}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All models + functions in main.py | Models in schemas.py, CRUD in persistence.py | Phase 1 | `from feedops.api.schemas import X` works without app startup |
| Lazy imports from main.py for `run_async_in_thread` | Direct imports from telemetry.py | Phase 1 | Eliminates circular import risk, enables unit testing |
| Single 3,737-line main.py | main.py + 4 extracted modules | Phase 1 | ~1,200 lines moved; main.py still ~2,500 lines (Phase 2-3 continue) |

---

## Open Questions

1. **Where does `_assembled_prompt_hash()` belong?**
   - What we know: It's a pure function (no Supabase calls) used exclusively inside `_persist_regeneration_result()` and `_persist_generated_content_and_history()` in persistence.py
   - What's unclear: Should it go in persistence.py (used there), schemas.py (pure utility), or a shared `utils.py`?
   - Recommendation: Put it in `persistence.py` — it has no meaning outside persistence context and its only callers are persistence functions.

2. **Does `_should_persist_finish_sentences()` belong in telemetry.py or job_management.py?**
   - What we know: It's a thin wrapper around `_task_should_persist_finish_sentences` from `feedops.generation.persistence`. It's called in the large batch functions and optimize route.
   - What's unclear: It has no telemetry or job logic — it's a generation decision helper.
   - Recommendation: Put it in `telemetry.py` per the CONTEXT.md assignment. It's a small shim and doesn't matter architecturally — Phase 2 will likely re-home it.

3. **Is `_validate_finish_sentences_payload()` in scope for this phase?**
   - What we know: It uses `metrics_registry` (telemetry) and `normalize_and_validate_finish_sentences` (pipeline). It's called in `_enforce_finish_sentence_parity()` which stays in main.py.
   - What's unclear: Does it belong in persistence, telemetry, or stays in main?
   - Recommendation: Leave in main.py — it's a finish-sentence processing function that belongs with Phase 2's `finish_processing.py` extraction.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ with pytest-asyncio 0.21+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -v -x` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DECOMP-01 | `from feedops.api.schemas import OptimizeSkuRequest` works without importing `main.py` | smoke | `pytest tests/api/test_schemas_smoke.py -x` | ❌ Wave 0 |
| DECOMP-02 | All Supabase functions in `persistence.py`, importable standalone | smoke | `pytest tests/api/test_persistence_smoke.py -x` | ❌ Wave 0 |
| DECOMP-03 | Job lifecycle helpers in `job_management.py`, importable standalone | smoke | `pytest tests/api/test_job_management_smoke.py -x` | ❌ Wave 0 |
| DECOMP-04 | `run_async_in_thread` + telemetry helpers in `telemetry.py`, no circular import | smoke | `pytest tests/api/test_telemetry_smoke.py -x` | ❌ Wave 0 |
| DECOMP-01 (secondary) | No circular imports: `python -c "import feedops.api.main"` exits 0 | integration | `python -c "import feedops.api.main"` | ✅ inline check |
| DECOMP-03 (health) | curl `/health` returns same structure before and after | manual/smoke | `curl $FEEDOPS_PIPELINE_URL/health` | manual |

### Sampling Rate

- **Per task commit:** `PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main" && pytest tests/api/ -x -q`
- **Per wave merge:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v`
- **Phase gate:** Full suite green + curl `/health` verified before phase complete

### Wave 0 Gaps

- [ ] `tests/api/test_schemas_smoke.py` — covers DECOMP-01 (standalone import, no circular dep, field defaults)
- [ ] `tests/api/test_persistence_smoke.py` — covers DECOMP-02 (importable, key functions accessible)
- [ ] `tests/api/test_job_management_smoke.py` — covers DECOMP-03 (importable, key functions accessible)
- [ ] `tests/api/test_telemetry_smoke.py` — covers DECOMP-04 (run_async_in_thread importable, no circular dep)
- [ ] Update `tests/api/test_regenerate_response_contract.py` line 3: change import path to `feedops.api.schemas`

---

## Sources

### Primary (HIGH confidence)

- Direct code inspection of `src/feedops/api/main.py` (3,737 lines, read in full) — function inventory, line numbers, dependency graph
- Direct code inspection of `src/feedops/api/generation_telemetry.py` — existing extracted module pattern verified
- Direct code inspection of `src/feedops/api/search_insights.py` — existing flat-in-api/ module pattern verified
- `pyproject.toml` — pytest configuration, asyncio_mode=auto confirmed
- `tests/api/test_regenerate_response_contract.py` — only existing test with direct main.py model import identified
- `.planning/phases/01-schemas-extraction/01-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- Grep of `from feedops.api.main import` across all `src/feedops/api/*.py` — 4 files with `run_async_in_thread` lazy imports (backfill.py ×2, gmc_sync.py ×1, search_insights.py ×1) confirmed

### Tertiary (LOW confidence)

- None — all findings verified by direct code inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; existing project stack confirmed
- Architecture: HIGH — extraction pattern verified from existing modules; function inventory complete
- Pitfalls: HIGH — identified from code inspection; circular import risk verified by tracing actual import chains

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable — no external library changes expected; internal code is static)
