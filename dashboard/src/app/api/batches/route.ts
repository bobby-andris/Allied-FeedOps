import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'
import {
  deriveBatchSummary,
  hydrateAssignmentsWithEventFailures,
  normalizeBatchStatus,
} from '@/lib/batches/reconciliation'
import { fetchBatchAssignmentsByBatchIds } from '@/lib/batches/assignment-store'

const VALID_BATCH_STATUSES = ['draft', 'pending', 'executing', 'published', 'partial', 'failed'] as const

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const rawStatus = searchParams.get('status')
  const status = normalizeBatchStatus(rawStatus)
  const batchId = searchParams.get('batch_id')

  try {
    const supabase = await createClient()
    
    let query = supabase
      .from('publish_batches')
      .select('*')
      .order('created_at', { ascending: false })

    if (rawStatus) {
      query = query.eq('status', status)
    }

    if (batchId) {
      query = query.eq('batch_id', batchId)
    }

    const { data, error } = await query

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const batchIds = (data || []).map((row) => row.batch_id)
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
      return NextResponse.json({ error: assignmentsError.message }, { status: 500 })
    }
    if (eventsError) {
      return NextResponse.json({ error: eventsError.message }, { status: 500 })
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

    const normalized = (data || []).map((row) => {
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

    return NextResponse.json({ data: normalized })
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
      const translatedStatus = status === 'ready' ? 'pending' : status === 'completed' ? 'published' : status
      if (!VALID_BATCH_STATUSES.includes(translatedStatus as typeof VALID_BATCH_STATUSES[number])) {
        return NextResponse.json(
          { error: `status must be one of: ${VALID_BATCH_STATUSES.join(', ')}` },
          { status: 400 }
        )
      }

      const normalizedStatus = translatedStatus as typeof VALID_BATCH_STATUSES[number]
      updateData.status = normalizedStatus
      if (normalizedStatus === 'published' || normalizedStatus === 'partial' || normalizedStatus === 'failed') {
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

    return NextResponse.json({
      data: {
        ...batch,
        status: normalizeBatchStatus(batch.status),
      },
    })
  } catch {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
