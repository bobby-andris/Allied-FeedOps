import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { postDecisions } from '@/lib/shopping-funnel/service'
import { toPostDecisionItem } from '@/lib/shopping-funnel/decision-staging'
import {
  buildStagedDecisionSnapshots,
  type SearchTermDecisionRow,
} from '@/lib/shopping-funnel/staging-snapshots'

interface PostStagedRequest {
  search_terms?: string[]
  start_date?: string
  end_date?: string
}

function normalizeSearchTerms(input: unknown): string[] {
  if (!Array.isArray(input)) {
    return []
  }
  return Array.from(
    new Set(
      input
        .filter((value): value is string => typeof value === 'string')
        .map((value) => value.trim())
        .filter((value) => value.length > 0)
    )
  )
}

async function logPostingErrors(results: Awaited<ReturnType<typeof postDecisions>>['results']) {
  const failures = results.filter((result) => result.status === 'error' && result.error)
  if (failures.length === 0) {
    return
  }

  const supabase = createAdminClient()
  await supabase.from('google_ads_api_errors').insert(
    failures.map((failure) => ({
      search_term: failure.search_term,
      action_attempted: failure.actions_completed.join(' | ') || 'post-staged',
      error_message: failure.error ?? 'Unknown error',
      error_code: failure.error_code ?? null,
      retry_count: failure.retry_count ?? 0,
    }))
  )
}

async function markPostedRows(results: Awaited<ReturnType<typeof postDecisions>>['results']) {
  const successfulTerms = results
    .filter((result) => result.status === 'success')
    .map((result) => result.search_term)

  if (successfulTerms.length === 0) {
    return
  }

  const supabase = createAdminClient()
  await supabase
    .from('search_term_decisions')
    .update({
      posted_to_google_ads: true,
      posted_at: new Date().toISOString(),
    })
    .in('search_term', successfulTerms)
    .eq('posted_to_google_ads', false)
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as PostStagedRequest
    const searchTerms = normalizeSearchTerms(body.search_terms)
    const supabase = createAdminClient()

    let stagedQuery = supabase
      .from('search_term_decisions')
      .select('search_term, action_type, custom_label_0, tier, created_at')
      .eq('posted_to_google_ads', false)
      .order('created_at', { ascending: false })

    if (searchTerms.length > 0) {
      stagedQuery = stagedQuery.in('search_term', searchTerms)
    }

    const { data: stagedRows, error: stagedError } = await stagedQuery
    if (stagedError) {
      throw stagedError
    }

    const snapshots = buildStagedDecisionSnapshots((stagedRows ?? []) as SearchTermDecisionRow[])
    if (snapshots.length === 0) {
      return NextResponse.json(
        { error: 'No staged decisions are available to post.' },
        { status: 400 }
      )
    }

    const decisions = snapshots.map(toPostDecisionItem)
    const response = await postDecisions(decisions, {
      startDate: body.start_date,
      endDate: body.end_date,
    })

    await logPostingErrors(response.results)
    await markPostedRows(response.results)

    return NextResponse.json({
      ...response,
      staged_term_count: snapshots.length,
    })
  } catch (error) {
    console.error('Posting staged decisions failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
