import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/intent/scorecard/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createSupabaseMock(options?: {
  actionLogs?: Array<{ action_type: string; status: string; created_at: string }>
  incidents?: Array<{ severity: string }>
}) {
  const actionLogs = options?.actionLogs ?? []
  const incidents = options?.incidents ?? []

  const from = vi.fn((table: string) => {
    if (table === 'policy_action_execution_log') {
      return {
        select: vi.fn().mockReturnValue({
          gte: vi.fn().mockResolvedValue({
            data: actionLogs,
            error: null,
          }),
        }),
      }
    }

    if (table === 'guardrail_incidents') {
      return {
        select: vi.fn().mockReturnValue({
          in: vi.fn().mockResolvedValue({
            data: incidents,
            error: null,
          }),
        }),
      }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('executive scorecard route', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns scorecard with ROAS, CPA, and action breakdown', async () => {
    const supabase = createSupabaseMock({
      actionLogs: [
        { action_type: 'promote', status: 'applied', created_at: '2026-02-20T10:00:00Z' },
        { action_type: 'demote', status: 'applied', created_at: '2026-02-20T11:00:00Z' },
        { action_type: 'negative', status: 'applied', created_at: '2026-02-20T12:00:00Z' },
        { action_type: 'hold', status: 'planned', created_at: '2026-02-20T13:00:00Z' },
      ],
      incidents: [],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest(
      'http://localhost/api/intent/scorecard?total_revenue=50000&total_cost=12000&total_conversions=80'
    )
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.roas).toBeGreaterThan(0)
    expect(body.cpa).toBeGreaterThan(0)
    expect(body.automationRate).toBeGreaterThan(0)
    expect(body.actionBreakdown).toBeDefined()
    expect(body.operationalHealth.healthGrade).toBe('healthy')
  })

  it('returns degraded health when high-severity incidents exist', async () => {
    const supabase = createSupabaseMock({
      actionLogs: [],
      incidents: [{ severity: 'high' }],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/scorecard')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.operationalHealth.healthGrade).toBe('degraded')
    expect(body.operationalHealth.guardrailStatus).toBe('hold')
  })

  it('returns critical health when critical incidents exist', async () => {
    const supabase = createSupabaseMock({
      actionLogs: [],
      incidents: [{ severity: 'critical' }],
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/scorecard')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.operationalHealth.healthGrade).toBe('critical')
  })
})
