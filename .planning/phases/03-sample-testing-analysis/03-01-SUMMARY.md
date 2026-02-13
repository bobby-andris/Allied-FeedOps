---
phase: 03-sample-testing-analysis
plan: 01
subsystem: testing
tags: [google-ads-api, python, supabase, data-collection, search-terms]

# Dependency graph
requires:
  - phase: 01-api-capability-validation
    provides: Google Ads API client setup and known-active offer IDs for fallback
  - phase: 02-comprehensive-data-discovery
    provides: Comprehensive understanding of available metrics and query patterns
provides:
  - 6 representative test SKUs across 5 product categories with confirmed activity
  - 60K+ unique search terms with impression/click data (90-day window)
  - Validated campaign-join pattern for search term fetching at scale
  - Python script for category-based SKU selection with activity validation
affects: [03-sample-testing-analysis, backfill-planning, production-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Category-based SKU selection from product_catalog with activity validation
    - Campaign-join pattern for search term fetching (two-step query)
    - Fallback to known-active SKUs when category selection yields insufficient results
    - Explicit date ranges instead of LAST_N_DAYS syntax (API requirement)

key-files:
  created:
    - scripts/phase3_select_skus.py
    - .planning/phases/03-sample-testing-analysis/sample-skus.json
    - .planning/phases/03-sample-testing-analysis/search-terms-by-sku.json
  modified: []

key-decisions:
  - "Use campaign-join pattern (shopping_performance_view → search_term_view) instead of direct product filtering"
  - "Explicit date ranges (BETWEEN start AND end) required - LAST_N_DAYS syntax rejected by API"
  - "Must include filtered fields in SELECT clause when using WHERE (e.g., campaign.advertising_channel_type)"
  - "Supplement with fallback known-active SKUs when category-based selection yields <5 SKUs"

patterns-established:
  - "Pattern 1: SKU selection - query product_catalog by category, map to variant_index for gmc_offer_id, validate activity via shopping_performance_view"
  - "Pattern 2: Search term fetching - get campaigns from shopping_performance_view by product IN clause, then fetch search terms for those campaigns"
  - "Pattern 3: Fallback supplementation - use Phase 1 known-active offer IDs to ensure adequate sample size"

# Metrics
duration: 6min
completed: 2026-02-13
---

# Phase 3 Plan 1: Sample SKU Selection and Search Term Fetching Summary

**Selected 6 SKUs across 5 categories with 60K+ search terms (560K impressions) using campaign-join pattern and category-based selection with fallback**

## Performance

- **Duration:** 6 min (378 seconds)
- **Started:** 2026-02-12T23:57:41Z
- **Completed:** 2026-02-13T00:03:59Z
- **Tasks:** 1 (combined SAMP-01 and SAMP-02)
- **Files modified:** 3 (1 script + 2 JSON outputs)

## Accomplishments

- Selected 6 representative test SKUs across 5 distinct product categories (grab bars, retractable hooks, glass shelves, multi hooks, wall accessories)
- Fetched 60,392 unique search terms with impression/click data from last 90 days
- Validated campaign-join pattern works at scale (560K total impressions across sample)
- Created reusable Python script for future SKU selection and search term collection

## Task Commits

Each task was committed atomically:

1. **Task 1: Select Test SKUs and Fetch Search Terms** - `61be33cc` (feat)

**Plan metadata:** (included in same commit)

## Files Created/Modified

- `scripts/phase3_select_skus.py` - Python script performing SAMP-01 (SKU selection) and SAMP-02 (search term fetching)
- `.planning/phases/03-sample-testing-analysis/sample-skus.json` - 6 selected SKUs with category, gmc_offer_id, title, impressions_30d
- `.planning/phases/03-sample-testing-analysis/search-terms-by-sku.json` - 60K+ search terms organized by master_sku with impression/click/conversion data (8.9MB)

## Decisions Made

1. **Combined SAMP-01 and SAMP-02 into single script**
   - Rationale: Both tasks share same data sources and execution flow
   - Benefit: Simpler execution, consistent data collection

2. **Use feedops.db.supabase_client.get_client() instead of direct environment loading**
   - Rationale: Existing codebase pattern handles environment variables properly
   - Benefit: Consistency with other scripts, no need to reinvent environment loading

3. **Explicit date ranges instead of LAST_N_DAYS syntax**
   - Rationale: Google Ads API rejects `LAST_90_DAYS` literal (invalid value error)
   - Solution: Calculate start/end dates in Python, use `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`
   - Impact: All future date range queries must use explicit dates

4. **Include filtered fields in SELECT clause**
   - Rationale: API requires fields used in WHERE filters to be in SELECT
   - Example: `WHERE campaign.advertising_channel_type = 'SHOPPING'` requires `SELECT campaign.advertising_channel_type`
   - Impact: All filtered queries need complete SELECT clauses

5. **Supplement with fallback SKUs when <5 selected**
   - Rationale: Category-based selection only yielded 2 SKUs with confirmed activity
   - Solution: Use Phase 1 known-active offer IDs to reach target of 5-10 SKUs
   - Result: Final selection of 6 SKUs across 5 categories

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Google Ads API query syntax errors**
- **Found during:** Task 1 (search term fetching)
- **Issue 1:** `LAST_90_DAYS` syntax rejected - "Invalid date literal supplied for DURING operator"
- **Issue 2:** Missing `campaign.advertising_channel_type` in SELECT when filtering by it
- **Issue 3:** Missing `segments.product_item_id` in SELECT when filtering by it
- **Fix:** Calculate explicit date ranges in Python, add all filtered fields to SELECT clauses
- **Files modified:** scripts/phase3_select_skus.py
- **Verification:** Queries succeeded, returned 60K+ search terms
- **Committed in:** 61be33cc (Task 1 commit)

**2. [Rule 1 - Bug] Fixed set.count() AttributeError**
- **Found during:** Task 1 (SKU selection logic)
- **Issue:** Used `categories_seen.count(category)` on a set object (sets don't have .count() method)
- **Fix:** Changed to dict-based counting: `category_counts.get(category, 0)`
- **Files modified:** scripts/phase3_select_skus.py
- **Verification:** SKU selection logic completed successfully
- **Committed in:** 61be33cc (Task 1 commit)

**3. [Rule 2 - Missing Critical] Added fallback SKU supplementation logic**
- **Found during:** Task 1 (SKU selection)
- **Issue:** Category-based selection only found 2 SKUs with activity (below target of 5-10)
- **Fix:** Added logic to supplement with known-active offer IDs from Phase 1 when count < 5
- **Files modified:** scripts/phase3_select_skus.py
- **Verification:** Final selection reached 6 SKUs across 5 categories
- **Committed in:** 61be33cc (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking query errors, 1 bug, 1 missing critical fallback logic)
**Impact on plan:** All auto-fixes necessary for functionality. No scope creep - stayed within SAMP-01/SAMP-02 requirements.

## Issues Encountered

1. **Google Ads API date syntax requirements**
   - Problem: Documentation examples use `LAST_N_DAYS` but actual API rejects it
   - Solution: Use explicit date ranges calculated in code
   - Learning: Always test date syntax variations during API capability validation

2. **Category-based selection yielded low coverage**
   - Problem: Only 1 product had confirmed activity in last 30 days (out of 20 candidates)
   - Root cause: Many products in catalog don't have recent Google Ads impressions
   - Solution: Fallback to known-active SKUs from Phase 1 testing
   - Future: May need longer lookback window (90 days) for activity validation

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for SAMP-03 (Keyword Planner idea generation):**
- 6 test SKUs selected with diverse categories
- Product titles available for seed keywords
- Sample size adequate for opportunity gap analysis

**Ready for SAMP-04 (Opportunity gap calculation):**
- Search terms collected (60K+) providing current coverage baseline
- Awaiting Keyword Planner ideas to calculate gap

**Ready for SAMP-05 (Performance measurement):**
- Campaign-join pattern validated and working
- Can measure query response times across batch sizes

**Sample quality:**
- 5 distinct categories represented
- 560K total impressions indicating active products
- Mix of product types (grab bars, hooks, shelves, accessories)
- No blockers for subsequent testing

---
*Phase: 03-sample-testing-analysis*
*Completed: 2026-02-13*
