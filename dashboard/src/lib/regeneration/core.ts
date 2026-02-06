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

// 28 Allied Brass finishes for product+finish tailored sentences
const FINISH_LIST = [
  'Antique Brass', 'Antique Bronze', 'Antique Copper', 'Antique Pewter',
  'Autumn Sparkle', 'Brushed Bronze', 'Fire Engine Red', 'Flat Troll Blue',
  'Glokzin Teal', 'Golden Yellow', 'Lavender', 'Matte Black', 'Matte Gray',
  'Matte White', 'Mediterranean Blue', 'Oil Rubbed Bronze', 'Pink',
  'Polished Brass', 'Polished Chrome', 'Polished Nickel', 'Satin Brass',
  'Satin Chrome', 'Satin Nickel', 'Sea Foam Green', 'Shaded Beige',
  'Spanish Gold', 'Unlacquered Brass', 'Venetian Bronze',
] as const

// Finish reference for LLM prompt
const FINISH_REFERENCE = `FINISH REFERENCE (28 finishes with their character):
Traditional Warm: Antique Brass (aged patina), Antique Bronze (deep brown), Antique Copper (burnished copper), Oil Rubbed Bronze (copper highlights), Polished Brass (mirror gold), Satin Brass (brushed gold), Spanish Gold (Old World gold), Unlacquered Brass (living patina), Venetian Bronze (golden highlights)
Traditional Cool: Antique Pewter (silvery gray)
Transitional: Brushed Bronze (warm matte), Polished Chrome (bright reflective), Polished Nickel (warm silver), Satin Chrome (brushed silver), Satin Nickel (warm brushed)
Contemporary Neutral: Matte Black (smooth non-reflective), Matte Gray (soft neutral), Matte White (clean crisp)
Statement Colors: Fire Engine Red (bold vibrant), Flat Troll Blue (matte playful), Glokzin Teal (coastal), Golden Yellow (sunny), Lavender (calming purple), Mediterranean Blue (deep sea), Pink (soft feminine), Sea Foam Green (coastal fresh)
Statement Other: Autumn Sparkle (shimmer), Shaded Beige (warm earth)`

// Fallback system prompt
const FALLBACK_SYSTEM_PROMPT = `You are an expert e-commerce content writer for Allied Brass bathroom hardware. Generate titles and descriptions that balance quality messaging with customer motivation.

## Core Principles

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
- Open with the TRUE WHY (customer's deeper motivation) when one exists naturally
- For standard products without dramatic pain points, focus on quality/craftsmanship
- Include {FINISH_SENTENCE} placeholder for Google/Bing descriptions
- Shopify descriptions are finish-agnostic (no placeholders)

## Guardrails
- NEVER invent specifications not in the evidence table
- NO banned words: luxurious, premium, exclusive, unique
- NO ALL CAPS or promotional language
- Claims must trace to evidence`

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
  const platformContext: Record<string, Record<string, string>> = {
    google: {
      title: 'Google Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass. Lead with finish placeholder for search relevance.',
      description: 'Google Shopping description - Open with the TRUE WHY. Plain text, 600-800 characters.',
    },
    bing: {
      title: 'Bing Shopping title - Format: {FINISH_NAME} [Product] [Key Specs] - [Differentiator] - [Collection] - Allied Brass. Include natural product synonyms.',
      description: 'Bing Shopping description - Open with the TRUE WHY. Include product synonyms naturally. Plain text, 700-1000 characters.',
    },
    shopify: {
      title: 'Shopify product title (H1) - NO finish name, NO "Allied Brass". Customer already clicked.',
      description: 'Shopify description - customer already clicked, convince them to buy. Mention 28 finishes. HTML format with <p> and <ul><li>. Do NOT include specific finish names or "Allied Brass".',
    },
  }

  const context = platformContext[platform]?.[contentType] || ''

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

FINISH SENTENCES (CRITICAL):
Generate 28 finish-specific sentences - one for each finish.
Each sentence should describe how THAT FINISH relates to THIS SPECIFIC PRODUCT.
DO NOT include Military Camo or Red White and Blue.

${FINISH_REFERENCE}

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
- For Google/Bing titles: Use {FINISH_NAME} placeholder at the START, then product/specs, then collection, then "Allied Brass"
- For Shopify titles: NO finish placeholder, NO "Allied Brass" anywhere in the title
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
  const platformContext: Record<string, Record<string, string>> = {
    google: {
      title: 'Google Shopping title - {FINISH_NAME} [Product] [Specs] - [Collection] - Allied Brass',
      description: 'Google Shopping description - Plain text only.',
    },
    bing: {
      title: 'Bing Shopping title - {FINISH_NAME} [Product] [Specs] - [Collection] - Allied Brass',
      description: 'Bing Shopping description - Plain text only.',
    },
    shopify: {
      title: 'Shopify product title - NO finish name, NO "Allied Brass".',
      description: 'Shopify description - HTML format. NO "Allied Brass", NO specific finish names.',
    },
  }

  const context = platformContext[platform]?.[contentType] || ''
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

    // Load prompt template
    let promptTemplate: PromptTemplate | null = null
    let systemPrompt = FALLBACK_SYSTEM_PROMPT

    try {
      promptTemplate = await loadActivePromptTemplate(supabase)
      if (promptTemplate) {
        systemPrompt = promptTemplate.system_prompt
      }
    } catch {
      // Use fallback
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
