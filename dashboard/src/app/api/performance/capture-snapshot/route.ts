/**
 * POST /api/performance/capture-snapshot
 *
 * Captures current performance snapshots for all SKUs that have been published.
 * This allows tracking performance over time after content optimization.
 *
 * Workflow:
 * 1. Get all SKUs with successful publish_events
 * 2. For each SKU, fetch current Google Ads performance
 * 3. Calculate days since publish
 * 4. Store in performance_snapshots table
 * 5. Return summary
 *
 * Optional query params:
 * - master_sku: Capture snapshot for specific SKU only
 * - platform: Filter by platform (google or bing)
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { fetchShoppingPerformance, getDateRange } from '@/lib/google-ads'

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()

    // Optional filters from query params
    const { searchParams } = new URL(request.url)
    const filterSku = searchParams.get('master_sku')
    const filterPlatform = searchParams.get('platform') as 'google' | 'bing' | null

    // 1. Get published SKUs (successful publish events)
    let query = supabase
      .from('publish_events')
      .select('id, master_sku, platform, environment, content_version, published_at')
      .eq('status', 'success')
      .eq('action', 'publish')
      .order('published_at', { ascending: false })

    if (filterSku) {
      query = query.eq('master_sku', filterSku)
    }

    if (filterPlatform) {
      query = query.eq('platform', filterPlatform)
    }

    const { data: publishEvents, error: publishError } = await query

    if (publishError) {
      return NextResponse.json(
        { error: `Failed to fetch publish events: ${publishError.message}` },
        { status: 500 }
      )
    }

    if (!publishEvents || publishEvents.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No published SKUs found',
        snapshots_created: 0,
      })
    }

    // Group by SKU + platform (use most recent publish event per SKU/platform)
    const skuPlatformMap = new Map<string, typeof publishEvents[0]>()
    for (const event of publishEvents) {
      const key = `${event.master_sku}:${event.platform}`
      if (!skuPlatformMap.has(key)) {
        skuPlatformMap.set(key, event)
      }
    }

    // 2. Fetch variant_index data to get Shopify product IDs
    const skuList = Array.from(new Set(publishEvents.map((e) => e.master_sku)))
    const { data: variantData, error: variantError } = await supabase
      .from('variant_index')
      .select('master_sku, shopify_product_id')
      .in('master_sku', skuList)

    if (variantError) {
      return NextResponse.json(
        { error: `Failed to fetch variant data: ${variantError.message}` },
        { status: 500 }
      )
    }

    // Map SKU -> Shopify product ID (use first match)
    const skuToProductId = new Map<string, string>()
    for (const variant of variantData || []) {
      if (!skuToProductId.has(variant.master_sku)) {
        skuToProductId.set(variant.master_sku, variant.shopify_product_id)
      }
    }

    // 3. Fetch Google Ads performance for all products (30-day window)
    const { startDate, endDate } = getDateRange('30d')
    const productIds = Array.from(new Set(Array.from(skuToProductId.values())))

    const performanceMap = await fetchShoppingPerformance(productIds, startDate, endDate)

    // 4. Create snapshots
    let snapshotsCreated = 0
    const errors: string[] = []

    for (const [, publishEvent] of skuPlatformMap) {
      const masterSku = publishEvent.master_sku
      const platform = publishEvent.platform
      const productId = skuToProductId.get(masterSku)

      if (!productId) {
        errors.push(`No Shopify product ID for ${masterSku}`)
        continue
      }

      const performance = performanceMap.get(productId)
      if (!performance || performance.impressions === 0) {
        // No performance data - this is OK, just skip (product may not have data yet)
        continue
      }

      // Calculate days since publish
      const publishDate = new Date(publishEvent.published_at)
      const now = new Date()
      const daysSincePublish = Math.floor((now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24))

      // Calculate CVR and CPC
      const cvr = performance.clicks > 0 ? performance.conversions / performance.clicks : 0
      const cpc = performance.clicks > 0 ? performance.cost / performance.clicks : 0

      // Insert snapshot
      const { error: insertError } = await supabase
        .from('performance_snapshots')
        .insert({
          master_sku: masterSku,
          platform,
          environment: publishEvent.environment || 'production',
          snapshot_date: endDate, // Use end date of window
          impressions: performance.impressions,
          clicks: performance.clicks,
          ctr: performance.ctr,
          conversions: Math.round(performance.conversions),
          conversion_value: performance.conversionValue,
          cvr,
          cost: performance.cost,
          cpc,
          roas: performance.roas,
          publish_event_id: publishEvent.id,
          content_version: publishEvent.content_version,
          days_since_publish: daysSincePublish,
        })

      if (insertError) {
        errors.push(`Failed to insert snapshot for ${masterSku}: ${insertError.message}`)
        continue
      }

      snapshotsCreated++
    }

    return NextResponse.json({
      success: true,
      message: `Captured ${snapshotsCreated} performance snapshots`,
      snapshots_created: snapshotsCreated,
      skus_processed: skuPlatformMap.size,
      errors: errors.length > 0 ? errors : undefined,
    })
  } catch (error) {
    console.error('Snapshot capture failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
