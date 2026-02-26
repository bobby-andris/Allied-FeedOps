import type { FunnelTier, QueryIntentFeatures } from '@/lib/shopping-funnel/types'

export type { FunnelTier, QueryIntentFeatures }

export type FallbackLevel = 'per_group' | 'global' | 'defaults'
export type ConfidenceLevel = 'High' | 'Medium' | 'Low'

/** Prescriptive action: what bidding treatment does this term need? */
export type RecommendedAction = 'promote' | 'demote' | 'block' | 'observe'

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

/** Behavioral intent signals from Google Ads data (Domain B of dual-domain scoring) */
export interface BehavioralSignals {
  rCTR: number              // term CTR / tier median CTR (0+, >1 = above average)
  cpcCeilingRatio: number   // avg CPC / tier median CPC (0+, near/above 1 = hitting ceiling)
  microConversionDelta: number // all_conversions - conversions (0+)
  rCTRScore: number         // normalized 0-1: min(rCTR / 3.0, 1.0)
  cpcCeilingScore: number   // normalized 0-1: min(ratio / 1.0, 1.0)
  microConvScore: number    // normalized 0-1: min(delta / 2.0, 1.0)
  costVelocityScore: number // normalized 0-1: spend velocity relative to tier median
  composite: number         // weighted behavioral intent score 0-1
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
  targetTier?: FunnelTier // the tier determineAction wants to move to
  totalImpressions?: number // needed for under_invested fix in Plan 02
  behavioralSignals?: BehavioralSignals // Domain B: behavioral intent from Google Ads data
  intentScore?: IntentScoreBreakdown // Unified intent score combining feed alignment + behavioral
  trigger?: string // which trigger fired in determineAction (wasted_spend, demote_underperform, promote_conversion, promote_intent, under_invested, observe)
}

/** Unified intent score combining Domain A (feed alignment) + Domain B (behavioral signals) */
export interface IntentScoreBreakdown {
  feedAlignmentScore: number  // 0-1 from Cloud Run /score-intent
  behavioralScore: number     // 0-1 from computeBehavioralIntent
  unifiedScore: number        // 0.55 * feed + 0.45 * behavioral
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
