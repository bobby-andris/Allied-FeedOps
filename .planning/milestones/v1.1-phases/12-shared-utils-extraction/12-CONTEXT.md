# Phase 12: Shared Utils Extraction - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Consolidate duplicated `_require_request_id()` and `GenerationBudgetExceededError` into a single `feedops/api/utils.py` module. Both persistence.py and job_management.py import from utils.py instead of defining their own copies. No circular imports introduced.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Whether to include only the 2 required symbols in utils.py or also relocate other shared primitives — keep it minimal (just the 2 symbols) unless a clear case emerges during implementation
- File naming: `utils.py` per success criteria
- Import update order: follow Phase 11 pattern (update all imports BEFORE deleting source definitions)
- Whether to clean up nearby imports while touching files — only if directly related to the moved symbols

</decisions>

<specifics>
## Specific Ideas

No specific requirements — the success criteria are precise:
1. `utils.py` contains exactly one `_require_request_id()` and `GenerationBudgetExceededError`
2. Neither persistence.py nor job_management.py defines these symbols
3. No circular imports
4. All tests pass

</specifics>

<code_context>
## Existing Code Insights

### Duplication Map
- `_require_request_id()` — duplicated in `persistence.py:478` AND `job_management.py:72`
- `GenerationBudgetExceededError` — single definition in `generator.py:54` (not duplicated, but being relocated to shared location)

### Current Import Graph
- `routes.py` imports `_require_request_id` from `job_management` (line 95)
- `routes.py` imports `GenerationBudgetExceededError` from `generator` (line 115)
- `persistence.py` uses its own local `_require_request_id` (line 230, 331, 403)
- `job_runner.py` imports `_resolve_execution_request_id` from `job_management` (line 28) — different function, not affected

### No Circular Import
- persistence.py does NOT import from job_management.py
- job_management.py does NOT import from persistence.py
- The duplication exists because they independently needed the same utility

### Established Patterns
- Phase 11 pattern: update all imports to new location FIRST, then delete old definitions
- Phase 9 pattern: ruff + pytest green after each deletion

### Integration Points
- New `src/feedops/api/utils.py` — created fresh
- `persistence.py` — remove local `_require_request_id`, import from utils
- `job_management.py` — remove local `_require_request_id`, import from utils
- `generator.py` — remove `GenerationBudgetExceededError` class, import from utils
- `routes.py` — update import paths for both symbols

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-shared-utils-extraction*
*Context gathered: 2026-03-04*
