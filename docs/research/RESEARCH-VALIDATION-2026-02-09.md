# Research Validation - Critical Errors Found

**Date**: 2026-02-09
**Status**: Phase 1 research had significant errors - correcting and re-running

---

## Errors Found in Original Research

### ❌ Error #1: Shopify Publishing "Broken" (cro-researcher)

**Claim**: "Shopify product pages show NO descriptions - publishing is broken"

**Reality**:
- FT-16 (the only APPROVED product) HAS a description on Shopify
- Published successfully 5 times on Feb 8, 2026
- Description is 1,273 characters and visible on live site
- Publishing infrastructure works correctly

**Root Cause**:
- Researcher checked UNAPPROVED products (MB-20, DT-32)
- Concluded infrastructure was broken
- Didn't validate against the ONE approved product

**Impact**:
- False P0 priority (fix publishing)
- Wasted 15-30% conversion lift estimate
- Misdirected implementation focus

---

### ❌ Error #2: "Quality Scores Don't Predict CTR" (ads-researcher)

**Claim**: "8 low-CTR SKUs scored 88-92 but have 0% CTR - scoring failed validation"

**Reality**:
- The 0% CTR is for OLD baseline titles (not the NEW scored titles)
- The NEW titles (88-92 scores) are UNAPPROVED and never tested live
- Comparing performance of OLD titles against scores of NEW titles = apples to oranges

**Example**:
| SKU | OLD Title (0% CTR) | NEW Title (91.67 score, untested) |
|-----|-------------------|-----------------------------------|
| CL-22 | "Retractable Wall Hook (Patent Pending), 2-1/2-Inch Extension, Carolina Collection, , Allied Brass" | "Antique Brass Retractable Wall Hook, 2-1/2-Inch Pull-Out, Wall Mount Brass - Carolina (Patent Pending), Allied Brass" |

**Root Cause**:
- Logical error in analysis (conflated baseline performance with candidate scoring)
- Didn't distinguish between "what's live" vs "what's proposed"
- Invalid conclusion from mismatched data

**Impact**:
- False conclusion that scoring system failed
- Recommended "fixing" a scoring system that may already work
- Didn't recognize the real issue: OLD titles are poor quality

---

### ✅ Valid Finding: 84% Missing Content (ads-researcher)

**Claim**: "41 of 49 low-CTR SKUs have no generated content"

**Validation**: ✅ CORRECT
- Only 8 of 49 SKUs have ANY generated content (16%)
- 41 SKUs (84%) have nothing - completely empty

**BUT**: Even the 8 with content aren't approved
- All 8 have candidate content
- ZERO have approved content
- Real issue: Approval workflow, not just generation

---

## What We Should Actually Be Researching

### The REAL Questions

1. **Are NEW titles better than OLD titles?**
   - Do quality improvements (88-92 scores) represent actual content improvements?
   - Would replacing OLD with NEW likely improve CTR?

2. **What makes content successful?**
   - FT-16 is approved and published - what's working there?
   - What patterns should we learn from and reinforce?

3. **How can we improve content generation?**
   - What's missing from prompts that causes gaps?
   - What evidence should we surface to LLM?
   - How can scoring guide better content?

### What We Should NOT Research

- ❌ Is publishing infrastructure broken? (It's not - FT-16 proves it works)
- ❌ Do scores predict performance of untested content? (Can't validate without testing)
- ❌ Why aren't descriptions visible? (They are visible when content is approved)

---

## Corrected Priority List

### P0 - Content Approval Workflow

**Issue**: Only 1 of 72,000+ products has approved content for Shopify
- FT-16 is the only approved product
- Publishing works fine - we just need more approved content
- Bottleneck: Approval process, not generation or publishing

**Action**:
- Review and approve more high-quality candidate content
- Test if NEW titles actually improve CTR vs OLD titles

### P1 - Generate Missing Content

**Issue**: 41 of 49 low-CTR SKUs have no content at all
- Can't approve what doesn't exist
- Need to generate content first

**Action**:
- Run batch generation for 41 missing SKUs
- Focus on low-CTR products first (highest improvement potential)

### P2 - Content Quality Improvements

**Issue**: Are the NEW titles actually better than OLD titles?
- Quality scores 88-92 suggest yes
- But need to validate with CRO analysis
- Need to understand what makes FT-16 successful

**Action**:
- Analyze FT-16 (approved, published, live)
- Compare OLD vs NEW titles objectively
- Use marketing skills to evaluate content quality
- Identify specific prompt/scoring improvements

---

## Re-Running CRO Research

**New Agent**: cro-analyst (respawned with correct focus)

**Research Goals**:
1. Analyze FT-16 as success baseline (using `marketing-skills:page-cro`)
2. Compare OLD vs NEW content quality (using `marketing-skills:copywriting`)
3. Research e-commerce best practices for bathroom hardware
4. Validate if high scores = high quality content
5. Provide specific recommendations for content improvement

**NOT researching**:
- Infrastructure issues (publishing works)
- Performance of untested content (can't validate)
- Approval workflows (business process, not content optimization)

---

## Lessons Learned

### Research Validation is Critical

- Always check assumptions against actual data
- Verify claims with the simplest test case (FT-16)
- Don't confuse "what's live" with "what's proposed"

### Focus Matters

- Task is "content generation optimization"
- Not "infrastructure debugging"
- Not "approval workflow improvement"
- Focus on: What makes content convert?

### Use Available Tools

- Marketing skills exist for a reason (page-cro, copywriting, paid-ads)
- Should have been used from the start
- Skills provide frameworks for content analysis

---

## Next Steps

1. ✅ cro-analyst running corrected CRO research
2. ⏳ Wait for validated content quality analysis
3. ⏳ Synthesize findings focused on content improvement
4. ⏳ Provide actionable recommendations for prompts/scoring

**Expected Timeline**: 10-15 minutes for proper CRO analysis

---

**Status**: Research validation complete, corrected research in progress
