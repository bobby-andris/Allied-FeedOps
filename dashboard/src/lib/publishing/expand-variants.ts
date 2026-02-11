/**
 * Expand Variants for Publishing
 *
 * Takes a master SKU's approved content (with {FINISH_NAME} templates)
 * and expands it to generate unique content for each variant.
 *
 * Uses:
 * - variant_index: Maps master_sku to all variant gmc_offer_ids with finish info
 * - variant_finish_sentences: Product-specific finish sentences for descriptions
 * - variant-content.ts: Template expansion utilities
 */

import { generateVariantTitle, generateVariantDescription, templateHasHardcodedFinish } from '@/lib/variant-content'
import { PLACEHOLDERS } from '@/lib/finish-data'
import { resolveCanonicalMasterSku } from '@/lib/master-sku'
import { createClient } from '@/lib/supabase/server'

export interface ExpandedVariant {
  gmc_offer_id: string
  master_sku: string
  finish: string
  finish_code: string | null
  title: string
  description: string
  image_url?: string
}

export interface ExpandVariantsOptions {
  master_sku: string
  platform: 'google' | 'bing'
  approved_title: string
  approved_description: string
}

interface ContentValidationIssue {
  code: string
  message: string
  actionable_message: string
}

const EXPECTED_FINISH_SENTENCE_COUNT = 28
const GENERIC_FINISH_COUNT_PATTERNS = [
  /\bfinish options:\s*available in[^.!\n]*(?:designer\s+)?finishes[^.!\n]*[.!]?/i,
  /\bavailable in (?:a wide variety of )?(?:lifetime )?(?:multiple|\d+)\s+(?:designer\s+)?finishes[^.!\n]*[.!]?/i,
  /\bmultiple designer finish options available\b[.!]?/i,
]

function countOccurrences(content: string, marker: string): number {
  if (!marker) return 0
  return content.split(marker).length - 1
}

function hasGenericFinishCountClaim(content: string): boolean {
  return GENERIC_FINISH_COUNT_PATTERNS.some((pattern) => pattern.test(content))
}

function normalizeFinishSentences(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return {}
  }
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>)
      .filter(([finish, sentence]) => {
        return typeof finish === 'string'
          && finish.trim().length > 0
          && typeof sentence === 'string'
          && sentence.trim().length > 0
      })
      .map(([finish, sentence]) => [finish.trim(), (sentence as string).trim()])
  )
}

function firstHardcodedFinish(content: string): string | null {
  const scrubbed = content
    .replace(new RegExp(PLACEHOLDERS.FINISH_SENTENCE, 'g'), ' ')
    .replace(new RegExp(PLACEHOLDERS.FINISH_NAME, 'g'), ' ')
    .replace(new RegExp(PLACEHOLDERS.FINISH_DESCRIPTION, 'g'), ' ')
  return templateHasHardcodedFinish(scrubbed)
}

/**
 * Query approved variant lifestyle images for publishing to GMC feed.
 * Returns map of gmc_offer_id -> shopify_cdn_url
 *
 * IMPORTANT: Only returns images that have been migrated to Shopify CDN.
 * Images still in Supabase Storage (not yet migrated) are excluded.
 *
 * Uses new variant_lifestyle_images table which properly links to gmc_offer_id
 * for precise variant-to-image mapping.
 */
async function queryApprovedVariantImages(
  supabase: Awaited<ReturnType<typeof createClient>>,
  master_sku: string
): Promise<Map<string, string>> {
  const { data: images, error } = await supabase
    .from('variant_lifestyle_images')
    .select('gmc_offer_id, shopify_cdn_url')
    .eq('master_sku', master_sku)
    .eq('approval_status', 'approved')
    .not('shopify_cdn_url', 'is', null)  // Must be migrated to CDN

  if (error) {
    console.error('Error fetching approved variant images:', error)
    return new Map()
  }

  const imageMap = new Map<string, string>()
  for (const img of images || []) {
    if (img.shopify_cdn_url) {
      imageMap.set(img.gmc_offer_id, img.shopify_cdn_url)
    }
  }

  return imageMap
}

/**
 * Expand templates for all variants of a master SKU.
 *
 * For each variant (finish), replaces {FINISH_NAME} in the title
 * and generates a variant-specific description using finish sentences.
 *
 * @returns Array of expanded variants ready for publishing
 */
export async function expandVariantsForPublish(
  options: ExpandVariantsOptions
): Promise<ExpandedVariant[]> {
  const { master_sku, platform, approved_title, approved_description } = options
  const supabase = await createClient()
  const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)

  // Get all variants for this SKU from variant_index
  const { data: variants, error: variantError } = await supabase
    .from('variant_index')
    .select('gmc_offer_id, finish, finish_code')
    .eq('master_sku', canonicalMasterSku)

  if (variantError) {
    console.error('Error fetching variants:', variantError)
    return []
  }

  if (!variants?.length) {
    console.warn(`No variants found for master_sku: ${canonicalMasterSku}`)
    return []
  }

  // Get finish sentences for this SKU/platform (product-specific finish descriptions)
  const { data: finishData, error: finishError } = await supabase
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', canonicalMasterSku)
    .eq('platform', platform)
    .single()

  if (finishError && finishError.code !== 'PGRST116') {
    // PGRST116 = no rows found, which is OK (we'll use generic fallback)
    console.error('Error fetching finish sentences:', finishError)
  }

  const finishSentences = normalizeFinishSentences(finishData?.finish_sentences)

  const finishPlaceholderCount = countOccurrences(approved_description, PLACEHOLDERS.FINISH_SENTENCE)
  if (finishPlaceholderCount < 1) {
    throw new Error('variant_finish_contradiction: publish_google_description_missing_finish_placeholder')
  }
  if (finishPlaceholderCount > 1) {
    throw new Error('variant_finish_contradiction: publish_google_description_multiple_finish_placeholders')
  }
  if (firstHardcodedFinish(approved_description)) {
    throw new Error('variant_finish_contradiction: publish_google_description_contains_finish_name')
  }
  if (hasGenericFinishCountClaim(approved_description)) {
    throw new Error('variant_finish_contradiction: publish_google_description_contains_generic_finish_count_claim')
  }
  if (Object.keys(finishSentences).length !== EXPECTED_FINISH_SENTENCE_COUNT) {
    throw new Error('variant_finish_contradiction: publish_google_finish_sentences_incomplete')
  }

  // Get approved variant images (with CDN URLs)
  const variantImages = await queryApprovedVariantImages(supabase, canonicalMasterSku)

  // Expand each variant
  return variants.map((v) => ({
    gmc_offer_id: v.gmc_offer_id,
    master_sku: canonicalMasterSku,
    finish: v.finish || 'Unknown',
    finish_code: v.finish_code,
    title: generateVariantTitle(approved_title, v.finish || 'Unknown', platform),
    description: generateVariantDescription(
      approved_description,
      v.finish || 'Unknown',
      finishSentences
    ),
    image_url: variantImages.get(v.gmc_offer_id),  // Direct lookup by gmc_offer_id
  }))
}

/**
 * Get the count of variants for a master SKU without expanding content.
 * Useful for pre-validation.
 */
export async function getVariantCount(master_sku: string): Promise<number> {
  const supabase = await createClient()
  const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)

  const { count, error } = await supabase
    .from('variant_index')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', canonicalMasterSku)

  if (error) {
    console.error('Error counting variants:', error)
    return 0
  }

  return count || 0
}

/**
 * Validate that content is ready for publishing (has approved_content).
 */
export async function validateContentForPublishing(
  master_sku: string,
  platform: 'google' | 'bing' | 'shopify'
): Promise<{
  isValid: boolean
  title: string | null
  description: string | null
  errors: string[]
  issues: ContentValidationIssue[]
}> {
  const supabase = await createClient()
  const canonicalMasterSku = await resolveCanonicalMasterSku(supabase, master_sku)
  const issues: ContentValidationIssue[] = []

  // Get approved content for both title and description
  const { data, error } = await supabase
    .from('generated_content')
    .select('content_type, approved_content')
    .eq('master_sku', canonicalMasterSku)
    .eq('platform', platform)
    .in('content_type', ['title', 'description'])

  if (error) {
    issues.push({
      code: 'publish_content_lookup_failed',
      message: `Database error: ${error.message}`,
      actionable_message: 'Retry publish. If this persists, inspect generated_content table access.',
    })
    return {
      isValid: false,
      title: null,
      description: null,
      errors: issues.map((issue) => issue.message),
      issues,
    }
  }

  const contentMap = new Map<string, string | null>()
  data?.forEach((row) => {
    contentMap.set(row.content_type, row.approved_content)
  })

  const title = contentMap.get('title') || null
  const description = contentMap.get('description') || null

  if (!title) {
    issues.push({
      code: `publish_missing_approved_title_${platform}`,
      message: `No approved title for ${platform}`,
      actionable_message: `Approve ${platform} title content before publishing.`,
    })
  }
  if (!description) {
    issues.push({
      code: `publish_missing_approved_description_${platform}`,
      message: `No approved description for ${platform}`,
      actionable_message: `Approve ${platform} description content before publishing.`,
    })
  }

  // Also check approval status
  const { data: approval } = await supabase
    .from('sku_approvals')
    .select('approval_status, title_approved, description_approved')
    .eq('master_sku', canonicalMasterSku)
    .single()

  if (!approval) {
    issues.push({
      code: 'publish_missing_approval_record',
      message: 'No approval record found',
      actionable_message: 'Approve this SKU in Review before publishing.',
    })
  } else if (approval.approval_status !== 'approved') {
    issues.push({
      code: 'publish_requires_approved_sku',
      message: `SKU approval status is "${approval.approval_status}", expected "approved"`,
      actionable_message: 'Approve this SKU in Review before publishing.',
    })
  }

  if (platform === 'google' || platform === 'bing') {
    if (description) {
      const finishPlaceholderCount = countOccurrences(description, PLACEHOLDERS.FINISH_SENTENCE)
      if (finishPlaceholderCount < 1) {
        issues.push({
          code: 'publish_google_description_missing_finish_placeholder',
          message: 'Google/Bing description must include exactly one {FINISH_SENTENCE} placeholder',
          actionable_message: 'Regenerate Google/Bing description so it includes one {FINISH_SENTENCE} placeholder.',
        })
      } else if (finishPlaceholderCount > 1) {
        issues.push({
          code: 'publish_google_description_multiple_finish_placeholders',
          message: 'Google/Bing description contains multiple {FINISH_SENTENCE} placeholders',
          actionable_message: 'Regenerate Google/Bing description so it contains a single {FINISH_SENTENCE} placeholder.',
        })
      }

      const hardcodedFinish = firstHardcodedFinish(description)
      if (hardcodedFinish) {
        issues.push({
          code: 'publish_google_description_contains_finish_name',
          message: `Google/Bing description contains hardcoded finish "${hardcodedFinish}"`,
          actionable_message: 'Regenerate Google/Bing description to make base copy finish-agnostic.',
        })
      }
      if (hasGenericFinishCountClaim(description)) {
        issues.push({
          code: 'publish_google_description_contains_generic_finish_count_claim',
          message: 'Google/Bing description contains generic finish-count claim language',
          actionable_message: 'Regenerate Google/Bing description to remove generic finish-count claims.',
        })
      }
    }

    const { data: finishData, error: finishError } = await supabase
      .from('variant_finish_sentences')
      .select('finish_sentences')
      .eq('master_sku', canonicalMasterSku)
      .eq('platform', platform)
      .maybeSingle()

    if (finishError && finishError.code !== 'PGRST116') {
      issues.push({
        code: 'publish_google_finish_sentences_lookup_failed',
        message: `Failed to load variant_finish_sentences: ${finishError.message}`,
        actionable_message: 'Retry publish. If this persists, inspect variant_finish_sentences table access.',
      })
    } else {
      const finishSentences = normalizeFinishSentences(finishData?.finish_sentences)
      if (Object.keys(finishSentences).length !== EXPECTED_FINISH_SENTENCE_COUNT) {
        issues.push({
          code: 'publish_google_finish_sentences_incomplete',
          message: `Expected ${EXPECTED_FINISH_SENTENCE_COUNT} finish sentences, found ${Object.keys(finishSentences).length}`,
          actionable_message: 'Regenerate Google/Bing descriptions to repopulate complete variant_finish_sentences coverage.',
        })
      }
    }
  }

  if (platform === 'shopify') {
    if (title) {
      if (title.toLowerCase().includes('allied brass')) {
        issues.push({
          code: 'publish_shopify_title_contains_brand',
          message: 'Shopify title contains "Allied Brass"',
          actionable_message: 'Regenerate Shopify title to remove brand mention.',
        })
      }
      const titleFinish = firstHardcodedFinish(title)
      if (titleFinish) {
        issues.push({
          code: 'publish_shopify_title_contains_finish_name',
          message: `Shopify title contains finish name "${titleFinish}"`,
          actionable_message: 'Regenerate Shopify title to keep it finish-agnostic.',
        })
      }
    }

    if (description) {
      const hasFinishPlaceholder = (
        description.includes(PLACEHOLDERS.FINISH_NAME)
        || description.includes(PLACEHOLDERS.FINISH_SENTENCE)
        || description.includes(PLACEHOLDERS.FINISH_DESCRIPTION)
      )
      if (hasFinishPlaceholder) {
        issues.push({
          code: 'publish_shopify_description_contains_finish_placeholder',
          message: 'Shopify description contains finish placeholders',
          actionable_message: 'Regenerate Shopify description to remove finish placeholders.',
        })
      }

      const descriptionFinish = firstHardcodedFinish(description)
      if (descriptionFinish) {
        issues.push({
          code: 'publish_shopify_description_contains_finish_name',
          message: `Shopify description contains finish name "${descriptionFinish}"`,
          actionable_message: 'Regenerate Shopify description so base copy is finish-agnostic.',
        })
      }
    }
  }

  return {
    isValid: issues.length === 0,
    title,
    description,
    errors: issues.map((issue) => issue.message),
    issues,
  }
}
