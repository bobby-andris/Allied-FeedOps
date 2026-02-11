import { createAdminClient } from '@/lib/supabase/admin'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const supabase = createAdminClient()

    const { data: jobs, error } = await supabase
      .from('batch_generation_jobs')
      .select('id, status, total_skus, completed_skus, failed_skus, options, error_message, created_at, started_at, completed_at')
      .order('created_at', { ascending: false })
      .limit(50)

    if (error) {
      console.error('Failed to fetch jobs:', error)
      return NextResponse.json(
        { error: 'Failed to fetch generation jobs' },
        { status: 500 }
      )
    }

    // For each job, get the SKU list
    const jobIds = (jobs || []).map(j => j.id)

    const skusByJob: Record<string, string[]> = {}
    if (jobIds.length > 0) {
      const { data: skuRecords } = await supabase
        .from('batch_generation_job_skus')
        .select('job_id, master_sku')
        .in('job_id', jobIds)

      for (const record of skuRecords || []) {
        if (!skusByJob[record.job_id]) {
          skusByJob[record.job_id] = []
        }
        skusByJob[record.job_id].push(record.master_sku)
      }
    }

    const result = (jobs || []).map(job => {
      const options = (job.options && typeof job.options === 'object')
        ? job.options as Record<string, unknown>
        : {}
      const expandedTotal = Number(options.expanded_total_skus ?? 0)
      const expandedCompleted = Number(options.expanded_completed_skus ?? 0)
      const expandedFailed = Number(options.expanded_failed_skus ?? 0)

      return {
        ...job,
        expanded_total_skus: Number.isFinite(expandedTotal) ? expandedTotal : 0,
        expanded_completed_skus: Number.isFinite(expandedCompleted) ? expandedCompleted : 0,
        expanded_failed_skus: Number.isFinite(expandedFailed) ? expandedFailed : 0,
        skus: skusByJob[job.id] || [],
      }
    })

    return NextResponse.json({ jobs: result })
  } catch (error) {
    console.error('Jobs API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
