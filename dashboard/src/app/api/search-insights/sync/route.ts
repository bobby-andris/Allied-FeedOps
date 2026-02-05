import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL || 'https://feedops-pipeline-623866089882.us-east1.run.app'

/**
 * POST /api/search-insights/sync
 * Trigger a search terms sync job
 *
 * Body:
 * - days: number (7-90, default 30)
 * - limit: number (100-5000, default 1000)
 * - enrichWithKeywordPlanner: boolean (default true)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      days = 30,
      limit = 1000,
      enrichWithKeywordPlanner = true,
    } = body

    // Validate inputs
    if (days < 7 || days > 90) {
      return NextResponse.json(
        { error: 'days must be between 7 and 90' },
        { status: 400 }
      )
    }

    if (limit < 100 || limit > 5000) {
      return NextResponse.json(
        { error: 'limit must be between 100 and 5000' },
        { status: 400 }
      )
    }

    // Call Cloud Run endpoint to start sync
    const response = await fetch(`${PIPELINE_URL}/search-insights/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        days,
        limit,
        enrich_with_keyword_planner: enrichWithKeywordPlanner,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Cloud Run sync error:', errorText)
      return NextResponse.json(
        { error: `Sync failed: ${response.statusText}` },
        { status: response.status }
      )
    }

    const result = await response.json()

    return NextResponse.json({
      success: true,
      jobId: result.job_id,
      status: result.status,
      daysRequested: days,
      enrichRequested: enrichWithKeywordPlanner,
    })
  } catch (error) {
    console.error('Sync trigger error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * GET /api/search-insights/sync
 * Get recent sync jobs and their status
 */
export async function GET() {
  try {
    const supabase = await createClient()

    // Get recent sync jobs
    const { data: jobs, error } = await supabase
      .from('search_query_sync_jobs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(10)

    if (error) {
      console.error('Error fetching sync jobs:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Get the most recent completed job
    const lastCompleted = jobs?.find((j) => j.status === 'completed')

    return NextResponse.json({
      jobs: jobs || [],
      lastSync: lastCompleted?.completed_at || null,
      lastSyncQueriesFetched: lastCompleted?.queries_fetched || 0,
      lastSyncQueriesEnriched: lastCompleted?.queries_enriched || 0,
    })
  } catch (error) {
    console.error('Sync jobs fetch error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
