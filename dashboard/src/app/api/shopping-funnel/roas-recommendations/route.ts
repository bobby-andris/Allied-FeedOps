import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getLabelTierPerformance,
  sanitizeDateInput,
} from '@/lib/shopping-funnel/service'
import { buildRoasRecommendations } from '@/lib/optimization/control-center'

function sanitizeLimit(input: string | null, fallback = 200, max = 2000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate
    const limit = sanitizeLimit(params.get('limit'))

    const performance = await getLabelTierPerformance({
      startDate,
      endDate,
    })

    const recommendations = buildRoasRecommendations(
      performance.rows.map((row) => ({
        customLabel0: row.custom_label_0,
        tier: row.tier,
        spend: row.cost_micros / 1_000_000,
        conversionValue: row.conversions_value,
        conversions: row.conversions,
        clicks: row.clicks,
      }))
    ).slice(0, limit)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: performance.date_window,
      performance_rows: performance.total_rows,
      recommendation_count: recommendations.length,
      recommendations,
    })
  } catch (error) {
    console.error('Shopping funnel ROAS recommendations fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

