---
phase: 11-performance-page-enhancements
plan: "02"
status: complete
completed: 2026-02-19
commits:
  - c02d75b2  # SKU detail endpoint + ExpandedSkuDetail panel
  - ac75cf44  # Inline ExpandedSkuDetail with variant breakdown and search terms
  - ce465933  # fix: normalize snapshot impressions/clicks to daily avg for valid delta
files_modified:
  - dashboard/src/app/api/performance/route.ts
  - dashboard/src/app/(dashboard)/performance/page.tsx
tasks_completed: 3
---

## What Was Built

### Task 1: SKU detail endpoint
- `GET /api/performance?sku=X` returns `skuDetail` with:
  - `variants[]`: per-finish impressions/clicks/CTR from `search_queries`, grouped in JS, sorted descending by impressions, top 20
  - `topSearchTerms[]`: deduplicated by query_text, summed impressions/clicks, top 10
- `skuDetail: null` when `sku` param absent (main list mode)

### Task 2: Inline ExpandedSkuDetail panel
- `expandedSku` string state (one-row-at-a-time, same pattern as Phase 9)
- Row click → fetches `?sku=X` → sets `skuDetail`, `detailLoading`
- Detail panel renders as `<TableRow colSpan={8}>` immediately below expanded row
- Two-column grid: variant performance table (left) + top search terms (right)
- ChevronDown/ChevronUp icon toggles in first cell

### Task 3: Data accuracy fix (post-execution discovery)
- **Bug found**: `performance_snapshots.impressions/clicks` store 30-day cumulative totals; `performance_baselines.avg_impressions/avg_clicks` store daily averages. Direct comparison produced +2500% deltas.
- **Fix**: In `route.ts`, divide `windowSnapshot.impressions` and `windowSnapshot.clicks` by `snapshotWindowDays` before building the `current` object. CTR and CVR are rates — unchanged.
- **Result**: Deltas now show valid daily-average comparison (e.g., 19,280 total ÷ 30 = 642/day → -12% vs 732/day baseline, not +2532%).
- Info banner updated to clarify impressions/clicks show daily averages.

## Decisions

- **Normalized daily averages in API** (not client): `snapshotWindowDays` already computed in route.ts; normalizing server-side means all downstream consumers (delta, sort, trend icons, summary cards) automatically get correct values.
- **Math.round for normalized values**: Avoids fractional impression counts in display (e.g., 642 not 642.67).
- **JS aggregation for search_queries**: Supabase client lacks GROUP BY; JS grouping by gmc_offer_id for variants, query_text for search terms.

## Phase 11 Success Criteria (All Met)

1. **PERF-01**: Delta comparison visible — baseline daily avg vs. snapshot daily avg per SKU ✓
2. **PERF-02**: Days-since-publish visible per row ✓
3. **PERF-03**: Color-coded trend icons (TrendingUp/Down/Minus, ±3% threshold) per row ✓
4. **VER-01**: Real data confirmed — 44 snapshots for 36 published SKUs ✓
5. **INLINE DETAIL**: Expandable row with variant breakdown + search terms ✓
6. **DATA ACCURACY**: Impressions/clicks deltas normalized to daily averages ✓

## Files Modified

- `dashboard/src/app/api/performance/route.ts`:
  - Added `SkuDetail`, `VariantPerformance`, `SearchTerm` interfaces
  - Added `sku` query param handling with variant breakdown + search term aggregation
  - Added `snapshotWindowDays` normalization for `current.impressions` and `current.clicks`
- `dashboard/src/app/(dashboard)/performance/page.tsx`:
  - Added `ExpandedSkuDetail` component
  - Added `expandedSku`, `skuDetail`, `detailLoading` state
  - Added `handleRowClick` with fetch to `?sku=X`
  - Updated info banner to clarify daily-average display
