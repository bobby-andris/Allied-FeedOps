import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

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

    const supabase = await createClient()

    // Fetch job details
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

    // Fetch SKU statuses for detailed progress
    const { data: skuRecords, error: skuError } = await supabase
      .from('batch_generation_job_skus')
      .select('master_sku, status, error_message')
      .eq('job_id', jobId)

    if (skuError) {
      console.error('Failed to fetch job SKUs:', skuError)
    }

    const skusByStatus = {
      pending: [] as string[],
      processing: [] as string[],
      completed: [] as string[],
      failed: [] as { sku: string; error: string }[],
    }

    for (const record of skuRecords || []) {
      if (record.status === 'failed') {
        skusByStatus.failed.push({
          sku: record.master_sku,
          error: record.error_message || 'Unknown error',
        })
      } else {
        skusByStatus[record.status as keyof typeof skusByStatus]?.push?.(record.master_sku)
      }
    }

    // Calculate estimated remaining time
    const completedCount = Number(job.completed_skus || 0) + Number(job.failed_skus || 0)
    const remainingCount = Math.max(Number(job.total_skus || 0) - completedCount, 0)
    const estimatedRemainingMinutes = job.status === 'processing'
      ? Math.ceil(remainingCount * 0.5) // ~30 seconds per SKU
      : 0
    const options = (job.options && typeof job.options === 'object')
      ? job.options as Record<string, unknown>
      : {}
    const expandedTotal = Number(options.expanded_total_skus ?? 0)
    const expandedCompleted = Number(options.expanded_completed_skus ?? 0)
    const expandedFailed = Number(options.expanded_failed_skus ?? 0)

    return NextResponse.json({
      job_id: job.id,
      status: job.status,
      total_skus: job.total_skus,
      completed_skus: job.completed_skus,
      failed_skus: job.failed_skus,
      expanded_total_skus: Number.isFinite(expandedTotal) ? expandedTotal : 0,
      expanded_completed_skus: Number.isFinite(expandedCompleted) ? expandedCompleted : 0,
      expanded_failed_skus: Number.isFinite(expandedFailed) ? expandedFailed : 0,
      options: job.options,
      created_at: job.created_at,
      started_at: job.started_at,
      completed_at: job.completed_at,
      estimated_remaining_minutes: estimatedRemainingMinutes,
      skus_by_status: skusByStatus,
      errors: skusByStatus.failed.length > 0 ? skusByStatus.failed : undefined,
    })
  } catch (error) {
    console.error('Job status API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
