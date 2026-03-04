---
phase: 04-gpt52-bug-fixes
plan: 02
subsystem: api
tags: [openai, gpt-5.2, prompt-caching, cache-key]

# Dependency graph
requires:
  - phase: 04-gpt52-bug-fixes
    provides: GPT-5.2 bug fix research and plan — temperature/reasoning_effort fix (04-01)
provides:
  - prompt_cache_key="feedops-pipeline-v1" on both create() call paths in openai_provider.py
affects: [05-provider-abstraction, 06-model-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "prompt_cache_key as first-class SDK parameter (NOT extra_body field) for cache bucketing across batch runs"

key-files:
  created: []
  modified:
    - src/feedops/providers/openai_provider.py

key-decisions:
  - "prompt_cache_key is a first-class OpenAI SDK parameter — do NOT nest inside extra_body"
  - "Static value 'feedops-pipeline-v1' shared across all requests to maximize cache hit rate"
  - "extra_body={prompt_cache_retention: 24h} preserved alongside prompt_cache_key on both paths"

patterns-established:
  - "Both API call paths (image and text) in generate() must carry identical cache configuration"

requirements-completed: [GPT-04, GPT-06]

# Metrics
duration: 5min
completed: 2026-03-03
---

# Phase 04 Plan 02: prompt_cache_key Added to OpenAI API Calls Summary

**`prompt_cache_key="feedops-pipeline-v1"` added as first-class SDK parameter to both image and text `client.chat.completions.create()` call paths in openai_provider.py**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-03T12:37:13Z
- **Completed:** 2026-03-03T12:42:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `prompt_cache_key="feedops-pipeline-v1"` to the image path `create()` call (line 408)
- Added `prompt_cache_key="feedops-pipeline-v1"` to the text path `create()` call (line 421)
- Preserved existing `extra_body={"prompt_cache_retention": "24h"}` on both paths untouched
- All 24 existing provider tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add prompt_cache_key to both API call paths** - `8fff7996` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/feedops/providers/openai_provider.py` - Added `prompt_cache_key="feedops-pipeline-v1"` to both `client.chat.completions.create()` calls (image path line 408, text path line 421)

## Decisions Made

- `prompt_cache_key` is a first-class OpenAI SDK parameter, confirmed via introspection — passed alongside `model`, `messages`, etc., NOT inside `extra_body`
- Static string `"feedops-pipeline-v1"` chosen as the cache key so all batch requests share the same cache bucket, maximizing hit rate across the full pipeline run
- No changes made beyond the two surgical one-line additions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 04 is now complete (both plans done): temperature/reasoning_effort bug fixed (04-01) + prompt_cache_key added (04-02)
- Phase 05 (provider abstraction) and Phase 06 (model evaluation) can proceed
- No blockers from this plan

---
*Phase: 04-gpt52-bug-fixes*
*Completed: 2026-03-03*
