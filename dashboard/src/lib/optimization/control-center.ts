import type { NeedsDecisionTerm } from '@/lib/shopping-funnel/types'
import { computeReviewerPriorityScore } from '@/lib/shopping-funnel/reviewer-priority'
import type { SupplementalConfidenceGate } from '@/lib/optimization/supplemental-confidence'

const BASELINE_TARGET_ROAS = {
  HIGH: 3.6,
  MEDIUM: 3.1,
  LOW: 2.6,
} as const

const MAX_ROAS_STEP_PCT = 0.1
const NEAR_TARGET_BAND_PCT = 0.08
const ADAPTIVE_ADJUSTMENT_GAIN = 0.6
const MIN_SPEND_FOR_ACTION = 100
const MIN_CLICKS_FOR_ACTION = 40
const MIN_CONVERSIONS_FOR_ACTION = 3
const MIN_CONFIDENCE_FOR_ACTION = 0.35

export interface OpportunityCluster {
  clusterKey: string
  termCount: number
  totalImpressions: number
  totalClicks: number
  totalCost: number
  aggregateImpactScore: number
  averageCpc: number
  attractivenessScore: number
  overlapRiskScore: number
  overlapRiskLevel: 'low' | 'medium' | 'high'
  averageRecommendationConfidence: number
  averageUncertainty: number
  uniqueLabelCount: number
  topCustomLabels: string[]
  topSearchTerms: string[]
}

export interface OpportunityLaunchBrief {
  clusterKey: string
  pilotName: string
  priority: 'high' | 'medium' | 'low'
  strategySummary: string
  budgetCapUsd: number
  observationWindowDays: number
  topTerms: string[]
  negativeControls: string[]
  buildoutChecklist: string[]
  successCriteria: {
    targetRoas: number
    minClicks: number
    minConversions: number
  }
  stopConditions: string[]
}

export interface LabelTierPerformanceRow {
  customLabel0: string
  tier: keyof typeof BASELINE_TARGET_ROAS
  spend: number
  conversionValue: number
  conversions: number
  clicks: number
}

export interface RecommendationQueueItem {
  searchTerm: string
  priorityScore: number
  impactScore: number
  baseConfidence: number
  confidence: number
  confidenceMultiplier: number
  confidenceAdjustmentReasons: string[]
  actionType: 'funnel' | 'global_block' | 'competitor' | 'branded'
  defaultTier?: 'campaign_negative' | 'high' | 'medium' | 'low'
  reasonCodes: string[]
  customLabelCount: number
  impressions: number
  clicks: number
  conversions: number
  cost: number
  conversionValue: number
}

export interface QueryScoreSummary {
  termCount: number
  avgImpactScore: number
  avgExpectedProfitProxy: number
  avgUncertainty: number
  topImpactTerms: Array<{ searchTerm: string; impactScore: number }>
}

export interface RecommendationQueueOptions {
  supplementalGate?: Pick<SupplementalConfidenceGate, 'multiplier' | 'reasons'>
}

export interface RoasRecommendation {
  customLabel0: string
  tier: keyof typeof BASELINE_TARGET_ROAS
  currentTargetRoas: number
  observedRoas: number
  roasGapRatio: number
  recommendedTargetRoas: number
  appliedStepPct: number
  maxAllowedStepPct: number
  direction: 'increase' | 'decrease' | 'hold'
  guardrailStatus: 'actionable' | 'insufficient_data' | 'near_target_band'
  confidence: number
  confidenceComponents: {
    clickConfidence: number
    conversionConfidence: number
    spendConfidence: number
    final: number
  }
  rationale: string
}

function deriveClusterKey(term: NeedsDecisionTerm): string {
  const objectKey = term.intent_features?.product_object?.trim().toLowerCase()
  if (objectKey) {
    return objectKey
  }

  const tokens = term.search_term.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (tokens.length === 0) {
    return 'uncategorized'
  }
  return tokens.slice(0, Math.min(2, tokens.length)).join(' ')
}

function aggregateTermMetrics(term: NeedsDecisionTerm): {
  impressions: number
  clicks: number
  cost: number
} {
  return term.custom_label_0s.reduce(
    (acc, assignment) => {
      acc.impressions += assignment.impressions
      acc.clicks += assignment.clicks
      acc.cost += assignment.cost_micros / 1_000_000
      return acc
    },
    { impressions: 0, clicks: 0, cost: 0 }
  )
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function deriveOverlapRiskLevel(score: number): OpportunityCluster['overlapRiskLevel'] {
  if (score >= 0.6) return 'high'
  if (score >= 0.35) return 'medium'
  return 'low'
}

export function buildOpportunityClusters(terms: NeedsDecisionTerm[]): OpportunityCluster[] {
  const byCluster = new Map<
    string,
    {
      terms: string[]
      impressions: number
      clicks: number
      cost: number
      impact: number
      confidence: number
      uncertainty: number
      mismatchCount: number
      labelCounts: Map<string, number>
    }
  >()

  for (const term of terms) {
    if (term.recommendation?.action_type && term.recommendation.action_type !== 'funnel') {
      continue
    }
    if (term.intent_features?.is_branded || term.intent_features?.is_competitor) {
      continue
    }

    const key = deriveClusterKey(term)
    const metrics = aggregateTermMetrics(term)
    const aggregate = byCluster.get(key) ?? {
      terms: [],
      impressions: 0,
      clicks: 0,
      cost: 0,
      impact: 0,
      confidence: 0,
      uncertainty: 0,
      mismatchCount: 0,
      labelCounts: new Map<string, number>(),
    }

    aggregate.terms.push(term.search_term)
    aggregate.impressions += metrics.impressions
    aggregate.clicks += metrics.clicks
    aggregate.cost += metrics.cost
    aggregate.impact += term.value_score?.impact_score ?? 0
    aggregate.confidence += term.recommendation?.confidence ?? 0
    aggregate.uncertainty += term.value_score?.uncertainty ?? 0
    if (term.intent_features?.has_mismatch_risk) {
      aggregate.mismatchCount += 1
    }
    for (const assignment of term.custom_label_0s) {
      aggregate.labelCounts.set(
        assignment.custom_label_0,
        (aggregate.labelCounts.get(assignment.custom_label_0) ?? 0) + assignment.impressions
      )
    }

    byCluster.set(key, aggregate)
  }

  const clusters: OpportunityCluster[] = []
  for (const [clusterKey, aggregate] of byCluster.entries()) {
    const termCount = aggregate.terms.length
    const averageCpc = aggregate.clicks > 0 ? aggregate.cost / aggregate.clicks : 0
    const lowCpcFactor = 1 / (1 + Math.max(averageCpc, 0))
    const avgImpact = aggregate.impact / Math.max(termCount, 1)
    const averageRecommendationConfidence = aggregate.confidence / Math.max(termCount, 1)
    const averageUncertainty = aggregate.uncertainty / Math.max(termCount, 1)
    const mismatchRate = aggregate.mismatchCount / Math.max(termCount, 1)
    const uniqueLabelCount = aggregate.labelCounts.size
    const labelDispersionScore = clamp((uniqueLabelCount - 1) / 3, 0, 1)
    const overlapRiskScore = clamp(
      labelDispersionScore * 0.45 + mismatchRate * 0.35 + averageUncertainty * 0.2,
      0,
      1
    )
    const confidenceFactor = 0.6 + averageRecommendationConfidence * 0.4
    const overlapPenaltyFactor = 1 - overlapRiskScore * 0.55
    const attractivenessScore = avgImpact * lowCpcFactor * confidenceFactor * overlapPenaltyFactor
    const topCustomLabels = Array.from(aggregate.labelCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([label]) => label)

    clusters.push({
      clusterKey,
      termCount,
      totalImpressions: aggregate.impressions,
      totalClicks: aggregate.clicks,
      totalCost: Number(aggregate.cost.toFixed(2)),
      aggregateImpactScore: Number(aggregate.impact.toFixed(2)),
      averageCpc: Number(averageCpc.toFixed(4)),
      attractivenessScore: Number(attractivenessScore.toFixed(4)),
      overlapRiskScore: Number(overlapRiskScore.toFixed(4)),
      overlapRiskLevel: deriveOverlapRiskLevel(overlapRiskScore),
      averageRecommendationConfidence: Number(averageRecommendationConfidence.toFixed(4)),
      averageUncertainty: Number(averageUncertainty.toFixed(4)),
      uniqueLabelCount,
      topCustomLabels,
      topSearchTerms: aggregate.terms.slice(0, 10),
    })
  }

  return clusters.sort((a, b) => b.attractivenessScore - a.attractivenessScore)
}

function normalizeClusterPriority(cluster: OpportunityCluster): OpportunityLaunchBrief['priority'] {
  if (cluster.attractivenessScore >= 90 && cluster.overlapRiskLevel !== 'high') {
    return 'high'
  }
  if (cluster.attractivenessScore >= 45 || cluster.overlapRiskLevel === 'medium') {
    return 'medium'
  }
  return 'low'
}

function buildNegativeControls(cluster: OpportunityCluster): string[] {
  const controls = [
    `Apply negatives to prevent overlap with existing ${cluster.clusterKey} funnel tiers.`,
    'Add branded and competitor exclusions for this pilot unless intentionally testing those segments.',
  ]
  for (const label of cluster.topCustomLabels.slice(0, 3)) {
    controls.push(`Apply overlap negatives for "${label}" outside the pilot scope.`)
  }
  return Array.from(new Set(controls))
}

function computeBudgetCap(cluster: OpportunityCluster): number {
  const seeded = Math.round(cluster.totalCost * 1.5)
  return clamp(seeded, 75, 650)
}

export function buildOpportunityLaunchBriefs(
  clusters: OpportunityCluster[],
  options?: {
    accountMedianRoas?: number
    maxBriefs?: number
  }
): OpportunityLaunchBrief[] {
  const medianRoas = options?.accountMedianRoas ?? 3
  const maxBriefs = options?.maxBriefs ?? 10

  return clusters.slice(0, Math.max(1, maxBriefs)).map((cluster) => {
    const priority = normalizeClusterPriority(cluster)
    const budgetCapUsd = computeBudgetCap(cluster)
    const targetRoas = Number((medianRoas * 1.2).toFixed(2))
    const minClicks = cluster.termCount >= 3 ? 80 : 50
    const minConversions = cluster.termCount >= 3 ? 3 : 2

    return {
      clusterKey: cluster.clusterKey,
      pilotName: `Pilot - ${cluster.clusterKey}`,
      priority,
      strategySummary:
        cluster.overlapRiskLevel === 'high'
          ? 'High overlap risk cluster. Launch with strict negatives and conservative budget while validating incremental lift.'
          : 'Low-CPC/high-intent cluster. Launch a constrained pilot to validate incremental volume before scale-up.',
      budgetCapUsd,
      observationWindowDays: 14,
      topTerms: cluster.topSearchTerms.slice(0, 5),
      negativeControls: buildNegativeControls(cluster),
      buildoutChecklist: [
        'Create dedicated pilot campaign or ad group for this query cluster.',
        'Apply shared negative lists and cluster-specific overlap controls.',
        'Tag pilot assets and budget for holdout comparison.',
      ],
      successCriteria: {
        targetRoas,
        minClicks,
        minConversions,
      },
      stopConditions: [
        `Pause if spend exceeds $${budgetCapUsd} before reaching ${minConversions} conversions.`,
        `Pause if ROAS remains below ${(targetRoas * 0.75).toFixed(2)}x after 14 days.`,
        'Pause immediately if overlap/cannibalization signals are confirmed.',
      ],
    }
  })
}

export function buildRecommendationQueue(
  terms: NeedsDecisionTerm[],
  limit = 100,
  options?: RecommendationQueueOptions
): RecommendationQueueItem[] {
  const confidenceMultiplier = clamp(options?.supplementalGate?.multiplier ?? 1, 0.6, 1)
  const confidenceAdjustmentReasons = options?.supplementalGate?.reasons ?? []

  const queue = terms
    .map((term) => {
      const aggregates = term.custom_label_0s.reduce(
        (acc, assignment) => {
          acc.impressions += assignment.impressions
          acc.clicks += assignment.clicks
          acc.conversions += assignment.conversions
          acc.cost += assignment.cost_micros / 1_000_000
          acc.conversionValue += assignment.conversions_value
          return acc
        },
        {
          impressions: 0,
          clicks: 0,
          conversions: 0,
          cost: 0,
          conversionValue: 0,
        }
      )

      const baseConfidence = term.recommendation?.confidence ?? 0
      const gatedConfidence = clamp(baseConfidence * confidenceMultiplier, 0, 0.99)

      return {
        searchTerm: term.search_term,
        priorityScore: computeReviewerPriorityScore(term.value_score),
        impactScore: term.value_score?.impact_score ?? 0,
        baseConfidence: Number(baseConfidence.toFixed(4)),
        confidence: Number(gatedConfidence.toFixed(4)),
        confidenceMultiplier: Number(confidenceMultiplier.toFixed(4)),
        confidenceAdjustmentReasons,
        actionType: term.recommendation?.action_type ?? 'funnel',
        defaultTier: term.recommendation?.default_tier,
        reasonCodes: term.recommendation?.reason_codes ?? [],
        customLabelCount: term.custom_label_0s.length,
        impressions: aggregates.impressions,
        clicks: aggregates.clicks,
        conversions: aggregates.conversions,
        cost: Number(aggregates.cost.toFixed(2)),
        conversionValue: Number(aggregates.conversionValue.toFixed(2)),
      } satisfies RecommendationQueueItem
    })
    .sort((a, b) => {
      const priorityDelta = b.priorityScore - a.priorityScore
      if (priorityDelta !== 0) return priorityDelta
      return b.impactScore - a.impactScore
    })

  return queue.slice(0, Math.max(1, limit))
}

export function buildQueryScoreSummary(terms: NeedsDecisionTerm[]): QueryScoreSummary {
  if (terms.length === 0) {
    return {
      termCount: 0,
      avgImpactScore: 0,
      avgExpectedProfitProxy: 0,
      avgUncertainty: 0,
      topImpactTerms: [],
    }
  }

  const totals = terms.reduce(
    (acc, term) => {
      acc.impact += term.value_score?.impact_score ?? 0
      acc.profit += term.value_score?.expected_profit_proxy ?? 0
      acc.uncertainty += term.value_score?.uncertainty ?? 0
      return acc
    },
    { impact: 0, profit: 0, uncertainty: 0 }
  )

  const topImpactTerms = terms
    .map((term) => ({
      searchTerm: term.search_term,
      impactScore: term.value_score?.impact_score ?? 0,
    }))
    .sort((a, b) => b.impactScore - a.impactScore)
    .slice(0, 10)

  return {
    termCount: terms.length,
    avgImpactScore: Number((totals.impact / terms.length).toFixed(2)),
    avgExpectedProfitProxy: Number((totals.profit / terms.length).toFixed(2)),
    avgUncertainty: Number((totals.uncertainty / terms.length).toFixed(4)),
    topImpactTerms,
  }
}

function boundChange(next: number, current: number): number {
  const lower = current * (1 - MAX_ROAS_STEP_PCT)
  const upper = current * (1 + MAX_ROAS_STEP_PCT)
  return Math.min(Math.max(next, lower), upper)
}

function normalizeConfidence(spend: number, clicks: number, conversions: number): {
  clickConfidence: number
  conversionConfidence: number
  spendConfidence: number
  final: number
} {
  const clickConfidence = clamp(clicks / 500, 0, 1)
  const conversionConfidence = clamp(conversions / 20, 0, 1)
  const spendConfidence = clamp(spend / 1000, 0, 1)
  const final = clickConfidence * 0.35 + conversionConfidence * 0.45 + spendConfidence * 0.2
  return {
    clickConfidence: Number(clickConfidence.toFixed(4)),
    conversionConfidence: Number(conversionConfidence.toFixed(4)),
    spendConfidence: Number(spendConfidence.toFixed(4)),
    final: Number(final.toFixed(4)),
  }
}

export function buildRoasRecommendations(
  rows: LabelTierPerformanceRow[]
): RoasRecommendation[] {
  return rows
    .map((row) => {
      const currentTargetRoas: number = BASELINE_TARGET_ROAS[row.tier]
      const observedRoas = row.spend > 0 ? row.conversionValue / row.spend : 0
      const roasGapRatio = currentTargetRoas > 0 ? observedRoas / currentTargetRoas - 1 : 0
      const confidenceComponents = normalizeConfidence(row.spend, row.clicks, row.conversions)
      const confidence = confidenceComponents.final

      let direction: RoasRecommendation['direction'] = 'hold'
      let recommendedTargetRoas: number = currentTargetRoas
      let appliedStepPct = 0
      let guardrailStatus: RoasRecommendation['guardrailStatus'] = 'actionable'
      let rationale = 'Observed ROAS is near baseline target.'
      const insufficientSignals: string[] = []

      if (row.spend < MIN_SPEND_FOR_ACTION) insufficientSignals.push('low spend')
      if (row.clicks < MIN_CLICKS_FOR_ACTION) insufficientSignals.push('low clicks')
      if (row.conversions < MIN_CONVERSIONS_FOR_ACTION) insufficientSignals.push('low conversions')
      if (confidence < MIN_CONFIDENCE_FOR_ACTION) insufficientSignals.push('low confidence')

      if (insufficientSignals.length > 0) {
        guardrailStatus = 'insufficient_data'
        rationale = `Insufficient evidence for tROAS change (${insufficientSignals.join(', ')}).`
      } else if (Math.abs(roasGapRatio) <= NEAR_TARGET_BAND_PCT) {
        guardrailStatus = 'near_target_band'
        rationale = `Observed ROAS is within ±${Math.round(NEAR_TARGET_BAND_PCT * 100)}% of target; holding to reduce policy churn.`
      } else {
        const rawStepPct = clamp(-roasGapRatio * ADAPTIVE_ADJUSTMENT_GAIN, -MAX_ROAS_STEP_PCT, MAX_ROAS_STEP_PCT)
        appliedStepPct = Number(rawStepPct.toFixed(4))
        recommendedTargetRoas = boundChange(currentTargetRoas * (1 + rawStepPct), currentTargetRoas)
        direction = rawStepPct > 0 ? 'increase' : 'decrease'
        rationale =
          rawStepPct > 0
            ? 'Observed ROAS is below target. Increasing tROAS can tighten traffic quality with bounded risk.'
            : 'Observed ROAS is above target. Decreasing tROAS can unlock incremental volume with bounded risk.'
      }

      return {
        customLabel0: row.customLabel0,
        tier: row.tier,
        currentTargetRoas,
        observedRoas: Number(observedRoas.toFixed(4)),
        roasGapRatio: Number(roasGapRatio.toFixed(4)),
        recommendedTargetRoas: Number(recommendedTargetRoas.toFixed(4)),
        appliedStepPct,
        maxAllowedStepPct: MAX_ROAS_STEP_PCT,
        direction,
        guardrailStatus,
        confidence,
        confidenceComponents,
        rationale,
      }
    })
    .sort((a, b) => {
      const actionableA = a.guardrailStatus === 'actionable' ? 1 : 0
      const actionableB = b.guardrailStatus === 'actionable' ? 1 : 0
      if (actionableA !== actionableB) return actionableB - actionableA

      const weightedGapA = Math.abs(a.roasGapRatio) * a.confidence
      const weightedGapB = Math.abs(b.roasGapRatio) * b.confidence
      return weightedGapB - weightedGapA
    })
}
