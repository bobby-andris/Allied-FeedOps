import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

interface AssignmentRequestBody {
  experiment_key?: string
  entity_keys?: string[]
  holdout_percent?: number
  created_by?: string
  metadata?: Record<string, unknown>
}

interface ExistingAssignment {
  entity_key: string
  cohort: 'control' | 'treatment'
}

function normalizeEntityKeys(input: string[] | undefined): string[] {
  if (!Array.isArray(input)) {
    return []
  }
  const seen = new Set<string>()
  const keys: string[] = []
  for (const raw of input) {
    if (typeof raw !== 'string') {
      continue
    }
    const value = raw.trim()
    if (!value || seen.has(value)) {
      continue
    }
    seen.add(value)
    keys.push(value)
  }
  return keys
}

function clampHoldoutPercent(input: number | undefined): number {
  if (!Number.isFinite(input)) {
    return 20
  }
  return Math.max(1, Math.min(95, Math.round(Number(input))))
}

function hashPercentile(value: string): number {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index)
    hash |= 0
  }
  return Math.abs(hash) % 100
}

function resolveCohort(experimentKey: string, entityKey: string, holdoutPercent: number): 'control' | 'treatment' {
  const percentile = hashPercentile(`${experimentKey}:${entityKey}`)
  return percentile < holdoutPercent ? 'control' : 'treatment'
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json()) as AssignmentRequestBody
    const experimentKey = body.experiment_key?.trim()
    const entityKeys = normalizeEntityKeys(body.entity_keys)
    const holdoutPercent = clampHoldoutPercent(body.holdout_percent)

    if (!experimentKey) {
      return NextResponse.json({ error: 'experiment_key is required' }, { status: 400 })
    }
    if (entityKeys.length === 0) {
      return NextResponse.json({ error: 'entity_keys is required' }, { status: 400 })
    }

    const supabase = createAdminClient()

    const { data: experimentRows, error: experimentError } = await supabase
      .from('experiment_registry')
      .select('experiment_key')
      .eq('experiment_key', experimentKey)

    if (experimentError) {
      if (isMissingRelationError(experimentError, 'experiment_registry')) {
        return NextResponse.json(
          {
            generated_at: new Date().toISOString(),
            experiment_key: experimentKey,
            assigned_count: 0,
            inserted_count: 0,
            assignments: [],
            warnings: ['Table "experiment_registry" is missing. Apply latest migrations to enable assignments.'],
          },
          { status: 200 }
        )
      }
      throw experimentError
    }

    if (!experimentRows || experimentRows.length === 0) {
      return NextResponse.json({ error: `experiment_key not found: ${experimentKey}` }, { status: 404 })
    }

    const { data: existingRows, error: existingError } = await supabase
      .from('experiment_assignments')
      .select('entity_key, cohort')
      .eq('experiment_key', experimentKey)
      .in('entity_key', entityKeys)

    if (existingError) {
      if (isMissingRelationError(existingError, 'experiment_assignments')) {
        warnings.push('Table "experiment_assignments" is missing. Apply latest migrations to enable holdout assignments.')
      } else {
        throw existingError
      }
    }

    const existingAssignments = new Map<string, ExistingAssignment>()
    for (const row of (existingRows ?? []) as ExistingAssignment[]) {
      existingAssignments.set(row.entity_key, row)
    }

    const rowsToInsert = entityKeys
      .filter((entityKey) => !existingAssignments.has(entityKey))
      .map((entityKey) => ({
        experiment_key: experimentKey,
        entity_key: entityKey,
        cohort: resolveCohort(experimentKey, entityKey, holdoutPercent),
        metadata: {
          ...(body.metadata ?? {}),
          assigned_by: body.created_by ?? null,
          holdout_percent: holdoutPercent,
        },
      }))

    const insert = await insertRowsSafe(supabase, 'experiment_assignments', rowsToInsert)
    if (insert.warning) {
      warnings.push(insert.warning)
    }

    const assignments = entityKeys.map((entityKey) => {
      const existing = existingAssignments.get(entityKey)
      if (existing) {
        return { entity_key: entityKey, cohort: existing.cohort, source: 'existing' as const }
      }
      return {
        entity_key: entityKey,
        cohort: resolveCohort(experimentKey, entityKey, holdoutPercent),
        source: 'generated' as const,
      }
    })

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      experiment_key: experimentKey,
      holdout_percent: holdoutPercent,
      assigned_count: assignments.length,
      existing_count: assignments.filter((item) => item.source === 'existing').length,
      inserted_count: insert.inserted,
      assignments,
      warnings,
    })
  } catch (error) {
    console.error('Assign experiment holdouts failed:', error)
    return NextResponse.json({ error: extractErrorMessage(error), warnings }, { status: 500 })
  }
}
