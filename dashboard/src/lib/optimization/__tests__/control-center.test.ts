import { describe, expect, it } from 'vitest'
import {
  buildOpportunityClusters,
  buildOpportunityLaunchBriefs,
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

  it('penalizes high-overlap clusters and exposes overlap risk metadata', () => {
    const terms: NeedsDecisionTerm[] = [
      {
        search_term: 'solid brass towel bar 24 inch',
        custom_label_0s: [
          {
            custom_label_0: 'Wall Mounted Towel Bars',
            source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - HIGH',
            source_tier: 'HIGH',
            impressions: 410,
            clicks: 32,
            cost_micros: 9800000,
            conversions: 3,
            conversions_value: 720,
          },
        ],
        intent_features: {
          product_object: 'towel bar',
          modifier_tokens: ['solid brass'],
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
          impact_score: 190,
          expected_clicks: 35,
          expected_cvr: 0.09,
          expected_conversion_value: 780,
          expected_profit_proxy: 310,
          uncertainty: 0.16,
        },
      },
      {
        search_term: 'bathroom holder shelf combo',
        custom_label_0s: [
          {
            custom_label_0: 'Soap Dishes & Holders',
            source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
            source_tier: 'HIGH',
            impressions: 390,
            clicks: 31,
            cost_micros: 12000000,
            conversions: 2,
            conversions_value: 420,
          },
          {
            custom_label_0: 'Baskets',
            source_campaign: 'AVD - Shopping - US - baskets - HIGH',
            source_tier: 'HIGH',
            impressions: 390,
            clicks: 31,
            cost_micros: 12000000,
            conversions: 2,
            conversions_value: 420,
          },
        ],
        intent_features: {
          product_object: 'holder',
          modifier_tokens: ['combo'],
          use_case_tokens: ['bathroom'],
          is_branded: false,
          is_competitor: false,
          has_mismatch_risk: true,
        },
        recommendation: {
          action_type: 'funnel',
          default_tier: 'medium',
          confidence: 0.58,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 220,
          expected_clicks: 37,
          expected_cvr: 0.05,
          expected_conversion_value: 480,
          expected_profit_proxy: 190,
          uncertainty: 0.52,
        },
      },
    ]

    const clusters = buildOpportunityClusters(terms)

    expect(clusters).toHaveLength(2)
    expect(clusters[0].clusterKey).toBe('towel bar')
    expect(clusters[1].overlapRiskLevel).toBe('high')
    expect(clusters[1].overlapRiskScore).toBeGreaterThan(clusters[0].overlapRiskScore)
  })
})

describe('buildOpportunityLaunchBriefs', () => {
  it('generates pilot-ready launch briefs with overlap controls and measurable success criteria', () => {
    const terms: NeedsDecisionTerm[] = [
      {
        search_term: 'solid brass towel bar 24 inch',
        custom_label_0s: [
          {
            custom_label_0: 'Wall Mounted Towel Bars',
            source_campaign: 'AVD - Shopping - US - Wall Mounted Towel Bars - HIGH',
            source_tier: 'HIGH',
            impressions: 410,
            clicks: 32,
            cost_micros: 9800000,
            conversions: 3,
            conversions_value: 720,
          },
        ],
        intent_features: {
          product_object: 'towel bar',
          modifier_tokens: ['solid brass'],
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
          impact_score: 190,
          expected_clicks: 35,
          expected_cvr: 0.09,
          expected_conversion_value: 780,
          expected_profit_proxy: 310,
          uncertainty: 0.16,
        },
      },
    ]

    const briefs = buildOpportunityLaunchBriefs(buildOpportunityClusters(terms), { accountMedianRoas: 3.2 })

    expect(briefs).toHaveLength(1)
    expect(briefs[0].clusterKey).toBe('towel bar')
    expect(briefs[0].pilotName.toLowerCase()).toContain('pilot')
    expect(briefs[0].negativeControls.length).toBeGreaterThan(0)
    expect(briefs[0].successCriteria.targetRoas).toBeGreaterThan(3)
    expect(briefs[0].budgetCapUsd).toBeGreaterThan(0)
    expect(briefs[0].stopConditions.length).toBeGreaterThan(0)
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

  it('holds recommendation and flags insufficient evidence when traffic/conversions are too low', () => {
    const rows: LabelTierPerformanceRow[] = [
      {
        customLabel0: 'Wall Mounted Guest Towel Holder',
        tier: 'MEDIUM',
        spend: 25,
        conversionValue: 400,
        conversions: 1,
        clicks: 18,
      },
    ]

    const recommendations = buildRoasRecommendations(rows)
    expect(recommendations).toHaveLength(1)
    expect(recommendations[0].direction).toBe('hold')
    expect(recommendations[0].recommendedTargetRoas).toBe(3.1)
    expect(recommendations[0].rationale.toLowerCase()).toContain('insufficient')
    expect(recommendations[0].guardrailStatus).toBe('insufficient_data')
  })

  it('caps adaptive tROAS step changes to 10% even for extreme ROAS gaps', () => {
    const rows: LabelTierPerformanceRow[] = [
      {
        customLabel0: 'Soap Dispensers',
        tier: 'HIGH',
        spend: 900,
        conversionValue: 270,
        conversions: 11,
        clicks: 710,
      },
    ]

    const recommendations = buildRoasRecommendations(rows)
    expect(recommendations).toHaveLength(1)
    expect(recommendations[0].direction).toBe('increase')
    expect(recommendations[0].recommendedTargetRoas).toBe(3.96)
    expect(recommendations[0].appliedStepPct).toBeCloseTo(0.1, 4)
    expect(recommendations[0].maxAllowedStepPct).toBeCloseTo(0.1, 4)
  })
})

describe('query intelligence regressions', () => {
  it('prioritizes recommendation queue by profit-weighted certainty score', () => {
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
          impact_score: 280,
          expected_clicks: 4,
          expected_cvr: 0,
          expected_conversion_value: 0,
          expected_profit_proxy: 45,
          uncertainty: 0.94,
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
          impact_score: 170,
          expected_clicks: 44,
          expected_cvr: 0.1,
          expected_conversion_value: 900,
          expected_profit_proxy: 220,
          uncertainty: 0.22,
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

  it('applies supplemental confidence gates without changing core queue ranking', () => {
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
            cost_micros: 19_260_000,
            conversions: 0,
            conversions_value: 0,
          },
        ],
        recommendation: {
          action_type: 'funnel',
          default_tier: 'high',
          confidence: 0.8,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 80,
          expected_clicks: 4,
          expected_cvr: 0,
          expected_conversion_value: 0,
          expected_profit_proxy: 40,
          uncertainty: 0.9,
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
            cost_micros: 12_000_000,
            conversions: 4,
            conversions_value: 800,
          },
        ],
        recommendation: {
          action_type: 'funnel',
          default_tier: 'low',
          confidence: 0.9,
          reason_codes: ['performance_weighted_tiering'],
        },
        value_score: {
          impact_score: 170,
          expected_clicks: 44,
          expected_cvr: 0.1,
          expected_conversion_value: 900,
          expected_profit_proxy: 220,
          uncertainty: 0.22,
        },
      },
    ]

    const queue = buildRecommendationQueue(terms, 10, {
      supplementalGate: {
        multiplier: 0.82,
        reasons: ['ga4_attribution_high_risk', 'shopify_low_sku_label_coverage'],
      },
    })

    expect(queue).toHaveLength(2)
    expect(queue[0].searchTerm).toBe('wall mounted towel bar brass')
    expect(queue[0].baseConfidence).toBeCloseTo(0.9, 4)
    expect(queue[0].confidence).toBeCloseTo(0.738, 4)
    expect(queue[0].confidenceMultiplier).toBeCloseTo(0.82, 4)
    expect(queue[0].confidenceAdjustmentReasons).toContain('ga4_attribution_high_risk')
  })
})
