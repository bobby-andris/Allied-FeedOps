import { createAdminClient } from '@/lib/supabase/admin'

const OPENAI_USAGE_ENDPOINT = 'https://api.openai.com/v1/organization/usage/completions'
const OPENAI_COST_ENDPOINT = 'https://api.openai.com/v1/organization/costs'
const DEFAULT_BUCKET_WIDTH = '1d'
const DEFAULT_DELTA_TOLERANCE = 0.15

export interface DailyWindow {
  startIso: string
  endIso: string
}

export interface CostOutlier {
  request_id: string | null
  master_sku: string
  platform: string
  content_type: string
  mode: string
  cost_usd: number | null
  latency_ms: number | null
  provider_attempt_count: number | null
  parse_retry_count: number | null
  created_at: string
}

interface InternalWindowAggregate {
  totalRequests: number
  withCostRequests: number
  missingCostRequests: number
  totalTokens: number
  totalCostUsd: number
  avgLatencyMs: number | null
  p95LatencyMs: number | null
  providerAttemptCountSum: number
  parseRetryCountSum: number
  modeBreakdown: Record<string, { requests: number; cost_usd: number }>
}

interface OpenAiWindowAggregate {
  usageAvailable: boolean
  costsAvailable: boolean
  openaiRequestCount: number
  inputTokens: number
  outputTokens: number
  cachedInputTokens: number
  totalCostUsd: number | null
  currency: string
  metadata: Record<string, unknown>
  warnings: string[]
}

interface OpenAiUsageCredentials {
  apiKey: string | null
  organizationId: string | null
  projectId: string | null
  sourceEnv: 'OPENAI_USAGE_API_KEY' | 'OPENAI_ADMIN_API_KEY' | 'OPENAI_API_KEY' | null
}

interface DeltaClassification {
  status: 'ok' | 'attention' | 'missing_openai_data'
  categories: string[]
  deltaRatio: number | null
  deltaCostUsd: number | null
}

export interface ReconciliationWindowCapture {
  window_start: string
  window_end: string
  openai_total_cost_usd: number | null
  internal_total_cost_usd: number
  delta_cost_usd: number | null
  delta_ratio: number | null
  status: DeltaClassification['status']
  categories: string[]
  openai_total_requests: number
  internal_total_requests: number
  internal_missing_cost_requests: number
  provider_attempt_count_sum: number
  parse_retry_count_sum: number
  warnings: string[]
}

export interface CostReconciliationCaptureSummary {
  generated_at: string
  windows_processed: number
  capture_results: ReconciliationWindowCapture[]
  warning_count: number
}

export interface CostReconciliationReport {
  generated_at: string
  lookback_days: number
  latest: ReconciliationWindowCapture | null
  windows: ReconciliationWindowCapture[]
  cost_outliers: CostOutlier[]
  latency_outliers: CostOutlier[]
}

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) {
    return null
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const toInteger = (value: unknown): number => {
  const parsed = toNumber(value)
  if (parsed === null) {
    return 0
  }
  return Math.trunc(parsed)
}

const round6 = (value: number): number => Number(value.toFixed(6))

export function buildUtcDailyWindows(days: number, now: Date = new Date()): DailyWindow[] {
  const windowCount = Math.max(1, Math.min(Math.trunc(days), 30))
  const utcMidnightToday = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate()
  )
  const dayMs = 24 * 60 * 60 * 1000
  const windows: DailyWindow[] = []

  for (let offset = windowCount; offset >= 1; offset -= 1) {
    const start = new Date(utcMidnightToday - offset * dayMs)
    const end = new Date(utcMidnightToday - (offset - 1) * dayMs)
    windows.push({
      startIso: start.toISOString(),
      endIso: end.toISOString(),
    })
  }

  return windows
}

export function computePercentile(values: number[], percentile: number): number | null {
  if (values.length === 0) {
    return null
  }
  const sorted = [...values].sort((a, b) => a - b)
  const clamped = Math.min(Math.max(percentile, 0), 1)
  const position = (sorted.length - 1) * clamped
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  if (lower === upper) {
    return sorted[lower]
  }
  const weight = position - lower
  return sorted[lower] * (1 - weight) + sorted[upper] * weight
}

export function classifyReconciliationDelta(input: {
  openaiTotalCostUsd: number | null
  internalTotalCostUsd: number
  openaiTotalRequests: number
  internalTotalRequests: number
  internalMissingCostRequests: number
  providerAttemptCountSum: number
  tolerance?: number
}): DeltaClassification {
  const categories: string[] = []
  const tolerance = input.tolerance ?? DEFAULT_DELTA_TOLERANCE

  if (input.openaiTotalCostUsd === null) {
    categories.push('openai_usage_unavailable')
    if (input.internalTotalRequests > 0) {
      categories.push('internal_only_activity')
    }
    return {
      status: 'missing_openai_data',
      categories,
      deltaRatio: null,
      deltaCostUsd: null,
    }
  }

  const deltaCostUsd = round6(input.openaiTotalCostUsd - input.internalTotalCostUsd)
  const denominator = Math.max(Math.abs(input.openaiTotalCostUsd), 1e-9)
  const deltaRatio = round6(deltaCostUsd / denominator)

  if (Math.abs(deltaRatio) <= tolerance) {
    categories.push('within_tolerance')
  } else {
    categories.push('out_of_tolerance')
  }

  if (input.internalMissingCostRequests > 0) {
    categories.push('internal_missing_cost_rows')
  }

  if (input.openaiTotalRequests > 0 && input.internalTotalRequests === 0) {
    categories.push('openai_without_internal_lineage')
  }

  if (input.openaiTotalRequests === 0 && input.internalTotalRequests > 0) {
    categories.push('internal_without_openai_usage')
  }

  if (
    input.internalTotalRequests > 0 &&
    input.providerAttemptCountSum > input.internalTotalRequests
  ) {
    categories.push('retry_amplification_detected')
  }

  return {
    status: categories.includes('out_of_tolerance') ? 'attention' : 'ok',
    categories,
    deltaRatio,
    deltaCostUsd,
  }
}

function parseOpenAiUsagePayload(payload: unknown): {
  openaiRequestCount: number
  inputTokens: number
  outputTokens: number
  cachedInputTokens: number
  metadata: Record<string, unknown>
} {
  const page = (payload ?? {}) as Record<string, unknown>
  const buckets = Array.isArray(page.data) ? page.data : []

  let openaiRequestCount = 0
  let inputTokens = 0
  let outputTokens = 0
  let cachedInputTokens = 0

  for (const bucket of buckets) {
    const bucketRecord = (bucket ?? {}) as Record<string, unknown>
    const results = Array.isArray(bucketRecord.results) ? bucketRecord.results : []
    for (const result of results) {
      const row = (result ?? {}) as Record<string, unknown>
      openaiRequestCount += toInteger(
        row.num_model_requests ?? row.requests ?? row.request_count ?? 0
      )
      inputTokens += toInteger(row.input_tokens ?? row.prompt_tokens ?? 0)
      outputTokens += toInteger(row.output_tokens ?? row.completion_tokens ?? 0)
      cachedInputTokens += toInteger(row.input_cached_tokens ?? row.cached_input_tokens ?? 0)
    }
  }

  return {
    openaiRequestCount,
    inputTokens,
    outputTokens,
    cachedInputTokens,
    metadata: {
      bucket_count: buckets.length,
      has_next_page: Boolean((page as { has_more?: unknown }).has_more),
      next_page: (page as { next_page?: unknown }).next_page ?? null,
    },
  }
}

function parseOpenAiCostsPayload(payload: unknown): {
  totalCostUsd: number | null
  currency: string
  metadata: Record<string, unknown>
} {
  const page = (payload ?? {}) as Record<string, unknown>
  const buckets = Array.isArray(page.data) ? page.data : []
  let totalCost = 0
  let hasAnyCost = false
  let currency = 'usd'

  for (const bucket of buckets) {
    const row = (bucket ?? {}) as Record<string, unknown>
    const bucketResults = Array.isArray(row.results) ? row.results : []
    for (const result of bucketResults) {
      const resultRecord = (result ?? {}) as Record<string, unknown>
      const resultAmount = toNumber((resultRecord.amount as { value?: unknown } | undefined)?.value)
      if (resultAmount !== null) {
        totalCost += resultAmount
        hasAnyCost = true
      }
      const resultCurrency = (resultRecord.amount as { currency?: unknown } | undefined)?.currency
      if (typeof resultCurrency === 'string' && resultCurrency.trim()) {
        currency = resultCurrency
      }
    }

    const bucketAmount = toNumber((row.amount as { value?: unknown } | undefined)?.value)
    if (bucketAmount !== null) {
      totalCost += bucketAmount
      hasAnyCost = true
    }

    const bucketCurrency = (row.amount as { currency?: unknown } | undefined)?.currency
    if (typeof bucketCurrency === 'string' && bucketCurrency.trim()) {
      currency = bucketCurrency
    }

    const lineItems = Array.isArray(row.line_items) ? row.line_items : []
    for (const item of lineItems) {
      const itemRecord = (item ?? {}) as Record<string, unknown>
      const lineAmount = toNumber(
        (itemRecord.amount as { value?: unknown } | undefined)?.value ??
          itemRecord.amount ??
          itemRecord.cost_usd
      )
      if (lineAmount !== null) {
        totalCost += lineAmount
        hasAnyCost = true
      }
      const lineCurrency =
        (itemRecord.amount as { currency?: unknown } | undefined)?.currency ?? itemRecord.currency
      if (typeof lineCurrency === 'string' && lineCurrency.trim()) {
        currency = lineCurrency
      }
    }
  }

  return {
    totalCostUsd: hasAnyCost ? round6(totalCost) : null,
    currency,
    metadata: {
      bucket_count: buckets.length,
      has_next_page: Boolean((page as { has_more?: unknown }).has_more),
      next_page: (page as { next_page?: unknown }).next_page ?? null,
    },
  }
}

async function fetchOpenAiWindowAggregate(
  window: DailyWindow,
  credentials: OpenAiUsageCredentials
): Promise<OpenAiWindowAggregate> {
  const openAiApiKey = credentials.apiKey
  if (!openAiApiKey) {
    return {
      usageAvailable: false,
      costsAvailable: false,
      openaiRequestCount: 0,
      inputTokens: 0,
      outputTokens: 0,
      cachedInputTokens: 0,
      totalCostUsd: null,
      currency: 'usd',
      metadata: {},
      warnings: [
        'OpenAI usage key is not configured; set OPENAI_USAGE_API_KEY (preferred), OPENAI_ADMIN_API_KEY, or OPENAI_API_KEY.',
      ],
    }
  }

  const startUnix = Math.floor(new Date(window.startIso).getTime() / 1000)
  const endUnix = Math.floor(new Date(window.endIso).getTime() / 1000)
  const headers: Record<string, string> = {
    Authorization: `Bearer ${openAiApiKey}`,
    'Content-Type': 'application/json',
  }
  if (credentials.organizationId) {
    headers['OpenAI-Organization'] = credentials.organizationId
  }
  if (credentials.projectId) {
    headers['OpenAI-Project'] = credentials.projectId
  }

  const warnings: string[] = []

  let usageAvailable = false
  let openaiRequestCount = 0
  let inputTokens = 0
  let outputTokens = 0
  let cachedInputTokens = 0
  let usageMetadata: Record<string, unknown> = {}

  try {
    const usageUrl = new URL(OPENAI_USAGE_ENDPOINT)
    usageUrl.searchParams.set('start_time', String(startUnix))
    usageUrl.searchParams.set('end_time', String(endUnix))
    usageUrl.searchParams.set('bucket_width', DEFAULT_BUCKET_WIDTH)

    const response = await fetch(usageUrl.toString(), { headers, cache: 'no-store' })
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        warnings.push(
          `OpenAI usage API auth error (${response.status}); key source=${credentials.sourceEnv ?? 'unknown'}. ` +
            'Use an org-level key with organization usage/cost permissions and set OPENAI_ORG_ID if required.'
        )
      } else {
        warnings.push(`OpenAI usage API error (${response.status})`)
      }
    } else {
      const parsed = parseOpenAiUsagePayload(await response.json())
      usageAvailable = true
      openaiRequestCount = parsed.openaiRequestCount
      inputTokens = parsed.inputTokens
      outputTokens = parsed.outputTokens
      cachedInputTokens = parsed.cachedInputTokens
      usageMetadata = parsed.metadata
    }
  } catch (error) {
    warnings.push(
      `OpenAI usage API request failed: ${error instanceof Error ? error.message : String(error)}`
    )
  }

  let costsAvailable = false
  let totalCostUsd: number | null = null
  let currency = 'usd'
  let costMetadata: Record<string, unknown> = {}

  try {
    const costsUrl = new URL(OPENAI_COST_ENDPOINT)
    costsUrl.searchParams.set('start_time', String(startUnix))
    costsUrl.searchParams.set('end_time', String(endUnix))
    costsUrl.searchParams.set('bucket_width', DEFAULT_BUCKET_WIDTH)

    const response = await fetch(costsUrl.toString(), { headers, cache: 'no-store' })
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        warnings.push(
          `OpenAI costs API auth error (${response.status}); key source=${credentials.sourceEnv ?? 'unknown'}. ` +
            'Use an org-level key with organization usage/cost permissions and set OPENAI_ORG_ID if required.'
        )
      } else {
        warnings.push(`OpenAI costs API error (${response.status})`)
      }
    } else {
      const parsed = parseOpenAiCostsPayload(await response.json())
      costsAvailable = parsed.totalCostUsd !== null
      totalCostUsd = parsed.totalCostUsd
      currency = parsed.currency
      costMetadata = parsed.metadata
    }
  } catch (error) {
    warnings.push(
      `OpenAI costs API request failed: ${error instanceof Error ? error.message : String(error)}`
    )
  }

  return {
    usageAvailable,
    costsAvailable,
    openaiRequestCount,
    inputTokens,
    outputTokens,
    cachedInputTokens,
    totalCostUsd,
    currency,
    metadata: {
      usage: usageMetadata,
      costs: costMetadata,
    },
    warnings,
  }
}

function resolveOpenAiUsageCredentials(): OpenAiUsageCredentials {
  const usageApiKey = process.env.OPENAI_USAGE_API_KEY?.trim() || null
  if (usageApiKey) {
    return {
      apiKey: usageApiKey,
      organizationId: process.env.OPENAI_ORG_ID?.trim() || null,
      projectId: process.env.OPENAI_PROJECT_ID?.trim() || null,
      sourceEnv: 'OPENAI_USAGE_API_KEY',
    }
  }

  const adminApiKey = process.env.OPENAI_ADMIN_API_KEY?.trim() || null
  if (adminApiKey) {
    return {
      apiKey: adminApiKey,
      organizationId: process.env.OPENAI_ORG_ID?.trim() || null,
      projectId: process.env.OPENAI_PROJECT_ID?.trim() || null,
      sourceEnv: 'OPENAI_ADMIN_API_KEY',
    }
  }

  const defaultApiKey = process.env.OPENAI_API_KEY?.trim() || null
  return {
    apiKey: defaultApiKey,
    organizationId: process.env.OPENAI_ORG_ID?.trim() || null,
    projectId: process.env.OPENAI_PROJECT_ID?.trim() || null,
    sourceEnv: defaultApiKey ? 'OPENAI_API_KEY' : null,
  }
}

async function fetchInternalWindowAggregate(
  supabase: ReturnType<typeof createAdminClient>,
  window: DailyWindow
): Promise<InternalWindowAggregate> {
  const { data, error } = await supabase
    .from('regeneration_history')
    .select(
      'request_id,cost_usd,tokens_used,latency_ms,provider_attempt_count,parse_retry_count,mode,created_at'
    )
    .gte('created_at', window.startIso)
    .lt('created_at', window.endIso)

  if (error) {
    throw new Error(`Failed to load regeneration history: ${error.message}`)
  }

  const rows = Array.isArray(data) ? data : []
  const latencies: number[] = []
  const modeBreakdown: Record<string, { requests: number; cost_usd: number }> = {}

  let totalCostUsd = 0
  let totalTokens = 0
  let withCostRequests = 0
  let providerAttemptCountSum = 0
  let parseRetryCountSum = 0

  for (const row of rows) {
    const mode =
      typeof row.mode === 'string' && row.mode.trim().length > 0 ? row.mode : 'unknown'
    if (!modeBreakdown[mode]) {
      modeBreakdown[mode] = { requests: 0, cost_usd: 0 }
    }

    modeBreakdown[mode].requests += 1

    const costUsd = toNumber(row.cost_usd)
    if (costUsd !== null) {
      withCostRequests += 1
      totalCostUsd += costUsd
      modeBreakdown[mode].cost_usd += costUsd
    }

    totalTokens += toInteger(row.tokens_used)

    const latency = toNumber(row.latency_ms)
    if (latency !== null) {
      latencies.push(latency)
    }

    providerAttemptCountSum += toInteger(row.provider_attempt_count)
    parseRetryCountSum += toInteger(row.parse_retry_count)
  }

  const totalRequests = rows.length
  const missingCostRequests = totalRequests - withCostRequests
  const avgLatencyMs =
    latencies.length > 0
      ? Number((latencies.reduce((sum, value) => sum + value, 0) / latencies.length).toFixed(3))
      : null
  const p95Latency = computePercentile(latencies, 0.95)

  return {
    totalRequests,
    withCostRequests,
    missingCostRequests,
    totalTokens,
    totalCostUsd: round6(totalCostUsd),
    avgLatencyMs,
    p95LatencyMs: p95Latency === null ? null : Number(p95Latency.toFixed(3)),
    providerAttemptCountSum,
    parseRetryCountSum,
    modeBreakdown,
  }
}

export async function runCostReconciliationCapture(options?: {
  lookbackDays?: number
  now?: Date
  supabase?: ReturnType<typeof createAdminClient>
}): Promise<CostReconciliationCaptureSummary> {
  const lookbackDays = Math.max(1, Math.min(Math.trunc(options?.lookbackDays ?? 1), 30))
  const now = options?.now ?? new Date()
  const supabase = options?.supabase ?? createAdminClient()
  const openAiCredentials = resolveOpenAiUsageCredentials()

  const windows = buildUtcDailyWindows(lookbackDays, now)
  const captureResults: ReconciliationWindowCapture[] = []

  for (const window of windows) {
    const [internal, openai] = await Promise.all([
      fetchInternalWindowAggregate(supabase, window),
      fetchOpenAiWindowAggregate(window, openAiCredentials),
    ])

    const classification = classifyReconciliationDelta({
      openaiTotalCostUsd: openai.totalCostUsd,
      internalTotalCostUsd: internal.totalCostUsd,
      openaiTotalRequests: openai.openaiRequestCount,
      internalTotalRequests: internal.totalRequests,
      internalMissingCostRequests: internal.missingCostRequests,
      providerAttemptCountSum: internal.providerAttemptCountSum,
    })

    const generatedAt = now.toISOString()

    const { error: openAiRollupError } = await supabase.from('openai_usage_window_rollups').upsert(
      {
        window_start: window.startIso,
        window_end: window.endIso,
        bucket_width: DEFAULT_BUCKET_WIDTH,
        openai_request_count: openai.openaiRequestCount,
        input_tokens: openai.inputTokens,
        output_tokens: openai.outputTokens,
        cached_input_tokens: openai.cachedInputTokens,
        total_cost_usd: openai.totalCostUsd,
        currency: openai.currency,
        source: 'openai_organization_api',
        metadata: {
          usage_available: openai.usageAvailable,
          costs_available: openai.costsAvailable,
          warnings: openai.warnings,
          ...openai.metadata,
        },
        captured_at: generatedAt,
      },
      { onConflict: 'window_start,window_end,bucket_width' }
    )
    if (openAiRollupError) {
      throw new Error(`Failed to upsert openai usage rollup: ${openAiRollupError.message}`)
    }

    const { error: internalRollupError } = await supabase.from('generation_cost_window_rollups').upsert(
      {
        window_start: window.startIso,
        window_end: window.endIso,
        bucket_width: DEFAULT_BUCKET_WIDTH,
        internal_request_count: internal.totalRequests,
        with_cost_request_count: internal.withCostRequests,
        missing_cost_request_count: internal.missingCostRequests,
        total_tokens: internal.totalTokens,
        total_cost_usd: internal.totalCostUsd,
        avg_latency_ms: internal.avgLatencyMs,
        p95_latency_ms: internal.p95LatencyMs,
        provider_attempt_count_sum: internal.providerAttemptCountSum,
        parse_retry_count_sum: internal.parseRetryCountSum,
        mode_breakdown: internal.modeBreakdown,
        metadata: {
          lookback_days: lookbackDays,
        },
        captured_at: generatedAt,
      },
      { onConflict: 'window_start,window_end,bucket_width' }
    )
    if (internalRollupError) {
      throw new Error(
        `Failed to upsert internal generation cost rollup: ${internalRollupError.message}`
      )
    }

    const { error: deltaRollupError } = await supabase.from('cost_reconciliation_deltas').upsert(
      {
        window_start: window.startIso,
        window_end: window.endIso,
        bucket_width: DEFAULT_BUCKET_WIDTH,
        openai_total_cost_usd: openai.totalCostUsd,
        internal_total_cost_usd: internal.totalCostUsd,
        delta_cost_usd: classification.deltaCostUsd,
        delta_ratio: classification.deltaRatio,
        openai_total_requests: openai.openaiRequestCount,
        internal_total_requests: internal.totalRequests,
        internal_with_cost_requests: internal.withCostRequests,
        internal_missing_cost_requests: internal.missingCostRequests,
        provider_attempt_count_sum: internal.providerAttemptCountSum,
        parse_retry_count_sum: internal.parseRetryCountSum,
        status: classification.status,
        mismatch_categories: classification.categories,
        metadata: {
          warnings: openai.warnings,
        },
        captured_at: generatedAt,
      },
      { onConflict: 'window_start,window_end,bucket_width' }
    )
    if (deltaRollupError) {
      throw new Error(`Failed to upsert cost reconciliation delta: ${deltaRollupError.message}`)
    }

    captureResults.push({
      window_start: window.startIso,
      window_end: window.endIso,
      openai_total_cost_usd: openai.totalCostUsd,
      internal_total_cost_usd: internal.totalCostUsd,
      delta_cost_usd: classification.deltaCostUsd,
      delta_ratio: classification.deltaRatio,
      status: classification.status,
      categories: classification.categories,
      openai_total_requests: openai.openaiRequestCount,
      internal_total_requests: internal.totalRequests,
      internal_missing_cost_requests: internal.missingCostRequests,
      provider_attempt_count_sum: internal.providerAttemptCountSum,
      parse_retry_count_sum: internal.parseRetryCountSum,
      warnings: openai.warnings,
    })
  }

  return {
    generated_at: now.toISOString(),
    windows_processed: captureResults.length,
    capture_results: captureResults,
    warning_count: captureResults.reduce((sum, row) => sum + row.warnings.length, 0),
  }
}

function mapOutlierRow(row: Record<string, unknown>): CostOutlier {
  return {
    request_id: typeof row.request_id === 'string' && row.request_id.trim() ? row.request_id : null,
    master_sku: String(row.master_sku ?? ''),
    platform: String(row.platform ?? ''),
    content_type: String(row.content_type ?? ''),
    mode: String(row.mode ?? 'unknown'),
    cost_usd: toNumber(row.cost_usd),
    latency_ms: toNumber(row.latency_ms),
    provider_attempt_count: toNumber(row.provider_attempt_count),
    parse_retry_count: toNumber(row.parse_retry_count),
    created_at: String(row.created_at ?? ''),
  }
}

export async function readCostReconciliationReport(options?: {
  lookbackDays?: number
  supabase?: ReturnType<typeof createAdminClient>
  now?: Date
}): Promise<CostReconciliationReport> {
  const lookbackDays = Math.max(1, Math.min(Math.trunc(options?.lookbackDays ?? 14), 90))
  const supabase = options?.supabase ?? createAdminClient()
  const now = options?.now ?? new Date()

  const { data: windowsData, error: windowsError } = await supabase
    .from('cost_reconciliation_deltas')
    .select(
      'window_start,window_end,openai_total_cost_usd,internal_total_cost_usd,delta_cost_usd,delta_ratio,status,mismatch_categories,openai_total_requests,internal_total_requests,internal_missing_cost_requests,provider_attempt_count_sum,parse_retry_count_sum,metadata,captured_at'
    )
    .order('window_start', { ascending: false })
    .limit(lookbackDays)

  if (windowsError) {
    throw new Error(`Failed to load reconciliation windows: ${windowsError.message}`)
  }

  const windows: ReconciliationWindowCapture[] = (Array.isArray(windowsData) ? windowsData : []).map(
    (row) => {
      const metadataWarnings =
        row.metadata &&
        typeof row.metadata === 'object' &&
        Array.isArray((row.metadata as { warnings?: unknown }).warnings)
          ? ((row.metadata as { warnings?: unknown[] }).warnings ?? []).map((item) => String(item))
          : []

      return {
        window_start: String(row.window_start),
        window_end: String(row.window_end),
        openai_total_cost_usd: toNumber(row.openai_total_cost_usd),
        internal_total_cost_usd: toNumber(row.internal_total_cost_usd) ?? 0,
        delta_cost_usd: toNumber(row.delta_cost_usd),
        delta_ratio: toNumber(row.delta_ratio),
        status: (String(row.status) as ReconciliationWindowCapture['status']) || 'missing_openai_data',
        categories: Array.isArray(row.mismatch_categories)
          ? row.mismatch_categories.map((item: unknown) => String(item))
          : [],
        openai_total_requests: toInteger(row.openai_total_requests),
        internal_total_requests: toInteger(row.internal_total_requests),
        internal_missing_cost_requests: toInteger(row.internal_missing_cost_requests),
        provider_attempt_count_sum: toInteger(row.provider_attempt_count_sum),
        parse_retry_count_sum: toInteger(row.parse_retry_count_sum),
        warnings: metadataWarnings,
      }
    }
  )

  const earliestWindowStart = windows.reduce<string | null>((minValue, row) => {
    if (!minValue) {
      return row.window_start
    }
    return row.window_start < minValue ? row.window_start : minValue
  }, null)

  const lookbackStartIso =
    earliestWindowStart ??
    new Date(now.getTime() - lookbackDays * 24 * 60 * 60 * 1000).toISOString()

  const [
    { data: costOutlierRows, error: costOutlierError },
    { data: latencyOutlierRows, error: latencyOutlierError },
  ] = await Promise.all([
    supabase
      .from('regeneration_history')
      .select(
        'request_id,master_sku,platform,content_type,mode,cost_usd,latency_ms,provider_attempt_count,parse_retry_count,created_at'
      )
      .gte('created_at', lookbackStartIso)
      .order('cost_usd', { ascending: false, nullsFirst: false })
      .limit(10),
    supabase
      .from('regeneration_history')
      .select(
        'request_id,master_sku,platform,content_type,mode,cost_usd,latency_ms,provider_attempt_count,parse_retry_count,created_at'
      )
      .gte('created_at', lookbackStartIso)
      .order('latency_ms', { ascending: false, nullsFirst: false })
      .limit(10),
  ])

  if (costOutlierError) {
    throw new Error(`Failed to load cost outliers: ${costOutlierError.message}`)
  }
  if (latencyOutlierError) {
    throw new Error(`Failed to load latency outliers: ${latencyOutlierError.message}`)
  }

  const costOutliers = (Array.isArray(costOutlierRows) ? costOutlierRows : []).map((row) =>
    mapOutlierRow(row as Record<string, unknown>)
  )
  const latencyOutliers = (Array.isArray(latencyOutlierRows) ? latencyOutlierRows : []).map((row) =>
    mapOutlierRow(row as Record<string, unknown>)
  )

  return {
    generated_at: now.toISOString(),
    lookback_days: lookbackDays,
    latest: windows[0] ?? null,
    windows,
    cost_outliers: costOutliers,
    latency_outliers: latencyOutliers,
  }
}
