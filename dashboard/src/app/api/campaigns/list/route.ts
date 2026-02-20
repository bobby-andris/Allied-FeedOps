import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getFunnelCampaignList,
  sanitizeDateInput,
  SHOPPING_FUNNEL_CACHE_TTL_MS,
  SHOPPING_FUNNEL_DATA_SOURCE,
} from '@/lib/shopping-funnel/service'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const fallbackWindow = defaultDateWindow(searchParams.get('range'))
    const startDate = sanitizeDateInput(searchParams.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(searchParams.get('end_date')) ?? fallbackWindow.endDate

    const campaigns = await getFunnelCampaignList({ startDate, endDate })
    return NextResponse.json({
      campaigns,
      campaign_count: campaigns.length,
      data_source: SHOPPING_FUNNEL_DATA_SOURCE,
      generated_at: new Date().toISOString(),
      cache_ttl_ms: SHOPPING_FUNNEL_CACHE_TTL_MS,
    })
  } catch (error) {
    console.error('Fetching campaign list failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
