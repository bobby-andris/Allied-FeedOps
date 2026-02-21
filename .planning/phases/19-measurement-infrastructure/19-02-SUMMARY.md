---
phase: 19-measurement-infrastructure
plan: 02
subsystem: dashboard-api
tags: [bottleneck-classifier, prompt-lineage, api-routes, typescript, measurement]
dependency_graph:
  requires: [supabase/migrations/035_measurement_infrastructure_schema.sql]
  provides: [POST /api/bottleneck/classify, GET /api/bottleneck/status, GET /api/prompt-lineage]
  affects: [Plan 03 (UI layer reads these endpoints)]
tech_stack:
  added: []
  patterns: [Next.js API routes, Supabase JS client, decision tree classification]
key_files:
  created:
    - dashboard/src/app/api/bottleneck/classify/route.ts
    - dashboard/src/app/api/bottleneck/status/route.ts
    - dashboard/src/app/api/prompt-lineage/route.ts
  modified: []
decisions:
  - "Delete-then-insert pattern for auto-classifications instead of true upsert — Supabase JS client cannot target partial unique indexes directly"
  - "Return full classification results in batch mode response for immediate client use"
  - "prompt-lineage uses maybeSingle() for optional alias/history lookups to avoid 406 errors"
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 3
  files_modified: 0
  completed_date: "2026-02-21"
---

# Phase 19 Plan 02: Bottleneck Classifier + Prompt Lineage API Summary

Three API routes providing the TypeScript backend for MEAS-03 (prompt lineage) and MEAS-04 (bottleneck classifier). These endpoints read existing Supabase signals to produce diagnostic labels per SKU, and trace published content back to the exact prompt version that generated it.

## What Was Built

### POST /api/bottleneck/classify
Decision tree classifier implementing 5 bottleneck categories in priority order:

1. **coverage_gap** (confidence 0.95): No `generated_content` row for this SKU
2. **code_path_gap** (confidence 0.90): Content exists but no successful `publish_events` row
3. **propagation_failure** (confidence 0.85): Published but `performance_snapshots` shows 0 impressions after 7+ days
4. **query_relevance** (confidence 0.75): >2 keywords in `keyword_coverage_master` with `in_title=false` AND `query_volume > 100`
5. **auction_bid** (confidence 0.60): Default fallback — all other signals clear

Additional modes:
- **Manual override**: `override_classification` + `override_by` params insert an `is_override=true` row
- **Batch mode**: `?batch=true` classifies all SKUs in `generated_content` using chunked parallel processing (20 concurrent)

Each classification includes an `evidence` JSONB object documenting which check was triggered and the supporting data.

### GET /api/bottleneck/status
Reads `sku_bottleneck_classifications` with optional filters:
- `master_sku`: filter to one SKU
- `classification`: filter by category
- `limit`: max results (default 100, max 1000)

Per-SKU deduplication prefers override rows over auto-classification. Returns:
- `classifications[]`: filtered results
- `total_count`: filtered count
- `by_category`: summary counts for all 5 categories (always computed over full table)

### GET /api/prompt-lineage
Full lineage chain for a published SKU:
- Queries latest successful `publish_events` row for the SKU + platform
- Returns `{ lineage: null, note: '...' }` for historical data with null `prompt_hash`
- Looks up human-readable alias from `prompt_version_aliases`
- Retrieves generation metadata from `regeneration_history` (flags, model, tokens, latency, quality)

Compare mode (`?compare=true&hash_a=X&hash_b=Y`):
- Returns two generation entries side-by-side for A/B prompt analysis
- Deduplicates to one entry per hash (most recent generation with that hash)

## Decisions Made

1. **Delete-then-insert for auto-classifications**: Supabase JS `.upsert()` cannot target partial unique indexes (WHERE clause) — the partial unique index `idx_sku_bottleneck_master_sku WHERE is_override = false` prevents direct upsert. Solution: DELETE existing auto row then INSERT new one. Override rows accumulate as history (no dedup needed).

2. **`maybeSingle()` for optional lookups**: Using `.maybeSingle()` instead of `.single()` for `prompt_version_aliases` and `regeneration_history` lookups avoids PostgREST 406 errors when rows don't exist. These are soft dependencies — the endpoint works without them.

3. **Batch mode chunked processing**: 20 concurrent SKU classifications per chunk avoids DB connection exhaustion while maintaining reasonable throughput for the expected ~79 SKUs with generated content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing build failure from empty @types directories**
- **Found during:** Task 1 verification (`npm run build`)
- **Issue:** `node_modules/@types/` contained 18 empty directories with spaces in their names (e.g., `d3-array 2`, `node 2`) causing TypeScript to fail looking up non-existent type definitions. This was a pre-existing blocker unrelated to our changes.
- **Fix:** Removed all 18 empty directories with `rmdir` — they were empty so removal was safe.
- **Files modified:** `node_modules/@types/` (not tracked in git)
- **Commit:** Included in Task 1 commit 460e507e

## Self-Check: PASSED

| Item | Status |
|------|--------|
| dashboard/src/app/api/bottleneck/classify/route.ts | FOUND |
| dashboard/src/app/api/bottleneck/status/route.ts | FOUND |
| dashboard/src/app/api/prompt-lineage/route.ts | FOUND |
| Commit 460e507e (Task 1) | FOUND |
| Commit 6aa8c985 (Task 2) | FOUND |
