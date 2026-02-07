/**
 * Tests for performance baseline capture
 *
 * RED -> GREEN -> REFACTOR cycle
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { captureBaseline } from '../baseline-capture'
import type { SupabaseClient } from '@supabase/supabase-js'
import * as googleAds from '../google-ads'

// Mock Google Ads module
vi.mock('../google-ads')

describe('captureBaseline', () => {
  let mockSupabase: SupabaseClient

  beforeEach(() => {
    vi.clearAllMocks()

    // Create mock Supabase client
    mockSupabase = {
      from: vi.fn(() => ({
        select: vi.fn(() => ({
          eq: vi.fn(() => ({
            single: vi.fn(() => Promise.resolve({
              data: { shopify_product_id: '1234567890' },
              error: null,
            })),
          })),
        })),
        upsert: vi.fn(() => Promise.resolve({ data: null, error: null })),
      })),
    } as unknown as SupabaseClient
  })

  it('captures 30-day performance baseline before publishing', async () => {
    // Setup: Mock Google Ads API to return performance data
    const mockPerformance = new Map([
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

    vi.mocked(googleAds.getDateRange).mockReturnValue({
      startDate: '2026-01-08',
      endDate: '2026-02-07',
    })
    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(mockPerformance)

    // Execute: Capture baseline for master SKU
    const result = await captureBaseline(mockSupabase, '920D-6', 'google')

    // Verify: Baseline data calculated and stored
    expect(result).toEqual({
      master_sku: '920D-6',
      platform: 'google',
      baseline_start_date: '2026-01-08',
      baseline_end_date: '2026-02-07',
      avg_impressions: 1506.67, // 45200 / 30 days
      avg_clicks: 48.2, // 1446 / 30
      avg_ctr: 0.032,
      avg_conversions: 2.97, // 89 / 30
      avg_conversion_value: 94.90, // 2847 / 30
      avg_cvr: 0.0615, // 89 / 1446
      avg_cost: 40.00, // 1200 / 30
      avg_roas: 2.37,
    })

    // Verify: Data upserted to Supabase
    expect(mockSupabase.from).toHaveBeenCalledWith('performance_baselines')
  })

  it('returns null when product has no performance data', async () => {
    // Setup: Empty performance data
    vi.mocked(googleAds.getDateRange).mockReturnValue({
      startDate: '2026-01-08',
      endDate: '2026-02-07',
    })
    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(new Map())

    // Execute
    const result = await captureBaseline(mockSupabase, '920D-6', 'google')

    // Verify: Returns null when no data
    expect(result).toBeNull()
  })

  it('calculates CVR correctly when there are clicks', async () => {
    const mockPerformance = new Map([
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

    vi.mocked(googleAds.getDateRange).mockReturnValue({
      startDate: '2026-01-08',
      endDate: '2026-02-07',
    })
    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(mockPerformance)

    const result = await captureBaseline(mockSupabase, '920D-6', 'google')

    // CVR = conversions / clicks = 10 / 200 = 0.05
    expect(result?.avg_cvr).toBe(0.05)
  })

  it('sets CVR to 0 when there are no clicks', async () => {
    const mockPerformance = new Map([
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

    vi.mocked(googleAds.getDateRange).mockReturnValue({
      startDate: '2026-01-08',
      endDate: '2026-02-07',
    })
    vi.mocked(googleAds.fetchShoppingPerformance).mockResolvedValue(mockPerformance)

    const result = await captureBaseline(mockSupabase, '920D-6', 'google')

    // CVR = 0 when no clicks
    expect(result?.avg_cvr).toBe(0)
  })
})
