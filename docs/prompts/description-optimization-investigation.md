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
- Has awkward finish injection: "Available in Antique Brass. Antique Brass features..."
- Reads like a spec sheet, not a reason to buy

## The Real Question

Are we optimizing for the wrong thing? We've been focused on "attribute density for algorithm matching" when we should probably focus on "answering what the buyer actually needs to know before spending $80."

---

## CRITICAL: Master SKU vs Variant SKU Architecture

Before you do anything, you MUST understand this architecture:

### Master SKU (e.g., BSK-275LA)
- The base product WITHOUT a specific finish
- Used for **Shopify product pages** where users can toggle between all 28 finishes on ONE URL
- Description must be **finish-neutral** because it applies to ALL 28 finishes
- Example: User visits one Shopify page, clicks through Antique Brass, Matte Black, Polished Chrome - same description shows for all

### Variant SKU (e.g., BSK-275LA-ABR)
- A specific finish variant (ABR = Antique Brass)
- Used for **Google Shopping and Bing** where each variant is a SEPARATE product listing
- Each variant has its own GMC ID (Google Merchant Center ID)
- Example: Google Shopping shows 28 separate listings for BSK-275LA, one for each finish

### The Current Flow
1. LLM generates ONE finish-neutral description (for Master SKU / Shopify)
2. `finish_injection.py` creates 28 variant descriptions by adding finish-specific content
3. Google/Bing receive the variant descriptions (with finish injected)
4. Shopify receives the master description (finish-neutral)

### The Same Logic Applies to Titles
- Master title (Shopify): "Wall-Mounted Shower Basket, Solid Brass, 18.75-Inch | Allied Brass"
- Variant title (Google/Bing): "Antique Brass Wall-Mounted Shower Basket, Solid Brass, 18.75-Inch | Allied Brass"

### The Finish Injection Problem (CRITICAL)
The current finish injection creates awkward output like:
"Available in Antique Brass. Antique Brass features a softened, aged golden patina..."

This is broken because:
1. The injected content itself is poorly written (repetitive)
2. The injection LOCATION is awkward (no natural transition)
3. The base description doesn't leave a natural place for finish content
4. ALL OF THE ABOVE need to be fixed

### Your Task Regarding Master/Variant
You need to figure out:
1. How should the MASTER description (Shopify) be written? (finish-neutral, works for all 28 finishes)
2. How should VARIANT descriptions (Google/Bing) differ? Should they just swap the finish name, or should different finishes have different selling points?
3. How should finish injection work better? Should the base description have a placeholder? Should finish content be woven in differently?
4. Should certain finishes emphasize specific benefits?
   - Matte Black: "hides water spots and fingerprints"
   - Unlacquered Brass: "develops a natural patina over time"
   - Polished Chrome: "easy to clean, matches most fixtures"

---

## The 28 Finishes (A Competitive Advantage)

Allied Brass offers 28 finishes - far more than most competitors. See @data/finishes.txt for the complete list with images.

**Traditional metallic finishes:**
Antique Brass, Antique Bronze, Brushed Bronze, Polished Brass, Polished Chrome, Polished Nickel, Satin Brass, Satin Chrome, Satin Nickel, Oil Rubbed Bronze, Venetian Bronze, Antique Copper, Antique Pewter, Unlacquered Brass

**Unique color finishes (major differentiator - competitors likely don't have these):**
Matte Black, Matte White, Matte Gray, Pink, Fire Engine Red, Lavender, Mediterranean Blue, Golden Yellow, Sea Foam Green, Flat Troll Blue, Autumn Sparkle, Glokzin Teal, Shaded Beige, Spanish Gold

**Investigation needed:**
- Which finishes are most popular/searched? Query Shopify Dev MCP, Google Ads MCP, or Google Analytics MCP for sales/search data
- Do people search for specific finishes? ("matte black towel bar", "antique brass shower caddy")
- Are the colorful finishes a niche opportunity or a major differentiator?
- Should variant descriptions for unique colors (Pink, Lavender) have different messaging than traditional metallics?

**Current finish metadata:**
There's a @data/finish-metadata.json file with AI-generated finish descriptions, but it needs improvement. You should either:
- Create better finish-specific benefit content
- Or figure out a better way to incorporate finishes into descriptions

---

## Your Mission

### Phase 1: Discover What People Actually Search

Use the Google Ads MCP to get REAL search data (customer ID: 6253381786).

Query the shopping_performance_view:
- What exact queries lead to clicks on shower caddies/baskets?
- What queries get impressions but NO clicks? (These reveal gaps)
- Do people search "shower basket" or "shower caddy" or "shower organizer"?
- Do people search for specific finishes? ("brass shower caddy", "matte black bathroom accessories")

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
- 28 designer finishes (coordinates with any bathroom) - MORE than competitors
- Assembled in Virginia, USA
- Unique color options competitors don't offer

Current descriptions bury these or don't mention them at all.

### Phase 3: Understand What Actually Gets Clicked

In Google Shopping, only the first ~150 characters show in the ad snippet. Everything after is invisible until someone clicks through.

This means:
- The first sentence must hook AND inform
- Burying the value proposition at character 400 is useless
- The snippet must answer: "Why should I click THIS one?"

Analyze: What do the first 150 characters of top-performing competitor listings say?

### Phase 4: Investigate Finish Popularity and Search Behavior

Use available MCP servers to answer:
1. **Shopify Dev MCP**: Which finishes sell best? Which have the highest conversion rates?
2. **Google Ads MCP**: Which finish-related search terms drive clicks? Do people search "matte black towel bar"?
3. **Google Analytics MCP**: Which finish variants get the most traffic?

This data will inform:
- Whether variant descriptions should emphasize finish differently based on popularity
- Whether the colorful finishes (Pink, Lavender, etc.) are worth special messaging
- What finish-related language actually resonates with searchers

### Phase 5: Create a Simple Framework (Not Rules)

Our current prompt has 15+ mechanical rules like "First sentence: product type + ONE key dimension + material." This creates compliance-seeking behavior that produces robotic output.

Instead, create a FRAMEWORK of 3-5 principles that:
1. Opens with benefit/outcome, not specs
2. Answers the buyer's top questions early
3. Justifies the premium price with concrete proof
4. Uses actual search terms (validated by data)
5. Works for BOTH master (Shopify) and variant (Google/Bing) descriptions

**Character limits:**
- Google: Up to 5,000 chars allowed, but determine optimal length based on what drives clicks
- Bing: Similar flexibility, but more literal keyword matching
- First 150 chars are critical (the visible snippet)

### Phase 6: Fix the Finish Injection System

The current `finish_injection.py` creates awkward output. You need to recommend:

1. **For Master/Shopify descriptions**: How to write finish-neutral content that works for all 28 finishes without mentioning any specific finish

2. **For Variant/Google/Bing descriptions**: How finish content should be incorporated:
   - Should the base description have a natural placeholder for finish?
   - Should finish be the opening hook for variants? ("The Antique Brass finish adds vintage charm to this...")
   - Should different finish categories (metallic vs colorful) have different injection patterns?

3. **Better finish content**: Create or recommend improved finish-specific content:
   - What are the actual BENEFITS of each finish? (not just "features a softened patina")
   - Matte Black: practical benefits (hides water spots)
   - Polished Chrome: practical benefits (easy to clean, widely compatible)
   - Colorful finishes: emotional benefits (make a statement, unique style)

### Phase 7: Prove It Works

Rewrite the BSK-275LA (shower basket) description in TWO versions:

**Version 1: Master Description (Shopify)**
- Finish-neutral
- Works for someone browsing all 28 finish options
- Answers "why this product" not "why this finish"

**Version 2: Variant Description (Google/Bing) - Antique Brass**
- Finish-specific
- Demonstrates how finish injection should work
- The finish is a selling point, not an awkward addition

Then validate BOTH:
1. Does the first 150 chars answer "why click this one?"
2. Does it contain the search terms people ACTUALLY use?
3. Does it answer the top 3 buyer questions?
4. Does it justify paying 4x the Amazon price?
5. Is the finish integration natural (for variant) or appropriately neutral (for master)?
6. **Would YOU click this instead of the $20 Amazon option?**

---

## Technical Context

Read these files:
- @CLAUDE.md - Project context, MCP server defaults
- @src/feedops/pipeline/prompts.py - Current LLM prompt (focus on lines 134-200)
- @src/feedops/pipeline/finish_injection.py - Current finish injection system (THIS IS BROKEN)
- @data/finishes.txt - All 28 finishes with image URLs
- @data/finish-metadata.json - Current finish descriptions (AI-generated, needs improvement)
- @dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json - Current output example

**MCP Servers Available:**
- Google Ads MCP (customer ID: 6253381786) - search term data, performance metrics
- Google Analytics MCP (Allied Brass - GA4 Old property) - traffic and behavior data
- Shopify Dev MCP - sales data, product performance by variant
- Supabase MCP (project: qezuszwufortkiutlhym) - internal data

---

## Deliverables

1. **Search Intent Analysis**: What do people actually search? Evidence from Google Ads or research. Include finish-specific search patterns.

2. **Finish Popularity Analysis**: Which finishes sell best? Which are searched most? Data from Shopify/GA/Google Ads.

3. **Buyer Psychology Summary**: The 3-5 questions that must be answered, specific to bathroom hardware buyers comparing premium vs budget options.

4. **New Framework**: 3-5 principles (not 15 rules) for writing descriptions that drive clicks and conversions. Must address BOTH master and variant descriptions.

5. **Finish Injection Recommendations**: How to fix the awkward finish injection. Include:
   - How master descriptions should be structured
   - How variant descriptions should incorporate finish
   - Better finish-specific benefit content

6. **Proof of Concept**: Rewritten BSK-275LA descriptions:
   - Master version (Shopify, finish-neutral)
   - Variant version (Google/Bing, Antique Brass)
   - Explanation of why they're better

7. **Exact Prompt Changes**: The specific text to replace in @src/feedops/pipeline/prompts.py. Must be copy-paste ready.

8. **Finish Injection Code Recommendations**: Specific changes needed for @src/feedops/pipeline/finish_injection.py (if applicable).

---

## Success Metrics

Not "does it score well on our internal metrics."

The real tests:
1. **Master (Shopify)**: "Would someone browsing finishes feel informed enough to pick one and buy?"
2. **Variant (Google/Bing)**: "Would a shopper comparing this $80 Antique Brass shower basket to a $20 Amazon one click ours AND feel confident buying it?"

---

## Constraints

- Use REAL DATA. Don't assume what people search - verify it.
- Keep it simple. More rules = more robotic output.
- The description must work for a HUMAN first, algorithm second.
- Must be adaptable across 40+ product categories (not just shower baskets).
- Master descriptions MUST be finish-neutral (no specific finish mentioned).
- Variant descriptions should make the finish a SELLING POINT, not an awkward addition.
- The 28 finishes (especially unique colors) are a competitive advantage - figure out how to leverage this.

---

## What NOT To Do

- Don't just add more rules to the existing prompt
- Don't stuff keywords unnaturally
- Don't lead with dimensions or specs
- Don't write marketing fluff ("premium quality", "elegant design")
- Don't assume you know what people search - verify with data
- Don't write finish content that sounds like "Antique Brass features a softened patina" - that's not a benefit, it's a description
- Don't ignore the master/variant distinction - they serve different purposes
```

---

## Why This Prompt Works

1. **Frames the REAL problem**: Premium product competing on price, not just "descriptions sound robotic"

2. **Explains the architecture**: Master vs Variant SKU distinction is critical and fully explained

3. **Forces data validation**: Every assumption must be verified with MCP servers

4. **Focuses on the buyer's decision**: "Why pay $80 instead of $20?" is the actual question

5. **Addresses finish injection**: The awkward finish problem is called out with clear expectations

6. **Emphasizes the snippet**: First 150 characters matter most

7. **Asks for framework, not rules**: Principles > mechanical rules

8. **Identifies the competitive advantage**: 28 finishes, especially unique colors

9. **Has real success metrics**: Different for master (Shopify) vs variant (Google/Bing)

10. **Clear deliverables**: 8 specific outputs including both description types

---

## After Running This Investigation

The new chat should produce:
1. Evidence-based insights on search behavior (including finish-specific)
2. Finish popularity data from Shopify/GA/Google Ads
3. A simple framework (3-5 principles) for both master and variant descriptions
4. Rewritten descriptions proving the framework works (master AND variant)
5. Finish injection recommendations
6. Copy-paste-ready prompt changes for prompts.py
7. Recommendations for finish_injection.py improvements

Review their recommendations, then decide what to implement.
