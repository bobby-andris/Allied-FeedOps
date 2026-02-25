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
  ConfidenceResult,
  ConfidenceFactors,
  ImpactRange,
  ScoringResult,
} from './tier-scoring.types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_BOUNDARY_SHIFT_PERCENT = 0.15
const MIN_SAMPLE_SIZE = 5
const DEFAULT_AOV = 85 // Allied Brass average order value in USD
const CACHE_TTL_MS = 10 * 60 * 1000 // 10 minutes

const DEFAULT_METRIC_DIST: MetricDistribution = {
  p25: 0, p50: 0, p75: 0, mean: 0, mad: 0, min: 0, max: 0,
}

const DEFAULT_DISTRIBUTIONS: Record<FunnelTier, TierDistribution> = {
  HIGH: {
    tier: 'HIGH',
    metrics: {
      roas: { p25: 4.0, p50: 5.5, p75: 8.0, mean: 6.0, mad: 1.5, min: 3.0, max: 15.0 },
      cvr: { p25: 0.04, p50: 0.06, p75: 0.10, mean: 0.07, mad: 0.02, min: 0.02, max: 0.20 },
      cpc: { p25: 0.50, p50: 0.80, p75: 1.20, mean: 0.85, mad: 0.25, min: 0.20, max: 2.00 },
      ctr: { p25: 0.03, p50: 0.05, p75: 0.08, mean: 0.05, mad: 0.02, min: 0.01, max: 0.15 },
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
      roas: { p25: 0.5, p50: 1.2, p75: 2.0, mean: 1.2, mad: 0.5, min: 0.0, max: 3.0 },
      cvr: { p25: 0.005, p50: 0.01, p75: 0.02, mean: 0.01, mad: 0.005, min: 0.0, max: 0.05 },
      cpc: { p25: 0.30, p50: 0.50, p75: 0.80, mean: 0.55, mad: 0.15, min: 0.10, max: 1.20 },
      ctr: { p25: 0.01, p50: 0.02, p75: 0.03, mean: 0.02, mad: 0.008, min: 0.002, max: 0.06 },
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
  intentFeatures?: QueryIntentFeatures
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
    const absDeviation = 0.50 * Math.abs(zRoas) + 0.20 * Math.abs(zCvr) + 0.15 * Math.abs(zCpc) + 0.15 * Math.abs(zCtr)
    tierFitScores[tier] = -absDeviation // Higher is better fit
  }

  // Recommended tier = best fit
  const recommendedTier = (['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]).reduce(
    (best, tier) => tierFitScores[tier] > tierFitScores[best] ? tier : best,
    'HIGH' as FunnelTier
  )

  const isMisplaced = recommendedTier !== currentTier

  // Confidence
  const confidence = computeConfidence(term, intentFeatures, currentTier)

  // Impact (only if misplaced)
  let impact: ImpactRange | null = null
  if (isMisplaced) {
    impact = estimateImpact(term, chooseDist(currentTier), chooseDist(recommendedTier))
  }

  // Verdict
  const fitStrength = Math.abs(tierFitScores[recommendedTier])
  const strengthWord = fitStrength < 0.5 ? 'strong' : fitStrength < 1.5 ? 'moderate' : 'weak'
  const verdict = isMisplaced
    ? `This term is a ${strengthWord} fit for ${recommendedTier} because its ROAS (${termRoas.toFixed(1)}) aligns with ${recommendedTier} tier distributions`
    : `This term is correctly placed in ${currentTier} — it is a ${strengthWord} fit`

  // Peer context
  const peerContext = buildPeerContext(termRoas, groupDist, customLabel0)

  return {
    searchTerm: term.search_term,
    customLabel0,
    currentTier,
    recommendedTier,
    isMisplaced,
    tierFitScores,
    confidence,
    impact,
    fallbackLevel,
    verdict,
    peerContext,
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

  // NLP alignment (20%): intent → tier alignment
  let intentAlignment = 0.5 // neutral default
  if (intentFeatures && currentTier) {
    if (intentFeatures.is_branded && currentTier === 'HIGH') {
      intentAlignment = 0.9 // branded queries convert well in HIGH
    } else if (intentFeatures.is_branded && currentTier !== 'HIGH') {
      intentAlignment = 0.3
    } else if (intentFeatures.is_competitor && currentTier === 'LOW') {
      intentAlignment = 0.8 // competitor queries are defensive in LOW
    } else if (intentFeatures.is_competitor && currentTier !== 'LOW') {
      intentAlignment = 0.3
    } else if (intentFeatures.product_object && currentTier === 'MEDIUM') {
      intentAlignment = 0.7 // product-specific terms align with MEDIUM
    } else {
      intentAlignment = 0.5
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
  targetDist: TierDistribution
): ImpactRange {
  const impressions = term.total_impressions // assume 30-day window

  const currentCvr = currentDist.metrics.cvr.p50
  const targetCvrP25 = targetDist.metrics.cvr.p25
  const targetCvrP50 = targetDist.metrics.cvr.p50
  const targetCvrP75 = targetDist.metrics.cvr.p75

  const lowDelta = targetCvrP25 - currentCvr
  const midDelta = targetCvrP50 - currentCvr
  const highDelta = targetCvrP75 - currentCvr

  return {
    low: Math.max(0, impressions * lowDelta * DEFAULT_AOV),
    mid: Math.max(0, impressions * midDelta * DEFAULT_AOV),
    high: Math.max(0, impressions * highDelta * DEFAULT_AOV),
    currency: 'USD',
    period: 'monthly',
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
// Helpers
// ---------------------------------------------------------------------------

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
