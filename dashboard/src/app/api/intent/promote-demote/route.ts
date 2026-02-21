import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { evaluatePromotionDemotion } from '@/lib/intent/policy'
import type { AssignmentTier } from '@/lib/shopping-funnel/types'
import type { TermMetrics } from '@/lib/intent/types'
import { insertRowsSafe } from '@/lib/intent/persistence'
import { loadLatestValueSignalScore } from '@/lib/intent/value-signal'

interface PromoteDemoteTerm {
  search_term: string
  custom_label_0?: string | null
  current_tier: AssignmentTier
  metrics: Partial<TermMetrics>
  confidence?: number
  margin_roas?: number
  attribution_quality_score?: number
  value_signal_score?: number
}

interface PromoteDemoteRequestBody {
  terms?: PromoteDemoteTerm[]
  created_by?: string
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
    const body = (await request.json()) as PromoteDemoteRequestBody
    const terms = body.terms ?? []

    if (!Array.isArray(terms) || terms.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty terms array' },
        { status: 400 }
      )
    }
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
      const decision = evaluatePromotionDemotion({
        searchTerm: term.search_term,
        currentTier: term.current_tier,
        metrics: coerceMetrics(term.metrics),
        confidence: Number(term.confidence ?? 0.5),
        marginRoas: term.margin_roas,
        attributionQualityScore: term.attribution_quality_score,
        valueSignalScore,
      })

      return {
        search_term: term.search_term,
        custom_label_0: term.custom_label_0 ?? null,
        current_tier: term.current_tier,
        value_signal_score: valueSignalScore,
        decision,
      }
    })

    const decisionLogRows = decisions.map((item) => ({
      search_term: item.search_term,
      custom_label_0: item.custom_label_0,
      decision_type: 'promote_demote',
      channel: 'shopping',
      policy_version: item.decision.policyVersion,
      decision_payload: {
        current_tier: item.current_tier,
        action: item.decision.action,
        reason_codes: item.decision.reasonCodes,
        value_signal_score: item.value_signal_score,
      },
      confidence: item.decision.confidence,
      requires_review: item.decision.action !== 'hold',
      created_by: body.created_by ?? null,
    }))

    const actionRows = decisions.map((item) => ({
      action_type: 'promote_demote',
      search_term: item.search_term,
      custom_label_0: item.custom_label_0,
      status: 'planned',
      policy_version: item.decision.policyVersion,
      action_payload: {
        current_tier: item.current_tier,
        recommended_action: item.decision.action,
      },
      reason_codes: item.decision.reasonCodes,
      created_by: body.created_by ?? null,
    }))

    const decisionLogInsert = await insertRowsSafe(supabase, 'policy_decision_log', decisionLogRows)
    if (decisionLogInsert.warning) warnings.push(decisionLogInsert.warning)

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', actionRows)
    if (actionInsert.warning) warnings.push(actionInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      decisions,
      persisted: {
        policy_decision_log: decisionLogInsert.inserted,
        policy_action_execution_log: actionInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Intent promote/demote evaluation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
