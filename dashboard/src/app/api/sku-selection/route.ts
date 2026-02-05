import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { scoreSkus, selectSkus, type SkuMetrics } from '@/lib/sku-scoring'
import { fetchShoppingPerformance, getDateRange, isGoogleAdsConfigured } from '@/lib/google-ads'

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const count = parseInt(searchParams.get('count') || '20')
    const excludeOptimized = searchParams.get('excludeOptimized') !== 'false'

    const supabase = await createClient()

    // Get already optimized SKUs from sku_approvals
    const { data: approvals } = await supabase
      .from('sku_approvals')
      .select('master_sku, approval_status')

    const optimizedSkus = new Set(
      (approvals || [])
        .filter((a) => a.approval_status === 'approved')
        .map((a) => a.master_sku)
    )

    // Get product info from variant_index
    const { data: variants } = await supabase
      .from('variant_index')
      .select('master_sku, product_title, product_category, shopify_product_id')

    // Group variants by master_sku
    const skuMap = new Map<
      string,
      { product_name: string; category: string; shopify_product_id: string | null; variant_count: number }
    >()

    for (const v of variants || []) {
      const existing = skuMap.get(v.master_sku)
      if (!existing) {
        skuMap.set(v.master_sku, {
          product_name: v.product_title || v.master_sku,
          category: v.product_category || 'Uncategorized',
          shopify_product_id: v.shopify_product_id,
          variant_count: 1,
        })
      } else {
        existing.variant_count++
      }
    }

    // Build SKU metrics
    let skuMetrics: SkuMetrics[]
    let usingSampleData = false

    if (isGoogleAdsConfigured()) {
      // Fetch real performance data from Google Ads
      const shopifyProductIds = [...new Set(
        Array.from(skuMap.values())
          .filter((v) => v.shopify_product_id)
          .map((v) => v.shopify_product_id!)
      )]

      if (shopifyProductIds.length > 0) {
        const { startDate, endDate } = getDateRange('30d')
        try {
          const performanceMap = await fetchShoppingPerformance(
            shopifyProductIds,
            startDate,
            endDate
          )

          skuMetrics = Array.from(skuMap.entries()).map(([master_sku, info]) => {
            const perf = info.shopify_product_id
              ? performanceMap.get(info.shopify_product_id)
              : undefined

            return {
              master_sku,
              product_name: info.product_name,
              category: info.category,
              impressions: perf?.impressions || 0,
              clicks: perf?.clicks || 0,
              conversions: perf?.conversions || 0,
              revenue: perf?.conversionValue || 0,
              cost: perf?.cost || 0,
              variant_count: info.variant_count,
              already_optimized: optimizedSkus.has(master_sku),
            }
          })
        } catch (googleAdsError) {
          console.error('Google Ads API failed, falling back to sample data:', googleAdsError)
          skuMetrics = generateSampleMetrics(skuMap, optimizedSkus)
          usingSampleData = true
        }
      } else {
        skuMetrics = generateSampleMetrics(skuMap, optimizedSkus)
        usingSampleData = true
      }
    } else {
      // Generate sample data when Google Ads is not configured
      skuMetrics = generateSampleMetrics(skuMap, optimizedSkus)
      usingSampleData = true
    }

    // Score and select SKUs
    const scored = scoreSkus(skuMetrics)
    const selection = selectSkus(scored, count, excludeOptimized)

    return NextResponse.json({
      ...selection,
      google_ads_configured: isGoogleAdsConfigured(),
      using_sample_data: usingSampleData,
    })
  } catch (error) {
    console.error('SKU selection error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * Generate sample metrics when Google Ads is not configured
 * Uses a deterministic seed based on SKU to ensure consistent results
 */
function generateSampleMetrics(
  skuMap: Map<string, { product_name: string; category: string; variant_count: number }>,
  optimizedSkus: Set<string>
): SkuMetrics[] {
  return Array.from(skuMap.entries()).map(([master_sku, info]) => {
    // Use SKU hash for deterministic but varied values
    const hash = hashCode(master_sku)
    const baseImpressions = 1000 + (Math.abs(hash) % 49000)
    const baseCtr = 0.01 + (Math.abs(hash >> 8) % 400) / 10000
    const baseCvr = 0.005 + (Math.abs(hash >> 16) % 200) / 10000

    const impressions = baseImpressions
    const clicks = Math.round(impressions * baseCtr)
    const conversions = Math.round(clicks * baseCvr)
    const avgOrderValue = 80 + (Math.abs(hash >> 24) % 120)
    const revenue = conversions * avgOrderValue
    const cost = clicks * (0.5 + (Math.abs(hash >> 4) % 100) / 100)

    return {
      master_sku,
      product_name: info.product_name,
      category: info.category,
      impressions,
      clicks,
      conversions,
      revenue,
      cost,
      variant_count: info.variant_count,
      already_optimized: optimizedSkus.has(master_sku),
    }
  })
}

function hashCode(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash // Convert to 32-bit integer
  }
  return hash
}
