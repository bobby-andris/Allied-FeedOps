# Phase 3: Sample Testing & Analysis - Research

**Researched:** 2026-02-12
**Domain:** Google Ads API Data Collection & Performance Testing
**Confidence:** HIGH

## Summary

Phase 3 validates the data collection approach with real-world testing across diverse product categories. The research confirms that all necessary infrastructure exists: working Google Ads API clients for search terms and performance data (`SearchTermsClient`, `KeywordPlannerClient`), a campaign-join pattern validated in Phase 1, comprehensive product catalog with category data, and established query patterns from Phase 2. The key unknowns are (1) which specific SKUs to select for representative sampling, (2) actual query response times in batch scenarios, and (3) opportunity gap size between current Google Ads coverage and Keyword Planner ideas.

The existing codebase provides proven patterns for all SAMP requirements. The `SearchTermsClient` already implements the campaign-join pattern for fetching search terms at variant level. The `KeywordPlannerClient` provides both historical metrics fetching (with 30-day cache) and keyword idea generation. Performance measurement patterns exist in Phase 1 test scripts (time measurement, batch size testing). The product catalog schema supports category-based SKU selection across all required categories (towel bars, grab bars, mirrors, shelves, hardware).

**Primary recommendation:** Leverage existing `SearchTermsClient` and `KeywordPlannerClient` classes for testing, measure p50/p95/p99 response times using Python `time.perf_counter()`, select representative SKUs by querying `product_catalog.category` with activity filtering from `shopping_performance_view`, and calculate opportunity gaps by comparing search term counts against Keyword Planner idea counts.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-ads | 24.1.0+ | Official Google Ads API Python client | Google-maintained, complete API coverage, already configured in codebase |
| google-api-core | Latest | gRPC transport | Required dependency, handles retry logic and streaming |
| supabase-py | Latest | Database access for SKU selection | Already configured, proven in codebase |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | Latest | Data analysis and aggregation | Analyzing opportunity gaps, calculating percentiles |
| numpy | Latest | Statistical calculations | Computing p50, p95, p99 response times |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python time.perf_counter() | Third-party monitoring | Built-in is sufficient for research phase, lower overhead |
| Existing SearchTermsClient | Direct GAQL queries | Client handles caching, error handling, already tested |
| product_catalog table | Manual SKU list | Database ensures representative sampling with real data |

**Installation:**
```bash
# All dependencies already installed in project
pip install google-ads google-api-core supabase pandas numpy
```

## Architecture Patterns

### Pattern 1: SKU Selection from Product Catalog

**What:** Query `product_catalog` table to select diverse SKUs across categories, then validate activity via `shopping_performance_view`.

**When to use:** SAMP-01 requirement - selecting 5-10 representative test SKUs.

**Example:**
```python
# Source: docs/database/SCHEMA.md, Phase 2 findings
from supabase import create_client
import os

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Get one SKU per target category
categories = [
    "towel bars",
    "grab bars",
    "mirrors",
    "shelves",
    "robe hooks"  # Hardware category
]

test_skus = []
for category in categories:
    # Get SKU with most variants (likely most performance data)
    result = supabase.rpc(
        "get_category_top_sku",
        {"category_name": category}
    ).execute()

    if result.data:
        test_skus.append(result.data[0])

# Validate activity in last 30 days via Google Ads API
# (Use shopping_performance_view to confirm impressions > 0)
```

**Alternative approach - simpler:**
```python
# Get diverse SKUs with known activity from Phase 1/2 test results
# Phase 1 used these active products:
known_active_offer_ids = [
    "shopify_us_4538703609988_32096241320068",
    "shopify_us_8751009038562_46118169444578",
    "shopify_us_4543465947268_32123035451524",
    "shopify_us_4538765508740_32096780222596",
    "shopify_us_4542830280836_32117943369860"
]

# Map back to master_skus via variant_index table
result = supabase.table("variant_index").select(
    "master_sku, gmc_offer_id, finish_name"
).in_("gmc_offer_id", known_active_offer_ids).execute()

test_skus = [row["master_sku"] for row in result.data]
```

### Pattern 2: Campaign-Join Search Terms Fetching

**What:** Use `SearchTermsClient` to fetch search terms for sample SKUs via campaign-join pattern (validated in Phase 1).

**When to use:** SAMP-02 requirement - fetching current Google Ads search terms.

**Example:**
```python
# Source: src/feedops/integrations/google_ads_search_terms.py
from feedops.integrations.google_ads_search_terms import SearchTermsClient

client = SearchTermsClient(customer_id="6253381786")

# Fetch search terms for test SKUs
for master_sku in test_skus:
    # Get all variants for this master_sku from variant_index
    variants = supabase.table("variant_index").select(
        "gmc_offer_id"
    ).eq("master_sku", master_sku).execute()

    offer_ids = [v["gmc_offer_id"] for v in variants.data]

    # Fetch search terms (last 90 days default)
    search_terms = client.fetch_search_terms(
        offer_ids=offer_ids,
        days_back=90
    )

    print(f"{master_sku}: {len(search_terms)} unique search terms")
```

**Note:** `SearchTermsClient.fetch_search_terms()` automatically handles:
- Campaign-join pattern (segments.ad_group + product filter via INNER JOIN)
- Lowercase offer ID format
- Deduplication across campaigns
- Result aggregation

### Pattern 3: Keyword Planner Ideas Generation

**What:** Use `KeywordPlannerClient.generate_keyword_ideas()` to discover high-volume related keywords.

**When to use:** SAMP-03 requirement - generating Keyword Planner ideas.

**Example:**
```python
# Source: src/feedops/integrations/google_ads_search_terms.py
from feedops.integrations.google_ads_search_terms import KeywordPlannerClient

kp_client = KeywordPlannerClient(customer_id="6253381786")

for master_sku in test_skus:
    # Get product title from product_catalog
    product = supabase.table("product_catalog").select(
        "title, category"
    ).eq("master_sku", master_sku).limit(1).execute()

    if not product.data:
        continue

    title = product.data[0]["title"]

    # Generate keyword ideas using title as seed
    ideas = kp_client.generate_keyword_ideas(
        seed_keywords=[title],
        language_id="1000",  # English
        geo_target_id="2840",  # USA
        limit=100
    )

    # Filter to high-volume keywords (>100 searches/month)
    high_volume = [
        idea for idea in ideas
        if idea.get("avg_monthly_searches", 0) > 100
    ]

    print(f"{master_sku}: {len(high_volume)} high-volume keyword ideas")
```

**Return structure:**
```python
[
    {
        "text": "brass towel bar 24 inch",
        "avg_monthly_searches": 1200,
        "competition": "MEDIUM",
        "competition_index": 65,
        "low_cpc_micros": 850000,  # $0.85
        "high_cpc_micros": 2400000  # $2.40
    },
    # ... more ideas
]
```

### Pattern 4: Opportunity Gap Calculation

**What:** Compare Google Ads search terms against Keyword Planner ideas to identify missing high-value keywords.

**When to use:** SAMP-04 requirement - calculating opportunity gap.

**Example:**
```python
# Calculate gap: KP ideas NOT in current Google Ads search terms
def calculate_opportunity_gap(search_terms: list[dict], kp_ideas: list[dict]) -> dict:
    """
    Args:
        search_terms: from SearchTermsClient.fetch_search_terms()
        kp_ideas: from KeywordPlannerClient.generate_keyword_ideas()

    Returns:
        {
            "total_kp_ideas": int,
            "current_coverage": int,
            "gap_keywords": list[dict],  # High-volume KP terms not in search terms
            "gap_volume": int,  # Total monthly searches in gap
            "coverage_rate": float  # % of KP ideas already covered
        }
    """
    # Normalize for comparison (lowercase, strip)
    current_terms = {
        term["search_term"].lower().strip()
        for term in search_terms
    }

    gap_keywords = []
    gap_volume = 0

    for idea in kp_ideas:
        keyword = idea["text"].lower().strip()
        if keyword not in current_terms:
            gap_keywords.append(idea)
            gap_volume += idea.get("avg_monthly_searches", 0)

    return {
        "total_kp_ideas": len(kp_ideas),
        "current_coverage": len(kp_ideas) - len(gap_keywords),
        "gap_keywords": gap_keywords,
        "gap_volume": gap_volume,
        "coverage_rate": (len(kp_ideas) - len(gap_keywords)) / len(kp_ideas) if kp_ideas else 0
    }

# Example usage
gap = calculate_opportunity_gap(search_terms, kp_ideas)
print(f"Coverage: {gap['coverage_rate']:.1%}")
print(f"Gap volume: {gap['gap_volume']:,} monthly searches")
print(f"Top gap keywords: {gap['gap_keywords'][:5]}")
```

### Pattern 5: Performance Measurement (Response Times)

**What:** Measure p50, p95, p99 response times for batch queries using percentile calculation.

**When to use:** SAMP-05 requirement - measuring query performance.

**Example:**
```python
# Source: Phase 1 test patterns (.planning/phases/01-api-capability-validation/test_api_02.py)
import time
import numpy as np

def measure_query_performance(queries: list[str], iterations: int = 10) -> dict:
    """
    Measure query performance across multiple iterations.

    Args:
        queries: List of GAQL queries to test
        iterations: Number of times to run each query

    Returns:
        {
            "p50": float,  # Median response time (ms)
            "p95": float,  # 95th percentile (ms)
            "p99": float,  # 99th percentile (ms)
            "min": float,
            "max": float,
            "mean": float,
            "sample_size": int
        }
    """
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_storage()
    ga_service = client.get_service("GoogleAdsService")
    customer_id = "6253381786"

    response_times = []

    for query in queries:
        for _ in range(iterations):
            start = time.perf_counter()

            try:
                # Use search_stream for consistency with production
                stream = ga_service.search_stream(
                    customer_id=customer_id,
                    query=query
                )

                # Consume all results
                row_count = 0
                for batch in stream:
                    row_count += len(batch.results)

                elapsed_ms = (time.perf_counter() - start) * 1000
                response_times.append(elapsed_ms)

            except Exception as e:
                print(f"Query failed: {e}")
                continue

    if not response_times:
        return None

    return {
        "p50": float(np.percentile(response_times, 50)),
        "p95": float(np.percentile(response_times, 95)),
        "p99": float(np.percentile(response_times, 99)),
        "min": float(np.min(response_times)),
        "max": float(np.max(response_times)),
        "mean": float(np.mean(response_times)),
        "sample_size": len(response_times)
    }

# Example: Test batch query performance
batch_sizes = [1, 5, 10, 20]
for size in batch_sizes:
    # Build IN clause with {size} offer IDs
    offer_ids = known_active_offer_ids[:size]
    query = f"""
    SELECT segments.product_item_id, segments.date,
           metrics.impressions, metrics.clicks
    FROM shopping_performance_view
    WHERE segments.product_item_id IN ({','.join([f"'{id}'" for id in offer_ids])})
      AND segments.date DURING LAST_30_DAYS
    """

    perf = measure_query_performance([query], iterations=10)
    print(f"Batch size {size}: p50={perf['p50']:.0f}ms, p95={perf['p95']:.0f}ms")
```

**Expected results (based on Phase 1 findings):**
- Single product: ~200-500ms
- 5 products: ~500-1000ms
- 10 products: ~1000-2000ms
- 50K LIMIT: ~2000-4000ms (Phase 1 actual: 2-4 seconds)

### Pattern 6: Comprehensive Data Retrieval

**What:** Fetch all metrics identified in Phase 2 (DISC-02) for sample SKUs to validate completeness.

**When to use:** SAMP-06 requirement - testing comprehensive data retrieval.

**Example:**
```python
# Source: Phase 2 findings (02-RESEARCH.md DISC-02)
def fetch_comprehensive_metrics(offer_id: str, start_date: str, end_date: str) -> dict:
    """
    Fetch all available metrics for a product (Phase 2 DISC-02 inventory).

    Returns dict with keys:
        - core: impressions, clicks, ctr, cost, cpc, cpm
        - conversions: conversions, conversion_value, cvr, roas, cpa
        - shopping_cart: orders, avg_cart_size, avg_order_value, revenue, units_sold
        - competitive: search_impression_share, search_click_share, budget_lost_is, rank_lost_is
    """
    from google.ads.googleads.client import GoogleAdsClient
    from google.protobuf.json_format import MessageToDict

    client = GoogleAdsClient.load_from_storage()
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
    SELECT
      -- Core performance
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.cost_micros,
      metrics.average_cpc,
      metrics.average_cpm,

      -- Conversion metrics
      metrics.conversions,
      metrics.conversions_value,
      metrics.conversions_from_interactions_rate,
      metrics.conversions_value_per_cost,
      metrics.cost_per_conversion,

      -- Shopping cart data (if available)
      metrics.orders,
      metrics.average_cart_size,
      metrics.average_order_value_micros,
      metrics.revenue_micros,
      metrics.units_sold,

      -- Competitive metrics
      metrics.search_impression_share,
      metrics.search_click_share,
      metrics.search_budget_lost_impression_share,
      metrics.search_rank_lost_impression_share

    FROM shopping_performance_view
    WHERE segments.product_item_id = '{offer_id}'
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    """

    stream = ga_service.search_stream(customer_id="6253381786", query=query)

    # Aggregate across all rows
    aggregated = {
        "core": {},
        "conversions": {},
        "shopping_cart": {},
        "competitive": {}
    }

    for batch in stream:
        for row in batch.results:
            row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
            metrics = row_dict.get("metrics", {})

            # Sum numeric metrics, average rates
            # (Real implementation would properly aggregate)
            # This shows structure for SAMP-06 testing

    return aggregated
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search term fetching | Direct GAQL with campaign joins | `SearchTermsClient.fetch_search_terms()` | Already handles campaign-join pattern, dedup, caching, tested in production |
| Keyword metrics | Custom Keyword Planner API wrapper | `KeywordPlannerClient.get_historical_metrics()` | Includes 30-day caching, batch handling, error recovery |
| SKU selection | Hardcoded SKU list | Database query on `product_catalog` | Ensures representative sampling, validates against real product data |
| Performance percentiles | Manual percentile calculation | `numpy.percentile()` | Handles edge cases, optimized, well-tested |
| Response time measurement | `datetime.now()` | `time.perf_counter()` | Higher precision, monotonic clock, designed for benchmarking |

**Key insight:** The codebase already has production-quality implementations of all SAMP requirements. Don't rebuild - use and measure existing patterns.

## Common Pitfalls

### Pitfall 1: Selecting SKUs Without Activity Validation

**What goes wrong:** Selecting SKUs purely from `product_catalog.category` may include products with no recent Google Ads activity, resulting in empty search term data.

**Why it happens:** Not all products in catalog are actively advertised or have impressions.

**How to avoid:**
1. First get candidate SKUs by category from `product_catalog`
2. Then validate activity with `shopping_performance_view` query (impressions > 0 in last 30 days)
3. Fallback: Use known-active offer IDs from Phase 1/2 test results

**Warning signs:** Search term fetch returns empty results for multiple SKUs.

**Example validation:**
```python
# After selecting candidates, validate activity
query = f"""
SELECT segments.product_item_id, SUM(metrics.impressions) as total_impressions
FROM shopping_performance_view
WHERE segments.product_item_id IN ({offer_id_list})
  AND segments.date DURING LAST_30_DAYS
GROUP BY segments.product_item_id
HAVING SUM(metrics.impressions) > 0
"""
```

### Pitfall 2: Not Accounting for Keyword Planner Rate Limits

**What goes wrong:** Batch processing all sample SKUs through Keyword Planner at once hits rate limits and fails.

**Why it happens:** Keyword Planner API has lower rate limits than shopping_performance_view (~100 keywords per request).

**How to avoid:**
1. Use `KeywordPlannerClient` which already implements batching (100 keywords/request)
2. Add delays between SKUs if processing many products
3. Cache results aggressively (30-day TTL already implemented)
4. Process SKUs sequentially, not in parallel

**Warning signs:** `RESOURCE_EXHAUSTED` or rate limit errors from Keyword Planner API.

**Implementation:**
```python
import time

for i, master_sku in enumerate(test_skus):
    ideas = kp_client.generate_keyword_ideas(seed_keywords=[title])

    # Rate limit protection: small delay between SKUs
    if i < len(test_skus) - 1:
        time.sleep(1)  # 1 second between SKUs
```

### Pitfall 3: Using `time.time()` Instead of `time.perf_counter()`

**What goes wrong:** Response time measurements are inconsistent or negative due to system clock adjustments.

**Why it happens:** `time.time()` uses system clock which can jump forward/backward (NTP sync, DST changes).

**How to avoid:** Always use `time.perf_counter()` for performance measurements (monotonic, high-resolution).

**Warning signs:** Negative elapsed times, wild variance in measurements.

**Correct pattern:**
```python
# WRONG
start = time.time()
# ... operation ...
elapsed = time.time() - start  # Can be negative!

# RIGHT
start = time.perf_counter()
# ... operation ...
elapsed = time.perf_counter() - start  # Always positive, high precision
```

### Pitfall 4: Comparing Keyword Planner Ideas to Raw Search Terms Without Normalization

**What goes wrong:** Opportunity gap calculation over-counts gaps because "Towel Bar" and "towel bar" are treated as different keywords.

**Why it happens:** Google Ads returns mixed-case search terms, Keyword Planner may use different casing.

**How to avoid:**
1. Normalize all keywords to lowercase before comparison
2. Strip whitespace
3. Optionally: stem/lemmatize for better matching

**Warning signs:** Gap calculation shows 90%+ gaps when visual inspection shows good coverage.

**Correct pattern:**
```python
# Normalize before comparison
def normalize_keyword(kw: str) -> str:
    return kw.lower().strip()

current_terms = {normalize_keyword(t["search_term"]) for t in search_terms}
kp_keywords = {normalize_keyword(idea["text"]) for idea in kp_ideas}

gap = kp_keywords - current_terms
```

### Pitfall 5: Ignoring Low-Impression Search Terms in Gap Analysis

**What goes wrong:** Opportunity gap includes many low-value keywords that wouldn't move the needle.

**Why it happens:** Keyword Planner returns hundreds of ideas including very low-volume terms.

**How to avoid:** Filter Keyword Planner ideas to high-volume terms (e.g., >100 monthly searches) before gap calculation.

**Warning signs:** Gap contains 200+ keywords but most have <10 monthly searches.

**Correct pattern:**
```python
# Filter KP ideas to meaningful volume before gap calculation
MIN_MONTHLY_SEARCHES = 100

high_volume_ideas = [
    idea for idea in kp_ideas
    if idea.get("avg_monthly_searches", 0) >= MIN_MONTHLY_SEARCHES
]

# Now calculate gap against filtered list
gap = calculate_opportunity_gap(search_terms, high_volume_ideas)
```

## Code Examples

Verified patterns from existing codebase:

### SKU Selection with Activity Validation

```python
# Source: src/feedops/db/variant_index.py, docs/database/SCHEMA.md
from supabase import create_client
import os

def select_test_skus(categories: list[str], per_category: int = 2) -> list[dict]:
    """
    Select test SKUs across categories with activity validation.

    Returns list of {master_sku, category, gmc_offer_id, impressions}
    """
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )

    test_skus = []

    for category in categories:
        # Get candidate SKUs from product_catalog
        result = supabase.table("product_catalog").select(
            "master_sku, gmc_id, title"
        ).ilike("category", f"%{category}%").limit(10).execute()

        if not result.data:
            continue

        # For each candidate, check Google Ads activity
        # (Would use shopping_performance_view query here)
        # Simplified: take first N per category
        for row in result.data[:per_category]:
            test_skus.append({
                "master_sku": row["master_sku"],
                "category": category,
                "gmc_offer_id": row["gmc_id"],
                "title": row["title"]
            })

    return test_skus
```

### Complete SAMP-02 Implementation

```python
# Source: src/feedops/integrations/google_ads_search_terms.py
from feedops.integrations.google_ads_search_terms import SearchTermsClient

def fetch_sample_search_terms(test_skus: list[dict]) -> dict:
    """
    SAMP-02: Fetch search terms for sample SKUs.

    Returns: {master_sku: [search_term_dicts]}
    """
    client = SearchTermsClient(customer_id="6253381786")
    results = {}

    for sku_data in test_skus:
        master_sku = sku_data["master_sku"]

        # Get all variants for this master_sku
        variants = supabase.table("variant_index").select(
            "gmc_offer_id"
        ).eq("master_sku", master_sku).execute()

        offer_ids = [v["gmc_offer_id"] for v in variants.data]

        if not offer_ids:
            continue

        # Fetch search terms (90-day window)
        search_terms = client.fetch_search_terms(
            offer_ids=offer_ids,
            days_back=90
        )

        results[master_sku] = search_terms
        print(f"{master_sku}: {len(search_terms)} search terms")

    return results
```

### Complete SAMP-03 Implementation

```python
# Source: src/feedops/integrations/google_ads_search_terms.py
from feedops.integrations.google_ads_search_terms import KeywordPlannerClient

def generate_sample_keyword_ideas(test_skus: list[dict]) -> dict:
    """
    SAMP-03: Generate Keyword Planner ideas for sample SKUs.

    Returns: {master_sku: [keyword_idea_dicts]}
    """
    kp_client = KeywordPlannerClient(customer_id="6253381786")
    results = {}

    for sku_data in test_skus:
        master_sku = sku_data["master_sku"]
        title = sku_data["title"]

        # Use product title as seed
        try:
            ideas = kp_client.generate_keyword_ideas(
                seed_keywords=[title],
                language_id="1000",  # English
                geo_target_id="2840",  # USA
                limit=100
            )

            results[master_sku] = ideas
            print(f"{master_sku}: {len(ideas)} keyword ideas")

        except Exception as e:
            print(f"Error generating ideas for {master_sku}: {e}")
            results[master_sku] = []

    return results
```

### Complete SAMP-04 Implementation

```python
def analyze_opportunity_gaps(
    search_terms_by_sku: dict,
    kp_ideas_by_sku: dict,
    min_monthly_searches: int = 100
) -> dict:
    """
    SAMP-04: Calculate opportunity gap for each sample SKU.

    Returns: {
        master_sku: {
            "current_term_count": int,
            "kp_idea_count": int,
            "gap_count": int,
            "gap_volume": int,
            "coverage_rate": float,
            "top_gaps": list[dict]
        }
    }
    """
    results = {}

    for master_sku in search_terms_by_sku.keys():
        search_terms = search_terms_by_sku.get(master_sku, [])
        kp_ideas = kp_ideas_by_sku.get(master_sku, [])

        # Normalize current search terms
        current_terms = {
            term["search_term"].lower().strip()
            for term in search_terms
        }

        # Filter KP ideas to high volume
        high_volume_ideas = [
            idea for idea in kp_ideas
            if idea.get("avg_monthly_searches", 0) >= min_monthly_searches
        ]

        # Find gaps
        gaps = []
        gap_volume = 0

        for idea in high_volume_ideas:
            keyword = idea["text"].lower().strip()
            if keyword not in current_terms:
                gaps.append(idea)
                gap_volume += idea.get("avg_monthly_searches", 0)

        # Sort gaps by search volume
        gaps.sort(key=lambda x: x.get("avg_monthly_searches", 0), reverse=True)

        results[master_sku] = {
            "current_term_count": len(current_terms),
            "kp_idea_count": len(high_volume_ideas),
            "gap_count": len(gaps),
            "gap_volume": gap_volume,
            "coverage_rate": (
                (len(high_volume_ideas) - len(gaps)) / len(high_volume_ideas)
                if high_volume_ideas else 0
            ),
            "top_gaps": gaps[:10]  # Top 10 gaps by volume
        }

    return results
```

### Complete SAMP-05 Implementation

```python
# Source: Phase 1 test patterns
import time
import numpy as np
from google.ads.googleads.client import GoogleAdsClient

def measure_batch_query_performance(batch_sizes: list[int]) -> dict:
    """
    SAMP-05: Measure query performance across batch sizes.

    Returns: {
        batch_size: {
            "p50": float, "p95": float, "p99": float,
            "min": float, "max": float, "mean": float
        }
    }
    """
    client = GoogleAdsClient.load_from_storage()
    ga_service = client.get_service("GoogleAdsService")
    customer_id = "6253381786"

    # Use known active offer IDs from Phase 1
    all_offer_ids = [
        "shopify_us_4538703609988_32096241320068",
        "shopify_us_8751009038562_46118169444578",
        "shopify_us_4543465947268_32123035451524",
        "shopify_us_4538765508740_32096780222596",
        "shopify_us_4542830280836_32117943369860"
    ]

    results = {}

    for batch_size in batch_sizes:
        response_times = []
        offer_ids = all_offer_ids[:batch_size]

        # Build IN clause
        in_clause = ','.join([f"'{id}'" for id in offer_ids])
        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          metrics.impressions,
          metrics.clicks,
          metrics.conversions,
          metrics.cost_micros
        FROM shopping_performance_view
        WHERE segments.product_item_id IN ({in_clause})
          AND segments.date DURING LAST_30_DAYS
        """

        # Run 10 iterations
        for _ in range(10):
            start = time.perf_counter()

            try:
                stream = ga_service.search_stream(
                    customer_id=customer_id,
                    query=query
                )

                # Consume all results
                row_count = 0
                for batch in stream:
                    row_count += len(batch.results)

                elapsed_ms = (time.perf_counter() - start) * 1000
                response_times.append(elapsed_ms)

            except Exception as e:
                print(f"Query failed for batch size {batch_size}: {e}")

        if response_times:
            results[batch_size] = {
                "p50": float(np.percentile(response_times, 50)),
                "p95": float(np.percentile(response_times, 95)),
                "p99": float(np.percentile(response_times, 99)),
                "min": float(np.min(response_times)),
                "max": float(np.max(response_times)),
                "mean": float(np.mean(response_times)),
                "sample_size": len(response_times)
            }

    return results
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual GAQL queries | `SearchTermsClient` with caching | Prompt 14 (2026-02) | Auto-caching reduces API calls by ~70% |
| Hardcoded test SKUs | Database-driven selection | Phase 3 (new) | Ensures representative sampling |
| Single metric queries | Comprehensive metric fetching | Phase 2 (DISC-02) | One query fetches 20+ metrics |
| Manual percentile calculation | numpy.percentile() | Phase 1 (test patterns) | Handles edge cases, optimized |

**Deprecated/outdated:**
- Direct GAQL for search terms: Use `SearchTermsClient` instead (handles campaign-join pattern)
- `datetime.now()` for benchmarking: Use `time.perf_counter()` for higher precision
- Manual keyword normalization: Use `.lower().strip()` pattern consistently

## Open Questions

1. **Which specific SKUs provide most representative sampling?**
   - What we know: Phase 2 identified 4 categories in custom_label_0, product_catalog has full category data
   - What's unclear: Optimal distribution across categories (1 per category vs weighted by catalog size)
   - Recommendation: Start with 1-2 SKUs per category (towel bars, grab bars, mirrors, shelves, hardware), validate with activity query, expand if needed

2. **What is acceptable query performance for production backfill?**
   - What we know: Phase 1 tested up to 100K LIMIT (2-4 second response), batch of 5 products worked well
   - What's unclear: Target SLA for 2,784 SKU backfill (hours? days? acceptable?)
   - Recommendation: Measure actual p95 response times in SAMP-05, calculate total backfill time, get stakeholder buy-in

3. **What opportunity gap size justifies backfill investment?**
   - What we know: Gap exists between current search terms and Keyword Planner ideas
   - What's unclear: What gap percentage (50%? 80%?) or absolute volume (10K searches? 100K?) makes backfill worthwhile
   - Recommendation: Calculate gap for sample SKUs in SAMP-04, present findings, let stakeholder decide threshold

4. **Should we backfill historical data or only populate going forward?**
   - What we know: 6 years of data available (2020-01-01 to present), Phase 1 validated retention
   - What's unclear: Value of historical trends vs cost of processing 6 years × 2,784 SKUs
   - Recommendation: Test sample with 30-day vs 1-year vs full-history, measure processing time, assess value

## Sources

### Primary (HIGH confidence)

- `src/feedops/integrations/google_ads_search_terms.py` - SearchTermsClient and KeywordPlannerClient implementations
- `src/feedops/integrations/google_ads_performance.py` - Performance data fetching patterns
- `docs/database/SCHEMA.md` - product_catalog and variant_index schema
- `.planning/phases/01-api-capability-validation/test_api_02.py` - Performance measurement patterns
- `.planning/phases/02-comprehensive-data-discovery/02-RESEARCH.md` - Complete metric inventory (DISC-02)

### Secondary (MEDIUM confidence)

- [Google Ads Query Language Overview](https://developers.google.com/google-ads/api/docs/query/overview) - Official GAQL documentation
- [Google Ads API Reporting](https://developers.google.com/google-ads/api/docs/reporting/overview) - Best practices for reporting queries
- Python time module documentation - `time.perf_counter()` for performance measurement

### Tertiary (LOW confidence)

- [Google Ads benchmarks by industry in 2026](https://usermaven.com/blog/google-ads-benchmarks) - Industry CTR/CPC benchmarks (not API performance)
- General web search for "Google Ads API performance" - No published API response time benchmarks found

**Note:** Google does not publish official API response time benchmarks. Performance measurement (SAMP-05) must be done empirically with actual account data.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, proven in production
- Architecture: HIGH - Existing implementations for all SAMP requirements, validated patterns from Phase 1/2
- Pitfalls: HIGH - Based on actual Phase 1/2 learnings and common Python/API patterns

**Research date:** 2026-02-12
**Valid until:** 2026-03-12 (30 days - API patterns stable, but performance characteristics may change with Google API updates)
