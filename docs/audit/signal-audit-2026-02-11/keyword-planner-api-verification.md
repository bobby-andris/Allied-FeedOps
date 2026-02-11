# GenerateKeywordIdeas - Keyword Planner API Verification

## Confirmed: Yes, it uses the Google Ads Keyword Planner API

### Service & Method

- **Service**: `KeywordPlanIdeaService` (Google Ads API)
- **Method**: `generate_keyword_ideas()` — calls `service.generate_keyword_ideas(request=request)`
- **Request type**: `GenerateKeywordIdeasRequest`
- **File**: `src/feedops/integrations/google_ads_search_terms.py`, lines 264-321

### SDK / Library

- **Library**: `google-ads` Python SDK (version `>=28.4.1` per `pyproject.toml`)
- **Client**: `google.ads.googleads.client.GoogleAdsClient`
- **Config**: Loaded from environment variables (Cloud Run secrets) or fallback to YAML config file
- **Proto mode**: `use_proto_plus: True`

### API Details

The `generate_keyword_ideas()` method in `KeywordPlannerClient` class (line 264):

- **Seeds supported**: `KeywordSeed`, `UrlSeed`, or `KeywordAndUrlSeed`
  - Keyword-only: `request.keyword_seed.keywords.extend(seed_keywords[:10])`
  - URL-only: `request.url_seed.url = seed_url`
  - Both: `request.keyword_and_url_seed`
- **Seed limit**: Max 10 keywords per request (hardcoded `[:10]` slice)
- **Default targeting**: English (`languageConstants/1000`), USA (`geoTargetConstants/2840`)
- **Network**: `GOOGLE_SEARCH` only
- **Result limit**: Configurable, default 100 ideas

### Return Format

Each idea returns:
- `keyword` (text)
- `avg_monthly_searches`
- `competition` (LOW/MEDIUM/HIGH/UNSPECIFIED)
- `competition_index` (0-100)
- `low_cpc_micros` / `high_cpc_micros`

### Also in Same Class: `get_historical_metrics()`

Uses `GenerateKeywordHistoricalMetricsRequest` on the same `KeywordPlanIdeaService`. This method:
- Supports batching (100 keywords per API call)
- Has Supabase caching in `keyword_metrics` table (30-day TTL)
- Returns monthly search volume breakdown in addition to the fields above

### How It's Exposed

1. **Cloud Run API endpoint**: `GET /search-insights/keywords/ideas`
   - File: `src/feedops/api/search_insights.py`, line 292
   - Parameters: `seed_keywords` (comma-separated), `seed_url` (optional), `limit` (default 50)
   - Instantiates `KeywordPlannerClient()` and calls `generate_keyword_ideas()`

2. **Historical metrics endpoint**: `POST /search-insights/keywords/metrics`
   - File: `src/feedops/api/search_insights.py`, line ~175
   - Calls `kp_client.get_historical_metrics()`

3. **NOT wired into evidence building**: No references in `src/feedops/pipeline/` or `dashboard/src/lib/evidence/`. It's purely an API-only feature for the Search Query Insights dashboard.

4. **NOT referenced in dashboard TypeScript**: No imports of KeywordPlannerClient or generate_keyword_ideas in the dashboard codebase.

### Quota / Rate Limits

- Documented in code comments: "rate limit: ~100 per request" (for historical metrics batching)
- No explicit rate-limit handling or retry logic — failures are caught and logged as warnings
- The Keyword Planner API is generally more rate-limited than other Google Ads services (noted in MEMORY.md)

### Customer ID

- Default: `6253381786` (Allied Brass account)
- Configurable via `GOOGLE_ADS_CUSTOMER_ID` env var or constructor parameter
