/**
 * Core regeneration logic extracted for reuse by batch and single-SKU APIs.
 */

import OpenAI from 'openai'
import type { ChatCompletionMessageParam, ChatCompletionContentPart } from 'openai/resources/chat/completions'
import type { SupabaseClient } from '@supabase/supabase-js'
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
  getFinishSentenceInstructions,
  validateGeneratedContent,
} from '@/lib/regeneration/prompts'
import crypto from 'node:crypto'

// Lazy-initialize OpenAI client
let _openai: OpenAI | null = null
export function getOpenAIClient(): OpenAI {
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

// Model to use for generation
export const MODEL = process.env.FEEDOPS_OPENAI_MODEL || 'gpt-5.2'

// Whether to use vision for descriptions
const USE_VISION = process.env.FEEDOPS_USE_VISION !== '0'

// FINISH_LIST, FINISH_REFERENCE, SYSTEM_PROMPT, and PLATFORM_CONTEXT
// are imported from @/lib/regeneration/prompts (single source of truth)

export type Platform = 'google' | 'bing' | 'shopify'
export type ContentType = 'title' | 'description'

export interface RegenerationResult {
  success: boolean
  content?: string
  finishSentences?: Record<string, string>
  version?: number
  error?: string
  model?: string
  usedEvidence?: boolean
  usedVision?: boolean
  mode?: 'full' | 'variant-adaptation'
}

/**
 * Build enhanced prompt using evidence table
 */
function buildEnhancedPrompt(
  contentType: ContentType,
  platform: Platform,
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
      platform,
      contentType,
      3
    )
    if (examples) {
      examplesSection = `\n\nGOLD STANDARD EXAMPLES:\n${examples}\n`
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
    ... (all 28 finishes)
  }
}`,
      requiresJson: true,
    }
  }

  // For titles and Shopify descriptions, use simple text response
  return {
    prompt: `Generate a ${contentType} for this product.

CONTEXT: ${context}
${examplesSection}${categoryGuidanceSection}
${evidenceMarkdown}

CRITICAL RULES:
- For Google/Bing titles: Use {FINISH_NAME} placeholder at the START, then product/specs, then "[Collection Name] Collection", then "Allied Brass". ALWAYS append "Collection" after the collection name.
- For Shopify titles: Must be the inner core of the Google/Bing title — same product, same specs, minus {FINISH_NAME} and "Allied Brass". Structure: [Collection Name] Collection [Product] [Key Specs] - [Differentiator]. ALWAYS append "Collection" after the collection name.
- For Shopify descriptions: NO "Allied Brass", NO specific finish names

Respond with ONLY the ${contentType} text, no additional explanation.`,
    requiresJson: false,
  }
}

/**
 * Build simple prompt (fallback when catalog not available)
 */
function buildSimplePrompt(
  contentType: ContentType,
  platform: Platform,
  productData: Record<string, unknown>
): { prompt: string; requiresJson: boolean } {
  const context = SIMPLE_PLATFORM_CONTEXT[platform]?.[contentType] || ''
  const isVariantDescription = contentType === 'description' && (platform === 'google' || platform === 'bing')

  if (isVariantDescription) {
    return {
      prompt: `Generate content for this product. You MUST respond with valid JSON.

CONTEXT: ${context}

PRODUCT DATA:
${JSON.stringify(productData, null, 2)}

${FINISH_REFERENCE}

Generate a base description (no specific finish names) and 28 finish-specific sentences.

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
- For Shopify: Do NOT include "Allied Brass" or any specific finish name

Respond with ONLY the ${contentType} text.`,
    requiresJson: false,
  }
}

/**
 * Core regeneration function - generates new content for a single SKU/platform/contentType
 */
export async function regenerateContent(
  supabase: SupabaseClient,
  masterSku: string,
  platform: Platform,
  contentType: ContentType
): Promise<RegenerationResult> {
  try {
    // Get variant data for context
    const { data: variantData } = await supabase
      .from('variant_index')
      .select('*')
      .eq('master_sku', masterSku)
      .limit(1)
      .maybeSingle()

    // Get current content for version tracking
    const { data: currentContentData } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', masterSku)
      .eq('platform', platform)
      .eq('content_type', contentType)
      .maybeSingle()

    // System prompt comes from code (single source of truth).
    // DB template provides gold standard examples + category guidance only.
    const systemPrompt = SYSTEM_PROMPT
    let promptTemplate: PromptTemplate | null = null

    try {
      promptTemplate = await loadActivePromptTemplate(supabase)
    } catch {
      // Examples/guidance not available — system prompt still works
    }

    // Build prompt with evidence
    let userPrompt = ''
    let imageUrl: string | null = null
    let useEnhancedPrompt = false
    let requiresJson = false

    const catalogExists = await productExistsInCatalog(supabase, masterSku)

    if (catalogExists) {
      try {
        const evidenceResult = await getProductEvidence(supabase, masterSku, {
          platform,
          finish_code: variantData?.finish_code,
        })

        imageUrl = evidenceResult.imageUrl
        useEnhancedPrompt = true

        const productCategory = variantData?.product_category
        const result = buildEnhancedPrompt(
          contentType,
          platform,
          evidenceResult.markdown,
          promptTemplate,
          productCategory
        )
        userPrompt = result.prompt
        requiresJson = result.requiresJson
      } catch {
        useEnhancedPrompt = false
      }
    }

    // Fallback to simple prompt
    if (!useEnhancedPrompt) {
      const productData = {
        master_sku: masterSku,
        product_title: variantData?.product_title || masterSku,
        product_category: variantData?.product_category || 'Bathroom Hardware',
        finish: variantData?.finish,
        dimensions: variantData?.dimensions,
      }

      const result = buildSimplePrompt(contentType, platform, productData)
      userPrompt = result.prompt
      requiresJson = result.requiresJson
    }

    const promptHash = crypto
      .createHash('sha256')
      .update(`${systemPrompt}\n\n${userPrompt}`, 'utf8')
      .digest('hex')

    // Build messages with optional vision
    const messages: ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
    ]

    const shouldUseVision = Boolean(USE_VISION && imageUrl && contentType === 'description')

    if (shouldUseVision && imageUrl) {
      const contentParts: ChatCompletionContentPart[] = [
        { type: 'text', text: userPrompt },
        {
          type: 'image_url',
          image_url: { url: imageUrl, detail: 'low' },
        },
      ]
      messages.push({ role: 'user', content: contentParts })
    } else {
      messages.push({ role: 'user', content: userPrompt })
    }

    // Call OpenAI
    const maxTokens = requiresJson ? 4000 : (contentType === 'title' ? 200 : 1000)
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
      return { success: false, error: 'No content generated from OpenAI' }
    }

    // Parse response
    let newContent: string
    let finishSentences: Record<string, string> | null = null

    if (requiresJson) {
      try {
        const parsed = JSON.parse(rawResponse)
        newContent = parsed.content?.trim()
        finishSentences = parsed.finish_sentences || null

        if (!newContent) {
          return { success: false, error: 'Invalid JSON response: missing content field' }
        }

        // Validate finish_sentences
        if (finishSentences) {
          const missingFinishes = FINISH_LIST.filter(f => !finishSentences![f])
          if (missingFinishes.length > 0) {
            console.warn(`Missing finish sentences for: ${missingFinishes.join(', ')}`)
          }
        }
      } catch {
        // Fallback: use raw response
        newContent = rawResponse
      }
    } else {
      newContent = rawResponse
    }

    // Validate and auto-retry on violations
    const violations = validateGeneratedContent(newContent, platform, contentType)

    if (violations.length > 0) {
      console.warn(`Validation violations for ${masterSku}/${platform}/${contentType}: ${violations.join('; ')}`)

      const retryInstruction = `VIOLATION — your previous response broke these rules:\n${violations.map(v => `- ${v}`).join('\n')}\n\nFix these violations in your new response.`

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
          temperature: 0.5,
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

          const retryViolations = validateGeneratedContent(newContent, platform, contentType)
          if (retryViolations.length === 0) {
            console.log('Auto-retry fixed validation violations')
          }
        }
      } catch {
        // Keep original content on retry failure
      }
    }

    // Save to database
    const currentVersion = currentContentData?.version ?? 0
    const nextVersion = currentVersion + 1

    if (currentContentData) {
      const { error: updateError } = await supabase
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

      if (updateError) {
        return { success: false, error: `Failed to update: ${updateError.message}` }
      }
    } else {
      const { error: insertError } = await supabase
        .from('generated_content')
        .insert({
          master_sku: masterSku,
          platform,
          content_type: contentType,
          candidate_content: newContent,
          baseline_content: null,
          version: 1,
          is_current: true,
          generation_model: MODEL,
          generation_prompt_hash: promptHash,
          generation_timestamp: new Date().toISOString(),
        })

      if (insertError) {
        return { success: false, error: `Failed to insert: ${insertError.message}` }
      }
    }

    // Save finish_sentences if present
    if (finishSentences && Object.keys(finishSentences).length > 0 && (platform === 'google' || platform === 'bing')) {
      await supabase
        .from('variant_finish_sentences')
        .upsert(
          {
            master_sku: masterSku,
            platform,
            finish_sentences: finishSentences,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'master_sku,platform' }
        )
    }

    // Log to regeneration history
    await supabase
      .from('regeneration_history')
      .insert({
        master_sku: masterSku,
        content_type: contentType,
        platform,
        mode: 'simple',
        previous_content: currentContentData?.candidate_content || null,
        new_content: newContent,
        model_version: MODEL,
        system_prompt: systemPrompt,
        user_prompt: userPrompt,
        prompt_hash: promptHash,
        quality_score_before: currentContentData?.quality_score || null,
      })

    return {
      success: true,
      content: newContent,
      finishSentences: finishSentences || undefined,
      version: nextVersion,
      model: MODEL,
      usedEvidence: useEnhancedPrompt,
      usedVision: shouldUseVision,
      mode: 'full',
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { success: false, error: message }
  }
}

/**
 * Build variant adaptation prompt
 */
function buildVariantAdaptationPrompt(
  contentType: ContentType,
  platform: Platform,
  baseSku: string,
  variantSku: string,
  baseContent: string,
  baseSpec: string,
  variantSpec: string
): { prompt: string; requiresJson: boolean } {
  const context = PLATFORM_CONTEXT[platform]?.[contentType] || ''
  const isVariantDescription = contentType === 'description' && (platform === 'google' || platform === 'bing')

  if (isVariantDescription) {
    return {
      prompt: `You are adapting product content for a variant specification. You MUST respond with valid JSON.

CONTEXT: ${context}

BASE PRODUCT: ${baseSku}
BASE CONTENT:
${baseContent}

TARGET PRODUCT: ${variantSku}
KEY DIFFERENCE: Specification changes from ${baseSpec} to ${variantSpec}

TASK:
1. Adapt the description for the ${variantSpec} specification
2. Update numeric specs and measurements (${baseSpec} → ${variantSpec})
3. Adjust use case emphasis based on the specification difference
4. Maintain the SAME brand voice, structure, and key selling points from the base content
5. Keep similar length and format
6. Generate finish_sentences for all 28 finishes relating to THIS variant

CRITICAL:
- This is a specification variant of the same product family
- Maintain consistency with the base content's storytelling and tone
- Focus only on meaningful differences (specs, use cases)
- Do NOT reinvent the entire description - adapt strategically

Respond with this EXACT JSON structure (no markdown, no code blocks):
{
  "content": "The adapted description for ${variantSpec}...",
  "finish_sentences": {
    "Antique Brass": "One sentence relating Antique Brass to this ${variantSpec} product...",
    ... (all 28 finishes)
  }
}`,
      requiresJson: true,
    }
  }

  // For titles
  return {
    prompt: `You are adapting a product title for a variant specification.

CONTEXT: ${context}

BASE PRODUCT: ${baseSku}
BASE TITLE: ${baseContent}

TARGET PRODUCT: ${variantSku}
KEY DIFFERENCE: Specification changes from ${baseSpec} to ${variantSpec}

TASK:
Adapt the title for the ${variantSpec} specification. Update the spec reference (${baseSpec} → ${variantSpec}) while maintaining the same structure and format.

CRITICAL RULES:
- For Google/Bing titles: Use {FINISH_NAME} placeholder at the START, update spec to ${variantSpec}
- For Shopify titles: Update spec to ${variantSpec}, keep same structure as base
- Maintain the SAME collection name, product name, and format
- ONLY change the specification number/identifier

Respond with ONLY the adapted title text.`,
    requiresJson: false,
  }
}

/**
 * Adapt content from a base SKU for a variant SKU
 * Uses focused prompting to maintain consistency while updating key differences
 */
export async function adaptVariantContent(
  supabase: SupabaseClient,
  baseSku: string,
  variantSku: string,
  platform: Platform,
  contentType: ContentType,
  baseSpec: string,
  variantSpec: string
): Promise<RegenerationResult> {
  try {
    // Get base content
    const { data: baseContentData } = await supabase
      .from('generated_content')
      .select('candidate_content, approved_content')
      .eq('master_sku', baseSku)
      .eq('platform', platform)
      .eq('content_type', contentType)
      .maybeSingle()

    if (!baseContentData) {
      return {
        success: false,
        error: `No base content found for ${baseSku}/${platform}/${contentType}`,
      }
    }

    // Use approved content if available, otherwise candidate
    const baseContent = baseContentData.approved_content || baseContentData.candidate_content

    if (!baseContent) {
      return {
        success: false,
        error: `Base content is empty for ${baseSku}/${platform}/${contentType}`,
      }
    }

    // Get current content for version tracking
    const { data: currentContentData } = await supabase
      .from('generated_content')
      .select('*')
      .eq('master_sku', variantSku)
      .eq('platform', platform)
      .eq('content_type', contentType)
      .maybeSingle()

    // Build adaptation prompt
    const systemPrompt = `You are a product content specialist adapting content for product specification variants. Your goal is to maintain brand consistency while updating key specification differences.`

    const { prompt: userPrompt, requiresJson } = buildVariantAdaptationPrompt(
      contentType,
      platform,
      baseSku,
      variantSku,
      baseContent,
      baseSpec,
      variantSpec
    )

    const promptHash = crypto
      .createHash('sha256')
      .update(`${systemPrompt}\n\n${userPrompt}`, 'utf8')
      .digest('hex')

    // Call OpenAI
    const messages: ChatCompletionMessageParam[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ]

    const maxTokens = requiresJson ? 4000 : (contentType === 'title' ? 200 : 1000)
    const tokenParams = MODEL.startsWith('gpt-5')
      ? ({ max_completion_tokens: maxTokens } as const)
      : ({ max_tokens: maxTokens } as const)

    const completion = await getOpenAIClient().chat.completions.create({
      model: MODEL,
      messages,
      temperature: 0.6, // Slightly lower than full generation for consistency
      stream: false,
      ...(requiresJson ? { response_format: { type: 'json_object' as const } } : {}),
      ...tokenParams,
    })

    const rawResponse = completion.choices[0]?.message?.content?.trim()

    if (!rawResponse) {
      return { success: false, error: 'No content generated from OpenAI' }
    }

    // Parse response
    let newContent: string
    let finishSentences: Record<string, string> | null = null

    if (requiresJson) {
      try {
        const parsed = JSON.parse(rawResponse)
        newContent = parsed.content?.trim()
        finishSentences = parsed.finish_sentences || null

        if (!newContent) {
          return { success: false, error: 'Invalid JSON response: missing content field' }
        }
      } catch {
        newContent = rawResponse
      }
    } else {
      newContent = rawResponse
    }

    // Validate
    const violations = validateGeneratedContent(newContent, platform, contentType)

    if (violations.length > 0) {
      console.warn(`Validation violations for ${variantSku}/${platform}/${contentType}: ${violations.join('; ')}`)
      // Continue anyway - variant adaptation is more forgiving
    }

    // Save to database
    const currentVersion = currentContentData?.version ?? 0
    const nextVersion = currentVersion + 1

    if (currentContentData) {
      const { error: updateError } = await supabase
        .from('generated_content')
        .update({
          candidate_content: newContent,
          version: nextVersion,
          is_current: true,
          generation_model: `${MODEL}-variant-adaptation`,
          generation_prompt_hash: promptHash,
          generation_timestamp: new Date().toISOString(),
        })
        .eq('id', currentContentData.id)

      if (updateError) {
        return { success: false, error: `Failed to update: ${updateError.message}` }
      }
    } else {
      const { error: insertError } = await supabase
        .from('generated_content')
        .insert({
          master_sku: variantSku,
          platform,
          content_type: contentType,
          candidate_content: newContent,
          baseline_content: null,
          version: 1,
          is_current: true,
          generation_model: `${MODEL}-variant-adaptation`,
          generation_prompt_hash: promptHash,
          generation_timestamp: new Date().toISOString(),
        })

      if (insertError) {
        return { success: false, error: `Failed to insert: ${insertError.message}` }
      }
    }

    // Save finish_sentences if present
    if (finishSentences && Object.keys(finishSentences).length > 0 && (platform === 'google' || platform === 'bing')) {
      await supabase
        .from('variant_finish_sentences')
        .upsert(
          {
            master_sku: variantSku,
            platform,
            finish_sentences: finishSentences,
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'master_sku,platform' }
        )
    }

    // Log to regeneration history
    await supabase
      .from('regeneration_history')
      .insert({
        master_sku: variantSku,
        content_type: contentType,
        platform,
        mode: 'variant-adaptation',
        previous_content: currentContentData?.candidate_content || null,
        new_content: newContent,
        model_version: `${MODEL}-variant-adaptation`,
        system_prompt: systemPrompt,
        user_prompt: userPrompt,
        prompt_hash: promptHash,
        quality_score_before: currentContentData?.quality_score || null,
      })

    return {
      success: true,
      content: newContent,
      finishSentences: finishSentences || undefined,
      version: nextVersion,
      model: `${MODEL}-variant-adaptation`,
      usedEvidence: false,
      usedVision: false,
      mode: 'variant-adaptation',
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { success: false, error: message }
  }
}
