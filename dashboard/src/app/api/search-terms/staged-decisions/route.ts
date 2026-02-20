import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  buildStagedDecisionSnapshots,
  type SearchTermDecisionRow,
} from '@/lib/shopping-funnel/staging-snapshots'

interface StagedDecisionsRequest {
  search_terms?: string[]
}

const MAX_SEARCH_TERMS_FILTER = 200

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

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as StagedDecisionsRequest
    const searchTerms = normalizeSearchTerms(body.search_terms)
    const searchTermSet = new Set(searchTerms)
    const useQueryFilter = searchTerms.length > 0 && searchTerms.length <= MAX_SEARCH_TERMS_FILTER
    const supabase = createAdminClient()

    let stagedQuery = supabase
      .from('search_term_decisions')
      .select('search_term, action_type, custom_label_0, tier, created_at')
      .eq('posted_to_google_ads', false)
      .order('created_at', { ascending: false })

    if (useQueryFilter) {
      stagedQuery = stagedQuery.in('search_term', searchTerms)
    }

    const { data: stagedRows, error: stagedError } = await stagedQuery
    if (stagedError) {
      throw stagedError
    }

    const { data: totalRows, error: totalError } = await supabase
      .from('search_term_decisions')
      .select('search_term')
      .eq('posted_to_google_ads', false)

    if (totalError) {
      throw totalError
    }

    let snapshots = buildStagedDecisionSnapshots((stagedRows ?? []) as SearchTermDecisionRow[])
    if (!useQueryFilter && searchTermSet.size > 0) {
      snapshots = snapshots.filter((snapshot) => searchTermSet.has(snapshot.search_term))
    }
    const totalUnpostedTerms = new Set((totalRows ?? []).map((row) => row.search_term)).size

    return NextResponse.json({
      decisions: snapshots,
      staged_term_count: snapshots.length,
      total_unposted_terms: totalUnpostedTerms,
    })
  } catch (error) {
    console.error('Fetching staged decisions failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
