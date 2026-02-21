import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

interface RollbackRequestBody {
  snapshot_id?: string
  reason?: string
  created_by?: string
}

interface PolicySnapshot {
  id: string
  snapshot_key: string
  payload: Record<string, unknown>
  policy_version: string
  created_at?: string
  restored_at?: string | null
}

function parseLimit(rawValue: string | null): number {
  const fallback = 20
  if (!rawValue) return fallback
  const parsed = Number.parseInt(rawValue, 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(100, Math.max(1, parsed))
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const warnings: string[] = []
    const limit = parseLimit(request.nextUrl.searchParams.get('limit'))

    const { data, error } = await supabase
      .from('policy_snapshots')
      .select('id, snapshot_key, policy_version, created_at, restored_at')
      .order('created_at', { ascending: false })
      .limit(limit)

    let snapshots: PolicySnapshot[] = []
    if (error) {
      if (isMissingRelationError(error, 'policy_snapshots')) {
        warnings.push('Table "policy_snapshots" is missing. Apply latest migrations to enable rollback history.')
      } else {
        throw error
      }
    } else {
      snapshots = (data as PolicySnapshot[] | null) ?? []
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      snapshot_count: snapshots.length,
      snapshots,
      warnings,
    })
  } catch (error) {
    console.error('Rollback snapshot listing failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as RollbackRequestBody
    const supabase = createAdminClient()
    const warnings: string[] = []
    let deactivatedNegativeCount = 0

    let snapshot: PolicySnapshot | null = null

    if (body.snapshot_id) {
      const { data, error } = await supabase
        .from('policy_snapshots')
        .select('id, snapshot_key, payload, policy_version')
        .eq('id', body.snapshot_id)
        .maybeSingle()

      if (error) {
        if (isMissingRelationError(error, 'policy_snapshots')) {
          warnings.push('Table "policy_snapshots" is missing. Rollback was logged without snapshot restore.')
        } else {
          throw error
        }
      } else {
        snapshot = (data as PolicySnapshot | null) ?? null
      }
    } else {
      const { data, error } = await supabase
        .from('policy_snapshots')
        .select('id, snapshot_key, payload, policy_version')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (error) {
        if (isMissingRelationError(error, 'policy_snapshots')) {
          warnings.push('Table "policy_snapshots" is missing. Rollback was logged without snapshot restore.')
        } else {
          throw error
        }
      } else {
        snapshot = (data as PolicySnapshot | null) ?? null
      }
    }

    if (snapshot) {
      const { data: rollbackCandidates, error: rollbackCandidatesError } = await supabase
        .from('negative_registry')
        .select('id')
        .eq('scope', 'cross_channel')
        .not('rollback_token', 'is', null)

      if (rollbackCandidatesError) {
        if (isMissingRelationError(rollbackCandidatesError, 'negative_registry')) {
          warnings.push('Table "negative_registry" is missing. Rollback could not deactivate cross-channel negatives.')
        } else {
          throw rollbackCandidatesError
        }
      } else {
        const candidateIds = ((rollbackCandidates as Array<{ id: string }> | null) ?? [])
          .map((row) => row.id)
          .filter((id): id is string => typeof id === 'string' && id.length > 0)

        if (candidateIds.length > 0) {
          const { error: deactivateError } = await supabase
            .from('negative_registry')
            .update({
              active: false,
              deactivated_at: new Date().toISOString(),
              deactivated_by: body.created_by ?? 'intent-control-center:rollback',
            })
            .eq('active', true)
            .in('id', candidateIds)

          if (deactivateError) {
            if (isMissingRelationError(deactivateError, 'negative_registry')) {
              warnings.push('Table "negative_registry" is missing. Rollback could not deactivate cross-channel negatives.')
            } else {
              throw deactivateError
            }
          } else {
            deactivatedNegativeCount = candidateIds.length
          }
        }
      }
    }

    const actionRows = [
      {
        action_type: 'rollback',
        search_term: null,
        custom_label_0: null,
        status: snapshot ? 'rolled_back' : 'planned',
        policy_version: snapshot?.policy_version ?? 'intent_v1',
        action_payload: {
          snapshot_id: snapshot?.id ?? null,
          snapshot_key: snapshot?.snapshot_key ?? null,
          reason: body.reason ?? 'guardrail_triggered',
        },
        reason_codes: ['rollback_protocol'],
        created_by: body.created_by ?? null,
      },
    ]

    const insertResult = await insertRowsSafe(supabase, 'policy_action_execution_log', actionRows)
    if (insertResult.warning) warnings.push(insertResult.warning)

    const operatorAuditInsert = await insertRowsSafe(supabase, 'operator_review_audit', [
      {
        queue_name: 'intent_rollback',
        entity_key: snapshot?.id ?? body.snapshot_id ?? 'latest',
        action: 'rollback_execute',
        before_state: {
          requested_snapshot_id: body.snapshot_id ?? null,
          rollback_reason: body.reason ?? 'guardrail_triggered',
        },
        after_state: {
          selected_action: 'rollback_execute',
          selected_snapshot_id: snapshot?.id ?? null,
          selected_status: snapshot ? 'rolled_back' : 'planned',
          recommended_action: 'rollback_execute',
          deactivated_negative_count: deactivatedNegativeCount,
        },
        actor: body.created_by ?? null,
      },
    ])
    if (operatorAuditInsert.warning) warnings.push(operatorAuditInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      rollback_applied: Boolean(snapshot),
      snapshot,
      deactivated_negative_count: deactivatedNegativeCount,
      warnings,
      persisted: {
        policy_action_execution_log: insertResult.inserted,
        operator_review_audit: operatorAuditInsert.inserted,
      },
    })
  } catch (error) {
    console.error('Rollback request failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}
