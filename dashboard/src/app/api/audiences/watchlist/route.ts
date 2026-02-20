import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4AttributionQuality, fetchGa4AudiencePerformance } from '@/lib/ga4/client'
import { buildAudienceWatchItems, DEFAULT_AUDIENCE_WATCHLIST } from '@/lib/ga4/audience-watchlist'

function sanitizeLimit(input: string | null, fallback = 100, max = 500): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const options = {
      propertyId: params.get('property_id') ?? undefined,
      startDate: params.get('start_date') ?? undefined,
      endDate: params.get('end_date') ?? undefined,
      limit: sanitizeLimit(params.get('limit')),
    }

    const warnings: string[] = []
    let attribution: Awaited<ReturnType<typeof fetchGa4AttributionQuality>> = {
      totalRevenue: 0,
      unassignedRevenue: 0,
      notSetCampaignRevenue: 0,
      unassignedRevenueShare: 0,
      notSetCampaignRevenueShare: 0,
      qualityScore: 0,
      riskLevel: 'high' as const,
      generatedAt: new Date().toISOString(),
      propertyId: options.propertyId ?? 'unknown',
      startDate: options.startDate ?? '30daysAgo',
      endDate: options.endDate ?? 'yesterday',
    }

    try {
      attribution = await fetchGa4AttributionQuality(options)
    } catch (error) {
      warnings.push(
        `Attribution quality unavailable from GA4 Data API: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`
      )
    }

    let audienceRows = [] as Awaited<ReturnType<typeof fetchGa4AudiencePerformance>>['rows']
    try {
      const audiencePerformance = await fetchGa4AudiencePerformance(options)
      audienceRows = audiencePerformance.rows
    } catch (error) {
      warnings.push(
        `Audience metrics unavailable from GA4 Data API: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`
      )
    }

    const watchItems = buildAudienceWatchItems(audienceRows, DEFAULT_AUDIENCE_WATCHLIST)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      attribution_quality: attribution,
      watchlist: watchItems,
      warnings,
      available: warnings.length === 0,
    })
  } catch (error) {
    console.error('Audience watchlist fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
