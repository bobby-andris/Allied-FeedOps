---
phase: 18-diagnosis-establish-ground-truth
plan: 01
subsystem: api
tags: [cloud-run, feature-flags, python, typescript, content-generation, architecture]

# Dependency graph
requires:
  - phase: 17-google-shopping-intelligence
    provides: "Research context on feed quality gaps and content generation pipeline"
provides:
  - "End-to-end call graph for Path A (single-SKU UI regeneration) and Path B (batch generation)"
  - "Feature flag call site audit with production vs legacy path classification"
  - "Cloud Run runtime env var state for all 3 feature flags"
  - "keyword_bank.json Docker container inclusion status confirmed"
affects:
  - "19-content-coverage-and-propagation"
  - "20-fix-and-optimize"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Architecture documentation pattern: summary table + ASCII call graphs + feature flag audit in one document"

key-files:
  created:
    - docs/architecture/generation-paths.md
    - .planning/phases/18-diagnosis-establish-ground-truth/18-01-SUMMARY.md
  modified: []

key-decisions:
  - "DIAG-02 CONFIRMED: Path A (UI regen) calls main.py::regenerate_content() via HTTP POST to Cloud Run /regenerate — generator.py::build_prompt() is bypassed"
  - "DIAG-03 CONFIRMED: All 3 feature flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1) have active call sites in production paths — all default to True (enabled) with no Cloud Run overrides"
  - "keyword_bank.json is absent from Cloud Run container — data/ excluded by .gcloudignore, external keywords always return [] in production"
  - "Paths A and B share identical core functions (_build_generation_user_prompt, _generate_with_metrics, _enforce_finish_sentence_parity) — diverge only in threading, persistence helpers, and route-level validation"

patterns-established:
  - "Feature flag documentation pattern: definition + all call sites + production/legacy classification + runtime state"

requirements-completed:
  - DIAG-02
  - DIAG-03

# Metrics
duration: 8min
completed: 2026-02-21
---

# Phase 18 Plan 01: Generation Paths — Code Trace and Feature Flag Audit Summary

**End-to-end call graph for UI regeneration (route.ts → Cloud Run → regenerate_content) and batch generation, with grep-verified feature flag wiring and Cloud Run runtime state confirmed.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-21T02:56:44Z
- **Completed:** 2026-02-21T03:05:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Traced Path A (single-SKU UI regeneration): `route.ts:211` → Cloud Run `/regenerate` → `main.py::regenerate_content()` with full function-level line references
- Documented bypassed functions: `generator.py::build_prompt()`, `keyword_placement.py`, `verifier.py`, `selection.py` — all exclusive to legacy 6-agent pipeline via `optimize.py`
- Feature flag audit confirmed: all 3 flags (`PROMPT_CONTRACT_V2` in `prompt_loader.py:149`, `INTENT_CURATOR_V1` in `evidence.py:371`, `SEGMENT_STRATEGY_V1` in `evidence.py:348`) are wired to production paths; `SEGMENT_STRATEGY_V1` in `generator.py:100` is legacy-only
- Cloud Run runtime check: no feature flag env vars set → all 3 default to `True` (enabled) and cannot be toggled without redeployment
- `keyword_bank.json` confirmed absent from Cloud Run container: `data/` excluded by `.gcloudignore:40`, `Dockerfile` only copies `src/` and `pyproject.toml` — external keywords always return `[]` in production

## Task Commits

1. **Task 1: Trace generation paths and document call graphs with feature flag audit** - `4fb5b939` (feat)

## Files Created/Modified

- `docs/architecture/generation-paths.md` — End-to-end call graphs for Path A and Path B, feature flag call site table with production/legacy classification, Cloud Run runtime state, keyword_bank.json container analysis

## Decisions Made

- DIAG-02: Single-SKU UI regeneration path confirmed end-to-end — bypasses generator.py entirely
- DIAG-03: All 3 feature flags wired into production code paths and enabled by default (no Cloud Run env vars needed to activate)
- Keyword bank gap identified: `data/keyword-bank.json` never available in Cloud Run → external keywords always empty in production (pre-existing condition, documented as finding)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — documentation task only, no external service configuration required.

## Next Phase Readiness

- `docs/architecture/generation-paths.md` is the canonical reference for Phase 19-20 agents
- DIAG-02 and DIAG-03 are fully answered with grep-verified evidence
- Key finding for Phase 20: keyword_bank.json gap means external keyword research data is not reaching the LLM prompt in production — Phase 20 should address this (Supabase migration or GCS mount)
- All feature flags are active; Phase 20 can rely on intent curation and segment strategy being enabled

---
*Phase: 18-diagnosis-establish-ground-truth*
*Completed: 2026-02-21*
