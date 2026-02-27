import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/optimization/experiments/promote/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

interface CandidateRow {
  id: number
  status: 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'
  sample_size: number
  observed_lift: number
}

function createPromoteSupabaseMock(options?: {
  runStatus?: 'proposed' | 'approved' | 'executing' | 'validated' | 'rejected'
  candidates?: CandidateRow[]
  actionMetadata?: Record<string, unknown>
}) {
  const runStatus = options?.runStatus ?? 'executing'
  const candidates: CandidateRow[] = options?.candidates ?? [
    {
      id: 11,
      status: 'executing',
      sample_size: 240,
      observed_lift: 0.12,
    },
  ]
  const actionMetadata = options?.actionMetadata ?? { existing_audit: { prior: true } }

  const runUpdatePayloads: Array<Record<string, unknown>> = []
  const actionUpdatePayloads: Array<Record<string, unknown>> = []

  const from = vi.fn((table: string) => {
    if (table === 'experiment_runs') {
      const maybeSingle = vi.fn().mockResolvedValue({
        data: {
          id: 'run-1',
          run_key: 'run-key-1',
          status: runStatus,
          action_id: 'action-1',
        },
        error: null,
      })
      const eqLookup = vi.fn().mockReturnValue({ maybeSingle })
      const limit = vi.fn().mockReturnValue({ eq: eqLookup })
      const select = vi.fn().mockReturnValue({ limit })

      const eqUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn((payload: Record<string, unknown>) => {
        runUpdatePayloads.push(payload)
        return { eq: eqUpdate }
      })

      return { select, update }
    }

    if (table === 'experiment_candidates') {
      const eqSelect = vi.fn().mockResolvedValue({
        data: candidates,
        error: null,
      })
      const select = vi.fn().mockReturnValue({ eq: eqSelect })

      const inUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn().mockReturnValue({ in: inUpdate })

      return { select, update }
    }

    if (table === 'optimization_action_queue') {
      const maybeSingle = vi.fn().mockResolvedValue({
        data: { metadata: actionMetadata },
        error: null,
      })
      const eqLookup = vi.fn().mockReturnValue({ maybeSingle })
      const select = vi.fn().mockReturnValue({ eq: eqLookup })

      const eqUpdate = vi.fn().mockResolvedValue({ error: null })
      const update = vi.fn((payload: Record<string, unknown>) => {
        actionUpdatePayloads.push(payload)
        return { eq: eqUpdate }
      })

      return { select, update }
    }

    return { select: vi.fn(), update: vi.fn() }
  })

  return {
    from,
    runUpdatePayloads,
    actionUpdatePayloads,
  }
}

describe('POST /api/optimization/experiments/promote', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('blocks gate evaluation unless the run is in executing status', async () => {
    const supabase = createPromoteSupabaseMock({
      runStatus: 'approved',
      candidates: [
        {
          id: 11,
          status: 'approved',
          sample_size: 200,
          observed_lift: 0.2,
        },
      ],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/optimization/experiments/promote', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        run_key: 'run-key-1',
        decision: 'promote',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(409)
    expect(String(body.error)).toContain('requires run status executing')
  })

  it('uses sample-size weighted lift for the promotion gate', async () => {
    const supabase = createPromoteSupabaseMock({
      candidates: [
        {
          id: 11,
          status: 'executing',
          sample_size: 1,
          observed_lift: 1,
        },
        {
          id: 12,
          status: 'executing',
          sample_size: 999,
          observed_lift: 0,
        },
      ],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/optimization/experiments/promote', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        run_key: 'run-key-1',
        decision: 'promote',
        min_sample_size: 100,
        min_observed_lift: 0.05,
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.promoted).toBe(false)
    expect(body.gate_status).toBe('failed')
    expect(body.gate_results.weighted_average_lift).toBeLessThan(0.05)
  })

  it('merges existing action metadata when writing promotion gate context', async () => {
    const supabase = createPromoteSupabaseMock({
      candidates: [
        {
          id: 11,
          status: 'executing',
          sample_size: 240,
          observed_lift: 0.12,
        },
      ],
      actionMetadata: {
        existing_audit: {
          previous_transition: 'approved_to_executing',
        },
      },
    })
    mocks.createAdminClient.mockReturnValue(supabase)

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

    expect(supabase.actionUpdatePayloads).toHaveLength(1)
    expect(supabase.actionUpdatePayloads[0]).toMatchObject({
      metadata: {
        existing_audit: {
          previous_transition: 'approved_to_executing',
        },
      },
    })
    expect(
      (supabase.actionUpdatePayloads[0].metadata as { promotion_gate?: { gate_pass?: boolean } }).promotion_gate?.gate_pass
    ).toBe(true)
  })
})
