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
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { success: false, error: message }
  }
}
