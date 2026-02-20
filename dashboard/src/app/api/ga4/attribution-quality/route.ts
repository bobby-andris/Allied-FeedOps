import { NextRequest, NextResponse } from 'next/server'
import {
  computeAttributionQuality,
  fetchGa4CampaignPerformance,
  fetchGa4AttributionQuality,
  getCanonicalGa4PropertyId,
} from '@/lib/ga4/client'

function sanitizeLimit(input: string | null, fallback = 200, max = 2000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const propertyId = params.get('property_id') ?? getCanonicalGa4PropertyId()
  const startDate = params.get('start_date') ?? '30daysAgo'
  const endDate = params.get('end_date') ?? 'yesterday'
  const options = {
    propertyId,
    startDate,
    endDate,
    limit: sanitizeLimit(params.get('limit')),
  }

  try {
    const [quality, campaignReport] = await Promise.all([
      fetchGa4AttributionQuality(options),
      fetchGa4CampaignPerformance(options),
    ])

    const problematicRows = campaignReport.rows
      .filter((row) => {
        const channel = row.channelGroup.toLowerCase().trim()
        const campaign = row.campaignName.toLowerCase().replace(/\s+/g, '')
        return channel === 'unassigned' || campaign === '(notset)' || campaign === 'notset'
      })
      .sort((a, b) => b.purchaseRevenue - a.purchaseRevenue)
      .slice(0, 25)

    return NextResponse.json({
      ...quality,
      problematic_rows: problematicRows,
      quality_summary: computeAttributionQuality(campaignReport.rows),
      available: true,
      warnings: [],
    })
  } catch (error) {
    console.error('GA4 attribution quality fetch failed:', error)
    const message = error instanceof Error ? error.message : 'GA4 attribution quality unavailable'
    const fallbackSummary = computeAttributionQuality([])

    return NextResponse.json({
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
      problematic_rows: [],
      quality_summary: fallbackSummary,
      available: false,
      warnings: [message],
    })
  }
}
