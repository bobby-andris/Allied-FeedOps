import { NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { evaluateGuardrails } from '@/lib/intent/policy'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'
import { evaluateRollbackReadiness } from '@/lib/intent/incident-automation'

export async function GET() {
  try {
    const supabase = createAdminClient()
    const warnings: string[] = []

    // 1. Load open incidents
    let openCriticalIncidents = 0
    let openHighIncidents = 0
    try {
      const { data, error } = await supabase
        .from('guardrail_incidents')
        .select('severity')
        .in('status', ['open', 'acknowledged'])

      if (error) throw error

      const rows = (data ?? []) as Array<{ severity: string }>
      openCriticalIncidents = rows.filter((r) => r.severity === 'critical').length
      openHighIncidents = rows.filter((r) => r.severity === 'high').length
    } catch (error) {
      if (isMissingRelationError(error, 'guardrail_incidents')) {
        warnings.push('Table "guardrail_incidents" is missing.')
      } else {
        warnings.push(`Incident query failed: ${extractErrorMessage(error)}`)
      }
    }

    // 2. Evaluate guardrail status
    const guardrailDecision = evaluateGuardrails({
      recentSpend: 0,
      recentRevenue: 0,
      baselineSpend: 0,
      baselineRevenue: 0,
      openCriticalIncidents,
      openHighIncidents,
    })

    // 3. Count snapshots
    let snapshotCount = 0
    try {
      const { count, error } = await supabase
        .from('policy_snapshots')
        .select('id', { count: 'exact', head: true })

      if (error) throw error
      snapshotCount = count ?? 0
    } catch (error) {
      if (isMissingRelationError(error, 'policy_snapshots')) {
        warnings.push('Table "policy_snapshots" is missing.')
      } else {
        warnings.push(`Snapshot count failed: ${extractErrorMessage(error)}`)
      }
    }

    // 4. Check active cross-channel negatives
    let hasActiveNegatives = false
    try {
      const { count, error } = await supabase
        .from('negative_registry')
        .select('id', { count: 'exact', head: true })
        .eq('scope', 'cross_channel')
        .eq('active', true)

      if (error) throw error
      hasActiveNegatives = (count ?? 0) > 0
    } catch (error) {
      if (isMissingRelationError(error, 'negative_registry')) {
        warnings.push('Table "negative_registry" is missing.')
      } else {
        warnings.push(`Negative registry query failed: ${extractErrorMessage(error)}`)
      }
    }

    // 5. Evaluate readiness
    const readiness = evaluateRollbackReadiness({
      guardrailStatus: guardrailDecision.status,
      snapshotCount,
      openCriticalIncidents,
      openHighIncidents,
      hasActiveNegatives,
    })

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      ...readiness,
      context: {
        guardrail_status: guardrailDecision.status,
        snapshot_count: snapshotCount,
        open_critical_incidents: openCriticalIncidents,
        open_high_incidents: openHighIncidents,
        has_active_negatives: hasActiveNegatives,
      },
      warnings,
    })
  } catch (error) {
    console.error('Rollback readiness evaluation failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}
