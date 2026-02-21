import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { routeIntentDecision } from '@/lib/intent/policy'
import type { TermMetrics } from '@/lib/intent/types'

function sanitizeLimit(input: string | null, fallback = 200, max = 5000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function aggregateMetrics(term: {
  custom_label_0s: Array<{
    impressions: number
    clicks: number
    cost_micros: number
    conversions: number
    conversions_value: number
  }>
}): TermMetrics {
  return term.custom_label_0s.reduce(
    (acc, assignment) => {
      acc.impressions += assignment.impressions
      acc.clicks += assignment.clicks
      acc.costMicros += assignment.cost_micros
      acc.conversions += assignment.conversions
      acc.conversionsValue += assignment.conversions_value
      return acc
    },
    {
      impressions: 0,
      clicks: 0,
      conversions: 0,
      conversionsValue: 0,
      costMicros: 0,
    }
  )
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
    const attributionQualityScore = (() => {
      const value = Number(params.get('attribution_quality_score'))
      if (!Number.isFinite(value)) return undefined
      return Math.max(0, Math.min(1, value))
    })()

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const decisions = termsResult.terms.map((term) => {
      const metrics = aggregateMetrics(term)
      const decision = routeIntentDecision({
        searchTerm: term.search_term,
        metrics,
        attributionQualityScore,
        existingTerm: term,
      })

      return {
        search_term: term.search_term,
        custom_label_0s: term.custom_label_0s,
        metrics,
        decision,
      }
    })

    const actionDistribution = decisions.reduce<Record<string, number>>((acc, item) => {
      const key = item.decision.routeAction
      acc[key] = (acc[key] ?? 0) + 1
      return acc
    }, {})

    const reviewRequiredCount = decisions.filter((item) => item.decision.requiresReview).length

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      policy_version: decisions[0]?.decision.policyVersion ?? 'intent_v1',
      date_window: termsResult.date_window,
      total_terms_evaluated: termsResult.total_count,
      review_required_count: reviewRequiredCount,
      action_distribution: actionDistribution,
      decisions,
    })
  } catch (error) {
    console.error('Intent decision queue fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
