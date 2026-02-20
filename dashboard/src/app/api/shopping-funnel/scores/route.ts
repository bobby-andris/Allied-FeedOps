import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildQueryScoreSummary } from '@/lib/optimization/control-center'

function sanitizeLimit(input: string | null, fallback = 3000, max = 10000): number {
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
      limit,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const summary = buildQueryScoreSummary(termsResult.terms)
    const scoreDistribution = termsResult.terms.reduce(
      (acc, term) => {
        const score = term.value_score?.impact_score ?? 0
        if (score >= 200) acc.high += 1
        else if (score >= 75) acc.medium += 1
        else acc.low += 1
        return acc
      },
      { high: 0, medium: 0, low: 0 }
    )

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      summary,
      score_distribution: scoreDistribution,
    })
  } catch (error) {
    console.error('Shopping funnel score summary fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

