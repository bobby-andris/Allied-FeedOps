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

import { generateVariantTitle, generateVariantDescription } from '@/lib/variant-content'
import { createClient } from '@/lib/supabase/server'

export interface ExpandedVariant {
  gmc_offer_id: string
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

/**
 * Query approved lifestyle images for a master SKU that have been migrated to Shopify CDN.
 * Returns a map of finish_code -> shopify_cdn_url for variant-specific images,
 * plus a master image URL if use_for_master is true.
 *
 * Strategy:
 * - Fetch all approved images for the SKU that have Shopify CDN URLs
 * - Build a map of finish-specific images (keyed by finish_code)
 * - Extract master image (use_for_master = true) as fallback
 *
 * IMPORTANT: Only images migrated to Shopify CDN are returned. Supabase Storage URLs
 * are not published to Google Sheets - they're only for review workflow.
 */
async function queryApprovedImages(
  supabase: Awaited<ReturnType<typeof createClient>>,
  master_sku: string
): Promise<{
  finishImages: Map<string, string>
  masterImageUrl: string | null
}> {
  const { data: images, error } = await supabase
    .from('generated_images')
    .select('finish_code, shopify_cdn_url, use_for_master')
    .eq('master_sku', master_sku)
    .eq('approval_status', 'approved')
    .not('shopify_cdn_url', 'is', null)

  if (error) {
    console.error('Error fetching approved images:', error)
    return { finishImages: new Map(), masterImageUrl: null }
  }

  if (!images || images.length === 0) {
    return { finishImages: new Map(), masterImageUrl: null }
  }

  const finishImages = new Map<string, string>()
  let masterImageUrl: string | null = null

  for (const img of images) {
    // Extract master image (applies to all variants)
    if (img.use_for_master && img.shopify_cdn_url) {
      masterImageUrl = img.shopify_cdn_url
    }

    // Extract finish-specific images
    if (img.finish_code && img.shopify_cdn_url && !img.use_for_master) {
      finishImages.set(img.finish_code, img.shopify_cdn_url)
    }
  }

  return { finishImages, masterImageUrl }
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

  // Get all variants for this SKU from variant_index
  const { data: variants, error: variantError } = await supabase
    .from('variant_index')
    .select('gmc_offer_id, finish, finish_code')
    .eq('master_sku', master_sku)

  if (variantError) {
    console.error('Error fetching variants:', variantError)
    return []
  }

  if (!variants?.length) {
    console.warn(`No variants found for master_sku: ${master_sku}`)
    return []
  }

  // Get finish sentences for this SKU/platform (product-specific finish descriptions)
  const { data: finishData, error: finishError } = await supabase
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', master_sku)
    .eq('platform', platform)
    .single()

  if (finishError && finishError.code !== 'PGRST116') {
    // PGRST116 = no rows found, which is OK (we'll use generic fallback)
    console.error('Error fetching finish sentences:', finishError)
  }

  const finishSentences = (finishData?.finish_sentences as Record<string, string>) || {}

  // Query approved lifestyle images for this SKU
  const { finishImages, masterImageUrl } = await queryApprovedImages(supabase, master_sku)

  // Expand each variant
  return variants.map((v) => {
    // Determine image URL: finish-specific takes precedence, then master fallback
    const imageUrl = v.finish_code
      ? finishImages.get(v.finish_code) || masterImageUrl || undefined
      : masterImageUrl || undefined

    return {
      gmc_offer_id: v.gmc_offer_id,
      finish: v.finish || 'Unknown',
      finish_code: v.finish_code,
      title: generateVariantTitle(approved_title, v.finish || 'Unknown', platform),
      description: generateVariantDescription(
        approved_description,
        v.finish || 'Unknown',
        finishSentences
      ),
      image_url: imageUrl,
    }
  })
}

/**
 * Get the count of variants for a master SKU without expanding content.
 * Useful for pre-validation.
 */
export async function getVariantCount(master_sku: string): Promise<number> {
  const supabase = await createClient()

  const { count, error } = await supabase
    .from('variant_index')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', master_sku)

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
}> {
  const supabase = await createClient()

  // Get approved content for both title and description
  const { data, error } = await supabase
    .from('generated_content')
    .select('content_type, approved_content')
    .eq('master_sku', master_sku)
    .eq('platform', platform)
    .in('content_type', ['title', 'description'])

  if (error) {
    return {
      isValid: false,
      title: null,
      description: null,
      errors: [`Database error: ${error.message}`],
    }
  }

  const contentMap = new Map<string, string | null>()
  data?.forEach((row) => {
    contentMap.set(row.content_type, row.approved_content)
  })

  const errors: string[] = []
  const title = contentMap.get('title') || null
  const description = contentMap.get('description') || null

  if (!title) {
    errors.push(`No approved title for ${platform}`)
  }
  if (!description) {
    errors.push(`No approved description for ${platform}`)
  }

  // Also check approval status
  const { data: approval } = await supabase
    .from('sku_approvals')
    .select('approval_status, title_approved, description_approved')
    .eq('master_sku', master_sku)
    .single()

  if (!approval) {
    errors.push('No approval record found')
  } else if (approval.approval_status !== 'approved') {
    errors.push(`SKU approval status is "${approval.approval_status}", expected "approved"`)
  }

  return {
    isValid: errors.length === 0,
    title,
    description,
    errors,
  }
}
