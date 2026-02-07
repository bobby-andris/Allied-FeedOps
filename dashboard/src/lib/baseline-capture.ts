/**
 * Performance baseline capture for pre-publish metrics
 *
 * Captures 30-day performance baseline before publishing content.
 * This allows measuring the impact of content optimization by comparing
 * baseline metrics to post-publish performance snapshots.
 */

import type { SupabaseClient } from '@supabase/supabase-js'
import { fetchShoppingPerformance, getDateRange } from './google-ads'

export interface PerformanceBaseline {
  master_sku: string
  platform: 'google' | 'bing'
  baseline_start_date: string
  baseline_end_date: string
  avg_impressions: number
  avg_clicks: number
  avg_ctr: number
  avg_conversions: number
  avg_conversion_value: number
  avg_cvr: number  // Conversion rate (conversions / clicks)
  avg_cost: number
  avg_roas: number
}

/**
 * Capture 30-day performance baseline for a master SKU before publishing
 *
 * @param supabase - Supabase client for database access
 * @param masterSku - Master SKU to capture baseline for
 * @param platform - Platform (google or bing)
 * @returns Performance baseline data, or null if no data available
 */
export async function captureBaseline(
  supabase: SupabaseClient,
  masterSku: string,
  platform: 'google' | 'bing'
): Promise<PerformanceBaseline | null> {
  // Get Shopify product ID from variant_index
  const { data: variant, error: variantError } = await supabase
    .from('variant_index')
    .select('shopify_product_id')
    .eq('master_sku', masterSku)
    .limit(1)
    .single()

  if (variantError || !variant) {
    console.warn(`No variant found for master SKU ${masterSku}`)
    return null
  }

  const shopifyProductId = variant.shopify_product_id

  // Get 30-day date range
  const { startDate, endDate } = getDateRange('30d')

  // Fetch performance data from Google Ads
  const performanceMap = await fetchShoppingPerformance(
    [shopifyProductId],
    startDate,
    endDate
  )

  const performance = performanceMap.get(shopifyProductId)

  // Return null if no performance data
  if (!performance || performance.impressions === 0) {
    console.warn(`No performance data for SKU ${masterSku} (product ID ${shopifyProductId})`)
    return null
  }

  // Calculate averages (30-day baseline)
  const days = 30
  const avgImpressions = Math.round((performance.impressions / days) * 100) / 100
  const avgClicks = Math.round((performance.clicks / days) * 100) / 100
  const avgConversions = Math.round((performance.conversions / days) * 100) / 100
  const avgConversionValue = Math.round((performance.conversionValue / days) * 100) / 100
  const avgCost = Math.round((performance.cost / days) * 100) / 100

  // Calculate CVR (conversion rate = conversions / clicks)
  const avgCvr = performance.clicks > 0
    ? Math.round((performance.conversions / performance.clicks) * 10000) / 10000
    : 0

  const baseline: PerformanceBaseline = {
    master_sku: masterSku,
    platform,
    baseline_start_date: startDate,
    baseline_end_date: endDate,
    avg_impressions: avgImpressions,
    avg_clicks: avgClicks,
    avg_ctr: performance.ctr,
    avg_conversions: avgConversions,
    avg_conversion_value: avgConversionValue,
    avg_cvr: avgCvr,
    avg_cost: avgCost,
    avg_roas: performance.roas,
  }

  // Upsert to performance_baselines table
  const { error: upsertError } = await supabase
    .from('performance_baselines')
    .upsert({
      master_sku: baseline.master_sku,
      platform: baseline.platform,
      baseline_start_date: baseline.baseline_start_date,
      baseline_end_date: baseline.baseline_end_date,
      avg_impressions: baseline.avg_impressions,
      avg_clicks: baseline.avg_clicks,
      avg_ctr: baseline.avg_ctr,
      avg_conversions: baseline.avg_conversions,
      avg_conversion_value: baseline.avg_conversion_value,
      avg_cvr: baseline.avg_cvr,
      avg_cost: baseline.avg_cost,
      avg_roas: baseline.avg_roas,
    })

  if (upsertError) {
    console.error(`Failed to upsert baseline for ${masterSku}:`, upsertError)
    throw new Error(`Failed to store baseline: ${upsertError.message}`)
  }

  console.log(`Captured baseline for ${masterSku} (${platform}): ${avgImpressions} avg impressions/day`)

  return baseline
}
