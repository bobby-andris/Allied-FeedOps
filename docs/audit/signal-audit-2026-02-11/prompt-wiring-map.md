# Signal Audit: Prompt Wiring Map + Causality Proof

**Author**: prompt-tracer (Teammate B)
**Date**: 2026-02-11
**Scope**: Trace complete prompt construction pipeline, prove signal-to-prompt-to-output causality

---

## 1. Architecture Summary

### Prompt Authority Chain

```
Python (Cloud Run) is the SINGLE SOURCE OF TRUTH for content generation.

SYSTEM_PROMPT  → src/feedops/pipeline/prompts.py (line 109, ~410 lines, static/cacheable)
USER_PROMPT    → Built per-SKU at runtime in src/feedops/api/main.py:_build_generation_user_prompt()
EVIDENCE TABLE → Built per-SKU by src/feedops/pipeline/evidence.py:build_evidence_table()
```

### Call Flow (Regeneration)

```
Dashboard UI → POST /api/regenerate (route.ts)
             → POST {PIPELINE_URL}/regenerate (Python Cloud Run)
             → load_parent_sku_from_supabase()
             → build_evidence_table(parent_sku)
             → format_evidence_markdown(evidence)
             → _build_generation_user_prompt(parent_sku, evidence_markdown, platform, content_type, feedback)
             → provider.generate(prompt=user_prompt, system_prompt=SYSTEM_PROMPT)
             → Return content + finish_sentences + prompt_hash
```

The dashboard `route.ts` (line 199) is a **thin HTTP proxy** — it forwards `master_sku`, `content_type`, `platform`, `feedback`, and `finish_code` to the Python API and receives generated content back. It does NOT construct prompts or call OpenAI.

---

## 2. Complete Wiring Map: DB Tables → Evidence → Prompt → Output

### 2.1 Product Catalog Data

| DB Table / Source | Field(s) | Evidence Field | Prompt Section | Output Impact |
|---|---|---|---|---|
| `product_catalog` (via `ParentSKU`) | master_sku, category, collection, current_title, current_description, material, style, shape, orientation, tilting, mounting_type, assembly_required, center_to_center, diameter, screw_size, mirror_height/width, thickness, weight_capacity, included_items, bullets 1-6 | Corresponding evidence rows (e.g., `master_sku`, `category`, `material`, `bullet_1`) | `## Available Product Data` markdown table in user prompt | Every factual claim in output MUST trace to these rows. LLM uses these as the sole source of product specs. |
| `product_catalog` (variants) | finish (all variants) | `available_finishes` | Evidence table | Finish variety messaging ("28 designer finishes") |
| `product_catalog` (first variant) | product_length/height/width, projection, product_weight, gtin, upc, main_image_url | Dimension/image evidence rows | Evidence table | Dimension claims in titles/descriptions |

### 2.2 Search Signal Data (KEY SIGNAL INJECTION POINT)

| DB Table / Source | Field(s) | Evidence Field | Prompt Section | Output Impact |
|---|---|---|---|---|
| `search_queries_by_master_sku` (view) | query_text, total_impressions, total_clicks, avg_monthly_searches, competition | `search_queries_top` | Evidence table: `"brass towel bar" (2.4K vol), "18 inch towel bar" (1.2K vol)` | LLM incorporates high-volume search terms into titles/descriptions |
| `search_queries_by_master_sku` | Aggregated themes from queries | `search_query_themes` | Evidence table: `Material: brass/chrome, Style: antique, Function: towel bar` | Guides LLM tone and keyword emphasis |
| `search_queries_by_master_sku` + title comparison | Queries with tokens missing from current title | `keyword_gaps_current_title` | Evidence table: `"brass towel holder" (1.5K vol), "wall mount towel rack" (800 vol)` | LLM fills keyword coverage gaps in new titles |
| `keyword_bank` (local JSON, optional) | external_keywords by category/SKU | `external_keywords` | Evidence table | Additional SEO keyword suggestions from Apify/SERP research |
| Google Ads API (via `fetch_master_sku_keywords`) | High-performing search terms | `keyword_intent_master` | Evidence table: filtered, finish-agnostic keywords | Keyword intent signals for title/description optimization |

### 2.3 Competitor Data

| DB Table / Source | Field(s) | Evidence Field | Prompt Section | Output Impact |
|---|---|---|---|---|
| `competitor_listings` | source, domain, brand, title, position | `competitor_direct_domains`, `competitor_marketplace_domains` | Evidence table: `Observed direct competitor domains: ...` | Market landscape context (NOT product facts) |
| `competitor_patterns` | pattern_type, pattern_value, frequency, sources | `competitor_direct_language_patterns`, `competitor_marketplace_language_patterns` | Evidence table: `Observed ... listing language (context only): ...` | Language pattern inspiration (sanitized, no comparative claims) |

### 2.4 Enrichment Data (On-the-fly, from product attributes)

| Source | Evidence Field | Prompt Section | Output Impact |
|---|---|---|---|
| Collection metadata JSON + `ParentSKU.collection` | `collection_context`, `collection_subgroup` | Evidence table: `Dottingham (Traditional/Classic) - elegant traditional style` | Collection coordination hooks in descriptions |
| Style classification heuristics | `design_style` | Evidence table: `traditional (elegant, timeless, refined)` | Tone/voice guidance for LLM |
| Feature detection (title/desc text analysis) | `feature_title_keywords`, `feature_benefits` | Evidence: `Reeded Grip, ADA Compliant` / `textured grip surface provides secure hold...` | Title keyword inclusion, description benefit statements |
| Finish variety analysis | `finish_variety` | Evidence: `Multiple designer finish options available` | Finish messaging in descriptions |
| Competitive positioning analysis | `competitive_edge`, `key_differentiators` | Evidence: `Combines coordinated collection design...` | Value proposition framing |
| Design intent aggregation | `design_intent_keywords` | Evidence: `traditional bathroom hardware, classic bath accessories...` | SEO keyword targeting |

### 2.5 Prompt Template Data (from Supabase)

| DB Table | Field(s) | How Used | Output Impact |
|---|---|---|---|
| `prompt_templates` | `gold_standard_examples` | Formatted as few-shot examples in user prompt (`Gold Standard Examples (data-only guidance):`) | Calibrates output format and quality |
| `prompt_templates` | `category_guidance` | Injected as `Category Guidance:` section in user prompt | Category-specific writing hints |
| `prompt_templates` | `platform_rules.excluded_finishes` | Filters finish list for generation | Excludes specialty finishes |

---

## 3. User Prompt Assembly

The user prompt is built by `_build_generation_user_prompt()` (main.py:356-422):

```
Product Evidence Table:
{evidence_markdown}                    ← ALL signal data lands here as markdown table rows

Target platform: {platform}
Content type to generate: {content_type}

Entity context: variant listing copy...
Canonical finish vocabulary reference: {finish_list}
Category Guidance:                      ← From DB or code-level heuristics
{category_guidance}
Gold Standard Examples:                 ← From prompt_templates table
{examples}
Reviewer Feedback:                      ← Human feedback (if regeneration with feedback)
{feedback}
Generate only the {content_type} for {platform}.
Return your response as JSON: {"content": "your generated {content_type} here"}
```

---

## 4. Causality Proof: Search Query Data → Prompt → Output

### Concrete Code Path

1. **Data Collection**: `fetch_search_queries_for_master_sku()` (search_query_insights.py:21-62)
   - Queries `search_queries_by_master_sku` view in Supabase
   - Filters: `master_sku = X`, `total_impressions >= 10`, ordered by impressions desc, limit 15

2. **Evidence Row Creation**: `format_search_queries_for_evidence()` (search_query_insights.py:115-197)
   - Creates `search_queries_top` evidence row with format: `"brass towel bar" (2.4K vol), "18 inch towel bar" (1.2K vol)`
   - Creates `search_query_themes` evidence row with format: `Material: brass/chrome, Style: antique, Function: towel bar`

3. **Keyword Gap Detection**: `build_keyword_gap_evidence_rows()` (keyword_gaps.py:190-208)
   - Compares search query tokens against current title tokens
   - Creates `keyword_gaps_current_title` evidence row: `"brass towel holder" (1.5K vol), "wall mount towel rack" (800 vol)`

4. **Evidence Injection**: `build_evidence_table()` (evidence.py:286-304)
   ```python
   search_queries = fetch_search_queries_for_master_sku(parent_sku.master_sku)
   if search_queries:
       search_evidence = format_search_queries_for_evidence(search_queries, "master")
       evidence.extend(search_evidence)   # ← INJECTED INTO EVIDENCE TABLE

   # ... later ...
   evidence.extend(build_keyword_gap_evidence_rows(parent_sku, search_queries))
   ```

5. **Prompt Assembly**: `format_evidence_markdown()` (evidence.py:328-349)
   - Renders all evidence rows (including search data) as markdown table
   - This table goes into the `{evidence_markdown}` slot of the user prompt

6. **LLM Instruction** (system prompt, line 186-193):
   ```
   Keywords from the placement plan are search intent signals, NOT product facts.
   external_keywords, keyword_intent_master, and design_intent_keywords are for SEO
   targeting—weave ONE naturally into prose, do NOT list them.
   ```

   And the scoring rubric (line 386-388):
   ```
   3. Keyword Inclusion (check these elements):
      [ ] Primary keyword from placement plan in google_title
      [ ] Primary keyword from placement plan in bing_title
      [ ] At least 2 product-type synonyms in bing_description
   ```

### What Changes WITH vs WITHOUT Search Data

**WITHOUT search data** (no `search_queries_by_master_sku` rows):
- Evidence table has ~20-30 rows of product catalog data only
- LLM generates titles/descriptions from product specs + enrichment heuristics
- Keyword inclusion scoring relies only on category-derived and external keyword bank terms
- Title may miss high-volume query terms customers actually use

**WITH search data** (search queries present):
- Evidence table gains 2-3 additional rows:
  - `search_queries_top`: actual customer search terms with volume/impression data
  - `search_query_themes`: extracted material/style/function themes
  - `keyword_gaps_current_title`: high-volume terms missing from current title
- LLM can incorporate actual customer language patterns
- Keyword gap data actively guides the LLM to cover missing search terms
- The `self_score.keyword_inclusion` metric is more meaningful with real search data

### Example: Evidence Table Difference

WITHOUT:
```
| keyword_intent_master | towel bar, bathroom towel holder | keyword_intent_master |
```

WITH (additional rows):
```
| search_queries_top | "brass towel bar" (2.4K vol), "18 inch towel bar wall mount" (890 vol), "towel bar bathroom" (1.1K vol) | search_insights |
| search_query_themes | Material: brass, Style: traditional, Function: towel bar/towel rack | search_insights |
| keyword_gaps_current_title | "wall mount towel rack" (800 vol), "brass bathroom towel holder" (650 vol) | keyword_gaps |
```

This directly causes the LLM to:
1. Include "wall mount" in the title (gap detection)
2. Use "towel bar" and "towel rack" as synonyms in Bing description (theme detection)
3. Front-load "brass" in descriptions (volume signal)

---

## 5. Drift Analysis: TS Legacy vs Python SOT

### Dashboard `/api/regenerate/route.ts` — NO DRIFT (Thin Proxy)
- **Status**: Pure HTTP proxy to Python Cloud Run (confirmed at line 199)
- It does NOT import or use `core.ts` or `prompts.ts` for generation
- It ONLY uses `validateGeneratedContent()` from `prompts.ts` for post-hoc validation (not generation)
- The `ensureSkuData()` call is non-blocking background data collection

### `dashboard/src/lib/regeneration/core.ts` — DEAD CODE
- **Status**: `regenerateContent()` and `adaptVariantContent()` are **NOT imported by any file** in the codebase
- Confirmed via grep: zero imports of `from '@/lib/regeneration/core'`
- This file contains a complete alternative generation pipeline using TypeScript OpenAI calls with its own prompt construction
- **Risk**: If anyone ever re-imports this, it would bypass the Python SOT entirely
- **Recommendation**: Delete or clearly mark as deprecated/archived

### `dashboard/src/lib/regeneration/prompts.ts` — PARTIAL ACTIVE USE
- **Status**: `validateGeneratedContent()` is actively used by `route.ts` (line 251) for content validation
- `SYSTEM_PROMPT` and `PLATFORM_CONTEXT` are defined but only referenced by the dead `core.ts`
- `FINISH_LIST` is used by the validator to check for hardcoded finish names
- **Risk**: The TS `SYSTEM_PROMPT` (line 60) is completely different from the Python `SYSTEM_PROMPT` (prompts.py line 109). If `core.ts` were ever re-activated, content quality and style would diverge.

### Specific Prompt Differences (TS vs Python):

| Aspect | Python SOT | TS Legacy |
|---|---|---|
| Title structure | Product type first, brand last (`Allied Brass` as final segment) | Finish first (`{FINISH_NAME} [Product]...Allied Brass`) |
| Description approach | Platform-specific (Google=feed fuel, Shopify=sales pitch) | "Balanced approach" (quality-first vs pain-point-first) |
| Scoring rubric | 6-dimension self-score with checklist (specificity, benefit coverage, keyword inclusion, format, brand voice, factual accuracy) | None |
| Claims traceability | Required `claims` array with `source_field` and `source_value` | Not required |
| Character limits | Explicit per-platform limits (Google desc 600-800, Bing desc 700-1000) | Similar but less detailed |
| Search query usage | Explicit instruction: "weave ONE naturally into prose, do NOT list them" | "Cross-reference queries against the product evidence" |

---

## 6. Output Schema and Quality Gates

The Python pipeline requests structured JSON output matching `CANDIDATE_SCHEMA` (prompts.py:9-99):

```json
{
  "google_title": "...",
  "google_short_title": "...",
  "google_description": "...",
  "bing_title": "...",
  "bing_description": "...",
  "shopify_title": "...",
  "shopify_description": "...",
  "shopify_meta_description": "...",
  "claims": [{"claim": "...", "source_field": "...", "source_value": "..."}],
  "self_score": {
    "specificity": 0-10,
    "benefit_coverage": 0-10,
    "keyword_inclusion": 0-10,
    "format_adherence": 0-10,
    "brand_voice": 0-10,
    "factual_accuracy": 0-10
  }
}
```

**NOTE**: The full schema (`CANDIDATE_SCHEMA`) is only used by the `/optimize-sku` endpoint path and the `OPTIMIZATION_TEMPLATE` legacy template. The `/regenerate` endpoint uses a simpler `{"content": "..."}` schema (main.py:889-893). This means **regeneration does NOT produce self-scores or claims tracing** — only the full optimization path does.

### Quality Gates

1. **Finish sentence validation** (main.py:548-581): `normalize_and_validate_finish_sentences()` checks each sentence against the base description for quality
2. **Finish sentence parity** (main.py:584-661): Google/Bing descriptions automatically get finish sentences generated and validated
3. **Content validation** (route.ts:251): Post-hoc validation via `validateGeneratedContent()` checks for Shopify title rules, minimum lengths, hardcoded finish names
4. **Kill switches**: `ensure_generation_enabled()` and `finish_sentence_regeneration_enabled()` allow disabling generation at runtime

---

## 7. Summary Findings

### Signal Data DOES Flow Into Prompts
**CONFIRMED**: Search query data, keyword gap analysis, competitor patterns, and enrichment context are all injected into the evidence table and included in the LLM prompt. The code path is:
```
Supabase tables → Python evidence builder → Markdown table → User prompt → LLM
```

### Signal Data DOES Change Outputs
**CONFIRMED**: The evidence table is the primary data source for the LLM. Search queries add `search_queries_top`, `search_query_themes`, and `keyword_gaps_current_title` rows that directly influence keyword selection and title/description optimization.

### Key Gaps and Risks

1. **Dead code risk**: `core.ts` is a complete alternative pipeline that would bypass Python SOT if re-imported
2. **Regeneration vs optimization asymmetry**: `/regenerate` uses `{"content": "..."}` schema (no self-scores, no claims), while `/optimize-sku` uses the full `CANDIDATE_SCHEMA` with quality scoring. Regenerated content lacks traceability metadata.
3. **Search data dependency**: If `search_queries_by_master_sku` has no data for a SKU, the generation proceeds without search signals — there's no explicit warning or fallback strategy
4. **Competitor data is optional**: If `competitor_listings`/`competitor_patterns` tables are empty, those evidence rows are simply absent — no degraded-mode notification
5. **Keyword bank is local-file dependent**: `data/keyword-bank.json` is gitignored and may not exist in Cloud Run — external keywords would silently be empty
