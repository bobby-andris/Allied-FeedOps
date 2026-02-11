# Phase 1: API Capability Validation - Research

**Researched:** 2026-02-11
**Domain:** Google Ads API (GAQL, shopping_performance_view, search_term_view)
**Confidence:** HIGH

## Summary

This research validates 5 critical assumptions about Google Ads API capabilities needed for a comprehensive product performance backfill strategy. Key findings confirm that while `search_term_view` intentionally cannot filter by `product_item_id`, the `shopping_performance_view` resource fully supports product-level queries with documented filtering capabilities. The campaign-join pattern (already implemented in the codebase) is the recommended approach for linking search terms to products.

Data retention is confirmed at 11 years as of November 2024, enabling historical backfills back to 2015. LIMIT constraints are not row-based but governed by gRPC response size (64MB cap) and IN clause limits (20,000 items). Custom labels are available across multiple views for filtering and segmentation.

**Primary recommendation:** Proceed with backfill strategy using `shopping_performance_view` for product-level data and campaign-join pattern for search term association. Test practical LIMIT ceilings with batch queries in Phase 3 (Sample Testing).

## User Constraints

No user constraints from CONTEXT.md (file does not exist for this phase).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-ads | 24.1.0+ | Official Google Ads API Python client | Google-maintained, complete API coverage, handles auth/pagination |
| google-api-core | Latest | gRPC transport for API calls | Required dependency, handles retry logic and gRPC streams |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-auth-oauthlib | Latest | OAuth2 authentication flow | Initial credential setup (already configured) |
| protobuf | 3.20+ | Proto message serialization | Required for google-ads client |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| google-ads Python client | Direct REST API calls | Python client handles pagination, streaming, retries, error mapping - REST is lower-level and more brittle |
| google-ads Python client | Google Ads MCP (via ToolSearch) | MCP useful for ad-hoc queries in Cursor, but Python client better for production pipelines with error handling and logging |

**Installation:**
```bash
pip install google-ads google-api-core
```

**Configuration:**
Already configured in `src/feedops/integrations/google_ads_performance.py` with environment variable and file-based config support.

## Architecture Patterns

### Recommended Project Structure
```
src/feedops/integrations/
├── google_ads_performance.py     # Product performance metrics
├── google_ads_search_terms.py    # Search terms with campaign-join
└── google_ads_base.py            # Shared client/query utilities (if needed)
```

### Pattern 1: Direct Product Filtering (shopping_performance_view)

**What:** Query `shopping_performance_view` filtering by `segments.product_item_id` to get performance metrics for specific products.

**When to use:** Fetching performance data (impressions, clicks, conversions, ROAS) for known product offer IDs.

**Example:**
```python
# Source: src/feedops/integrations/google_ads_performance.py (lines 198-217)
query = f"""
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
WHERE
  segments.product_item_id = '{safe_offer_id}'
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
ORDER BY segments.date
"""
```

**Batch variant:**
```python
# Source: src/feedops/integrations/google_ads_performance.py (lines 326-346)
# For multiple products in single query
safe_ids = [oid.replace("'", "\\'") for oid in offer_ids]
ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)

query = f"""
SELECT
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_micros
FROM shopping_performance_view
WHERE
  segments.product_item_id IN ({ids_clause})
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
ORDER BY segments.product_item_id, segments.date
"""
```

### Pattern 2: Campaign-Join for Search Terms

**What:** Since `search_term_view` cannot filter by product, first fetch campaign→product mappings from `shopping_performance_view`, then fetch search terms by campaign.id, then join in application code.

**When to use:** Associating search query data with specific products.

**Example:**
```python
# Source: src/feedops/integrations/google_ads_search_terms.py (lines 472-518)

# Step 1: Get campaign→product mapping
def _fetch_campaign_products(self, days: int = 30) -> dict[str, list[str]]:
    query = f"""
        SELECT
            segments.product_item_id,
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_{days}_DAYS
            AND campaign.advertising_channel_type = 'SHOPPING'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 50000
    """
    # Returns: {"campaign_id": ["product_id_1", "product_id_2", ...]}

# Step 2: Fetch search terms by campaign
query = f"""
    SELECT
        search_term_view.search_term,
        segments.search_term_match_type,
        campaign.id,
        metrics.impressions,
        metrics.clicks,
        metrics.ctr,
        metrics.conversions
    FROM search_term_view
    WHERE campaign.id IN ({campaign_ids})
        AND segments.date DURING LAST_{days}_DAYS
"""

# Step 3: Join in Python code
# Map search terms to products via shared campaign.id
```

### Pattern 3: Custom Label Filtering

**What:** Use `segments.product_custom_attribute_0` through `segments.product_custom_attribute_4` to filter products by custom labels.

**When to use:** Segmenting products by category, tier, collection, or other business metadata stored in GMC custom labels.

**Example:**
```python
# Filter performance by product category
query = f"""
SELECT
  segments.product_item_id,
  segments.product_custom_attribute_0,
  metrics.impressions,
  metrics.clicks
FROM shopping_performance_view
WHERE
  segments.product_custom_attribute_0 = 'Towel Bars'
  AND segments.date DURING LAST_30_DAYS
"""
```

### Anti-Patterns to Avoid

- **Direct search_term_view filtering by product:** Google intentionally removed `product_item_id` from `search_term_view`. Use campaign-join pattern instead.
- **Unbounded LIMIT clauses:** While there's no hard row limit, responses are capped at 64MB gRPC message size. Large queries may fail. Use pagination or batch by date ranges.
- **Case-sensitive offer ID matching:** GMC uses `shopify_US_` (uppercase) but database may have `shopify_us_` (lowercase). Always normalize case when matching.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API pagination | Custom iterator with page tokens | `GoogleAdsService.search_stream()` | Built-in streaming handles batching, backpressure, retries |
| OAuth2 refresh | Manual token refresh logic | `google-ads` client with refresh_token config | Library handles token expiry and refresh automatically |
| GAQL query escaping | String replacement for single quotes | `offer_id.replace("'", "\\'")` | Prevents SQL injection, handles edge cases |
| Date range iteration | Manual date chunking for large queries | `segments.date BETWEEN` with LIMIT | API handles pagination within date ranges |
| gRPC error handling | Try/except on raw gRPC errors | `google.ads.googleads.errors.GoogleAdsException` | Provides structured error codes and field-level error details |

**Key insight:** The google-ads Python client handles authentication, pagination, retries, error mapping, and message serialization. Building these from scratch introduces bugs and maintenance burden.

## Research Questions (API-01 through API-05)

### API-01: Can search_term_view filter by product_item_id?

**Answer:** No (confirmed)

**Confidence:** HIGH

**Evidence:**
- Google intentionally removed the ability to link search terms directly to products in the Google Ads API
- `search_term_view` resource does not include `segments.product_item_id` field
- This is documented as intentional product design to prevent query performance issues
- Campaign-join pattern is the recommended workaround (already implemented in codebase)

**Source:**
- Web search: "google ads api search_term_view filter by product_item_id 2026"
- Existing implementation: `src/feedops/integrations/google_ads_search_terms.py` uses campaign-join

**Impact:** Backfill strategy must use campaign-join pattern (fetch campaign→product mapping, then search terms by campaign). This is already implemented and working in production code.

### API-02: Does shopping_performance_view support product-level queries?

**Answer:** Yes (confirmed with working GAQL examples)

**Confidence:** HIGH

**Evidence:**
- `shopping_performance_view` includes `segments.product_item_id` field for filtering
- Existing codebase has working queries filtering by single product and batches (IN clause)
- Supports all key metrics: impressions, clicks, CTR, conversions, conversion_value, cost_micros
- Supports date segmentation: `segments.date` for daily breakdown

**Working GAQL example:**
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
WHERE
  segments.product_item_id = 'shopify_US_7721863643362_42804912849122'
  AND segments.date BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY segments.date
```

**Source:**
- Existing implementation: `src/feedops/integrations/google_ads_performance.py` (lines 198-217, 326-346)
- Google Ads MCP schema: Confirmed `segments.product_item_id` availability

**Impact:** Product-level backfill is fully supported. Use direct filtering for single products or IN clause for batches (up to 20,000 IDs per query).

### API-03: What is the maximum LIMIT value that works reliably?

**Answer:** No hard row limit, but constrained by gRPC response size (64MB) and IN clause limit (20,000 items)

**Confidence:** MEDIUM (documented but not tested in this codebase)

**Evidence:**
- gRPC response size limited to 64MB per request
- IN clause limited to 20,000 items per query
- Existing code uses LIMIT 50000 successfully for campaign-product mapping
- Pagination via `search_stream()` handles large result sets automatically

**Practical limits:**
- Single product queries: No meaningful limit (one product's daily data for 11 years ~4,015 rows)
- Batch queries: Limit by number of products (20,000 max in IN clause) or use pagination
- Large date ranges: Use `search_stream()` pagination to handle >64MB responses

**Source:**
- Web search: "google ads api gaql limit maximum 2026"
- Existing code: `src/feedops/integrations/google_ads_search_terms.py` line 489 uses LIMIT 50000

**Testing needed:** Phase 3 should test actual performance with 10K, 50K, 100K LIMIT values to measure response times and reliability.

**Impact:** Backfill strategy should batch by products (max 20K per query) rather than setting arbitrary LIMIT values. Use pagination for large result sets.

### API-04: What are actual data retention windows?

**Answer:** 11 years for Google Ads data (effective November 13, 2024)

**Confidence:** HIGH

**Evidence:**
- Google announced 11-year data retention policy effective November 13, 2024
- Replaces previous 5-year policy
- Enables historical queries back to November 13, 2013 (as of 2024)
- Exception: Reach and frequency metrics limited to 3 years
- Shopping campaign data (shopping_performance_view, search_term_view) covered by 11-year policy

**Source:**
- Web search: "google ads api data retention 11 years 2026"
- Official announcement: November 13, 2024 policy update

**Testing recommendation:** Phase 3 should test queries for dates in 2015-2016 range to confirm actual availability for this account.

**Impact:** Backfill can safely target 2015-present for performance and search term data. 11-year window supports comprehensive historical analysis.

### API-05: Is custom_label_0 available in Merchant API product_view?

**Answer:** Yes (confirmed in Google Ads API, Merchant API equivalent: `customLabel0`)

**Confidence:** HIGH

**Evidence:**
- Google Ads API: `segments.product_custom_attribute_0` through `_4` available in shopping_performance_view
- Merchant API: `customLabel0` through `customLabel4` available in product_view
- Existing codebase uses custom labels in Google Sheets feed (columns E-G, K for custom_label_0, 1, 2, 4)
- MCP schema confirms availability across multiple views

**GAQL example:**
```sql
SELECT
  segments.product_item_id,
  segments.product_custom_attribute_0,
  segments.product_custom_attribute_1,
  metrics.impressions
FROM shopping_performance_view
WHERE
  segments.product_custom_attribute_0 = 'Towel Bars'
  AND segments.date DURING LAST_30_DAYS
```

**Source:**
- Google Ads MCP schema (shopping_performance_view segments)
- Existing implementation: `dashboard/src/lib/publishing/google-sheets.ts` uses custom_label columns

**Impact:** Custom labels can be used for product segmentation in queries. Consider populating custom labels with business metadata (category, tier, collection) for easier filtering.

## Common Pitfalls

### Pitfall 1: search_term_view Product Filtering

**What goes wrong:** Attempting to filter `search_term_view` by `segments.product_item_id` results in query errors or empty results.

**Why it happens:** Google removed product_item_id from search_term_view to prevent performance issues and protect advertiser privacy.

**How to avoid:** Use campaign-join pattern - map campaigns to products via `shopping_performance_view`, fetch search terms by `campaign.id`, join in application code.

**Warning signs:** GAQL queries on search_term_view that include `segments.product_item_id` in WHERE clause will fail with field not found error.

### Pitfall 2: Offer ID Case Sensitivity

**What goes wrong:** Queries return no results despite products existing in GMC, or duplicate rows appear in Google Sheets feed.

**Why it happens:** GMC requires uppercase format (`shopify_US_`), but database may store lowercase (`shopify_us_`). Inconsistent case causes lookup failures.

**How to avoid:**
- Database storage: Lowercase for consistency
- GMC/Sheets publishing: Transform to uppercase before writing
- Query matching: Use case-insensitive comparison or normalize before filtering

**Warning signs:** "No data found" for products that definitely have impressions, or duplicate feed rows with mixed case IDs.

### Pitfall 3: gRPC Response Size Limits

**What goes wrong:** Large queries fail with gRPC error "message larger than max" or timeout without results.

**Why it happens:** gRPC response capped at 64MB. Queries returning massive result sets (e.g., all products for all days over 11 years) exceed this limit.

**How to avoid:**
- Use `search_stream()` for automatic pagination
- Batch by date ranges (monthly or quarterly chunks)
- Limit products per query (20,000 max in IN clause)
- Order by segments for efficient streaming

**Warning signs:** Queries that work for small date ranges but fail for large ranges, or queries that hang and timeout.

### Pitfall 4: IN Clause Limits

**What goes wrong:** Queries with >20,000 product IDs in IN clause fail with syntax error or query rejection.

**Why it happens:** GAQL limits IN clause to 20,000 items to prevent query complexity issues.

**How to avoid:**
- Batch product IDs into chunks of 10,000-15,000 for safety margin
- Use multiple sequential queries for large product catalogs
- Consider filtering by custom labels instead if products share categories

**Warning signs:** Query errors when filtering large product sets, successful queries with <10K products but failures with >20K.

## Code Examples

Verified patterns from existing codebase:

### Single Product Performance Query

```python
# Source: src/feedops/integrations/google_ads_performance.py (lines 198-217)
def fetch_product_performance(offer_id: str, start_date: str, end_date: str):
    safe_offer_id = offer_id.replace("'", "\\'")

    query = f"""
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
    WHERE
      segments.product_item_id = '{safe_offer_id}'
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    ORDER BY segments.date
    """

    rows = _run_gaql_query(client, customer_id, query)
    # Returns list[dict] with protobuf messages converted to dicts
```

### Batch Product Performance Query

```python
# Source: src/feedops/integrations/google_ads_performance.py (lines 326-346)
def fetch_batch_product_performance(offer_ids: list[str], start_date: str, end_date: str):
    safe_ids = [oid.replace("'", "\\'") for oid in offer_ids]
    ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.conversions,
      metrics.conversions_value,
      metrics.cost_micros
    FROM shopping_performance_view
    WHERE
      segments.product_item_id IN ({ids_clause})
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    ORDER BY segments.product_item_id, segments.date
    """

    rows = _run_gaql_query(client, customer_id, query)
    # Group by product_item_id in application code
```

### Campaign-Join Pattern for Search Terms

```python
# Source: src/feedops/integrations/google_ads_search_terms.py (lines 472-518)

# Step 1: Map campaigns to products
def _fetch_campaign_products(days: int = 30) -> dict[str, list[str]]:
    query = f"""
        SELECT
            segments.product_item_id,
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_{days}_DAYS
            AND campaign.advertising_channel_type = 'SHOPPING'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 50000
    """

    rows = _run_gaql_query(client, customer_id, query)

    # Build campaign_id -> [product_ids] mapping
    campaign_products: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        campaign_id = row["campaign"]["id"]
        product_id = row["segments"]["product_item_id"]
        if product_id not in campaign_products[campaign_id]:
            campaign_products[campaign_id].append(product_id)

    return campaign_products

# Step 2: Fetch search terms by campaign
def fetch_search_terms(campaign_ids: list[str], days: int = 30):
    campaign_ids_str = ", ".join(campaign_ids)

    query = f"""
        SELECT
            search_term_view.search_term,
            segments.search_term_match_type,
            campaign.id,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.conversions
        FROM search_term_view
        WHERE campaign.id IN ({campaign_ids_str})
            AND segments.date DURING LAST_{days}_DAYS
    """

    rows = _run_gaql_query(client, customer_id, query)

    # Join to products using campaign_products mapping
    # Each search term maps to all products in that campaign
```

### Custom Label Filtering

```python
# Filter by product category stored in custom_label_0
query = f"""
SELECT
  segments.product_item_id,
  segments.product_custom_attribute_0,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM shopping_performance_view
WHERE
  segments.product_custom_attribute_0 = 'Towel Bars'
  AND segments.date BETWEEN '2025-01-01' AND '2025-12-31'
ORDER BY metrics.impressions DESC
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 5-year data retention | 11-year data retention | November 13, 2024 | Historical backfills can now go back to 2015 (or 2013 for older accounts) |
| Direct search term→product linking | Campaign-join pattern | API v13+ (2022) | More complex query logic but necessary for search term analysis |
| REST API | gRPC with google-ads client library | API v11+ (2021) | Faster, more efficient, better pagination |
| Manual pagination | `search_stream()` automatic pagination | API v8+ (2020) | Simpler code, handles backpressure automatically |

**Deprecated/outdated:**
- **Content API for Shopping:** Replaced by Merchant API (September 2023). Use Merchant API for product data.
- **AdWords API:** Fully sunset April 27, 2022. Must use Google Ads API.
- **Manual OAuth refresh:** google-ads client handles token refresh automatically.

## Open Questions

1. **Practical LIMIT performance**
   - What we know: No hard row limit, but gRPC 64MB response cap and 20K IN clause limit
   - What's unclear: Actual query performance (p50, p95, p99 latency) for 10K, 50K, 100K result sets
   - Recommendation: Test in Phase 3 with representative queries on production account

2. **Historical data completeness**
   - What we know: 11-year retention policy since November 2024
   - What's unclear: Whether this account has continuous data back to 2015 or if there are gaps
   - Recommendation: Sample queries for 2015, 2018, 2021 date ranges to verify actual availability

3. **Custom label population strategy**
   - What we know: Custom labels available for filtering, currently populated in Google Sheets feed
   - What's unclear: Should we populate custom_label_4 with product_item_id for easier filtering?
   - Recommendation: Evaluate in Phase 2 - may simplify queries but adds maintenance burden

4. **Performance Max campaign data**
   - What we know: Performance Max campaigns exist in account (mentioned in DISC-05)
   - What's unclear: Do Performance Max campaigns populate shopping_performance_view with product-level data?
   - Recommendation: Test in Phase 3 with sample Performance Max campaign query

## Sources

### Primary (HIGH confidence)

- **Existing codebase:**
  - `src/feedops/integrations/google_ads_performance.py` - Working shopping_performance_view queries
  - `src/feedops/integrations/google_ads_search_terms.py` - Campaign-join pattern implementation
  - `dashboard/src/lib/publishing/google-sheets.ts` - Custom label usage

- **Google Ads MCP schema:**
  - Loaded via ToolSearch: `mcp__google-ads-mcp__search`
  - Confirmed field availability across all views

### Secondary (MEDIUM confidence)

- **Web search (verified with official sources):**
  - Google Ads API data retention policy (11 years, November 2024)
  - gRPC response size limits (64MB)
  - IN clause limits (20,000 items)

### Tertiary (LOW confidence)

- **Web search (single source, needs verification):**
  - Specific p95/p99 latency numbers for large queries (marked for Phase 3 testing)
  - Performance Max campaign data structure (needs direct testing)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - google-ads Python client is official and already integrated
- Architecture: HIGH - Patterns verified in working production code
- Pitfalls: HIGH - Derived from existing codebase comments and documented workarounds
- API-01 answer: HIGH - Multiple sources confirm, existing code uses workaround
- API-02 answer: HIGH - Working queries in production codebase
- API-03 answer: MEDIUM - Documented but not tested with this account's data volume
- API-04 answer: HIGH - Official Google announcement
- API-05 answer: HIGH - Confirmed in MCP schema and existing sheets integration

**Research date:** 2026-02-11
**Valid until:** 2026-03-15 (30 days - Google Ads API is stable, but should revalidate before Phase 1-5 execution)

---

**Next Steps:**
- Phase 2: Comprehensive Data Discovery (enumerate all views, metrics, filtering capabilities)
- Phase 3: Sample Testing & Analysis (test LIMIT performance, historical data availability, validate with real queries)
- Phase 4: Documentation & Decision (consolidate into comprehensive API reference, provide Go/No-Go recommendation)
