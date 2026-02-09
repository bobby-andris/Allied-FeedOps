import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'
import { 
  fetchShoppingPerformance, 
  getDateRange, 
  isGoogleAdsConfigured,
  type ProductPerformance 
} from '@/lib/google-ads'

// Types for the API response
interface SkuPerformance {
  sku: string
  name: string
  platform: string
  publishedAt: string
  shopifyProductId: string | null
  baseline: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
  current: {
    ctr: number
    cvr: number
    impressions: number
    clicks: number
  }
}

interface PerformanceResponse {
  summary: {
    totalPublished: number
    avgCtrChange: number
    avgCvrChange: number
    totalImpressions: number
    totalClicks: number
  }
  skus: SkuPerformance[]
  warnings: string[]
}

// SKU to Shopify Product ID mapping is now queried from variant_index table

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const sku = searchParams.get('sku')
  const platform = searchParams.get('platform') || 'google'
  const dateRange = searchParams.get('dateRange') || '30d'

  const warnings: string[] = []

  try {
    const supabase = await createClient()
    
    // 1. Query publish_events for successful publishes
    let publishQuery = supabase
      .from('publish_events')
      .select('*')
      .eq('status', 'success')
      .eq('action', 'publish')
      .order('published_at', { ascending: false })

    if (platform) {
      publishQuery = publishQuery.eq('platform', platform)
    }

    if (sku) {
      publishQuery = publishQuery.eq('master_sku', sku)
    }

    const { data: publishEvents, error: publishError } = await publishQuery

    if (publishError) {
      console.error('Failed to fetch publish events:', publishError)
      return NextResponse.json({ error: publishError.message }, { status: 500 })
    }

    // Get unique SKUs that have been published
    const publishedSkuMap = new Map<string, { publishedAt: string; platform: string }>()
    for (const event of publishEvents || []) {
      const key = `${event.master_sku}-${event.platform}`
      if (!publishedSkuMap.has(key)) {
        publishedSkuMap.set(key, {
          publishedAt: event.published_at,
          platform: event.platform,
        })
      }
    }

    const uniqueSkus = [...new Set((publishEvents || []).map(e => e.master_sku))]

    // 2. Query variant_index to get Shopify product IDs and product titles
    const { data: variantIndexData, error: variantIndexError } = await supabase
      .from('variant_index')
      .select('master_sku, shopify_product_id, product_title')
      .in('master_sku', uniqueSkus)

    if (variantIndexError) {
      console.error('Failed to fetch variant index:', variantIndexError)
      warnings.push('Failed to fetch product mapping data')
    }

    // Build SKU to product mapping from variant_index (take first variant per master_sku)
    const skuToProductMap = new Map<string, { shopifyProductId: string; name: string }>()
    for (const variant of variantIndexData || []) {
      if (!skuToProductMap.has(variant.master_sku)) {
        skuToProductMap.set(variant.master_sku, {
          shopifyProductId: variant.shopify_product_id,
          name: variant.product_title || `SKU ${variant.master_sku}`,
        })
      }
    }

    // 3. Query performance_baselines for these SKUs
    let baselineQuery = supabase
      .from('performance_baselines')
      .select('*')

    if (uniqueSkus.length > 0) {
      baselineQuery = baselineQuery.in('master_sku', uniqueSkus)
    }

    if (platform) {
      baselineQuery = baselineQuery.eq('platform', platform)
    }

    const { data: baselines, error: baselineError } = await baselineQuery

    if (baselineError) {
      console.error('Failed to fetch baselines:', baselineError)
      // Don't fail the request, just note the warning
      warnings.push('Failed to fetch baseline data')
    }

    // Create a map of baselines by SKU-platform
    const baselineMap = new Map<string, {
      avgCtr: number
      avgCvr: number
      avgImpressions: number
      avgClicks: number
    }>()

    for (const baseline of baselines || []) {
      const key = `${baseline.master_sku}-${baseline.platform}`
      baselineMap.set(key, {
        avgCtr: baseline.avg_ctr || 0,
        avgCvr: baseline.avg_cvr || 0,
        avgImpressions: baseline.avg_impressions || 0,
        avgClicks: baseline.avg_clicks || 0,
      })
    }

    // 4. Fetch current performance from Google Ads (for google platform)
    let googleAdsData = new Map<string, ProductPerformance>()
    
    if (platform === 'google' && isGoogleAdsConfigured()) {
      // Get Shopify product IDs for the published SKUs
      const shopifyProductIds: string[] = []
      const skuToProductId = new Map<string, string>()

      for (const skuId of uniqueSkus) {
        const mapping = skuToProductMap.get(skuId)
        if (mapping) {
          shopifyProductIds.push(mapping.shopifyProductId)
          skuToProductId.set(skuId, mapping.shopifyProductId)
        }
      }

      if (shopifyProductIds.length > 0) {
        try {
          const { startDate, endDate } = getDateRange(dateRange)
          googleAdsData = await fetchShoppingPerformance(
            shopifyProductIds,
            startDate,
            endDate
          )
        } catch (error) {
          console.error('Failed to fetch Google Ads data:', error)
          warnings.push('Failed to fetch live Google Ads data. Showing cached data only.')
        }
      }

      // Distribute Google Ads product-level data to all master_skus sharing that product
      // (handles multi-SKU products like DMF-2/2X, DMF-2/3X sharing same product_id)
      const skuToGoogleAdsData = new Map<string, ProductPerformance>()
      for (const [skuId, mapping] of skuToProductMap) {
        if (googleAdsData.has(mapping.shopifyProductId)) {
          skuToGoogleAdsData.set(skuId, googleAdsData.get(mapping.shopifyProductId)!)
        }
      }
      googleAdsData = skuToGoogleAdsData
    } else if (platform === 'google' && !isGoogleAdsConfigured()) {
      warnings.push('Google Ads API is not configured. Using cached data only.')
    }

    // 5. Query performance_snapshots for fallback/additional data
    const { startDate, endDate } = getDateRange(dateRange)
    
    let snapshotQuery = supabase
      .from('performance_snapshots')
      .select('*')
      .gte('snapshot_date', startDate)
      .lte('snapshot_date', endDate)
      .order('snapshot_date', { ascending: false })

    if (uniqueSkus.length > 0) {
      snapshotQuery = snapshotQuery.in('master_sku', uniqueSkus)
    }

    if (platform) {
      snapshotQuery = snapshotQuery.eq('platform', platform)
    }

    const { data: snapshots } = await snapshotQuery

    // Create a map of latest snapshots by SKU-platform
    const snapshotMap = new Map<string, {
      ctr: number
      cvr: number
      impressions: number
      clicks: number
    }>()

    for (const snapshot of snapshots || []) {
      const key = `${snapshot.master_sku}-${snapshot.platform}`
      if (!snapshotMap.has(key)) {
        snapshotMap.set(key, {
          ctr: snapshot.ctr || 0,
          cvr: snapshot.cvr || 0,
          impressions: snapshot.impressions || 0,
          clicks: snapshot.clicks || 0,
        })
      }
    }

    // 6. Build the response
    const skuPerformanceList: SkuPerformance[] = []

    for (const [key, publishInfo] of publishedSkuMap) {
      const skuId = key.substring(0, key.lastIndexOf('-' + publishInfo.platform))
      const skuMapping = skuToProductMap.get(skuId)
      const shopifyProductId = skuMapping?.shopifyProductId || null
      const productName = skuMapping?.name || `SKU ${skuId}`

      // Get baseline data
      const baselineKey = `${skuId}-${publishInfo.platform}`
      const baseline = baselineMap.get(baselineKey) || {
        avgCtr: 0,
        avgCvr: 0,
        avgImpressions: 0,
        avgClicks: 0,
      }

      // Get current data - prefer Google Ads live data, fall back to snapshots
      let current = {
        ctr: 0,
        cvr: 0,
        impressions: 0,
        clicks: 0,
      }

      if (googleAdsData.has(skuId)) {
        const gadsData = googleAdsData.get(skuId)!
        current = {
          ctr: gadsData.ctr * 100, // Convert to percentage
          cvr: gadsData.conversions > 0 && gadsData.clicks > 0
            ? (gadsData.conversions / gadsData.clicks) * 100
            : 0,
          impressions: gadsData.impressions,
          clicks: gadsData.clicks,
        }
      } else if (snapshotMap.has(baselineKey)) {
        const snapshot = snapshotMap.get(baselineKey)!
        current = {
          ctr: snapshot.ctr,
          cvr: snapshot.cvr,
          impressions: snapshot.impressions,
          clicks: snapshot.clicks,
        }
      }

      skuPerformanceList.push({
        sku: skuId,
        name: productName,
        platform: publishInfo.platform,
        publishedAt: publishInfo.publishedAt.split('T')[0], // Format as YYYY-MM-DD
        shopifyProductId,
        baseline: {
          ctr: baseline.avgCtr,
          cvr: baseline.avgCvr,
          impressions: baseline.avgImpressions,
          clicks: baseline.avgClicks,
        },
        current,
      })
    }

    // Calculate summary stats
    let totalCtrChange = 0
    let totalCvrChange = 0
    let validCtrCount = 0
    let validCvrCount = 0
    let totalImpressions = 0
    let totalClicks = 0

    for (const skuPerf of skuPerformanceList) {
      totalImpressions += skuPerf.current.impressions
      totalClicks += skuPerf.current.clicks

      if (skuPerf.baseline.ctr > 0) {
        const ctrChange = ((skuPerf.current.ctr - skuPerf.baseline.ctr) / skuPerf.baseline.ctr) * 100
        totalCtrChange += ctrChange
        validCtrCount++
      }

      if (skuPerf.baseline.cvr > 0) {
        const cvrChange = ((skuPerf.current.cvr - skuPerf.baseline.cvr) / skuPerf.baseline.cvr) * 100
        totalCvrChange += cvrChange
        validCvrCount++
      }
    }

    const response: PerformanceResponse = {
      summary: {
        totalPublished: skuPerformanceList.length,
        avgCtrChange: validCtrCount > 0 ? totalCtrChange / validCtrCount : 0,
        avgCvrChange: validCvrCount > 0 ? totalCvrChange / validCvrCount : 0,
        totalImpressions,
        totalClicks,
      },
      skus: skuPerformanceList,
      warnings,
    }

    return NextResponse.json(response)
  } catch (error) {
    console.error('Performance API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
