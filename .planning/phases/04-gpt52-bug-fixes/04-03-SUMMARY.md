---
phase: 04-gpt52-bug-fixes
plan: 03
subsystem: testing
tags: [python, verification, cli, stdlib, content-quality, post-deploy]

requires:
  - phase: 04-gpt52-bug-fixes plan 01-02
    provides: Working GPT-5.2 bug fixes (temperature, reasoning_effort, json_schema, prompt_cache_key) to verify against

provides:
  - Standalone Python CLI script for post-deploy content quality verification
  - Automated pass/fail check on description length per platform per SKU
  - Reusable tool for Phase 5 (Claude provider) and Phase 7 (Bing fix) regression testing

affects:
  - Phase 05 (Claude provider evaluation) — use script to compare Claude vs GPT-5.2 output quality
  - Phase 07 (Bing fix verification) — use --platforms bing to confirm Bing description length fix

tech-stack:
  added: []
  patterns:
    - "Post-deploy verification script pattern: stdlib-only Python CLI, argparse + urllib, structured PASS/FAIL output"

key-files:
  created:
    - scripts/verify_content_quality.py
  modified: []

key-decisions:
  - "Stdlib only (urllib, argparse, json, sys) — no external dependencies needed for a verification script; eliminates venv requirement for operators"
  - "OSError re-raised for connection failures (exit code 2) vs HTTP errors (exit code 1) — distinguishes setup errors from content quality failures"
  - "Default timeout 300s — content generation takes ~3 min; CLI-configurable for faster smoke tests"

patterns-established:
  - "Verification script pattern: standalone Python, argparse CLI, FEEDOPS_PIPELINE_URL env var fallback, structured per-platform output"

requirements-completed: [GPT-06]

duration: 4min
completed: 2026-03-03
---

# Phase 04-03: GPT-5.2 Bug Fixes — Verification Script Summary

**Standalone Python verification CLI (`scripts/verify_content_quality.py`) that POSTs to `/optimize-sku` and reports PASS/FAIL per platform based on description length (default: 500 chars)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-03T12:42:03Z
- **Completed:** 2026-03-03T12:46:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `scripts/verify_content_quality.py` — 310-line standalone verification script
- CLI accepts `--pipeline-url`, `--master-sku` (repeatable), `--platforms`, `--min-desc-len`, `--timeout`
- Falls back to `FEEDOPS_PIPELINE_URL` env var when `--pipeline-url` omitted
- Prints structured PASS/FAIL output with desc char count and title preview per platform
- Stdlib only — no external dependencies; immediately runnable after `git pull`
- Exit codes: 0=all pass, 1=any fail, 2=connection/setup error

## Task Commits

Each task was committed atomically:

1. **Task 1: Create verify_content_quality.py verification script** - `b00333df` (feat)

## Files Created/Modified
- `scripts/verify_content_quality.py` - Post-deploy content quality CLI tool

## Decisions Made
- Used stdlib `urllib` following the pattern from `scripts/smoke_regenerate_lineage.py` — no `requests` dependency needed
- OSError (connection failures) re-raised to caller and caught in `main()` → exit code 2; HTTP errors caught in `verify_sku()` → ERROR status → exit code 1 — distinguishes unreachable pipeline from bad content
- Default timeout 300s matches ~3 min generation time; configurable for faster checks
- Default SKUs `["920D-6", "AP-41/18"]` match the plan's GPT-06 requirement

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 4 complete — all 3 plans executed (GPT-01 temperature fix, GPT-02 reasoning_effort, GPT-03 json_schema strict mode in plan 01; GPT-04 prompt_cache_key in plan 02; GPT-06 verification script in plan 03)
- Verification script ready for Phase 5 (Claude provider) and Phase 7 (Bing fix)
- Run: `python3 scripts/verify_content_quality.py --pipeline-url $FEEDOPS_PIPELINE_URL`

---
*Phase: 04-gpt52-bug-fixes*
*Completed: 2026-03-03*
