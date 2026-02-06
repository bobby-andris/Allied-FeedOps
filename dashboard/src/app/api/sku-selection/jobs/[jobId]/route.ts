import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params

    if (!jobId) {
      return NextResponse.json(
        { error: 'Job ID is required' },
        { status: 400 }
      )
    }

    // Try Cloud Run first for real-time status
    if (PIPELINE_URL) {
      try {
        const response = await fetch(`${PIPELINE_URL}/batch-status/${jobId}`)
        if (response.ok) {
          const data = await response.json()
          return NextResponse.json(data)
        }
      } catch {
        // Fall through to Supabase query
      }
    }

    // Fallback: query Supabase directly
    const supabase = createAdminClient()

    const { data: job, error: jobError } = await supabase
      .from('batch_generation_jobs')
      .select('*')
      .eq('id', jobId)
      .single()

    if (jobError || !job) {
      return NextResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      )
    }

    const { data: skus } = await supabase
      .from('batch_generation_job_skus')
      .select('*')
      .eq('job_id', jobId)

    return NextResponse.json({
      job_id: job.id,
      status: job.status,
      total_skus: job.total_skus,
      completed_skus: job.completed_skus || 0,
      failed_skus: job.failed_skus || 0,
      skus: skus || [],
    })
  } catch (error) {
    console.error('Job status API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
