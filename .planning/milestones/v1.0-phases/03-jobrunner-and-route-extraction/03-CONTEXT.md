# Phase 3: JobRunner and Route Extraction - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify duplicated `process_batch_job()` and `process_hybrid_batch_job()` into a single `JobRunner` class. Slim `main.py` from 2,075 lines to <500 by extracting route handlers and the unified job processor. All existing API endpoints must return identical responses. Job cancellation and graceful shutdown must work without orphaned threads.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All structural decisions are delegated to Claude — this is a mechanical refactoring following the same patterns established in Phases 1-2. Specific areas of discretion:

- **JobRunner class design**: How to unify batch and hybrid processing (strategy pattern, mode flag, shared base class, etc.)
- **Regeneration job scope**: Whether `process_regenerate_job()` is unified into JobRunner or remains separate (JOBS-01 only specifies batch+hybrid, but regen has similar patterns)
- **Route file organization**: How to split routes out of main.py to hit <500 lines (single router file vs domain-split files)
- **Job cancellation mechanism**: How to implement JOBS-05 (threading events, global registry, etc.) and graceful shutdown behavior for in-progress SKUs
- **Variant adaptation integration**: Where the hybrid-specific variant adaptation logic lives within the unified runner
- **Progress tracking**: How to handle the different progress models (batch: simple completed/failed counts; hybrid: requested vs expanded scope with overflow invariant)

### Carried from Phases 1-2

- All modules flat in `src/feedops/api/` — established pattern
- Clean break imports, no re-exports from main.py
- Preserve exact function signatures during extraction
- One commit per logical extraction
- Pytest verification after each extraction

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/feedops/api/schemas.py`: All Pydantic models (Phase 1) — JobRunner will import request/response types
- `src/feedops/api/persistence.py`: CRUD functions (Phase 1) — `_persist_generated_content_and_history()`, `_upsert_batch_job_sku_status()`, etc.
- `src/feedops/api/telemetry.py`: `run_async_in_thread()`, `_emit_generation_summary()` (Phase 1)
- `src/feedops/api/job_management.py`: Job lifecycle helpers (Phase 1) — job creation, status tracking
- `src/feedops/api/generation.py`: Core generation orchestration (Phase 2) — `generate_per_platform()`
- `src/feedops/api/finish_processing.py`: Finish sentence persistence (Phase 2)
- `src/feedops/api/intent_scoring.py`: Self-contained with own APIRouter (Phase 2) — pattern for route extraction

### Established Patterns
- APIRouter pattern for self-contained route groups (intent_scoring.py already uses this)
- `run_async_in_thread()` for background jobs (must preserve — containers kill BackgroundTasks)
- Supabase client via `get_client()` (not passed as parameter in job processing)

### Key Duplication Analysis
- **Shared between batch and hybrid (~60%)**:
  - Job status initialization (`status: "processing"`, `started_at`)
  - SKU status tracking (`_upsert_batch_job_sku_status()`)
  - Content generation via `generate_per_platform()` with `asyncio.wait_for(timeout=300.0)`
  - Content persistence loop (platform × content_type → `_persist_generated_content_and_history()`)
  - Telemetry emission (`_emit_generation_summary()`)
  - Finish sentence persistence (`persist_finish_sentences()`)
  - Final job status update
- **Hybrid-only**:
  - `generate_full_content_v2()` inner function (refactored generation + persistence)
  - Family processing with base → variant adaptation flow
  - Requested vs expanded scope tracking with overflow invariant
  - `_build_job_options()`, `_update_job_progress()`, `_record_sku_result()` helper closures
- **Batch-only**:
  - Simpler progress tracking (single completed/failed counters)
  - Direct `asyncio.wait_for()` inline (not extracted to helper)
  - `_normalize_generation_options()` call

### Integration Points
- `main.py` line 968: `process_batch_job` passed to `run_async_in_thread()` from batch route
- `main.py` line 1173: `process_hybrid_batch_job` passed to `run_async_in_thread()` from hybrid route
- `main.py` line 595: `process_regenerate_job` is a third background processor (similar pattern)
- Route handlers at lines 349-1207 (13 endpoints) + backfill routes at lines 2026-2075
- `hybrid_generation.py`: Contains `adapt_variant_content()` and `extract_spec_difference()` — called by hybrid job

### Functions remaining in main.py (currently, pre-Phase 3)
- `_app_lifespan()` — app startup (must stay)
- `attach_request_context()` — middleware (must stay)
- 13 route handlers (lines 349-1207)
- `process_batch_job()` (lines 1208-1486) — moves to JobRunner
- `process_hybrid_batch_job()` (lines 1488-2024) — moves to JobRunner
- 5 backfill route handlers (lines 2026-2075)
- Various helper functions used by routes and jobs

</code_context>

<specifics>
## Specific Ideas

No specific requirements — this is a mechanical refactoring following the same pattern as Phases 1-2. Requirements (DECOMP-09, JOBS-01 through JOBS-06) define the exact target structure and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-jobrunner-and-route-extraction*
*Context gathered: 2026-03-03*
