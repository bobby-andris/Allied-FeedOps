# Prompt & Scoring System Audit — DRAFT

**Status**: Awaiting ads-researcher and cro-researcher findings before finalizing recommendations

**Auditor**: prompt-engineer agent
**Date**: 2026-02-09

---

## Executive Summary

This audit evaluates the content generation system's prompt, scoring algorithms, evidence pipeline, and gold standard examples to identify gaps between what we're optimizing for (quality metrics) and what drives revenue (clicks, conversions).

**Key Question**: Are we scoring for "good content" or "content that drives revenue"?

---

## 1. System Prompt Audit

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/regeneration/prompts.ts` (lines 60-137)

### Current Approach

The prompt uses a **balanced framework**:
- **Quality-First (DEFAULT)**: Standard products (towel bars, hooks, shelves) → Open with craftsmanship, materials, design
- **Pain-Point-First (SELECTIVE)**: Products with natural frustrations (grab bars, rollerless TP holders, space-saving combos) → Open with problem, then solution

### Strengths

1. **Authentic messaging**: "DO NOT manufacture drama where none exists. Authenticity matters." (line 90)
2. **Clear decision tree**: Specific examples of when to apply pain-point messaging vs quality-first
3. **Finish integration**: 28 product-specific finish sentences (excludes novelty finishes)
4. **Title structure**: Optimized for search relevance (finish-first, collection before brand)
5. **Guardrails**: No banned words, no invented specs, claims must trace to evidence

### Potential Issues

**WAITING FOR ADS-RESEARCHER DATA TO CONFIRM**:
- Does the "balanced approach" actually correlate with performance?
- Are quality-first titles getting clicks, or do shoppers scroll past them?
- Do pain-point openings drive conversions, or do they feel manipulative?

**Observations**:
1. **Collection naming**: "ALWAYS append 'Collection' after collection name" (lines 96, 106) — This adds length. Does it help or hurt CTR?
2. **Shopify title rules**: NO finish name, NO "Allied Brass" — Correct for on-site browsing, but enforced via validation only (not in prompt emphasis)
3. **Synonym strategy (Bing)**: "Use synonyms across DIFFERENT sentences naturally" — Good approach, but no evidence it's being followed in practice
4. **Platform context differentiation**: Google vs Bing vs Shopify have different user intents, but descriptions are very similar in practice

### Missing Elements

**WAITING FOR CRO-RESEARCHER DATA TO CONFIRM**:
- No mention of cross-surface journey (Google Shopping → Shopify product page)
- No emphasis on price competitiveness positioning
- No guidance on lifestyle image integration (recently added to feed)

---

## 2. Scoring System Audit

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/quality-scoring.ts`

### Current Metrics

#### CTR Proxy (Title Score, 0-10)
**Method**: Zone-based analysis
- **Mobile Zone (0-30 chars)**: Product type + dimension = +3-5 points
- **Desktop Zone (31-70 chars)**: Material, functional modifier = +1-2 points
- **Extended Zone (71-150 chars)**: Brand placement = +1-2 points

**Assumption**: Titles with product type and dimension in the first 30 characters will get more clicks.

**CRITICAL QUESTION (AWAITING ADS-RESEARCHER DATA)**:
- Do SKUs with high zone scores actually have high CTR?
- Or are we measuring "well-formatted titles" instead of "titles that drive clicks"?

#### CVR Proxy (Description Score, 0-10)
**Method**: Platform-specific length targets + attribute density
- **Google**: 600-800 chars ideal
- **Bing**: 700-1000 chars ideal
- **Shopify**: 600-1000 chars ideal
- **Attribute density**: 2+ searchable attributes in first 150 chars = +2 points

**Assumption**: Descriptions with more attributes and proper length will convert better.

**CRITICAL QUESTION (AWAITING CRO-RESEARCHER DATA)**:
- Do longer descriptions actually convert better?
- Is "attribute density" a proxy for conversion, or just for feed eligibility?
- Does opening with engagement hooks (Shopify) correlate with add-to-cart rate?

#### Brand Voice (0-10)
**Method**: Premium cue counting - crafted, engineered, precision, solid brass, etc.

**Issue**: Diminishing returns built in, but no validation that these words correlate with revenue.

#### Readability (0-10)
**Method**: Penalty-based - dimension dumps, keyword lists, long sentences, brand-only fragments

**Strength**: Prevents robotic writing, but does it predict human engagement?

### Composite Score Calculation

**Formula**: `(CTR + CVR + Voice + Readability) / 40 * 100`

**Hard violation penalties**:
- Shopify title with "Allied Brass": -30 points
- Shopify title with finish name: -30 points
- Hardcoded finish in Google/Bing description: -20 points

**CRITICAL ISSUE**:
The composite score treats all dimensions equally. But do they actually contribute equally to revenue?

**AWAITING RESEARCHER DATA**:
- Which dimension (CTR, CVR, Voice, Readability) has the strongest correlation with actual revenue?
- Should we weight CTR proxy higher than Voice?

---

## 3. Evidence Pipeline Audit

**Files**:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/builder.ts`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/search-queries.ts`

### Currently Surfaced to LLM

| Evidence Field | Source | Format |
|----------------|--------|--------|
| master_sku, category, collection | `product_catalog` | Direct fields |
| current_title, current_description | `product_catalog` | Baseline content |
| bullet_1 through bullet_6 | `product_catalog` | Feature bullets |
| material, style, shape, mounting_type | `product_catalog` | Attributes |
| product_length, height, width, weight | `product_catalog` | Dimensions with units |
| available_finishes, finish_count | `product_catalog` | 28 finish list |
| selected_finish, finish_character | `variant_index` + finish metadata | Finish context (Google/Bing only) |
| design_style | On-the-fly enrichment | Traditional/Contemporary/Transitional |
| feature_benefits | On-the-fly enrichment | Detected from bullets |
| room_context | On-the-fly enrichment | Bathroom/Kitchen/etc |
| competitive_edge, warranty | Hardcoded enrichment | "Solid brass construction...", "Limited lifetime warranty" |
| **search_queries_top** | `search_queries_by_master_sku` | Top 10 queries with volume |
| **search_query_themes** | Extracted from queries | Material/Style/Function keywords |

### NOT Surfaced (Available in Database)

| Table | What's Available | Why It Might Matter |
|-------|------------------|---------------------|
| `performance_baselines` | Pre-optimization CTR, CVR, impressions | Show LLM what's currently working/not working |
| `competitor_listings` | Competitor titles, descriptions, SERP position | Learn from what ranks well |
| `keyword_metrics` | Keyword Planner search volume, competition, CPC | Prioritize high-value keywords |
| `price_competitiveness_product_view` (GMC) | Benchmark price vs competitors | Position against market |
| `product_performance_view` (GMC) | Click-through rate by product | Actual CTR data (not proxy) |

### Evidence Pipeline Strengths

1. **Search query integration**: Already pulling top queries with volume data (lines 124-159 in `search-queries.ts`)
2. **Theme extraction**: Automatically detects material/style/function patterns (lines 201-263)
3. **Finish metadata**: Categorizes finishes by style affinity (Traditional Warm, Contemporary Neutral, etc.)
4. **Variant context**: For Google/Bing, provides finish-specific context

### Evidence Pipeline Gaps

**CRITICAL GAPS**:
1. **No performance feedback loop**: LLM doesn't see "previous title had 2% CTR, current baseline is 0.5% CTR"
2. **No competitor context**: LLM doesn't see "top 3 SERP results all mention 'wall mount' in title"
3. **No keyword value prioritization**: Search queries show volume, but not CPC or competition level
4. **No price positioning**: LLM doesn't know if product is premium, mid-tier, or value

**AWAITING RESEARCHER DATA**:
- Would surfacing performance baselines actually improve content quality?
- Do competitor titles contain patterns we should adopt?

---

## 4. Gold Standard Examples Audit

**Source**: `prompt_templates` table, 10 examples (SKUs: AP-41/24, DT-41-24-HK, CU-GRS-24, FR-24R, CL-GLT-24, CL-27-92, RDM-4/3X, AP-1TB/22, BSK-275LA, CL-22)

### Example Quality

**Strengths**:
1. **Category diversity**: Towel bars (2), grab bars (1), TP holders (2), mirrors (2), shelves (1), shower accessories (1), hooks (1)
2. **Style coverage**: Traditional (7), Contemporary (1), Transitional (2)
3. **Pain-point vs Quality-first balance**:
   - Pain-point examples: Grab bar ("hospital look"), rollerless TP holder ("spring hassle"), shower basket ("bottles on floor")
   - Quality-first examples: Standard towel bar, mirrors, shelves
4. **Finish sentences**: All 10 examples include 28 product-specific finish sentences
5. **Platform differentiation**: Google vs Bing vs Shopify titles/descriptions properly differentiated

### Potential Issues

**AWAITING ADS-RESEARCHER DATA**:
- Are these 10 SKUs actually high performers?
- Or were they selected for category coverage, not revenue performance?

**Observation**: Examples were selected for "high volume, classic design, representative" — but no mention of actual CTR, CVR, or revenue metrics.

### Example Analysis: AP-41/24 (Astor Place 24" Towel Bar)

**Google Title**: `{FINISH_NAME} 24 Inch Solid Brass Towel Bar - Wall Mounted - Astor Place - Allied Brass`

**Why it works (per example notes)**: "Quality-first opening is correct here — a standard towel bar has no dramatic pain point. Description focuses on craftsmanship (solid brass vs hollow tubing) without manufacturing drama."

**Google Description Opening**: "A towel bar should look as good as the rest of your bathroom. This 24-inch bar is crafted from solid brass—not hollow tubing or plated plastic—with traditional Astor Place detailing..."

**QUESTION FOR ADS-RESEARCHER**: Does this quality-first approach actually get clicks? Or do shoppers scroll past it for titles with price/urgency?

---

## 5. Cross-Platform Consistency Analysis

### Title Formats

**Google/Bing**:
```
{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass
```

**Shopify**:
```
[Collection Name] Collection [Product Type] [Key Specs] - [Differentiator]
```

**Platform Context Strings**:
- Google: "Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass. ALWAYS append 'Collection' after the collection name."
- Bing: Same as Google, plus "Include natural product synonyms across different sentences."
- Shopify: "Must be the inner core of the Google/Bing title — same product identity, minus finish and brand."

### Description Differentiation

**Google**: "Assess first: does this product have a natural pain point? If yes, open with the problem. If no, open with quality/craftsmanship. Write for a human scanning Shopping ads."

**Bing**: "Same balanced assessment as Google (quality-first default, pain-point only when natural). Include product synonyms naturally across different sentences."

**Shopify**: "Customer already clicked, now convince them to add to cart. Open with their problem or desired outcome when natural, otherwise lead with quality/craftsmanship. Mention 28 finishes as a benefit."

### Analysis

**Strengths**:
1. Clear intent differentiation: Shopping ad (click driver) vs on-site (conversion)
2. Shopify removes brand/finish (correct for variant selection page)
3. Bing synonym guidance (avoid parenthetical dumps)

**Potential Issues (AWAITING CRO-RESEARCHER DATA)**:
1. **Cross-surface journey**: User sees Google Shopping ad, clicks to Shopify product page. Do descriptions feel consistent or jarring?
2. **Google vs Bing**: Both use same pain-point assessment. Should Bing lean harder into synonyms for broader search coverage?
3. **Shopify engagement**: "Mention 28 finishes as a benefit" — Does this actually drive conversions, or is it just filler?

---

## 6. Preliminary Findings

### What's Working

1. **Authentic messaging framework**: Quality-first default prevents manufactured drama
2. **Search query integration**: Evidence pipeline already surfaces top queries with volume
3. **Platform-specific rules**: Shopify title validation prevents "Allied Brass" and finish names
4. **Finish sentence approach**: Product-specific sentences for 28 finishes (not generic "available in X finish")
5. **Gold standard variety**: 10 examples span categories, styles, and pain-point vs quality-first approaches

### What Needs Validation (AWAITING RESEARCHER DATA)

1. ~~**Zone-based title scoring**: Does mobile zone (0-30 chars) product type actually predict CTR?~~ **ANSWERED BY ADS-RESEARCHER**
2. **Description length targets**: Do 600-800 char descriptions outperform shorter/longer?
3. **Attribute density**: Does "2+ attributes in first 150 chars" correlate with conversion?
4. ~~**Quality-first vs Pain-point**: Which approach drives more revenue in practice?~~ **ANSWERED BY ADS-RESEARCHER**
5. **Collection name suffix**: Does "Astor Place Collection" help or hurt CTR vs "Astor Place"?

### CRITICAL DISCOVERY (ADS-RESEARCHER FINDINGS)

**THE SCORING DISCONNECT**:
- 8 low-CTR SKUs have quality scores of 88-92 (excellent by our metrics)
- Yet they have 0% CTR in Google Ads
- **Conclusion**: High quality scores DO NOT correlate with actual CTR performance

**THE 84% DATA GAP**:
- 41 of 49 low-CTR SKUs are missing generated content entirely
- We can't validate scoring for SKUs that don't have content yet
- **P0 Priority**: Generate missing content before optimizing scoring

**KEYWORD GAPS IDENTIFIED**:
- "bathroom" keyword: 40.5K monthly searches, missing from many titles
- FT-6 (top revenue SKU, $3,938) missing "bathroom" in title despite relevance
- Search query → title alignment is good but not perfect

**VALIDATION RESULTS**:
1. **Zone-based scoring ❌ FAILED**: High zone scores (product type in mobile zone) don't predict CTR
2. **Quality-first approach ⚠️ UNCLEAR**: Only 8 SKUs with content, all have 0% CTR regardless of approach
3. **Composite weighting ❌ FAILED**: Treating all dimensions equally doesn't predict revenue

### Critical Gaps

1. **No performance feedback loop**: LLM doesn't see current CTR/CVR baselines
2. **No competitor intelligence**: LLM doesn't see SERP title patterns
3. **No keyword value weighting**: Search queries show volume but not CPC or competition
4. **Composite score weighting**: All dimensions weighted equally, but may not contribute equally to revenue

---

## 7. Recommendations (Based on Ads-Researcher Findings)

### IMMEDIATE ACTIONS (P0)

**1. Fix the Data Gap First**
- **Issue**: 84% of low-CTR SKUs (41 of 49) have NO generated content
- **Action**: Run batch generation for all 41 missing SKUs before any prompt optimization
- **Why**: Can't validate scoring or prompt changes without content to measure
- **Effort**: Medium (existing batch generation API)
- **Impact**: HIGH - blocks all other optimization

### SCORING SYSTEM RECALIBRATION (P1)

**2. Add Keyword Coverage Metric**
- **Issue**: "bathroom" (40.5K searches) missing from titles, FT-6 ($3,938 revenue) lacks context keywords
- **Current**: Zone-based scoring assumes product type placement predicts CTR (FAILED validation)
- **New Metric**: Keyword Coverage Score (0-10)
  - Check if high-volume search keywords appear in title
  - Weight by search volume from `keyword_metrics` table
  - Penalize missing high-intent keywords (10K+ monthly searches)
- **Implementation**:
  ```typescript
  function scoreKeywordCoverage(title: string, searchQueries: SearchQueryInsight[]): number {
    const titleLower = title.toLowerCase()
    let score = 0

    // Check top 5 queries (weighted by volume)
    for (const query of searchQueries.slice(0, 5)) {
      const volume = query.avg_monthly_searches ?? 0
      if (volume > 10000 && titleLower.includes(query.query_text.toLowerCase())) {
        score += 3 // High-volume match
      } else if (volume > 1000 && titleLower.includes(query.query_text.toLowerCase())) {
        score += 2 // Medium-volume match
      }
    }

    // Check for critical context keywords
    const contextKeywords = ['bathroom', 'kitchen', 'shower', 'vanity']
    const hasContext = contextKeywords.some(kw => titleLower.includes(kw))
    if (!hasContext) score -= 2 // Penalize missing context

    return clamp0to10(score)
  }
  ```
- **Effort**: Low (1-2 hours)
- **Impact**: HIGH - directly addresses identified keyword gaps

**3. Reweight Composite Score Formula**
- **Current**: `(CTR + CVR + Voice + Readability) / 40 * 100` (equal weights)
- **Issue**: CTR proxy (zone-based) failed validation, but we're weighting it 25%
- **New Formula**:
  ```typescript
  compositeScore = (
    keywordCoverage * 0.30 +  // NEW: Search alignment (30%)
    cvrProxy * 0.25 +          // Description quality (25%)
    ctrProxy * 0.15 +          // Zone structure (15%, reduced from 25%)
    brandVoice * 0.15 +        // Premium positioning (15%)
    readability * 0.15         // Human engagement (15%)
  ) * 100
  ```
- **Rationale**: Keyword coverage predicts search visibility better than zone placement
- **Effort**: Low (30 minutes)
- **Impact**: MEDIUM - aligns scoring with actual search behavior

### PROMPT IMPROVEMENTS (P1)

**4. Add Room Context Emphasis**
- **Issue**: FT-6 missing "bathroom" despite 40.5K monthly searches for "bathroom shelves"
- **Current Prompt**: Room context in evidence table, but not emphasized in title generation
- **New Instruction** (add to `PLATFORM_CONTEXT.google.title`):
  ```
  CRITICAL: Include room context (bathroom/kitchen/shower) when search queries show 10K+ monthly volume for "[room] [product]" pattern. Check search_queries_top evidence field.
  ```
- **Effort**: Low (5 minutes)
- **Impact**: MEDIUM - addresses 40.5K search volume gap

**5. Strengthen Search Query Integration**
- **Issue**: Search query → title alignment is "good but not perfect"
- **Current Prompt**: Evidence table shows `search_queries_top` but doesn't mandate usage
- **New Instruction** (add after line 91 in `SYSTEM_PROMPT`):
  ```
  ### Search Query Alignment (CRITICAL)
  The evidence table includes `search_queries_top` showing actual customer search terms with volume data.
  - HIGH priority (10K+ monthly searches): Must include these keywords in title
  - MEDIUM priority (1K-10K searches): Strongly consider including
  - Use natural phrasing, not keyword stuffing
  - Example: If "bathroom glass shelf" shows 8.1K searches, ensure both "bathroom" and "glass shelf" appear in title
  ```
- **Effort**: Low (10 minutes)
- **Impact**: HIGH - closes search query alignment gap

### EVIDENCE PIPELINE ENHANCEMENTS (P2)

**6. Surface Keyword Value Metrics**
- **Issue**: Evidence shows search volume but not CPC or competition level
- **Current**: `search_queries_top` shows "(2.4K vol)" format
- **Enhancement**: Add CPC and competition data from `keyword_metrics` table
  ```typescript
  // In search-queries.ts formatSearchQueriesForEvidence()
  if (volume && volume > 0) {
    const cpc = insight.low_cpc_micros ? (insight.low_cpc_micros / 1000000).toFixed(2) : null
    const comp = insight.competition ?? 'UNKNOWN'
    queryParts.push(`"${text}" (${formatVolume(volume)} vol, $${cpc} CPC, ${comp} comp)`)
  }
  ```
- **Output**: `"bathroom shelf" (8.1K vol, $0.45 CPC, MEDIUM comp)`
- **Benefit**: LLM can prioritize high-value keywords (high volume, low competition, decent CPC)
- **Effort**: Low (30 minutes)
- **Impact**: MEDIUM - helps LLM prioritize keyword selection

**7. Add Performance Baseline Context** (AWAITING CRO-RESEARCHER DATA)
- **Issue**: LLM doesn't see "current title has 0% CTR"
- **Enhancement**: Surface baseline performance when regenerating
- **Deferred**: Need CRO-researcher data on conversion context
- **Effort**: Medium (1-2 hours)
- **Impact**: TBD

### NEXT STEPS (AWAITING CRO-RESEARCHER)

Still waiting for cro-researcher findings to address:
1. Description length validation (600-800 chars vs actual conversions)
2. Cross-surface journey consistency (Google Shopping → Shopify)
3. "28 finishes" messaging effectiveness
4. Engagement hook validation (pain-point vs quality-first for conversions)

---

## Appendix: Files Analyzed

1. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/regeneration/prompts.ts` (272 lines)
2. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/quality-scoring.ts` (887 lines)
3. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/builder.ts` (322 lines)
4. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/search-queries.ts` (302 lines)
5. `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` (1735 lines)
6. Supabase `prompt_templates` table (10 gold standard examples)

---

**Status**: DRAFT — Awaiting ads-researcher and cro-researcher findings to complete analysis and recommendations.
