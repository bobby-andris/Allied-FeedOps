# Phase 3: JobRunner and Route Extraction - Research

**Researched:** 2026-03-03
**Domain:** Python async background job unification, FastAPI route extraction, threading patterns
**Confidence:** HIGH — all findings based on direct codebase inspection

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

None — all structural decisions are delegated to Claude. This is a mechanical refactoring following patterns established in Phases 1-2.

### Claude's Discretion

- **JobRunner class design**: How to unify batch and hybrid processing (strategy pattern, mode flag, shared base class, etc.)
- **Regeneration job scope**: Whether `process_regenerate_job()` is unified into JobRunner or remains separate
- **Route file organization**: How to split routes out of main.py to hit <500 lines (single router file vs domain-split files)
- **Job cancellation mechanism**: How to implement JOBS-05 (threading events, global registry, etc.)
- **Variant adaptation integration**: Where hybrid-specific variant adaptation logic lives within the unified runner
- **Progress tracking**: How to handle the different progress models (batch vs hybrid)

### Carried from Phases 1-2

- All modules flat in `src/feedops/api/` — no subdirectories
- Clean break imports, no re-exports from main.py
- Preserve exact function signatures during extraction
- One commit per logical extraction
- Pytest verification after each extraction

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DECOMP-09 | Reduce `main.py` to <500 lines (route definitions and request handling only) | Route extraction plan: move routes to `routes.py`; JobRunner moves jobs. Combined brings main.py to ~250 lines. |
| JOBS-01 | Replace `process_batch_job()` and `process_hybrid_batch_job()` with unified `JobRunner` class | Both functions share ~60% logic; unified class with `mode` enum or strategy is cleanest separation |
| JOBS-02 | Single job processing loop with batch/hybrid mode flag | `JobRunner.run()` dispatches on mode — single loop for shared SKU iteration, strategy for mode-specific steps |
| JOBS-03 | Shared retry logic, error handling, and status updates | `_upsert_batch_job_sku_status()` + `_emit_generation_summary()` are already extracted; JobRunner composes them |
| JOBS-04 | Configurable SKU processing strategy (full generation vs variant adaptation) | Two strategies: `FullGenerationStrategy` (batch + hybrid base SKUs) and `VariantAdaptationStrategy` (hybrid variants) |
| JOBS-05 | Proper cancellation support and graceful shutdown | `threading.Event` sentinel on `JobRunner`; check before each SKU; no new external dependencies |
| JOBS-06 | Batch and hybrid generation produce identical results to current implementation | Parity contract test: run both old and new paths with identical mocks, compare DB write calls |
</phase_requirements>

---

## Summary

Phase 3 has two distinct sub-problems that must both be solved to reach the DECOMP-09 line-count target: (1) unify the two background job processor functions into a `JobRunner` class, and (2) extract route handlers out of `main.py` into a separate router module.

The critical math: removing `process_batch_job()` (279 lines) and `process_hybrid_batch_job()` (538 lines) saves 817 lines but the remaining route handlers still total ~859 lines plus ~347 lines of setup — far exceeding the 500-line target. Route extraction is not optional; it is required to hit DECOMP-09.

The two job processors share approximately 60% of their logic: job status initialization, SKU status tracking, `generate_per_platform()` invocation with `asyncio.wait_for(timeout=300.0)`, content persistence loop, telemetry emission, finish sentence persistence, and final job status update. The 40% that differs is: (a) progress tracking model (simple counters vs requested/expanded scope with overflow invariant) and (b) hybrid-only variant adaptation after base SKU generation. A `JobRunner` class with a mode enum cleanly separates these. The regeneration job (`process_regenerate_job`) is structurally different (single SKU, uses `_execute_regeneration_request()`) and should remain separate — JOBS-01 only specifies batch+hybrid.

**Primary recommendation:** Two-plan phase. Plan 03-01: extract `JobRunner` to `job_runner.py` (JOBS-01 through JOBS-06). Plan 03-02: extract route handlers to `routes.py` and register via `app.include_router()` (DECOMP-09). Both plans follow the established one-commit-per-extraction pattern with pytest verification.

---

## Standard Stack

### Core (already in use — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` | stdlib | Async job loop, `wait_for()` timeout | Already used in both job processors |
| `threading.Thread` | stdlib | Non-daemon background threads for Cloud Run | `run_async_in_thread()` already established pattern |
| `threading.Event` | stdlib | Cancellation sentinel for JOBS-05 | Standard Python cancellation pattern; no third-party needed |
| `fastapi.APIRouter` | 0.115.x | Route group extraction | Already used by `intent_scoring.py`, `search_insights.py`, `monitoring.py` |
| `pytest-asyncio` | installed | Async test support | `asyncio_mode = "auto"` in pyproject.toml |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime.timezone.utc` | stdlib | Timestamps in job updates | All job status writes use `datetime.now(timezone.utc).isoformat()` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `threading.Event` for cancellation | Global dict `{job_id: cancel_flag}` | Registry is more complex but allows per-job cancellation from HTTP endpoint; Event is simpler and sufficient for graceful shutdown |
| Single `routes.py` router | Domain-split routers (`generation_routes.py`, `status_routes.py`) | Single file is 859 lines but still cleaner than in main.py; domain split adds files without clear benefit for this phase |
| Strategy pattern for JobRunner | `if mode == "batch"` branching | Strategy is more extensible but more complex; mode flag is sufficient and matches JOBS-02 literal requirement |

---

## Architecture Patterns

### Recommended Project Structure (after Phase 3)

```
src/feedops/api/
├── main.py           # <500 lines: app setup, lifespan, middleware, router mounts only
├── routes.py         # Route handler functions (optimize-sku, regenerate, batch, hybrid, images)
├── job_runner.py     # NEW: JobRunner class (JOBS-01 through JOBS-05)
├── schemas.py        # Phase 1: Pydantic models (unchanged)
├── persistence.py    # Phase 1: DB CRUD (unchanged)
├── job_management.py # Phase 1: Job lifecycle helpers (unchanged)
├── telemetry.py      # Phase 1: run_async_in_thread, _emit_generation_summary (unchanged)
├── generation.py     # Phase 2: _execute_regeneration_request (unchanged)
├── finish_processing.py  # Phase 2: finish sentence helpers (unchanged)
├── intent_scoring.py # Phase 2: APIRouter-based (unchanged)
└── ...               # All other existing modules (unchanged)
```

### Pattern 1: APIRouter for Route Extraction

**What:** Move all `@app.get`/`@app.post` route handlers from `main.py` into a new `routes.py` module using `APIRouter`. Register with `app.include_router()` in `main.py`.

**When to use:** Established pattern — `intent_scoring.py`, `search_insights.py`, `monitoring.py`, `performance_baseline.py`, `gmc_sync.py` all use this exact pattern.

**Example (from existing intent_scoring.py pattern):**
```python
# src/feedops/api/routes.py
from fastapi import APIRouter
from feedops.api.job_runner import JobRunner
from feedops.api.telemetry import run_async_in_thread
# ... all other imports currently in main.py route handler bodies

router = APIRouter()

@router.post("/batch-optimize", response_model=BatchJobResponse, tags=["Generation"])
async def batch_optimize(request: BatchOptimizeRequest):
    ...
    run_async_in_thread(
        JobRunner(mode="batch").run,
        request_id=get_request_id(),
        job_id=job_id,
        ...
    )
    ...

# In main.py:
from feedops.api.routes import router as main_router
app.include_router(main_router)
```

**Critical:** `process_regenerate_job` is called via `run_async_in_thread` from `regenerate_content` route. When routes move to `routes.py`, `process_regenerate_job` must move with them (it is an internal implementation detail of the regenerate route, not a shared job processor).

### Pattern 2: JobRunner with Mode Enum

**What:** Single class replacing both `process_batch_job()` and `process_hybrid_batch_job()`. Mode determines which processing strategy is used for each SKU.

**When to use:** JOBS-01 + JOBS-02 mandate this specific consolidation.

**Recommended design:**
```python
# src/feedops/api/job_runner.py
import asyncio
import threading
from datetime import datetime, timezone
import logging

from feedops.api.persistence import _persist_generated_content_and_history, _upsert_batch_job_sku_status, _persist_finish_prompt_lineage
from feedops.api.telemetry import _emit_generation_summary, _telemetry_scope_for_content, _should_persist_finish_sentences
from feedops.api.schemas import _normalize_generation_options, _content_field_key
from feedops.api.job_management import _resolve_execution_request_id
from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.api.runtime_controls import ensure_generation_enabled
from feedops.api.prompt_loader import get_platform_system_prompt_hash
from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
from feedops.api.generation_telemetry import provider_label as _provider_label
from feedops.api.telemetry import _extract_scoped_telemetry
from feedops.api.hybrid_generation import adapt_variant_content, extract_spec_difference
from feedops.db.supabase_client import get_client
from feedops.providers import get_provider
from feedops.providers.base import close_provider
from feedops.pipeline.generator import generate_per_platform
from feedops.generation.persistence import persist_finish_sentences
from feedops.observability import log_event

logger = logging.getLogger(__name__)


class JobRunner:
    """Unified background job processor for batch and hybrid generation jobs."""

    def __init__(self, mode: str, cancel_event: threading.Event | None = None):
        """
        Args:
            mode: "batch" or "hybrid"
            cancel_event: Optional threading.Event for graceful cancellation.
                          Checked before each SKU. If set, job terminates cleanly.
        """
        assert mode in ("batch", "hybrid"), f"Unknown mode: {mode}"
        self.mode = mode
        self.cancel_event = cancel_event or threading.Event()

    async def run(self, *, job_id: str, **kwargs) -> None:
        """Entry point called by run_async_in_thread()."""
        if self.mode == "batch":
            await self._run_batch(job_id=job_id, **kwargs)
        else:
            await self._run_hybrid(job_id=job_id, **kwargs)

    def _is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    async def _generate_full_sku(self, *, supabase, provider, sku, platforms, content_types, lineage_request_id, job_id, request_id, options=None) -> dict:
        """Shared full generation + persistence for a single SKU (used by both modes)."""
        # ... extracted from generate_full_content_v2 in process_hybrid_batch_job
        # ... and the SKU loop body in process_batch_job
        ...

    async def _run_batch(self, *, job_id: str, skus: list[str], num_candidates: int, dry_run: bool, options: dict | None = None) -> None:
        """Batch mode: simple counter tracking, direct SKU list."""
        # ... body of process_batch_job (unchanged logic)

    async def _run_hybrid(self, *, job_id: str, families: list, single_skus: list[str], options: dict, requested_skus: list[str] | None = None) -> None:
        """Hybrid mode: requested/expanded scope tracking, variant adaptation after base."""
        # ... body of process_hybrid_batch_job (unchanged logic)
```

### Pattern 3: Cancellation via threading.Event

**What:** `threading.Event` flag checked at the start of each SKU iteration. If set, the job updates status to "cancelled" and returns cleanly.

**Why:** No new dependencies. Integrates with existing `run_async_in_thread()` pattern. Graceful shutdown means in-progress SKU completes; the next SKU check catches cancellation.

**Implementation:**
```python
# In JobRunner._run_batch / _run_hybrid, at top of SKU loop:
for sku in skus:
    if self._is_cancelled():
        logger.info("Job %s cancelled before processing %s", job_id, sku)
        break  # exit loop cleanly
    # ... process sku
```

**Shutdown hook (optional, for graceful container shutdown):**
```python
# In telemetry.py or job_runner.py:
_active_job_runners: dict[str, "JobRunner"] = {}

def register_runner(job_id: str, runner: "JobRunner") -> None:
    _active_job_runners[job_id] = runner

def cancel_runner(job_id: str) -> bool:
    runner = _active_job_runners.pop(job_id, None)
    if runner:
        runner.cancel_event.set()
        return True
    return False
```

### Anti-Patterns to Avoid

- **Passing `supabase` client as constructor param to JobRunner:** The established pattern is `get_client()` called at start of run. All existing extracted modules use this — do not change it.
- **Moving `_app_lifespan` to routes.py:** It must stay in main.py — it is the app startup hook.
- **Moving CORS/middleware to routes.py:** Middleware is app-level; stays in main.py.
- **Re-exporting from main.py:** Clean break — no backward-compat shims in main.py after extraction.
- **Calling `run_async_in_thread(process_batch_job, ...)` after extraction:** Route handlers in `routes.py` must call `run_async_in_thread(JobRunner(mode="batch").run, ...)` — the old function names cannot remain.
- **Forgetting dual-namespace monkeypatching in tests:** Phase 02-02 established that after extraction, tests must patch at BOTH `api_main` and the new module. For JobRunner tests, patch at `feedops.api.job_runner`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async-to-thread bridging | Custom thread pool manager | `run_async_in_thread()` (already in telemetry.py) | Already handles event loop lifecycle, daemon=False guarantee, crash recovery |
| Job status persistence | Custom status tracker | `_upsert_batch_job_sku_status()` (persistence.py) | Already extracted, tested, handles all edge cases |
| Cancellation UI endpoint | New HTTP endpoint for cancel | Optional: test cancel via threading.Event directly | JOBS-05 spec says "graceful shutdown", not "HTTP cancel API" — threading.Event is sufficient |
| Progress tracking | New table/model | Existing `batch_generation_jobs.options` JSONB | Hybrid already stores `expanded_completed_skus` etc. in options blob |

---

## Common Pitfalls

### Pitfall 1: Route Extraction Leaves main.py Too Large Without Route Splitting

**What goes wrong:** Developers move only the job processors (817 lines) and declare success, but `main.py` still has 1,159 lines — far over 500.

**Why it happens:** The 500-line target is easily met by moving just the jobs IF you count only jobs. But the route handlers are 859 lines by themselves.

**How to avoid:** Plan 03-02 explicitly targets route extraction. The math: after moving jobs AND routes, main.py contains only app setup (~250 lines) + imports trimmed to essentials. Target: ~200-250 lines.

**Verified line counts (as of Phase 3 start):**
- `process_batch_job()`: lines 1208-1486 = 279 lines
- `process_hybrid_batch_job()`: lines 1488-2025 = 538 lines
- Route handlers (optimize-sku, regenerate, images, batch, hybrid, backfill stubs): ~909 lines
- App setup (imports, lifespan, middleware, router mounts): ~347 lines
- **Total: 2,075 lines**

### Pitfall 2: `generate_full_content_v2` Inner Function Closure

**What goes wrong:** In `process_hybrid_batch_job`, `generate_full_content_v2` is an inner `async def` that closes over `supabase`, `provider`, `platforms`, `content_types`, `lineage_request_id`, `job_id`, `request_id`, `options`. When extracting to JobRunner, these captured variables must become explicit parameters or instance variables.

**Why it happens:** The inner function is a convenience closure — it works in-place but breaks as a standalone method.

**How to avoid:** Convert to `async def _generate_full_sku(self, *, supabase, provider, sku, platforms, content_types, lineage_request_id, job_id, request_id, options)` — pass all formerly-captured variables explicitly. This is safer than storing them on `self` (avoids state mutation bugs in async).

### Pitfall 3: `adapt_variant_content` Import Already in main.py as `noqa: F401`

**What goes wrong:** `hybrid_generation.py`'s `adapt_variant_content` is imported in `main.py` with `# noqa: F401 - re-exported for test patching compatibility`. If tests patch `feedops.api.main.adapt_variant_content`, and routes move to `routes.py`, those patches will fail silently.

**Why it happens:** Test patching uses the module where the name is bound, not where it was defined.

**How to avoid:** When extracting routes, check `tests/` for any `patch("feedops.api.main.adapt_variant_content", ...)`. Move the re-export line to `routes.py` if needed, or patch at `feedops.api.hybrid_generation.adapt_variant_content` directly (more correct).

### Pitfall 4: `process_regenerate_job` Scope

**What goes wrong:** `process_regenerate_job` (lines 595-704) is invoked by `regenerate_content` route handler (lines 706-823) via `run_async_in_thread(process_regenerate_job, ...)`. If routes move to `routes.py` but `process_regenerate_job` stays in `main.py`, there's a circular import.

**Why it happens:** `routes.py` would need to import from `main.py`.

**How to avoid:** Move `process_regenerate_job` to `routes.py` alongside the `regenerate_content` route that calls it. It is not a shared utility — it is an internal implementation detail of that one route.

### Pitfall 5: Progress Overflow Invariant (Hybrid-Specific)

**What goes wrong:** The hybrid job has a strict invariant enforced by `_update_job_progress(enforce_invariant=True)` — `processed_requested` must not exceed `requested_total`. This logic is unique to hybrid mode and must not be applied to batch mode.

**Why it happens:** Developers merge the two modes too aggressively into a single loop, applying hybrid's overflow check to batch.

**How to avoid:** Keep `_run_batch()` and `_run_hybrid()` as separate methods in JobRunner. Share the SKU generation logic (`_generate_full_sku()`) but keep progress tracking mode-specific.

### Pitfall 6: Batch Route Imports `_normalize_generation_options` from `schemas.py`

**What goes wrong:** `batch_optimize` route calls `_normalize_generation_options(request.options)`. If this import is missed when extracting routes, the import in `routes.py` will fail.

**Why it happens:** `_normalize_generation_options` is imported at the top of `main.py` with the schemas import block. It's easy to miss when transcribing route handler imports.

**How to avoid:** Do a full import audit before extracting. All names used in route handlers that come from `main.py`'s top-level imports must be re-imported in `routes.py`.

### Pitfall 7: Backfill Stubs Import from `backfill.py` at Module Level in main.py

**What goes wrong:** Lines 234-244 of `main.py` import `StartBackfillRequest`, `BackfillJobResponse`, etc. from `feedops.api.backfill`. The 5 backfill route stubs at lines 2031-2065 use these. If backfill stubs move to `routes.py`, they must bring these imports.

**How to avoid:** Move backfill stub routes to `routes.py` with explicit `from feedops.api.backfill import ...`.

---

## Code Examples

### Verified Pattern: APIRouter Already Used in intent_scoring.py

```python
# Source: src/feedops/api/intent_scoring.py (Phase 2 extraction)
from fastapi import APIRouter
router = APIRouter()

@router.post("/score-intent", ...)
async def api_score_intent(request: ScoreIntentRequest):
    ...

# In main.py:
from feedops.api.intent_scoring import router as intent_scoring_router
app.include_router(intent_scoring_router)
```

This is the exact pattern `routes.py` should follow.

### Verified Pattern: run_async_in_thread Usage

```python
# Source: src/feedops/api/main.py lines 966-975 (batch route)
run_async_in_thread(
    process_batch_job,          # becomes: JobRunner(mode="batch").run
    request_id=get_request_id(),
    job_id=job_id,
    skus=canonical_skus,
    num_candidates=request.num_candidates,
    dry_run=request.dry_run,
    options=options,
)
```

After extraction, the call site changes to:
```python
run_async_in_thread(
    JobRunner(mode="batch").run,
    request_id=get_request_id(),
    job_id=job_id,
    skus=canonical_skus,
    num_candidates=request.num_candidates,
    dry_run=request.dry_run,
    options=options,
)
```

The `run_async_in_thread` signature is `(async_func, request_id=None, **kwargs)` — `run()` receives `**kwargs` so all named args pass through correctly.

### Verified Pattern: Cancellation Check (to implement)

```python
# In JobRunner._run_batch():
for sku in skus:
    if self.cancel_event.is_set():
        logger.info("Job %s: cancellation requested before %s, stopping.", job_id, sku)
        supabase.table("batch_generation_jobs").update({
            "status": "failed",
            "error_message": "Job cancelled",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        return
    # ... rest of SKU processing
```

### Verified Pattern: Smoke Test Structure (matches Phase 1-2 pattern)

```python
# tests/api/test_job_runner_smoke.py
def test_job_runner_importable_standalone():
    from feedops.api.job_runner import JobRunner
    runner = JobRunner(mode="batch")
    assert callable(runner.run)

def test_no_circular_import_with_main():
    import feedops.api.job_runner
    import feedops.api.main

def test_cancel_event_respected():
    import threading
    from feedops.api.job_runner import JobRunner
    event = threading.Event()
    runner = JobRunner(mode="batch", cancel_event=event)
    assert not runner._is_cancelled()
    event.set()
    assert runner._is_cancelled()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `process_batch_job()` as top-level async function | `JobRunner(mode="batch").run()` method | Phase 3 | Enables shared logic, cancellation, easier testing |
| Routes defined directly on `app` with `@app.post` | Routes via `APIRouter` + `include_router()` | Phase 3 (for generation routes) | Already done for intent_scoring, monitoring, perf_baseline |
| 2,075-line monolith | main.py <500 lines, routes in routes.py, jobs in job_runner.py | Phase 3 | Modular isolation makes future bug fixes and Phase 4-6 work safer |

---

## Open Questions

1. **Should `process_regenerate_job` move into JobRunner as a third mode ("regenerate")?**
   - What we know: JOBS-01 says batch+hybrid only. `process_regenerate_job` uses `_execute_regeneration_request()` (a completely different code path from `generate_per_platform()`).
   - What's unclear: Whether the cancellation/status-tracking benefits of JobRunner would help the regen job.
   - Recommendation: Leave it out of JobRunner. Move it to `routes.py` alongside the `regenerate_content` route that calls it. Revisit in a future phase if needed.

2. **Route file name: `routes.py` vs `generation_routes.py` vs `main_routes.py`?**
   - What we know: All other extracted routers are named by domain (`intent_scoring.py`, `search_insights.py`). The routes remaining in main.py don't have a single clean domain name.
   - Recommendation: `routes.py` — simple, unambiguous, matches the role as "the primary routes formerly in main.py."

3. **How many plans does Phase 3 need?**
   - What we know: Two distinct extractions (JobRunner and route extraction), each ~300-500 lines of new/moved code.
   - Recommendation: Two plans — Plan 03-01 (JobRunner extraction), Plan 03-02 (route extraction to routes.py). Same pattern as Phase 2's two plans.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -x -q` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DECOMP-09 | `main.py` is under 500 lines | smoke/assertion | `pytest tests/api/test_main_line_count.py -x` | ❌ Wave 0 |
| JOBS-01 | `JobRunner` class exists; `process_batch_job`/`process_hybrid_batch_job` do not exist in codebase | smoke | `pytest tests/api/test_job_runner_smoke.py -x` | ❌ Wave 0 |
| JOBS-02 | Single `run()` method dispatches on `mode` flag | unit | `pytest tests/api/test_job_runner_smoke.py::test_run_dispatches_on_mode -x` | ❌ Wave 0 |
| JOBS-03 | Shared status updates use `_upsert_batch_job_sku_status()` | unit (mock) | `pytest tests/api/test_job_runner_smoke.py::test_shared_status_updates -x` | ❌ Wave 0 |
| JOBS-04 | Variant adaptation called for hybrid variants, not for batch | unit (mock) | `pytest tests/api/test_job_runner_smoke.py::test_variant_adaptation_strategy -x` | ❌ Wave 0 |
| JOBS-05 | `cancel_event.set()` stops processing at next SKU boundary | unit | `pytest tests/api/test_job_runner_smoke.py::test_cancel_event_respected -x` | ❌ Wave 0 |
| JOBS-06 | Batch job DB writes match pre-extraction behavior | parity (mock) | `pytest tests/api/test_job_runner_smoke.py::test_batch_parity -x` | ❌ Wave 0 |
| JOBS-06 | Hybrid job DB writes match pre-extraction behavior | parity (mock) | `pytest tests/api/test_job_runner_smoke.py::test_hybrid_parity -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -x -q`
- **Per wave merge:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/api/test_job_runner_smoke.py` — covers JOBS-01 through JOBS-06
- [ ] `tests/api/test_main_line_count.py` — covers DECOMP-09 (simple assertion: `wc -l main.py < 500`)

*(Existing test infrastructure covers all other requirements — `tests/conftest.py`, `asyncio_mode = "auto"`, pytest-asyncio are all configured.)*

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection — `src/feedops/api/main.py` (2,075 lines, read completely)
- Direct codebase inspection — `src/feedops/api/telemetry.py`, `job_management.py`, `generation.py`, `hybrid_generation.py`
- Direct codebase inspection — `tests/api/test_job_management_smoke.py`, `test_generation.py`, `test_persistence_smoke.py` (existing test patterns)
- `pyproject.toml` `[tool.pytest.ini_options]` — test config verified

### Secondary (MEDIUM confidence)

- FastAPI APIRouter pattern — verified from `src/feedops/api/intent_scoring.py` (Phase 2 extraction, working in production)

### Tertiary (LOW confidence)

- None — all findings are from direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all patterns already in codebase
- Architecture: HIGH — based on direct line-count analysis and existing extraction patterns
- Pitfalls: HIGH — derived from actual code structure, closure analysis, and import chain inspection

**Research date:** 2026-03-03
**Valid until:** Until Phase 3 planning begins (stable codebase, no expiry)
