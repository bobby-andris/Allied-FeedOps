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
import {
  SYSTEM_PROMPT,
  FINISH_LIST,
  FINISH_REFERENCE,
  PLATFORM_CONTEXT,
  SIMPLE_PLATFORM_CONTEXT,
  FEEDBACK_PLATFORM_CONTEXT,
  getFinishSentenceInstructions,
  validateGeneratedContent,
} from '@/lib/regeneration/prompts'
import crypto from 'node:crypto'
import { ensureSkuData } from '@/lib/data-collection/ensure-data'

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

// FINISH_LIST, FINISH_REFERENCE, SYSTEM_PROMPT, and PLATFORM_CONTEXT
// are imported from @/lib/regeneration/prompts (single source of truth)

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

// System prompt is imported from @/lib/regeneration/prompts (SYSTEM_PROMPT)
// No longer using a fallback — code is the single source of truth

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
  const context = PLATFORM_CONTEXT[platform]?.[contentType] || ''

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
    return {
      prompt: `Generate content for this product. You MUST respond with valid JSON.

CONTEXT: ${context}
${examplesSection}${categoryGuidanceSection}
${evidenceMarkdown}

${getFinishSentenceInstructions()}

Remember:
- Assess first: pain-point opening only when a natural frustration exists, otherwise quality/craftsmanship
- Every factual claim must be traceable to the evidence table above
- The base description must NOT include any specific finish name — finish content goes ONLY in finish_sentences
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
- For Google/Bing titles: Use {FINISH_NAME} placeholder at the START, then product/specs, then "[Collection Name] Collection", then "Allied Brass". ALWAYS append "Collection" after the collection name.
- For Shopify titles: Must be the inner core of the Google/Bing title — same product, same specs, minus {FINISH_NAME} and "Allied Brass". Structure: [Collection Name] Collection [Product] [Key Specs] - [Differentiator]. ALWAYS append "Collection" after the collection name.
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
  const context = FEEDBACK_PLATFORM_CONTEXT[platform] || platform

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
  const context = SIMPLE_PLATFORM_CONTEXT[platform]?.[contentType] || ''

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
  const context = FEEDBACK_PLATFORM_CONTEXT[platform] || platform

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

    // Ensure data collection before regeneration (non-blocking, best-effort)
    ensureSkuData(master_sku, supabase)
      .then((result) => {
        if (result.success && result.details) {
          console.log(`Data collection for ${master_sku}:`, result.details)
        }
      })
      .catch((error) => {
        console.warn('Background data collection failed:', error)
      })

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
    // System prompt comes from code (single source of truth).
    // DB template provides gold standard examples + category guidance only.
    const systemPrompt = SYSTEM_PROMPT
    let promptTemplate: PromptTemplate | null = null

    try {
      promptTemplate = await loadActivePromptTemplate(supabase)
      if (promptTemplate) {
        console.log(`Loaded examples/guidance from template: ${promptTemplate.name} v${promptTemplate.version}`)
      }
    } catch (templateError) {
      console.warn('Failed to load prompt template for examples:', templateError)
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

    // ==================== VALIDATE & AUTO-RETRY ====================
    const violations = validateGeneratedContent(newContent, platform, content_type)

    if (violations.length > 0) {
      console.warn(`Validation violations for ${master_sku}/${platform}/${content_type}: ${violations.join('; ')}`)

      // Auto-retry once with violation feedback
      const retryInstruction = `VIOLATION — your previous response broke these rules:\n${violations.map(v => `- ${v}`).join('\n')}\n\nFix these violations in your new response. This is critical.`

      const retryMessages: ChatCompletionMessageParam[] = [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
        { role: 'assistant', content: requiresJson ? rawResponse : newContent },
        { role: 'user', content: retryInstruction },
      ]

      try {
        const retryCompletion = await getOpenAIClient().chat.completions.create({
          model: MODEL,
          messages: retryMessages,
          temperature: 0.5, // Lower temp for correction
          stream: false,
          ...(requiresJson ? { response_format: { type: 'json_object' as const } } : {}),
          ...tokenParams,
        })

        const retryResponse = retryCompletion.choices[0]?.message?.content?.trim()

        if (retryResponse) {
          if (requiresJson) {
            try {
              const parsed = JSON.parse(retryResponse)
              if (parsed.content?.trim()) {
                newContent = parsed.content.trim()
                finishSentences = parsed.finish_sentences || finishSentences
              }
            } catch {
              // Keep original if retry parse fails
            }
          } else {
            newContent = retryResponse
          }

          const retryViolations = validateGeneratedContent(newContent, platform, content_type)
          if (retryViolations.length > 0) {
            console.warn(`Retry still has violations: ${retryViolations.join('; ')}`)
          } else {
            console.log('Auto-retry fixed validation violations')
          }
        }
      } catch (retryError) {
        console.warn('Auto-retry failed, using original content:', retryError)
      }
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
