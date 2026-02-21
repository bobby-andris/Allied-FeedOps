import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'
import { computeExecutiveScorecard } from '@/lib/intent/executive-scorecard'
import type { GuardrailRolloutStatus } from '@/lib/intent/types'

function parseIntParam(value: string | null, fallback: number): number {
  if (!value) return fallback
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createAdminClient()
    const warnings: string[] = []
    const params = request.nextUrl.searchParams
    const periodDays = parseIntParam(params.get('period_days'), 30)

    // 1. Load action execution log stats
    let decisionsTotal = 0
    let decisionsAutoApplied = 0
    let decisionsReviewed = 0
    let decisionsPending = 0
    let promotionCount = 0
    let demotionCount = 0
    let negativeCount = 0
    let holdCount = 0
    let avgDecisionLatencyHours = 0

    try {
      const cutoffDate = new Date(Date.now() - periodDays * 86400000).toISOString()
      const { data, error } = await supabase
        .from('policy_action_execution_log')
        .select('action_type, status, created_at')
        .gte('created_at', cutoffDate)

      if (error) throw error

      const rows = (data ?? []) as Array<{
        action_type: string
        status: string
        created_at: string
      }>
      decisionsTotal = rows.length

      for (const row of rows) {
        if (row.status === 'applied') decisionsAutoApplied++
        else if (row.status === 'reviewed') decisionsReviewed++
        else if (row.status === 'planned') decisionsPending++

        const actionType = row.action_type ?? ''
        if (actionType.includes('promot')) promotionCount++
        else if (actionType.includes('demot')) demotionCount++
        else if (actionType === 'negative' || actionType.includes('exclude')) negativeCount++
        else holdCount++
      }

      // Compute avg decision latency from created_at spread
      if (rows.length >= 2) {
        const timestamps = rows
          .map((r) => new Date(r.created_at).getTime())
          .filter(Number.isFinite)
          .sort((a, b) => a - b)
        if (timestamps.length >= 2) {
          const spanMs = timestamps[timestamps.length - 1] - timestamps[0]
          avgDecisionLatencyHours = spanMs / (timestamps.length * 3600000)
        }
      }
    } catch (error) {
      if (isMissingRelationError(error, 'policy_action_execution_log')) {
        warnings.push('Table "policy_action_execution_log" is missing. Decision metrics unavailable.')
      } else {
        warnings.push(`Decision log query failed: ${extractErrorMessage(error)}`)
      }
    }

    // 2. Load revenue/cost from operator review audit or use params
    const totalRevenue = Number(params.get('total_revenue') ?? 0)
    const totalCost = Number(params.get('total_cost') ?? 0)
    const totalConversions = Number(params.get('total_conversions') ?? 0)
    const totalConversionsValue = totalRevenue > 0 ? totalRevenue : totalConversions * 150

    // 3. Load guardrail status
    let guardrailStatus: GuardrailRolloutStatus = 'go'
    let openIncidentCount = 0
    try {
      const { data, error } = await supabase
        .from('guardrail_incidents')
        .select('severity')
        .in('status', ['open', 'acknowledged'])

      if (error) throw error

      const incidents = (data ?? []) as Array<{ severity: string }>
      openIncidentCount = incidents.length
      const hasCritical = incidents.some((i) => i.severity === 'critical')
      const hasHigh = incidents.some((i) => i.severity === 'high')
      guardrailStatus = hasCritical ? 'blocked' : hasHigh ? 'hold' : 'go'
    } catch (error) {
      if (isMissingRelationError(error, 'guardrail_incidents')) {
        warnings.push('Table "guardrail_incidents" is missing.')
      } else {
        warnings.push(`Incident query failed: ${extractErrorMessage(error)}`)
      }
    }

    const scorecard = computeExecutiveScorecard({
      totalRevenue,
      totalCost,
      totalConversions,
      totalConversionsValue,
      periodDays,
      decisionsTotal,
      decisionsAutoApplied,
      decisionsReviewed,
      decisionsPending,
      avgDecisionLatencyHours: Number(avgDecisionLatencyHours.toFixed(2)),
      promotionCount,
      demotionCount,
      negativeCount,
      holdCount,
      guardrailStatus,
      openIncidentCount,
    })

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      ...scorecard,
      warnings,
    })
  } catch (error) {
    console.error('Executive scorecard failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}
