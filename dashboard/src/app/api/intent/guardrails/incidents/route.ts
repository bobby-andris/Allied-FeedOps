import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

type IncidentAction = 'acknowledge' | 'resolve' | 'ignore'

interface IncidentStatusRequestBody {
  incident_id?: string
  action?: IncidentAction | string
  actor?: string
  note?: string
}

const VALID_ACTIONS = new Set<IncidentAction>(['acknowledge', 'resolve', 'ignore'])

function updatePayloadForAction(action: IncidentAction, actor: string | null, now: string) {
  if (action === 'acknowledge') {
    return {
      status: 'acknowledged',
      acknowledged_at: now,
      acknowledged_by: actor,
    }
  }

  if (action === 'resolve') {
    return {
      status: 'resolved',
      resolved_at: now,
    }
  }

  return {
    status: 'ignored',
    resolved_at: now,
  }
}

export async function POST(request: NextRequest) {
  const warnings: string[] = []
  try {
    const body = (await request.json().catch(() => ({}))) as IncidentStatusRequestBody
    const incidentId = typeof body.incident_id === 'string' ? body.incident_id.trim() : ''
    const action = typeof body.action === 'string' ? body.action.trim().toLowerCase() : ''
    const actor = typeof body.actor === 'string' && body.actor.trim().length > 0 ? body.actor : null

    if (!incidentId) {
      return NextResponse.json({ error: 'incident_id is required' }, { status: 400 })
    }

    if (!VALID_ACTIONS.has(action as IncidentAction)) {
      return NextResponse.json(
        { error: 'action must be one of: acknowledge, resolve, ignore' },
        { status: 400 }
      )
    }

    const timestamp = new Date().toISOString()
    const supabase = createAdminClient()
    const payload = updatePayloadForAction(action as IncidentAction, actor, timestamp)

    const { data, error } = await supabase
      .from('guardrail_incidents')
      .update(payload)
      .eq('id', incidentId)
      .select('id, rule_id, severity, status, acknowledged_at, acknowledged_by, resolved_at')
      .maybeSingle()

    if (error) {
      if (isMissingRelationError(error, 'guardrail_incidents')) {
        warnings.push(
          'Table "guardrail_incidents" is missing. Incident status update could not be persisted.'
        )
        return NextResponse.json(
          {
            generated_at: timestamp,
            updated: false,
            warnings,
          },
          { status: 200 }
        )
      }
      throw error
    }

    if (!data) {
      return NextResponse.json({ error: `Incident ${incidentId} not found` }, { status: 404 })
    }

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', [
      {
        action_type: 'guardrail_incident_status_update',
        search_term: null,
        custom_label_0: null,
        status: 'applied',
        policy_version: 'intent_v1',
        action_payload: {
          incident_id: incidentId,
          action,
          note: body.note ?? null,
        },
        reason_codes: ['guardrail_incident_update', `action_${action}`],
        created_by: actor,
      },
    ])
    if (actionInsert.warning) warnings.push(actionInsert.warning)

    const operatorAuditInsert = await insertRowsSafe(supabase, 'operator_review_audit', [
      {
        queue_name: 'guardrail_incidents',
        entity_key: incidentId,
        action,
        before_state: {
          rule_id: data.rule_id ?? null,
          severity: data.severity ?? null,
        },
        after_state: {
          selected_action: action,
          selected_status: data.status ?? null,
          recommended_action: action,
          recommended_status: data.status ?? null,
        },
        actor,
      },
    ])
    if (operatorAuditInsert.warning) warnings.push(operatorAuditInsert.warning)

    return NextResponse.json({
      generated_at: timestamp,
      updated: true,
      incident: data,
      warnings,
      persisted: {
        policy_action_execution_log: actionInsert.inserted,
        operator_review_audit: operatorAuditInsert.inserted,
      },
    })
  } catch (error) {
    console.error('Guardrail incident status update failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error), warnings },
      { status: 500 }
    )
  }
}
