import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { resolveCanonicalMasterSkuList } from '@/lib/master-sku'
import {
  CATCHALL_CUSTOM_LABEL,
  isCatchallCustomLabel,
  normalizeCustomLabelValue,
} from '@/lib/regeneration/custom-label'

interface BatchRegenerateRequest {
  skus?: string[]
  all?: boolean
  custom_label_0?: string
  platforms?: Platform[]
  content_types?: ContentType[]
}

interface RegenerateResult {
  sku: string
  platform: Platform
  content_type: ContentType
  success: boolean
  state?: 'completed' | 'no_change'
  idempotent?: boolean
  content?: string
  version?: number
  validation_errors?: string[]
  actionable_message?: string | null
  code?: string | null
  step?: string | null
  error?: string
}

type Platform = 'google' | 'bing' | 'shopify'
type ContentType = 'title' | 'description'

const PLATFORMS: Platform[] = ['google', 'bing', 'shopify']
const CONTENT_TYPES: ContentType[] = ['title', 'description']
const DELAY_BETWEEN_CALLS_MS = 250
const PAGE_SIZE = 1000
const REGENERATE_AUTH_FORWARD_HEADERS = ['cookie', 'authorization'] as const

interface GeneratedContentSkuCount {
  skuCounts: Map<string, number>
  totalItems: number
}

interface VariantLabelRow {
  master_sku: string | null
  custom_label_0: string | null
  custom_labels: Record<string, unknown> | null
}

type RegenerateSelectionScope = 'all' | 'skus' | 'custom_label_0'

interface ResolvedTargetSkus {
  targetSkus: string[]
  totalContentItems: number
  scope: RegenerateSelectionScope
}

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function getRegenerateEndpoint(request: NextRequest): string {
  return new URL('/api/regenerate', request.url).toString()
}

function getForwardedRegenerateHeaders(request: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  for (const headerName of REGENERATE_AUTH_FORWARD_HEADERS) {
    const value = request.headers.get(headerName)
    if (value) headers[headerName] = value
  }
  return headers
}

type ParsedRegenerateErrorPayload = {
  error?: unknown
  actionable_message?: unknown
  code?: unknown
  step?: unknown
  validation_errors?: unknown
}

function isInternalRegenerateAuthFailure(response: Response): boolean {
  if (response.status === 401 || response.status === 403 || response.status === 307) {
    return true
  }
  return response.redirected
}

function extractSegmentLabel(row: VariantLabelRow): string | null {
  const direct = typeof row.custom_label_0 === 'string' ? row.custom_label_0 : null
  if (direct && direct.trim()) return direct.trim()

  if (row.custom_labels && typeof row.custom_labels === 'object') {
    const labels = row.custom_labels as Record<string, unknown>
    const nested = typeof labels.custom_label_0 === 'string'
      ? labels.custom_label_0
      : (typeof labels.customLabel0 === 'string' ? labels.customLabel0 : null)
    if (nested && nested.trim()) return nested.trim()
  }
  return null
}

function uniqueMasterSkus(rows: VariantLabelRow[]): string[] {
  return [...new Set(rows.map((row) => row.master_sku).filter((sku): sku is string => Boolean(sku)))]
}

function sumItemCountForSkus(skuCounts: Map<string, number>, skus: string[]): number {
  return skus.reduce((acc, sku) => acc + (skuCounts.get(sku) ?? 0), 0)
}

async function fetchGeneratedContentSkuCounts(
  supabase: ReturnType<typeof createAdminClient>,
): Promise<GeneratedContentSkuCount> {
  const skuCounts = new Map<string, number>()
  let totalItems = 0
  let offset = 0

  while (true) {
    const { data, error } = await supabase
      .from('generated_content')
      .select('master_sku')
      .not('candidate_content', 'is', null)
      .order('master_sku', { ascending: true })
      .range(offset, offset + PAGE_SIZE - 1)

    if (error) {
      throw error
    }

    const rows = (data ?? []) as Array<{ master_sku: string | null }>
    if (rows.length === 0) break

    for (const row of rows) {
      if (!row.master_sku) continue
      totalItems += 1
      skuCounts.set(row.master_sku, (skuCounts.get(row.master_sku) ?? 0) + 1)
    }

    if (rows.length < PAGE_SIZE) break
    offset += PAGE_SIZE
  }

  return { skuCounts, totalItems }
}

function isMissingCustomLabelColumnError(error: unknown): boolean {
  const message = error instanceof Error
    ? error.message
    : (typeof error === 'object' && error && 'message' in error && typeof (error as { message?: unknown }).message === 'string'
      ? (error as { message: string }).message
      : '')
  return message.toLowerCase().includes('column variant_index.custom_label_0 does not exist')
}

async function fetchAllVariantRows(
  supabase: ReturnType<typeof createAdminClient>,
): Promise<VariantLabelRow[]> {
  const rows: VariantLabelRow[] = []
  let offset = 0
  let includeDirectLabelColumn = true

  while (true) {
    if (includeDirectLabelColumn) {
      const { data, error } = await supabase
        .from('variant_index')
        .select('master_sku, custom_label_0, custom_labels')
        .order('master_sku', { ascending: true })
        .range(offset, offset + PAGE_SIZE - 1)

      if (error && isMissingCustomLabelColumnError(error)) {
        includeDirectLabelColumn = false
        offset = 0
        rows.length = 0
        continue
      }

      if (error) {
        throw error
      }

      const page = (data ?? []) as VariantLabelRow[]
      rows.push(...page)
      if (page.length < PAGE_SIZE) break
      offset += PAGE_SIZE
      continue
    }

    const { data, error } = await supabase
      .from('variant_index')
      .select('master_sku, custom_labels')
      .order('master_sku', { ascending: true })
      .range(offset, offset + PAGE_SIZE - 1)

    if (error) {
      throw error
    }

    const page = ((data ?? []) as Array<{ master_sku: string | null; custom_labels: Record<string, unknown> | null }>)
      .map((row) => ({
          master_sku: row.master_sku,
          custom_label_0: null,
          custom_labels: row.custom_labels,
        }))
    rows.push(...page)
    if (page.length < PAGE_SIZE) break
    offset += PAGE_SIZE
  }

  return rows
}

async function fetchVariantMasterSkusByCustomLabel(
  supabase: ReturnType<typeof createAdminClient>,
  customLabel: string,
): Promise<string[]> {
  const variantRows = await fetchAllVariantRows(supabase)

  if (isCatchallCustomLabel(customLabel)) {
    return uniqueMasterSkus(variantRows.filter((row) => !extractSegmentLabel(row)))
  }

  const normalizedTarget = normalizeCustomLabelValue(customLabel)
  if (!normalizedTarget) return []

  const matches = variantRows.filter((row) => {
    const extracted = extractSegmentLabel(row)
    return extracted && normalizeCustomLabelValue(extracted) === normalizedTarget
  })

  return uniqueMasterSkus(matches)
}

async function resolveTargetSkus(args: {
  supabase: ReturnType<typeof createAdminClient>
  skus?: string[]
  all?: boolean
  customLabel0?: string
}): Promise<ResolvedTargetSkus> {
  const { supabase, skus, all, customLabel0 } = args
  const { skuCounts, totalItems } = await fetchGeneratedContentSkuCounts(supabase)
  const regeneratableSkus = new Set([...skuCounts.keys()])

  let rawTargetSkus: string[] = []
  let scope: RegenerateSelectionScope = 'skus'

  if (all) {
    rawTargetSkus = [...regeneratableSkus]
    scope = 'all'
  } else if (Array.isArray(skus) && skus.length > 0) {
    rawTargetSkus = skus
    scope = 'skus'
  } else if (customLabel0) {
    rawTargetSkus = await fetchVariantMasterSkusByCustomLabel(supabase, customLabel0)
    scope = 'custom_label_0'
  } else {
    return {
      targetSkus: [],
      totalContentItems: 0,
      scope: 'skus',
    }
  }

  const canonicalSkus = await resolveCanonicalMasterSkuList(supabase, rawTargetSkus)
  const dedupedCanonicalSkus = [...new Set(canonicalSkus.filter((sku) => sku))]

  if (scope === 'skus') {
    return {
      targetSkus: dedupedCanonicalSkus,
      totalContentItems: sumItemCountForSkus(skuCounts, dedupedCanonicalSkus),
      scope,
    }
  }

  const filteredSkus = dedupedCanonicalSkus.filter((sku) => regeneratableSkus.has(sku))
  const selectedTotalItems = scope === 'all'
    ? totalItems
    : sumItemCountForSkus(skuCounts, filteredSkus)

  return {
    targetSkus: filteredSkus,
    totalContentItems: selectedTotalItems,
    scope,
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: BatchRegenerateRequest = await request.json()
    const { skus, all, custom_label_0, platforms, content_types } = body
    const customLabel0 = typeof custom_label_0 === 'string' ? custom_label_0.trim() : ''

    if (!skus && !all && !customLabel0) {
      return NextResponse.json(
        {
          error: 'Must provide one of: "skus" array, "all: true", or "custom_label_0"',
          code: 'batch_regenerate_missing_selection',
          step: 'request_validation',
          actionable_message: 'Pass an explicit SKU list, set all=true, or provide custom_label_0 and retry.',
        },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()
    let resolvedTargets: ResolvedTargetSkus
    try {
      resolvedTargets = await resolveTargetSkus({
        supabase,
        skus,
        all,
        customLabel0: customLabel0 || undefined,
      })
    } catch (error) {
      console.error('Failed to resolve batch regenerate target SKUs:', error)
      return NextResponse.json(
        {
          error: 'Failed to fetch SKUs from database',
          code: 'batch_regenerate_sku_fetch_failed',
          step: 'target_sku_lookup',
          actionable_message: 'Retry. If this persists, inspect generated_content and variant_index access.',
        },
        { status: 500 }
      )
    }

    const targetSkus = resolvedTargets.targetSkus

    if (targetSkus.length === 0) {
      return NextResponse.json(
        {
          error: 'No SKUs to regenerate',
          code: 'batch_regenerate_empty_selection',
          step: 'target_sku_validation',
          actionable_message: 'Select SKUs that already have generated content and retry.',
        },
        { status: 400 }
      )
    }

    const targetPlatforms = platforms || [...PLATFORMS]
    const targetContentTypes = content_types || [...CONTENT_TYPES]
    const totalOperations =
      targetSkus.length * targetPlatforms.length * targetContentTypes.length

    const regenerateEndpoint = getRegenerateEndpoint(request)
    const regenerateHeaders = getForwardedRegenerateHeaders(request)

    const results: RegenerateResult[] = []
    let completed = 0
    let successful = 0
    let failed = 0

    for (const sku of targetSkus) {
      for (const platform of targetPlatforms) {
        for (const contentType of targetContentTypes) {
          try {
            const regenerateResponse = await fetch(regenerateEndpoint, {
              method: 'POST',
              headers: regenerateHeaders,
              body: JSON.stringify({
                master_sku: sku,
                content_type: contentType,
                platform,
                mode: 'simple',
              }),
            })

            const payload = await regenerateResponse
              .json()
              .catch(() => null)
            const parsedPayload: ParsedRegenerateErrorPayload | null =
              payload && typeof payload === 'object'
                ? (payload as ParsedRegenerateErrorPayload)
                : null

            if (!regenerateResponse.ok) {
              const authFailure = isInternalRegenerateAuthFailure(regenerateResponse)
              const errorMessage = authFailure
                ? 'Internal regenerate request was not authenticated'
                : (typeof parsedPayload?.error === 'string'
                  ? parsedPayload.error
                  : `Regeneration failed with status ${regenerateResponse.status}`)
              const actionableMessage = authFailure
                ? 'Refresh your dashboard session and retry. If this persists, inspect auth forwarding and middleware redirects.'
                : (typeof parsedPayload?.actionable_message === 'string'
                  ? parsedPayload.actionable_message
                  : 'Inspect API validation details for this SKU and retry.')
              results.push({
                sku,
                platform,
                content_type: contentType,
                success: false,
                error: errorMessage,
                actionable_message: actionableMessage,
                code: authFailure
                  ? 'batch_regenerate_internal_auth_required'
                  : (typeof parsedPayload?.code === 'string' ? parsedPayload.code : null),
                step: authFailure
                  ? 'internal_regenerate_auth'
                  : (typeof parsedPayload?.step === 'string' ? parsedPayload.step : null),
                validation_errors: Array.isArray(parsedPayload?.validation_errors)
                  ? parsedPayload.validation_errors.filter((v: unknown): v is string => typeof v === 'string')
                  : [],
              })
              failed++
            } else {
              results.push({
                sku,
                platform,
                content_type: contentType,
                success: true,
                state:
                  payload?.state === 'no_change'
                    ? 'no_change'
                    : 'completed',
                idempotent: payload?.idempotent === true,
                content:
                  typeof payload?.content === 'string'
                    ? payload.content
                    : undefined,
                version:
                  typeof payload?.version === 'number'
                    ? payload.version
                    : undefined,
                validation_errors: Array.isArray(payload?.validation_errors)
                  ? payload.validation_errors.filter((v: unknown): v is string => typeof v === 'string')
                  : [],
                actionable_message:
                  typeof payload?.actionable_message === 'string'
                    ? payload.actionable_message
                    : null,
              })
              successful++
            }
          } catch (error) {
            results.push({
              sku,
              platform,
              content_type: contentType,
              success: false,
              error:
                error instanceof Error ? error.message : 'Unknown error',
              actionable_message:
                'Retry this SKU. If it keeps failing, inspect dashboard API logs for this operation.',
              code: 'batch_regenerate_operation_exception',
              step: 'batch_regenerate_operation',
            })
            failed++
          }

          completed++
          if (completed % 10 === 0) {
            console.log(
              `Batch regeneration progress: ${completed}/${totalOperations} (${successful} success, ${failed} failed)`
            )
          }
          await sleep(DELAY_BETWEEN_CALLS_MS)
        }
      }
    }

    return NextResponse.json({
      success: true,
      selection_scope: resolvedTargets.scope,
      selected_custom_label_0: customLabel0 || null,
      summary: {
        total_skus: targetSkus.length,
        total_operations: totalOperations,
        successful,
        failed,
        with_validation_warnings: results.filter(
          (r) => r.success && Array.isArray(r.validation_errors) && r.validation_errors.length > 0
        ).length,
        no_change: results.filter((r) => r.state === 'no_change').length,
      },
      results,
    })
  } catch (error) {
    console.error('Batch regeneration error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Internal server error',
        code: 'batch_regenerate_unhandled_exception',
        step: 'route_exception',
        actionable_message: 'Retry once. If this persists, inspect dashboard API logs.',
      },
      { status: 500 }
    )
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const customLabel0Raw = searchParams.get('custom_label_0')
    const customLabel0 = customLabel0Raw?.trim()

    const supabase = createAdminClient()
    let resolvedTargets: ResolvedTargetSkus
    try {
      resolvedTargets = await resolveTargetSkus({
        supabase,
        all: !customLabel0,
        customLabel0: customLabel0 || undefined,
      })
    } catch (error) {
      console.error('Failed to fetch regeneration stats:', error)
      return NextResponse.json({ error: 'Failed to fetch content' }, { status: 500 })
    }

    const skus = resolvedTargets.targetSkus
    const totalItems = resolvedTargets.totalContentItems

    return NextResponse.json({
      skus,
      selection_scope: resolvedTargets.scope,
      selected_custom_label_0: customLabel0 ?? null,
      total_skus: skus.length,
      total_content_items: totalItems,
      estimated_time_minutes: Math.ceil((totalItems * 1.5) / 60),
      catchall_value: CATCHALL_CUSTOM_LABEL,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
