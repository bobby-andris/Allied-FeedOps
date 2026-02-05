import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

/**
 * GET /api/search-insights
 * Fetch search query data for the Search Insights dashboard
 *
 * Query params:
 * - sku: Master SKU to filter by
 * - finish: Finish code for variant-level filtering
 * - platform: 'google' | 'bing' | 'shopify'
 * - view: 'aggregate' | 'variant'
 * - minImpressions: Minimum impressions threshold
 * - limit: Max results (default 100)
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const masterSku = searchParams.get('sku')
    const finishCode = searchParams.get('finish')
    const platform = searchParams.get('platform') || 'google'
    const viewType = searchParams.get('view') || 'aggregate'
    const minImpressions = parseInt(searchParams.get('minImpressions') || '0', 10)
    const limit = parseInt(searchParams.get('limit') || '100', 10)

    const supabase = await createClient()

    // For Shopify, only show master SKU level data
    if (platform === 'shopify') {
      if (!masterSku) {
        return NextResponse.json({
          platform: 'shopify',
          viewType: 'master',
          queries: [],
          note: 'Enter a Master SKU to view search query insights',
        })
      }

      const { data: queries, error } = await supabase
        .from('search_queries_by_master_sku')
        .select('*')
        .eq('master_sku', masterSku)
        .order('total_impressions', { ascending: false })
        .limit(limit)

      if (error) {
        console.error('Error fetching search queries:', error)
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      return NextResponse.json({
        platform: 'shopify',
        viewType: 'master',
        masterSku,
        queries: queries || [],
        note: 'Shopify uses master SKU descriptions - variant breakdown not applicable',
      })
    }

    // For Google/Bing, support both aggregate and variant views
    if (viewType === 'aggregate' && masterSku) {
      // Aggregate view: all variants combined
      const { data: queries, error: queriesError } = await supabase
        .from('search_queries_by_master_sku')
        .select('*')
        .eq('master_sku', masterSku)
        .order('total_impressions', { ascending: false })
        .limit(limit)

      if (queriesError) {
        console.error('Error fetching aggregated queries:', queriesError)
        return NextResponse.json({ error: queriesError.message }, { status: 500 })
      }

      // Get variant breakdown summary
      const { data: variantSummary } = await supabase
        .from('search_queries')
        .select('finish_code, finish')
        .eq('master_sku', masterSku)

      // Count unique finishes
      const finishCounts: Record<string, number> = {}
      variantSummary?.forEach((q) => {
        if (q.finish_code) {
          finishCounts[q.finish_code] = (finishCounts[q.finish_code] || 0) + 1
        }
      })

      // Get summary stats
      const stats = calculateSummaryStats(queries || [])

      return NextResponse.json({
        platform,
        viewType: 'aggregate',
        masterSku,
        queries: queries || [],
        variantBreakdown: finishCounts,
        stats,
        note: 'Aggregate view shows all queries across all finish variants',
      })
    }

    if (viewType === 'variant' && masterSku) {
      // Variant-specific view
      let query = supabase
        .from('search_queries')
        .select('*')
        .eq('master_sku', masterSku)
        .order('impressions', { ascending: false })

      if (finishCode) {
        query = query.eq('finish_code', finishCode)
      }

      if (minImpressions > 0) {
        query = query.gte('impressions', minImpressions)
      }

      const { data: queries, error } = await query.limit(limit)

      if (error) {
        console.error('Error fetching variant queries:', error)
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      // Group by finish for UI
      const byFinish: Record<string, {
        finish: string | null
        finish_code: string | null
        queries: typeof queries
        totalImpressions: number
        totalClicks: number
      }> = {}

      queries?.forEach((q) => {
        const finish = q.finish_code || 'UNKNOWN'
        if (!byFinish[finish]) {
          byFinish[finish] = {
            finish: q.finish,
            finish_code: q.finish_code,
            queries: [],
            totalImpressions: 0,
            totalClicks: 0,
          }
        }
        byFinish[finish].queries.push(q)
        byFinish[finish].totalImpressions += q.impressions || 0
        byFinish[finish].totalClicks += q.clicks || 0
      })

      // Get available finishes for dropdown
      const { data: availableFinishes } = await supabase
        .from('search_queries')
        .select('finish_code, finish')
        .eq('master_sku', masterSku)

      const uniqueFinishes = Array.from(
        new Map(
          availableFinishes
            ?.filter((f) => f.finish_code)
            .map((f) => [f.finish_code, { finish_code: f.finish_code, finish: f.finish }])
        ).values()
      )

      return NextResponse.json({
        platform,
        viewType: 'variant',
        masterSku,
        selectedFinish: finishCode,
        queries: queries || [],
        byFinish,
        availableFinishes: uniqueFinishes,
        note: finishCode
          ? `Showing queries that triggered the ${finishCode} variant specifically`
          : 'Showing queries broken down by finish variant',
      })
    }

    // Default: top queries across all SKUs (no SKU filter)
    const { data: queries, error } = await supabase
      .from('search_queries')
      .select('*')
      .order('impressions', { ascending: false })
      .limit(limit)

    if (error) {
      console.error('Error fetching all queries:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Get last sync info
    const { data: lastSync } = await supabase
      .from('search_query_sync_jobs')
      .select('completed_at, queries_fetched')
      .eq('status', 'completed')
      .order('completed_at', { ascending: false })
      .limit(1)
      .single()

    return NextResponse.json({
      platform,
      viewType: 'all',
      queries: queries || [],
      lastSynced: lastSync?.completed_at || null,
      totalQueriesSynced: lastSync?.queries_fetched || 0,
      note: 'Enter a Master SKU to see SKU-specific search insights',
    })
  } catch (error) {
    console.error('Search insights API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * Calculate summary statistics from queries
 */
function calculateSummaryStats(queries: Array<{
  total_impressions?: number
  total_clicks?: number
  total_conversions?: number
  total_conversion_value?: number
  avg_monthly_searches?: number | null
}>) {
  const totals = queries.reduce(
    (acc, q) => ({
      impressions: acc.impressions + (q.total_impressions || 0),
      clicks: acc.clicks + (q.total_clicks || 0),
      conversions: acc.conversions + (q.total_conversions || 0),
      conversionValue: acc.conversionValue + (q.total_conversion_value || 0),
      searchVolume: acc.searchVolume + (q.avg_monthly_searches || 0),
    }),
    { impressions: 0, clicks: 0, conversions: 0, conversionValue: 0, searchVolume: 0 }
  )

  return {
    totalQueries: queries.length,
    totalImpressions: totals.impressions,
    totalClicks: totals.clicks,
    totalConversions: Math.round(totals.conversions * 100) / 100,
    totalConversionValue: Math.round(totals.conversionValue * 100) / 100,
    totalSearchVolume: totals.searchVolume,
    ctr: totals.impressions > 0
      ? Math.round((totals.clicks / totals.impressions) * 10000) / 100
      : 0,
    cvr: totals.clicks > 0
      ? Math.round((totals.conversions / totals.clicks) * 10000) / 100
      : 0,
  }
}
