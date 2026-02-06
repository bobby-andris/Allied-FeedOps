/**
 * Prompt Loader - Load gold standard examples and prompts from Supabase
 *
 * Fetches the active prompt template which includes:
 * - System prompt with TRUE WHY framework
 * - 10 gold standard examples for few-shot learning
 * - Category-specific guidance
 * - Platform rules
 */

import { SupabaseClient } from '@supabase/supabase-js'

export interface GoldStandardExample {
  index: number
  category: string
  master_sku: string
  gold_standard_content: {
    google_title: string
    bing_title?: string
    shopify_title: string
    google_description: string
    bing_description?: string
    shopify_description: string
    why_it_works: string
  }
}

export interface PlatformRules {
  google: {
    title_structure: string
    description_placeholder: string
    brand_suffix: string
  }
  bing: {
    title_structure: string
    description_placeholder: string
    brand_suffix: string
  }
  shopify: {
    title_structure: string
    description_placeholder: string | null
    brand_suffix: string | null
    notes: string
  }
  finish_count: number
  excluded_finishes: string[]
}

export interface PromptTemplate {
  id: string
  name: string
  version: number
  is_active: boolean
  system_prompt: string
  gold_standard_examples: {
    version: string
    examples: GoldStandardExample[]
  }
  category_guidance: Record<string, string>
  platform_rules: PlatformRules
  description: string | null
  created_at: string
}

// Cache for loaded template (5 minute TTL)
let cachedTemplate: PromptTemplate | null = null
let cacheTimestamp: number = 0
const CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes

/**
 * Load the active prompt template from Supabase
 * Returns cached version if available and not expired
 */
export async function loadActivePromptTemplate(
  supabase: SupabaseClient
): Promise<PromptTemplate | null> {
  // Check cache
  const now = Date.now()
  if (cachedTemplate && (now - cacheTimestamp) < CACHE_TTL_MS) {
    return cachedTemplate
  }

  try {
    const { data, error } = await supabase
      .from('prompt_templates')
      .select('*')
      .eq('is_active', true)
      .single()

    if (error) {
      console.warn('Failed to load active prompt template:', error.message)
      return null
    }

    if (!data) {
      console.warn('No active prompt template found')
      return null
    }

    // Update cache
    cachedTemplate = data as PromptTemplate
    cacheTimestamp = now

    return cachedTemplate
  } catch (err) {
    console.error('Error loading prompt template:', err)
    return null
  }
}

/**
 * Get category guidance for a specific category
 */
export function getCategoryGuidance(
  template: PromptTemplate,
  category: string
): string | null {
  if (!template.category_guidance) return null

  // Try exact match first
  if (template.category_guidance[category]) {
    return template.category_guidance[category]
  }

  // Try partial match (e.g., "Towel Bars" matches "Towel Bars - Standard")
  for (const [key, value] of Object.entries(template.category_guidance)) {
    if (category.toLowerCase().includes(key.toLowerCase()) ||
        key.toLowerCase().includes(category.toLowerCase())) {
      return value
    }
  }

  return null
}

/**
 * Format gold standard examples for inclusion in prompt
 */
export function formatGoldStandardExamples(
  template: PromptTemplate,
  platform: 'google' | 'bing' | 'shopify',
  contentType: 'title' | 'description',
  maxExamples: number = 3
): string {
  const examples = template.gold_standard_examples.examples.slice(0, maxExamples)

  const formattedExamples = examples.map((ex, idx) => {
    const content = ex.gold_standard_content
    const title = platform === 'shopify' ? content.shopify_title : content.google_title
    const description = platform === 'shopify' ? content.shopify_description : content.google_description

    if (contentType === 'title') {
      return `Example ${idx + 1} (${ex.category}):
Title: ${title}
Why it works: ${content.why_it_works}`
    } else {
      return `Example ${idx + 1} (${ex.category}):
Description: ${description}
Why it works: ${content.why_it_works}`
    }
  })

  return formattedExamples.join('\n\n')
}

// NOTE: buildSystemPromptFromTemplate was removed.
// The system prompt now lives in code at @/lib/regeneration/prompts.ts (SYSTEM_PROMPT).
// This loader only provides gold standard examples and category guidance from the DB.

/**
 * Get excluded finishes from platform rules
 */
export function getExcludedFinishes(template: PromptTemplate): string[] {
  return template.platform_rules?.excluded_finishes || []
}

/**
 * Get finish count from platform rules
 */
export function getFinishCount(template: PromptTemplate): number {
  return template.platform_rules?.finish_count || 28
}

/**
 * Clear the cached template (useful for testing or after template updates)
 */
export function clearPromptCache(): void {
  cachedTemplate = null
  cacheTimestamp = 0
}
