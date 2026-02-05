import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

/**
 * GET /api/search-insights/sync/[jobId]
 * Get status of a specific sync job
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params

    if (!jobId) {
      return NextResponse.json({ error: 'Job ID required' }, { status: 400 })
    }

    const supabase = await createClient()

    const { data: job, error } = await supabase
      .from('search_query_sync_jobs')
      .select('*')
      .eq('id', jobId)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Job not found' }, { status: 404 })
      }
      console.error('Error fetching sync job:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Calculate progress percentage
    let progress = 0
    if (job.status === 'completed') {
      progress = 100
    } else if (job.status === 'running') {
      // Estimate based on expected time (rough approximation)
      const startedAt = new Date(job.started_at).getTime()
      const now = Date.now()
      const elapsed = (now - startedAt) / 1000 // seconds
      // Assume ~60 seconds for a full sync
      progress = Math.min(Math.round((elapsed / 60) * 100), 95)
    }

    return NextResponse.json({
      jobId: job.id,
      status: job.status,
      jobType: job.job_type,
      daysLookback: job.days_lookback,
      limitResults: job.limit_results,
      enrichWithKeywordPlanner: job.enrich_with_keyword_planner,
      queriesFetched: job.queries_fetched,
      queriesEnriched: job.queries_enriched,
      errorMessage: job.error_message,
      progress,
      createdAt: job.created_at,
      startedAt: job.started_at,
      completedAt: job.completed_at,
    })
  } catch (error) {
    console.error('Job status fetch error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
