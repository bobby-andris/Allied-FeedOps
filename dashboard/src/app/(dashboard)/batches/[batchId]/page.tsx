import { createClient } from "@/lib/supabase/server"
import { BatchDetailClient } from "@/components/batches/BatchDetailClient"
import { notFound } from "next/navigation"
import {
  deriveBatchSummary,
  hydrateAssignmentsWithEventFailures,
  normalizeBatchStatus,
} from "@/lib/batches/reconciliation"
import { fetchBatchAssignmentsByBatchId } from "@/lib/batches/assignment-store"

export default async function BatchDetailPage({
  params,
}: {
  params: Promise<{ batchId: string }>
}) {
  const { batchId } = await params
  const supabase = await createClient()

  // Fetch batch
  const { data: batch, error: batchError } = await supabase
    .from('publish_batches')
    .select('*')
    .eq('batch_id', batchId)
    .single()

  if (batchError || !batch) {
    console.error('Failed to fetch batch:', batchError)
    notFound()
  }

  // Fetch SKU assignments
  const { data: assignments, error: assignmentsError } = await fetchBatchAssignmentsByBatchId(
    supabase,
    batchId
  )

  if (assignmentsError) {
    console.error('Failed to fetch assignments:', assignmentsError)
  }

  const { data: eventsData, error: eventsError } = await supabase
    .from('publish_events')
    .select('master_sku, status, error_message, published_at')
    .eq('batch_id', batchId)
    .order('published_at', { ascending: false })

  if (eventsError) {
    console.error('Failed to fetch publish events:', eventsError)
  }

  const hydratedAssignments = hydrateAssignmentsWithEventFailures(
    assignments || [],
    eventsData || []
  )
  const summary = deriveBatchSummary(batch.status, hydratedAssignments)

  const normalizedBatch = {
    ...batch,
    status: normalizeBatchStatus(summary.status),
    sku_count: summary.skuCount,
    success_count: summary.successCount,
    failed_count: summary.failedCount,
  }

  return (
    <div className="p-8">
      <BatchDetailClient 
        batch={normalizedBatch} 
        assignments={hydratedAssignments} 
      />
    </div>
  )
}
