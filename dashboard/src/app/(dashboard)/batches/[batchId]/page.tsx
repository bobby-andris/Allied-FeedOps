import { createClient } from "@/lib/supabase/server"
import { BatchDetailClient } from "@/components/batches/BatchDetailClient"
import { notFound } from "next/navigation"

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
  const { data: assignments, error: assignmentsError } = await supabase
    .from('batch_sku_assignments')
    .select('*')
    .eq('batch_id', batchId)
    .order('created_at', { ascending: true })

  if (assignmentsError) {
    console.error('Failed to fetch assignments:', assignmentsError)
  }

  return (
    <div className="p-8">
      <BatchDetailClient 
        batch={batch} 
        assignments={assignments || []} 
      />
    </div>
  )
}
