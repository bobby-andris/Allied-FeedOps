---
phase: 13-fix-google-ads-data-sourcing-variant-metrics-from-shopping-performance-view-and-per-campaign-search-terms-sync
plan: 02
subsystem: google-ads-integration
tags: [bug-fix, search-terms, variant-attribution, database-migration, data-quality]
dependency_graph:
  requires: [13-01]
  provides: [fixed-fetch-search-terms, synced_at-column, delete-before-insert]
  affects: [13-03-PLAN.md]
tech_stack:
  added: []
  patterns: [per-variant-fan-out, delete-before-insert, resume-safe-idempotency]
key_files:
  created:
    - supabase/migrations/027_add_synced_at_to_search_queries.sql
  modified:
    - src/feedops/integrations/google_ads_search_terms.py
    - src/feedops/jobs/workers.py
    - docs/database/SCHEMA.md
decisions:
  - "Bug 1 fix applied: replaced item_ids[0] with per-item_id loop (Option B fan-out) — each variant in a campaign gets its own search term row"
  - "Bug 2 fix SKIPPED: 13-01 empirical data confirmed baselines are non-zero for all tested SKUs — lowercase offer IDs work correctly with Google Ads API"
  - "Delete-before-insert strategy: per-SKU delete right before re-insert (not full table wipe) — resume-safe, only processed SKUs cleared"
  - "synced_at column: NULL = pre-fix data (wrong attribution), non-NULL = post-fix corrected data — enables auditing which rows have been re-synced"
metrics:
  duration: 2 minutes
  completed_date: 2026-02-19
  tasks: 2
  files: 4
---

# Phase 13 Plan 02: Fix Data Sourcing Bugs Summary

Fixed the two data sourcing bugs identified in 13-DIAGNOSIS.md: corrected per-variant search term attribution in `fetch_search_terms()` (fan-out instead of first-item), added per-SKU delete-before-insert to `collect_search_terms_batch()`, and created migration 027 adding the `synced_at` column to track which rows have been re-synced with corrected logic.

## Bugs Fixed

### Bug 1: Search Term Variant Attribution (FIXED)

**Location**: `src/feedops/integrations/google_ads_search_terms.py`, lines 599–641

**Before (broken):**
```python
if item_ids:
    gmc_offer_id = item_ids[0]  # Always highest-impression variant
    variant_info = self.get_variant_info(gmc_offer_id)

results.append({...single row with gmc_offer_id = item_ids[0]...})
```

**After (fixed):**
```python
if item_ids:
    for item_id in item_ids[:10]:  # Up to 10 variants per campaign
        variant_info = self.get_variant_info(item_id)
        results.append({...one row per item_id with gmc_offer_id = item_id...})
else:
    results.append({...single row with gmc_offer_id = None...})
```

**Impact**: FR-23 previously had 1 distinct gmc_offer_id in search_queries (UNL). After re-sync (Plan 3), it will have up to 28 — one per finish variant.

### Bug 2: Performance Metrics Offer ID Case (SKIPPED — NOT A BUG)

**Decision**: Empirical evidence from Plan 01 confirmed all 5 tested published SKUs have non-zero baselines (FR-23: 447.77 avg impressions, CL-24C: 618.37, CL-11: 475.30, CL-22: 222.70, A-20: 67.23). Lowercase offer IDs work correctly with the API. No fix applied to `google_ads_performance.py`.

## Changes Made

### `src/feedops/integrations/google_ads_search_terms.py`

1. **`fetch_search_terms()`** (lines 599–641): Replaced single-result append with a loop over `item_ids[:10]`, emitting one result dict per variant in the campaign. Empty-campaign fallback preserved (one null-offer-id row).

2. **`save_search_terms_to_db()`** (line 950): Added `"synced_at": datetime.utcnow().isoformat()` to the `deduped[key]` dict so every write post-fix is timestamped.

### `src/feedops/jobs/workers.py`

**`collect_search_terms_batch()`** (lines 135–155): Added per-SKU delete before calling `save_search_terms_to_db()`:
- Collects unique master_skus from validated_terms
- Deletes all existing search_queries rows for each SKU before re-inserting
- Resume-safe: only processed SKUs are cleared; un-processed SKUs retain original rows (distinguishable by synced_at=NULL)
- Uses `get_client()` imported inline (consistent with existing pattern in other workers)

### `supabase/migrations/027_add_synced_at_to_search_queries.sql` (NEW)

```sql
ALTER TABLE search_queries
  ADD COLUMN IF NOT EXISTS synced_at timestamp with time zone;

CREATE INDEX IF NOT EXISTS idx_search_queries_synced_at
  ON search_queries (synced_at);

COMMENT ON COLUMN search_queries.synced_at IS
  'Timestamp when this row was last synced with corrected Phase 13 logic. NULL = pre-fix data.';
```

### `docs/database/SCHEMA.md`

Added `synced_at` column row to the search_queries columns table and `idx_search_queries_synced_at` to the Indexes section.

## Deviations from Plan

None — plan executed exactly as written. Option B (fan-out per item_id) was chosen as directed. Performance metrics fix was correctly skipped based on diagnosis confirmation.

## Ready for Plan 3

No re-sync has been triggered. Plan 3 will:
1. Apply migration 027 to the live database
2. Trigger re-sync of all SKUs via `collect_search_terms_batch()`
3. Verify that affected SKUs (FR-23, A-20, CL-22, CL-11, CL-24C) now have multiple distinct gmc_offer_ids in search_queries

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix fetch_search_terms() variant attribution + add synced_at migration | a2307ee8 | google_ads_search_terms.py, 027_add_synced_at.sql, SCHEMA.md |
| 2 | Add per-SKU delete-before-insert to collect_search_terms_batch | 29a9ae5b | workers.py |

## Self-Check: PASSED

- [x] `src/feedops/integrations/google_ads_search_terms.py` exists and modified
- [x] `src/feedops/jobs/workers.py` exists and modified
- [x] `supabase/migrations/027_add_synced_at_to_search_queries.sql` exists (created)
- [x] `docs/database/SCHEMA.md` exists and updated
- [x] Commit a2307ee8 verified in git log
- [x] Commit 29a9ae5b verified in git log
- [x] All 7 plan verification criteria met
- [x] All 3 Python files pass syntax check
