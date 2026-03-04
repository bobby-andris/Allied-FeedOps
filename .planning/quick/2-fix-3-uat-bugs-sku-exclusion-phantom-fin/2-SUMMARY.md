---
phase: quick-2
plan: 01
subsystem: sku-selection, review, publish, pipeline
tags: [bug-fix, finish-sentences, sku-exclusion, publish-validation]
dependency_graph:
  requires: []
  provides: [BUG-A-fix, BUG-B2-fix, BUG-B4-fix]
  affects: [sku-selection-api, review-page, expand-variants, finish-processing, generator]
tech_stack:
  added: []
  patterns: [per-finish-coverage-check, sku-specific-finish-list, variant-index-lookup]
key_files:
  modified:
    - dashboard/src/app/api/sku-selection/route.ts
    - dashboard/src/app/(dashboard)/review/[sku]/page.tsx
    - dashboard/src/lib/publishing/expand-variants.ts
    - src/feedops/api/prompt_loader.py
    - src/feedops/api/finish_processing.py
    - src/feedops/pipeline/generator.py
decisions:
  - "SKU exclusion uses presence in generated_content (not approved_content IS NOT NULL) — any generated content means the SKU is already in-progress"
  - "Review page filters finish sentences at query time using relevantFinishes set derived from variant_index"
  - "Publish validation uses per-finish coverage check (all variant finishes covered) rather than exact count match"
  - "get_finish_list_for_sku falls back gracefully to FINISH_LIST_28 if Supabase unavailable"
  - "generator._build_finish_metadata_rows uses variant-derived finishes from parent_sku.variants (no DB call)"
metrics:
  duration: "8 minutes"
  completed: "2026-03-04"
  tasks_completed: 2
  files_modified: 6
---

# Quick Task 2 Plan 01: Fix 3 UAT Bugs (SKU Exclusion, Phantom Finish, Publish Validation) Summary

**One-liner:** Fixed SKU exclusion scope to any generated content row, added SKU-specific finish list queried from variant_index with graceful fallback, and replaced blunt count comparison with per-finish coverage validation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix SKU exclusion + review page finish filtering + publish validation (TypeScript) | 85fec202 | route.ts, page.tsx, expand-variants.ts |
| 2 | Add SKU-specific finish list + wire into pipeline (Python) | cf17d6ec | prompt_loader.py, finish_processing.py, generator.py |

## What Was Built

### Bug A — SKU Exclusion Scope (route.ts)

**Before:** `generated_content` query filtered by `.not('approved_content', 'is', null)` — only excluded SKUs with approved content.

**After:** Query selects all `master_sku` from `generated_content` with no filter — any SKU with any generated content row is excluded from Generate tab recommendations.

**Impact:** SKUs that have been generated but not yet approved are no longer re-recommended, preventing duplicate work.

### Bug B4 (Review) — Phantom Finish Sentences (page.tsx)

**Before:** `finishSentences` passed all 28 finish sentences from DB directly to the client, showing finish sentences for finishes that don't exist in variant_index for the SKU.

**After:** `filterFinishSentences()` function filters each platform's finish sentences to only include keys matching the `relevantFinishes` set (derived from `variant_index` for this SKU). Review page now shows only finish sentences for actual product variants.

### Bug B4 (Publish) — Finish Count Mismatch (expand-variants.ts)

**Before:** `Object.keys(finishSentences).length !== uniqueFinishes` — exact count comparison threw error for any SKU with fewer than 28 variants when the DB had 28 finish sentences.

**After:** `requiredFinishes.filter(f => !finishSentences[f])` — per-finish coverage check. Publish succeeds as long as every variant finish has a sentence. DB can have 28 sentences while SKU has 25 variants — no error.

### Bug B2 — Phantom Finish Generation (Python pipeline)

**`get_finish_list_for_sku(master_sku)` added to `prompt_loader.py`:**
- Queries `variant_index` table for finishes specific to this SKU
- Falls back to `FINISH_LIST_28` if Supabase unavailable or no variants found
- Graceful degradation with warning logs

**`finish_processing.py` wired to use SKU-specific list:**
- `_build_finish_sentences_user_prompt`: uses `get_finish_list_for_sku(master_sku)` — prompt schema lists only actual finishes
- `_validate_finish_sentences_payload`: validates against SKU-specific list — no false "incomplete" rejections
- `_enforce_finish_sentence_parity`: uses `finish_names` (SKU-specific) for schema, fallback generation, and completeness check

**`generator.py` wired to use variant-derived list:**
- `_build_finish_metadata_rows`: derives finish list from `parent_sku.variants` (no DB call needed — variants already loaded)
- `_normalize_finish_sentence_payload`: uses `get_finish_list_for_sku(parent_sku.master_sku)` for canonical coverage enforcement

## Verification

- TypeScript compiles clean: `npx tsc --noEmit` — no errors
- Next.js build passes: `npm run build` — all routes compiled successfully
- Python imports clean: all 3 modules import without errors
- Pre-existing lint errors in `BcgTableView.tsx` and one other file are out-of-scope (not modified by this task)

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items

**Pre-existing lint errors (out of scope):**
- `BcgTableView.tsx`: 7 "Cannot create components during render" errors (react-hooks/static-components)
- Another file: 1 "Calling setState synchronously within an effect" error
- These existed before this task and are not caused by our changes.

## Self-Check: PASSED

Files exist:
- dashboard/src/app/api/sku-selection/route.ts — FOUND
- dashboard/src/app/(dashboard)/review/[sku]/page.tsx — FOUND
- dashboard/src/lib/publishing/expand-variants.ts — FOUND
- src/feedops/api/prompt_loader.py — FOUND
- src/feedops/api/finish_processing.py — FOUND
- src/feedops/pipeline/generator.py — FOUND

Commits exist:
- 85fec202 — FOUND (fix TypeScript side)
- cf17d6ec — FOUND (Python pipeline side)
