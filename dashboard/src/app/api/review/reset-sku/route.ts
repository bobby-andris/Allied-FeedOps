import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const { master_sku } = await request.json()
    if (!master_sku) {
      return NextResponse.json({ error: 'master_sku required' }, { status: 400 })
    }

    const supabase = await createClient()

    // Safety: refuse to reset SKUs that have been published
    const { data: publishEvents, error: publishCheckError } = await supabase
      .from('publish_events')
      .select('id')
      .eq('master_sku', master_sku)
      .eq('status', 'success')
      .limit(1)

    if (publishCheckError) {
      console.error('reset-sku: publish check error', publishCheckError)
      return NextResponse.json({ error: publishCheckError.message }, { status: 500 })
    }

    if (publishEvents && publishEvents.length > 0) {
      return NextResponse.json(
        { error: 'Cannot reset a published SKU. Use a different workflow for published content.' },
        { status: 409 },
      )
    }

    const deleted: Record<string, number> = {}

    // Delete order matters: children before parents (FK constraints)

    // 1. regeneration_history (FK → generated_content.id)
    const { count: rhCount, error: rhError } = await supabase
      .from('regeneration_history')
      .delete({ count: 'exact' })
      .eq('master_sku', master_sku)
    if (rhError) {
      console.error('reset-sku: regeneration_history delete error', rhError)
      return NextResponse.json({ error: rhError.message }, { status: 500 })
    }
    deleted.regeneration_history = rhCount ?? 0

    // 2. batch_sku_assignments (only from draft/pending batches)
    const { data: draftBatches } = await supabase
      .from('publish_batches')
      .select('id')
      .in('status', ['draft', 'pending'])

    const draftBatchIds = (draftBatches ?? []).map(b => b.id)
    let bsaCount = 0
    if (draftBatchIds.length > 0) {
      const { count, error: bsaError } = await supabase
        .from('batch_sku_assignments')
        .delete({ count: 'exact' })
        .eq('master_sku', master_sku)
        .in('batch_id', draftBatchIds)
      if (bsaError) {
        console.error('reset-sku: batch_sku_assignments delete error', bsaError)
        // Non-fatal — continue
      }
      bsaCount = count ?? 0
    }
    deleted.batch_sku_assignments = bsaCount

    // 3. variant_approvals
    const { count: vaCount, error: vaError } = await supabase
      .from('variant_approvals')
      .delete({ count: 'exact' })
      .eq('master_sku', master_sku)
    if (vaError) {
      console.error('reset-sku: variant_approvals delete error', vaError)
      return NextResponse.json({ error: vaError.message }, { status: 500 })
    }
    deleted.variant_approvals = vaCount ?? 0

    // 4. variant_finish_sentences
    const { count: vfsCount, error: vfsError } = await supabase
      .from('variant_finish_sentences')
      .delete({ count: 'exact' })
      .eq('master_sku', master_sku)
    if (vfsError) {
      console.error('reset-sku: variant_finish_sentences delete error', vfsError)
      return NextResponse.json({ error: vfsError.message }, { status: 500 })
    }
    deleted.variant_finish_sentences = vfsCount ?? 0

    // 5. sku_approvals
    const { count: saCount, error: saError } = await supabase
      .from('sku_approvals')
      .delete({ count: 'exact' })
      .eq('master_sku', master_sku)
    if (saError) {
      console.error('reset-sku: sku_approvals delete error', saError)
      return NextResponse.json({ error: saError.message }, { status: 500 })
    }
    deleted.sku_approvals = saCount ?? 0

    // 6. generated_content (parent — deleted last)
    const { count: gcCount, error: gcError } = await supabase
      .from('generated_content')
      .delete({ count: 'exact' })
      .eq('master_sku', master_sku)
    if (gcError) {
      console.error('reset-sku: generated_content delete error', gcError)
      return NextResponse.json({ error: gcError.message }, { status: 500 })
    }
    deleted.generated_content = gcCount ?? 0

    return NextResponse.json({ success: true, master_sku, deleted })
  } catch (error) {
    console.error('reset-sku: unhandled error', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}
