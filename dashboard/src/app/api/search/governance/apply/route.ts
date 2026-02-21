import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'

interface ApplyCandidate {
  search_term: string
  custom_label_0?: string | null
  recommended_tier: 'broad' | 'phrase' | 'exact'
  confidence: number
  reason_codes?: string[]
}

interface ApplyRequestBody {
  candidates?: ApplyCandidate[]
  created_by?: string
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as ApplyRequestBody
    const candidates = body.candidates ?? []

    if (!Array.isArray(candidates) || candidates.length === 0) {
      return NextResponse.json(
        { error: 'Request must include a non-empty candidates array' },
        { status: 400 }
      )
    }

    const supabase = createAdminClient()
    const warnings: string[] = []
    let dedupedNegativeCount = 0

    const recommendationRows = candidates.map((candidate) => ({
      search_term: candidate.search_term,
      custom_label_0: candidate.custom_label_0 ?? null,
      recommended_search_tier: candidate.recommended_tier,
      status: 'approved',
      confidence: Math.max(0, Math.min(1, Number(candidate.confidence) || 0)),
      metadata: {
        reason_codes: candidate.reason_codes ?? [],
      },
      approved_by: body.created_by ?? null,
      approved_at: new Date().toISOString(),
    }))

    const negativeRows = candidates.map((candidate) => ({
      term: candidate.search_term,
      scope: 'cross_channel',
      source_policy: 'intent_v1',
      confidence: Math.max(0, Math.min(1, Number(candidate.confidence) || 0)),
      reason_codes: candidate.reason_codes ?? ['search_graduation_conflict_prevention'],
      rollback_token: `rollback:${candidate.search_term}`,
      active: true,
      metadata: {
        recommended_search_tier: candidate.recommended_tier,
      },
      created_by: body.created_by ?? null,
    }))

    const actionRows = candidates.map((candidate) => ({
      action_type: 'search_governance_apply',
      search_term: candidate.search_term,
      custom_label_0: candidate.custom_label_0 ?? null,
      status: 'planned',
      policy_version: 'intent_v1',
      action_payload: {
        recommended_search_tier: candidate.recommended_tier,
      },
      reason_codes: candidate.reason_codes ?? ['search_governance_apply'],
      created_by: body.created_by ?? null,
    }))

    const operatorAuditRows = candidates.map((candidate) => ({
      queue_name: 'search_governance',
      entity_key: candidate.search_term,
      action: 'approve_candidate',
      before_state: {
        recommended_tier: candidate.recommended_tier,
        confidence: Math.max(0, Math.min(1, Number(candidate.confidence) || 0)),
        reason_codes: candidate.reason_codes ?? [],
      },
      after_state: {
        selected_action: 'approve_candidate',
        selected_tier: candidate.recommended_tier,
        recommended_action: 'approve_candidate',
        recommended_tier: candidate.recommended_tier,
        status: 'approved',
      },
      actor: body.created_by ?? null,
    }))

    const candidateTerms = Array.from(
      new Set(
        candidates
          .map((candidate) => candidate.search_term)
          .filter((term): term is string => typeof term === 'string' && term.trim().length > 0)
      )
    )

    let existingActiveNegativeTerms = new Set<string>()
    if (candidateTerms.length > 0) {
      const { data, error } = await supabase
        .from('negative_registry')
        .select('term')
        .eq('scope', 'cross_channel')
        .eq('active', true)
        .in('term', candidateTerms)

      if (error) {
        if (isMissingRelationError(error, 'negative_registry')) {
          warnings.push('Table "negative_registry" is missing. Cross-channel negative dedupe was skipped.')
        } else {
          throw error
        }
      } else {
        existingActiveNegativeTerms = new Set(
          ((data as Array<{ term: string }> | null) ?? [])
            .map((row) => row.term)
            .filter((term): term is string => typeof term === 'string' && term.trim().length > 0)
        )
      }
    }

    const dedupedNegativeRows = negativeRows.filter((row) => !existingActiveNegativeTerms.has(row.term))
    dedupedNegativeCount = negativeRows.length - dedupedNegativeRows.length

    const recoInsert = await insertRowsSafe(supabase, 'search_buildout_recommendations', recommendationRows)
    if (recoInsert.warning) warnings.push(recoInsert.warning)

    const negativeInsert = await insertRowsSafe(supabase, 'negative_registry', dedupedNegativeRows)
    if (negativeInsert.warning) warnings.push(negativeInsert.warning)

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', actionRows)
    if (actionInsert.warning) warnings.push(actionInsert.warning)

    const operatorAuditInsert = await insertRowsSafe(supabase, 'operator_review_audit', operatorAuditRows)
    if (operatorAuditInsert.warning) warnings.push(operatorAuditInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      applied_count: candidates.length,
      deduped_negative_count: dedupedNegativeCount,
      persisted: {
        search_buildout_recommendations: recoInsert.inserted,
        negative_registry: negativeInsert.inserted,
        policy_action_execution_log: actionInsert.inserted,
        operator_review_audit: operatorAuditInsert.inserted,
      },
      warnings,
    })
  } catch (error) {
    console.error('Applying search governance candidates failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
