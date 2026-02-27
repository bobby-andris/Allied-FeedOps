import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

type RunStatus = 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'

interface ExperimentCandidateInput {
  candidate_key?: string
  generated_content_id?: string
  regeneration_history_id?: string
  request_id?: string
  master_sku?: string
  platform?: string
  content_type?: string
  cohort?: 'control' | 'treatment' | 'holdout'
  status?: RunStatus
  observed_lift?: number
  sample_size?: number
  metrics?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

interface CreateRunBody {
  run_key?: string
  experiment_key?: string
  action_id?: string
  change_package_id?: string
  generation_effect_window_id?: number
  status?: RunStatus
  owner?: string
  metadata?: Record<string, unknown>
  candidates?: ExperimentCandidateInput[]
}

interface UpdateRunBody {
  run_id?: string
  run_key?: string
  next_status?: RunStatus
  gate_status?: string
  gate_results?: Record<string, unknown>
}

const RUN_TRANSITIONS: Record<RunStatus, RunStatus[]> = {
  proposed: ['approved', 'rejected'],
  approved: ['executing', 'rejected'],
  executing: ['validated', 'rejected'],
  validated: [],
  rejected: [],
}

function sanitizeLimit(input: string | null, fallback = 50, max = 500): number {
  const parsed = Number(input)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return Math.min(Math.floor(parsed), max)
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

function isRunStatus(value: unknown): value is RunStatus {
  return value === 'proposed' || value === 'approved' || value === 'executing' || value === 'validated' || value === 'rejected'
}

function canTransition(from: RunStatus, to: RunStatus): boolean {
  return RUN_TRANSITIONS[from].includes(to)
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const params = request.nextUrl.searchParams
    const limit = sanitizeLimit(params.get('limit'))
    const statusParam = params.get('status')
    const status = isRunStatus(statusParam) ? statusParam : null

    const supabase = createAdminClient()

    let runQuery = supabase
      .from('experiment_runs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (status) {
      runQuery = runQuery.eq('status', status)
    }

    const { data: runs, error: runsError } = await runQuery

    if (runsError) {
      if (isMissingRelationError(runsError, 'experiment_runs')) {
        warnings.push('Table "experiment_runs" is missing. Apply latest migrations to enable R5 experiment lifecycle.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          runs: [],
          candidates: [],
          warnings,
        })
      }
      throw runsError
    }

    const runIds = (runs ?? []).map((row) => row.id).filter(Boolean)
    let candidates: Array<Record<string, unknown>> = []

    if (runIds.length > 0) {
      const { data: candidateRows, error: candidatesError } = await supabase
        .from('experiment_candidates')
        .select('*')
        .in('run_id', runIds)
        .order('created_at', { ascending: false })

      if (candidatesError) {
        if (isMissingRelationError(candidatesError, 'experiment_candidates')) {
          warnings.push('Table "experiment_candidates" is missing. Candidate-level lifecycle details are unavailable.')
        } else {
          throw candidatesError
        }
      } else {
        candidates = (candidateRows ?? []) as Array<Record<string, unknown>>
      }
    }

    const candidatesByRunId = new Map<string, Array<Record<string, unknown>>>()
    for (const candidate of candidates) {
      const runId = typeof candidate.run_id === 'string' ? candidate.run_id : null
      if (!runId) continue
      const current = candidatesByRunId.get(runId) ?? []
      current.push(candidate)
      candidatesByRunId.set(runId, current)
    }

    const runRows = (runs ?? []).map((row) => ({
      ...row,
      candidates: candidatesByRunId.get(row.id) ?? [],
    }))

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      runs: runRows,
      candidates,
      warnings,
    })
  } catch (error) {
    console.error('Fetch experiment runs failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as CreateRunBody

    if (!body.experiment_key?.trim()) {
      return NextResponse.json({ error: 'experiment_key is required' }, { status: 400 })
    }

    const status = isRunStatus(body.status) ? body.status : 'proposed'
    const runKey = body.run_key?.trim() || `${slugify(body.experiment_key)}-${Date.now()}`

    const row = {
      run_key: runKey,
      experiment_key: body.experiment_key.trim(),
      action_id: body.action_id ?? null,
      change_package_id: body.change_package_id ?? null,
      generation_effect_window_id: body.generation_effect_window_id ?? null,
      status,
      owner: body.owner ?? null,
      metadata: body.metadata ?? {},
      started_at: status === 'executing' ? new Date().toISOString() : null,
    }

    const supabase = createAdminClient()

    const { data: insertedRun, error: insertError } = await supabase
      .from('experiment_runs')
      .insert(row)
      .select('*')
      .maybeSingle()

    if (insertError) {
      if (isMissingRelationError(insertError, 'experiment_runs')) {
        warnings.push('Table "experiment_runs" is missing. Apply latest migrations to enable R5 experiment lifecycle.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          created: false,
          warnings,
        })
      }
      throw insertError
    }

    let candidateInsert: { inserted: number; warning?: string } = { inserted: 0 }

    if (insertedRun?.id && Array.isArray(body.candidates) && body.candidates.length > 0) {
      const candidateRows = body.candidates.map((candidate, index) => ({
        run_id: insertedRun.id,
        candidate_key: candidate.candidate_key?.trim() || `${runKey}-candidate-${index + 1}`,
        generated_content_id: candidate.generated_content_id ?? null,
        regeneration_history_id: candidate.regeneration_history_id ?? null,
        request_id: candidate.request_id ?? null,
        master_sku: candidate.master_sku ?? null,
        platform: candidate.platform ?? null,
        content_type: candidate.content_type ?? null,
        cohort: candidate.cohort ?? null,
        status: isRunStatus(candidate.status) ? candidate.status : 'proposed',
        observed_lift: Number.isFinite(candidate.observed_lift) ? Number(candidate.observed_lift) : null,
        sample_size: Number.isFinite(candidate.sample_size) ? Number(candidate.sample_size) : null,
        metrics: candidate.metrics ?? null,
        metadata: candidate.metadata ?? {},
      }))

      candidateInsert = await insertRowsSafe(supabase, 'experiment_candidates', candidateRows)
      if (candidateInsert.warning) {
        warnings.push(candidateInsert.warning)
      }
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      created: true,
      run: insertedRun,
      candidate_rows_inserted: candidateInsert.inserted,
      warnings,
    })
  } catch (error) {
    console.error('Create experiment run failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}

export async function PATCH(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as UpdateRunBody
    const nextStatus = body.next_status

    if (!nextStatus || !isRunStatus(nextStatus)) {
      return NextResponse.json({ error: 'next_status is required and must be a valid run status' }, { status: 400 })
    }

    if (!body.run_id && !body.run_key) {
      return NextResponse.json({ error: 'run_id or run_key is required' }, { status: 400 })
    }

    const supabase = createAdminClient()

    let lookupQuery = supabase
      .from('experiment_runs')
      .select('id, run_key, status')
      .limit(1)

    lookupQuery = body.run_id
      ? lookupQuery.eq('id', body.run_id)
      : lookupQuery.eq('run_key', body.run_key as string)

    const { data: currentRun, error: lookupError } = await lookupQuery.maybeSingle()

    if (lookupError) {
      if (isMissingRelationError(lookupError, 'experiment_runs')) {
        warnings.push('Table "experiment_runs" is missing. Apply latest migrations to enable R5 experiment lifecycle.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          updated: false,
          warnings,
        })
      }
      throw lookupError
    }

    if (!currentRun) {
      return NextResponse.json({ error: 'Experiment run not found' }, { status: 404 })
    }

    if (!isRunStatus(currentRun.status)) {
      return NextResponse.json({ error: 'Current run status is invalid' }, { status: 409 })
    }

    if (!canTransition(currentRun.status, nextStatus)) {
      return NextResponse.json(
        { error: `Invalid run status transition: ${currentRun.status} -> ${nextStatus}` },
        { status: 409 }
      )
    }

    const nowIso = new Date().toISOString()
    const payload: Record<string, unknown> = {
      status: nextStatus,
      gate_status: body.gate_status ?? null,
      gate_results: body.gate_results ?? null,
    }

    if (nextStatus === 'executing') {
      payload.started_at = nowIso
    }
    if (nextStatus === 'validated' || nextStatus === 'rejected') {
      payload.completed_at = nowIso
    }

    const { error: updateError } = await supabase
      .from('experiment_runs')
      .update(payload)
      .eq('id', currentRun.id)

    if (updateError) {
      if (isMissingRelationError(updateError, 'experiment_runs')) {
        warnings.push('Table "experiment_runs" is missing. Apply latest migrations to enable R5 experiment lifecycle.')
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
      run_id: currentRun.id,
      run_key: currentRun.run_key,
      from_status: currentRun.status,
      to_status: nextStatus,
      warnings,
    })
  } catch (error) {
    console.error('Update experiment run failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}
