import { describe, expect, it } from 'vitest'
import {
  calculateCalibrationScore,
  assessWorkloadBalance,
  identifyCalibrationOutliers,
} from '@/lib/intent/reviewer-calibration'

describe('calculateCalibrationScore', () => {
  it('returns 1.0 for a perfectly calibrated reviewer', () => {
    const score = calculateCalibrationScore({
      totalActions: 100,
      alignmentRate: 1.0,
      uniqueEntities: 50,
    })
    expect(score).toBe(1.0)
  })

  it('returns 0 for a reviewer with no activity and no alignment', () => {
    const score = calculateCalibrationScore({
      totalActions: 0,
      alignmentRate: 0,
      uniqueEntities: 0,
    })
    expect(score).toBe(0)
  })

  it('weights alignment at 60%', () => {
    const score = calculateCalibrationScore({
      totalActions: 0,
      alignmentRate: 1.0,
      uniqueEntities: 0,
    })
    expect(score).toBe(0.6)
  })

  it('weights volume at 30% and caps at 100 actions', () => {
    const score50 = calculateCalibrationScore({
      totalActions: 50,
      alignmentRate: 0,
      uniqueEntities: 0,
    })
    expect(score50).toBeCloseTo(0.15, 4)

    const score200 = calculateCalibrationScore({
      totalActions: 200,
      alignmentRate: 0,
      uniqueEntities: 0,
    })
    expect(score200).toBeCloseTo(0.3, 4)
  })

  it('weights breadth at 10% and caps at 50 entities', () => {
    const score25 = calculateCalibrationScore({
      totalActions: 0,
      alignmentRate: 0,
      uniqueEntities: 25,
    })
    expect(score25).toBeCloseTo(0.05, 4)

    const score100 = calculateCalibrationScore({
      totalActions: 0,
      alignmentRate: 0,
      uniqueEntities: 100,
    })
    expect(score100).toBeCloseTo(0.1, 4)
  })

  it('produces correct combined score', () => {
    // alignmentRate=0.8 * 0.6 = 0.48
    // min(60/100, 1) * 0.3 = 0.6 * 0.3 = 0.18
    // min(30/50, 1) * 0.1 = 0.6 * 0.1 = 0.06
    // total = 0.72
    const score = calculateCalibrationScore({
      totalActions: 60,
      alignmentRate: 0.8,
      uniqueEntities: 30,
    })
    expect(score).toBeCloseTo(0.72, 4)
  })
})

describe('assessWorkloadBalance', () => {
  it('returns balanced for empty input', () => {
    const result = assessWorkloadBalance([])
    expect(result.giniCoefficient).toBe(0)
    expect(result.isBalanced).toBe(true)
    expect(result.recommendations).toHaveLength(0)
  })

  it('returns Gini=0 for a single actor', () => {
    const result = assessWorkloadBalance([{ actor: 'alice', total_actions: 100 }])
    expect(result.giniCoefficient).toBe(0)
    expect(result.isBalanced).toBe(true)
  })

  it('returns Gini=0 for perfectly equal distribution', () => {
    const result = assessWorkloadBalance([
      { actor: 'alice', total_actions: 50 },
      { actor: 'bob', total_actions: 50 },
      { actor: 'carol', total_actions: 50 },
    ])
    expect(result.giniCoefficient).toBe(0)
    expect(result.isBalanced).toBe(true)
  })

  it('returns high Gini when all work goes to one actor', () => {
    const result = assessWorkloadBalance([
      { actor: 'alice', total_actions: 100 },
      { actor: 'bob', total_actions: 0 },
      { actor: 'carol', total_actions: 0 },
    ])
    // Gini should be close to 1 (maximum inequality with 3 actors = 2/3)
    expect(result.giniCoefficient).toBeGreaterThan(0.5)
    expect(result.isBalanced).toBe(false)
  })

  it('detects imbalanced workload and recommends redistribution', () => {
    const result = assessWorkloadBalance([
      { actor: 'alice', total_actions: 100 },
      { actor: 'bob', total_actions: 10 },
      { actor: 'carol', total_actions: 10 },
    ])
    expect(result.isBalanced).toBe(false)
    expect(result.recommendations.length).toBeGreaterThan(0)
    expect(result.recommendations.some((r) => r.includes('alice'))).toBe(true)
  })

  it('marks balanced when distribution is reasonably even', () => {
    const result = assessWorkloadBalance([
      { actor: 'alice', total_actions: 40 },
      { actor: 'bob', total_actions: 35 },
      { actor: 'carol', total_actions: 30 },
    ])
    expect(result.giniCoefficient).toBeLessThan(0.4)
    expect(result.isBalanced).toBe(true)
  })
})

describe('identifyCalibrationOutliers', () => {
  it('returns empty for fewer than 2 actors', () => {
    const result = identifyCalibrationOutliers([
      { actor: 'alice', total_actions: 50, alignment_rate: 0.9 },
    ])
    expect(result).toHaveLength(0)
  })

  it('returns empty when all actors have same alignment rate', () => {
    const result = identifyCalibrationOutliers([
      { actor: 'alice', total_actions: 50, alignment_rate: 0.8 },
      { actor: 'bob', total_actions: 50, alignment_rate: 0.8 },
      { actor: 'carol', total_actions: 50, alignment_rate: 0.8 },
    ])
    expect(result).toHaveLength(0)
  })

  it('identifies actors with alignment rate >1.5 std devs from mean', () => {
    const result = identifyCalibrationOutliers([
      { actor: 'alice', total_actions: 50, alignment_rate: 0.9 },
      { actor: 'bob', total_actions: 50, alignment_rate: 0.85 },
      { actor: 'carol', total_actions: 50, alignment_rate: 0.88 },
      { actor: 'dave', total_actions: 50, alignment_rate: 0.3 }, // outlier below
    ])
    expect(result.length).toBeGreaterThan(0)
    const daveOutlier = result.find((o) => o.actor === 'dave')
    expect(daveOutlier).toBeDefined()
    expect(daveOutlier!.direction).toBe('below')
  })

  it('flags both above and below outliers', () => {
    const result = identifyCalibrationOutliers([
      { actor: 'alice', total_actions: 50, alignment_rate: 1.0 }, // high outlier
      { actor: 'bob', total_actions: 50, alignment_rate: 0.5 },
      { actor: 'carol', total_actions: 50, alignment_rate: 0.5 },
      { actor: 'dave', total_actions: 50, alignment_rate: 0.5 },
      { actor: 'eve', total_actions: 50, alignment_rate: 0.0 }, // low outlier
    ])
    const above = result.filter((o) => o.direction === 'above')
    const below = result.filter((o) => o.direction === 'below')
    expect(above.length).toBeGreaterThanOrEqual(1)
    expect(below.length).toBeGreaterThanOrEqual(1)
  })
})
