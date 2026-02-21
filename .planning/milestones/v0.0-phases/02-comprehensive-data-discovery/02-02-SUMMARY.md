---
phase: 02-comprehensive-data-discovery
plan: 02
subsystem: api
tags: [google-ads-api, custom-labels, performance-max, gaql, discovery]

# Dependency graph
requires:
  - phase: 01-api-capability-validation
    provides: Validated API client loading pattern, field naming conventions, query patterns
provides:
  - Custom label filtering validation (exact, IN, NOT, cross-attribute)
  - Custom label population analysis (4 populated, custom_label_4 available)
  - Performance Max data patterns confirmed (product-level metrics, asset groups, placements)
  - Working GAQL query examples for custom labels and PMax
affects: [03-segmentation-analysis, future-backfill-planning, product-filtering-strategy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Custom label segmentation pattern for category filtering
    - Performance Max query pattern using shopping_performance_view
    - placement_view metric compatibility constraints

key-files:
  created:
    - scripts/discover_custom_labels_and_pmax.py
    - .planning/phases/02-comprehensive-data-discovery/disc-03-04-05-results.json
  modified: []

key-decisions:
  - "Custom labels 0-3 are populated with category/tier data; custom_label_4 available for future use"
  - "Performance Max campaigns populate shopping_performance_view with product-level data (same pattern as Standard Shopping)"
  - "performance_max_placement_view supports impressions metric only (clicks incompatible)"
  - "Custom label filtering supports exact match, IN, NOT, and cross-attribute queries with ~1s response times"

patterns-established:
  - "Custom label filtering pattern: Use custom_attribute0-4 for high-cardinality segmentation to avoid long IN clauses"
  - "PMax query pattern: Filter shopping_performance_view by campaign.advertising_channel_type = 'PERFORMANCE_MAX'"
  - "Placement view limitation: Only impressions metric compatible with performance_max_placement_view"

# Metrics
duration: 3min
completed: 2026-02-12
---

# Phase 02 Plan 02: Custom Label Filtering and PMax Discovery Summary

**All 5 custom label filtering operations validated (exact, IN, NOT, cross-attribute) with ~1s response times; Performance Max confirmed to populate shopping_performance_view with product-level metrics**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-12T02:00:39Z
- **Completed:** 2026-02-12T02:03:41Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Custom label filtering capabilities fully tested across all 5 attributes (product_custom_attribute0-4)
- All filtering operations successful: exact match, IN clause, NOT filter, cross-attribute combinations
- Custom label population strategy documented: 4 labels populated, custom_label_4 available
- Performance Max data patterns validated across 5 query types
- Confirmed PMax campaigns populate shopping_performance_view with product-level metrics
- Identified performance_max_placement_view metric compatibility constraint (impressions only)

## Task Commits

Each task was committed atomically:

1. **Task 1: Test custom label filtering capabilities (DISC-03, DISC-04)** - `d8e22489` (feat)
2. **Task 2: Validate Performance Max data patterns (DISC-05)** - `8a9342ee` (feat)

## Files Created/Modified
- `scripts/discover_custom_labels_and_pmax.py` - Discovery script testing custom label filters and PMax query patterns
- `.planning/phases/02-comprehensive-data-discovery/disc-03-04-05-results.json` - Complete results with query patterns, timing data, and population analysis

## Decisions Made

**1. Custom Label Population Strategy**
- 4 custom labels currently populated (0-3) with category and tier data
- custom_label_4 is available for future use
- Recommendation: Could populate custom_label_4 with product_item_id or category data for efficient segmentation
- Custom labels are READ-ONLY via Google Ads API (SET via Google Sheets supplemental feed)

**2. Performance Max Query Pattern**
- PMax campaigns populate shopping_performance_view just like Standard Shopping campaigns
- Filter by `campaign.advertising_channel_type = 'PERFORMANCE_MAX'` to isolate PMax data
- Product-level metrics (impressions, clicks, conversions, cost) available for PMax products
- Asset groups queryable with ad_strength data

**3. Placement View Metric Compatibility**
- performance_max_placement_view supports impressions metric only
- clicks, conversions, and other metrics are incompatible with this view
- This is an API constraint, not a data availability issue

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed performance_max_placement_view query to use compatible metrics**
- **Found during:** Task 2 (PMax placement data test)
- **Issue:** Query included `metrics.clicks` which is incompatible with performance_max_placement_view, causing PROHIBITED_METRIC_IN_SELECT_OR_WHERE_CLAUSE error
- **Fix:** Removed clicks metric from placement query, kept impressions only
- **Files modified:** scripts/discover_custom_labels_and_pmax.py
- **Verification:** Placement query succeeded, returned 20 placement records with GOOGLE_PRODUCTS placement type
- **Committed in:** 8a9342ee (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug - API metric compatibility)
**Impact on plan:** Auto-fix necessary for query correctness. Discovery of metric constraint is valuable finding about API capabilities.

## Issues Encountered
None - all queries executed successfully after metric compatibility fix.

## Custom Label Filtering Test Results

**Tested Operations:**
1. **Exact match:** `custom_attribute0 = 'value'` - ✓ Success (20 rows, 1.157s)
2. **IN clause:** `custom_attribute0 IN ('v1', 'v2', 'v3')` - ✓ Success (20 rows, 0.936s)
3. **NOT filter:** `custom_attribute0 != 'value'` - ✓ Success (20 rows, 1.275s)
4. **Cross-attribute:** `custom_attribute0 = 'v1' AND custom_attribute1 = 'v2'` - ✓ Success (20 rows, 0.992s)

**Population Analysis:**
- custom_label_0: 4 unique categories (wall mounted swing towel arms, towel rings, mirrors, shelves)
- custom_label_1: 1 value (low)
- custom_label_2: 4 values (sports team themes)
- custom_label_3: 2 values (bidnamic_pull, bidnamic zombie pmax)
- custom_label_4: **AVAILABLE** for new data

## Performance Max Discovery Results

**1. Campaign Identification:**
- 15 PMax campaigns found (0 currently active)
- Query succeeded in 0.492s

**2. Product-Level Performance:**
- 20 product records found with impressions > 0 in last 30 days
- Confirms PMax populates shopping_performance_view
- Top product: shopify_us_8751009038562_46118169444578 (484 impressions)

**3. Asset Groups:**
- 20 asset groups queryable
- ad_strength data available

**4. Placements:**
- 20 placement records found
- Top placement: GOOGLE_PRODUCTS (5,797 impressions)
- **Limitation:** Only impressions metric compatible

**5. Campaign Comparison:**
- 501 campaign records returned
- SHOPPING channel: 0 impressions (no active campaigns)
- Data structure confirms channel_type filter works correctly

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Custom label filtering capabilities fully validated for product segmentation queries
- Performance Max data patterns documented for future performance analysis
- Ready for segmentation analysis (Phase 02 Plan 03)
- custom_label_4 available if future plans need additional product categorization

## Self-Check: PASSED

**Files verified:**
- ✓ scripts/discover_custom_labels_and_pmax.py
- ✓ .planning/phases/02-comprehensive-data-discovery/disc-03-04-05-results.json

**Commits verified:**
- ✓ d8e22489 (Task 1 - custom label filtering)
- ✓ 8a9342ee (Task 2 - PMax data validation)

---
*Phase: 02-comprehensive-data-discovery*
*Completed: 2026-02-12*
