import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import { classifyIntent } from '@/lib/intent/taxonomy'
import { evaluateGuardrails, evaluateSearchGovernance } from '@/lib/intent/policy'
import { extractErrorMessage, insertRowsSafe, isMissingRelationError } from '@/lib/intent/persistence'
import type { SearchTier } from '@/lib/intent/types'

interface MovementTerm {
  search_term: string
  custom_label_0?: string | null
  current_tier: SearchTier
  metrics: {
    impressions?: number
    clicks?: number
    conversions?: number
    conversionsValue?: number
    costMicros?: number
  }
  confidence?: number
  attribution_quality_score?: number
}

interface MovementRequestBody {
  terms?: MovementTerm[]
  created_by?: string
  source_limit?: number
  attribution_quality_score?: number
}

interface SearchBuildoutRecommendationRow {
  search_term: string
  custom_label_0: string | null
  confidence: number | null
  metadata: {
    current_tier?: SearchTier
    metrics?: MovementTerm['metrics']
  } | null
}

function sanitizeLimit(input: number | undefined, fallback = 250, max = 2000): number {
  if (input == null) return fallback
  const numeric = Number(input)
  if (!Number.isFinite(numeric) || numeric <= 0) return fallback
  return Math.min(Math.floor(numeric), max)
}

function normalizeTier(value: unknown): SearchTier {
  if (value === 'exact' || value === 'phrase' || value === 'broad') {
    return value
  }
  return 'broad'
}

function normalizeConfidence(value: number | null | undefined, fallback = 0.55): number {
  const numeric = Number(value ?? fallback)
  if (!Number.isFinite(numeric)) return fallback
  return Math.max(0, Math.min(1, numeric))
}

function coerceMetrics(input: MovementTerm['metrics']) {
  return {
    impressions: Math.max(0, Number(input.impressions ?? 0) || 0),
    clicks: Math.max(0, Number(input.clicks ?? 0) || 0),
    conversions: Math.max(0, Number(input.conversions ?? 0) || 0),
    conversionsValue: Math.max(0, Number(input.conversionsValue ?? 0) || 0),
    costMicros: Math.max(0, Number(input.costMicros ?? 0) || 0),
  }
}

async function loadTermsFromApprovedQueue(limit: number): Promise<{
  terms: MovementTerm[]
  warnings: string[]
}> {
  const warnings: string[] = []
  const supabase = createAdminClient()
  try {
    const { data, error } = await supabase
      .from('search_buildout_recommendations')
      .select('search_term, custom_label_0, confidence, metadata')
      .eq('status', 'approved')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) throw error

    const rows = (data ?? []) as SearchBuildoutRecommendationRow[]
    const terms = rows.map((row) => ({
      search_term: row.search_term,
      custom_label_0: row.custom_label_0,
      current_tier: normalizeTier(row.metadata?.current_tier),
      metrics: coerceMetrics(row.metadata?.metrics ?? {}),
      confidence: normalizeConfidence(row.confidence),
    }))

    return { terms, warnings }
  } catch (error) {
    if (isMissingRelationError(error, 'search_buildout_recommendations')) {
      warnings.push(
        'Table "search_buildout_recommendations" is missing. Provide explicit movement terms in the request body.'
      )
    } else {
      warnings.push(`Unable to load approved Search buildout recommendations: ${extractErrorMessage(error)}`)
    }
    return { terms: [], warnings }
  }
}

async function evaluateRolloutSafety(attributionQualityScore?: number): Promise<{
  status: 'go' | 'hold' | 'blocked'
  reason_codes: string[]
  incidents: Array<{
    ruleId: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    message: string
    suggestedAction: string
  }>
  open_critical_incidents: number
  open_high_incidents: number
  stale_data_hours: number
  warnings: string[]
}> {
  const warnings: string[] = []
  const supabase = createAdminClient()

  let openCriticalIncidents = 0
  let openHighIncidents = 0
  try {
    const { data, error } = await supabase
      .from('guardrail_incidents')
      .select('severity, status')
      .in('status', ['open', 'acknowledged'])
      .order('created_at', { ascending: false })
      .limit(200)

    if (error) throw error

    const rows = (data ?? []) as Array<{ severity: 'low' | 'medium' | 'high' | 'critical' }>
    openCriticalIncidents = rows.filter((row) => row.severity === 'critical').length
    openHighIncidents = rows.filter((row) => row.severity === 'high').length
  } catch (error) {
    if (isMissingRelationError(error, 'guardrail_incidents')) {
      warnings.push('Table "guardrail_incidents" is missing. Rollout safety will default to conservative hold logic.')
      openHighIncidents = 3
    } else {
      warnings.push(`Unable to evaluate open guardrail incidents: ${extractErrorMessage(error)}`)
      openHighIncidents = 3
    }
  }

  let staleDataHours = 0
  try {
    const { data, error } = await supabase
      .from('query_value_scores')
      .select('created_at')
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) throw error

    if (data?.created_at) {
      const ageMs = Date.now() - new Date(data.created_at).getTime()
      staleDataHours = Math.max(0, ageMs / (1000 * 60 * 60))
    }
  } catch (error) {
    if (isMissingRelationError(error, 'query_value_scores')) {
      warnings.push('Table "query_value_scores" is missing. Data freshness checks are degraded.')
      staleDataHours = 25
    } else {
      warnings.push(`Unable to evaluate query-value freshness: ${extractErrorMessage(error)}`)
      staleDataHours = 25
    }
  }

  const decision = evaluateGuardrails({
    recentSpend: 0,
    recentRevenue: 0,
    baselineSpend: 0,
    baselineRevenue: 0,
    attributionQualityScore,
    staleDataHours,
    openCriticalIncidents,
    openHighIncidents,
  })

  return {
    status: decision.status,
    reason_codes: decision.reasonCodes,
    incidents: decision.incidents,
    open_critical_incidents: openCriticalIncidents,
    open_high_incidents: openHighIncidents,
    stale_data_hours: Number(staleDataHours.toFixed(2)),
    warnings,
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json().catch(() => ({}))) as MovementRequestBody

    let terms = body.terms ?? []
    const warnings: string[] = []

    if (body.terms != null && !Array.isArray(body.terms)) {
      return NextResponse.json(
        { error: 'Request body field "terms" must be an array when provided' },
        { status: 400 }
      )
    }

    if (terms.length === 0) {
      const fallback = await loadTermsFromApprovedQueue(sanitizeLimit(body.source_limit))
      terms = fallback.terms
      warnings.push(...fallback.warnings)
    }

    if (terms.length === 0) {
      const rolloutSafety = await evaluateRolloutSafety(body.attribution_quality_score)
      warnings.push(...rolloutSafety.warnings)
      return NextResponse.json({
        generated_at: new Date().toISOString(),
        generated_count: 0,
        staged_count: 0,
        cancelled_count: 0,
        decisions: [],
        persisted: {
          policy_decision_log: 0,
          policy_action_execution_log: 0,
        },
        rollout_safety: {
          status: rolloutSafety.status,
          reason_codes: rolloutSafety.reason_codes,
          incidents: rolloutSafety.incidents,
          open_critical_incidents: rolloutSafety.open_critical_incidents,
          open_high_incidents: rolloutSafety.open_high_incidents,
          stale_data_hours: rolloutSafety.stale_data_hours,
        },
        warnings,
      })
    }

    const decisions = terms.map((term) => {
      const classification = classifyIntent(term.search_term)
      const metrics = coerceMetrics(term.metrics)
      const decision = evaluateSearchGovernance({
        searchTerm: term.search_term,
        currentTier: term.current_tier,
        metrics,
        confidence: Number(term.confidence ?? 0.55),
        classification,
        attributionQualityScore: term.attribution_quality_score,
      })

      return {
        search_term: term.search_term,
        custom_label_0: term.custom_label_0 ?? null,
        current_tier: term.current_tier,
        decision,
      }
    })

    const rolloutSafety = await evaluateRolloutSafety(body.attribution_quality_score)
    warnings.push(...rolloutSafety.warnings)

    const supabase = createAdminClient()

    const decisionRows = decisions.map((item) => ({
      search_term: item.search_term,
      custom_label_0: item.custom_label_0,
      decision_type: 'search_tier_movement',
      channel: 'search',
      policy_version: item.decision.policyVersion,
      decision_payload: {
        current_tier: item.current_tier,
        action: item.decision.action,
        recommended_tier: item.decision.recommendedTier,
      },
      confidence: item.decision.confidence,
      requires_review: item.decision.action !== 'hold',
      created_by: body.created_by ?? null,
    }))

    const shouldCancelActions = rolloutSafety.status !== 'go'
    const actionRows = decisions
      .filter((item) => item.decision.action !== 'hold')
      .map((item) => ({
        action_type: 'search_tier_movement',
        search_term: item.search_term,
        custom_label_0: item.custom_label_0,
        status: shouldCancelActions ? 'cancelled' : 'planned',
        policy_version: item.decision.policyVersion,
        action_payload: {
          current_tier: item.current_tier,
          recommended_tier: item.decision.recommendedTier,
          action: item.decision.action,
          rollout_safety_status: rolloutSafety.status,
        },
        reason_codes: shouldCancelActions
          ? [...item.decision.reasonCodes, `rollout_safety_${rolloutSafety.status}`]
          : item.decision.reasonCodes,
        created_by: body.created_by ?? null,
      }))

    const operatorAuditRows = decisions
      .filter((item) => item.decision.action !== 'hold')
      .map((item) => ({
        queue_name: 'search_governance_movements',
        entity_key: item.search_term,
        action: item.decision.action,
        before_state: {
          current_tier: item.current_tier,
          recommended_tier: item.decision.recommendedTier ?? null,
          rollout_safety_status: rolloutSafety.status,
        },
        after_state: {
          selected_action: shouldCancelActions ? 'cancel_due_to_rollout_safety' : item.decision.action,
          selected_tier: shouldCancelActions ? item.current_tier : item.decision.recommendedTier ?? null,
          recommended_action: item.decision.action,
          recommended_tier: item.decision.recommendedTier ?? null,
          execution_status: shouldCancelActions ? 'cancelled' : 'staged',
        },
        actor: body.created_by ?? null,
      }))

    const decisionInsert = await insertRowsSafe(supabase, 'policy_decision_log', decisionRows)
    if (decisionInsert.warning) warnings.push(decisionInsert.warning)

    const actionInsert = await insertRowsSafe(supabase, 'policy_action_execution_log', actionRows)
    if (actionInsert.warning) warnings.push(actionInsert.warning)

    const operatorAuditInsert = await insertRowsSafe(supabase, 'operator_review_audit', operatorAuditRows)
    if (operatorAuditInsert.warning) warnings.push(operatorAuditInsert.warning)

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      generated_count: decisions.length,
      staged_count: shouldCancelActions ? 0 : actionRows.length,
      cancelled_count: shouldCancelActions ? actionRows.length : 0,
      decisions,
      persisted: {
        policy_decision_log: decisionInsert.inserted,
        policy_action_execution_log: actionInsert.inserted,
        operator_review_audit: operatorAuditInsert.inserted,
      },
      rollout_safety: {
        status: rolloutSafety.status,
        reason_codes: rolloutSafety.reason_codes,
        incidents: rolloutSafety.incidents,
        open_critical_incidents: rolloutSafety.open_critical_incidents,
        open_high_incidents: rolloutSafety.open_high_incidents,
        stale_data_hours: rolloutSafety.stale_data_hours,
      },
      warnings,
    })
  } catch (error) {
    console.error('Search governance movement evaluation failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
