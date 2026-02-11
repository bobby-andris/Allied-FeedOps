import { createClient } from "@/lib/supabase/server"
import { BatchesClient } from "@/components/batches/BatchesClient"
import { PublishBatch } from "@/lib/supabase/types"
import {
  deriveBatchSummary,
  hydrateAssignmentsWithEventFailures,
  normalizeBatchStatus,
} from "@/lib/batches/reconciliation"
import { fetchBatchAssignmentsByBatchIds } from "@/lib/batches/assignment-store"

export default async function BatchesPage() {
  const supabase = await createClient()
  
  const { data: batchesData, error } = await supabase
    .from('publish_batches')
    .select('*')
    .order('created_at', { ascending: false })

  const batchIds = (batchesData || []).map((row) => row.batch_id)

  const [{ data: assignmentsData, error: assignmentsError }, { data: eventsData, error: eventsError }] = batchIds.length
    ? await Promise.all([
      fetchBatchAssignmentsByBatchIds(supabase, batchIds),
      supabase
        .from('publish_events')
        .select('batch_id, master_sku, status, error_message, published_at')
        .in('batch_id', batchIds),
    ])
    : [{ data: [], error: null }, { data: [], error: null }]

  if (assignmentsError) {
    console.error('Failed to fetch assignment status data:', assignmentsError)
  }
  if (eventsError) {
    console.error('Failed to fetch publish event data:', eventsError)
  }

  const assignmentsByBatch = new Map<string, Array<{
    master_sku: string
    status: 'pending' | 'success' | 'partial' | 'failed' | null
    error_message: string | null
  }>>()
  for (const row of assignmentsData || []) {
    if (!assignmentsByBatch.has(row.batch_id)) {
      assignmentsByBatch.set(row.batch_id, [])
    }
    assignmentsByBatch.get(row.batch_id)!.push({
      master_sku: row.master_sku,
      status: row.status,
      error_message: row.error_message,
    })
  }

  const eventsByBatch = new Map<string, Array<{
    master_sku: string
    status: 'success' | 'failed'
    error_message: string | null
    published_at: string | null
  }>>()
  for (const row of eventsData || []) {
    if (!row.batch_id) continue
    if (!eventsByBatch.has(row.batch_id)) {
      eventsByBatch.set(row.batch_id, [])
    }
    eventsByBatch.get(row.batch_id)!.push({
      master_sku: row.master_sku,
      status: row.status,
      error_message: row.error_message,
      published_at: row.published_at,
    })
  }

  const batches: PublishBatch[] = (batchesData || []).map((row) => {
    const hydratedAssignments = hydrateAssignmentsWithEventFailures(
      assignmentsByBatch.get(row.batch_id) || [],
      eventsByBatch.get(row.batch_id) || []
    )
    const summary = deriveBatchSummary(row.status, hydratedAssignments)
    return {
      ...row,
      status: normalizeBatchStatus(summary.status),
      sku_count: summary.skuCount,
      success_count: summary.successCount,
      failed_count: summary.failedCount,
    }
  })

  if (error) {
    console.error('Failed to fetch batches:', error)
  }

  // Calculate stats
  const stats = {
    totalBatches: batches.length,
    draftCount: batches.filter(b => b.status === 'draft').length,
    publishedCount: batches.filter(b => b.status === 'published').length,
    skusPublished: batches.reduce((acc, b) => acc + (b.success_count || 0), 0),
  }

  return (
    <div className="p-8">
      <BatchesClient batches={batches} stats={stats} />
    </div>
  )
}
