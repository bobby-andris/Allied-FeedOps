import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4AttributionQuality } from '@/lib/ga4/client'
import {
  buildRootCauseRows,
  computeLandingInvalidRevenueShare,
  fetchGa4CampaignPatternQuality,
  fetchGa4LandingPageQuality,
  fetchGa4SourceMediumQuality,
  getNormalizedForensicsPropertyId,
} from '@/lib/ga4/forensics'
import { createAdminClient } from '@/lib/supabase/admin'

function sanitizeLimit(input: string | null, fallback = 250, max = 2000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
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

function isMissingRelationError(error: unknown, relationName: string): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }
  const code = Reflect.get(error, 'code')
  if (code === '42P01' || code === 'PGRST205') {
    return true
  }
  const message = extractErrorMessage(error).toLowerCase()
  const relationToken = relationName.toLowerCase()
  return (
    (message.includes('does not exist') || message.includes('could not find the table')) &&
    (message.includes(relationToken) || message.includes(`public.${relationToken}`))
  )
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const propertyId = getNormalizedForensicsPropertyId(params.get('property_id') ?? undefined)
  const startDate = params.get('start_date') ?? '30daysAgo'
  const endDate = params.get('end_date') ?? 'yesterday'
  const limit = sanitizeLimit(params.get('limit'))
  const warnings: string[] = []

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
    const landingPage = await fetchGa4LandingPageQuality({
      propertyId,
      startDate,
      endDate,
      limit,
    })
    landingPageRows = landingPage.rows
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

  const rootCauseRows = buildRootCauseRows({
    sourceMediumRows,
    landingPageRows,
    campaignPatternRows,
  })
  const landingInvalidRevenueShare = computeLandingInvalidRevenueShare(landingPageRows)

  let incidents: Array<{
    id: string
    rule_id: string
    severity: string
    status: string
    message: string
    impacted_entities: unknown
    metadata: unknown
    created_at: string
  }> = []

  try {
    const supabase = createAdminClient()
    const { data, error } = await supabase
      .from('guardrail_incidents')
      .select('id, rule_id, severity, status, message, impacted_entities, metadata, created_at')
      .or('rule_id.like.ga4_*,rule_id.like.attribution_*')
      .order('created_at', { ascending: false })
      .limit(50)

    if (error) {
      throw error
    }

    incidents = (data ?? []) as typeof incidents
  } catch (error) {
    if (isMissingRelationError(error, 'guardrail_incidents')) {
      warnings.push(
        'Guardrail incidents unavailable: table "guardrail_incidents" is missing. Apply migrations 033 and 034.'
      )
    } else {
      warnings.push(`Guardrail incidents unavailable: ${extractErrorMessage(error)}`)
    }
  }

  const available =
    quality.totalRevenue > 0 ||
    sourceMediumRows.length > 0 ||
    landingPageRows.length > 0 ||
    campaignPatternRows.length > 0

  return NextResponse.json({
    property_id: propertyId,
    start_date: startDate,
    end_date: endDate,
    generated_at: new Date().toISOString(),
    quality_summary: quality,
    source_medium_rows: sourceMediumRows,
    landing_page_rows: landingPageRows,
    campaign_pattern_rows: campaignPatternRows,
    root_cause_rows: rootCauseRows,
    landing_invalid_revenue_share: landingInvalidRevenueShare,
    incidents,
    available,
    warnings,
  })
}
