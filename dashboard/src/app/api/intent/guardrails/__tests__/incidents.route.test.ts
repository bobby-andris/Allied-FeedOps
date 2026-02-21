import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/intent/guardrails/incidents/route'

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

function buildSupabaseForIncidentUpdate(updatedRow: Record<string, unknown> | null) {
  const maybeSingle = vi.fn().mockResolvedValue({ data: updatedRow, error: null })
  const select = vi.fn().mockReturnValue({ maybeSingle })
  const eq = vi.fn().mockReturnValue({ select })
  const update = vi.fn().mockReturnValue({ eq })
  const from = vi.fn().mockReturnValue({ update })

  return {
    from,
    _calls: {
      from,
      update,
      eq,
      select,
      maybeSingle,
    },
  }
}

describe('POST /api/intent/guardrails/incidents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.insertRowsSafe.mockResolvedValue({ inserted: 1 })
  })

  it('acknowledges an incident and records an execution log row', async () => {
    const supabase = buildSupabaseForIncidentUpdate({
      id: 'i-1',
      rule_id: 'critical_incident_open',
      severity: 'critical',
      status: 'acknowledged',
      acknowledged_at: '2026-02-20T00:00:00.000Z',
      acknowledged_by: 'operator@test',
      resolved_at: null,
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const request = new NextRequest('http://localhost/api/intent/guardrails/incidents', {
      method: 'POST',
      body: JSON.stringify({
        incident_id: 'i-1',
        action: 'acknowledge',
        actor: 'operator@test',
      }),
      headers: {
        'content-type': 'application/json',
      },
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.updated).toBe(true)
    expect(body.incident.status).toBe('acknowledged')
    expect(mocks.insertRowsSafe).toHaveBeenCalledWith(
      expect.anything(),
      'policy_action_execution_log',
      expect.any(Array)
    )
    expect(mocks.insertRowsSafe).toHaveBeenCalledWith(
      expect.anything(),
      'operator_review_audit',
      expect.arrayContaining([
        expect.objectContaining({
          queue_name: 'guardrail_incidents',
          entity_key: 'i-1',
          action: 'acknowledge',
          actor: 'operator@test',
        }),
      ])
    )
  })

  it('returns 400 for unsupported incident actions', async () => {
    const request = new NextRequest('http://localhost/api/intent/guardrails/incidents', {
      method: 'POST',
      body: JSON.stringify({
        incident_id: 'i-1',
        action: 'escalate',
      }),
      headers: {
        'content-type': 'application/json',
      },
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(400)
    expect(body.error).toContain('action')
  })
})
