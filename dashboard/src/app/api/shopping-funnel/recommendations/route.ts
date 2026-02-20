import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildRecommendationQueue } from '@/lib/optimization/control-center'

function sanitizeLimit(input: string | null, fallback = 100, max = 1000): number {
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
      limit: 3000,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const queue = buildRecommendationQueue(termsResult.terms, limit)

    const actionDistribution = queue.reduce<Record<string, number>>((acc, item) => {
      acc[item.actionType] = (acc[item.actionType] ?? 0) + 1
      return acc
    }, {})

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      total_terms_evaluated: termsResult.total_count,
      queue_count: queue.length,
      action_distribution: actionDistribution,
      queue,
    })
  } catch (error) {
    console.error('Shopping funnel recommendations fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

