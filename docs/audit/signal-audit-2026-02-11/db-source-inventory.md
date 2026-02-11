# Signal & Data Source Inventory Audit

**Auditor**: db-auditor (Teammate A)
**Date**: 2026-02-11
**Universe**: 2,784 distinct master_skus in `variant_index` (72,023 variant rows); 2,892 master_skus in `product_catalog` (75,770 variant rows); 32 product categories

---

## 1. Source-by-Source Inventory

### 1.1 Product Catalog (`product_catalog`)

| Metric | Value |
|--------|-------|
| Distinct master_skus | 2,892 |
| Total variant rows | 75,770 |
| With narrative_copy | 75,770 (100%) |
| With material | 75,770 (100%) |
| With style | 75,770 (100%) |
| With dimensions | 75,770 (100%) |

**Coverage**: **100% of SKUs**. Every row has narrative copy, material, style, and dimensional data populated.

**Join keys**: `master_sku`, `option_sku` (joins to `variant_index`)

**Freshness**: Static catalog data. Updated when products change (not on a schedule).

**Bias/limitations**: None significant. This is the foundation signal. Narrative copy is manufacturer-authored and can be generic/repetitive across similar products, but contains verifiable specs.

**Verdict**: SUFFICIENT for all SKUs. This is the bedrock evidence source.

---

### 1.2 Google Ads Search Queries (`search_queries` / `search_queries_by_master_sku`)

| Metric | Value |
|--------|-------|
| SKUs with search query data | **84** (3.0% of 2,784) |
| Total query rows (variant-level) | 1,950 |
| Aggregated master-SKU rows | 894 (84 SKUs) |
| Enriched with Keyword Planner | 1,532 of 2,147 total (71.4%) |
| Data period | 2026-01-06 to 2026-02-07 |
| Last sync | 2026-02-07 |

**Coverage**: **3.0% of SKUs** have search query data. Only 84 master_skus out of 2,784.

**Freshness/TTL**: Sync triggered on-demand via `ensureSearchQueryData()` when data is >7 days stale. Last successful sync job fetched 1,000 queries on 2026-02-07. No automated cron/scheduler -- relies on user-triggered workflows (SKU selection, regeneration).

**Join keys**: `master_sku` (denormalized), `gmc_offer_id` (variant-level)

**Bias/limitations**:
- **Circular bias**: Search queries reflect what Google Ads is showing for the CURRENT feed titles. If the current title says "Brass Towel Bar 24 Inch", queries will skew toward those terms. New/better terms won't appear until content changes.
- **Only covers SKUs with active ad spend** -- products not in Shopping campaigns have zero query data.
- **1,000-row fetch limit per sync job**: May miss long-tail queries for large catalogs.
- **Multi-SKU products**: `item_ids` JSONB array handles this, but aggregation logic must account for shared product_ids.

**Verdict**: SUFFICIENT for the 84 high-history SKUs. **NOT SUFFICIENT for 97% of catalog** (cold start).

---

### 1.3 Keyword Planner Cache (`keyword_metrics`)

| Metric | Value |
|--------|-------|
| Total cached keywords | 714 |
| With volume data | 714 (100%) |
| With competition data | 714 (100%) |
| Data period | 2026-02-06 to 2026-02-07 |

**Coverage**: 714 unique keywords cached. These correspond to the search queries fetched for the 84 SKUs that have query data.

**Freshness/TTL**: 30-day TTL per keyword. Only updated monthly (Google Ads Keyword Planner data is monthly).

**Join keys**: `keyword` text (joins to `search_queries.query_text`)

**Bias/limitations**:
- Only contains keywords that were discovered through search query sync. No proactive keyword research for categories without ad history.
- Rate-limited API -- can't bulk-query thousands of keywords at once.

**Verdict**: Useful enrichment layer but **NOT an independent signal source**. Only enriches existing search queries. Cannot bootstrap cold-start SKUs.

---

### 1.4 Keyword Coverage Tables (`keyword_coverage_master`, `keyword_coverage_variant`, `finish_search_patterns`)

| Table | Rows |
|-------|------|
| keyword_coverage_master | **0** |
| keyword_coverage_variant | **0** |
| finish_search_patterns | **0** |

**Coverage**: **ZERO**. All three tables are empty.

**Assessment**: Schema exists but these tables have never been populated. The code to compute keyword coverage gaps exists (`keyword_gaps.py`) but writes evidence rows inline rather than persisting to these tables.

**Verdict**: NOT POPULATED. Dead tables. The keyword gap logic runs at generation-time but results are ephemeral (not stored).

---

### 1.5 Performance Baselines (`performance_baselines`)

| Metric | Value |
|--------|-------|
| SKUs with baselines | **76** (2.7% of 2,784) |
| Total rows | 168 (multiple platforms per SKU) |
| Data period | 2026-02-03 to 2026-02-11 |

**Coverage**: **2.7% of SKUs**. 76 master_skus have pre-optimization baseline metrics.

**Freshness/TTL**: Auto-captured by `ensureBaselineData()` when a SKU is selected for optimization. 60-day stale threshold triggers re-capture. No scheduled collection.

**Join keys**: `(master_sku, platform)` composite PK

**Bias/limitations**:
- Only captured for SKUs that have been touched by the optimization pipeline.
- Measures current state -- if products have seasonal patterns, a single 30-day window may not be representative.

**Verdict**: SUFFICIENT for measuring delta on optimized SKUs. **NOT AVAILABLE for cold-start.**

---

### 1.6 Performance Snapshots (`performance_snapshots`)

| Metric | Value |
|--------|-------|
| SKUs with snapshots | **1** |
| Total rows | 1 |
| Snapshot date | 2025-12-31 |

**Coverage**: **Effectively zero**. Only 1 SKU has a single snapshot from 2025-12-31.

**Freshness**: Last fetched 2026-02-03. No automated collection schedule (no Cloud Scheduler configured).

**Verdict**: **NOT FUNCTIONAL**. The snapshot capture endpoint exists but is not being called regularly. Post-publish delta tracking is non-operational.

---

### 1.7 Search Query Snapshots (`search_query_snapshots`)

| Metric | Value |
|--------|-------|
| Total rows | **0** |

**Coverage**: **ZERO**. Table is empty.

**Verdict**: **NOT FUNCTIONAL**. Schema exists but no data has ever been captured. Post-publish search query delta tracking is non-operational.

---

### 1.8 Competitor Intelligence (`competitor_listings`, `competitor_patterns`, `competitor_scrape_jobs`)

| Metric | Value |
|--------|-------|
| Categories with competitor data | **2 of 32** (6.3%) |
| Categories covered | "towel bars", "toilet paper holders" |
| Total listings | 15 |
| Unique competitor domains | 10 |
| Pattern types | 5 (across 1 category, 8 patterns total) |
| Last scrape | 2026-02-05 |

**Coverage**: **6.3% of categories**. Only 2 categories have any competitor data, with a total of just 15 listings. This is pilot-level data from 3 Apify scrape jobs.

**Freshness**: One-off scrapes run 2026-02-04 to 2026-02-05. No scheduled collection.

**Join keys**: `product_category` (text match to `product_catalog.category`)

**Bias/limitations**:
- Extremely sparse. 15 listings across 2 categories is insufficient for pattern extraction.
- Competitor patterns table has only 8 entries in 1 category.
- No per-SKU competitor mapping -- category-level only.

**Verdict**: **NOT SUFFICIENT** for any meaningful competitive intelligence signal. Proof-of-concept only.

---

### 1.9 Prompt Templates (`prompt_templates`)

| Metric | Value |
|--------|-------|
| Active templates | 1 ("content-generation-v2") |
| Gold standard examples | **0** |
| Has category guidance | Yes |
| Has platform rules | Yes |

**Coverage**: One active template with category guidance and platform rules, but **ZERO gold standard examples**.

**Verdict**: Template infrastructure exists but **gold standard examples are empty**. The generation pipeline cannot use few-shot learning from high-performing examples.

---

### 1.10 Generated Content (`generated_content`)

| Metric | Value |
|--------|-------|
| SKUs with any content | 92 |
| Total rows | 496 |
| With candidate content | 440 |
| With approved content | 14 (3 SKUs) |

**Assessment**: 92 SKUs have been through generation. Only 3 SKUs have fully approved content. This is early-stage.

---

### 1.11 Publish Events (`publish_events`)

| Metric | Value |
|--------|-------|
| Published SKUs | 3 |
| Total events | 29 (25 successful) |
| Date range | 2026-02-03 to 2026-02-08 |

**Assessment**: Only 3 SKUs have been published. System is in early production.

---

### 1.12 Regeneration History (`regeneration_history`)

| Metric | Value |
|--------|-------|
| Total regenerations | 194 |
| SKUs regenerated | 28 |
| With user feedback | 9 |

**Assessment**: 28 SKUs have been iterated on. Only 9 regenerations included user feedback text. This could become a learning signal in future but is too sparse now.

---

### 1.13 Lifestyle Images (`product_lifestyle_images`, `variant_lifestyle_images`)

| Table | SKUs | Total | Approved |
|-------|------|-------|----------|
| Product-level | 8 | 16 | 3 |
| Variant-level | 18 | 50 | 3 |

**Assessment**: Lifestyle image generation is working but covers very few SKUs. Not directly relevant to text content generation signals.

---

### 1.14 Sync Jobs (`search_query_sync_jobs`)

| Metric | Value |
|--------|-------|
| Total jobs | 10 visible |
| Successful | 4 |
| Failed | 6 (5 due to missing google-ads.yaml config) |
| Last successful | 2026-02-07 |

**Assessment**: Sync infrastructure works but had config issues early on (missing yaml). After fixing, 4 successful syncs fetched 1,000 queries each with keyword enrichment.

---

## 2. Evidence Pipeline Architecture

The Python evidence builder (`src/feedops/pipeline/evidence.py`) assembles these signals at generation time:

1. **Product catalog fields** (ParentSKU model): Always available, 100% coverage
2. **Google Ads keywords** (`fetch_master_sku_keywords`): From `search_queries` table
3. **External keywords** (`get_external_keywords`): From keyword bank (competitor research)
4. **Search query insights** (`fetch_search_queries_for_master_sku`): Actual customer search terms
5. **Keyword gap analysis** (`build_keyword_gap_evidence_rows`): High-volume terms missing from current title
6. **Competitor evidence** (`build_competitor_evidence`): Category language patterns
7. **On-the-fly enrichment** (`enrich_product`): Design context, functional features, competitive positioning

Signals 2-6 are **optional** -- the pipeline continues even if they return empty. For the 97% of SKUs without search/competitor data, the evidence table contains only #1 (product catalog) and #7 (enrichment heuristics).

---

## 3. Cross-Signal Overlap

| Signal combination | SKU count |
|-------------------|-----------|
| Search queries + Performance baselines | 15 |
| Search queries only (no baseline) | 69 |
| Baselines only (no search queries) | 61 |
| Neither search nor baseline | ~2,639 (94.8%) |

Only **15 SKUs** have both search query data AND performance baselines -- the richest signal combination.

---

## 4. Verdicts

### High-History SKUs (84 SKUs with search query data)

**Verdict: DATA SUFFICIENT (with caveats)**

These 84 SKUs have:
- Product catalog data (100%)
- Google Ads search terms with Keyword Planner enrichment (71.4% enrichment rate)
- Performance baselines (15 of 84 also have baselines)
- Competitor category intelligence (only for towel bars / toilet paper holders)

**Caveats**:
- Circular query bias: search terms reflect current feed, not ideal feed
- Only 2 of 32 categories have competitor data
- Gold standard examples are empty -- no few-shot learning
- Post-publish tracking (snapshots) is non-functional, so we can't measure if the "rich" data actually improved content

### Cold-Start SKUs (2,700 SKUs with no search query data)

**Verdict: DATA NOT SUFFICIENT for data-DRIVEN generation**

These SKUs have:
- Product catalog data (100%) -- specs, narrative, dimensions, bullets
- On-the-fly enrichment heuristics
- Nothing else

**What's missing for cold start**:
1. **Category-level keyword intelligence**: No mechanism to inherit search patterns from similar products in the same category. If "Towel Bars" has 666 SKUs but only ~20 have search data, the other ~646 get ZERO keyword signal.
2. **Competitor language patterns**: 30 of 32 categories have zero competitor data.
3. **Cross-SKU learning**: No way to propagate keyword insights from high-history SKUs to similar cold-start products.
4. **Keyword Planner seeding**: Could use category names + product attributes to proactively query Keyword Planner for cold-start SKUs, but this pipeline does not exist.
5. **GMC product status/issues**: No cached Merchant Center product_view data. Could reveal disapprovals, title truncation warnings, missing attributes.
6. **Gold standard examples**: Empty in prompt_templates. Even a handful of high-quality examples per category would significantly improve generation quality.
7. **Performance feedback loop**: Snapshots table is empty. Cannot learn which generated titles/descriptions actually perform well.

---

## 5. Data Freshness Summary

| Source | Last Updated | Auto-Refresh? | Schedule |
|--------|-------------|---------------|----------|
| product_catalog | Static (manual) | No | On catalog update |
| search_queries | 2026-02-07 | On-demand | 7-day stale threshold |
| keyword_metrics | 2026-02-07 | With search sync | 30-day TTL |
| performance_baselines | 2026-02-11 | On-demand | 60-day stale threshold |
| performance_snapshots | 2025-12-31 | **NOT ACTIVE** | No scheduler |
| search_query_snapshots | Never | **NOT ACTIVE** | No scheduler |
| competitor_listings | 2026-02-05 | **NOT ACTIVE** | No scheduler |
| keyword_coverage_* | Never populated | N/A | N/A |
| finish_search_patterns | Never populated | N/A | N/A |

---

## 6. Key Gaps and Recommendations (Summary)

1. **Category keyword propagation**: Build a pipeline that aggregates search queries at the category level and makes them available to cold-start SKUs in the same category.
2. **Proactive Keyword Planner seeding**: For categories with no search data, seed Keyword Planner queries using `{category} + {material} + {mounting_type}` combinations.
3. **Competitor scraping at scale**: Expand from 2 categories to all 32. Even 10-20 listings per category would provide category language signals.
4. **Populate gold standard examples**: Curate 3-5 high-quality examples per category in `prompt_templates.gold_standard_examples`.
5. **Activate performance snapshot collection**: Set up Cloud Scheduler to call `/api/performance/capture-snapshot` weekly.
6. **GMC product health caching**: Periodic sync of `product_view` data from Merchant API to surface disapprovals and attribute warnings.
7. **Cross-SKU keyword inheritance**: When generating for SKU X in "Towel Bars", include top keywords from ALL towel bar SKUs that have search data.
