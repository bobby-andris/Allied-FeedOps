# External Signals Assessment: Keyword Planner + Merchant Competitive

## Executive Summary

**Keyword Planner: FULLY IMPLEMENTED and wired into generation pipeline.** Both `GenerateKeywordHistoricalMetrics` and `GenerateKeywordIdeas` are coded, deployed, cached, and actively feeding evidence to the LLM. No new implementation needed.

**Merchant API Competitive Metrics: NOT implemented.** No `price_competitiveness_product_view` or `benchmark_price` code exists anywhere in the codebase. Competitive intelligence relies entirely on Apify-based SERP/marketplace scraping, which IS implemented and wired into generation.

**Cold-start SKU gap: Partially addressed.** Search query data requires existing Google Ads impressions. For SKUs with zero ad history, the `GenerateKeywordIdeas` endpoint exists but is NOT automatically invoked during generation -- it's only exposed as a manual API endpoint.

---

## 1. Keyword Planner -- Implementation Status

### 1.1 What EXISTS and is DEPLOYED

| Component | Location | Status |
|---|---|---|
| `KeywordPlannerClient` class | `src/feedops/integrations/google_ads_search_terms.py:86-321` | **PRODUCTION** |
| `get_historical_metrics()` | Same file, lines 110-165 | Fetches `avg_monthly_searches`, `competition`, `competition_index`, CPC data |
| `generate_keyword_ideas()` | Same file, lines 264-321 | Seeds from keywords or URL, returns up to 250K ideas |
| Cache layer (`keyword_metrics` table) | Schema documented, 30-day TTL | **Operational** -- upsert on `keyword` column |
| Cloud Run API: `/search-insights/sync` | `src/feedops/api/search_insights.py:97-140` | Triggers search term fetch + KP enrichment |
| Cloud Run API: `/search-insights/enrich` | `src/feedops/api/search_insights.py:172-211` | On-demand KP enrichment for arbitrary keywords |
| Cloud Run API: `/search-insights/keywords/ideas` | `src/feedops/api/search_insights.py:292-334` | Manual keyword idea generation |
| `enrich_with_keyword_metrics()` | `google_ads_search_terms.py:1050-1121` | Enriches `search_queries` rows with KP volume data |

### 1.2 How KP Data Flows into Generation

The full pipeline path is:

1. **Data Collection** (`ensureSkuData` / `ensureAllData` in `dashboard/src/lib/data-collection/ensure-data.ts`):
   - Calls `/search-insights/sync` which fetches search terms + enriches with KP metrics
   - Triggered automatically before regeneration and SKU selection
   - 7-day staleness check on `search_query_sync_jobs`

2. **Evidence Assembly** (`src/feedops/pipeline/evidence.py:286-303`):
   - `fetch_search_queries_for_master_sku()` reads from `search_queries_by_master_sku` table
   - Returns `query_text`, `total_impressions`, `avg_monthly_searches`, `competition`
   - `format_search_queries_for_evidence()` formats as Evidence rows with volume annotations (e.g., `"brass towel bar" (2.4K vol)`)
   - Evidence fields: `search_queries_top`, `search_query_themes`

3. **Keyword Gap Detection** (`src/feedops/pipeline/keyword_gaps.py`):
   - `compute_keyword_gaps_for_title()` compares search queries against current title tokens
   - Filters out finish-specific queries, category-irrelevant queries, stop words
   - Produces `keyword_gaps_current_title` evidence field
   - Uses `avg_monthly_searches` (KP data) as primary ranking signal, falls back to impressions

4. **Prompt Injection**: Evidence table is formatted as markdown and injected into LLM prompt

### 1.3 What is NOT Wired

| Feature | Exists as Code | Wired into Generation Pipeline |
|---|---|---|
| `GenerateKeywordHistoricalMetrics` | YES | YES (via sync + enrich flow) |
| `GenerateKeywordIdeas` from seeds | YES (API endpoint) | **NO** -- manual-only endpoint |
| KP cache with 30-day TTL | YES | YES |
| Variant-level search queries | YES (`fetch_search_queries_for_variant`) | **NOT used in evidence.py** -- master-level only |

### 1.4 Gap: Cold-Start SKU Problem

For a brand-new SKU with zero Google Ads impressions:
- `search_queries_by_master_sku` will be empty (no search term data to collect)
- `keyword_metrics` cache may or may not have relevant entries from other SKUs
- `GenerateKeywordIdeas` could seed from product attributes but is NOT called during generation

**Current fallbacks for cold-start:**
- `get_external_keywords()` from `feedops.integrations.keyword_bank` (static keyword bank by category)
- `fetch_master_sku_keywords()` from `feedops.integrations.google_ads` (product-level Google Ads keywords)
- Competitor evidence from SERP scraping (if category has been scraped)
- On-the-fly enrichment from `enrich_product()` (design context, functional features)

**Assessment:** The cold-start fallbacks provide reasonable coverage. The keyword bank + competitor patterns give the LLM category-relevant language. However, `GenerateKeywordIdeas` could improve cold-start quality by discovering high-volume related queries from product attributes.

---

## 2. Merchant API Competitive Metrics -- Implementation Status

### 2.1 What EXISTS

**Zero Merchant API competitive metrics code.** Grep for `price_competitiveness`, `benchmark_price`, and `merchant.*competitive` across the entire `src/` tree returned no results.

### 2.2 What EXISTS for Competitive Intelligence (Alternative)

The project uses **Apify-based SERP and marketplace scraping** instead:

| Component | Location | Status |
|---|---|---|
| Competitor scrape API | `dashboard/src/app/api/competitors/scrape/route.ts` | **PRODUCTION** |
| Scrape ingestion | `dashboard/src/app/api/competitors/ingest/route.ts` | **PRODUCTION** |
| Competitor listings query | `dashboard/src/app/api/competitors/route.ts` | **PRODUCTION** |
| `competitor_listings` table | Schema with `product_category`, `source_type`, `domain`, `brand`, `title`, `position` | **Populated** |
| `competitor_patterns` table | Schema with `pattern_type`, `pattern_value`, `frequency`, `sources` | **Populated** |
| `competitor_scrape_jobs` table | Job tracking for Apify runs | **Populated** |
| Python evidence builder | `src/feedops/pipeline/competitor_evidence.py` | **PRODUCTION** |
| Evidence integration | `src/feedops/pipeline/evidence.py:307-318` | Wired into generation |

**Supported scrape sources:**
- Google SERP (via `apify/google-search-scraper`)
- Amazon (via `axesso_data/amazon-search-scraper`)
- Wayfair (via `123webdata/wayfair-scraper`)
- Home Depot (via `rigelbytes/homedepot-scraper`)

**Evidence fields produced:**
- `competitor_direct_domains` -- top direct competitor domains by frequency
- `competitor_marketplace_domains` -- top marketplace domains
- `competitor_direct_language_patterns` -- title structure patterns from direct sellers
- `competitor_marketplace_language_patterns` -- listing language from marketplaces

**Safety guardrails in competitor_evidence.py:**
- Unsafe language patterns are filtered (`_UNSAFE_COMPETITOR_LANGUAGE_PATTERNS`)
- No comparative claims ("better than", "superior", "outperform")
- Explicitly labeled as "context only, not product facts"

### 2.3 What Merchant API COULD Add

The Google Merchant API offers `price_competitiveness_product_view`:
```sql
SELECT id, offer_id, price, benchmark_price, report_country_code
FROM price_competitiveness_product_view WHERE report_country_code = 'US'
```

This provides:
- `benchmark_price`: Average price competitors charge for the same product
- Price positioning (above/below/at market)

**However:** This data is useful for **pricing strategy and SKU prioritization**, NOT for content generation. The generation pipeline should never make price claims in titles/descriptions. Benchmark price data could inform:
1. Which SKUs to prioritize for optimization (competitively priced = higher conversion potential)
2. Post-publish monitoring (are we competitive on price?)

---

## 3. Ranked Recommendations

### Priority 1: NO ACTION NEEDED -- Keyword Planner (Already Complete)

**Status:** Fully implemented, deployed, and wired into generation.
**Impact:** Already providing search volume signals to every generation run.
**Cost:** Zero.
**Risk:** None.

The only potential enhancement is wiring `GenerateKeywordIdeas` into generation for cold-start SKUs, but the existing fallbacks (keyword bank + competitor patterns + enrichment) provide adequate coverage.

### Priority 2: LOW PRIORITY -- GenerateKeywordIdeas for Cold-Start SKUs

**What:** During `build_evidence_table()`, if `search_queries_by_master_sku` returns empty, call `KeywordPlannerClient.generate_keyword_ideas()` with seed keywords derived from product category + key attributes.

**Implementation sketch:**
```python
# In evidence.py, after search_queries fetch returns empty:
if not search_queries and parent_sku.category:
    kp = KeywordPlannerClient()
    seeds = [parent_sku.category, f"brass {parent_sku.category}"]
    ideas = kp.generate_keyword_ideas(seed_keywords=seeds, limit=20)
    # Convert to same format as search_queries for reuse
    search_queries = [{"query_text": i["keyword"], "avg_monthly_searches": i["avg_monthly_searches"]} for i in ideas]
```

**Impact:** Moderate -- improves first-generation quality for new SKUs. Once a SKU gets ad impressions, real search term data will take over.
**Engineering Cost:** ~2 hours. Add cold-start branch in `evidence.py`, cache results in `keyword_metrics`.
**Risk:** LOW. KP API is rate-limited but the cache prevents repeated calls. Only triggered when no search data exists.

### Priority 3: DEFER -- Merchant API Price Competitiveness

**What:** Fetch `benchmark_price` from Merchant API and store for SKU prioritization.

**Why defer:**
1. Not useful for content generation (no price claims in titles/descriptions)
2. Existing competitor scraping already provides competitive landscape context
3. Would require new integration code + schema + sync jobs
4. SKU prioritization currently works well via performance baselines + tier scoring

**When to revisit:** When building a dedicated pricing/merchandising dashboard, or when competitive positioning becomes a key prioritization signal.
**Engineering Cost:** ~1-2 days (new integration, table, sync job, dashboard UI).
**Risk:** LOW technically, but adds operational complexity for marginal benefit.

### Priority 4: DEFER -- Variant-Level Search Query Evidence

**What:** `fetch_search_queries_for_variant()` exists but is not called during evidence assembly. Could improve finish-specific descriptions.

**Why defer:** Master-level queries already capture the dominant intent. Finish-specific queries are lower volume and the finish injection system handles variant differentiation through product attributes rather than search data.

**Engineering Cost:** ~1 hour.
**Risk:** Very low.

---

## 4. Database Tables Status Summary

| Table | Has Data | Used in Generation | Notes |
|---|---|---|---|
| `keyword_metrics` | YES (cached) | YES (via search query enrichment) | 30-day TTL, auto-refreshed |
| `search_queries` | YES | YES (via `search_queries_by_master_sku`) | Variant-level data |
| `search_queries_by_master_sku` | YES | YES (direct evidence source) | Aggregated from search_queries |
| `keyword_coverage_master` | Schema exists | NOT VERIFIED | May be populated by keyword_gaps |
| `keyword_coverage_variant` | Schema exists | NOT VERIFIED | May be populated by keyword_gaps |
| `finish_search_patterns` | Schema exists | NOT VERIFIED | May be populated by search sync |
| `competitor_listings` | YES | YES (via competitor_evidence) | Apify-sourced |
| `competitor_patterns` | YES | YES (via competitor_evidence) | Aggregated from listings |
| `competitor_scrape_jobs` | YES | N/A (job tracking) | Apify run tracking |

---

## 5. Key Finding: Signal Chain is Already Strong

The generation pipeline already consumes:

1. **Product evidence** (catalog attributes, dimensions, finishes) -- `evidence.py`
2. **Search query signals** (real Google Ads search terms + KP volume) -- `search_query_insights.py`
3. **Keyword gap detection** (high-volume queries missing from title) -- `keyword_gaps.py`
4. **Competitor language patterns** (SERP + marketplace title structures) -- `competitor_evidence.py`
5. **External keyword bank** (category-level keyword research) -- `keyword_bank.py`
6. **On-the-fly enrichment** (design context, functional features, competitive positioning) -- `enrichment.py`

This represents a comprehensive signal stack. The marginal improvement from adding more signals is likely small compared to improving prompt quality and generation model selection.
