import { useQuery } from '@tanstack/react-query'
import { createClient } from '@/lib/supabase/client'
import type { PerformanceBaseline, PerformanceStatus } from '@/lib/supabase/types'
import { calculatePerformanceStatus, getCategoryAvgCTR } from '@/lib/performance-utils'

interface CurrentMetrics {
  impressions: number
  clicks: number
  ctr: number
  conversions: number
  conversion_value: number
}

interface UsePerformanceDataResult {
  current: CurrentMetrics | null
  baseline: PerformanceBaseline | null
  status: PerformanceStatus
  loading: boolean
  error: string | null
}

/**
 * Hook to fetch and aggregate performance data for a SKU
 *
 * Data sources:
 * 1. performance_baselines - pre-publish baseline metrics
 * 2. performance_snapshots - post-publish tracked metrics (last 30 days aggregated)
 */
export function usePerformanceData(
  sku: string,
  platform: 'google' | 'bing' | 'shopify' = 'google'
): UsePerformanceDataResult {
  const { data, isLoading, error } = useQuery({
    queryKey: ['performance', sku, platform],
    queryFn: async () => {
      const supabase = createClient()

      // Fetch baseline
      const { data: baseline, error: baselineError } = await supabase
        .from('performance_baselines')
        .select('*')
        .eq('master_sku', sku)
        .eq('platform', platform)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (baselineError) {
        console.error('Error fetching baseline:', baselineError)
      }

      // Fetch snapshots (last 30 days)
      const thirtyDaysAgo = new Date()
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
      const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0]

      const { data: snapshots, error: snapshotsError } = await supabase
        .from('performance_snapshots')
        .select('*')
        .eq('master_sku', sku)
        .eq('platform', platform)
        .gte('snapshot_date', thirtyDaysAgoStr)
        .order('snapshot_date', { ascending: false })

      if (snapshotsError) {
        console.error('Error fetching snapshots:', snapshotsError)
      }

      // Aggregate snapshots into current metrics
      let current: CurrentMetrics | null = null
      if (snapshots && snapshots.length > 0) {
        const totalImpressions = snapshots.reduce((sum, s) => sum + (s.impressions || 0), 0)
        const totalClicks = snapshots.reduce((sum, s) => sum + (s.clicks || 0), 0)
        const totalConversions = snapshots.reduce((sum, s) => sum + (s.conversions || 0), 0)
        const totalConversionValue = snapshots.reduce((sum, s) => sum + (s.conversion_value || 0), 0)
        const avgCTR = totalImpressions > 0 ? totalClicks / totalImpressions : 0

        current = {
          impressions: totalImpressions,
          clicks: totalClicks,
          ctr: avgCTR,
          conversions: totalConversions,
          conversion_value: totalConversionValue,
        }
      }

      // Calculate status
      const categoryAvgCTR = getCategoryAvgCTR('Bathroom Accessories')
      const status = calculatePerformanceStatus(
        current?.ctr,
        baseline?.avg_ctr,
        categoryAvgCTR
      )

      return {
        current,
        baseline: baseline as PerformanceBaseline | null,
        status,
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!sku,
  })

  return {
    current: data?.current || null,
    baseline: data?.baseline || null,
    status: data?.status || 'no-data',
    loading: isLoading,
    error: error ? 'Failed to fetch performance data' : null,
  }
}
