# Description Optimization - Detailed Context

This document contains detailed context for the description optimization investigation. Read sections as needed - don't try to load everything at once.

---

## Master SKU vs Variant SKU Architecture

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

---

## The 28 Finishes (Competitive Advantage)

Allied Brass offers 28 finishes - far more than most competitors. See `@data/finishes.txt` for the complete list with images.

**Traditional metallic finishes:**
Antique Brass, Antique Bronze, Brushed Bronze, Polished Brass, Polished Chrome, Polished Nickel, Satin Brass, Satin Chrome, Satin Nickel, Oil Rubbed Bronze, Venetian Bronze, Antique Copper, Antique Pewter, Unlacquered Brass

**Unique color finishes (major differentiator):**
Matte Black, Matte White, Matte Gray, Pink, Fire Engine Red, Lavender, Mediterranean Blue, Golden Yellow, Sea Foam Green, Flat Troll Blue, Autumn Sparkle, Glokzin Teal, Shaded Beige, Spanish Gold

**Current finish metadata:**
`@data/finish-metadata.json` has AI-generated finish descriptions but needs improvement.

---

## Allied Brass Differentiators

Why pay $80 instead of $20 for an Amazon product?

1. **Solid brass construction** - Won't rust, outlasts plastic/chrome-plated steel
2. **Lifetime warranty** - Risk-free purchase
3. **28 designer finishes** - Coordinates with any bathroom, more options than competitors
4. **Assembled in Virginia, USA**
5. **Unique color options** - Pink, Lavender, etc. that competitors don't offer

---

## Technical Files Reference

| File | Purpose |
|------|---------|
| `@CLAUDE.md` | Project context, MCP server defaults |
| `@src/feedops/pipeline/prompts.py` | Current LLM prompt (lines 134-200) |
| `@src/feedops/pipeline/finish_injection.py` | Current finish injection (BROKEN) |
| `@data/finishes.txt` | All 28 finishes with image URLs |
| `@data/finish-metadata.json` | Finish descriptions (needs improvement) |
| `@dashboard_data/lifestyle-eval-candidate/google-patch-BSK-275LA.json` | Current output example |

---

## MCP Servers Available

| Server | Customer ID / Property | Use For |
|--------|----------------------|---------|
| Google Ads MCP | 6253381786 | Search term data, shopping performance |
| Google Analytics MCP | Allied Brass - GA4 (Old) | Traffic and behavior data |
| Shopify Dev MCP | - | Sales data, variant performance |
| Supabase MCP | qezuszwufortkiutlhym | Internal data |

---

## Character Limits

- **Google**: Up to 5,000 chars allowed, but first ~150 chars show in snippet
- **Bing**: Similar flexibility, more literal keyword matching
- **First 150 chars are critical** - that's what shows in Shopping ads

---

## What Good Looks Like

### Master Description (Shopify) - Finish Neutral
Should work for someone browsing all 28 finish options. Answers "why this product" not "why this finish."

### Variant Description (Google/Bing) - Finish Specific
The finish should be a SELLING POINT, not an awkward addition. Example approaches:
- "The Antique Brass finish adds vintage charm to this rust-proof shower caddy..."
- Lead with finish for popular finish searches ("matte black towel bar")

---

## Common Buyer Questions (Bathroom Hardware)

1. Will it rust in my shower?
2. Will it hold my tall shampoo bottles?
3. Will it match my other bathroom fixtures?
4. Is it hard to install?
5. Why is this $80 when Amazon has one for $20?
