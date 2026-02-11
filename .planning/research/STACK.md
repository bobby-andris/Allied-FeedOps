# Stack Research

**Domain:** Google Ads API Integration (Python)
**Researched:** 2026-02-11
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| google-ads | 29.0.0 | Official Google Ads API client library | Google's official Python client with full API coverage, active maintenance, and best-in-class authentication handling. Supports GAQL queries, streaming for large datasets, and all Google Ads API v18+ features. |
| Python | >=3.11 | Runtime environment | Project already on 3.11+. Library requires >=3.9 but 3.11+ provides better performance and type hints. Cloud Run supports 3.11+ natively. |
| GAQL | v18+ | Google Ads Query Language | Standard query language for Google Ads API. SQL-like syntax optimized for advertising data. Required for search_stream and search operations. |
| google-auth | >=2.48.0 | Authentication | Official OAuth2/service account library. Already in project dependencies. Handles refresh tokens and credential lifecycle. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | >=2.0 | Data processing for large result sets | Processing 50K+ row query results before Supabase insert. Already in project. Essential for batch operations and data transformation. |
| supabase | >=2.0 | Data storage | Storing search terms, performance data, keyword metrics. Already integrated with project. |
| google-api-python-client | >=2.0 | Merchant API integration | Required for custom_label_0 sync via Merchant API. Already in project for GMC integration. |
| httpx | >=0.25 | HTTP client for API calls | Async-capable client for concurrent API operations. Already in project dependencies. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Unit testing Google Ads queries | Already configured in project. Use pytest-asyncio for async client tests. |
| google-ads-python CLI | OAuth2 setup and testing | Bundled with library. Use `generate_user_credentials.py` for initial auth setup. |
| BigQuery (optional) | Large-scale data backfill | Google's recommended pattern for historical data migration (2+ years of performance data). |

## Installation

```bash
# Core
pip install google-ads>=29.0.0

# Supporting (already in project)
pip install pandas>=2.0 supabase>=2.0 google-auth>=2.48.0 google-api-python-client>=2.0

# Dev dependencies
pip install pytest>=7.0 pytest-asyncio>=0.21
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| google-ads 29.0.0 | google-ads 28.4.1 (current) | Project is already on 28.x. Upgrade to 29.0.0 for latest API features, but not urgent—28.x still supported. |
| SearchStream | Search with pagination | Use Search for <10K rows. SearchStream automatically handles pagination for 50K+ results. |
| Service account auth | OAuth2 user credentials | Service accounts better for Cloud Run automation. OAuth2 for user-initiated flows. Project uses OAuth2 refresh tokens (already configured). |
| BigQuery backfill | Direct API iteration | BigQuery recommended by Google for 2+ year historical data loads. Direct API works for <180 day backfills. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| google-ads-python <28.0 | Deprecated API versions (v15 and earlier). Missing GAQL streaming features. | google-ads >=28.4.1 (current project) or >=29.0.0 (latest) |
| AdWords API libraries | Sunset in April 2022. Replaced by Google Ads API. | google-ads (Google Ads API v18+) |
| Manual pagination loops | Error-prone, doesn't handle rate limits. Library has built-in streaming. | `search_stream()` for large datasets (>10K rows) |
| Hardcoded credentials | Security risk, breaks Cloud Run deployments. | Environment variables (GOOGLE_ADS_DEVELOPER_TOKEN, etc.) or google-ads.yaml with secret management |

## Stack Patterns by Variant

**If querying <10K rows (e.g., single product search terms):**
- Use `GoogleAdsService.Search()` with fixed 10K page size
- Results fit in memory, simpler error handling

**If querying 50K+ rows (e.g., all search terms, all performance data):**
- Use `GoogleAdsService.SearchStream()`
- Library handles pagination automatically
- Lower memory footprint (streaming iterator)

**If backfilling 2+ years of data:**
- Use BigQuery Data Transfer Service (Google's recommended pattern)
- Schedule Cloud Run function to pull from BigQuery to Supabase
- Avoids API rate limits for large historical loads

## Query Patterns (GAQL)

### Product-Level Search Terms
```sql
SELECT
  segments.date,
  segments.product_item_id,
  segments.search_term_match_type,
  metrics.impressions,
  metrics.clicks
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND segments.product_item_id IS NOT NULL
```

**Data Retention:** 180 days for search_term_view

### Performance Data
```sql
SELECT
  segments.date,
  segments.product_item_id,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM shopping_performance_view
WHERE segments.date DURING LAST_730_DAYS
  AND campaign.advertising_channel_type = 'SHOPPING'
```

**Data Retention:** 2 years (730 days) for performance metrics

### Pagination Limits
- **Search:** 10K rows per page (fixed)
- **SearchStream:** No explicit limit, streams all results
- **Rate Limits:** Standard access = no read limits (confirmed for customer 6253381786)

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| google-ads 29.0.0 | Python >=3.9 | Project uses 3.11+ (fully compatible) |
| google-ads 28.4.1 | Python >=3.9 | Current project version (fully compatible) |
| pandas >=2.0 | Python >=3.9 | Already in project at 2.0+ |
| google-auth >=2.48.0 | Python >=3.7 | Already in project, no conflicts |

## API Validation Findings

Based on existing code (`src/feedops/integrations/google_ads_search_terms.py`) and official documentation:

✅ **Product-level queries confirmed:** `segments.product_item_id` filter works in `search_term_view` and `shopping_performance_view`

✅ **Large result sets supported:** SearchStream handles 50K+ rows automatically (tested pattern in existing code)

✅ **Data retention validated:**
- Search terms: 180 days (`search_term_view`)
- Performance: 2 years (`shopping_performance_view`)

✅ **Custom labels available:** Accessible via Merchant API `product_view` (not Google Ads API directly). Requires `google-api-python-client` for Merchant API integration.

⚠️ **Keyword Planner gaps:**
- `GenerateKeywordHistoricalMetrics` provides search volume but NOT opportunity score
- Opportunity analysis requires manual calculation: compare search volume to current impression share
- Rate limited (batch size: 100 keywords max per request)

## Sources

- **Google Ads Python Client Library** (HIGH confidence)
  - Official docs: https://developers.google.com/google-ads/api/docs/client-libs/python
  - PyPI: https://pypi.org/project/google-ads/ (verified v29.0.0, Jan 2026)
  - GitHub: https://github.com/googleads/google-ads-python

- **GAQL Reference** (HIGH confidence)
  - Official query language guide: https://developers.google.com/google-ads/api/docs/query/overview
  - Pagination: https://developers.google.com/google-ads/api/docs/reporting/paging

- **Google Ads API Data Retention** (HIGH confidence)
  - Search terms view: https://developers.google.com/google-ads/api/fields/v18/search_term_view (180 days)
  - Shopping performance view: https://developers.google.com/google-ads/api/fields/v18/shopping_performance_view (730 days)

- **BigQuery Integration Pattern** (MEDIUM confidence)
  - Google Cloud blog: Best practices for Google Ads API data backfill
  - WebSearch verification: Multiple sources confirm BigQuery Data Transfer Service as recommended pattern for large historical loads

- **Existing Implementation** (HIGH confidence)
  - File: `src/feedops/integrations/google_ads_search_terms.py`
  - Current library: google-ads 28.4.1 (from pyproject.toml)
  - Patterns: SearchStream for large queries, environment variable auth, KeywordPlannerClient

---
*Stack research for: Google Ads API Integration (Python)*
*Researched: 2026-02-11*
