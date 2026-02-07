/**
 * GET /api/monitoring/performance-delta
 *
 * Calculate performance changes between baseline and post-publish snapshots.
 * Shows which SKUs improved/degraded after content optimization.
 *
 * Query params:
 * - master_sku?: Filter by specific SKU
 * - platform?: Filter by platform (google/bing)
 * - min_days?: Minimum days since publish (default: 7)
 * - max_days?: Maximum days since publish (default: 30)
 *
 * Returns:
 * - SKU performance deltas (baseline vs current)
 * - Statistical significance indicators
 * - Trend direction (improving/declining/stable)
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

interface PerformanceDelta {
  master_sku: string
  platform: string
  environment: string
  days_since_publish: number
  publish_event_id: number
  content_version: number | null

  // Baseline metrics
  baseline_impressions: number
  baseline_clicks: number
  baseline_ctr: number
  baseline_conversions: number
  baseline_cvr: number
  baseline_roas: number

  // Current metrics
  current_impressions: number
  current_clicks: number
  current_ctr: number
  current_conversions: number
  current_cvr: number
  current_roas: number

  // Deltas (percentage change)
  impressions_delta: number
  clicks_delta: number
  ctr_delta: number
  conversions_delta: number
  cvr_delta: number
  roas_delta: number

  // Trend
  trend: 'improving' | 'declining' | 'stable'
  significance: 'high' | 'medium' | 'low' | 'insufficient_data'
}

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { searchParams } = new URL(request.url)

    const filterSku = searchParams.get('master_sku')
    const filterPlatform = searchParams.get('platform') as 'google' | 'bing' | null
    const minDays = parseInt(searchParams.get('min_days') || '7')
    const maxDays = parseInt(searchParams.get('max_days') || '30')

    // 1. Get latest snapshots for each SKU/platform combination
    let snapshotQuery = supabase
      .from('performance_snapshots')
      .select('*')
      .gte('days_since_publish', minDays)
      .lte('days_since_publish', maxDays)
      .order('snapshot_date', { ascending: false })

    if (filterSku) {
      snapshotQuery = snapshotQuery.eq('master_sku', filterSku)
    }
    if (filterPlatform) {
      snapshotQuery = snapshotQuery.eq('platform', filterPlatform)
    }

    const { data: snapshots, error: snapshotError } = await snapshotQuery

    if (snapshotError) {
      return NextResponse.json(
        { error: `Failed to fetch snapshots: ${snapshotError.message}` },
        { status: 500 }
      )
    }

    if (!snapshots || snapshots.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No snapshots found in specified time range',
        deltas: [],
      })
    }

    // Group by SKU+platform (get most recent snapshot for each)
    const latestSnapshots = new Map<string, typeof snapshots[0]>()
    for (const snapshot of snapshots) {
      const key = `${snapshot.master_sku}:${snapshot.platform}`
      if (!latestSnapshots.has(key)) {
        latestSnapshots.set(key, snapshot)
      }
    }

    // 2. Get baselines for these SKUs
    const skus = Array.from(new Set(snapshots.map((s) => s.master_sku)))
    const { data: baselines, error: baselineError } = await supabase
      .from('performance_baselines')
      .select('*')
      .in('master_sku', skus)

    if (baselineError) {
      return NextResponse.json(
        { error: `Failed to fetch baselines: ${baselineError.message}` },
        { status: 500 }
      )
    }

    // Map SKU+platform -> baseline
    const baselineMap = new Map<string, typeof baselines[0]>()
    for (const baseline of baselines || []) {
      const key = `${baseline.master_sku}:${baseline.platform}`
      baselineMap.set(key, baseline)
    }

    // 3. Calculate deltas
    const deltas: PerformanceDelta[] = []

    for (const [key, snapshot] of latestSnapshots) {
      const baseline = baselineMap.get(key)
      if (!baseline) {
        // No baseline - can't calculate delta
        continue
      }

      // Calculate percentage changes
      const calculateDelta = (current: number, baseline: number): number => {
        if (baseline === 0) return current > 0 ? 100 : 0
        return ((current - baseline) / baseline) * 100
      }

      const impressionsDelta = calculateDelta(snapshot.impressions || 0, baseline.avg_impressions || 0)
      const clicksDelta = calculateDelta(snapshot.clicks || 0, baseline.avg_clicks || 0)
      const ctrDelta = calculateDelta(snapshot.ctr || 0, baseline.avg_ctr || 0)
      const conversionsDelta = calculateDelta(snapshot.conversions || 0, baseline.avg_conversions || 0)
      const cvrDelta = calculateDelta(snapshot.cvr || 0, baseline.avg_cvr || 0)
      const roasDelta = calculateDelta(snapshot.roas || 0, baseline.avg_roas || 0)

      // Determine trend (simple heuristic: CTR + CVR + ROAS)
      const trendScore = (ctrDelta + cvrDelta + roasDelta) / 3
      let trend: PerformanceDelta['trend']
      if (trendScore > 5) {
        trend = 'improving'
      } else if (trendScore < -5) {
        trend = 'declining'
      } else {
        trend = 'stable'
      }

      // Determine significance based on sample size and magnitude
      let significance: PerformanceDelta['significance']
      const totalImpressions = (snapshot.impressions || 0) + (baseline.avg_impressions || 0)
      const maxDelta = Math.max(
        Math.abs(ctrDelta),
        Math.abs(cvrDelta),
        Math.abs(roasDelta)
      )

      if (totalImpressions < 100) {
        significance = 'insufficient_data'
      } else if (totalImpressions > 1000 && maxDelta > 10) {
        significance = 'high'
      } else if (totalImpressions > 500 || maxDelta > 5) {
        significance = 'medium'
      } else {
        significance = 'low'
      }

      deltas.push({
        master_sku: snapshot.master_sku,
        platform: snapshot.platform,
        environment: snapshot.environment,
        days_since_publish: snapshot.days_since_publish || 0,
        publish_event_id: snapshot.publish_event_id || 0,
        content_version: snapshot.content_version,

        baseline_impressions: baseline.avg_impressions || 0,
        baseline_clicks: baseline.avg_clicks || 0,
        baseline_ctr: baseline.avg_ctr || 0,
        baseline_conversions: baseline.avg_conversions || 0,
        baseline_cvr: baseline.avg_cvr || 0,
        baseline_roas: baseline.avg_roas || 0,

        current_impressions: snapshot.impressions || 0,
        current_clicks: snapshot.clicks || 0,
        current_ctr: snapshot.ctr || 0,
        current_conversions: snapshot.conversions || 0,
        current_cvr: snapshot.cvr || 0,
        current_roas: snapshot.roas || 0,

        impressions_delta: impressionsDelta,
        clicks_delta: clicksDelta,
        ctr_delta: ctrDelta,
        conversions_delta: conversionsDelta,
        cvr_delta: cvrDelta,
        roas_delta: roasDelta,

        trend,
        significance,
      })
    }

    // Sort by significance (high first) then by trend score
    deltas.sort((a, b) => {
      const sigOrder = { high: 0, medium: 1, low: 2, insufficient_data: 3 }
      const sigDiff = sigOrder[a.significance] - sigOrder[b.significance]
      if (sigDiff !== 0) return sigDiff

      // Within same significance, sort by CTR delta (descending)
      return b.ctr_delta - a.ctr_delta
    })

    // Summary stats
    const improving = deltas.filter((d) => d.trend === 'improving').length
    const declining = deltas.filter((d) => d.trend === 'declining').length
    const stable = deltas.filter((d) => d.trend === 'stable').length

    return NextResponse.json({
      success: true,
      deltas,
      summary: {
        total: deltas.length,
        improving,
        declining,
        stable,
        avg_ctr_delta: deltas.reduce((sum, d) => sum + d.ctr_delta, 0) / deltas.length || 0,
        avg_cvr_delta: deltas.reduce((sum, d) => sum + d.cvr_delta, 0) / deltas.length || 0,
        avg_roas_delta: deltas.reduce((sum, d) => sum + d.roas_delta, 0) / deltas.length || 0,
      },
    })
  } catch (error) {
    console.error('Performance delta calculation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
