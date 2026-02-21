import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/experiments/results/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createSupabaseMock() {
  const from = vi.fn((table: string) => {
    if (table === 'experiment_registry') {
      const limit = vi.fn().mockResolvedValue({
        data: [
          {
            experiment_key: 'exp-1',
            name: 'Search buildout holdout',
            initiative: 'Query mining + buildout',
            hypothesis: 'Graduated terms improve margin efficiency',
            status: 'active',
            start_date: '2026-02-01',
            end_date: null,
            success_threshold: 0.08,
            failure_threshold: -0.05,
            created_at: '2026-02-01T00:00:00.000Z',
          },
        ],
        error: null,
      })
      const order = vi.fn().mockReturnValue({ limit })
      const select = vi.fn().mockReturnValue({ order })
      return { select }
    }

    if (table === 'experiment_outcomes') {
      const order = vi.fn().mockResolvedValue({
        data: [
          {
            experiment_key: 'exp-1',
            metric_name: 'margin_roas',
            observed_lift: 0.11,
            sample_size: 640,
            status: 'observing',
            measured_at: '2026-02-20T12:00:00.000Z',
            metadata: {},
          },
        ],
        error: null,
      })
      const inFilter = vi.fn().mockReturnValue({ order })
      const select = vi.fn().mockReturnValue({ in: inFilter })
      return { select }
    }

    if (table === 'experiment_assignments') {
      const inFilter = vi.fn().mockReturnValue({
        order: vi.fn().mockResolvedValue({
          data: [
            { experiment_key: 'exp-1', entity_key: 'term-a', cohort: 'control', assigned_at: '2026-02-15T00:00:00.000Z' },
            { experiment_key: 'exp-1', entity_key: 'term-b', cohort: 'treatment', assigned_at: '2026-02-15T00:00:00.000Z' },
          ],
          error: null,
        }),
      })
      const select = vi.fn().mockReturnValue({ in: inFilter })
      return { select }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('GET /api/experiments/results', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns assignments and weekly governance summary with recommended action', async () => {
    mocks.createAdminClient.mockReturnValue(createSupabaseMock())

    const request = new NextRequest('http://localhost/api/experiments/results?limit=50')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.experiments).toHaveLength(1)
    expect(body.outcomes).toHaveLength(1)
    expect(body.assignments).toHaveLength(2)
    expect(body.governance).toHaveLength(1)
    expect(body.governance[0]).toMatchObject({
      experiment_key: 'exp-1',
      weekly_status: 'promote_to_scale',
      latest_metric_name: 'margin_roas',
    })
    expect(body.governance[0].holdout_share).toBeCloseTo(0.5, 4)
  })
})
