import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GET } from '@/app/api/intent/rollback/readiness/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createSupabaseMock(options?: {
  incidents?: Array<{ severity: string }>
  snapshotCount?: number
  activeNegativeCount?: number
}) {
  const incidents = options?.incidents ?? []
  const snapshotCount = options?.snapshotCount ?? 0
  const activeNegativeCount = options?.activeNegativeCount ?? 0

  const from = vi.fn((table: string) => {
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

    if (table === 'policy_snapshots') {
      return {
        select: vi.fn().mockResolvedValue({
          count: snapshotCount,
          error: null,
        }),
      }
    }

    if (table === 'negative_registry') {
      return {
        select: vi.fn().mockReturnValue({
          eq: vi.fn().mockReturnValue({
            eq: vi.fn().mockResolvedValue({
              count: activeNegativeCount,
              error: null,
            }),
          }),
        }),
      }
    }

    return { select: vi.fn() }
  })

  return { from }
}

describe('rollback readiness route', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns not ready when no incidents and snapshots available', async () => {
    const supabase = createSupabaseMock({
      incidents: [],
      snapshotCount: 2,
      activeNegativeCount: 0,
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const response = await GET()
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.ready).toBe(false)
    expect(body.recommendation).toBe('no_rollback_needed')
  })

  it('returns not ready when no snapshots available even with incidents', async () => {
    const supabase = createSupabaseMock({
      incidents: [{ severity: 'critical' }],
      snapshotCount: 0,
      activeNegativeCount: 0,
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const response = await GET()
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.ready).toBe(false)
    expect(body.recommendation).toBe('no_snapshots_available')
  })

  it('returns ready when critical incidents exist and snapshots available', async () => {
    const supabase = createSupabaseMock({
      incidents: [{ severity: 'critical' }],
      snapshotCount: 3,
      activeNegativeCount: 5,
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const response = await GET()
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.ready).toBe(true)
    expect(body.recommendation).toBe('rollback_recommended')
    expect(body.context.guardrail_status).toBe('blocked')
    expect(body.context.snapshot_count).toBe(3)
  })

  it('includes checklist in response', async () => {
    const supabase = createSupabaseMock({
      incidents: [{ severity: 'high' }, { severity: 'high' }, { severity: 'high' }],
      snapshotCount: 1,
      activeNegativeCount: 2,
    })
    mocks.createAdminClient.mockReturnValue(supabase)

    const response = await GET()
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.checklist).toBeDefined()
    expect(body.checklist.length).toBeGreaterThan(0)
  })
})
