import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest, NextResponse } from 'next/server'

/**
 * GET /api/competitors/scrape/[jobId]
 * Get the status of a scrape job
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const supabase = createAdminClient()

    const { data: job, error } = await supabase
      .from('competitor_scrape_jobs')
      .select('*')
      .eq('id', jobId)
      .single()

    if (error) {
      console.error('Error fetching job:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    if (!job) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 })
    }

    return NextResponse.json({ job })
  } catch (error) {
    console.error('Job status API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

/**
 * PATCH /api/competitors/scrape/[jobId]
 * Update the status of a scrape job
 *
 * Body:
 * - status: 'pending' | 'running' | 'completed' | 'failed'
 * - apify_run_id?: string
 * - apify_dataset_id?: string
 * - listings_count?: number
 * - error_message?: string
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    const body = await request.json()
    const supabase = createAdminClient()

    // Build update object
    const update: Record<string, unknown> = {}

    if (body.status) {
      update.status = body.status
      if (body.status === 'running' && !body.started_at) {
        update.started_at = new Date().toISOString()
      }
      if (['completed', 'failed'].includes(body.status)) {
        update.completed_at = new Date().toISOString()
      }
    }

    if (body.apify_run_id !== undefined) {
      update.apify_run_id = body.apify_run_id
    }

    if (body.apify_dataset_id !== undefined) {
      update.apify_dataset_id = body.apify_dataset_id
    }

    if (body.listings_count !== undefined) {
      update.listings_count = body.listings_count
    }

    if (body.error_message !== undefined) {
      update.error_message = body.error_message
    }

    const { data: job, error } = await supabase
      .from('competitor_scrape_jobs')
      .update(update)
      .eq('id', jobId)
      .select()
      .single()

    if (error) {
      console.error('Error updating job:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ job })
  } catch (error) {
    console.error('Job update API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
