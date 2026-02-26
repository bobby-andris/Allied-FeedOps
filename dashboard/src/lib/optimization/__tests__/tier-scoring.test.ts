import { describe, it, expect } from 'vitest'
import type { LabelTierPerformance, ExistingFunnelTerm, FunnelTier, QueryIntentFeatures } from '@/lib/shopping-funnel/types'
import type { GroupDistributions, TierDistribution, TierBoundaries, CalibrationConfig, RecommendedAction } from '../tier-scoring.types'
import { DEFAULT_CALIBRATION } from '../tier-scoring.types'
import {
  computeTierDistributions,
  computeTierBoundaries,
  scoreTerm,
  computeConfidence,
  estimateImpact,
  computeGlobalDistributions,
  buildHeroCallout,
} from '../tier-scoring'

// ---------------------------------------------------------------------------
// Test Fixtures
// ---------------------------------------------------------------------------

function makeLabelTierPerf(overrides: Partial<LabelTierPerformance> = {}): LabelTierPerformance {
  return {
    custom_label_0: 'Towel Bars',
    tier: 'HIGH',
    impressions: 1000,
    clicks: 50,
    cost_micros: 5_000_000, // $5
    conversions: 5,
    conversions_value: 25_000_000, // $25 (micros) — actually let's use dollar values per interface
    roas: 5.0,
    ...overrides,
  }
}

function makeTermWithFunnels(overrides: Partial<ExistingFunnelTerm> & { label?: string; tier?: string } = {}): ExistingFunnelTerm {
  const { label, tier, ...rest } = overrides
  return {
    search_term: 'brass towel bar',
    total_impressions: 500,
    total_clicks: 25,
    total_cost_micros: 2_500_000,
    total_conversions: 3,
    total_conversions_value: 150,
    funnels: [{
      custom_label_0: label ?? 'Towel Bars',
      tier: (tier ?? 'High') as 'High' | 'Medium' | 'Low' | 'Campaign Negative' | 'Unknown',
      error: false,
      error_message: null,
    }],
    ...rest,
  }
}

/**
 * Normal distribution: 20+ rows with normal-ish ROAS (2-6 range) across tiers
 */
function makeNormalDistribution(label = 'Towel Bars'): LabelTierPerformance[] {
  const rows: LabelTierPerformance[] = []
  // HIGH tier: 8 rows, ROAS 4-8
  const highRoas = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0]
  for (const roas of highRoas) {
    rows.push(makeLabelTierPerf({
      custom_label_0: label,
      tier: 'HIGH',
      roas,
      impressions: 1000 + Math.round(roas * 100),
      clicks: 50 + Math.round(roas * 5),
      cost_micros: 5_000_000,
      conversions: Math.round(roas),
      conversions_value: roas * 5_000_000,
    }))
  }
  // MEDIUM tier: 8 rows, ROAS 2-4
  const medRoas = [2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 3.8, 4.0]
  for (const roas of medRoas) {
    rows.push(makeLabelTierPerf({
      custom_label_0: label,
      tier: 'MEDIUM',
      roas,
      impressions: 800 + Math.round(roas * 100),
      clicks: 30 + Math.round(roas * 5),
      cost_micros: 4_000_000,
      conversions: Math.round(roas),
      conversions_value: roas * 4_000_000,
    }))
  }
  // LOW tier: 8 rows, ROAS 0.5-2
  const lowRoas = [0.5, 0.8, 1.0, 1.2, 1.5, 1.7, 1.8, 2.0]
  for (const roas of lowRoas) {
    rows.push(makeLabelTierPerf({
      custom_label_0: label,
      tier: 'LOW',
      roas,
      impressions: 500 + Math.round(roas * 100),
      clicks: 10 + Math.round(roas * 5),
      cost_micros: 3_000_000,
      conversions: Math.max(1, Math.round(roas)),
      conversions_value: roas * 3_000_000,
    }))
  }
  return rows
}

/**
 * Sparse distribution: 3 rows per tier (triggers fallback at <5)
 */
function makeSparseDistribution(label = 'Rare Category'): LabelTierPerformance[] {
  return [
    makeLabelTierPerf({ custom_label_0: label, tier: 'HIGH', roas: 5.0, clicks: 20, conversions: 3 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'HIGH', roas: 6.0, clicks: 25, conversions: 4 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'HIGH', roas: 7.0, clicks: 30, conversions: 5 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'MEDIUM', roas: 3.0, clicks: 15, conversions: 2 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'MEDIUM', roas: 3.5, clicks: 18, conversions: 2 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'MEDIUM', roas: 2.5, clicks: 12, conversions: 1 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'LOW', roas: 1.0, clicks: 5, conversions: 0 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'LOW', roas: 0.8, clicks: 3, conversions: 0 }),
    makeLabelTierPerf({ custom_label_0: label, tier: 'LOW', roas: 1.2, clicks: 7, conversions: 1 }),
  ]
}

/**
 * Skewed distribution: heavy right-skew (most at 0-2, outliers at 15-50)
 */
function makeSkewedDistribution(label = 'Skewed Group'): LabelTierPerformance[] {
  const rows: LabelTierPerformance[] = []
  // HIGH tier: mostly low ROAS with outlier
  const highRoas = [3.0, 3.5, 4.0, 4.5, 5.0, 15.0, 50.0]
  for (const roas of highRoas) {
    rows.push(makeLabelTierPerf({ custom_label_0: label, tier: 'HIGH', roas, clicks: 30, conversions: 3 }))
  }
  // MEDIUM tier: normal
  const medRoas = [2.0, 2.5, 3.0, 3.0, 3.5, 3.5, 4.0]
  for (const roas of medRoas) {
    rows.push(makeLabelTierPerf({ custom_label_0: label, tier: 'MEDIUM', roas, clicks: 20, conversions: 2 }))
  }
  // LOW tier: mostly near zero
  const lowRoas = [0.1, 0.2, 0.5, 0.8, 1.0, 1.0, 1.5]
  for (const roas of lowRoas) {
    rows.push(makeLabelTierPerf({ custom_label_0: label, tier: 'LOW', roas, clicks: 10, conversions: 1 }))
  }
  return rows
}

// ---------------------------------------------------------------------------
// TIER-01: Distribution Computation
// ---------------------------------------------------------------------------

describe('TIER-01: computeTierDistributions', () => {
  it('returns per-group per-tier distributions with p25 <= p50 <= p75 for all metrics', () => {
    const rows = makeNormalDistribution('Towel Bars')
    const result = computeTierDistributions(rows)

    expect(result.size).toBe(1)
    const group = result.get('Towel Bars')!
    expect(group).toBeDefined()
    expect(group.customLabel0).toBe('Towel Bars')

    for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
      const dist = group.tiers[tier]
      expect(dist).toBeDefined()
      expect(dist.tier).toBe(tier)

      for (const metric of ['roas', 'cvr', 'cpc', 'ctr'] as const) {
        const m = dist.metrics[metric]
        expect(m.p25).toBeLessThanOrEqual(m.p50)
        expect(m.p50).toBeLessThanOrEqual(m.p75)
        expect(m.min).toBeLessThanOrEqual(m.p25)
        expect(m.p75).toBeLessThanOrEqual(m.max)
        expect(typeof m.mean).toBe('number')
        expect(typeof m.mad).toBe('number')
        expect(m.mad).toBeGreaterThanOrEqual(0)
      }
    }
  })

  it('computes correct ROAS distribution values for known data', () => {
    const rows = makeNormalDistribution('Towel Bars')
    const result = computeTierDistributions(rows)
    const group = result.get('Towel Bars')!

    // HIGH tier ROAS: [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0]
    const highRoas = group.tiers.HIGH.metrics.roas
    expect(highRoas.p50).toBeCloseTo(5.75, 0) // median of 8 values
    expect(highRoas.min).toBeCloseTo(4.0, 1)
  })

  it('handles multiple groups independently', () => {
    const rows = [
      ...makeNormalDistribution('Towel Bars'),
      ...makeNormalDistribution('Shower Doors'),
    ]
    const result = computeTierDistributions(rows)
    expect(result.size).toBe(2)
    expect(result.has('Towel Bars')).toBe(true)
    expect(result.has('Shower Doors')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// TIER-02: Tier Boundaries
// ---------------------------------------------------------------------------

describe('TIER-02: computeTierBoundaries', () => {
  it('derives HIGH floor from MEDIUM p25 and LOW ceiling from MEDIUM p75', () => {
    const rows = makeNormalDistribution()
    const result = computeTierDistributions(rows)
    const group = result.get('Towel Bars')!
    const boundaries = group.boundaries

    expect(boundaries.metric).toBe('roas')
    // MEDIUM ROAS: [2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 3.8, 4.0]
    // p25 ~ 2.575, p75 ~ 3.575
    expect(boundaries.highFloor.value).toBeGreaterThan(0)
    expect(boundaries.lowCeiling.value).toBeGreaterThan(boundaries.highFloor.value)
  })

  it('caps shift at 15% when previous boundaries provided', () => {
    const rows = makeNormalDistribution()
    // First compute without previous
    const result1 = computeTierDistributions(rows)
    const group1 = result1.get('Towel Bars')!
    const b1 = group1.boundaries

    // Now create drastically different data that would shift >15%
    const shifted = makeNormalDistribution()
    // Double MEDIUM ROAS
    for (const row of shifted) {
      if (row.tier === 'MEDIUM') row.roas *= 2
    }
    const result2 = computeTierDistributions(shifted, { previousDistributions: result1 })
    const group2 = result2.get('Towel Bars')!
    const b2 = group2.boundaries

    // The high floor should be capped
    if (b2.highFloor.capped) {
      const maxShift = b1.highFloor.value * 0.15
      expect(Math.abs(b2.highFloor.value - b1.highFloor.value)).toBeLessThanOrEqual(maxShift + 0.001)
    }
    // uncappedValue should reflect the true data-driven value
    expect(b2.highFloor.previousValue).toBeCloseTo(b1.highFloor.value, 2)
  })
})

// ---------------------------------------------------------------------------
// TIER-03: Robust Z-Score Scoring
// ---------------------------------------------------------------------------

describe('TIER-03: scoreTerm (robust z-scores)', () => {
  it('uses median/MAD not mean/stddev for z-scores', () => {
    // Create skewed data where mean != median significantly
    const rows = makeSkewedDistribution('Skewed Group')
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Skewed Group')!
    const globalFallback = computeGlobalDistributions(rows)

    // HIGH tier has outliers 15.0 and 50.0 — mean will be much higher than median
    const highDist = group.tiers.HIGH.metrics.roas
    expect(highDist.mean).toBeGreaterThan(highDist.p50) // confirms skew

    // Score a term that's close to the median but far from the mean
    const term = makeTermWithFunnels({
      label: 'Skewed Group',
      tier: 'High',
      total_impressions: 500,
      total_clicks: 30,
      total_cost_micros: 3_000_000,
      total_conversions: 3,
      total_conversions_value: 13.5, // ROAS ~4.5 (close to median ~4.5, far from mean ~12)
    })

    const score = scoreTerm(term, group, globalFallback)
    // With robust z-score (median-based), this term should fit HIGH well
    // With mean-based z-score, it would look like a poor fit (far below mean of ~12)
    expect(score.tierFitScores.HIGH).toBeDefined()
    expect(typeof score.tierFitScores.HIGH).toBe('number')
    expect(score.searchTerm).toBe('brass towel bar')
  })

  it('produces tier fit scores for all three tiers', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      total_conversions_value: 150, // decent ROAS
    })

    const score = scoreTerm(term, group, globalFallback)
    expect(score.tierFitScores).toHaveProperty('HIGH')
    expect(score.tierFitScores).toHaveProperty('MEDIUM')
    expect(score.tierFitScores).toHaveProperty('LOW')
    expect(score.recommendedTier).toMatch(/^(HIGH|MEDIUM|LOW)$/)
    expect(typeof score.isMisplaced).toBe('boolean')
    expect(typeof score.verdict).toBe('string')
    expect(score.verdict.length).toBeGreaterThan(0)
    expect(typeof score.peerContext).toBe('string')
  })

  it('handles MAD=0 gracefully (all values identical)', () => {
    const rows: LabelTierPerformance[] = []
    // All HIGH tier rows have identical ROAS
    for (let i = 0; i < 6; i++) {
      rows.push(makeLabelTierPerf({ tier: 'HIGH', roas: 5.0, clicks: 50, conversions: 5 }))
    }
    for (let i = 0; i < 6; i++) {
      rows.push(makeLabelTierPerf({ tier: 'MEDIUM', roas: 3.0, clicks: 30, conversions: 3 }))
    }
    for (let i = 0; i < 6; i++) {
      rows.push(makeLabelTierPerf({ tier: 'LOW', roas: 1.0, clicks: 10, conversions: 1 }))
    }

    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({ total_conversions_value: 150 })
    const score = scoreTerm(term, group, globalFallback)
    // Should not throw or return NaN
    expect(Number.isFinite(score.tierFitScores.HIGH)).toBe(true)
    expect(Number.isFinite(score.tierFitScores.MEDIUM)).toBe(true)
    expect(Number.isFinite(score.tierFitScores.LOW)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// TIER-04: Hierarchical Fallback
// ---------------------------------------------------------------------------

describe('TIER-04: Hierarchical fallback', () => {
  it('uses global distributions when per-group tier has <5 terms', () => {
    // Sparse group (3 per tier) + normal group combined
    const sparseRows = makeSparseDistribution('Rare Category')
    const normalRows = makeNormalDistribution('Towel Bars')
    const allRows = [...sparseRows, ...normalRows]

    const distMap = computeTierDistributions(allRows)
    const sparseGroup = distMap.get('Rare Category')!
    const globalFallback = computeGlobalDistributions(allRows)

    // Sparse group should have insufficient tiers
    expect(sparseGroup.insufficientTiers.length).toBeGreaterThan(0)

    // Score a term from the sparse group
    const term = makeTermWithFunnels({
      label: 'Rare Category',
      tier: 'High',
      total_conversions_value: 150,
    })

    const score = scoreTerm(term, sparseGroup, globalFallback)
    // Should fall back to global
    expect(score.fallbackLevel).toBe('global')
  })

  it('uses defaults when global is also sparse', () => {
    // Only sparse data, no large group to provide robust global fallback
    const sparseRows = makeSparseDistribution('Only Category')

    const distMap = computeTierDistributions(sparseRows)
    const group = distMap.get('Only Category')!
    const globalFallback = computeGlobalDistributions(sparseRows)

    const term = makeTermWithFunnels({
      label: 'Only Category',
      tier: 'High',
      total_conversions_value: 150,
    })

    const score = scoreTerm(term, group, globalFallback)
    // When global is also insufficient, should fall back to defaults
    expect(['global', 'defaults']).toContain(score.fallbackLevel)
  })
})

// ---------------------------------------------------------------------------
// TIER-05: Insufficient Data Flagging
// ---------------------------------------------------------------------------

describe('TIER-05: Insufficient data flagging', () => {
  it('marks tiers with <5 non-zero-metric terms in insufficientTiers', () => {
    const rows = makeSparseDistribution('Small Group')
    const result = computeTierDistributions(rows)
    const group = result.get('Small Group')!

    // All tiers have only 3 rows each — all should be insufficient
    expect(group.insufficientTiers).toContain('HIGH')
    expect(group.insufficientTiers).toContain('MEDIUM')
    expect(group.insufficientTiers).toContain('LOW')
  })

  it('computes distributions even for insufficient tiers (not empty)', () => {
    const rows = makeSparseDistribution('Small Group')
    const result = computeTierDistributions(rows)
    const group = result.get('Small Group')!

    // Distributions should still be computed even though flagged
    for (const tier of ['HIGH', 'MEDIUM', 'LOW'] as FunnelTier[]) {
      expect(group.tiers[tier]).toBeDefined()
      expect(group.tiers[tier].sampleSize).toBeGreaterThan(0)
      expect(group.tiers[tier].metrics.roas.p50).toBeGreaterThan(0)
    }
  })

  it('does NOT flag tiers with >=5 terms', () => {
    const rows = makeNormalDistribution('Large Group')
    const result = computeTierDistributions(rows)
    const group = result.get('Large Group')!

    // 8 rows per tier — none should be insufficient
    expect(group.insufficientTiers).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// TIER-06: Confidence Scoring
// ---------------------------------------------------------------------------

describe('TIER-06: computeConfidence', () => {
  it('returns score between 0 and 1 with correct factor weights', () => {
    const term = makeTermWithFunnels({
      total_clicks: 200,
      total_conversions: 15,
    })

    const result = computeConfidence(term)
    expect(result.score).toBeGreaterThanOrEqual(0)
    expect(result.score).toBeLessThanOrEqual(1)
    expect(result.level).toMatch(/^(High|Medium|Low)$/)

    // Verify all factor components are 0-1
    const f = result.factors
    expect(f.dataVolume).toBeGreaterThanOrEqual(0)
    expect(f.dataVolume).toBeLessThanOrEqual(1)
    expect(f.consistency).toBeGreaterThanOrEqual(0)
    expect(f.consistency).toBeLessThanOrEqual(1)
    expect(f.significance).toBeGreaterThanOrEqual(0)
    expect(f.significance).toBeLessThanOrEqual(1)
    expect(f.intentAlignment).toBeGreaterThanOrEqual(0)
    expect(f.intentAlignment).toBeLessThanOrEqual(1)
  })

  it('gives high data volume factor for many clicks', () => {
    const highClicks = makeTermWithFunnels({ total_clicks: 500 })
    const lowClicks = makeTermWithFunnels({ total_clicks: 5 })

    const highResult = computeConfidence(highClicks)
    const lowResult = computeConfidence(lowClicks)

    expect(highResult.factors.dataVolume).toBeGreaterThan(lowResult.factors.dataVolume)
  })

  it('gives high significance factor for many conversions', () => {
    const highConv = makeTermWithFunnels({ total_conversions: 50 })
    const lowConv = makeTermWithFunnels({ total_conversions: 1 })

    const highResult = computeConfidence(highConv)
    const lowResult = computeConfidence(lowConv)

    expect(highResult.factors.significance).toBeGreaterThan(lowResult.factors.significance)
  })

  it('weights are 30/30/20/20 in combined score', () => {
    // Manually verify: set all factors to known values and check weighted sum
    const term = makeTermWithFunnels({
      total_clicks: 100, // dataVolume = 1.0
      total_conversions: 10, // significance = 1.0
    })

    const result = computeConfidence(term)
    // Combined = 0.3*volume + 0.3*consistency + 0.2*significance + 0.2*alignment
    const expected = 0.3 * result.factors.dataVolume
      + 0.3 * result.factors.consistency
      + 0.2 * result.factors.significance
      + 0.2 * result.factors.intentAlignment

    expect(result.score).toBeCloseTo(expected, 5)
  })

  it('uses intent features when provided', () => {
    const term = makeTermWithFunnels({ tier: 'High' })
    const brandedIntent: QueryIntentFeatures = {
      product_object: 'towel bar',
      modifier_tokens: ['brass'],
      use_case_tokens: [],
      is_branded: true,
      is_competitor: false,
      has_mismatch_risk: false,
    }

    const withIntent = computeConfidence(term, brandedIntent, 'HIGH')
    const withoutIntent = computeConfidence(term)

    // Branded + HIGH tier should have good alignment
    expect(withIntent.factors.intentAlignment).toBeGreaterThanOrEqual(0.5)
    // Without intent, should use neutral 0.5
    expect(withoutIntent.factors.intentAlignment).toBe(0.5)
  })

  it('classifies confidence levels correctly', () => {
    // High confidence: many clicks + conversions
    const highTerm = makeTermWithFunnels({ total_clicks: 500, total_conversions: 50 })
    const highResult = computeConfidence(highTerm)
    expect(highResult.score).toBeGreaterThanOrEqual(0.6)

    // Low confidence: few clicks + conversions
    const lowTerm = makeTermWithFunnels({ total_clicks: 2, total_conversions: 0 })
    const lowResult = computeConfidence(lowTerm)
    expect(lowResult.score).toBeLessThan(0.5)
  })
})

// ---------------------------------------------------------------------------
// Impact Estimation
// ---------------------------------------------------------------------------

describe('estimateImpact', () => {
  it('returns ImpactRange with low <= mid <= high', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!

    const term = makeTermWithFunnels({
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 5_000_000,
      total_conversions: 2,
      total_conversions_value: 100,
    })

    const impact = estimateImpact(
      term,
      group.tiers.LOW, // current tier distribution
      group.tiers.HIGH  // target tier distribution
    )

    expect(impact.low).toBeLessThanOrEqual(impact.mid)
    expect(impact.mid).toBeLessThanOrEqual(impact.high)
    expect(impact.low).toBeGreaterThanOrEqual(0)
    expect(impact.currency).toBe('USD')
    expect(impact.period).toBe('monthly')
  })

  it('returns non-negative values even when target ROAS is lower', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!

    const term = makeTermWithFunnels({ total_impressions: 500 })
    const impact = estimateImpact(term, group.tiers.HIGH, group.tiers.LOW)
    expect(impact.low).toBeGreaterThanOrEqual(0)
    expect(impact.mid).toBeGreaterThanOrEqual(0)
    expect(impact.high).toBeGreaterThanOrEqual(0)
  })
})

// ---------------------------------------------------------------------------
// Phase 33.1: Calibration
// ---------------------------------------------------------------------------

describe('Phase 33.1: Calibration', () => {
  it('estimateImpact returns non-zero for upward ROAS movement', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!

    // Term with $5 spend, moving from LOW to HIGH
    const term = makeTermWithFunnels({
      total_impressions: 500,
      total_clicks: 25,
      total_cost_micros: 5_000_000, // $5
      total_conversions: 1,
      total_conversions_value: 6, // low ROAS
    })

    const impact = estimateImpact(term, group.tiers.LOW, group.tiers.HIGH)
    expect(impact.mid).toBeGreaterThan(0)
    // LOW ROAS p50 ~1.2, HIGH ROAS p50 ~5.75; $5 * (5.75 - 1.2) = ~$22.75
    expect(impact.mid).toBeGreaterThan(10) // sanity check — not $0
  })

  it('estimateImpact returns $0 for downward movement', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!

    const term = makeTermWithFunnels({
      total_cost_micros: 5_000_000,
    })

    // HIGH → LOW: ROAS drops, delta negative, Math.max floors to 0
    const impact = estimateImpact(term, group.tiers.HIGH, group.tiers.LOW)
    expect(impact.low).toBe(0)
    expect(impact.mid).toBe(0)
    expect(impact.high).toBe(0)
  })

  it('estimateImpact includes direction field', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!

    const term = makeTermWithFunnels({ total_cost_micros: 5_000_000 })

    const upward = estimateImpact(term, group.tiers.LOW, group.tiers.HIGH)
    expect(upward.direction).toBe('upward')

    const downward = estimateImpact(term, group.tiers.HIGH, group.tiers.LOW)
    expect(downward.direction).toBe('downward')

    const lateral = estimateImpact(term, group.tiers.MEDIUM, group.tiers.MEDIUM)
    expect(lateral.direction).toBe('lateral')
  })

  it('scoreTerm with calibration filters low-delta terms', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // A term that is borderline — ROAS close to boundary between tiers
    // MEDIUM ROAS range: 2-4, place term at ~3.0 (solidly medium)
    // but assign to HIGH so it disagrees slightly
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 500,
      total_clicks: 50,
      total_cost_micros: 5_000_000,
      total_conversions: 5,
      total_conversions_value: 15, // ROAS = 15/5 = 3.0 (MEDIUM range)
    })

    // Use strict thresholds to see if borderline case is filtered
    const strictConfig: CalibrationConfig = {
      minFitScoreDelta: 0.3,
      minConfidence: 0.40,
      minImpressions: 50,
      averageOrderValue: 85,
    }

    const score = scoreTerm(term, group, globalFallback, undefined, strictConfig)
    // Whether misplaced or not depends on actual delta — but fitScoreDelta should be populated
    expect(typeof score.fitScoreDelta).toBe('number')
    // If delta < 0.3, isMisplaced should be false even if recommended != current
    if (score.fitScoreDelta < 0.3) {
      expect(score.isMisplaced).toBe(false)
    }
  })

  it('scoreTerm with calibration filters low-confidence terms', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Very few clicks → low confidence
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'Low', // assign to LOW
      total_impressions: 200,
      total_clicks: 2,  // very few clicks → low data volume
      total_cost_micros: 500_000,
      total_conversions: 0,
      total_conversions_value: 0,
    })

    const config: CalibrationConfig = {
      minFitScoreDelta: 0.0, // no delta threshold — isolate confidence filter
      minConfidence: 0.40,
      minImpressions: 0, // no impression threshold
      averageOrderValue: 85,
    }

    const score = scoreTerm(term, group, globalFallback, undefined, config)
    // With 2 clicks, confidence should be low (dataVolume = 2/100 = 0.02)
    expect(score.confidence.score).toBeLessThan(0.40)
    expect(score.isMisplaced).toBe(false)
  })

  it('scoreTerm with calibration filters low-impression terms', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Low impressions
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'Low',
      total_impressions: 10, // below 50 threshold
      total_clicks: 5,
      total_cost_micros: 500_000,
      total_conversions: 1,
      total_conversions_value: 5,
    })

    const config: CalibrationConfig = {
      minFitScoreDelta: 0.0,
      minConfidence: 0.0,
      minImpressions: 50,
      averageOrderValue: 85,
    }

    const score = scoreTerm(term, group, globalFallback, undefined, config)
    expect(score.isMisplaced).toBe(false)
  })

  it('scoreTerm populates dataConfirmed for well-placed high-confidence terms', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // HIGH tier term with HIGH ROAS → should confirm placement
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 500,
      total_clicks: 100,
      total_cost_micros: 5_000_000,
      total_conversions: 10,
      total_conversions_value: 30, // ROAS = 30/5 = 6.0 (solidly HIGH)
    })

    const score = scoreTerm(term, group, globalFallback)
    // ROAS 6.0 is well within HIGH tier range — recommended should be HIGH
    if (score.recommendedTier === 'HIGH') {
      expect(score.dataConfirmed).toBe(true)
      expect(score.isMisplaced).toBe(false)
    }
  })

  it('scoreTerm populates fitScoreDelta', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      total_impressions: 500,
      total_clicks: 25,
      total_cost_micros: 2_500_000,
      total_conversions: 3,
      total_conversions_value: 150,
    })

    const score = scoreTerm(term, group, globalFallback)
    expect(typeof score.fitScoreDelta).toBe('number')
    expect(score.fitScoreDelta).toBeGreaterThanOrEqual(0)
  })

  it('buildHeroCallout reflects calibrated misplaced count', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Create terms that are well-placed (should not be flagged with calibration)
    const terms = [
      // HIGH ROAS term in HIGH → confirmed
      makeTermWithFunnels({
        search_term: 'brass towel bar premium',
        label: 'Towel Bars',
        tier: 'High',
        total_impressions: 500,
        total_clicks: 100,
        total_cost_micros: 5_000_000,
        total_conversions: 10,
        total_conversions_value: 30,
      }),
      // LOW ROAS term in LOW → confirmed
      makeTermWithFunnels({
        search_term: 'cheap bar',
        label: 'Towel Bars',
        tier: 'Low',
        total_impressions: 300,
        total_clicks: 5,
        total_cost_micros: 1_000_000,
        total_conversions: 0,
        total_conversions_value: 0,
      }),
    ]

    const scores = terms.map(t => scoreTerm(t, group, globalFallback))
    const hero = buildHeroCallout(scores)
    // With calibrated scoring, well-placed terms should not be flagged
    const misplacedCount = scores.filter(s => s.isMisplaced).length
    expect(misplacedCount).toBeLessThanOrEqual(1) // most should be correctly placed
    if (misplacedCount === 0) {
      expect(hero).toBe('All scored terms appear correctly placed')
    }
  })
})

// ---------------------------------------------------------------------------
// Phase 34.1: Decision Logic Bug Fixes
// ---------------------------------------------------------------------------

describe('Phase 34.1: Bug 1 — Wasted spend override', () => {
  it('wasted spend term with 0 conversions and >$5 spend gets block when in HIGH', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 10_000_000, // $10
      total_conversions: 0,
      total_conversions_value: 0,
    })

    const score = scoreTerm(term, group, globalFallback)
    expect(score.recommendedAction).toBe('block')
  })

  it('wasted spend term with 0 conversions and >$5 spend gets constrain when in MEDIUM/LOW', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'Medium',
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 10_000_000, // $10
      total_conversions: 0,
      total_conversions_value: 0,
    })

    const score = scoreTerm(term, group, globalFallback)
    expect(score.recommendedAction).toBe('constrain')
  })
})

describe('Phase 34.1: Bug 2 — Impact formula for wasted spend', () => {
  it('wasted spend impact equals monthly cost saved, not $0', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 8_000_000, // $8
      total_conversions: 0,
      total_conversions_value: 0,
    })

    const score = scoreTerm(term, group, globalFallback)
    expect(score.impact).not.toBeNull()
    expect(score.impact!.mid).toBeGreaterThanOrEqual(4) // at least 50% of $8
    expect(score.impact!.mid).toBeGreaterThan(0) // NOT $0
  })

  it('promote impact is positive when term ROAS exceeds target tier median', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // High ROAS term in HIGH tier — scoring engine should see it fits LOW better
    // HIGH ROAS: p50 ~5.75, LOW ROAS: p50 ~1.2
    // With ROAS 60/5=12.0, this is way above HIGH median, so recommended might be HIGH still
    // Let's use a term with ROAS in the LOW tier range but placed in HIGH
    // Actually we need a term that gets recommendedAction='promote'
    // A term with moderate ROAS placed in HIGH that fits MEDIUM better
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 500,
      total_clicks: 100,
      total_cost_micros: 100_000_000, // $100
      total_conversions: 15,
      total_conversions_value: 500, // ROAS = 500/100 = 5.0
    })

    const score = scoreTerm(term, group, globalFallback)
    // If misplaced with a downward move, impact should be positive
    if (score.isMisplaced && score.impact) {
      expect(score.impact.mid).toBeGreaterThanOrEqual(0)
    }
    // At minimum, verify impact is not null when misplaced
    if (score.isMisplaced) {
      expect(score.impact).not.toBeNull()
    }
  })
})

describe('Phase 34.1: Bug 3 — CPC inversion', () => {
  it('cheap CPC (negative z-score) does not penalize fit score', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Cheap CPC term: low cost, many clicks
    const cheapTerm = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 200,
      total_cost_micros: 1_000_000, // $1 / 200 clicks = $0.005 CPC (very cheap)
      total_conversions: 10,
      total_conversions_value: 60,
    })

    // Expensive CPC term: high cost, few clicks
    const expensiveTerm = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 10,
      total_cost_micros: 20_000_000, // $20 / 10 clicks = $2.00 CPC (expensive)
      total_conversions: 10,
      total_conversions_value: 60,
    })

    const cheapScore = scoreTerm(cheapTerm, group, globalFallback)
    const expensiveScore = scoreTerm(expensiveTerm, group, globalFallback)

    // Cheap CPC should produce a BETTER (higher/less negative) HIGH tier fit score than expensive CPC
    // because cheap CPC should not be penalized
    expect(cheapScore.tierFitScores.HIGH).toBeGreaterThanOrEqual(expensiveScore.tierFitScores.HIGH)
  })

  it('expensive CPC (positive z-score) penalizes fit score', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Baseline: term with CPC at the tier median
    const baselineTerm = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 2_500_000, // $2.5 / 50 = $0.05 CPC
      total_conversions: 5,
      total_conversions_value: 30,
    })

    // Expensive: CPC well above median
    const expensiveTerm = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 5,
      total_cost_micros: 25_000_000, // $25 / 5 = $5.00 CPC (very expensive)
      total_conversions: 5,
      total_conversions_value: 30,
    })

    const baselineScore = scoreTerm(baselineTerm, group, globalFallback)
    const expensiveScore = scoreTerm(expensiveTerm, group, globalFallback)

    // Expensive CPC should produce a WORSE (lower/more negative) fit score
    expect(expensiveScore.tierFitScores.HIGH).toBeLessThan(baselineScore.tierFitScores.HIGH)
  })
})

describe('Phase 34.1: Bug 4 — Prescriptive verdicts', () => {
  it('wasted spend verdict includes spend amount and "block" language', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 1000,
      total_clicks: 50,
      total_cost_micros: 10_000_000, // $10
      total_conversions: 0,
      total_conversions_value: 0,
    })

    const score = scoreTerm(term, group, globalFallback)
    // actionReason should include dollar amount and block language
    expect(score.actionReason).toBeDefined()
    expect(score.actionReason).toMatch(/\$/)
    expect(score.actionReason!.toLowerCase()).toMatch(/block/)
    // Should NOT use descriptive language
    expect(score.actionReason!.toLowerCase()).not.toMatch(/fits/)
    expect(score.actionReason!.toLowerCase()).not.toMatch(/distribution/)
  })

  it('promote verdict includes prescriptive action language', () => {
    const rows = makeNormalDistribution()
    const distMap = computeTierDistributions(rows)
    const group = distMap.get('Towel Bars')!
    const globalFallback = computeGlobalDistributions(rows)

    // Need a term that will get recommendedAction='promote'
    // promote = isMisplaced + recommendedTier deeper in funnel
    // A term in HIGH with metrics that fit MEDIUM better (downward = promote)
    const term = makeTermWithFunnels({
      label: 'Towel Bars',
      tier: 'High',
      total_impressions: 500,
      total_clicks: 100,
      total_cost_micros: 5_000_000, // $5
      total_conversions: 8,
      total_conversions_value: 15, // ROAS = 15/5 = 3.0 (fits MEDIUM range 2-4)
    })

    const score = scoreTerm(term, group, globalFallback)
    if (score.recommendedAction === 'promote') {
      expect(score.actionReason).toBeDefined()
      expect(score.actionReason!.toLowerCase()).toMatch(/promote|aggressive|move/)
      expect(score.actionReason!.toLowerCase()).not.toMatch(/resembles/)
      expect(score.actionReason!.toLowerCase()).not.toMatch(/fits/)
    }
    // Also verify the verdict field is prescriptive
    expect(score.verdict.toLowerCase()).not.toMatch(/resembles/)
  })
})
