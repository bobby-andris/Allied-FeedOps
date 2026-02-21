---
phase: 07-data-quality-validation
plan: 02
subsystem: data-collection
tags: [validation, data-quality, multi-sku, contamination-prevention]
dependency-graph:
  requires:
    - phase-06-data-collection-pipeline
    - docs/architecture/multi-sku-pattern.md
  provides:
    - multi-SKU family detection
    - publish contamination prevention
    - baseline eligibility validation
  affects:
    - performance_baselines (adds metadata column)
    - backfill job workers
tech-stack:
  added:
    - contamination.py (publish event validation)
    - multi_sku.py (family detection)
  patterns:
    - Batch eligibility checking
    - JSONB metadata storage
    - Date boundary validation
key-files:
  created:
    - src/feedops/jobs/multi_sku.py
    - src/feedops/jobs/contamination.py
    - supabase/migrations/030_add_performance_baselines_metadata.sql
  modified:
    - src/feedops/jobs/workers.py
    - src/feedops/jobs/validators.py
decisions:
  - title: "Multi-SKU metadata in JSONB column"
    rationale: "Flexible metadata storage without schema changes for future validation flags"
    alternatives: ["Separate table", "Boolean columns"]
    choice: "JSONB metadata column"
  - title: "Batch eligibility check before data fetch"
    rationale: "Prevents wasted API calls for ineligible SKUs"
    alternatives: ["Check during upsert", "Check in separate pre-validation step"]
    choice: "Check before fetch"
  - title: "30-day contamination threshold"
    rationale: "Ensures sufficient separation between baseline and post-publish periods"
    alternatives: ["14 days", "60 days"]
    choice: "30 days (configurable via VALIDATION_THRESHOLDS)"
metrics:
  duration: 228
  tasks-completed: 2
  files-created: 3
  files-modified: 2
  lines-added: 695
  commits: 2
  completed-date: 2026-02-13
---

# Phase 07 Plan 02: Multi-SKU Detection and Contamination Prevention Summary

**One-liner:** Multi-SKU family detection via shopify_product_id matching and publish contamination prevention with 30-day threshold for baseline data integrity.

## Overview

Implemented validation logic to ensure baseline performance data integrity by detecting multi-SKU families (where multiple master_skus share the same product_id) and preventing baseline capture for recently published SKUs. Multi-SKU families are flagged in the database with JSONB metadata, and SKUs published within 30 days are automatically skipped during baseline collection.

## Implementation Details

### Multi-SKU Family Detection (VALID-03, VALID-08)

Created `src/feedops/jobs/multi_sku.py` with three functions:

1. **detect_multi_sku_families(master_skus)**: Batch detection of multi-SKU families
   - Queries variant_index for shopify_product_id
   - Groups by product_id to find families with >1 master_sku
   - Returns dict mapping each SKU to its family members
   - Example: DMF-2/2X, DMF-2/3X, DMF-2/4X all share product_id 4539975336068

2. **is_multi_sku_family(master_sku)**: Quick single-SKU check
   - More efficient than batch function for one-off checks
   - Uses count query instead of fetching all variants

3. **get_family_metadata(master_sku, family_members)**: Generate metadata dict
   - Returns JSONB-ready metadata for database storage
   - Includes: is_multi_sku_family, family_members, family_size, data_aggregation
   - Stored in performance_baselines.metadata column

### Publish Contamination Prevention (VALID-04, VALID-09)

Created `src/feedops/jobs/contamination.py` with three functions:

1. **check_baseline_eligibility(master_sku, platform)**: Single SKU check
   - Queries publish_events for successful publishes within 30-day threshold
   - Returns (eligible: bool, reason: str)
   - Threshold configurable via VALIDATION_THRESHOLDS

2. **check_batch_eligibility(master_skus, platform)**: Batch check
   - Single query for entire batch (more efficient)
   - Returns dict mapping each SKU to (eligible, reason)
   - SKUs without publish events marked eligible

3. **validate_date_boundaries(start, end, master_sku, platform)**: Date overlap check
   - Ensures baseline period doesn't overlap with any publish event
   - Additional validation after contamination threshold check
   - Prevents edge cases where baseline window spans a publish

### Worker Integration

Updated `src/feedops/jobs/workers.py` collect_performance_batch():

**Execution flow:**
1. **Contamination check** (before data fetch): Filters ineligible SKUs, prevents wasted API calls
2. **Data collection**: Fetches only for eligible SKUs
3. **Multi-SKU detection** (after aggregation): Identifies families via product_id matching
4. **Date boundary validation** (before upsert): Ensures no overlap with publish events
5. **Metadata storage**: Adds family flags to baseline_record.metadata

**Result statuses:**
- `ok`: Data collected successfully
- `skipped`: Ineligible due to recent publish or date overlap
- `no_data`: No performance data found
- `validation_error`: Data validation failed

Multi-SKU families are flagged in result with `multi_sku_family: true` and `family_size: N`.

### Database Changes

**Migration 030**: Added metadata JSONB column to performance_baselines
```sql
ALTER TABLE performance_baselines ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
```

**Metadata structure:**
```json
{
  "is_multi_sku_family": true,
  "family_members": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X"],
  "family_size": 3,
  "data_aggregation": "product_id_level"
}
```

Non-family SKUs: `{"is_multi_sku_family": false}`

### Validation Updates

Updated `src/feedops/jobs/validators.py`:

1. **Added contamination threshold**: `baseline_contamination_days: 30` to VALIDATION_THRESHOLDS
2. **Updated ValidatedPerformanceMetrics**: Added `metadata` field with default `{"is_multi_sku_family": false}`

## Deviations from Plan

None - plan executed exactly as written.

## Testing

All modules import successfully:
```bash
python -c "from feedops.jobs.multi_sku import detect_multi_sku_families, is_multi_sku_family, get_family_metadata"
python -c "from feedops.jobs.contamination import check_baseline_eligibility, check_batch_eligibility, validate_date_boundaries"
python -c "from feedops.jobs.workers import collect_performance_batch"
```

Integration verified via grep:
- `check_batch_eligibility` called at line 228 (before fetch)
- `detect_multi_sku_families` called at line 314 (after aggregation)
- `validate_date_boundaries` called at line 350 (before upsert)

## Key Learnings

1. **Product-ID level aggregation**: Google Ads aggregates performance at product_id (not master_sku), requiring family detection and flagging
2. **Contamination prevention**: SKUs published within 30 days must be excluded to avoid mixing pre/post-optimization data
3. **JSONB flexibility**: Metadata column supports future validation flags without schema changes
4. **Batch efficiency**: Eligibility checks before API calls prevent wasted quota on ineligible SKUs

## Files Changed

**Created:**
- `src/feedops/jobs/multi_sku.py` (202 lines)
- `src/feedops/jobs/contamination.py` (169 lines)
- `supabase/migrations/030_add_performance_baselines_metadata.sql` (8 lines)

**Modified:**
- `src/feedops/jobs/workers.py` (+91 lines)
- `src/feedops/jobs/validators.py` (+2 lines)

**Total:** 472 lines added

## Commits

1. **f7b3a9fc**: feat(07-02): add multi-SKU detection and publish contamination prevention
   - Created multi_sku.py and contamination.py modules
   - Implements VALID-03, VALID-04, VALID-09

2. **be07bbcb**: feat(07-02): integrate contamination and multi-SKU checks into performance worker
   - Updated validators.py and workers.py
   - Added migration 030 for metadata column
   - Implements VALID-08 (database flagging)

## Next Steps

Plan 07-03 will implement validation testing to verify contamination prevention and multi-SKU detection work correctly with real data.

---

## Self-Check: PASSED

**Files exist:**
```bash
✓ src/feedops/jobs/multi_sku.py
✓ src/feedops/jobs/contamination.py
✓ supabase/migrations/030_add_performance_baselines_metadata.sql
```

**Commits exist:**
```bash
✓ f7b3a9fc: feat(07-02): add multi-SKU detection and publish contamination prevention
✓ be07bbcb: feat(07-02): integrate contamination and multi-SKU checks into performance worker
```

**Integration verified:**
```bash
✓ check_batch_eligibility referenced in workers.py (line 228)
✓ detect_multi_sku_families referenced in workers.py (line 314)
✓ validate_date_boundaries referenced in workers.py (line 350)
```

All deliverables confirmed.
