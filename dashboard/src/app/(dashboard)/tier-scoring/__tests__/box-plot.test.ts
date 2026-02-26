import { describe, it, expect } from 'vitest'
import { aggregateDistributions, detectOverlaps } from '../components/RoasBoxPlot'
import type { GroupDistributions, TierDistribution } from '@/lib/optimization/tier-scoring.types'

// ---------------------------------------------------------------------------
// Test helper: minimal GroupDistributions mock
// ---------------------------------------------------------------------------

function makeTierDistribution(roas: {
  p25: number; p50: number; p75: number; min: number; max: number
}, sampleSize = 10): TierDistribution {
  return {
    tier: 'HIGH', // overridden by parent
    metrics: {
      roas: { ...roas, mean: roas.p50, mad: 0.1 },
      cvr: { p25: 0, p50: 0, p75: 0, min: 0, max: 0, mean: 0, mad: 0 },
      cpc: { p25: 0, p50: 0, p75: 0, min: 0, max: 0, mean: 0, mad: 0 },
      ctr: { p25: 0, p50: 0, p75: 0, min: 0, max: 0, mean: 0, mad: 0 },
    },
    sampleSize,
    fallbackLevel: 'per_group',
  }
}

function makeGroupDistributions(overrides?: {
  HIGH?: { p25: number; p50: number; p75: number; min: number; max: number; sampleSize?: number };
  MEDIUM?: { p25: number; p50: number; p75: number; min: number; max: number; sampleSize?: number };
  LOW?: { p25: number; p50: number; p75: number; min: number; max: number; sampleSize?: number };
}): GroupDistributions {
  const high = overrides?.HIGH ?? { p25: 5, p50: 8, p75: 12, min: 2, max: 20 }
  const medium = overrides?.MEDIUM ?? { p25: 2, p50: 4, p75: 6, min: 1, max: 10 }
  const low = overrides?.LOW ?? { p25: 0.5, p50: 1.5, p75: 3, min: 0, max: 5 }

  return {
    customLabel0: 'TestGroup',
    tiers: {
      HIGH: { ...makeTierDistribution(high, overrides?.HIGH?.sampleSize), tier: 'HIGH' },
      MEDIUM: { ...makeTierDistribution(medium, overrides?.MEDIUM?.sampleSize), tier: 'MEDIUM' },
      LOW: { ...makeTierDistribution(low, overrides?.LOW?.sampleSize), tier: 'LOW' },
    },
    boundaries: {
      highFloor: { value: 6, capped: false, uncappedValue: 6, previousValue: null },
      lowCeiling: { value: 3, capped: false, uncappedValue: 3, previousValue: null },
      metric: 'roas',
    },
    totalTerms: 30,
    scoredTerms: 25,
    insufficientTiers: [],
  }
}

// ---------------------------------------------------------------------------
// aggregateDistributions
// ---------------------------------------------------------------------------

describe('aggregateDistributions', () => {
  it('transforms distributions to box plot data for all 3 tiers', () => {
    const distributions = { group1: makeGroupDistributions() }
    const result = aggregateDistributions(distributions)

    expect(result).toHaveLength(3)
    expect(result.map(d => d.tier)).toEqual(['HIGH', 'MEDIUM', 'LOW'])
    expect(result.every(d => d.hasData)).toBe(true)
  })

  it('averages across multiple groups', () => {
    const distributions = {
      group1: makeGroupDistributions({
        HIGH: { p25: 4, p50: 6, p75: 10, min: 2, max: 15 },
      }),
      group2: makeGroupDistributions({
        HIGH: { p25: 6, p50: 10, p75: 14, min: 4, max: 25 },
      }),
    }
    const result = aggregateDistributions(distributions)

    const high = result.find(d => d.tier === 'HIGH')!
    // Average of 4,6 = 5 for p25
    expect(high.p25).toBeCloseTo(5)
    // Average of 6,10 = 8 for p50
    expect(high.p50).toBeCloseTo(8)
    // Average of 10,14 = 12 for p75
    expect(high.p75).toBeCloseTo(12)
  })

  it('marks tiers with no data as hasData: false', () => {
    const group = makeGroupDistributions()
    // Override HIGH tier to have zero sample size
    group.tiers.HIGH.sampleSize = 0

    const distributions = { group1: group }
    const result = aggregateDistributions(distributions)

    const high = result.find(d => d.tier === 'HIGH')!
    expect(high.hasData).toBe(false)
  })

  it('handles empty distributions record', () => {
    const result = aggregateDistributions({})
    expect(result).toHaveLength(3)
    expect(result.every(d => !d.hasData)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// detectOverlaps
// ---------------------------------------------------------------------------

describe('detectOverlaps', () => {
  it('detects overlap when higher tier p25 < lower tier p75', () => {
    const data = [
      { tier: 'HIGH' as const, label: 'Premium', p25: 3, p50: 8, p75: 12, min: 1, max: 20, color: '', hasData: true },
      { tier: 'MEDIUM' as const, label: 'Mid-tier', p25: 2, p50: 4, p75: 6, min: 1, max: 10, color: '', hasData: true },
      { tier: 'LOW' as const, label: 'Budget', p25: 0.5, p50: 1.5, p75: 3, min: 0, max: 5, color: '', hasData: true },
    ]
    const overlaps = detectOverlaps(data)
    // HIGH p25 (3) < MEDIUM p75 (6) => overlap
    // MEDIUM p25 (2) < LOW p75 (3) => overlap
    expect(overlaps).toHaveLength(2)
    expect(overlaps[0]).toEqual({ left: 'HIGH', right: 'MEDIUM' })
    expect(overlaps[1]).toEqual({ left: 'MEDIUM', right: 'LOW' })
  })

  it('returns no overlaps when tiers are well-separated', () => {
    const data = [
      { tier: 'HIGH' as const, label: 'Premium', p25: 10, p50: 15, p75: 20, min: 8, max: 25, color: '', hasData: true },
      { tier: 'MEDIUM' as const, label: 'Mid-tier', p25: 4, p50: 6, p75: 8, min: 2, max: 9, color: '', hasData: true },
      { tier: 'LOW' as const, label: 'Budget', p25: 0.5, p50: 1.5, p75: 3, min: 0, max: 4, color: '', hasData: true },
    ]
    const overlaps = detectOverlaps(data)
    expect(overlaps).toHaveLength(0)
  })

  it('skips comparison when a tier has no data', () => {
    const data = [
      { tier: 'HIGH' as const, label: 'Premium', p25: 3, p50: 8, p75: 12, min: 1, max: 20, color: '', hasData: true },
      { tier: 'MEDIUM' as const, label: 'Mid-tier', p25: 0, p50: 0, p75: 0, min: 0, max: 0, color: '', hasData: false },
      { tier: 'LOW' as const, label: 'Budget', p25: 0.5, p50: 1.5, p75: 3, min: 0, max: 5, color: '', hasData: true },
    ]
    const overlaps = detectOverlaps(data)
    expect(overlaps).toHaveLength(0)
  })
})
