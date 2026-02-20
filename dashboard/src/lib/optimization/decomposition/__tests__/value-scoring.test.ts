import { describe, expect, it } from 'vitest'
import {
  createValueScoringContext,
  scorePairValueWithContext,
} from '@/lib/optimization/decomposition/value-scoring'
import type { SearchTermSourceAssignment } from '@/lib/shopping-funnel/types'

function assignment(overrides: Partial<SearchTermSourceAssignment> = {}): SearchTermSourceAssignment {
  return {
    custom_label_0: 'Soap Dishes & Holders',
    source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
    source_tier: 'HIGH',
    impressions: 500,
    clicks: 25,
    cost_micros: 8_000_000,
    conversions: 2,
    conversions_value: 180,
    ...overrides,
  }
}

describe('value scoring calibration', () => {
  it('uses hierarchical priors to avoid zeroing expected value for sparse terms', () => {
    const historical = [
      assignment({ clicks: 120, conversions: 12, conversions_value: 1_200, cost_micros: 30_000_000 }),
      assignment({ clicks: 80, conversions: 6, conversions_value: 520, cost_micros: 16_000_000 }),
      assignment({
        custom_label_0: 'Wall Mounted Towel Bars',
        source_tier: 'LOW',
        clicks: 60,
        conversions: 7,
        conversions_value: 910,
        cost_micros: 14_000_000,
      }),
    ]

    const context = createValueScoringContext(historical)
    const sparse = assignment({ impressions: 300, clicks: 1, conversions: 0, conversions_value: 0, cost_micros: 450_000 })
    const scored = scorePairValueWithContext(sparse, sparse.custom_label_0, context)

    expect(scored.value.expected_cvr).toBeGreaterThan(0)
    expect(scored.value.expected_conversion_value).toBeGreaterThan(0)
    expect(scored.value.uncertainty).toBeGreaterThan(0.5)
    expect(scored.modelInputs).toHaveProperty('scoring_model', 'score_v1_calibrated')
  })

  it('adapts expected cvr when label-tier prior is strong', () => {
    const baseline = assignment({ source_tier: 'MEDIUM', clicks: 50, conversions: 2, conversions_value: 200 })
    const highCvrPeers = Array.from({ length: 4 }).map(() =>
      assignment({
        source_tier: 'MEDIUM',
        clicks: 100,
        conversions: 20,
        conversions_value: 2200,
        cost_micros: 25_000_000,
      })
    )

    const context = createValueScoringContext([baseline, ...highCvrPeers])
    const scored = scorePairValueWithContext(baseline, baseline.custom_label_0, context)

    const observedCvr = baseline.conversions / baseline.clicks
    expect(scored.value.expected_cvr).toBeGreaterThan(observedCvr)
  })

  it('reduces uncertainty for stronger click/conversion evidence', () => {
    const context = createValueScoringContext([
      assignment({ clicks: 160, conversions: 18, conversions_value: 2400, cost_micros: 40_000_000 }),
      assignment({ clicks: 120, conversions: 10, conversions_value: 1300, cost_micros: 28_000_000 }),
    ])

    const lowEvidence = assignment({ clicks: 4, conversions: 0, conversions_value: 0, impressions: 150 })
    const highEvidence = assignment({ clicks: 120, conversions: 14, conversions_value: 1600, impressions: 900 })

    const lowScore = scorePairValueWithContext(lowEvidence, lowEvidence.custom_label_0, context)
    const highScore = scorePairValueWithContext(highEvidence, highEvidence.custom_label_0, context)

    expect(highScore.value.uncertainty).toBeLessThan(lowScore.value.uncertainty)
  })
})

