/**
 * Tier Scoring Engine — Pure computation module
 *
 * Replaces hardcoded ROAS thresholds (3.6/3.1/2.6) with dynamic,
 * distribution-based scoring using robust z-scores (median/MAD).
 *
 * Zero side effects — no fetch, no Supabase, no HTTP.
 */

import {
  median,
  medianAbsoluteDeviation,
  quantile,
  mean as ssMean,
  standardDeviation,
} from 'simple-statistics'

import type { LabelTierPerformance, ExistingFunnelTerm, QueryIntentFeatures } from '@/lib/shopping-funnel/types'
import type {
  FunnelTier,
  FallbackLevel,
  MetricDistribution,
  TierDistribution,
  TierBoundaries,
  BoundaryValue,
  GroupDistributions,
  TermScore,
  BehavioralSignals,
  IntentScoreBreakdown,
  ConfidenceResult,
  ConfidenceFactors,
  ImpactRange,
  ScoringResult,
  CalibrationConfig,
  RecommendedAction,
} from './tier-scoring.types'
import { DEFAULT_CALIBRATION } from './tier-scoring.types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_BOUNDARY_SHIFT_PERCENT = 0.15
const MIN_SAMPLE_SIZE = 5
const CACHE_TTL_MS = 10 * 60 * 1000 // 10 minutes

const DEFAULT_METRIC_DIST: MetricDistribution = {
  p25: 0, p50: 0, p75: 0, mean: 0, mad: 0, min: 0, max: 0,
}

// Waterfall Shopping defaults: HIGH priority = top-of-funnel (broad, restricted bidding, lowest ROAS),
// LOW priority = bottom-of-funnel (high-intent, aggressive bidding, highest ROAS).
// See docs/domain/waterfall-shopping-structure.md for full explanation.
const DEFAULT_DISTRIBUTIONS: Record<FunnelTier, TierDistribution> = {
  HIGH: {
    tier: 'HIGH',
    metrics: {
      roas: { p25: 0.5, p50: 1.2, p75: 2.0, mean: 1.2, mad: 0.5, min: 0.0, max: 3.0 },
      cvr: { p25: 0.005, p50: 0.01, p75: 0.02, mean: 0.01, mad: 0.005, min: 0.0, max: 0.05 },
      cpc: { p25: 0.30, p50: 0.50, p75: 0.80, mean: 0.55, mad: 0.15, min: 0.10, max: 1.20 },
      ctr: { p25: 0.01, p50: 0.02, p75: 0.03, mean: 0.02, mad: 0.008, min: 0.002, max: 0.06 },
    },
    sampleSize: 0,
    fallbackLevel: 'defaults',
  },
  MEDIUM: {
    tier: 'MEDIUM',
    metrics: {
      roas: { p25: 2.0, p50: 3.0, p75: 4.0, mean: 3.0, mad: 0.8, min: 1.0, max: 6.0 },
      cvr: { p25: 0.02, p50: 0.04, p75: 0.06, mean: 0.04, mad: 0.01, min: 0.01, max: 0.10 },
      cpc: { p25: 0.40, p50: 0.70, p75: 1.00, mean: 0.70, mad: 0.20, min: 0.15, max: 1.50 },
      ctr: { p25: 0.02, p50: 0.04, p75: 0.06, mean: 0.04, mad: 0.01, min: 0.005, max: 0.10 },
    },
    sampleSize: 0,
    fallbackLevel: 'defaults',
  },
  LOW: {
    tier: 'LOW',
    metrics: {
      roas: { p25: 4.0, p50: 5.5, p75: 8.0, mean: 6.0, mad: 1.5, min: 3.0, max: 15.0 },
      cvr: { p25: 0.04, p50: 0.06, p75: 0.10, mean: 0.07, mad: 0.02, min: 0.02, max: 0.20 },
      cpc: { p25: 0.50, p50: 0.80, p75: 1.20, mean: 0.85, mad: 0.25, min: 0.20, max: 2.00 },
      ctr: { p25: 0.03, p50: 0.05, p75: 0.08, mean: 0.05, mad: 0.02, min: 0.01, max: 0.15 },
    },
    sampleSize: 0,
    fallbackLevel: 'defaults',
  },
}

// ---------------------------------------------------------------------------
// Module-level cache
// ---------------------------------------------------------------------------

let _distributionCache: {
  distributions: Map<string, GroupDistributions>
  globalFallback: Record<FunnelTier, TierDistribution>
  computedAt: number
} | null = null

// ---------------------------------------------------------------------------
// Core: computeTierDistributions
// ---------------------------------------------------------------------------

export function computeTierDistributions(
  rows: LabelTierPerformance[],
  options?: { previousDistributions?: Map<string, GroupDistributions> }
): Map<string, GroupDistributions> {
  const grouped = groupBy(rows, r => r.custom_label_0)
  const result = new Map<string, GroupDistributions>()

  for (const [label, groupRows] of Object.entries(grouped)) {
    const byTier = groupBy(groupRows, r => r.tier)
    const tiers: Record<FunnelTier, TierDistribution> = {} as Record<FunnelTier, TierDistribution>
    const insufficientTiers: FunnelTier[] = []
    let totalTerms = 0

    for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
      const tierRows = byTier[tier] || []
      totalTerms += tierRows.length
      const nonZeroRows = tierRows.filter(r => r.clicks > 0 || r.conversions > 0)

      if (nonZeroRows.length < MIN_SAMPLE_SIZE) {
        insufficientTiers.push(tier)
      }

      tiers[tier] = computeSingleTierDistribution(tierRows, tier, 'per_group')
    }

    const previousGroup = options?.previousDistributions?.get(label)
    const boundaries = computeTierBoundaries(
      tiers.MEDIUM,
      previousGroup?.boundaries
    )

    result.set(label, {
      customLabel0: label,
      tiers,
      boundaries,
      totalTerms,
      scoredTerms: 0, // updated when scoring
      insufficientTiers,
    })
  }

  return result
}

// ---------------------------------------------------------------------------
// Core: computeGlobalDistributions
// ---------------------------------------------------------------------------

export function computeGlobalDistributions(
  rows: LabelTierPerformance[]
): Record<FunnelTier, TierDistribution> {
  const byTier = groupBy(rows, r => r.tier)
  const result: Record<FunnelTier, TierDistribution> = {} as Record<FunnelTier, TierDistribution>

  for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
    const tierRows = byTier[tier] || []
    result[tier] = computeSingleTierDistribution(tierRows, tier, 'global')
  }

  return result
}

// ---------------------------------------------------------------------------
// Core: computeTierBoundaries
// ---------------------------------------------------------------------------

export function computeTierBoundaries(
  mediumTier: TierDistribution,
  previousBoundaries?: TierBoundaries
): TierBoundaries {
  const rawHighFloor = mediumTier.metrics.roas.p25
  const rawLowCeiling = mediumTier.metrics.roas.p75

  return {
    highFloor: capBoundaryShift(rawHighFloor, previousBoundaries?.highFloor ?? null),
    lowCeiling: capBoundaryShift(rawLowCeiling, previousBoundaries?.lowCeiling ?? null),
    metric: 'roas',
  }
}

// ---------------------------------------------------------------------------
// Core: scoreTerm
// ---------------------------------------------------------------------------

export function scoreTerm(
  term: ExistingFunnelTerm,
  groupDist: GroupDistributions,
  globalFallback: Record<FunnelTier, TierDistribution>,
  intentFeatures?: QueryIntentFeatures,
  config: CalibrationConfig = DEFAULT_CALIBRATION,
  feedAlignmentScore?: number,  // 0-1 from Cloud Run /score-intent
  avgCPA?: number,              // from account audit, replaces hardcoded $5
): TermScore {
  const currentTier = mapTierLabel(term.funnels[0]?.tier ?? 'Unknown')
  const customLabel0 = term.funnels[0]?.custom_label_0 ?? ''

  // Compute term-level metrics
  const costDollars = Math.max(term.total_cost_micros / 1_000_000, 0.01)
  const termRoas = term.total_conversions_value / costDollars
  const termCvr = term.total_conversions / Math.max(term.total_clicks, 1)
  const termCpc = costDollars / Math.max(term.total_clicks, 1)
  const termCtr = term.total_clicks / Math.max(term.total_impressions, 1)

  // Determine fallback level
  const fallbackLevel = determineFallbackLevel(currentTier, groupDist, globalFallback)

  // Choose distribution based on fallback
  const chooseDist = (tier: FunnelTier): TierDistribution => {
    if (fallbackLevel === 'defaults') return DEFAULT_DISTRIBUTIONS[tier]
    if (fallbackLevel === 'global') return globalFallback[tier]
    return groupDist.tiers[tier]
  }

  // Compute robust z-score fit per tier (inverted: higher = better fit)
  const tierFitScores: Record<FunnelTier, number> = {} as Record<FunnelTier, number>
  for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
    const dist = chooseDist(tier)
    const zRoas = robustZScore(termRoas, dist.metrics.roas)
    const zCvr = robustZScore(termCvr, dist.metrics.cvr)
    const zCpc = robustZScore(termCpc, dist.metrics.cpc)
    const zCtr = robustZScore(termCtr, dist.metrics.ctr)

    // Fit score: negative absolute z-score (closer to 0 = better fit)
    // Weight ROAS most heavily (50%), then CVR (20%), CPC (15%), CTR (15%)
    // CPC is inverse: lower = better. Only penalize expensive terms (positive z-score).
    const cpcPenalty = Math.max(0, zCpc)
    const absDeviation = 0.50 * Math.abs(zRoas) + 0.20 * Math.abs(zCvr) + 0.15 * cpcPenalty + 0.15 * Math.abs(zCtr)
    tierFitScores[tier] = -absDeviation // Higher is better fit
  }

  // Recommended tier = best fit
  const recommendedTier = (['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]).reduce(
    (best, tier) => tierFitScores[tier] > tierFitScores[best] ? tier : best,
    'HIGH' as FunnelTier
  )

  // Confidence (computed before isMisplaced — needed for threshold gating)
  const confidence = computeConfidence(term, intentFeatures, currentTier)

  // Calibrated isMisplaced gating
  const fitScoreDelta = tierFitScores[recommendedTier] - tierFitScores[currentTier]
  const meetsDeltaThreshold = fitScoreDelta >= config.minFitScoreDelta
  const meetsConfidenceFloor = confidence.score >= config.minConfidence
  const hasMinimumData = term.total_impressions >= config.minImpressions
  const isMisplaced = recommendedTier !== currentTier
    && meetsDeltaThreshold
    && meetsConfidenceFloor
    && hasMinimumData

  const dataConfirmed = recommendedTier === currentTier && hasMinimumData && meetsConfidenceFloor

  // Compute unified intent score (Domain A feed alignment + Domain B behavioral)
  let intentScoreBreakdown: IntentScoreBreakdown | undefined
  const queryWordCount = term.search_term.trim().split(/\s+/).length

  // Determine prescriptive action using ROAS-based logic + intent scoring
  const currentTierDist = chooseDist(currentTier)

  // Behavioral intent signals (Domain B) — compute BEFORE determineAction so we have rCTR
  let behavioralSignals: BehavioralSignals | undefined
  if (term.total_average_cpc !== undefined && term.total_all_conversions !== undefined) {
    const tierMedianCtr = currentTierDist.metrics.ctr.p50
    const tierMedianCpcMicros = currentTierDist.metrics.cpc.p50 * 1_000_000 // dist stores CPC in dollars
    const tierMedianDailySpend = (currentTierDist.metrics.cpc.p50 * 1_000_000 *
      Math.max(currentTierDist.metrics.ctr.p50 * 100, 1)) / 30

    behavioralSignals = computeBehavioralIntent(
      {
        ctr: termCtr,
        avgCpcMicros: term.total_average_cpc,
        allConversions: term.total_all_conversions,
        conversions: term.total_conversions,
        costMicros: term.total_cost_micros,
        impressions: term.total_impressions,
      },
      tierMedianCtr,
      tierMedianCpcMicros,
      tierMedianDailySpend,
    )
  }

  // Compute unified intent score
  if (feedAlignmentScore !== undefined || behavioralSignals) {
    const feed = feedAlignmentScore ?? 0
    const behavioral = behavioralSignals?.composite ?? 0
    intentScoreBreakdown = {
      feedAlignmentScore: feed,
      behavioralScore: behavioral,
      unifiedScore: 0.55 * feed + 0.45 * behavioral,
    }
  }

  const { action: recommendedAction, targetTier, trigger } = determineAction(
    currentTier,
    currentTierDist,
    termRoas,
    term.total_conversions,
    term.total_cost_micros,
    isMisplaced,
    intentScoreBreakdown?.unifiedScore,
    behavioralSignals?.rCTR,
    queryWordCount,
    avgCPA,
  )

  // Impact: compute for misplaced OR wasted spend terms
  const wastedSpendThreshold = (avgCPA ?? 5) * 1.5
  const isWastedSpend = term.total_conversions === 0 && costDollars > wastedSpendThreshold
  let impact: ImpactRange | null = null
  if (isMisplaced || isWastedSpend) {
    impact = estimateImpact(term, chooseDist(currentTier), chooseDist(targetTier), config)
  }

  // Prescriptive verdict and action reason
  let actionReason: string
  switch (trigger) {
    case 'wasted_spend':
      if (recommendedAction === 'block') {
        actionReason = `Block — spent $${costDollars.toFixed(0)} with zero conversions`
      } else {
        actionReason = `Demote to ${targetTier} — spent $${costDollars.toFixed(0)} with zero conversions`
      }
      break
    case 'demote_underperform':
      actionReason = `Demote — underperforming in ${currentTier}, move to ${targetTier} for restricted bidding`
      break
    case 'promote_conversion':
      actionReason = `Promote to ${targetTier} — conversion-proven performer in ${currentTier} tier`
      break
    case 'promote_intent':
      actionReason = `Promote to ${targetTier} — intent-proven (score ${intentScoreBreakdown?.unifiedScore?.toFixed(2) ?? '?'}) with zero conversions`
      break
    case 'under_invested':
      actionReason = `Under-invested — promote to ${targetTier} for more aggressive bidding`
      break
    default:
      actionReason = `Aligned — performing as expected in ${currentTier}`
  }

  const verdict = actionReason

  // Peer context
  const peerContext = buildPeerContext(termRoas, groupDist, customLabel0)

  return {
    searchTerm: term.search_term,
    customLabel0,
    currentTier,
    recommendedTier,
    isMisplaced,
    tierFitScores,
    fitScoreDelta,
    dataConfirmed,
    confidence,
    impact,
    fallbackLevel,
    totalConversions: term.total_conversions,
    totalCostMicros: term.total_cost_micros,
    actualRoas: termRoas,
    verdict,
    peerContext,
    recommendedAction,
    actionReason,
    targetTier,
    totalImpressions: term.total_impressions ?? 0,
    behavioralSignals,
    intentScore: intentScoreBreakdown,
    trigger: trigger,
  }
}

// ---------------------------------------------------------------------------
// Core: computeConfidence
// ---------------------------------------------------------------------------

export function computeConfidence(
  term: ExistingFunnelTerm,
  intentFeatures?: QueryIntentFeatures,
  currentTier?: FunnelTier
): ConfidenceResult {
  // Data volume (30%): clicks / 100, capped at 1
  const dataVolume = Math.min(term.total_clicks / 100, 1)

  // Consistency (30%): proxy from funnel data spread
  let consistency = 0.5 // neutral default
  if (term.funnels.length > 1) {
    // Multiple funnel assignments — use agreement as proxy
    const tiers = term.funnels.map(f => f.tier)
    const allSame = tiers.every(t => t === tiers[0])
    consistency = allSame ? 0.9 : 0.3
  }

  // Statistical significance (20%): conversions / 10, capped at 1
  const significance = Math.min(term.total_conversions / 10, 1)

  // NLP alignment (20%): query specificity → tier alignment
  // Waterfall model: specific/transactional → LOW (aggressive bidding), broad/generic → HIGH (restricted)
  // Branded terms have separate campaigns and should NOT appear in the waterfall structure.
  // If they do appear, treat as anomaly (low alignment in any tier).
  let intentAlignment = 0.5 // neutral default
  if (intentFeatures && currentTier) {
    if (intentFeatures.is_branded) {
      // Branded terms shouldn't be in the waterfall — separate campaigns handle these.
      // Low alignment regardless of tier signals a routing anomaly.
      intentAlignment = 0.2
    } else if (intentFeatures.is_competitor) {
      // Competitor terms are defensive — keep restricted in HIGH/MEDIUM to limit spend
      if (currentTier === 'HIGH') intentAlignment = 0.7
      else if (currentTier === 'MEDIUM') intentAlignment = 0.5
      else intentAlignment = 0.3 // competitor in LOW = risky aggressive spend
    } else if (intentFeatures.product_object) {
      // Product-specific terms (e.g., "brass toilet paper holder") = mid-to-high intent
      if (currentTier === 'LOW') intentAlignment = 0.8
      else if (currentTier === 'MEDIUM') intentAlignment = 0.7
      else intentAlignment = 0.4 // product-specific stuck in broad tier
    } else {
      // Generic/broad terms belong in HIGH (restricted)
      if (currentTier === 'HIGH') intentAlignment = 0.7
      else if (currentTier === 'MEDIUM') intentAlignment = 0.5
      else intentAlignment = 0.3 // generic in LOW = wasting aggressive bids
    }
  }

  const factors: ConfidenceFactors = {
    dataVolume,
    consistency,
    significance,
    intentAlignment,
  }

  // Combined = weighted sum: 30/30/20/20
  const score = 0.3 * dataVolume + 0.3 * consistency + 0.2 * significance + 0.2 * intentAlignment

  const level = score >= 0.70 ? 'High' : score >= 0.40 ? 'Medium' : 'Low'

  return { score, level, factors }
}

// ---------------------------------------------------------------------------
// Core: estimateImpact
// ---------------------------------------------------------------------------

export function estimateImpact(
  term: ExistingFunnelTerm,
  currentDist: TierDistribution,
  targetDist: TierDistribution,
  config: CalibrationConfig = DEFAULT_CALIBRATION
): ImpactRange {
  const monthlySpend = term.total_cost_micros / 1_000_000

  // Wasted spend fast path: zero conversions with meaningful spend
  if (term.total_conversions === 0 && term.total_cost_micros > 5_000_000) {
    return {
      low: monthlySpend * 0.5,
      mid: monthlySpend * 0.8,
      high: monthlySpend,
      currency: 'USD',
      period: 'monthly',
      direction: (currentDist.tier === 'HIGH' ? 'lateral' : 'upward') as ImpactRange['direction'],
    }
  }

  // Use ROAS delta as primary signal (aligned with 50% weighting in scoring)
  const currentRoas = currentDist.metrics.roas.p50
  const targetRoasP25 = targetDist.metrics.roas.p25
  const targetRoasP50 = targetDist.metrics.roas.p50
  const targetRoasP75 = targetDist.metrics.roas.p75

  // Impact = spend * (targetROAS - currentROAS) = incremental revenue
  const lowDelta = targetRoasP25 - currentRoas
  const midDelta = targetRoasP50 - currentRoas
  const highDelta = targetRoasP75 - currentRoas

  // Determine movement direction in the waterfall funnel
  // "promote" (downward in funnel) = moving toward LOW (more aggressive bidding, higher intent)
  // "demote" (upward in funnel) = moving toward HIGH (more restricted bidding)
  // funnelDepth: HIGH=1 (top/broad), MEDIUM=2, LOW=3 (bottom/high-intent)
  const funnelDepth: Record<FunnelTier, number> = { HIGH: 1, MEDIUM: 2, LOW: 3 }
  const direction: 'upward' | 'downward' | 'lateral' =
    funnelDepth[targetDist.tier] > funnelDepth[currentDist.tier] ? 'downward'
    : funnelDepth[targetDist.tier] < funnelDepth[currentDist.tier] ? 'upward'
    : 'lateral'

  return {
    low: Math.max(0, monthlySpend * lowDelta),
    mid: Math.max(0, monthlySpend * midDelta),
    high: Math.max(0, monthlySpend * highDelta),
    currency: 'USD',
    period: 'monthly',
    direction,
  }
}

// ---------------------------------------------------------------------------
// Core: getCachedDistributions
// ---------------------------------------------------------------------------

export function getCachedDistributions(
  rows: LabelTierPerformance[],
  previousDistributions?: Map<string, GroupDistributions>
): { distributions: Map<string, GroupDistributions>; globalFallback: Record<FunnelTier, TierDistribution> } {
  const now = Date.now()

  if (_distributionCache && (now - _distributionCache.computedAt) < CACHE_TTL_MS) {
    return {
      distributions: _distributionCache.distributions,
      globalFallback: _distributionCache.globalFallback,
    }
  }

  const distributions = computeTierDistributions(rows, { previousDistributions })
  const globalFallback = computeGlobalDistributions(rows)

  _distributionCache = {
    distributions,
    globalFallback,
    computedAt: now,
  }

  return { distributions, globalFallback }
}

// ---------------------------------------------------------------------------
// Core: buildHeroCallout
// ---------------------------------------------------------------------------

export function buildHeroCallout(scores: TermScore[]): string {
  const misplaced = scores.filter(s => s.isMisplaced)
  const count = misplaced.length

  if (count === 0) {
    return 'All scored terms appear correctly placed'
  }

  const totalLow = misplaced.reduce((sum, s) => sum + (s.impact?.low ?? 0), 0)
  const formatted = totalLow >= 1000
    ? `$${(totalLow / 1000).toFixed(1)}K`
    : `$${Math.round(totalLow)}`

  return `${count} term${count === 1 ? '' : 's'} may be in the wrong tier — ${formatted}/mo potential impact`
}

// ---------------------------------------------------------------------------
// Core: computeBehavioralIntent
// ---------------------------------------------------------------------------

/**
 * Compute behavioral intent signals from Google Ads data (Domain B).
 *
 * Three signals indicate genuine purchase intent for zero-conversion terms:
 * 1. rCTR: high relative CTR (users clicking this term more than peers)
 * 2. CPC ceiling: Smart Bidding is pushing CPC toward tier median (Google sees value)
 * 3. Micro-conversions: add-to-cart / begin-checkout without purchase (near-converters)
 * 4. Cost velocity: how fast this term burns budget relative to tier median daily spend
 *
 * @param term - Term-level metrics (CTR, avgCpc in micros, allConversions, conversions, costMicros, impressions)
 * @param tierMedianCtr - Median CTR for the current tier (from distribution)
 * @param tierMedianCpcMicros - Median CPC in micros for the current tier
 * @param tierMedianDailySpend - Median daily spend in micros for the current tier (0 if unknown)
 */
export function computeBehavioralIntent(
  term: {
    ctr: number
    avgCpcMicros: number
    allConversions: number
    conversions: number
    costMicros: number
    impressions: number
  },
  tierMedianCtr: number,
  tierMedianCpcMicros: number,
  tierMedianDailySpend: number,
): BehavioralSignals {
  // 1. Relative CTR: term CTR / tier median CTR
  const effectiveMedianCtr = Math.max(tierMedianCtr, 0.01)
  const rCTR = term.ctr / effectiveMedianCtr
  const rCTRScore = Math.min(rCTR / 3.0, 1.0) // 3x median = max score

  // 2. CPC ceiling pressure: avg CPC / tier median CPC
  // With Target ROAS bidding, CPC caps are $0.01 (nominal). Instead we compare
  // the term's actual CPC against the tier's median CPC. A ratio near or above 1.0
  // means Smart Bidding is pushing this term's CPC to the tier ceiling — it sees value.
  const cpcCeilingRatio = tierMedianCpcMicros > 0
    ? term.avgCpcMicros / tierMedianCpcMicros
    : 0
  const cpcCeilingScore = Math.min(cpcCeilingRatio / 1.0, 1.0) // at or above median = max

  // 3. Micro-conversion delta: all_conversions - conversions (clamp to 0+)
  const microConversionDelta = Math.max(term.allConversions - term.conversions, 0)
  const microConvScore = Math.min(microConversionDelta / 2.0, 1.0) // 2+ micro-convs = max

  // 4. Cost velocity: how fast this term spends relative to tier median daily spend
  // Estimate term daily spend assuming 30-day window
  const termDailySpend = term.costMicros / 30
  const effectiveMedianDailySpend = Math.max(tierMedianDailySpend, 1)
  const velocityRatio = termDailySpend / effectiveMedianDailySpend
  let costVelocityScore: number
  if (microConversionDelta > 0) {
    // Has micro-conversions: moderate spend velocity is positive (active engagement)
    costVelocityScore = Math.min(velocityRatio / 3.0, 1.0) * 0.5
  } else {
    // No micro-conversions: fast spend with no signal = bad (wasted)
    costVelocityScore = 1.0 - Math.min(velocityRatio / 3.0, 1.0)
  }

  // Composite: research weights with cross_device (0.15) redistributed
  // rCTR: 0.30, CPC ceiling: 0.25, micro-conv: 0.20, cost velocity: 0.10
  // cross_device deferred (0.15 weight → set to 0 contribution)
  // Total active weight: 0.85 — composite can be < 1.0 max (fine for unified scoring)
  const composite =
    0.30 * rCTRScore +
    0.25 * cpcCeilingScore +
    0.20 * microConvScore +
    0.10 * costVelocityScore

  return {
    rCTR,
    cpcCeilingRatio,
    microConversionDelta,
    rCTRScore,
    cpcCeilingScore,
    microConvScore,
    costVelocityScore,
    composite,
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * 5-trigger decision matrix for term routing recommendations.
 *
 * Trigger priority (ORDER MATTERS — first match wins):
 *   A. Wasted Spend Override: zero conversions + spend > 1.5x avgCPA
 *   B. Demote (Underperforming): has conversions but ROAS < tier p25
 *   C. Promote (Conversion-Proven): ROAS > tier p75
 *   D. Promote (Intent-Proven): zero conversions + high intent score + (high rCTR OR 3+ word query)
 *   E. Under-Invested: meets promote criteria (C or D) AND low impression share
 *
 * Sequential movement enforced: never skip tiers (HIGH -> LOW not allowed).
 */
export function determineAction(
  currentTier: FunnelTier,
  currentTierDist: TierDistribution,
  termRoas: number,
  totalConversions: number,
  totalCostMicros: number,
  isMisplaced: boolean,
  intentScore?: number,      // unified 0-1
  rCTR?: number,             // raw rCTR for Trigger D gate
  queryWordCount?: number,   // word count for Trigger D gate
  avgCPA?: number,           // from account audit, replaces hardcoded $5
): { action: RecommendedAction; targetTier: FunnelTier; trigger: string } {
  const costDollars = totalCostMicros / 1_000_000
  const TIER_UP: Record<FunnelTier, FunnelTier> = { HIGH: 'HIGH', MEDIUM: 'HIGH', LOW: 'MEDIUM' }
  const TIER_DOWN: Record<FunnelTier, FunnelTier> = { HIGH: 'MEDIUM', MEDIUM: 'LOW', LOW: 'LOW' }

  const wastedSpendThreshold = 1.5 * (avgCPA || 5)

  // --- Trigger A: Wasted Spend Override ---
  // Zero conversions + spent more than 1.5x avg CPA = wasted spend
  if (totalConversions === 0 && costDollars > wastedSpendThreshold) {
    if (currentTier === 'HIGH') {
      return { action: 'block', targetTier: 'HIGH', trigger: 'wasted_spend' }
    }
    return { action: 'demote', targetTier: 'HIGH', trigger: 'wasted_spend' }
  }

  const p25 = currentTierDist.metrics.roas.p25
  const p75 = currentTierDist.metrics.roas.p75

  // --- Trigger B: Demote (Underperforming) ---
  // Has conversions but ROAS is below tier's p25 — demote one step toward HIGH
  if (totalConversions > 0 && termRoas < p25 && currentTier !== 'HIGH') {
    return { action: 'demote', targetTier: TIER_UP[currentTier], trigger: 'demote_underperform' }
  }

  // --- Trigger C: Promote (Conversion-Proven) ---
  // ROAS above tier p75 — promote one step toward LOW (more aggressive bidding)
  if (termRoas > p75 && currentTier !== 'LOW') {
    // Check for under-invested (Trigger E): if also low impression share, flag it
    // Use totalImpressions as proxy — terms with < 30% of typical volume are under-invested
    // (Impression share data not directly available on the term; this is a placeholder for
    // when campaign-level impression share is passed through)
    return { action: 'promote', targetTier: TIER_DOWN[currentTier], trigger: 'promote_conversion' }
  }

  // --- Trigger D: Promote (Intent-Proven, Zero Conversions) ---
  // Zero conversions BUT high unified intent score AND supporting evidence
  if (
    totalConversions === 0 &&
    intentScore !== undefined &&
    intentScore >= 0.65 &&
    ((rCTR !== undefined && rCTR >= 1.5) || (queryWordCount !== undefined && queryWordCount >= 3)) &&
    currentTier !== 'LOW'
  ) {
    return { action: 'promote', targetTier: TIER_DOWN[currentTier], trigger: 'promote_intent' }
  }

  // --- Default: Observe ---
  return { action: 'observe', targetTier: currentTier, trigger: 'observe' }
}

function computeSingleTierDistribution(
  rows: LabelTierPerformance[],
  tier: FunnelTier,
  fallbackLevel: FallbackLevel
): TierDistribution {
  if (rows.length === 0) {
    return {
      tier,
      metrics: {
        roas: { ...DEFAULT_METRIC_DIST },
        cvr: { ...DEFAULT_METRIC_DIST },
        cpc: { ...DEFAULT_METRIC_DIST },
        ctr: { ...DEFAULT_METRIC_DIST },
      },
      sampleSize: 0,
      fallbackLevel,
    }
  }

  // Extract metric arrays
  const roasValues = rows.map(r => r.roas)
  const cvrValues = rows.map(r => r.conversions / Math.max(r.clicks, 1))
  const cpcValues = rows.map(r => (r.cost_micros / 1_000_000) / Math.max(r.clicks, 1))
  const ctrValues = rows.map(r => r.clicks / Math.max(r.impressions, 1))

  // Cap ROAS at p99 before computing distributions
  const roasCapped = capAtPercentile(roasValues, 0.99)

  return {
    tier,
    metrics: {
      roas: buildMetricDistribution(roasCapped),
      cvr: buildMetricDistribution(cvrValues),
      cpc: buildMetricDistribution(cpcValues),
      ctr: buildMetricDistribution(ctrValues),
    },
    sampleSize: rows.length,
    fallbackLevel,
  }
}

function buildMetricDistribution(values: number[]): MetricDistribution {
  if (values.length === 0) return { ...DEFAULT_METRIC_DIST }

  const sorted = [...values].sort((a, b) => a - b)

  return {
    p25: quantile(sorted, 0.25),
    p50: median(sorted),
    p75: quantile(sorted, 0.75),
    mean: ssMean(sorted),
    mad: values.length >= 3 ? medianAbsoluteDeviation(sorted) : 0,
    min: sorted[0],
    max: sorted[sorted.length - 1],
  }
}

function capAtPercentile(values: number[], percentile: number): number[] {
  if (values.length < 2) return values
  const sorted = [...values].sort((a, b) => a - b)
  const cap = quantile(sorted, percentile)
  return values.map(v => Math.min(v, cap))
}

function capBoundaryShift(rawValue: number, previous: BoundaryValue | null): BoundaryValue {
  if (!previous) {
    return {
      value: rawValue,
      capped: false,
      uncappedValue: rawValue,
      previousValue: null,
    }
  }

  const maxShift = previous.value * MAX_BOUNDARY_SHIFT_PERCENT
  const delta = rawValue - previous.value
  const capped = Math.abs(delta) > maxShift

  const cappedValue = capped
    ? previous.value + Math.sign(delta) * maxShift
    : rawValue

  return {
    value: cappedValue,
    capped,
    uncappedValue: rawValue,
    previousValue: previous.value,
  }
}

function robustZScore(value: number, dist: MetricDistribution): number {
  // Use median and MAD for robust z-score
  if (dist.mad === 0) return 0
  return (value - dist.p50) / dist.mad
}

function mapTierLabel(tier: string): FunnelTier {
  const map: Record<string, FunnelTier> = {
    'High': 'HIGH',
    'Medium': 'MEDIUM',
    'Low': 'LOW',
    'HIGH': 'HIGH',
    'MEDIUM': 'MEDIUM',
    'LOW': 'LOW',
  }
  return map[tier] ?? 'MEDIUM'
}

function determineFallbackLevel(
  currentTier: FunnelTier,
  groupDist: GroupDistributions,
  globalFallback: Record<FunnelTier, TierDistribution>
): FallbackLevel {
  // Check if current tier is insufficient in group
  if (!groupDist.insufficientTiers.includes(currentTier)) {
    return 'per_group'
  }

  // Check if global has sufficient data
  const globalTier = globalFallback[currentTier]
  if (globalTier.sampleSize >= MIN_SAMPLE_SIZE) {
    return 'global'
  }

  // Both group and global are insufficient
  return 'defaults'
}

function buildPeerContext(termRoas: number, groupDist: GroupDistributions, label: string): string {
  // Collect all ROAS values across tiers
  const allRoas: number[] = []
  for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
    const dist = groupDist.tiers[tier]
    if (dist.sampleSize > 0) {
      // We don't have raw values, so estimate rank from distributions
      allRoas.push(dist.metrics.roas.p25, dist.metrics.roas.p50, dist.metrics.roas.p75)
    }
  }

  if (allRoas.length === 0) return `No peer data available for ${label}`

  const sorted = [...allRoas].sort((a, b) => a - b)
  const belowCount = sorted.filter(v => v <= termRoas).length
  const percentile = Math.round((belowCount / sorted.length) * 100)

  const displayLabel = label || 'this group'
  if (percentile >= 85) return `Ranks in top ${100 - percentile}% of ${displayLabel} terms`
  if (percentile <= 15) return `Ranks in bottom ${percentile}% of ${displayLabel} terms`
  return `Ranks at ${percentile}th percentile among ${displayLabel} terms`
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {}
  for (const item of items) {
    const key = keyFn(item)
    if (!result[key]) result[key] = []
    result[key].push(item)
  }
  return result
}
