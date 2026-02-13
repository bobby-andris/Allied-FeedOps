---
phase: 06-data-collection-pipeline
plan: 01
subsystem: data-collection
tags: [workers, batch-processing, google-ads, merchant-center, idempotent]

dependency_graph:
  requires:
    - phase: 05
      plan: all
      reason: "BatchProcessor infrastructure and job management layer"
  provides:
    - "4 async worker functions for data collection (search terms, performance, keyword planner, custom labels)"
    - "Idempotent batch collection logic with campaign-join and aggregation patterns"
    - "GMC custom labels sync with JSONB storage in variant_index"
  affects:
    - "Phase 2 backfill API endpoints (will route to these workers)"
    - "Data collection automation (scheduled jobs, dashboard triggers)"

tech_stack:
  added:
    - KeywordPlannerClient (30-day cache TTL)
    - fetch_merchant_center_items (GMC API integration)
  patterns:
    - Campaign-join pattern for search terms (2-step query with variant lookup)
    - Variant aggregation for performance metrics (sum impressions/clicks, weighted avg CTR)
    - Module-level caching for GMC data (5-minute TTL, reused across batches)
    - Idempotent upserts with ON CONFLICT for all database writes

key_files:
  created:
    - src/feedops/jobs/workers.py
    - supabase/migrations/026_add_custom_labels_to_variant_index.sql
  modified:
    - src/feedops/jobs/__init__.py

decisions:
  - title: "GMC Data Caching Strategy"
    context: "GMC API returns all products at once (expensive call)"
    options:
      - "Call GMC API per batch (wasteful for consecutive batches)"
      - "Cache at worker level with TTL (chosen)"
    rationale: "Module-level cache with 5-minute TTL avoids redundant API calls across consecutive batches within same job run"
    impact: "Significant API cost reduction for large backfill jobs"

  - title: "Search Terms Filtering Approach"
    context: "SearchTermsClient.fetch_search_terms() returns ALL search terms with master_sku populated"
    options:
      - "Pass batch to client for filtering (requires client modification)"
      - "Filter results after fetch in worker (chosen)"
    rationale: "Client is batch-native (campaign-join pattern doesn't support per-SKU filtering). Worker filtering is simple and preserves client API."
    impact: "Clean separation of concerns; client handles campaign-join, worker handles batch filtering"

metrics:
  duration_seconds: 210
  duration_minutes: 3.5
  completed_at: "2026-02-13T10:33:52Z"
  tasks_completed: 2
  commits: 2
  files_created: 2
  files_modified: 1
---

# Phase 06 Plan 01: Data Collection Workers Summary

**One-liner:** 4 async batch collection workers (search terms, performance, keyword planner, custom labels) with idempotent upserts, campaign-join pattern, variant aggregation, and GMC caching.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement Google Ads collection workers | 1decab30 | workers.py |
| 2 | Implement Keyword Planner and Custom Labels workers | 5f564e0e | workers.py, __init__.py, 026_migration |

## Implementation Details

### Worker 1: Search Terms Collection (`collect_search_terms_batch`)

**Purpose:** Collect Google Ads search terms for a batch of master SKUs using campaign-join pattern.

**Key Features:**
- Uses `SearchTermsClient.fetch_search_terms()` with campaign-join pattern (DATA-01)
- Fetches ALL search terms, then filters to batch SKUs (client is batch-native)
- Saves via `save_search_terms_to_db()` with idempotent upserts (ON CONFLICT: query_text, gmc_offer_id, period_start, period_end)
- Uses explicit YYYY-MM-DD date ranges via `compute_date_range(180)` (DATA-07)
- Returns `{"item_id": sku, "status": "ok", "terms_count": N}` or `"no_data"` status

**Data Flow:**
1. Initialize SearchTermsClient
2. Compute 180-day date range (explicit YYYY-MM-DD format)
3. Fetch all search terms (campaign-join pattern)
4. Filter to batch SKUs using master_sku field (populated via get_variant_info() lookup)
5. Save with idempotent upserts
6. Return status for each SKU

### Worker 2: Performance Metrics Collection (`collect_performance_batch`)

**Purpose:** Collect 180-day performance metrics from Google Ads, aggregate to master_sku level.

**Key Features:**
- Queries `variant_index` to get all `gmc_offer_id` values for each master_sku
- Calls `fetch_batch_product_performance()` with all offer IDs in one batch (efficient)
- Aggregates variant-level metrics: sum impressions/clicks/conversions, weighted avg CTR
- Upserts to `performance_baselines` with ON CONFLICT (master_sku, platform)
- Includes `baseline_start_date` and `baseline_end_date` fields (DATA-05)
- Calculates avg_* fields by dividing totals by 180 days (DATA-02)

**Data Flow:**
1. Build offer_id → master_sku mapping from variant_index
2. Fetch batch performance for all variants
3. Aggregate metrics to master_sku level
4. Calculate averages (avg_impressions, avg_clicks, avg_ctr, etc.)
5. Upsert to performance_baselines with date range fields
6. Return status with totals for each SKU

### Worker 3: Keyword Planner Collection (`collect_keyword_planner_batch`)

**Purpose:** Enrich keywords with Keyword Planner historical metrics (search volume, competition, CPC).

**Key Features:**
- Queries `variant_index` for product_title (seed keyword)
- Queries `search_queries` for top 5 existing search terms (additional seeds)
- Calls `KeywordPlannerClient.get_historical_metrics()` with `use_cache=True, cache_max_age_days=30` (DATA-03)
- Client handles caching internally (idempotent upserts to keyword_metrics table)
- Rate limiting applied at BatchProcessor level (not in worker)

**Data Flow:**
1. Get product_title from variant_index
2. Get top 5 search terms from search_queries
3. Build keyword list: [product_title] + top_search_terms
4. Fetch metrics with 30-day cache
5. Return status with keywords_enriched count

### Worker 4: Custom Labels Collection (`collect_custom_labels_batch`)

**Purpose:** Sync custom labels 0-4 from GMC to variant_index.custom_labels JSONB column.

**Key Features:**
- Calls `fetch_merchant_center_items()` ONCE (GMC API returns all products)
- Module-level cache with 5-minute TTL (_gmc_cache global, reused across batches)
- Normalizes offer IDs to lowercase for lookup (DATA-08)
- Updates `variant_index.custom_labels` with JSONB value `{"customLabel0": val, ...}`
- Idempotent via `.update().eq("gmc_offer_id", offer_id)` (unique constraint)
- Includes `updated_at` timestamp (DATA-10)

**Data Flow:**
1. Check module-level cache (5-minute TTL)
2. If expired: fetch GMC items, build {offerId: labels} lookup, cache
3. For each master_sku: get variants from variant_index
4. Update custom_labels JSONB for each variant
5. Return status with variants_updated count

## Database Changes

**Migration 026:** Add `custom_labels` JSONB column to `variant_index`

```sql
ALTER TABLE variant_index ADD COLUMN IF NOT EXISTS custom_labels jsonb;
COMMENT ON COLUMN variant_index.custom_labels IS 'Custom labels 0-4 from GMC...';
```

This column stores GMC custom labels as `{"customLabel0": "value", "customLabel1": "value", ...}`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verification commands passed:

```bash
# Workers 1 & 2
PYTHONPATH=./src python -c "from feedops.jobs.workers import collect_search_terms_batch, collect_performance_batch; print('OK')"

# Workers 3 & 4
PYTHONPATH=./src python -c "from feedops.jobs.workers import collect_keyword_planner_batch, collect_custom_labels_batch; print('OK')"

# Package exports
PYTHONPATH=./src python -c "from feedops.jobs import collect_search_terms_batch, collect_performance_batch, collect_keyword_planner_batch, collect_custom_labels_batch; print('All 4 workers imported')"
```

## Integration Points

### Phase 1 Infrastructure (05-*)
- Workers match `process_fn` signature: `async def fn(batch: list[str]) -> list[dict]`
- Used by `BatchProcessor` (05-02) with rate limiting and checkpointing
- Managed by job manager functions (05-01): create_job, update_job_status, etc.
- Invoked via backfill API endpoints (05-03): /backfill/start, /backfill/resume

### Existing Clients (DO NOT re-implement)
- `SearchTermsClient` (google_ads_search_terms.py)
- `KeywordPlannerClient` (google_ads_search_terms.py)
- `fetch_batch_product_performance` (google_ads_performance.py)
- `fetch_merchant_center_items` (merchant_center.py)

### Database Tables
- `search_queries` (search terms with variant-level tracking)
- `performance_baselines` (master_sku-level 180-day metrics)
- `keyword_metrics` (cached Keyword Planner data)
- `variant_index` (SKU ↔ offer ID mapping + custom_labels JSONB)

## Next Steps

**Phase 2 (06-02):** Update backfill API endpoints to route to real workers
- Replace `_noop_process` placeholder with worker function routing
- Map job_type → worker function
- Verify idempotent resume after checkpoint

**Phase 3 (06-03):** Implement full backfill orchestration
- Combine all 4 workers into single "full_backfill" job type
- Add inter-worker dependencies (e.g., search terms → keyword planner)

**Phase 4 (06-04):** Add monitoring and alerting
- Job failure notifications
- Data staleness detection
- API rate limit monitoring

## Success Criteria

- [x] All 4 worker functions exist in `src/feedops/jobs/workers.py`
- [x] All functions match BatchProcessor's `process_fn` signature
- [x] Search terms worker uses SearchTermsClient (campaign-join pattern)
- [x] Performance worker uses fetch_batch_product_performance with variant aggregation
- [x] Keyword Planner worker uses KeywordPlannerClient with 30-day caching
- [x] Custom labels worker uses fetch_merchant_center_items with variant_index.custom_labels JSONB upserts
- [x] All workers use idempotent database writes (ON CONFLICT or unique constraint)
- [x] All workers include collection timestamps
- [x] Workers are exported from feedops.jobs package
- [x] Migration 026 adds custom_labels column to variant_index

## Self-Check: PASSED

**Created Files:**
```bash
✓ src/feedops/jobs/workers.py (exists, 599 lines)
✓ supabase/migrations/026_add_custom_labels_to_variant_index.sql (exists)
```

**Modified Files:**
```bash
✓ src/feedops/jobs/__init__.py (exports all 4 workers)
```

**Commits:**
```bash
✓ 1decab30 - feat(06-01): implement search terms and performance collection workers
✓ 5f564e0e - feat(06-01): implement Keyword Planner and Custom Labels workers
```

All claims verified.
