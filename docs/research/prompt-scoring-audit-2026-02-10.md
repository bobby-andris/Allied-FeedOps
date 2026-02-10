# Prompt & Scoring Methodology Audit

**Date**: 2026-02-10
**Auditor**: prompt-engineer agent
**Scope**: System prompt, quality scoring, evidence pipeline, gold standard examples, platform differentiation
**Context**: Only 1 published SKU (FT-16), ~75-80/100 avg quality, ~2-3% approval rate
**Integrated Research**: Google Shopping research (ads-researcher, 2026-02-10), Shopify CRO research (cro-researcher, pending)

---

## 1. System Prompt Audit

### Files Analyzed
- `dashboard/src/lib/regeneration/prompts.ts` (272 lines) -- SINGLE SOURCE OF TRUTH
- `dashboard/src/lib/regeneration/core.ts` (791 lines) -- Generation orchestration
- Supabase `prompt_templates` table -- Gold standard examples (10 SKUs, version 2.1.0)

### What the System Prompt Does Well

**A. Balanced Approach Framework (lines 65-89)**
The quality-first vs pain-point-first decision framework is sound. It correctly identifies that standard products (towel bars, hooks) should lead with craftsmanship, while pain-point products (grab bars, rollerless TP holders) should lead with frustration. This avoids manufactured drama -- a real risk with AI content.

**B. Title Structure (lines 93-99)**
`{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass`

This follows Google Shopping best practices:
- Finish first (search relevance for finish-specific queries)
- Product type early (critical for mobile zone visibility)
- Brand last (lower priority for non-household brands)

**C. Guardrails (lines 132-137)**
Banned words, no invented specs, claims-must-trace-to-evidence -- all appropriate for GMC compliance.

**D. Finish Sentence Architecture (lines 188-215)**
The 28-finish sentence system is genuinely innovative. Each sentence relates the finish to the specific product, not generic descriptions. This produces differentiated variant content at scale.

### Critical Gaps in System Prompt

**GAP 1: No Search Query Integration Mandate**

The prompt mentions search data is available in the evidence table but never instructs the LLM to prioritize high-volume keywords. The prior audit (2026-02-09) identified this exact issue -- FT-6 missing "bathroom" despite 40.5K monthly searches for "bathroom [product]" patterns.

**Current state** (line 60-137): No mention of search queries or keyword prioritization.

**Recommended addition** after line 99:
```
### Search Query Alignment (CRITICAL)
The evidence table includes `search_queries_top` with actual customer search terms and volume.
- Keywords with 10K+ monthly searches: MUST appear in title
- Keywords with 1K-10K searches: Strongly consider including
- Always include room context (bathroom/kitchen) when search data shows volume
- Use natural phrasing -- not keyword stuffing
```

**Impact**: HIGH. Directly addresses the gap where generated titles miss high-volume terms.

**GAP 2: No Character Count Guidance for Titles**

The prompt specifies title structure but not length targets. The scoring system (quality-scoring.ts) penalizes titles under 60 chars and rewards 70-150 chars, but the LLM doesn't know this.

**Recommended addition** after the title structure section:
```
### Title Length Targets
- Google/Bing: 70-120 characters optimal (penalized under 60)
- Shopify: 50-80 characters (product page H1, not search listing)
- Mobile truncation at ~30 chars -- front-load product type
```

**GAP 3: No Description Character Count in Prompt**

Description length targets exist in PLATFORM_CONTEXT (lines 146, 150, 154) but are buried in brief context strings. The LLM sees "600-800 characters" for Google but this could be more prominent.

**GAP 4: No Competitive Differentiation Instructions**

The prompt mentions "solid brass -- not hollow tubing" but doesn't systematically instruct the LLM to address competitive alternatives. For bathroom hardware at $30-80 price points, buyers need justification against $10-15 Amazon alternatives.

**Recommended addition**:
```
### Competitive Positioning
Address the price-quality gap naturally:
- Why solid brass matters (not die-cast zinc, not plastic)
- What "lifetime warranty" means in practice
- 28 finishes as coordination advantage over big-box 3-4 finish options
```

**GAP 5: Missing "Collection" Suffix Consistency**

Lines 96-97 instruct to "ALWAYS append 'Collection' after the collection name" but this rule is repeated 7 times across the file. Despite this, it's one of the most frequent manual revision reasons in the approval workflow. The repetition suggests the instruction needs to be structured differently -- perhaps as a validation rule rather than just a prompt instruction.

### Prompt Template (DB) vs Code Prompt Alignment

The DB template (`content-generation-v2`) has a system_prompt of 2,087 chars that uses "TRUE WHY" framework language. The code prompt (`SYSTEM_PROMPT`) in prompts.ts uses "Balanced Approach" language. **These are different framings of the same concept.**

However, `core.ts` line 229 explicitly uses `SYSTEM_PROMPT` from code and ignores the DB's `system_prompt`. The DB template is only used for gold standard examples and category guidance. This is correct -- single source of truth is maintained.

**Potential issue**: If someone updates the DB template's system_prompt thinking it will take effect, it won't. The code comment at prompts.ts:57-59 documents this, but it could confuse future maintainers.

---

## 2. Quality Scoring System Evaluation

### File: `dashboard/src/lib/quality-scoring.ts` (887 lines)

### Current Architecture

The system has two scoring layers:
1. **4-Dimension Analysis** (`analyzeContent`): ctrProxy (0-10), cvrProxy (0-10), brandVoice (0-10), readability (0-10) -> composite 0-100
2. **6-Dimension Analysis** (`analyzeSixDimensions`): Maps the 4-dimension scores to 6 categories via weighted formulas

### CTR Proxy (Title Scoring) -- Needs Recalibration

**Zone-based analysis (lines 187-278)**:
- Mobile zone (0-30 chars): +3 for product type
- Desktop zone (31-70 chars): +1 for product type
- Material in desktop zone: +1
- Brand at end: +2
- Dimension in title: +2

**Problem**: This scores *structure* but not *search alignment*. A title can score 9/10 by having product type in mobile zone, dimensions, material, and brand at end -- yet miss the actual keywords shoppers search for. The prior audit confirmed this: 8 SKUs scored 88-92 but had 0% CTR.

**Recommendation**: Add a `scoreKeywordAlignment` function that checks generated title against `search_queries_top` evidence. Weight: 30% of composite (highest single factor).

### CVR Proxy (Description Scoring) -- Largely Accurate

**Scoring dimensions (lines 372-529)**:
- Length targets per platform (Google 600-800, Bing 700-1000, Shopify 600-1000)
- Attribute density in first 150 chars (feed fuel)
- Measurement/spec counts (3+ = bonus)
- Trust signals (warranty, Virginia, 28 finishes)
- Synonym coverage for Google/Bing
- Room context mentions
- Installation mentions
- Shopify-specific: engagement hooks, bullet structure, specs section

**Assessment**: This is well-designed. The platform-specific scoring correctly identifies different user intents:
- Google/Bing: Feed fuel (searchable attributes) matters most
- Shopify: Engagement hooks and trust signals matter most

**Minor issue**: The exclamation point penalty (line 520-522, -1 point) is correct for Google/Bing feed content but overly harsh for Shopify where a single tasteful exclamation mark can boost engagement. Consider platform-specific handling.

### Brand Voice Scoring -- Reasonable but Static

**Scoring (lines 536-571)**:
- Starts at 5 (neutral baseline)
- Premium cues: "crafted", "engineered", "precision", "solid brass" (+1-2)
- Generic fillers penalty: "this product", "this item" (-0)
- ALL CAPS penalty: -2
- Banned marketing words: -3

**Assessment**: The "premium positioning" target matches Allied Brass's market segment (mid-premium bathroom hardware, $30-80 price points). However, the scoring is purely lexical -- it checks for specific words but cannot evaluate whether the *tone* reads as premium.

**Concern**: The premium cue list includes "lifetime warranty" and "limited lifetime warranty" but the prompt's banned words list includes "luxurious", "premium", "exclusive". There's tension -- you want premium positioning but ban the word "premium." This is actually correct (show don't tell), but it means the brand voice score rewards indirect signals.

### Readability Scoring -- Appropriate but Limited

**Scoring (lines 578-627)**:
- Google/Bing only (Shopify gets 10 by default)
- Penalizes dimension dumps in opening
- Penalizes keyword lists at end
- Penalizes very long sentences (>150 chars)
- Penalizes brand-only fragment at end

**Assessment**: Setting Shopify to automatic 10 is correct -- Shopify descriptions are explicitly HTML with bullets, paragraphs, and structure that don't need readability scoring. However, the penalty list is narrow. Consider adding:
- Penalize repetitive sentence openings (AI content often starts 3+ sentences with "This [product]")
- Penalize passive voice density in Google/Bing descriptions

### Composite Score Formula -- Misaligned

**Current (line 687-689)**:
```
compositeScore = (ctr + cvr + brandVoice + readability) / 40 * 100
```

This gives equal 25% weight to all four dimensions. Problems:
- Readability for Google/Bing is rarely penalized (most content passes), so it inflates scores
- Brand voice starts at 5 and easily reaches 7-8, also inflating
- The two dimensions that actually correlate with business outcomes (CTR proxy, CVR proxy) get only 50% combined weight

**Recommendation** (aligned with prior audit):
```
compositeScore = (
  keywordAlignment * 0.30 +  // NEW: Search alignment
  cvrProxy * 0.25 +          // Description quality
  ctrProxy * 0.15 +          // Zone structure (reduced)
  brandVoice * 0.15 +        // Premium positioning
  readability * 0.15         // Human engagement
) / 10 * 100
```

### 6-Dimension Mapping -- Derivative, Not Independent

The `analyzeSixDimensions` function (lines 778-886) maps 4 scores to 6 dimensions:
- Specificity = cvrProxy * 0.6 + brandVoice * 0.4
- Benefit Coverage = cvrProxy
- Keyword Inclusion = ctrProxy
- Format Adherence = length checks
- Brand Voice = brandVoice (direct)
- Factual Accuracy = 10 - (issues * 2)

**Problem**: Specificity and Benefit Coverage are both derived primarily from cvrProxy. They're not independent dimensions -- they're just different weightings of the same underlying score. This means the 6-dimension view doesn't actually provide 6 independent signals.

**Factual Accuracy** is particularly weak: it only checks for formatting issues (ALL CAPS, URLs, banned words) -- not whether claims trace to evidence. True factual accuracy would require comparing generated claims against the evidence table, which is expensive but would be valuable.

---

## 3. Evidence Pipeline Audit

### Files Analyzed
- `dashboard/src/lib/evidence/builder.ts` (322 lines)
- `dashboard/src/lib/evidence/search-queries.ts` (302 lines)
- `dashboard/src/lib/evidence/enrichment.ts` (310 lines)
- `dashboard/src/lib/evidence/types.ts` (91 lines)

### What's Surfaced to the LLM

The evidence table provided to the LLM includes:

| Category | Fields | Source |
|----------|--------|--------|
| Core ID | master_sku, category, collection | catalog |
| Current Content | current_title, current_description | catalog |
| Feature Bullets | bullet_1 through bullet_6 | catalog |
| Attributes | material, style, shape, orientation, tilting, mounting_type | catalog |
| Dimensions | product_length/height/width, projection, weight, center_to_center, diameter, mirror_height/width, thickness, weight_capacity | catalog |
| Finishes | available_finishes, finish_count, selected_finish (if variant) | catalog |
| Enrichment | design_style, feature_title_keywords, feature_benefits, room_context, competitive_edge, warranty | enrichment |
| Search Data | search_queries_top, search_query_themes | search_insights |
| Images | product_image_url | catalog |

### Evidence Pipeline Strengths

1. **Comprehensive product data**: All 11 dimension fields, 6 bullets, material, style, etc.
2. **On-the-fly enrichment**: Design style detection (traditional/modern/transitional/industrial/coastal/designer) with tone guidance
3. **Functional feature detection**: 16 feature patterns (reeded grip, L-shaped, ADA compliant, etc.) with title keywords
4. **Search query integration**: Top queries with volume data, theme extraction

### Evidence Pipeline Gaps

**GAP A: No Competitor Data in Evidence**

The `competitor_listings` and `competitor_patterns` tables exist (documented in SCHEMA.md) but are NOT surfaced in the evidence table. The LLM generates content without seeing what competitors rank for or how they structure titles.

**Recommended addition** to `builder.ts`:
```typescript
// Add top competitor title patterns for this category
if (competitorPatterns.length > 0) {
  evidence.push({
    field: 'competitor_title_patterns',
    value: patterns.map(p => p.pattern_value).join(', '),
    source: 'competitor_intelligence',
  })
}
```

**Impact**: MEDIUM. Helps LLM understand market positioning and differentiation opportunities.

**GAP B: No Performance Baseline in Evidence**

The evidence table shows the LLM what the product IS but not how it's PERFORMING. Adding current CTR/impressions/clicks would enable the LLM to adjust strategy (e.g., more aggressive keyword inclusion for 0-CTR SKUs).

**GAP C: Search Volume Not Prioritized**

`search-queries.ts` formats queries as `"brass towel bar" (2.4K vol)` but doesn't flag which keywords are missing from the current title. The LLM has to do this comparison itself.

**Recommended addition**:
```typescript
evidence.push({
  field: 'missing_high_volume_keywords',
  value: 'bathroom (40.5K), glass shelf (8.1K)',
  source: 'keyword_gap_analysis',
})
```

**GAP D: No Price Context**

The product catalog doesn't include price data in the evidence table. For bathroom hardware, price-quality positioning is critical -- the LLM can't write "worth every penny" messaging without knowing the price point.

**GAP E: Theme Extraction Is Basic**

`extractQueryThemes()` in search-queries.ts categorizes into Material/Style/Function but misses:
- Intent signals (buy, best, review, vs, comparison)
- Dimension-specific queries ("24 inch towel bar" -- common exact-match pattern)
- Brand queries ("allied brass" -- indicates brand awareness)

---

## 4. Platform Differentiation Assessment

### Current Platform Differentiation

| Aspect | Google | Bing | Shopify |
|--------|--------|------|---------|
| Title prefix | {FINISH_NAME} | {FINISH_NAME} | None |
| Brand in title | "Allied Brass" suffix | "Allied Brass" suffix | No brand |
| Description format | Plain text 600-800 chars | Plain text 700-1000 chars | HTML with bullets |
| Finish handling | {FINISH_SENTENCE} placeholder | {FINISH_SENTENCE} placeholder | Finish-agnostic |
| Synonym strategy | Standard | Natural synonym distribution | N/A |
| Trust signals | Lifetime warranty + solid brass | Same | Warranty + 28 finishes + engagement hooks |

### Assessment

**Google vs Bing**: The differentiation is minimal -- primarily length targets and synonym instructions for Bing. This is reasonable because both platforms serve Shopping ad intent. However:

- **Bing titles could be more aggressive with synonyms**: The prompt says to "use synonyms across DIFFERENT sentences naturally" for Bing but the title structure is identical to Google. Consider allowing longer Bing titles with synonym variants (e.g., "Towel Bar / Towel Rack" in the extended zone, since Bing supports up to 150 chars and Bing Shopping has less competition).

**Google vs Shopify**: Differentiation is correct and meaningful:
- Google: Search-optimized, keyword-rich, finish-specific
- Shopify: Conversion-optimized, finish-agnostic, HTML with engagement structure

**Missing differentiation**: The prompt doesn't account for Google Shopping's structured data attributes (`structured_title`, `structured_description`) which have different optimization rules than free-text titles. The system already publishes to these fields (see Google Sheets column layout in CLAUDE.md) but the prompt doesn't distinguish between standard and structured fields.

---

## 5. Gold Standard Examples Review

### Current Examples (10 SKUs in prompt_templates)

| # | SKU | Category | Style | Approach |
|---|-----|----------|-------|----------|
| 1 | AP-41/24 | Towel Bars - Standard | Traditional | Quality-first |
| 2 | DT-41-24-HK | Towel Bars - With Hooks | Traditional | Pain-point (space-saving) |
| 3 | CU-GRS-24 | Grab Bars/ADA | Contemporary | Pain-point (institutional look) |
| 4 | FR-24R | TP Holders - Rollerless | Traditional | Pain-point (spring hassle) |
| 5 | CL-GLT-24 | TP Holders - With Shelf | Traditional | Pain-point (phone storage) |
| 6 | CL-27-92 | Mirrors - Wall Mounted | Traditional | Pain-point (forgettable mirrors) |
| 7 | RDM-4/3X | Mirrors - Makeup | Traditional | Pain-point (hunching over sink) |
| 8 | AP-1TB/22 | Shelves - Glass | Traditional | Pain-point (one wall spot) |
| 9 | BSK-275LA | Shower Accessories | Traditional | Pain-point (bottles on floor) |
| 10 | CL-22 | Statement/Niche | Traditional | Pain-point (hooks catch sleeves) |

### Strengths

1. **Category diversity**: 10 different product categories covered
2. **Approach balance**: Quality-first (#1) vs pain-point (#2-10) clearly demonstrated
3. **Finish sentence quality**: All 28 finishes with product-specific sentences, not generic
4. **"why_it_works" annotations**: Each example explains the approach rationale
5. **Cross-platform consistency**: Google, Bing, Shopify versions all provided

### Issues

**ISSUE 1: Style Bias -- 9/10 Traditional**

Nine of ten examples are "Traditional" style. Only #3 (Cube Design grab bar) is Contemporary. Zero examples of Modern, Transitional, Industrial, or Coastal styles. This creates a few-shot learning bias toward traditional language patterns.

**Impact**: Generated content for modern/contemporary products may inherit traditional tone ("elegant," "refined") when it should use crisp/clean language.

**Fix**: Replace 2-3 examples with non-traditional products (e.g., a Montero/contemporary towel bar, a Pipeline/industrial shelf).

**ISSUE 2: Pain-Point Overrepresentation**

9 of 10 examples use pain-point openings. The system prompt says quality-first is the DEFAULT, yet the examples show pain-point as dominant. This sends mixed signals -- the LLM will likely default to pain-point because that's what most examples demonstrate.

**Fix**: Make examples 50/50 (5 quality-first, 5 pain-point) to match the prompt's stated default.

**ISSUE 3: No Robe Hook or Simple Hook Example**

Robe hooks are one of the highest-volume categories but are missing from gold standards. These are quintessential quality-first products -- no natural pain point, just "good hook for robes/towels."

**ISSUE 4: Title Length Inconsistency**

Looking at the gold standard Google titles:
- #1: `{FINISH_NAME} 24 Inch Solid Brass Towel Bar - Wall Mounted - Astor Place - Allied Brass` (82 chars without finish)
- #9: `{FINISH_NAME} Shower Basket Caddy - Rust Proof Solid Brass - Wall Mount - Allied Brass` (78 chars without finish)

With a finish name like "Oil Rubbed Bronze" (17 chars), these become 99-95 chars -- good range. But shorter finish names like "Pink" (4 chars) make them 86-82 chars. This variability is inherent to the finish-first structure but worth noting.

**ISSUE 5: Missing "Collection" Suffix in Some Examples**

Example #9 (BSK-275LA) has `collection: null` -- no collection in the title. The gold standard correctly omits it. But example titles for collection products don't always append "Collection" consistently in the examples despite the prompt repeating this rule 7 times. This inconsistency in examples vs rules creates confusion.

---

## 6. Content Quality vs Approval Rate Analysis

### The Core Question

Quality scores average 75-80/100, yet approval rate is ~2-3%. This massive gap suggests one of three issues:

### Hypothesis A: Score Doesn't Measure What the Approver Cares About

**Evidence FOR**:
- The scoring system checks structure (zones, length, keywords) but not subjective quality
- "Collection" suffix missing is a common rejection reason -- not scored
- Finish name leaking into base description is a common rejection reason -- only caught by validation, not scoring
- The 6-dimension mapping derives multiple dimensions from the same underlying scores

**Evidence AGAINST**:
- FT-16 scored 91.67 and WAS approved, suggesting high scores do indicate quality

**Assessment**: PARTIALLY TRUE. The score measures structural compliance, but the approver also evaluates content naturalness, accuracy, and brand alignment. A score of 75 can mean "structurally sound but reads like AI wrote it."

### Hypothesis B: Approval Threshold Too High

**Evidence FOR**:
- Only 1 of ~50+ SKUs with generated content has been fully approved
- The approval workflow requires title_approved + description_approved + image_approved
- Images add another approval bottleneck independent of content quality

**Evidence AGAINST**:
- The business is spending significant time and money on content generation, so high standards are warranted

**Assessment**: PARTIALLY TRUE. The image approval requirement compounds the bottleneck. A SKU with perfect content but unapproved images can't progress.

### Hypothesis C: Content Quality Genuinely Not Good Enough

**Evidence FOR**:
- FT-16's Bing description (the only one NOT approved) is notably different from the gold standards. It reads:
  > "Towel ring for bathroom use, 6 inches / 6-inch / 6in diameter, round wall-mounted design..."
  This is a keyword-stuffed format that doesn't match the brand voice at all. It includes slash-separated dimension alternatives and reads like a feed optimization dump, not natural copy.
- The quality score for FT-16 is 91.67 across ALL platforms, which seems suspicious -- identical scores for wildly different content quality

**Evidence AGAINST**:
- FT-16's Google and Shopify content are genuinely good quality and were approved

**Assessment**: PARTIALLY TRUE. The Bing description reveals a significant prompt compliance issue -- the LLM sometimes falls back to keyword-stuffing mode despite explicit instructions against it. This suggests the synonym instruction for Bing (lines 117-123) may be interpreted too aggressively.

### Root Cause Synthesis

The 2-3% approval rate is driven by a combination of:
1. **Structural issues that scoring catches but content generation fails on** (Collection suffix, finish name leakage)
2. **Content naturalness that scoring CANNOT measure** (AI-sounding patterns, keyword stuffing)
3. **Pipeline bottleneck from image approval requirements**
4. **Score inflation from readability and brand voice dimensions** that almost never penalize

---

## 7. Prioritized Recommendations

### P0: Fix Score-Approval Misalignment (Highest Impact)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 1 | **Add keyword coverage scoring dimension** that checks generated titles against search_queries_top | Low | HIGH |
| 2 | **Reweight composite score**: keyword 30%, CVR 25%, CTR 15%, brand 15%, readability 15% | Low | HIGH |
| 3 | **Add "Collection" suffix validation** to `validateGeneratedContent()` as a hard check | Low | MEDIUM |

### P1: System Prompt Improvements

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 4 | **Add Search Query Alignment section** to system prompt (mandate high-volume keywords) | Low | HIGH |
| 5 | **Add title character count targets** to system prompt | Low | MEDIUM |
| 6 | **Add competitive positioning instructions** | Low | MEDIUM |
| 7 | **Strengthen Bing anti-stuffing instructions** -- add negative example of keyword-stuffed Bing content | Low | MEDIUM |

### P2: Gold Standard Examples

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 8 | **Diversify styles**: Replace 2-3 traditional examples with modern/transitional/industrial | Medium | MEDIUM |
| 9 | **Balance approach ratio**: Adjust to 50/50 quality-first vs pain-point | Medium | MEDIUM |
| 10 | **Add robe hook example** (high-volume quality-first archetype) | Low | LOW |

### P3: Evidence Pipeline Enhancements

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 11 | **Surface competitor patterns** from competitor_listings/competitor_patterns tables | Medium | MEDIUM |
| 12 | **Add performance baseline** to evidence table (CTR, impressions) | Medium | MEDIUM |
| 13 | **Add missing keyword gap analysis** to evidence (flag high-volume keywords not in current title) | Medium | HIGH |
| 14 | **Surface keyword value metrics** (CPC, competition) alongside volume | Low | LOW |

### P4: Scoring System Structural Fixes

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 15 | **Make 6-dimension scores independent** (separate Specificity from Benefit Coverage) | Medium | MEDIUM |
| 16 | **Add AI-naturalness detection** (penalize repetitive sentence openings, keyword stuffing patterns) | High | HIGH |
| 17 | **Platform-specific exclamation handling** (allow in Shopify, penalize in Google/Bing) | Low | LOW |

---

## Implementation Priority Matrix

```
                    HIGH IMPACT
                        |
    [1] Keyword scoring  |  [13] Keyword gap analysis
    [2] Reweight scores  |  [16] AI-naturalness detection
    [4] Search query     |
        mandate          |
    ─────────────────────┼─────────────────────────────
    [3] Collection       |  [8] Diversify examples
        validation       |  [9] Balance approach ratio
    [5] Title length     |  [11] Competitor patterns
    [6] Competitive      |  [12] Performance baseline
        positioning      |
    [7] Bing anti-stuff  |
                        |
                    LOW IMPACT
         LOW EFFORT            HIGH EFFORT
```

**Start here**: Items 1, 2, 4 (all low effort, high impact) -- can be done in a single session.

---

## Appendix: FT-16 Content Analysis

FT-16 (Foxtrot Collection 6 Inch Towel Ring) is the only published SKU. Quality score: 91.67/100 across all platforms.

### Google Title (APPROVED)
`{FINISH_NAME} 6 Inch Solid Brass Towel Ring - Wall Mounted - Foxtrot Collection - Allied Brass`
- Zone analysis: Product type in mobile zone -- YES ("Solid Brass Towel Ring" starts within 30 chars with most finishes)
- Specs: 6 Inch -- present
- Collection: "Foxtrot Collection" -- correct suffix
- Brand: "Allied Brass" at end -- correct
- **Assessment**: Good title following the template structure

### Google Description (APPROVED)
- 601 chars (target 600-800) -- at lower boundary
- Opens with quality-first approach (correct for towel ring -- no pain point)
- Includes: solid brass, 6-inch, wall-mounted, 2-inch projection, 10 lb capacity, lifetime warranty
- Has {FINISH_SENTENCE} placeholder -- correct
- **Assessment**: Well-crafted, evidence-based, appropriate length

### Bing Description (NOT APPROVED)
- 911 chars (target 700-1000) -- within range
- Opens with "Towel ring for bathroom use, 6 inches / 6-inch / 6in diameter" -- KEYWORD STUFFED
- Contains slash-separated dimension alternatives
- Lists finish name in base description (Antique Brass)
- **Assessment**: FAILS brand voice, violates synonym integration rules, contains hardcoded finish name

### Shopify Title (APPROVED)
`Foxtrot Collection 6 Inch Round Towel Ring - Solid Brass Wall Mount`
- No "Allied Brass" -- correct
- No finish name -- correct
- Includes collection + product + spec + material
- **Assessment**: Clean, effective product page H1

### Shopify Description (APPROVED)
- 1,273 chars with HTML structure
- Opens with engagement hook: "A hand towel deserves a dedicated spot"
- Bullet list with 8 items including bold labels
- Mentions 28 finishes, lifetime warranty
- **Assessment**: Excellent Shopify product page content

### Key Takeaway from FT-16

The Google and Shopify content are genuinely high quality and were rightfully approved. The Bing description failed because the LLM misinterpreted the synonym instruction as "include dimension alternatives" rather than "use product type synonyms across sentences." This is a prompt clarity issue, not a capability issue.

---

## 8. Integration with Google Shopping Research (ads-researcher)

The ads-researcher's Google Shopping research (2026-02-10) provides data that validates and extends several audit findings.

### Validation of Audit Findings

**CONFIRMED: Finish-first title structure is correct**
Research data: Finish-specific searches have 1.07% CTR vs 0.77% for generic product searches (39% CTR advantage). Our title structure `{FINISH_NAME} [Product] [Specs]...` correctly front-loads the highest-CTR attribute.

**CONFIRMED: Brand position should NOT be first**
Research data: ZERO search queries contained "Allied Brass" or any competitor brand. The market is entirely attribute-driven. Our structure correctly places "Allied Brass" at the end. However, competitors like Moen/Kohler/Delta lead with brand. Allied Brass should NOT follow this pattern because it lacks comparable brand recognition.

**CONFIRMED: Size in title drives highest CTR**
Research data: "60 grab bar" has 4.15% CTR -- the highest in the dataset. Size-specific queries show high purchase intent. Our title structure includes `[Key Specs]` but the prompt could be more explicit about always including dimensions.

**CONFIRMED: "Solid Brass" is a key differentiator**
Research data: Most competitors (Moen, Delta) use zinc alloy. Our material inclusion in titles differentiates at a glance. The scoring system rewards material in desktop zone (+1 point) but could weight this higher given competitive dynamics.

### New Insights Requiring Prompt Updates

**FINDING: Title structure order should be reconsidered**

Current system: `{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass`

Research-recommended: `{FINISH_NAME} [Product Type] [Size] - [Material] [Mounting] - [Collection] Collection - Allied Brass`

Key difference: Research data suggests explicit `[Material]` and `[Mounting]` slots rather than generic `[Differentiator]`. The word "Solid Brass" should be a fixed element, not optional.

**FINDING: Unlacquered Brass is a premium keyword**

Research data: "unlacquered brass" queries have 3.05% CTR. This finish commands premium attention. The gold standard examples should include at least one Unlacquered Brass-focused example showing how to leverage this keyword opportunity.

**FINDING: Category-specific title structures needed**

Research provides category-specific title formulas (towel bars, glass shelves, grab bars, soap dishes, robe hooks). The current system uses one universal template. Consider adding category_guidance in the prompt template to specify title element order per category.

### Research-Informed Recommendation Updates

| Original Rec # | Updated Recommendation | Justification |
|----------------|----------------------|---------------|
| 4 | Strengthen to require "Solid Brass" in ALL titles | Competitive differentiation confirmed by research |
| 5 | Specify 70-150 chars for Google/Bing | Research confirms 150-char budget should be fully used |
| 6 | Add "28 finishes" as mandatory differentiator | Research shows finish variety = competitive moat |

---

**End of Report**
