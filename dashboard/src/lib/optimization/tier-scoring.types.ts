import type { FunnelTier, QueryIntentFeatures } from '@/lib/shopping-funnel/types'

export type { FunnelTier, QueryIntentFeatures }

export type FallbackLevel = 'per_group' | 'global' | 'defaults'
export type ConfidenceLevel = 'High' | 'Medium' | 'Low'

/** Prescriptive action: what bidding treatment does this term need? */
export type RecommendedAction = 'promote' | 'constrain' | 'block' | 'observe'

export interface CalibrationConfig {
  /** Minimum fit score delta between current and recommended tier to flag as opportunity */
  minFitScoreDelta: number
  /** Minimum confidence score to flag a term */
  minConfidence: number
  /** Minimum monthly impressions for a term to be scoreable */
  minImpressions: number
  /** AOV for impact estimation */
  averageOrderValue: number
}

export const DEFAULT_CALIBRATION: CalibrationConfig = {
  minFitScoreDelta: 0.3,
  minConfidence: 0.40,
  minImpressions: 50,
  averageOrderValue: 85,
}

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
  fitScoreDelta: number // delta between recommended and current fit scores
  dataConfirmed: boolean // true when data agrees with gut-assigned tier
  confidence: ConfidenceResult
  impact: ImpactRange | null // null if not misplaced
  fallbackLevel: FallbackLevel
  totalConversions: number // raw conversions for wasted spend detection (LEAK-03)
  totalCostMicros: number // raw cost for wasted spend detection (LEAK-03)
  actualRoas: number // actual ROAS = conversions_value / spend
  verdict: string // plain English explanation
  peerContext: string // e.g., "ranks in top 15% of Towel Bar terms"
  recommendedAction?: RecommendedAction // what to do (replaces isMisplaced/recommendedTier as primary output)
  actionReason?: string // why (prescriptive explanation)
  totalImpressions?: number // needed for under_invested fix in Plan 02
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
  direction: 'upward' | 'downward' | 'lateral' // movement direction for Phase 34 wasted spend
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
