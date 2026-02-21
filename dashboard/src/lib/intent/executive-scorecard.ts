import type { GuardrailRolloutStatus } from '@/lib/intent/types'

export interface ExecutiveScorecardInput {
  totalRevenue: number
  totalCost: number
  totalConversions: number
  totalConversionsValue: number
  periodDays: number
  decisionsTotal: number
  decisionsAutoApplied: number
  decisionsReviewed: number
  decisionsPending: number
  avgDecisionLatencyHours: number
  promotionCount: number
  demotionCount: number
  negativeCount: number
  holdCount: number
  guardrailStatus: GuardrailRolloutStatus
  openIncidentCount: number
}

export type HealthGrade = 'healthy' | 'degraded' | 'critical'

export interface ExecutiveScorecardResult {
  roas: number
  cpa: number
  totalRevenue: number
  totalCost: number
  totalConversions: number
  periodDays: number
  automationRate: number
  pendingReviewRate: number
  avgDecisionLatencyHours: number
  actionBreakdown: {
    promote: number
    demote: number
    negative: number
    hold: number
  }
  operationalHealth: {
    guardrailStatus: GuardrailRolloutStatus
    openIncidentCount: number
    healthGrade: HealthGrade
  }
}

function safeRatio(numerator: number, denominator: number): number {
  if (denominator <= 0) return 0
  return numerator / denominator
}

function deriveHealthGrade(
  status: GuardrailRolloutStatus,
  openIncidents: number
): HealthGrade {
  if (status === 'blocked') return 'critical'
  if (status === 'hold' || openIncidents > 0) return 'degraded'
  return 'healthy'
}

export function computeExecutiveScorecard(
  input: ExecutiveScorecardInput
): ExecutiveScorecardResult {
  const roas = safeRatio(input.totalConversionsValue, input.totalCost)
  const cpa = safeRatio(input.totalCost, input.totalConversions)
  const automationRate = safeRatio(input.decisionsAutoApplied, input.decisionsTotal)
  const pendingReviewRate = safeRatio(input.decisionsPending, input.decisionsTotal)

  const total = input.decisionsTotal
  const actionBreakdown = {
    promote: safeRatio(input.promotionCount, total),
    demote: safeRatio(input.demotionCount, total),
    negative: safeRatio(input.negativeCount, total),
    hold: safeRatio(input.holdCount, total),
  }

  return {
    roas,
    cpa,
    totalRevenue: input.totalRevenue,
    totalCost: input.totalCost,
    totalConversions: input.totalConversions,
    periodDays: input.periodDays,
    automationRate,
    pendingReviewRate,
    avgDecisionLatencyHours: input.avgDecisionLatencyHours,
    actionBreakdown,
    operationalHealth: {
      guardrailStatus: input.guardrailStatus,
      openIncidentCount: input.openIncidentCount,
      healthGrade: deriveHealthGrade(input.guardrailStatus, input.openIncidentCount),
    },
  }
}
