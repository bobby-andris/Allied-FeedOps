import { describe, expect, it } from 'vitest'
import {
  buildOpportunityClusters,
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

  it('zero-conversion rows always recommend increase (constrain bidding)', () => {
    const rows: LabelTierPerformanceRow[] = [
      {
        customLabel0: 'Grab Bars',
        tier: 'LOW',
        spend: 200,
        conversionValue: 0,
        conversions: 0,
        clicks: 150,
      },
    ]

    const recommendations = buildRoasRecommendations(rows)
    expect(recommendations.length).toBe(1)
    expect(recommendations[0].direction).toBe('increase')
    expect(recommendations[0].observedRoas).toBe(0)
    expect(recommendations[0].rationale).toContain('zero conversions')
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

