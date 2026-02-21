import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { buildGraduationBatch } from '@/lib/intent/graduation'
import type { GraduationWithHoldoutInput } from '@/lib/intent/graduation'
import type { IntentClassification, TermMetrics } from '@/lib/intent/types'
import { insertRowsSafe, extractErrorMessage } from '@/lib/intent/persistence'

interface GraduationTermPayload {
  search_term: string
  classification: IntentClassification
  metrics: Partial<TermMetrics>
  confidence?: number
  already_covered_in_search?: boolean
  attribution_quality_score?: number
  is_holdout?: boolean
}

interface GraduationRequestBody {
  terms?: GraduationTermPayload[]
  experiment_key?: string
  holdout_rate?: number
  created_by?: string
}

function coerceMetrics(input?: Partial<TermMetrics>): TermMetrics {
  return {
    impressions: Math.max(0, Number(input?.impressions ?? 0) || 0),
    clicks: Math.max(0, Number(input?.clicks ?? 0) || 0),
    conversions: Math.max(0, Number(input?.conversions ?? 0) || 0),
    conversionsValue: Math.max(0, Number(input?.conversionsValue ?? 0) || 0),
    costMicros: Math.max(0, Number(input?.costMicros ?? 0) || 0),
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as GraduationRequestBody
    const rawTerms = body.terms ?? []

    if (!Array.isArray(rawTerms) || rawTerms.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty terms array' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()
    const warnings: string[] = []

    // Map request payloads to graduation inputs
    const inputs: GraduationWithHoldoutInput[] = rawTerms.map((term) => ({
      searchTerm: term.search_term,
      classification: term.classification,
      metrics: coerceMetrics(term.metrics),
      confidence: Number(term.confidence ?? 0.5),
      alreadyCoveredInSearch: term.already_covered_in_search,
      attributionQualityScore: term.attribution_quality_score,
      isHoldout: term.is_holdout,
      experimentKey: body.experiment_key,
    }))

    // Evaluate batch
    const batchResult = buildGraduationBatch(
      inputs,
      body.experiment_key,
      body.holdout_rate
    )

    // Persist results to policy_action_execution_log
    const actionRows = batchResult.results.map((result) => ({
      action_type: 'graduation',
      search_term: result.searchTerm,
      custom_label_0: null,
      status: result.eligible ? 'planned' : 'skipped',
      policy_version: result.policyVersion,
      action_payload: {
        eligible: result.eligible,
        suggested_tier: result.suggestedTier,
        holdout_excluded: result.holdoutExcluded,
        experiment_key: result.experimentKey ?? null,
        reason_codes: result.reasonCodes,
      },
      reason_codes: result.reasonCodes,
      created_by: body.created_by ?? null,
    }))

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', actionRows)
    if (actionInsert.warning) warnings.push(actionInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      batch: batchResult,
      persisted: {
        policy_action_execution_log: actionInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Graduation evaluation failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}

export async function GET() {
  try {
    const supabase = createAdminClient()

    const { data, error } = await supabase
      .from('policy_action_execution_log')
      .select('*')
      .eq('action_type', 'graduation')
      .order('created_at', { ascending: false })
      .limit(100)

    if (error) {
      // Table may not exist yet
      return NextResponse.json({
        history: [],
        warning: 'Table may not exist yet. Apply latest migrations.',
      })
    }

    return NextResponse.json({
      history: data ?? [],
      count: data?.length ?? 0,
    })
  } catch (error) {
    console.error('Graduation history fetch failed:', error)
    return NextResponse.json(
      { error: extractErrorMessage(error) },
      { status: 500 }
    )
  }
}
