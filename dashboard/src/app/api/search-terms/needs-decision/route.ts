import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeLimit,
  sanitizeMinImpressions,
  sanitizeOffset,
} from '@/lib/shopping-funnel/service'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const range = searchParams.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(searchParams.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(searchParams.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(searchParams.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(searchParams.get('min_impressions'))
    const limit = sanitizeLimit(searchParams.get('limit'), 500, 3000)
    const offset = sanitizeOffset(searchParams.get('offset'))

    const result = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit,
      offset,
    })

    return NextResponse.json(result)
  } catch (error) {
    console.error('Needs decision fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
