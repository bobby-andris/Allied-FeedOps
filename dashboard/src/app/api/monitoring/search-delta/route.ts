/**
 * GET /api/monitoring/search-delta
 *
 * Detect changes in search query landscape after content publish.
 * Identifies new queries, lost queries, and volume shifts.
 *
 * Query params:
 * - master_sku?: Filter by specific SKU
 * - min_days?: Minimum days since publish (default: 7)
 * - comparison_window?: Days to look back for comparison (default: 30)
 *
 * Returns:
 * - New queries appearing post-publish
 * - Lost queries (dropped after publish)
 * - Volume changes for existing queries
 * - Query opportunity analysis
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

interface SearchQueryDelta {
  query_text: string
  master_sku: string
  gmc_offer_id: string | null
  finish: string | null

  // Status
  status: 'new' | 'lost' | 'volume_increase' | 'volume_decrease' | 'stable'

  // Before metrics (from baseline or earlier snapshots)
  before_impressions: number
  before_clicks: number
  before_avg_monthly_searches: number | null

  // After metrics (from recent snapshots)
  after_impressions: number
  after_clicks: number
  after_avg_monthly_searches: number | null

  // Deltas
  impressions_delta: number
  clicks_delta: number
  search_volume_delta: number | null

  // Opportunity score (higher = better opportunity)
  opportunity_score: number

  // Dates
  first_seen: string | null
  last_seen: string | null
  days_since_publish: number
}

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const filterSku = searchParams.get('master_sku')
    const minDays = parseInt(searchParams.get('min_days') || '7')
    // const comparisonWindow = parseInt(searchParams.get('comparison_window') || '30') // Reserved for future use

    // 1. Get published SKUs with their publish dates
    let publishQuery = supabase
      .from('publish_events')
      .select('id, master_sku, platform, published_at')
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
        deltas: [],
      })
    }

    // Group by SKU (get most recent publish per SKU)
    const skuPublishMap = new Map<string, typeof publishEvents[0]>()
    for (const event of publishEvents) {
      if (!skuPublishMap.has(event.master_sku)) {
        skuPublishMap.set(event.master_sku, event)
      }
    }

    const deltas: SearchQueryDelta[] = []

    // 2. For each SKU, compare search queries before/after publish
    for (const [sku, publishEvent] of skuPublishMap) {
      const publishDate = new Date(publishEvent.published_at)
      const now = new Date()
      const daysSincePublish = Math.floor((now.getTime() - publishDate.getTime()) / (1000 * 60 * 60 * 24))

      if (daysSincePublish < minDays) {
        // Too soon after publish - skip
        continue
      }

      // Get snapshots after publish
      const { data: afterSnapshots, error: afterError } = await supabase
        .from('search_query_snapshots')
        .select('*')
        .eq('master_sku', sku)
        .gte('snapshot_date', publishDate.toISOString().split('T')[0])

      if (afterError) {
        console.error(`Failed to fetch after snapshots for ${sku}:`, afterError)
        continue
      }

      // Get baseline queries (from search_queries table - historical data)
      const { data: beforeQueries, error: beforeError } = await supabase
        .from('search_queries')
        .select('*')
        .eq('master_sku', sku)

      if (beforeError) {
        console.error(`Failed to fetch before queries for ${sku}:`, beforeError)
        continue
      }

      // Build before/after maps
      const beforeMap = new Map<string, typeof beforeQueries[0]>()
      for (const query of beforeQueries || []) {
        beforeMap.set(query.query_text, query)
      }

      const afterMap = new Map<string, typeof afterSnapshots[0]>()
      for (const snapshot of afterSnapshots || []) {
        // Get latest snapshot for each query
        if (!afterMap.has(snapshot.query_text)) {
          afterMap.set(snapshot.query_text, snapshot)
        }
      }

      // Analyze changes
      const allQueries = new Set([...beforeMap.keys(), ...afterMap.keys()])

      for (const queryText of allQueries) {
        const before = beforeMap.get(queryText)
        const after = afterMap.get(queryText)

        let status: SearchQueryDelta['status']
        let beforeImpressions = 0
        let beforeClicks = 0
        let beforeSearchVolume: number | null = null
        let afterImpressions = 0
        let afterClicks = 0
        let afterSearchVolume: number | null = null

        if (before) {
          beforeImpressions = before.impressions || 0
          beforeClicks = before.clicks || 0
          beforeSearchVolume = before.avg_monthly_searches || null
        }

        if (after) {
          afterImpressions = after.impressions || 0
          afterClicks = after.clicks || 0
          afterSearchVolume = after.avg_monthly_searches || null
        }

        // Determine status
        if (!before && after) {
          status = 'new'
        } else if (before && !after) {
          status = 'lost'
        } else {
          const impressionsDelta = afterImpressions - beforeImpressions
          const threshold = Math.max(beforeImpressions * 0.2, 10) // 20% or 10 impressions

          if (impressionsDelta > threshold) {
            status = 'volume_increase'
          } else if (impressionsDelta < -threshold) {
            status = 'volume_decrease'
          } else {
            status = 'stable'
          }
        }

        // Calculate deltas
        const impressionsDelta = afterImpressions - beforeImpressions
        const clicksDelta = afterClicks - beforeClicks
        const searchVolumeDelta = beforeSearchVolume && afterSearchVolume
          ? afterSearchVolume - beforeSearchVolume
          : null

        // Calculate opportunity score (higher = better)
        // Factors: search volume, low competition, CTR potential
        let opportunityScore = 0
        if (after && after.avg_monthly_searches) {
          opportunityScore += Math.min(after.avg_monthly_searches / 100, 100) // Search volume (max 100 pts)
        }
        if (after && after.competition === 'LOW') {
          opportunityScore += 50
        } else if (after && after.competition === 'MEDIUM') {
          opportunityScore += 25
        }
        if (status === 'new') {
          opportunityScore += 30 // Bonus for new queries
        }
        if (afterClicks > 0 && afterImpressions > 0) {
          const ctr = afterClicks / afterImpressions
          opportunityScore += ctr * 1000 // CTR bonus (max ~100 pts)
        }

        deltas.push({
          query_text: queryText,
          master_sku: sku,
          gmc_offer_id: after?.gmc_offer_id || before?.gmc_offer_id || null,
          finish: after?.finish || before?.finish || null,

          status,

          before_impressions: beforeImpressions,
          before_clicks: beforeClicks,
          before_avg_monthly_searches: beforeSearchVolume,

          after_impressions: afterImpressions,
          after_clicks: afterClicks,
          after_avg_monthly_searches: afterSearchVolume,

          impressions_delta: impressionsDelta,
          clicks_delta: clicksDelta,
          search_volume_delta: searchVolumeDelta,

          opportunity_score: Math.round(opportunityScore),

          first_seen: after?.fetched_at || before?.fetched_at || null,
          last_seen: after?.fetched_at || before?.fetched_at || null,
          days_since_publish: daysSincePublish,
        })
      }
    }

    // Sort by opportunity score (descending)
    deltas.sort((a, b) => b.opportunity_score - a.opportunity_score)

    // Summary stats
    const newQueries = deltas.filter((d) => d.status === 'new').length
    const lostQueries = deltas.filter((d) => d.status === 'lost').length
    const volumeIncrease = deltas.filter((d) => d.status === 'volume_increase').length
    const volumeDecrease = deltas.filter((d) => d.status === 'volume_decrease').length
    const stable = deltas.filter((d) => d.status === 'stable').length

    return NextResponse.json({
      success: true,
      deltas,
      summary: {
        total: deltas.length,
        new_queries: newQueries,
        lost_queries: lostQueries,
        volume_increase: volumeIncrease,
        volume_decrease: volumeDecrease,
        stable,
        top_opportunities: deltas.slice(0, 10).map((d) => ({
          query: d.query_text,
          score: d.opportunity_score,
          status: d.status,
        })),
      },
    })
  } catch (error) {
    console.error('Search delta calculation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
