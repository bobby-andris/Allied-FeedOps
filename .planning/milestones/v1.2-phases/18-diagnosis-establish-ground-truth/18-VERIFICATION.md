---
phase: 18-diagnosis-establish-ground-truth
verified: 2026-02-21T04:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "Open the overview page in the dashboard and confirm CoverageFunnel renders above stat cards"
    expected: "5-stage funnel with counts and drop-off percentages visible; clicking a stage expands an inline SKU list"
    why_human: "Visual rendering and click-to-expand interaction cannot be verified programmatically"
  - test: "Confirm the Confirmed in Sheets stage shows spot-check results (matched/checked badge) rather than 'Not yet checked'"
    expected: "Badge reads 'Spot-check: 10/10 matched'; last-run timestamp may show null (see note in gaps)"
    why_human: "Requires visual inspection of the rendered component in a browser"
---

# Phase 18: Diagnosis — Establish Ground Truth Verification Report

**Phase Goal:** Answer four sequential questions with evidence: Is content reaching GMC? Which code path runs in production? Are feature flags wired to the active path? Is the SKU coverage funnel wide enough to move metrics?
**Verified:** 2026-02-21T04:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Success Criteria (from ROADMAP.md)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | SKU coverage funnel shows exact counts at each stage with no ambiguity | VERIFIED | `/api/funnel/summary` and `/api/funnel/skus` endpoints live; `CoverageFunnel` integrated into overview `page.tsx` at line 123 |
| 2 | Single-SKU UI regeneration path documented end-to-end with function names and bypassed functions | VERIFIED | `docs/architecture/generation-paths.md` — ASCII call graph from `route.ts:211` through `main.py::regenerate_content()` with 7 bypassed functions listed |
| 3 | Feature flag audit confirms with grep evidence which flags have active call sites in production path | VERIFIED | Call site table in `generation-paths.md` — all 3 flags wired to production paths; `SEGMENT_STRATEGY_V1` in `generator.py:100` explicitly labeled legacy-only |
| 4 | Propagation spot-check for 10-20 SKUs confirms Google Sheets rows match Supabase approved_content | VERIFIED | `spot-check-results.json` shows 10/10 SKUs matched; `{FINISH_NAME}` scope quantified at 28 rows/28 SKUs (intentional template) |

**Score:** 4/4 success criteria verified

---

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Code path trace documents the exact function call sequence for Path A and Path B | VERIFIED | `docs/architecture/generation-paths.md` — full ASCII call graphs for Path A (route.ts → main.py::regenerate_content), Path B1 (batch-optimize → process_batch_job), Path B2 (hybrid-generate → process_hybrid_batch_job) |
| 2 | Divergence points between Path A and Path B are explicitly listed | VERIFIED | 8-row table in generation-paths.md listing thread model, persistence helper, versioning, route.ts validation, data collection as divergence points |
| 3 | Feature flag audit confirms which flags are wired into which production paths with grep evidence | VERIFIED | 4-row call site table with file:line for each flag; `is_intent_curator_v1_enabled` at `evidence.py:371`, `is_segment_strategy_v1_enabled` at `evidence.py:348`, `is_prompt_contract_v2_enabled` at `prompt_loader.py:149` — all grep-verified |
| 4 | Cloud Run runtime env vars are checked to determine actual flag state | VERIFIED | `gcloud run services describe` output in generation-paths.md — no flag env vars set; all 3 default to `True` |
| 5 | Overview page shows visual 5-stage SKU coverage funnel | VERIFIED | `CoverageFunnel.tsx` exists with 5 stages, loading skeleton, drop-off indicators; imported and rendered in `page.tsx:123` |
| 6 | Each funnel stage shows raw count and drop-off percentage | VERIFIED | `calcDropoff()` function in `CoverageFunnel.tsx:66-73` computes both delta count and percentage; `DropoffIndicator` renders between stages |
| 7 | Clicking a funnel stage expands inline SKU list (not navigation) | VERIFIED | `toggleStage()` + `expandedStage` state in component; `SkuList` renders inline within same card when `expandedStage` is set; fetches `/api/funnel/skus?stage=X` on click |
| 8 | 10-20 published SKUs spot-checked comparing Supabase approved_content vs Google Sheets rows | VERIFIED | `spot-check-results.json` shows 10 SKUs checked (all published that exist); mix of recently_published (5), random (3), fill (2) |
| 9 | Discrepancies documented and {FINISH_NAME} placeholder bug scope quantified | VERIFIED | 0 structural discrepancies; `finish_name_bug` section lists 28 affected SKUs across 28 rows — confirmed as intentional template properly expanded by `expand-variants.ts` |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/architecture/generation-paths.md` | End-to-end call graph for both generation paths with feature flag wiring | VERIFIED | 315 lines; contains `regenerate_content`, feature flag call site table, Cloud Run env check, keyword_bank.json analysis |
| `dashboard/src/app/api/funnel/summary/route.ts` | Funnel stage counts from Supabase | VERIFIED | Exports `GET`; uses Set-based dedup for DISTINCT counting; reads spot-check-results.json for stage 5 |
| `dashboard/src/app/api/funnel/skus/route.ts` | Per-stage SKU lists for expandable detail | VERIFIED | Exports `GET`; validates stage param (400 for invalid); handles all 4 clickable stages with pagination |
| `dashboard/src/components/dashboard/CoverageFunnel.tsx` | Visual funnel component with expandable SKU lists | VERIFIED | `'use client'` directive; `CoverageFunnel` named export; fetches `/api/funnel/summary` in `useEffect`; lazy SKU list fetch on stage click |
| `dashboard/src/app/(dashboard)/page.tsx` | Overview page with funnel integrated | VERIFIED | Imports `CoverageFunnel` at line 12; renders `<CoverageFunnel />` at line 123 |
| `scripts/spot_check_propagation.py` | Reusable propagation verification script | VERIFIED | Contains `spot_check` function; references `approved_content`; calls Node.js helper via subprocess |
| `.planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json` | Structured results for funnel confirmed_sample stage | VERIFIED | Valid JSON; `summary.total_checked=10`, `total_matched=10`, `finish_name_bug_count=28`; 10 per-SKU entries with `title_match`/`description_match` booleans |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `dashboard/src/app/api/regenerate/route.ts` | `main.py::regenerate_content()` | HTTP POST to Cloud Run /regenerate | WIRED | `route.ts:211` — `fetch(\`${PIPELINE_URL}/regenerate\`, ...)` confirmed via grep |
| `feature_flags.py` | `evidence.py` | `is_intent_curator_v1_enabled` and `is_segment_strategy_v1_enabled` | WIRED | `evidence.py:25-26` imports both; called at lines 348 and 371 |
| `CoverageFunnel.tsx` | `/api/funnel/summary` | `fetch` on mount in `useEffect` | WIRED | `CoverageFunnel.tsx:258` — `fetch('/api/funnel/summary')` |
| `CoverageFunnel.tsx` | `/api/funnel/skus` | `fetch` on stage click in `SkuList` | WIRED | `CoverageFunnel.tsx:116` — `fetch(\`/api/funnel/skus?stage=${stageKey}&...\`)` |
| `page.tsx` | `CoverageFunnel` | component import | WIRED | `page.tsx:12` imports; `page.tsx:123` renders `<CoverageFunnel />` |
| `scripts/spot_check_propagation.py` | `Supabase generated_content.approved_content` | supabase-py select query | WIRED | `spot_check_propagation.py:382-385` — `.select("master_sku, content_type, approved_content")` |
| `scripts/spot_check_propagation.py` | `Google Sheets SupplementalFeedData` | Node.js helper via subprocess | WIRED | `spot_check_propagation.py:244` — `subprocess.run(["node", str(NODE_HELPER), ...])` → `fetch_sheets_data.js:31-32` targets production sheet ID |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DIAG-01 | 18-02-PLAN.md | System can report SKU coverage funnel (total catalog → generated → approved → published → confirmed) | SATISFIED | `/api/funnel/summary` and `/api/funnel/skus` endpoints + `CoverageFunnel` component live on overview page |
| DIAG-02 | 18-01-PLAN.md | Execution path for single-SKU UI regeneration traced and documented | SATISFIED | `generation-paths.md` — Path A call graph from `route.ts:211` through all `main.py` functions, with 7 bypassed functions named |
| DIAG-03 | 18-01-PLAN.md | Feature flag call-site audit for PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1 | SATISFIED | Call site table in `generation-paths.md` with file:line for all 3 flags; runtime state confirmed via `gcloud describe` |
| DIAG-04 | 18-03-PLAN.md | Propagation spot-check verifies published content reached Google Sheets | SATISFIED | `spot-check-results.json` — 10/10 published SKUs matched; {FINISH_NAME} scope quantified |

All 4 requirements fully satisfied. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `dashboard/src/app/api/funnel/summary/route.ts` | 101 | `parsed.run_at ?? null` — reads non-existent key; JSON uses `run_timestamp` | Warning | `confirmed_sample.last_run` is always `null` in the API response and UI; match/checked counts display correctly |

**Note on the run_at / run_timestamp mismatch:** The `confirmed_sample` stage correctly shows matched (10) and checked (10) counts because those read `parsed.summary.total_checked` and `parsed.summary.total_matched` which do exist. Only the `last_run` timestamp field is silently null. The funnel dashboard still answers DIAG-01 with correct data. This is cosmetic and does not block the phase goal.

---

### Human Verification Required

#### 1. CoverageFunnel Visual Rendering

**Test:** Open the overview page (`/`) in the deployed dashboard or local dev server.
**Expected:** SKU Coverage Funnel card appears above the existing stat cards. Shows 5 stage cards with numeric counts, drop-off indicators between stages, and ChevronRight icons on clickable stages.
**Why human:** Visual layout and presence on page cannot be verified programmatically.

#### 2. Stage Click-to-Expand

**Test:** Click any of the first 4 stage cards (Total Catalog, Generated, Approved, Published).
**Expected:** An inline SKU list expands below the funnel showing SKU IDs with load-more pagination.
**Why human:** Interactive behavior (click → expand → load) cannot be verified by static analysis.

#### 3. Confirmed in Sheets Stage

**Test:** View the Confirmed in Sheets stage card and the spot-check badge below the funnel.
**Expected:** Stage card shows a count (matched=10); badge reads "Spot-check: 10/10 matched". Last-run timestamp may be absent (null) due to the `run_at` field name mismatch.
**Why human:** Requires rendering to confirm the badge populates from the confirmed_sample data.

---

### Gaps Summary

No gaps blocking goal achievement. All 4 success criteria, all 9 observable truths, all 7 key artifacts, and all 4 requirement IDs (DIAG-01 through DIAG-04) are verified.

One minor cosmetic issue found: `confirmed_sample.last_run` always returns `null` because `route.ts:101` reads `parsed.run_at` while `spot-check-results.json` uses the key `run_timestamp`. The matched/checked counts are unaffected. This can be fixed in a follow-on phase with a one-line change to read `parsed.run_timestamp ?? null`.

---

## Phase Assessment

**Goal achieved.** All four diagnostic questions are answered with evidence:

1. **Is content reaching GMC?** — Yes, propagation spot-check confirms 10/10 published SKUs have structurally matching content in Google Sheets. `{FINISH_NAME}` is an intentional template, properly expanded at publish time.

2. **Which code path runs in production?** — Single-SKU UI regeneration runs `main.py::regenerate_content()` via HTTP POST to Cloud Run `/regenerate`. `generator.py::build_prompt()`, `keyword_placement.py`, `verifier.py`, and `selection.py` are bypassed. Batch generation uses the identical core functions (`_build_generation_user_prompt`, `_generate_with_metrics`, `_enforce_finish_sentence_parity`).

3. **Are feature flags wired to the active path?** — All 3 flags are wired and enabled (defaulting to `True`; no Cloud Run env var overrides). Notable finding: `keyword_bank.json` is absent from the Cloud Run container (`data/` excluded by `.gcloudignore`) — external keyword data never reaches the LLM prompt in production.

4. **Is the SKU coverage funnel wide enough to move metrics?** — Funnel now visible on the overview page with live counts from Supabase. Only 10 SKUs have been published; the total catalog has ~2,784 distinct SKUs. The funnel quantifies the coverage gap for Phase 19-20 prioritization.

---

_Verified: 2026-02-21T04:00:00Z_
_Verifier: Claude (gsd-verifier)_
