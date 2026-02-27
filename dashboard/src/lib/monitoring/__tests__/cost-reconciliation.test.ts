import { describe, expect, it } from 'vitest'
import {
  buildUtcDailyWindows,
  classifyReconciliationDelta,
  computePercentile,
  runCostReconciliationCapture,
} from '@/lib/monitoring/cost-reconciliation'
import { vi } from 'vitest'

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

  it('surfaces explicit auth warning when OpenAI organization APIs return 403', async () => {
    process.env.OPENAI_USAGE_API_KEY = 'usage-key'
    process.env.OPENAI_ORG_ID = 'org_test'

    const originalFetch = global.fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
    } as Response)

    const rollups: Record<string, unknown>[] = []
    const fakeSupabase = {
      from(table: string) {
        if (table === 'regeneration_history') {
          return {
            select() {
              return this
            },
            gte() {
              return this
            },
            async lt() {
              return { data: [], error: null }
            },
          }
        }
        return {
          async upsert(payload: Record<string, unknown>) {
            rollups.push({ table, payload })
            return { error: null }
          },
        }
      },
    }

    try {
      const summary = await runCostReconciliationCapture({
        lookbackDays: 1,
        now: new Date('2026-02-28T12:00:00.000Z'),
        supabase: fakeSupabase as never,
      })

      const warnings = summary.capture_results[0]?.warnings ?? []
      expect(warnings.some((w) => w.includes('org-level key with organization usage/cost permissions'))).toBe(
        true
      )

      const deltaRows = rollups.filter((row) => row.table === 'cost_reconciliation_deltas')
      expect(deltaRows.length).toBe(1)
      const metadata = (deltaRows[0].payload as { metadata?: { warnings?: string[] } }).metadata
      expect(Array.isArray(metadata?.warnings)).toBe(true)
      expect(metadata?.warnings?.length).toBeGreaterThan(0)
    } finally {
      global.fetch = originalFetch
      delete process.env.OPENAI_USAGE_API_KEY
      delete process.env.OPENAI_ORG_ID
    }
  })
})
