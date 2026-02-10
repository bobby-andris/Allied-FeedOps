# Quick Start: Content Generation Optimization

## For New Claude Code Session

### Copy This Command

```
Please use agent teams to implement @docs/prompts/25-content-generation-optimization.md
```

---

## What It Does

**Validates** your content generation methodology by comparing against:
- Google Shopping best practices (2026)
- Competitor patterns (bathroom hardware)
- Shopify CRO principles
- Industry standards

**Why Now**: You have only 1 published SKU. Validate methodology BEFORE scaling to 1,000+.

---

## What You'll Get

### Research Report (3 agents, ~1 hour)

1. **Google Shopping Best Practices**
   - GMC structured data guidelines
   - Competitor title analysis
   - Keyword optimization patterns

2. **Shopify CRO Validation**
   - Product page conversion principles
   - FT-16 content evaluation (OLD vs NEW)
   - Buyer decision factor research

3. **Methodology Audit**
   - Prompt gaps vs best practices
   - Scoring alignment with what matters
   - Evidence pipeline completeness

### Deliverables

- ✅ **What's working** (aligned with best practices)
- ✅ **What needs fixing** (conflicts with standards)
- ✅ **What's missing** (gaps vs competitors)
- ✅ **Action plan** (quick wins → long-term improvements)

---

## Critical Context

### What You Have
- **1 published SKU**: FT-16 (Google Shopping + Shopify)
- **72,000 SKUs**: Generated content ready to publish
- **2-3% approval rate**: Despite 75-80/100 quality scores
- **Publishing works**: FT-16 proves infrastructure is fine

### What You DON'T Have
- ❌ Performance data (1 SKU = insufficient sample)
- ❌ Failed optimization to debug (haven't scaled yet)
- ❌ Broken infrastructure (publishing works)

### Research Focus
- ✅ Industry best practices and competitor patterns
- ✅ Methodology validation before scaling
- ✅ Marketing expertise (page-cro, copywriting, paid-ads)
- ❌ NOT analyzing our own performance data

---

## Agent Overview

| Agent | Role | Duration | Skills Used |
|-------|------|----------|-------------|
| **ads-researcher** | Google Shopping best practices + competitor analysis | 20 min | `marketing-skills:paid-ads` |
| **cro-researcher** | Shopify CRO research + FT-16 validation | 20 min | `marketing-skills:page-cro`, `copywriting` |
| **prompt-engineer** | Audit system against discovered best practices | 20 min | Waits for 1 & 2 |

---

## Common Pitfalls (Avoid These)

**❌ Wrong Approaches**:
1. Analyzing our performance data (insufficient sample)
2. Debugging "why we failed" (we haven't scaled yet)
3. Assuming publishing is broken (FT-16 proves it works)
4. Comparing OLD performance vs NEW scores (invalid)

**✅ Right Approaches**:
1. Research what successful competitors do
2. Use marketing skills for expert validation
3. Compare methodology against industry standards
4. Identify gaps vs winning patterns

---

## Files Referenced

| File | Purpose |
|------|---------|
| `prompts.ts` | System prompt (272 lines) |
| `quality-scoring.ts` | 6-dimension scoring (887 lines) |
| `evidence/builder.ts` | Evidence table construction |
| `SCHEMA.md` | Database schema (read first for SQL) |

---

## Success Checklist

Before claiming complete:
- ☐ Used `marketing-skills:paid-ads`
- ☐ Used `marketing-skills:page-cro`
- ☐ Used `marketing-skills:copywriting`
- ☐ Analyzed 5+ competitor examples
- ☐ Compared prompts vs best practices
- ☐ Identified specific gaps (not vague)
- ☐ Prioritized recommendations with rationale

---

## After Research

1. **Review** validation report
2. **Approve** implementation plan
3. **Implement** quick wins
4. **Test** on 10-20 SKUs
5. **Scale** with confidence

---

## Need More Context?

- **Full spec**: `docs/prompts/25-content-generation-optimization.md` (main task)
- **Detailed guide**: `docs/prompts/25-content-generation-optimization-OPTIMIZED.md`
- **Ultra-concise**: `docs/prompts/25-READY-TO-EXECUTE.md`
- **Execution mode**: `docs/prompts/EXECUTION-MODE-GUIDE.md`

---

**Ready?** Paste the command at the top into a new Claude Code session. ⬆️
