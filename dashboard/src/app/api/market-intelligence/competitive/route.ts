import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { COMPETITOR_TOKENS, BRAND_TOKENS } from '@/lib/market-intelligence/constants'
import { isBrandTerm, matchesCompetitor, costMicrosToDollars } from '@/lib/market-intelligence/computations'
import type { CompetitiveData, BrandSplit, CompetitorMention } from '@/lib/market-intelligence/types'

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const customLabel0 = request.nextUrl.searchParams.get('customLabel0')

    // Build term->label lookup from query_value_scores
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

    const termToLabel = new Map<string, string>()
    for (const row of qvsRows ?? []) {
      termToLabel.set(row.search_term.toLowerCase(), row.custom_label_0)
    }

    // Fetch search_queries
    const { data: sqRows, error: sqError } = await supabase
      .from('search_queries')
      .select('query_text, impressions, clicks, cost_micros, conversions, conversion_value')
      .gt('impressions', 0)

    if (sqError) {
      console.error('search_queries fetch failed:', sqError)
      return NextResponse.json({ error: sqError.message }, { status: 500 })
    }

    // Aggregate by query_text
    interface AggTerm {
      queryText: string
      impressions: number
      clicks: number
      costMicros: number
      conversions: number
      revenue: number
    }

    const termAgg = new Map<string, AggTerm>()

    for (const row of sqRows ?? []) {
      const lower = (row.query_text as string).toLowerCase()
      const label = termToLabel.get(lower)
      if (customLabel0 && !label) continue

      const existing = termAgg.get(lower)
      if (existing) {
        existing.impressions += Number(row.impressions ?? 0)
        existing.clicks += Number(row.clicks ?? 0)
        existing.costMicros += Number(row.cost_micros ?? 0)
        existing.conversions += Number(row.conversions ?? 0)
        existing.revenue += Number(row.conversion_value ?? 0)
      } else {
        termAgg.set(lower, {
          queryText: row.query_text as string,
          impressions: Number(row.impressions ?? 0),
          clicks: Number(row.clicks ?? 0),
          costMicros: Number(row.cost_micros ?? 0),
          conversions: Number(row.conversions ?? 0),
          revenue: Number(row.conversion_value ?? 0),
        })
      }
    }

    const allTerms = Array.from(termAgg.values())

    // --- 1. Brand vs Non-Brand Split (DEMAND-05) ---
    const segments: Record<BrandSplit['segment'], Omit<BrandSplit, 'segment' | 'roas'> & { costMicros: number }> = {
      brand: { revenue: 0, spend: 0, impressions: 0, clicks: 0, conversions: 0, termCount: 0, costMicros: 0 },
      non_brand: { revenue: 0, spend: 0, impressions: 0, clicks: 0, conversions: 0, termCount: 0, costMicros: 0 },
      competitor: { revenue: 0, spend: 0, impressions: 0, clicks: 0, conversions: 0, termCount: 0, costMicros: 0 },
    }

    for (const term of allTerms) {
      const competitorMatches = matchesCompetitor(term.queryText, COMPETITOR_TOKENS)
      let segment: BrandSplit['segment']

      if (competitorMatches.length > 0) {
        segment = 'competitor'
      } else if (isBrandTerm(term.queryText, BRAND_TOKENS)) {
        segment = 'brand'
      } else {
        segment = 'non_brand'
      }

      const s = segments[segment]
      s.revenue += term.revenue
      s.costMicros += term.costMicros
      s.spend += costMicrosToDollars(term.costMicros)
      s.impressions += term.impressions
      s.clicks += term.clicks
      s.conversions += term.conversions
      s.termCount += 1
    }

    const brandSplit: BrandSplit[] = (['brand', 'non_brand', 'competitor'] as const).map(seg => ({
      segment: seg,
      revenue: segments[seg].revenue,
      spend: segments[seg].spend,
      roas: segments[seg].spend > 0 ? segments[seg].revenue / segments[seg].spend : 0,
      impressions: segments[seg].impressions,
      clicks: segments[seg].clicks,
      conversions: segments[seg].conversions,
      termCount: segments[seg].termCount,
    }))

    // --- 2. Competitor Mention Tracking (DEMAND-06) ---
    const competitorMentions: CompetitorMention[] = []

    for (const token of COMPETITOR_TOKENS) {
      const matchingTerms = allTerms.filter(t =>
        t.queryText.toLowerCase().includes(token)
      )

      if (matchingTerms.length === 0) continue

      const totalImpressions = matchingTerms.reduce((s, t) => s + t.impressions, 0)
      const totalClicks = matchingTerms.reduce((s, t) => s + t.clicks, 0)
      const totalCostMicros = matchingTerms.reduce((s, t) => s + t.costMicros, 0)
      const totalConversions = matchingTerms.reduce((s, t) => s + t.conversions, 0)
      const totalRevenue = matchingTerms.reduce((s, t) => s + t.revenue, 0)
      const spend = costMicrosToDollars(totalCostMicros)

      // Top 5 terms by impressions
      const topTerms = [...matchingTerms]
        .sort((a, b) => b.impressions - a.impressions)
        .slice(0, 5)
        .map(t => t.queryText)

      competitorMentions.push({
        token,
        termCount: matchingTerms.length,
        impressions: totalImpressions,
        clicks: totalClicks,
        spend,
        conversions: totalConversions,
        revenue: totalRevenue,
        roas: spend > 0 ? totalRevenue / spend : 0,
        topTerms,
      })
    }

    competitorMentions.sort((a, b) => b.spend - a.spend)

    // --- KPIs ---
    const totalRevenue = brandSplit.reduce((s, b) => s + b.revenue, 0)
    const brandRevenue = segments.brand.revenue
    const competitorSpend = segments.competitor.spend
    const topCompetitor = competitorMentions.length > 0 ? competitorMentions[0].token : null
    const nonBrandSeg = brandSplit.find(b => b.segment === 'non_brand')
    const nonBrandRoas = nonBrandSeg?.roas ?? 0

    const result: CompetitiveData = {
      brandSplit,
      competitorMentions,
      kpis: {
        brandRevenuePercent: totalRevenue > 0 ? (brandRevenue / totalRevenue) * 100 : 0,
        competitorSpend,
        topCompetitor,
        nonBrandRoas,
      },
    }

    return NextResponse.json(result)
  } catch (err) {
    console.error('Market intelligence competitive failed:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
