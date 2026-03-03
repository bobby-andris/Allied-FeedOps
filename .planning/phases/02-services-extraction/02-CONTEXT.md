# Phase 2: Services Extraction - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract business logic from main.py (currently 2,654 lines after Phase 1) into three service modules: `finish_processing.py`, `intent_scoring.py`, and `generation.py`. Add unit tests per module (DECOMP-11). Ensure run_async_in_thread has a daemon=False test (DECOMP-08). All API endpoints must return identical responses after extraction (DECOMP-10).

</domain>

<decisions>
## Implementation Decisions

### Module boundaries
- `finish_processing.py`: `_validate_finish_sentences_payload()`, `_enforce_finish_sentence_parity()`, `_build_finish_sentences_user_prompt()` — all finish-related logic in one module
- `intent_scoring.py`: `_get_intent_scorer()`, `_extract_query_intent_generation_diagnostics()`, `api_score_intent()` route handler (self-contained enough to own its route)
- `generation.py`: `_build_generation_user_prompt()`, `_execute_regeneration_request()` — core generation orchestration and prompt assembly
- Route handlers for all other endpoints stay in main.py — only intent scoring moves its route (it's fully self-contained)

### run_async_in_thread (DECOMP-08)
- Keep in `telemetry.py` where Phase 1 placed it — callers already updated, import graph is clean
- Add unit test asserting `thread.daemon == False` to satisfy DECOMP-08
- No need for a separate utils.py — the function is well-placed

### Test approach (DECOMP-11)
- One test file per extracted module: `test_finish_processing.py`, `test_intent_scoring.py`, `test_generation.py`
- Real unit tests with mocked dependencies (Supabase, OpenAI) — not just smoke tests
- Test actual business logic: finish parity catches missing finishes, intent scoring returns expected structure, generation handles error paths
- Add daemon=False assertion for run_async_in_thread in existing telemetry tests

### Import and commit strategy (carried from Phase 1)
- All modules flat in `src/feedops/api/` — established pattern
- Clean break imports, no re-exports from main.py
- Preserve exact function signatures — zero changes during move
- One commit per module extraction
- Pytest verification after each extraction

### generation_telemetry.py
- Claude's discretion on whether to merge into telemetry.py or leave as-is — check for overlap and decide

### Claude's Discretion
- Exact function grouping for edge cases (helpers that could go in multiple modules)
- Internal module organization and ordering
- Test case selection and mock depth
- Whether generation_telemetry.py merges into telemetry.py

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/feedops/api/schemas.py`: All Pydantic models already extracted (Phase 1) — service modules import types from here
- `src/feedops/api/persistence.py`: CRUD functions extracted (Phase 1) — generation.py will call these
- `src/feedops/api/telemetry.py`: run_async_in_thread + metrics helpers extracted (Phase 1)
- `src/feedops/api/job_management.py`: Job lifecycle helpers extracted (Phase 1)
- `src/feedops/api/prompt_builder.py`: Existing prompt orchestrator — generation.py coordinates with this

### Established Patterns
- Flat module layout in `src/feedops/api/` (prompt_loader.py, search_insights.py, schemas.py, persistence.py, etc.)
- Supabase client passed as parameter to functions (not imported as global)
- Phase 1 smoke test pattern in `tests/api/test_*_smoke.py` — Phase 2 tests go deeper with mocked deps

### Integration Points
- `main.py` route handlers call into service modules (thin wrappers after extraction)
- `generation.py` will call `persistence.py` for DB reads/writes and `telemetry.py` for metrics
- `finish_processing.py` called by generation flow and regeneration flow
- `intent_scoring.py` is self-contained with its own route

### Functions remaining in main.py after Phase 2
- `_app_lifespan()` — app startup
- `attach_request_context()` — middleware
- All route handlers except intent scoring
- `process_batch_job()` and `process_hybrid_batch_job()` — Phase 3 scope

</code_context>

<specifics>
## Specific Ideas

No specific requirements — this is a mechanical extraction following the same pattern as Phase 1. Requirements (DECOMP-05 through DECOMP-11) define the exact target modules and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-services-extraction*
*Context gathered: 2026-03-03*
