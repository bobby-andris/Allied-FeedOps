import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

type QueueState = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'

interface QueueScoreInput {
  expected_revenue_impact?: number
  confidence_score?: number
  effort_score?: number
  policy_risk_score?: number
  score_version?: string
  inputs?: Record<string, unknown>
}

interface QueueCreateBody {
  action_key?: string
  source_type?: string
  source_ref?: string
  change_package_id?: string
  generation_effect_window_id?: number
  experiment_key?: string
  master_sku?: string
  platform?: string
  action_type?: string
  title?: string
  rationale?: string
  recommended_payload?: Record<string, unknown>
  expected_revenue_impact?: number
  confidence_score?: number
  effort_score?: number
  policy_risk_score?: number
  priority_score?: number
  metadata?: Record<string, unknown>
  score?: QueueScoreInput
}

interface QueueTransitionBody {
  action_id?: string
  action_key?: string
  next_state?: QueueState
  actor?: string
}

const TRANSITIONS: Record<QueueState, QueueState[]> = {
  proposed: ['approved', 'rejected'],
  approved: ['executing', 'rejected'],
  executing: ['validated', 'rejected'],
  validated: [],
  rejected: [],
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

function sanitizeLimit(input: string | null, fallback = 50, max = 500): number {
  const parsed = Number(input)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return Math.min(Math.floor(parsed), max)
}

function toFiniteNumber(value: unknown): number | null {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function computeCompositeScore(score: Required<Pick<QueueScoreInput, 'expected_revenue_impact' | 'confidence_score' | 'effort_score' | 'policy_risk_score'>>): number {
  return (
    score.expected_revenue_impact * 0.45 +
    score.confidence_score * 0.35 -
    score.effort_score * 0.1 -
    score.policy_risk_score * 0.1
  )
}

function normalizeScoreInput(body: QueueCreateBody): QueueScoreInput | null {
  const source = body.score ?? {}
  const expectedRevenueImpact = toFiniteNumber(source.expected_revenue_impact ?? body.expected_revenue_impact)
  const confidenceScore = toFiniteNumber(source.confidence_score ?? body.confidence_score)
  const effortScore = toFiniteNumber(source.effort_score ?? body.effort_score)
  const policyRiskScore = toFiniteNumber(source.policy_risk_score ?? body.policy_risk_score)

  if (
    expectedRevenueImpact === null &&
    confidenceScore === null &&
    effortScore === null &&
    policyRiskScore === null
  ) {
    return null
  }

  return {
    expected_revenue_impact: expectedRevenueImpact ?? 0,
    confidence_score: confidenceScore ?? 0,
    effort_score: effortScore ?? 0,
    policy_risk_score: policyRiskScore ?? 0,
    score_version: source.score_version ?? 'r5.v1',
    inputs: source.inputs ?? {},
  }
}

function isQueueState(value: unknown): value is QueueState {
  return value === 'proposed' || value === 'approved' || value === 'executing' || value === 'validated' || value === 'rejected'
}

function canTransition(current: QueueState, next: QueueState): boolean {
  return TRANSITIONS[current].includes(next)
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const params = request.nextUrl.searchParams
    const limit = sanitizeLimit(params.get('limit'))
    const stateParam = params.get('state')
    const state = isQueueState(stateParam) ? stateParam : null
    const supabase = createAdminClient()

    let queueQuery = supabase
      .from('optimization_action_queue')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (state) {
      queueQuery = queueQuery.eq('current_state', state)
    }

    const { data: queueRows, error: queueError } = await queueQuery

    if (queueError) {
      if (isMissingRelationError(queueError, 'optimization_action_queue')) {
        warnings.push('Table "optimization_action_queue" is missing. Apply latest migrations to enable optimization queue.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          queue: [],
          score_rows: [],
          warnings,
        })
      }
      throw queueError
    }

    const actionIds = (queueRows ?? []).map((row) => row.id).filter(Boolean)
    let scoreRows: Array<Record<string, unknown>> = []

    if (actionIds.length > 0) {
      const { data: scores, error: scoresError } = await supabase
        .from('optimization_action_scores')
        .select('*')
        .in('action_id', actionIds)
        .order('created_at', { ascending: false })

      if (scoresError) {
        if (isMissingRelationError(scoresError, 'optimization_action_scores')) {
          warnings.push('Table "optimization_action_scores" is missing. Queue scoring history is unavailable.')
        } else {
          throw scoresError
        }
      } else {
        scoreRows = (scores ?? []) as Array<Record<string, unknown>>
      }
    }

    const latestScoreByActionId = new Map<string, Record<string, unknown>>()
    for (const score of scoreRows) {
      const actionId = typeof score.action_id === 'string' ? score.action_id : null
      if (actionId && !latestScoreByActionId.has(actionId)) {
        latestScoreByActionId.set(actionId, score)
      }
    }

    const queue = (queueRows ?? []).map((row) => ({
      ...row,
      latest_score: latestScoreByActionId.get(row.id) ?? null,
    }))

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      queue,
      score_rows: scoreRows,
      warnings,
    })
  } catch (error) {
    console.error('Fetch optimization action queue failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as QueueCreateBody

    if (!body.title?.trim() || !body.action_type?.trim()) {
      return NextResponse.json({ error: 'title and action_type are required' }, { status: 400 })
    }

    const actionKey = body.action_key?.trim() || `${slugify(body.action_type)}-${Date.now()}`
    const scoreInput = normalizeScoreInput(body)
    const expectedRevenueImpact = scoreInput ? scoreInput.expected_revenue_impact ?? 0 : toFiniteNumber(body.expected_revenue_impact)
    const confidenceScore = scoreInput ? scoreInput.confidence_score ?? 0 : toFiniteNumber(body.confidence_score)
    const effortScore = scoreInput ? scoreInput.effort_score ?? 0 : toFiniteNumber(body.effort_score)
    const policyRiskScore = scoreInput ? scoreInput.policy_risk_score ?? 0 : toFiniteNumber(body.policy_risk_score)

    const row = {
      action_key: actionKey,
      source_type: body.source_type ?? 'lineage_outcome',
      source_ref: body.source_ref ?? null,
      change_package_id: body.change_package_id ?? null,
      generation_effect_window_id: body.generation_effect_window_id ?? null,
      experiment_key: body.experiment_key ?? null,
      master_sku: body.master_sku ?? null,
      platform: body.platform ?? null,
      action_type: body.action_type.trim(),
      title: body.title.trim(),
      rationale: body.rationale ?? null,
      recommended_payload: body.recommended_payload ?? null,
      current_state: 'proposed' as QueueState,
      priority_score: toFiniteNumber(body.priority_score),
      expected_revenue_impact: expectedRevenueImpact,
      confidence_score: confidenceScore,
      effort_score: effortScore,
      policy_risk_score: policyRiskScore,
      metadata: body.metadata ?? {},
    }

    const supabase = createAdminClient()

    const { data: insertedAction, error: insertError } = await supabase
      .from('optimization_action_queue')
      .insert(row)
      .select('*')
      .maybeSingle()

    if (insertError) {
      if (isMissingRelationError(insertError, 'optimization_action_queue')) {
        warnings.push('Table "optimization_action_queue" is missing. Apply latest migrations to enable optimization queue.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          created: false,
          warnings,
        })
      }
      throw insertError
    }

    let scoreInsert: { inserted: number; warning?: string } = { inserted: 0 }

    if (insertedAction?.id && scoreInput) {
      const scoreRow = {
        action_id: insertedAction.id,
        score_version: scoreInput.score_version ?? 'r5.v1',
        expected_revenue_impact: scoreInput.expected_revenue_impact ?? 0,
        confidence_score: scoreInput.confidence_score ?? 0,
        effort_score: scoreInput.effort_score ?? 0,
        policy_risk_score: scoreInput.policy_risk_score ?? 0,
        composite_score: computeCompositeScore({
          expected_revenue_impact: scoreInput.expected_revenue_impact ?? 0,
          confidence_score: scoreInput.confidence_score ?? 0,
          effort_score: scoreInput.effort_score ?? 0,
          policy_risk_score: scoreInput.policy_risk_score ?? 0,
        }),
        inputs: scoreInput.inputs ?? {},
      }

      scoreInsert = await insertRowsSafe(supabase, 'optimization_action_scores', [scoreRow])
      if (scoreInsert.warning) {
        warnings.push(scoreInsert.warning)
      }
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      created: true,
      action: insertedAction,
      score_rows_inserted: scoreInsert.inserted,
      warnings,
    })
  } catch (error) {
    console.error('Create optimization action failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}

export async function PATCH(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as QueueTransitionBody
    const nextState = body.next_state
    const actor = body.actor?.trim() ?? null

    if (!nextState || !isQueueState(nextState)) {
      return NextResponse.json({ error: 'next_state is required and must be a valid queue state' }, { status: 400 })
    }

    if (!body.action_id && !body.action_key) {
      return NextResponse.json({ error: 'action_id or action_key is required' }, { status: 400 })
    }

    const supabase = createAdminClient()

    let lookupQuery = supabase
      .from('optimization_action_queue')
      .select('id, action_key, current_state, metadata')
      .limit(1)

    lookupQuery = body.action_id
      ? lookupQuery.eq('id', body.action_id)
      : lookupQuery.eq('action_key', body.action_key as string)

    const { data: currentRow, error: lookupError } = await lookupQuery.maybeSingle()

    if (lookupError) {
      if (isMissingRelationError(lookupError, 'optimization_action_queue')) {
        warnings.push('Table "optimization_action_queue" is missing. Apply latest migrations to enable optimization queue.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          updated: false,
          warnings,
        })
      }
      throw lookupError
    }

    if (!currentRow) {
      return NextResponse.json({ error: 'Queue action not found' }, { status: 404 })
    }

    if (!isQueueState(currentRow.current_state)) {
      return NextResponse.json(
        { error: `Current state is invalid for action ${currentRow.action_key}` },
        { status: 409 }
      )
    }

    if (!canTransition(currentRow.current_state, nextState)) {
      return NextResponse.json(
        { error: `Invalid state transition: ${currentRow.current_state} -> ${nextState}` },
        { status: 409 }
      )
    }

    const nowIso = new Date().toISOString()
    const currentMetadata = currentRow.metadata && typeof currentRow.metadata === 'object'
      ? (currentRow.metadata as Record<string, unknown>)
      : {}

    const updatePayload: Record<string, unknown> = {
      current_state: nextState,
      metadata: {
        ...currentMetadata,
        last_transition: {
          from: currentRow.current_state,
          to: nextState,
          actor,
          at: nowIso,
        },
      },
    }

    if (nextState === 'approved') {
      updatePayload.approved_at = nowIso
      updatePayload.approved_by = actor
    } else if (nextState === 'executing') {
      updatePayload.executed_at = nowIso
    } else if (nextState === 'validated') {
      updatePayload.validated_at = nowIso
    }

    const { error: updateError } = await supabase
      .from('optimization_action_queue')
      .update(updatePayload)
      .eq('id', currentRow.id)

    if (updateError) {
      if (isMissingRelationError(updateError, 'optimization_action_queue')) {
        warnings.push('Table "optimization_action_queue" is missing. Apply latest migrations to enable optimization queue.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          updated: false,
          warnings,
        })
      }
      throw updateError
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      updated: true,
      action_id: currentRow.id,
      action_key: currentRow.action_key,
      from_state: currentRow.current_state,
      to_state: nextState,
      warnings,
    })
  } catch (error) {
    console.error('Update optimization action failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}
