import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const status = searchParams.get('status')
  const batchId = searchParams.get('batch_id')

  try {
    const supabase = await createClient()
    
    let query = supabase
      .from('publish_batches')
      .select('*')
      .order('created_at', { ascending: false })

    if (status) {
      query = query.eq('status', status)
    }

    if (batchId) {
      query = query.eq('batch_id', batchId)
    }

    const { data, error } = await query

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ data })
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { name, notes, target_date, skus } = body

    if (!name) {
      return NextResponse.json(
        { error: 'name is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()
    const batchId = `batch-${Date.now()}`

    // Create batch
    const { data: batch, error: batchError } = await supabase
      .from('publish_batches')
      .insert({
        batch_id: batchId,
        name,
        notes: notes || null,
        target_date: target_date || null,
        status: 'draft',
        sku_count: skus?.length || 0,
        success_count: 0,
        failed_count: 0,
        created_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (batchError) {
      return NextResponse.json({ error: batchError.message }, { status: 500 })
    }

    // Add SKUs to batch if provided
    if (skus && skus.length > 0) {
      const assignments = skus.map((sku: string) => ({
        batch_id: batchId,
        master_sku: sku,
        created_at: new Date().toISOString(),
      }))

      const { error: assignError } = await supabase
        .from('batch_sku_assignments')
        .insert(assignments)

      if (assignError) {
        console.error('Failed to assign SKUs to batch:', assignError)
      }
    }

    return NextResponse.json({ data: batch })
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { batch_id, status, notes, add_skus, remove_skus } = body

    if (!batch_id) {
      return NextResponse.json(
        { error: 'batch_id is required' },
        { status: 400 }
      )
    }

    const supabase = await createClient()

    // Update batch status/notes
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString(),
    }

    if (status) {
      updateData.status = status
      if (status === 'completed' || status === 'published') {
        updateData.executed_at = new Date().toISOString()
      }
    }

    if (notes !== undefined) {
      updateData.notes = notes
    }

    const { data: batch, error: updateError } = await supabase
      .from('publish_batches')
      .update(updateData)
      .eq('batch_id', batch_id)
      .select()
      .single()

    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    // Add SKUs
    if (add_skus && add_skus.length > 0) {
      const assignments = add_skus.map((sku: string) => ({
        batch_id,
        master_sku: sku,
        created_at: new Date().toISOString(),
      }))

      await supabase
        .from('batch_sku_assignments')
        .upsert(assignments, { onConflict: 'batch_id,master_sku' })

      // Update SKU count
      const { count } = await supabase
        .from('batch_sku_assignments')
        .select('*', { count: 'exact', head: true })
        .eq('batch_id', batch_id)

      await supabase
        .from('publish_batches')
        .update({ sku_count: count || 0 })
        .eq('batch_id', batch_id)
    }

    // Remove SKUs
    if (remove_skus && remove_skus.length > 0) {
      await supabase
        .from('batch_sku_assignments')
        .delete()
        .eq('batch_id', batch_id)
        .in('master_sku', remove_skus)

      // Update SKU count
      const { count } = await supabase
        .from('batch_sku_assignments')
        .select('*', { count: 'exact', head: true })
        .eq('batch_id', batch_id)

      await supabase
        .from('publish_batches')
        .update({ sku_count: count || 0 })
        .eq('batch_id', batch_id)
    }

    return NextResponse.json({ data: batch })
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
