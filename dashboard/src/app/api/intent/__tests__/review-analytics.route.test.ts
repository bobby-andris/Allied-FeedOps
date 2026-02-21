import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/intent/review-analytics/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createSupabaseMock(rows: Array<Record<string, unknown>>) {
  const limit = vi.fn().mockResolvedValue({ data: rows, error: null })
  const order = vi.fn().mockReturnValue({ limit })
  const gte = vi.fn().mockReturnValue({ order })
  const select = vi.fn().mockReturnValue({ gte })
  const from = vi.fn().mockReturnValue({ select })
  return { from }
}

describe('GET /api/intent/review-analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns operator calibration and decision consistency summaries', async () => {
    const supabase = createSupabaseMock([
      {
        queue_name: 'search_governance',
        entity_key: 'term-1',
        action: 'approve_candidate',
        actor: 'operator-a',
        created_at: '2026-02-20T12:00:00.000Z',
        before_state: { recommended_action: 'approve_candidate' },
        after_state: { selected_action: 'approve_candidate' },
      },
      {
        queue_name: 'search_governance',
        entity_key: 'term-1',
        action: 'cancel_candidate',
        actor: 'operator-b',
        created_at: '2026-02-20T13:00:00.000Z',
        before_state: { recommended_action: 'approve_candidate' },
        after_state: { selected_action: 'cancel_candidate' },
      },
      {
        queue_name: 'guardrail_incidents',
        entity_key: 'incident-1',
        action: 'acknowledge',
        actor: 'operator-a',
        created_at: '2026-02-20T14:00:00.000Z',
        before_state: { recommended_action: 'acknowledge' },
        after_state: { selected_action: 'acknowledge' },
      },
    ])
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/review-analytics?range=30d&limit=200')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.summary.total_actions).toBe(3)
    expect(body.summary.unique_entities).toBe(2)
    expect(body.summary.unique_actors).toBe(2)
    expect(body.summary.consistency_rate).toBeCloseTo(0.5, 2)
    expect(body.summary.alignment_rate).toBeCloseTo(2 / 3, 2)
    expect(body.queue_summaries[0]).toMatchObject({
      queue_name: 'search_governance',
    })
    expect(body.actor_summaries[0]).toMatchObject({
      actor: 'operator-a',
    })
  })
})
