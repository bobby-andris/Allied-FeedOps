---
name: collection-storytelling
description: Leverages Allied Brass's 41 named collections as a competitive advantage in content generation. Use when generating product descriptions, titles, or any content where the product belongs to a collection. ALWAYS use this before writing content that could benefit from collection identity — coordinated design is Allied Brass's strongest differentiator vs Kingston Brass, Moen, and Delta. Also use when creating cross-sell copy, "complete the look" content, or collection landing page copy.
---

# Collection Storytelling for Content Generation

Allied Brass has 41 named collections, each with a distinct design language. No competitor at this price tier offers coordinated bathroom accessory collections — Kingston Brass, Moen, and Delta sell individual pieces, not design systems. This is a genuine and under-leveraged competitive moat.

## Why Collections Matter for Content

- **Coordinated design is a premium buyer expectation.** Shoppers searching "matching bathroom accessories" or "coordinated bathroom hardware set" are high-intent buyers willing to pay more for pieces that work together. They're solving the "will this match?" anxiety that kills conversions.
- **"Complete the look" is one of the strongest conversion hooks in home decor.** KBB trade research confirms accessory bundles increase average transaction value. A towel bar buyer who discovers a matching toilet paper holder, robe hook, and mirror in the same collection buys 3-4 pieces instead of 1.
- **Collections solve the subtle mismatch problem.** Two "brushed nickel" pieces from different brands often look visibly different under bathroom lighting. Single-collection sourcing eliminates this — every piece is guaranteed finish-matched.
- **Competitors don't offer this.** Delta markets around faucet collections but doesn't extend into accessories. Moen leads with tech innovation, not coordinated design. Nobody at Allied Brass's price tier offers 41 complete collections across 28 finishes.
- **The Allied Brass website has zero collection-level editorial copy.** Collection pages show products with no design story, no aesthetic description, no "complete the room" language. Content generation is the primary place to communicate collection identity.

## Collection Profiles

### Runtime Config

Detailed per-collection profiles (design aesthetic, style category, target buyer, content integration examples) are maintained in the runtime YAML config:

**`src/feedops/config/collection_stories.yaml`**

This file is loaded by `prompt_builder.py` and injected per-collection into the LLM prompt. Read it when you need specific collection details.

### Quick Reference — Collection Tiers by Product Count

**Tier 1 (3,000+ variants):** Clearview, Pacific Grove, Dottingham, Waverly Place, Prestige Regal, Prestige Skyline, Carolina, Carolina Crystal
**Tier 2 (1,200-3,000):** Pacific Beach, Que New, Monte Carlo, Mercury, Pipeline, Satellite Orbit Two, Montero, Prestige Que New, Prestige Monte Carlo, Southbeach, Continental, Fresno, Venus, Retro Dot, Retro Wave
**Tier 3 (<1,200):** Satellite Orbit One, Remi, Skyline, Washington Square, Astor Place, Tribecca, Tango, Sag Harbor, Soho, Shadwell, Mambo, Foxtrot, Regal, Bolero, Dayton, Malibu, Argo, Essex

### Style Categories

| Category | Collections |
|----------|-------------|
| **Traditional/Classic** | Carolina, Carolina Crystal, Essex, Monte Carlo, Prestige Monte Carlo, Prestige Regal, Regal, Retro Dot, Retro Wave |
| **Transitional** | Astor Place, Continental, Dottingham, Mercury, Prestige Que New, Que New, Soho, Washington Square, Waverly Place |
| **Contemporary/Modern** | Argo, Dayton, Fresno, Montero, Remi, Southbeach, Tribecca, Venus |
| **Contemporary Specialty** | Bolero, Clearview, Foxtrot, Malibu, Mambo, Pacific Beach, Pacific Grove, Pipeline, Prestige Skyline, Sag Harbor, Satellite Orbit One, Satellite Orbit Two, Shadwell, Skyline, Tango |

## Collection Integration Patterns

Five natural ways to weave collection identity into product content:

### 1. Opening Hook
Place collection name in the first sentence to establish design context immediately.

> "Part of the Carolina Collection, this 18-inch towel bar brings traditional warmth to your bathroom with meticulously turned posts and grooved backplates."

Best for: Shopify descriptions where you have room to set the scene.

### 2. Closing Coordination
End with a coordination call-to-action that encourages multi-piece purchases.

> "Coordinates with other Waverly Place Collection pieces — towel rings, robe hooks, and toilet paper holders — for a unified bathroom aesthetic."

Best for: Google/Bing descriptions where the opening must lead with product specs.

### 3. Design Story
Embed the collection's aesthetic narrative mid-description.

> "The Montero Collection draws from mid-century modern geometry — bold square backplates and rectangular posts that make a confident architectural statement."

Best for: Shopify descriptions for design-forward collections (Montero, Pipeline, Remi, Tribecca).

### 4. Problem-Solution
Address the mismatch anxiety directly, with the collection as the answer.

> "Tired of mismatched bathroom accessories? The Waverly Place Collection ensures every piece — from towel bars to mirrors — shares the same grooved contemporary detailing in your chosen finish."

Best for: Shopify descriptions targeting renovators. Very high conversion hook.

### 5. Subtle Mention
Light touch for character-limited contexts.

> "...in the signature clean lines of the Continental Collection."

Best for: Google Shopping titles and short descriptions where every character counts.

## When NOT to Mention Collections

- **Google Shopping titles where character count is critical** — product type and dimensions take priority over collection name. Use collection in description, not title, unless there's room.
- **If no collection data exists for the product** — never infer or invent collection references.
- **If the collection name adds no design context** — some collection names (like "Soho") are evocative on their own; others benefit from description.
- **Don't force collection mentions** — if the sentence reads better without it, leave it out. Natural > comprehensive.
- **Variant finish sentences** — these are already tight on characters. Collection mention is lower priority than finish description.

## Cross-Selling Language

Suggest related products WITHOUT being pushy. These hooks work because they help the shopper, not because they push inventory.

**Explicit coordination:**
- "Pairs beautifully with the matching towel ring and robe hook from the same collection."
- "Part of a full bathroom accessory collection — towel bars, hooks, shelves, and mirrors in 28 coordinated finishes."

**Design system framing:**
- "One of over 20 pieces in the [Collection] design system — everything you need to outfit a complete bathroom."
- "Designed to coordinate with matching accessories in the same finish, from the same collection."

**Problem-solving framing:**
- "No more mixing brands and hoping finishes match — every [Collection] piece is guaranteed to coordinate."
- "Complete the room with one collection, one finish, one design language."

**Subtle hooks:**
- "Also available: matching towel ring, robe hook, and toilet paper holder."
- "Explore the full [Collection] Collection for a coordinated bathroom."

## Integration with Existing Pipeline

### How Collection Data Flows

1. `collection_descriptions.py` loads the 41-collection CSV and provides `get_collection_description(name)` → raw description text
2. `collection_stories.yaml` provides storytelling guidance per collection (aesthetic, style, target buyer, integration examples)
3. `prompt_builder.py` injects collection context into the dynamic user prompt per-SKU
4. The LLM weaves collection identity into generated content

### What This Skill Supplements

- **`collection_descriptions.py`** provides factual collection descriptions (what the collection looks like)
- **`collection_stories.yaml`** provides storytelling guidance (how to talk about the collection in content)
- **`brand_voice.yaml`** provides overall brand voice rules (applies to all content)
- **`storytelling_patterns.yaml`** provides per-category narrative frameworks (towel bars, grab bars, etc.)

Collection storytelling intersects with all of these — it's the layer that connects product-level content to collection-level design identity.
