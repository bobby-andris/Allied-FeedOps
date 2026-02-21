import { describe, expect, it } from 'vitest'
import {
  evaluateShoppingToSearchGraduation,
  evaluateGuardrails,
  evaluatePromotionDemotion,
  evaluateSearchGovernance,
  recommendBidPolicy,
  routeIntentDecision,
} from '@/lib/intent/policy'
import { classifyIntent } from '@/lib/intent/taxonomy'

describe('classifyIntent', () => {
  it('classifies brand queries as BRAND_CORE', () => {
    const result = classifyIntent('Allied Brass towel bar')
    expect(result.intentClass).toBe('BRAND_CORE')
    expect(result.isBranded).toBe(true)
  })

  it('classifies competitor queries as COMPETITOR', () => {
    const result = classifyIntent('signature hardware towel ring alternative')
    expect(result.intentClass).toBe('COMPETITOR')
    expect(result.isCompetitor).toBe(true)
  })
})

describe('routeIntentDecision', () => {
  it('routes high intent product terms to funnel high tier', () => {
    const decision = routeIntentDecision({
      searchTerm: '24 inch brass towel bar wall mount',
      metrics: {
        impressions: 400,
        clicks: 120,
        conversions: 8,
        conversionsValue: 1600,
        costMicros: 420000000,
      },
      attributionQualityScore: 0.8,
    })

    expect(decision.routeAction).toBe('funnel')
    expect(decision.recommendedTier).toBe('high')
    expect(decision.classification.intentClass).toBe('PRODUCT_HIGH')
  })

  it('routes mismatch terms to global block', () => {
    const decision = routeIntentDecision({
      searchTerm: 'bathroom contractor near me job',
      metrics: {
        impressions: 300,
        clicks: 100,
        conversions: 0,
        conversionsValue: 0,
        costMicros: 180000000,
      },
    })

    expect(decision.routeAction).toBe('global_block')
    expect(decision.classification.intentClass).toBe('MISMATCH')
  })

  it('uses value signal score to calibrate route confidence', () => {
    const baseInput = {
      searchTerm: '24 inch brass towel bar wall mount',
      metrics: {
        impressions: 500,
        clicks: 130,
        conversions: 7,
        conversionsValue: 1500,
        costMicros: 410000000,
      },
      attributionQualityScore: 0.82,
    }

    const lowValueSignal = routeIntentDecision({
      ...baseInput,
      valueSignalScore: 0.2,
    })

    const highValueSignal = routeIntentDecision({
      ...baseInput,
      valueSignalScore: 0.9,
    })

    expect(lowValueSignal.confidence).toBeLessThan(highValueSignal.confidence)
  })
})

describe('evaluatePromotionDemotion', () => {
  it('promotes low to medium when thresholds are met', () => {
    const decision = evaluatePromotionDemotion({
      searchTerm: 'brass wall mounted towel bar',
      currentTier: 'low',
      metrics: {
        impressions: 1000,
        clicks: 100,
        conversions: 6,
        conversionsValue: 1000,
        costMicros: 200000000,
      },
      confidence: 0.8,
      marginRoas: 4,
    })

    expect(decision.action).toBe('promote_to_medium')
  })

  it('negatives high spend zero conversion terms', () => {
    const decision = evaluatePromotionDemotion({
      searchTerm: 'cheap bathroom fixture',
      currentTier: 'medium',
      metrics: {
        impressions: 2000,
        clicks: 300,
        conversions: 0,
        conversionsValue: 0,
        costMicros: 35000000,
      },
      confidence: 0.7,
    })

    expect(decision.action).toBe('negative')
  })
})

describe('evaluateSearchGovernance', () => {
  it('promotes broad to phrase when minimum performance is met', () => {
    const classification = classifyIntent('wall mounted brass towel bar')
    const decision = evaluateSearchGovernance({
      searchTerm: 'wall mounted brass towel bar',
      currentTier: 'broad',
      metrics: {
        impressions: 1200,
        clicks: 150,
        conversions: 3,
        conversionsValue: 700,
        costMicros: 160000000,
      },
      classification,
      confidence: 0.65,
    })

    expect(decision.action).toBe('promote_to_phrase')
    expect(decision.recommendedTier).toBe('phrase')
  })
})

describe('recommendBidPolicy', () => {
  it('holds when confidence gate is not met', () => {
    const decision = recommendBidPolicy({
      key: 'Wall Mounted Towel Bars|high',
      channel: 'shopping',
      intentClass: 'PRODUCT_HIGH',
      currentTargetRoas: 3.6,
      observedRoas: 5,
      confidence: 0.4,
      attributionQualityScore: 0.9,
    })

    expect(decision.action).toBe('hold')
    expect(decision.recommendedTargetRoas).toBe(3.6)
  })

  it('supports CPA mode with bounded decreases on over-performance', () => {
    const decision = recommendBidPolicy({
      key: 'Wall Mounted Towel Bars|medium',
      channel: 'search',
      intentClass: 'CATEGORY_MID',
      targetMode: 'cpa',
      currentTargetCpa: 40,
      observedCpa: 28,
      confidence: 0.85,
      attributionQualityScore: 0.92,
    })

    expect(decision.action).toBe('decrease_target')
    expect(decision.recommendedTargetCpa).toBeGreaterThanOrEqual(36)
    expect(decision.recommendedTargetCpa).toBeLessThanOrEqual(40)
  })
})

describe('evaluateShoppingToSearchGraduation', () => {
  it('recommends exact graduation for high-intent profitable terms', () => {
    const classification = classifyIntent('24 inch brass towel bar wall mount')
    const decision = evaluateShoppingToSearchGraduation({
      searchTerm: '24 inch brass towel bar wall mount',
      classification,
      metrics: {
        impressions: 2200,
        clicks: 220,
        conversions: 8,
        conversionsValue: 1700,
        costMicros: 320000000,
      },
      confidence: 0.82,
      alreadyCoveredInSearch: false,
    })

    expect(decision.eligible).toBe(true)
    expect(decision.suggestedTier).toBe('exact')
  })

  it('blocks graduation when already covered in search', () => {
    const classification = classifyIntent('bathroom towel ring brass')
    const decision = evaluateShoppingToSearchGraduation({
      searchTerm: 'bathroom towel ring brass',
      classification,
      metrics: {
        impressions: 1400,
        clicks: 160,
        conversions: 5,
        conversionsValue: 900,
        costMicros: 280000000,
      },
      confidence: 0.76,
      alreadyCoveredInSearch: true,
    })

    expect(decision.eligible).toBe(false)
    expect(decision.suggestedTier).toBeNull()
  })
})

describe('evaluateGuardrails', () => {
  it('returns blocked when critical incidents are active', () => {
    const decision = evaluateGuardrails({
      recentSpend: 12000,
      recentRevenue: 9000,
      baselineSpend: 8000,
      baselineRevenue: 10000,
      attributionQualityScore: 0.4,
      staleDataHours: 30,
      openCriticalIncidents: 1,
      openHighIncidents: 2,
    })

    expect(decision.status).toBe('blocked')
    expect(decision.incidents.length).toBeGreaterThan(0)
  })
})
