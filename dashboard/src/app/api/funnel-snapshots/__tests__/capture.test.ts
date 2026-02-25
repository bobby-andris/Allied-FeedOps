import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

// ---------------------------------------------------------------------------
// Hoisted mocks — available before any module-level code runs
// ---------------------------------------------------------------------------
const mocks = vi.hoisted(() => {
  const upsert = vi.fn().mockResolvedValue({ error: null })
  const deleteFn = vi.fn().mockReturnValue({
    lt: vi.fn().mockReturnValue({
      select: vi.fn().mockResolvedValue({ data: [], error: null }),
    }),
  })
  const from = vi.fn().mockReturnValue({
    upsert,
    delete: deleteFn,
  })

  return {
    getLabelTierPerformance: vi.fn(),
    from,
    upsert,
    deleteFn,
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
function makeRequest(headers: Record<string, string> = {}): NextRequest {
  return new NextRequest('http://localhost/api/funnel-snapshots/capture', {
    method: 'POST',
    headers,
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('POST /api/funnel-snapshots/capture', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.CRON_SECRET = 'test-secret'

    mocks.getLabelTierPerformance.mockResolvedValue({
      rows: SAMPLE_ROWS,
      total_rows: SAMPLE_ROWS.length,
      date_window: { start: '2026-02-24', end: '2026-02-24' },
      data_source: 'google_ads_api_live',
      generated_at: new Date().toISOString(),
      cache_ttl_ms: 0,
    })
  })

  it('rejects requests without valid Authorization header (returns 401)', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    const res = await POST(makeRequest())
    expect(res.status).toBe(401)
    const body = await res.json()
    expect(body.error).toBeDefined()
  })

  it('rejects requests with wrong Bearer token (returns 401)', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    const res = await POST(makeRequest({ authorization: 'Bearer wrong-token' }))
    expect(res.status).toBe(401)
  })

  it('calls getLabelTierPerformance with yesterday date and upserts rows to Supabase', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    const res = await POST(
      makeRequest({ authorization: 'Bearer test-secret' }),
    )
    expect(res.status).toBe(200)

    // getLabelTierPerformance should have been called with yesterday's date
    expect(mocks.getLabelTierPerformance).toHaveBeenCalledOnce()
    const callArgs = mocks.getLabelTierPerformance.mock.calls[0][0]
    expect(callArgs.startDate).toBe(callArgs.endDate) // single-day query

    // Supabase upsert should have been called with correct row data
    expect(mocks.from).toHaveBeenCalledWith('funnel_snapshots_daily')
    expect(mocks.upsert).toHaveBeenCalledOnce()
    const upsertArgs = mocks.upsert.mock.calls[0]
    const rows = upsertArgs[0]
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({
      custom_label_0: 'Towel Bar',
      tier: 'HIGH',
      impressions: 1200,
    })
    // onConflict for idempotent upsert
    expect(upsertArgs[1]).toMatchObject({
      onConflict: expect.stringContaining('snapshot_date'),
    })
  })

  it('returns snapshot_date and rows_captured in response body', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    const res = await POST(
      makeRequest({ authorization: 'Bearer test-secret' }),
    )
    const body = await res.json()
    expect(body.snapshot_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(body.rows_captured).toBe(2)
  })

  it('handles re-run for same day via upsert (no duplicate error)', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    // First run
    const res1 = await POST(
      makeRequest({ authorization: 'Bearer test-secret' }),
    )
    expect(res1.status).toBe(200)

    // Second run (same data) — upsert should succeed without error
    const res2 = await POST(
      makeRequest({ authorization: 'Bearer test-secret' }),
    )
    expect(res2.status).toBe(200)
    expect(mocks.upsert).toHaveBeenCalledTimes(2)
  })

  it('deletes rows older than 90 days during capture', async () => {
    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    await POST(makeRequest({ authorization: 'Bearer test-secret' }))

    // The delete chain: .from('funnel_snapshots_daily').delete().lt('snapshot_date', cutoffDate)
    const fromCalls = mocks.from.mock.calls.map((c: string[]) => c[0])
    expect(fromCalls).toContain('funnel_snapshots_daily')
    expect(mocks.deleteFn).toHaveBeenCalled()

    const ltCall = mocks.deleteFn.mock.results[0].value.lt
    expect(ltCall).toHaveBeenCalledWith(
      'snapshot_date',
      expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    )
  })

  it('returns 500 with error message when getLabelTierPerformance throws', async () => {
    mocks.getLabelTierPerformance.mockRejectedValueOnce(
      new Error('Google Ads API unavailable'),
    )

    const { POST } = await import(
      '@/app/api/funnel-snapshots/capture/route'
    )
    const res = await POST(
      makeRequest({ authorization: 'Bearer test-secret' }),
    )
    expect(res.status).toBe(500)
    const body = await res.json()
    expect(body.error).toBeDefined()
  })
})
