---
phase: 20-targeted-fixes-intelligence-application
plan: "04"
subsystem: content-generation
tags: [feedback-layer, persistent-corrections, sku-corrections, structured-feedback, fix-01]
dependency_graph:
  requires: [20-03]
  provides: [persistent-corrections-table, structured-feedback-ui, correction-accumulation]
  affects: [regeneration-pipeline, dashboard-review-ui]
tech_stack:
  added:
    - sku_corrections Supabase table (platform/content_type scoped corrections)
  patterns:
    - structured feedback: tone_style/emphasis/length_preference layered on free-text
    - corrections accumulate per SKU: upsert with unique index on correction text
    - platform scoping: corrections for 'all' apply to any platform request
key_files:
  created:
    - supabase/migrations/036_sku_corrections.sql
  modified:
    - src/feedops/api/main.py
    - dashboard/src/app/api/regenerate/route.ts
    - dashboard/src/components/review/FeedbackModal.tsx
    - dashboard/src/components/review/RegenerateButton.tsx
decisions:
  - "Implemented apply_feedback_layer inline in /regenerate (20-03 was complete, prompt_builder.py available)"
  - "FeedbackModal extended with collapsible Advanced Feedback section to avoid overwhelming simple-case users"
  - "Correction lookup filters by platform IN (request.platform, 'all') per research Pitfall 4"
  - "save_as_correction triggers upsert with on_conflict on unique index to prevent duplicate corrections"
  - "Checkbox component from existing UI library (no new dependencies)"
metrics:
  duration: "~45 minutes"
  completed_date: "2026-02-21"
  tasks_completed: 2
  files_changed: 5
---

# Phase 20 Plan 04: Structured Feedback Layer and Persistent Corrections Summary

Persistent corrections table + structured feedback UI completing FIX-01. Users can now set tone/emphasis/length controls when regenerating, and corrections that accumulate per SKU ensure repeated issues get resolved permanently.

## What Was Built

### Task 1: sku_corrections Migration and Python Endpoint Wiring

Created `supabase/migrations/036_sku_corrections.sql` with:
- `sku_corrections` table scoped by master_sku/platform/content_type
- `is_active` boolean for soft-deletion/deactivation
- Lookup index on (master_sku, platform, content_type, is_active)
- Unique index on (master_sku, platform, content_type, correction_type, correction_text) WHERE is_active = TRUE to prevent duplicates
- Applied to remote Supabase database

Updated `src/feedops/api/main.py` `RegenerateRequest`:
- New fields: `tone_style`, `emphasis` (list), `length_preference`, `save_as_correction`
- Correction lookup before generation: fetches active corrections filtered by platform IN (request.platform, 'all')
- Session feedback built from structured fields + free-text
- Correction save after successful generation when `save_as_correction=True`

### Task 2: Dashboard Structured Feedback UI

Updated `dashboard/src/app/api/regenerate/route.ts`:
- Added `tone_style`, `emphasis`, `length_preference`, `save_as_correction` to `RegenerateRequest` interface
- Forwards all structured feedback fields to Cloud Run pipeline

Updated `dashboard/src/components/review/FeedbackModal.tsx` with collapsible "Advanced Feedback Controls":
- Tone/style selector: Formal, Conversational, Technical, Aspirational (toggle buttons)
- Content emphasis: Finish Details, Dimensions/Size, Use Case, Compatibility, Luxury Positioning (multi-select pills)
- Length control: Shorter, Standard, Longer (toggle buttons)
- "Remember this correction for future regenerations" checkbox with amber-tinted warning box

Updated `dashboard/src/components/review/RegenerateButton.tsx`:
- Imports `StructuredFeedback` type from FeedbackModal
- Passes structured fields through to `/api/regenerate` payload

## Verification

- `sku_corrections` table confirmed in Supabase (verified via execute_sql RPC)
- `grep -n 'sku_corrections'` finds both lookup and save logic in main.py
- `grep -n 'tone_style'` finds new fields in both main.py and route.ts
- `npm run build` passes with zero TypeScript errors
- `npx tsc --noEmit` zero errors
- `npm run lint` zero errors (1 pre-existing img warning unrelated to plan)

## Deviations from Plan

### Auto-fixed: Migration delivery method

**Found during:** Task 1 - supabase db push

**Issue:** Supabase migration system had duplicate-numbered files (004, 026, 032, etc.) causing `db push` to fail with duplicate key violations. The `--include-all` flag tried to re-apply already-applied migrations.

**Fix:** Temporarily renamed the duplicate local-only migration files (with `_TEMP_` prefix) to make them unrecognized by the CLI, applied only migration 036, then restored the renamed files.

**Files modified:** supabase migration system state (no code changes)

**Impact:** Minimal — migration system state was not altered beyond marking 036 as applied.

### Plan note honored: prompt_builder.py from 20-03 was available

The `<important_note>` said to create apply_feedback_layer integration points if prompt_builder.py didn't exist. It did exist (20-03 completed first), so the full integration was implemented directly rather than stub code.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| supabase/migrations/036_sku_corrections.sql exists | FOUND |
| dashboard/src/components/review/FeedbackModal.tsx exists | FOUND |
| Task 1 commit (2c46e4b1) exists | FOUND |
| Task 2 commit (963cbafc) exists | FOUND |
| sku_corrections table in Supabase | VERIFIED (9 columns: id, master_sku, platform, content_type, correction_text, correction_type, is_active, created_at, updated_at) |
