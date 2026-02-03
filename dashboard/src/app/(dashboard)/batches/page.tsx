import { createClient } from "@/lib/supabase/server"
import { BatchesClient } from "@/components/batches/BatchesClient"
import { PublishBatch } from "@/lib/supabase/types"

export default async function BatchesPage() {
  const supabase = await createClient()
  
  const { data: batchesData, error } = await supabase
    .from('publish_batches')
    .select('*')
    .order('created_at', { ascending: false })

  const batches: PublishBatch[] = batchesData || []

  if (error) {
    console.error('Failed to fetch batches:', error)
  }

  // Calculate stats
  const stats = {
    totalBatches: batches.length,
    draftCount: batches.filter(b => b.status === 'draft').length,
    completedCount: batches.filter(b => b.status === 'completed').length,
    skusPublished: batches.reduce((acc, b) => acc + (b.success_count || 0), 0),
  }

  return (
    <div className="p-8">
      <BatchesClient batches={batches} stats={stats} />
    </div>
  )
}
