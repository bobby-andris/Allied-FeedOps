import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildOpportunityClusters, buildOpportunityLaunchBriefs } from '@/lib/optimization/control-center'

function sanitizeLimit(input: string | null, fallback = 25, max = 200): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function sanitizeMedianRoas(input: string | null, fallback = 3.1): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.max(value, 0.5), 20)
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
    const accountMedianRoas = sanitizeMedianRoas(params.get('account_median_roas'))

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
    const launchBriefs = buildOpportunityLaunchBriefs(clusters, {
      accountMedianRoas,
      maxBriefs: Math.min(limit, 10),
    })

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      pipeline: termsResult.pipeline,
      cluster_count: clusters.length,
      clusters,
      launch_briefs: launchBriefs,
      account_median_roas: accountMedianRoas,
    })
  } catch (error) {
    console.error('Shopping funnel opportunities fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
