# Content Generation Optimization - Research Synthesis

**Date**: 2026-02-09
**Team**: content-optimization
**Status**: Phase 1 Complete, Ready for Implementation

---

## Research Team Results

### ✅ Task #1: Google Ads Performance Research (ads-researcher)
**Report**: See team messages above
**Status**: Complete

**Key Findings**:
- **84% missing content**: 41 of 49 low-CTR SKUs have no generated titles/descriptions
- **Quality score paradox**: 88-92 scored titles have 0% CTR
- **Keyword gaps**: "bathroom" (40.5K monthly searches) missing from category-appropriate titles
- **Top performer**: FT-6 (corner glass shelf) - $3,938 revenue, but missing "bathroom" context

### ✅ Task #2: Shopify CRO Research (cro-researcher)
**Report**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/research/shopify-cro-analysis-2026-02-09.md`
**Status**: Complete

**Key Findings**:
- **Critical blocker**: Shopify product pages show ZERO descriptions
- **Content exists**: 88-93 scored descriptions in database, not published
- **Expected lift**: 15-30% add-to-cart improvement from publishing descriptions
- **Validation**: Two-title strategy (Google vs Shopify) is best practice

### ✅ Task #3: Prompt & Scoring Audit (prompt-engineer)
**Report**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/research/prompt-scoring-audit-2026-02-09.md`
**Status**: Complete

**Key Findings**:
- **CTR proxy failed**: Zone-based scoring doesn't correlate with actual CTR
- **CVR proxy passed**: Description scoring accurately identifies quality content
- **Framework validated**: Pain-point messaging, trust signals, platform differentiation all correct
- **Recalibration needed**: Add keyword coverage metric, reweight composite score

---

## Critical Issues Discovered

### 🚨 P0 - Infrastructure Blockers (Must Fix First)

1. **Shopify Descriptions Not Published**
   - **Impact**: 15-30% conversion loss (no product descriptions on site)
   - **Fix**: Modify `dashboard/src/lib/publishing/shopify.ts` to publish `descriptionHtml`
   - **Effort**: 1-2 hours
   - **Priority**: CRITICAL

2. **84% Missing Generated Content**
   - **Impact**: Can't optimize 41 of 49 low-CTR products
   - **Fix**: Run batch generation for missing SKUs
   - **Effort**: Medium (use existing `/batch-optimize` endpoint)
   - **Priority**: CRITICAL

### ❌ P1 - Scoring System Issues

3. **Zone-Based CTR Proxy Doesn't Work**
   - **Issue**: High scores (88-92) but 0% CTR performance
   - **Root cause**: Scoring "product type in mobile zone" but missing high-value keywords
   - **Fix**: Add keyword coverage metric (0-10 score based on search query alignment)
   - **Effort**: Low (1-2 hours)
   - **Priority**: HIGH

4. **Composite Score Weighting Wrong**
   - **Issue**: Failed CTR proxy weighted equally (25%) with valid metrics
   - **Fix**: Reweight - Keyword Coverage 30%, CVR 25%, CTR 15%, Voice 15%, Readability 15%
   - **Effort**: Low (10 minutes)
   - **Priority**: HIGH

### ⚠️ P2 - Prompt Improvements

5. **Search Query Alignment Not Enforced**
   - **Issue**: Prompt suggests using search queries but doesn't mandate inclusion
   - **Fix**: Strengthen prompt with explicit keyword requirements
   - **Example**: "If 'bathroom glass shelf' shows 8.1K searches, ensure both 'bathroom' and 'glass shelf' appear in title"
   - **Effort**: Low (10 minutes)
   - **Priority**: MEDIUM

6. **Room Context Not Emphasized**
   - **Issue**: Category keywords ("bathroom", "kitchen") missing despite high search volume
   - **Fix**: Add mandatory room context when search volume >10K
   - **Effort**: Low (10 minutes)
   - **Priority**: MEDIUM

---

## Validated Strengths (Keep These)

✅ **Description Quality**: 88-93 scored content follows CRO best practices
✅ **Platform Differentiation**: Two-title approach (Google vs Shopify) is correct
✅ **Content Structure**: Benefits-first, bullets, trust signals all validated
✅ **Pain-Point Framework**: Works when natural frustration exists
✅ **Finish Variety Messaging**: "28 finishes" addresses coordination anxiety

---

## Implementation Priority Matrix

### Week 1: Fix Infrastructure Blockers
**Goal**: Unblock optimization work and stop conversion leakage

| Task | Impact | Effort | Priority | Files |
|------|--------|--------|----------|-------|
| Publish Shopify descriptions | CRITICAL | 1-2h | P0 | `shopify.ts` |
| Generate 41 missing SKUs | HIGH | 4-6h | P0 | Use existing API |

**Expected Lift**: 15-30% add-to-cart improvement

---

### Week 2: Recalibrate Scoring & Prompts
**Goal**: Fix failed CTR proxy and strengthen keyword alignment

| Task | Impact | Effort | Priority | Files |
|------|--------|--------|----------|-------|
| Add keyword coverage metric | HIGH | 1-2h | P1 | `quality-scoring.ts` |
| Reweight composite score | MEDIUM | 10m | P1 | `quality-scoring.ts` |
| Strengthen search query prompt | HIGH | 10m | P1 | `prompts.ts` |
| Add room context emphasis | MEDIUM | 10m | P1 | `prompts.ts` |

**Expected Lift**: Close 40.5K monthly search gap ("bathroom" keyword)

---

### Week 3: Enhance Evidence Pipeline
**Goal**: Surface high-value data to LLM for better keyword selection

| Task | Impact | Effort | Priority | Files |
|------|--------|--------|----------|-------|
| Surface keyword value (CPC + competition) | MEDIUM | 1h | P2 | `search-queries.ts` |
| Add performance baseline context | MEDIUM | 2h | P2 | `builder.ts` |

**Expected Lift**: Better keyword prioritization based on revenue potential

---

### Week 4: CRO Optimizations (Optional)
**Goal**: Incremental conversion improvements

| Task | Impact | Effort | Priority | Files |
|------|--------|--------|----------|-------|
| Add warranty badge | LOW | 30m | P3 | `prompts.ts` |
| Improve collection cross-sell | LOW | 1h | P3 | `prompts.ts` |

---

## Quick Wins (Implement First)

1. **Publish Shopify descriptions** (1-2 hours, 15-30% lift)
2. **Add keyword coverage metric** (1-2 hours, fixes 40.5K search gap)
3. **Strengthen search query prompt** (10 minutes, closes alignment gap)
4. **Reweight composite score** (10 minutes, deprioritize failed metric)

**Total effort**: ~4 hours
**Total impact**: 15-30% conversion lift + keyword alignment fix

---

## Files to Modify

### P0 - Critical
1. `dashboard/src/lib/publishing/shopify.ts` - Add descriptionHtml field

### P1 - High Priority
2. `dashboard/src/lib/quality-scoring.ts` - Add keyword coverage + reweight
3. `dashboard/src/lib/regeneration/prompts.ts` - Strengthen keyword guidance

### P2 - Medium Priority
4. `dashboard/src/lib/evidence/search-queries.ts` - Surface CPC + competition
5. `dashboard/src/lib/evidence/builder.ts` - Add performance baseline

---

## Success Metrics

### Week 1 (Infrastructure)
- ✅ Shopify product pages show descriptions
- ✅ 41 missing SKUs have generated content

### Week 2 (Scoring)
- ✅ Keyword coverage metric operational
- ✅ Quality scores now correlate with CTR performance
- ✅ "bathroom" keyword appears in category-appropriate titles

### Week 3 (Evidence)
- ✅ Evidence table includes CPC + competition data
- ✅ Performance baselines visible in evidence

### Overall
- 📈 15-30% add-to-cart improvement (Shopify)
- 📈 Measurable CTR lift from keyword alignment
- 📈 Quality scores predict performance (validation)

---

## Next Steps

1. **User approval**: Review this synthesis and approve implementation plan
2. **Phase 2 execution**: Begin with Week 1 (P0 fixes)
3. **Testing**: Validate each change before moving to next priority
4. **Measurement**: Track conversion rates and CTR before/after changes

**Ready for implementation**: All research complete, priorities clear, files identified.

---

**Research Team**:
- ads-researcher (Google Ads performance analysis)
- cro-researcher (Shopify CRO research)
- prompt-engineer (Prompt & scoring audit)

**Team Lead**: Claude Sonnet 4.5
