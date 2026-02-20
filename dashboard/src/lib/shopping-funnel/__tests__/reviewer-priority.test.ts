import { describe, expect, it } from 'vitest'
import {
  computeReviewerPriorityScore,
  isHighImpactValueScore,
} from '@/lib/shopping-funnel/reviewer-priority'
import type { QueryValueScore } from '@/lib/shopping-funnel/types'

describe('reviewer priority helpers', () => {
  it('weights expected profit proxy by certainty for reviewer priority', () => {
    const lowCertaintyHighImpact: QueryValueScore = {
      impact_score: 300,
      expected_clicks: 20,
      expected_cvr: 0.02,
      expected_conversion_value: 120,
      expected_profit_proxy: 60,
      uncertainty: 0.9,
    }

    const highCertaintyProfit: QueryValueScore = {
      impact_score: 180,
      expected_clicks: 35,
      expected_cvr: 0.05,
      expected_conversion_value: 500,
      expected_profit_proxy: 220,
      uncertainty: 0.2,
    }

    expect(computeReviewerPriorityScore(highCertaintyProfit)).toBeGreaterThan(
      computeReviewerPriorityScore(lowCertaintyHighImpact)
    )
  })

  it('treats rows as high impact only when priority and uncertainty thresholds are met', () => {
    const candidate: QueryValueScore = {
      impact_score: 95,
      expected_clicks: 14,
      expected_cvr: 0.08,
      expected_conversion_value: 410,
      expected_profit_proxy: 160,
      uncertainty: 0.32,
    }

    expect(
      isHighImpactValueScore(candidate, {
        minPriorityScore: 60,
        maxUncertainty: 0.4,
      })
    ).toBe(true)

    expect(
      isHighImpactValueScore(candidate, {
        minPriorityScore: 200,
        maxUncertainty: 0.4,
      })
    ).toBe(false)

    expect(
      isHighImpactValueScore(candidate, {
        minPriorityScore: 60,
        maxUncertainty: 0.2,
      })
    ).toBe(false)
  })
})
