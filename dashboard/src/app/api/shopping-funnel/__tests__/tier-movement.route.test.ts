import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST, GET } from '@/app/api/shopping-funnel/tier-movement/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  executeTierMovementBatch: vi.fn(),
  updateSupplementalFeedTiers: vi.fn(),
  evaluatePromotionDemotion: vi.fn(),
  evaluateGuardrails: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/intent/tier-movement', () => ({
  executeTierMovementBatch: mocks.executeTierMovementBatch,
  updateSupplementalFeedTiers: mocks.updateSupplementalFeedTiers,
}))

vi.mock('@/lib/intent/policy', () => ({
  evaluatePromotionDemotion: mocks.evaluatePromotionDemotion,
  evaluateGuardrails: mocks.evaluateGuardrails,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return { ...actual }
})

function makePostRequest(body: Record<string, unknown>): NextRequest {
  return new NextRequest('http://localhost:3000/api/shopping-funnel/tier-movement', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeGetRequest(params: Record<string, string> = {}): NextRequest {
  const url = new URL('http://localhost:3000/api/shopping-funnel/tier-movement')
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  return new NextRequest(url, { method: 'GET' })
}

describe('POST /api/shopping-funnel/tier-movement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createAdminClient.mockReturnValue({})
    mocks.evaluatePromotionDemotion.mockReturnValue({
      searchTerm: 'brass towel bar',
      action: 'promote_to_medium',
      confidence: 0.8,
      reasonCodes: ['low_to_medium_threshold_met'],
      policyVersion: 'intent_v1',
    })
  })

  it('returns 400 for empty movements', async () => {
    const response = await POST(makePostRequest({ movements: [] }))
    expect(response.status).toBe(400)
    const body = await response.json()
    expect(body.error).toContain('non-empty movements')
  })

  it('returns 400 for missing movements', async () => {
    const response = await POST(makePostRequest({}))
    expect(response.status).toBe(400)
  })

  it('returns 400 when movements exceed batch limit', async () => {
    const movements = Array.from({ length: 101 }, (_, i) => ({
      search_term: `term ${i}`,
      custom_label_0: `Label - Low`,
      current_tier: 'low',
      target_tier: 'medium',
    }))
    const response = await POST(makePostRequest({ movements }))
    expect(response.status).toBe(400)
    const body = await response.json()
    expect(body.error).toContain('100')
  })

  it('executes batch and returns results', async () => {
    mocks.executeTierMovementBatch.mockResolvedValue({
      results: [
        {
          searchTerm: 'brass towel bar',
          customLabel0: 'Towel Bars - Low',
          currentTier: 'low',
          targetTier: 'medium',
          status: 'applied',
          reasonCodes: ['tier_movement_applied'],
        },
      ],
      appliedCount: 1,
      failedCount: 0,
      blockedCount: 0,
      reviewRequiredCount: 0,
      guardrailStatus: 'go',
      executedAt: '2026-02-20T00:00:00.000Z',
    })

    const response = await POST(
      makePostRequest({
        movements: [
          {
            search_term: 'brass towel bar',
            custom_label_0: 'Towel Bars - Low',
            current_tier: 'low',
            target_tier: 'medium',
            confidence: 0.8,
          },
        ],
        created_by: 'test-operator',
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.appliedCount).toBe(1)
    expect(body.guardrailStatus).toBe('go')
    expect(mocks.executeTierMovementBatch).toHaveBeenCalledOnce()
  })

  it('skips sheet update for dry runs', async () => {
    mocks.executeTierMovementBatch.mockResolvedValue({
      results: [{ status: 'applied' }],
      appliedCount: 1,
      failedCount: 0,
      blockedCount: 0,
      reviewRequiredCount: 0,
      guardrailStatus: 'go',
      executedAt: '2026-02-20T00:00:00.000Z',
    })

    await POST(
      makePostRequest({
        movements: [
          {
            search_term: 'brass towel bar',
            custom_label_0: 'Towel Bars - Low',
            current_tier: 'low',
            target_tier: 'medium',
            gmc_offer_ids: ['shopify_us_123_456'],
          },
        ],
        dry_run: true,
      })
    )

    expect(mocks.updateSupplementalFeedTiers).not.toHaveBeenCalled()
  })

  it('calls sheet update when movements have gmc_offer_ids', async () => {
    mocks.executeTierMovementBatch.mockResolvedValue({
      results: [
        {
          searchTerm: 'brass towel bar',
          customLabel0: 'Towel Bars - Medium',
          currentTier: 'low',
          targetTier: 'medium',
          status: 'applied',
          reasonCodes: ['tier_movement_applied'],
        },
      ],
      appliedCount: 1,
      failedCount: 0,
      blockedCount: 0,
      reviewRequiredCount: 0,
      guardrailStatus: 'go',
      executedAt: '2026-02-20T00:00:00.000Z',
    })
    mocks.updateSupplementalFeedTiers.mockResolvedValue({ updated: 1, errors: [] })

    await POST(
      makePostRequest({
        movements: [
          {
            search_term: 'brass towel bar',
            custom_label_0: 'Towel Bars - Low',
            current_tier: 'low',
            target_tier: 'medium',
            gmc_offer_ids: ['shopify_us_123_456'],
          },
        ],
      })
    )

    expect(mocks.updateSupplementalFeedTiers).toHaveBeenCalledOnce()
  })
})

describe('GET /api/shopping-funnel/tier-movement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns movement history', async () => {
    const mockSelect = vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          order: vi.fn().mockReturnValue({
            limit: vi.fn().mockResolvedValue({
              data: [
                {
                  id: 'uuid-1',
                  action_type: 'tier_movement',
                  search_term: 'brass towel bar',
                  custom_label_0: 'Towel Bars - Medium',
                  status: 'applied',
                  policy_version: 'intent_v1',
                  action_payload: {
                    previous_tier: 'low',
                    new_tier: 'medium',
                    action: 'promote_to_medium',
                  },
                  reason_codes: ['low_to_medium_threshold_met'],
                  created_by: 'operator',
                  created_at: '2026-02-20T00:00:00.000Z',
                },
              ],
              error: null,
            }),
          }),
        }),
      }),
    })

    mocks.createAdminClient.mockReturnValue({
      from: vi.fn().mockReturnValue({ select: mockSelect }),
    })

    const response = await GET(makeGetRequest())
    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.entries).toHaveLength(1)
    expect(body.entries[0].searchTerm).toBe('brass towel bar')
    expect(body.entries[0].previousTier).toBe('low')
    expect(body.entries[0].newTier).toBe('medium')
  })
})
