import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'

type CandidateStatus = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'
type RunStatus = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'

interface PromoteBody {
  run_id?: string
  run_key?: string
  decision?: 'promote' | 'reject'
  min_sample_size?: number
  min_observed_lift?: number
  actor?: string
}

function sanitizeThreshold(value: unknown, fallback: number, min: number): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.max(parsed, min)
}

function isCandidateStatus(value: unknown): value is CandidateStatus {
  return value === 'proposed' || value === 'approved' || value === 'executing' || value === 'validated' || value === 'rejected'
}

function isRunStatus(value: unknown): value is RunStatus {
  return value === 'proposed' || value === 'approved' || value === 'executing' || value === 'validated' || value === 'rejected'
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as PromoteBody
    const decision = body.decision === 'reject' ? 'reject' : 'promote'

    if (!body.run_id && !body.run_key) {
      return NextResponse.json({ error: 'run_id or run_key is required' }, { status: 400 })
    }

    const minSampleSize = sanitizeThreshold(body.min_sample_size, 100, 1)
    const minObservedLift = sanitizeThreshold(body.min_observed_lift, 0.05, -1)

    const supabase = createAdminClient()

    let runQuery = supabase
      .from('experiment_runs')
      .select('id, run_key, status, action_id')
      .limit(1)

    runQuery = body.run_id ? runQuery.eq('id', body.run_id) : runQuery.eq('run_key', body.run_key as string)

    const { data: runRow, error: runError } = await runQuery.maybeSingle()

    if (runError) {
      if (isMissingRelationError(runError, 'experiment_runs')) {
        warnings.push('Table "experiment_runs" is missing. Apply latest migrations to enable experiment promotion gates.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          promoted: false,
          warnings,
        })
      }
      throw runError
    }

    if (!runRow) {
      return NextResponse.json({ error: 'Experiment run not found' }, { status: 404 })
    }

    if (!isRunStatus(runRow.status)) {
      return NextResponse.json({ error: `Invalid run status: ${String(runRow.status)}` }, { status: 409 })
    }

    if (runRow.status !== 'executing') {
      return NextResponse.json(
        { error: `Promotion gate requires run status executing; got ${runRow.status}` },
        { status: 409 }
      )
    }

    const { data: candidates, error: candidateError } = await supabase
      .from('experiment_candidates')
      .select('id, status, observed_lift, sample_size')
      .eq('run_id', runRow.id)

    if (candidateError) {
      if (isMissingRelationError(candidateError, 'experiment_candidates')) {
        warnings.push('Table "experiment_candidates" is missing. Apply latest migrations to enable experiment promotion gates.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          promoted: false,
          warnings,
        })
      }
      throw candidateError
    }

    const candidateRows = candidates ?? []
    const sampleTotal = candidateRows.reduce(
      (sum, row) => sum + (Number.isFinite(row.sample_size) ? Number(row.sample_size) : 0),
      0
    )

    const weightedLiftNumerator = candidateRows.reduce((sum, row) => {
      const sampleSize = Number.isFinite(row.sample_size) ? Number(row.sample_size) : 0
      const observedLift = Number.isFinite(row.observed_lift) ? Number(row.observed_lift) : null
      if (sampleSize <= 0 || observedLift === null) {
        return sum
      }
      return sum + observedLift * sampleSize
    }, 0)

    const weightedLiftDenominator = candidateRows.reduce((sum, row) => {
      const sampleSize = Number.isFinite(row.sample_size) ? Number(row.sample_size) : 0
      const observedLift = Number.isFinite(row.observed_lift) ? Number(row.observed_lift) : null
      if (sampleSize <= 0 || observedLift === null) {
        return sum
      }
      return sum + sampleSize
    }, 0)

    const weightedAverageLift = weightedLiftDenominator > 0
      ? weightedLiftNumerator / weightedLiftDenominator
      : null

    const hasRejectedCandidate = candidateRows.some((row) => row.status === 'rejected')

    const gatePass =
      decision === 'promote' &&
      candidateRows.length > 0 &&
      sampleTotal >= minSampleSize &&
      weightedAverageLift !== null &&
      weightedAverageLift >= minObservedLift &&
      !hasRejectedCandidate

    const nowIso = new Date().toISOString()
    const nextRunStatus = gatePass ? 'validated' : 'rejected'
    const nextCandidateStatus: CandidateStatus = gatePass ? 'validated' : 'rejected'
    const gateStatus = decision === 'reject'
      ? 'manual_reject'
      : gatePass
        ? 'passed'
        : 'failed'

    const gateResults = {
      decision,
      gate_pass: gatePass,
      min_sample_size: minSampleSize,
      min_observed_lift: minObservedLift,
      candidate_count: candidateRows.length,
      sample_total: sampleTotal,
      weighted_average_lift: weightedAverageLift,
      has_rejected_candidate: hasRejectedCandidate,
      actor: body.actor ?? null,
      evaluated_at: nowIso,
    }

    const { error: runUpdateError } = await supabase
      .from('experiment_runs')
      .update({
        status: nextRunStatus,
        gate_status: gateStatus,
        gate_results: gateResults,
        completed_at: nowIso,
      })
      .eq('id', runRow.id)

    if (runUpdateError) {
      throw runUpdateError
    }

    const candidateIds = candidateRows
      .map((row) => row.id)
      .filter((id): id is number => Number.isFinite(id))

    if (candidateIds.length > 0) {
      const { error: candidateUpdateError } = await supabase
        .from('experiment_candidates')
        .update({ status: nextCandidateStatus })
        .in('id', candidateIds)

      if (candidateUpdateError) {
        throw candidateUpdateError
      }
    }

    if (runRow.action_id) {
      const { data: actionRow, error: actionLookupError } = await supabase
        .from('optimization_action_queue')
        .select('metadata')
        .eq('id', runRow.action_id)
        .maybeSingle()

      if (actionLookupError && !isMissingRelationError(actionLookupError, 'optimization_action_queue')) {
        throw actionLookupError
      }
      if (actionLookupError && isMissingRelationError(actionLookupError, 'optimization_action_queue')) {
        warnings.push('Table "optimization_action_queue" is missing. Queue lifecycle linkage was not updated.')
      }

      const existingMetadata =
        actionRow?.metadata && typeof actionRow.metadata === 'object'
          ? (actionRow.metadata as Record<string, unknown>)
          : {}

      const actionUpdate: Record<string, unknown> = {
        current_state: nextRunStatus === 'validated' ? 'validated' : 'rejected',
        metadata: {
          ...existingMetadata,
          promotion_gate: {
            source: 'experiment-promotion-gate',
            run_key: runRow.run_key,
            gate_status: gateStatus,
            gate_pass: gatePass,
            evaluated_at: nowIso,
          },
        },
      }

      if (nextRunStatus === 'validated') {
        actionUpdate.validated_at = nowIso
      }

      if (!actionLookupError) {
        const { error: actionUpdateError } = await supabase
          .from('optimization_action_queue')
          .update(actionUpdate)
          .eq('id', runRow.action_id)

        if (actionUpdateError && !isMissingRelationError(actionUpdateError, 'optimization_action_queue')) {
          throw actionUpdateError
        }
        if (actionUpdateError && isMissingRelationError(actionUpdateError, 'optimization_action_queue')) {
          warnings.push('Table "optimization_action_queue" is missing. Queue lifecycle linkage was not updated.')
        }
      }
    }

    return NextResponse.json({
      generated_at: nowIso,
      promoted: gatePass,
      run_id: runRow.id,
      run_key: runRow.run_key,
      next_run_status: nextRunStatus,
      next_candidate_status: nextCandidateStatus,
      gate_status: gateStatus,
      gate_results: gateResults,
      warnings,
    })
  } catch (error) {
    console.error('Promote experiment run failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}
