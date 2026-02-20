import { describe, expect, it } from 'vitest'
import {
  buildOpportunityClusters,
  buildQueryScoreSummary,
  buildRecommendationQueue,
  buildRoasRecommendations,
  type LabelTierPerformanceRow,
} from '@/lib/optimization/control-center'
import type { NeedsDecisionTerm } from '@/lib/shopping-funnel/types'

describe('buildOpportunityClusters', () => {
  it('groups high-opportunity terms by detected product object and ranks by attractiveness', () => {
    const terms: NeedsDecisionTerm[] = [
      {
        search_term: 'wall mounted towel bar brass',
        custom_label_0s: [
          {
            custom_label_0: 'Wall Mounted Towel Bars',
            source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - HIGH',
            source_tier: 'HIGH',
            impressions: 500,
            clicks: 40,
            cost_micros: 12000000,
            conversions: 4,
            conversions_value: 800,
          },
        ],
        intent_features: {
          product_object: 'towel bar',
          modifier_tokens: ['wall mount', 'brass'],
          use_case_tokens: ['bathroom'],
          is_branded: false,
          is_competitor: false,
          has_mismatch_risk: false,
        },
        recommendation: {
          action_type: 'funnel',
          default_tier: 'low',
          confidence: 0.82,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 210,
          expected_clicks: 44,
          expected_cvr: 0.1,
          expected_conversion_value: 900,
          expected_profit_proxy: 450,
          uncertainty: 0.18,
        },
      },
      {
        search_term: 'black towel bar wall mount',
        custom_label_0s: [
          {
            custom_label_0: 'Wall Mounted Towel Bars',
            source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - MEDIUM',
            source_tier: 'MEDIUM',
            impressions: 380,
            clicks: 31,
            cost_micros: 9500000,
            conversions: 3,
            conversions_value: 560,
          },
        ],
        intent_features: {
          product_object: 'towel bar',
          modifier_tokens: ['wall mount'],
          use_case_tokens: ['bathroom'],
          is_branded: false,
          is_competitor: false,
          has_mismatch_risk: false,
        },
        recommendation: {
          action_type: 'funnel',
          default_tier: 'medium',
          confidence: 0.74,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 170,
          expected_clicks: 33,
          expected_cvr: 0.096,
          expected_conversion_value: 610,
          expected_profit_proxy: 300,
          uncertainty: 0.24,
        },
      },
    ]

    const clusters = buildOpportunityClusters(terms)

    expect(clusters.length).toBeGreaterThan(0)
    expect(clusters[0]?.clusterKey).toBe('towel bar')
    expect(clusters[0]?.termCount).toBe(2)
    expect(clusters[0]?.attractivenessScore).toBeGreaterThan(0)
  })
})

describe('buildRoasRecommendations', () => {
  it('recommends lower target when observed ROAS is materially above baseline target', () => {
    const rows: LabelTierPerformanceRow[] = [
      {
        customLabel0: 'Wall Mounted Towel Bars',
        tier: 'HIGH',
        spend: 1000,
        conversionValue: 5000,
        conversions: 50,
        clicks: 800,
      },
    ]

    const recommendations = buildRoasRecommendations(rows)
    expect(recommendations.length).toBe(1)
    expect(recommendations[0].currentTargetRoas).toBe(3.6)
    expect(recommendations[0].recommendedTargetRoas).toBeLessThan(3.6)
    expect(recommendations[0].direction).toBe('decrease')
  })

  it('recommends higher target when observed ROAS is materially below baseline target', () => {
    const rows: LabelTierPerformanceRow[] = [
      {
        customLabel0: 'Soap Dishes & Holders',
        tier: 'LOW',
        spend: 1400,
        conversionValue: 1700,
        conversions: 12,
        clicks: 920,
      },
    ]

    const recommendations = buildRoasRecommendations(rows)
    expect(recommendations.length).toBe(1)
    expect(recommendations[0].currentTargetRoas).toBe(2.6)
    expect(recommendations[0].recommendedTargetRoas).toBeGreaterThan(2.6)
    expect(recommendations[0].direction).toBe('increase')
  })
})

describe('query intelligence regressions', () => {
  it('keeps recommendation queue ordering stable by impact score', () => {
    const terms: NeedsDecisionTerm[] = [
      {
        search_term: 'soap dishes for shower',
        custom_label_0s: [
          {
            custom_label_0: 'Soap Dishes & Holders',
            source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
            source_tier: 'HIGH',
            impressions: 56,
            clicks: 4,
            cost_micros: 19260000,
            conversions: 0,
            conversions_value: 0,
          },
        ],
        recommendation: {
          action_type: 'funnel',
          default_tier: 'high',
          confidence: 0.58,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 12,
          expected_clicks: 4,
          expected_cvr: 0,
          expected_conversion_value: 0,
          expected_profit_proxy: -19.26,
          uncertainty: 0.92,
        },
      },
      {
        search_term: 'wall mounted towel bar brass',
        custom_label_0s: [
          {
            custom_label_0: 'Wall Mounted Towel Bars',
            source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - MEDIUM',
            source_tier: 'MEDIUM',
            impressions: 500,
            clicks: 40,
            cost_micros: 12000000,
            conversions: 4,
            conversions_value: 800,
          },
        ],
        recommendation: {
          action_type: 'funnel',
          default_tier: 'low',
          confidence: 0.82,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 210,
          expected_clicks: 44,
          expected_cvr: 0.1,
          expected_conversion_value: 900,
          expected_profit_proxy: 450,
          uncertainty: 0.18,
        },
      },
    ]

    const queue = buildRecommendationQueue(terms, 10)

    expect(queue).toHaveLength(2)
    expect(queue[0].searchTerm).toBe('wall mounted towel bar brass')
    expect(queue[1].searchTerm).toBe('soap dishes for shower')
  })

  it('keeps score summary numerically consistent', () => {
    const terms: NeedsDecisionTerm[] = [
      {
        search_term: 'term one',
        custom_label_0s: [
          {
            custom_label_0: 'Soap Dishes & Holders',
            source_campaign: 'A',
            source_tier: 'HIGH',
            impressions: 100,
            clicks: 10,
            cost_micros: 1000000,
            conversions: 1,
            conversions_value: 50,
          },
        ],
        value_score: {
          impact_score: 100,
          expected_clicks: 10,
          expected_cvr: 0.1,
          expected_conversion_value: 50,
          expected_profit_proxy: 40,
          uncertainty: 0.1,
        },
      },
      {
        search_term: 'term two',
        custom_label_0s: [
          {
            custom_label_0: 'Soap Dishes & Holders',
            source_campaign: 'B',
            source_tier: 'HIGH',
            impressions: 200,
            clicks: 20,
            cost_micros: 2000000,
            conversions: 2,
            conversions_value: 80,
          },
        ],
        value_score: {
          impact_score: 50,
          expected_clicks: 20,
          expected_cvr: 0.1,
          expected_conversion_value: 80,
          expected_profit_proxy: 30,
          uncertainty: 0.2,
        },
      },
    ]

    const summary = buildQueryScoreSummary(terms)

    expect(summary.termCount).toBe(2)
    expect(summary.avgImpactScore).toBe(75)
    expect(summary.avgExpectedProfitProxy).toBe(35)
    expect(summary.avgUncertainty).toBe(0.15)
    expect(summary.topImpactTerms[0]).toEqual({ searchTerm: 'term one', impactScore: 100 })
  })
})
