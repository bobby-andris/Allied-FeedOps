import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'
import { POST } from '@/app/api/intent/bid-policy/route'

const mocks = vi.hoisted(() => ({
  createAdminClient: vi.fn(),
  getLabelTierPerformance: vi.fn(),
  recommendBidPolicy: vi.fn(),
  insertRowsSafe: vi.fn(),
}))

vi.mock('@/lib/supabase/admin', () => ({
  createAdminClient: mocks.createAdminClient,
}))

vi.mock('@/lib/shopping-funnel/service', () => ({
  getLabelTierPerformance: mocks.getLabelTierPerformance,
}))

vi.mock('@/lib/intent/policy', () => ({
  recommendBidPolicy: mocks.recommendBidPolicy,
}))

vi.mock('@/lib/intent/persistence', async () => {
  const actual =
    await vi.importActual<typeof import('@/lib/intent/persistence')>('@/lib/intent/persistence')
  return {
    ...actual,
    insertRowsSafe: mocks.insertRowsSafe,
  }
})

describe('POST /api/intent/bid-policy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createAdminClient.mockReturnValue({})
    mocks.getLabelTierPerformance.mockResolvedValue({ rows: [] })
  })

  it('supports CPA mode rows without writing ROAS recommendation rows', async () => {
    mocks.recommendBidPolicy.mockReturnValue({
      key: 'HIGH|HIGH',
      action: 'decrease_target',
      recommendedTargetCpa: 42,
      confidence: 0.81,
      reasonCodes: ['observed_cpa_below_target'],
      policyVersion: 'intent_v1',
    })
    mocks.insertRowsSafe.mockImplementation(async (_client: unknown, table: string) => {
      if (table === 'policy_decision_log') {
        return { inserted: 1 }
      }
      if (table === 'roas_target_recommendations') {
        return { inserted: 0 }
      }
      return { inserted: 0 }
    })

    const request = new NextRequest('http://localhost/api/intent/bid-policy', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        rows: [
          {
            custom_label_0: 'HIGH',
            tier: 'HIGH',
            target_mode: 'cpa',
            current_target_cpa: 50,
            observed_cpa: 35,
            confidence: 0.81,
          },
        ],
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.decision_count).toBe(1)
    expect(body.decisions[0].decision.recommendedTargetCpa).toBe(42)
    expect(body.persisted.roas_target_recommendations).toBe(0)
    expect(
      mocks.insertRowsSafe.mock.calls.some((call) => call[1] === 'roas_target_recommendations')
    ).toBe(false)
    expect(mocks.insertRowsSafe.mock.calls.some((call) => call[1] === 'policy_decision_log')).toBe(
      true
    )
  })

  it('keeps ROAS mode persistence behavior for shopping tier rows', async () => {
    mocks.recommendBidPolicy.mockReturnValue({
      key: 'MEDIUM|MEDIUM',
      action: 'increase_target',
      recommendedTargetRoas: 3.25,
      confidence: 0.67,
      reasonCodes: ['observed_roas_below_target'],
      policyVersion: 'intent_v1',
    })
    mocks.insertRowsSafe.mockImplementation(async (_client: unknown, table: string) => {
      if (table === 'policy_decision_log') return { inserted: 1 }
      if (table === 'roas_target_recommendations') return { inserted: 1 }
      return { inserted: 0 }
    })

    const request = new NextRequest('http://localhost/api/intent/bid-policy', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        rows: [
          {
            custom_label_0: 'MEDIUM',
            tier: 'MEDIUM',
            current_target_roas: 3.1,
            observed_roas: 2.8,
            confidence: 0.67,
          },
        ],
      }),
    })

    const response = await POST(request)
    const body = await response.json()

    expect(response.status).toBe(200)
    expect(body.decision_count).toBe(1)
    expect(body.decision_mode_breakdown.roas).toBe(1)
    expect(body.persisted.roas_target_recommendations).toBe(1)
    expect(mocks.insertRowsSafe.mock.calls.some((call) => call[1] === 'roas_target_recommendations')).toBe(
      true
    )
    expect(mocks.insertRowsSafe.mock.calls.some((call) => call[1] === 'policy_decision_log')).toBe(
      true
    )
  })

  it('hydrates attribution quality score from attribution confidence when row input is missing it', async () => {
    const maybeSingle = vi.fn().mockResolvedValue({
      data: { confidence_score: 0.44 },
      error: null,
    })
    const limit = vi.fn().mockReturnValue({ maybeSingle })
    const order = vi.fn().mockReturnValue({ limit })
    const eq = vi.fn().mockReturnValue({ order })
    const select = vi.fn().mockReturnValue({ eq })

    mocks.createAdminClient.mockReturnValue({
      from: vi.fn((table: string) => {
        if (table === 'attribution_confidence_daily') {
          return { select }
        }
        return { select: vi.fn() }
      }),
    })

    mocks.recommendBidPolicy.mockReturnValue({
      key: 'HIGH|HIGH',
      action: 'hold',
      recommendedTargetRoas: 3.6,
      confidence: 0.81,
      reasonCodes: ['confidence_low_or_data_degraded'],
      policyVersion: 'intent_v1',
    })
    mocks.insertRowsSafe.mockResolvedValue({ inserted: 1 })

    const request = new NextRequest('http://localhost/api/intent/bid-policy', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        rows: [
          {
            custom_label_0: 'HIGH',
            tier: 'HIGH',
            current_target_roas: 3.6,
            observed_roas: 3.3,
            confidence: 0.81,
          },
        ],
      }),
    })

    const response = await POST(request)
    expect(response.status).toBe(200)

    expect(mocks.recommendBidPolicy).toHaveBeenCalledTimes(1)
    expect(mocks.recommendBidPolicy.mock.calls[0][0]).toMatchObject({
      attributionQualityScore: 0.44,
    })
  })

  it('hydrates value signal score from margin and returns tables when row input is missing it', async () => {
    const maybeSingle = vi.fn().mockResolvedValue({
      data: { confidence_score: 0.77 },
      error: null,
    })
    const limitAttribution = vi.fn().mockReturnValue({ maybeSingle })
    const orderAttribution = vi.fn().mockReturnValue({ limit: limitAttribution })
    const eqAttribution = vi.fn().mockReturnValue({ order: orderAttribution })
    const selectAttribution = vi.fn().mockReturnValue({ eq: eqAttribution })

    const limitMargin = vi.fn().mockResolvedValue({
      data: [{ gross_margin_rate: 0.45 }, { gross_margin_rate: 0.55 }],
      error: null,
    })
    const orderMargin = vi.fn().mockReturnValue({ limit: limitMargin })
    const selectMargin = vi.fn().mockReturnValue({ order: orderMargin })

    const limitReturns = vi.fn().mockResolvedValue({
      data: [{ return_amount: 5 }, { return_amount: 15 }],
      error: null,
    })
    const orderReturns = vi.fn().mockReturnValue({ limit: limitReturns })
    const selectReturns = vi.fn().mockReturnValue({ order: orderReturns })

    mocks.createAdminClient.mockReturnValue({
      from: vi.fn((table: string) => {
        if (table === 'attribution_confidence_daily') {
          return { select: selectAttribution }
        }
        if (table === 'sku_margin_daily') {
          return { select: selectMargin }
        }
        if (table === 'order_line_returns_daily') {
          return { select: selectReturns }
        }
        return { select: vi.fn() }
      }),
    })

    mocks.recommendBidPolicy.mockReturnValue({
      key: 'LOW|LOW',
      action: 'hold',
      recommendedTargetRoas: 2.6,
      confidence: 0.74,
      reasonCodes: ['confidence_low_or_data_degraded'],
      policyVersion: 'intent_v1',
    })
    mocks.insertRowsSafe.mockResolvedValue({ inserted: 1 })

    const request = new NextRequest('http://localhost/api/intent/bid-policy', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        rows: [
          {
            custom_label_0: 'LOW',
            tier: 'LOW',
            current_target_roas: 2.6,
            observed_roas: 2.4,
            confidence: 0.74,
          },
        ],
      }),
    })

    const response = await POST(request)
    expect(response.status).toBe(200)

    expect(mocks.recommendBidPolicy).toHaveBeenCalledTimes(1)
    expect(mocks.recommendBidPolicy.mock.calls[0][0]).toMatchObject({
      valueSignalScore: 0.62,
    })
  })
})
