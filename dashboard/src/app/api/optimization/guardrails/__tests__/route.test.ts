import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { GET, POST } from '@/app/api/optimization/guardrails/route'

const mocks = vi.hoisted(() => ({
  getNeedsDecisionTerms: vi.fn(),
  getLabelTierPerformance: vi.fn(),
  fetchGa4AttributionQuality: vi.fn(),
  fetchShopifyValueSignalsWithLabelMapping: vi.fn(),
  fetchGa4AudiencePerformance: vi.fn(),
  createAdminClient: vi.fn(),
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  defaultDateWindow: () => ({ startDate: '2026-02-01', endDate: '2026-02-20' }),
  sanitizeDateInput: (value: string | null | undefined) => value ?? undefined,
  sanitizeCustomLabel: (value: string | null | undefined) => value ?? undefined,
  sanitizeMinImpressions: () => 0,
  getNeedsDecisionTerms: mocks.getNeedsDecisionTerms,
  getLabelTierPerformance: mocks.getLabelTierPerformance,
}))

vi.mock('@/lib/ga4/client', () => ({
  fetchGa4AttributionQuality: mocks.fetchGa4AttributionQuality,
  fetchGa4AudiencePerformance: mocks.fetchGa4AudiencePerformance,
}))

vi.mock('@/lib/shopify/value-signals', () => ({
  fetchShopifyValueSignalsWithLabelMapping: mocks.fetchShopifyValueSignalsWithLabelMapping,
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

describe('GET /api/optimization/guardrails', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getNeedsDecisionTerms.mockResolvedValue({
      terms: [
        {
          search_term: 'soap dish holder',
          custom_label_0s: [
            {
              custom_label_0: 'Soap Dishes & Holders',
              source_campaign: 'AVD - Shopping - US - Soap Dishes & Holders - HIGH',
              source_tier: 'HIGH',
              impressions: 300,
              clicks: 10,
              cost_micros: 1_200_000,
              conversions: 0,
              conversions_value: 0,
            },
          ],
          recommendation: {
            action_type: 'funnel',
            default_tier: 'high',
            confidence: 0.4,
            reason_codes: ['performance_weighted_tiering'],
          },
          value_score: {
            impact_score: 200,
            expected_clicks: 10,
            expected_cvr: 0.01,
            expected_conversion_value: 20,
            expected_profit_proxy: 5,
            uncertainty: 0.8,
          },
        },
      ],
      total_count: 1,
      date_window: {
        startDate: '2026-02-01',
        endDate: '2026-02-20',
      },
    })

    mocks.getLabelTierPerformance.mockResolvedValue({
      rows: [
        {
          custom_label_0: 'Soap Dishes & Holders',
          tier: 'HIGH',
          impressions: 400,
          clicks: 18,
          cost_micros: 9_000_000,
          conversions: 1,
          conversions_value: 120,
          roas: 1.33,
        },
      ],
    })

    mocks.fetchGa4AttributionQuality.mockResolvedValue({
      available: true,
      qualityScore: 0.6,
      riskLevel: 'high',
      unassignedRevenueShare: 0.29,
      notSetCampaignRevenueShare: 0.18,
    })

    mocks.fetchGa4AudiencePerformance.mockResolvedValue({
      rows: [
        {
          audienceName: 'A1_HighIntent_NoPurchase_7d',
          sessions: 400,
          transactions: 0,
          purchaseRevenue: 0,
        },
      ],
    })

    mocks.fetchShopifyValueSignalsWithLabelMapping.mockResolvedValue({
      mappedSkuCount: 50,
      skuCountInOrders: 200,
      totalRevenue: 100_000,
      unmappedSkuRevenue: 45_000,
      orderCount: 200,
      uniqueCustomers: 150,
      repeatCustomerRate: 0.3,
      averageOrderValue: 500,
      topCustomLabels: [],
      topSkus: [],
    })
  })

  it('returns guardrail incidents and rollout decision', async () => {
    const request = new NextRequest('http://localhost/api/optimization/guardrails?range=30d')
    const response = await GET(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.guardrail_decision.status).toBe('blocked')
    expect(Array.isArray(body.incidents)).toBe(true)
    expect(body.incidents.length).toBeGreaterThan(0)
    expect(body.metrics.low_confidence_high_impact_share).toBeDefined()
  })
})

describe('POST /api/optimization/guardrails', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.INTERNAL_API_TOKEN = 'test-token'
  })

  it('requires internal token outside development when persisting', async () => {
    const request = new NextRequest('http://localhost/api/optimization/guardrails?persist=true', {
      method: 'POST',
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(401)
    expect(body.error).toContain('Unauthorized')
  })
})
