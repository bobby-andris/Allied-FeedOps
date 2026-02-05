/**
 * Supabase query helpers for evidence table builder
 */

import type { SupabaseClient } from '@supabase/supabase-js'
import type { ProductCatalogRow, EvidenceContext, ProductEvidenceResult } from './types'
import { buildEvidenceTable, formatEvidenceMarkdown } from './builder'
import {
  getSearchQueriesForMasterSku,
  getSearchQueriesForVariant,
  formatSearchQueriesForEvidence,
} from './search-queries'

/**
 * Get product evidence from product_catalog table
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU to look up
 * @param context - Platform and variant context
 * @returns Evidence array, formatted markdown, and image URL
 */
export async function getProductEvidence(
  supabase: SupabaseClient,
  masterSku: string,
  context: EvidenceContext
): Promise<ProductEvidenceResult> {
  // Query all variants for this master SKU
  const { data: rows, error } = await supabase
    .from('product_catalog')
    .select('*')
    .eq('master_sku', masterSku)
    .order('position')

  if (error) {
    console.error('Error fetching product catalog:', error)
    throw new Error(`Failed to fetch product catalog: ${error.message}`)
  }

  if (!rows || rows.length === 0) {
    throw new Error(`Product not found in catalog: ${masterSku}`)
  }

  let evidence = buildEvidenceTable(rows as ProductCatalogRow[], context)

  // Add search query insights (actual search terms customers use)
  const searchQueries = await getSearchQueriesForMasterSku(supabase, masterSku).catch(() => [])
  if (searchQueries.length > 0) {
    const searchEvidence = formatSearchQueriesForEvidence(searchQueries, 'master')
    evidence = [...evidence, ...searchEvidence]
  }

  // For variant-specific contexts (Google/Bing), also add variant queries
  if (context.finish_code && (context.platform === 'google' || context.platform === 'bing')) {
    const variantQueries = await getSearchQueriesForVariant(
      supabase,
      masterSku,
      context.finish_code
    ).catch(() => [])
    if (variantQueries.length > 0) {
      const variantEvidence = formatSearchQueriesForEvidence(variantQueries, 'variant')
      evidence = [...evidence, ...variantEvidence]
    }
  }

  const markdown = formatEvidenceMarkdown(evidence)

  // Extract image URL from evidence
  const imageEvidence = evidence.find((e) => e.field === 'product_image_url')
  const imageUrl = imageEvidence?.value ?? null

  return { evidence, markdown, imageUrl }
}

/**
 * Get variant evidence by GMC offer ID
 *
 * @param supabase - Supabase client
 * @param gmcId - Google Merchant Center offer ID (e.g., shopify_US_123_456)
 * @param platform - Target platform (google or bing)
 * @returns Evidence array, formatted markdown, and image URL
 */
export async function getVariantEvidence(
  supabase: SupabaseClient,
  gmcId: string,
  platform: 'google' | 'bing'
): Promise<ProductEvidenceResult> {
  // First get the variant to find master_sku and finish_code
  const { data: variant, error: variantError } = await supabase
    .from('product_catalog')
    .select('master_sku, finish_code')
    .eq('gmc_id', gmcId)
    .single()

  if (variantError || !variant) {
    throw new Error(`Variant not found for GMC ID: ${gmcId}`)
  }

  return getProductEvidence(supabase, variant.master_sku, {
    platform,
    finish_code: variant.finish_code,
  })
}

/**
 * Check if product exists in catalog
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU to check
 * @returns true if product exists
 */
export async function productExistsInCatalog(
  supabase: SupabaseClient,
  masterSku: string
): Promise<boolean> {
  const { count, error } = await supabase
    .from('product_catalog')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', masterSku)

  if (error) {
    console.error('Error checking product catalog:', error)
    return false
  }

  return (count ?? 0) > 0
}

/**
 * Get variant finish code from variant_index table
 * Falls back to this when we have master_sku but no direct finish info
 *
 * @param supabase - Supabase client
 * @param masterSku - Master SKU
 * @param finishName - Finish name (e.g., "Polished Chrome")
 * @returns Finish code or null
 */
export async function getFinishCodeFromVariantIndex(
  supabase: SupabaseClient,
  masterSku: string,
  finishName?: string
): Promise<string | null> {
  let query = supabase
    .from('variant_index')
    .select('finish_code')
    .eq('master_sku', masterSku)

  if (finishName) {
    query = query.eq('finish', finishName)
  }

  const { data, error } = await query.limit(1).single()

  if (error || !data) {
    return null
  }

  return data.finish_code
}
