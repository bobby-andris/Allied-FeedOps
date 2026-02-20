export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical'
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved' | 'ignored'
export type RolloutDecisionStatus = 'go' | 'hold' | 'blocked'

export interface OptimizationGuardrailInput {
  supplementalMultiplier: number
  supplementalWarnings: string[]
  queueMetrics: {
    total: number
    highImpactCount: number
    lowConfidenceHighImpactCount: number
  }
  roasMetrics: {
    total: number
    actionableCount: number
  }
  opportunityMetrics: {
    total: number
    highOverlapCount: number
  }
  audienceMetrics: {
    highPriorityCount: number
  }
  reportDate: string
}

export interface OptimizationGuardrailIncident {
  ruleId: string
  severity: IncidentSeverity
  status: IncidentStatus
  message: string
  impactedEntities: Array<Record<string, unknown>>
  suggestedAction: string
  metadata: Record<string, unknown>
}

export interface OptimizationRolloutDecision {
  status: RolloutDecisionStatus
  confidence: number
  rationale: string
}

export interface OptimizationGuardrailEvaluation {
  incidents: OptimizationGuardrailIncident[]
  decision: OptimizationRolloutDecision
  metrics: {
    lowConfidenceHighImpactShare: number
    roasActionableShare: number
    highOverlapClusterShare: number
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function round4(value: number): number {
  return Number(value.toFixed(4))
}

function share(numerator: number, denominator: number): number {
  if (!Number.isFinite(denominator) || denominator <= 0) {
    return 0
  }
  return numerator / denominator
}

function buildDecision(incidents: OptimizationGuardrailIncident[]): OptimizationRolloutDecision {
  const counts = incidents.reduce(
    (acc, incident) => {
      acc[incident.severity] += 1
      return acc
    },
    { low: 0, medium: 0, high: 0, critical: 0 } as Record<IncidentSeverity, number>
  )

  const status: RolloutDecisionStatus =
    counts.critical > 0 || counts.high > 0 ? 'blocked' : counts.medium >= 2 ? 'hold' : 'go'

  const riskPenalty = counts.critical * 0.35 + counts.high * 0.25 + counts.medium * 0.1 + counts.low * 0.05
  const confidence = round4(clamp(1 - riskPenalty, 0.1, 1))

  let rationale = 'Guardrails are healthy. Safe to continue monitored rollout.'
  if (status === 'blocked') {
    rationale =
      'High-severity guardrail incidents detected. Block rollout changes until attribution and recommendation quality recover.'
  } else if (status === 'hold') {
    rationale =
      'Multiple medium-risk guardrail incidents detected. Hold automation and continue manual review until signals stabilize.'
  }

  return {
    status,
    confidence,
    rationale,
  }
}

export function evaluateOptimizationGuardrails(
  input: OptimizationGuardrailInput
): OptimizationGuardrailEvaluation {
  const incidents: OptimizationGuardrailIncident[] = []

  const lowConfidenceHighImpactShare = round4(
    share(input.queueMetrics.lowConfidenceHighImpactCount, input.queueMetrics.highImpactCount)
  )
  const roasActionableShare = round4(share(input.roasMetrics.actionableCount, input.roasMetrics.total))
  const highOverlapClusterShare = round4(
    share(input.opportunityMetrics.highOverlapCount, input.opportunityMetrics.total)
  )

  if (input.supplementalMultiplier <= 0.85) {
    incidents.push({
      ruleId: 'opt_supplemental_confidence_degraded',
      severity: 'high',
      status: 'open',
      message: `Supplemental confidence multiplier dropped to ${input.supplementalMultiplier.toFixed(
        2
      )}, indicating elevated data-quality risk for automated decisions.`,
      impactedEntities: [{ domain: 'query_intelligence' }],
      suggestedAction:
        'Keep recommendation mode in manual review and investigate GA4 attribution quality + Shopify mapping coverage.',
      metadata: {
        report_date: input.reportDate,
        observed_multiplier: input.supplementalMultiplier,
        threshold: 0.85,
      },
    })
  }

  if (input.queueMetrics.highImpactCount >= 5 && lowConfidenceHighImpactShare >= 0.3) {
    incidents.push({
      ruleId: 'opt_high_impact_low_confidence',
      severity: 'high',
      status: 'open',
      message: `Low-confidence share among high-impact terms is ${(lowConfidenceHighImpactShare * 100).toFixed(
        1
      )}%, above 30% threshold.`,
      impactedEntities: [{ domain: 'review_queue' }],
      suggestedAction:
        'Increase human review rigor for top impact terms and pause automated routing proposals until confidence improves.',
      metadata: {
        report_date: input.reportDate,
        observed_share: lowConfidenceHighImpactShare,
        threshold: 0.3,
        high_impact_count: input.queueMetrics.highImpactCount,
      },
    })
  }

  if (input.roasMetrics.total >= 20 && roasActionableShare < 0.35) {
    incidents.push({
      ruleId: 'opt_roas_low_actionable_share',
      severity: 'medium',
      status: 'open',
      message: `Actionable tROAS recommendation share is ${(roasActionableShare * 100).toFixed(
        1
      )}%, below 35% threshold.`,
      impactedEntities: [{ domain: 'bidding_policy' }],
      suggestedAction:
        'Hold large-scale tROAS updates and diagnose label-tier data sufficiency before widening rollout.',
      metadata: {
        report_date: input.reportDate,
        observed_share: roasActionableShare,
        threshold: 0.35,
        total_recommendations: input.roasMetrics.total,
      },
    })
  }

  if (input.opportunityMetrics.total >= 5 && highOverlapClusterShare >= 0.4) {
    incidents.push({
      ruleId: 'opt_high_overlap_opportunity_share',
      severity: 'medium',
      status: 'open',
      message: `High-overlap opportunity cluster share is ${(highOverlapClusterShare * 100).toFixed(
        1
      )}%, above 40% threshold.`,
      impactedEntities: [{ domain: 'campaign_expansion' }],
      suggestedAction:
        'Require overlap controls and budget-capped pilots before launching new cluster-derived campaigns.',
      metadata: {
        report_date: input.reportDate,
        observed_share: highOverlapClusterShare,
        threshold: 0.4,
        total_clusters: input.opportunityMetrics.total,
      },
    })
  }

  if (input.audienceMetrics.highPriorityCount >= 3) {
    incidents.push({
      ruleId: 'opt_audience_risk_concentration',
      severity: 'medium',
      status: 'open',
      message: `${input.audienceMetrics.highPriorityCount} high-priority audience recommendations are active, signaling elevated targeting risk concentration.`,
      impactedEntities: [{ domain: 'audience_strategy' }],
      suggestedAction:
        'Prioritize audience exclusions/hold recommendations and defer scaling tests until risk concentration declines.',
      metadata: {
        report_date: input.reportDate,
        observed_count: input.audienceMetrics.highPriorityCount,
        threshold: 3,
      },
    })
  }

  if (input.supplementalWarnings.length >= 2) {
    incidents.push({
      ruleId: 'opt_supplemental_signal_unavailable',
      severity: 'low',
      status: 'open',
      message: `Multiple supplemental signal warnings detected (${input.supplementalWarnings.length}).`,
      impactedEntities: [{ domain: 'supplemental_signals' }],
      suggestedAction:
        'Continue Google Ads-first operation, but resolve supplemental signal availability gaps for safer automation.',
      metadata: {
        report_date: input.reportDate,
        warning_count: input.supplementalWarnings.length,
        warnings: input.supplementalWarnings,
      },
    })
  }

  return {
    incidents,
    decision: buildDecision(incidents),
    metrics: {
      lowConfidenceHighImpactShare,
      roasActionableShare,
      highOverlapClusterShare,
    },
  }
}
