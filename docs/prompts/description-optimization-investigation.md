# Description Optimization Investigation

**Copy the prompt below into a new Claude Code chat.**

---

## The Prompt

```
## The Problem

Allied Brass sells premium bathroom hardware ($60-$150) competing against Amazon ($15-$30). Our descriptions score 90% internally but read like spec sheets and don't justify the premium price.

Example (shower basket BSK-275LA):
"This 18.75-inch wall-mounted shower basket is crafted from solid brass... Available in Antique Brass. Antique Brass features a softened, aged golden patina..."

Problems: Opens with dimensions, awkward finish injection, doesn't answer "why pay 4x more?"

## Your Mission (Do These In Order)

### Phase 1: Read Context
Read @docs/prompts/description-optimization-context.md for critical background on:
- Master SKU vs Variant SKU architecture (CRITICAL - understand this first)
- The 28 finishes and why they matter
- MCP servers available and their IDs

Then read @CLAUDE.md for project defaults.

### Phase 2: Gather Real Data
Use Google Ads MCP (customer ID: 6253381786) to find:
- What do people ACTUALLY search for shower caddies? ("shower basket" vs "shower caddy"?)
- Do people search for specific finishes? ("matte black towel bar")
- What queries get impressions but no clicks? (reveals gaps)

Query Shopify Dev MCP for:
- Which finishes sell best?
- Which have highest conversion rates?

### Phase 3: Analyze Current System
Read these files:
- @src/feedops/pipeline/prompts.py (lines 134-200) - current LLM prompt
- @src/feedops/pipeline/finish_injection.py - current finish injection (IT'S BROKEN)
- @dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json - current output

Identify what's causing robotic output.

### Phase 4: Create Framework
Create a simple framework (3-5 principles, NOT 15 rules) for descriptions that:
1. Open with benefit, not specs
2. Answer buyer questions (Will it rust? Why pay more?)
3. Justify the premium price
4. Work for BOTH:
   - Master descriptions (Shopify, finish-neutral)
   - Variant descriptions (Google/Bing, finish-specific)

### Phase 5: Fix Finish Injection
Recommend how to fix the awkward finish injection:
- How should master descriptions be structured?
- How should finish content be incorporated in variants?
- Should different finishes have different selling points?

### Phase 6: Prove It Works
Write TWO descriptions for BSK-275LA:
1. **Master (Shopify)**: Finish-neutral, works for all 28 finishes
2. **Variant (Google/Bing)**: Antique Brass, finish is a selling point

Validate: Would YOU click the variant over a $20 Amazon option?

## Deliverables

1. Search intent findings (with data)
2. Finish popularity findings (with data)
3. Framework (3-5 principles for master AND variant)
4. Finish injection recommendations
5. Proof of concept descriptions (master + variant)
6. Exact prompt changes for @src/feedops/pipeline/prompts.py (copy-paste ready)

## Key Constraints

- Use REAL DATA from MCP servers, not assumptions
- Master descriptions must be finish-neutral
- Variant descriptions should make finish a selling point
- First 150 chars matter most (Shopping ad snippet)
- Framework must work across 40+ product categories

## Success Test

Not "does it score 90% internally."

Real test: "Would a shopper comparing this $80 Antique Brass shower basket to a $20 Amazon one click ours AND feel confident buying it?"
```

---

## If You Run Out of Context

If the chat gets long, you can continue in a new chat with this follow-up prompt:

```
Continue the description optimization investigation.

Previous findings: [paste key findings from previous chat]

Remaining tasks:
- [list what's left to do]

Read @docs/prompts/description-optimization-context.md for background.
```
