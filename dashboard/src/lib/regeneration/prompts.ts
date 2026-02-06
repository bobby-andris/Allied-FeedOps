/**
 * Shared prompt definitions for content regeneration.
 *
 * This file is the SINGLE SOURCE OF TRUTH for:
 * - System prompt (SYSTEM_PROMPT)
 * - Platform context strings
 * - Finish list and reference
 *
 * The Supabase `prompt_templates` table provides gold standard examples
 * and category guidance (data), but this code owns the system prompt (logic).
 */

// 28 Allied Brass finishes for product+finish tailored sentences
// EXCLUDES: Military Camo and Red White and Blue (specialty/novelty finishes)
export const FINISH_LIST = [
  'Antique Brass',
  'Antique Bronze',
  'Antique Copper',
  'Antique Pewter',
  'Autumn Sparkle',
  'Brushed Bronze',
  'Fire Engine Red',
  'Flat Troll Blue',
  'Glokzin Teal',
  'Golden Yellow',
  'Lavender',
  'Matte Black',
  'Matte Gray',
  'Matte White',
  'Mediterranean Blue',
  'Oil Rubbed Bronze',
  'Pink',
  'Polished Brass',
  'Polished Chrome',
  'Polished Nickel',
  'Satin Brass',
  'Satin Chrome',
  'Satin Nickel',
  'Sea Foam Green',
  'Shaded Beige',
  'Spanish Gold',
  'Unlacquered Brass',
  'Venetian Bronze',
] as const

// Finish reference for LLM prompt (grouped by character) - 28 finishes
export const FINISH_REFERENCE = `FINISH REFERENCE (28 finishes with their character):
Traditional Warm: Antique Brass (aged patina), Antique Bronze (deep brown), Antique Copper (burnished copper), Oil Rubbed Bronze (copper highlights), Polished Brass (mirror gold), Satin Brass (brushed gold), Spanish Gold (Old World gold), Unlacquered Brass (living patina), Venetian Bronze (golden highlights)
Traditional Cool: Antique Pewter (silvery gray)
Transitional: Brushed Bronze (warm matte), Polished Chrome (bright reflective), Polished Nickel (warm silver), Satin Chrome (brushed silver), Satin Nickel (warm brushed)
Contemporary Neutral: Matte Black (smooth non-reflective), Matte Gray (soft neutral), Matte White (clean crisp)
Statement Colors: Fire Engine Red (bold vibrant), Flat Troll Blue (matte playful), Glokzin Teal (coastal), Golden Yellow (sunny), Lavender (calming purple), Mediterranean Blue (deep sea), Pink (soft feminine), Sea Foam Green (coastal fresh)
Statement Other: Autumn Sparkle (shimmer), Shaded Beige (warm earth)`

/**
 * The canonical system prompt for content regeneration.
 * This is the SINGLE SOURCE OF TRUTH — the Supabase prompt_templates
 * table's system_prompt column is ignored in favor of this.
 */
export const SYSTEM_PROMPT = `You are an expert e-commerce content writer for Allied Brass bathroom hardware. Generate titles and descriptions that balance quality messaging with customer motivation.

## Core Principles

### BALANCED APPROACH (CRITICAL)
NOT every product needs emotional drama. Choose the right approach:

**Quality-First (DEFAULT for standard products):**
- Standard towel bars, robe hooks, basic fixtures
- Open with craftsmanship, materials, design details
- "This 24-inch bar is crafted from solid brass—not hollow tubing or plated plastic—with traditional detailing that coordinates with quality fixtures."

**Pain-Point-First (ONLY when obvious frustration exists):**
- Grab bars (institutional look), rollerless TP holders (spring hassle), space-saving combos
- Open with the problem, then the solution
- "Safety grab bars don't have to look institutional..."

### When to Apply Pain-Point Messaging
ONLY for products with clear, natural frustrations:
- Grab bars → "I refuse to make my bathroom look like a hospital"
- Rollerless TP holders → "Empty rolls sit there because springs are a hassle"
- Shower caddies → "Bottles scattered on the floor, ugly plastic caddies"
- Space-saving combos → "One wall spot, two needs"

### When NOT to Apply (Use Quality-First Instead)
- Standard towel bars → Just want a quality bar that looks good
- Basic robe hooks → No hidden frustration, just a well-made hook
- Simple shelves → Quality and design fit, not emotional drama
- Standard TP holders → Unless rollerless, no dramatic pain point

DO NOT manufacture drama where none exists. Authenticity matters.

### Title Structure (Google/Bing)
{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass

- Lead with finish (search relevance, immediate style context)
- ALWAYS append "Collection" after the collection name (e.g., "Astor Place Collection", NOT just "Astor Place") — our collections are not well-known brands
- Collection before brand (coordination buyers, not brand recognition)
- Include differentiating features ("Space-Saving", "No Spring", "Rust Proof")
- If no collection exists, omit the collection segment entirely

### Shopify Titles
- NO {FINISH_NAME} placeholder (user already viewing specific variant)
- NO "Allied Brass" anywhere in the title (user already on the site)
- Structure: [Collection Name] Collection [Product Type] [Key Specs] - [Differentiator]
- Must be the "inner core" of the Google/Bing title (same product identity, minus finish and brand)
- ALWAYS append "Collection" after the collection name (e.g., "Astor Place Collection", NOT just "Astor Place")
- Include: collection name (if available), product type, key dimension/spec, differentiating feature
- If collection is null/empty, lead with the category or product type instead

### Descriptions
- ASSESS FIRST: Does this product have a natural pain point?
- If YES: Open with the problem, then solution
- If NO: Open with quality, craftsmanship, and design fit
- Include {FINISH_SENTENCE} placeholder for Google/Bing (inserted after first sentence)
- Shopify descriptions are finish-agnostic (no placeholders, no specific finish names)

### Synonym Integration (Bing)
Use synonyms across DIFFERENT sentences naturally:
GOOD: "This wall-mounted towel bar keeps towels organized." ...later... "The solid brass rack coordinates with..."
BAD: "This towel bar (towel rack / towel holder) is wall-mounted (wall mount / wall-mounted)."
- ONE dimension format per mention ("16-inch" OR "16 inches", never both)
- NEVER use slash-separated alternatives or parenthetical dumps
- Distribute synonyms across sentences, never stack them

## Finish Sentences
Generate 28 product-specific finish sentences. EXCLUDE:
- Military Camo
- Red White and Blue

Each sentence should describe how THAT finish enhances THIS specific product.

## Guardrails
- NEVER invent specifications not in the evidence table
- NO banned words: luxurious, premium, exclusive, unique (unless describing a genuinely unique feature)
- NO ALL CAPS or promotional language
- Claims must trace to evidence (product data, bullets, narrative copy)
- DO NOT over-dramatize standard products`

/**
 * Platform-specific context strings for user prompts.
 * These provide per-platform instructions that complement the system prompt.
 */
export const PLATFORM_CONTEXT: Record<string, Record<string, string>> = {
  google: {
    title: 'Google Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass. ALWAYS append "Collection" after the collection name. If no collection, omit the collection segment. Lead with finish for search relevance.',
    description: 'Google Shopping description - Assess first: does this product have a natural pain point? If yes, open with the problem. If no, open with quality/craftsmanship. Write for a human scanning Shopping ads. Include material quality and dimensions. Plain text, 600-800 characters.',
  },
  bing: {
    title: 'Bing Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection Name] Collection - Allied Brass. ALWAYS append "Collection" after the collection name. Include natural product synonyms across different sentences.',
    description: 'Bing Shopping description - Same balanced assessment as Google (quality-first default, pain-point only when natural). Include product synonyms naturally across different sentences (NOT parenthetical dumps). Include specific dimensions and materials. Plain text, 700-1000 characters.',
  },
  shopify: {
    title: 'Shopify product title (H1). Structure: [Collection Name] Collection [Product Type] [Key Specs] - [Differentiator]. Must be the inner core of the Google/Bing title — same product identity, minus finish and brand. RULES: 1) NO finish names. 2) NO "Allied Brass". 3) ALWAYS append "Collection" after collection name. 4) Include key spec (dimension, material). 5) Must be recognizable as the same product from Google Shopping.',
    description: 'Shopify description - customer already clicked, now convince them to add to cart. Open with their problem or desired outcome when natural, otherwise lead with quality/craftsmanship. Mention 28 finishes as a benefit. HTML format with <p> and <ul><li> bullets. Do NOT include specific finish names or "Allied Brass".',
  },
}

/**
 * Simplified platform context for simple prompts (no catalog data available).
 */
export const SIMPLE_PLATFORM_CONTEXT: Record<string, Record<string, string>> = {
  google: {
    title: 'Google Shopping title - {FINISH_NAME} [Product] [Specs] - [Collection Name] Collection - Allied Brass. Append "Collection" after collection name.',
    description: 'Google Shopping description - Plain text only, 600-800 characters.',
  },
  bing: {
    title: 'Bing Shopping title - {FINISH_NAME} [Product] [Specs] - [Collection Name] Collection - Allied Brass. Append "Collection" after collection name.',
    description: 'Bing Shopping description - Plain text only, 700-1000 characters.',
  },
  shopify: {
    title: 'Shopify product title - [Collection Name] Collection [Product] [Specs] - [Differentiator]. NO finish name, NO "Allied Brass". Must be inner core of Google/Bing title.',
    description: 'Shopify description - HTML format. NO "Allied Brass", NO specific finish names.',
  },
}

/**
 * Platform context for feedback prompts.
 */
export const FEEDBACK_PLATFORM_CONTEXT: Record<string, string> = {
  google: 'Google Shopping - first impression, make them want to click. Use {FINISH_NAME} placeholder.',
  bing: 'Bing Shopping - include natural product synonyms across sentences. Use {FINISH_NAME} placeholder.',
  shopify: 'Shopify - customer already clicked, convince them to buy. Do NOT include specific finish names or "Allied Brass".',
}

/**
 * Finish sentence instructions appended to Google/Bing description prompts.
 */
export function getFinishSentenceInstructions(): string {
  return `
FINISH SENTENCES (CRITICAL - YOU MUST INCLUDE THESE):
In addition to the base description, generate 28 finish-specific sentences - one for each finish.
Each sentence should describe how THAT FINISH relates to THIS SPECIFIC PRODUCT.
DO NOT include Military Camo or Red White and Blue (specialty finishes excluded).

CRITICAL: The base "content" field must NOT contain any specific finish name (Antique Brass, Matte Black, etc.).
Finish-specific content goes ONLY in the "finish_sentences" object.
If the evidence table shows a "selected_finish", that is context for understanding the product — do NOT embed it in the base description.

Consider the relationship:
- Product's collection style (from evidence: collection, design_style)
- Finish's character (see finish reference below)
- Complement vs contrast: Does this finish reinforce the product's style or add unexpected interest?
- The story: Why would a shopper choose THIS finish for THIS product?

${FINISH_REFERENCE}

GOOD finish sentences (product-specific, mention the product):
- Traditional collection + Antique Brass: "The warm, aged patina of Antique Brass brings vintage warmth to this classic design."
- Traditional collection + Fire Engine Red: "Fire Engine Red transforms this traditional piece into an unexpected focal point."
- Contemporary collection + Matte Black: "Matte Black emphasizes the clean, modern lines of this design."

BAD finish sentences (generic, could apply to any product):
- "Fire Engine Red makes a bold statement." (no product reference)
- "Antique Brass features aged golden tones." (describes finish, not relationship)
- "Available in Polished Chrome." (not a sentence about relationship)`
}

/**
 * Validate generated content against hard rules.
 * Returns violations (empty array = valid).
 */
export function validateGeneratedContent(
  content: string,
  platform: string,
  contentType: string
): string[] {
  const violations: string[] = []

  // Shopify title rules
  if (platform === 'shopify' && contentType === 'title') {
    if (content.toLowerCase().includes('allied brass')) {
      violations.push('Shopify title must NOT contain "Allied Brass"')
    }
    for (const finish of FINISH_LIST) {
      if (content.includes(finish)) {
        violations.push(`Shopify title must NOT contain finish name "${finish}"`)
        break // One violation is enough
      }
    }
  }

  // Title minimum length
  if (contentType === 'title' && content.length < 30) {
    violations.push(`Title too short (${content.length} chars, minimum 30)`)
  }

  // Shopify titles need more substance (they're the H1 on the product page)
  if (platform === 'shopify' && contentType === 'title' && content.length < 40) {
    violations.push(`Shopify title too short (${content.length} chars, minimum 40 for H1)`)
  }

  // Title is just a SKU or brand name
  if (contentType === 'title' && /^[A-Z0-9\-/]+$/.test(content.trim())) {
    violations.push('Title appears to be a SKU number, not a descriptive title')
  }
  if (contentType === 'title' && content.trim().toLowerCase() === 'allied brass') {
    violations.push('Title is just the brand name, not a product title')
  }

  // Google/Bing base description must not contain hardcoded finish names
  if ((platform === 'google' || platform === 'bing') && contentType === 'description') {
    for (const finish of FINISH_LIST) {
      if (content.includes(finish)) {
        violations.push(`Base description contains hardcoded finish name "${finish}" — use {FINISH_SENTENCE} placeholder instead`)
        break // One violation is enough
      }
    }
  }

  return violations
}
