# Description Optimization Investigation Prompt

Use this prompt in a **new Claude Code chat** to investigate and fix our product descriptions using real data and fresh perspective.

---

## The Prompt

```
## The Problem

Allied Brass sells premium bathroom hardware ($60-$150) competing against Amazon products ($15-$30). Our product descriptions score 90% on internal quality metrics, but they read like database exports - and we have no evidence they actually drive clicks or sales.

Example of what we're producing (shower basket, SKU: BSK-275LA):

"This 18.75-inch wall-mounted shower basket is crafted from solid brass for lasting bathroom storage. Available in Antique Brass. Antique Brass features a softened, aged golden patina..."

This description:
- Opens with dimensions instead of benefits
- Doesn't answer why someone should pay $80 instead of $20
- Uses "shower basket" when people might search "shower caddy"
- Reads like a spec sheet, not a reason to buy

## The Real Question

Are we optimizing for the wrong thing? We've been focused on "attribute density for algorithm matching" when we should probably focus on "answering what the buyer actually needs to know before spending $80."

## Your Mission

### Phase 1: Discover What People Actually Search

Use the Google Ads MCP to get REAL search data (customer ID: 6253381786).

Query the shopping_performance_view:
- What exact queries lead to clicks on shower caddies/baskets?
- What queries get impressions but NO clicks? (These reveal gaps)
- Do people search "shower basket" or "shower caddy" or "shower organizer"?

Don't assume. Verify.

If Google Ads data is limited, use WebSearch to research:
- Top search terms for shower storage products
- What language do actual product listings use?
- How do top-ranked competitors describe similar products?

### Phase 2: Understand Why Someone Would Pay $80

Allied Brass is premium-priced. A buyer comparing options is asking:
1. Why is this $80 when Amazon has one for $20?
2. Will it rust in my shower? (The #1 complaint about cheap caddies)
3. Will it actually hold my tall shampoo bottles?
4. Will it match my other bathroom fixtures?
5. Is it hard to install?

Allied Brass's real differentiators:
- Solid brass construction (won't rust, outlasts plastic/chrome-plated steel)
- Lifetime warranty (risk-free purchase)
- 28 designer finishes (coordinates with any bathroom)
- Assembled in Virginia, USA

Current descriptions bury these or don't mention them at all.

### Phase 3: Understand What Actually Gets Clicked

In Google Shopping, only the first ~150 characters show in the ad snippet. Everything after is invisible until someone clicks through.

This means:
- The first sentence must hook AND inform
- Burying the value proposition at character 400 is useless
- The snippet must answer: "Why should I click THIS one?"

Analyze: What do the first 150 characters of top-performing competitor listings say?

### Phase 4: Create a Simple Framework (Not Rules)

Our current prompt has 15+ mechanical rules like "First sentence: product type + ONE key dimension + material." This creates compliance-seeking behavior that produces robotic output.

Instead, create a FRAMEWORK of 3-5 principles that:
1. Opens with benefit/outcome, not specs
2. Answers the buyer's top questions early
3. Justifies the premium price with concrete proof
4. Uses actual search terms (validated by data)
5. Works within constraints:
   - Google: 600-800 chars total, first 150 chars critical
   - Bing: 700-1000 chars, more literal matching
   - Descriptions are "finish-neutral" - a separate system injects finish details

### Phase 5: Prove It Works

Rewrite the BSK-275LA (shower basket) description using your framework.

Then validate:
1. Does the first 150 chars answer "why click this one?"
2. Does it contain the search terms people ACTUALLY use? (Verify against Phase 1 data)
3. Does it answer the top 3 buyer questions?
4. Does it justify paying 4x the Amazon price?
5. **Would YOU click this instead of the $20 Amazon option?**

Compare your version against the current one. Be specific about what's better and why.

## Technical Context

Read these files:
- @CLAUDE.md - Project context, MCP server defaults
- @src/feedops/pipeline/prompts.py - Current LLM prompt (focus on lines 134-200)
- @dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json - Current output
- @src/feedops/pipeline/finish_injection.py - How finish details get added (descriptions start finish-neutral)

Important: The generation pipeline writes a "finish-neutral" base description, then finish_injection.py adds finish-specific content. Your framework must account for this.

## Deliverables

1. **Search Intent Analysis**: What do people actually search? Evidence from Google Ads or research.

2. **Buyer Psychology Summary**: The 3-5 questions that must be answered, specific to bathroom hardware buyers comparing premium vs budget options.

3. **New Framework**: 3-5 principles (not 15 rules) for writing descriptions that drive clicks and conversions.

4. **Proof of Concept**: Rewritten BSK-275LA description with explanation of why it's better.

5. **Exact Prompt Changes**: The specific text to replace in @src/feedops/pipeline/prompts.py (lines 136-152). This must be copy-paste ready.

## Success Metric

Not "does it score well on our internal metrics."

The real test: **"Would a shopper comparing this $80 shower basket to a $20 Amazon one click ours AND feel confident buying it?"**

## Constraints

- Use REAL DATA. Don't assume what people search - verify it.
- Keep it simple. More rules = more robotic output.
- The description must work for a HUMAN first, algorithm second.
- Must be adaptable across 40+ product categories (not just shower baskets).
- Descriptions are finish-neutral, then get finish injected - don't bake in finish details.

## What NOT To Do

- Don't just add more rules to the existing prompt
- Don't stuff keywords unnaturally
- Don't lead with dimensions or specs
- Don't write marketing fluff ("premium quality", "elegant design")
- Don't assume you know what people search - verify with data
```

---

## Why This Prompt Works

1. **Frames the REAL problem**: Premium product competing on price, not just "descriptions sound robotic"

2. **Forces data validation**: Every assumption must be verified with Google Ads or research

3. **Focuses on the buyer's decision**: "Why pay $80 instead of $20?" is the actual question

4. **Emphasizes the snippet**: First 150 characters matter most - this is often ignored

5. **Asks for framework, not rules**: Principles > mechanical rules

6. **Has a real success metric**: "Would you click this over the Amazon option?"

7. **Includes technical constraints**: Character limits, finish injection, multi-category needs

8. **Clear deliverables**: Search analysis, framework, proof of concept, exact prompt changes

## After Running This Investigation

The new chat should produce:
1. Evidence-based insights on search behavior
2. A simple framework (3-5 principles)
3. A rewritten description that proves the framework works
4. Copy-paste-ready prompt changes for prompts.py

Review their recommendations, then decide what to implement.
