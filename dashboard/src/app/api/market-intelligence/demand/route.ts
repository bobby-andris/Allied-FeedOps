import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  costMicrosToDollars,
  buildLongTailBuckets,
  parseMonthlySearchVolumes,
  computeMoMChange,
  classifySeasonalDirection,
} from '@/lib/market-intelligence/computations'
import type {
  DemandData,
  ImpressionShareGap,
  CpcOpportunity,
  SeasonalTerm,
  NewTerm,
} from '@/lib/market-intelligence/types'
import { NEW_TERM_WINDOW_DAYS } from '@/lib/market-intelligence/constants'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const customLabel0 = request.nextUrl.searchParams.get('customLabel0')

    // Build a term->customLabel0 lookup from query_value_scores
    // (search_queries doesn't have custom_label_0 directly)
    let qvsQuery = supabase
      .from('query_value_scores')
      .select('search_term, custom_label_0')

    if (customLabel0) {
      qvsQuery = qvsQuery.eq('custom_label_0', customLabel0)
    }

    const { data: qvsRows, error: qvsError } = await qvsQuery

    if (qvsError) {
      console.error('query_value_scores fetch failed:', qvsError)
      return NextResponse.json({ error: qvsError.message }, { status: 500 })
    }

    // Build lookup: search_term -> custom_label_0
    const termToLabel = new Map<string, string>()
    for (const row of qvsRows ?? []) {
      termToLabel.set(row.search_term.toLowerCase(), row.custom_label_0)
    }

    const termSet = new Set(termToLabel.keys())

    // Fetch search_queries data
    const { data: sqRows, error: sqError } = await supabase
      .from('search_queries')
      .select('query_text, impressions, clicks, cost_micros, conversions, conversion_value, period_start, avg_monthly_searches, high_cpc_micros')
      .gt('impressions', 0)

    if (sqError) {
      console.error('search_queries fetch failed:', sqError)
      return NextResponse.json({ error: sqError.message }, { status: 500 })
    }

    // Aggregate search_queries by query_text (may have multiple variant rows)
    interface AggTerm {
      queryText: string
      customLabel0: string
      impressions: number
      clicks: number
      costMicros: number
      conversions: number
      revenue: number
      periodStart: string
      avgMonthlySearches: number | null
      highCpcMicros: number | null
    }

    const termAgg = new Map<string, AggTerm>()

    for (const row of sqRows ?? []) {
      const lower = (row.query_text as string).toLowerCase()
      const label = termToLabel.get(lower)
      // If customLabel0 filter active, skip terms not in query_value_scores
      if (customLabel0 && !label) continue

      const existing = termAgg.get(lower)
      if (existing) {
        existing.impressions += Number(row.impressions ?? 0)
        existing.clicks += Number(row.clicks ?? 0)
        existing.costMicros += Number(row.cost_micros ?? 0)
        existing.conversions += Number(row.conversions ?? 0)
        existing.revenue += Number(row.conversion_value ?? 0)
        // Keep earliest period_start
        if (row.period_start && row.period_start < existing.periodStart) {
          existing.periodStart = row.period_start
        }
        // Keep non-null keyword metrics
        if (row.avg_monthly_searches && !existing.avgMonthlySearches) {
          existing.avgMonthlySearches = Number(row.avg_monthly_searches)
        }
        if (row.high_cpc_micros && !existing.highCpcMicros) {
          existing.highCpcMicros = Number(row.high_cpc_micros)
        }
      } else {
        termAgg.set(lower, {
          queryText: row.query_text as string,
          customLabel0: label ?? '',
          impressions: Number(row.impressions ?? 0),
          clicks: Number(row.clicks ?? 0),
          costMicros: Number(row.cost_micros ?? 0),
          conversions: Number(row.conversions ?? 0),
          revenue: Number(row.conversion_value ?? 0),
          periodStart: (row.period_start as string) ?? '',
          avgMonthlySearches: row.avg_monthly_searches ? Number(row.avg_monthly_searches) : null,
          highCpcMicros: row.high_cpc_micros ? Number(row.high_cpc_micros) : null,
        })
      }
    }

    const allTerms = Array.from(termAgg.values())

    // Also fetch keyword_metrics for enrichment (seasonal + any missing market data)
    const { data: kmRows } = await supabase
      .from('keyword_metrics')
      .select('keyword, avg_monthly_searches, high_cpc_micros, monthly_searches')

    const keywordMetrics = new Map<string, {
      avgMonthlySearches: number | null
      highCpcMicros: number | null
      monthlySearches: unknown
    }>()
    for (const row of kmRows ?? []) {
      keywordMetrics.set((row.keyword as string).toLowerCase(), {
        avgMonthlySearches: row.avg_monthly_searches ? Number(row.avg_monthly_searches) : null,
        highCpcMicros: row.high_cpc_micros ? Number(row.high_cpc_micros) : null,
        monthlySearches: row.monthly_searches,
      })
    }

    // Enrich terms with keyword_metrics data where search_queries fields are null
    for (const term of allTerms) {
      const km = keywordMetrics.get(term.queryText.toLowerCase())
      if (km) {
        if (!term.avgMonthlySearches && km.avgMonthlySearches) {
          term.avgMonthlySearches = km.avgMonthlySearches
        }
        if (!term.highCpcMicros && km.highCpcMicros) {
          term.highCpcMicros = km.highCpcMicros
        }
      }
    }

    // --- 1. Impression Share Gaps (DEMAND-01) ---
    const impressionShare: ImpressionShareGap[] = allTerms
      .map(t => {
        const market = t.avgMonthlySearches
        const sharePercent = market && market > 0 ? (t.impressions / market) * 100 : null
        const gap = market ? market - t.impressions : null
        return {
          queryText: t.queryText,
          customLabel0: t.customLabel0,
          actualImpressions: t.impressions,
          marketVolume: market,
          sharePercent,
          gap,
        }
      })
      .sort((a, b) => (b.marketVolume ?? 0) - (a.marketVolume ?? 0))
      .slice(0, 100)

    // --- 2. CPC Opportunity (DEMAND-02) ---
    const cpcOpportunity: CpcOpportunity[] = allTerms
      .filter(t => t.clicks > 0)
      .map(t => {
        const actualCpc = t.costMicros / t.clicks
        const marketHigh = t.highCpcMicros
        const headroom = marketHigh && marketHigh > 0 ? (1 - actualCpc / marketHigh) * 100 : null
        let savings: CpcOpportunity['savings'] = 'at_market'
        if (headroom !== null) {
          if (headroom > 10) savings = 'below_market'
          else if (headroom < -10) savings = 'above_market'
        }
        return {
          queryText: t.queryText,
          customLabel0: t.customLabel0,
          actualCpcMicros: actualCpc,
          marketHighCpcMicros: marketHigh,
          headroomPercent: headroom,
          savings,
        }
      })
      .sort((a, b) => (b.headroomPercent ?? 0) - (a.headroomPercent ?? 0))
      .slice(0, 100)

    // --- 3. Seasonal Patterns (DEMAND-03) ---
    const seasonal: SeasonalTerm[] = []
    for (const [keyword, km] of keywordMetrics) {
      if (!km.monthlySearches) continue
      const label = termToLabel.get(keyword)
      if (customLabel0 && !label) continue

      const volumes = parseMonthlySearchVolumes(km.monthlySearches)
      if (volumes.length < 2) continue

      const { current, prior, changePercent } = computeMoMChange(volumes)
      const direction = classifySeasonalDirection(changePercent)
      if (direction === 'stable') continue

      seasonal.push({
        queryText: keyword,
        customLabel0: label ?? '',
        avgMonthlySearches: km.avgMonthlySearches ?? 0,
        monthlyVolumes: volumes,
        currentMonthSearches: current,
        priorMonthSearches: prior,
        changePercent,
        direction,
      })
    }
    seasonal.sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))

    // --- 4. New Term Discovery (DEMAND-04) ---
    const cutoffDate = new Date(Date.now() - NEW_TERM_WINDOW_DAYS * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0]

    // Get terms only seen in the last N days
    const recentTerms = allTerms.filter(t => t.periodStart >= cutoffDate)
    const olderTermSet = new Set(
      allTerms.filter(t => t.periodStart < cutoffDate).map(t => t.queryText.toLowerCase())
    )
    const newTerms: NewTerm[] = recentTerms
      .filter(t => !olderTermSet.has(t.queryText.toLowerCase()))
      .map(t => ({
        queryText: t.queryText,
        customLabel0: t.customLabel0,
        firstSeen: t.periodStart,
        impressions: t.impressions,
        clicks: t.clicks,
        conversions: t.conversions,
      }))
      .sort((a, b) => b.impressions - a.impressions)
      .slice(0, 50)

    // --- 5. Long-Tail Analysis (DEMAND-07) ---
    const longTailInput = allTerms.map(t => ({
      queryText: t.queryText,
      roas: t.costMicros > 0 ? t.revenue / costMicrosToDollars(t.costMicros) : 0,
      cvr: t.clicks > 0 ? t.conversions / t.clicks : 0,
      impressions: t.impressions,
      conversions: t.conversions,
      revenue: t.revenue,
      spend: costMicrosToDollars(t.costMicros),
    }))
    const longTail = buildLongTailBuckets(longTailInput)

    // --- KPIs ---
    const termsWithMarketData = impressionShare.filter(t => t.sharePercent !== null)
    const avgImpressionShare =
      termsWithMarketData.length > 0
        ? termsWithMarketData.reduce((s, t) => s + (t.sharePercent ?? 0), 0) / termsWithMarketData.length
        : null

    const termsWithCpc = cpcOpportunity.filter(t => t.headroomPercent !== null)
    const avgCpcHeadroom =
      termsWithCpc.length > 0
        ? termsWithCpc.reduce((s, t) => s + (t.headroomPercent ?? 0), 0) / termsWithCpc.length
        : null

    const result: DemandData = {
      impressionShare,
      cpcOpportunity,
      seasonal,
      newTerms,
      longTail,
      kpis: {
        avgImpressionShare,
        avgCpcHeadroom,
        seasonalAlertCount: seasonal.length,
        newTermCount: newTerms.length,
      },
    }

    return NextResponse.json(result)
  } catch (err) {
    console.error('Market intelligence demand failed:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
