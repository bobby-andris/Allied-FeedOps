/**
 * GET /api/monitoring/sync-jobs
 *
 * Fetches search query sync job history from search_query_sync_jobs table.
 * Returns active jobs (running/pending) and last 5 completed/failed jobs.
 */

import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET() {
  try {
    const supabase = await createClient()

    const selectColumns =
      'id, status, job_type, days_lookback, queries_fetched, queries_enriched, error_message, created_at, started_at, completed_at'

    // Get active jobs (status = 'running' or 'pending')
    const { data: activeData, error: activeError } = await supabase
      .from('search_query_sync_jobs')
      .select(selectColumns)
      .in('status', ['running', 'pending'])
      .order('created_at', { ascending: false })
      .limit(5)

    if (activeError) {
      console.error('Error fetching active sync jobs:', activeError)
    }

    // Get last 5 completed/failed jobs
    const { data: historyData, error: historyError } = await supabase
      .from('search_query_sync_jobs')
      .select(selectColumns)
      .in('status', ['completed', 'failed'])
      .order('created_at', { ascending: false })
      .limit(5)

    if (historyError) {
      console.error('Error fetching sync job history:', historyError)
    }

    return NextResponse.json({
      active: activeData || [],
      history: historyData || [],
    })
  } catch (error) {
    console.error('Sync jobs fetch error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch sync jobs' },
      { status: 500 }
    )
  }
}
