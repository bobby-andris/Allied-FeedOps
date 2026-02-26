import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  classifyQuadrant,
  computeMedians,
  computeTrendDirection,
  costMicrosToDollars,
} from '@/lib/market-intelligence/computations'
import type { ProductsData, ProductGroup, ProductGroupDetail } from '@/lib/market-intelligence/types'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const customLabel0 = request.nextUrl.searchParams.get('customLabel0')
    const groupParam = request.nextUrl.searchParams.get('group')

    // If group param provided, return drill-down detail
    if (groupParam) {
      return handleGroupDetail(supabase, groupParam)
    }

    // --- Default mode: BCG overview ---

    // 1. Fetch query_value_scores for term->label mapping and tier info
    let qvsQuery = supabase
      .from('query_value_scores')
      .select('search_term, custom_label_0, model_inputs')

    if (customLabel0) {
      qvsQuery = qvsQuery.eq('custom_label_0', customLabel0)
    }

    const { data: qvsRows, error: qvsError } = await qvsQuery

    if (qvsError) {
      console.error('query_value_scores fetch failed:', qvsError)
      return NextResponse.json({ error: qvsError.message }, { status: 500 })
    }

    // Build label->terms mapping
    const labelTerms = new Map<string, Set<string>>()
    for (const row of qvsRows ?? []) {
      const label = row.custom_label_0
      if (!labelTerms.has(label)) {
        labelTerms.set(label, new Set())
      }
      labelTerms.get(label)!.add(row.search_term.toLowerCase())
    }

    // 2. Fetch search_queries for metrics
    const { data: sqRows, error: sqError } = await supabase
      .from('search_queries')
      .select('query_text, impressions, clicks, cost_micros, conversions, conversion_value')
      .gt('impressions', 0)

    if (sqError) {
      console.error('search_queries fetch failed:', sqError)
      return NextResponse.json({ error: sqError.message }, { status: 500 })
    }

    // Aggregate by query_text first
    const termMetrics = new Map<string, {
      impressions: number
      clicks: number
      costMicros: number
      conversions: number
      revenue: number
    }>()

    for (const row of sqRows ?? []) {
      const lower = (row.query_text as string).toLowerCase()
      const existing = termMetrics.get(lower)
      if (existing) {
        existing.impressions += Number(row.impressions ?? 0)
        existing.clicks += Number(row.clicks ?? 0)
        existing.costMicros += Number(row.cost_micros ?? 0)
        existing.conversions += Number(row.conversions ?? 0)
        existing.revenue += Number(row.conversion_value ?? 0)
      } else {
        termMetrics.set(lower, {
          impressions: Number(row.impressions ?? 0),
          clicks: Number(row.clicks ?? 0),
          costMicros: Number(row.cost_micros ?? 0),
          conversions: Number(row.conversions ?? 0),
          revenue: Number(row.conversion_value ?? 0),
        })
      }
    }

    // Aggregate into label-level metrics
    interface LabelMetrics {
      impressions: number
      clicks: number
      costMicros: number
      conversions: number
      revenue: number
      termCount: number
    }

    const labelMetrics = new Map<string, LabelMetrics>()

    for (const [label, terms] of labelTerms) {
      const metrics: LabelMetrics = {
        impressions: 0,
        clicks: 0,
        costMicros: 0,
        conversions: 0,
        revenue: 0,
        termCount: 0,
      }

      for (const term of terms) {
        const tm = termMetrics.get(term)
        if (tm) {
          metrics.impressions += tm.impressions
          metrics.clicks += tm.clicks
          metrics.costMicros += tm.costMicros
          metrics.conversions += tm.conversions
          metrics.revenue += tm.revenue
          metrics.termCount += 1
        }
      }

      if (metrics.termCount > 0) {
        labelMetrics.set(label, metrics)
      }
    }

    // 3. Compute trends from funnel_snapshots_daily
    const now = new Date()
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0]
    const sixtyDaysAgo = new Date(now.getTime() - 60 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0]

    const { data: recentSnapshots } = await supabase
      .from('funnel_snapshots_daily')
      .select('custom_label_0, conversions_value')
      .gte('snapshot_date', thirtyDaysAgo)

    const { data: priorSnapshots } = await supabase
      .from('funnel_snapshots_daily')
      .select('custom_label_0, conversions_value')
      .gte('snapshot_date', sixtyDaysAgo)
      .lt('snapshot_date', thirtyDaysAgo)

    const recentRevByLabel = new Map<string, number>()
    for (const row of recentSnapshots ?? []) {
      const label = row.custom_label_0
      recentRevByLabel.set(label, (recentRevByLabel.get(label) ?? 0) + Number(row.conversions_value ?? 0))
    }

    const priorRevByLabel = new Map<string, number>()
    for (const row of priorSnapshots ?? []) {
      const label = row.custom_label_0
      priorRevByLabel.set(label, (priorRevByLabel.get(label) ?? 0) + Number(row.conversions_value ?? 0))
    }

    // 4. Build groups, compute medians, classify quadrants
    const rawGroups: Array<{
      customLabel0: string
      roas: number
      revenue: number
      spend: number
      impressions: number
      conversions: number
      termCount: number
      trend: number
      trendDirection: 'up' | 'down' | 'flat'
    }> = []

    for (const [label, metrics] of labelMetrics) {
      const spend = costMicrosToDollars(metrics.costMicros)
      const roas = spend > 0 ? metrics.revenue / spend : 0

      const recentRev = recentRevByLabel.get(label) ?? 0
      const priorRev = priorRevByLabel.get(label) ?? 0
      const trend = priorRev > 0 ? ((recentRev - priorRev) / priorRev) * 100 : 0

      rawGroups.push({
        customLabel0: label,
        roas,
        revenue: metrics.revenue,
        spend,
        impressions: metrics.impressions,
        conversions: metrics.conversions,
        termCount: metrics.termCount,
        trend,
        trendDirection: computeTrendDirection(trend),
      })
    }

    const roasValues = rawGroups.map(g => g.roas)
    const revenueValues = rawGroups.map(g => g.revenue)
    const medianRoas = computeMedians(roasValues)
    const medianRevenue = computeMedians(revenueValues)

    // 5. Classify quadrants
    const groups: ProductGroup[] = rawGroups.map(g => ({
      ...g,
      quadrant: classifyQuadrant(g.roas, g.revenue, medianRoas, medianRevenue),
    }))

    // Sort by revenue descending
    groups.sort((a, b) => b.revenue - a.revenue)

    // 6. KPIs
    const starCount = groups.filter(g => g.quadrant === 'star').length
    const cashCowCount = groups.filter(g => g.quadrant === 'cashCow').length
    const questionMarkCount = groups.filter(g => g.quadrant === 'questionMark').length
    const dogCount = groups.filter(g => g.quadrant === 'dog').length
    const totalRevenue = groups.reduce((s, g) => s + g.revenue, 0)
    const totalSpend = groups.reduce((s, g) => s + g.spend, 0)

    const result: ProductsData = {
      groups,
      medianRoas,
      medianRevenue,
      kpis: {
        starCount,
        cashCowCount,
        questionMarkCount,
        dogCount,
        totalRevenue,
        totalSpend,
      },
    }

    return NextResponse.json(result)
  } catch (err) {
    console.error('Market intelligence products failed:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function handleGroupDetail(supabase: any, group: string): Promise<NextResponse> {
  // 1. Fetch terms for this group
  const { data: qvsRows, error: qvsError } = await supabase
    .from('query_value_scores')
    .select('search_term, custom_label_0, model_inputs, impact_score')
    .eq('custom_label_0', group)

  if (qvsError) {
    return NextResponse.json({ error: qvsError.message }, { status: 500 })
  }

  if (!qvsRows || qvsRows.length === 0) {
    return NextResponse.json({ error: `No data for group: ${group}` }, { status: 404 })
  }

  // 2. Get metrics for each term
  const termSet = new Set((qvsRows as Array<{ search_term: string }>).map(r => r.search_term.toLowerCase()))

  const { data: sqRows, error: sqError } = await supabase
    .from('search_queries')
    .select('query_text, impressions, clicks, cost_micros, conversions, conversion_value')
    .gt('impressions', 0)

  if (sqError) {
    return NextResponse.json({ error: sqError.message }, { status: 500 })
  }

  // Aggregate search_queries by term
  const termMetrics = new Map<string, {
    impressions: number
    clicks: number
    costMicros: number
    conversions: number
    revenue: number
  }>()

  for (const row of sqRows ?? []) {
    const lower = (row.query_text as string).toLowerCase()
    if (!termSet.has(lower)) continue

    const existing = termMetrics.get(lower)
    if (existing) {
      existing.impressions += Number(row.impressions ?? 0)
      existing.clicks += Number(row.clicks ?? 0)
      existing.costMicros += Number(row.cost_micros ?? 0)
      existing.conversions += Number(row.conversions ?? 0)
      existing.revenue += Number(row.conversion_value ?? 0)
    } else {
      termMetrics.set(lower, {
        impressions: Number(row.impressions ?? 0),
        clicks: Number(row.clicks ?? 0),
        costMicros: Number(row.cost_micros ?? 0),
        conversions: Number(row.conversions ?? 0),
        revenue: Number(row.conversion_value ?? 0),
      })
    }
  }

  // Build top terms
  const qvsMap = new Map<string, { currentTier: string }>()
  for (const row of qvsRows as Array<{ search_term: string; model_inputs: Record<string, unknown> }>) {
    const inputs = typeof row.model_inputs === 'string' ? JSON.parse(row.model_inputs) : row.model_inputs
    qvsMap.set(row.search_term.toLowerCase(), {
      currentTier: (inputs?.currentTier as string) ?? 'UNKNOWN',
    })
  }

  const topTerms = Array.from(termMetrics.entries())
    .map(([term, m]) => {
      const spend = costMicrosToDollars(m.costMicros)
      return {
        searchTerm: term,
        currentTier: qvsMap.get(term)?.currentTier ?? 'UNKNOWN',
        impressions: m.impressions,
        clicks: m.clicks,
        revenue: m.revenue,
        roas: spend > 0 ? m.revenue / spend : 0,
      }
    })
    .sort((a, b) => b.impressions - a.impressions)
    .slice(0, 50)

  // Compute group-level metrics for detail
  const totalRevenue = topTerms.reduce((s, t) => s + t.revenue, 0)
  const totalSpend = Array.from(termMetrics.values()).reduce(
    (s, m) => s + costMicrosToDollars(m.costMicros),
    0
  )
  const roas = totalSpend > 0 ? totalRevenue / totalSpend : 0

  // Compute trend from funnel_snapshots_daily
  const now = new Date()
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0]
  const sixtyDaysAgo = new Date(now.getTime() - 60 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0]

  const { data: recentSnaps } = await supabase
    .from('funnel_snapshots_daily')
    .select('conversions_value')
    .eq('custom_label_0', group)
    .gte('snapshot_date', thirtyDaysAgo)

  const { data: priorSnaps } = await supabase
    .from('funnel_snapshots_daily')
    .select('conversions_value')
    .eq('custom_label_0', group)
    .gte('snapshot_date', sixtyDaysAgo)
    .lt('snapshot_date', thirtyDaysAgo)

  const recentRev = (recentSnaps ?? []).reduce(
    (s: number, r: { conversions_value: number }) => s + Number(r.conversions_value ?? 0),
    0
  )
  const priorRev = (priorSnaps ?? []).reduce(
    (s: number, r: { conversions_value: number }) => s + Number(r.conversions_value ?? 0),
    0
  )
  const trend = priorRev > 0 ? ((recentRev - priorRev) / priorRev) * 100 : 0

  // Determine quadrant (need global medians for context — approximate from this group)
  // For drill-down, quadrant is informational; the overview computes it properly
  const quadrant = roas > 2 && totalRevenue > 100 ? 'star' as const :
    roas > 2 ? 'cashCow' as const :
    totalRevenue > 100 ? 'questionMark' as const :
    'dog' as const

  const detail: ProductGroupDetail = {
    customLabel0: group,
    quadrant,
    roas,
    revenue: totalRevenue,
    spend: totalSpend,
    trend,
    topTerms,
  }

  return NextResponse.json(detail)
}
