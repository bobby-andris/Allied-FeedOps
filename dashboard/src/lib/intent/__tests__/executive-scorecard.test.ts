import { describe, expect, it } from 'vitest'
import {
  computeExecutiveScorecard,
  type ExecutiveScorecardInput,
} from '@/lib/intent/executive-scorecard'

describe('computeExecutiveScorecard', () => {
  const baseInput: ExecutiveScorecardInput = {
    totalRevenue: 50000,
    totalCost: 12000,
    totalConversions: 80,
    totalConversionsValue: 50000,
    periodDays: 30,
    decisionsTotal: 200,
    decisionsAutoApplied: 120,
    decisionsReviewed: 60,
    decisionsPending: 20,
    avgDecisionLatencyHours: 4.5,
    promotionCount: 15,
    demotionCount: 5,
    negativeCount: 10,
    holdCount: 170,
    guardrailStatus: 'go',
    openIncidentCount: 0,
  }

  it('computes ROAS from revenue and cost', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.roas).toBeCloseTo(50000 / 12000, 2)
  })

  it('computes CPA from cost and conversions', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.cpa).toBeCloseTo(12000 / 80, 2)
  })

  it('computes automation rate from auto-applied vs total', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.automationRate).toBeCloseTo(120 / 200, 4)
  })

  it('computes action breakdown percentages', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.actionBreakdown.promote).toBeCloseTo(15 / 200, 4)
    expect(result.actionBreakdown.demote).toBeCloseTo(5 / 200, 4)
    expect(result.actionBreakdown.negative).toBeCloseTo(10 / 200, 4)
    expect(result.actionBreakdown.hold).toBeCloseTo(170 / 200, 4)
  })

  it('includes decision latency in output', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.avgDecisionLatencyHours).toBe(4.5)
  })

  it('includes operational health summary', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.operationalHealth.guardrailStatus).toBe('go')
    expect(result.operationalHealth.openIncidentCount).toBe(0)
    expect(result.operationalHealth.healthGrade).toBe('healthy')
  })

  it('marks health as degraded when guardrails on hold', () => {
    const result = computeExecutiveScorecard({
      ...baseInput,
      guardrailStatus: 'hold',
      openIncidentCount: 2,
    })
    expect(result.operationalHealth.healthGrade).toBe('degraded')
  })

  it('marks health as critical when guardrails blocked', () => {
    const result = computeExecutiveScorecard({
      ...baseInput,
      guardrailStatus: 'blocked',
      openIncidentCount: 1,
    })
    expect(result.operationalHealth.healthGrade).toBe('critical')
  })

  it('handles zero cost gracefully for ROAS', () => {
    const result = computeExecutiveScorecard({ ...baseInput, totalCost: 0 })
    expect(result.roas).toBe(0)
  })

  it('handles zero conversions gracefully for CPA', () => {
    const result = computeExecutiveScorecard({ ...baseInput, totalConversions: 0 })
    expect(result.cpa).toBe(0)
  })

  it('handles zero decisions gracefully', () => {
    const result = computeExecutiveScorecard({
      ...baseInput,
      decisionsTotal: 0,
      decisionsAutoApplied: 0,
      decisionsReviewed: 0,
      decisionsPending: 0,
      promotionCount: 0,
      demotionCount: 0,
      negativeCount: 0,
      holdCount: 0,
    })
    expect(result.automationRate).toBe(0)
    expect(result.actionBreakdown.promote).toBe(0)
  })

  it('includes period context', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.periodDays).toBe(30)
  })

  it('computes pending review rate', () => {
    const result = computeExecutiveScorecard(baseInput)
    expect(result.pendingReviewRate).toBeCloseTo(20 / 200, 4)
  })
})
