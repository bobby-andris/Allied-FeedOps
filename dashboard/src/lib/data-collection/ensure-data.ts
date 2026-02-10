/**
 * Automated data collection helpers
 *
 * Ensures baseline and performance data is collected before/after SKU operations.
 * Integrates with SKU selection, regeneration, and publishing workflows.
 */

import { createAdminClient } from '@/lib/supabase/admin'

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

export type DataCollectionResult = {
  success: boolean
  error?: string
  details?: {
    baseline_captured?: boolean
    snapshot_captured?: boolean
    search_terms_synced?: boolean
    search_terms_enriched?: boolean
  }
}

/**
 * Ensure baseline data exists for a SKU before regeneration/optimization
 *
 * Checks if baseline performance data exists, if not triggers capture.
 * Returns immediately with success=true if data already exists.
 */
export async function ensureBaselineData(
  masterSku: string,
  supabase?: ReturnType<typeof createAdminClient>
): Promise<DataCollectionResult> {
  const client = supabase || createAdminClient()

  try {
    // Check if baseline already exists (within last 60 days)
    const { data: existing, error: queryError } = await client
      .from('performance_baselines')
      .select('master_sku, baseline_start_date')
      .eq('master_sku', masterSku)
      .gte('baseline_start_date', new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString())
      .limit(1)
      .maybeSingle()

    if (queryError) {
      console.error(`Failed to check baseline for ${masterSku}:`, queryError)
      return { success: false, error: queryError.message }
    }

    if (existing) {
      // Baseline already exists and is recent
      return {
        success: true,
        details: { baseline_captured: false }, // Already existed
      }
    }

    // Baseline doesn't exist, trigger capture via Cloud Run
    if (!PIPELINE_URL) {
      console.warn('FEEDOPS_PIPELINE_URL not set, skipping baseline capture')
      return {
        success: true, // Non-fatal, allow operation to continue
        details: { baseline_captured: false },
      }
    }

    const response = await fetch(`${PIPELINE_URL}/performance/capture-baseline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ master_skus: [masterSku] }),
    })

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}))
      console.error(`Baseline capture failed for ${masterSku}:`, errorBody)
      return {
        success: true, // Non-fatal
        details: { baseline_captured: false },
      }
    }

    return {
      success: true,
      details: { baseline_captured: true },
    }
  } catch (error) {
    console.error(`ensureBaselineData error for ${masterSku}:`, error)
    return {
      success: true, // Non-fatal, allow operation to continue
      error: error instanceof Error ? error.message : 'Unknown error',
      details: { baseline_captured: false },
    }
  }
}

/**
 * Ensure search query data exists for SKUs
 *
 * Triggers search term sync and enrichment if data is stale (>7 days).
 * Returns immediately with success=true if data is recent.
 */
export async function ensureSearchQueryData(
  masterSkus: string[],
  supabase?: ReturnType<typeof createAdminClient>
): Promise<DataCollectionResult> {
  const client = supabase || createAdminClient()

  try {
    // Check if search query data is recent (within last 7 days)
    const { data: recentJobs, error: jobError } = await client
      .from('search_query_sync_jobs')
      .select('id, completed_at, status')
      .eq('status', 'completed')
      .gte('completed_at', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString())
      .order('completed_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (jobError) {
      console.error('Failed to check search query jobs:', jobError)
      return { success: false, error: jobError.message }
    }

    if (recentJobs) {
      // Data is recent, no need to sync
      return {
        success: true,
        details: {
          search_terms_synced: false, // Already recent
          search_terms_enriched: false,
        },
      }
    }

    // Data is stale or missing, trigger sync via Cloud Run
    if (!PIPELINE_URL) {
      console.warn('FEEDOPS_PIPELINE_URL not set, skipping search term sync')
      return {
        success: true, // Non-fatal
        details: {
          search_terms_synced: false,
          search_terms_enriched: false,
        },
      }
    }

    // Trigger search term sync
    const syncResponse = await fetch(`${PIPELINE_URL}/search-insights/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        days: 30, // Last 30 days
        force_refresh: false,
      }),
    })

    if (!syncResponse.ok) {
      const errorBody = await syncResponse.json().catch(() => ({}))
      console.error('Search term sync failed:', errorBody)
      return {
        success: true, // Non-fatal
        details: {
          search_terms_synced: false,
          search_terms_enriched: false,
        },
      }
    }

    const syncResult = await syncResponse.json()
    const jobId = syncResult.job_id

    // Wait for sync to complete (up to 30 seconds)
    let attempts = 0
    const maxAttempts = 30
    let syncCompleted = false

    while (attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, 1000)) // Wait 1 second
      attempts++

      const statusResponse = await fetch(`${PIPELINE_URL}/search-insights/sync/${jobId}`)
      if (!statusResponse.ok) break

      const status = await statusResponse.json()
      if (status.status === 'completed') {
        syncCompleted = true
        break
      }
      if (status.status === 'failed') break
    }

    if (!syncCompleted) {
      console.warn('Search term sync did not complete in time')
      return {
        success: true, // Non-fatal
        details: {
          search_terms_synced: false,
          search_terms_enriched: false,
        },
      }
    }

    // Trigger keyword enrichment for new queries
    const enrichResponse = await fetch(`${PIPELINE_URL}/search-insights/enrich`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        force_refresh: false,
        batch_size: 100,
      }),
    })

    if (!enrichResponse.ok) {
      console.warn('Keyword enrichment failed (non-fatal)')
    }

    return {
      success: true,
      details: {
        search_terms_synced: true,
        search_terms_enriched: enrichResponse.ok,
      },
    }
  } catch (error) {
    console.error('ensureSearchQueryData error:', error)
    return {
      success: true, // Non-fatal, allow operation to continue
      error: error instanceof Error ? error.message : 'Unknown error',
      details: {
        search_terms_synced: false,
        search_terms_enriched: false,
      },
    }
  }
}

/**
 * Ensure all data is collected for a single SKU before optimization
 *
 * Combines baseline capture and search query sync.
 * Used by regeneration API to ensure rich evidence is available.
 */
export async function ensureSkuData(
  masterSku: string,
  supabase?: ReturnType<typeof createAdminClient>
): Promise<DataCollectionResult> {
  const client = supabase || createAdminClient()

  // Run baseline and search query collection in parallel (both non-blocking)
  const [baselineResult, searchResult] = await Promise.all([
    ensureBaselineData(masterSku, client),
    ensureSearchQueryData([masterSku], client),
  ])

  // Combine results
  const success = baselineResult.success && searchResult.success

  return {
    success,
    error: baselineResult.error || searchResult.error,
    details: {
      baseline_captured: baselineResult.details?.baseline_captured || false,
      search_terms_synced: searchResult.details?.search_terms_synced || false,
      search_terms_enriched: searchResult.details?.search_terms_enriched || false,
    },
  }
}

/**
 * Ensure all data is collected for a batch of SKUs before generation
 *
 * Used by SKU selection and batch generation APIs to ensure evidence is available.
 * Non-blocking: returns success even if some data collection fails.
 */
export async function ensureAllData(
  masterSkus: string[],
  supabase?: ReturnType<typeof createAdminClient>
): Promise<DataCollectionResult> {
  const client = supabase || createAdminClient()

  if (masterSkus.length === 0) {
    return { success: true, details: {} }
  }

  // Check baseline coverage
  const { data: existingBaselines } = await client
    .from('performance_baselines')
    .select('master_sku')
    .in('master_sku', masterSkus)
    .gte('baseline_start_date', new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString())

  const existingSkus = new Set((existingBaselines || []).map((b) => b.master_sku))
  const missingBaselines = masterSkus.filter((sku) => !existingSkus.has(sku))

  // Trigger baseline capture for missing SKUs (if any)
  let baselineCaptured = false
  if (missingBaselines.length > 0 && PIPELINE_URL) {
    try {
      const response = await fetch(`${PIPELINE_URL}/performance/capture-baseline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ master_skus: missingBaselines }),
      })

      if (response.ok) {
        baselineCaptured = true
      }
    } catch (error) {
      console.warn('Batch baseline capture failed (non-fatal):', error)
    }
  }

  // Trigger search query sync (once for all SKUs)
  const searchResult = await ensureSearchQueryData(masterSkus, client)

  return {
    success: true, // Always non-blocking
    details: {
      baseline_captured: baselineCaptured,
      search_terms_synced: searchResult.details?.search_terms_synced || false,
      search_terms_enriched: searchResult.details?.search_terms_enriched || false,
    },
  }
}

/**
 * Capture post-publish performance snapshot
 *
 * Called after publishing to track performance changes.
 * Links snapshot to publish event for tracking.
 */
export async function capturePostPublishSnapshot(
  masterSku: string,
  publishEventId: string,
  supabase?: ReturnType<typeof createAdminClient>
): Promise<DataCollectionResult> {
  // client available for future use when direct DB writes are needed
  const _client = supabase || createAdminClient()
  void _client

  try {
    if (!PIPELINE_URL) {
      console.warn('FEEDOPS_PIPELINE_URL not set, skipping post-publish snapshot')
      return {
        success: true, // Non-fatal
        details: { snapshot_captured: false },
      }
    }

    const response = await fetch(`${PIPELINE_URL}/performance/capture-snapshot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        master_sku: masterSku,
        publish_event_id: publishEventId,
      }),
    })

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}))
      console.error(`Post-publish snapshot failed for ${masterSku}:`, errorBody)
      return {
        success: true, // Non-fatal
        details: { snapshot_captured: false },
      }
    }

    return {
      success: true,
      details: { snapshot_captured: true },
    }
  } catch (error) {
    console.error(`capturePostPublishSnapshot error for ${masterSku}:`, error)
    return {
      success: true, // Non-fatal
      error: error instanceof Error ? error.message : 'Unknown error',
      details: { snapshot_captured: false },
    }
  }
}
