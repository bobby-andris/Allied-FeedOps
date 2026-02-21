import { describe, expect, it } from 'vitest'
import {
  calculateLagAdjustedROAS,
  buildMarginAdjustedDecision,
} from '@/lib/intent/profit-forecast'
import type { TermMetrics, PromotionDemotionDecision } from '@/lib/intent/types'
import type { ProfitSignals } from '@/lib/intent/profit-forecast'

function makeMetrics(overrides?: Partial<TermMetrics>): TermMetrics {
  return {
    impressions: 500,
    clicks: 150,
    conversions: 8,
    conversionsValue: 2000,
    costMicros: 500_000_000, // $500
    ...overrides,
  }
}

function makeDecision(
  action: PromotionDemotionDecision['action']
): PromotionDemotionDecision {
  return {
    searchTerm: 'test term',
    action,
    confidence: 0.8,
    reasonCodes: ['test_reason'],
    policyVersion: 'intent_v1',
  }
}

describe('calculateLagAdjustedROAS', () => {
  it('computes ROAS with COGS deduction', () => {
    // Revenue: $2000, COGS: 35% ($700), Returns: 0%
    // Net revenue: $2000 - $700 = $1300
    // Lag factor default: 1.12 → $1300 * 1.12 = $1456
    // Spend: $500 → ROAS = $1456 / $500 = 2.912
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0.35, 0)
    expect(roas).toBeCloseTo(2.912, 2)
  })

  it('computes ROAS with return rate adjustment', () => {
    // Revenue: $2000, COGS: 0%, Returns: 10% ($200)
    // Net revenue: $2000 * 0.90 - 0 = $1800
    // Lag factor: 1.12 → $1800 * 1.12 = $2016
    // Spend: $500 → ROAS = $2016 / $500 = 4.032
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0, 0.10)
    expect(roas).toBeCloseTo(4.032, 2)
  })

  it('computes ROAS with both COGS and returns', () => {
    // Revenue: $2000, COGS: 30% ($600), Returns: 8% ($160 off top)
    // Net revenue: $2000 * (1 - 0.08) - $2000 * 0.30 = $1840 - $600 = $1240
    // Lag factor: 1.12 → $1240 * 1.12 = $1388.8
    // Spend: $500 → ROAS = $1388.8 / $500 = 2.7776
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0.30, 0.08)
    expect(roas).toBeCloseTo(2.7776, 2)
  })

  it('applies custom lag days factor', () => {
    // Revenue: $2000, COGS: 0%, Returns: 0%
    // Net revenue: $2000
    // lagDays=14: factor = 1 + (0.12) * (14/7) = 1.24
    // Lag adjusted: $2000 * 1.24 = $2480
    // Spend: $500 → ROAS = $2480 / $500 = 4.96
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0, 0, 14)
    expect(roas).toBeCloseTo(4.96, 2)
  })

  it('applies zero lag days (no lag adjustment)', () => {
    // lagDays=0: factor = 1 + 0.12 * 0 = 1.0
    // Net revenue: $2000 * 1.0 = $2000
    // ROAS = $2000 / $500 = 4.0
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0, 0, 0)
    expect(roas).toBeCloseTo(4.0, 2)
  })

  it('returns 0 when spend is zero', () => {
    const roas = calculateLagAdjustedROAS(makeMetrics({ costMicros: 0 }), 0.35, 0.05)
    expect(roas).toBe(0)
  })

  it('returns negative ROAS when COGS+returns exceed revenue', () => {
    // COGS 80% + returns 30% = 110% of revenue consumed
    const roas = calculateLagAdjustedROAS(makeMetrics(), 0.80, 0.30)
    expect(roas).toBeLessThan(0)
  })
})

describe('buildMarginAdjustedDecision', () => {
  const profitSignals: ProfitSignals = {
    cogsRate: 0.35,
    returnRate: 0.05,
    dataAge: 2,
  }

  it('downgrades promote_to_high when margin-adjusted ROAS below floor', () => {
    // With 35% COGS + 5% returns on $2000 revenue / $500 spend:
    // Net = $2000 * 0.95 - $2000 * 0.35 = $1900 - $700 = $1200
    // Lag: $1200 * 1.12 = $1344 → ROAS = 2.688
    // Floor for promote_to_high = 3.6 → should downgrade
    const decision = makeDecision('promote_to_high')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.marginDowngraded).toBe(true)
    expect(result.action).toBe('hold')
    expect(result.originalAction).toBe('promote_to_high')
    expect(result.reasonCodes).toContain('margin_adjusted_below_floor')
    expect(result.profitAdjustedRoas).toBeLessThan(3.6)
  })

  it('downgrades promote_to_medium when margin-adjusted ROAS below floor', () => {
    // Same metrics, floor for promote_to_medium = 3.1
    // ROAS = 2.688 < 3.1 → downgrade
    const decision = makeDecision('promote_to_medium')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.marginDowngraded).toBe(true)
    expect(result.action).toBe('hold')
    expect(result.originalAction).toBe('promote_to_medium')
  })

  it('keeps promote_to_high when margin-adjusted ROAS is above floor', () => {
    // High revenue: $5000 / $500 spend
    // Net = $5000 * 0.95 - $5000 * 0.35 = $4750 - $1750 = $3000
    // Lag: $3000 * 1.12 = $3360 → ROAS = 6.72
    // Floor = 3.6 → above floor, no downgrade
    const decision = makeDecision('promote_to_high')
    const highRevenueMetrics = makeMetrics({ conversionsValue: 5000 })
    const result = buildMarginAdjustedDecision(decision, profitSignals, highRevenueMetrics)

    expect(result.marginDowngraded).toBe(false)
    expect(result.action).toBe('promote_to_high')
    expect(result.originalAction).toBe('promote_to_high')
  })

  it('does not downgrade hold actions', () => {
    const decision = makeDecision('hold')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.marginDowngraded).toBe(false)
    expect(result.action).toBe('hold')
  })

  it('does not downgrade demote actions', () => {
    const decision = makeDecision('demote_to_low')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.marginDowngraded).toBe(false)
    expect(result.action).toBe('demote_to_low')
  })

  it('does not downgrade negative actions', () => {
    const decision = makeDecision('negative')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.marginDowngraded).toBe(false)
    expect(result.action).toBe('negative')
  })

  it('includes profitAdjustedRoas in result', () => {
    const decision = makeDecision('hold')
    const result = buildMarginAdjustedDecision(decision, profitSignals, makeMetrics())

    expect(result.profitAdjustedRoas).toBeDefined()
    expect(typeof result.profitAdjustedRoas).toBe('number')
  })
})
