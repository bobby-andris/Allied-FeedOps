import { NextRequest, NextResponse } from 'next/server'
import { fetchGa4CampaignPerformance, getCanonicalGa4PropertyId } from '@/lib/ga4/client'

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
    const result = await fetchGa4CampaignPerformance(options)
    return NextResponse.json(result)
  } catch (error) {
    console.error('GA4 campaign performance fetch failed:', error)
    const message = error instanceof Error ? error.message : 'GA4 campaign performance unavailable'
    return NextResponse.json({
      propertyId,
      startDate,
      endDate,
      rows: [],
      generatedAt: new Date().toISOString(),
      available: false,
      warnings: [message],
    })
  }
}
