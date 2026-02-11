/**
 * Client for calling the FeedOps Python pipeline on Cloud Run.
 *
 * Use this when you want to use the Python pipeline's comprehensive prompts
 * and evidence building instead of the TypeScript implementation.
 *
 * Configuration:
 * - Set FEEDOPS_PIPELINE_URL environment variable to the Cloud Run service URL
 * - Optional: Set FEEDOPS_USE_CLOUD_RUN=1 to enable Cloud Run mode
 */

const PIPELINE_URL = process.env.FEEDOPS_PIPELINE_URL

// =============================================================================
// Request Types
// =============================================================================

export interface OptimizeRequest {
  master_sku: string
  num_candidates?: number
  dry_run?: boolean
}

export interface RegenerateRequest {
  master_sku: string
  content_type: 'title' | 'description'
  platform: 'google' | 'bing' | 'shopify'
  feedback?: string
  finish_code?: string
}

export interface BatchOptimizeRequest {
  skus: string[]
  num_candidates?: number
  dry_run?: boolean
  options?: {
    titles?: boolean
    descriptions?: boolean
    platforms?: ('google' | 'bing' | 'shopify')[]
  }
}

export interface HybridGenerateRequest {
  skus: string[]
  options: {
    titles: boolean
    descriptions: boolean
    platforms: ('google' | 'bing' | 'shopify')[]
  }
}

// =============================================================================
// Response Types
// =============================================================================

export interface HealthResponse {
  status: 'healthy' | 'degraded'
  service: string
  version: string
  product_catalog_count: number
  supabase_connected: boolean
}

export interface OptimizeResponse {
  success: boolean
  master_sku: string
  message: string
  report?: string
  error?: string
}

export interface RegenerateResponse {
  success: boolean
  master_sku: string
  content_type: string
  platform: string
  content: string
  used_feedback: boolean
  model?: string
}

export interface BatchJobResponse {
  success: boolean
  job_id: string
  status: string
  total_skus: number
}

export interface BatchSkuStatus {
  id: string
  job_id: string
  master_sku: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  started_at?: string
  completed_at?: string
}

export interface BatchStatusResponse {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'partial' | 'failed'
  total_skus: number
  completed_skus: number
  failed_skus: number
  expanded_total_skus?: number
  expanded_completed_skus?: number
  expanded_failed_skus?: number
  skus: BatchSkuStatus[]
}

export interface HybridJobResponse {
  success: boolean
  job_id: string
  status: string
  total_skus: number
  multi_sku_families: number
  single_skus: number
  strategy: {
    base_skus: number
    variant_skus: number
  }
}

// =============================================================================
// Error Types
// =============================================================================

export class PipelineError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public detail?: string
  ) {
    super(message)
    this.name = 'PipelineError'
  }
}

// =============================================================================
// Pipeline Client
// =============================================================================

export class PipelineClient {
  private baseUrl: string

  constructor(baseUrl?: string) {
    const url = baseUrl || PIPELINE_URL
    if (!url) {
      throw new PipelineError(
        'FEEDOPS_PIPELINE_URL environment variable not set',
        500
      )
    }
    // Remove trailing slash if present
    this.baseUrl = url.replace(/\/$/, '')
  }

  /**
   * Check pipeline health and connectivity.
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`)
    if (!response.ok) {
      throw new PipelineError(
        `Health check failed: ${response.statusText}`,
        response.status
      )
    }
    return response.json()
  }

  /**
   * Optimize a single SKU - generates titles and descriptions for all platforms.
   */
  async optimizeSku(request: OptimizeRequest): Promise<OptimizeResponse> {
    const response = await fetch(`${this.baseUrl}/optimize-sku`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        master_sku: request.master_sku,
        num_candidates: request.num_candidates ?? 3,
        dry_run: request.dry_run ?? true,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new PipelineError(
        error.detail || response.statusText,
        response.status,
        error.detail
      )
    }

    return response.json()
  }

  /**
   * Regenerate specific content (title or description) with optional feedback.
   */
  async regenerate(request: RegenerateRequest): Promise<RegenerateResponse> {
    const response = await fetch(`${this.baseUrl}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        master_sku: request.master_sku,
        content_type: request.content_type,
        platform: request.platform,
        feedback: request.feedback,
        finish_code: request.finish_code,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new PipelineError(
        error.detail || response.statusText,
        response.status,
        error.detail
      )
    }

    return response.json()
  }

  /**
   * Queue batch optimization for multiple SKUs.
   * Returns immediately with job_id - use getBatchStatus to check progress.
   */
  async batchOptimize(request: BatchOptimizeRequest): Promise<BatchJobResponse> {
    const response = await fetch(`${this.baseUrl}/batch-optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skus: request.skus,
        num_candidates: request.num_candidates ?? 1,
        dry_run: request.dry_run ?? true,
        options: request.options,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new PipelineError(
        error.detail || response.statusText,
        response.status,
        error.detail
      )
    }

    return response.json()
  }

  /**
   * Get status of a batch optimization job.
   */
  async getBatchStatus(jobId: string): Promise<BatchStatusResponse> {
    const response = await fetch(`${this.baseUrl}/batch-status/${jobId}`)

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new PipelineError(
        error.detail || response.statusText,
        response.status,
        error.detail
      )
    }

    return response.json()
  }

  /**
   * Generate content using hybrid approach for multi-SKU families.
   * Detects families automatically and uses variant adaptation for cost savings.
   * Returns immediately with job_id - use getBatchStatus to check progress.
   *
   * **Always use this instead of the TypeScript dashboard implementation.**
   * Cloud Run has no timeout limits and can handle any batch size.
   */
  async hybridGenerate(request: HybridGenerateRequest): Promise<HybridJobResponse> {
    const response = await fetch(`${this.baseUrl}/hybrid-generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skus: request.skus,
        options: request.options,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new PipelineError(
        error.detail || response.statusText,
        response.status,
        error.detail
      )
    }

    return response.json()
  }

  /**
   * Poll batch job until completion or timeout.
   * @param jobId - The batch job ID to poll
   * @param options - Polling options
   * @returns Final batch status
   */
  async waitForBatchCompletion(
    jobId: string,
    options: {
      pollIntervalMs?: number
      timeoutMs?: number
      onProgress?: (status: BatchStatusResponse) => void
    } = {}
  ): Promise<BatchStatusResponse> {
    const pollInterval = options.pollIntervalMs ?? 5000
    const timeout = options.timeoutMs ?? 600000 // 10 minutes default
    const startTime = Date.now()

    while (Date.now() - startTime < timeout) {
      const status = await this.getBatchStatus(jobId)

      if (options.onProgress) {
        options.onProgress(status)
      }

      if (
        status.status === 'completed' ||
        status.status === 'partial' ||
        status.status === 'failed'
      ) {
        return status
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval))
    }

    throw new PipelineError(`Batch job ${jobId} timed out after ${timeout}ms`)
  }
}

// =============================================================================
// Singleton Instance & Helpers
// =============================================================================

let _client: PipelineClient | null = null

/**
 * Get the singleton PipelineClient instance.
 * Throws if FEEDOPS_PIPELINE_URL is not configured.
 */
export function getPipelineClient(): PipelineClient {
  if (!_client) {
    _client = new PipelineClient()
  }
  return _client
}

/**
 * Check if the pipeline is configured (URL is set).
 */
export function isPipelineConfigured(): boolean {
  return !!PIPELINE_URL
}

/**
 * Check if Cloud Run mode is enabled.
 */
export function isCloudRunEnabled(): boolean {
  return process.env.FEEDOPS_USE_CLOUD_RUN === '1'
}

/**
 * Get pipeline client if configured, otherwise return null.
 * Useful for optional Cloud Run integration.
 */
export function getOptionalPipelineClient(): PipelineClient | null {
  if (!isPipelineConfigured()) {
    return null
  }
  try {
    return getPipelineClient()
  } catch {
    return null
  }
}
