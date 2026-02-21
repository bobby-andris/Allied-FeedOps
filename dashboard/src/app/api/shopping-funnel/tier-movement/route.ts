import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { evaluatePromotionDemotion } from '@/lib/intent/policy'
import {
  executeTierMovementBatch,
  updateSupplementalFeedTiers,
} from '@/lib/intent/tier-movement'
import type { AssignmentTier } from '@/lib/shopping-funnel/types'
import type {
  GuardrailInput,
  PromotionDemotionAction,
  TermMetrics,
  TierMovementRequest,
} from '@/lib/intent/types'
import { INTENT_POLICY_VERSION } from '@/lib/intent/types'
import { extractErrorMessage } from '@/lib/intent/persistence'

interface TierMovementRequestBody {
  movements: Array<{
    search_term: string
    custom_label_0: string
    current_tier: AssignmentTier
    target_tier: AssignmentTier
    confidence?: number
    metrics?: Partial<TermMetrics>
    margin_roas?: number
    gmc_offer_ids?: string[]
  }>
  dry_run?: boolean
  created_by?: string
  guardrail_override?: GuardrailInput
}

function actionForTierChange(
  currentTier: AssignmentTier,
  targetTier: AssignmentTier
): PromotionDemotionAction {
  if (targetTier === 'campaign_negative') return 'negative'
  if (currentTier === 'low' && targetTier === 'medium') return 'promote_to_medium'
  if (currentTier === 'low' && targetTier === 'high') return 'promote_to_high'
  if (currentTier === 'medium' && targetTier === 'high') return 'promote_to_high'
  if (currentTier === 'high' && targetTier === 'medium') return 'demote_to_medium'
  if (currentTier === 'high' && targetTier === 'low') return 'demote_to_low'
  if (currentTier === 'medium' && targetTier === 'low') return 'demote_to_low'
  return 'hold'
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
    const body = (await request.json()) as TierMovementRequestBody

    if (!Array.isArray(body.movements) || body.movements.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty movements array' },
        { status: 400 }
      )
    }

    if (body.movements.length > 100) {
      return NextResponse.json(
        { error: 'Maximum 100 movements per batch' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()

    // Build guardrail input — use override if provided, otherwise use defaults
    const guardrailInput: GuardrailInput = body.guardrail_override ?? {
      recentSpend: 0,
      recentRevenue: 0,
      baselineSpend: 0,
      baselineRevenue: 0,
    }

    // Build movement requests with policy validation
    const movementRequests: TierMovementRequest[] = body.movements.map((m) => {
      const action = actionForTierChange(m.current_tier, m.target_tier)
      const metrics = coerceMetrics(m.metrics)

      // Run policy evaluation to validate the movement
      const policyDecision = evaluatePromotionDemotion({
        searchTerm: m.search_term,
        currentTier: m.current_tier,
        metrics,
        confidence: Number(m.confidence ?? 0.5),
        marginRoas: m.margin_roas,
      })

      return {
        searchTerm: m.search_term,
        customLabel0: m.custom_label_0,
        currentTier: m.current_tier,
        targetTier: m.target_tier,
        action,
        confidence: policyDecision.confidence,
        reasonCodes: policyDecision.reasonCodes,
        policyVersion: INTENT_POLICY_VERSION,
        requestedBy: body.created_by,
      }
    })

    // Execute batch
    const batchResult = await executeTierMovementBatch(supabase, {
      movements: movementRequests,
      dryRun: body.dry_run,
      createdBy: body.created_by,
    }, guardrailInput)

    // If not dry run and there are applied movements, update Google Sheets
    const sheetErrors: string[] = []
    if (!body.dry_run && batchResult.appliedCount > 0) {
      const appliedMovements = batchResult.results
        .filter((r) => r.status === 'applied')
        .map((r, idx) => {
          const original = body.movements[idx]
          return {
            gmcOfferIds: original?.gmc_offer_ids ?? [],
            newLabelValue: r.customLabel0,
          }
        })
        .filter((m) => m.gmcOfferIds.length > 0)

      if (appliedMovements.length > 0) {
        try {
          const sheetResult = await updateSupplementalFeedTiers(appliedMovements)
          if (sheetResult.errors.length > 0) {
            sheetErrors.push(...sheetResult.errors)
          }
        } catch (error) {
          sheetErrors.push(`Sheet update failed: ${extractErrorMessage(error)}`)
        }
      }
    }

    return NextResponse.json({
      ...batchResult,
      sheetErrors: sheetErrors.length > 0 ? sheetErrors : undefined,
    })
  } catch (error) {
    console.error('Tier movement execution failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const limit = Math.min(Math.max(1, Number(params.get('limit') ?? 50)), 200)
    const status = params.get('status') ?? 'applied'

    const supabase = createAdminClient()

    const { data, error } = await supabase
      .from('policy_action_execution_log')
      .select('id, action_type, search_term, custom_label_0, status, policy_version, action_payload, reason_codes, created_by, created_at')
      .eq('action_type', 'tier_movement')
      .eq('status', status)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw error
    }

    const entries = (data ?? []).map((row) => {
      const payload = (typeof row.action_payload === 'object' && row.action_payload !== null)
        ? row.action_payload as Record<string, unknown>
        : {}
      return {
        id: row.id,
        searchTerm: row.search_term,
        customLabel0: row.custom_label_0,
        previousTier: payload.previous_tier ?? null,
        newTier: payload.new_tier ?? null,
        action: payload.action ?? null,
        status: row.status,
        confidence: null,
        reasonCodes: row.reason_codes ?? [],
        createdBy: row.created_by,
        createdAt: row.created_at,
      }
    })

    return NextResponse.json({
      entries,
      count: entries.length,
      generated_at: new Date().toISOString(),
    })
  } catch (error) {
    console.error('Tier movement history fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
