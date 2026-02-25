/**
 * POST /api/funnel-snapshots/backfill
 *
 * Backfills funnel_snapshots_daily with historical Google Ads tier data.
 * Accepts a date range and iterates day-by-day, calling getLabelTierPerformance
 * for each day and upserting results to Supabase.
 *
 * Auth: Bearer token must match CRON_SECRET env var.
 * Safety: Max 90 days per request.
 *
 * Designed for one-time use to populate historical data for trend cards.
 * Run against localhost to avoid Vercel function timeouts.
 */

import { NextRequest, NextResponse } from 'next/server'

import { getLabelTierPerformance } from '@/lib/shopping-funnel/service'
import { createAdminClient } from '@/lib/supabase/admin'

export async function POST(request: NextRequest) {
  // --- Auth check (same pattern as capture/route.ts) ---
  const cronSecret = process.env.CRON_SECRET
  if (!cronSecret) {
    return NextResponse.json(
      { error: 'CRON_SECRET not configured' },
      { status: 401 }
    )
  }

  const authHeader = request.headers.get('authorization') ?? ''
  const token = authHeader.replace(/^Bearer\s+/i, '')
  if (token !== cronSecret) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  // --- Parse date range from request body ---
  let body: { start_date?: string; end_date?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body' },
      { status: 400 }
    )
  }

  const { start_date, end_date } = body

  if (!start_date || !end_date) {
    return NextResponse.json(
      { error: 'start_date and end_date required' },
      { status: 400 }
    )
  }

  // --- Safety: limit max range to 90 days ---
  const startMs = new Date(start_date).getTime()
  const endMs = new Date(end_date).getTime()
  const dayCount = Math.ceil((endMs - startMs) / (1000 * 60 * 60 * 24)) + 1

  if (dayCount > 90) {
    return NextResponse.json(
      { error: 'Max 90 days per request' },
      { status: 400 }
    )
  }

  // --- Iterate day-by-day ---
  const supabase = createAdminClient()
  const results: Array<{ date: string; rows: number }> = []

  const current = new Date(start_date)
  const endDate = new Date(end_date)

  while (current <= endDate) {
    const dateStr = current.toISOString().split('T')[0]

    try {
      const result = await getLabelTierPerformance({
        startDate: dateStr,
        endDate: dateStr,
      })

      // Map to Supabase rows — EXACT same mapping as capture/route.ts lines 52-60
      const rows = result.rows.map((row) => ({
        snapshot_date: dateStr,
        custom_label_0: row.custom_label_0,
        tier: row.tier,
        impressions: row.impressions,
        clicks: row.clicks,
        cost_micros: row.cost_micros,
        conversions: row.conversions,
        conversions_value: row.conversions_value,
        roas: row.roas,
      }))

      if (rows.length > 0) {
        const { error: upsertError } = await supabase
          .from('funnel_snapshots_daily')
          .upsert(rows, { onConflict: 'snapshot_date,custom_label_0,tier' })

        if (upsertError) {
          console.error(`[backfill] Upsert failed for ${dateStr}:`, upsertError.message)
          results.push({ date: dateStr, rows: -1 })
          current.setDate(current.getDate() + 1)
          continue
        }
      }

      results.push({ date: dateStr, rows: rows.length })
      console.log(`[backfill] ${dateStr}: ${rows.length} rows`)
    } catch (err) {
      console.error(`[backfill] Error for ${dateStr}:`, err)
      results.push({ date: dateStr, rows: -1 })
    }

    current.setDate(current.getDate() + 1)
  }

  return NextResponse.json({
    total_days: results.length,
    total_rows: results.filter((r) => r.rows > 0).reduce((sum, r) => sum + r.rows, 0),
    days: results,
  })
}
