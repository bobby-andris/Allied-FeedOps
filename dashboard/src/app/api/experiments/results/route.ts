import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'

function sanitizeLimit(input: string | null, fallback = 50, max = 500): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const params = request.nextUrl.searchParams
    const limit = sanitizeLimit(params.get('limit'))
    const supabase = createAdminClient()

    const { data: experiments, error: experimentsError } = await supabase
      .from('experiment_registry')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (experimentsError) {
      if (isMissingRelationError(experimentsError, 'experiment_registry')) {
        warnings.push('Table "experiment_registry" is missing. Apply latest migrations to enable experiments.')
        return NextResponse.json({
          generated_at: new Date().toISOString(),
          experiments: [],
          outcomes: [],
          warnings,
        })
      }
      throw experimentsError
    }

    const experimentKeys = (experiments ?? []).map((item) => item.experiment_key).filter(Boolean)

    type OutcomeRow = {
      experiment_key: string
      metric_name: string
      observed_lift: number
      sample_size: number
      status: string
      measured_at: string
      metadata: unknown
    }

    type AssignmentRow = {
      experiment_key: string
      entity_key: string
      cohort: 'control' | 'treatment'
      assigned_at: string
    }

    let outcomes: OutcomeRow[] = []
    let assignments: AssignmentRow[] = []

    if (experimentKeys.length > 0) {
      const { data: outcomeRows, error: outcomesError } = await supabase
        .from('experiment_outcomes')
        .select('experiment_key, metric_name, observed_lift, sample_size, status, measured_at, metadata')
        .in('experiment_key', experimentKeys)
        .order('measured_at', { ascending: false })

      if (outcomesError) {
        if (isMissingRelationError(outcomesError, 'experiment_outcomes')) {
          warnings.push('Table "experiment_outcomes" is missing. Outcome tracking is unavailable.')
        } else {
          throw outcomesError
        }
      } else {
        outcomes = (outcomeRows ?? []) as typeof outcomes
      }

      const { data: assignmentRows, error: assignmentsError } = await supabase
        .from('experiment_assignments')
        .select('experiment_key, entity_key, cohort, assigned_at')
        .in('experiment_key', experimentKeys)
        .order('assigned_at', { ascending: false })

      if (assignmentsError) {
        if (isMissingRelationError(assignmentsError, 'experiment_assignments')) {
          warnings.push('Table "experiment_assignments" is missing. Holdout assignment tracking is unavailable.')
        } else {
          throw assignmentsError
        }
      } else {
        assignments = (assignmentRows ?? []) as AssignmentRow[]
      }
    }

    const latestOutcomeByExperiment = new Map<string, OutcomeRow>()
    for (const outcome of outcomes) {
      if (!latestOutcomeByExperiment.has(outcome.experiment_key)) {
        latestOutcomeByExperiment.set(outcome.experiment_key, outcome)
      }
    }

    const assignmentStatsByExperiment = new Map<
      string,
      { controlCount: number; treatmentCount: number; totalCount: number }
    >()
    for (const assignment of assignments) {
      const current = assignmentStatsByExperiment.get(assignment.experiment_key) ?? {
        controlCount: 0,
        treatmentCount: 0,
        totalCount: 0,
      }
      if (assignment.cohort === 'control') {
        current.controlCount += 1
      } else {
        current.treatmentCount += 1
      }
      current.totalCount += 1
      assignmentStatsByExperiment.set(assignment.experiment_key, current)
    }

    const governance = (experiments ?? []).map((experiment) => {
      const latestOutcome = latestOutcomeByExperiment.get(experiment.experiment_key)
      const assignmentStats = assignmentStatsByExperiment.get(experiment.experiment_key) ?? {
        controlCount: 0,
        treatmentCount: 0,
        totalCount: 0,
      }
      const holdoutShare =
        assignmentStats.totalCount > 0 ? assignmentStats.controlCount / assignmentStats.totalCount : null

      let weeklyStatus: 'needs_data' | 'observe_more_data' | 'hold' | 'promote_to_scale' | 'rollback_or_pause' =
        'needs_data'
      if (latestOutcome) {
        if (
          experiment.success_threshold !== null &&
          Number.isFinite(experiment.success_threshold) &&
          latestOutcome.observed_lift >= Number(experiment.success_threshold)
        ) {
          weeklyStatus = 'promote_to_scale'
        } else if (
          experiment.failure_threshold !== null &&
          Number.isFinite(experiment.failure_threshold) &&
          latestOutcome.observed_lift <= Number(experiment.failure_threshold)
        ) {
          weeklyStatus = 'rollback_or_pause'
        } else if ((latestOutcome.sample_size ?? 0) < 100) {
          weeklyStatus = 'observe_more_data'
        } else {
          weeklyStatus = 'hold'
        }
      }

      const now = Date.now()
      const lastCheckpointAt = latestOutcome ? Date.parse(latestOutcome.measured_at) : Date.parse(experiment.start_date)
      const oneWeekMs = 7 * 24 * 60 * 60 * 1000
      const checkpointDue = Number.isFinite(lastCheckpointAt) ? now - lastCheckpointAt >= oneWeekMs : true

      return {
        experiment_key: experiment.experiment_key,
        initiative: experiment.initiative,
        weekly_status: weeklyStatus,
        checkpoint_due: checkpointDue,
        holdout_share: holdoutShare,
        holdout_control_count: assignmentStats.controlCount,
        holdout_treatment_count: assignmentStats.treatmentCount,
        latest_metric_name: latestOutcome?.metric_name ?? null,
        latest_observed_lift: latestOutcome?.observed_lift ?? null,
        latest_sample_size: latestOutcome?.sample_size ?? null,
        latest_measured_at: latestOutcome?.measured_at ?? null,
      }
    })

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      experiments: experiments ?? [],
      outcomes,
      assignments,
      governance,
      warnings,
    })
  } catch (error) {
    console.error('Fetch experiment results failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error), warnings },
      { status: 500 }
    )
  }
}
