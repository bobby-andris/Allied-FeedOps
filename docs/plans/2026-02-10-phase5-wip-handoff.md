# Phase 5 WIP Handoff (Gold Examples + Keyword/Competitor Evidence Scaffolding)

Date: 2026-02-10

This file documents the **uncommitted** work currently in the working tree on `master`.
It exists to stop repeated exploration and make it easy to continue in a new Codex chat.

## Current Branch / Commit State

- Current branch: `master`
- **No new commits yet** for the Phase 5 work described below.
- A recovery patch of the current diff was written to: `/tmp/allied-feedops-wip.patch`

## Files Changed (Uncommitted)

Modified (6):
- `docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md`
- `src/feedops/api/prompt_loader.py`
- `src/feedops/pipeline/generator.py`
- `src/feedops/pipeline/prompts.py`
- `tests/test_pipeline.py`
- `tests/test_prompt_loader.py`

Untracked (4):
- `src/feedops/pipeline/keyword_gaps.py`
- `src/feedops/pipeline/competitor_evidence.py`
- `tests/test_keyword_gaps.py`
- `tests/test_competitor_evidence.py`

Note: There are **no uncommitted TypeScript changes** in `dashboard/` in the current working tree.

## What Was Implemented

### 1) Gold standard examples are injected into Python prompt assembly

Goal: include few-shot examples that show the expected **cross-platform** response shape (Google + Shopify) without duplicating prompt logic per platform.

Key changes:
- `src/feedops/api/prompt_loader.py`
  - `format_gold_standard_examples()` now supports a configurable `max_description_chars` (default `5000`).
  - New formatter: `format_gold_standard_examples_bundle(max_examples=2, max_description_chars=5000)` that renders:
    - `google_title`, `google_description`
    - `shopify_title`, `shopify_description`
    - `why_it_works`
- `src/feedops/pipeline/prompts.py`
  - Added `{gold_examples}` placeholder to:
    - `USER_PROMPT_TEMPLATE`
    - `OPTIMIZATION_TEMPLATE`
    - `VARIANT_USER_PROMPT_TEMPLATE`
- `src/feedops/pipeline/generator.py`
  - Calls `format_gold_standard_examples_bundle(max_examples=2)` and injects a `## Gold Standard Examples` section into:
    - `build_prompt()`
    - `build_split_prompt()`
    - `build_variant_prompt()`

Rationale:
- Previously, descriptions were truncated to ~300 chars, which is misleading because the model treats the excerpt as the full “gold standard”.
- Google descriptions allow up to `5000` chars, so using `5000` as the example cap avoids accidental “partial examples”.

### 2) Keyword gaps module (not wired into evidence yet)

- `src/feedops/pipeline/keyword_gaps.py`
  - Computes high-volume search queries **not covered** by the current title.
  - Excludes finish-specific queries using the same finish filter helpers in `src/feedops/pipeline/evidence.py`.
  - Output is intended as **search-intent guidance**, not product facts.

### 3) Competitor evidence module (not wired into evidence yet)

- `src/feedops/pipeline/competitor_evidence.py`
  - Fetches competitor listings/patterns from Supabase (when available).
  - Classifies sources into buckets:
    - `direct` vs `marketplace` vs `mixed` vs `unknown`
  - Safety notes are explicit in module docstring:
    - Competitor data must not be treated as proof of Allied Brass product specs.
    - No “better than competitors” or unverifiable comparisons.

## Tests Added / Updated

- `tests/test_prompt_loader.py`
  - Ensures gold examples bundle formatting works and the 5000 char cap is honored.
- `tests/test_pipeline.py`
  - Ensures prompts include/omit gold examples depending on availability.
- `tests/test_keyword_gaps.py`
  - Validates ranking + finish-specific filtering + evidence-row formatting.
- `tests/test_competitor_evidence.py`
  - Validates direct vs marketplace classification and pattern bucketing.

## Verification Commands Run (Pass)

These are the exact commands that were run and passed in this working tree:

```bash
.venv/bin/pytest -q tests/test_prompt_loader.py tests/test_pipeline.py tests/test_keyword_gaps.py tests/test_competitor_evidence.py
```

Result: `54 passed` (warnings are from third-party deps).

## What’s Still Missing (Phase 5)

The master plan Phase 5 “Definition of done” requires keyword gaps + competitor context to appear in the **evidence table**.
Right now:
- The two new modules exist and have unit tests.
- `src/feedops/pipeline/evidence.py` does **not** call them yet.

Next implementation steps:
1. Wire `keyword_gaps.build_keyword_gap_evidence_rows()` into `src/feedops/pipeline/evidence.py` after fetching `search_queries_by_master_sku`.
2. Wire `competitor_evidence.build_competitor_evidence()` into `src/feedops/pipeline/evidence.py` and convert to safe, compact `Evidence` rows.
3. Add an evidence-level integration test (one test that monkeypatches query + competitor fetches and asserts evidence rows are present and policy-safe).
4. Update `docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md` Execution Log with Phase 5 tasks + the verification commands above plus the new evidence integration test.

## Suggested Commit Strategy (Run Locally)

The Codex sandbox in this session may not be able to create git branch refs/locks. If git works in your local terminal, do:

```bash
git switch -c codex/python-single-source-of-truth-phase5

git add src/feedops/api/prompt_loader.py src/feedops/pipeline/generator.py src/feedops/pipeline/prompts.py tests/test_prompt_loader.py tests/test_pipeline.py
git commit -m "phase5: inject gold standard examples into prompts"

git add src/feedops/pipeline/keyword_gaps.py src/feedops/pipeline/competitor_evidence.py tests/test_keyword_gaps.py tests/test_competitor_evidence.py
git commit -m "phase5: add keyword gaps + competitor evidence modules"

git add docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md docs/plans/2026-02-10-phase5-wip-handoff.md
git commit -m "docs: phase5 ledger + handoff notes"
```

