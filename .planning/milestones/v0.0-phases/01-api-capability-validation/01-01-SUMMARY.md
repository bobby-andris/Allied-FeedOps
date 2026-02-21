---
phase: 01-api-capability-validation
plan: 01
subsystem: google-ads-api
tags: [validation, api-testing, gaql, search-terms, performance-data]
dependency_graph:
  requires: []
  provides:
    - api-01-confirmed
    - api-02-confirmed
    - working-gaql-patterns
  affects:
    - phase-02-data-discovery
    - backfill-strategy
tech_stack:
  added:
    - google-ads-python-client==24.1.0
  patterns:
    - gaql-query-validation
    - api-error-analysis
    - case-sensitivity-testing
key_files:
  created:
    - .planning/phases/01-api-capability-validation/test_api_01.py
    - .planning/phases/01-api-capability-validation/test_api_02.py
    - .planning/phases/01-api-capability-validation/find_active_products.py
    - .planning/phases/01-api-capability-validation/test_case_sensitivity.py
    - .planning/phases/01-api-capability-validation/api-01-test-results.json
    - .planning/phases/01-api-capability-validation/api-02-test-results.json
  modified: []
decisions:
  - title: search_term_view Cannot Filter by Product
    rationale: API explicitly rejects segments.product_item_id in search_term_view queries
    alternatives_considered:
      - Direct product filtering (rejected - API limitation)
      - Campaign-join pattern (selected - already implemented in codebase)
    impact: Must use two-step query pattern for product→search term association
  - title: Google Ads API Uses Lowercase Offer IDs
    rationale: Testing revealed API returns and expects shopify_us_ format, not shopify_US_
    alternatives_considered: []
    impact: Database format matches API format (no transformation needed for queries)
metrics:
  duration_minutes: 4
  completed_date: "2026-02-11"
  tasks_completed: 2
  test_queries_executed: 5
  api_validations: 2
---

# Phase 01 Plan 01: Core API View Validation Summary

**One-liner:** Validated Google Ads API query patterns - search_term_view cannot filter by product (API-01), shopping_performance_view fully supports product-level queries (API-02).

## What Was Built

### API-01: search_term_view Product Filtering Test

**Test objective:** Confirm that search_term_view does NOT support filtering by `segments.product_item_id`.

**Test queries:**
1. **Product filter attempt** (expected to fail):
```sql
SELECT
  search_term_view.search_term,
  campaign.id,
  metrics.impressions,
  metrics.clicks
FROM search_term_view
WHERE segments.product_item_id = 'shopify_us_7721863643362_42804912849122'
  AND segments.date DURING LAST_30_DAYS
```

**Result:** ❌ Query failed with `INVALID_ARGUMENT` error
- Error message: "Cannot select or filter on the following segments: 'segments.product_item_id'(could not support requested resources: 'SEARCH_TERM_VIEW'), since segment is incompatible with the resource in the FROM clause or other selected segmenting resources."
- **Conclusion:** API explicitly rejects product_item_id in search_term_view

2. **Basic query** (expected to succeed):
```sql
SELECT
  search_term_view.search_term,
  campaign.id,
  metrics.impressions,
  metrics.clicks
FROM search_term_view
WHERE segments.date DURING LAST_7_DAYS
  AND metrics.impressions > 10
ORDER BY metrics.impressions DESC
LIMIT 10
```

**Result:** ✅ Query returned 10 results
- Sample terms: "recessed toilet paper holder" (1,775 impressions), "shower squeegee" (839 impressions), "valet rod" (766 impressions)
- **Conclusion:** search_term_view is functional, just cannot filter by product

**API-01 Confirmed:** search_term_view does NOT support product-level filtering. Campaign-join pattern is required.

---

### API-02: shopping_performance_view Product Query Test

**Test objective:** Confirm that shopping_performance_view DOES support filtering by `segments.product_item_id` (single product and batch).

**Test 1: Single product query**
```sql
SELECT
  segments.product_item_id,
  segments.date,
  campaign.advertising_channel_type,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_micros
FROM shopping_performance_view
WHERE segments.product_item_id = 'shopify_us_4538703609988_32096241320068'
  AND segments.date DURING LAST_30_DAYS
ORDER BY segments.date DESC
LIMIT 30
```

**Result:** ✅ Query returned 30 results
- Date range: 2026-02-10 to 2026-01-12 (30 days of daily data)
- Metrics captured: impressions, clicks, CTR, conversions, conversion value, cost
- Channel types: SHOPPING and PERFORMANCE_MAX campaigns both included
- Sample data point: 2026-02-10 SHOPPING campaign - 245 impressions, 2 clicks, 0.82% CTR, $7.09 cost

**Test 2: Batch query (IN clause)**
```sql
SELECT
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr
FROM shopping_performance_view
WHERE segments.product_item_id IN (
  'shopify_us_4538703609988_32096241320068',
  'shopify_us_8751009038562_46118169444578',
  'shopify_us_4543465947268_32123035451524',
  'shopify_us_4538765508740_32096780222596',
  'shopify_us_4542830280836_32117943369860'
)
  AND segments.date DURING LAST_30_DAYS
ORDER BY segments.product_item_id, segments.date DESC
```

**Result:** ✅ Query returned 133 results across 5 products
- Product 1: 30 rows (complete 30-day history)
- Product 2: 13 rows (partial data - some days had no impressions)
- Product 3: 30 rows
- Product 4: 30 rows
- Product 5: 30 rows
- **Conclusion:** Batch queries with IN clause work successfully for multiple products

**API-02 Confirmed:** shopping_performance_view fully supports product-level filtering (single and batch).

---

### Case Sensitivity Discovery

**Finding:** Google Ads API uses **lowercase** `shopify_us_` format for product_item_id.

**Evidence:**
- Query with `shopify_US_` (uppercase): ❌ 0 results
- Query with `shopify_us_` (lowercase): ✅ 7 results

**Impact:**
- Database already stores lowercase format (`variant_index.gmc_offer_id`)
- No transformation needed when querying Google Ads API
- **Important:** Google Sheets publishing must still transform to uppercase `shopify_US_` for GMC sync (as documented in CLAUDE.md)

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Missing use_proto_plus configuration**
- **Found during:** Task 1, initial test execution
- **Issue:** GoogleAdsClient.load_from_env() failed with "missing required 'use_proto_plus' key" error
- **Fix:** Implemented custom `_load_client()` function following pattern from existing `google_ads_performance.py` integration
- **Files modified:** test_api_01.py, test_api_02.py
- **Commit:** Included in task commits

**2. [Rule 3 - Blocking Issue] Test product had no recent data**
- **Found during:** Task 2, initial query returned 0 results
- **Issue:** Hardcoded test product ID had no recent activity in Google Ads
- **Fix:** Created `find_active_products.py` helper script to identify products with recent impressions (>10 in last 7 days), selected top 5 active products
- **Files created:** find_active_products.py
- **Commit:** feat(01-01): validate shopping_performance_view product queries (API-02)

**3. [Rule 3 - Blocking Issue] Case sensitivity mismatch**
- **Found during:** Task 2, queries with uppercase IDs returned 0 results despite products having data
- **Issue:** API expects lowercase `shopify_us_` but plan examples used uppercase `shopify_US_`
- **Fix:** Created `test_case_sensitivity.py` to validate both formats, updated all test scripts to use lowercase format
- **Files created:** test_case_sensitivity.py
- **Commit:** feat(01-01): validate shopping_performance_view product queries (API-02)

---

## Verification Results

All verification criteria met:

**Task 1 Verification:**
- ✅ Product-filtered query returned error (documented exact error message)
- ✅ Basic query returned actual search term data (documented 10 sample rows)
- ✅ Both results captured in api-01-test-results.json

**Task 2 Verification:**
- ✅ Single product query returned rows with impressions/clicks/etc for specific product
- ✅ Batch query returned rows for multiple products grouped by product_item_id
- ✅ Queries returned non-zero metrics data (30 rows for single product, 133 rows for 5 products)
- ✅ Sample response data documented in api-02-test-results.json

**Overall Verification:**
- ✅ API-01 test query failed with documented error (confirms search_term_view limitation)
- ✅ API-01 basic query succeeded (confirms search_term_view works for non-product queries)
- ✅ API-02 single product query returned product-level performance data
- ✅ API-02 batch query returned data for multiple products
- ✅ All results documented with actual API responses

---

## Success Criteria

**From plan:** Both API-01 and API-02 requirements have definitive answers backed by actual API test results, not just documentation research. The answers match research predictions (API-01: no, API-02: yes) and are documented with evidence.

**Status:** ✅ **FULLY MET**

1. ✅ API-01 confirmed: search_term_view does NOT support product_item_id filtering
   - Actual API error message documented
   - Basic query confirms view is functional
   - Campaign-join pattern required (already implemented in codebase)

2. ✅ API-02 confirmed: shopping_performance_view fully supports product-level queries
   - Single product query: 30 rows with all key metrics
   - Batch query: 133 rows across 5 products
   - Working GAQL examples with actual response data

3. ✅ Bonus discovery: Case sensitivity clarified
   - API uses lowercase `shopify_us_` format
   - Database format matches API (no transformation needed)

---

## Key Insights

1. **Campaign-join pattern is mandatory:** search_term_view cannot be filtered by product - must map campaigns to products via shopping_performance_view, then fetch search terms by campaign.id.

2. **shopping_performance_view is fully capable:** Supports all key metrics (impressions, clicks, CTR, conversions, cost) with product-level filtering (single and batch).

3. **Case sensitivity matters:** Google Ads API uses lowercase `shopify_us_` format internally, but GMC feed requires uppercase `shopify_US_` transformation during publishing.

4. **Performance Max campaigns included:** shopping_performance_view returns data for both SHOPPING and PERFORMANCE_MAX campaign types, confirming comprehensive coverage.

---

## Impact on Roadmap

**Phase 2 (Comprehensive Data Discovery):**
- Can proceed with confidence that shopping_performance_view will support product-level queries
- Must design campaign-join pattern for search term association
- Should test query performance (LIMIT values, IN clause sizes) in sample testing phase

**Phase 3 (Sample Testing & Analysis):**
- Use confirmed query patterns from this phase
- Test with larger product batches to validate IN clause limits (documented max: 20,000)
- Measure query latency for batch sizing decisions

**Phase 4 (Documentation & Decision):**
- Document working GAQL patterns from this phase
- Include case sensitivity guidance (lowercase for queries, uppercase for GMC publishing)
- Provide Go/No-Go recommendation based on these positive validation results

---

## Next Steps

1. Execute plan 01-02 (API-03, API-04, API-05 validation)
2. Document LIMIT performance testing approach for Phase 3
3. Confirm data retention windows with historical queries

---

## Self-Check

Verifying all claims and artifacts:

**Created files:**
```bash
# Test scripts
[✓] .planning/phases/01-api-capability-validation/test_api_01.py
[✓] .planning/phases/01-api-capability-validation/test_api_02.py
[✓] .planning/phases/01-api-capability-validation/find_active_products.py
[✓] .planning/phases/01-api-capability-validation/test_case_sensitivity.py

# Test results
[✓] .planning/phases/01-api-capability-validation/api-01-test-results.json
[✓] .planning/phases/01-api-capability-validation/api-02-test-results.json
```

**Commits:**
```bash
[✓] 23db91a0 - test(01-01): validate search_term_view limitations (API-01)
[✓] cec214ab - feat(01-01): validate shopping_performance_view product queries (API-02)
```

**Test results verified:**
- API-01: search_term_view product filter returned INVALID_ARGUMENT error ✓
- API-01: search_term_view basic query returned 10 results ✓
- API-02: Single product query returned 30 results ✓
- API-02: Batch query returned 133 results across 5 products ✓

## Self-Check: PASSED

All files exist, all commits present, all test results verified.
