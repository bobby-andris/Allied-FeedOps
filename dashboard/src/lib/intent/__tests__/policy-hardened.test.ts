import { describe, expect, it } from 'vitest'
import {
  routeIntentDecision,
  evaluatePromotionDemotion,
  recommendBidPolicy,
} from '@/lib/intent/policy'

describe('policy functions with dirty inputs (hardening)', () => {
  it('routeIntentDecision handles NaN metrics without throwing', () => {
    const decision = routeIntentDecision({
      searchTerm: 'brass towel bar 24 inch',
      metrics: {
        impressions: NaN,
        clicks: 100,
        conversions: 5,
        conversionsValue: 800,
        costMicros: 200000000,
      },
      attributionQualityScore: 0.85,
    })
    expect(decision.classification.intentClass).toBe('PRODUCT_HIGH')
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
    expect(decision.confidence).toBeLessThanOrEqual(1)
  })

  it('routeIntentDecision handles negative metrics gracefully', () => {
    const decision = routeIntentDecision({
      searchTerm: 'bathroom robe hook chrome',
      metrics: {
        impressions: -100,
        clicks: -50,
        conversions: -1,
        conversionsValue: -200,
        costMicros: -100000000,
      },
    })
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
    expect(decision.confidence).toBeLessThanOrEqual(1)
  })

  it('routeIntentDecision clamps out-of-range scores', () => {
    const decision = routeIntentDecision({
      searchTerm: 'polished nickel soap dish',
      metrics: {
        impressions: 500,
        clicks: 80,
        conversions: 4,
        conversionsValue: 700,
        costMicros: 160000000,
      },
      attributionQualityScore: 5.0,
      valueSignalScore: -1.0,
    })
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
    expect(decision.confidence).toBeLessThanOrEqual(1)
  })

  it('evaluatePromotionDemotion handles Infinity metrics', () => {
    const decision = evaluatePromotionDemotion({
      searchTerm: 'wall mount towel bar',
      currentTier: 'low',
      metrics: {
        impressions: Infinity,
        clicks: 100,
        conversions: 5,
        conversionsValue: 800,
        costMicros: Infinity,
      },
      confidence: 0.8,
      marginRoas: 4,
    })
    expect(decision.action).toBeDefined()
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
    expect(decision.confidence).toBeLessThanOrEqual(1)
  })

  it('recommendBidPolicy handles NaN ROAS values', () => {
    const decision = recommendBidPolicy({
      key: 'Towel Bars|high',
      channel: 'shopping',
      intentClass: 'PRODUCT_HIGH',
      currentTargetRoas: NaN,
      observedRoas: NaN,
      confidence: 0.8,
      attributionQualityScore: 0.9,
    })
    expect(decision.action).toBe('hold')
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
  })

  it('recommendBidPolicy handles negative CPA values', () => {
    const decision = recommendBidPolicy({
      key: 'Robe Hooks|medium',
      channel: 'search',
      intentClass: 'CATEGORY_MID',
      targetMode: 'cpa',
      currentTargetCpa: -40,
      observedCpa: -20,
      confidence: 0.85,
      attributionQualityScore: 0.92,
    })
    expect(decision.action).toBe('hold')
    expect(decision.confidence).toBeGreaterThanOrEqual(0)
  })
})
