# Phase 1: Schemas Extraction - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract all Pydantic request/response models, Supabase CRUD functions, job lifecycle helpers, and telemetry/metrics functions from the 3,737-line `main.py` into four isolated modules. main.py retains route definitions, request handling, and the two large batch processing functions. No behavior changes — purely structural.

</domain>

<decisions>
## Implementation Decisions

### Module boundaries
- Extract ALL four modules in Phase 1: `schemas.py`, `persistence.py`, `job_management.py`, `telemetry.py`
- All modules live flat in `src/feedops/api/` alongside main.py (matches existing pattern — prompt_loader.py, search_insights.py already there)
- `persistence.py` gets CRUD functions only — Supabase client initialization stays in main.py's lifespan, passed as parameter
- `job_management.py` gets lifecycle helpers only (job creation, status tracking, idempotency checks, error formatting) — the big `process_batch_job()` and `process_hybrid_batch_job()` stay in main.py until Phase 3 unifies them into JobRunner

### Import strategy
- Clean break: update all callers to import from new modules directly, no re-exports from main.py
- 3 files need updating for `run_async_in_thread`: search_insights.py, gmc_sync.py, backfill.py
- Named imports for schemas: `from feedops.api.schemas import OptimizeRequest, BatchOptimizeRequest`
- Preserve exact function signatures during move — zero signature changes, type hint improvements are a separate concern

### Test approach
- Smoke tests only: one test file per extracted module verifying imports work, no circular dependencies, key classes/functions accessible (~5-10 tests total)
- Full contract testing deferred to Phase 2 (DECOMP-11)

### Commit strategy
- One commit per module (4 commits): schemas.py, persistence.py, job_management.py, telemetry.py
- Each commit independently reviewable and revertable
- Local verification after each extraction (pytest + `python -c 'import feedops.api.main'`)
- Single deploy + curl verification after all 4 modules extracted

### Claude's Discretion
- Exact function grouping within each module (which helpers go where)
- Internal module organization (ordering, grouping by concern)
- Smoke test specifics (which assertions, which edge cases)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/feedops/providers/base.py`: Already has `LLMProvider` ABC and factory — good pattern to follow for module interfaces
- `src/feedops/api/prompt_loader.py`, `search_insights.py`: Existing extracted modules that demonstrate the flat-in-api/ pattern
- `src/feedops/providers/__init__.py`: Shows re-export pattern via `__init__.py` (can use for schemas if needed)

### Established Patterns
- Lazy imports: `gmc_sync.py` and `backfill.py` use `from feedops.api.main import run_async_in_thread` inside function bodies — these are lazy imports to avoid circular deps
- Supabase client: Initialized in `_app_lifespan()` and stored as global — persistence functions access it as a module-level variable
- Pydantic models: 17 models at lines 295-503 (request/response) + 3 at lines 3662-3677 (intent scoring) — all use `BaseModel`

### Integration Points
- `main.py` line 120: `_app_lifespan()` — Supabase client init, must remain in main.py
- `main.py` line 243: `run_async_in_thread()` — moves to telemetry.py or a shared utility, 3 callers to update
- `main.py` lines 2792-3615: `process_batch_job()` and `process_hybrid_batch_job()` — stay in main.py, will reference persistence/telemetry from new modules
- Tests in `tests/api/` — may need import path updates if they reference main.py internals

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. This is a mechanical refactoring phase with clear inputs and outputs.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-schemas-extraction*
*Context gathered: 2026-03-03*
