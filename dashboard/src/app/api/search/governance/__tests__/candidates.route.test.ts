import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/search/governance/candidates/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  defaultDateWindow: vi.fn(),
  getNeedsDecisionTerms: vi.fn(),
  sanitizeCustomLabel: vi.fn(),
  sanitizeDateInput: vi.fn(),
  sanitizeMinImpressions: vi.fn(),
  routeIntentDecision: vi.fn(),
  evaluateSearchGovernance: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: mocks.defaultDateWindow,
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
  sanitizeCustomLabel: mocks.sanitizeCustomLabel,
  sanitizeDateInput: mocks.sanitizeDateInput,
  sanitizeMinImpressions: mocks.sanitizeMinImpressions,
}))

vi.mock('@/lib/intent/policy', () => ({
  routeIntentDecision: mocks.routeIntentDecision,
  evaluateSearchGovernance: mocks.evaluateSearchGovernance,
}))

function buildSupabaseWithPersistedRows(
  rows: Array<{
    search_term: string
    custom_label_0: string | null
    recommended_search_tier: 'broad' | 'phrase' | 'exact'
    confidence: number
    metadata: {
      intent_class?: string
      reason_codes?: string[]
    }
  }>
) {
  const limit = vi.fn().mockResolvedValue({ data: rows, error: null })
  const order = vi.fn().mockReturnValue({ limit })
  const eq = vi.fn().mockReturnValue({ order })
  const select = vi.fn().mockReturnValue({ eq })
  const from = vi.fn().mockReturnValue({ select })

  return {
    from,
    _calls: {
      from,
      select,
      eq,
      order,
      limit,
    },
  }
}

describe('GET /api/search/governance/candidates', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.defaultDateWindow.mockReturnValue({
      startDate: '2026-01-01',
      endDate: '2026-01-30',
    })
    mocks.sanitizeDateInput.mockReturnValue(null)
    mocks.sanitizeCustomLabel.mockReturnValue(null)
    mocks.sanitizeMinImpressions.mockReturnValue(0)
  })

  it('returns persisted draft queue candidates when available', async () => {
    const supabase = buildSupabaseWithPersistedRows([
      {
        search_term: 'unlacquered brass towel bar',
        custom_label_0: 'HIGH',
        recommended_search_tier: 'exact',
        confidence: 0.84,
        metadata: {
          intent_class: 'PRODUCT_HIGH',
          reason_codes: ['exact_graduation_threshold_met'],
        },
      },
    ])

    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest(
      'http://localhost/api/search/governance/candidates?range=30d&limit=200'
    )
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.source).toBe('persisted')
    expect(body.candidate_count).toBe(1)
    expect(body.candidates[0].search_term).toBe('unlacquered brass towel bar')
    expect(body.candidates[0].governance.recommendedTier).toBe('exact')
    expect(body.candidates[0].route_decision.classification.intentClass).toBe('PRODUCT_HIGH')
    expect(body.candidates[0].buildout.cluster_key).toBe('towel bar')
    expect(body.candidates[0].buildout.suggested_campaign).toContain('Search')
    expect(body.cluster_summaries.length).toBeGreaterThan(0)
    expect(body.cluster_summaries[0].cluster_key).toBe('towel bar')
    expect(mocks.getNeedsDecisionTerms).not.toHaveBeenCalled()
  })

  it('falls back to computed candidates when persisted queue is empty', async () => {
    const supabase = buildSupabaseWithPersistedRows([])
    mocks.createAdminClient.mockReturnValue(supabase)

    mocks.getNeedsDecisionTerms.mockResolvedValue({
      date_window: {
        startDate: '2026-01-01',
        endDate: '2026-01-30',
      },
      total_count: 1,
      terms: [
        {
          search_term: 'brass robe hook',
          custom_label_0s: [
            {
              custom_label_0: 'MEDIUM',
              impressions: 100,
              clicks: 12,
              conversions: 3,
              conversions_value: 48,
              cost_micros: 14_000_000,
            },
          ],
        },
      ],
    })

    mocks.routeIntentDecision.mockReturnValue({
      classification: { intentClass: 'CATEGORY_MID' },
      confidence: 0.72,
    })
    mocks.evaluateSearchGovernance.mockReturnValue({
      action: 'promote_to_phrase',
      recommendedTier: 'phrase',
      confidence: 0.72,
      reasonCodes: ['broad_to_phrase_threshold_met'],
    })

    const request = new NextRequest('http://localhost/api/search/governance/candidates?range=30d')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.source).toBe('computed')
    expect(body.candidate_count).toBe(1)
    expect(body.candidates[0].search_term).toBe('brass robe hook')
    expect(body.candidates[0].governance.recommendedTier).toBe('phrase')
    expect(body.candidates[0].buildout.cluster_key).toBe('robe hook')
    expect(body.candidates[0].buildout.suggested_ad_group).toContain('Robe Hook')
    expect(body.cluster_summaries.length).toBe(1)
    expect(body.cluster_summaries[0].candidate_count).toBe(1)
    expect(mocks.getNeedsDecisionTerms).toHaveBeenCalledTimes(1)
  })
})
