---
status: complete
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

- truth: "Changing time selectors updates metric values correctly for each master SKU"
  status: failed
  reason: "User reported: I think that there is something wrong with the variant sku data for each master SKU and therefore making all the metrics wrong"
  severity: major
  test: 2
  artifacts: []
  missing: []
- truth: "Some published SKUs unexpectedly show 'No snapshot' — data coverage needs investigation"
  status: failed
  reason: "User reported: there are a few rows that show 'No Snapshot' which should be investigated"
  severity: minor
  test: 6
  artifacts: []
  missing: []
- truth: "Delta values show accurate non-zero percentages for published SKUs with snapshots"
  status: failed
  reason: "User reported: There are a decent amount of rows that show 0 so we need to check these numbers to ensure they are accurate"
  severity: major
  test: 5
  artifacts: []
  missing: []
- truth: "Expanded inline panel shows variant breakdown (per-finish impressions/clicks) for each SKU"
  status: failed
  reason: "User reported: pass but a lot of SKUs show no variant data so we need to ensure that these queries are correct"
  severity: major
  test: 8
  artifacts: []
  missing: []
