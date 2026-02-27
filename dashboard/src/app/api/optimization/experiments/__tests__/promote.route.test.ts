import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/optimization/experiments/promote/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createPromoteSupabaseMock(options: {
  sampleSize: number
  observedLift: number
  hasRejectedCandidate?: boolean
}) {
  const from = vi.fn((table: string) => {
    if (table === 'experiment_runs') {
      const maybeSingle = vi.fn().mockResolvedValue({
        data: {
          id: 'run-1',
          run_key: 'run-key-1',
          status: 'executing',
          action_id: 'action-1',
        },
        error: null,
      })
      const eqLookup = vi.fn().mockReturnValue({ maybeSingle })
      const limit = vi.fn().mockReturnValue({ eq: eqLookup })
      const select = vi.fn().mockReturnValue({ limit })

      const eqUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn().mockReturnValue({ eq: eqUpdate })

      return { select, update }
    }

    if (table === 'experiment_candidates') {
      const eqSelect = vi.fn().mockResolvedValue({
        data: [
          {
            id: 11,
            status: options.hasRejectedCandidate ? 'rejected' : 'executing',
            sample_size: options.sampleSize,
            observed_lift: options.observedLift,
          },
        ],
        error: null,
      })
      const select = vi.fn().mockReturnValue({ eq: eqSelect })

      const inUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn().mockReturnValue({ in: inUpdate })

      return { select, update }
    }

    if (table === 'optimization_action_queue') {
      const eqUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn().mockReturnValue({ eq: eqUpdate })
      return { update }
    }

    return { select: vi.fn(), update: vi.fn() }
  })

  return { from }
}

describe('POST /api/optimization/experiments/promote', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('blocks promotion when sample size and lift do not satisfy gate thresholds', async () => {
    mocks.createAdminClient.mockReturnValue(
      createPromoteSupabaseMock({
        sampleSize: 20,
        observedLift: 0.01,
      })
    )

    const request = new NextRequest('http://localhost/api/optimization/experiments/promote', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        run_key: 'run-key-1',
        decision: 'promote',
        min_sample_size: 100,
        min_observed_lift: 0.05,
        actor: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.promoted).toBe(false)
    expect(body.next_run_status).toBe('rejected')
    expect(body.gate_status).toBe('failed')
  })

  it('promotes run when gate thresholds are satisfied', async () => {
    mocks.createAdminClient.mockReturnValue(
      createPromoteSupabaseMock({
        sampleSize: 240,
        observedLift: 0.12,
      })
    )

    const request = new NextRequest('http://localhost/api/optimization/experiments/promote', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        run_key: 'run-key-1',
        decision: 'promote',
        min_sample_size: 100,
        min_observed_lift: 0.05,
        actor: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.promoted).toBe(true)
    expect(body.next_run_status).toBe('validated')
    expect(body.gate_status).toBe('passed')
  })
})
