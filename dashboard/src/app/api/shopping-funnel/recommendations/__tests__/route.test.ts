import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  getNeedsDecisionTerms: vi.fn(),
  buildRecommendationQueue: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: vi.fn().mockReturnValue({ startDate: '2026-01-01', endDate: '2026-02-01' }),
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
  sanitizeCustomLabel: vi.fn().mockImplementation((v: string | null) => v),
  sanitizeDateInput: vi.fn().mockImplementation((v: string | null) => v),
  sanitizeMinImpressions: vi.fn().mockReturnValue(50),
}))

vi.mock('@/lib/optimization/control-center', () => ({
  buildRecommendationQueue: mocks.buildRecommendationQueue,
}))

import { GET, POST } from '@/app/api/shopping-funnel/recommendations/route'

function makeGetRequest(params: Record<string, string> = {}): NextRequest {
  const url = new URL('http://localhost:3000/api/shopping-funnel/recommendations')
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  return new NextRequest(url, { method: 'GET' })
}

function makePostRequest(body: Record<string, unknown>): NextRequest {
  return new NextRequest('http://localhost:3000/api/shopping-funnel/recommendations', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  })
}

// Helper to build a chainable Supabase mock
function mockSupabaseChain(result: { data: unknown; error: unknown }) {
  const terminal = vi.fn().mockResolvedValue(result)
  const chain: Record<string, ReturnType<typeof vi.fn>> = {}

  // Each method returns the chain object itself, except the terminal
  const methods = ['from', 'select', 'upsert', 'update', 'eq', 'in', 'order', 'limit', 'single']
  for (const method of methods) {
    chain[method] = vi.fn().mockReturnValue(chain)
  }
  // Terminal: limit/select at the end resolves
  chain.limit = terminal
  // For single() calls (undo fetch)
  chain.single = vi.fn().mockResolvedValue(result)
  // For .select() after upsert/update (returns promise)
  const selectAfterMutation = vi.fn().mockResolvedValue(result)

  // Override upsert/update to return a chain where .select() resolves
  const mutationChain = {
    select: selectAfterMutation,
  }
  chain.upsert = vi.fn().mockReturnValue(mutationChain)
  chain.update = vi.fn().mockReturnValue({
    eq: vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        select: selectAfterMutation,
      }),
    }),
  })

  return { chain, terminal, selectAfterMutation }
}

describe('POST /api/shopping-funnel/recommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('approves a single term with review_status=accepted', async () => {
    const approvedRecord = {
      id: 'uuid-1',
      search_term: 'brass towel bar',
      custom_label_0: 'Towel Bars - Low',
      recommended_action: 'funnel',
      recommended_tier: 'medium',
      review_status: 'accepted',
      accepted: true,
      accepted_at: '2026-02-25T00:00:00.000Z',
      accepted_by: 'operator',
    }

    const { chain, selectAfterMutation } = mockSupabaseChain({
      data: [approvedRecord],
      error: null,
    })
    mocks.createAdminClient.mockReturnValue(chain)

    const response = await POST(
      makePostRequest({
        action: 'approve',
        searchTerm: 'brass towel bar',
        customLabel0: 'Towel Bars - Low',
        recommendedTier: 'medium',
        currentTier: 'low',
        confidence: 0.85,
        impact: { low: 100, mid: 200, high: 300 },
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.ok).toBe(true)
    expect(body.record.review_status).toBe('accepted')
    expect(body.record.accepted).toBe(true)

    // Verify upsert was called with correct data
    expect(chain.upsert).toHaveBeenCalledOnce()
    const upsertArgs = chain.upsert.mock.calls[0]
    expect(upsertArgs[0].review_status).toBe('accepted')
    expect(upsertArgs[0].accepted).toBe(true)
    expect(upsertArgs[0].recommended_action).toBe('funnel')
    expect(upsertArgs[0].accepted_by).toBe('operator')
    expect(upsertArgs[1]).toEqual({ onConflict: 'search_term,custom_label_0' })
    expect(selectAfterMutation).toHaveBeenCalled()
  })

  it('approves with recommended_action=global_block for wasted spend', async () => {
    const { chain } = mockSupabaseChain({
      data: [{ id: 'uuid-2', recommended_action: 'global_block', review_status: 'accepted' }],
      error: null,
    })
    mocks.createAdminClient.mockReturnValue(chain)

    const response = await POST(
      makePostRequest({
        action: 'approve',
        searchTerm: 'competitor brand name',
        customLabel0: 'Towel Bars - Low',
        recommendedTier: 'medium',
        currentTier: 'low',
        confidence: 0.9,
        impact: { low: 50, mid: 100, high: 150 },
        recommendedAction: 'global_block',
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.ok).toBe(true)

    const upsertArgs = chain.upsert.mock.calls[0]
    expect(upsertArgs[0].recommended_action).toBe('global_block')
  })

  it('rejects a single term with review_status=rejected', async () => {
    const { chain } = mockSupabaseChain({
      data: [{ id: 'uuid-3', review_status: 'rejected', accepted: false }],
      error: null,
    })
    mocks.createAdminClient.mockReturnValue(chain)

    const response = await POST(
      makePostRequest({
        action: 'reject',
        searchTerm: 'irrelevant term',
        customLabel0: 'Towel Bars - Low',
        reason: 'Not relevant to product line',
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.ok).toBe(true)

    const upsertArgs = chain.upsert.mock.calls[0]
    expect(upsertArgs[0].review_status).toBe('rejected')
    expect(upsertArgs[0].accepted).toBe(false)
    expect(upsertArgs[0].metadata.rejection_reason).toBe('Not relevant to product line')
  })

  it('undoes a recommendation back to pending', async () => {
    // Mock the existing record fetch (single)
    const existingMeta = {
      currentTier: 'low',
      history: [{ action: 'approved', at: '2026-02-24T00:00:00.000Z' }],
    }

    // Build a custom mock for undo which has two Supabase calls
    const selectAfterUpdate = vi.fn().mockResolvedValue({
      data: [{ id: 'uuid-4', review_status: 'pending', accepted: false, accepted_at: null }],
      error: null,
    })

    const fromMock = vi.fn()

    // First call: select existing metadata (.from().select().eq().eq().single())
    const singleMock = vi.fn().mockResolvedValue({ data: { metadata: existingMeta }, error: null })
    const selectChain = {
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          single: singleMock,
        }),
      }),
    }

    // Second call: update (.from().update().eq().eq().select())
    const updateChain = {
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          select: selectAfterUpdate,
        }),
      }),
    }

    let callCount = 0
    fromMock.mockImplementation(() => {
      callCount++
      if (callCount === 1) {
        return { select: vi.fn().mockReturnValue(selectChain) }
      }
      return { update: vi.fn().mockReturnValue(updateChain) }
    })

    mocks.createAdminClient.mockReturnValue({ from: fromMock })

    const response = await POST(
      makePostRequest({
        action: 'undo',
        searchTerm: 'brass towel bar',
        customLabel0: 'Towel Bars - Low',
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.ok).toBe(true)
    expect(body.record.review_status).toBe('pending')
    expect(body.record.accepted).toBe(false)
    expect(body.record.accepted_at).toBeNull()

    // Verify update call includes undo in history
    expect(fromMock).toHaveBeenCalledTimes(2)
  })

  it('batch approves multiple terms', async () => {
    const records = [
      { id: 'uuid-5', search_term: 'term1', review_status: 'accepted' },
      { id: 'uuid-6', search_term: 'term2', review_status: 'accepted' },
    ]

    const { chain } = mockSupabaseChain({ data: records, error: null })
    mocks.createAdminClient.mockReturnValue(chain)

    const response = await POST(
      makePostRequest({
        action: 'batch_approve',
        terms: [
          {
            searchTerm: 'term1',
            customLabel0: 'Towel Bars - Low',
            recommendedTier: 'medium',
            currentTier: 'low',
            confidence: 0.85,
            impact: { low: 100, mid: 200, high: 300 },
          },
          {
            searchTerm: 'term2',
            customLabel0: 'Soap Dishes - Low',
            recommendedTier: 'medium',
            currentTier: 'low',
            confidence: 0.90,
            impact: { low: 50, mid: 100, high: 150 },
          },
        ],
      })
    )

    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.ok).toBe(true)
    expect(body.approved_count).toBe(2)

    // Verify upsert called with array of rows
    const upsertArgs = chain.upsert.mock.calls[0]
    expect(upsertArgs[0]).toHaveLength(2)
    expect(upsertArgs[0][0].review_status).toBe('accepted')
    expect(upsertArgs[0][1].review_status).toBe('accepted')
    expect(upsertArgs[1]).toEqual({ onConflict: 'search_term,custom_label_0' })
  })

  it('returns 400 for batch_approve with empty terms', async () => {
    const response = await POST(
      makePostRequest({ action: 'batch_approve', terms: [] })
    )
    expect(response.status).toBe(400)
    const body = await response.json()
    expect(body.error).toContain('non-empty terms')
  })

  it('returns 400 for unknown action', async () => {
    const response = await POST(makePostRequest({ action: 'invalid_action' }))
    expect(response.status).toBe(400)
    const body = await response.json()
    expect(body.error).toContain('Unknown action')
  })
})

describe('GET /api/shopping-funnel/recommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns history for ?action=history', async () => {
    const historyData = [
      {
        id: 'uuid-h1',
        search_term: 'brass towel bar',
        review_status: 'accepted',
        accepted_at: '2026-02-25T00:00:00.000Z',
      },
      {
        id: 'uuid-h2',
        search_term: 'chrome soap dish',
        review_status: 'rejected',
        accepted_at: null,
      },
    ]

    const { chain } = mockSupabaseChain({ data: historyData, error: null })
    mocks.createAdminClient.mockReturnValue(chain)

    const response = await GET(makeGetRequest({ action: 'history' }))
    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.history).toHaveLength(2)
    expect(body.history[0].review_status).toBe('accepted')
  })

  it('returns statuses for ?action=statuses', async () => {
    const statusData = [
      {
        search_term: 'brass towel bar',
        custom_label_0: 'Towel Bars - Low',
        review_status: 'accepted',
        accepted_at: '2026-02-25T00:00:00.000Z',
        accepted_by: 'operator',
        metadata: {},
      },
    ]

    // For statuses, the chain is: from().select().order() which resolves
    const orderMock = vi.fn().mockResolvedValue({ data: statusData, error: null })
    const selectMock = vi.fn().mockReturnValue({ order: orderMock })
    const fromMock = vi.fn().mockReturnValue({ select: selectMock })

    mocks.createAdminClient.mockReturnValue({ from: fromMock })

    const response = await GET(makeGetRequest({ action: 'statuses' }))
    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.statuses).toHaveLength(1)
    expect(body.statuses[0].review_status).toBe('accepted')
  })

  it('returns recommendation queue for default GET (no action)', async () => {
    mocks.getNeedsDecisionTerms.mockResolvedValue({
      terms: [{ searchTerm: 'brass towel bar' }],
      total_count: 1,
      date_window: { start: '2026-01-01', end: '2026-02-01' },
    })
    mocks.buildRecommendationQueue.mockReturnValue([
      { searchTerm: 'brass towel bar', actionType: 'funnel' },
    ])

    const response = await GET(makeGetRequest())
    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.queue).toHaveLength(1)
    expect(body.queue_count).toBe(1)
    expect(body.action_distribution).toEqual({ funnel: 1 })
    expect(mocks.getNeedsDecisionTerms).toHaveBeenCalledOnce()
  })
})
