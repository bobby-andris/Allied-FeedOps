import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/search/governance/buildouts/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  defaultDateWindow: vi.fn(),
  getNeedsDecisionTerms: vi.fn(),
  sanitizeDateInput: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: mocks.defaultDateWindow,
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
  sanitizeDateInput: mocks.sanitizeDateInput,
}))

function buildPersistedSupabase(rows: Array<Record<string, unknown>>) {
  const limit = vi.fn().mockResolvedValue({ data: rows, error: null })
  const order = vi.fn().mockReturnValue({ limit })
  const inFilter = vi.fn().mockReturnValue({ order })
  const select = vi.fn().mockReturnValue({ in: inFilter })
  const from = vi.fn().mockReturnValue({ select })
  return { from }
}

describe('GET /api/search/governance/buildouts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.defaultDateWindow.mockReturnValue({
      startDate: '2026-01-01',
      endDate: '2026-01-30',
    })
    mocks.sanitizeDateInput.mockReturnValue(null)
  })

  it('returns structured buildout briefs from persisted recommendation queue', async () => {
    mocks.createAdminClient.mockReturnValue(
      buildPersistedSupabase([
        {
          search_term: 'unlacquered brass towel bar',
          custom_label_0: 'HIGH',
          recommended_search_tier: 'exact',
          confidence: 0.86,
          metadata: {
            intent_class: 'PRODUCT_HIGH',
            reason_codes: ['exact_readiness_threshold_met'],
          },
        },
        {
          search_term: 'brass towel bar wall mount',
          custom_label_0: 'HIGH',
          recommended_search_tier: 'phrase',
          confidence: 0.72,
          metadata: {
            intent_class: 'CATEGORY_MID',
            reason_codes: ['broad_to_phrase_threshold_met'],
          },
        },
      ])
    )

    const response = await GET(
      new NextRequest('http://localhost/api/search/governance/buildouts?range=30d&limit=200')
    )
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.source).toBe('persisted')
    expect(body.brief_count).toBeGreaterThan(0)
    expect(body.buildout_briefs[0].cluster_key).toBe('towel bar')
    expect(body.buildout_briefs[0].suggested_campaign).toContain('Search')
    expect(body.buildout_briefs[0].top_terms.length).toBeGreaterThan(0)
  })

  it('falls back to computed mining when persisted queue has no rows', async () => {
    mocks.createAdminClient.mockReturnValue(buildPersistedSupabase([]))
    mocks.getNeedsDecisionTerms.mockResolvedValue({
      date_window: { startDate: '2026-01-01', endDate: '2026-01-30' },
      terms: [
        {
          search_term: 'brass robe hook',
          custom_label_0s: [
            {
              custom_label_0: 'MEDIUM',
              impressions: 120,
              clicks: 20,
              conversions: 3,
              conversions_value: 80,
              cost_micros: 16_000_000,
            },
          ],
        },
      ],
    })

    const response = await GET(new NextRequest('http://localhost/api/search/governance/buildouts'))
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.source).toBe('computed')
    expect(body.brief_count).toBe(1)
    expect(body.buildout_briefs[0].cluster_key).toBe('robe hook')
  })
})
