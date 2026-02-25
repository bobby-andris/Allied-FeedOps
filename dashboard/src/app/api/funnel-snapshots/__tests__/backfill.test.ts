import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

// ---------------------------------------------------------------------------
// Hoisted mocks — available before any module-level code runs
// ---------------------------------------------------------------------------
const mocks = vi.hoisted(() => {
  const upsert = vi.fn().mockResolvedValue({ error: null })
  const from = vi.fn().mockReturnValue({ upsert })

  return {
    getLabelTierPerformance: vi.fn(),
    from,
    upsert,
    createAdminClient: vi.fn(() => ({ from })),
  }
})

vi.mock('@/lib/shopping-funnel/service', () => ({
  getLabelTierPerformance: mocks.getLabelTierPerformance,
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeRequest(
  headers: Record<string, string> = {},
  body?: Record<string, unknown>
): NextRequest {
  return new NextRequest('http://localhost/api/funnel-snapshots/backfill', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

const SAMPLE_ROWS = [
  {
    custom_label_0: 'Towel Bar',
    tier: 'HIGH' as const,
    impressions: 1200,
    clicks: 80,
    cost_micros: 5_000_000,
    conversions: 3,
    conversions_value: 450.0,
    roas: 0.9,
  },
  {
    custom_label_0: 'Towel Bar',
    tier: 'MEDIUM' as const,
    impressions: 600,
    clicks: 30,
    cost_micros: 2_000_000,
    conversions: 1,
    conversions_value: 120.0,
    roas: 0.6,
  },
]

function makeLabelTierResponse() {
  return {
    rows: SAMPLE_ROWS,
    total_rows: SAMPLE_ROWS.length,
    date_window: { start: '2026-02-22', end: '2026-02-22' },
    data_source: 'google_ads_api_live',
    generated_at: new Date().toISOString(),
    cache_ttl_ms: 0,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('POST /api/funnel-snapshots/backfill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    process.env.CRON_SECRET = 'test-secret'

    mocks.getLabelTierPerformance.mockResolvedValue(makeLabelTierResponse())
  })

  it('returns 401 when no Authorization header provided', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    const res = await POST(
      makeRequest({}, { start_date: '2026-02-22', end_date: '2026-02-24' })
    )
    expect(res.status).toBe(401)
    const body = await res.json()
    expect(body.error).toBeDefined()
  })

  it('returns 401 when token does not match CRON_SECRET', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    const res = await POST(
      makeRequest(
        { authorization: 'Bearer wrong-token' },
        { start_date: '2026-02-22', end_date: '2026-02-24' }
      )
    )
    expect(res.status).toBe(401)
  })

  it('returns 400 when start_date or end_date missing from body', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )

    // Missing end_date
    const res1 = await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { start_date: '2026-02-22' }
      )
    )
    expect(res1.status).toBe(400)
    const body1 = await res1.json()
    expect(body1.error).toContain('required')

    // Missing start_date
    const res2 = await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { end_date: '2026-02-24' }
      )
    )
    expect(res2.status).toBe(400)
  })

  it('returns 400 when date range exceeds 90 days', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    const res = await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { start_date: '2025-01-01', end_date: '2025-06-01' }
      )
    )
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error).toContain('90 days')
  })

  it('calls getLabelTierPerformance once per day for a 3-day range', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    const res = await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { start_date: '2026-02-22', end_date: '2026-02-24' }
      )
    )
    expect(res.status).toBe(200)

    // Should be called exactly 3 times (one per day)
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledTimes(3)

    // Each call should use same date for startDate and endDate (single-day query)
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledWith({
      startDate: '2026-02-22',
      endDate: '2026-02-22',
    })
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledWith({
      startDate: '2026-02-23',
      endDate: '2026-02-23',
    })
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledWith({
      startDate: '2026-02-24',
      endDate: '2026-02-24',
    })

    const body = await res.json()
    expect(body.total_days).toBe(3)
    expect(body.total_rows).toBe(6) // 2 rows per day * 3 days
  })

  it('maps rows to correct format with all expected columns', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { start_date: '2026-02-22', end_date: '2026-02-22' }
      )
    )

    expect(mocks.from).toHaveBeenCalledWith('funnel_snapshots_daily')
    expect(mocks.upsert).toHaveBeenCalledOnce()

    const upsertArgs = mocks.upsert.mock.calls[0]
    const rows = upsertArgs[0]

    // Verify all columns match capture/route.ts mapping
    expect(rows[0]).toEqual({
      snapshot_date: '2026-02-22',
      custom_label_0: 'Towel Bar',
      tier: 'HIGH',
      impressions: 1200,
      clicks: 80,
      cost_micros: 5_000_000,
      conversions: 3,
      conversions_value: 450.0,
      roas: 0.9,
    })

    // Verify onConflict matches capture endpoint
    expect(upsertArgs[1]).toMatchObject({
      onConflict: 'snapshot_date,custom_label_0,tier',
    })
  })

  it('continues processing remaining days when one day throws an error', async () => {
    // First day throws, second day succeeds
    mocks.getLabelTierPerformance
      .mockRejectedValueOnce(new Error('Google Ads API error'))
      .mockResolvedValueOnce(makeLabelTierResponse())

    const { POST } = await import(
      '@/app/api/funnel-snapshots/backfill/route'
    )
    const res = await POST(
      makeRequest(
        { authorization: 'Bearer test-secret' },
        { start_date: '2026-02-22', end_date: '2026-02-23' }
      )
    )
    expect(res.status).toBe(200)

    // Both days should have been attempted
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledTimes(2)

    const body = await res.json()
    expect(body.total_days).toBe(2)
    expect(body.days[0].rows).toBe(-1) // first day failed
    expect(body.days[1].rows).toBe(2) // second day succeeded
  })
})
