import { describe, expect, it } from 'vitest'
import {
  buildUtcDailyWindows,
  classifyReconciliationDelta,
  computePercentile,
} from '@/lib/monitoring/cost-reconciliation'

describe('cost reconciliation helpers', () => {
  it('builds deterministic UTC windows', () => {
    const now = new Date('2026-02-28T15:45:00.000Z')
    const windows = buildUtcDailyWindows(2, now)

    expect(windows).toEqual([
      {
        startIso: '2026-02-26T00:00:00.000Z',
        endIso: '2026-02-27T00:00:00.000Z',
      },
      {
        startIso: '2026-02-27T00:00:00.000Z',
        endIso: '2026-02-28T00:00:00.000Z',
      },
    ])
  })

  it('flags out-of-tolerance deltas and retry amplification', () => {
    const classification = classifyReconciliationDelta({
      openaiTotalCostUsd: 12,
      internalTotalCostUsd: 8,
      openaiTotalRequests: 40,
      internalTotalRequests: 20,
      internalMissingCostRequests: 2,
      providerAttemptCountSum: 25,
      tolerance: 0.1,
    })

    expect(classification.status).toBe('attention')
    expect(classification.categories).toContain('out_of_tolerance')
    expect(classification.categories).toContain('internal_missing_cost_rows')
    expect(classification.categories).toContain('retry_amplification_detected')
    expect(classification.deltaCostUsd).toBe(4)
  })

  it('classifies missing OpenAI usage data distinctly', () => {
    const classification = classifyReconciliationDelta({
      openaiTotalCostUsd: null,
      internalTotalCostUsd: 1.2,
      openaiTotalRequests: 0,
      internalTotalRequests: 4,
      internalMissingCostRequests: 0,
      providerAttemptCountSum: 4,
    })

    expect(classification.status).toBe('missing_openai_data')
    expect(classification.categories).toContain('openai_usage_unavailable')
    expect(classification.categories).toContain('internal_only_activity')
    expect(classification.deltaRatio).toBeNull()
  })

  it('computes percentile for uneven distributions', () => {
    const value = computePercentile([10, 20, 30, 40], 0.95)
    expect(value).toBeCloseTo(38.5)
  })
})
