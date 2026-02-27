import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { PATCH, POST } from '@/app/api/optimization/action-queue/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  insertRowsSafe: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual = await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return {
    ...actual,
    insertRowsSafe: mocks.insertRowsSafe,
  }
})

function createPostSupabaseMock() {
  const from = vi.fn((table: string) => {
    if (table === 'optimization_action_queue') {
      return {
        insert: vi.fn().mockReturnValue({
          select: vi.fn().mockReturnValue({
            maybeSingle: vi.fn().mockResolvedValue({
              data: {
                id: 'action-1',
                action_key: 'content-refresh-1',
                current_state: 'proposed',
              },
              error: null,
            }),
          }),
        }),
      }
    }

    return {
      insert: vi.fn(),
      select: vi.fn(),
      update: vi.fn(),
    }
  })

  return { from }
}

function createPatchSupabaseMock(currentState: string) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: {
      id: 'action-1',
      action_key: 'content-refresh-1',
      current_state: currentState,
      metadata: {},
    },
    error: null,
  })
  const eqForLookup = vi.fn().mockReturnValue({ maybeSingle })
  const limit = vi.fn().mockReturnValue({ eq: eqForLookup })
  const select = vi.fn().mockReturnValue({ limit })

  const eqForUpdate = vi.fn().mockResolvedValue({ error: null })
  const update = vi.fn().mockReturnValue({ eq: eqForUpdate })

  const from = vi.fn((_table: string) => ({
    select,
    update,
  }))

  return { from }
}

describe('optimization action queue route', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.insertRowsSafe.mockResolvedValue({ inserted: 1 })
  })

  it('creates queue action rows and persists a score snapshot', async () => {
    mocks.createAdminClient.mockReturnValue(createPostSupabaseMock())

    const request = new NextRequest('http://localhost/api/optimization/action-queue', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        title: 'Refresh top leak terms for CL-55',
        action_type: 'content_refresh',
        master_sku: 'CL-55',
        platform: 'google',
        score: {
          expected_revenue_impact: 0.12,
          confidence_score: 0.81,
          effort_score: 0.22,
          policy_risk_score: 0.05,
        },
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.created).toBe(true)
    expect(body.score_rows_inserted).toBe(1)
    expect(mocks.insertRowsSafe).toHaveBeenCalledWith(
      expect.anything(),
      'optimization_action_scores',
      expect.arrayContaining([
        expect.objectContaining({
          action_id: 'action-1',
          score_version: 'r5.v1',
        }),
      ])
    )
  })

  it('blocks invalid queue state transitions', async () => {
    mocks.createAdminClient.mockReturnValue(createPatchSupabaseMock('proposed'))

    const request = new NextRequest('http://localhost/api/optimization/action-queue', {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        action_id: 'action-1',
        next_state: 'validated',
        actor: 'test:suite',
      }),
    })

    const response = await PATCH(request)
    const body = await response.json()

    expect(response.status).toBe(409)
    expect(String(body.error)).toContain('Invalid state transition')
  })
})
