---
phase: 02-comprehensive-data-discovery
plan: 01
subsystem: api
tags: [google-ads, api-discovery, shopping, performance-max, metrics]

# Dependency graph
requires:
  - phase: 01-api-capability-validation
    provides: Client loading patterns, query validation methods, custom label field naming
provides:
  - Complete inventory of 23 Shopping-relevant Google Ads API views/resources
  - Enumeration of 36 performance metrics with data types and live validation
  - Report type mapping with granularity levels for all Shopping views
  - Metric group validation showing which metrics return real data vs theoretical availability
affects: [03-shopping-taxonomy-discovery, 04-comprehensive-sample-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GoogleAdsFieldService for schema discovery and metadata queries"
    - "Metric categorization by use case (core, conversion, cart, impression share, etc.)"
    - "Live validation queries to distinguish available metrics from populated metrics"

key-files:
  created:
    - scripts/discover_views_and_metrics.py
    - .planning/phases/02-comprehensive-data-discovery/disc-01-02-06-results.json
  modified: []

key-decisions:
  - "Use CONTAINS ALL syntax for selectable_with queries (not = operator)"
  - "Remove conversions_value_per_cost from validation (incompatible with shopping_performance_view)"
  - "Categorize metrics into 7 groups for targeted validation and use case clarity"

patterns-established:
  - "Schema discovery pattern: Use GoogleAdsFieldService to query field metadata before building data queries"
  - "Validation pattern: Test metric groups with LAST_7_DAYS queries to confirm data availability"
  - "Resource enumeration: Query by pattern (shopping%, %_view, asset_group%) then get selectable fields"

# Metrics
duration: 9min
completed: 2026-02-12
---

# Phase 02 Plan 01: Views and Metrics Discovery Summary

**Comprehensive enumeration of 23 Shopping-relevant views with 76+ fields each, 36 performance metrics validated with live API data, and complete report type mapping establishing data source foundation for backfill planning**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-12T02:54:51Z
- **Completed:** 2026-02-12T03:03:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Discovered 23 Shopping-relevant views/resources including shopping_performance_view (76 fields), campaign (388 fields), ad_group (285 fields), and 15+ specialized views
- Enumerated 36 performance metrics available in shopping_performance_view across 7 categories (core performance, conversion, shopping cart, impression share, cross-sell/lead, attribution, asset performance)
- Validated all 5 metric groups return live data for customer 6253381786 with sample queries
- Mapped all report types with granularity levels (product+date, campaign+date, query+ad_group, etc.) and use cases
- Identified metric incompatibilities (conversions_value_per_cost not supported in shopping_performance_view)

## Task Commits

Each task was committed atomically:

1. **Task 1 & 2: Enumerate views/metrics and validate groups** - `d8e2248` (feat)
   - Created discover_views_and_metrics.py with GoogleAdsFieldService queries
   - Generated 335KB JSON results file with complete inventory
   - Validated all metric groups with live API queries

Note: Both tasks were completed in a single commit as they're tightly coupled (validation depends on enumeration results).

## Files Created/Modified

- `scripts/discover_views_and_metrics.py` - Discovery script using GoogleAdsFieldService for schema metadata and live validation
- `.planning/phases/02-comprehensive-data-discovery/disc-01-02-06-results.json` - Complete inventory (335KB, 12,283 lines) with views, metrics, report types, and validation results

## Decisions Made

**1. Query syntax for selectable_with**
- Discovered that GoogleAdsFieldService requires `CONTAINS ALL` operator for selectable_with queries, not `=` operator
- Rationale: API explicitly rejects `=` with error message listing valid operators

**2. Metric incompatibility handling**
- Removed `conversions_value_per_cost` from conversion metrics validation query
- Rationale: API returned PROHIBITED_METRIC error indicating metric is incompatible with shopping_performance_view resource
- Impact: This is valuable discovery data - not all theoretically available metrics work with all views

**3. Metric categorization strategy**
- Grouped metrics into 7 categories: core_performance (13), conversion (10), shopping_cart (13), impression_share (0), cross_sell_lead (0), attribution (0), asset_performance (0)
- Rationale: Enables targeted validation and helps Phase 3 understand which metric groups are relevant for this account
- Finding: Some categories (impression_share, cross_sell_lead, attribution) returned 0 metrics when filtered for shopping_performance_view, suggesting they're available at different granularity levels

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed GoogleAdsFieldService query syntax**
- **Found during:** Task 1 (field enumeration for each resource)
- **Issue:** Query `WHERE selectable_with = 'resource_name'` failed with OPERATOR_FIELD_MISMATCH error
- **Fix:** Changed to `WHERE selectable_with CONTAINS ALL ('resource_name')` per API error message
- **Files modified:** scripts/discover_views_and_metrics.py (lines 129-131, 163-166)
- **Verification:** All subsequent queries succeeded, 23 resources enumerated successfully
- **Committed in:** d8e2248 (Task 1 commit)

**2. [Rule 3 - Blocking] Removed incompatible metric from validation query**
- **Found during:** Task 2 (conversion metrics validation)
- **Issue:** Query failed with PROHIBITED_METRIC error for conversions_value_per_cost in shopping_performance_view
- **Fix:** Removed metric from query, adjusted sample data collection to match remaining fields
- **Files modified:** scripts/discover_views_and_metrics.py (lines 342-371)
- **Verification:** Conversion metrics validation succeeded with 5 sample rows
- **Committed in:** d8e2248 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking issues)
**Impact on plan:** Both auto-fixes were necessary to complete execution - syntax errors that prevented queries from running. The incompatible metric discovery is valuable data (not all metrics work with all views) that will inform Phase 3 sample testing.

## Issues Encountered

None - both deviations were API syntax/compatibility issues resolved via error messages.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 02 Plan 02 (Custom Labels and Performance Max):**
- Complete inventory of available views provides foundation for targeted exploration
- Metric validation establishes baseline understanding of data availability
- Report type mapping clarifies which views to use for which granularity levels

**Key insights for next plans:**
- shopping_performance_view confirmed as primary product-level resource (76 fields)
- Asset group resources available for Performance Max analysis (5 PMax-specific views)
- Impression share metrics likely require campaign-level queries (not product-level)

**Blockers:** None

**Discoveries for Phase 3:**
- conversions_value_per_cost incompatibility suggests need to test metric compatibility across all views
- 0 metrics returned for some categories when filtered by shopping_performance_view suggests multi-view strategy needed for complete metric coverage

---
*Phase: 02-comprehensive-data-discovery*
*Completed: 2026-02-12*
