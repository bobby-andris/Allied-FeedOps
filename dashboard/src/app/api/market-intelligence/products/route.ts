import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  classifyQuadrant,
  computeMedians,
  computeTrendDirection,
  costMicrosToDollars,
  paginateRpc,
  fetchLatestPeriod,
} from '@/lib/market-intelligence/computations'
import type { ProductsData, ProductGroup, ProductGroupDetail, TierGroup } from '@/lib/market-intelligence/types'

export const dynamic = 'force-dynamic'

interface ProductGroupRow {
  custom_label_0: string
  impressions: number
  clicks: number
  cost_micros: number
  conversions: number
  revenue: number
  term_count: number
}

interface TermMetricsRow {
  query_text: string
  custom_label_0: string
  impressions: number
  clicks: number
  cost_micros: number
  conversions: number
  revenue: number
  period_start: string
  avg_monthly_searches: number | null
  high_cpc_micros: number | null
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const customLabel0 = request.nextUrl.searchParams.get('customLabel0')
    const groupParam = request.nextUrl.searchParams.get('group')

    // Use latest major period for accurate single-period metrics
    const latestPeriod = await fetchLatestPeriod(supabase)

    // If group param provided, return drill-down detail
    if (groupParam) {
      return handleGroupDetail(supabase, groupParam, latestPeriod)
    }

    // --- Default mode: BCG overview ---

    // 1. Fetch pre-aggregated product group metrics for the latest period
    let groupRows: ProductGroupRow[]
    try {
      groupRows = await paginateRpc<ProductGroupRow>(supabase, 'market_intelligence_product_groups', {
        p_custom_label_0: customLabel0 || null,
        p_period_start: latestPeriod,
      })
    } catch (err) {
      console.error('product groups rpc failed:', err)
      return NextResponse.json({ error: err instanceof Error ? err.message : 'RPC failed' }, { status: 500 })
    }

    // 2. Compute trends from funnel_snapshots_daily
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

    // Detect insufficient prior data — if prior window has <10% of recent window rows,
    // trends are unreliable and should show as flat
    const priorDataSufficient = (priorSnapshots?.length ?? 0) > (recentSnapshots?.length ?? 0) * 0.3

    // 3. Build groups with trends and quadrants
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

    for (const row of groupRows) {
      const spend = costMicrosToDollars(Number(row.cost_micros ?? 0))
      const revenue = Number(row.revenue ?? 0)
      const roas = spend > 0 ? revenue / spend : 0
      const label = row.custom_label_0

      const recentRev = recentRevByLabel.get(label) ?? 0
      const priorRev = priorRevByLabel.get(label) ?? 0
      // Only compute trend if prior period has sufficient data
      const trend = priorDataSufficient && priorRev > 0
        ? ((recentRev - priorRev) / priorRev) * 100
        : 0

      rawGroups.push({
        customLabel0: label,
        roas,
        revenue,
        spend,
        impressions: Number(row.impressions ?? 0),
        conversions: Number(row.conversions ?? 0),
        termCount: Number(row.term_count ?? 0),
        trend,
        trendDirection: computeTrendDirection(trend),
      })
    }

    const roasValues = rawGroups.map(g => g.roas)
    const revenueValues = rawGroups.map(g => g.revenue)
    const medianRoas = computeMedians(roasValues)
    const medianRevenue = computeMedians(revenueValues)

    // 4. Classify quadrants
    const groups: ProductGroup[] = rawGroups.map(g => ({
      ...g,
      quadrant: classifyQuadrant(g.roas, g.revenue, medianRoas, medianRevenue),
    }))

    groups.sort((a, b) => b.revenue - a.revenue)

    // 5. KPIs
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
      period: {
        from: latestPeriod ?? '',
        to: latestPeriod ?? '',
        totalTerms: groups.reduce((s, g) => s + g.termCount, 0),
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
async function handleGroupDetail(supabase: any, group: string, latestPeriod: string | null): Promise<NextResponse> {
  // Fetch term-level metrics for this specific group, filtered to latest period
  let typedTermRows: TermMetricsRow[]
  try {
    typedTermRows = await paginateRpc<TermMetricsRow>(supabase, 'market_intelligence_term_metrics', {
      p_custom_label_0: group,
      p_period_start: latestPeriod,
    })
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : 'RPC failed' }, { status: 500 })
  }

  if (typedTermRows.length === 0) {
    return NextResponse.json({ error: `No data for group: ${group}` }, { status: 404 })
  }

  // Get tier info from query_value_scores
  const { data: qvsRows } = await supabase
    .from('query_value_scores')
    .select('search_term, model_inputs')
    .eq('custom_label_0', group)

  const qvsMap = new Map<string, { currentTier: string }>()
  for (const row of (qvsRows ?? []) as Array<{ search_term: string; model_inputs: Record<string, unknown> }>) {
    const inputs = typeof row.model_inputs === 'string' ? JSON.parse(row.model_inputs) : row.model_inputs
    qvsMap.set(row.search_term.toLowerCase(), {
      currentTier: (inputs?.currentTier as string) ?? 'UNKNOWN',
    })
  }

  // Build top terms
  const topTerms = typedTermRows
    .map(row => {
      const spend = costMicrosToDollars(Number(row.cost_micros ?? 0))
      return {
        searchTerm: row.query_text,
        currentTier: qvsMap.get(row.query_text.toLowerCase())?.currentTier ?? 'UNKNOWN',
        impressions: Number(row.impressions ?? 0),
        clicks: Number(row.clicks ?? 0),
        revenue: Number(row.revenue ?? 0),
        roas: spend > 0 ? Number(row.revenue ?? 0) / spend : 0,
      }
    })
    .sort((a, b) => b.impressions - a.impressions)
    .slice(0, 50)

  // Build tier groups from topTerms
  const tierMap = new Map<string, typeof topTerms>()
  for (const term of topTerms) {
    const tier = term.currentTier || 'UNKNOWN'
    if (!tierMap.has(tier)) tierMap.set(tier, [])
    tierMap.get(tier)!.push(term)
  }

  const TIER_ORDER = ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
  const tierGroups: TierGroup[] = TIER_ORDER
    .filter(tier => tierMap.has(tier))
    .map(tier => {
      const terms = tierMap.get(tier)!
      return {
        tier,
        termCount: terms.length,
        totalImpressions: terms.reduce((s, t) => s + t.impressions, 0),
        totalRevenue: terms.reduce((s, t) => s + t.revenue, 0),
        terms,
      }
    })

  // Compute group-level metrics
  const totalRevenue = topTerms.reduce((s, t) => s + t.revenue, 0)
  const totalSpend = typedTermRows.reduce(
    (s, row) => s + costMicrosToDollars(Number(row.cost_micros ?? 0)),
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
  // Only compute trend if prior period has sufficient data (>30% of recent)
  const priorSufficient = (priorSnaps?.length ?? 0) > (recentSnaps?.length ?? 0) * 0.3
  const trend = priorSufficient && priorRev > 0 ? ((recentRev - priorRev) / priorRev) * 100 : 0

  // Determine quadrant (approximate — overview computes proper medians)
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
    tierGroups,
  }

  return NextResponse.json(detail)
}
