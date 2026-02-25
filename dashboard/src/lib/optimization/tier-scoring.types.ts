import type { FunnelTier, QueryIntentFeatures } from '@/lib/shopping-funnel/types'

export type { FunnelTier, QueryIntentFeatures }

export type FallbackLevel = 'per_group' | 'global' | 'defaults'
export type ConfidenceLevel = 'High' | 'Medium' | 'Low'

export interface MetricDistribution {
  p25: number
  p50: number // median
  p75: number
  mean: number
  mad: number // median absolute deviation
  min: number
  max: number
}

export interface TierDistribution {
  tier: FunnelTier
  metrics: {
    roas: MetricDistribution
    cvr: MetricDistribution
    cpc: MetricDistribution
    ctr: MetricDistribution
  }
  sampleSize: number
  fallbackLevel: FallbackLevel
}

export interface BoundaryValue {
  value: number
  capped: boolean // was the shift capped at 15%?
  uncappedValue: number // what the data-driven value was before capping
  previousValue: number | null
}

export interface TierBoundaries {
  highFloor: BoundaryValue // MEDIUM p25 — above this = HIGH candidate
  lowCeiling: BoundaryValue // MEDIUM p75 — below this = LOW candidate
  metric: 'roas' // primary metric for boundaries
}

export interface GroupDistributions {
  customLabel0: string
  tiers: Record<FunnelTier, TierDistribution>
  boundaries: TierBoundaries
  totalTerms: number
  scoredTerms: number
  insufficientTiers: FunnelTier[] // tiers with <5 non-zero-metric terms
}

export interface TermScore {
  searchTerm: string
  customLabel0: string
  currentTier: FunnelTier
  recommendedTier: FunnelTier
  isMisplaced: boolean
  tierFitScores: Record<FunnelTier, number> // robust z-score per tier
  confidence: ConfidenceResult
  impact: ImpactRange | null // null if not misplaced
  fallbackLevel: FallbackLevel
  verdict: string // plain English explanation
  peerContext: string // e.g., "ranks in top 15% of Towel Bar terms"
}

export interface ConfidenceResult {
  score: number // 0-1 combined score
  level: ConfidenceLevel
  factors: ConfidenceFactors
}

export interface ConfidenceFactors {
  dataVolume: number // 0-1, weight 30%
  consistency: number // 0-1, weight 30%
  significance: number // 0-1, weight 20%
  intentAlignment: number // 0-1, weight 20%
}

export interface ImpactRange {
  low: number // conservative (p25 scenario)
  mid: number // expected (p50 scenario)
  high: number // optimistic (p75 scenario)
  currency: 'USD'
  period: 'monthly'
}

export interface ScoringResult {
  distributions: Map<string, GroupDistributions>
  scores: TermScore[]
  globalFallback: Record<FunnelTier, TierDistribution>
  computedAt: string
  totalGroups: number
  totalTermsScored: number
  totalMisplaced: number
  totalImpact: ImpactRange
  heroCallout: string // "23 terms may be in the wrong tier — $2.4K/mo potential impact"
}
