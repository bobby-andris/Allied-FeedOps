/**
 * POST /api/monitoring/snapshot-capture
 *
 * Capture search query snapshots for post-publish monitoring.
 * Fetches current search query performance and stores in search_query_snapshots table.
 *
 * Query params:
 * - master_sku?: Capture snapshots for specific SKU only
 * - force?: Force capture even if recent snapshot exists (default: false)
 *
 * Returns:
 * - Number of snapshots created
 * - Errors (if any)
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const filterSku = searchParams.get('master_sku')
    const force = searchParams.get('force') === 'true'

    // 1. Get published SKUs
    let publishQuery = supabase
      .from('publish_events')
      .select('id, master_sku, platform, environment, content_version, published_at')
      .eq('status', 'success')
      .order('published_at', { ascending: false })

    if (filterSku) {
      publishQuery = publishQuery.eq('master_sku', filterSku)
    }

    const { data: publishEvents, error: publishError } = await publishQuery

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

    // Group by SKU (get most recent publish per SKU)
    const skuPublishMap = new Map<string, typeof publishEvents[0]>()
    for (const event of publishEvents) {
      if (!skuPublishMap.has(event.master_sku)) {
        skuPublishMap.set(event.master_sku, event)
      }
    }

    const today = new Date().toISOString().split('T')[0]

    // 2. Check for existing snapshots today (unless force=true)
    if (!force) {
      const { data: existingSnapshots } = await supabase
        .from('search_query_snapshots')
        .select('master_sku')
        .eq('snapshot_date', today)

      // Remove SKUs that already have snapshots today
      for (const snapshot of existingSnapshots || []) {
        skuPublishMap.delete(snapshot.master_sku)
      }

      if (skuPublishMap.size === 0) {
        return NextResponse.json({
          success: true,
          message: 'All SKUs already have snapshots for today',
          snapshots_created: 0,
        })
      }
    }

    // 3. Fetch current search query data
    const skus = Array.from(skuPublishMap.keys())
    const { data: searchQueries, error: searchError } = await supabase
      .from('search_queries')
      .select('*')
      .in('master_sku', skus)

    if (searchError) {
      return NextResponse.json(
        { error: `Failed to fetch search queries: ${searchError.message}` },
        { status: 500 }
      )
    }

    if (!searchQueries || searchQueries.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No search query data found for published SKUs',
        snapshots_created: 0,
      })
    }

    // 4. Create snapshots
    let snapshotsCreated = 0
    const errors: string[] = []

    for (const query of searchQueries) {
      const publishEvent = skuPublishMap.get(query.master_sku)
      if (!publishEvent) continue

      // Calculate days since publish
      const publishDate = new Date(publishEvent.published_at)
      const now = new Date()
      const daysSincePublish = Math.floor((now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24))

      // Insert snapshot
      const { error: insertError } = await supabase
        .from('search_query_snapshots')
        .insert({
          query_text: query.query_text,
          master_sku: query.master_sku,
          gmc_offer_id: query.gmc_offer_id,
          finish: query.finish,
          finish_code: query.finish_code,

          impressions: query.impressions || 0,
          clicks: query.clicks || 0,
          conversions: query.conversions || 0,
          conversion_value: query.conversion_value || 0,
          cost_micros: query.cost_micros || 0,
          ctr: query.ctr || null,
          cvr: query.cvr || null,

          avg_monthly_searches: query.avg_monthly_searches || null,
          competition: query.competition || null,
          competition_index: query.competition_index || null,
          low_cpc_micros: query.low_cpc_micros || null,
          high_cpc_micros: query.high_cpc_micros || null,

          snapshot_date: today,
          days_since_publish: daysSincePublish,
          publish_event_id: publishEvent.id,
          content_version: publishEvent.content_version || null,

          period_start: query.period_start,
          period_end: query.period_end,
        })
        .select()

      if (insertError) {
        // Check if it's a duplicate (unique constraint violation)
        if (insertError.code === '23505') {
          // Skip duplicates silently
          continue
        }
        errors.push(`Failed to snapshot query "${query.query_text}" for ${query.master_sku}: ${insertError.message}`)
        continue
      }

      snapshotsCreated++
    }

    return NextResponse.json({
      success: true,
      message: `Captured ${snapshotsCreated} search query snapshots`,
      snapshots_created: snapshotsCreated,
      queries_processed: searchQueries.length,
      skus_processed: skuPublishMap.size,
      errors: errors.length > 0 ? errors : undefined,
    })
  } catch (error) {
    console.error('Search query snapshot capture failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
