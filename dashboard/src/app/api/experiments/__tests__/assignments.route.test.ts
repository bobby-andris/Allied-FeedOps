import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/experiments/assignments/route'

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

function createSupabaseMock(existingEntityKeys: string[]) {
  const from = vi.fn((table: string) => {
    if (table === 'experiment_registry') {
      const eq = vi.fn().mockResolvedValue({
        data: [{ experiment_key: 'exp-1', initiative: 'search-buildout', start_date: '2026-02-01' }],
        error: null,
      })
      const select = vi.fn().mockReturnValue({ eq })
      return { select }
    }

    if (table === 'experiment_assignments') {
      const inFilter = vi.fn().mockResolvedValue({
        data: existingEntityKeys.map((entity_key) => ({
          experiment_key: 'exp-1',
          entity_key,
          cohort: 'control',
        })),
        error: null,
      })
      const eq = vi.fn().mockReturnValue({ in: inFilter })
      const select = vi.fn().mockReturnValue({ eq })
      return { select }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('POST /api/experiments/assignments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.insertRowsSafe.mockImplementation(async (_client: unknown, _table: string, rows: unknown[]) => ({
      inserted: rows.length,
    }))
  })

  it('creates holdout assignments while preserving existing assignment rows', async () => {
    mocks.createAdminClient.mockReturnValue(createSupabaseMock(['term-a']))

    const request = new NextRequest('http://localhost/api/experiments/assignments', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        experiment_key: 'exp-1',
        entity_keys: ['term-a', 'term-b'],
        holdout_percent: 40,
        created_by: 'test:suite',
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.assigned_count).toBe(2)
    expect(body.inserted_count).toBe(1)
    expect(body.assignments).toHaveLength(2)
    expect(body.assignments[0]).toHaveProperty('entity_key')
    expect(body.assignments[0]).toHaveProperty('cohort')

    const insertCall = mocks.insertRowsSafe.mock.calls.find((call) => call[1] === 'experiment_assignments')
    expect(insertCall).toBeDefined()
    expect(insertCall?.[2]).toHaveLength(1)
    expect(insertCall?.[2]?.[0]).toMatchObject({
      experiment_key: 'exp-1',
      entity_key: 'term-b',
      metadata: {
        assigned_by: 'test:suite',
      },
    })
  })
})
