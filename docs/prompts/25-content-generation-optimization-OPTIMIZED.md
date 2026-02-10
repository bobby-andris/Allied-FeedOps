# Task 25: Content Generation Optimization — Validate Methodology Before Scaling

## Quick Start for New Claude Code Session

**Single Command to Start**:
```
Please use agent teams to implement @docs/prompts/25-content-generation-optimization.md
```

---

## What This Task Is About

**NOT**: Analyzing our performance data (we only have 1 published SKU)
**NOT**: Debugging why optimization failed (we haven't started scaling yet)
**NOT**: Fixing broken publishing infrastructure (it works - FT-16 proves it)

**YES**: Validating our content generation methodology BEFORE scaling from 1 to 1,000+ SKUs
**YES**: Comparing our approach against industry best practices and competitors
**YES**: Using marketing skills to evaluate if we're set up for success

---

## Critical Context

### What We Have
- **Only ONE published SKU**: FT-16 (both Google Shopping and Shopify)
- **~72,000 SKUs** with generated content (candidate_content)
- **~2-3% approval rate** despite 75-80/100 quality scores
- **Publishing works correctly** (FT-16 is live and updated)

### What We're Researching
1. **Google Shopping Best Practices**: Are our titles/descriptions following 2026 GMC guidelines?
2. **Competitor Analysis**: What do successful bathroom hardware sellers do differently?
3. **Shopify CRO Principles**: Does our content follow conversion optimization best practices?
4. **Methodology Gaps**: What's missing from our prompts, scoring, or evidence pipeline?

### What Success Looks Like
- ✅ Confidence that our methodology aligns with industry standards
- ✅ Specific recommendations for improving prompts, scoring, and evidence
- ✅ Prioritized action plan (quick wins vs long-term improvements)

---

## Team Structure

**Team**: `content-optimization`

**3 Parallel Agents**:

### Agent 1: Google Shopping Best Practices (ads-researcher)
- **USE**: `marketing-skills:paid-ads` for expert guidance
- Research 2026 Google Shopping optimization best practices
- Analyze competitor titles in bathroom hardware (scrape Google Shopping results)
- Research GMC structured data guidelines for AI-generated content
- Validate search query → title alignment strategy
- **Deliverable**: Best practices report + competitor pattern analysis

### Agent 2: Shopify CRO Research (cro-researcher)
- **USE**: `marketing-skills:page-cro` to analyze FT-16 live page
- **USE**: `marketing-skills:copywriting` to compare OLD vs NEW content
- Research Shopify product page conversion best practices
- Analyze competitor product pages (bathroom hardware e-commerce)
- Validate our FT-16 content against CRO principles
- Research buyer decision factors for bathroom fixtures
- **Deliverable**: CRO validation report + Shopify content guidelines

### Agent 3: Methodology Audit (prompt-engineer)
- **WAIT** for Agents 1 & 2 to finish research
- Audit `prompts.ts` against discovered best practices
- Audit `quality-scoring.ts` for alignment with what matters
- Audit `evidence/builder.ts` for data pipeline gaps
- Compare gold standard examples against research findings
- **Deliverable**: Gap analysis + prioritized improvement recommendations

---

## Key Marketing Skills to Use

**MUST USE during research**:
- `marketing-skills:paid-ads` - Google Shopping optimization expertise
- `marketing-skills:page-cro` - Product page conversion analysis
- `marketing-skills:copywriting` - Content quality evaluation

These skills provide expert frameworks for validating our methodology.

---

## Common Pitfalls to Avoid

### ❌ DON'T Do This
1. Pull our own performance data and try to correlate with scores (we don't have enough)
2. Analyze "why did this fail" (we haven't scaled yet - nothing failed)
3. Debug publishing infrastructure (it works)
4. Compare OLD content performance vs NEW content scores (invalid comparison)
5. Make assumptions about what's broken (validate first)

### ✅ DO This Instead
1. Research what successful competitors and industry leaders do
2. Use marketing skills for expert evaluation
3. Validate our methodology against best practices
4. Identify gaps between our approach and winning patterns
5. Recommend improvements BEFORE we scale

---

## Files to Reference

| File | Purpose | Lines |
|------|---------|-------|
| `dashboard/src/lib/regeneration/prompts.ts` | System prompt (SINGLE SOURCE) | 272 |
| `dashboard/src/lib/quality-scoring.ts` | 6-dimension scoring system | 887 |
| `dashboard/src/lib/evidence/builder.ts` | Evidence table construction | 322 |
| `dashboard/src/lib/evidence/search-queries.ts` | Search query formatting | 302 |
| `docs/database/SCHEMA.md` | Complete database schema | Always read first |

---

## MCP Tools Available

**Google Ads & GMC**:
- `mcp__google-ads-mcp__search` - Performance data, Keyword Planner
- `mcp__merchant-api-devdocs__*` - GMC docs, structured data guidelines

**Database**:
- `mcp__supabase__execute_sql` - Query Supabase (check SCHEMA.md first)

**Competitor Research**:
- `mcp__Apify__*` - Scrape Google Shopping results, competitor pages
- `mcp__claude-in-chrome__*` - Live site analysis, browser automation

**Documentation**:
- `mcp__plugin_context7_context7__*` - Library docs
- `WebSearch` - Industry research, best practices articles

---

## Expected Timeline

**Phase 1: Research** (30-45 minutes)
- 3 agents working in parallel
- Agents 1 & 2: Independent research
- Agent 3: Waits for 1 & 2, then audits

**Phase 2: Synthesis** (15-20 minutes)
- Combine findings into validation report
- Priority matrix (impact vs effort)
- Recommendations organized by timeline

**Total**: ~1 hour for comprehensive research and validation

---

## Validation Criteria

Before claiming research complete, ensure:

- ✅ Used `marketing-skills:paid-ads` for Google Shopping guidance
- ✅ Used `marketing-skills:page-cro` for Shopify CRO validation
- ✅ Used `marketing-skills:copywriting` to evaluate content quality
- ✅ Analyzed at least 5 competitor titles/descriptions
- ✅ Compared our prompts against discovered best practices
- ✅ Identified specific gaps (not vague "could be better")
- ✅ Prioritized recommendations with rationale

---

## Next Steps After Research

1. **Review findings** with business owner
2. **Approve implementation plan** (quick wins vs long-term)
3. **Implement prompt improvements** based on research
4. **Recalibrate scoring system** to measure what matters
5. **Generate new content** for 10-20 SKUs to validate improvements
6. **Scale publishing** with confidence in methodology

---

**Ready to start?**

Just run: `Please use agent teams to implement @docs/prompts/25-content-generation-optimization.md`
