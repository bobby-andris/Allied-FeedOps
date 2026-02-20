import type { NeedsDecisionTerm } from '@/lib/shopping-funnel/types'

const BASELINE_TARGET_ROAS = {
  HIGH: 3.6,
  MEDIUM: 3.1,
  LOW: 2.6,
} as const

export interface OpportunityCluster {
  clusterKey: string
  termCount: number
  totalImpressions: number
  totalClicks: number
  totalCost: number
  aggregateImpactScore: number
  averageCpc: number
  attractivenessScore: number
  topSearchTerms: string[]
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
  impactScore: number
  confidence: number
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

export interface RoasRecommendation {
  customLabel0: string
  tier: keyof typeof BASELINE_TARGET_ROAS
  currentTargetRoas: number
  observedRoas: number
  recommendedTargetRoas: number
  direction: 'increase' | 'decrease' | 'hold'
  confidence: number
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

export function buildOpportunityClusters(terms: NeedsDecisionTerm[]): OpportunityCluster[] {
  const byCluster = new Map<
    string,
    {
      terms: string[]
      impressions: number
      clicks: number
      cost: number
      impact: number
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
    }

    aggregate.terms.push(term.search_term)
    aggregate.impressions += metrics.impressions
    aggregate.clicks += metrics.clicks
    aggregate.cost += metrics.cost
    aggregate.impact += term.value_score?.impact_score ?? 0

    byCluster.set(key, aggregate)
  }

  const clusters: OpportunityCluster[] = []
  for (const [clusterKey, aggregate] of byCluster.entries()) {
    const termCount = aggregate.terms.length
    const averageCpc = aggregate.clicks > 0 ? aggregate.cost / aggregate.clicks : 0
    const lowCpcFactor = 1 / (1 + Math.max(averageCpc, 0))
    const attractivenessScore = (aggregate.impact / Math.max(termCount, 1)) * lowCpcFactor

    clusters.push({
      clusterKey,
      termCount,
      totalImpressions: aggregate.impressions,
      totalClicks: aggregate.clicks,
      totalCost: Number(aggregate.cost.toFixed(2)),
      aggregateImpactScore: Number(aggregate.impact.toFixed(2)),
      averageCpc: Number(averageCpc.toFixed(4)),
      attractivenessScore: Number(attractivenessScore.toFixed(4)),
      topSearchTerms: aggregate.terms.slice(0, 10),
    })
  }

  return clusters.sort((a, b) => b.attractivenessScore - a.attractivenessScore)
}

export function buildRecommendationQueue(
  terms: NeedsDecisionTerm[],
  limit = 100
): RecommendationQueueItem[] {
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

      return {
        searchTerm: term.search_term,
        impactScore: term.value_score?.impact_score ?? 0,
        confidence: term.recommendation?.confidence ?? 0,
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
    .sort((a, b) => b.impactScore - a.impactScore)

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
  const lower = current * 0.9
  const upper = current * 1.1
  return Math.min(Math.max(next, lower), upper)
}

function normalizeConfidence(clicks: number, conversions: number): number {
  const clickConfidence = Math.min(clicks / 500, 1)
  const conversionConfidence = Math.min(conversions / 20, 1)
  return Number((clickConfidence * 0.5 + conversionConfidence * 0.5).toFixed(4))
}

export function buildRoasRecommendations(
  rows: LabelTierPerformanceRow[]
): RoasRecommendation[] {
  return rows
    .map((row) => {
      const currentTargetRoas: number = BASELINE_TARGET_ROAS[row.tier]
      const observedRoas = row.spend > 0 ? row.conversionValue / row.spend : 0
      const confidence = normalizeConfidence(row.clicks, row.conversions)

      let direction: RoasRecommendation['direction'] = 'hold'
      let recommendedTargetRoas: number = currentTargetRoas
      let rationale = 'Observed ROAS is near baseline target.'

      if (observedRoas >= currentTargetRoas * 1.2 && row.conversions >= 10) {
        direction = 'decrease'
        recommendedTargetRoas = boundChange(currentTargetRoas * 0.95, currentTargetRoas)
        rationale = 'ROAS is materially above target. Lowering target can safely unlock incremental volume.'
      } else if (observedRoas <= currentTargetRoas * 0.8 && row.conversions >= 5) {
        direction = 'increase'
        recommendedTargetRoas = boundChange(currentTargetRoas * 1.05, currentTargetRoas)
        rationale = 'ROAS is materially below target. Raising target can reduce low-quality spend.'
      }

      return {
        customLabel0: row.customLabel0,
        tier: row.tier,
        currentTargetRoas,
        observedRoas: Number(observedRoas.toFixed(4)),
        recommendedTargetRoas: Number(recommendedTargetRoas.toFixed(4)),
        direction,
        confidence,
        rationale,
      }
    })
    .sort((a, b) => Math.abs(b.observedRoas - b.currentTargetRoas) - Math.abs(a.observedRoas - a.currentTargetRoas))
}
