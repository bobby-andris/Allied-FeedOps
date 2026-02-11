# Signal Reality & Sufficiency Audit

**Date**: 2026-02-11
**Branch**: `signal-audit`
**Scope**: Do keyword/search/competitive signals actually flow into prompts and measurably change generated content?

---

## TL;DR

| Question | Answer |
|----------|--------|
| Do signals flow into prompts? | **YES** — search queries, keyword gaps, competitor patterns, and enrichment data are injected as evidence rows into the LLM prompt |
| Do signals change outputs? | **YES** — evidence rows add `search_queries_top`, `search_query_themes`, `keyword_gaps_current_title` that directly influence keyword selection |
| Is the data sufficient? | **For 84 high-history SKUs: YES (with caveats). For 2,700 cold-start SKUs: NO** |
| Is Keyword Planner implemented? | **YES** — fully deployed, cached, wired into generation |
| Is Merchant competitive data implemented? | **NO** — and should be deferred (not useful for content generation) |
| Is post-publish tracking working? | **NO** — `performance_snapshots` has 1 row, `search_query_snapshots` has 0 rows |

---

## 1. Database / Source Inventory

### Universe

- **2,784** distinct master_skus in `variant_index` (72,023 variant rows)
- **2,892** master_skus in `product_catalog` (75,770 variant rows)
- **32** product categories
- **92** SKUs have any generated content; **3** have approved+published content

### Source-by-Source Summary

| Source | Coverage | Freshness | Join Key | Status |
|--------|----------|-----------|----------|--------|
| `product_catalog` | 100% (2,892 SKUs) | Static (on catalog change) | `master_sku` | SUFFICIENT |
| `search_queries` / `_by_master_sku` | 3.0% (84 SKUs) | 7-day stale threshold | `master_sku`, `gmc_offer_id` | SUFFICIENT for 84 SKUs only |
| `keyword_metrics` (KP cache) | 714 keywords | 30-day TTL | `keyword` text | Enrichment only, not independent |
| `performance_baselines` | 2.7% (76 SKUs) | 60-day stale threshold | `(master_sku, platform)` | SUFFICIENT for measured SKUs |
| `performance_snapshots` | ~0% (1 row) | **NOT ACTIVE** | `(master_sku, platform)` | **NON-FUNCTIONAL** |
| `search_query_snapshots` | 0% (0 rows) | **NOT ACTIVE** | — | **NON-FUNCTIONAL** |
| `competitor_listings` / `_patterns` | 6.3% (2 of 32 categories) | One-off (2026-02-05) | `product_category` | Proof-of-concept only |
| `keyword_coverage_master` | 0% (0 rows) | Never populated | — | **DEAD TABLE** |
| `keyword_coverage_variant` | 0% (0 rows) | Never populated | — | **DEAD TABLE** |
| `finish_search_patterns` | 0% (0 rows) | Never populated | — | **DEAD TABLE** |
| `prompt_templates` (gold examples) | 1 template, **10 examples** | Active (generator.py) | — | **POPULATED** — 10 cross-category few-shot examples actively injected into every generation prompt |

### Cross-Signal Overlap

| Signal Combination | SKU Count |
|-------------------|-----------|
| Search queries + Performance baselines | 15 |
| Search queries only | 69 |
| Baselines only | 61 |
| Neither | ~2,639 (94.8%) |

Only **15 SKUs** have both search query data AND performance baselines — the richest signal combination.

### Bias/Limitations

1. **Circular query bias**: Search queries reflect what Google Ads shows for CURRENT titles. Better terms won't appear until content changes.
2. **Ad spend dependency**: Only SKUs in active Shopping campaigns have search query data.
3. **1,000-row fetch limit**: May miss long-tail queries for large catalogs.
4. **Competitor sparsity**: 15 listings across 2 categories is insufficient for real pattern extraction.

---

## 2. Sufficiency Verdicts

### High-History SKUs (84 SKUs with search query data)

**VERDICT: DATA SUFFICIENT (with caveats)**

These SKUs have product catalog (100%), search terms with KP enrichment (71.4% enriched), and some have performance baselines. The generation pipeline uses all of this.

**Caveats**:
- Post-publish tracking is non-functional (can't measure if signals improved outcomes)
- Only 2/32 categories have competitor data

### Cold-Start SKUs (2,700 SKUs with no search query data)

**VERDICT: DATA NOT SUFFICIENT for data-driven generation**

These SKUs get only product catalog + on-the-fly enrichment heuristics. No search terms, no keyword gaps, no competitor context (for 30/32 categories).

**What's missing for cold start**:

1. **Functional Sub-Type (FST) keyword propagation**: No mechanism to inherit search patterns from high-data sibling SKUs with the same functional product type. Category-level grouping would be harmful — e.g., "Glass Shelves" contains 10 distinct sub-types (corner, double, triple, +towel bar, +gallery rail, etc.) with different search intents. FST clustering is needed instead.
2. **Proactive KP seeding**: `GenerateKeywordIdeas` (Google Ads Keyword Planner API) exists as API endpoint but is NOT invoked during generation for cold-start SKUs
3. **Competitor coverage**: 30/32 categories have zero competitor data
4. **Cross-SKU keyword inheritance at FST level**: ~60-80 functional sub-type clusters exist across the catalog; keywords should propagate within FST clusters, not across them
5. **GMC product health**: No cached Merchant Center `product_view` data for disapprovals/warnings
6. **Performance feedback loop**: Snapshots table empty — can't learn which titles actually perform well

**CORRECTION**: Gold standard examples ARE populated (10 examples across 10 categories) and actively wired into generation via `generator.py`. The initial audit incorrectly reported them as empty.

---

## 3. Prompt Wiring Map

### Architecture

```
Python (Cloud Run) is the SINGLE SOURCE OF TRUTH.

SYSTEM_PROMPT  → src/feedops/pipeline/prompts.py (line 109, ~410 lines)
USER_PROMPT    → Built per-SKU in src/feedops/api/main.py:_build_generation_user_prompt()
EVIDENCE TABLE → Built per-SKU by src/feedops/pipeline/evidence.py:build_evidence_table()
```

### Call Flow

```
Dashboard UI → POST /api/regenerate (route.ts, thin proxy)
             → POST {PIPELINE_URL}/regenerate (Python Cloud Run)
             → load_parent_sku_from_supabase()
             → build_evidence_table(parent_sku)
             → format_evidence_markdown(evidence)
             → _build_generation_user_prompt(parent_sku, evidence_md, platform, content_type, feedback)
             → provider.generate(prompt=user_prompt, system_prompt=SYSTEM_PROMPT)
             → Return content + finish_sentences + prompt_hash
```

### Complete Wiring: Tables → Evidence → Prompt → Output

| DB Source | Evidence Field | Prompt Section | Output Impact |
|-----------|---------------|----------------|---------------|
| `product_catalog` (ParentSKU) | `master_sku`, `category`, `material`, etc. | `## Available Product Data` table | Every factual claim traces here |
| `search_queries_by_master_sku` | `search_queries_top` | Evidence row: `"brass towel bar" (2.4K vol)` | LLM incorporates high-volume terms |
| `search_queries_by_master_sku` | `search_query_themes` | Evidence row: `Material: brass, Style: antique` | Guides tone and keyword emphasis |
| Search queries + title comparison | `keyword_gaps_current_title` | Evidence row: `"wall mount towel rack" (800 vol)` | LLM fills coverage gaps |
| `keyword_bank` (JSON, optional) | `external_keywords` | Evidence row | Additional SEO suggestions |
| Google Ads API | `keyword_intent_master` | Evidence row | Keyword intent signals |
| `competitor_listings` | `competitor_direct_domains` | Evidence row | Market landscape context |
| `competitor_patterns` | `competitor_direct_language_patterns` | Evidence row | Language pattern inspiration |
| Collection metadata | `collection_context` | Evidence row | Collection coordination hooks |
| Style heuristics | `design_style` | Evidence row | Tone/voice guidance |
| Feature detection | `feature_title_keywords` | Evidence row | Title keyword inclusion |
| `prompt_templates` | `gold_standard_examples` | `Gold Standard Examples:` section | Few-shot calibration (currently empty) |
| `prompt_templates` | `category_guidance` | `Category Guidance:` section | Category-specific writing hints |

### Drift Analysis

| Component | Status | Risk |
|-----------|--------|------|
| `route.ts` (regeneration) | Pure HTTP proxy — NO DRIFT | None |
| `core.ts` (legacy TS pipeline) | **DEAD CODE** — zero imports in codebase | Medium (if re-imported, bypasses Python SOT) |
| `prompts.ts` (legacy TS prompts) | Partially active — `validateGeneratedContent()` used | Low (validation only, not generation) |
| TS `SYSTEM_PROMPT` vs Python `SYSTEM_PROMPT` | **Completely different** | High if `core.ts` reactivated |

### Regeneration vs Optimization Asymmetry

- `/optimize-sku` uses full `CANDIDATE_SCHEMA` with `self_score` (6 dimensions) and `claims` tracing
- `/regenerate` uses simple `{"content": "..."}` schema — **no self-scores, no claims tracing**
- This means regenerated content lacks quality metadata

---

## 4. External Signals Assessment

### Keyword Planner: FULLY IMPLEMENTED

| Component | Status |
|-----------|--------|
| `KeywordPlannerClient` class | Production (google_ads_search_terms.py:86-321) |
| `get_historical_metrics()` | Deployed, returns volume/competition/CPC |
| `generate_keyword_ideas()` | Deployed as API endpoint, NOT auto-invoked for cold-start |
| `keyword_metrics` cache (30-day TTL) | Operational |
| Cloud Run `/search-insights/sync` | Production (triggers fetch + KP enrichment) |
| Cloud Run `/search-insights/enrich` | Production (on-demand enrichment) |
| Cloud Run `/search-insights/keywords/ideas` | Production (manual endpoint) |
| `enrich_with_keyword_metrics()` | Production (enriches search_queries with KP data) |

**Gap**: `GenerateKeywordIdeas` could bootstrap cold-start SKUs but is not called during generation.

### Merchant API Competitive Metrics: NOT IMPLEMENTED

- Zero code for `price_competitiveness_product_view` or `benchmark_price`
- **Should be deferred** — benchmark pricing is useful for merchandising/pricing, not content generation
- Competitive intelligence is handled by Apify-based SERP scraping (implemented and wired)

### Ranked Recommendations

| Priority | Action | Impact | Cost | Risk |
|----------|--------|--------|------|------|
| 1 | **No action** — Keyword Planner + Gold Examples already complete | Already providing signals + few-shot calibration | $0 | None |
| 2 | Wire `GenerateKeywordIdeas` (KP API) for cold-start in `evidence.py` using FST-derived seed keywords | Moderate — improves first-gen quality for new SKUs | ~2 hours | Low (rate-limited but cached) |
| 3 | Build Functional Sub-Type (FST) clustering for keyword propagation | High — enables keyword sharing within ~60-80 product type clusters without harmful generalization | ~6 hours | Low |
| 4 | Expand competitor scraping to all 32 categories | Moderate — provides language patterns for cold-start | ~4 hours | Low |
| 5 | Activate performance snapshot collection (Cloud Scheduler) | High — enables feedback loop | ~1 hour | Low |
| 6 | Merchant API price competitiveness | Low (for content gen) | ~1-2 days | Low |

---

## 5. Causality Proof

### Code Path Confirmed

1. `fetch_search_queries_for_master_sku()` → queries `search_queries_by_master_sku` view
2. `format_search_queries_for_evidence()` → creates `search_queries_top` and `search_query_themes` evidence rows
3. `build_keyword_gap_evidence_rows()` → creates `keyword_gaps_current_title` row
4. `build_evidence_table()` → assembles all evidence rows into list
5. `format_evidence_markdown()` → renders as markdown table
6. `_build_generation_user_prompt()` → injects evidence markdown into user prompt
7. LLM receives evidence and is instructed: "weave ONE [keyword] naturally into prose, do NOT list them"
8. Scoring rubric checks: "Primary keyword from placement plan in google_title"

### WITH vs WITHOUT Search Data

**WITHOUT** (cold-start):
- Evidence table has ~20-30 rows of product catalog + enrichment only
- LLM generates from specs and heuristics
- Generic titles like "Brass Towel Bar by Allied Brass"

**WITH** (search data present, additional rows):
```
| search_queries_top | "brass towel bar" (2.4K vol), "18 inch towel bar wall mount" (890 vol) | search_insights |
| search_query_themes | Material: brass, Style: traditional, Function: towel bar/rack | search_insights |
| keyword_gaps_current_title | "wall mount towel rack" (800 vol), "brass bathroom towel holder" (650 vol) | keyword_gaps |
```

This causes the LLM to:
1. Include "wall mount" in title (gap detection)
2. Use "towel bar" and "towel rack" as synonyms in Bing description (theme detection)
3. Front-load "brass" in descriptions (volume signal)

---

## 6. Critical Risks

1. **Dead code timebomb**: `dashboard/src/lib/regeneration/core.ts` is a complete alternative pipeline. If re-imported, it bypasses Python SOT with completely different prompts. **Recommendation**: Delete or rename to `.deprecated.ts`.

2. **Silent signal dropout**: If search queries, competitor data, or keyword bank return empty, generation proceeds without warning. No log, no flag, no degraded-mode indicator. The output looks identical — you can't tell if it used signals or not.

3. **Keyword bank deployment gap**: `data/keyword-bank.json` is gitignored and may not exist on Cloud Run. External keywords would silently be empty.

4. **Post-publish tracking non-functional**: Cannot measure if signal-enriched content actually performs better. The feedback loop is broken.

5. **Search data coverage scales with generation**: Only SKUs that have been generated/optimized get search data pulled from Google Ads. The 84 SKUs with data = the SKUs processed so far. Coverage will grow as more SKUs are generated. For truly cold-start SKUs (new products, no ad history), FST-based KP seeding is the recommended solution.
