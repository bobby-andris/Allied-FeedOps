import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { postDecisions } from '@/lib/shopping-funnel/service'
import type { PostDecisionItem } from '@/lib/shopping-funnel/types'

interface PostDecisionsRequest {
  decisions?: PostDecisionItem[]
  start_date?: string
  end_date?: string
}

async function logPostingErrors(results: Awaited<ReturnType<typeof postDecisions>>['results']) {
  const failures = results.filter((result) => result.status === 'error' && result.error)
  if (failures.length === 0) {
    return
  }

  try {
    const supabase = createAdminClient()
    await supabase.from('google_ads_api_errors').insert(
      failures.map((failure) => ({
        search_term: failure.search_term,
        action_attempted: failure.actions_completed.join(' | ') || 'post-decisions',
        error_message: failure.error ?? 'Unknown error',
        error_code: failure.error_code ?? null,
        retry_count: failure.retry_count ?? 0,
      }))
    )
  } catch (error) {
    console.error('Failed to write posting errors to Supabase:', error)
  }
}

async function markPostedRows(results: Awaited<ReturnType<typeof postDecisions>>['results']) {
  const successfulTerms = results
    .filter((result) => result.status === 'success')
    .map((result) => result.search_term)

  if (successfulTerms.length === 0) {
    return
  }

  try {
    const supabase = createAdminClient()
    await supabase
      .from('search_term_decisions')
      .update({
        posted_to_google_ads: true,
        posted_at: new Date().toISOString(),
      })
      .in('search_term', successfulTerms)
      .eq('posted_to_google_ads', false)
  } catch (error) {
    console.error('Failed to mark staged decisions as posted:', error)
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as PostDecisionsRequest
    const decisions = body.decisions ?? []

    if (!Array.isArray(decisions) || decisions.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty decisions array' },
        { status: 400 }
      )
    }

    const response = await postDecisions(decisions, {
      startDate: body.start_date,
      endDate: body.end_date,
    })

    await logPostingErrors(response.results)
    await markPostedRows(response.results)
    return NextResponse.json(response)
  } catch (error) {
    console.error('Posting decisions failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
