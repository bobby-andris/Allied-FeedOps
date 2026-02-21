import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET, POST } from '@/app/api/intent/rollback/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  insertRowsSafe: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return {
    ...actual,
    insertRowsSafe: mocks.insertRowsSafe,
  }
})

function createSupabaseMock(options?: {
  snapshots?: Array<{
    id: string
    snapshot_key: string
    policy_version: string
    created_at: string
    restored_at?: string | null
    payload?: Record<string, unknown>
  }>
  snapshotLookup?: {
    id: string
    snapshot_key: string
    policy_version: string
    payload: Record<string, unknown>
  } | null
  activeNegativeIds?: string[]
}) {
  const snapshots = options?.snapshots ?? []
  const snapshotLookup = options?.snapshotLookup ?? null
  const activeNegativeIds = options?.activeNegativeIds ?? []

  const from = vi.fn((table: string) => {
    if (table === 'policy_snapshots') {
      const maybeSingle = vi.fn().mockResolvedValue({
        data: snapshotLookup,
        error: null,
      })
      const eq = vi.fn().mockReturnValue({ maybeSingle })
      const limit = vi.fn().mockResolvedValue({
        data: snapshots,
        error: null,
      })
      const order = vi.fn().mockReturnValue({ limit, maybeSingle })
      const select = vi.fn().mockReturnValue({ order, eq })
      return { select }
    }

    if (table === 'negative_registry') {
      const select = vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          not: vi.fn().mockResolvedValue({
            data: activeNegativeIds.map((id) => ({ id })),
            error: null,
          }),
        }),
      })
      const inFilter = vi.fn().mockResolvedValue({ error: null })
      const eq = vi.fn().mockReturnValue({ in: inFilter })
      const update = vi.fn().mockReturnValue({ eq })
      return { select, update }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('intent rollback route', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.insertRowsSafe.mockResolvedValue({ inserted: 1 })
  })

  it('lists recent policy snapshots for rollback selection', async () => {
    const supabase = createSupabaseMock({
      snapshots: [
        {
          id: 'snapshot-1',
          snapshot_key: 'intent_v1_2026_02_20',
          policy_version: 'intent_v1',
          created_at: '2026-02-20T12:00:00.000Z',
          restored_at: null,
          payload: {},
        },
      ],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/rollback?limit=10')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.snapshot_count).toBe(1)
    expect(body.snapshots[0].id).toBe('snapshot-1')
  })

  it('deactivates cross-channel rollback negatives when rollback is applied', async () => {
    const supabase = createSupabaseMock({
      snapshotLookup: {
        id: 'snapshot-1',
        snapshot_key: 'intent_v1_2026_02_20',
        policy_version: 'intent_v1',
        payload: {},
      },
      activeNegativeIds: ['neg-1', 'neg-2'],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/rollback', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        snapshot_id: 'snapshot-1',
        reason: 'guardrail_incident',
        created_by: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.rollback_applied).toBe(true)
    expect(body.deactivated_negative_count).toBe(2)
    expect(mocks.insertRowsSafe).toHaveBeenCalledWith(
      expect.anything(),
      'operator_review_audit',
      expect.arrayContaining([
        expect.objectContaining({
          queue_name: 'intent_rollback',
          entity_key: 'snapshot-1',
          action: 'rollback_execute',
          actor: 'test:suite',
        }),
      ])
    )
  })
})
