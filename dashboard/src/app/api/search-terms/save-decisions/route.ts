import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import type { AssignmentTier, DecisionActionType, SaveDecisionItem } from '@/lib/shopping-funnel/types'

interface SaveDecisionsRequest {
  decisions?: SaveDecisionItem[]
  created_by?: string
}

interface SaveDecisionRow {
  search_term: string
  action_type: DecisionActionType
  custom_label_0: string | null
  tier: AssignmentTier | null
  source_campaign: string | null
  source_tier: string | null
  impressions: number | null
  clicks: number | null
  cost_micros: number | null
  conversions: number | null
  conversions_value: number | null
  created_by: string | null
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as SaveDecisionsRequest
    const decisions = body.decisions ?? []

    if (!Array.isArray(decisions) || decisions.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty decisions array' },
        { status: 400 }
      )
    }

    const rows: SaveDecisionRow[] = decisions.flatMap((decision): SaveDecisionRow[] => {
      if (decision.action_type === 'funnel' && (decision.assignments?.length ?? 0) > 0) {
        return decision.assignments!.map((assignment) => ({
          search_term: decision.search_term,
          action_type: decision.action_type,
          custom_label_0: assignment.custom_label_0,
          tier: assignment.tier,
          source_campaign: decision.source_campaign ?? null,
          source_tier: decision.source_tier ?? null,
          impressions: decision.impressions ?? null,
          clicks: decision.clicks ?? null,
          cost_micros: decision.cost_micros ?? null,
          conversions: decision.conversions ?? null,
          conversions_value: decision.conversions_value ?? null,
          created_by: body.created_by ?? null,
        }))
      }

      return [
        {
          search_term: decision.search_term,
          action_type: decision.action_type,
          custom_label_0: null,
          tier: null,
          source_campaign: decision.source_campaign ?? null,
          source_tier: decision.source_tier ?? null,
          impressions: decision.impressions ?? null,
          clicks: decision.clicks ?? null,
          cost_micros: decision.cost_micros ?? null,
          conversions: decision.conversions ?? null,
          conversions_value: decision.conversions_value ?? null,
          created_by: body.created_by ?? null,
        },
      ]
    })

    const supabase = createAdminClient()
    const uniqueTerms = Array.from(new Set(rows.map((row) => row.search_term)))

    if (uniqueTerms.length > 0) {
      const { error: deleteError } = await supabase
        .from('search_term_decisions')
        .delete()
        .eq('posted_to_google_ads', false)
        .in('search_term', uniqueTerms)
      if (deleteError) {
        throw deleteError
      }
    }

    const { error: insertError } = await supabase.from('search_term_decisions').insert(rows)
    if (insertError) {
      throw insertError
    }

    return NextResponse.json({
      success: true,
      saved_count: rows.length,
      staged_term_count: uniqueTerms.length,
    })
  } catch (error) {
    console.error('Saving decisions failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
