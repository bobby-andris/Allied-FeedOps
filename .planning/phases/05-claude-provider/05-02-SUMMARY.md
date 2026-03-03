---
phase: 05-claude-provider
plan: 02
subsystem: api
tags: [anthropic, claude, provider, factory, env-var, testing]

# Dependency graph
requires:
  - phase: 05-claude-provider plan 01
    provides: ClaudeProvider class with structured JSON output and retry logic
provides:
  - Claude branch in get_provider() via FEEDOPS_PROVIDER=claude env var
  - _build_claude_provider() builder function with env var overrides
  - 7 new factory tests covering all Claude selection scenarios
affects:
  - 06-evaluation
  - main.py provider instantiation

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import of ClaudeProvider inside _build_claude_provider() to avoid import-time anthropic dependency"
    - "effective_preferred = preferred or preferred_env pattern for programmatic + env var provider selection"
    - "Claude explicit-only selection — no auto-fallback chains (per architecture decision)"

key-files:
  created: []
  modified:
    - src/feedops/providers/factory.py
    - tests/test_providers.py

key-decisions:
  - "Claude not added to FallbackProvider chains — explicit selection only until Phase 6 evaluation results"
  - "effective_preferred merges preferred arg and FEEDOPS_PROVIDER env var with arg taking precedence"
  - "FEEDOPS_CLAUDE_SDK_TIMEOUT_SECONDS defaults to 60s (vs 45s for OpenAI) — Claude requests run longer"

patterns-established:
  - "Lazy builder pattern: _build_claude_provider() lazy-imports ClaudeProvider to avoid anthropic import when unused"
  - "Provider env var override: FEEDOPS_PROVIDER env var checked before any auto-detection logic"

requirements-completed:
  - PROV-04

# Metrics
duration: 5min
completed: 2026-03-03
---

# Phase 05 Plan 02: Factory Claude Provider Wiring Summary

**Runtime provider switching via FEEDOPS_PROVIDER=claude env var, enabling head-to-head evaluation without code changes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-03T15:25:00Z
- **Completed:** 2026-03-03T15:27:09Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added _build_claude_provider() builder with lazy import and full env var override support (FEEDOPS_CLAUDE_SDK_TIMEOUT_SECONDS, FEEDOPS_CLAUDE_JSON_RETRY_MAX)
- Wired FEEDOPS_PROVIDER=claude branch into get_provider() with ANTHROPIC_API_KEY validation and clear error message
- Updated ValueError message and docstring to document Claude as a first-class provider
- Added 7 factory tests covering all Claude selection scenarios with zero regression on existing 21 tests (28 total in test_providers.py, 53 total across both provider test files)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend factory.py with Claude provider support** - `eff6878f` (feat)
2. **Task 2: Add factory tests for Claude provider selection** - `5e0051db` (test)

**Plan metadata:** (included in final docs commit)

## Files Created/Modified
- `src/feedops/providers/factory.py` - Added _build_claude_provider() builder, FEEDOPS_PROVIDER=claude branch in get_provider(), updated ValueError and docstring
- `tests/test_providers.py` - Added ClaudeProvider import, 7 new factory tests for Claude selection scenarios

## Decisions Made
- Claude not added to FallbackProvider chains — per user decision, explicit selection only until Phase 6 evaluation confirms quality
- effective_preferred merges programmatic preferred arg with FEEDOPS_PROVIDER env var (arg takes priority when both set)
- FEEDOPS_CLAUDE_SDK_TIMEOUT_SECONDS defaults to 60s vs 45s for OpenAI — Claude requests tend to run longer with extended thinking

## Deviations from Plan

None - plan executed exactly as written. The only minor variation: existing `preferred == "gemini"` / `preferred == "openai"` checks in fallback section were updated to use `effective_preferred` for consistency (not specified in plan but required for FEEDOPS_PROVIDER=openai/gemini env var to work correctly throughout the full function).

## Issues Encountered
None - factory extension was straightforward. Both plan verification commands produce expected output.

## Next Phase Readiness
- Phase 5 is now complete — ClaudeProvider (Plan 01) + factory wiring (Plan 02) both done
- Phase 6 (evaluation) can now run head-to-head comparisons by setting FEEDOPS_PROVIDER=claude vs FEEDOPS_PROVIDER=openai with no code changes
- Blocker: 10 SKU evaluation set not yet defined — Bobby/Robert must confirm selection before Phase 6 begins

---
*Phase: 05-claude-provider*
*Completed: 2026-03-03*
