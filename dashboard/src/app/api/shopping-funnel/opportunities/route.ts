import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildOpportunityClusters } from '@/lib/optimization/control-center'

function sanitizeLimit(input: string | null, fallback = 25, max = 200): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(params.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(params.get('min_impressions'))
    const limit = sanitizeLimit(params.get('limit'))

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit: 5000,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const clusters = buildOpportunityClusters(termsResult.terms).slice(0, limit)

    const launchBriefs = clusters.slice(0, 10).map((cluster) => ({
      cluster_key: cluster.clusterKey,
      rationale:
        'Low-CPC/high-impact cluster detected. Consider a budget-capped pilot with overlap guardrails.',
      suggested_actions: [
        'Create pilot campaign/ad group for this cluster.',
        'Apply strict negative overlap controls with existing funnel labels.',
        'Track pilot ROAS against account median and stop after 14 days if underperforming.',
      ],
      top_terms: cluster.topSearchTerms.slice(0, 5),
    }))

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      pipeline: termsResult.pipeline,
      cluster_count: clusters.length,
      clusters,
      launch_briefs: launchBriefs,
    })
  } catch (error) {
    console.error('Shopping funnel opportunities fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
