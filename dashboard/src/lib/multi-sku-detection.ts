/**
 * Multi-SKU Product Detection
 *
 * Identifies product families where multiple master_skus share the same Shopify product_id.
 * Example: DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share product_id 4539975336068
 */

import type { SupabaseClient } from '@supabase/supabase-js'

export interface MultiSkuFamily {
  productId: string
  masterSkus: string[]
  baseSku: string // Typically the lowest variant (e.g., DMF-2/2X)
  variantSkus: string[] // Related SKUs that need adaptation (e.g., DMF-2/3X, 2/4X, 2/5X)
}

/**
 * Extract Shopify product_id from GMC offer_id
 * shopify_us_4539975336068_32103134298244 → 4539975336068
 */
export function extractProductId(offerId: string): string | null {
  const parts = offerId.split('_')
  return parts.length >= 4 ? parts[2] : null
}

/**
 * Get all master_skus that share the same product_id as the given SKU
 */
export async function getRelatedMasterSkus(
  supabase: SupabaseClient,
  masterSku: string
): Promise<string[]> {
  // Get product_id for this SKU
  const { data: variants } = await supabase
    .from('variant_index')
    .select('gmc_offer_id')
    .eq('master_sku', masterSku)
    .limit(1)

  if (!variants || variants.length === 0) {
    return [masterSku] // Only the SKU itself
  }

  const productId = extractProductId(variants[0].gmc_offer_id)
  if (!productId) {
    return [masterSku]
  }

  // Find all SKUs with the same product_id
  const { data: relatedVariants } = await supabase
    .from('variant_index')
    .select('master_sku, gmc_offer_id')
    .ilike('gmc_offer_id', `shopify_us_${productId}_%`)

  if (!relatedVariants) {
    return [masterSku]
  }

  // Get unique master_skus
  const uniqueSkus = Array.from(
    new Set(relatedVariants.map((v) => v.master_sku))
  ).sort()

  return uniqueSkus
}

/**
 * Detect multi-SKU product families in a list of SKUs
 */
export async function detectMultiSkuFamilies(
  supabase: SupabaseClient,
  masterSkus: string[]
): Promise<MultiSkuFamily[]> {
  const families: MultiSkuFamily[] = []
  const processedSkus = new Set<string>()

  for (const sku of masterSkus) {
    if (processedSkus.has(sku)) continue

    const relatedSkus = await getRelatedMasterSkus(supabase, sku)

    if (relatedSkus.length > 1) {
      // Multi-SKU family detected
      const { data: variants } = await supabase
        .from('variant_index')
        .select('gmc_offer_id')
        .eq('master_sku', relatedSkus[0])
        .limit(1)

      const productId = variants?.[0]?.gmc_offer_id
        ? extractProductId(variants[0].gmc_offer_id) || 'unknown'
        : 'unknown'

      // Base SKU is typically the first alphabetically (e.g., DMF-2/2X before DMF-2/3X)
      const baseSku = relatedSkus[0]
      const variantSkus = relatedSkus.slice(1)

      families.push({
        productId,
        masterSkus: relatedSkus,
        baseSku,
        variantSkus,
      })

      // Mark all related SKUs as processed
      relatedSkus.forEach((s) => processedSkus.add(s))
    } else {
      // Single-SKU product (no adaptation needed)
      processedSkus.add(sku)
    }
  }

  return families
}

/**
 * Check if a SKU is part of a multi-SKU family
 */
export async function isMultiSkuProduct(
  supabase: SupabaseClient,
  masterSku: string
): Promise<boolean> {
  const relatedSkus = await getRelatedMasterSkus(supabase, masterSku)
  return relatedSkus.length > 1
}

/**
 * Get the base SKU for a given variant SKU
 */
export async function getBaseSku(
  supabase: SupabaseClient,
  masterSku: string
): Promise<string> {
  const relatedSkus = await getRelatedMasterSkus(supabase, masterSku)
  return relatedSkus[0] // First alphabetically is the base
}

/**
 * Extract specification difference from SKU names
 * Example: DMF-2/2X vs DMF-2/5X → "2X" vs "5X"
 */
export function extractSpecDifference(baseSku: string, variantSku: string): {
  baseSpec: string
  variantSpec: string
} {
  // Try to find numeric differences like 2X, 3X, 5X, 16-GAL, etc.
  const baseMatch = baseSku.match(/(\d+(?:\.\d+)?[A-Z]*)/g)
  const variantMatch = variantSku.match(/(\d+(?:\.\d+)?[A-Z]*)/g)

  if (baseMatch && variantMatch) {
    // Find the differing spec
    for (let i = 0; i < Math.min(baseMatch.length, variantMatch.length); i++) {
      if (baseMatch[i] !== variantMatch[i]) {
        return {
          baseSpec: baseMatch[i],
          variantSpec: variantMatch[i],
        }
      }
    }
  }

  // Fallback: return full SKU names
  return {
    baseSpec: baseSku,
    variantSpec: variantSku,
  }
}
