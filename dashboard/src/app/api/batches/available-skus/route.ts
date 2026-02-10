import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const excludeBatchId = searchParams.get('exclude_batch_id')

  try {
    const supabase = await createClient()

    // Get all approved SKUs
    const { data: approvedSkus, error: approvalError } = await supabase
      .from('sku_approvals')
      .select('master_sku, approval_status')
      .eq('approval_status', 'approved')

    if (approvalError) {
      return NextResponse.json({ error: approvalError.message }, { status: 500 })
    }

    if (!approvedSkus || approvedSkus.length === 0) {
      return NextResponse.json({ data: [] })
    }

    // Get SKUs already in active (non-completed, non-failed) batches
    const { data: activeBatches, error: batchError } = await supabase
      .from('publish_batches')
      .select('batch_id')
      .not('status', 'in', '("completed","failed")')

    if (batchError) {
      return NextResponse.json({ error: batchError.message }, { status: 500 })
    }

    const activeBatchIds = activeBatches?.map(b => b.batch_id) || []

    // Get SKUs assigned to active batches
    let assignedSkus: string[] = []
    if (activeBatchIds.length > 0) {
      const { data: assignments, error: assignError } = await supabase
        .from('batch_sku_assignments')
        .select('master_sku')
        .in('batch_id', activeBatchIds)

      if (assignError) {
        return NextResponse.json({ error: assignError.message }, { status: 500 })
      }

      assignedSkus = assignments?.map(a => a.master_sku) || []
    }

    // If excluding a specific batch, also get its SKUs and exclude them from the unavailable list
    // (so they still show as "available" for adding to that specific batch)
    if (excludeBatchId) {
      // No additional filtering needed - SKUs in the excluded batch
      // should still show as unavailable since they're already assigned
    }

    // Filter out SKUs that are already assigned to active batches
    const availableSkus = approvedSkus.filter(
      sku => !assignedSkus.includes(sku.master_sku)
    )

    return NextResponse.json({ data: availableSkus })
  } catch (error) {
    console.error('Error fetching available SKUs:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
