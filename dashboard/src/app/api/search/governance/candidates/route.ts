import { NextRequest, NextResponse } from 'next/server'
import { createAdminClient } from '@/lib/supabase/admin'
import {
  defaultDateWindow,
  getNeedsDecisionTerms,
  sanitizeCustomLabel,
  sanitizeDateInput,
  sanitizeMinImpressions,
} from '@/lib/shopping-funnel/service'
import { routeIntentDecision, evaluateSearchGovernance } from '@/lib/intent/policy'
import {
  buildSearchBuildoutSuggestion,
  summarizeSearchBuildoutClusters,
} from '@/lib/intent/buildout-intelligence'
import { extractErrorMessage, isMissingRelationError } from '@/lib/intent/persistence'
import type { IntentClass, SearchTier } from '@/lib/intent/types'

function sanitizeLimit(input: string | null, fallback = 300, max = 5000): number {
  const value = Number(input)
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }
  return Math.min(Math.floor(value), max)
}

function mapTierToGovernanceAction(recommendedTier: SearchTier): string {
  if (recommendedTier === 'exact') return 'promote_to_exact'
  if (recommendedTier === 'phrase') return 'promote_to_phrase'
  return 'graduate_shopping_to_search'
}

function normalizeConfidence(value: number | null | undefined): number {
  const numeric = Number(value ?? 0)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(1, numeric))
}

function normalizeIntentClass(value: unknown): IntentClass {
  switch (value) {
    case 'BRAND_CORE':
    case 'PRODUCT_HIGH':
    case 'CATEGORY_MID':
    case 'DISCOVERY_LOW':
    case 'COMPETITOR':
    case 'INFO_ASSIST':
    case 'MISMATCH':
    case 'RISK_POLICY':
      return value
    default:
      return 'CATEGORY_MID'
  }
}

export async function GET(request: NextRequest) {
  const warnings: string[] = []
  try {
    const params = request.nextUrl.searchParams
    const range = params.get('range')
    const fallbackWindow = defaultDateWindow(range)
    const startDate = sanitizeDateInput(params.get('start_date')) ?? fallbackWindow.startDate
    const endDate = sanitizeDateInput(params.get('end_date')) ?? fallbackWindow.endDate

    const customLabel0 = sanitizeCustomLabel(params.get('custom_label_0'))
    const minImpressions = sanitizeMinImpressions(params.get('min_impressions'))
    const limit = sanitizeLimit(params.get('limit'))
    const supabase = createAdminClient()

    type PersistedCandidateRow = {
      search_term: string
      custom_label_0: string | null
      recommended_search_tier: SearchTier
      confidence: number | null
      metadata: {
        intent_class?: string
        reason_codes?: string[]
        current_tier?: SearchTier
      } | null
    }

    try {
      const { data, error } = await supabase
        .from('search_buildout_recommendations')
        .select('search_term, custom_label_0, recommended_search_tier, confidence, metadata')
        .eq('status', 'candidate')
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) throw error

      const persistedRows = (data ?? []) as PersistedCandidateRow[]
      if (persistedRows.length > 0) {
        const candidates = persistedRows.map((row) => {
          const metadata = row.metadata ?? {}
          const reasonCodes = Array.isArray(metadata.reason_codes)
            ? metadata.reason_codes.filter((code): code is string => typeof code === 'string')
            : ['candidate_from_persisted_queue']
          const intentClass = normalizeIntentClass(metadata.intent_class)
          const confidence = normalizeConfidence(row.confidence)
          const action = mapTierToGovernanceAction(row.recommended_search_tier)
          const buildout = buildSearchBuildoutSuggestion({
            searchTerm: row.search_term,
            intentClass,
            recommendedTier: row.recommended_search_tier,
            confidence,
            reasonCodes,
          })

          return {
            search_term: row.search_term,
            custom_label_0s: row.custom_label_0 ? [{ custom_label_0: row.custom_label_0 }] : [],
            current_tier: metadata.current_tier ?? 'broad',
            metrics: {
              impressions: 0,
              clicks: 0,
              conversions: 0,
              conversionsValue: 0,
              costMicros: 0,
            },
            route_decision: {
              routeAction: 'search_exact_candidate',
              confidence,
              requiresReview: confidence < 0.75,
              reasonCodes,
              policyVersion: 'intent_v1',
              classification: {
                intentClass,
              },
            },
            governance: {
              action,
              recommendedTier: row.recommended_search_tier,
              confidence,
              reasonCodes,
              policyVersion: 'intent_v1',
            },
            buildout,
          }
        })

        const clusterSummaries = summarizeSearchBuildoutClusters(
          candidates.map((candidate) => candidate.buildout)
        )

        return NextResponse.json({
          generated_at: new Date().toISOString(),
          source: 'persisted',
          date_window: {
            startDate,
            endDate,
          },
          candidate_count: candidates.length,
          candidates,
          cluster_summaries: clusterSummaries,
          warnings,
        })
      }
    } catch (error) {
      if (isMissingRelationError(error, 'search_buildout_recommendations')) {
        warnings.push(
          'Table "search_buildout_recommendations" is missing. Falling back to computed candidates.'
        )
      } else {
        warnings.push(`Persisted Search candidate queue unavailable: ${extractErrorMessage(error)}`)
      }
    }

    const termsResult = await getNeedsDecisionTerms({
      startDate,
      endDate,
      customLabel0,
      minImpressions,
      limit,
      offset: 0,
      sortBy: 'impact_desc',
    })

    const candidates = termsResult.terms
      .map((term) => {
        const metrics = term.custom_label_0s.reduce(
          (acc, assignment) => {
            acc.impressions += assignment.impressions
            acc.clicks += assignment.clicks
            acc.conversions += assignment.conversions
            acc.conversionsValue += assignment.conversions_value
            acc.costMicros += assignment.cost_micros
            return acc
          },
          {
            impressions: 0,
            clicks: 0,
            conversions: 0,
            conversionsValue: 0,
            costMicros: 0,
          }
        )

        const routeDecision = routeIntentDecision({
          searchTerm: term.search_term,
          metrics,
          existingTerm: term,
        })

        const governance = evaluateSearchGovernance({
          searchTerm: term.search_term,
          currentTier: 'broad',
          metrics,
          confidence: routeDecision.confidence,
          classification: routeDecision.classification,
        })

        const recommendedTier = governance.recommendedTier ?? 'phrase'
        const buildout = buildSearchBuildoutSuggestion({
          searchTerm: term.search_term,
          intentClass: routeDecision.classification.intentClass,
          recommendedTier,
          confidence: governance.confidence,
          reasonCodes: governance.reasonCodes,
        })

        return {
          search_term: term.search_term,
          custom_label_0s: term.custom_label_0s,
          current_tier: 'broad' as SearchTier,
          metrics,
          route_decision: routeDecision,
          governance,
          buildout,
        }
      })
      .filter((item) => item.governance.action !== 'hold' && item.governance.action !== 'exclude')

    const clusterSummaries = summarizeSearchBuildoutClusters(
      candidates.map((candidate) => candidate.buildout)
    )

    return NextResponse.json({
      generated_at: new Date().toISOString(),
      source: 'computed',
      date_window: termsResult.date_window,
      candidate_count: candidates.length,
      candidates,
      cluster_summaries: clusterSummaries,
      warnings,
    })
  } catch (error) {
    console.error('Search governance candidate fetch failed:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error', warnings },
      { status: 500 }
    )
  }
}
