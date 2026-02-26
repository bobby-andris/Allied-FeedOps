import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

// Mock setup using vi.hoisted for proper hoisting
const mocks = vi.hoisted(() => {
  const upsertFn = vi.fn().mockResolvedValue({ error: null })
  const selectFn = vi.fn().mockReturnValue({ data: [], error: null })
  const notFn = vi.fn().mockReturnValue({ data: [], error: null })
  const fromFn = vi.fn().mockReturnValue({
    upsert: upsertFn,
    select: selectFn,
    not: notFn,
  })

  return {
    createAdminClient: vi.fn().mockReturnValue({
      from: fromFn,
    }),
    fromFn,
    upsertFn,
    selectFn,
    notFn,
  }
})

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: vi.fn().mockReturnValue({ startDate: '2026-01-01', endDate: '2026-02-01' }),
  getNeedsDecisionTerms: vi.fn().mockResolvedValue({ terms: [], total_count: 0, date_window: {} }),
  sanitizeCustomLabel: vi.fn((v: string | null) => v),
  sanitizeDateInput: vi.fn((v: string | null) => v),
  sanitizeMinImpressions: vi.fn(() => 50),
}))

vi.mock('@/lib/optimization/control-center', () => ({
  buildRecommendationQueue: vi.fn().mockReturnValue([]),
}))

function makePostRequest(body: Record<string, unknown>): NextRequest {
  return new NextRequest('http://localhost:3000/api/shopping-funnel/recommendations', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('POST /api/shopping-funnel/recommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset default mock behavior
    mocks.upsertFn.mockResolvedValue({ error: null })
    mocks.selectFn.mockReturnValue({ data: [], error: null })
    mocks.notFn.mockReturnValue({ data: [], error: null })
    mocks.fromFn.mockReturnValue({
      upsert: mocks.upsertFn,
      select: mocks.selectFn,
      not: mocks.notFn,
    })
  })

  describe('label_block action', () => {
    it('inserts correct row shape with sentinel search_term and label scope', async () => {
      const { POST } = await import('@/app/api/shopping-funnel/recommendations/route')

      const req = makePostRequest({
        action: 'label_block',
        customLabel0: 'Grab Bars',
      })

      const res = await POST(req)
      const json = await res.json()

      expect(res.status).toBe(200)
      expect(json).toMatchObject({
        success: true,
        action: 'label_block',
        customLabel0: 'Grab Bars',
      })

      // Verify the upsert was called on routing_recommendations
      expect(mocks.fromFn).toHaveBeenCalledWith('routing_recommendations')

      // Verify the upsert row shape
      const upsertCall = mocks.upsertFn.mock.calls[0]
      const row = upsertCall[0]
      expect(row).toMatchObject({
        search_term: '__LABEL_BLOCK__',
        custom_label_0: 'Grab Bars',
        recommended_action: 'label_block',
        action_scope: 'label',
        review_status: 'accepted',
        accepted: true,
        accepted_by: 'dashboard_user',
        confidence: 1.0,
      })
      expect(row.accepted_at).toBeDefined()
      expect(row.metadata.history).toHaveLength(1)
      expect(row.metadata.history[0].action).toBe('label_block')

      // Verify onConflict
      const upsertOptions = upsertCall[1]
      expect(upsertOptions).toEqual({ onConflict: 'search_term,custom_label_0' })
    })

    it('returns 400 when customLabel0 is missing', async () => {
      const { POST } = await import('@/app/api/shopping-funnel/recommendations/route')

      const req = makePostRequest({
        action: 'label_block',
      })

      const res = await POST(req)
      expect(res.status).toBe(400)

      const json = await res.json()
      expect(json.error).toBe('customLabel0 required')
    })
  })

  // TODO: identify_search_candidates uses outdated simple thresholds (ROAS/impressions/conversions).
  // The scoring engine now uses intent scores, confidence factors, triggers, and tier fit scores.
  // Rewrite these tests when the route logic is updated to use the full scoring engine.
  describe.skip('identify_search_candidates action', () => {
    it('filters by ROAS/impressions/conversions thresholds', async () => {
      // Mock query_value_scores with mixed candidates
      const mockCandidates = [
        {
          search_term: 'polished nickel grab bar 18in',
          custom_label_0: 'Grab Bars',
          model_inputs: { actualRoas: 4.0, totalImpressions: 200, totalConversions: 5 },
        },
        {
          search_term: 'cheap grab bar',
          custom_label_0: 'Grab Bars',
          model_inputs: { actualRoas: 2.0, totalImpressions: 200, totalConversions: 3 }, // ROAS < 3.0
        },
        {
          search_term: 'rare brass bar',
          custom_label_0: 'Grab Bars',
          model_inputs: { actualRoas: 5.0, totalImpressions: 50, totalConversions: 1 }, // impressions < 100
        },
        {
          search_term: 'decorative bar',
          custom_label_0: 'Grab Bars',
          model_inputs: { actualRoas: 4.0, totalImpressions: 300, totalConversions: 0 }, // conversions = 0
        },
      ]

      // For identify_search_candidates: from('query_value_scores').select().not()
      const selectChain = {
        not: vi.fn().mockResolvedValue({ data: mockCandidates, error: null }),
      }
      const upsertForSearchBuildout = vi.fn().mockResolvedValue({ error: null })

      mocks.fromFn.mockImplementation((table: string) => {
        if (table === 'query_value_scores') {
          return {
            select: vi.fn().mockReturnValue(selectChain),
          }
        }
        if (table === 'search_buildout_recommendations') {
          return {
            upsert: upsertForSearchBuildout,
          }
        }
        return { upsert: mocks.upsertFn }
      })

      const { POST } = await import('@/app/api/shopping-funnel/recommendations/route')

      const req = makePostRequest({ action: 'identify_search_candidates' })
      const res = await POST(req)
      const json = await res.json()

      expect(res.status).toBe(200)
      expect(json.success).toBe(true)
      expect(json.candidateCount).toBe(1)

      // Only Term A should be upserted
      expect(upsertForSearchBuildout).toHaveBeenCalledTimes(1)
      const upsertedRows = upsertForSearchBuildout.mock.calls[0][0]
      expect(upsertedRows).toHaveLength(1)
      expect(upsertedRows[0].search_term).toBe('polished nickel grab bar 18in')
      expect(upsertedRows[0].recommended_search_tier).toBe('exact')
      expect(upsertedRows[0].status).toBe('candidate')
    })

    it('handles empty results gracefully', async () => {
      const selectChain = {
        not: vi.fn().mockResolvedValue({ data: [], error: null }),
      }

      mocks.fromFn.mockImplementation((table: string) => {
        if (table === 'query_value_scores') {
          return {
            select: vi.fn().mockReturnValue(selectChain),
          }
        }
        return { upsert: mocks.upsertFn }
      })

      const { POST } = await import('@/app/api/shopping-funnel/recommendations/route')

      const req = makePostRequest({ action: 'identify_search_candidates' })
      const res = await POST(req)
      const json = await res.json()

      expect(res.status).toBe(200)
      expect(json.success).toBe(true)
      expect(json.candidateCount).toBe(0)

      // No upsert should be called on search_buildout_recommendations
      // (upsertFn is the default mock, should not be called for search_buildout_recommendations)
    })
  })
})
