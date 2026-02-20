import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/ga4/snapshot-capture/route'

const mocks = vi.hoisted(() => {
  const from = vi.fn()
  return {
    fetchGa4AttributionQuality: vi.fn(),
    fetchGa4SourceMediumQuality: vi.fn(),
    fetchGa4LandingPageQuality: vi.fn(),
    fetchGa4CampaignPatternQuality: vi.fn(),
    buildRootCauseRows: vi.fn(),
    computeLandingInvalidRevenueShare: vi.fn(),
    computeConsecutiveOutOfRangeStreak: vi.fn(),
    evaluateAttributionIncidents: vi.fn(),
    fetchShopifyOrderSnapshots: vi.fn(),
    from,
    createAdminClient: vi.fn(() => ({
      from,
    })),
  }
})

vi.mock('@/lib/ga4/client', () => ({
  fetchGa4AttributionQuality: mocks.fetchGa4AttributionQuality,
}))

vi.mock('@/lib/ga4/forensics', () => ({
  getNormalizedForensicsPropertyId: (value?: string) => value ?? 'properties/342525135',
  resolveGa4DateWindow: () => ({
    startDate: '2026-02-01',
    endDate: '2026-02-01',
    start: new Date('2026-02-01T00:00:00.000Z'),
    end: new Date('2026-02-01T00:00:00.000Z'),
    lookbackDays: 1,
  }),
  fetchGa4SourceMediumQuality: mocks.fetchGa4SourceMediumQuality,
  fetchGa4LandingPageQuality: mocks.fetchGa4LandingPageQuality,
  fetchGa4CampaignPatternQuality: mocks.fetchGa4CampaignPatternQuality,
  buildRootCauseRows: mocks.buildRootCauseRows,
  computeLandingInvalidRevenueShare: mocks.computeLandingInvalidRevenueShare,
  computeConsecutiveOutOfRangeStreak: mocks.computeConsecutiveOutOfRangeStreak,
  evaluateAttributionIncidents: mocks.evaluateAttributionIncidents,
  isReconciliationOutOfRange: () => false,
}))

vi.mock('@/lib/shopify/value-signals', () => ({
  fetchShopifyOrderSnapshots: mocks.fetchShopifyOrderSnapshots,
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

function createSupabaseTableMock() {
  return {
    upsert: vi.fn().mockResolvedValue({ error: null }),
    select: vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        order: vi.fn().mockReturnValue({
          limit: vi.fn().mockResolvedValue({ data: [], error: null }),
        }),
      }),
      in: vi.fn().mockReturnValue({
        in: vi.fn().mockResolvedValue({ data: [], error: null }),
      }),
      or: vi.fn().mockReturnValue({
        order: vi.fn().mockReturnValue({
          limit: vi.fn().mockResolvedValue({ data: [], error: null }),
        }),
      }),
    }),
    in: vi.fn().mockReturnValue({
      in: vi.fn().mockResolvedValue({ data: [], error: null }),
    }),
    insert: vi.fn().mockResolvedValue({ error: null }),
  }
}

describe('POST /api/ga4/snapshot-capture', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mocks.fetchGa4AttributionQuality.mockResolvedValue({
      propertyId: 'properties/342525135',
      startDate: '2026-02-01',
      endDate: '2026-02-01',
      generatedAt: '2026-02-02T00:00:00.000Z',
      totalRevenue: 1000,
      unassignedRevenue: 200,
      notSetCampaignRevenue: 100,
      unassignedRevenueShare: 0.2,
      notSetCampaignRevenueShare: 0.1,
      qualityScore: 0.85,
      riskLevel: 'medium',
    })
    mocks.fetchGa4SourceMediumQuality.mockResolvedValue({ rows: [] })
    mocks.fetchGa4LandingPageQuality.mockResolvedValue({ rows: [] })
    mocks.fetchGa4CampaignPatternQuality.mockResolvedValue({ rows: [] })
    mocks.buildRootCauseRows.mockReturnValue([])
    mocks.computeLandingInvalidRevenueShare.mockReturnValue(0)
    mocks.computeConsecutiveOutOfRangeStreak.mockReturnValue(0)
    mocks.evaluateAttributionIncidents.mockReturnValue([])
    mocks.fetchShopifyOrderSnapshots.mockResolvedValue([])
  })

  it('keeps snapshot upserts idempotent for same property/date', async () => {
    const qualityTable = createSupabaseTableMock()
    const sourceMediumTable = createSupabaseTableMock()
    const landingTable = createSupabaseTableMock()
    const rootCauseTable = createSupabaseTableMock()
    const reconciliationTable = createSupabaseTableMock()
    const incidentsTable = createSupabaseTableMock()

    mocks.from.mockImplementation((tableName: string) => {
      if (tableName === 'ga4_attribution_quality_daily') return qualityTable
      if (tableName === 'ga4_source_medium_daily') return sourceMediumTable
      if (tableName === 'ga4_landing_page_quality_daily') return landingTable
      if (tableName === 'ga4_attribution_root_cause_daily') return rootCauseTable
      if (tableName === 'ga4_shopify_reconciliation_daily') return reconciliationTable
      if (tableName === 'guardrail_incidents') return incidentsTable
      return createSupabaseTableMock()
    })

    const request = new NextRequest(
      'http://localhost/api/ga4/snapshot-capture?start_date=2026-02-01&end_date=2026-02-01',
      { method: 'POST' }
    )

    const firstResponse = await POST(request)
    const secondResponse = await POST(request)
    const firstBody = await firstResponse.json()
    const secondBody = await secondResponse.json()

    expect(firstResponse.status).toBe(200)
    expect(secondResponse.status).toBe(200)
    expect(firstBody.snapshot_result.reportDate).toBe('2026-02-01')
    expect(secondBody.snapshot_result.reportDate).toBe('2026-02-01')
    expect(qualityTable.upsert).toHaveBeenCalled()
    expect(qualityTable.upsert.mock.calls[0][1]).toEqual(
      expect.objectContaining({ onConflict: 'property_id,report_date' })
    )
  })

  it('handles empty Shopify data gracefully', async () => {
    const genericTable = createSupabaseTableMock()
    mocks.from.mockReturnValue(genericTable)

    const request = new NextRequest('http://localhost/api/ga4/snapshot-capture', {
      method: 'POST',
    })
    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.reconciliation_summary.shopifyRevenue).toBe(0)
    expect(body.reconciliation_summary.orderCount).toBe(0)
    expect(body.warnings).not.toContainEqual(expect.stringContaining('Shopify reconciliation unavailable'))
  })
})
