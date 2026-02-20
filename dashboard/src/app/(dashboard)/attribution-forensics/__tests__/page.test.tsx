import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import AttributionForensicsPage from '@/app/(dashboard)/attribution-forensics/page'

describe('AttributionForensicsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders diagnostics with partial API payloads', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()

      if (url.includes('/api/ga4/attribution-forensics')) {
        return new Response(
          JSON.stringify({
            property_id: 'properties/342525135',
            start_date: '30daysAgo',
            end_date: 'yesterday',
            generated_at: new Date().toISOString(),
            quality_summary: {
              qualityScore: 0.81,
              riskLevel: 'medium',
              unassignedRevenueShare: 0.21,
              notSetCampaignRevenueShare: 0.1,
              totalRevenue: 12000,
            },
            landing_invalid_revenue_share: 0.08,
            root_cause_rows: [
              {
                rootCauseType: 'campaign_pattern',
                rootCauseKey: 'nonstandard',
                sessions: 120,
                transactions: 3,
                purchaseRevenue: 800,
                revenueShare: 0.06,
                sessionShare: 0.04,
                sampleValues: ['Random campaign'],
              },
            ],
            incidents: [],
            warnings: ['campaign naming diagnostics unavailable'],
            available: true,
          }),
          { status: 200 }
        )
      }

      if (url.includes('/api/ga4/attribution-trend')) {
        return new Response(
          JSON.stringify({
            points: [
              {
                reportDate: '2026-02-19',
                totalRevenue: 1000,
                unassignedRevenue: 200,
                notSetCampaignRevenue: 100,
                unassignedRevenueShare: 0.2,
                notSetCampaignRevenueShare: 0.1,
                qualityScore: 0.82,
              },
            ],
            warnings: [],
            available: true,
          }),
          { status: 200 }
        )
      }

      return new Response(
        JSON.stringify({
          ga4Revenue: 1000,
          shopifyRevenue: 900,
          revenueDelta: 100,
          revenueRatio: 1.111111,
          orderCount: 10,
          warnings: [],
          available: true,
        }),
        { status: 200 }
      )
    })

    render(<AttributionForensicsPage />)

    await waitFor(() => {
      expect(screen.getByText('Attribution Forensics')).toBeInTheDocument()
      expect(screen.getByText('Root Cause Breakdown')).toBeInTheDocument()
      expect(screen.getByText('Handoff Packet')).toBeInTheDocument()
    })
  })
})
