import { describe, expect, it, vi, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'
import { GET } from '@/app/api/ga4/attribution-forensics/route'

const mocks = vi.hoisted(() => ({
  fetchGa4AttributionQuality: vi.fn(),
  fetchGa4SourceMediumQuality: vi.fn(),
  fetchGa4LandingPageQuality: vi.fn(),
  fetchGa4CampaignPatternQuality: vi.fn(),
  buildRootCauseRows: vi.fn(),
  computeLandingInvalidRevenueShare: vi.fn(),
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/ga4/client', () => ({
  fetchGa4AttributionQuality: mocks.fetchGa4AttributionQuality,
}))

vi.mock('@/lib/ga4/forensics', () => ({
  getNormalizedForensicsPropertyId: (value?: string) => value ?? 'properties/342525135',
  fetchGa4SourceMediumQuality: mocks.fetchGa4SourceMediumQuality,
  fetchGa4LandingPageQuality: mocks.fetchGa4LandingPageQuality,
  fetchGa4CampaignPatternQuality: mocks.fetchGa4CampaignPatternQuality,
  buildRootCauseRows: mocks.buildRootCauseRows,
  computeLandingInvalidRevenueShare: mocks.computeLandingInvalidRevenueShare,
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

describe('GET /api/ga4/attribution-forensics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns available=false with warnings when GA4 data fetch fails', async () => {
    mocks.fetchGa4AttributionQuality.mockRejectedValue(new Error('GA4 down'))
    mocks.fetchGa4SourceMediumQuality.mockRejectedValue(new Error('GA4 down'))
    mocks.fetchGa4LandingPageQuality.mockRejectedValue(new Error('GA4 down'))
    mocks.fetchGa4CampaignPatternQuality.mockRejectedValue(new Error('GA4 down'))
    mocks.buildRootCauseRows.mockReturnValue([])
    mocks.computeLandingInvalidRevenueShare.mockReturnValue(0)
    mocks.createAdminClient.mockImplementation(() => {
      throw new Error('No supabase')
    })

    const request = new NextRequest('http://localhost/api/ga4/attribution-forensics')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.available).toBe(false)
    expect(Array.isArray(body.warnings)).toBe(true)
    expect(body.warnings.length).toBeGreaterThan(0)
  })

  it('returns populated forensics payload when dependencies succeed', async () => {
    mocks.fetchGa4AttributionQuality.mockResolvedValue({
      propertyId: 'properties/342525135',
      startDate: '30daysAgo',
      endDate: 'yesterday',
      generatedAt: '2026-02-20T00:00:00.000Z',
      totalRevenue: 5000,
      unassignedRevenue: 1000,
      notSetCampaignRevenue: 400,
      unassignedRevenueShare: 0.2,
      notSetCampaignRevenueShare: 0.08,
      qualityScore: 0.82,
      riskLevel: 'medium',
    })
    mocks.fetchGa4SourceMediumQuality.mockResolvedValue({ rows: [] })
    mocks.fetchGa4LandingPageQuality.mockResolvedValue({ rows: [] })
    mocks.fetchGa4CampaignPatternQuality.mockResolvedValue({ rows: [] })
    mocks.buildRootCauseRows.mockReturnValue([
      {
        rootCauseType: 'campaign_pattern',
        rootCauseKey: 'nonstandard',
        sessions: 100,
        transactions: 2,
        purchaseRevenue: 120,
        revenueShare: 0.02,
        sessionShare: 0.03,
        sampleValues: ['Random campaign'],
      },
    ])
    mocks.computeLandingInvalidRevenueShare.mockReturnValue(0.05)
    mocks.createAdminClient.mockReturnValue({
      from: vi.fn().mockReturnValue({
        select: vi.fn().mockReturnValue({
          or: vi.fn().mockReturnValue({
            order: vi.fn().mockReturnValue({
              limit: vi.fn().mockResolvedValue({
                data: [],
                error: null,
              }),
            }),
          }),
        }),
      }),
    })

    const request = new NextRequest('http://localhost/api/ga4/attribution-forensics')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.available).toBe(true)
    expect(body.quality_summary.totalRevenue).toBe(5000)
    expect(body.root_cause_rows).toHaveLength(1)
  })
})
