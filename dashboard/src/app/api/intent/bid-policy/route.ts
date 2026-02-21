import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { getLabelTierPerformance } from '@/lib/shopping-funnel/service'
import { recommendBidPolicy } from '@/lib/intent/policy'
import type { BidPolicyInput } from '@/lib/intent/types'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'
import { loadLatestValueSignalScore } from '@/lib/intent/value-signal'

type TargetMode = 'roas' | 'cpa'

interface BidPolicyRequestBody {
  rows?: Array<{
    custom_label_0: string
    tier: 'HIGH' | 'MEDIUM' | 'LOW'
    target_mode?: TargetMode
    current_target_roas?: number
    observed_roas?: number
    current_target_cpa?: number
    observed_cpa?: number
    confidence?: number
    attribution_quality_score?: number
    value_signal_score?: number
  }>
  target_mode?: TargetMode
  start_date?: string
  end_date?: string
  created_by?: string
  value_signal_score?: number
}

function toIntentClass(tier: 'HIGH' | 'MEDIUM' | 'LOW'): BidPolicyInput['intentClass'] {
  if (tier === 'HIGH') return 'PRODUCT_HIGH'
  if (tier === 'MEDIUM') return 'CATEGORY_MID'
  return 'DISCOVERY_LOW'
}

function baselineTargetRoas(tier: 'HIGH' | 'MEDIUM' | 'LOW'): number {
  if (tier === 'HIGH') return 3.6
  if (tier === 'MEDIUM') return 3.1
  return 2.6
}

function normalizeTargetMode(value: string | null | undefined): TargetMode {
  return value === 'cpa' ? 'cpa' : 'roas'
}

async function loadLatestShoppingAttributionQualityScore(
  supabase: ReturnType<typeof createAdminClient>,
  warnings: string[]
): Promise<number | undefined> {
  try {
    if (!supabase || typeof supabase.from !== 'function') {
      return undefined
    }

    const { data, error } = await supabase
      .from('attribution_confidence_daily')
      .select('confidence_score')
      .eq('channel', 'shopping')
      .order('snapshot_date', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) throw error

    const numeric = Number(data?.confidence_score)
    if (!Number.isFinite(numeric)) {
      return undefined
    }
    return Math.max(0, Math.min(1, numeric))
  } catch (error) {
    if (isMissingRelationError(error, 'attribution_confidence_daily')) {
      warnings.push(
        'Table "attribution_confidence_daily" is missing. Bid-policy attribution confidence fallback was skipped.'
      )
    } else {
      warnings.push(
        `Unable to load latest shopping attribution confidence: ${extractErrorMessage(error)}`
      )
    }
    return undefined
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json().catch(() => ({}))) as BidPolicyRequestBody
    const supabase = createAdminClient()
    const warnings: string[] = []

    let sourceRows = body.rows
    if (!Array.isArray(sourceRows) || sourceRows.length === 0) {
      const perf = await getLabelTierPerformance({
        startDate: body.start_date,
        endDate: body.end_date,
      })
      sourceRows = perf.rows.map((row) => ({
        custom_label_0: row.custom_label_0,
        tier: row.tier,
        target_mode: 'roas' as const,
        current_target_roas: baselineTargetRoas(row.tier),
        observed_roas: row.roas,
        confidence: Math.min(row.clicks / 500, 1),
        attribution_quality_score: undefined,
      }))
    }

    const shouldHydrateAttributionQuality = sourceRows.some(
      (row) => row.attribution_quality_score == null
    )
    const fallbackAttributionQualityScore = shouldHydrateAttributionQuality
      ? await loadLatestShoppingAttributionQualityScore(supabase, warnings)
      : undefined

    const shouldHydrateValueSignal = sourceRows.some(
      (row) => row.value_signal_score == null
    ) && body.value_signal_score == null
    const fallbackValueSignalScore = shouldHydrateValueSignal
      ? await loadLatestValueSignalScore(supabase, warnings)
      : undefined

    const decisions = sourceRows.map((row) => {
      const key = `${row.custom_label_0}|${row.tier}`
      const targetMode = normalizeTargetMode(row.target_mode ?? body.target_mode)
      const currentTargetRoas =
        row.current_target_roas == null ? baselineTargetRoas(row.tier) : Number(row.current_target_roas)
      const observedRoas = row.observed_roas == null ? currentTargetRoas : Number(row.observed_roas)
      const currentTargetCpa = row.current_target_cpa == null ? 0 : Number(row.current_target_cpa)
      const observedCpa = row.observed_cpa == null ? currentTargetCpa : Number(row.observed_cpa)
      const attributionQualityScore =
        row.attribution_quality_score == null
          ? fallbackAttributionQualityScore
          : Number(row.attribution_quality_score)
      const valueSignalScore =
        row.value_signal_score == null
          ? (body.value_signal_score == null ? fallbackValueSignalScore : Number(body.value_signal_score))
          : Number(row.value_signal_score)

      const decision = recommendBidPolicy({
        key,
        channel: 'shopping',
        intentClass: toIntentClass(row.tier),
        targetMode,
        currentTargetRoas,
        observedRoas,
        currentTargetCpa,
        observedCpa,
        confidence: Number(row.confidence ?? 0.5),
        attributionQualityScore,
        valueSignalScore,
      })
      return {
        ...row,
        target_mode: targetMode,
        current_target_roas: currentTargetRoas,
        observed_roas: observedRoas,
        current_target_cpa: currentTargetCpa,
        observed_cpa: observedCpa,
        attribution_quality_score: attributionQualityScore,
        value_signal_score: valueSignalScore,
        key,
        decision,
      }
    })
    const roasDecisions = decisions.filter((item) => item.target_mode === 'roas')

    const recommendationRows = roasDecisions.map((item) => ({
      custom_label_0: item.custom_label_0,
      tier: item.tier.toLowerCase(),
      current_target_roas: item.current_target_roas,
      recommended_target_roas:
        item.decision.recommendedTargetRoas == null
          ? item.current_target_roas
          : item.decision.recommendedTargetRoas,
      confidence: item.decision.confidence,
      approved: false,
      applied: false,
      metadata: {
        policy_version: item.decision.policyVersion,
        action: item.decision.action,
        reason_codes: item.decision.reasonCodes,
        target_mode: item.target_mode,
        observed_roas: item.observed_roas,
        value_signal_score: item.value_signal_score,
      },
    }))

    const decisionLogRows = decisions.map((item) => ({
      search_term: null,
      custom_label_0: item.custom_label_0,
      decision_type: 'bid_policy',
      channel: 'shopping',
      policy_version: item.decision.policyVersion,
      decision_payload: {
        tier: item.tier,
        target_mode: item.target_mode,
        action: item.decision.action,
        recommended_target_roas:
          item.target_mode === 'roas' ? item.decision.recommendedTargetRoas : null,
        recommended_target_cpa:
          item.target_mode === 'cpa' ? item.decision.recommendedTargetCpa : null,
        value_signal_score: item.value_signal_score,
      },
      confidence: item.decision.confidence,
      requires_review: item.decision.action !== 'hold',
      created_by: body.created_by ?? null,
    }))

    const recoInsert =
      recommendationRows.length > 0
        ? await insertRowsSafe(supabase, 'roas_target_recommendations', recommendationRows)
        : { inserted: 0 }
    if ('warning' in recoInsert && recoInsert.warning) warnings.push(recoInsert.warning)

    const decisionInsert = await insertRowsSafe(supabase, 'policy_decision_log', decisionLogRows)
    if (decisionInsert.warning) warnings.push(decisionInsert.warning)

    const cpaCount = decisions.length - roasDecisions.length
    if (cpaCount > 0) {
      warnings.push(
        'CPA mode recommendations were logged to policy_decision_log only. Configure a CPA recommendation table before auto-apply.'
      )
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      decision_count: decisions.length,
      decision_mode_breakdown: {
        roas: roasDecisions.length,
        cpa: cpaCount,
      },
      decisions,
      persisted: {
        roas_target_recommendations: recoInsert.inserted,
        policy_decision_log: decisionInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Bid policy evaluation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
