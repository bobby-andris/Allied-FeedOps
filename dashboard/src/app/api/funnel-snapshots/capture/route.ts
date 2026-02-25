/**
 * POST /api/funnel-snapshots/capture
 *
 * Captures yesterday's shopping funnel tier data from Google Ads
 * and persists it to the funnel_snapshots_daily table in Supabase.
 *
 * Auth: Bearer token must match CRON_SECRET env var.
 * Designed to be called daily by GCP Cloud Scheduler at 6 AM UTC.
 */

import { NextRequest, NextResponse } from 'next/server'

import { getLabelTierPerformance } from '@/lib/shopping-funnel/service'
import { createAdminClient } from '@/lib/supabase/admin'

/**
 * Send a failure alert to Slack via webhook.
 * Silently skips if SLACK_WEBHOOK_URL is not configured.
 * Never throws — Slack failures must not break capture responses.
 */
async function sendSlackAlert(message: string): Promise<void> {
  const webhookUrl = process.env.SLACK_WEBHOOK_URL
  if (!webhookUrl) return

  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: message }),
    })
  } catch {
    // Slack failure must never break the capture endpoint
  }
}

export async function POST(request: NextRequest) {
  // --- Auth check ---
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

  try {
    // --- Compute yesterday's date in UTC ---
    const d = new Date()
    d.setUTCDate(d.getUTCDate() - 1)
    const yesterday = d.toISOString().split('T')[0]

    console.log(`[funnel-capture] Starting capture for ${yesterday}`)

    // --- Fetch tier performance from Google Ads ---
    const result = await getLabelTierPerformance({
      startDate: yesterday,
      endDate: yesterday,
    })

    console.log(`[funnel-capture] Fetched ${result.rows.length} rows from Google Ads`)

    // --- Map to Supabase rows ---
    const rows = result.rows.map((row) => ({
      snapshot_date: yesterday,
      custom_label_0: row.custom_label_0,
      tier: row.tier,
      impressions: row.impressions,
      clicks: row.clicks,
      cost_micros: row.cost_micros,
      conversions: row.conversions,
      conversions_value: row.conversions_value,
      roas: row.roas,
    }))

    // --- Upsert to Supabase ---
    const supabase = createAdminClient()

    if (rows.length > 0) {
      const { error: upsertError } = await supabase
        .from('funnel_snapshots_daily')
        .upsert(rows, { onConflict: 'snapshot_date,custom_label_0,tier' })

      if (upsertError) {
        throw new Error(`Upsert failed: ${upsertError.message}`)
      }
    }

    console.log(`[funnel-capture] Upserted ${rows.length} rows`)

    // --- Zero-row alert ---
    if (rows.length === 0) {
      await sendSlackAlert(
        `:warning: FunnelCapture returned 0 rows for ${yesterday}. Google Ads may have no data or the query failed silently.`
      )
    }

    // --- 90-day retention cleanup ---
    const cutoff = new Date()
    cutoff.setUTCDate(cutoff.getUTCDate() - 90)
    const cutoffDate = cutoff.toISOString().split('T')[0]

    const { data: deletedRows } = await supabase
      .from('funnel_snapshots_daily')
      .delete()
      .lt('snapshot_date', cutoffDate)
      .select('id')

    const rowsDeleted = deletedRows?.length ?? 0

    console.log(`[funnel-capture] Cleanup complete: ${rowsDeleted} rows older than ${cutoffDate} deleted`)

    return NextResponse.json({
      snapshot_date: yesterday,
      rows_captured: rows.length,
      rows_deleted: rowsDeleted,
    })
  } catch (error) {
    console.error('[funnel-capture] Error:', error)
    const errorMsg = error instanceof Error ? error.message : 'Unknown error'

    // Compute yesterday for alert context (d may not be in scope if error was early)
    const alertDate = new Date()
    alertDate.setUTCDate(alertDate.getUTCDate() - 1)
    const alertYesterday = alertDate.toISOString().split('T')[0]
    await sendSlackAlert(
      `:warning: FunnelCapture FAILED for ${alertYesterday}\nError: ${errorMsg}`
    )

    return NextResponse.json(
      { error: errorMsg },
      { status: 500 }
    )
  }
}
