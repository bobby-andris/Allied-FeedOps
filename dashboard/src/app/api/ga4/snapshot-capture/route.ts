import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4AttributionQuality } from '@/lib/ga4/client'
import {
  buildRootCauseRows,
  computeConsecutiveOutOfRangeStreak,
  computeLandingInvalidRevenueShare,
  evaluateAttributionIncidents,
  fetchGa4CampaignPatternQuality,
  fetchGa4LandingPageQuality,
  fetchGa4SourceMediumQuality,
  getNormalizedForensicsPropertyId,
  isReconciliationOutOfRange,
  resolveGa4DateWindow,
  type Ga4ShopifyReconciliationSummary,
} from '@/lib/ga4/forensics'
import { fetchShopifyOrderSnapshots } from '@/lib/shopify/value-signals'
import { createAdminClient } from '@/lib/supabase/admin'

interface SnapshotCaptureResult {
  propertyId: string
  reportDate: string
  qualityUpserted: boolean
  sourceMediumRowsUpserted: number
  landingPageRowsUpserted: number
  rootCauseRowsUpserted: number
  reconciliationUpserted: boolean
  incidentsInserted: number
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  if (error && typeof error === 'object') {
    const maybeMessage = Reflect.get(error, 'message')
    const maybeDetails = Reflect.get(error, 'details')
    const maybeHint = Reflect.get(error, 'hint')
    const parts = [maybeMessage, maybeDetails, maybeHint]
      .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
      .map((part) => part.trim())
    if (parts.length > 0) {
      return parts.join(' | ')
    }
  }
  return 'Unknown error'
}

function isMissingRelationError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }
  const code = Reflect.get(error, 'code')
  if (code === '42P01' || code === 'PGRST205') {
    return true
  }
  const message = extractErrorMessage(error).toLowerCase()
  return (
    (message.includes('does not exist') && message.includes('relation')) ||
    message.includes('could not find the table')
  )
}

function sanitizeInteger(input: string | null, fallback: number, max: number): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function allowCronGet(request: NextRequest): boolean {
  const cronHeader = request.headers.get('x-vercel-cron')
  if (cronHeader) {
    return true
  }

  const secret = process.env.CRON_SECRET
  if (!secret) {
    return false
  }
  const authHeader = request.headers.get('authorization')
  return authHeader === `Bearer ${secret}`
}

async function buildReconciliationSummary(input: {
  propertyId: string
  startDate: string
  endDate: string
  maxOrders: number
}): Promise<Ga4ShopifyReconciliationSummary> {
  const { propertyId, startDate, endDate, maxOrders } = input
  const resolvedWindow = resolveGa4DateWindow(startDate, endDate)
  const orders = await fetchShopifyOrderSnapshots({
    lookbackDays: resolvedWindow.lookbackDays + 2,
    maxOrders,
  })

  const startMs = resolvedWindow.start.getTime()
  const endMs = resolvedWindow.end.getTime() + 24 * 60 * 60 * 1000 - 1
  const windowOrders = orders.filter((order) => {
    const createdAtMs = new Date(order.createdAt).getTime()
    return createdAtMs >= startMs && createdAtMs <= endMs
  })

  const shopifyRevenue = Number(
    windowOrders.reduce((sum, order) => sum + order.totalRevenue, 0).toFixed(4)
  )

  return {
    propertyId,
    startDate: resolvedWindow.startDate,
    endDate: resolvedWindow.endDate,
    ga4Revenue: 0,
    shopifyRevenue,
    revenueDelta: 0,
    revenueRatio: null,
    orderCount: windowOrders.length,
    generatedAt: new Date().toISOString(),
  }
}

async function captureSnapshot(request: NextRequest): Promise<NextResponse> {
  const params = request.nextUrl.searchParams
  const propertyId = getNormalizedForensicsPropertyId(params.get('property_id') ?? undefined)
  const startDate = params.get('start_date') ?? 'yesterday'
  const endDate = params.get('end_date') ?? 'yesterday'
  const limit = sanitizeInteger(params.get('limit'), 3000, 20000)
  const maxOrders = sanitizeInteger(params.get('max_orders'), 3000, 10000)
  const warnings: string[] = []

  const resolvedWindow = resolveGa4DateWindow(startDate, endDate)
  const reportDate = resolvedWindow.endDate

  let quality: Awaited<ReturnType<typeof fetchGa4AttributionQuality>> = {
    propertyId,
    startDate,
    endDate,
    generatedAt: new Date().toISOString(),
    totalRevenue: 0,
    unassignedRevenue: 0,
    notSetCampaignRevenue: 0,
    unassignedRevenueShare: 0,
    notSetCampaignRevenueShare: 0,
    qualityScore: 0,
    riskLevel: 'high',
  }
  let sourceMediumRows: Awaited<ReturnType<typeof fetchGa4SourceMediumQuality>>['rows'] = []
  let landingPageRows: Awaited<ReturnType<typeof fetchGa4LandingPageQuality>>['rows'] = []
  let campaignPatternRows: Awaited<ReturnType<typeof fetchGa4CampaignPatternQuality>>['rows'] = []
  let reconciliation: Ga4ShopifyReconciliationSummary = {
    propertyId,
    startDate: resolvedWindow.startDate,
    endDate: resolvedWindow.endDate,
    ga4Revenue: 0,
    shopifyRevenue: 0,
    revenueDelta: 0,
    revenueRatio: null,
    orderCount: 0,
    generatedAt: new Date().toISOString(),
  }

  try {
    quality = await fetchGa4AttributionQuality({
      propertyId,
      startDate,
      endDate,
      limit,
    })
  } catch (error) {
    warnings.push(
      `Attribution quality unavailable from GA4 Data API: ${extractErrorMessage(error)}`
    )
  }

  try {
    const sourceMedium = await fetchGa4SourceMediumQuality({
      propertyId,
      startDate,
      endDate,
      limit,
    })
    sourceMediumRows = sourceMedium.rows
  } catch (error) {
    warnings.push(`Source/medium diagnostics unavailable: ${extractErrorMessage(error)}`)
  }

  try {
    const landing = await fetchGa4LandingPageQuality({
      propertyId,
      startDate,
      endDate,
      limit,
    })
    landingPageRows = landing.rows
  } catch (error) {
    warnings.push(`Landing page diagnostics unavailable: ${extractErrorMessage(error)}`)
  }

  try {
    const campaignPatterns = await fetchGa4CampaignPatternQuality({
      propertyId,
      startDate,
      endDate,
      limit,
    })
    campaignPatternRows = campaignPatterns.rows
  } catch (error) {
    warnings.push(
      `Campaign naming diagnostics unavailable: ${extractErrorMessage(error)}`
    )
  }

  try {
    reconciliation = await buildReconciliationSummary({
      propertyId,
      startDate,
      endDate,
      maxOrders,
    })
  } catch (error) {
    warnings.push(`Shopify reconciliation unavailable: ${extractErrorMessage(error)}`)
  }

  reconciliation.ga4Revenue = Number(quality.totalRevenue.toFixed(4))
  reconciliation.revenueDelta = Number((reconciliation.ga4Revenue - reconciliation.shopifyRevenue).toFixed(4))
  reconciliation.revenueRatio =
    reconciliation.shopifyRevenue > 0
      ? Number((reconciliation.ga4Revenue / reconciliation.shopifyRevenue).toFixed(6))
      : null

  const landingInvalidRevenueShare = computeLandingInvalidRevenueShare(landingPageRows)
  const rootCauseRows = buildRootCauseRows({
    sourceMediumRows,
    landingPageRows,
    campaignPatternRows,
  })

  const result: SnapshotCaptureResult = {
    propertyId,
    reportDate,
    qualityUpserted: false,
    sourceMediumRowsUpserted: 0,
    landingPageRowsUpserted: 0,
    rootCauseRowsUpserted: 0,
    reconciliationUpserted: false,
    incidentsInserted: 0,
  }

  try {
    const supabase = createAdminClient()

    const { error: qualityError } = await supabase
      .from('ga4_attribution_quality_daily')
      .upsert(
        {
          property_id: propertyId,
          report_date: reportDate,
          unattributed_revenue_share: Number(
            Math.max(quality.unassignedRevenueShare, quality.notSetCampaignRevenueShare).toFixed(6)
          ),
          unassigned_channel_revenue_share: Number(quality.unassignedRevenueShare.toFixed(6)),
          not_set_campaign_revenue_share: Number(quality.notSetCampaignRevenueShare.toFixed(6)),
          reconciliation_delta: reconciliation.revenueDelta,
          quality_score: Number(quality.qualityScore.toFixed(6)),
          source_payload: {
            start_date: quality.startDate,
            end_date: quality.endDate,
            total_revenue: quality.totalRevenue,
            generated_at: quality.generatedAt,
          },
        },
        {
          onConflict: 'property_id,report_date',
        }
      )

    if (qualityError) {
      throw qualityError
    }
    result.qualityUpserted = true

    if (sourceMediumRows.length > 0) {
      const payload = sourceMediumRows.map((row) => ({
        property_id: propertyId,
        report_date: reportDate,
        source_medium: row.sourceMedium,
        quality_bucket: row.bucket,
        sessions: row.sessions,
        transactions: row.transactions,
        purchase_revenue: Number(row.purchaseRevenue.toFixed(4)),
        revenue_share: row.revenueShare,
        session_share: row.sessionShare,
        source_payload: {
          start_date: startDate,
          end_date: endDate,
        },
      }))

      const { error } = await supabase
        .from('ga4_source_medium_daily')
        .upsert(payload, { onConflict: 'property_id,report_date,quality_bucket,source_medium' })

      if (error) {
        throw error
      }
      result.sourceMediumRowsUpserted = payload.length
    }

    if (landingPageRows.length > 0) {
      const payload = landingPageRows.map((row) => ({
        property_id: propertyId,
        report_date: reportDate,
        landing_page: row.landingPage,
        quality_bucket: row.bucket,
        sessions: row.sessions,
        transactions: row.transactions,
        purchase_revenue: Number(row.purchaseRevenue.toFixed(4)),
        revenue_share: row.revenueShare,
        session_share: row.sessionShare,
        source_payload: {
          start_date: startDate,
          end_date: endDate,
        },
      }))

      const { error } = await supabase
        .from('ga4_landing_page_quality_daily')
        .upsert(payload, { onConflict: 'property_id,report_date,quality_bucket,landing_page' })

      if (error) {
        throw error
      }
      result.landingPageRowsUpserted = payload.length
    }

    if (rootCauseRows.length > 0) {
      const payload = rootCauseRows.map((row) => ({
        property_id: propertyId,
        report_date: reportDate,
        root_cause_type: row.rootCauseType,
        root_cause_key: row.rootCauseKey,
        sessions: row.sessions,
        transactions: row.transactions,
        purchase_revenue: Number(row.purchaseRevenue.toFixed(4)),
        revenue_share: row.revenueShare,
        session_share: row.sessionShare,
        source_payload: {
          sample_values: row.sampleValues,
          start_date: startDate,
          end_date: endDate,
        },
      }))

      const { error } = await supabase
        .from('ga4_attribution_root_cause_daily')
        .upsert(payload, { onConflict: 'property_id,report_date,root_cause_type,root_cause_key' })

      if (error) {
        throw error
      }
      result.rootCauseRowsUpserted = payload.length
    }

    const { error: reconciliationError } = await supabase
      .from('ga4_shopify_reconciliation_daily')
      .upsert(
        {
          property_id: propertyId,
          report_date: reportDate,
          ga4_revenue: reconciliation.ga4Revenue,
          shopify_revenue: reconciliation.shopifyRevenue,
          revenue_delta: reconciliation.revenueDelta,
          revenue_ratio: reconciliation.revenueRatio,
          order_count: reconciliation.orderCount,
          source_payload: {
            start_date: reconciliation.startDate,
            end_date: reconciliation.endDate,
            generated_at: reconciliation.generatedAt,
          },
        },
        { onConflict: 'property_id,report_date' }
      )

    if (reconciliationError) {
      throw reconciliationError
    }
    result.reconciliationUpserted = true

    const { data: ratioRows, error: ratioError } = await supabase
      .from('ga4_shopify_reconciliation_daily')
      .select('revenue_ratio, report_date')
      .eq('property_id', propertyId)
      .order('report_date', { ascending: false })
      .limit(3)

    if (ratioError) {
      throw ratioError
    }

    const reconciliationOutOfRangeStreak = computeConsecutiveOutOfRangeStreak(
      (ratioRows ?? []).map((row) => row.revenue_ratio as number | null)
    )

    const incidents = evaluateAttributionIncidents({
      unassignedRevenueShare: quality.unassignedRevenueShare,
      notSetCampaignRevenueShare: quality.notSetCampaignRevenueShare,
      landingInvalidRevenueShare,
      reconciliationRatio: reconciliation.revenueRatio,
      reconciliationOutOfRangeStreak,
      propertyId,
      reportDate,
    })

    if (incidents.length > 0) {
      const ruleIds = incidents.map((incident) => incident.ruleId)
      const { data: existingIncidents, error: existingIncidentsError } = await supabase
        .from('guardrail_incidents')
        .select('rule_id, metadata, status')
        .in('rule_id', ruleIds)
        .in('status', ['open', 'acknowledged'])

      if (existingIncidentsError) {
        throw existingIncidentsError
      }

      const existingKeys = new Set(
        (existingIncidents ?? [])
          .map((incident) => {
            const metadata = (incident.metadata ?? {}) as Record<string, unknown>
            const existingDate =
              typeof metadata.report_date === 'string' ? metadata.report_date : undefined
            return existingDate ? `${incident.rule_id}|${existingDate}` : null
          })
          .filter((key): key is string => Boolean(key))
      )

      const incidentPayload = incidents
        .filter((incident) => !existingKeys.has(`${incident.ruleId}|${reportDate}`))
        .map((incident) => ({
          rule_id: incident.ruleId,
          severity: incident.severity,
          status: incident.status,
          impacted_entities: incident.impactedEntities,
          message: incident.message,
          suggested_action:
            incident.ruleId === 'ga4_shopify_reconciliation_ratio'
              ? 'Review GA4/Shopify revenue parity and attribution pipelines with analytics owner.'
              : 'Generate evidence packet and escalate to analytics implementation owner.',
          metadata: incident.metadata,
        }))

      if (incidentPayload.length > 0) {
        const { error: incidentInsertError } = await supabase
          .from('guardrail_incidents')
          .insert(incidentPayload)
        if (incidentInsertError) {
          throw incidentInsertError
        }
      }

      result.incidentsInserted = incidentPayload.length
    }
  } catch (error) {
    if (isMissingRelationError(error)) {
      warnings.push(
        'Snapshot persistence failed: required attribution telemetry tables are missing. Apply migrations 033 and 034.'
      )
    } else {
      warnings.push(`Snapshot persistence failed: ${extractErrorMessage(error)}`)
    }
  }

  return NextResponse.json({
    generated_at: new Date().toISOString(),
    property_id: propertyId,
    report_date: reportDate,
    start_date: startDate,
    end_date: endDate,
    landing_invalid_revenue_share: landingInvalidRevenueShare,
    reconciliation_out_of_range: isReconciliationOutOfRange(reconciliation.revenueRatio),
    snapshot_result: result,
    quality_summary: quality,
    reconciliation_summary: reconciliation,
    warnings,
    available: warnings.length === 0,
  })
}

export async function POST(request: NextRequest) {
  return captureSnapshot(request)
}

export async function GET(request: NextRequest) {
  if (!allowCronGet(request)) {
    return NextResponse.json(
      {
        error: 'GET is reserved for trusted cron calls. Use POST for manual captures.',
      },
      { status: 405 }
    )
  }

  return captureSnapshot(request)
}
