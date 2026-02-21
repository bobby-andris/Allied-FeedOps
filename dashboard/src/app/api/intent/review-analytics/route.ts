import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'

interface OperatorReviewAuditRow {
  queue_name: string
  entity_key: string
  action: string
  actor: string | null
  created_at: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
}

type NormalizedAuditRow = {
  queueName: string
  entityKey: string
  action: string
  actor: string
  createdAt: string
  beforeState: Record<string, unknown>
  afterState: Record<string, unknown>
}

type GroupStats = {
  queueName: string
  entityKey: string
  actions: Set<string>
  buckets: Set<string>
  actors: Set<string>
}

function parseRangeDays(range: string | null): number {
  switch ((range ?? '').toLowerCase()) {
    case '7d':
      return 7
    case '60d':
      return 60
    case '90d':
      return 90
    case '30d':
    default:
      return 30
  }
}

function parseLimit(rawValue: string | null): number {
  const fallback = 2000
  if (!rawValue) return fallback
  const parsed = Number.parseInt(rawValue, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return Math.min(5000, parsed)
}

function asObject(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return {}
}

function asString(value: unknown, fallback = ''): string {
  if (typeof value !== 'string') return fallback
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : fallback
}

function actionBucket(action: string): 'positive' | 'negative' | 'neutral' {
  const normalized = action.toLowerCase()
  if (
    normalized.includes('cancel') ||
    normalized.includes('reject') ||
    normalized.includes('ignore') ||
    normalized.includes('rollback')
  ) {
    return 'negative'
  }
  if (
    normalized.includes('approve') ||
    normalized.includes('promote') ||
    normalized.includes('acknowledge') ||
    normalized.includes('resolve') ||
    normalized.includes('stage') ||
    normalized.includes('apply') ||
    normalized.includes('execute')
  ) {
    return 'positive'
  }
  return 'neutral'
}

function alignmentFlag(row: NormalizedAuditRow): boolean | null {
  const selectedAction = asString(row.afterState.selected_action, '')
  const recommendedAction =
    asString(row.afterState.recommended_action, '') || asString(row.beforeState.recommended_action, '')

  if (selectedAction && recommendedAction) {
    return selectedAction.toLowerCase() === recommendedAction.toLowerCase()
  }

  const selectedTier = asString(row.afterState.selected_tier, '')
  const recommendedTier =
    asString(row.afterState.recommended_tier, '') || asString(row.beforeState.recommended_tier, '')

  if (selectedTier && recommendedTier) {
    return selectedTier.toLowerCase() === recommendedTier.toLowerCase()
  }

  return null
}

function buildGroupStats(rows: NormalizedAuditRow[]): Map<string, GroupStats> {
  const groups = new Map<string, GroupStats>()
  for (const row of rows) {
    const key = `${row.queueName}::${row.entityKey}`
    const existing = groups.get(key)
    if (existing) {
      existing.actions.add(row.action)
      existing.buckets.add(actionBucket(row.action))
      existing.actors.add(row.actor)
      continue
    }

    groups.set(key, {
      queueName: row.queueName,
      entityKey: row.entityKey,
      actions: new Set([row.action]),
      buckets: new Set([actionBucket(row.action)]),
      actors: new Set([row.actor]),
    })
  }
  return groups
}

function consistencyRateFromGroups(groups: Iterable<GroupStats>): number {
  let total = 0
  let conflicts = 0
  for (const group of groups) {
    total += 1
    const hasPositive = group.buckets.has('positive')
    const hasNegative = group.buckets.has('negative')
    if (hasPositive && hasNegative) {
      conflicts += 1
    }
  }
  if (total === 0) return 0
  return Number(((total - conflicts) / total).toFixed(4))
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const range = request.nextUrl.searchParams.get('range')
    const days = parseRangeDays(range)
    const limit = parseLimit(request.nextUrl.searchParams.get('limit'))
    const endDate = new Date()
    const startDate = new Date(endDate)
    startDate.setDate(endDate.getDate() - days)

    const supabase = createAdminClient()
    const { data, error } = await supabase
      .from('operator_review_audit')
      .select('queue_name, entity_key, action, actor, created_at, before_state, after_state')
      .gte('created_at', startDate.toISOString())
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) {
      if (isMissingRelationError(error, 'operator_review_audit')) {
        warnings.push(
          'Table "operator_review_audit" is missing. Operator calibration analytics are unavailable until migration 035 is applied.'
        )
      } else {
        throw error
      }
    }

    const normalizedRows: NormalizedAuditRow[] = (((data as OperatorReviewAuditRow[] | null) ?? [])
      .map((row) => ({
        queueName: asString(row.queue_name, 'unknown_queue'),
        entityKey: asString(row.entity_key, 'unknown_entity'),
        action: asString(row.action, 'unknown_action'),
        actor: asString(row.actor, 'unknown_actor'),
        createdAt: asString(row.created_at, new Date().toISOString()),
        beforeState: asObject(row.before_state),
        afterState: asObject(row.after_state),
      }))
      .filter((row) => row.queueName.length > 0 && row.entityKey.length > 0 && row.action.length > 0))

    const entityGroups = buildGroupStats(normalizedRows)
    const overallConsistencyRate = consistencyRateFromGroups(entityGroups.values())

    const uniqueEntities = new Set(normalizedRows.map((row) => `${row.queueName}::${row.entityKey}`))
    const uniqueActors = new Set(normalizedRows.map((row) => row.actor).filter((actor) => actor !== 'unknown_actor'))

    const nowMs = Date.now()
    const velocityCutoffMs = nowMs - 24 * 60 * 60 * 1000
    const reviewVelocity24h = normalizedRows.filter(
      (row) => new Date(row.createdAt).getTime() >= velocityCutoffMs
    ).length

    let alignmentEligible = 0
    let alignmentMatches = 0
    for (const row of normalizedRows) {
      const aligned = alignmentFlag(row)
      if (aligned == null) continue
      alignmentEligible += 1
      if (aligned) alignmentMatches += 1
    }
    const overallAlignmentRate =
      alignmentEligible === 0 ? 0 : Number((alignmentMatches / alignmentEligible).toFixed(4))

    const queueBuckets = new Map<
      string,
      {
        rows: NormalizedAuditRow[]
        groups: Map<string, GroupStats>
        actors: Set<string>
        alignmentEligible: number
        alignmentMatches: number
      }
    >()

    for (const row of normalizedRows) {
      const existing = queueBuckets.get(row.queueName)
      if (existing) {
        existing.rows.push(row)
        existing.actors.add(row.actor)
        const aligned = alignmentFlag(row)
        if (aligned != null) {
          existing.alignmentEligible += 1
          if (aligned) existing.alignmentMatches += 1
        }
        continue
      }

      const aligned = alignmentFlag(row)
      queueBuckets.set(row.queueName, {
        rows: [row],
        groups: buildGroupStats([row]),
        actors: new Set([row.actor]),
        alignmentEligible: aligned == null ? 0 : 1,
        alignmentMatches: aligned ? 1 : 0,
      })
    }

    for (const [queueName, bucket] of queueBuckets.entries()) {
      bucket.groups = buildGroupStats(bucket.rows.map((row) => ({ ...row, queueName })))
    }

    const queueSummaries = Array.from(queueBuckets.entries())
      .map(([queueName, bucket]) => ({
        queue_name: queueName,
        total_actions: bucket.rows.length,
        unique_entities: bucket.groups.size,
        unique_actors: bucket.actors.size,
        consistency_rate: consistencyRateFromGroups(bucket.groups.values()),
        alignment_rate:
          bucket.alignmentEligible === 0
            ? 0
            : Number((bucket.alignmentMatches / bucket.alignmentEligible).toFixed(4)),
      }))
      .sort((a, b) => b.total_actions - a.total_actions)

    const actorBuckets = new Map<
      string,
      {
        totalActions: number
        entities: Set<string>
        queues: Set<string>
        alignmentEligible: number
        alignmentMatches: number
      }
    >()

    for (const row of normalizedRows) {
      const key = row.actor
      const existing = actorBuckets.get(key)
      const aligned = alignmentFlag(row)
      if (existing) {
        existing.totalActions += 1
        existing.entities.add(`${row.queueName}::${row.entityKey}`)
        existing.queues.add(row.queueName)
        if (aligned != null) {
          existing.alignmentEligible += 1
          if (aligned) existing.alignmentMatches += 1
        }
        continue
      }

      actorBuckets.set(key, {
        totalActions: 1,
        entities: new Set([`${row.queueName}::${row.entityKey}`]),
        queues: new Set([row.queueName]),
        alignmentEligible: aligned == null ? 0 : 1,
        alignmentMatches: aligned ? 1 : 0,
      })
    }

    const actorSummaries = Array.from(actorBuckets.entries())
      .map(([actor, bucket]) => ({
        actor,
        total_actions: bucket.totalActions,
        unique_entities: bucket.entities.size,
        queue_count: bucket.queues.size,
        alignment_rate:
          bucket.alignmentEligible === 0
            ? 0
            : Number((bucket.alignmentMatches / bucket.alignmentEligible).toFixed(4)),
      }))
      .sort((a, b) => b.total_actions - a.total_actions)

    const conflictEntities = Array.from(entityGroups.values())
      .filter((group) => group.buckets.has('positive') && group.buckets.has('negative'))
      .map((group) => ({
        queue_name: group.queueName,
        entity_key: group.entityKey,
        actions: Array.from(group.actions).sort(),
        actor_count: group.actors.size,
      }))
      .slice(0, 20)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: {
        range: `${days}d`,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
      },
      summary: {
        total_actions: normalizedRows.length,
        unique_entities: uniqueEntities.size,
        unique_actors: uniqueActors.size,
        consistency_rate: overallConsistencyRate,
        alignment_rate: overallAlignmentRate,
        review_velocity_24h: reviewVelocity24h,
      },
      queue_summaries: queueSummaries,
      actor_summaries: actorSummaries,
      conflict_entities: conflictEntities,
      warnings,
    })
  } catch (error) {
    console.error('Review analytics fetch failed:', error)
    return NextResponse.json(
      {
        error: extractErrorMessage(error),
        warnings,
      },
      { status: 500 }
    )
  }
}
