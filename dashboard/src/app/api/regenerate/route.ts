import { NextRequest, NextResponse } from 'next/server'
import OpenAI from 'openai'
import type { ChatCompletionMessageParam, ChatCompletionContentPart } from 'openai/resources/chat/completions'
import { FeedbackPreset } from '@/lib/supabase/types'
import { createAdminClient } from '@/lib/supabase/admin'
import { getProductEvidence, productExistsInCatalog } from '@/lib/evidence'
import {
  loadActivePromptTemplate,
  formatGoldStandardExamples,
  getCategoryGuidance,
  type PromptTemplate,
} from '@/lib/prompts/loader'
import crypto from 'node:crypto'

// Lazy-initialize OpenAI client (avoid build-time instantiation)
let _openai: OpenAI | null = null
function getOpenAIClient(): OpenAI {
  if (!_openai) {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error('OPENAI_API_KEY environment variable is not set')
    }
    _openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    })
  }
  return _openai
}

// Model to use for generation (default aligns with Python backend)
const MODEL = process.env.FEEDOPS_OPENAI_MODEL || 'gpt-5.2'

// 28 Allied Brass finishes for product+finish tailored sentences
// EXCLUDES: Military Camo and Red White and Blue (specialty/novelty finishes)
const FINISH_LIST = [
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
const FINISH_REFERENCE = `FINISH REFERENCE (28 finishes with their character):
Traditional Warm: Antique Brass (aged patina), Antique Bronze (deep brown), Antique Copper (burnished copper), Oil Rubbed Bronze (copper highlights), Polished Brass (mirror gold), Satin Brass (brushed gold), Spanish Gold (Old World gold), Unlacquered Brass (living patina), Venetian Bronze (golden highlights)
Traditional Cool: Antique Pewter (silvery gray)
Transitional: Brushed Bronze (warm matte), Polished Chrome (bright reflective), Polished Nickel (warm silver), Satin Chrome (brushed silver), Satin Nickel (warm brushed)
Contemporary Neutral: Matte Black (smooth non-reflective), Matte Gray (soft neutral), Matte White (clean crisp)
Statement Colors: Fire Engine Red (bold vibrant), Flat Troll Blue (matte playful), Glokzin Teal (coastal), Golden Yellow (sunny), Lavender (calming purple), Mediterranean Blue (deep sea), Pink (soft feminine), Sea Foam Green (coastal fresh)
Statement Other: Autumn Sparkle (shimmer), Shaded Beige (warm earth)`

// Whether to use vision for descriptions (default: true)
const USE_VISION = process.env.FEEDOPS_USE_VISION !== '0'

// Feedback preset descriptions
const FEEDBACK_PRESETS: Record<FeedbackPreset, string> = {
  shorter: 'Make this shorter and more concise while keeping key information',
  longer: 'Expand this with more detail and product benefits',
  more_specific: 'Replace vague claims with specific, verifiable details',
  different_angle: 'Take a different approach - emphasize different benefits or features',
  more_keywords: 'Include more relevant search keywords naturally',
  less_promotional: 'Remove promotional language, make it more factual',
  better_hook: 'Improve the opening to be more compelling',
}

interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  mode: 'simple' | 'with_feedback'
  feedback?: {
    current_content: string
    user_feedback: string
    feedback_type?: FeedbackPreset
    finish?: string // Optional finish for variant-specific regeneration
  }
  options?: {
    num_candidates?: number
  }
}

// Fallback system prompt (used when prompt_templates not available)
const FALLBACK_SYSTEM_PROMPT = `You are an expert e-commerce content writer for Allied Brass bathroom hardware. Generate titles and descriptions that balance quality messaging with customer motivation.

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
{FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass

- Lead with finish (search relevance, immediate style context)
- Collection before brand (coordination buyers, not brand recognition)
- Include differentiating features ("Space-Saving", "No Spring", "Rust Proof")

### Shopify Titles
- NO {FINISH_NAME} placeholder (user already viewing specific variant)
- NO "Allied Brass" (user already on the site)
- Match the product catalog title style

### Descriptions
- ASSESS FIRST: Does this product have a natural pain point?
- If YES: Open with the problem, then solution
- If NO: Open with quality, craftsmanship, and design fit
- Include {FINISH_SENTENCE} placeholder for Google/Bing (inserted after first sentence)
- Shopify descriptions are finish-agnostic (no placeholders)

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
 * Build enhanced prompt using evidence table
 */
function buildEnhancedPrompt(
  contentType: 'title' | 'description',
  platform: string,
  evidenceMarkdown: string,
  promptTemplate?: PromptTemplate | null,
  productCategory?: string
): { prompt: string; requiresJson: boolean } {
  // Updated context with TRUE WHY approach and new title structure
  const platformContext: Record<string, Record<string, string>> = {
    google: {
      title: 'Google Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass. Lead with finish placeholder for search relevance. Make them want to click.',
      description: 'Google Shopping description - Open with the TRUE WHY (the customer\'s deeper motivation). Write for a human scanning Shopping ads. Include material quality and dimensions. Plain text, 600-800 characters.',
    },
    bing: {
      title: 'Bing Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass. Include natural product synonyms. Make them want to click.',
      description: 'Bing Shopping description - Open with the TRUE WHY. Include product synonyms naturally (towel bar/rack, shower basket/caddy). Include specific dimensions and materials. Plain text, 700-1000 characters.',
    },
    shopify: {
      title: 'Shopify product title (H1) - NO finish name, NO "Allied Brass". Customer already clicked. Match product catalog title style.',
      description: 'Shopify description - customer already clicked, now convince them to add to cart. Open with their problem or desired outcome. Mention 28 finishes as a benefit. HTML format with <p> and <ul><li> bullets. Do NOT include specific finish names.',
    },
  }

  const context = platformContext[platform]?.[contentType] || ''

  // Add gold standard examples if available
  let examplesSection = ''
  if (promptTemplate && contentType) {
    const examples = formatGoldStandardExamples(
      promptTemplate,
      platform as 'google' | 'bing' | 'shopify',
      contentType,
      3 // Include 3 examples
    )
    if (examples) {
      examplesSection = `\n\nGOLD STANDARD EXAMPLES (learn from these):\n${examples}\n`
    }
  }

  // Add category guidance if available
  let categoryGuidanceSection = ''
  if (promptTemplate && productCategory) {
    const guidance = getCategoryGuidance(promptTemplate, productCategory)
    if (guidance) {
      categoryGuidanceSection = `\n\nCATEGORY-SPECIFIC GUIDANCE for ${productCategory}:\n${guidance}\n`
    }
  }

  // For Google/Bing descriptions, request JSON with finish_sentences
  const isVariantDescription = contentType === 'description' && (platform === 'google' || platform === 'bing')

  if (isVariantDescription) {
    const finishSentencesInstructions = `
FINISH SENTENCES (CRITICAL - YOU MUST INCLUDE THESE):
In addition to the base description, generate 28 finish-specific sentences - one for each finish.
Each sentence should describe how THAT FINISH relates to THIS SPECIFIC PRODUCT.
DO NOT include Military Camo or Red White and Blue (specialty finishes excluded).

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

    return {
      prompt: `Generate content for this product. You MUST respond with valid JSON.

CONTEXT: ${context}
${examplesSection}${categoryGuidanceSection}
${evidenceMarkdown}

${finishSentencesInstructions}

Remember:
- Open with the TRUE WHY (customer's deeper motivation) when one exists naturally
- For standard products without dramatic pain points, focus on quality/craftsmanship
- Every factual claim must be traceable to the evidence table above
- The base description should NOT include any specific finish name
- Each finish_sentence should relate the specific finish to THIS product

Respond with this EXACT JSON structure (no markdown, no code blocks):
{
  "content": "The base description text here (no finish names)...",
  "finish_sentences": {
    "Antique Brass": "One sentence relating Antique Brass to this product...",
    "Antique Bronze": "One sentence relating Antique Bronze to this product...",
    ... (all 28 finishes - exclude Military Camo and Red White and Blue)
  }
}`,
      requiresJson: true,
    }
  }

  // For titles and Shopify, use simple text response
  return {
    prompt: `Generate a ${contentType} for this product.

CONTEXT: ${context}
${examplesSection}${categoryGuidanceSection}
${evidenceMarkdown}

CRITICAL RULES:
- For Google/Bing titles: Use {FINISH_NAME} placeholder at the START, followed by product/specs, then collection, then "Allied Brass"
- For Shopify titles: NO finish placeholder, NO "Allied Brass"
- Do NOT include any actual finish name like "Antique Brass", "Matte Black", etc.

Remember:
- Write for a human who's about to spend $80 and wants to feel good about it
- Every factual claim must be traceable to the evidence table above
- Weave keywords naturally, don't list them

Respond with ONLY the ${contentType} text, no additional explanation or formatting.`,
    requiresJson: false,
  }
}

/**
 * Build enhanced feedback prompt using evidence table
 */
function buildEnhancedFeedbackPrompt(
  contentType: 'title' | 'description',
  platform: string,
  evidenceMarkdown: string,
  currentContent: string,
  feedback: string
): string {
  const platformContext: Record<string, string> = {
    google: 'Google Shopping - first impression, make them want to click. Use {FINISH_NAME} placeholder.',
    bing: 'Bing Shopping - include natural product synonyms. Use {FINISH_NAME} placeholder.',
    shopify: 'Shopify - customer already clicked, convince them to buy. Do NOT include specific finish names.',
  }

  const context = platformContext[platform] || platform

  return `You are improving a product ${contentType} TEMPLATE based on reviewer feedback.

PLATFORM: ${context}

CURRENT ${contentType.toUpperCase()}:
${currentContent}

REVIEWER FEEDBACK:
${feedback}

${evidenceMarkdown}

CRITICAL TEMPLATE RULES:
- For Google/Bing: Use {FINISH_NAME} placeholder where finish should appear (NOT a specific finish like "Antique Brass")
- For Google/Bing: Optionally use {FINISH_DESCRIPTION} for finish description
- For Shopify: Do NOT include any finish name
- This template will be used for ALL 28 finish variants

Remember the buyer questions you're answering:
- "Will this look good in MY bathroom?"
- "Will this match my other fixtures?"
- "Is this actually better than the $20 Amazon option?"
- "Will this last? Is it quality?"

Generate an improved ${contentType} template that addresses the feedback while answering these buyer questions.
Every factual claim must be traceable to the evidence table above.

Respond with ONLY the improved ${contentType} template text, no additional explanation or formatting.`
}

/**
 * Build simple prompt (fallback when catalog not available)
 */
function buildSimplePrompt(
  contentType: 'title' | 'description',
  platform: string,
  productData: Record<string, unknown>
): { prompt: string; requiresJson: boolean } {
  const platformContext: Record<string, Record<string, string>> = {
    google: {
      title: 'Google Shopping title - this is their first impression. Make them want to click. Include product type, key dimension, and "Allied Brass" at end.',
      description: 'Google Shopping description - write for a human scanning Shopping ads. Plain text only.',
    },
    bing: {
      title: 'Bing Shopping title - include natural product synonyms. Make them want to click. Include "Allied Brass" at end.',
      description: 'Bing Shopping description - write for humans, include product synonyms naturally. Plain text only.',
    },
    shopify: {
      title: 'Shopify product title (H1) - customer already clicked. Help them feel confident about buying. Do NOT include finish name.',
      description: 'Shopify description - customer already clicked, now convince them to add to cart. Open with their problem or desired outcome. Mention 28 finishes as a benefit. HTML format with <p> and <ul><li> bullets. Do NOT include specific finish names.',
    },
  }

  const context = platformContext[platform]?.[contentType] || ''

  // For Google/Bing descriptions, request JSON with finish_sentences
  const isVariantDescription = contentType === 'description' && (platform === 'google' || platform === 'bing')

  if (isVariantDescription) {
    return {
      prompt: `Generate content for this product. You MUST respond with valid JSON.

CONTEXT: ${context}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

${FINISH_REFERENCE}

Generate a base description (no specific finish names) and 28 finish-specific sentences.
Each finish sentence should relate the finish to THIS product.

Respond with this EXACT JSON structure (no markdown, no code blocks):
{
  "content": "The base description text here (no finish names)...",
  "finish_sentences": {
    "Antique Brass": "One sentence relating Antique Brass to this product...",
    ... (all 28 finishes)
  }
}`,
      requiresJson: true,
    }
  }

  return {
    prompt: `Generate a ${contentType} for this product.

CONTEXT: ${context}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

CRITICAL:
- Do NOT include any specific finish name like "Antique Brass", "Matte Black", etc.

Remember: Write for a human who's about to spend $80 and wants to feel good about it.

Respond with ONLY the ${contentType} text, no additional explanation or formatting.`,
    requiresJson: false,
  }
}

/**
 * Build simple feedback prompt (fallback)
 */
function buildSimpleFeedbackPrompt(
  contentType: 'title' | 'description',
  platform: string,
  productData: Record<string, unknown>,
  currentContent: string,
  feedback: string
): string {
  const platformContext: Record<string, string> = {
    google: 'Google Shopping - first impression, make them want to click. Use {FINISH_NAME} placeholder.',
    bing: 'Bing Shopping - include natural product synonyms. Use {FINISH_NAME} placeholder.',
    shopify: 'Shopify - customer already clicked, convince them to buy. Do NOT include specific finish names.',
  }

  const context = platformContext[platform] || platform

  return `You are improving a product ${contentType} TEMPLATE based on reviewer feedback.

PLATFORM: ${context}

CURRENT ${contentType.toUpperCase()}:
${currentContent}

REVIEWER FEEDBACK:
${feedback}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

CRITICAL:
- For Google/Bing: Use {FINISH_NAME} placeholder (NOT a specific finish like "Antique Brass")
- For Shopify: Do NOT include any finish name
- This template will be used for ALL 28 finish variants

Remember the buyer questions you're answering:
- "Will this look good in MY bathroom?"
- "Will this match my other fixtures?"
- "Is this actually better than the $20 Amazon option?"
- "Will this last? Is it quality?"

Generate an improved ${contentType} template that addresses the feedback while answering these buyer questions.

Respond with ONLY the improved ${contentType} template text, no additional explanation or formatting.`
}

type SupabaseErrLike = {
  code?: string | null
  message?: string
  details?: string | null
  hint?: string | null
}

function logSupabaseError(context: string, err: SupabaseErrLike | null | undefined) {
  if (!err) return
  console.error(context, {
    code: err.code ?? null,
    message: err.message ?? 'Unknown error',
    details: err.details ?? null,
    hint: err.hint ?? null,
  })
}

function errorResponse(
  status: number,
  payload: { error: string; code?: string | null; details?: string | null; hint?: string | null; step?: string }
) {
  // Never leak DB internals in production responses.
  const isProd = process.env.NODE_ENV === 'production'
  if (isProd) {
    return NextResponse.json({ error: payload.error }, { status })
  }
  return NextResponse.json(payload, { status })
}

export async function POST(request: NextRequest) {
  try {
    // Validate OpenAI API key
    if (!process.env.OPENAI_API_KEY) {
      return NextResponse.json(
        { error: 'OpenAI API key not configured' },
        { status: 500 }
      )
    }

    const body: RegenerateRequest = await request.json()
    const { master_sku, content_type, platform, mode, feedback, options: _options } = body

    // Validate required fields
    if (!master_sku || !content_type || !platform || !mode) {
      return NextResponse.json(
        { error: 'Missing required fields: master_sku, content_type, platform, mode' },
        { status: 400 }
      )
    }

    if (mode === 'with_feedback' && (!feedback?.user_feedback || !feedback?.current_content)) {
      return NextResponse.json(
        { error: 'Feedback mode requires feedback.user_feedback and feedback.current_content' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()

    // Quick schema sanity check (migration 004 must be applied)
    const schemaCheck = await supabase
      .from('generated_content')
      .select('id,version,is_current')
      .limit(1)

    if (schemaCheck.error) {
      logSupabaseError('Supabase schema check failed (generated_content)', schemaCheck.error)
      return errorResponse(500, {
        error:
          'Supabase schema is out of date for regeneration (run migration 004_regeneration_history.sql)',
        code: schemaCheck.error.code ?? null,
        details: schemaCheck.error.message ?? null,
        hint: schemaCheck.error.hint ?? null,
        step: 'schema_check_generated_content',
      })
    }

    // Get variant data for finish info
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('*')
      .eq('master_sku', master_sku)
      .limit(1)
      .maybeSingle()

    if (variantError) {
      logSupabaseError('Failed to fetch variant data', variantError)
    }

    // Get current content for comparison (needed for history logging)
    const { data: currentContentData, error: currentContentError } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', master_sku)
      .eq('platform', platform)
      .eq('content_type', content_type)
      .maybeSingle()

    if (currentContentError) {
      logSupabaseError('Failed to fetch current generated content', currentContentError)
    }

    // ==================== LOAD PROMPT TEMPLATE ====================
    let promptTemplate: PromptTemplate | null = null
    let systemPrompt = FALLBACK_SYSTEM_PROMPT

    try {
      promptTemplate = await loadActivePromptTemplate(supabase)
      if (promptTemplate) {
        systemPrompt = promptTemplate.system_prompt
        console.log(`Loaded prompt template: ${promptTemplate.name} v${promptTemplate.version}`)
      } else {
        console.log('No active prompt template, using fallback system prompt')
      }
    } catch (templateError) {
      console.warn('Failed to load prompt template:', templateError)
    }

    // ==================== BUILD PROMPT WITH EVIDENCE ====================
    let userPrompt = '' // Will be assigned below
    let imageUrl: string | null = null
    let useEnhancedPrompt = false
    let requiresJson = false // True for Google/Bing descriptions (finish_sentences)

    // Check if product exists in catalog for enhanced evidence
    const catalogExists = await productExistsInCatalog(supabase, master_sku)

    if (catalogExists) {
      try {
        // Get finish code for variant-specific context
        const finishCode = feedback?.finish || variantData?.finish_code || undefined

        // Build rich evidence table from product_catalog
        const evidenceResult = await getProductEvidence(supabase, master_sku, {
          platform: platform as 'google' | 'bing' | 'shopify',
          finish_code: finishCode,
        })

        imageUrl = evidenceResult.imageUrl
        useEnhancedPrompt = true

        if (mode === 'simple') {
          // Get product category for category-specific guidance
          const productCategory = variantData?.product_category || undefined
          const result = buildEnhancedPrompt(
            content_type,
            platform,
            evidenceResult.markdown,
            promptTemplate,
            productCategory
          )
          userPrompt = result.prompt
          requiresJson = result.requiresJson
        } else {
          // Combine preset + custom feedback
          const feedbackText = feedback!.feedback_type
            ? `${FEEDBACK_PRESETS[feedback!.feedback_type]}. ${feedback!.user_feedback}`
            : feedback!.user_feedback

          userPrompt = buildEnhancedFeedbackPrompt(
            content_type,
            platform,
            evidenceResult.markdown,
            feedback!.current_content,
            feedbackText
          )
          // Feedback mode doesn't use JSON (simpler flow)
          requiresJson = false
        }

        console.log(`Using enhanced prompt with evidence table for ${master_sku} (${platform}/${content_type})`)
      } catch (evidenceError) {
        console.warn('Failed to build evidence table, falling back to simple prompt:', evidenceError)
        useEnhancedPrompt = false
      }
    }

    // Fallback to simple prompt if catalog not available
    if (!useEnhancedPrompt) {
      const productData = {
        master_sku,
        product_title: variantData?.product_title || master_sku,
        product_category: variantData?.product_category || 'Bathroom Hardware',
        finish: variantData?.finish,
        finish_code: variantData?.finish_code,
        dimensions: variantData?.dimensions,
      }

      if (mode === 'simple') {
        const result = buildSimplePrompt(content_type, platform, productData)
        userPrompt = result.prompt
        requiresJson = result.requiresJson
      } else {
        const feedbackText = feedback!.feedback_type
          ? `${FEEDBACK_PRESETS[feedback!.feedback_type]}. ${feedback!.user_feedback}`
          : feedback!.user_feedback

        userPrompt = buildSimpleFeedbackPrompt(
          content_type,
          platform,
          productData,
          feedback!.current_content,
          feedbackText
        )
        // Feedback mode doesn't use JSON
        requiresJson = false
      }
    }

    const promptHash = crypto
      .createHash('sha256')
      .update(`${systemPrompt}\n\n${userPrompt}`, 'utf8')
      .digest('hex')

    // ==================== BUILD MESSAGES WITH OPTIONAL VISION ====================
    const messages: ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
    ]

    // Add vision support for descriptions when image URL is available
    const shouldUseVision = USE_VISION && imageUrl && content_type === 'description'

    if (shouldUseVision && imageUrl) {
      // Build multimodal message with text and image
      const contentParts: ChatCompletionContentPart[] = [
        { type: 'text', text: userPrompt },
        {
          type: 'image_url',
          image_url: {
            url: imageUrl, // imageUrl is guaranteed non-null here
            detail: 'low', // Use low detail to reduce token cost (~85 tokens)
          },
        },
      ]
      messages.push({ role: 'user', content: contentParts })
      console.log(`Using vision with image: ${imageUrl}`)
    } else {
      messages.push({ role: 'user', content: userPrompt })
    }

    // ==================== CALL OPENAI ====================
    // JSON mode needs more tokens for finish_sentences (28 entries)
    const maxTokens = requiresJson ? 4000 : (content_type === 'title' ? 200 : 1000)
    const tokenParams = MODEL.startsWith('gpt-5')
      ? ({ max_completion_tokens: maxTokens } as const)
      : ({ max_tokens: maxTokens } as const)

    const completion = await getOpenAIClient().chat.completions.create({
      model: MODEL,
      messages,
      temperature: 0.7,
      stream: false,
      ...(requiresJson ? { response_format: { type: 'json_object' as const } } : {}),
      ...tokenParams,
    })

    const rawResponse = completion.choices[0]?.message?.content?.trim()

    if (!rawResponse) {
      return NextResponse.json(
        { error: 'No content generated from OpenAI' },
        { status: 500 }
      )
    }

    // Parse response based on mode
    let newContent: string
    let finishSentences: Record<string, string> | null = null

    if (requiresJson) {
      try {
        const parsed = JSON.parse(rawResponse)
        newContent = parsed.content?.trim()
        finishSentences = parsed.finish_sentences || null

        if (!newContent) {
          return NextResponse.json(
            { error: 'Invalid JSON response: missing content field' },
            { status: 500 }
          )
        }

        // Validate finish_sentences has all 28 finishes
        if (finishSentences) {
          const missingFinishes = FINISH_LIST.filter(f => !finishSentences![f])
          if (missingFinishes.length > 0) {
            console.warn(`Missing finish sentences for: ${missingFinishes.join(', ')}`)
          }
        }

        console.log(`Parsed JSON response with ${finishSentences ? Object.keys(finishSentences).length : 0} finish sentences`)
      } catch (parseError) {
        console.error('Failed to parse JSON response:', parseError)
        // Fallback: use raw response as content (best effort)
        newContent = rawResponse
      }
    } else {
      newContent = rawResponse
    }

    // ==================== SAVE TO DATABASE ====================
    const currentVersion = currentContentData?.version ?? 0

    let savedContentId: string | null = null
    let nextVersion = currentVersion + 1

    if (currentContentData) {
      const { data: updated, error: updateError } = await supabase
        .from('generated_content')
        .update({
          candidate_content: newContent,
          version: nextVersion,
          is_current: true,
          generation_model: MODEL,
          generation_prompt_hash: promptHash,
          generation_timestamp: new Date().toISOString(),
        })
        .eq('id', currentContentData.id)
        .select('id')
        .single()

      if (updateError) {
        logSupabaseError('Failed to update generated_content', updateError)
        return errorResponse(500, {
          error: 'Failed to save generated content',
          code: updateError.code ?? null,
          details: updateError.message ?? null,
          hint: updateError.hint ?? null,
          step: 'generated_content_update',
        })
      }

      savedContentId = updated?.id ?? null
    } else {
      nextVersion = 1
      const { data: inserted, error: insertError } = await supabase
        .from('generated_content')
        .insert({
          master_sku,
          platform,
          content_type,
          candidate_content: newContent,
          baseline_content: null,
          version: nextVersion,
          is_current: true,
          generation_model: MODEL,
          generation_prompt_hash: promptHash,
          generation_timestamp: new Date().toISOString(),
        })
        .select('id')
        .single()

      if (insertError) {
        logSupabaseError('Failed to insert generated_content', insertError)
        return errorResponse(500, {
          error: 'Failed to save generated content',
          code: insertError.code ?? null,
          details: insertError.message ?? null,
          hint: insertError.hint ?? null,
          step: 'generated_content_insert',
        })
      }

      savedContentId = inserted?.id ?? null
    }

    // Log to regeneration history
    const { error: historyError } = await supabase
      .from('regeneration_history')
      .insert({
        master_sku,
        content_type,
        platform,
        mode,
        feedback_text: feedback?.user_feedback || null,
        feedback_preset: feedback?.feedback_type || null,
        previous_content: currentContentData?.candidate_content || null,
        new_content: newContent,
        model_version: MODEL,
        system_prompt: systemPrompt,
        user_prompt: userPrompt,
        prompt_hash: promptHash,
        quality_score_before: currentContentData?.quality_score || null,
        generated_content_id: savedContentId,
      })

    if (historyError) {
      logSupabaseError('Failed to log regeneration history', historyError)
      return errorResponse(500, {
        error: 'Failed to save regeneration history',
        code: historyError.code ?? null,
        details: historyError.message ?? null,
        hint: historyError.hint ?? null,
        step: 'regeneration_history_insert',
      })
    }

    // Save finish_sentences to separate table (for Google/Bing descriptions only)
    let finishSentencesSaved = false
    if (finishSentences && Object.keys(finishSentences).length > 0 && (platform === 'google' || platform === 'bing')) {
      // Upsert finish sentences (insert or update on conflict)
      const { error: finishError } = await supabase
        .from('variant_finish_sentences')
        .upsert(
          {
            master_sku,
            platform,
            finish_sentences: finishSentences,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'master_sku,platform' }
        )

      if (finishError) {
        logSupabaseError('Failed to save finish sentences', finishError)
        // Non-fatal: log but continue (content was saved successfully)
        console.warn('Finish sentences not saved, but content was saved successfully')
      } else {
        finishSentencesSaved = true
        console.log(`Saved ${Object.keys(finishSentences).length} finish sentences for ${master_sku}/${platform}`)
      }
    }

    return NextResponse.json({
      success: true,
      content: newContent,
      version: nextVersion,
      mode,
      model: MODEL,
      generated_content_id: savedContentId,
      used_evidence: useEnhancedPrompt,
      used_vision: shouldUseVision,
      finish_sentences_count: finishSentences ? Object.keys(finishSentences).length : 0,
      finish_sentences_saved: finishSentencesSaved,
    })
  } catch (error) {
    console.error('Regeneration error:', error)
    return errorResponse(500, {
      error: error instanceof Error ? error.message : 'Internal server error',
      step: 'unhandled_exception',
    })
  }
}
