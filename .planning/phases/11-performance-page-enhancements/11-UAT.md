---
status: diagnosed
phase: 11-performance-page-enhancements
source: [11-01-SUMMARY.md, 11-02-SUMMARY.md]
started: 2026-02-19T12:30:00Z
updated: 2026-02-19T13:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Delta table loads with published SKUs
expected: Navigate to /performance. Table shows published SKUs with columns for SKU name, publish date, days-since-publish, and metrics. Not empty (36 SKUs have snapshot data).
result: pass

### 2. Dual time selectors visible
expected: Two dropdowns appear above the table — one for Baseline window (7d/30d/60d) and one for Snapshot window (7d/30d/60d). Changing either selector updates the metric values shown.
result: issue
reported: "I think that there is something wrong with the variant sku data for each master SKU and therefore making all the metrics wrong"
severity: major

### 3. Days-since-publish column
expected: Each row shows how many days ago the SKU was published (e.g., "42d ago" or similar). This number reflects time since the actual publish event.
result: pass

### 4. Trend icons per row
expected: Each row with snapshot data shows a trending icon — green arrow up (≥+3%), red arrow down (≤-3%), or gray dash (within ±3%). Icons reflect the impressions delta direction.
result: pass

### 5. Delta values are sensible numbers
expected: Impressions and clicks deltas show reasonable percentages — not +2500% or wildly inflated. For example, a typical row might show -12% or +8%, not +2000%. An info banner explains that impressions/clicks show daily averages.
result: issue
reported: "There are a decent amount of rows that show 0 so we need to check these numbers to ensure they are accurate"
severity: major

### 6. Filter toggle: With snapshot vs All SKUs
expected: A toggle or filter button switches between "With snapshot" (only SKUs that have snapshot data, ~36 rows) and "All SKUs" (includes published SKUs without snapshots, shown with a muted/dimmed background and "No snapshot" badge).
result: issue
reported: "there are a few rows that show 'No Snapshot' which should be investigated"
severity: minor

### 7. Sortable columns
expected: Clicking a column header (e.g., CTR delta or impressions) sorts the table by that column. The sorted column shows a sort direction indicator. Clicking again reverses sort order.
result: pass

### 8. Inline SKU expand — variant breakdown + search terms
expected: Clicking a SKU row expands an inline panel below that row (list stays visible above/below). The panel shows two columns: left = per-finish variant performance (impressions/clicks), right = top search terms for that SKU.
result: issue
reported: "pass but a lot of SKUs show no variant data so we need to ensure that these queries are correct"
severity: major

### 9. Expand/collapse toggle, one row at a time
expected: A chevron icon in the first column toggles open/closed. Opening a second row closes the first. Clicking the open row again collapses it.
result: pass

## Summary

total: 9
passed: 5
issues: 4
pending: 0
skipped: 0

## Gaps

- truth: "Baseline avg_impressions and avg_clicks are accurate daily averages (not per-variant totals)"
  status: failed
  reason: "User reported: I think that there is something wrong with the variant sku data for each master SKU and therefore making all the metrics wrong"
  severity: major
  test: 2
  root_cause: "src/feedops/api/performance_baseline.py divides total_impressions by variants_with_data (variant count) instead of days_lookback (30 days). Stored baseline is a per-variant total, not a daily average. When route.ts normalizes the snapshot by snapshotWindowDays, the two values are on incompatible scales — baseline is inflated ~6x relative to current, making all deltas wrong."
  artifacts:
    - path: "src/feedops/api/performance_baseline.py"
      issue: "avg_impressions = total_impressions / variants_with_data — wrong divisor, should be / days_lookback"
    - path: "src/feedops/api/performance_baseline.py"
      issue: "avg_clicks = total_clicks / variants_with_data — same wrong divisor"
  missing:
    - "Change divisor to days_lookback in _capture_google_baseline()"
    - "Re-run baseline capture for all published SKUs to overwrite corrupt stored values"
- truth: "Delta values show accurate non-zero percentages for published SKUs with snapshots"
  status: failed
  reason: "User reported: There are a decent amount of rows that show 0 so we need to check these numbers to ensure they are accurate"
  severity: major
  test: 5
  root_cause: "route.ts snapshot window filter uses snapshot_date <= publishDate + snapshotWindowDays (absolute date ceiling). Snapshots are stored with snapshot_date = today's date (the API query end date). Any SKU published more than snapshotWindowDays (30d) before the snapshot capture date has its snapshot silently excluded. All 44 backfilled snapshots (captured Feb 2026 for SKUs published months earlier) are likely excluded — hasSnapshot=false → 0 deltas."
  artifacts:
    - path: "dashboard/src/app/api/performance/route.ts"
      issue: "lines 241-245: snapshots.find() with s.snapshot_date <= publishDatePlus — upper bound excludes all valid snapshots for older publishes"
  missing:
    - "Replace window filter with snapshots[0] (already sorted DESC) — most recent snapshot, no date ceiling"
- truth: "Some published SKUs unexpectedly show 'No snapshot' — data coverage needs investigation"
  status: failed
  reason: "User reported: there are a few rows that show 'No Snapshot' which should be investigated"
  severity: minor
  test: 6
  root_cause: "Same root cause as test 5 — the snapshot_date <= publishDatePlus window filter excludes snapshots for SKUs published more than snapshotWindowDays before capture. Every SKU published before ~Jan 20 (30 days before Feb 19 backfill) would show No Snapshot. This is not a missing snapshot issue — the data exists, but the query throws it away."
  artifacts:
    - path: "dashboard/src/app/api/performance/route.ts"
      issue: "lines 241-245: same upper-bound window filter as test 5"
  missing:
    - "Same fix as test 5 — use snapshots[0] instead of window filter"
- truth: "Expanded inline panel shows variant breakdown (per-finish impressions/clicks) for each SKU"
  status: failed
  reason: "User reported: pass but a lot of SKUs show no variant data so we need to ensure that these queries are correct"
  severity: major
  test: 8
  root_cause: "Two compounding issues: (1) google_ads_search_terms.py sync assigns search terms to item_ids[0] only (first product in campaign) — all other products in the campaign get master_sku=null in search_queries. (2) gmc_offer_id from Google Ads is uppercase (shopify_US_) but DB stores lowercase (shopify_us_), causing get_variant_info case-sensitive lookup to fail and write master_sku=null. Route.ts then queries .eq('master_sku', sku) which returns 0 rows for any SKU whose data has null master_sku."
  artifacts:
    - path: "src/feedops/integrations/google_ads_search_terms.py"
      issue: "lines 595-598: campaign-level join uses item_ids[0] only — all other products in campaign get no variant attribution"
    - path: "src/feedops/integrations/google_ads_search_terms.py"
      issue: "line 387: .eq('gmc_offer_id', gmc_offer_id) is case-sensitive but Google Ads returns shopify_US_ (uppercase) vs DB shopify_us_ (lowercase)"
    - path: "dashboard/src/app/api/performance/route.ts"
      issue: "lines 334-338: .eq('master_sku', sku) returns empty for rows with null master_sku"
  missing:
    - "In route.ts: join through variant_index to get all gmc_offer_ids for the master_sku, then query search_queries .in('gmc_offer_id', offerIds) — resilient to null master_sku in historical data"
    - "In google_ads_search_terms.py get_variant_info: lowercase the incoming gmc_offer_id before lookup (.eq('gmc_offer_id', gmc_offer_id.lower())) to fix future syncs"
