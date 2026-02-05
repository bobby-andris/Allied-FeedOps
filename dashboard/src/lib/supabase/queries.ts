import { SupabaseClient } from '@supabase/supabase-js'
import { SkuApproval, PublishBatch, GeneratedContent, VariantIndex, VariantApproval } from './types'

// Use generic SupabaseClient until we have generated types
type Client = SupabaseClient

// Review Queue Queries
export interface ReviewFilters {
  status?: 'pending' | 'approved' | 'revision' | 'rejected'
  category?: string
  collection?: string
  minScore?: number
  maxScore?: number
  search?: string
  limit?: number
  offset?: number
}

export async function getReviewQueue(client: Client, filters: ReviewFilters = {}) {
  let query = client
    .from('sku_approvals')
    .select('*')
    .order('created_at', { ascending: false })

  if (filters.status) {
    query = query.eq('approval_status', filters.status)
  }

  if (filters.limit) {
    query = query.limit(filters.limit)
  }

  if (filters.offset) {
    query = query.range(filters.offset, filters.offset + (filters.limit || 50) - 1)
  }

  const { data, error } = await query

  if (error) throw error
  return data as SkuApproval[]
}

export async function getSkuApproval(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('sku_approvals')
    .select('*')
    .eq('master_sku', masterSku)
    .single()

  if (error && error.code !== 'PGRST116') throw error
  return data as SkuApproval | null
}

export async function updateApproval(
  client: Client,
  masterSku: string,
  approval: Partial<Omit<SkuApproval, 'id' | 'master_sku' | 'created_at'>>
) {
  // First check if record exists
  const { data: existing } = await client
    .from('sku_approvals')
    .select('id')
    .eq('master_sku', masterSku)
    .single()

  if (existing) {
    // Update existing record
    const { data, error } = await client
      .from('sku_approvals')
      .update({
        ...approval,
        updated_at: new Date().toISOString(),
      })
      .eq('master_sku', masterSku)
      .select()
      .single()

    if (error) throw error
    return data as SkuApproval
  } else {
    // Insert new record
    const { data, error } = await client
      .from('sku_approvals')
      .insert({
        master_sku: masterSku,
        ...approval,
        approval_status: approval.approval_status || 'pending',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error) throw error
    return data as SkuApproval
  }
}

export async function approveElement(
  client: Client,
  masterSku: string,
  element: 'title' | 'description' | 'image',
  approved: boolean
) {
  const field = `${element}_approved`
  return updateApproval(client, masterSku, {
    [field]: approved ? 1 : 0,
  })
}

// Variant Queries
export async function getVariantsForSku(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('variant_index')
    .select('*')
    .eq('master_sku', masterSku)
    .order('finish', { ascending: true })

  if (error) throw error
  return data as VariantIndex[]
}

export async function getVariantApprovals(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('variant_approvals')
    .select('*')
    .eq('master_sku', masterSku)
    .order('finish', { ascending: true })

  if (error) throw error
  return data as VariantApproval[]
}

export async function getVariantApproval(client: Client, masterSku: string, finish: string) {
  const { data, error } = await client
    .from('variant_approvals')
    .select('*')
    .eq('master_sku', masterSku)
    .eq('finish', finish)
    .single()

  if (error && error.code !== 'PGRST116') throw error
  return data as VariantApproval | null
}

export async function updateVariantApproval(
  client: Client,
  masterSku: string,
  finish: string,
  approval: Partial<Omit<VariantApproval, 'id' | 'master_sku' | 'finish' | 'created_at'>>
) {
  // First check if record exists
  const { data: existing } = await client
    .from('variant_approvals')
    .select('id')
    .eq('master_sku', masterSku)
    .eq('finish', finish)
    .single()

  if (existing) {
    // Update existing record
    const { data, error } = await client
      .from('variant_approvals')
      .update({
        ...approval,
        updated_at: new Date().toISOString(),
      })
      .eq('master_sku', masterSku)
      .eq('finish', finish)
      .select()
      .single()

    if (error) throw error
    return data as VariantApproval
  } else {
    // Insert new record
    const { data, error } = await client
      .from('variant_approvals')
      .insert({
        master_sku: masterSku,
        finish,
        ...approval,
        approval_status: approval.approval_status || 'pending',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select()
      .single()

    if (error) throw error
    return data as VariantApproval
  }
}

export async function approveVariantElement(
  client: Client,
  masterSku: string,
  finish: string,
  element: 'title' | 'description' | 'image',
  approved: boolean
) {
  const field = `${element}_approved`
  return updateVariantApproval(client, masterSku, finish, {
    [field]: approved ? 1 : 0,
  })
}

// Batch Queries
export async function getBatches(client: Client, status?: string) {
  let query = client
    .from('publish_batches')
    .select('*')
    .order('created_at', { ascending: false })

  if (status) {
    query = query.eq('status', status)
  }

  const { data, error } = await query

  if (error) throw error
  return data as PublishBatch[]
}

export async function getBatch(client: Client, batchId: string) {
  const { data, error } = await client
    .from('publish_batches')
    .select('*')
    .eq('batch_id', batchId)
    .single()

  if (error) throw error
  return data as PublishBatch
}

export async function createBatch(
  client: Client,
  batch: { name: string; notes?: string; target_date?: string }
) {
  const { data, error } = await client
    .from('publish_batches')
    .insert({
      name: batch.name,
      notes: batch.notes || null,
      target_date: batch.target_date || null,
      status: 'draft',
      sku_count: 0,
      success_count: 0,
      failed_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .select()
    .single()

  if (error) throw error
  return data as PublishBatch
}

export async function updateBatchStatus(
  client: Client,
  batchId: string,
  status: PublishBatch['status']
) {
  const updateData: Record<string, unknown> = {
    status,
    updated_at: new Date().toISOString(),
  }
  
  if (status === 'completed') {
    updateData.executed_at = new Date().toISOString()
  }

  const { data, error } = await client
    .from('publish_batches')
    .update(updateData)
    .eq('batch_id', batchId)
    .select()
    .single()

  if (error) throw error
  return data as PublishBatch
}

// Content Queries
export async function getGeneratedContent(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('generated_content')
    .select('*')
    .eq('master_sku', masterSku)

  if (error) throw error
  return data as GeneratedContent[]
}

export async function getGeneratedImages(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('generated_images')
    .select('*')
    .eq('master_sku', masterSku)
    .order('variation_index', { ascending: true })

  if (error) throw error
  return data
}

/**
 * Get product+finish tailored sentences for variant content generation.
 * These are LLM-generated sentences that describe how each finish relates to the specific product.
 *
 * @param client - Supabase client
 * @param masterSku - The master SKU
 * @param platform - 'google' or 'bing'
 * @returns Object mapping finish names to product-specific sentences, or null if not found
 */
export async function getFinishSentences(
  client: Client,
  masterSku: string,
  platform: 'google' | 'bing'
): Promise<Record<string, string> | null> {
  const { data, error } = await client
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', masterSku)
    .eq('platform', platform)
    .single()

  if (error) {
    // PGRST116 = row not found (not an error, just no data)
    if (error.code !== 'PGRST116') {
      console.error('Error fetching finish sentences:', error)
    }
    return null
  }

  return data?.finish_sentences as Record<string, string> || null
}

// Performance Queries
export async function getPerformanceSnapshots(
  client: Client,
  masterSku: string,
  platform?: string
) {
  let query = client
    .from('performance_snapshots')
    .select('*')
    .eq('master_sku', masterSku)
    .order('snapshot_date', { ascending: true })

  if (platform) {
    query = query.eq('platform', platform)
  }

  const { data, error } = await query

  if (error) throw error
  return data
}

export async function getPerformanceBaseline(
  client: Client,
  masterSku: string,
  platform: string
) {
  const { data, error } = await client
    .from('performance_baselines')
    .select('*')
    .eq('master_sku', masterSku)
    .eq('platform', platform)
    .single()

  if (error && error.code !== 'PGRST116') throw error
  return data
}

// Stats/Aggregates
export async function getApprovalStats(client: Client) {
  const { data, error } = await client
    .from('sku_approvals')
    .select('approval_status')

  if (error) throw error

  const stats = {
    pending: 0,
    approved: 0,
    revision: 0,
    rejected: 0,
    total: data?.length || 0,
  }

  data?.forEach((row: { approval_status: string }) => {
    const status = row.approval_status as keyof typeof stats
    if (status in stats && status !== 'total') {
      stats[status]++
    }
  })

  return stats
}

export async function getPublishedSkus(client: Client, environment: 'staging' | 'production') {
  const { data, error } = await client
    .from('publish_events')
    .select('master_sku')
    .eq('environment', environment)
    .eq('action', 'publish')
    .eq('status', 'success')

  if (error) throw error
  
  // Deduplicate
  const uniqueSkus = [...new Set(data?.map((row: { master_sku: string }) => row.master_sku))]
  return uniqueSkus
}
