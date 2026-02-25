/**
 * GET /api/funnel-snapshots/trends
 *
 * Returns 7-day vs previous-7-day aggregated funnel metrics
 * from funnel_snapshots_daily for trend summary cards.
 */

import { NextResponse } from 'next/server'

import { createAdminClient } from '@/lib/supabase/admin'

interface SnapshotRow {
  snapshot_date: string
  impressions: number
  clicks: number
  cost_micros: number
  conversions: number
  conversions_value: number
}

interface PeriodMetrics {
  impressions: number
  clicks: number
  ctr: number
  cost_micros: number
  conversions: number
  conversions_value: number
  roas: number
}

function zeroPeriod(): PeriodMetrics {
  return {
    impressions: 0,
    clicks: 0,
    ctr: 0,
    cost_micros: 0,
    conversions: 0,
    conversions_value: 0,
    roas: 0,
  }
}

function aggregateRows(rows: SnapshotRow[]): PeriodMetrics {
  const sums = rows.reduce(
    (acc, row) => ({
      impressions: acc.impressions + (row.impressions ?? 0),
      clicks: acc.clicks + (row.clicks ?? 0),
      cost_micros: acc.cost_micros + (row.cost_micros ?? 0),
      conversions: acc.conversions + (row.conversions ?? 0),
      conversions_value: acc.conversions_value + (row.conversions_value ?? 0),
    }),
    { impressions: 0, clicks: 0, cost_micros: 0, conversions: 0, conversions_value: 0 },
  )

  const ctr = sums.impressions > 0 ? sums.clicks / sums.impressions : 0
  const costDollars = sums.cost_micros / 1e6
  const roas = costDollars > 0 ? sums.conversions_value / costDollars : 0

  return {
    ...sums,
    ctr,
    roas,
  }
}

export async function GET() {
  try {
    const supabase = createAdminClient()

    // Compute date boundaries in UTC
    const today = new Date()

    const yesterday = new Date(today)
    yesterday.setUTCDate(yesterday.getUTCDate() - 1)
    const yesterdayStr = yesterday.toISOString().split('T')[0]

    const fifteenDaysAgo = new Date(today)
    fifteenDaysAgo.setUTCDate(fifteenDaysAgo.getUTCDate() - 15)
    const fifteenDaysAgoStr = fifteenDaysAgo.toISOString().split('T')[0]

    const sevenDaysAgo = new Date(today)
    sevenDaysAgo.setUTCDate(sevenDaysAgo.getUTCDate() - 7)
    const sevenDaysAgoStr = sevenDaysAgo.toISOString().split('T')[0]

    // Fetch all rows from last 15 days
    const { data: rows, error } = await supabase
      .from('funnel_snapshots_daily')
      .select('snapshot_date, impressions, clicks, cost_micros, conversions, conversions_value')
      .gte('snapshot_date', fifteenDaysAgoStr)
      .lte('snapshot_date', yesterdayStr)

    if (error) {
      throw new Error(`Supabase query failed: ${error.message}`)
    }

    const allRows = (rows ?? []) as SnapshotRow[]

    if (allRows.length === 0) {
      return NextResponse.json(
        {
          has_data: false,
          has_previous: false,
          current: zeroPeriod(),
          previous: null,
        },
        {
          headers: { 'Cache-Control': 'public, s-maxage=3600' },
        },
      )
    }

    // Split into current (last 7 days) and previous (prior 7 days)
    const currentRows = allRows.filter((r) => r.snapshot_date > sevenDaysAgoStr)
    const previousRows = allRows.filter((r) => r.snapshot_date <= sevenDaysAgoStr)

    const current = currentRows.length > 0 ? aggregateRows(currentRows) : zeroPeriod()
    const hasPrevious = previousRows.length > 0
    const previous = hasPrevious ? aggregateRows(previousRows) : null

    return NextResponse.json(
      {
        has_data: true,
        has_previous: hasPrevious,
        current,
        previous,
      },
      {
        headers: { 'Cache-Control': 'public, s-maxage=3600' },
      },
    )
  } catch (error) {
    console.error('[funnel-trends] Error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 },
    )
  }
}
