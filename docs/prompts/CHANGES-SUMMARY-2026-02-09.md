# Prompt File Corrections - Summary of Changes

**Date**: 2026-02-09
**Task**: Edit `docs/prompts/25-content-generation-optimization.md` for new Claude Code chat

---

## What Was Done

### ✅ Edited Main Prompt File

**File**: `docs/prompts/25-content-generation-optimization.md`

**Key Changes**:
1. **Objective Section**: Reframed from reactive analysis to proactive validation
   - BEFORE: "Investigate what's working, what's not" (implies we have data)
   - AFTER: "Validate methodology BEFORE scaling" (correct framing)

2. **Agent 1 (ads-researcher)**: Shifted from performance analysis to best practices research
   - BEFORE: "Pull top-performing SKUs by revenue" (we don't have enough data)
   - AFTER: "Research Google Shopping best practices and competitor patterns" (correct)
   - ADDED: Mandatory use of `marketing-skills:paid-ads`

3. **Agent 2 (cro-researcher)**: Shifted from pattern analysis to CRO validation
   - BEFORE: "Analyze current Shopify content patterns" (assumes we have data)
   - AFTER: "Research Shopify CRO best practices and validate FT-16 content" (correct)
   - ADDED: Mandatory use of `marketing-skills:page-cro` and `copywriting`

4. **Agent 3 (prompt-engineer)**: Shifted from performance correlation to methodology audit
   - BEFORE: "Does high score correlate with performance?" (can't validate with 1 SKU)
   - AFTER: "Compare our methodology against best practices from Agents 1 & 2" (correct)

5. **Critical Context Section**: Added comprehensive anti-patterns and success metrics
   - What we HAVE (1 published SKU, 72K candidates, 2-3% approval rate)
   - What we DON'T HAVE (performance data, failed optimization to debug)
   - Research DO's (compare against industry standards, use marketing skills)
   - Research DON'Ts (assume we have data, debug infrastructure, analyze untested content)

---

## Additional Files Created

### 📘 Reference Guides

1. **`25-content-generation-optimization-OPTIMIZED.md`**
   - Full quick-start guide with all context
   - Explains task goal, team structure, common pitfalls
   - Lists all required marketing skills
   - Expected timeline and validation criteria

2. **`25-READY-TO-EXECUTE.md`**
   - Ultra-concise execution guide
   - Single command to start
   - Critical success factors highlighted
   - Timeline and next steps

3. **`EXECUTION-MODE-GUIDE.md`**
   - How to start a new Claude Code session
   - Copy/paste command with context
   - Why start fresh (clean context)
   - Expected agent behavior

4. **`QUICK-START-GUIDE.md`**
   - Quick reference for new session
   - What you'll get (research report structure)
   - Critical context summary
   - Success checklist

### 📊 Research Documentation

5. **`docs/research/RESEARCH-VALIDATION-2026-02-09.md`**
   - Documents errors found in original research
   - Error #1: False "Shopify publishing broken" claim
   - Error #2: Invalid OLD vs NEW content comparison
   - Lessons learned and corrected approach

6. **`docs/research/SYNTHESIS-2026-02-09.md`**
   - Complete research synthesis (from corrected research)
   - Priority matrix (P0, P1, P2 improvements)
   - Implementation timeline (Week 1-4)
   - Success metrics and next steps

---

## File Organization

```
docs/prompts/
├── 25-content-generation-optimization.md (EDITED - main spec)
├── 25-content-generation-optimization-OPTIMIZED.md (NEW - detailed guide)
├── 25-READY-TO-EXECUTE.md (NEW - concise execution guide)
├── EXECUTION-MODE-GUIDE.md (NEW - new session instructions)
├── QUICK-START-GUIDE.md (NEW - quick reference)
└── CHANGES-SUMMARY-2026-02-09.md (THIS FILE)

docs/research/
├── RESEARCH-VALIDATION-2026-02-09.md (NEW - error analysis)
└── SYNTHESIS-2026-02-09.md (UPDATED - research findings)
```

---

## Key Corrections Made

### ❌ Original (Incorrect) Assumptions

1. **Assumed we have performance data** to correlate with quality scores
   - Reality: Only 1 published SKU (FT-16) - insufficient sample

2. **Assumed we need to debug failed optimization**
   - Reality: We haven't scaled yet - this is PRE-optimization validation

3. **Assumed infrastructure is broken** (Shopify descriptions not publishing)
   - Reality: Publishing works - FT-16 proves it

4. **Compared OLD content performance vs NEW content scores**
   - Reality: Invalid comparison - NEW content never tested live

### ✅ Corrected (Accurate) Approach

1. **Compare methodology against industry best practices**
   - Research Google Shopping optimization standards (2026)
   - Analyze competitor patterns in bathroom hardware
   - Use marketing skills for expert evaluation

2. **Validate FT-16 as reference point**
   - Only approved/published SKU
   - Use to validate methodology, not analyze performance

3. **Use marketing skills for validation**
   - `marketing-skills:paid-ads` - Google Shopping expertise
   - `marketing-skills:page-cro` - Shopify CRO principles
   - `marketing-skills:copywriting` - Content quality evaluation

4. **Focus on methodology gaps**
   - What's missing from prompts?
   - What evidence should we surface?
   - How should scoring be recalibrated?

---

## How to Use These Files

### For New Claude Code Session

**Best approach**: Use `QUICK-START-GUIDE.md` or `25-READY-TO-EXECUTE.md`

**Single command**:
```
Please use agent teams to implement @docs/prompts/25-content-generation-optimization.md
```

**Context to provide**:
```
CRITICAL CONTEXT:
- We have only 1 published SKU (FT-16) - no performance data to analyze
- This is PROACTIVE validation ("is our methodology optimal?") not REACTIVE analysis
- Compare our methodology against industry best practices, NOT our own performance
- MUST USE marketing skills: page-cro, copywriting, paid-ads
```

### For Reference During Execution

- **Task goal unclear?** → Read `RESEARCH-VALIDATION-2026-02-09.md` (what NOT to do)
- **Need full context?** → Read `25-content-generation-optimization-OPTIMIZED.md`
- **Quick reference?** → Read `25-READY-TO-EXECUTE.md`

---

## Expected Outcomes

After running corrected task in new session:

### ✅ Research Report
- Google Shopping best practices (2026)
- Competitor analysis (bathroom hardware)
- Shopify CRO validation
- Methodology audit (prompts, scoring, evidence)

### ✅ Gap Analysis
- What we're doing right (aligned with standards)
- What we're doing wrong (conflicts with best practices)
- What we're missing (gaps vs competitors)

### ✅ Implementation Plan
- Quick wins (implement immediately)
- Medium-term (requires testing)
- Long-term (new capabilities needed)
- Prioritized by impact vs effort

---

## Critical Success Factors

**MUST happen in new session**:
- ✅ Use `marketing-skills:paid-ads` for Google Shopping research
- ✅ Use `marketing-skills:page-cro` to analyze FT-16
- ✅ Use `marketing-skills:copywriting` to compare OLD vs NEW
- ✅ Research competitor patterns (5+ examples)
- ✅ Compare methodology against industry standards
- ❌ NOT analyze our own performance data (insufficient sample)
- ❌ NOT assume infrastructure is broken (it works)
- ❌ NOT compare untested content performance (invalid)

---

## Timeline

**Research Phase**: 30-45 minutes (3 agents in parallel)
**Synthesis Phase**: 15-20 minutes (combine findings)
**Total**: ~1 hour for comprehensive validation

---

## Next Steps

1. **Start fresh Claude Code session** with corrected prompt
2. **Review research findings** and validation report
3. **Approve implementation plan** (or request changes)
4. **Implement quick wins** (prompt improvements, scoring recalibration)
5. **Scale publishing** with confidence in methodology

---

**Status**: All files created and ready for new session execution

**Corrected by**: Claude Sonnet 4.5
**Date**: 2026-02-09
