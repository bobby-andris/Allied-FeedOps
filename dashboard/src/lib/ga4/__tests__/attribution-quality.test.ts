import { describe, expect, it } from 'vitest'
import { computeAttributionQuality, type Ga4CampaignRow } from '@/lib/ga4/client'

describe('computeAttributionQuality', () => {
  it('calculates revenue quality metrics from unassigned and (not set) traffic', () => {
    const rows: Ga4CampaignRow[] = [
      {
        channelGroup: 'Paid Shopping',
        campaignName: 'AVD Shopping HIGH',
        sessions: 1200,
        transactions: 80,
        purchaseRevenue: 12000,
      },
      {
        channelGroup: 'Unassigned',
        campaignName: '(not set)',
        sessions: 400,
        transactions: 10,
        purchaseRevenue: 3000,
      },
      {
        channelGroup: 'Paid Search',
        campaignName: '(not set)',
        sessions: 200,
        transactions: 5,
        purchaseRevenue: 1000,
      },
    ]

    const result = computeAttributionQuality(rows)

    expect(result.totalRevenue).toBe(16000)
    expect(result.unassignedRevenue).toBe(3000)
    expect(result.notSetCampaignRevenue).toBe(4000)
    expect(result.unassignedRevenueShare).toBeCloseTo(0.1875, 4)
    expect(result.notSetCampaignRevenueShare).toBeCloseTo(0.25, 4)
    expect(result.qualityScore).toBeLessThan(0.8)
  })

  it('returns perfect quality when there is no unassigned or not-set revenue', () => {
    const rows: Ga4CampaignRow[] = [
      {
        channelGroup: 'Paid Shopping',
        campaignName: 'AVD Shopping LOW',
        sessions: 900,
        transactions: 64,
        purchaseRevenue: 9900,
      },
    ]

    const result = computeAttributionQuality(rows)

    expect(result.totalRevenue).toBe(9900)
    expect(result.unassignedRevenueShare).toBe(0)
    expect(result.notSetCampaignRevenueShare).toBe(0)
    expect(result.qualityScore).toBe(1)
    expect(result.riskLevel).toBe('low')
  })
})

