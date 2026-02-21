import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { evaluateGuardrails } from '@/lib/intent/policy'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'
import { autoDetectIncidents } from '@/lib/intent/incident-automation'

function sanitizeNumber(value: string | null): number | null {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  return parsed
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const supabase = createAdminClient()
    const warnings: string[] = []

    const recentSpendParam = sanitizeNumber(params.get('recent_spend'))
    const recentRevenueParam = sanitizeNumber(params.get('recent_revenue'))
    const baselineSpendParam = sanitizeNumber(params.get('baseline_spend'))
    const baselineRevenueParam = sanitizeNumber(params.get('baseline_revenue'))
    const attributionQualityParam = sanitizeNumber(params.get('attribution_quality_score'))

    let openCriticalIncidents = 0
    let openHighIncidents = 0
    let incidentRows: Array<{
      id: string
      rule_id: string
      severity: 'low' | 'medium' | 'high' | 'critical'
      status: string
      message: string
      suggested_action: string | null
      created_at: string
    }> = []

    try {
      const { data, error } = await supabase
        .from('guardrail_incidents')
        .select('id, rule_id, severity, status, message, suggested_action, created_at')
        .in('status', ['open', 'acknowledged'])
        .order('created_at', { ascending: false })
        .limit(100)

      if (error) throw error

      incidentRows = (data ?? []) as typeof incidentRows
      openCriticalIncidents = incidentRows.filter((row) => row.severity === 'critical').length
      openHighIncidents = incidentRows.filter((row) => row.severity === 'high').length
    } catch (error) {
      if (isMissingRelationError(error, 'guardrail_incidents')) {
        warnings.push('Table "guardrail_incidents" is missing. Guardrail incident history is unavailable.')
      } else {
        warnings.push(`Guardrail incidents unavailable: ${extractErrorMessage(error)}`)
      }
    }

    let staleDataHours = 0
    try {
      const { data, error } = await supabase
        .from('query_value_scores')
        .select('created_at')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (error) throw error

      if (data?.created_at) {
        const ageMs = Date.now() - new Date(data.created_at).getTime()
        staleDataHours = Math.max(0, ageMs / (1000 * 60 * 60))
      }
    } catch (error) {
      if (isMissingRelationError(error, 'query_value_scores')) {
        warnings.push('Table "query_value_scores" is missing. Data freshness checks are degraded.')
      } else {
        warnings.push(`Unable to evaluate data staleness: ${extractErrorMessage(error)}`)
      }
    }

    const recentSpend = recentSpendParam ?? 0
    const recentRevenue = recentRevenueParam ?? 0
    const baselineSpend = baselineSpendParam ?? (recentSpend > 0 ? recentSpend * 0.9 : 0)
    const baselineRevenue = baselineRevenueParam ?? (recentRevenue > 0 ? recentRevenue * 0.95 : 0)

    const guardrailDecision = evaluateGuardrails({
      recentSpend,
      recentRevenue,
      baselineSpend,
      baselineRevenue,
      attributionQualityScore: attributionQualityParam ?? undefined,
      staleDataHours,
      openCriticalIncidents,
      openHighIncidents,
    })

    // Auto-detect and persist new incidents from guardrail evaluation
    const existingOpenRuleIds = incidentRows.map((row) => row.rule_id)
    const autoDetected = autoDetectIncidents({
      guardrailDecision,
      existingOpenRuleIds,
    })

    let autoCreatedCount = 0
    if (autoDetected.newIncidents.length > 0) {
      try {
        const insertResult = await insertRowsSafe(
          supabase,
          'guardrail_incidents',
          autoDetected.newIncidents as unknown as Record<string, unknown>[]
        )
        autoCreatedCount = insertResult.inserted
        if (insertResult.warning) warnings.push(insertResult.warning)
      } catch {
        warnings.push('Failed to auto-persist detected incidents.')
      }
    }

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      status: guardrailDecision.status,
      policy_version: guardrailDecision.policyVersion,
      reason_codes: guardrailDecision.reasonCodes,
      derived_incidents: guardrailDecision.incidents,
      open_incidents: incidentRows,
      open_critical_incidents: openCriticalIncidents,
      open_high_incidents: openHighIncidents,
      stale_data_hours: Number(staleDataHours.toFixed(2)),
      auto_created_incidents: autoCreatedCount,
      auto_skipped_incidents: autoDetected.skippedCount,
      warnings,
    })
  } catch (error) {
    console.error('Guardrail evaluation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
