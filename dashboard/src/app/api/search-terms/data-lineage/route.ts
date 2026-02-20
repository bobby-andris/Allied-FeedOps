import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getShoppingFunnelDataLineage,
  sanitizeDateInput,
} from '@/lib/shopping-funnel/service'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const range = searchParams.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(searchParams.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(searchParams.get('end_date')) ?? fallbackWindow.endDate

    const result = await getShoppingFunnelDataLineage({
      startDate,
      endDate,
    })

    return NextResponse.json(result)
  } catch (error) {
    console.error('Shopping funnel data lineage fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
