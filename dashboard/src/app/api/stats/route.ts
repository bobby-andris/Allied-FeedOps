import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const supabase = await createClient()

    // Get approval stats
    const { data: approvals } = await supabase
      .from('sku_approvals')
      .select('approval_status')

    const approvalStats = {
      pending: 0,
      approved: 0,
      revision: 0,
      rejected: 0,
      total: approvals?.length || 0,
    }

    approvals?.forEach((row) => {
      const status = row.approval_status as keyof typeof approvalStats
      if (status in approvalStats && status !== 'total') {
        approvalStats[status]++
      }
    })

    // Get batch stats
    const { data: batches } = await supabase
      .from('publish_batches')
      .select('status')

    const batchStats = {
      draft: 0,
      ready: 0,
      executing: 0,
      completed: 0,
      failed: 0,
      total: batches?.length || 0,
    }

    batches?.forEach((row) => {
      const status = row.status as keyof typeof batchStats
      if (status in batchStats && status !== 'total') {
        batchStats[status]++
      }
    })

    // Get published SKUs count
    const { data: publishedEvents } = await supabase
      .from('publish_events')
      .select('master_sku')
      .eq('environment', 'production')
      .eq('action', 'publish')
      .eq('status', 'success')

    const uniquePublishedSkus = new Set(publishedEvents?.map(e => e.master_sku))

    return NextResponse.json({
      approvals: approvalStats,
      batches: batchStats,
      publishedSkus: uniquePublishedSkus.size,
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
