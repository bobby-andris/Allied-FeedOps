# Prompt & Scoring System Audit — FINAL

**Status**: Complete synthesis of ads-researcher and cro-researcher findings
**Auditor**: prompt-engineer agent
**Date**: 2026-02-09

---

## Executive Summary

This audit evaluated the content generation system against actual performance data from Google Ads and Shopify. **Key finding**: The system is generating high-quality content (88-93/100 scores), but has two critical blockers:

1. **84% missing content** (41/49 low-CTR SKUs have no generated titles/descriptions)
2. **100% missing Shopify descriptions** (AI content exists in database but isn't published to live site)

The scoring system itself needs recalibration: zone-based title scoring doesn't correlate with CTR, while description scoring is accurate.

---

## Critical Findings

### 🚨 P0: Publishing Infrastructure Broken

**Shopify product pages show ZERO descriptions** despite high-quality content existing in database.

- **Database**: 400-600 word HTML descriptions (scores 88-93/100)
- **Live site**: Completely blank description sections
- **Expected lift**: 15-30% add-to-cart improvement (industry benchmark)
- **Root cause**: Publishing pipeline writes to Google Sheets but NOT to Shopify `descriptionHtml` field

**Impact on cross-surface journey**:
- Google Shopping ad → promises detailed product info
- Shopify landing page → delivers only title + price + images
- Message discontinuity risk: No persuasion layer, no trust signals, no objection handling

### 🚨 P0: Content Generation Gap

**84% of low-CTR SKUs are missing content entirely**:
- 41 of 49 low-CTR SKUs have NO generated titles/descriptions
- Can't validate scoring or prompt changes without content to measure
- Blocks all other optimization work

### ❌ CTR Proxy Validation Failed

**Zone-based scoring doesn't predict clicks**:
- 8 low-CTR SKUs have quality scores of 88-92 (excellent by our metrics)
- Yet they all have 0% CTR in Google Ads
- **Problem**: We're scoring "product type in mobile zone" but missing high-value keywords
- **Example**: FT-6 ($3,938 revenue) missing "bathroom" (40.5K monthly searches)

### ✅ CVR Proxy Validation Passed

**Description scoring is accurate**:
- 88-93 scores correctly identify high-quality content
- Length targets (400-600 words) validated by CRO research
- Structure (benefits-first, bullets, specs) follows best practices
- Trust signals (warranty, Made in USA) correctly emphasized

---

## Recommendations by Priority

### P0: Fix Publishing Infrastructure (Week 1)

#### 1. Publish Shopify Descriptions
- **File**: `dashboard/src/lib/publishing/shopify.ts`
- **Action**: Add `descriptionHtml` field to product update mutation
- **Expected lift**: 15-30% add-to-cart improvement
- **Effort**: Low (1-2 hours)
- **Impact**: CRITICAL - fixes #1 conversion blocker

#### 2. Generate Missing Content
- **Action**: Run batch generation for 41 missing SKUs
- **Why**: Blocks all optimization validation
- **Effort**: Medium (existing batch API)
- **Impact**: HIGH - enables data-driven optimization

---

### P1: Scoring System Recalibration (Week 2)

#### 3. Add Keyword Coverage Metric
- **Problem**: Zone placement ≠ search alignment
- **Solution**: NEW scoring dimension (0-10)
  - Check if high-volume search keywords appear in title
  - Weight by search volume from `keyword_metrics` table
  - Penalize missing context keywords ("bathroom", "kitchen", "shower")

**Implementation**:
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
- **Impact**: HIGH - directly addresses keyword gaps (40.5K monthly searches)

#### 4. Reweight Composite Score
- **Current**: Equal weights (25% each dimension)
- **New**: Prioritize keyword coverage over zone structure

```typescript
compositeScore = (
  keywordCoverage * 0.30 +  // NEW: Search alignment (30%)
  cvrProxy * 0.25 +          // Description quality (25%)
  ctrProxy * 0.15 +          // Zone structure (15%, reduced from 25%)
  brandVoice * 0.15 +        // Premium positioning (15%)
  readability * 0.15         // Human engagement (15%)
) * 100
```

- **Effort**: Low (30 minutes)
- **Impact**: MEDIUM - aligns scoring with search behavior

---

### P1: Prompt Improvements (Week 2)

#### 5. Strengthen Search Query Integration
- **Problem**: Search query → title alignment "good but not perfect"
- **Current**: Evidence table shows `search_queries_top` but doesn't mandate usage
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
- **Impact**: HIGH - closes 40.5K search volume gap

#### 6. Add Room Context Emphasis
- **Problem**: FT-6 missing "bathroom" despite relevance
- **New Instruction** (add to `PLATFORM_CONTEXT.google.title`):

```
CRITICAL: Include room context (bathroom/kitchen/shower) when search queries show 10K+ monthly volume for "[room] [product]" pattern. Check search_queries_top evidence field.
```

- **Effort**: Low (5 minutes)
- **Impact**: MEDIUM - improves search relevance

---

### P2: Evidence Pipeline Enhancements (Week 3)

#### 7. Surface Keyword Value Metrics
- **Current**: `"bathroom shelf" (8.1K vol)`
- **Enhanced**: `"bathroom shelf" (8.1K vol, $0.45 CPC, MEDIUM comp)"`

**Implementation** (in `search-queries.ts`):
```typescript
if (volume && volume > 0) {
  const cpc = insight.low_cpc_micros ? (insight.low_cpc_micros / 1000000).toFixed(2) : null
  const comp = insight.competition ?? 'UNKNOWN'
  queryParts.push(`"${text}" (${formatVolume(volume)} vol, $${cpc} CPC, ${comp} comp)`)
}
```

- **Benefit**: LLM prioritizes high-value keywords (high volume, low competition, decent CPC)
- **Effort**: Low (30 minutes)
- **Impact**: MEDIUM - improves keyword selection

#### 8. Add Performance Baseline Context
- **Problem**: LLM doesn't see "current title has 0% CTR" when regenerating
- **Solution**: Surface baseline performance in evidence table

**Implementation** (in `evidence/builder.ts`):
```typescript
if (performanceBaseline) {
  evidence.push({
    field: 'current_performance',
    value: `CTR: ${baseline.avg_ctr?.toFixed(2)}%, Impressions: ${baseline.avg_impressions}, Clicks: ${baseline.avg_clicks}`,
    source: 'performance_baseline'
  })
}
```

- **Benefit**: LLM can adjust approach for underperforming content
- **Effort**: Medium (1-2 hours)
- **Impact**: MEDIUM - creates feedback loop

---

### P3: Quick CRO Wins (Week 4)

#### 9. Add Warranty Badge
- **Action**: Shopify theme customization
- **Banner**: "🛡️ Limited Lifetime Warranty | Assembled in USA"
- **Placement**: Near price/CTA (visible before scroll)
- **Effort**: Low (1 hour)
- **Impact**: MEDIUM - trust signal above fold

#### 10. Improve Collection Cross-Sell
- **Current**: "Complete your bathroom with matching pieces from the [Collection] collection"
- **Better**: "Complete your bathroom: [Towel Bars](link) | [Hooks](link) | [Shelves](link) from the [Collection] collection"
- **Effort**: Low (edit template)
- **Impact**: MEDIUM - increases average order value

---

## Validation Results

### ✅ What's Working

1. **Description Quality**: Scores 88-93 are accurate - content structure, length, and messaging validated by CRO research
2. **Two-Title Approach**: Google (finish + brand + specs) vs Shopify (collection + product) is best practice
3. **Pain-Point Framework**: Authentic approach - only apply when natural frustrations exist (grab bars, rollerless TP holders)
4. **"28 Finishes" Messaging**: Addresses coordination anxiety (bathroom hardware-specific buyer need)
5. **Trust Signals**: Warranty + Made in USA in first paragraph drives conversion
6. **Platform Differentiation**: Google/Bing/Shopify contexts correctly target different user intents

### ❌ What Failed Validation

1. **Zone-Based CTR Proxy**: Product type in mobile zone (0-30 chars) doesn't predict clicks
2. **Equal Composite Weighting**: All dimensions weighted 25% despite different revenue correlation
3. **Keyword Coverage**: High-value keywords (40.5K searches) missing from titles

### ⚠️ What Needs Monitoring

1. **Collection Name Suffix**: "Astor Place Collection" adds length - needs A/B test to validate
2. **Quality-First vs Pain-Point**: Only 8 SKUs with content, all have 0% CTR - insufficient data
3. **Synonym Strategy (Bing)**: Prompt guidance exists but no validation of adherence

---

## CRO Framework Validated

### Bathroom Hardware Buyer Decision Factors

Research confirmed buyers need at decision time:

1. **Dimensions** (will it fit?) - ✅ Current descriptions include
2. **Finish coordination** (match existing fixtures?) - ✅ "28 finishes" messaging addresses
3. **Installation confidence** (DIY-friendly?) - ✅ "Concealed screw mounting, all hardware included"
4. **Quality justification** ($40 Allied vs $12 Amazon?) - ✅ "Solid brass outlasts die-cast zinc"

### High-Converting Description Structure

✅ Current AI descriptions follow best practices:

```
[HOOK: Problem/aspiration in 1 sentence]
[TRUST: Warranty + Made in USA]
[BENEFIT: What this solves]

BULLETS (4-6 with action verbs):
- Create a tidy look...
- Hang with confidence...
- Get a cohesive finish...

SPECS BLOCK:
- Dimensions: specific measurements
- Material: brass + why it matters
- Warranty: Limited lifetime

[CROSS-SELL: Collection mention]
```

---

## Impact vs Effort Matrix

### Quick Wins (Low Effort, High Impact)

1. ✅ Publish Shopify descriptions (15-30% conversion lift)
2. ✅ Add keyword coverage metric (fixes 40.5K search gap)
3. ✅ Strengthen search query prompt (closes alignment gap)

### Major Projects (High Effort, High Impact)

4. Generate missing content for 41 SKUs (enables optimization)
5. Add performance baseline feedback loop (creates learning system)

### Fill-Ins (Low Effort, Medium Impact)

6. Reweight composite score formula
7. Add room context emphasis
8. Surface keyword value metrics (CPC + competition)
9. Add warranty badge
10. Improve collection cross-sell links

### Skip (High Effort, Low Impact)

- None identified - all recommendations have clear ROI

---

## Implementation Sequence

**Week 1 (Unblock)**:
1. Publish Shopify descriptions → Fix #1 conversion blocker
2. Generate 41 missing SKUs → Enable optimization validation

**Week 2 (Recalibrate)**:
3. Add keyword coverage metric → Fix failed CTR proxy
4. Reweight composite score → Align with revenue correlation
5. Strengthen search query prompt → Close alignment gap
6. Add room context emphasis → Capture 40.5K searches

**Week 3 (Enhance)**:
7. Surface keyword value metrics → Improve LLM prioritization
8. Add performance baseline context → Create feedback loop

**Week 4 (Optimize)**:
9. Add warranty badge → Quick CRO win
10. Improve cross-sell → Increase AOV

---

## Files Analyzed

1. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/regeneration/prompts.ts` (272 lines)
2. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/quality-scoring.ts` (887 lines)
3. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/builder.ts` (322 lines)
4. `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/evidence/search-queries.ts` (302 lines)
5. `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` (1735 lines)
6. Supabase `prompt_templates` table (10 gold standard examples)
7. Ads-researcher report: Google Ads performance analysis
8. CRO-researcher report: Shopify conversion optimization analysis

---

**End of Report**
