import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/optimization/decomposition/health/route'

const mocks = vi.hoisted(() => ({
  getNeedsDecisionTerms: vi.fn(),
  computeCoverageStats: vi.fn(),
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: () => ({ startDate: '2026-02-01', endDate: '2026-02-20' }),
  sanitizeDateInput: (value: string | null | undefined) => value ?? undefined,
  sanitizeCustomLabel: (value: string | null | undefined) => value ?? undefined,
  sanitizeMinImpressions: () => 0,
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
}))

vi.mock('@/lib/optimization/decomposition/repository', () => ({
  computeCoverageStats: mocks.computeCoverageStats,
}))

describe('GET /api/optimization/decomposition/health', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.getNeedsDecisionTerms.mockResolvedValue({
      terms: [
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
            confidence: 0.58,
            reason_codes: ['performance_weighted_tiering'],
          },
        },
      ],
      date_window: {
        startDate: '2026-02-01',
        endDate: '2026-02-20',
      },
      generated_at: '2026-02-20T00:00:00.000Z',
      pipeline: {
        enabled: true,
        parser_version: 'decomp_v1',
        score_version: 'score_v1',
        recommendation_version: 'route_v1',
        stale_threshold_hours: 24,
        pairs_total: 1,
        pairs_cached: 1,
        pairs_recomputed: 0,
        warnings: [],
        latest_artifact_created_at: '2026-02-20T00:00:00.000Z',
      },
    })

    mocks.computeCoverageStats.mockResolvedValue({
      totalPairs: 1,
      cachedPairs: 1,
      missingPairs: 0,
      stalePairs: 0,
      staleShare: 0,
      coveragePercent: 100,
      latestCreatedAt: '2026-02-20T00:00:00.000Z',
      details: [],
    })
  })

  it('returns coverage and confidence diagnostics', async () => {
    const request = new NextRequest('http://localhost/api/optimization/decomposition/health?limit=100')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.coverage.total_pairs).toBe(1)
    expect(body.coverage.coverage_percent).toBe(100)
    expect(body.confidence_distribution.low).toBe(1)
    expect(body.low_confidence_terms[0].search_term).toBe('soap dishes for shower')
    expect(body.pipeline.parser_version).toBe('decomp_v1')
  })
})
