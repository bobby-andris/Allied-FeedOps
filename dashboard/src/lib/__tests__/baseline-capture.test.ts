import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { SupabaseClient } from '@supabase/supabase-js'

import { captureBaseline } from '../baseline-capture'
import * as googleAds from '../google-ads'

vi.mock('../google-ads')

type MockContext = {
  supabase: SupabaseClient
  upsert: ReturnType<typeof vi.fn>
}

function createSupabaseMock(shopifyProductId: string | null = '1234567890'): MockContext {
  const single = vi.fn().mockResolvedValue({
    data: shopifyProductId ? { shopify_product_id: shopifyProductId } : null,
    error: null,
  })
  const limit = vi.fn(() => ({ single }))
  const eq = vi.fn(() => ({ limit }))
  const select = vi.fn(() => ({ eq }))
  const upsert = vi.fn().mockResolvedValue({ data: null, error: null })

  const from = vi.fn((table: string) => {
    if (table === 'variant_index') {
      return { select }
    }
    if (table === 'performance_baselines') {
      return { upsert }
    }
    return {}
  })

  return {
    supabase: { from } as unknown as SupabaseClient,
    upsert,
  }
}

describe('captureBaseline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(googleAds.getDateRange).mockReturnValue({
      startDate: '2026-01-08',
      endDate: '2026-02-07',
    })
  })

  it('captures and stores 30-day baseline metrics before publishing', async () => {
    const { supabase, upsert } = createSupabaseMock('1234567890')
    const performanceMap = new Map([
      ['1234567890', {
        productItemId: 'shopify_US_1234567890_9876543210',
        impressions: 45200,
        clicks: 1446,
        ctr: 0.032,
        conversions: 89,
        conversionValue: 2847,
        cost: 1200,
        roas: 2.37,
        dailyData: [],
      }],
    ])

    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(performanceMap)

    const result = await captureBaseline(supabase, '920D-6', 'google')

    expect(result).toEqual({
      master_sku: '920D-6',
      platform: 'google',
      baseline_start_date: '2026-01-08',
      baseline_end_date: '2026-02-07',
      avg_impressions: 1506.67,
      avg_clicks: 48.2,
      avg_ctr: 0.032,
      avg_conversions: 2.97,
      avg_conversion_value: 94.9,
      avg_cvr: 0.0615,
      avg_cost: 40,
      avg_roas: 2.37,
    })

    expect(upsert).toHaveBeenCalledTimes(1)
  })

  it('returns null when no performance data is available', async () => {
    const { supabase, upsert } = createSupabaseMock('1234567890')
    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(new Map())

    const result = await captureBaseline(supabase, '920D-6', 'google')

    expect(result).toBeNull()
    expect(upsert).not.toHaveBeenCalled()
  })

  it('calculates avg_cvr from conversions/clicks when clicks are present', async () => {
    const { supabase } = createSupabaseMock('1234567890')
    const performanceMap = new Map([
      ['1234567890', {
        productItemId: 'shopify_US_1234567890_9876543210',
        impressions: 10000,
        clicks: 200,
        ctr: 0.02,
        conversions: 10,
        conversionValue: 500,
        cost: 100,
        roas: 5.0,
        dailyData: [],
      }],
    ])

    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(performanceMap)

    const result = await captureBaseline(supabase, '920D-6', 'google')

    expect(result?.avg_cvr).toBe(0.05)
  })

  it('sets avg_cvr to zero when clicks are zero', async () => {
    const { supabase } = createSupabaseMock('1234567890')
    const performanceMap = new Map([
      ['1234567890', {
        productItemId: 'shopify_US_1234567890_9876543210',
        impressions: 10000,
        clicks: 0,
        ctr: 0,
        conversions: 0,
        conversionValue: 0,
        cost: 0,
        roas: 0,
        dailyData: [],
      }],
    ])

    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(performanceMap)

    const result = await captureBaseline(supabase, '920D-6', 'google')

    expect(result?.avg_cvr).toBe(0)
  })
})
