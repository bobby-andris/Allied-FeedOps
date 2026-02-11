import type { PostgrestError, SupabaseClient } from '@supabase/supabase-js'

export type BatchAssignmentStatus = 'pending' | 'success' | 'partial' | 'failed' | null

export interface BatchAssignmentRow {
  id: string
  batch_id: string
  master_sku: string
  created_at: string
  status: BatchAssignmentStatus
  error_message: string | null
}

const SELECT_WITH_STATUS_COLUMNS = 'id, batch_id, master_sku, created_at, status, error_message'
const SELECT_FALLBACK_COLUMNS = 'id, batch_id, master_sku, created_at'

function withMissingStatusColumns(rows: Array<{
  id: string
  batch_id: string
  master_sku: string
  created_at: string | null
}>): BatchAssignmentRow[] {
  return rows.map((row) => ({
    id: row.id,
    batch_id: row.batch_id,
    master_sku: row.master_sku,
    created_at: row.created_at || '',
    status: null,
    error_message: null,
  }))
}

async function runAssignmentsQueryWithFallback(
  queryFactory: (selectColumns: string) => PromiseLike<{
    data: unknown[] | null
    error: PostgrestError | null
  }>
): Promise<{
  data: BatchAssignmentRow[]
  error: PostgrestError | null
}> {
  const { data, error } = await queryFactory(SELECT_WITH_STATUS_COLUMNS)

  if (!error) {
    return {
      data: (data || []) as BatchAssignmentRow[],
      error: null,
    }
  }

  if (error.code === '42703') {
    const fallbackResult = await queryFactory(SELECT_FALLBACK_COLUMNS)
    if (fallbackResult.error) {
      return {
        data: [],
        error: fallbackResult.error,
      }
    }
    return {
      data: withMissingStatusColumns(
        (fallbackResult.data || []) as Array<{
          id: string
          batch_id: string
          master_sku: string
          created_at: string | null
        }>
      ),
      error: null,
    }
  }

  return {
    data: [],
    error,
  }
}

export async function fetchBatchAssignmentsByBatchIds(
  supabase: SupabaseClient,
  batchIds: string[]
): Promise<{
  data: BatchAssignmentRow[]
  error: PostgrestError | null
}> {
  if (batchIds.length === 0) {
    return { data: [], error: null }
  }

  return runAssignmentsQueryWithFallback((selectColumns) =>
    supabase
      .from('batch_sku_assignments')
      .select(selectColumns)
      .in('batch_id', batchIds)
  )
}

export async function fetchBatchAssignmentsByBatchId(
  supabase: SupabaseClient,
  batchId: string
): Promise<{
  data: BatchAssignmentRow[]
  error: PostgrestError | null
}> {
  return runAssignmentsQueryWithFallback((selectColumns) =>
    supabase
      .from('batch_sku_assignments')
      .select(selectColumns)
      .eq('batch_id', batchId)
      .order('created_at', { ascending: true })
  )
}
