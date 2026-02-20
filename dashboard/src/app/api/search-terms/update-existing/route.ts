import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { updateExistingAssignments } from '@/lib/shopping-funnel/service'
import type { ExistingFunnelUpdate } from '@/lib/shopping-funnel/types'

interface UpdateExistingRequest {
  updates?: ExistingFunnelUpdate[]
  start_date?: string
  end_date?: string
}

async function logUpdateErrors(results: Awaited<ReturnType<typeof updateExistingAssignments>>['results']) {
  const failures = results.filter((result) => result.status === 'error' && result.error)
  if (failures.length === 0) {
    return
  }

  try {
    const supabase = createAdminClient()
    await supabase.from('google_ads_api_errors').insert(
      failures.map((failure) => ({
        search_term: failure.search_term,
        action_attempted: `${failure.custom_label_0} | update-existing`,
        error_message: failure.error ?? 'Unknown error',
        error_code: failure.error_code ?? null,
        retry_count: failure.retry_count ?? 0,
      }))
    )
  } catch (error) {
    console.error('Failed to write update errors to Supabase:', error)
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as UpdateExistingRequest
    const updates = body.updates ?? []

    if (!Array.isArray(updates) || updates.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty updates array' },
        { status: 400 }
      )
    }

    const response = await updateExistingAssignments(updates, {
      startDate: body.start_date,
      endDate: body.end_date,
    })

    await logUpdateErrors(response.results)
    return NextResponse.json(response)
  } catch (error) {
    console.error('Updating existing assignments failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
