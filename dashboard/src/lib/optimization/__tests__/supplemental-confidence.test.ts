import { describe, expect, it } from 'vitest'
import { computeSupplementalConfidenceGate } from '@/lib/optimization/supplemental-confidence'

describe('computeSupplementalConfidenceGate', () => {
  it('applies stronger penalties when GA4 attribution quality is high-risk', () => {
    const gate = computeSupplementalConfidenceGate({
      ga4: {
        available: true,
        qualityScore: 0.58,
        riskLevel: 'high',
        unassignedRevenueShare: 0.33,
        notSetCampaignRevenueShare: 0.2,
      },
      shopify: {
        available: true,
        mappedSkuCount: 120,
        skuCountInOrders: 300,
        totalRevenue: 250000,
        unmappedSkuRevenue: 120000,
      },
    })

    expect(gate.multiplier).toBeLessThan(0.82)
    expect(gate.reasons).toContain('ga4_attribution_high_risk')
    expect(gate.reasons).toContain('shopify_low_sku_label_coverage')
    expect(gate.reasons).toContain('shopify_high_unmapped_revenue_share')
  })

  it('remains neutral when supplemental signals are healthy', () => {
    const gate = computeSupplementalConfidenceGate({
      ga4: {
        available: true,
        qualityScore: 0.94,
        riskLevel: 'low',
        unassignedRevenueShare: 0.04,
        notSetCampaignRevenueShare: 0.02,
      },
      shopify: {
        available: true,
        mappedSkuCount: 180,
        skuCountInOrders: 200,
        totalRevenue: 150000,
        unmappedSkuRevenue: 10000,
      },
    })

    expect(gate.multiplier).toBe(1)
    expect(gate.reasons).toHaveLength(0)
    expect(gate.warnings).toHaveLength(0)
  })

  it('surfaces warnings without forcing penalties when supplemental data is unavailable', () => {
    const gate = computeSupplementalConfidenceGate({
      ga4: {
        available: false,
      },
      shopify: {
        available: false,
      },
    })

    expect(gate.multiplier).toBe(1)
    expect(gate.reasons).toHaveLength(0)
    expect(gate.warnings.length).toBeGreaterThanOrEqual(2)
  })
})
