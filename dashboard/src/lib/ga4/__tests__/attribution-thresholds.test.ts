import { describe, expect, it } from 'vitest'
import {
  computeConsecutiveOutOfRangeStreak,
  evaluateAttributionIncidents,
  isReconciliationOutOfRange,
} from '@/lib/ga4/forensics'

describe('attribution guardrail thresholds', () => {
  it('flags reconciliation out-of-range ratios correctly', () => {
    expect(isReconciliationOutOfRange(0.79)).toBe(true)
    expect(isReconciliationOutOfRange(1.21)).toBe(true)
    expect(isReconciliationOutOfRange(1.0)).toBe(false)
    expect(isReconciliationOutOfRange(null)).toBe(false)
  })

  it('counts consecutive out-of-range streak from latest snapshot', () => {
    expect(computeConsecutiveOutOfRangeStreak([1.25, 1.22, 1.3, 1.1])).toBe(3)
    expect(computeConsecutiveOutOfRangeStreak([0.9, 1.3, 1.4])).toBe(0)
  })

  it('generates incidents for breached thresholds', () => {
    const incidents = evaluateAttributionIncidents({
      unassignedRevenueShare: 0.3,
      notSetCampaignRevenueShare: 0.2,
      landingInvalidRevenueShare: 0.11,
      reconciliationRatio: 1.25,
      reconciliationOutOfRangeStreak: 3,
      propertyId: 'properties/342525135',
      reportDate: '2026-02-20',
    })

    expect(incidents.map((incident) => incident.ruleId)).toEqual(
      expect.arrayContaining([
        'ga4_unassigned_revenue_share',
        'ga4_not_set_campaign_revenue_share',
        'ga4_invalid_landing_page_revenue_share',
        'ga4_shopify_reconciliation_ratio',
      ])
    )
  })
})
