import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { routeIntentDecision } from '@/lib/intent/policy'
import type { TermMetrics } from '@/lib/intent/types'
import { insertRowsSafe } from '@/lib/intent/persistence'
import { loadLatestValueSignalScore } from '@/lib/intent/value-signal'

interface RouteRequestTerm {
  search_term: string
  custom_label_0?: string | null
  metrics?: Partial<TermMetrics>
  value_signal_score?: number
}

interface RouteRequestBody {
  terms?: RouteRequestTerm[]
  created_by?: string
  attribution_quality_score?: number
  value_signal_score?: number
}

function coerceMetrics(input?: Partial<TermMetrics>): TermMetrics {
  return {
    impressions: Math.max(0, Number(input?.impressions ?? 0) || 0),
    clicks: Math.max(0, Number(input?.clicks ?? 0) || 0),
    conversions: Math.max(0, Number(input?.conversions ?? 0) || 0),
    conversionsValue: Math.max(0, Number(input?.conversionsValue ?? 0) || 0),
    costMicros: Math.max(0, Number(input?.costMicros ?? 0) || 0),
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as RouteRequestBody
    const terms = body.terms ?? []

    if (!Array.isArray(terms) || terms.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty terms array' },
        { status: 400 }
      )
    }

    const attributionQualityScore =
      typeof body.attribution_quality_score === 'number'
        ? Math.max(0, Math.min(1, body.attribution_quality_score))
        : undefined
    const supabase = createAdminClient()
    const warnings: string[] = []

    const shouldHydrateValueSignal =
      body.value_signal_score == null && terms.some((term) => term.value_signal_score == null)
    const fallbackValueSignalScore = shouldHydrateValueSignal
      ? await loadLatestValueSignalScore(supabase, warnings)
      : undefined

    const decisions = terms.map((term) => {
      const valueSignalScore =
        term.value_signal_score == null
          ? (body.value_signal_score == null ? fallbackValueSignalScore : Number(body.value_signal_score))
          : Number(term.value_signal_score)
      const decision = routeIntentDecision({
        searchTerm: term.search_term,
        metrics: coerceMetrics(term.metrics),
        attributionQualityScore,
        valueSignalScore,
      })

      return {
        search_term: term.search_term,
        custom_label_0: term.custom_label_0 ?? null,
        value_signal_score: valueSignalScore,
        decision,
      }
    })

    const recommendationRows = decisions.map((item) => ({
      search_term: item.search_term,
      custom_label_0: item.custom_label_0 ?? '__all__',
      recommended_action: item.decision.routeAction,
      recommended_tier: item.decision.recommendedTier ?? null,
      reason_codes: item.decision.reasonCodes,
      confidence: item.decision.confidence,
      review_status: item.decision.requiresReview ? 'pending' : 'accepted',
      metadata: {
        policy_version: item.decision.policyVersion,
        intent_class: item.decision.classification.intentClass,
        subclasses: item.decision.classification.subclasses,
        matched_tokens: item.decision.classification.matchedTokens,
        value_signal_score: item.value_signal_score,
      },
    }))

    const decisionLogRows = decisions.map((item) => ({
      search_term: item.search_term,
      custom_label_0: item.custom_label_0,
      decision_type: 'route',
      channel: 'cross_channel',
      policy_version: item.decision.policyVersion,
      decision_payload: item.decision,
      confidence: item.decision.confidence,
      requires_review: item.decision.requiresReview,
      created_by: body.created_by ?? null,
    }))

    const recommendationInsert = await insertRowsSafe(supabase, 'routing_recommendations', recommendationRows)
    if (recommendationInsert.warning) warnings.push(recommendationInsert.warning)

    const decisionLogInsert = await insertRowsSafe(supabase, 'policy_decision_log', decisionLogRows)
    if (decisionLogInsert.warning) warnings.push(decisionLogInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      decisions,
      persisted: {
        routing_recommendations: recommendationInsert.inserted,
        policy_decision_log: decisionLogInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Intent route decision failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
