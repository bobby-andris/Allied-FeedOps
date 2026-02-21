---
phase: 22-fix-integration-bugs-doc-gaps
plan: 01
subsystem: api
tags: [python, typescript, cloud-run, keyword-bank, prompt-builder, gmc]

# Dependency graph
requires:
  - phase: 20-prompt-architecture
    provides: "prompt_builder.py with apply_feedback_layer() and sku_corrections integration"
  - phase: 20-feedback-layer
    provides: "sku_corrections table with correction_text column"
provides:
  - "apply_feedback_layer() reads correction_text as first-priority key from sku_corrections dicts"
  - "confirmed_sample.last_run populates from run_timestamp (not missing run_at field)"
  - "keyword_bank.json included in Docker build via src/feedops/integrations/data/ tree"
  - "GMC_MERCHANT_ID=136699027 set and verified in Cloud Run feedops-pipeline service"
affects: [23-gmc-sync, content-generation, funnel-monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-relative paths: Path(__file__).parent for data files in Docker containers"
    - "correction_text priority ordering: correction_text > text > correction > str(correction)"

key-files:
  created:
    - src/feedops/integrations/data/keyword-bank.json
  modified:
    - src/feedops/api/prompt_builder.py
    - dashboard/src/app/api/funnel/summary/route.ts
    - src/feedops/integrations/keyword_bank.py

key-decisions:
  - "GMC_MERCHANT_ID=136699027 (Allied Brass MC ID) sourced from .env.vercel — no user input required"
  - "keyword_bank.json copied from data/ (gitignored) to src/feedops/integrations/data/ (tracked in git) for Docker inclusion"
  - "correction_text added as first-priority fallback; existing text/correction fallbacks preserved for backward compat"

patterns-established:
  - "Data files used by Python modules should live in src/feedops/integrations/data/ alongside the module, resolved via Path(__file__).parent"

requirements-completed: [FIX-01, MEAS-02]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 22 Plan 01: Fix Integration Bugs Summary

**Four runtime/integration bugs fixed: correction_text key priority in apply_feedback_layer(), run_timestamp field mapping in funnel API, keyword_bank.json moved into Docker-included src/ tree, and GMC_MERCHANT_ID=136699027 set in Cloud Run**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T12:22:51Z
- **Completed:** 2026-02-21T12:24:49Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Fixed FIX-01: apply_feedback_layer() now extracts `correction_text` as first-priority key from sku_corrections dicts — persistent corrections will now work correctly
- Fixed funnel dashboard: `confirmed_sample.last_run` now maps to `parsed.run_timestamp` (the field that exists in spot-check JSON, not the non-existent `run_at`)
- Fixed keyword bank Docker inclusion: moved keyword-bank.json into src/ tree with module-relative Path resolution, enabling Cloud Run containers to find it
- Satisfied MEAS-02: GMC_MERCHANT_ID=136699027 set directly on Cloud Run feedops-pipeline service via gcloud and verified

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix apply_feedback_layer() field name mismatch and confirmed_sample.last_run** - `37602b98` (fix)
2. **Task 2: Move keyword_bank.json into src/ tree and set GMC_MERCHANT_ID via gcloud** - `06a0d351` (fix)

## Files Created/Modified

- `src/feedops/api/prompt_builder.py` - Added `correction_text` as first-priority key; updated docstring to reference sku_corrections table
- `dashboard/src/app/api/funnel/summary/route.ts` - Changed `parsed.run_at` to `parsed.run_timestamp` for confirmed_sample.last_run
- `src/feedops/integrations/keyword_bank.py` - Changed DEFAULT_KEYWORD_BANK_PATH from relative `Path("data/...")` to module-relative `Path(__file__).parent / "data" / ...`
- `src/feedops/integrations/data/keyword-bank.json` - 12-entry keyword bank data file, now tracked in git under src/ tree for Docker build inclusion

## Decisions Made

- GMC Merchant Center ID `136699027` sourced from `.env.vercel` — no user input required; set directly via `gcloud run services update`
- Keyword bank JSON copied from gitignored `data/` directory to tracked `src/feedops/integrations/data/` directory — no data loss, just new location
- `correction_text` priority ordering preserves backward compatibility: falls through to `text`, `correction`, then `str(correction)` if `correction_text` absent

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - GMC_MERCHANT_ID was set programmatically via gcloud during Task 2. No manual steps required.

## Next Phase Readiness

- FIX-01 feedback layer is now fully wired: sku_corrections rows will correctly deliver their `correction_text` into prompts
- MEAS-02 GMC sync can now authenticate: Cloud Run service has GMC_MERCHANT_ID=136699027 in its environment
- keyword_bank.json will be included in the next Docker image build (next push to master triggers Cloud Build)
- Dashboard funnel page will now correctly show last_run timestamp from spot-check results

---
*Phase: 22-fix-integration-bugs-doc-gaps*
*Completed: 2026-02-21*
