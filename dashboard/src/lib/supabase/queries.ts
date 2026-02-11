import { SupabaseClient } from '@supabase/supabase-js'
import {
  SkuApproval,
  PublishBatch,
  GeneratedContent,
  VariantIndex,
  VariantApproval,
  SearchQuery,
  SearchQueryByMasterSku,
  SearchQuerySyncJob,
  KeywordMetrics,
  KeywordCoverageVariant,
  KeywordCoverageMaster,
  FinishSearchPattern,
} from './types'

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
  
  if (status === 'published' || status === 'partial' || status === 'failed') {
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

// ============================================================================
// Search Query Insights
// ============================================================================

export interface SearchQueryFilters {
  masterSku?: string
  finishCode?: string
  platform?: 'google' | 'bing' | 'shopify'
  view?: 'aggregate' | 'variant'
  periodStart?: string
  periodEnd?: string
  minImpressions?: number
  limit?: number
  offset?: number
}

/**
 * Get search queries for a specific SKU with optional finish filter.
 * Returns variant-level data for Google/Bing or aggregated for Shopify.
 */
export async function getSearchQueriesForSku(
  client: Client,
  filters: SearchQueryFilters
) {
  const { masterSku, finishCode, view = 'aggregate', limit = 100, offset = 0 } = filters

  if (!masterSku) {
    // Return top queries across all SKUs
    const { data, error } = await client
      .from('search_queries')
      .select('*')
      .order('impressions', { ascending: false })
      .limit(limit)

    if (error) throw error
    return { queries: data as SearchQuery[], viewType: 'all' }
  }

  if (view === 'aggregate') {
    // Aggregated view: all variants combined
    const { data, error } = await client
      .from('search_queries_by_master_sku')
      .select('*')
      .eq('master_sku', masterSku)
      .order('total_impressions', { ascending: false })
      .range(offset, offset + limit - 1)

    if (error) throw error
    return { queries: data as SearchQueryByMasterSku[], viewType: 'aggregate' }
  }

  // Variant-specific view
  let query = client
    .from('search_queries')
    .select('*')
    .eq('master_sku', masterSku)
    .order('impressions', { ascending: false })

  if (finishCode) {
    query = query.eq('finish_code', finishCode)
  }

  const { data, error } = await query.range(offset, offset + limit - 1)

  if (error) throw error
  return { queries: data as SearchQuery[], viewType: 'variant' }
}

/**
 * Get aggregated queries for a master SKU (combined across all variants).
 */
export async function getAggregatedQueries(
  client: Client,
  masterSku: string,
  limit = 100
) {
  const { data, error } = await client
    .from('search_queries_by_master_sku')
    .select('*')
    .eq('master_sku', masterSku)
    .order('total_impressions', { ascending: false })
    .limit(limit)

  if (error) throw error
  return data as SearchQueryByMasterSku[]
}

/**
 * Get search queries by variant (specific finish).
 */
export async function getSearchQueriesByVariant(
  client: Client,
  masterSku: string,
  finishCode?: string,
  limit = 100
) {
  let query = client
    .from('search_queries')
    .select('*')
    .eq('master_sku', masterSku)
    .order('impressions', { ascending: false })

  if (finishCode) {
    query = query.eq('finish_code', finishCode)
  }

  const { data, error } = await query.limit(limit)

  if (error) throw error
  return data as SearchQuery[]
}

/**
 * Get variant breakdown summary for a master SKU.
 * Returns counts of queries per finish.
 */
export async function getVariantBreakdown(client: Client, masterSku: string) {
  const { data, error } = await client
    .from('search_queries')
    .select('finish_code, finish')
    .eq('master_sku', masterSku)

  if (error) throw error

  // Count queries per finish
  const breakdown: Record<string, { finish: string; count: number; totalImpressions: number }> = {}

  data?.forEach((row) => {
    if (row.finish_code) {
      if (!breakdown[row.finish_code]) {
        breakdown[row.finish_code] = {
          finish: row.finish || row.finish_code,
          count: 0,
          totalImpressions: 0,
        }
      }
      breakdown[row.finish_code].count++
    }
  })

  return breakdown
}

/**
 * Get keyword coverage for a SKU (which keywords are in titles/descriptions).
 */
export async function getKeywordCoverage(
  client: Client,
  masterSku: string,
  platform: 'google' | 'bing' | 'shopify'
) {
  if (platform === 'shopify') {
    // Shopify uses master-level coverage
    const { data, error } = await client
      .from('keyword_coverage_master')
      .select('*')
      .eq('master_sku', masterSku)
      .order('query_volume', { ascending: false })

    if (error) throw error
    return data as KeywordCoverageMaster[]
  }

  // Google/Bing use variant-level coverage
  const { data, error } = await client
    .from('keyword_coverage_variant')
    .select('*')
    .eq('master_sku', masterSku)
    .order('query_volume', { ascending: false })

  if (error) throw error
  return data as KeywordCoverageVariant[]
}

/**
 * Get keyword gaps (high-volume keywords not in title).
 */
export async function getKeywordGaps(
  client: Client,
  masterSku: string,
  platform: 'google' | 'bing' | 'shopify',
  limit = 20
) {
  const table = platform === 'shopify' ? 'keyword_coverage_master' : 'keyword_coverage_variant'

  const { data, error } = await client
    .from(table)
    .select('*')
    .eq('master_sku', masterSku)
    .eq('in_title', false)
    .gt('query_volume', 0)
    .order('query_volume', { ascending: false })
    .limit(limit)

  if (error) throw error
  return data
}

/**
 * Get finish-specific search patterns.
 */
export async function getFinishSearchPatterns(
  client: Client,
  options: { finishCode?: string; category?: string; limit?: number } = {}
) {
  const { finishCode, category, limit = 50 } = options

  let query = client
    .from('finish_search_patterns')
    .select('*')
    .order('total_impressions', { ascending: false })

  if (finishCode) {
    query = query.eq('finish_code', finishCode)
  }

  if (category) {
    query = query.eq('category', category)
  }

  const { data, error } = await query.limit(limit)

  if (error) throw error
  return data as FinishSearchPattern[]
}

/**
 * Get cached keyword metrics from Keyword Planner.
 */
export async function getKeywordMetrics(client: Client, keywords: string[]) {
  if (keywords.length === 0) return []

  const { data, error } = await client
    .from('keyword_metrics')
    .select('*')
    .in('keyword', keywords)

  if (error) throw error
  return data as KeywordMetrics[]
}

/**
 * Get sync job status.
 */
export async function getSyncJobStatus(client: Client, jobId: string) {
  const { data, error } = await client
    .from('search_query_sync_jobs')
    .select('*')
    .eq('id', jobId)
    .single()

  if (error) throw error
  return data as SearchQuerySyncJob
}

/**
 * Get recent sync jobs.
 */
export async function getRecentSyncJobs(client: Client, limit = 10) {
  const { data, error } = await client
    .from('search_query_sync_jobs')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limit)

  if (error) throw error
  return data as SearchQuerySyncJob[]
}

/**
 * Get last successful sync timestamp.
 */
export async function getLastSyncTimestamp(client: Client) {
  const { data, error } = await client
    .from('search_query_sync_jobs')
    .select('completed_at')
    .eq('status', 'completed')
    .order('completed_at', { ascending: false })
    .limit(1)
    .single()

  if (error && error.code !== 'PGRST116') throw error
  return data?.completed_at as string | null
}

/**
 * Get search query insights summary stats for a SKU.
 */
export async function getSearchInsightsSummary(client: Client, masterSku: string) {
  // Get total queries count
  const { count: totalQueries, error: countError } = await client
    .from('search_queries')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', masterSku)

  if (countError) throw countError

  // Get aggregated metrics
  const { data: queries } = await client
    .from('search_queries')
    .select('impressions, clicks, conversions, conversion_value, avg_monthly_searches')
    .eq('master_sku', masterSku)

  const totals = queries?.reduce(
    (acc, q) => ({
      impressions: acc.impressions + (q.impressions || 0),
      clicks: acc.clicks + (q.clicks || 0),
      conversions: acc.conversions + (q.conversions || 0),
      conversionValue: acc.conversionValue + (q.conversion_value || 0),
      totalSearchVolume: acc.totalSearchVolume + (q.avg_monthly_searches || 0),
    }),
    { impressions: 0, clicks: 0, conversions: 0, conversionValue: 0, totalSearchVolume: 0 }
  ) || { impressions: 0, clicks: 0, conversions: 0, conversionValue: 0, totalSearchVolume: 0 }

  // Get keyword coverage
  const { count: gapsCount } = await client
    .from('keyword_coverage_variant')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', masterSku)
    .eq('in_title', false)
    .gt('query_volume', 0)

  const { count: coveredCount } = await client
    .from('keyword_coverage_variant')
    .select('*', { count: 'exact', head: true })
    .eq('master_sku', masterSku)
    .eq('in_title', true)

  const coveragePercent = (coveredCount || 0) + (gapsCount || 0) > 0
    ? ((coveredCount || 0) / ((coveredCount || 0) + (gapsCount || 0))) * 100
    : 0

  return {
    totalQueries: totalQueries || 0,
    totalImpressions: totals.impressions,
    totalClicks: totals.clicks,
    totalConversions: totals.conversions,
    totalConversionValue: totals.conversionValue,
    totalSearchVolume: totals.totalSearchVolume,
    keywordsInTitle: coveredCount || 0,
    keywordsNotInTitle: gapsCount || 0,
    coveragePercent,
    ctr: totals.impressions > 0 ? (totals.clicks / totals.impressions) * 100 : 0,
  }
}
