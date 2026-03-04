# TypeScript Content Generation Methodology

This document details the exact methodology implemented in the TypeScript dashboard for generating product titles and descriptions. It serves as a reference for comparing and potentially unifying approaches with the Python pipeline.

## Overview

The TypeScript content generation system lives primarily in:
- `dashboard/src/app/api/regenerate/route.ts` - Main API endpoint
- `dashboard/src/lib/evidence/*` - Evidence table builder (ported from Python)
- `dashboard/src/lib/variant-content.ts` - Variant content composition at display time
- `dashboard/src/lib/finish-data.ts` - 30 finish definitions with marketing descriptions

## Core Philosophy: Context Over Rules

The system uses a **context-driven approach** rather than prescriptive rules:

```
OLD APPROACH (rule-following):
"FIRST SENTENCE PATTERN: [Dimension] [product] in [Finish]..."
→ Robotic, templated output

NEW APPROACH (context-driven):
Provide understanding of WHO is buying, WHY they're buying, WHAT questions they have
→ Let LLM write naturally compelling copy
```

## Architecture: Two-Stage Content Generation

### Stage 1: LLM Generation (via `/api/regenerate`)

Generates **base content** that is finish-agnostic:
- Titles: No specific finish name (finish inserted at display time)
- Descriptions (Google/Bing): Base description + 28 finish-specific sentences
- Descriptions (Shopify): Finish-agnostic (Shopify shows all finishes on one page)

### Stage 2: Display-Time Composition (via `variant-content.ts`)

Combines base content with finish-specific information:
- Titles: Simple insertion of finish name
- Descriptions: Insert product+finish tailored sentence after first sentence

## The Regeneration API Flow

### 1. Request Structure

```typescript
interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  feedback?: {
    current_content: string
    user_feedback: string
    feedback_type?: FeedbackPreset
  }
}
```

### 2. Evidence Table Building

If product exists in `product_catalog`, builds rich evidence table:

```typescript
const evidenceResult = await getProductEvidence(supabase, master_sku, {
  platform,
  finish_code,
})
```

Evidence includes:
- **Core**: master_sku, category, collection, current_title, current_description
- **Features**: bullet_1 through bullet_6
- **Attributes**: material, style, shape, orientation, mounting_type
- **Dimensions**: product_length, product_height, product_width, projection, weight_capacity
- **Finishes**: available_finishes (comma-separated), finish_count
- **Enrichment**: design_style, feature_benefits, room_context, competitive_edge, warranty

Evidence is formatted as markdown table for the LLM prompt.

### 3. System Prompt (Context-Driven)

```typescript
const SYSTEM_PROMPT = `You are a product content writer for Allied Brass bathroom and kitchen hardware.
Create content that helps buyers understand why this product is worth it.

BEFORE YOU WRITE, THINK ABOUT WHO IS READING THIS:

1. WHO IS SEARCHING FOR THIS PRODUCT?
- A homeowner renovating a bathroom who wants it to look intentional
- A designer specifying fixtures for a client who expects quality
- Someone replacing a broken/ugly product who wants an upgrade

2. WHAT QUESTIONS DO THEY HAVE BEFORE SPENDING $80+?
- "Will this look good in MY bathroom?" → Help them visualize it
- "Will this match my other fixtures?" → Address finish coordination
- "Is this actually better than the $20 Amazon option?" → Explain the value
- "Will this last? Is it quality?" → Provide trust signals

3. WHAT MAKES ALLIED BRASS WORTH IT?
- Style without sacrifice: You don't have to choose between "looks good" and "works well"
- Personalization: 28 finishes to match any bathroom vision
- Innovation: Rollerless TP holders, retractable rods, decorative grab bars
- Durability: Solid brass outlasts plastic and die-cast

PLATFORM CONTEXT:
- Google/Bing (variant): Base content + 28 finish-specific sentences
- Shopify (master): All finishes on one page. Help them choose and buy.

CRITICAL RULES:
- Never invent specifications not in the product data
- Every factual claim must be traceable to the evidence table
- "Allied Brass" should be the final segment in titles
- No ALL CAPS, no promotional language
- Base content should NOT include specific finish names`
```

### 4. Platform-Specific Prompts

#### Google/Bing Descriptions (JSON mode with finish_sentences)

```typescript
const isVariantDescription = contentType === 'description' &&
  (platform === 'google' || platform === 'bing')

if (isVariantDescription) {
  // Request JSON response with finish_sentences
  prompt = `Generate content for this product. You MUST respond with valid JSON.

${evidenceMarkdown}

${FINISH_REFERENCE}

GOOD finish sentences (product-specific):
- Traditional collection + Antique Brass: "The warm, aged patina of Antique Brass brings vintage warmth to this classic design."
- Traditional collection + Fire Engine Red: "Fire Engine Red transforms this traditional piece into an unexpected focal point."

BAD finish sentences (generic):
- "Fire Engine Red makes a bold statement." (no product reference)
- "Antique Brass features aged golden tones." (describes finish, not relationship)

Respond with this EXACT JSON structure:
{
  "content": "The base description text here (no finish names)...",
  "finish_sentences": {
    "Antique Brass": "One sentence relating Antique Brass to this product...",
    ... (all 28 finishes)
  }
}`
  requiresJson = true
}
```

#### Titles and Shopify (plain text)

```typescript
prompt = `Generate a ${contentType} for this product.

CONTEXT: ${platformContext}

${evidenceMarkdown}

CRITICAL: Do NOT include any specific finish name.

Respond with ONLY the ${contentType} text, no additional explanation.`
requiresJson = false
```

### 5. OpenAI API Call

```typescript
const completion = await openai.chat.completions.create({
  model: MODEL, // Default: 'gpt-5.2'
  messages,
  temperature: 0.7,
  ...(requiresJson ? { response_format: { type: 'json_object' } } : {}),
  ...(MODEL.startsWith('gpt-5')
    ? { max_completion_tokens: requiresJson ? 4000 : 1000 }
    : { max_tokens: requiresJson ? 4000 : 1000 }),
})
```

### 6. Vision Support

For descriptions, if main image URL is available:
```typescript
const shouldUseVision = USE_VISION && imageUrl && content_type === 'description'

if (shouldUseVision) {
  messages.push({
    role: 'user',
    content: [
      { type: 'text', text: userPrompt },
      { type: 'image_url', image_url: { url: imageUrl, detail: 'low' } },
    ],
  })
}
```

### 7. Response Parsing and Storage

```typescript
// For JSON mode (Google/Bing descriptions)
if (requiresJson) {
  const parsed = JSON.parse(rawResponse)
  newContent = parsed.content?.trim()
  finishSentences = parsed.finish_sentences || null
}

// Save base content to generated_content table
await supabase.from('generated_content').update({
  candidate_content: newContent,
  version: nextVersion,
  generation_model: MODEL,
  generation_prompt_hash: promptHash,
})

// Save finish sentences to separate table
if (finishSentences && (platform === 'google' || platform === 'bing')) {
  await supabase.from('variant_finish_sentences').upsert({
    master_sku,
    platform,
    finish_sentences: finishSentences,
  }, { onConflict: 'master_sku,platform' })
}

// Log to regeneration_history for audit trail
await supabase.from('regeneration_history').insert({
  master_sku, content_type, platform, mode,
  system_prompt: SYSTEM_PROMPT,
  user_prompt: userPrompt,
  prompt_hash: promptHash,
  new_content: newContent,
})
```

## Display-Time Variant Content Composition

### Title Generation (`generateVariantTitle`)

```typescript
export function generateVariantTitle(
  baseTitle: string | null,
  finishName: string,
  platform: 'google' | 'bing' = 'google'
): string {
  // Case 1: Replace {FINISH_NAME} placeholder
  if (result.includes(PLACEHOLDERS.FINISH_NAME)) {
    return result.replace(/{FINISH_NAME}/g, finishName)
  }

  // Case 2: Target finish already in title
  if (result.toLowerCase().includes(finishName.toLowerCase())) {
    return result
  }

  // Case 3: Different finish in title → replace it
  for (const existingFinish of getAllFinishNames()) {
    if (result.toLowerCase().includes(existingFinish.toLowerCase())) {
      return result.replace(new RegExp(existingFinish, 'gi'), finishName)
    }
  }

  // Case 4: No finish → append based on platform
  if (platform === 'bing') {
    return `${result} in ${finishName}`
  }
  return `${result} - ${finishName}`
}
```

### Description Generation (`generateVariantDescription`)

```typescript
export function generateVariantDescription(
  baseDescription: string | null,
  finishName: string,
  finishSentences?: Record<string, string>
): string {
  // Priority 1: Use product-specific finish sentence if available
  if (finishSentences?.[finishName]) {
    const finishSentence = finishSentences[finishName]

    // Insert after first sentence
    const firstPeriodMatch = result.search(/(?<!\d)\.(?!\d)/)
    if (firstPeriodMatch > 0) {
      const before = result.slice(0, firstPeriodMatch + 1)
      const after = result.slice(firstPeriodMatch + 1)
      return `${before} ${finishSentence}${after.startsWith(' ') ? after : ' ' + after}`.trim()
    }
    return `${result} ${finishSentence}`.trim()
  }

  // Fallback: Legacy placeholder replacement or generic
  return generateVariantDescriptionGeneric(baseDescription, finishName)
}
```

## Finish Data Structure

### 30 Finishes Categorized

```typescript
// Categories for LLM context
Traditional Warm: Antique Brass, Antique Bronze, Antique Copper,
  Oil Rubbed Bronze, Polished Brass, Satin Brass, Spanish Gold,
  Unlacquered Brass, Venetian Bronze
Traditional Cool: Antique Pewter
Transitional: Brushed Bronze, Polished Chrome, Polished Nickel,
  Satin Chrome, Satin Nickel
Contemporary Neutral: Matte Black, Matte Gray, Matte White
Statement Colors: Fire Engine Red, Flat Troll Blue, Glokzin Teal,
  Golden Yellow, Lavender, Mediterranean Blue, Pink, Sea Foam Green
Statement Other: Autumn Sparkle, Military Camo, Red White and Blue,
  Shaded Beige
```

### Finish Data Interface

```typescript
interface FinishData {
  name: string      // "Antique Brass"
  code: string      // "ABR"
  description: string // Marketing description for legacy fallback
  style: 'traditional' | 'contemporary' | 'transitional' | 'statement'
  tone: 'warm' | 'cool' | 'neutral' | 'bold'
}
```

## Database Schema

### `generated_content`
Stores base content (finish-agnostic):
- `candidate_content` - LLM-generated content
- `baseline_content` - Original/current content for comparison
- `version` - Incremented on each regeneration
- `generation_model`, `generation_prompt_hash`, `generation_timestamp`

### `variant_finish_sentences`
Stores product+finish tailored sentences:
- `master_sku`, `platform` (unique constraint)
- `finish_sentences` (JSONB) - Map of finish name → tailored sentence

### `regeneration_history`
Audit trail:
- Full prompt (system + user)
- `prompt_hash` for deduplication
- Previous and new content

## Key Differences from Python Pipeline

| Aspect | TypeScript | Python |
|--------|------------|--------|
| Storage | Supabase tables | JSON patch files |
| Variants | Display-time composition | Generation-time per variant |
| Finish sentences | Separate table, generated once | Inline in variant patches |
| Evidence | Markdown table from product_catalog | Similar evidence builder |
| Vision | Optional (descriptions only) | Not implemented |
| Audit trail | regeneration_history table | File-based reports |

## API Calls Per SKU

For a full regeneration of one SKU:
- **Title (all platforms)**: 1 call each = 3 calls (simple text)
- **Description (Google/Bing)**: 1 call each = 2 calls (JSON with finish_sentences)
- **Description (Shopify)**: 1 call (simple text)
- **Total**: 6 API calls per SKU

Note: Google/Bing descriptions generate all 28 finish sentences in one call.

## Example Output

### Generated Content (stored in `generated_content`)

```json
{
  "candidate_content": "This towel bar from the Carolina collection features solid brass construction with concealed mounting for a clean, decorator-friendly appearance. The 24-inch bar provides ample hanging space while the timeless design coordinates with other Carolina accessories. Backed by Allied Brass's limited lifetime warranty."
}
```

### Finish Sentences (stored in `variant_finish_sentences`)

```json
{
  "Antique Brass": "The warm, aged patina of Antique Brass brings vintage warmth to the Carolina collection's classic styling.",
  "Fire Engine Red": "Fire Engine Red transforms this traditional towel bar into an unexpected focal point that adds personality to any bathroom.",
  "Matte Black": "Matte Black provides a modern, sophisticated contrast that updates the Carolina collection's classic form."
}
```

### Composed Variant Description (at display time)

For Antique Brass variant:
> "This towel bar from the Carolina collection features solid brass construction with concealed mounting for a clean, decorator-friendly appearance. **The warm, aged patina of Antique Brass brings vintage warmth to the Carolina collection's classic styling.** The 24-inch bar provides ample hanging space while the timeless design coordinates with other Carolina accessories. Backed by Allied Brass's limited lifetime warranty."

## Fallback Hierarchy

1. **Product-specific finish sentence** (from `variant_finish_sentences`)
2. **Placeholder replacement** (`{FINISH_NAME}`, `{FINISH_DESCRIPTION}`)
3. **Hardcoded finish detection and replacement**
4. **Generic finish insertion** (from `finish-data.ts`)

---

## Files Reference

| File | Purpose |
|------|---------|
| `dashboard/src/app/api/regenerate/route.ts` | Main API endpoint |
| `dashboard/src/lib/evidence/builder.ts` | Build evidence markdown from product_catalog |
| `dashboard/src/lib/evidence/queries.ts` | Fetch product data from Supabase |
| `dashboard/src/lib/evidence/enrichment.ts` | Design style, features, room context |
| `dashboard/src/lib/variant-content.ts` | Display-time variant composition |
| `dashboard/src/lib/finish-data.ts` | 30 finish definitions |
| `supabase/migrations/009_variant_finish_sentences.sql` | Finish sentences table |
