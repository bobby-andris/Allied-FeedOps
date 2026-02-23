import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getExistingFunnelTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeLimit,
  sanitizeMinImpressions,
  sanitizeOffset,
  sanitizeTierFilter,
  shouldShowErrorsOnly,
} from '@/lib/shopping-funnel/service'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const range = searchParams.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(searchParams.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(searchParams.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(searchParams.get('custom_label_0'))
    const tier = sanitizeTierFilter(searchParams.get('tier'))
    const showErrorsOnly = shouldShowErrorsOnly(searchParams.get('show_errors_only'))
    const minImpressions = sanitizeMinImpressions(searchParams.get('min_impressions'))
    const limit = sanitizeLimit(searchParams.get('limit'), 2000, 5000)
    const offset = sanitizeOffset(searchParams.get('offset'))
    const sortByRaw = searchParams.get('sort_by')
    const validExistingSorts = new Set(['impressions_desc', 'cost_desc', 'conversions_desc', 'search_asc', 'errors_first'])
    const sortBy = validExistingSorts.has(sortByRaw ?? '') ? sortByRaw as 'impressions_desc' | 'cost_desc' | 'conversions_desc' | 'search_asc' | 'errors_first' : 'errors_first'

    const result = await getExistingFunnelTerms({
      startDate,
      endDate,
      customLabel0,
      tier,
      showErrorsOnly,
      minImpressions,
      limit,
      offset,
      sortBy,
    })

    return NextResponse.json(result)
  } catch (error) {
    console.error('Existing funnel fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
