import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------
const mocks = vi.hoisted(() => {
  const select = vi.fn()
  const gte = vi.fn()
  const lte = vi.fn()
  const from = vi.fn()

  return {
    from,
    select,
    gte,
    lte,
    createAdminClient: vi.fn(() => ({ from })),
  }
})

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a snapshot row for testing */
function makeRow(overrides: Record<string, unknown> = {}) {
  return {
    snapshot_date: '2026-02-24',
    custom_label_0: 'Towel Bar',
    tier: 'HIGH',
    impressions: 1000,
    clicks: 50,
    cost_micros: 3_000_000,
    conversions: 2,
    conversions_value: 300,
    roas: 1.0,
    ...overrides,
  }
}

/** Configure the Supabase mock chain to return the given rows */
function stubSupabaseRows(rows: Record<string, unknown>[]) {
  const lte = vi.fn().mockResolvedValue({ data: rows, error: null })
  const gte = vi.fn().mockReturnValue({ lte })
  const select = vi.fn().mockReturnValue({ gte })
  mocks.from.mockReturnValue({ select })
}

function makeGetRequest(url = 'http://localhost/api/funnel-snapshots/trends'): NextRequest {
  return new NextRequest(url, { method: 'GET' })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('GET /api/funnel-snapshots/trends', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns aggregated 7d current and previous period sums', async () => {
    const today = new Date()
    const d1 = new Date(today)
    d1.setUTCDate(d1.getUTCDate() - 1)
    const d8 = new Date(today)
    d8.setUTCDate(d8.getUTCDate() - 8)

    const currentRows = [
      makeRow({ snapshot_date: d1.toISOString().split('T')[0], impressions: 500, clicks: 25 }),
      makeRow({ snapshot_date: d1.toISOString().split('T')[0], impressions: 300, clicks: 15, tier: 'MEDIUM' }),
    ]
    const previousRows = [
      makeRow({ snapshot_date: d8.toISOString().split('T')[0], impressions: 400, clicks: 20 }),
      makeRow({ snapshot_date: d8.toISOString().split('T')[0], impressions: 200, clicks: 10, tier: 'MEDIUM' }),
    ]

    stubSupabaseRows([...currentRows, ...previousRows])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())
    expect(res.status).toBe(200)

    const body = await res.json()
    expect(body.has_data).toBe(true)
    // Current period totals: 500+300=800 impressions, 25+15=40 clicks
    expect(body.current.impressions).toBe(800)
    expect(body.current.clicks).toBe(40)
    // Previous period totals: 400+200=600 impressions, 20+10=30 clicks
    expect(body.previous.impressions).toBe(600)
    expect(body.previous.clicks).toBe(30)
  })

  it('computes CTR as clicks/impressions (guards division by zero)', async () => {
    stubSupabaseRows([
      makeRow({ impressions: 1000, clicks: 50 }),
    ])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())
    const body = await res.json()

    // CTR = 50/1000 = 0.05
    expect(body.current.ctr).toBeCloseTo(0.05, 4)

    // Test zero-impression guard
    stubSupabaseRows([makeRow({ impressions: 0, clicks: 0 })])
    const res2 = await GET(makeGetRequest())
    const body2 = await res2.json()
    expect(body2.current.ctr).toBe(0) // No NaN or Infinity
    expect(Number.isFinite(body2.current.ctr)).toBe(true)
  })

  it('computes ROAS as conversions_value / (cost_micros / 1e6) (guards division by zero)', async () => {
    stubSupabaseRows([
      makeRow({ conversions_value: 300, cost_micros: 3_000_000 }),
    ])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())
    const body = await res.json()

    // ROAS = 300 / (3_000_000 / 1e6) = 300 / 3 = 100
    expect(body.current.roas).toBeCloseTo(100, 2)

    // Test zero-cost guard
    stubSupabaseRows([makeRow({ conversions_value: 0, cost_micros: 0 })])
    const res2 = await GET(makeGetRequest())
    const body2 = await res2.json()
    expect(body2.current.roas).toBe(0) // No NaN or Infinity
    expect(Number.isFinite(body2.current.roas)).toBe(true)
  })

  it('returns has_data: false when no snapshot rows exist', async () => {
    stubSupabaseRows([])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())
    const body = await res.json()

    expect(body.has_data).toBe(false)
  })

  it('returns has_previous: false when only current period has data', async () => {
    const today = new Date()
    const d1 = new Date(today)
    d1.setUTCDate(d1.getUTCDate() - 1)

    // Only recent rows, no rows older than 7 days
    stubSupabaseRows([
      makeRow({ snapshot_date: d1.toISOString().split('T')[0], impressions: 500 }),
    ])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())
    const body = await res.json()

    expect(body.has_data).toBe(true)
    expect(body.has_previous).toBe(false)
  })

  it('applies Cache-Control header to response', async () => {
    stubSupabaseRows([makeRow()])

    const { GET } = await import('@/app/api/funnel-snapshots/trends/route')
    const res = await GET(makeGetRequest())

    const cacheControl = res.headers.get('cache-control')
    expect(cacheControl).toBeDefined()
    expect(cacheControl).toMatch(/max-age|s-maxage|no-cache/)
  })
})
