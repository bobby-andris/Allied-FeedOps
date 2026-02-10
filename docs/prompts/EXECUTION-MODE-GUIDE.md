# 🚀 Execution Mode: Start Fresh Claude Code Session

## Copy/Paste This Into New Chat

```
Please use agent teams to implement @docs/prompts/25-content-generation-optimization.md

CRITICAL CONTEXT:
- We have only 1 published SKU (FT-16) - no performance data to analyze
- This is PROACTIVE validation ("is our methodology optimal?") not REACTIVE analysis
- Compare our methodology against industry best practices, NOT our own performance
- MUST USE marketing skills: page-cro, copywriting, paid-ads

See @docs/prompts/25-READY-TO-EXECUTE.md for full context.
```

---

## What This Will Do

Spawns 3-agent team to validate content generation methodology:

1. **ads-researcher**: Research Google Shopping best practices + competitor analysis
2. **cro-researcher**: Research Shopify CRO principles + validate FT-16 content
3. **prompt-engineer**: Audit our system against discovered best practices

**Timeline**: ~1 hour
**Outcome**: Validation report + prioritized recommendations

---

## Reference Docs (Already Created)

| File | Purpose |
|------|---------|
| `25-content-generation-optimization.md` | **Main spec** (edited to reflect actual goal) |
| `25-content-generation-optimization-OPTIMIZED.md` | Quick start guide with all context |
| `25-READY-TO-EXECUTE.md` | Ultra-concise execution guide |
| `EXECUTION-MODE-GUIDE.md` | This file (how to start new session) |

---

## Why Start Fresh Session?

Current session has:
- ❌ 2 rounds of incorrect research (wrong assumptions)
- ❌ Validation/correction cycles consuming context
- ❌ Agents with stale understanding of task goal

New session gets:
- ✅ Clean context with corrected task specification
- ✅ No confusion from previous false starts
- ✅ Direct path to correct research approach

---

## Expected Agent Behavior

**Agent 1 (ads-researcher)** should:
- ✅ Use `marketing-skills:paid-ads` for Google Shopping expertise
- ✅ Scrape competitor titles from Google Shopping results
- ✅ Research GMC structured data guidelines (2026)
- ❌ NOT pull our performance data (insufficient sample)

**Agent 2 (cro-researcher)** should:
- ✅ Use `marketing-skills:page-cro` to analyze https://www.alliedbrass.com/products/ft-16
- ✅ Use `marketing-skills:copywriting` to compare OLD vs NEW content
- ✅ Research Shopify CRO best practices for bathroom hardware
- ❌ NOT assume publishing is broken (FT-16 proves it works)

**Agent 3 (prompt-engineer)** should:
- ✅ Wait for Agents 1 & 2 to complete research first
- ✅ Audit `prompts.ts` against discovered best practices
- ✅ Audit `quality-scoring.ts` for alignment with what matters
- ❌ NOT validate scoring against our own performance (can't with 1 SKU)

---

## Success Criteria

Research is complete when you have:
- ✅ Used all 3 required marketing skills
- ✅ Analyzed 5+ competitor titles/pages
- ✅ Compared our methodology against industry standards
- ✅ Identified specific gaps (not vague "could be better")
- ✅ Prioritized recommendations (quick wins vs long-term)

---

## After Research Completes

1. Review validation report and recommendations
2. Approve implementation plan (or request changes)
3. Implement quick wins (prompt improvements, evidence pipeline)
4. Recalibrate scoring system
5. Scale publishing with confidence in methodology

---

**Ready to start fresh?** Open new Claude Code session and paste the command above. ⬆️
