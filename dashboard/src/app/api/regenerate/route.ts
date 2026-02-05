import { NextRequest, NextResponse } from 'next/server'
import OpenAI from 'openai'
import type { ChatCompletionMessageParam, ChatCompletionContentPart } from 'openai/resources/chat/completions'
import { FeedbackPreset } from '@/lib/supabase/types'
import { createAdminClient } from '@/lib/supabase/admin'
import { getProductEvidence, productExistsInCatalog } from '@/lib/evidence'
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

// All 28 Allied Brass finishes with their character for product+finish tailored sentences
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
  'Military Camo',
  'Oil Rubbed Bronze',
  'Pink',
  'Polished Brass',
  'Polished Chrome',
  'Polished Nickel',
  'Red White and Blue',
  'Satin Brass',
  'Satin Chrome',
  'Satin Nickel',
  'Sea Foam Green',
  'Shaded Beige',
  'Spanish Gold',
  'Unlacquered Brass',
  'Venetian Bronze',
] as const

// Finish reference for LLM prompt (grouped by character)
const FINISH_REFERENCE = `FINISH REFERENCE (28 finishes with their character):
Traditional Warm: Antique Brass (aged patina), Antique Bronze (deep brown), Antique Copper (burnished copper), Oil Rubbed Bronze (copper highlights), Polished Brass (mirror gold), Satin Brass (brushed gold), Spanish Gold (Old World gold), Unlacquered Brass (living patina), Venetian Bronze (golden highlights)
Traditional Cool: Antique Pewter (silvery gray)
Transitional: Brushed Bronze (warm matte), Polished Chrome (bright reflective), Polished Nickel (warm silver), Satin Chrome (brushed silver), Satin Nickel (warm brushed)
Contemporary Neutral: Matte Black (smooth non-reflective), Matte Gray (soft neutral), Matte White (clean crisp)
Statement Colors: Fire Engine Red (bold vibrant), Flat Troll Blue (matte playful), Glokzin Teal (coastal), Golden Yellow (sunny), Lavender (calming purple), Mediterranean Blue (deep sea), Pink (soft feminine), Sea Foam Green (coastal fresh)
Statement Other: Autumn Sparkle (shimmer), Military Camo (pattern), Red White and Blue (patriotic), Shaded Beige (warm earth)`

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

// Context-driven system prompt (matches Python backend philosophy)
const SYSTEM_PROMPT = `You are a product content writer for Allied Brass bathroom and kitchen hardware.
Create content that helps buyers understand why this product is worth it.

BEFORE YOU WRITE, THINK ABOUT WHO IS READING THIS:

1. WHO IS SEARCHING FOR THIS PRODUCT?
- A homeowner renovating a bathroom who wants it to look intentional, not like an afterthought
- A designer specifying fixtures for a client who expects quality
- Someone replacing a broken/ugly product who wants an upgrade, not just a replacement

2. WHAT QUESTIONS DO THEY HAVE BEFORE SPENDING $80+?
- "Will this look good in MY bathroom?" → Help them visualize it
- "Will this match my other fixtures?" → Address finish coordination
- "Is this actually better than the $20 Amazon option?" → Explain the value
- "Will this last? Is it quality?" → Provide trust signals (material, warranty)

3. WHAT MAKES ALLIED BRASS WORTH IT?
- Style without sacrifice: You don't have to choose between "looks good" and "works well"
- Personalization: 28 finishes to match any bathroom vision
- Innovation: Rollerless TP holders, retractable rods, decorative grab bars, ventilated baskets
- Durability: Solid brass outlasts plastic and die-cast that crack and corrode
- Coordination: Match everything across 42+ collections

PLATFORM CONTEXT:
- Google/Bing (variant): Base content + 28 finish-specific sentences. Make them want to click.
- Shopify (master): All finishes on one page. Customer already clicked. Help them choose and buy.

CONTENT STRUCTURE:
For Google/Bing descriptions, you will generate:
1. A BASE DESCRIPTION - finish-agnostic, describes the product
2. FINISH SENTENCES - 28 product-specific sentences, one per finish, describing how each finish relates to THIS product

For titles and Shopify, generate simple content without specific finish names.

CRITICAL RULES:
- Never invent specifications not in the product data
- Every factual claim must be traceable to the provided evidence table
- "Allied Brass" should be the final segment in titles
- No ALL CAPS, no promotional language like "Premium", "Luxury", "Best"
- Write for a human who's about to spend $80 and wants to feel good about it
- When an image is provided, use it to verify product details but don't describe the image directly
- Base content should NOT include specific finish names (finish is added at display time)`

/**
 * Build enhanced prompt using evidence table
 */
function buildEnhancedPrompt(
  contentType: 'title' | 'description',
  platform: string,
  evidenceMarkdown: string
): { prompt: string; requiresJson: boolean } {
  const platformContext: Record<string, Record<string, string>> = {
    google: {
      title: 'Google Shopping title - this is their first impression. Make them want to click. Include product type, key dimension, and "Allied Brass" at end. Do NOT include specific finish names.',
      description: 'Google Shopping description - write for a human scanning Shopping ads. Answer their questions about this product. Include material quality and dimensions. Plain text only, 600-800 characters target.',
    },
    bing: {
      title: 'Bing Shopping title - include natural product synonyms. Make them want to click. Include "Allied Brass" at end. Do NOT include specific finish names.',
      description: 'Bing Shopping description - write for humans, include product synonyms naturally (e.g., towel bar/rack, shower basket/caddy). Include specific dimensions and materials. Plain text only, 700-1000 characters target.',
    },
    shopify: {
      title: 'Shopify product title (H1) - customer already clicked. Help them feel confident about buying. Do NOT include finish name (Shopify shows all finishes).',
      description: 'Shopify description - customer already clicked, now convince them to add to cart. Open with their problem or desired outcome. Mention 28 finishes as a benefit. Include trust signals. HTML format with <p> and <ul><li> bullets. Do NOT include a specific finish name.',
    },
  }

  const context = platformContext[platform]?.[contentType] || ''

  // For Google/Bing descriptions, request JSON with finish_sentences
  const isVariantDescription = contentType === 'description' && (platform === 'google' || platform === 'bing')

  if (isVariantDescription) {
    const finishSentencesInstructions = `
FINISH SENTENCES (CRITICAL - YOU MUST INCLUDE THESE):
In addition to the base description, generate 28 finish-specific sentences - one for each finish.
Each sentence should describe how THAT FINISH relates to THIS SPECIFIC PRODUCT.

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

${evidenceMarkdown}

${finishSentencesInstructions}

Remember:
- Write for a human who's about to spend $80 and wants to feel good about it
- Every factual claim must be traceable to the evidence table above
- The base description should NOT include any specific finish name
- Each finish_sentence should relate the specific finish to THIS product

Respond with this EXACT JSON structure (no markdown, no code blocks):
{
  "content": "The base description text here (no finish names)...",
  "finish_sentences": {
    "Antique Brass": "One sentence relating Antique Brass to this product...",
    "Antique Bronze": "One sentence relating Antique Bronze to this product...",
    ... (all 28 finishes)
  }
}`,
      requiresJson: true,
    }
  }

  // For titles and Shopify, use simple text response
  return {
    prompt: `Generate a ${contentType} for this product.

CONTEXT: ${context}

${evidenceMarkdown}

CRITICAL RULES:
- Do NOT include any specific finish name like "Antique Brass", "Matte Black", etc.
- For titles, finish will be inserted automatically at display time
- For Shopify descriptions, the page shows all finishes - do not mention a specific one

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
          const result = buildEnhancedPrompt(content_type, platform, evidenceResult.markdown)
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
      .update(`${SYSTEM_PROMPT}\n\n${userPrompt}`, 'utf8')
      .digest('hex')

    // ==================== BUILD MESSAGES WITH OPTIONAL VISION ====================
    const messages: ChatCompletionMessageParam[] = [
      { role: 'system', content: SYSTEM_PROMPT },
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
        system_prompt: SYSTEM_PROMPT,
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
