import { NextRequest, NextResponse } from 'next/server'
import {
  fetchGa4AttributionTrend,
  getNormalizedForensicsPropertyId,
} from '@/lib/ga4/forensics'

function sanitizeLimit(input: string | null, fallback = 20000, max = 50000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const propertyId = getNormalizedForensicsPropertyId(params.get('property_id') ?? undefined)
  const startDate = params.get('start_date') ?? '30daysAgo'
  const endDate = params.get('end_date') ?? 'yesterday'
  const limit = sanitizeLimit(params.get('limit'))

  try {
    const trend = await fetchGa4AttributionTrend({
      propertyId,
      startDate,
      endDate,
      limit,
    })

    return NextResponse.json({
      property_id: trend.propertyId,
      start_date: trend.startDate,
      end_date: trend.endDate,
      generated_at: trend.generatedAt,
      points: trend.points,
      available: true,
      warnings: [],
    })
  } catch (error) {
    console.error('GA4 attribution trend fetch failed:', error)
    return NextResponse.json({
      property_id: propertyId,
      start_date: startDate,
      end_date: endDate,
      generated_at: new Date().toISOString(),
      points: [],
      available: false,
      warnings: [error instanceof Error ? error.message : 'Attribution trend unavailable'],
    })
  }
}
