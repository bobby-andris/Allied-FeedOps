import { NextRequest, NextResponse } from 'next/server'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { buildRecommendationQueue } from '@/lib/optimization/control-center'
import { createAdminClient } from '@/lib/supabase/admin'

function sanitizeLimit(input: string | null, fallback = 100, max = 1000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams
    const action = params.get('action')

    // --- History query ---
    if (action === 'history') {
      const supabase = createAdminClient()
      const { data, error } = await supabase
        .from('routing_recommendations')
        .select('*')
        .in('review_status', ['accepted', 'rejected'])
        .order('accepted_at', { ascending: false, nullsFirst: false })
        .order('created_at', { ascending: false })
        .limit(200)

      if (error) {
        console.error('Failed to fetch recommendation history:', error)
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      return NextResponse.json({ history: data })
    }

    // --- Statuses query ---
    if (action === 'statuses') {
      const supabase = createAdminClient()
      const { data, error } = await supabase
        .from('routing_recommendations')
        .select('search_term, custom_label_0, review_status, accepted_at, accepted_by, metadata')
        .order('created_at', { ascending: false })

      if (error) {
        console.error('Failed to fetch recommendation statuses:', error)
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      return NextResponse.json({ statuses: data })
    }

    // --- Default: recommendation queue (existing behavior) ---
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(params.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(params.get('min_impressions'))
    const limit = sanitizeLimit(params.get('limit'))

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit: 3000,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const queue = buildRecommendationQueue(termsResult.terms, limit)

    const actionDistribution = queue.reduce<Record<string, number>>((acc, item) => {
      acc[item.actionType] = (acc[item.actionType] ?? 0) + 1
      return acc
    }, {})

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      date_window: termsResult.date_window,
      total_terms_evaluated: termsResult.total_count,
      queue_count: queue.length,
      action_distribution: actionDistribution,
      queue,
    })
  } catch (error) {
    console.error('Shopping funnel recommendations fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

// ---- POST handler: approve / reject / undo / batch_approve ----

interface ApprovePayload {
  action: 'approve'
  searchTerm: string
  customLabel0: string
  recommendedTier: string
  currentTier: string
  confidence: number
  impact: { low: number; mid: number; high: number }
  recommendedAction?: string
}

interface RejectPayload {
  action: 'reject'
  searchTerm: string
  customLabel0: string
  reason?: string
}

interface UndoPayload {
  action: 'undo'
  searchTerm: string
  customLabel0: string
}

interface BatchApprovePayload {
  action: 'batch_approve'
  terms: Array<{
    searchTerm: string
    customLabel0: string
    recommendedTier: string
    currentTier: string
    confidence: number
    impact: { low: number; mid: number; high: number }
  }>
}

interface LabelBlockPayload {
  action: 'label_block'
  customLabel0: string
  metadata?: Record<string, unknown>
}

interface IdentifySearchCandidatesPayload {
  action: 'identify_search_candidates'
}

type ActionPayload = ApprovePayload | RejectPayload | UndoPayload | BatchApprovePayload | LabelBlockPayload | IdentifySearchCandidatesPayload

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as ActionPayload
    const supabase = createAdminClient()

    switch (body.action) {
      case 'approve': {
        const now = new Date().toISOString()
        const recAction = body.recommendedAction ?? 'funnel'
        const { data, error } = await supabase
          .from('routing_recommendations')
          .upsert(
            {
              search_term: body.searchTerm,
              custom_label_0: body.customLabel0,
              recommended_action: recAction,
              recommended_tier: body.recommendedTier,
              confidence: body.confidence,
              review_status: 'accepted',
              accepted: true,
              accepted_at: now,
              accepted_by: 'operator',
              metadata: {
                currentTier: body.currentTier,
                impact: body.impact,
                history: [{ action: 'approved', at: now }],
              },
            },
            { onConflict: 'search_term,custom_label_0' }
          )
          .select()

        if (error) {
          console.error('Approve failed:', error)
          return NextResponse.json({ error: error.message }, { status: 500 })
        }

        return NextResponse.json({ ok: true, record: data?.[0] ?? null })
      }

      case 'reject': {
        const now = new Date().toISOString()
        const metadata: Record<string, unknown> = {
          history: [{ action: 'rejected', at: now }],
        }
        if (body.reason) {
          metadata.rejection_reason = body.reason
        }

        const { data, error } = await supabase
          .from('routing_recommendations')
          .upsert(
            {
              search_term: body.searchTerm,
              custom_label_0: body.customLabel0,
              recommended_action: 'funnel',
              review_status: 'rejected',
              accepted: false,
              confidence: 0,
              metadata,
            },
            { onConflict: 'search_term,custom_label_0' }
          )
          .select()

        if (error) {
          console.error('Reject failed:', error)
          return NextResponse.json({ error: error.message }, { status: 500 })
        }

        return NextResponse.json({ ok: true, record: data?.[0] ?? null })
      }

      case 'undo': {
        const now = new Date().toISOString()

        // First fetch existing metadata to append history
        const { data: existing } = await supabase
          .from('routing_recommendations')
          .select('metadata')
          .eq('search_term', body.searchTerm)
          .eq('custom_label_0', body.customLabel0)
          .single()

        const existingMeta = (existing?.metadata as Record<string, unknown>) ?? {}
        const existingHistory = Array.isArray(existingMeta.history)
          ? existingMeta.history
          : []

        const { data, error } = await supabase
          .from('routing_recommendations')
          .update({
            review_status: 'pending',
            accepted: false,
            accepted_at: null,
            accepted_by: null,
            metadata: {
              ...existingMeta,
              history: [...existingHistory, { action: 'undone', at: now }],
            },
          })
          .eq('search_term', body.searchTerm)
          .eq('custom_label_0', body.customLabel0)
          .select()

        if (error) {
          console.error('Undo failed:', error)
          return NextResponse.json({ error: error.message }, { status: 500 })
        }

        if (!data || data.length === 0) {
          return NextResponse.json(
            { error: 'No matching recommendation found to undo' },
            { status: 404 }
          )
        }

        return NextResponse.json({ ok: true, record: data[0] })
      }

      case 'batch_approve': {
        if (!body.terms || body.terms.length === 0) {
          return NextResponse.json(
            { error: 'batch_approve requires a non-empty terms array' },
            { status: 400 }
          )
        }

        const now = new Date().toISOString()
        const rows = body.terms.map((term) => ({
          search_term: term.searchTerm,
          custom_label_0: term.customLabel0,
          recommended_action: 'funnel' as const,
          recommended_tier: term.recommendedTier,
          confidence: term.confidence,
          review_status: 'accepted' as const,
          accepted: true,
          accepted_at: now,
          accepted_by: 'operator',
          metadata: {
            currentTier: term.currentTier,
            impact: term.impact,
            history: [{ action: 'approved', at: now }],
          },
        }))

        const { data, error } = await supabase
          .from('routing_recommendations')
          .upsert(rows, { onConflict: 'search_term,custom_label_0' })
          .select()

        if (error) {
          console.error('Batch approve failed:', error)
          return NextResponse.json({ error: error.message }, { status: 500 })
        }

        return NextResponse.json({
          ok: true,
          approved_count: data?.length ?? 0,
          records: data,
        })
      }

      case 'label_block': {
        if (!body.customLabel0) {
          return NextResponse.json(
            { error: 'customLabel0 required' },
            { status: 400 }
          )
        }

        const now = new Date().toISOString()
        const { error } = await supabase
          .from('routing_recommendations')
          .upsert(
            {
              search_term: '__LABEL_BLOCK__',
              custom_label_0: body.customLabel0,
              recommended_action: 'label_block',
              action_scope: 'label',
              review_status: 'accepted',
              accepted: true,
              accepted_at: now,
              accepted_by: 'dashboard_user',
              confidence: 1.0,
              metadata: {
                ...(body.metadata ?? {}),
                history: [{ action: 'label_block', at: now, by: 'dashboard_user' }],
              },
            },
            { onConflict: 'search_term,custom_label_0' }
          )

        if (error) {
          console.error('Label block failed:', error)
          return NextResponse.json({ error: error.message }, { status: 500 })
        }

        return NextResponse.json({
          success: true,
          action: 'label_block',
          customLabel0: body.customLabel0,
        })
      }

      case 'identify_search_candidates': {
        // Find high-ROAS, high-volume terms from query_value_scores
        const { data: candidates, error: fetchError } = await supabase
          .from('query_value_scores')
          .select('search_term, custom_label_0, model_inputs')
          .not('model_inputs', 'is', null)

        if (fetchError) {
          console.error('Search candidate fetch failed:', fetchError)
          return NextResponse.json({ error: fetchError.message }, { status: 500 })
        }

        // Filter candidates: ROAS > 3.0, impressions > 100, conversions > 0
        const searchCandidates = (candidates || [])
          .filter((c) => {
            const inputs = c.model_inputs as Record<string, unknown> | null
            if (!inputs) return false
            const roas = Number(inputs.actualRoas ?? 0)
            const impressions = Number(inputs.totalImpressions ?? 0)
            const conversions = Number(inputs.totalConversions ?? 0)
            return roas > 3.0 && impressions > 100 && conversions > 0
          })
          .map((c) => ({
            search_term: c.search_term,
            custom_label_0: c.custom_label_0,
            recommended_search_tier: 'exact' as const,
            status: 'candidate',
            confidence: 0.8,
            metadata: {
              source: 'tier_scoring_engine',
              identified_at: new Date().toISOString(),
            },
          }))

        if (searchCandidates.length > 0) {
          const { error: insertError } = await supabase
            .from('search_buildout_recommendations')
            .upsert(searchCandidates, { onConflict: 'search_term' })

          if (insertError) {
            console.error('Search candidate insert failed:', insertError)
            return NextResponse.json({ error: insertError.message }, { status: 500 })
          }
        }

        return NextResponse.json({
          success: true,
          candidateCount: searchCandidates.length,
        })
      }

      default:
        return NextResponse.json(
          { error: `Unknown action: ${(body as { action: string }).action}` },
          { status: 400 }
        )
    }
  } catch (error) {
    console.error('Recommendations POST failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
