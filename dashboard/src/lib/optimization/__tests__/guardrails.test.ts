import { describe, expect, it } from 'vitest'
import { evaluateOptimizationGuardrails } from '@/lib/optimization/guardrails'

describe('evaluateOptimizationGuardrails', () => {
  it('returns blocked decision when high-severity incidents are present', () => {
    const result = evaluateOptimizationGuardrails({
      supplementalMultiplier: 0.8,
      supplementalWarnings: ['ga4 unavailable'],
      queueMetrics: {
        total: 20,
        highImpactCount: 10,
        lowConfidenceHighImpactCount: 5,
      },
      roasMetrics: {
        total: 30,
        actionableCount: 6,
      },
      opportunityMetrics: {
        total: 10,
        highOverlapCount: 5,
      },
      audienceMetrics: {
        highPriorityCount: 1,
      },
      reportDate: '2026-02-20',
    })

    expect(result.decision.status).toBe('blocked')
    expect(result.incidents.some((incident) => incident.ruleId === 'opt_supplemental_confidence_degraded')).toBe(
      true
    )
    expect(result.incidents.some((incident) => incident.ruleId === 'opt_high_impact_low_confidence')).toBe(true)
  })

  it('returns hold decision for medium-risk concentration without high-severity blockers', () => {
    const result = evaluateOptimizationGuardrails({
      supplementalMultiplier: 0.93,
      supplementalWarnings: [],
      queueMetrics: {
        total: 30,
        highImpactCount: 12,
        lowConfidenceHighImpactCount: 2,
      },
      roasMetrics: {
        total: 30,
        actionableCount: 8,
      },
      opportunityMetrics: {
        total: 12,
        highOverlapCount: 5,
      },
      audienceMetrics: {
        highPriorityCount: 4,
      },
      reportDate: '2026-02-20',
    })

    expect(result.decision.status).toBe('hold')
    expect(result.incidents.some((incident) => incident.severity === 'medium')).toBe(true)
  })

  it('returns go decision when guardrail thresholds are healthy', () => {
    const result = evaluateOptimizationGuardrails({
      supplementalMultiplier: 1,
      supplementalWarnings: [],
      queueMetrics: {
        total: 30,
        highImpactCount: 15,
        lowConfidenceHighImpactCount: 1,
      },
      roasMetrics: {
        total: 25,
        actionableCount: 15,
      },
      opportunityMetrics: {
        total: 10,
        highOverlapCount: 1,
      },
      audienceMetrics: {
        highPriorityCount: 1,
      },
      reportDate: '2026-02-20',
    })

    expect(result.decision.status).toBe('go')
    expect(result.incidents).toHaveLength(0)
    expect(result.decision.confidence).toBeGreaterThanOrEqual(0.8)
  })
})
